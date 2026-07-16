"""Integration platform router — Nango adapter layer.

Preserves the same API contract as the original custom integration platform,
but proxies all operations to Nango. Nango handles OAuth flows, token refresh,
credential encryption, and the provider catalog.

This adapter synthesizes fields Nango doesn't natively track (app_category,
capabilities, channel_key) from a static metadata mapping.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app import config
from app.models import (
    AuthMode,
    ConnectionStatus,
    IntegrationProvider,
    IntegrationConnection,
    IntegrationConnectionCreate,
    IntegrationCredentials,
    OAuthCredentialsUpdate,
)
from app import nango_client
from app.nango_provider_meta import get_app_category, get_capabilities, get_channel_key
from pydantic import BaseModel, Field

logger = logging.getLogger("mem_dog.routers.integrations")

router = APIRouter(prefix="/api/v1/integrations", tags=["Integrations"])


class ConnectSessionCreate(BaseModel):
    """Start a Nango Connect session for host-driven OAuth."""
    provider_key: str = Field(..., min_length=1)
    user_id: Optional[str] = Field(
        None,
        description="End-user id for Nango; defaults to the authenticated md_* / JWT user.",
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_platform_key(request: Request) -> None:
    """When API_KEY is set, only the global platform key may mutate OAuth app credentials."""
    if not config.API_KEY:
        return
    if getattr(request.state, "auth_type", None) != "global":
        raise HTTPException(
            status_code=403,
            detail="Provider OAuth credentials require the platform API key",
        )


def _resolve_user_scope(request: Request, explicit_user_id: Optional[str] = None) -> Optional[str]:
    """Scope connections to the caller for md_*/JWT; allow platform filter/all.

    - ``per_user`` / ``jwt``: always the authenticated user; reject cross-user explicit ids.
    - ``global`` / open (no API_KEY): optional ``explicit_user_id``, else None (all).
    """
    auth_type = getattr(request.state, "auth_type", None)
    caller = getattr(request.state, "user_id", None)
    explicit = (explicit_user_id or "").strip() or None

    if auth_type in ("per_user", "jwt"):
        if not caller:
            raise HTTPException(status_code=401, detail="Authentication required")
        if explicit and explicit != caller:
            raise HTTPException(
                status_code=403,
                detail="Cannot access another user's integration connections",
            )
        return caller

    return explicit


def _connection_owner_id(nango_conn: Dict[str, Any]) -> str:
    end_user = nango_conn.get("end_user", {})
    if isinstance(end_user, dict):
        return str(end_user.get("id") or "").strip()
    return ""


def _assert_connection_access(request: Request, nango_conn: Dict[str, Any]) -> None:
    """Forbid md_*/JWT callers from touching another user's connection."""
    auth_type = getattr(request.state, "auth_type", None)
    if auth_type not in ("per_user", "jwt"):
        return
    caller = getattr(request.state, "user_id", None)
    if not caller:
        raise HTTPException(status_code=401, detail="Authentication required")
    owner = _connection_owner_id(nango_conn)
    if owner != caller:
        raise HTTPException(status_code=404, detail="Connection not found")


# Known auth modes from Nango provider templates (built-in knowledge).
# The GET /config list response doesn't include auth_mode, so we infer it.
_NANGO_OAUTH_PROVIDERS = {
    "slack", "discord", "github", "gitlab", "google", "google-calendar",
    "google-drive", "google-mail", "google-sheets", "microsoft-teams",
    "outlook", "salesforce", "hubspot", "jira", "asana", "zoom", "shopify",
    "quickbooks", "zendesk", "dropbox", "linkedin", "twitter", "facebook",
    "instagram", "reddit", "notion", "airtable", "trello", "pipedrive",
    "bamboohr", "front", "basecamp", "bitbucket", "monday", "clickup",
    "todoist", "square", "paypal", "freshdesk", "box", "netlify", "contentful",
    "stripe",  # Stripe uses OAuth2 in Nango
}
_NANGO_API_KEY_PROVIDERS = {
    "openai", "anthropic", "sendgrid", "mailgun", "datadog", "sentry",
    "pagerduty", "linear", "brex", "apollo",
}
_NANGO_BASIC_PROVIDERS = {
    "amplitude", "affinity", "ashby",
}


def _nango_to_provider(nango_config: Dict[str, Any]) -> IntegrationProvider:
    """Map a Nango integration config to our IntegrationProvider model."""
    key = nango_config.get("unique_key", nango_config.get("provider_config_key", ""))
    provider_name = nango_config.get("provider", key)

    # Determine auth_mode — prefer explicit value, fall back to template knowledge
    auth_mode_raw = nango_config.get("auth_mode", "").upper()
    if auth_mode_raw:
        auth_mode_map = {
            "OAUTH2": AuthMode.OAUTH2, "OAUTH1": AuthMode.OAUTH2,
            "API_KEY": AuthMode.API_KEY, "BASIC": AuthMode.BASIC,
            "APP": AuthMode.OAUTH2, "CUSTOM": AuthMode.API_KEY,
            "NONE": AuthMode.NONE,
        }
        auth_mode = auth_mode_map.get(auth_mode_raw, AuthMode.NONE)
    elif provider_name in _NANGO_OAUTH_PROVIDERS:
        auth_mode = AuthMode.OAUTH2
    elif provider_name in _NANGO_API_KEY_PROVIDERS:
        auth_mode = AuthMode.API_KEY
    elif provider_name in _NANGO_BASIC_PROVIDERS:
        auth_mode = AuthMode.BASIC
    else:
        auth_mode = AuthMode.OAUTH2  # default assumption

    # Nango doesn't expose oauth_client_id in GET responses (encrypted).
    # If the integration exists in Nango, treat OAuth as configured —
    # the user set credentials via the Configure flow (PUT /oauth-credentials).
    # Providers seeded with placeholders ("CONFIGURE_VIA_UI") are detected below.
    oauth_client_id = nango_config.get("oauth_client_id", "")
    if auth_mode == AuthMode.API_KEY:
        oauth_configured = True
    elif oauth_client_id and oauth_client_id not in ("CONFIGURE_ME", "CONFIGURE_VIA_UI", ""):
        oauth_configured = True
    else:
        # Provider exists in Nango but Nango hides the client_id.
        # Default to True since the provider was created via the config API.
        oauth_configured = True

    proxy = nango_config.get("proxy")
    proxy_base_url = proxy.get("base_url", "") if isinstance(proxy, dict) else ""

    return IntegrationProvider(
        provider_key=key,
        display_name=nango_config.get("display_name") or provider_name.replace("-", " ").title(),
        description=nango_config.get("description") or "",
        logo_url=nango_config.get("logo_url") or "",
        category=get_app_category(key),
        app_category=get_app_category(key),
        capabilities=get_capabilities(key),
        channel_key=get_channel_key(key),
        auth_mode=auth_mode,
        authorization_url=nango_config.get("authorization_url") or "",
        token_url=nango_config.get("token_url") or "",
        scope=nango_config.get("scope") or "",
        proxy_base_url=proxy_base_url or "",
        config=nango_config.get("custom") or {},
        is_enabled=True,
        oauth_configured=oauth_configured,
        created_at=nango_config.get("created_at"),
        updated_at=nango_config.get("updated_at"),
    )


def _nango_to_connection(nango_conn: Dict[str, Any]) -> IntegrationConnection:
    """Map a Nango connection to our IntegrationConnection model."""
    # Nango connection health
    health = nango_conn.get("health", {})
    status_raw = health.get("status", "connected") if isinstance(health, dict) else "connected"
    status_map = {
        "connected": ConnectionStatus.ACTIVE,
        "error": ConnectionStatus.ERROR,
        "disconnected": ConnectionStatus.REVOKED,
    }
    status = status_map.get(status_raw, ConnectionStatus.ACTIVE)

    end_user = nango_conn.get("end_user", {})
    user_id = end_user.get("id", "") if isinstance(end_user, dict) else ""

    metadata = nango_conn.get("metadata", {}) or {}

    return IntegrationConnection(
        connection_id=str(nango_conn.get("id", nango_conn.get("connection_id", ""))),
        user_id=user_id,
        provider_key=nango_conn.get("provider_config_key", nango_conn.get("provider", "")),
        display_name=metadata.get("display_name"),
        account_id=metadata.get("account_id"),
        account_email=metadata.get("account_email"),
        status=status,
        status_message=health.get("error") if isinstance(health, dict) else None,
        scopes=nango_conn.get("credentials", {}).get("scope") if isinstance(nango_conn.get("credentials"), dict) else None,
        metadata=metadata,
        created_at=nango_conn.get("created_at"),
        updated_at=nango_conn.get("updated_at"),
    )


# =============================================================================
# App Categories (static — Nango doesn't have this concept)
# =============================================================================

APP_CATEGORIES = [
    {"key": "chat", "label": "Chat", "count": 25},
    {"key": "messaging", "label": "Messaging", "count": 13},
    {"key": "email", "label": "Email", "count": 20},
    {"key": "video", "label": "Video & Meetings", "count": 13},
    {"key": "social", "label": "Social Media", "count": 18},
    {"key": "crm", "label": "CRM & Sales", "count": 16},
    {"key": "productivity", "label": "Productivity", "count": 24},
    {"key": "devtools", "label": "Dev Tools", "count": 24},
    {"key": "cloud", "label": "Cloud & Storage", "count": 21},
    {"key": "finance", "label": "Finance", "count": 19},
    {"key": "support", "label": "Customer Support", "count": 8},
    {"key": "hr", "label": "HR & People", "count": 12},
    {"key": "data-ai", "label": "Data & AI", "count": 30},
    {"key": "commerce", "label": "Commerce & Content", "count": 19},
    {"key": "business-ops", "label": "Operations", "count": 65},
]


@router.get("/app-categories")
async def list_app_categories() -> List[Dict[str, Any]]:
    """List the 15 unified app categories."""
    return APP_CATEGORIES


# =============================================================================
# Providers (backed by Nango integrations)
# =============================================================================

@router.get("/providers", response_model=List[IntegrationProvider])
async def list_providers(
    category: Optional[str] = Query(None, description="Filter by legacy category"),
    app_category: Optional[str] = Query(None, description="Filter by app category"),
    enabled_only: bool = Query(True, description="Only return enabled providers"),
) -> List[IntegrationProvider]:
    """List all integration providers from Nango."""
    try:
        configs = await nango_client.list_integrations()
        providers = [_nango_to_provider(c) for c in configs]

        if category:
            providers = [p for p in providers if p.category == category]
        if app_category:
            providers = [p for p in providers if p.app_category == app_category]

        providers.sort(key=lambda p: (p.app_category, p.display_name))
        return providers
    except Exception as exc:
        logger.exception("list_providers failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/providers/{provider_key}", response_model=IntegrationProvider)
async def get_provider(provider_key: str) -> IntegrationProvider:
    """Get a single provider from Nango."""
    try:
        config_data = await nango_client.get_integration(provider_key)
        if not config_data:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_key}")
        return _nango_to_provider(config_data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get_provider failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/providers/{provider_key}/oauth-credentials", response_model=IntegrationProvider)
async def set_oauth_credentials(
    provider_key: str, body: OAuthCredentialsUpdate, request: Request
) -> IntegrationProvider:
    """Set OAuth client credentials on a Nango integration (platform key only)."""
    _require_platform_key(request)
    try:
        await nango_client.update_integration(provider_key, {
            "oauth_client_id": body.client_id,
            "oauth_client_secret": body.client_secret,
        })
        config_data = await nango_client.get_integration(provider_key)
        if not config_data:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_key}")
        provider = _nango_to_provider(config_data)
        # Nango doesn't expose oauth_client_id in GET, so force true after successful PUT
        if body.client_id:
            provider.oauth_configured = True
        return provider
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("set_oauth_credentials failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/providers/{provider_key}/oauth-credentials", response_model=IntegrationProvider)
async def clear_oauth_credentials(provider_key: str, request: Request) -> IntegrationProvider:
    """Clear OAuth client credentials from a Nango integration (platform key only)."""
    _require_platform_key(request)
    try:
        await nango_client.update_integration(provider_key, {
            "oauth_client_id": "",
            "oauth_client_secret": "",
        })
        config_data = await nango_client.get_integration(provider_key)
        if not config_data:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_key}")
        return _nango_to_provider(config_data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("clear_oauth_credentials failed")
        raise HTTPException(status_code=500, detail=str(exc))


# =============================================================================
# Connections (backed by Nango connections)
# =============================================================================

@router.get("/connections", response_model=List[IntegrationConnection])
async def list_connections(
    request: Request,
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    provider_key: Optional[str] = Query(None, description="Filter by provider"),
) -> List[IntegrationConnection]:
    """List connections from Nango.

    Workspace ``md_*`` / JWT keys are auto-scoped to the key owner. Platform key
    may pass ``user_id`` or omit it to list all (admin / gateway).
    """
    scoped_user = _resolve_user_scope(request, user_id)
    try:
        nango_conns = await nango_client.list_connections(end_user_id=scoped_user)
        connections = [_nango_to_connection(c) for c in nango_conns]

        if provider_key:
            connections = [c for c in connections if c.provider_key == provider_key]

        return connections
    except Exception as exc:
        logger.exception("list_connections failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/connections/{connection_id}", response_model=IntegrationConnection)
async def get_connection(connection_id: str, request: Request) -> IntegrationConnection:
    """Get a single connection from Nango."""
    try:
        nango_conn = await nango_client.get_connection(connection_id)
        if not nango_conn:
            raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
        _assert_connection_access(request, nango_conn)
        return _nango_to_connection(nango_conn)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get_connection failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(connection_id: str, request: Request) -> None:
    """Delete a connection in Nango."""
    try:
        nango_conn = await nango_client.get_connection(connection_id)
        if not nango_conn:
            raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
        _assert_connection_access(request, nango_conn)
        await nango_client.delete_connection(connection_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("delete_connection failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/connections/api-key", response_model=IntegrationConnection)
async def create_api_key_connection(
    body: IntegrationConnectionCreate, request: Request
) -> IntegrationConnection:
    """Create an API-key connection in Nango."""
    if not body.api_key:
        raise HTTPException(status_code=400, detail="api_key is required for API key connections")

    # Force end_user to the authenticated workspace user when using md_*/JWT
    scoped_user = _resolve_user_scope(request, body.user_id)
    if not scoped_user:
        raise HTTPException(status_code=400, detail="user_id is required")
    body.user_id = scoped_user

    try:
        result = await nango_client.create_connection({
            "connection_id": f"conn-{body.user_id}-{body.provider_key}",
            "provider_config_key": body.provider_key,
            "credentials": {
                "apiKey": body.api_key,
            },
            "connection_config": {},
            "metadata": {
                "display_name": body.display_name or body.provider_key,
                "account_id": body.account_id or "",
                "account_email": body.account_email or "",
            },
            "end_user": {
                "id": body.user_id,
            },
        })

        # Fetch the created connection to get full details
        conn_id = result.get("id", result.get("connection_id", ""))
        nango_conn = await nango_client.get_connection(
            str(conn_id),
            provider_config_key=body.provider_key,
        )
        if nango_conn:
            return _nango_to_connection(nango_conn)

        # Fallback: construct response from what we have
        return IntegrationConnection(
            connection_id=str(conn_id),
            user_id=body.user_id,
            provider_key=body.provider_key,
            display_name=body.display_name or body.provider_key,
            account_id=body.account_id,
            account_email=body.account_email,
            status=ConnectionStatus.ACTIVE,
            created_at=_now_iso(),
            updated_at=_now_iso(),
        )
    except Exception as exc:
        logger.exception("create_api_key_connection failed")
        raise HTTPException(status_code=500, detail=str(exc))


# =============================================================================
# OAuth2 Flow (Nango handles the full flow)
# =============================================================================

@router.get("/oauth/authorize/{provider_key}")
async def get_oauth_authorize_url(
    request: Request,
    provider_key: str,
    user_id: Optional[str] = Query(None, description="mem-dog user ID (defaults to auth user)"),
    redirect_uri: str = Query("", description="OAuth callback URI (unused, Nango handles callback)"),
    scopes: Optional[str] = Query(None, description="Override default scopes"),
) -> Dict[str, str]:
    """Generate an OAuth2 authorization URL via Nango's direct OAuth flow."""
    resolved_user = _resolve_user_scope(request, user_id)
    if not resolved_user:
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        # Nango's self-hosted OAuth flow: browser redirects to /oauth/connect/<provider>
        nango_url = nango_client.NANGO_API_URL.rstrip("/")
        server_url = os.getenv("NANGO_SERVER_URL", nango_url)
        public_key = os.getenv("NANGO_PUBLIC_KEY", "")
        authorize_url = (
            f"{server_url}/oauth/connect/{provider_key}"
            f"?connection_id={resolved_user}"
            f"&public_key={public_key}"
        )
        if scopes:
            authorize_url += f"&params={{\"scopes\":\"{scopes}\"}}"
        return {"authorize_url": authorize_url, "state": resolved_user}
    except Exception as exc:
        logger.exception("get_oauth_authorize_url failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/oauth/connect-session")
async def create_oauth_connect_session(
    body: ConnectSessionCreate, request: Request
) -> Dict[str, Any]:
    """Create a Nango Connect session token/URL for host-driven OAuth UX."""
    resolved_user = _resolve_user_scope(request, body.user_id)
    if not resolved_user:
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        session = await nango_client.create_connect_session(
            end_user_id=resolved_user,
            provider_config_key=body.provider_key,
        )
        return {
            "user_id": resolved_user,
            "provider_key": body.provider_key,
            "token": session.get("token") or session.get("data", {}).get("token"),
            "connect_link": (
                session.get("connect_link")
                or session.get("connect_url")
                or session.get("data", {}).get("connect_link")
            ),
            "raw": session,
        }
    except Exception as exc:
        logger.exception("create_oauth_connect_session failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query("", description="Authorization code (handled by Nango)"),
    state: str = Query("", description="OAuth state (handled by Nango)"),
) -> Dict[str, str]:
    """OAuth callback — Nango handles this internally.

    This endpoint is kept for backward compatibility but the actual callback
    is handled by Nango. If called directly, it returns a success message.
    """
    return {
        "status": "ok",
        "message": "OAuth callback handled by Nango. Check connections for the new connection.",
    }


@router.post("/oauth/refresh/{connection_id}", response_model=IntegrationConnection)
async def refresh_connection(connection_id: str, request: Request) -> IntegrationConnection:
    """Refresh OAuth tokens — Nango auto-refreshes, so this verifies health."""
    try:
        nango_conn = await nango_client.get_connection(connection_id)
        if not nango_conn:
            raise HTTPException(status_code=404, detail=f"Connection not found: {connection_id}")
        _assert_connection_access(request, nango_conn)
        return _nango_to_connection(nango_conn)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("refresh_connection failed")
        raise HTTPException(status_code=500, detail=str(exc))


# =============================================================================
# Internal: Credential Access (from Nango)
# =============================================================================

@router.get("/connections/{connection_id}/credentials", response_model=IntegrationCredentials)
async def get_credentials(connection_id: str, request: Request) -> IntegrationCredentials:
    """Get decrypted credentials from Nango (scoped to connection owner for md_*/JWT)."""
    try:
        nango_conn = await nango_client.get_connection(
            connection_id,
            include_credentials=True,
        )
        if not nango_conn:
            raise HTTPException(status_code=404, detail=f"Credentials not found for: {connection_id}")
        _assert_connection_access(request, nango_conn)

        creds = nango_conn.get("credentials", {})
        return IntegrationCredentials(
            connection_id=connection_id,
            access_token=creds.get("access_token"),
            refresh_token=creds.get("refresh_token"),
            api_key=creds.get("apiKey") or creds.get("api_key"),
            token_type=creds.get("token_type", "bearer"),
            expires_at=creds.get("expires_at"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("get_credentials failed")
        raise HTTPException(status_code=500, detail=str(exc))

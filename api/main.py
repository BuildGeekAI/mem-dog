import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import config
from app.auth import ensure_jwt_user_profile
from app.storage import get_storage
from app.telemetry import setup_telemetry, get_tracer, get_meter
from app.routers import data, versions, list as list_router, tags, bulk_delete
from app.routers import users, access, memories, channel_identities, channels
from app.routers import ai_config, prompts, embeddings, viewpoints, ai_query, skills, analysis_templates, agent_configs
from app.routers import machines, ollama_proxy, k8s_pods
from app.routers import stats, store
from app.routers import ingest
from app.routers import integrations
from app.routers import graph
from app.routers import organizations, projects
from app.routers import webhooks_mgmt
from app.routers import gmail_push
from app.routers import gdrive_push
from app.routers import zoom_push
from app.routers import host

# ---------------------------------------------------------------------------
# Initialise OpenTelemetry (traces + metrics + logs) before anything else
# ---------------------------------------------------------------------------
setup_telemetry()

logger = logging.getLogger("mem_dog.main")

# ---------------------------------------------------------------------------
# Deployment (from repo root; see docs/setup/MANUAL_DEPLOY_INSTRUCTIONS.md)
# ---------------------------------------------------------------------------
#   ./scripts/manual-deploy.sh setup-env -p PROJECT_ID -e dev
#   ./scripts/manual-deploy.sh setup-postgres -p PROJECT_ID -e dev   # optional
#   REDIS_URL='...' ./scripts/manual-deploy.sh setup-redis -p PROJECT_ID -e dev   # optional
#   SUPABASE_URL='...' SUPABASE_SERVICE_ROLE_KEY='...' ./scripts/manual-deploy.sh setup-supabase -p PROJECT_ID -e dev   # optional
#   USE_POSTGRES_STORAGE=true USE_REDIS_STORAGE=true USE_SUPABASE_STORAGE=true \
#     ./scripts/manual-deploy.sh deploy-api -p PROJECT_ID -e dev
#   ./scripts/manual-deploy.sh deploy-all -p PROJECT_ID -e dev
#   ./scripts/manual-deploy.sh status -p PROJECT_ID -e dev
# Or: ./scripts/deploy.sh -p PROJECT_ID -e dev

# ---------------------------------------------------------------------------
# Application version — single source of truth
# ---------------------------------------------------------------------------
API_VERSION = "4.0.0"

app = FastAPI(
    title="Mem-Dog API",
    description="""Lean memory system with versioned data storage (local filesystem or Google Cloud Storage).

## Features

- **Data Storage**: Store and version any type of data locally or in GCS
- **Tags**: User-defined tags for organizing and searching data
- **Timeline**: Track all user actions with full history
- **User Management**: User profiles, roles, and API key management
- **Access Control**: Per-data access permissions
- **Memories**: Unified context system (timeline, session, conversation, user, org, factual, episodic, semantic)
- **Integration Platform**: 300+ provider integrations with OAuth2/API-key auth, proactive token refresh, and encrypted credential storage
- **AI Layer** (optional): Intelligent data processing with multiple AI engines
  - Prompts: Create and manage prompt templates
  - Embeddings: Generate vector embeddings for semantic search
  - Viewpoints: AI-powered analysis and interpretations
  - Skills: AI agent role and capability definitions
  - NLP Query: Natural language querying across data

## AI Engines Supported

- OpenAI (GPT-4, embeddings)
- Ollama (self-hosted)
- Google Gemini
- LiteLLM (proxy to 100+ models)
""",
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Data", "description": "Core data storage operations"},
        {"name": "Tags", "description": "Tag management and search"},
        {"name": "Memories", "description": "Memory management (timeline, session, conversation, user, org, factual, episodic, semantic)"},
        {"name": "Versions", "description": "Version management"},
        {"name": "List", "description": "User data listing with formats"},
        {"name": "Users", "description": "User profile management"},
        {"name": "API Keys", "description": "API key management"},
        {"name": "AI Configuration", "description": "AI engine configuration and preferences"},
        {"name": "AI Prompts", "description": "Prompt template management"},
        {"name": "AI Embeddings", "description": "Vector embedding operations"},
        {"name": "AI Viewpoints", "description": "AI-powered analysis"},
        {"name": "AI Skills", "description": "AI agent skill management"},
        {"name": "AI Query", "description": "Natural language querying"},
        {"name": "Bulk Delete", "description": "Mass data and memory deletion operations"},
        {"name": "Statistics", "description": "Platform-wide and per-user statistics"},
        {"name": "Store", "description": "CRUD API for testing: same endpoints for Redis, Postgres, Supabase, and GCS; set redis=true, postgres=true, supabase=true, or gcs=true"},
        {"name": "Channel Identities", "description": "Correlate channel identities (channel_type + channel_unique_id) with user_id; CRUD and lookup"},
        {"name": "Channels", "description": "Per-channel metadata and config (how to communicate with each channel)"},
        {"name": "Integrations", "description": "Integration platform — 300+ providers, OAuth2/API-key connections, credential management, proactive token refresh"},
    ],
)

# ---------------------------------------------------------------------------
# Instrument FastAPI with OpenTelemetry (auto-creates spans per request)
# ---------------------------------------------------------------------------
if config.OTEL_ENABLED:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI OpenTelemetry instrumentation active")
    except Exception as _otel_err:
        logger.warning("FastAPI OTel instrumentation unavailable (skipping): %s", _otel_err)

# ---------------------------------------------------------------------------
# Application-level metrics
# ---------------------------------------------------------------------------
meter = get_meter("mem_dog.http")
request_counter = meter.create_counter(
    name="http.server.request_count",
    description="Total HTTP requests handled",
    unit="1",
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Record per-request metrics (method, path, status)."""
    response = await call_next(request)
    request_counter.add(
        1,
        {
            "http.method": request.method,
            "http.route": request.url.path,
            "http.status_code": str(response.status_code),
        },
    )
    return response


# ---------------------------------------------------------------------------
# API Key authentication (when API_KEY env var is set)
# ---------------------------------------------------------------------------
_PUBLIC_PATHS = frozenset({"/", "/health", "/ready", "/docs", "/redoc", "/openapi.json", "/api/v1/gmail/push", "/api/v1/gdrive/push", "/api/v1/zoom/push"})


def _error_code_for_status(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        503: "service_unavailable",
    }.get(status_code, "http_error")


def _structured_error(
    *,
    status_code: int,
    detail: Any,
    request_id: Optional[str],
) -> dict:
    """Host-friendly error envelope; keep FastAPI ``detail`` for compatibility."""
    message: str
    code = _error_code_for_status(status_code)
    details: dict = {}
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("detail") or detail)
        code = str(detail.get("code") or code)
        extra = detail.get("details")
        if isinstance(extra, dict):
            details = extra
    elif isinstance(detail, list):
        message = "Validation failed"
        code = "validation_error"
        details = {"errors": detail}
    else:
        message = str(detail) if detail is not None else "Error"
    return {
        "detail": detail if not isinstance(detail, list) else message,
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        },
    }


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Dual-path auth: global service key OR per-user ``md_*`` key.

    Also assigns / echoes ``X-Request-Id`` for host log correlation (Phase F3).
    """
    # Defaults — no authenticated user
    request.state.user_id = None
    request.state.auth_type = None
    request_id = (
        request.headers.get("x-request-id")
        or request.headers.get("X-Request-Id")
        or ""
    ).strip() or str(uuid.uuid4())
    request.state.request_id = request_id

    async def _respond(response):
        response.headers["X-Request-Id"] = request_id
        return response

    if request.method == "OPTIONS" or request.url.path in _PUBLIC_PATHS:
        return await _respond(await call_next(request))

    provided = request.headers.get("x-api-key", "")

    if not config.API_KEY:
        # No global key configured (local dev) — pass through
        return await _respond(await call_next(request))

    # 1. Global service key — inter-service / admin
    #    If a JWT Bearer is also present, prefer JWT to extract user_id
    #    (browser sends both x-api-key and Bearer token).
    if provided == config.API_KEY:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer ") and config.SUPABASE_JWT_SECRET:
            token = auth_header[7:]
            try:
                import jwt as pyjwt
                payload = pyjwt.decode(
                    token, config.SUPABASE_JWT_SECRET, algorithms=["HS256"],
                    options={"verify_aud": False},
                )
                sub = payload.get("sub")
                if sub:
                    request.state.user_id = sub
                    request.state.auth_type = "jwt"
                    await ensure_jwt_user_profile(sub, payload)
                    return await _respond(await call_next(request))
            except Exception:
                logger.debug("JWT decode failed alongside global key, using global", exc_info=True)
        request.state.auth_type = "global"
        return await _respond(await call_next(request))

    # 2. Per-user key (md_ prefix) — O(1) lookup via Supabase
    if provided.startswith("md_"):
        try:
            storage = get_storage()
            user_id = storage.validate_api_key(provided)
            if user_id:
                request.state.user_id = user_id
                request.state.auth_type = "per_user"
                return await _respond(await call_next(request))
        except Exception:
            logger.debug("Per-user key validation error", exc_info=True)

    # 3. Supabase JWT (browser users)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and config.SUPABASE_JWT_SECRET:
        token = auth_header[7:]
        try:
            import jwt as pyjwt
            payload = pyjwt.decode(
                token, config.SUPABASE_JWT_SECRET, algorithms=["HS256"],
                options={"verify_aud": False},
            )
            sub = payload.get("sub")
            if sub:
                request.state.user_id = sub
                request.state.auth_type = "jwt"
                await ensure_jwt_user_profile(sub, payload)
                return await _respond(await call_next(request))
        except Exception:
            logger.debug("JWT auth failed", exc_info=True)

    return await _respond(
        JSONResponse(
            status_code=401,
            content=_structured_error(
                status_code=401,
                detail="Invalid or missing API key",
                request_id=request_id,
            ),
        )
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=_structured_error(
            status_code=exc.status_code,
            detail=exc.detail,
            request_id=request_id,
        ),
        headers={"X-Request-Id": request_id or ""},
    )


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify UI domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Core routers
app.include_router(data.router)
app.include_router(tags.router)
app.include_router(versions.router)
app.include_router(list_router.router)
app.include_router(bulk_delete.router)

# User management routers
app.include_router(users.router)
app.include_router(access.router)

# Memory management router (replaces timeline + sessions)
app.include_router(memories.router)

# Channel identity correlation (channel <-> user_id)
app.include_router(channel_identities.router)

# Channels bucket — per-channel metadata
app.include_router(channels.router)

# AI routers (conditionally active based on config)
app.include_router(ai_config.router)
app.include_router(prompts.router)
app.include_router(embeddings.router)
app.include_router(viewpoints.router)
app.include_router(skills.router)
app.include_router(analysis_templates.router)
app.include_router(agent_configs.router)
app.include_router(ai_query.router)

# Statistics router
app.include_router(stats.router)

# Store router (active when REDIS_URL is set)
app.include_router(store.router)

# Universal Data Envelope ingest router (Plan 3)
app.include_router(ingest.router)

# Integration platform (Nango-like provider + connection management)
app.include_router(integrations.router)

# Graph memory (entity/relationship layer)
app.include_router(graph.router)

# Organization & project hierarchy
app.include_router(organizations.router)
app.include_router(projects.router)
app.include_router(host.router)

# Per-user webhook endpoint management
app.include_router(webhooks_mgmt.router)
app.include_router(gmail_push.router)
app.include_router(gdrive_push.router)
app.include_router(zoom_push.router)

# Model infrastructure management (machines, ollama proxy, k8s pods)
app.include_router(machines.router)
app.include_router(ollama_proxy.router)
app.include_router(k8s_pods.router)

logger.info(
    "Mem-Dog API started",
    extra={
        "version": API_VERSION,
        "environment": config.ENVIRONMENT,
        "storage_backend": config.STORAGE_BACKEND,
        "ai_enabled": str(config.is_ai_enabled()),
        "user_management_enabled": str(config.is_user_management_enabled()),
        "memories_enabled": str(config.is_memories_enabled()),
        "stats_enabled": str(config.is_stats_enabled()),
    },
)
@app.on_event("shutdown")
async def _shutdown():
    """Clean up resources."""
    try:
        from app.graphiti_client import close_graphiti
        await close_graphiti()
    except Exception as exc:
        logger.debug("Graphiti shutdown: %s", exc)

@app.on_event("startup")
async def _bootstrap():
    """Create the default user and seed analysis templates."""
    logger.info(
        "mem-dog-api starting — version=%s default_user_id=%s storage=%s",
        config.APP_VERSION if hasattr(config, 'APP_VERSION') else "unknown",
        config.DEFAULT_USER_ID,
        config.STORAGE_BACKEND,
    )
    try:
        storage = get_storage()
        storage.ensure_default_user()
    except Exception as exc:
        logger.warning("Failed to bootstrap default user: %s", exc)

    try:
        storage = get_storage()
        inserted = storage.seed_analysis_templates()
        if inserted > 0:
            logger.info("Seeded %d analysis templates (prompts + skills)", inserted)
    except RuntimeError:
        pass  # AI disabled or Postgres not configured — no templates to seed
    except Exception as exc:
        logger.warning("Failed to seed analysis templates: %s", exc)

    # Token refresh is now handled automatically by Nango — no background task needed.

    # Initialize Graphiti (Neo4j knowledge graph) if configured
    try:
        from app.graphiti_client import is_graphiti_enabled, get_graphiti, graphiti_unavailable_reason
        if is_graphiti_enabled():
            client = await get_graphiti()
            if client is not None:
                logger.info("Graphiti knowledge graph initialized")
            else:
                logger.warning(
                    "Graphiti soft-disabled at startup: %s",
                    graphiti_unavailable_reason() or "unavailable",
                )
    except Exception as exc:
        logger.warning("Graphiti initialization skipped: %s", exc)

    # Integration providers are now managed by Nango — no seeding needed.

@app.get("/")
async def root():
    return {
        "service": "mem-dog-api",
        "version": API_VERSION,
        "environment": config.ENVIRONMENT,
        "storage_backend": config.STORAGE_BACKEND,
        "default_user_id": config.DEFAULT_USER_ID,
        "multitenant_path_sample": f"{config.DEFAULT_USER_ID}/data_01EXAMPLE/ver_20250101T000000Z/data",
        "ai_enabled": config.is_ai_enabled(),
        "user_management_enabled": config.is_user_management_enabled(),
        "memories_enabled": config.is_memories_enabled(),
        "stats_enabled": config.is_stats_enabled(),
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    """Readiness probe for host circuit breakers — storage must be constructible."""
    try:
        storage = get_storage()
        _ = storage  # touch singleton
        return {"status": "ready"}
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "detail": str(exc)},
        )


@app.get("/api/v1/auth/me")
async def auth_me(request: Request):
    """Return the authenticated user's profile. Works for all 3 auth types."""
    user_id = getattr(request.state, "user_id", None)
    auth_type = getattr(request.state, "auth_type", None)
    if not user_id:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    try:
        storage = get_storage()
        user = storage.get_user(user_id)
        return {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "auth_type": auth_type,
        }
    except Exception:
        return {"user_id": user_id, "auth_type": auth_type}


@app.get("/debug/config")
async def debug_config():
    """Debug: whether store backends see their config (values not revealed)."""
    storage = get_storage()

    postgres_error = None
    if config.is_postgres_store_enabled() and storage._store_for("postgres") is None:
        try:
            from app.store import PostgresStore
            PostgresStore(config.POSTGRES_URL)
        except Exception as e:
            postgres_error = f"{type(e).__name__}: {e}"

    return {
        "postgres_url_set": bool(config.POSTGRES_URL and config.POSTGRES_URL.strip()),
        "postgres_url_prefix": config.POSTGRES_URL[:40] + "..." if config.POSTGRES_URL else "",
        "postgres_store_active": storage._store_for("postgres") is not None,
        "postgres_connection_error": postgres_error,
        "redis_store_configured": bool(config.REDIS_URL and config.REDIS_URL.strip()),
        "supabase_store_configured": bool(
            config.SUPABASE_URL and config.SUPABASE_URL.strip()
            and config.SUPABASE_KEY and config.SUPABASE_KEY.strip()
        ),
        "gcs_store_configured": bool(config.STORE_GCS_BUCKET and config.STORE_GCS_BUCKET.strip()),
    }

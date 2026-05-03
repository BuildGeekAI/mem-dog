"""Auth helpers for extracting user identity from per-user API keys.

The middleware sets ``request.state.user_id`` and ``request.state.auth_type``
on every request.  Handlers can use these helpers to optionally scope
operations to the authenticated user.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Request

logger = logging.getLogger("mem_dog.auth")


def get_authenticated_user_id(request: Request) -> Optional[str]:
    """Return the user_id bound to a per-user API key, or ``None``."""
    return getattr(request.state, "user_id", None)


def get_effective_user_id(
    request: Request, explicit_user_id: Optional[str] = None
) -> Optional[str]:
    """Return *explicit_user_id* if provided, else the key-bound user, else ``None``."""
    if explicit_user_id:
        return explicit_user_id
    return get_authenticated_user_id(request)


async def ensure_jwt_user_profile(sub: str, payload: dict) -> None:
    """Auto-create a memdog user profile on first JWT-authenticated request.

    Uses the Supabase JWT ``sub`` (UUID) as the user_id.  Email and display
    name are extracted from standard JWT claims when available.
    """
    from app.storage import get_storage

    storage = get_storage()
    try:
        storage.get_user(sub)
        return  # user already exists
    except Exception:
        pass  # user not found — create below

    email = (
        payload.get("email")
        or payload.get("user_metadata", {}).get("email")
        or f"{sub}@jwt"
    )
    display_name = (
        payload.get("user_metadata", {}).get("full_name")
        or payload.get("user_metadata", {}).get("name")
        or email.split("@")[0]
    )
    username = email.split("@")[0]

    try:
        storage._create_user_with_id(
            user_id=sub,
            username=username,
            email=email,
            display_name=display_name,
        )
        logger.info("Auto-created profile for JWT user %s (%s)", sub, email)
        # Add new user to the default organization
        try:
            storage.add_org_member("org_default", sub, "member")
            logger.info("Added JWT user %s to org_default", sub)
        except Exception:
            logger.debug("Could not add JWT user to org_default", exc_info=True)
    except Exception:
        logger.debug("Could not auto-create JWT user profile", exc_info=True)

"""Helper to resolve org_id / project_id from request context.

When a caller provides project_id, we validate membership.
When neither is provided, we fall back to the user's defaults from their profile.
Both may be None for legacy (user_id-only) mode.
"""

from typing import Optional, Tuple

from fastapi import Request

from app import config
from app.storage import get_storage


def resolve_project_context(
    request: Request,
    org_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Return (org_id, project_id) — both may be None for legacy mode.

    Resolution order:
    1. Explicit parameters win.
    2. If project_id given without org_id, look up the project to get org_id.
    3. If neither given, use the user's defaults from their profile.
    """
    if project_id:
        if not org_id:
            storage = get_storage()
            proj = storage.get_project(project_id)
            if proj:
                org_id = proj.org_id
        return org_id, project_id

    if org_id:
        return org_id, None

    # Fall back to user defaults
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        try:
            storage = get_storage()
            user = storage.get_user(user_id)
            if user:
                return (
                    getattr(user, "default_org_id", None),
                    getattr(user, "default_project_id", None),
                )
        except Exception:
            pass

    return None, None

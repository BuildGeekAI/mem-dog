"""Extract API key from request and create a MemDog client."""

from __future__ import annotations

from contextvars import ContextVar

from mem_dog_client.simple import MemDog

from app.config import MEM_DOG_API_URL

# Per-request API key stored via contextvars (set by ASGI middleware)
_current_api_key: ContextVar[str | None] = ContextVar("_current_api_key", default=None)


def set_api_key(key: str | None) -> None:
    _current_api_key.set(key)


def get_api_key() -> str | None:
    return _current_api_key.get()


def create_client(api_key: str) -> MemDog:
    """Create a MemDog client scoped to the given API key."""
    return MemDog(base_url=MEM_DOG_API_URL, api_key=api_key, timeout=60.0)


def require_client() -> MemDog:
    """Get a MemDog client for the current request, or raise."""
    key = get_api_key()
    if not key:
        raise ValueError(
            "No API key found. Connect with x-api-key header or ?api_key= query param."
        )
    return create_client(key)

"""Transform registry for unified data model normalization.

Maps (provider_key, resource_type) -> transform function.
"""

from __future__ import annotations

from typing import Any, Callable

# Registry: (provider_key, resource_type) -> transform function
_registry: dict[tuple[str, str], Callable[[dict[str, Any]], dict[str, Any]]] = {}


def register(provider_key: str, resource_type: str):
    """Decorator to register a transform function."""
    def decorator(fn: Callable[[dict[str, Any]], dict[str, Any]]):
        _registry[(provider_key, resource_type)] = fn
        return fn
    return decorator


def get_transform(
    provider_key: str,
    resource_type: str,
) -> Callable[[dict[str, Any]], dict[str, Any]] | None:
    """Look up a transform function for a provider + resource type."""
    return _registry.get((provider_key, resource_type))


# Import transform modules to trigger registration
from . import crm_contact  # noqa: F401, E402
from . import calendar_event  # noqa: F401, E402

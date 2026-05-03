"""API client package for the mem-dog webhook agent.

Exposes module-level singletons so that every part of the agent package
shares the same client instances (and therefore the same base URL).

All HTTP calls are made through the shared :data:`~session._session`
(a ``requests.Session`` with a retrying ``HTTPAdapter``) so SSL/TCP
transient failures are retried automatically without any changes in the
individual client modules.

Usage::

    from .api_client import data_client, memory_client, stats_client
    from .api_client import staging_client, ai_client, tracking_client
"""

from .ai import AIClient
from .data import DataClient
from .memories import MemoryClient
from .session import _session
from .staging import StagingClient
from .stats import StatsClient
from .tracking import WebhookTrackingClient

data_client: DataClient = DataClient()
memory_client: MemoryClient = MemoryClient()
stats_client: StatsClient = StatsClient()
staging_client: StagingClient = StagingClient()
ai_client: AIClient = AIClient()
tracking_client: WebhookTrackingClient = WebhookTrackingClient()

__all__ = [
    "data_client",
    "memory_client",
    "stats_client",
    "staging_client",
    "ai_client",
    "tracking_client",
    "_session",
    "DataClient",
    "MemoryClient",
    "StatsClient",
    "StagingClient",
    "AIClient",
    "WebhookTrackingClient",
]

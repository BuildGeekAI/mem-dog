"""FinancialAgent — trade ticks, order books, and market data (Plan 3)."""

from ..base import BaseSubAgent


class FinancialAgent(BaseSubAgent):
    """Processes financial market data: trades, quotes, order books, FIX messages.

    Handles tick data, OHLCV bars, order book snapshots, FIX protocol messages,
    financial statements, and transaction records.
    """

    AGENT_TYPE = "financial"
    AGENT_PURPOSE = "Processes financial data including trade ticks, order books, and market data"
    MIME_PATTERNS = [
        "application/x-financial",
        "application/x-fix",
        "application/x-trading-data",
        "application/x-market-data",
        "application/x-quickfix",
        "text/x-fix",
    ]
    MODEL_TIER = "medium"

    def _process(self, payload_json: str, data_id: str, group_context=None, payload_meta=None) -> dict:
        from ..llm_utils import analyse_payload
        return analyse_payload(
            self.AGENT_TYPE, payload_json, data_id, self.instance_id,
            self.AGENT_PURPOSE, group_context, payload_meta,
        )

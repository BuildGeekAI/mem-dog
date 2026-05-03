"""ChannelMessageAgent — normalised channel message handler (Plan 2).

Handles payloads that have been identified as chat/messaging channel
messages by the receiver and router (Layer 0 detection).  The
``channel_message`` dict injected into ``meta_data`` by the receiver
is used to enrich stored tags so memories can be queried by channel
type, thread, or peer.
"""

import json

from ..base import BaseSubAgent


class ChannelMessageAgent(BaseSubAgent):
    """Processes normalised channel messages from any chat platform.

    Routes payloads identified as chat-type (WhatsApp, Telegram, Slack,
    Discord, Teams, SMS …) so they are stored with channel-aware tags and
    linked to conversation memories.
    """

    AGENT_TYPE = "channel_message"
    AGENT_PURPOSE = "Processes normalised channel messages (WhatsApp, Telegram, Slack, …)"
    MIME_PATTERNS = [
        "application/x-channel-message",
        "application/x-chat",
        "application/x-whatsapp",
        "application/x-telegram",
        "application/x-slack",
    ]
    MODEL_TIER = "medium"

    def _process(
        self,
        payload_json: str,
        data_id: str,
        group_context=None,
        payload_meta=None,
    ) -> dict:
        """Analyse channel message content using the LLM pipeline.

        Enriches ``payload_meta`` with channel-specific metadata before
        delegating to the standard ``analyse_payload`` helper.

        Args:
            payload_json: Raw webhook payload as a JSON string.
            data_id: mem-dog data ID returned by ``write_record()``.
            group_context: Optional group context forwarded from the router.
            payload_meta: Optional dict with detection-layer metadata.

        Returns:
            Result dict with ``status``, ``data_id``, analysis fields,
            and ``channel_context`` populated from the group context.
        """
        from ..llm_utils import analyse_payload

        # Enrich payload_meta with channel context for the analysis prompt
        enriched_meta = dict(payload_meta or {})
        if group_context and group_context.channel_type:
            enriched_meta["channel_type"] = group_context.channel_type
            enriched_meta["channel_peer_id"] = group_context.channel_peer_id
            enriched_meta["channel_thread_id"] = group_context.channel_thread_id

        result = analyse_payload(
            self.AGENT_TYPE,
            payload_json,
            data_id,
            self.instance_id,
            self.AGENT_PURPOSE,
            group_context,
            enriched_meta,
        )

        # Attach channel context to the result for traceability
        if group_context:
            result["channel_context"] = {
                "channel_type": group_context.channel_type,
                "peer_id": group_context.channel_peer_id,
                "thread_id": group_context.channel_thread_id,
                "conversation_memory_id": group_context.conversation_memory_id,
            }

        return result

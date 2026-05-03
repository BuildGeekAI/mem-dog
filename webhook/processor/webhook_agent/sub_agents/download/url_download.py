"""UrlDownloadAgent — discovers URLs from a page, emits webhook events for parallel processing."""

import json
import logging
from typing import TYPE_CHECKING, Any

from ..base import BaseSubAgent
from ...api_client import memory_client
from ...api_client.config import AGENT_USER_ID
from ...api_client.session import _session
from ...meta_schema import (
    get_crawl, get_memory, get_owner, get_prompt, get_url, get_user_id,
    build_meta_data,
)
from ...url_context import crawl_urls, get_urls_to_download

if TYPE_CHECKING:
    from ...group_context import GroupContext

logger = logging.getLogger("mem_dog.webhook.sub_agents.download.url_download")

# Internal webhook receiver URL for emitting per-URL events
_RECEIVER_URL = "http://webhook-receiver.webhook-pipeline.svc.cluster.local:8080/"


def _emit_webhook_event(payload: dict) -> bool:
    """POST a webhook event to the receiver for async processing. Returns True on success."""
    try:
        resp = _session.post(
            _RECEIVER_URL,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Emitted webhook event for url=%s", (payload.get("data") or {}).get("url", "?")[:80])
        return True
    except Exception as exc:
        logger.warning("Failed to emit webhook event: %s", exc)
        return False


class UrlDownloadAgent(BaseSubAgent):
    """Sub-agent that discovers URLs and emits webhook events for each.

    Instead of downloading content in-process (which causes OOM on large crawls),
    this agent discovers URLs via Gemini url_context or legacy BFS crawl, then
    POSTs a separate webhook event per URL back to the receiver. Each URL is then
    processed independently and in parallel by the pipeline.
    """

    AGENT_TYPE = "url_download"
    AGENT_PURPOSE = "Discovers URLs and emits webhook events for parallel download and processing"
    MIME_PATTERNS: list[str] = []

    def write_record(
        self,
        payload_json: str,
        name: str = "event",
        group_context: "GroupContext | None" = None,
        extra_tags: list[str] | None = None,
        trace_context: dict | None = None,
        meta_data: dict | None = None,
    ) -> dict[str, Any]:
        """Discover URLs and emit a webhook event per URL for parallel processing."""
        meta_data = meta_data or {}
        creator_user_id = (
            (group_context.user_id if group_context else None)
            or get_user_id(meta_data)
            or AGENT_USER_ID
        )

        # Crawl mode: discover documents via Gemini/BFS, emit events
        crawl_config = get_crawl(meta_data)
        if crawl_config and isinstance(crawl_config, dict):
            url = get_url(meta_data) or (json.loads(payload_json).get("url") if payload_json else None)
            return self._emit_crawl(url, crawl_config, meta_data, group_context, extra_tags or [], creator_user_id)

        # Single URL mode: resolve page links, emit events
        url = get_url(meta_data) or (json.loads(payload_json).get("url") if payload_json else None)
        if not url or not str(url).strip().startswith(("http://", "https://")):
            return {
                "status": "error",
                "instance_id": self.instance_id,
                "error_message": "Missing or invalid url in metadata",
            }

        prompt = get_prompt(meta_data)
        urls_to_download = get_urls_to_download(url, prompt)
        if not urls_to_download:
            return {
                "status": "success",
                "emitted": 0,
                "instance_id": self.instance_id,
                "message": "No URLs discovered (page had no matching links)",
            }

        emitted = 0
        for target_url in urls_to_download:
            payload = self._build_url_event(target_url, creator_user_id, meta_data)
            if _emit_webhook_event(payload):
                emitted += 1

        return {
            "status": "success" if emitted else "error",
            "data_id": f"crawl-emit-{emitted}",
            "emitted": emitted,
            "discovered": len(urls_to_download),
            "instance_id": self.instance_id,
        }

    def _emit_crawl(
        self,
        url: str | None,
        crawl_config: dict,
        meta_data: dict,
        group_context: "GroupContext | None",
        extra_tags: list[str],
        creator_user_id: str,
    ) -> dict[str, Any]:
        """Discover documents via crawl, create a semantic memory, emit events."""
        from urllib.parse import urlparse as _urlparse

        if not url or not str(url).strip().startswith(("http://", "https://")):
            return {
                "status": "error",
                "instance_id": self.instance_id,
                "error_message": "Missing or invalid url for crawl",
            }

        prompt = get_prompt(meta_data)
        max_depth = int(crawl_config.get("max_depth", 1))
        max_pages = int(crawl_config.get("max_pages", 50))
        max_documents = int(crawl_config.get("max_documents", 200))

        discovered = crawl_urls(url, prompt=prompt, max_depth=max_depth, max_pages=max_pages, max_documents=max_documents)
        if not discovered:
            return {
                "status": "success",
                "emitted": 0,
                "discovered_count": 0,
                "instance_id": self.instance_id,
                "message": "No documents discovered during crawl",
            }

        # Create a semantic memory for this crawl
        domain = _urlparse(url).netloc or "unknown"
        memory_name = crawl_config.get("memory_name") or f"Crawl: {domain}"
        memory_id = f"crawl-{domain}-{id(discovered) % 100000}"
        try:
            memory_client.ensure(
                memory_id=memory_id,
                memory_type="semantic",
                name=memory_name,
                description=f"Documents crawled from {url} (depth={max_depth})",
                agent_instance_id=self.instance_id,
                user_id=creator_user_id,
            )
        except Exception as exc:
            logger.warning("Crawl: failed to create semantic memory: %s", exc)

        # Resolve memory_ids for the events
        memory_ids, _, _ = self._resolve_memories_and_tags(
            group_context, meta_data, extra_tags,
        )
        if memory_id not in memory_ids:
            memory_ids.append(memory_id)

        # Emit a webhook event per discovered URL
        emitted = 0
        for doc in discovered:
            target_url = doc["url"]
            payload = self._build_url_event(
                target_url, creator_user_id, meta_data,
                memory_ids=memory_ids,
                title=doc.get("title"),
            )
            if _emit_webhook_event(payload):
                emitted += 1

        logger.info(
            "Crawl complete | url=%s discovered=%d emitted=%d memory=%s",
            url[:80], len(discovered), emitted, memory_id,
        )

        return {
            "status": "success" if emitted else "error",
            "data_id": f"crawl-emit-{emitted}",
            "emitted": emitted,
            "discovered_count": len(discovered),
            "memory_id": memory_id,
            "instance_id": self.instance_id,
        }

    def _build_url_event(
        self,
        url: str,
        user_id: str,
        source_meta: dict,
        memory_ids: list[str] | None = None,
        title: str | None = None,
    ) -> dict:
        """Build a webhook payload for a single URL to be processed by the pipeline.

        IMPORTANT: ``url`` is placed ONLY in ``data``, NOT in ``telemetry``.
        This prevents the router's Layer 0b from re-routing the event back to
        url_download (which would create an infinite loop).  Downstream agents
        discover the URL in ``payload["url"]`` during their ``_fetch_binary()``
        staging step.
        """
        return {
            "data": {
                "event": "url.download",
                "url": url,
                "title": title or url.split("/")[-1].split("?")[0] or "document",
            },
            "telemetry": {
                "user_id": user_id,
                "prompt": get_prompt(source_meta),
                **({"memory_list": memory_ids} if memory_ids else {}),
            },
        }

    def _resolve_memories_and_tags(
        self,
        group_context: "GroupContext | None",
        meta_data: dict,
        extra_tags: list[str],
    ) -> tuple[list[str], list[str], str | None]:
        """Build memory_ids and tags."""
        memory_dict: dict = get_memory(meta_data) or {}
        memory_from_dict = self._flatten_memory_dict(memory_dict) if memory_dict else []
        memory_list: list[str] = memory_from_dict or meta_data.get("memory_list") or []
        owner = get_owner(meta_data)
        creator_user_id = None
        if group_context is not None:
            creator_user_id = group_context.user_id
        if not creator_user_id:
            creator_user_id = get_user_id(meta_data) or (
                (owner or {}).get("user") or {}
            ).get("user_id")

        memory_ids: list[str] = []
        tags = [f"agent_type:{self.AGENT_TYPE}", self.instance_id]
        if creator_user_id:
            tags.append(f"user_id:{creator_user_id}")

        if memory_list:
            memory_ids = list(memory_list)
        elif group_context is not None:
            conversation_memory_id = getattr(group_context, "conversation_memory_id", None)
            memory_ids = [
                group_context.timeline_memory_id,
                group_context.session_memory_id,
            ]
            if conversation_memory_id:
                memory_ids.append(conversation_memory_id)
            if creator_user_id:
                personal_tl = f"timeline-{creator_user_id}"
                if personal_tl not in memory_ids:
                    memory_ids.append(personal_tl)
            tags.append(f"group_id:{group_context.group_id}")
            if getattr(group_context, "channel_type", None):
                tags.append(f"channel_type:{group_context.channel_type}")

        from ...meta_schema import get_trace_memory_id, get_session_id
        trace_memory_id = get_trace_memory_id(meta_data)
        if trace_memory_id and trace_memory_id not in memory_ids:
            memory_ids.append(trace_memory_id)
        session_id = get_session_id(meta_data)
        if session_id:
            session_memory_id = f"session-{session_id}"
            if session_memory_id not in memory_ids:
                memory_ids.append(session_memory_id)

        for own_id in (self.timeline_memory_id, self.session_memory_id):
            if own_id in memory_ids:
                memory_ids.remove(own_id)

        tags.extend(extra_tags)
        return memory_ids, tags, creator_user_id

    def _process(
        self,
        payload_json: str,
        data_id: str,
        group_context: "GroupContext | None" = None,
        payload_meta: dict | None = None,
    ) -> dict[str, Any]:
        """No-op: actual processing is done by the per-URL webhook events."""
        return {
            "status": "ok",
            "data_id": data_id,
            "reason": "url_events_emitted; processing handled by per-URL pipeline invocations",
        }

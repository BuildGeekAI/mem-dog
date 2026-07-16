"""Shared LLM utilities for Tier-1 (text) sub-agents.

Provides the single public entry point used by every text-based sub-agent:

* :func:`analyse_payload` — full pipeline:

  1. **Stage** — download the payload's content via
     :class:`~api_client.staging.StagingClient`, persist it to the GCS
     staging bucket as ``raw`` + ``meta.json``.
  2. **Analyse** — pass the content (truncated to
     :data:`_MAX_CONTENT_CHARS`) to the model server via
     :func:`~model_client.chat_for_data_type`.
  3. **Viewpoint** — store the analysis as a versioned viewpoint linked
     to the ``data_id`` via :class:`~api_client.ai.AIClient`.
  4. **Embedding** — trigger vector embedding generation for the
     ``data_id`` via :class:`~api_client.ai.AIClient`.

All model inference is delegated to the dedicated model server (Cloud Run B)
via HTTP.  No LLM code runs in-process.  See :mod:`~webhook_agent.model_client`
for transport and authentication details.

Graceful degradation
--------------------
Every step is wrapped so that a failure in one stage (download, LLM, viewpoint,
embedding) returns an error result dict rather than raising — no payload is
ever silently dropped.
"""

import base64
import io
import json as _json
import logging
import struct
import threading
import zipfile
import tarfile
from typing import TYPE_CHECKING, Any, Optional

logger = logging.getLogger("mem_dog.webhook.sub_agents.llm_utils")

if TYPE_CHECKING:
    from ..group_context import GroupContext


def _infer_ai_engine(model_str: str) -> str:
    """Derive the AI engine name from a LiteLLM model string.

    E.g. ``"ollama/gemma3:12b"`` → ``"ollama"``,
    ``"gemini/gemini-3.1-pro-preview"`` → ``"gemini"``.
    """
    if "/" in model_str:
        return model_str.split("/", 1)[0]
    return model_str


def _try_parse_json_obj(text: str) -> dict | None:
    """Try to parse *text* as a JSON object. Returns dict or None."""
    if not text or not text.startswith("{"):
        return None
    try:
        obj = _json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (ValueError, TypeError):
        pass
    return None


def _repair_truncated_json(text: str) -> dict | None:
    """Attempt to repair truncated JSON by closing open brackets/braces.

    LLMs sometimes hit max_tokens mid-JSON. This tries progressive
    repairs: close strings, arrays, objects.
    """
    if not text or not text.startswith("{"):
        return None
    # Try closing progressively
    for suffix in ['"}', '"]', '"]}', '""]}', '"}', ']}', '}']:
        attempt = text + suffix
        obj = _try_parse_json_obj(attempt)
        if obj is not None:
            return obj
    # Brute force: count open braces/brackets and close them
    opens = 0
    open_brackets = 0
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            opens += 1
        elif ch == '}':
            opens -= 1
        elif ch == '[':
            open_brackets += 1
        elif ch == ']':
            open_brackets -= 1
    # Close any open string, then brackets, then braces
    repair = text
    if in_string:
        repair += '"'
    repair += ']' * max(0, open_brackets)
    repair += '}' * max(0, opens)
    return _try_parse_json_obj(repair)


def _unwrap_double_encoded(obj: dict) -> dict:
    """Fix double-encoded JSON: {"summary": "{\"category\":...}"} → parse inner JSON."""
    if len(obj) == 1 and "summary" in obj:
        inner = obj["summary"]
        if isinstance(inner, str) and inner.strip().startswith("{"):
            parsed = _try_parse_json_obj(inner.strip())
            if parsed and len(parsed) > 1:
                return parsed
            # Try repairing truncated inner JSON
            repaired = _repair_truncated_json(inner.strip())
            if repaired and len(repaired) > 1:
                return repaired
    return obj


def _parse_analysis_to_json(raw_analysis: str) -> str:
    """Parse LLM output into a JSON string.

    Strategy:
    1. Try direct JSON parse (LLM was asked to return JSON).
       - Unwrap double-encoded JSON if needed.
    2. Try extracting JSON from markdown code fences.
    3. Try repairing truncated JSON (LLM hit max_tokens).
    4. Last resort: ``{"summary": raw_text}``.
    """
    import re
    trimmed = raw_analysis.strip()

    # --- Strategy 1: direct JSON parse ---
    obj = _try_parse_json_obj(trimmed)
    if obj is not None:
        return _json.dumps(_unwrap_double_encoded(obj))

    # --- Strategy 2: extract from code fences ---
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", trimmed, re.DOTALL)
    if fence_match:
        obj = _try_parse_json_obj(fence_match.group(1).strip())
        if obj is not None:
            return _json.dumps(_unwrap_double_encoded(obj))

    # --- Strategy 3: repair truncated JSON ---
    if trimmed.startswith("{"):
        obj = _repair_truncated_json(trimmed)
        if obj is not None:
            return _json.dumps(_unwrap_double_encoded(obj))

    # --- Strategy 4: wrap raw text as summary ---
    return _json.dumps({"summary": trimmed})


def _extract_tags_from_analysis(raw_analysis: str, agent_type: str) -> list[str]:
    """Extract tags from LLM output (JSON or text format).

    Returns a list of prefixed tag strings, e.g.::

        ["category:finance / trading", "entity:stripe", "keyword:checkout flow", "auto:true"]
    """
    tags: list[str] = []

    # Try JSON first (LLM should return JSON now)
    obj = _try_parse_json_obj(raw_analysis.strip())
    if obj is not None:
        cat = obj.get("category", "")
        if cat and isinstance(cat, str):
            tags.append(f"category:{cat.lower()}")
        for ent in (obj.get("entities") or []):
            ent = str(ent).strip()
            if ent and ent.lower() not in ("none", "n/a", "-"):
                tags.append(f"entity:{ent.lower()}")
        for kw in (obj.get("keywords") or []):
            kw = str(kw).strip()
            if kw and kw.lower() not in ("none", "n/a", "-"):
                tags.append(f"keyword:{kw.lower()}")
    else:
        # Fallback: text-section parsing
        for line in raw_analysis.splitlines():
            stripped = line.strip()
            upper = stripped.upper()
            if upper.startswith("CATEGORY:"):
                val = stripped[len("CATEGORY:"):].strip().strip("\"'")
                if val:
                    tags.append(f"category:{val.lower()}")
            elif upper.startswith("ENTITIES:"):
                val = stripped[len("ENTITIES:"):].strip()
                for ent in val.split(","):
                    ent = ent.strip().strip("\"'")
                    if ent and ent.lower() not in ("none", "n/a", "-"):
                        tags.append(f"entity:{ent.lower()}")
            elif upper.startswith("KEYWORDS:"):
                val = stripped[len("KEYWORDS:"):].strip()
                for kw in val.split(","):
                    kw = kw.strip().strip("\"'")
                    if kw and kw.lower() not in ("none", "n/a", "-"):
                        tags.append(f"keyword:{kw.lower()}")
    if tags:
        tags.append("auto:true")
    return tags


def _write_api_results_async(
    agent_type: str,
    data_id: str,
    raw_analysis: str,
    owner_uid: str | None,
    ai_engine: str = "",
    model_name: str = "",
) -> None:
    """Fire-and-forget viewpoint + embedding writes in a daemon thread."""

    def _run():
        from ..api_client import ai_client
        vp_ok = False
        try:
            # Convert structured LLM output to JSON for storage
            analysis_json = _parse_analysis_to_json(raw_analysis)
            logger.info("[%s] (bg) creating viewpoint | data_id=%s", agent_type, data_id)
            vp = ai_client.create_viewpoint(
                data_id=data_id,
                name=f"{agent_type} — webhook analysis",
                analysis_text=analysis_json,
                user_id=owner_uid,
                ai_engine=ai_engine or None,
                model_name=model_name or None,
            )
            vp_ok = vp.get("viewpoint_id") or vp.get("status") != "error"
            logger.info("[%s] (bg) viewpoint created | %s", agent_type, vp)
        except Exception as exc:
            logger.warning("[%s] (bg) viewpoint failed | %s", agent_type, exc)

        # Best-effort auto-tagging from structured analysis
        if vp_ok:
            try:
                auto_tags = _extract_tags_from_analysis(raw_analysis, agent_type)
                if auto_tags:
                    from ..api_client.data import DataClient
                    data_client = DataClient()
                    data_client.add_tags(data_id, auto_tags, user_id=owner_uid)
                    logger.info("[%s] (bg) auto-tags added | data_id=%s  count=%d", agent_type, data_id, len(auto_tags))
            except Exception as exc:
                logger.warning("[%s] (bg) auto-tagging failed | %s", agent_type, exc)

        # Best-effort graph entity/relationship persistence
        try:
            obj = _try_parse_json_obj(raw_analysis.strip())
            typed_entities = (obj or {}).get("typed_entities", [])
            relationships = (obj or {}).get("relationships", [])
            if typed_entities:
                from ..api_client.graph import graph_client
                graph_entities = []
                for te in typed_entities:
                    if isinstance(te, dict) and te.get("name"):
                        graph_entities.append({
                            "entity_name": str(te["name"]),
                            "entity_type": str(te.get("type", "concept")),
                            "confidence": float(te.get("confidence", 0.8)),
                        })
                graph_rels = []
                for r in (relationships or []):
                    if isinstance(r, dict) and r.get("source") and r.get("target"):
                        graph_rels.append({
                            "source": str(r["source"]),
                            "target": str(r["target"]),
                            "rel_type": str(r.get("type", "mentions")),
                        })
                if graph_entities:
                    uid = owner_uid or "default"
                    graph_client.batch_create_entities(data_id, graph_entities, graph_rels, uid)
                    logger.info("[%s] (bg) graph entities persisted | data_id=%s  count=%d", agent_type, data_id, len(graph_entities))
        except Exception as exc:
            logger.warning("[%s] (bg) graph persistence failed (non-blocking) | %s", agent_type, exc)

        # Embedding can use parsed body even when viewpoint failed.
        if not vp_ok:
            logger.warning(
                "[%s] (bg) viewpoint not stored — still attempting embedding | data_id=%s",
                agent_type, data_id,
            )

        try:
            logger.info("[%s] (bg) triggering embedding | data_id=%s", agent_type, data_id)
            emb = ai_client.create_embedding(data_id=data_id, user_id=owner_uid)
            logger.info("[%s] (bg) embedding triggered | %s", agent_type, emb)
        except Exception as exc:
            logger.warning("[%s] (bg) embedding failed | %s", agent_type, exc)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _inject_urls_from_meta(payload: dict, payload_meta: dict | None) -> None:
    """Ensure URLs from payload_meta are visible in the payload dict.

    The router passes only the ``data`` section as payload_json to sub-agents,
    but URLs (source URL, API download URL) live in ``telemetry``/``meta_data``.
    This injects them so ``stage_binary`` / ``_fetch_binary`` can find them.
    """
    meta = payload_meta or {}
    for field in ("url", "download_url", "gcs_uri"):
        val = meta.get(field)
        if val and isinstance(val, str) and field not in payload:
            payload[field] = val


# Maximum characters forwarded to the LLM prompt.
# The full content is always stored in GCS regardless of this limit.
_MAX_CONTENT_CHARS: int = 4_000
# Large/very-large tier models (gemma3:27b+) can handle more context.
# Phase 0 baseline caps: docs/adr/0001-document-parsing-baseline.md
_MAX_CONTENT_CHARS_LARGE: int = 8_000

# Per-agent-type prompts — each instructs the model on what to extract / summarise
# ---------------------------------------------------------------------------
# Prompt resolution — skills-based JSON prompts for all sub-agents
# ---------------------------------------------------------------------------

def _resolve_config(
    agent_type: str,
    payload_meta: dict[str, Any] | None,
    user_id: str | None = None,
    is_truncated: bool = False,
) -> tuple[str, str | None]:
    """Resolve analysis prompt and optional system prompt.

    Returns ``(prompt, system_prompt)`` where system_prompt may be ``None``
    (caller uses the default).

    Priority:
    1. Message-level override — ``prompt`` field in *payload_meta*.
    2. User DB config — per-user agent config from API.
    3. System DB config — system-default agent config from API.
    4. Hardcoded fallback — :func:`~skills.build_prompt`.
    """
    # Tier 1: message-level override (user-provided prompt in webhook payload)
    if payload_meta and payload_meta.get("prompt"):
        logger.debug("[%s] using message-level prompt override", agent_type)
        return payload_meta["prompt"], None

    # Tier 2+3: DB config (user override → system default)
    try:
        from ..api_client import ai_client
        config = ai_client.get_pipeline_config(agent_type, user_id)
        if config:
            from .skills import build_prompt_from_config
            prompt = build_prompt_from_config(config, agent_type, is_truncated=is_truncated)
            logger.debug("[%s] using DB pipeline config (user_id=%s)", agent_type, config.get("user_id"))
            return prompt, config.get("system_prompt")
    except Exception as exc:
        logger.debug("[%s] pipeline config lookup failed: %s", agent_type, exc)

    # Tier 4: hardcoded fallback
    from .skills import build_prompt
    return build_prompt(agent_type, is_truncated=is_truncated), None


# ---------------------------------------------------------------------------
# Internal LLM runner
# ---------------------------------------------------------------------------

_DEFAULT_SYSTEM_PROMPT = (
    "You are a data analysis assistant. You MUST respond with ONLY "
    "a valid JSON object — no markdown, no code fences, no preamble, "
    "no explanation. Output raw JSON and nothing else."
)


def _run_llm(
    content: str,
    prompt: str,
    max_tokens: int = 4096,
    agent_type: str = "",
    user_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """Send a completion request via smart routing for a sub-agent.

    Args:
        content: Text content included after the prompt separator.
        prompt: Instruction for the model.
        max_tokens: Token budget for the response (default 65536 to avoid
            mid-JSON truncation for structured analysis output).
        agent_type: Sub-agent data type for smart routing.
        user_id: Owner user ID for smart routing preference lookup.
        system_prompt: Optional override for the system message.
            If ``None``, uses :data:`_DEFAULT_SYSTEM_PROMPT`.

    Returns:
        The model's response text, or an error string prefixed with
        ``"[analysis_error]"`` so callers can detect failures without raising.
    """
    from .. import model_client

    messages = [
        {
            "role": "system",
            "content": system_prompt or _DEFAULT_SYSTEM_PROMPT,
        },
        {"role": "user", "content": f"{prompt}\n\n---\n{content}"},
    ]

    logger.info(
        "LLM request | agent_type=%s  max_tokens=%d  content_chars=%d",
        agent_type, max_tokens, len(content),
    )
    logger.debug("LLM prompt   |\n%s", prompt)
    logger.debug("LLM content  |\n%s", content)

    try:
        result = model_client.chat_for_data_type(
            messages, agent_type=agent_type, user_id=user_id,
            max_tokens=max_tokens, temperature=0.3,
        )
        usage = model_client.get_last_usage()
        actual_model = usage.get("model", "unknown") if usage else "unknown"
        logger.info("LLM response | agent_type=%s  model=%s  chars=%d", agent_type, actual_model, len(result))
        logger.debug("LLM response text |\n%s", result)
        return result
    except Exception as exc:
        logger.warning("Model call failed (agent_type=%s, %s): %s", agent_type, type(exc).__name__, exc)
        return f"[analysis_error] {type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyse_payload(
    agent_type: str,
    payload_json: str,
    data_id: str,
    agent_instance_id: str = "",
    agent_purpose: str = "",
    group_context: "Optional[GroupContext]" = None,
    payload_meta: Optional[dict] = None,
) -> dict[str, Any]:
    """Stage → analyse → viewpoint → embedding pipeline for Tier-1 sub-agents.

    This is the single call made by each Tier-1 sub-agent's ``process()``
    method::

        def _process(self, payload_json, data_id, group_context=None, payload_meta=None):
            from ..llm_utils import analyse_payload
            return analyse_payload(
                self.AGENT_TYPE, payload_json, data_id,
                self.instance_id, self.AGENT_PURPOSE,
                group_context, payload_meta,
            )

    Args:
        agent_type: ``AGENT_TYPE`` of the calling sub-agent.
        payload_json: Raw webhook payload as a JSON string.
        data_id: The mem-dog data ID returned by ``write_record()``.
            Used to link the viewpoint and embedding to the stored record.
        agent_instance_id: Stable instance ID written into ``meta.json``.
        agent_purpose: Human-readable purpose written into ``meta.json``.
        group_context: Optional group context forwarded from the router.
            Written into ``meta.json`` for full provenance.
        payload_meta: Optional dict with ``detection_layer`` and
            ``mime_type`` forwarded from the router.

    Returns:
        A result dict containing:

        * ``status`` — ``"success"`` or ``"error"``
        * ``agent_type``
        * ``staged_uri`` — GCS URI of the raw object (empty if no bucket)
        * ``content_length`` — bytes of content staged / analysed
        * ``content_source`` — ``"url"``, ``"inline"``, or ``"payload_dump"``
        * ``analysis`` — LLM summary text (on success)
        * ``viewpoint`` — viewpoint API response dict
        * ``embedding`` — embedding API response dict
        * ``metadata`` — full provenance dict written to ``meta.json``
        * ``error`` — error string (on failure instead of ``analysis``)
    """
    from ..api_client import ai_client, staging_client

    logger.info(
        "[%s] analyse_payload START | data_id=%s  agent_instance=%s  purpose=%s",
        agent_type,
        data_id,
        agent_instance_id or "(none)",
        agent_purpose or "(none)",
    )
    logger.debug("[%s] payload_json (first 500 chars) |\n%s", agent_type, payload_json[:500])
    if payload_meta:
        logger.info("[%s] payload_meta | %s", agent_type, payload_meta)
    if group_context:
        logger.info("[%s] group_context | %s", agent_type, group_context)

    # ------------------------------------------------------------------
    # 1. Parse payload
    # ------------------------------------------------------------------
    try:
        payload = _json.loads(payload_json)
        logger.debug("[%s] payload parsed as JSON | keys=%s", agent_type, list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)
    except (ValueError, TypeError):
        payload = {"raw": payload_json}
        logger.debug("[%s] payload is not valid JSON; wrapped in raw key", agent_type)

    # ------------------------------------------------------------------
    # 2. Stage — download + persist to GCS
    # ------------------------------------------------------------------
    _inject_urls_from_meta(payload, payload_meta)
    logger.info("[%s] staging payload | data_id=%s", agent_type, data_id)
    try:
        content, staged_uri, metadata = staging_client.stage(
            payload=payload,
            agent_type=agent_type,
            data_id=data_id,
            agent_instance_id=agent_instance_id,
            agent_purpose=agent_purpose,
            group_ctx=group_context,
            payload_meta=payload_meta,
        )
        content_source = metadata.get("source", {}).get("url_field") and "url" or (
            "inline" if metadata.get("source", {}).get("field") else "payload_dump"
        )
        # Derive a cleaner content_source label from the source meta
        src = metadata.get("source", {})
        if src.get("url"):
            content_source = "url"
        elif src.get("field"):
            content_source = "inline"
        else:
            content_source = "payload_dump"
        logger.info(
            "[%s] staging done | staged_uri=%s  content_source=%s  content_chars=%d",
            agent_type,
            staged_uri or "(none)",
            content_source,
            len(content),
        )
    except Exception as exc:
        logger.warning("Staging failed for %s/%s: %s", agent_type, data_id, exc)
        return {
            "status": "error",
            "agent_type": agent_type,
            "data_id": data_id,
            "error": f"[staging_error] {type(exc).__name__}: {exc}",
        }

    # ------------------------------------------------------------------
    # 3. Analyse — run LLM on a truncated window of the content
    # ------------------------------------------------------------------
    # Check if agent uses large/very-large tier for context window sizing.
    from . import AGENT_REGISTRY
    agent_tier = getattr(AGENT_REGISTRY.get(agent_type), "MODEL_TIER", "medium")

    max_chars = _MAX_CONTENT_CHARS_LARGE if agent_tier in ("large", "very-large") else _MAX_CONTENT_CHARS
    is_truncated = len(content) > max_chars
    owner_uid_routing = group_context.user_id if group_context else None
    prompt, system_prompt = _resolve_config(agent_type, payload_meta, user_id=owner_uid_routing, is_truncated=is_truncated)
    truncated = content[:max_chars]

    logger.info(
        "[%s] calling LLM | content_chars_sent=%d  truncated=%s",
        agent_type,
        len(truncated),
        len(content) > _MAX_CONTENT_CHARS,
    )
    raw_analysis = _run_llm(truncated, prompt, agent_type=agent_type, user_id=owner_uid_routing, system_prompt=system_prompt)

    # Report token usage (best-effort) and capture actual model for provenance
    _actual_model = ""
    try:
        from .. import model_client
        from ..api_client import stats_client
        usage = model_client.get_last_usage()
        _actual_model = usage.get("model", "") if usage else ""
        if usage and usage.get("model"):
            owner_uid_for_tokens = group_context.user_id if group_context else None
            if owner_uid_for_tokens:
                stats_client.record_token_usage(
                    user_id=owner_uid_for_tokens,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    model=usage.get("model", ""),
                    agent_type=agent_type,
                    duration_ms=usage.get("duration_ms"),
                )
    except Exception as tok_exc:
        logger.debug("Token usage reporting failed: %s", tok_exc)

    if raw_analysis.startswith("[analysis_error]"):
        logger.warning("[%s] LLM analysis error | %s", agent_type, raw_analysis)
        return {
            "status": "error",
            "agent_type": agent_type,
            "data_id": data_id,
            "staged_uri": staged_uri,
            "content_length": len(content),
            "content_source": content_source,
            "metadata": metadata,
            "error": raw_analysis,
        }

    logger.info("[%s] LLM analysis complete | analysis_chars=%d", agent_type, len(raw_analysis))

    # ------------------------------------------------------------------
    # 4. Viewpoint + Embedding — fire-and-forget in background thread
    # ------------------------------------------------------------------
    owner_uid = group_context.user_id if group_context else None
    _write_api_results_async(
        agent_type, data_id, raw_analysis, owner_uid,
        ai_engine=_infer_ai_engine(_actual_model) if _actual_model else "",
        model_name=_actual_model,
    )

    logger.info(
        "[%s] analyse_payload DONE | data_id=%s  status=success",
        agent_type,
        data_id,
    )

    return {
        "status": "success",
        "agent_type": agent_type,
        "data_id": data_id,
        "staged_uri": staged_uri,
        "content_length": len(content),
        "content_source": content_source,
        "analysis": raw_analysis,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Multimodal LLM runner (video / audio via Gemini)
# ---------------------------------------------------------------------------

# URL fields to check when extracting the media source URL from a payload
_MEDIA_URL_FIELDS = ("url", "source_url", "file_url", "download_url", "href", "link")


def _pdf_data_uri_to_image_parts(data_uri: str, max_pages: int = 3) -> list[dict]:
    """Convert a base64-encoded PDF data URI into image_url content parts.

    Renders up to *max_pages* pages as JPEG using PyMuPDF (fitz) and returns
    them as ``image_url`` parts suitable for OpenAI-style multimodal messages.
    Uses JPEG at 150 DPI to keep payload under Ollama Cloud's body size limit.
    """
    import fitz  # pymupdf

    # Strip the data URI header to get raw base64
    # Format: data:application/pdf;base64,<data>
    header, _, b64_data = data_uri.partition(",")
    pdf_bytes = base64.b64decode(b64_data)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parts: list[dict] = []
    for page_num in range(min(len(doc), max_pages)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=150)
        # Use JPEG for much smaller payload than PNG
        jpeg_bytes = pix.tobytes("jpeg", jpg_quality=80)
        jpg_b64 = base64.b64encode(jpeg_bytes).decode("ascii")
        logger.info(
            "PDF page %d → JPEG | %dx%d  %d bytes",
            page_num + 1, pix.width, pix.height, len(jpeg_bytes),
        )
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{jpg_b64}"},
        })
    doc.close()
    return parts


def _run_multimodal_llm(
    media_url: str,
    prompt: str,
    mime_type: str = "",
    max_tokens: int = 4096,
    agent_type: str = "",
    user_id: Optional[str] = None,
) -> str:
    """Send a multimodal completion request with a media URL to Gemini.

    For audio/video media, uses LiteLLM's ``file`` content type with
    ``file_id`` (URL) and ``format`` (MIME type) so Gemini receives
    proper ``file_data`` parts.  For images or unknown types, falls back
    to the ``image_url`` content type.

    Args:
        media_url: Public URL or ``data:`` URI of the media file.
        prompt: Instruction for the model.
        mime_type: MIME type hint (e.g. ``"video/mp4"``).  Required for
            audio/video so Gemini can identify the media type.
        max_tokens: Token budget for the response (default 65536 for
            structured JSON output with entities and transcript).
        agent_type: Sub-agent data type for smart routing overrides.
        user_id: Owner user ID for smart routing preference lookup.

    Returns:
        The model's response text, or an error string prefixed with
        ``"[analysis_error]"``.
    """
    from .. import model_client

    mime_lower = (mime_type or "").lower()
    # Strip codec params for LiteLLM (e.g. "video/webm;codecs=vp9" → "video/webm")
    if ";" in mime_lower:
        mime_lower = mime_lower.split(";")[0].strip()
        mime_type = mime_lower
    is_av = mime_lower.startswith(("audio/", "video/"))

    # ── PDF-to-image conversion for Ollama Cloud ──
    # Ollama Cloud doesn't accept PDF input (returns 500). Convert PDF pages
    # to PNG images so vision models (qwen3-vl etc.) can process them.
    is_pdf = mime_lower == "application/pdf"
    if is_pdf and media_url.startswith("data:"):
        try:
            image_parts = _pdf_data_uri_to_image_parts(media_url)
            if image_parts:
                logger.info("Converted PDF to %d page image(s) for vision model", len(image_parts))
                content_parts: list[dict] = [{"type": "text", "text": prompt}] + image_parts
                messages = [{"role": "user", "content": content_parts}]
                # Skip normal media_part construction
                mime_type = "image/png"
            else:
                raise ValueError("no pages rendered")
        except Exception as exc:
            logger.warning("PDF-to-image conversion failed (%s), sending raw PDF", exc)
            # Fall through to normal path (works for Gemini)
            content_parts = [
                {"type": "text", "text": prompt},
                {"type": "file", "file": {"file_data": media_url}},
            ]
            messages = [{"role": "user", "content": content_parts}]
    else:
        is_image = mime_lower.startswith("image/")
        if media_url.startswith("data:") and is_image:
            # Inline base64 image — use image_url so both Gemini and Ollama can read it
            media_part: dict = {
                "type": "image_url",
                "image_url": {"url": media_url},
            }
        elif media_url.startswith("data:"):
            # Non-image data URI (audio/video) — use file content type (Gemini)
            media_part = {
                "type": "file",
                "file": {"file_data": media_url},
            }
        elif is_av or media_url.startswith("gs://"):
            # Remote URL or GCS URI — file content type for audio/video/gs://
            media_part = {
                "type": "file",
                "file": {"file_id": media_url, "format": mime_type},
            }
        else:
            # Images and other types — use image_url
            media_part = {
                "type": "image_url",
                "image_url": {"url": media_url},
            }

        content_parts = [
            {"type": "text", "text": prompt},
            media_part,
        ]
        messages = [{"role": "user", "content": content_parts}]

    logger.info(
        "Multimodal LLM request | media_url=%s  mime_type=%s  max_tokens=%d",
        media_url,
        mime_type or "(auto)",
        max_tokens,
    )

    try:
        result = model_client.chat_multimodal_for_data_type(
            messages, agent_type=agent_type, user_id=user_id,
            max_tokens=max_tokens, temperature=0.3, mime_type=mime_type,
        )
        logger.info("Multimodal LLM response | chars=%d", len(result))
        logger.debug("Multimodal LLM response text |\n%s", result)
        return result
    except Exception as exc:
        logger.warning(
            "Multimodal model call failed (%s): %s", type(exc).__name__, exc
        )
        return f"[analysis_error] {type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Public entry point — media (video / audio) pipeline
# ---------------------------------------------------------------------------

def analyse_media_payload(
    agent_type: str,
    payload_json: str,
    data_id: str,
    agent_instance_id: str = "",
    agent_purpose: str = "",
    group_context: "Optional[GroupContext]" = None,
    payload_meta: Optional[dict] = None,
) -> dict[str, Any]:
    """Stage → multimodal analyse → viewpoint → embedding pipeline for media sub-agents.

    Mirrors :func:`analyse_payload` but uses the multimodal Gemini path
    instead of text-only LLM analysis.  Media (video/audio) is downloaded
    as binary, staged to GCS, then the source URL is sent to Gemini for
    transcription and analysis.

    Args:
        agent_type: ``AGENT_TYPE`` of the calling sub-agent.
        payload_json: Raw webhook payload as a JSON string.
        data_id: The mem-dog data ID returned by ``write_record()``.
        agent_instance_id: Stable instance ID written into ``meta.json``.
        agent_purpose: Human-readable purpose written into ``meta.json``.
        group_context: Optional group context forwarded from the router.
        payload_meta: Optional dict with ``detection_layer`` and
            ``mime_type`` forwarded from the router.

    Returns:
        A result dict (same shape as :func:`analyse_payload`).
    """
    from ..api_client import ai_client, staging_client

    logger.info(
        "[%s] analyse_media_payload START | data_id=%s  agent_instance=%s",
        agent_type,
        data_id,
        agent_instance_id or "(none)",
    )

    # ------------------------------------------------------------------
    # 1. Parse payload
    # ------------------------------------------------------------------
    try:
        payload = _json.loads(payload_json)
    except (ValueError, TypeError):
        payload = {"raw": payload_json}

    # ------------------------------------------------------------------
    # 2. Stage — download binary media + persist to GCS
    # ------------------------------------------------------------------
    _inject_urls_from_meta(payload, payload_meta)

    try:
        content_bytes, staged_uri, metadata = staging_client.stage_binary(
            payload=payload,
            agent_type=agent_type,
            data_id=data_id,
            agent_instance_id=agent_instance_id,
            agent_purpose=agent_purpose,
            group_ctx=group_context,
            payload_meta=payload_meta,
        )
        logger.info(
            "[%s] binary staging done | staged_uri=%s  size_bytes=%d",
            agent_type,
            staged_uri or "(none)",
            len(content_bytes),
        )
    except Exception as exc:
        logger.warning("Binary staging failed for %s/%s: %s", agent_type, data_id, exc)
        return {
            "status": "error",
            "agent_type": agent_type,
            "data_id": data_id,
            "error": f"[staging_error] {type(exc).__name__}: {exc}",
        }

    # ------------------------------------------------------------------
    # 3. Analyse — send media URL (or base64) to Gemini multimodal
    # ------------------------------------------------------------------
    # Prefer gcs_uri for Vertex AI (native gs:// support, no auth needed)
    source_url = (payload_meta or {}).get("gcs_uri") or ""
    if not source_url:
        source_url = metadata.get("source", {}).get("url", "")
    if not source_url:
        # Try to find URL directly from payload
        for field in _MEDIA_URL_FIELDS:
            url = payload.get(field)
            if url and isinstance(url, str) and url.startswith(("http://", "https://")):
                source_url = url
                break

    owner_uid_routing = group_context.user_id if group_context else None
    prompt, _sys_prompt = _resolve_config(agent_type, payload_meta, user_id=owner_uid_routing)
    mime_type = (payload_meta or {}).get("mime_type", "")
    # Strip codec parameters (e.g. "video/webm;codecs=vp9,opus" → "video/webm")
    if ";" in mime_type:
        mime_type = mime_type.split(";")[0].strip()

    # Always send bytes inline as base64 data URI — we already have the
    # content from staging so there's no need to pass a URL that the LLM
    # provider may not be able to fetch (gs:// on gemini/, auth-gated http).
    ct = mime_type or metadata.get("source", {}).get("content_type", "application/octet-stream")
    b64 = base64.b64encode(content_bytes).decode("ascii")
    media_ref = f"data:{ct};base64,{b64}"
    logger.info(
        "[%s] calling multimodal LLM | inline base64  mime_type=%s  bytes=%d",
        agent_type,
        ct,
        len(content_bytes),
    )

    raw_analysis = _run_multimodal_llm(media_ref, prompt, mime_type=mime_type, agent_type=agent_type, user_id=owner_uid_routing)

    # Report token usage (best-effort) and capture actual model for provenance
    _actual_model_mm = ""
    try:
        from .. import model_client
        from ..api_client import stats_client
        usage = model_client.get_last_usage()
        _actual_model_mm = usage.get("model", "") if usage else ""
        if usage and usage.get("model"):
            owner_uid_for_tokens = group_context.user_id if group_context else None
            if owner_uid_for_tokens:
                stats_client.record_token_usage(
                    user_id=owner_uid_for_tokens,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    model=usage.get("model", ""),
                    agent_type=agent_type,
                    duration_ms=usage.get("duration_ms"),
                )
    except Exception as tok_exc:
        logger.debug("Token usage reporting failed: %s", tok_exc)

    if raw_analysis.startswith("[analysis_error]"):
        logger.warning("[%s] multimodal analysis error | %s", agent_type, raw_analysis)
        return {
            "status": "error",
            "agent_type": agent_type,
            "data_id": data_id,
            "staged_uri": staged_uri,
            "content_length": len(content_bytes),
            "content_source": "binary",
            "metadata": metadata,
            "error": raw_analysis,
        }

    logger.info(
        "[%s] multimodal analysis complete | analysis_chars=%d",
        agent_type,
        len(raw_analysis),
    )

    # ------------------------------------------------------------------
    # 4. Viewpoint + Embedding — fire-and-forget in background thread
    # ------------------------------------------------------------------
    owner_uid = group_context.user_id if group_context else None
    _write_api_results_async(
        agent_type, data_id, raw_analysis, owner_uid,
        ai_engine=_infer_ai_engine(_actual_model_mm) if _actual_model_mm else "",
        model_name=_actual_model_mm,
    )

    logger.info(
        "[%s] analyse_media_payload DONE | data_id=%s  status=success",
        agent_type,
        data_id,
    )

    return {
        "status": "success",
        "agent_type": agent_type,
        "data_id": data_id,
        "staged_uri": staged_uri,
        "content_length": len(content_bytes),
        "content_source": "binary",
        "analysis": raw_analysis,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Document text extraction helpers
# ---------------------------------------------------------------------------

def _extract_document_text(content_bytes: bytes, mime_type: str) -> str:
    """Extract readable text from a document binary (PDF, DOCX, XLSX, PPTX).

    Delegates to :mod:`document_parse` (``DOCUMENT_PARSER`` flag).
    """
    from ..document_parse import parse_document

    return parse_document(content_bytes, mime_type).markdown


# ---------------------------------------------------------------------------
# Public entry point — document pipeline (PDF, Office)
# ---------------------------------------------------------------------------

def analyse_document_payload(
    agent_type: str,
    payload_json: str,
    data_id: str,
    agent_instance_id: str = "",
    agent_purpose: str = "",
    group_context: "Optional[GroupContext]" = None,
    payload_meta: Optional[dict] = None,
) -> dict[str, Any]:
    """Stage → extract text → LLM analyse → viewpoint → embedding for documents.

    Extracts readable text from PDF/Office binaries and sends the text to the
    LLM.  If extraction yields < 50 chars (e.g. scanned/image PDF), falls back
    to :func:`analyse_media_payload` for Gemini vision.
    """
    from ..api_client import ai_client, staging_client

    logger.info(
        "[%s] analyse_document_payload START | data_id=%s", agent_type, data_id,
    )

    # 1. Parse payload
    try:
        payload = _json.loads(payload_json)
    except (ValueError, TypeError):
        payload = {"raw": payload_json}

    # 2. Stage binary
    # Ensure the URL from payload_meta is visible to stage_binary
    meta_url = (payload_meta or {}).get("url")
    if meta_url and isinstance(meta_url, str) and "url" not in payload:
        payload["url"] = meta_url

    try:
        content_bytes, staged_uri, metadata = staging_client.stage_binary(
            payload=payload,
            agent_type=agent_type,
            data_id=data_id,
            agent_instance_id=agent_instance_id,
            agent_purpose=agent_purpose,
            group_ctx=group_context,
            payload_meta=payload_meta,
        )
        logger.info(
            "[%s] binary staging done | staged_uri=%s  size=%d",
            agent_type, staged_uri or "(none)", len(content_bytes),
        )
    except Exception as exc:
        logger.warning("Binary staging failed for %s/%s: %s", agent_type, data_id, exc)
        return {
            "status": "error",
            "agent_type": agent_type,
            "data_id": data_id,
            "error": f"[staging_error] {type(exc).__name__}: {exc}",
        }

    # 3. Parse document → markdown + persist artifacts
    mime_type = (payload_meta or {}).get("mime_type", "")
    from ..document_parse import parse_document
    from ..document_parse.persist import persist_parsed_document

    parsed_doc = parse_document(content_bytes, mime_type)
    extracted_text = parsed_doc.markdown
    owner_uid = group_context.user_id if group_context else None
    parsed_store = persist_parsed_document(data_id, parsed_doc, user_id=owner_uid)
    logger.info(
        "[%s] document parse | parser=%s pages=%s chars=%d persist=%s",
        agent_type,
        parsed_doc.parser,
        parsed_doc.page_count,
        len(extracted_text),
        parsed_store.get("parse_status", parsed_store.get("status")),
    )

    if len(extracted_text.strip()) < 50:
        # Scanned / image-heavy document — fall back to Gemini vision
        logger.info(
            "[%s] extracted text too short (%d chars), falling back to media pipeline",
            agent_type, len(extracted_text),
        )
        return analyse_media_payload(
            agent_type, payload_json, data_id,
            agent_instance_id, agent_purpose,
            group_context, payload_meta,
        )

    # 4. LLM analysis on extracted text
    is_truncated = len(extracted_text) > _MAX_CONTENT_CHARS
    owner_uid_routing = group_context.user_id if group_context else None
    prompt, system_prompt = _resolve_config(agent_type, payload_meta, user_id=owner_uid_routing, is_truncated=is_truncated)
    truncated = extracted_text[:_MAX_CONTENT_CHARS]

    logger.info(
        "[%s] calling LLM on extracted text | chars=%d",
        agent_type, len(truncated),
    )
    raw_analysis = _run_llm(truncated, prompt, agent_type=agent_type, user_id=owner_uid_routing, system_prompt=system_prompt)

    # Report token usage (best-effort) and capture actual model for provenance
    _actual_model_doc = ""
    try:
        from .. import model_client
        from ..api_client import stats_client
        usage = model_client.get_last_usage()
        _actual_model_doc = usage.get("model", "") if usage else ""
        if usage and usage.get("model"):
            owner_uid_for_tokens = group_context.user_id if group_context else None
            if owner_uid_for_tokens:
                stats_client.record_token_usage(
                    user_id=owner_uid_for_tokens,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    model=usage.get("model", ""),
                    agent_type=agent_type,
                    duration_ms=usage.get("duration_ms"),
                )
    except Exception as tok_exc:
        logger.debug("Token usage reporting failed: %s", tok_exc)

    if raw_analysis.startswith("[analysis_error]"):
        logger.warning("[%s] LLM analysis error | %s", agent_type, raw_analysis)
        return {
            "status": "error",
            "agent_type": agent_type,
            "data_id": data_id,
            "staged_uri": staged_uri,
            "content_length": len(content_bytes),
            "content_source": "document",
            "metadata": metadata,
            "error": raw_analysis,
        }

    logger.info("[%s] document analysis complete | chars=%d", agent_type, len(raw_analysis))

    # 5. Viewpoint
    owner_uid = group_context.user_id if group_context else None
    analysis_json = _parse_analysis_to_json(raw_analysis)
    viewpoint = ai_client.create_viewpoint(
        data_id=data_id,
        name=f"{agent_type} — webhook analysis",
        analysis_text=analysis_json,
        user_id=owner_uid,
        ai_engine=_infer_ai_engine(_actual_model_doc) if _actual_model_doc else None,
        model_name=_actual_model_doc or None,
    )

    # 6. Embedding
    embedding = ai_client.create_embedding(data_id=data_id, user_id=owner_uid)

    logger.info("[%s] analyse_document_payload DONE | data_id=%s", agent_type, data_id)

    return {
        "status": "success",
        "agent_type": agent_type,
        "data_id": data_id,
        "staged_uri": staged_uri,
        "content_length": len(content_bytes),
        "content_source": "document",
        "analysis": raw_analysis,
        "viewpoint": viewpoint,
        "embedding": embedding,
        "metadata": metadata,
        "parsed": parsed_doc.to_dict(),
        "parsed_store": parsed_store,
    }


# ---------------------------------------------------------------------------
# Binary metadata extraction helpers (stdlib only)
# ---------------------------------------------------------------------------

def _extract_binary_metadata(content_bytes: bytes, mime_type: str, agent_type: str) -> str:
    """Extract metadata from binary files using stdlib only.

    Returns a human-readable metadata string for the LLM to analyse.
    """
    size = len(content_bytes)

    # --- Archive ---
    if agent_type == "archive":
        return _extract_archive_metadata(content_bytes, mime_type, size)

    # --- Medical Imaging (DICOM) ---
    if agent_type == "medical_imaging":
        return _extract_dicom_metadata(content_bytes, size)

    # --- 3D Models ---
    if agent_type == "model_3d":
        return _extract_3d_metadata(content_bytes, mime_type, size)

    # --- LiDAR ---
    if agent_type == "lidar":
        return _extract_lidar_metadata(content_bytes, mime_type, size)

    # --- Satellite ---
    if agent_type == "satellite":
        return _extract_satellite_metadata(content_bytes, mime_type, size)

    # --- Scientific (binary) ---
    if agent_type == "scientific":
        return _extract_scientific_metadata(content_bytes, mime_type, size)

    return f"Binary file: {mime_type or 'unknown'}, {size} bytes. No detailed metadata extracted."


def _extract_archive_metadata(content_bytes: bytes, mime_type: str, size: int) -> str:
    """Extract file listing from ZIP or TAR archives."""
    buf = io.BytesIO(content_bytes)

    # Try ZIP
    if zipfile.is_zipfile(buf):
        buf.seek(0)
        try:
            with zipfile.ZipFile(buf) as zf:
                names = zf.namelist()
                total_uncompressed = sum(i.file_size for i in zf.infolist())
                lines = [
                    f"ZIP archive: {size} bytes compressed, {total_uncompressed} bytes uncompressed",
                    f"Total entries: {len(names)}",
                    "",
                    "File listing (first 50):",
                ]
                for name in names[:50]:
                    info = zf.getinfo(name)
                    lines.append(f"  {name}  ({info.file_size} bytes)")
                if len(names) > 50:
                    lines.append(f"  ... and {len(names) - 50} more entries")
                return "\n".join(lines)
        except Exception as exc:
            logger.debug("ZIP listing failed: %s", exc)

    # Try TAR (including gzip/bzip2)
    buf.seek(0)
    for mode in ("r:gz", "r:bz2", "r:xz", "r:"):
        try:
            buf.seek(0)
            with tarfile.open(fileobj=buf, mode=mode) as tf:
                members = tf.getmembers()
                total_size = sum(m.size for m in members)
                lines = [
                    f"TAR archive ({mode}): {size} bytes, {total_size} bytes uncompressed",
                    f"Total entries: {len(members)}",
                    "",
                    "File listing (first 50):",
                ]
                for m in members[:50]:
                    kind = "dir" if m.isdir() else "file"
                    lines.append(f"  {m.name}  ({m.size} bytes, {kind})")
                if len(members) > 50:
                    lines.append(f"  ... and {len(members) - 50} more entries")
                return "\n".join(lines)
        except Exception:
            continue

    return f"Archive file: {mime_type or 'unknown'}, {size} bytes. Could not parse listing."


def _extract_dicom_metadata(content_bytes: bytes, size: int) -> str:
    """Extract basic DICOM header metadata using struct."""
    lines = [f"DICOM file: {size} bytes"]

    # DICOM files have a 128-byte preamble followed by 'DICM'
    if len(content_bytes) >= 132:
        magic = content_bytes[128:132]
        if magic == b"DICM":
            lines.append("Valid DICOM preamble detected (DICM magic)")
        else:
            lines.append("No DICM magic at offset 128 — may be raw DICOM or non-standard")

    # Try to extract some basic DICOM tags (Group, Element, VR)
    # DICOM tags start at byte 132 for standard files
    if len(content_bytes) > 200:
        # Look for common text patterns in the header region
        header_region = content_bytes[128:min(2048, len(content_bytes))]
        # Try to find patient/study info as ASCII strings
        try:
            text = header_region.decode("ascii", errors="ignore")
            # Filter to printable sequences
            printable_seqs = []
            current = []
            for ch in text:
                if ch.isprintable() and ch != "\x00":
                    current.append(ch)
                else:
                    if len(current) >= 4:
                        printable_seqs.append("".join(current))
                    current = []
            if printable_seqs:
                lines.append("Header strings: " + " | ".join(printable_seqs[:15]))
        except Exception:
            pass

    return "\n".join(lines)


def _extract_3d_metadata(content_bytes: bytes, mime_type: str, size: int) -> str:
    """Extract metadata from 3D model files (OBJ, STL, GLTF/GLB)."""
    mime_lower = (mime_type or "").lower()

    # OBJ (text format)
    if "obj" in mime_lower or content_bytes[:2] == b"# ":
        try:
            text = content_bytes[:50000].decode("utf-8", errors="ignore")
            vertices = text.count("\nv ") + (1 if text.startswith("v ") else 0)
            faces = text.count("\nf ") + (1 if text.startswith("f ") else 0)
            return f"OBJ 3D model: {size} bytes\nVertices: ~{vertices}\nFaces: ~{faces}"
        except Exception:
            pass

    # STL binary: 80-byte header + 4-byte triangle count
    if len(content_bytes) >= 84 and b"solid" not in content_bytes[:5].lower():
        try:
            header = content_bytes[:80].decode("ascii", errors="ignore").strip("\x00").strip()
            tri_count = struct.unpack_from("<I", content_bytes, 80)[0]
            return f"STL binary 3D model: {size} bytes\nHeader: {header or '(empty)'}\nTriangles: {tri_count}"
        except Exception:
            pass

    # STL ASCII
    if content_bytes[:5].lower().startswith(b"solid"):
        try:
            text = content_bytes[:50000].decode("ascii", errors="ignore")
            facets = text.count("facet normal")
            return f"STL ASCII 3D model: {size} bytes\nFacets: ~{facets}"
        except Exception:
            pass

    # GLTF JSON
    if b'"asset"' in content_bytes[:1000]:
        try:
            gltf = _json.loads(content_bytes)
            asset = gltf.get("asset", {})
            meshes = len(gltf.get("meshes", []))
            nodes = len(gltf.get("nodes", []))
            materials = len(gltf.get("materials", []))
            return (
                f"glTF 3D model: {size} bytes\n"
                f"Generator: {asset.get('generator', 'unknown')}\n"
                f"Version: {asset.get('version', '?')}\n"
                f"Meshes: {meshes}, Nodes: {nodes}, Materials: {materials}"
            )
        except Exception:
            pass

    # GLB binary: magic 0x46546C67
    if content_bytes[:4] == b"glTF":
        try:
            version = struct.unpack_from("<I", content_bytes, 4)[0]
            total_len = struct.unpack_from("<I", content_bytes, 8)[0]
            return f"GLB binary 3D model: {size} bytes\nglTF version: {version}\nDeclared length: {total_len}"
        except Exception:
            pass

    return f"3D model file: {mime_type or 'unknown'}, {size} bytes."


def _extract_lidar_metadata(content_bytes: bytes, mime_type: str, size: int) -> str:
    """Extract metadata from LiDAR point cloud files (PCD, LAS)."""
    # PCD (text header)
    if content_bytes[:3] == b"# ." or content_bytes[:7] == b"VERSION":
        try:
            header_end = content_bytes.find(b"DATA")
            if header_end > 0:
                header = content_bytes[:header_end + 20].decode("ascii", errors="ignore")
                return f"PCD point cloud: {size} bytes\n\n{header.strip()}"
        except Exception:
            pass

    # LAS binary header (version 1.x)
    if content_bytes[:4] == b"LASF" and len(content_bytes) >= 227:
        try:
            major = content_bytes[24]
            minor = content_bytes[25]
            # Point count at offset 107 (uint32) for LAS 1.2
            point_count = struct.unpack_from("<I", content_bytes, 107)[0]
            # Scale factors at offset 131 (3 doubles)
            sx, sy, sz = struct.unpack_from("<ddd", content_bytes, 131)
            # Offsets at offset 155 (3 doubles)
            ox, oy, oz = struct.unpack_from("<ddd", content_bytes, 155)
            # Min/max at offset 179 (6 doubles: max_x, min_x, max_y, min_y, max_z, min_z)
            bounds = struct.unpack_from("<dddddd", content_bytes, 179)
            return (
                f"LAS point cloud: {size} bytes\n"
                f"Version: {major}.{minor}\n"
                f"Point count: {point_count}\n"
                f"Scale: ({sx}, {sy}, {sz})\n"
                f"Offset: ({ox}, {oy}, {oz})\n"
                f"Bounds X: [{bounds[1]:.2f}, {bounds[0]:.2f}]\n"
                f"Bounds Y: [{bounds[3]:.2f}, {bounds[2]:.2f}]\n"
                f"Bounds Z: [{bounds[5]:.2f}, {bounds[4]:.2f}]"
            )
        except Exception as exc:
            logger.debug("LAS header parsing failed: %s", exc)

    return f"LiDAR point cloud file: {mime_type or 'unknown'}, {size} bytes."


def _extract_satellite_metadata(content_bytes: bytes, mime_type: str, size: int) -> str:
    """Extract metadata from satellite imagery files (GeoTIFF, HDF5, NetCDF)."""
    mime_lower = (mime_type or "").lower()

    # TIFF / GeoTIFF
    if mime_lower in ("image/tiff", "application/x-geotiff") or content_bytes[:2] in (b"II", b"MM"):
        try:
            byte_order = "<" if content_bytes[:2] == b"II" else ">"
            magic = struct.unpack_from(f"{byte_order}H", content_bytes, 2)[0]
            if magic == 42:  # Standard TIFF
                ifd_offset = struct.unpack_from(f"{byte_order}I", content_bytes, 4)[0]
                return (
                    f"TIFF/GeoTIFF: {size} bytes\n"
                    f"Byte order: {'little-endian' if byte_order == '<' else 'big-endian'}\n"
                    f"First IFD offset: {ifd_offset}"
                )
            elif magic == 43:  # BigTIFF
                return f"BigTIFF/GeoTIFF: {size} bytes"
        except Exception:
            pass

    # HDF5 magic: \x89HDF\r\n\x1a\n
    if content_bytes[:8] == b"\x89HDF\r\n\x1a\n":
        return f"HDF5 file: {size} bytes. Contains hierarchical scientific datasets."

    # NetCDF magic: CDF\x01 or CDF\x02
    if content_bytes[:3] == b"CDF":
        version = content_bytes[3] if len(content_bytes) > 3 else 0
        return f"NetCDF file (version {version}): {size} bytes. Contains array-oriented scientific data."

    return f"Satellite data file: {mime_type or 'unknown'}, {size} bytes."


def _extract_scientific_metadata(content_bytes: bytes, mime_type: str, size: int) -> str:
    """Extract metadata from scientific data files."""
    mime_lower = (mime_type or "").lower()

    # HDF5
    if content_bytes[:8] == b"\x89HDF\r\n\x1a\n":
        return f"HDF5 scientific data: {size} bytes."

    # PDB (protein data bank — text)
    if "pdb" in mime_lower or content_bytes[:6] in (b"HEADER", b"ATOM  ", b"HETATM"):
        try:
            text = content_bytes[:20000].decode("ascii", errors="ignore")
            atoms = text.count("\nATOM  ") + text.count("\nHETATM")
            return f"PDB protein structure: {size} bytes\nAtom records: ~{atoms}"
        except Exception:
            pass

    return f"Scientific data file: {mime_type or 'unknown'}, {size} bytes."


# Text-based scientific MIME types that should use the text pipeline
_SCIENTIFIC_TEXT_MIMES = frozenset({
    "application/x-fastq",
    "application/x-vcf",
    "chemical/x-pdb",
    "chemical/x-mdl-sdfile",
    "application/x-lims",
})


# ---------------------------------------------------------------------------
# Public entry point — binary metadata pipeline
# ---------------------------------------------------------------------------

def analyse_binary_metadata_payload(
    agent_type: str,
    payload_json: str,
    data_id: str,
    agent_instance_id: str = "",
    agent_purpose: str = "",
    group_context: "Optional[GroupContext]" = None,
    payload_meta: Optional[dict] = None,
) -> dict[str, Any]:
    """Stage → extract metadata → LLM analyse → viewpoint → embedding for binary formats.

    Extracts structural metadata from binary files using stdlib and sends the
    metadata text to the LLM for analysis.  No binary data is sent to the LLM.
    """
    from ..api_client import ai_client, staging_client

    logger.info(
        "[%s] analyse_binary_metadata_payload START | data_id=%s", agent_type, data_id,
    )

    # 1. Parse payload
    try:
        payload = _json.loads(payload_json)
    except (ValueError, TypeError):
        payload = {"raw": payload_json}

    # 2. Stage binary
    # Ensure the URL from payload_meta is visible to stage_binary
    meta_url = (payload_meta or {}).get("url")
    if meta_url and isinstance(meta_url, str) and "url" not in payload:
        payload["url"] = meta_url

    try:
        content_bytes, staged_uri, metadata = staging_client.stage_binary(
            payload=payload,
            agent_type=agent_type,
            data_id=data_id,
            agent_instance_id=agent_instance_id,
            agent_purpose=agent_purpose,
            group_ctx=group_context,
            payload_meta=payload_meta,
        )
        logger.info(
            "[%s] binary staging done | staged_uri=%s  size=%d",
            agent_type, staged_uri or "(none)", len(content_bytes),
        )
    except Exception as exc:
        logger.warning("Binary staging failed for %s/%s: %s", agent_type, data_id, exc)
        return {
            "status": "error",
            "agent_type": agent_type,
            "data_id": data_id,
            "error": f"[staging_error] {type(exc).__name__}: {exc}",
        }

    # 3. Extract metadata from binary
    mime_type = (payload_meta or {}).get("mime_type", "")
    metadata_text = _extract_binary_metadata(content_bytes, mime_type, agent_type)

    # 4. LLM analysis on metadata text
    is_truncated = len(metadata_text) > _MAX_CONTENT_CHARS
    owner_uid_routing = group_context.user_id if group_context else None
    prompt, system_prompt = _resolve_config(agent_type, payload_meta, user_id=owner_uid_routing, is_truncated=is_truncated)
    truncated = metadata_text[:_MAX_CONTENT_CHARS]

    logger.info(
        "[%s] calling LLM on extracted metadata | chars=%d",
        agent_type, len(truncated),
    )
    raw_analysis = _run_llm(truncated, prompt, agent_type=agent_type, user_id=owner_uid_routing, system_prompt=system_prompt)

    # Report token usage (best-effort) and capture actual model for provenance
    _actual_model_bin = ""
    try:
        from .. import model_client
        from ..api_client import stats_client
        usage = model_client.get_last_usage()
        _actual_model_bin = usage.get("model", "") if usage else ""
        if usage and usage.get("model"):
            owner_uid_for_tokens = group_context.user_id if group_context else None
            if owner_uid_for_tokens:
                stats_client.record_token_usage(
                    user_id=owner_uid_for_tokens,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    model=usage.get("model", ""),
                    agent_type=agent_type,
                    duration_ms=usage.get("duration_ms"),
                )
    except Exception as tok_exc:
        logger.debug("Token usage reporting failed: %s", tok_exc)

    if raw_analysis.startswith("[analysis_error]"):
        logger.warning("[%s] binary metadata analysis error | %s", agent_type, raw_analysis)
        return {
            "status": "error",
            "agent_type": agent_type,
            "data_id": data_id,
            "staged_uri": staged_uri,
            "content_length": len(content_bytes),
            "content_source": "binary_metadata",
            "metadata": metadata,
            "error": raw_analysis,
        }

    logger.info("[%s] binary metadata analysis complete | chars=%d", agent_type, len(raw_analysis))

    # 5. Viewpoint
    owner_uid = group_context.user_id if group_context else None
    analysis_json = _parse_analysis_to_json(raw_analysis)
    viewpoint = ai_client.create_viewpoint(
        data_id=data_id,
        name=f"{agent_type} — webhook analysis",
        analysis_text=analysis_json,
        user_id=owner_uid,
        ai_engine=_infer_ai_engine(_actual_model_bin) if _actual_model_bin else None,
        model_name=_actual_model_bin or None,
    )

    # 6. Embedding
    embedding = ai_client.create_embedding(data_id=data_id, user_id=owner_uid)

    logger.info("[%s] analyse_binary_metadata_payload DONE | data_id=%s", agent_type, data_id)

    return {
        "status": "success",
        "agent_type": agent_type,
        "data_id": data_id,
        "staged_uri": staged_uri,
        "content_length": len(content_bytes),
        "content_source": "binary_metadata",
        "analysis": raw_analysis,
        "viewpoint": viewpoint,
        "embedding": embedding,
        "metadata": metadata,
    }

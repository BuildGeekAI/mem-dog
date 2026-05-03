"""Staging client — download external data and persist to GCS.

Every sub-agent calls :meth:`StagingClient.stage` to:

1. Fetch the payload's content (remote URL or inline field).
2. Upload the raw content to
   ``gs://{WEBHOOK_STAGING_BUCKET}/{agent_type}/{data_id}/raw``.
3. Build and upload a rich ``meta.json`` provenance document alongside it.

The staged files are **permanent** — they are linked to the mem-dog
``data_id`` and serve as the authoritative record of what was ingested.

GCS bucket layout::

    {WEBHOOK_STAGING_BUCKET}/
      {agent_type}/
        {data_id}/
          raw         ← full downloaded content (UTF-8 text)
          meta.json   ← provenance metadata

Configuration
-------------
Set ``WEBHOOK_STAGING_BUCKET`` in the agent ``.env``.  If the variable is
empty the client operates in **local-only mode**: content is fetched and
returned but nothing is uploaded to GCS (useful for local dev without a
bucket).
"""

import json as _json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from .config import DEFAULT_TIMEOUT, WEBHOOK_STAGING_BUCKET
from .session import _session

logger = logging.getLogger("mem_dog.webhook.api_client.staging")

# Payload fields checked in priority order when looking for a remote URL
_URL_FIELDS = ("url", "source_url", "file_url", "download_url", "href", "link")

# Payload fields checked in priority order for inline text content
_CONTENT_FIELDS = ("content", "text", "body", "data", "raw", "message", "payload")


class StagingClient:
    """Downloads external data and stages it in GCS with provenance metadata.

    Instantiated once at module load (singleton pattern).  When
    ``WEBHOOK_STAGING_BUCKET`` is empty, GCS writes are skipped and only
    the fetched content is returned so local development works without
    cloud credentials.
    """

    def __init__(self, bucket_name: str = WEBHOOK_STAGING_BUCKET) -> None:
        self._bucket_name = bucket_name
        self._gcs: Any = None  # lazy-initialised GCS client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stage(
        self,
        payload: dict,
        agent_type: str,
        data_id: str,
        agent_instance_id: str = "",
        agent_purpose: str = "",
        group_ctx: Any = None,
        payload_meta: Optional[dict] = None,
    ) -> tuple[str, str, dict]:
        """Fetch content and persist it to GCS with full provenance metadata.

        Args:
            payload: The decoded webhook payload dict.
            agent_type: The sub-agent type string (e.g. ``"json"``).
            data_id: The mem-dog data ID returned by ``write_record()``.
            agent_instance_id: Stable instance ID of the calling sub-agent.
            agent_purpose: Human-readable purpose of the calling sub-agent.
            group_ctx: Optional :class:`~group_context.GroupContext` for the
                caller.  Used to populate the ``group`` section of
                ``meta.json``.
            payload_meta: Optional dict carrying detection-layer metadata
                (``detection_layer``, ``mime_type``) forwarded from the
                router.

        Returns:
            A three-tuple of ``(content, staged_uri, metadata)`` where:

            * *content* is the full downloaded text (un-truncated).
            * *staged_uri* is the GCS URI of the raw object, or an empty
              string when the bucket is not configured.
            * *metadata* is the full ``meta.json`` dict that was written.
        """
        content, source, source_meta = self._fetch(
            payload, payload_meta=payload_meta, data_id=data_id
        )
        meta = self._build_meta(
            payload=payload,
            data_id=data_id,
            agent_type=agent_type,
            agent_instance_id=agent_instance_id,
            agent_purpose=agent_purpose,
            group_ctx=group_ctx,
            payload_meta=payload_meta or {},
            source_meta=source_meta,
        )

        staged_uri = ""
        if self._bucket_name:
            staged_uri = self._upload(agent_type, data_id, content, meta)
        else:
            logger.debug(
                "WEBHOOK_STAGING_BUCKET not set — skipping GCS upload for %s/%s",
                agent_type,
                data_id,
            )

        return content, staged_uri, meta

    # ------------------------------------------------------------------
    # Fetch helpers
    # ------------------------------------------------------------------

    def _fetch(
        self,
        payload: dict,
        payload_meta: Optional[dict] = None,
        data_id: Optional[str] = None,
    ) -> tuple[str, str, dict]:
        """Download or extract the main content from a payload.

        When ``payload_meta`` has ``is_downloaded`` true and ``data_id`` is set,
        content is already stored in mem-dog; skip URL download and fetch from
        the API instead.

        Returns:
            A three-tuple of ``(content, source_label, source_meta)`` where
            *source_label* is ``"api"``, ``"url"``, ``"inline"``, or
            ``"payload_dump"`` and *source_meta* carries provenance.
        """
        meta = payload_meta or {}

        # Prefer reading directly from GCS when gcs_uri is available
        gcs_uri = meta.get("gcs_uri") or ""
        if gcs_uri and gcs_uri.startswith("gs://"):
            try:
                content_bytes, content_type = self._read_gcs_uri(gcs_uri)
                content = content_bytes.decode("utf-8", errors="replace")
                return (
                    content,
                    "gcs",
                    {
                        "gcs_uri": gcs_uri,
                        "content_type": content_type,
                        "size_bytes": len(content_bytes),
                    },
                )
            except Exception as exc:
                logger.warning(
                    "Failed to read from GCS URI %s: %s — falling back to API",
                    gcs_uri, exc,
                )

        if meta.get("is_downloaded") and data_id:
            try:
                from . import data_client
                content, content_type = data_client.get_raw(data_id, user_id=meta.get("user_id"))
                return (
                    content,
                    "api",
                    {
                        "data_id": data_id,
                        "content_type": content_type,
                        "size_bytes": len(content.encode("utf-8", errors="replace")),
                    },
                )
            except Exception as exc:
                logger.warning(
                    "Failed to fetch content from API for data_id=%s (is_downloaded): %s",
                    data_id,
                    exc,
                )
                # Fall through to URL/inline/payload_dump
        for field in _URL_FIELDS:
            url = payload.get(field)
            if url and isinstance(url, str) and url.startswith(("http://", "https://")):
                result = self._download_url(url, field)
                if result is not None:
                    return result

        for field in _CONTENT_FIELDS:
            value = payload.get(field)
            if value and isinstance(value, str):
                return (
                    value,
                    "inline",
                    {"field": field, "size_bytes": len(value.encode())},
                )

        dumped = _json.dumps(payload, indent=2)
        return (
            dumped,
            "payload_dump",
            {"field": None, "size_bytes": len(dumped.encode())},
        )

    def _download_url(
        self, url: str, url_field: str
    ) -> Optional[tuple[str, str, dict]]:
        """Attempt to download *url* and return ``(content, "url", meta)`` or ``None``."""
        t0 = time.monotonic()
        try:
            resp = _session.get(url, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            content = resp.text
            return (
                content,
                "url",
                {
                    "url": url,
                    "url_field": url_field,
                    "http_status": resp.status_code,
                    "content_type": resp.headers.get("Content-Type", ""),
                    "size_bytes": len(resp.content),
                    "download_ms": elapsed_ms,
                },
            )
        except Exception as exc:
            logger.warning("Failed to download %s from field %r: %s", url, url_field, exc)
            return None

    # ------------------------------------------------------------------
    # Metadata builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_meta(
        payload: dict,
        data_id: str,
        agent_type: str,
        agent_instance_id: str,
        agent_purpose: str,
        group_ctx: Any,
        payload_meta: dict,
        source_meta: dict,
    ) -> dict:
        """Construct the full provenance metadata dict."""
        meta: dict = {
            "data_id": data_id,
            "staged_at": datetime.now(timezone.utc).isoformat(),
            "source": source_meta,
            "agent": {
                "type": agent_type,
                "instance_id": agent_instance_id,
                "purpose": agent_purpose,
            },
            "detection": {
                "layer": payload_meta.get("detection_layer", ""),
                "mime_type": payload_meta.get("mime_type", ""),
            },
        }

        if group_ctx is not None:
            from dataclasses import asdict as _asdict
            try:
                meta["group"] = _asdict(group_ctx)
            except TypeError:
                meta["group"] = {
                    "user_id": getattr(group_ctx, "user_id", ""),
                    "group_id": getattr(group_ctx, "group_id", ""),
                    "prefix": getattr(group_ctx, "prefix", ""),
                    "timeline_memory_id": getattr(group_ctx, "timeline_memory_id", ""),
                    "session_memory_id": getattr(group_ctx, "session_memory_id", ""),
                }

        return meta

    # ------------------------------------------------------------------
    # GCS upload
    # ------------------------------------------------------------------

    def _gcs_client(self) -> Any:
        """Lazy-initialise and return the GCS client."""
        if self._gcs is None:
            try:
                from google.cloud import storage  # type: ignore[import]
                self._gcs = storage.Client()
            except ImportError as exc:
                raise RuntimeError(
                    "google-cloud-storage is not installed. "
                    "Add it to requirements.txt or unset WEBHOOK_STAGING_BUCKET."
                ) from exc
        return self._gcs

    def _read_gcs_uri(self, gcs_uri: str) -> tuple[bytes, str]:
        """Read raw bytes from a ``gs://bucket/path`` URI.

        Returns:
            A two-tuple of ``(content_bytes, content_type)``.
        """
        # Parse gs://bucket/path
        without_scheme = gcs_uri[len("gs://"):]
        bucket_name, _, blob_path = without_scheme.partition("/")
        if not bucket_name or not blob_path:
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")

        client = self._gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        content_bytes = blob.download_as_bytes()
        content_type = blob.content_type or "application/octet-stream"
        logger.info(
            "Read %d bytes from GCS URI %s (content_type=%s)",
            len(content_bytes), gcs_uri, content_type,
        )
        return content_bytes, content_type

    def _upload(
        self, agent_type: str, data_id: str, content: str, meta: dict
    ) -> str:
        """Write ``raw`` and ``meta.json`` to GCS and return the raw URI.

        Args:
            agent_type: Used as the top-level GCS prefix.
            data_id: Unique identifier for this staged record.
            content: Full downloaded text.
            meta: Provenance metadata dict.

        Returns:
            GCS URI of the raw object, e.g.
            ``gs://my-bucket/json/uuid/raw``.
        """
        bucket = self._gcs_client().bucket(self._bucket_name)
        prefix = f"{agent_type}/{data_id}"

        raw_blob = bucket.blob(f"{prefix}/raw")
        raw_blob.upload_from_string(content, content_type="text/plain; charset=utf-8")

        meta_with_gcs = dict(meta)
        raw_uri = f"gs://{self._bucket_name}/{prefix}/raw"
        meta_with_gcs["gcs"] = {
            "bucket": self._bucket_name,
            "raw_path": f"{prefix}/raw",
            "meta_path": f"{prefix}/meta.json",
            "uri": raw_uri,
        }

        meta_blob = bucket.blob(f"{prefix}/meta.json")
        meta_blob.upload_from_string(
            _json.dumps(meta_with_gcs, indent=2),
            content_type="application/json",
        )

        logger.info(
            "Staged %s/%s → %s (%d bytes)",
            agent_type,
            data_id,
            raw_uri,
            len(content.encode()),
        )
        return raw_uri

    # ------------------------------------------------------------------
    # Binary media staging
    # ------------------------------------------------------------------

    def stage_binary(
        self,
        payload: dict,
        agent_type: str,
        data_id: str,
        agent_instance_id: str = "",
        agent_purpose: str = "",
        group_ctx: Any = None,
        payload_meta: Optional[dict] = None,
    ) -> tuple[bytes, str, dict]:
        """Download binary media and persist to GCS with correct content-type.

        Similar to :meth:`stage` but operates on raw bytes (video/audio)
        instead of UTF-8 text.

        Returns:
            A three-tuple of ``(content_bytes, staged_uri, metadata)``.
        """
        content_bytes, source_url, source_meta = self._fetch_binary(
            payload, payload_meta=payload_meta, data_id=data_id
        )
        meta = self._build_meta(
            payload=payload,
            data_id=data_id,
            agent_type=agent_type,
            agent_instance_id=agent_instance_id,
            agent_purpose=agent_purpose,
            group_ctx=group_ctx,
            payload_meta=payload_meta or {},
            source_meta=source_meta,
        )

        staged_uri = ""
        if self._bucket_name:
            staged_uri = self._upload_binary(
                agent_type, data_id, content_bytes, meta,
                content_type=source_meta.get("content_type", "application/octet-stream"),
            )
        else:
            logger.debug(
                "WEBHOOK_STAGING_BUCKET not set — skipping binary GCS upload for %s/%s",
                agent_type,
                data_id,
            )

        return content_bytes, staged_uri, meta

    def _fetch_binary(
        self,
        payload: dict,
        payload_meta: Optional[dict] = None,
        data_id: Optional[str] = None,
    ) -> tuple[bytes, str, dict]:
        """Download binary media content from a URL or the API.

        When ``payload_meta`` has ``is_downloaded`` true and ``data_id`` is set,
        content is already stored in mem-dog; fetch bytes from the API instead
        of re-downloading from the URL.

        Returns:
            A three-tuple of ``(content_bytes, source_url, source_meta)``.
        """
        meta = payload_meta or {}

        # Prefer reading directly from GCS when gcs_uri is available (IAM-based, no API key)
        gcs_uri = meta.get("gcs_uri") or ""
        if gcs_uri and gcs_uri.startswith("gs://"):
            try:
                content_bytes, content_type = self._read_gcs_uri(gcs_uri)
                source_url = ""
                for field in _URL_FIELDS:
                    url = payload.get(field)
                    if url and isinstance(url, str) and url.startswith(("http://", "https://")):
                        source_url = url
                        break
                return (
                    content_bytes,
                    source_url,
                    {
                        "gcs_uri": gcs_uri,
                        "content_type": content_type,
                        "size_bytes": len(content_bytes),
                        "source": "gcs",
                    },
                )
            except Exception as exc:
                logger.warning(
                    "Failed to read from GCS URI %s: %s — falling back to API",
                    gcs_uri, exc,
                )

        # If content was already downloaded by UrlDownloadAgent, fetch from API
        if meta.get("is_downloaded") and data_id:
            try:
                from . import data_client
                content_bytes, content_type = data_client.get_raw_bytes(
                    data_id, user_id=meta.get("user_id")
                )
                # Preserve the original URL for Gemini multimodal
                source_url = ""
                for field in _URL_FIELDS:
                    url = payload.get(field)
                    if url and isinstance(url, str) and url.startswith(("http://", "https://")):
                        source_url = url
                        break
                return (
                    content_bytes,
                    source_url,
                    {
                        "data_id": data_id,
                        "content_type": content_type,
                        "size_bytes": len(content_bytes),
                        "source": "api",
                    },
                )
            except Exception as exc:
                logger.warning(
                    "Failed to fetch binary from API for data_id=%s (is_downloaded): %s",
                    data_id,
                    exc,
                )
                # Fall through to URL download

        for field in _URL_FIELDS:
            url = payload.get(field)
            if url and isinstance(url, str) and url.startswith(("http://", "https://")):
                result = self._download_binary(url, field)
                if result is not None:
                    return result

        raise ValueError(
            f"No downloadable URL found in payload for binary staging "
            f"(checked fields: {_URL_FIELDS})"
        )

    def _download_binary(
        self, url: str, url_field: str
    ) -> Optional[tuple[bytes, str, dict]]:
        """Download *url* as raw bytes and return ``(bytes, url, meta)`` or ``None``."""
        t0 = time.monotonic()
        try:
            resp = _session.get(url, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return (
                resp.content,
                url,
                {
                    "url": url,
                    "url_field": url_field,
                    "http_status": resp.status_code,
                    "content_type": resp.headers.get("Content-Type", "application/octet-stream"),
                    "size_bytes": len(resp.content),
                    "download_ms": elapsed_ms,
                },
            )
        except Exception as exc:
            logger.warning("Failed to download binary %s from field %r: %s", url, url_field, exc)
            return None

    def _upload_binary(
        self, agent_type: str, data_id: str, content: bytes, meta: dict,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Write binary ``raw`` and ``meta.json`` to GCS and return the raw URI."""
        bucket = self._gcs_client().bucket(self._bucket_name)
        prefix = f"{agent_type}/{data_id}"

        raw_blob = bucket.blob(f"{prefix}/raw")
        raw_blob.upload_from_string(content, content_type=content_type)

        meta_with_gcs = dict(meta)
        raw_uri = f"gs://{self._bucket_name}/{prefix}/raw"
        meta_with_gcs["gcs"] = {
            "bucket": self._bucket_name,
            "raw_path": f"{prefix}/raw",
            "meta_path": f"{prefix}/meta.json",
            "uri": raw_uri,
        }

        meta_blob = bucket.blob(f"{prefix}/meta.json")
        meta_blob.upload_from_string(
            _json.dumps(meta_with_gcs, indent=2),
            content_type="application/json",
        )

        logger.info(
            "Staged binary %s/%s → %s (%d bytes, %s)",
            agent_type,
            data_id,
            raw_uri,
            len(content),
            content_type,
        )
        return raw_uri

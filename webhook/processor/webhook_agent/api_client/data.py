"""Data API client.

Handles creating, retrieving metadata for, and deleting data items via
the memdog ``/api/v1/data`` endpoint.
"""

import logging
from typing import Any

from .config import AGENT_USER_ID, DEFAULT_TIMEOUT, MEM_DOG_API_URL, UPLOAD_TIMEOUT
from .session import _session

logger = logging.getLogger("mem_dog.webhook.api_client.data")


class DataClient:
    """Thin wrapper around the /api/v1/data endpoint."""

    def __init__(self, base_url: str = MEM_DOG_API_URL) -> None:
        self._base = f"{base_url}/api/v1/data"

    def create(
        self,
        content: str,
        name: str,
        description: str,
        tags: list[str],
        memory_ids: list[str],
        exclusive: bool = True,
        # Plan 1 — provenance fields
        url: str | None = None,
        mime_type: str | None = None,
        is_downloaded: bool = False,
        owner: dict | None = None,
        # Multitenancy — owner user_id for correct bucket path
        owner_user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new data entry in memdog.

        Args:
            content: Raw content / payload as a string.
            name: Human-readable name for the entry.
            description: Description stored with the entry.
            tags: List of tag strings.
            memory_ids: Memory IDs to associate the data with.
            exclusive: When ``True``, data is associated *only* with the
                provided memories (not the default user timeline).
            url: Optional remote URL the content was fetched from.
            mime_type: Declared or detected MIME type.
            is_downloaded: Whether the URL has been fetched already.
            owner: DataOwner-compatible dict for provenance.

        Returns:
            The API response dict containing at least ``data_id`` and ``version``.

        Raises:
            requests.RequestException: On any HTTP error.
        """
        import json as _json

        post_data: dict[str, Any] = {
            "content": content,
            "name": name,
            "description": description,
            "tags": ",".join(tags),
            "memory_ids": ",".join(memory_ids),
            "exclusive": "true" if exclusive else "false",
        }
        if url:
            post_data["url"] = url
        if mime_type:
            post_data["mime_type"] = mime_type
        if is_downloaded:
            post_data["is_downloaded"] = "true"
        if owner:
            post_data["owner"] = _json.dumps(owner)
        post_data["owner_user_id"] = owner_user_id or AGENT_USER_ID

        resp = _session.post(
            self._base,
            data=post_data,
            timeout=UPLOAD_TIMEOUT,
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        logger.info(
            "Created data entry",
            extra={"data_id": result.get("data_id"), "version": result.get("version")},
        )
        return result

    def create_from_bytes(
        self,
        content_bytes: bytes,
        content_type: str,
        name: str,
        description: str,
        tags: list[str],
        memory_ids: list[str],
        exclusive: bool = True,
        url: str | None = None,
        mime_type: str | None = None,
        is_downloaded: bool = False,
        owner: dict | None = None,
        owner_user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new data entry by uploading raw bytes (multipart).

        Same semantics as :meth:`create` but accepts binary content
        instead of a text string, sending it as a multipart file upload.

        Returns:
            The API response dict containing at least ``data_id`` and ``version``.

        Raises:
            requests.RequestException: On any HTTP error.
        """
        import json as _json

        form_data: dict[str, Any] = {
            "name": name,
            "description": description,
            "tags": ",".join(tags),
            "memory_ids": ",".join(memory_ids),
            "exclusive": "true" if exclusive else "false",
        }
        if url:
            form_data["url"] = url
        if mime_type:
            form_data["mime_type"] = mime_type
        if is_downloaded:
            form_data["is_downloaded"] = "true"
        if owner:
            form_data["owner"] = _json.dumps(owner)
        form_data["owner_user_id"] = owner_user_id or AGENT_USER_ID

        resp = _session.post(
            self._base,
            data=form_data,
            files={"file": (name, content_bytes, content_type)},
            timeout=UPLOAD_TIMEOUT,
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        logger.info(
            "Created data entry (bytes)",
            extra={"data_id": result.get("data_id"), "version": result.get("version")},
        )
        return result

    def update_download_state(
        self,
        data_id: str,
        is_downloaded: bool = True,
    ) -> dict[str, Any]:
        """Mark a data item as downloaded (or reset to not-downloaded).

        Args:
            data_id: The data item identifier.
            is_downloaded: New download state.

        Returns:
            Updated metadata dict.

        Raises:
            requests.RequestException: On any HTTP error.
        """
        resp = _session.patch(
            f"{self._base}/{data_id}/download",
            json={"is_downloaded": is_downloaded},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        logger.info(
            "Updated download state: %s → is_downloaded=%s", data_id, is_downloaded
        )
        return result

    def add_tags(
        self,
        data_id: str,
        tags: list[str],
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Add tags to an existing data item.

        Args:
            data_id: The data item identifier.
            tags: Tag strings to add.
            user_id: Owner user ID (for multitenancy).

        Returns:
            Updated metadata dict.
        """
        params: dict[str, str] = {}
        if user_id:
            params["user_id"] = user_id
        resp = _session.post(
            f"{self._base}/{data_id}/tags/add",
            json={"tags": tags},
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        result: dict[str, Any] = resp.json()
        logger.info("Added %d tags to %s", len(tags), data_id)
        return result

    def get_metadata(self, data_id: str, user_id: str | None = None) -> dict[str, Any]:
        """Retrieve metadata for a data item.

        Args:
            data_id: The data item identifier.
            user_id: Owner user ID (for multitenancy path resolution).

        Returns:
            The metadata dict (includes ``tags``, ``memory_ids``, etc.).

        Raises:
            requests.RequestException: On any HTTP error.
        """
        url = f"{self._base}/{data_id}/metadata"
        params = {}
        if user_id:
            params["user_id"] = user_id
        resp = _session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def get_raw(self, data_id: str, version: int | None = None, user_id: str | None = None) -> tuple[str, str]:
        """Retrieve raw content for a data item (for staging when is_downloaded).

        Args:
            data_id: The data item identifier.
            version: Optional version; default is current.
            user_id: Owner user ID (for multitenancy path resolution).

        Returns:
            (content_str, content_type). Content is decoded as UTF-8 where possible.

        Raises:
            requests.RequestException: On any HTTP error.
        """
        url = f"{self._base}/{data_id}"
        params = {}
        if version is not None:
            params["version"] = str(version)
        if user_id:
            params["user_id"] = user_id
        resp = _session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "").split(";")[0].strip() or "application/octet-stream"
        try:
            text = resp.text
        except Exception:
            text = resp.content.decode("utf-8", errors="replace")
        return text, content_type

    def get_raw_bytes(self, data_id: str, version: int | None = None, user_id: str | None = None) -> tuple[bytes, str]:
        """Retrieve raw content as bytes for a data item (for binary media).

        Unlike :meth:`get_raw` which decodes to text, this returns the raw
        response bytes — safe for video, audio, and other binary formats.

        Returns:
            ``(content_bytes, content_type)``.
        """
        url = f"{self._base}/{data_id}"
        params = {}
        if version is not None:
            params["version"] = str(version)
        if user_id:
            params["user_id"] = user_id
        resp = _session.get(url, params=params, timeout=UPLOAD_TIMEOUT)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "").split(";")[0].strip() or "application/octet-stream"
        return resp.content, content_type

    def delete(self, data_id: str, user_id: str | None = None) -> dict[str, Any]:
        """Delete a data item.

        Args:
            data_id: The data item identifier.
            user_id: Optional user ID who owns the data (for multitenancy path resolution).

        Returns:
            The API response dict.

        Raises:
            requests.RequestException: On any HTTP error.
        """
        url = f"{self._base}/{data_id}"
        params = {}
        if user_id:
            params["user_id"] = user_id
        resp = _session.delete(url, params=params, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        logger.info("Deleted data entry: %s (user_id=%s)", data_id, user_id)
        return resp.json()

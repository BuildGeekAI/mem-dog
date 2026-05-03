"""
BlobStore abstraction layer for Mem-Dog storage backends.

Provides a unified interface for blob (file) operations that can be backed
by Google Cloud Storage, the local file system, or Supabase PostgreSQL.
"""

import base64
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional

logger = logging.getLogger("mem_dog.blob_store")


@dataclass
class BlobInfo:
    """Metadata about a blob returned by list operations."""

    name: str  # relative path within the store
    content_type: str  # MIME type (e.g. "application/json")


class BlobStore(ABC):
    """Abstract base class for blob storage backends.

    Each instance represents a single logical store (analogous to a GCS bucket
    or a local directory). The ``Storage`` class holds multiple ``BlobStore``
    instances — one per purpose (raw data, metadata, timeline, etc.).
    """

    @abstractmethod
    def write(self, path: str, content: bytes, content_type: str = "application/octet-stream") -> None:
        """Write *content* to *path*, creating intermediate directories/structures as needed."""

    @abstractmethod
    def read(self, path: str) -> bytes:
        """Read and return the raw bytes at *path*.

        Raises ``FileNotFoundError`` if the blob does not exist.
        """

    @abstractmethod
    def get_content_type(self, path: str) -> str:
        """Return the MIME content type for the blob at *path*.

        Raises ``FileNotFoundError`` if the blob does not exist.
        """

    @abstractmethod
    def delete(self, path: str) -> None:
        """Delete the blob at *path*. No-op if it does not exist."""

    @abstractmethod
    def list_blobs(self, prefix: str = "") -> List[BlobInfo]:
        """List all blobs whose path starts with *prefix*.

        Returns a list of ``BlobInfo`` objects.  Internal bookkeeping files
        (e.g. content-type sidecars) are excluded from results.
        """

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Return ``True`` if a blob exists at *path*."""


# ---------------------------------------------------------------------------
# Google Cloud Storage implementation
# ---------------------------------------------------------------------------


class GCSBlobStore(BlobStore):
    """BlobStore backed by a Google Cloud Storage bucket.

    The ``google-cloud-storage`` SDK is imported lazily so that local-only
    installations never need the dependency.
    """

    def __init__(self, bucket_name: str, project: Optional[str] = None):
        from google.cloud import storage as gcs_storage

        self._client = gcs_storage.Client(project=project or None)
        self._bucket = self._client.bucket(bucket_name)
        self._bucket_name = bucket_name
        logger.debug("GCSBlobStore initialised for bucket %s", bucket_name)

    def write(self, path: str, content: bytes, content_type: str = "application/octet-stream") -> None:
        blob = self._bucket.blob(path)
        blob.upload_from_string(content, content_type=content_type)

    def read(self, path: str) -> bytes:
        from google.cloud.exceptions import NotFound

        blob = self._bucket.blob(path)
        try:
            return blob.download_as_bytes()
        except NotFound:
            raise FileNotFoundError(f"Blob not found: gs://{self._bucket_name}/{path}")

    def get_content_type(self, path: str) -> str:
        from google.cloud.exceptions import NotFound

        blob = self._bucket.blob(path)
        try:
            blob.reload()
            return blob.content_type or "application/octet-stream"
        except NotFound:
            raise FileNotFoundError(f"Blob not found: gs://{self._bucket_name}/{path}")

    def delete(self, path: str) -> None:
        from google.cloud.exceptions import NotFound

        blob = self._bucket.blob(path)
        try:
            blob.delete()
        except NotFound:
            pass

    def list_blobs(self, prefix: str = "") -> List[BlobInfo]:
        blobs = self._bucket.list_blobs(prefix=prefix)
        result: List[BlobInfo] = []
        for blob in blobs:
            result.append(BlobInfo(name=blob.name, content_type=blob.content_type or "application/octet-stream"))
        return result

    def exists(self, path: str) -> bool:
        blob = self._bucket.blob(path)
        return blob.exists()


# ---------------------------------------------------------------------------
# Local file system implementation
# ---------------------------------------------------------------------------

# Sidecar file extension used to persist the content type alongside the data.
_CT_SUFFIX = ".__ct"


class LocalBlobStore(BlobStore):
    """BlobStore backed by a directory on the local file system.

    Each instance is rooted at *base_dir*.  Blob paths map directly to file
    paths relative to the root.  Content types are stored in tiny sidecar
    files with the ``.__ct`` extension.
    """

    def __init__(self, base_dir: Path):
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        logger.debug("LocalBlobStore initialised at %s", self._base)

    def _resolve(self, path: str) -> Path:
        """Resolve a blob path to an absolute file path."""
        return self._base / path

    def _ct_path(self, path: str) -> Path:
        """Return the sidecar path that stores the content type."""
        return self._base / (path + _CT_SUFFIX)

    def write(self, path: str, content: bytes, content_type: str = "application/octet-stream") -> None:
        file_path = self._resolve(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        # Persist content type in sidecar
        self._ct_path(path).write_text(content_type, encoding="utf-8")

    def read(self, path: str) -> bytes:
        file_path = self._resolve(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"Blob not found: {file_path}")
        return file_path.read_bytes()

    def get_content_type(self, path: str) -> str:
        ct_file = self._ct_path(path)
        if ct_file.is_file():
            return ct_file.read_text(encoding="utf-8").strip()
        # Fallback: if the data file exists but has no sidecar, return octet-stream.
        if self._resolve(path).is_file():
            return "application/octet-stream"
        raise FileNotFoundError(f"Blob not found: {self._resolve(path)}")

    def delete(self, path: str) -> None:
        file_path = self._resolve(path)
        ct_file = self._ct_path(path)
        if file_path.is_file():
            file_path.unlink()
        if ct_file.is_file():
            ct_file.unlink()

    def list_blobs(self, prefix: str = "") -> List[BlobInfo]:
        search_root = self._base / prefix if prefix else self._base
        result: List[BlobInfo] = []

        if not search_root.exists():
            # If the prefix resolves to a non-existent directory, check if
            # it's a partial directory name by searching the parent.
            parent = search_root.parent
            if not parent.exists():
                return result
            for item in parent.rglob("*"):
                if not item.is_file():
                    continue
                rel = str(item.relative_to(self._base)).replace("\\", "/")
                if rel.endswith(_CT_SUFFIX):
                    continue
                if rel.startswith(prefix):
                    ct = self._ct_path(rel)
                    ct_val = ct.read_text(encoding="utf-8").strip() if ct.is_file() else "application/octet-stream"
                    result.append(BlobInfo(name=rel, content_type=ct_val))
            return result

        if search_root.is_file():
            rel = str(search_root.relative_to(self._base)).replace("\\", "/")
            if not rel.endswith(_CT_SUFFIX):
                ct = self._ct_path(rel)
                ct_val = ct.read_text(encoding="utf-8").strip() if ct.is_file() else "application/octet-stream"
                result.append(BlobInfo(name=rel, content_type=ct_val))
            return result

        for item in search_root.rglob("*"):
            if not item.is_file():
                continue
            rel = str(item.relative_to(self._base)).replace("\\", "/")
            if rel.endswith(_CT_SUFFIX):
                continue
            ct = self._ct_path(rel)
            ct_val = ct.read_text(encoding="utf-8").strip() if ct.is_file() else "application/octet-stream"
            result.append(BlobInfo(name=rel, content_type=ct_val))

        return result

    def exists(self, path: str) -> bool:
        return self._resolve(path).is_file()


# ---------------------------------------------------------------------------
# Supabase PostgreSQL implementation
# ---------------------------------------------------------------------------

_GCP_METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts"
    "/default/identity?audience={audience}&format=full"
)


def _fetch_identity_token(audience: str) -> Optional[str]:
    """Fetch a Google Cloud identity token for *audience* from the GCP metadata server.

    Returns ``None`` when running outside of GCP (e.g. local dev) or when the
    metadata server is unreachable.  The token is fetched fresh on every call
    so it stays valid across long-running processes; callers that need
    performance can cache it externally.
    """
    import urllib.request

    url = _GCP_METADATA_TOKEN_URL.format(audience=audience)
    try:
        req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception as exc:
        logger.debug("Could not fetch GCP identity token for %s: %s", audience, exc)
        return None


def _attach_identity_token_hook(postgrest_client: Any, audience: str) -> None:
    """Attach a request event hook that injects a GCP OIDC identity token.

    The hook fires after supabase-py's auth() sets ``Authorization: Bearer
    <supabase-jwt>``, so the identity token reliably overrides it.
    Cloud Run IAM sees the identity token; the proxy reads the Supabase key
    from the ``apikey`` header (also set by supabase-py) or from its
    ``SUPABASE_DEFAULT_JWT`` env var.

    Works with all supabase-py 2.x versions by patching the postgrest session
    directly rather than relying on SyncClientOptions.http_client.
    """

    def _inject(request: Any) -> None:
        token = _fetch_identity_token(audience)
        if token:
            request.headers["Authorization"] = f"Bearer {token}"

    postgrest_client.session.event_hooks.setdefault("request", []).append(_inject)


class SupabaseBlobStore(BlobStore):
    """BlobStore backed by a Supabase PostgreSQL table (mem_dog_blobs).

    Each instance represents one logical store identified by *store_name*
    (e.g. ``"meta"``, ``"memories"``).  All blobs for all logical stores share
    a single table keyed on ``(store_name, path)``.

    The optional *user_id_extractor* callable derives the tenant ``user_id``
    from a blob path on write so that rows carry an explicit ``user_id`` column
    that can be used for Row Level Security policies and efficient per-user
    queries.  Pass ``None`` for system-level stores where user scoping does not
    apply (e.g. ``stats``, ``prompts``).

    The ``supabase`` Python package is imported lazily so that non-Supabase
    deployments never need the dependency.
    """

    _TABLE = "mem_dog_blobs"

    def __init__(
        self,
        store_name: str,
        supabase_url: str,
        supabase_key: str,
        api_gateway_key: Optional[str] = None,
        use_identity_token: bool = False,
        user_id_extractor: Optional[Callable[[str], Optional[str]]] = None,
    ) -> None:
        from supabase import create_client
        from supabase.lib.client_options import SyncClientOptions

        self._store_name = store_name
        self._user_id_extractor = user_id_extractor
        options: Optional[SyncClientOptions] = None
        if api_gateway_key:
            options = SyncClientOptions(headers={"x-api-key": api_gateway_key})
        self._client = create_client(supabase_url, supabase_key, options=options)
        if use_identity_token and not api_gateway_key:
            # The proxy requires a Google OIDC identity token (Cloud Run IAM auth).
            # Patch the postgrest session directly so the hook fires after supabase-py
            # sets its own Authorization header, overriding the Supabase JWT with the
            # Google identity token. The proxy then reads the Supabase key from the
            # apikey header (also set by supabase-py) or SUPABASE_DEFAULT_JWT.
            _attach_identity_token_hook(self._client.postgrest, supabase_url)
        logger.debug("SupabaseBlobStore initialised for store '%s'", store_name)

    def _extract_user_id(self, path: str) -> Optional[str]:
        if self._user_id_extractor is None:
            return None
        try:
            return self._user_id_extractor(path)
        except Exception:
            return None

    def write(self, path: str, content: bytes, content_type: str = "application/octet-stream") -> None:
        row = {
            "store_name": self._store_name,
            "path": path,
            "content": base64.b64encode(content).decode("ascii"),
            "content_type": content_type,
        }
        uid = self._extract_user_id(path)
        if uid is not None:
            row["user_id"] = uid
        self._client.table(self._TABLE).upsert(
            row, on_conflict="store_name,path"
        ).execute()

    def read(self, path: str) -> bytes:
        res = (
            self._client.table(self._TABLE)
            .select("content")
            .eq("store_name", self._store_name)
            .eq("path", path)
            .execute()
        )
        if not res.data:
            raise FileNotFoundError(
                f"Blob not found: supabase://{self._store_name}/{path}"
            )
        raw = res.data[0].get("content")
        if raw is None:
            raise FileNotFoundError(
                f"Blob not found: supabase://{self._store_name}/{path}"
            )
        return base64.b64decode(raw)

    def get_content_type(self, path: str) -> str:
        res = (
            self._client.table(self._TABLE)
            .select("content_type")
            .eq("store_name", self._store_name)
            .eq("path", path)
            .execute()
        )
        if not res.data:
            raise FileNotFoundError(
                f"Blob not found: supabase://{self._store_name}/{path}"
            )
        return res.data[0].get("content_type") or "application/octet-stream"

    def delete(self, path: str) -> None:
        try:
            self._client.table(self._TABLE).delete().eq(
                "store_name", self._store_name
            ).eq("path", path).execute()
        except Exception:
            pass

    def list_blobs(self, prefix: str = "") -> List[BlobInfo]:
        try:
            query = (
                self._client.table(self._TABLE)
                .select("path, content_type")
                .eq("store_name", self._store_name)
            )
            if prefix:
                query = query.like("path", f"{prefix}%")
            res = query.execute()
        except Exception:
            return []
        result: List[BlobInfo] = []
        for row in res.data or []:
            p = row.get("path")
            ct = row.get("content_type") or "application/octet-stream"
            if p is not None:
                result.append(BlobInfo(name=p, content_type=ct))
        return result

    def exists(self, path: str) -> bool:
        try:
            res = (
                self._client.table(self._TABLE)
                .select("path")
                .eq("store_name", self._store_name)
                .eq("path", path)
                .limit(1)
                .execute()
            )
            return bool(res.data)
        except Exception:
            return False

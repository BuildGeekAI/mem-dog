"""Optional store backed by Redis, Postgres, Supabase, or GCS (for testing CRUD API).

Provides Store (abstract), RedisStore, PostgresStore, SupabaseStore, and GCSStore.
Backend selected via query param (redis=true, postgres=true, supabase=true, or gcs=true) on the store API.
GCSStore persists directly to GCS objects; use when you need GCS-backed persistence.
"""
import base64
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

logger = logging.getLogger("mem_dog.store")

# Content-type suffix for Redis keys (value stored at key, content-type at key + _CT_SUFFIX).
_CT_SUFFIX = ".__ct"


class Store(ABC):
    """Abstract store. Implementations: Redis, Postgres, Supabase (cloud or local), GCS."""

    @abstractmethod
    def get(self, key: str) -> Optional[Tuple[bytes, str]]:
        """Return (value_bytes, content_type) for key, or None if missing."""

    @abstractmethod
    def set(
        self,
        key: str,
        value: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Store value with optional content_type."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove key (and its content-type meta). No-op if key does not exist."""

    @abstractmethod
    def list_keys(self, prefix: str = "") -> List[str]:
        """Return keys with optional prefix. Excludes internal meta keys (e.g. .__ct)."""


class RedisStore(Store):
    """Store backed by Redis. Uses key for value and key + .__ct for content-type."""

    def __init__(self, redis_url: str):
        import redis
        self._client = redis.from_url(redis_url, decode_responses=False)
        self._ct_suffix_bytes = _CT_SUFFIX.encode("utf-8")
        logger.info("Redis store initialised (url redacted)")

    def _ct_key(self, key: str) -> str:
        return key + _CT_SUFFIX

    def get(self, key: str) -> Optional[Tuple[bytes, str]]:
        value = self._client.get(key)
        if value is None:
            return None
        ct = self._client.get(self._ct_key(key))
        content_type = ct.decode("utf-8") if ct else "application/octet-stream"
        return (value, content_type)

    def set(
        self,
        key: str,
        value: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        self._client.set(key, value)
        self._client.set(self._ct_key(key), content_type.encode("utf-8"))

    def delete(self, key: str) -> None:
        self._client.delete(key, self._ct_key(key))

    def list_keys(self, prefix: str = "") -> List[str]:
        out: List[str] = []
        for k in self._client.scan_iter(match=prefix + "*" if prefix else "*", count=100):
            key_str = k.decode("utf-8")
            if key_str.endswith(_CT_SUFFIX):
                continue
            out.append(key_str)
        return sorted(out)


class PostgresStore(Store):
    """Store backed by PostgreSQL. Table store_kv (key, value, content_type)."""

    _TABLE = "store_kv"

    def __init__(self, postgres_url: str):
        import psycopg2
        # psycopg2 expects postgresql://; strip +psycopg2 if present
        dsn = postgres_url.replace("postgresql+psycopg2://", "postgresql://", 1)
        self._dsn = dsn
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True
        self._ensure_table()
        logger.info("Postgres store initialised (url redacted)")

    def _ensure_table(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS store_kv (
                    key TEXT PRIMARY KEY,
                    value BYTEA NOT NULL,
                    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )

    def get(self, key: str) -> Optional[Tuple[bytes, str]]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT value, content_type FROM store_kv WHERE key = %s",
                (key,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        raw = row[0]
        value = bytes(raw) if isinstance(raw, memoryview) else raw
        return (value, row[1] or "application/octet-stream")

    def set(
        self,
        key: str,
        value: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO store_kv (key, value, content_type, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    content_type = EXCLUDED.content_type,
                    updated_at = now()
                """,
                (key, value, content_type),
            )

    def delete(self, key: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM store_kv WHERE key = %s", (key,))

    def list_keys(self, prefix: str = "") -> List[str]:
        with self._conn.cursor() as cur:
            if prefix:
                cur.execute(
                    "SELECT key FROM store_kv WHERE key LIKE %s ORDER BY key",
                    (prefix + "%",),
                )
            else:
                cur.execute("SELECT key FROM store_kv ORDER BY key")
            rows = cur.fetchall()
        return [r[0] for r in rows]


class SupabaseStore(Store):
    """Store backed by Supabase. Uses table store_kv (kv_key, value base64, content_type). Table must exist.
    Column kv_key avoids PostgREST reserved-word parsing issues with 'key'.
    When url points to GCP API Gateway, pass api_gateway_key to add x-api-key header."""

    _TABLE = "store_kv"
    _KEY_COL = "kv_key"

    def __init__(self, url: str, key: str, api_gateway_key: Optional[str] = None):
        from supabase import create_client
        from supabase.lib.client_options import SyncClientOptions
        options = None
        if api_gateway_key:
            options = SyncClientOptions(headers={"x-api-key": api_gateway_key})
        self._client = create_client(url, key, options=options)
        logger.info("Supabase store initialised (url redacted)")

    def get(self, key: str) -> Optional[Tuple[bytes, str]]:
        try:
            res = self._client.table(self._TABLE).select("value, content_type").eq(self._KEY_COL, key).execute()
        except Exception:
            return None
        if not res.data or len(res.data) == 0:
            return None
        row = res.data[0]
        raw = row.get("value")
        if raw is None:
            return None
        try:
            value = base64.b64decode(raw)
        except Exception:
            return None
        ct = row.get("content_type") or "application/octet-stream"
        return (value, ct)

    def set(
        self,
        key: str,
        value: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        b64 = base64.b64encode(value).decode("ascii")
        self._client.table(self._TABLE).upsert(
            {self._KEY_COL: key, "value": b64, "content_type": content_type},
            on_conflict=self._KEY_COL,
        ).execute()

    def delete(self, key: str) -> None:
        try:
            self._client.table(self._TABLE).delete().eq(self._KEY_COL, key).execute()
        except Exception:
            pass

    def list_keys(self, prefix: str = "") -> List[str]:
        try:
            res = self._client.table(self._TABLE).select(self._KEY_COL).execute()
        except Exception:
            return []
        keys = [r[self._KEY_COL] for r in (res.data or []) if r.get(self._KEY_COL) is not None]
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        return sorted(keys)


class GCSStore(Store):
    """Store backed by GCS. Each key is an object at store_kv/<key>. Persists reliably (no SQLite)."""

    _PREFIX = "store_kv/"

    def __init__(self, bucket_name: str, project: Optional[str] = None):
        from google.cloud import storage
        self._client = storage.Client(project=project)
        self._bucket = self._client.bucket(bucket_name)
        logger.info("GCS store initialised (bucket=%s)", bucket_name)

    def _blob_path(self, key: str) -> str:
        return self._PREFIX + key

    def get(self, key: str) -> Optional[Tuple[bytes, str]]:
        blob = self._bucket.blob(self._blob_path(key))
        try:
            data = blob.download_as_bytes()
        except Exception:
            return None
        ct = blob.content_type or "application/octet-stream"
        return (data, ct)

    def set(
        self,
        key: str,
        value: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        blob = self._bucket.blob(self._blob_path(key))
        blob.upload_from_string(
            value,
            content_type=content_type,
        )

    def delete(self, key: str) -> None:
        try:
            self._bucket.blob(self._blob_path(key)).delete()
        except Exception:
            pass

    def list_keys(self, prefix: str = "") -> List[str]:
        prefix_path = self._PREFIX + prefix
        blobs = self._bucket.list_blobs(prefix=prefix_path)
        keys = []
        for b in blobs:
            name = b.name
            if name.startswith(self._PREFIX):
                key = name[len(self._PREFIX) :]
                keys.append(key)
        return sorted(keys)

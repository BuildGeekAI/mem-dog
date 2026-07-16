"""Backend-agnostic storage layer with OO abstraction.

Provides BaseStorage (abstract), LocalStorage (local filesystem), and GCSStorage (Google Cloud
Storage). Callers use get_storage() to obtain the singleton instance configured by
STORAGE_BACKEND. All CRUD and domain logic lives on BaseStorage; subclasses implement
_build_stores() to supply the BlobStore instances for each logical store.
"""
import base64
import json
import logging
import math
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from typing import Literal
from datetime import datetime, timedelta
from pathlib import Path
import uuid

import httpx

from app import config
from app.ids import generate_data_id, generate_memory_id
from app.telemetry import get_tracer, get_meter
from app.blob_store import BlobStore, BlobInfo, GCSBlobStore, LocalBlobStore, SupabaseBlobStore
from app.store import Store, RedisStore, PostgresStore, SupabaseStore, GCSStore
from app.models import (
    DataMetadata, DataDeviceInfo, VersionInfo, DataListItem, AccessUpdate,
    DataOwner, DataProvenance, ServiceParticipant, EventMeta,
    # Memory models
    MemoryType, MemoryDuration, MEMORY_TYPE_DURATION,
    MemoryCategory, MEMORY_TYPE_CATEGORY, AccessLevel, DEFAULT_TTL_HOURS,
    Memory, MemoryCreate, MemoryUpdate, MemoryDataEntry, DeviceInfo,
    # AI Layer models
    AIEngineConfig, AIEngineConfigCreate, AIModelCapabilities,
    UserAIPreferences, GlobalAIAvailability, GlobalAIEngineInfo,
    Prompt, PromptCreate, Embedding, EmbeddingCreate, EmbeddingSummary,
    Viewpoint, ViewpointCreate, ViewpointUpdate, AIEngineType, AISignature, AIKeyMode,
    Skill, SkillCreate, SkillUpdate,
    AnalysisTemplate, AnalysisTemplateCreate, AnalysisTemplateUpdate, AnalysisTemplateKind,
    AgentConfig, AgentConfigCreate, AgentConfigUpdate,
    # User Management models
    User, UserCreate, UserUpdate, UserResponse, UserStatus, UserRole,
    UserCredentials, APIKeyCreate, APIKeyResponse,
    # Statistics models
    GlobalStats, DataStats, MemoryStats, EmbeddingStats, ViewpointStats,
    UserSummaryStats, PerUserStats, PerUserDataStats, PerUserMemoryStats,
    PerUserEmbeddingStats, PerUserViewpointStats, PerUserTokenStats,
    TokenUsageRecord,
    # Channel identity correlation
    ChannelIdentityCreate, ChannelIdentityRecord, ChannelIdentityListResponse,
    ChannelMetadata, ChannelMetadataCreate,
)

logger = logging.getLogger("mem_dog.storage")
tracer = get_tracer("mem_dog.storage")
meter = get_meter("mem_dog.storage")

# ---- Storage-level metrics ----
_data_ops_counter = meter.create_counter(
    "storage.data.operations",
    description="Count of data storage operations",
    unit="1",
)
_storage_errors_counter = meter.create_counter(
    "storage.errors",
    description="Count of storage operation errors",
    unit="1",
)

# Blob path prefix for analysis templates (stored in prompts store).
_ANALYSIS_TEMPLATES_PREFIX = "_analysis_templates/"

# Blob path prefix for agent configs (stored in prompts store).
_AGENT_CONFIGS_PREFIX = "_agent_configs/"

# Valid AIEngineType values for persistence (AISignature / Embedding / Viewpoint).
_VALID_STORAGE_ENGINES: frozenset[str] = frozenset(e.value for e in AIEngineType)

# Provider aliases and internal labels → AIEngineType.
_STORAGE_ENGINE_ALIASES: dict[str, str] = {
    "google": "gemini",
    "vertex_ai": "gemini",
    "vertex": "gemini",
    "local": "ollama",
    "ollama_local": "ollama",
    "ollama_cloud": "ollama",
    "model_server": "ollama",
}


def _normalize_storage_engine(engine_type: str) -> str:
    """Map provider aliases and bare model names to a valid ``AIEngineType`` value.

  Used when persisting ``AISignature`` on embeddings and viewpoints so clients
  that pass LiteLLM provider strings (``google/...``) or model-server bare
  names (``llama3.2:1b``) do not trigger validation errors.
    """
    key = (engine_type or "").strip().lower()
    if not key:
        return AIEngineType.OLLAMA.value
    if key in _VALID_STORAGE_ENGINES:
        return key
    if key in _STORAGE_ENGINE_ALIASES:
        return _STORAGE_ENGINE_ALIASES[key]
    if "/" in key:
        provider = key.split("/", 1)[0]
        if provider in _STORAGE_ENGINE_ALIASES:
            return _STORAGE_ENGINE_ALIASES[provider]
        if provider in _VALID_STORAGE_ENGINES:
            return provider
    # Bare model names (e.g. MODEL_SERVER_MODEL) — treat as local Ollama inference.
    return AIEngineType.OLLAMA.value

# Fixed subdirectory names used by the local filesystem backend.
_LOCAL_SUBDIRS = {
    "raw": "raw",
    "meta": "meta",
    "memories": "memories",
    "index": "index",
    "users": "users",
    "prompts": "prompts",
    "embeddings": "embeddings",
    "viewpoints": "viewpoints",
    "ai_config": "ai_config",
    "skills": "skills",
    "stats": "stats",
    "channels": "channels",
}

# ISO-8601 compact timestamp format used for version path labels (URL-safe, sortable).
_VER_TS_FMT = "%Y%m%dT%H%M%SZ"


def _make_version_label(dt: Optional[datetime] = None) -> str:
    """Return a sortable version label like ``ver_20250225T143022Z``."""
    ts = (dt or datetime.utcnow()).strftime(_VER_TS_FMT)
    return f"ver_{ts}"


def _sanitize_version_label(label: str) -> str:
    """Ensure label starts with ``ver_``; strip characters unsafe in blob paths."""
    safe = label.replace(" ", "_").replace("/", "-").replace("\\", "-")
    if not safe.startswith("ver_"):
        safe = f"ver_{safe}"
    return safe


class BaseStorage(ABC):
    """Backend-agnostic storage layer.

    Each logical store (raw, meta, timeline, …) is a ``BlobStore`` instance
    backed by GCS or the local filesystem.  All structured data (metadata,
    memories, embeddings, viewpoints, prompts, skills) is stored in blob storage.
    Subclasses implement _build_stores() to provide the appropriate BlobStores.
    """

    @abstractmethod
    def _build_stores(self) -> Dict[str, BlobStore]:
        """Return a dict of logical store name -> BlobStore. Subclasses implement for local or GCS."""
        ...

    def _build_redis_store(self) -> Optional[Store]:
        """Return optional Redis store. Default: None. Subclasses may override."""
        return None

    def _build_postgres_store(self) -> Optional[Store]:
        """Return optional Postgres store. Default: None. Subclasses may override."""
        return None

    def _build_supabase_store(self) -> Optional[Store]:
        """Return optional Supabase store. Default: None. Subclasses may override."""
        return None

    def _build_gcs_store(self) -> Optional[Store]:
        """Return optional GCS store. Default: None. Subclasses may override."""
        return None

    def __init__(self) -> None:
        stores = self._build_stores()
        self.raw_store: BlobStore = stores["raw"]
        self.meta_store: BlobStore = stores["meta"]
        self.memories_store: BlobStore = stores["memories"]
        # index_store: dedicated bucket for reverse indexes; falls back to meta_store under _idx/ prefix
        self.index_store: BlobStore = stores.get("index") or stores["meta"]
        self.user_store: Optional[BlobStore] = stores.get("users")
        self.prompts_store: Optional[BlobStore] = stores.get("prompts")
        self.embeddings_store: Optional[BlobStore] = stores.get("embeddings")
        self.viewpoints_store: Optional[BlobStore] = stores.get("viewpoints")
        self.ai_config_store: Optional[BlobStore] = stores.get("ai_config")
        self.skills_store: Optional[BlobStore] = stores.get("skills")
        self.stats_store: Optional[BlobStore] = stores.get("stats")
        self.channels_store: Optional[BlobStore] = stores.get("channels")
        self.redis_store: Optional[Store] = self._build_redis_store()
        self.postgres_store: Optional[Store] = self._build_postgres_store()
        self.supabase_store: Optional[Store] = self._build_supabase_store()
        self.gcs_store: Optional[Store] = self._build_gcs_store()
        logger.info(
            "Storage initialised (backend=%s)",
            type(self).__name__,
        )
    
    def _check_ai_enabled(self) -> None:
        """Raise error if AI layer is not configured."""
        if not config.is_ai_enabled():
            raise RuntimeError("AI layer is not configured. Set PROMPTS_BUCKET, EMBEDDINGS_BUCKET, VIEWPOINTS_BUCKET, AI_CONFIG_BUCKET, and SKILLS_BUCKET environment variables.")
    
    def _check_user_management_enabled(self) -> None:
        """Raise error if user management is not configured."""
        if not config.is_user_management_enabled():
            raise RuntimeError("User management is not configured. Set USER_BUCKET environment variable.")
    
    def _check_memories_enabled(self) -> None:
        """Raise error if memory management is not configured."""
        if not config.is_memories_enabled():
            raise RuntimeError("Memory management is not configured. Set MEMORIES_BUCKET environment variable.")
    
    def _check_stats_enabled(self) -> None:
        """Raise error if statistics feature is not configured."""
        if not config.is_stats_enabled():
            raise RuntimeError(
                "Statistics feature is not configured. Set STATS_BUCKET environment variable."
            )

    # =========================================================================
    # Memory Path Helpers
    # =========================================================================

    @staticmethod
    def _infer_memory_type_from_id(memory_id: str) -> str:
        """Infer memory_type value from a memory ID using naming conventions.

        Supports both generated IDs (``mem_{type}_{ulid}``) and the fixed IDs
        used for default memories (``timeline-{user}``, ``tracing-{user}-pipeline``,
        ``session-grp-...``, etc.).  Returns the value that matches a ``MemoryType``
        enum entry.  Falls back to ``"custom"`` when the type cannot be determined.
        """
        lower = memory_id.lower()
        # Generated IDs: mem_{type}_{ulid}
        if lower.startswith("mem_"):
            parts = lower.split("_", 2)
            if len(parts) >= 2:
                inferred = parts[1]
                if inferred in {t.value for t in MemoryType}:
                    return inferred
        # Fixed / convention IDs
        for prefix, mtype in [
            ("timeline-", MemoryType.TIMELINE.value),
            ("session-", MemoryType.SESSION.value),
            ("conversation-", MemoryType.CONVERSATION.value),
            ("agent-session-", MemoryType.SESSION.value),
            ("tracing-", MemoryType.TRACING.value),
            ("factual-", MemoryType.FACTUAL.value),
            ("episodic-", MemoryType.EPISODIC.value),
            ("semantic-", MemoryType.SEMANTIC.value),
            ("user-", MemoryType.USER.value),
            ("organizational-", MemoryType.ORGANIZATIONAL.value),
        ]:
            if lower.startswith(prefix):
                return mtype
        return MemoryType.CUSTOM.value

    @staticmethod
    def _memory_meta_path(user_id: str, memory_id: str) -> str:
        """Return ``{user_id}/{memory_type}/{memory_id}/meta.json``."""
        mtype = BaseStorage._infer_memory_type_from_id(memory_id)
        return f"{user_id}/{mtype}/{memory_id}/meta.json"

    @staticmethod
    def _memory_data_path(user_id: str, memory_id: str, data_id: str) -> str:
        """Return ``{user_id}/{memory_type}/{memory_id}/data/{data_id}.json``."""
        mtype = BaseStorage._infer_memory_type_from_id(memory_id)
        return f"{user_id}/{mtype}/{memory_id}/data/{data_id}.json"

    @staticmethod
    def _memory_prefix(user_id: str, memory_id: str) -> str:
        """Return the prefix for all blobs belonging to a memory."""
        mtype = BaseStorage._infer_memory_type_from_id(memory_id)
        return f"{user_id}/{mtype}/{memory_id}/"

    # =========================================================================
    # Embedding & Viewpoint Path Helpers (multitenant, per-version)
    # =========================================================================

    @staticmethod
    def _embedding_blob_path(user_id: str, data_id: str, version_label: str, embedding_id: str) -> str:
        """Return ``{user_id}/{data_id}/{version_label}/embeddings/{embedding_id}.json``."""
        return f"{user_id}/{data_id}/{version_label}/embeddings/{embedding_id}.json"

    @staticmethod
    def _viewpoint_blob_path(user_id: str, data_id: str, version_label: str, viewpoint_id: str) -> str:
        """Return ``{user_id}/{data_id}/{version_label}/viewpoints/{viewpoint_id}.json``."""
        return f"{user_id}/{data_id}/{version_label}/viewpoints/{viewpoint_id}.json"

    @staticmethod
    def _embedding_prefix(user_id: str, data_id: str, version_label: Optional[str] = None) -> str:
        """Return the list prefix for embeddings.

        With version_label: ``{user_id}/{data_id}/{version_label}/embeddings/``
        Without: ``{user_id}/{data_id}/`` (scan across all versions)
        """
        if version_label:
            return f"{user_id}/{data_id}/{version_label}/embeddings/"
        return f"{user_id}/{data_id}/"

    @staticmethod
    def _viewpoint_prefix(user_id: str, data_id: str, version_label: Optional[str] = None) -> str:
        """Return the list prefix for viewpoints.

        With version_label: ``{user_id}/{data_id}/{version_label}/viewpoints/``
        Without: ``{user_id}/{data_id}/`` (scan across all versions)
        """
        if version_label:
            return f"{user_id}/{data_id}/{version_label}/viewpoints/"
        return f"{user_id}/{data_id}/"

    # =========================================================================
    # Reverse Index Helpers
    # =========================================================================

    def _write_data_index(self, user_id: str, data_id: str, metadata: "DataMetadata") -> None:
        """Write/update the reverse index entries for a data item. Best-effort; never raises."""
        try:
            ts = (metadata.updated_at or metadata.created_at or datetime.utcnow().isoformat() + "Z").replace(":", "").replace("-", "").replace(".", "")[:15] + "Z"
            summary = {
                "data_id": data_id,
                "user_id": user_id,
                "updated_at": metadata.updated_at,
                "created_at": metadata.created_at,
                "name": metadata.name,
                "mime_type": metadata.mime_type,
                "tags": metadata.tags or [],
                "memory_ids": metadata.memory_ids or [],
                "current_version": metadata.current_version,
                "source_service": metadata.source_service,
            }
            payload = json.dumps(summary, indent=2).encode("utf-8")
            # Per-item index
            self.index_store.write(f"_idx/{user_id}/data/{data_id}.json", payload, "application/json")
            # Time-sorted listing stub (empty payload, key acts as listing entry)
            ts_key = f"_idx/{user_id}/data_ts/{ts}_{data_id}"
            self.index_store.write(ts_key, b"", "application/octet-stream")
            # Tag indexes
            for tag in (metadata.tags or []):
                self.index_store.write(f"_idx/{user_id}/tags/{tag}/{data_id}.json", payload, "application/json")
        except Exception as exc:
            logger.debug("_write_data_index failed (non-fatal): %s", exc)

    def _delete_data_index(self, user_id: str, data_id: str, tags: Optional[List[str]] = None, timestamp_prefix: Optional[str] = None) -> None:
        """Remove reverse index entries for a deleted data item. Best-effort; never raises."""
        try:
            self.index_store.delete(f"_idx/{user_id}/data/{data_id}.json")
        except Exception:
            pass
        try:
            # Remove all time-sorted entries for this data_id (scan narrow prefix)
            for info in self.index_store.list_blobs(prefix=f"_idx/{user_id}/data_ts/"):
                if info.name.endswith(f"_{data_id}"):
                    try:
                        self.index_store.delete(info.name)
                    except Exception:
                        pass
        except Exception:
            pass
        for tag in (tags or []):
            try:
                self.index_store.delete(f"_idx/{user_id}/tags/{tag}/{data_id}.json")
            except Exception:
                pass

    def _write_memory_index(self, user_id: str, memory_type: str, memory_id: str, memory: "Memory") -> None:
        """Write/update the reverse index entry for a memory. Best-effort; never raises."""
        try:
            ts = (memory.updated_at or memory.created_at or datetime.utcnow().isoformat() + "Z").replace(":", "").replace("-", "").replace(".", "")[:15] + "Z"
            summary = {
                "memory_id": memory_id,
                "memory_type": memory_type,
                "user_id": user_id,
                "name": memory.name,
                "updated_at": memory.updated_at,
                "created_at": memory.created_at,
            }
            payload = json.dumps(summary, indent=2).encode("utf-8")
            self.index_store.write(f"_idx/{user_id}/memories/{memory_type}/{memory_id}.json", payload, "application/json")
            ts_key = f"_idx/{user_id}/memory_ts/{ts}_{memory_id}"
            self.index_store.write(ts_key, b"", "application/octet-stream")
        except Exception as exc:
            logger.debug("_write_memory_index failed (non-fatal): %s", exc)

    def _delete_memory_index(self, user_id: str, memory_id: str) -> None:
        """Remove reverse index entries for a deleted memory. Best-effort; never raises."""
        mtype = self._infer_memory_type_from_id(memory_id)
        try:
            self.index_store.delete(f"_idx/{user_id}/memories/{mtype}/{memory_id}.json")
        except Exception:
            pass
        try:
            for info in self.index_store.list_blobs(prefix=f"_idx/{user_id}/memory_ts/"):
                if info.name.endswith(f"_{memory_id}"):
                    try:
                        self.index_store.delete(info.name)
                    except Exception:
                        pass
        except Exception:
            pass

    # =========================================================================
    # Per-Data Telemetry Index Helpers
    # =========================================================================

    def _init_data_telemetry_index(
        self, user_id: str, data_id: str, version_label: str, telemetry_memory_id: str
    ) -> None:
        """Write the initial telemetry index stub for a (data_id, version) pair.

        Path: ``{user_id}/telemetry/data_id/{data_id}/{version_label}/data_ids.json``
        Content: ``{"span_data_ids": [], "telemetry_memory_id": "..."}``
        Best-effort; never raises.
        """
        try:
            stub = {
                "data_id": data_id,
                "user_id": user_id,
                "version_label": version_label,
                "telemetry_memory_id": telemetry_memory_id,
                "span_data_ids": [],
            }
            path = f"{user_id}/telemetry/data_id/{data_id}/{version_label}/data_ids.json"
            self.memories_store.write(path, json.dumps(stub, indent=2).encode("utf-8"), "application/json")
        except Exception as exc:
            logger.debug("_init_data_telemetry_index failed (non-fatal): %s", exc)

    def _append_telemetry_index(
        self, user_id: str, data_id: str, version_label: str, span_data_id: str
    ) -> None:
        """Append a span_data_id to the per-version telemetry index. Best-effort; never raises.

        Called by webhook processor / sub-agents when a telemetry span is stored.
        """
        try:
            path = f"{user_id}/telemetry/data_id/{data_id}/{version_label}/data_ids.json"
            try:
                content = self.memories_store.read(path)
                idx = json.loads(content)
            except FileNotFoundError:
                idx = {"data_id": data_id, "user_id": user_id, "version_label": version_label, "span_data_ids": []}
            if span_data_id not in idx.get("span_data_ids", []):
                idx.setdefault("span_data_ids", []).append(span_data_id)
            self.memories_store.write(path, json.dumps(idx, indent=2).encode("utf-8"), "application/json")
        except Exception as exc:
            logger.debug("_append_telemetry_index failed (non-fatal): %s", exc)

    def get_data_telemetry_index(
        self, user_id: str, data_id: str, version_label: str
    ) -> dict:
        """Return the telemetry index for a (data_id, version_label) pair, or an empty stub."""
        try:
            path = f"{user_id}/telemetry/data_id/{data_id}/{version_label}/data_ids.json"
            content = self.memories_store.read(path)
            return json.loads(content)
        except FileNotFoundError:
            return {"data_id": data_id, "user_id": user_id, "version_label": version_label, "span_data_ids": []}
        except Exception as exc:
            logger.warning("get_data_telemetry_index failed: %s", exc)
            return {"data_id": data_id, "user_id": user_id, "version_label": version_label, "span_data_ids": []}

    def _store_for(self, backend: Literal["redis", "postgres", "supabase", "gcs"]) -> Optional[Store]:
        """Return the Store for the given backend (redis, postgres, supabase, or gcs)."""
        if backend == "redis":
            return self.redis_store
        if backend == "postgres":
            return self.postgres_store
        if backend == "supabase":
            return self.supabase_store
        return self.gcs_store

    def store_get(self, key: str, backend: Literal["redis", "postgres", "supabase", "gcs"]) -> Optional[Tuple[bytes, str]]:
        """Return (value_bytes, content_type) for store key, or None if missing or backend not configured."""
        store = self._store_for(backend)
        if store is None:
            return None
        return store.get(key)

    def store_set(
        self,
        key: str,
        value: bytes,
        content_type: str = "application/octet-stream",
        backend: Literal["redis", "postgres", "supabase", "gcs"] = "redis",
    ) -> None:
        """Store value in the given backend. No-op if that backend is not configured."""
        store = self._store_for(backend)
        if store is not None:
            store.set(key, value, content_type)

    def store_delete(self, key: str, backend: Literal["redis", "postgres", "supabase", "gcs"]) -> None:
        """Remove key from the given backend. No-op if backend not configured or key missing."""
        store = self._store_for(backend)
        if store is not None:
            store.delete(key)

    def store_list_keys(self, prefix: str = "", backend: Literal["redis", "postgres", "supabase", "gcs"] = "redis") -> List[str]:
        """List store keys with optional prefix. Returns [] if backend not configured."""
        store = self._store_for(backend)
        if store is None:
            return []
        return store.list_keys(prefix)

    def store_raw_data(
        self,
        data_id: str,
        version: int,
        content: bytes,
        content_type: str,
        user_id: str,
        version_label: Optional[str] = None,
    ) -> Tuple[int, str]:
        """Store raw data and return (size, version_label).

        ``version_label`` is a URL-safe timestamp slug like ``ver_20250225T143022Z``.
        When not provided, a fresh label is generated from the current UTC time.
        Path: ``{user_id}/{data_id}/{version_label}/data``
        """
        with tracer.start_as_current_span("store_raw_data") as span:
            # Guarantee user_id is never empty — fall back to DEFAULT_USER if caller passes ""
            user_id = (user_id or "").strip() or config.DEFAULT_USER_ID
            span.set_attribute("data_id", data_id)
            span.set_attribute("version", version)
            span.set_attribute("content_type", content_type)
            span.set_attribute("user_id", user_id)
            span.set_attribute("size_bytes", len(content))

            vl = _sanitize_version_label(version_label) if version_label else _make_version_label()
            blob_path = f"{user_id}/{data_id}/{vl}/data"
            logger.info("Storing raw data at path: %s", blob_path)
            self.raw_store.write(blob_path, content, content_type)

            span.set_attribute("version_label", vl)
            _data_ops_counter.add(1, {"operation": "store_raw", "content_type": content_type})
            logger.debug("Stored raw data", extra={"data_id": data_id, "version": version, "version_label": vl, "size": len(content), "user_id": user_id})
            return len(content), vl

    def get_raw_data(self, data_id: str, user_id: str, version: Optional[int] = None) -> Optional[Tuple[bytes, str]]:
        """Get raw data. If version is None, gets current version. Returns None if not found.

        Path: ``{user_id}/{data_id}/{version_label}/data``
        The version_label is resolved from the VersionInfo recorded in metadata.
        """
        with tracer.start_as_current_span("get_raw_data") as span:
            span.set_attribute("data_id", data_id)
            span.set_attribute("user_id", user_id)

            metadata = self.get_metadata(data_id, user_id)
            if metadata is None:
                return None

            if version is None:
                version = metadata.current_version

            span.set_attribute("version", version)

            version_info = next((v for v in metadata.versions if v.version == version), None)
            vl = getattr(version_info, "version_label", None) if version_info else None

            if not vl:
                logger.warning("No version_label found for data_id=%s version=%s", data_id, version)
                _storage_errors_counter.add(1, {"operation": "get_raw", "error": "no_version_label"})
                return None

            blob_path = f"{user_id}/{data_id}/{_sanitize_version_label(vl)}/data"
            try:
                content = self.raw_store.read(blob_path)
                content_type = self.raw_store.get_content_type(blob_path)
                _data_ops_counter.add(1, {"operation": "get_raw", "content_type": content_type})
                return content, content_type
            except FileNotFoundError:
                _storage_errors_counter.add(1, {"operation": "get_raw", "error": "not_found"})
                return None

    def store_parsed_artifacts(
        self,
        data_id: str,
        user_id: str,
        markdown: str,
        document: dict,
        version: Optional[int] = None,
    ) -> dict:
        """Persist parsed markdown + JSON next to the raw blob for a data version.

        Paths:
          ``{user_id}/{data_id}/{version_label}/parsed/document.md``
          ``{user_id}/{data_id}/{version_label}/parsed/document.json``
        """
        user_id = (user_id or "").strip() or config.DEFAULT_USER_ID
        metadata = self.get_metadata(data_id, user_id)
        if metadata is None:
            raise FileNotFoundError(f"Data not found: {data_id}")

        ver = version if version is not None else metadata.current_version
        version_info = next((v for v in metadata.versions if v.version == ver), None)
        vl = getattr(version_info, "version_label", None) if version_info else None
        if not vl:
            vl = metadata.data_version_label
        if not vl:
            raise FileNotFoundError(f"No version_label for data_id={data_id} version={ver}")

        vl = _sanitize_version_label(vl)
        base = f"{user_id}/{data_id}/{vl}/parsed"
        md_path = f"{base}/document.md"
        json_path = f"{base}/document.json"

        doc_payload = dict(document)
        doc_payload.setdefault("parse_status", "ready")
        doc_payload.setdefault("markdown_uri", md_path)

        self.raw_store.write(md_path, markdown.encode("utf-8"), "text/markdown; charset=utf-8")
        self.raw_store.write(
            json_path,
            json.dumps(doc_payload, indent=2).encode("utf-8"),
            "application/json",
        )
        logger.info("Stored parsed artifacts for %s at %s", data_id, base)
        return {
            "data_id": data_id,
            "version_label": vl,
            "parse_status": doc_payload.get("parse_status", "ready"),
            "markdown_path": md_path,
            "json_path": json_path,
        }

    def get_parsed_artifact(
        self,
        data_id: str,
        user_id: str,
        fmt: str = "markdown",
        version: Optional[int] = None,
    ) -> Optional[Tuple[bytes, str]]:
        """Return parsed body bytes and content-type (markdown or json)."""
        user_id = (user_id or "").strip() or config.DEFAULT_USER_ID
        metadata = self.get_metadata(data_id, user_id)
        if metadata is None:
            return None

        ver = version if version is not None else metadata.current_version
        version_info = next((v for v in metadata.versions if v.version == ver), None)
        vl = getattr(version_info, "version_label", None) if version_info else None
        if not vl:
            vl = metadata.data_version_label
        if not vl:
            return None

        vl = _sanitize_version_label(vl)
        suffix = "document.json" if fmt == "json" else "document.md"
        blob_path = f"{user_id}/{data_id}/{vl}/parsed/{suffix}"
        try:
            content = self.raw_store.read(blob_path)
            content_type = self.raw_store.get_content_type(blob_path)
            return content, content_type
        except FileNotFoundError:
            return None

    def store_metadata(self, metadata: DataMetadata) -> None:
        """Store metadata in the blob store.

        Writes two blobs:
        - ``{user_id}/{data_id}/meta.json`` — latest/current (fast access)
        - ``{user_id}/{data_id}/{version_label}/meta.json`` — per-version snapshot (new)

        The ``address`` field is excluded because it is computed at response time.
        """
        with tracer.start_as_current_span("store_metadata") as span:
            span.set_attribute("data_id", metadata.data_id)
            raw_uid = (
                metadata.owner.user.get("user_id")
                if metadata.owner and metadata.owner.user
                else ""
            )
            # Guarantee user_id is never empty
            user_id = (raw_uid or "").strip() or config.DEFAULT_USER_ID
            span.set_attribute("user_id", user_id)
            payload = json.dumps(metadata.model_dump(exclude={"address"}), indent=2).encode("utf-8")

            # Latest / current copy
            blob_path = f"{user_id}/{metadata.data_id}/meta.json"
            logger.info("Storing metadata at path: %s", blob_path)
            self.meta_store.write(blob_path, payload, "application/json")

            # Per-version snapshot — use version_label from the latest VersionInfo if available
            latest_vi = metadata.versions[-1] if metadata.versions else None
            vl = getattr(latest_vi, "version_label", None) if latest_vi else None
            if vl:
                snapshot_path = f"{user_id}/{metadata.data_id}/{_sanitize_version_label(vl)}/meta.json"
                try:
                    self.meta_store.write(snapshot_path, payload, "application/json")
                except Exception as exc:
                    logger.debug("Failed to write per-version metadata snapshot (non-fatal): %s", exc)

    def get_metadata(self, data_id: str, user_id: str) -> Optional[DataMetadata]:
        """Get metadata. Returns None if not found.

        Path: ``{user_id}/{data_id}/meta.json``
        """
        with tracer.start_as_current_span("get_metadata") as span:
            span.set_attribute("data_id", data_id)
            span.set_attribute("user_id", user_id)
            blob_path = f"{user_id}/{data_id}/meta.json"
            try:
                content = self.meta_store.read(blob_path)
                data = json.loads(content)
                return DataMetadata(**data)
            except FileNotFoundError:
                _storage_errors_counter.add(1, {"operation": "get_metadata", "error": "not_found"})
                return None

    def list_all_metadata(self, user_id: Optional[str] = None) -> List[DataListItem]:
        """List all data items from the blob store. Optionally filter by owner user_id."""
        with tracer.start_as_current_span("list_all_metadata") as span:
            items = []
            prefix = f"{user_id}/" if user_id else ""
            blob_infos = self.meta_store.list_blobs(prefix=prefix)

            for info in blob_infos:
                if info.name.endswith("/meta.json"):
                    # Skip per-version snapshots: they live at {user_id}/{data_id}/ver_.../meta.json
                    # Top-level metas are at {user_id}/{data_id}/meta.json (2 slashes, no ver_ segment)
                    parts = info.name.rstrip("/meta.json").rsplit("/", 1)
                    if len(parts) >= 1 and parts[-1].startswith("ver_"):
                        continue
                    try:
                        content = self.meta_store.read(info.name)
                        metadata = json.loads(content)

                        # Get the latest version info
                        latest_version = metadata["versions"][-1] if metadata["versions"] else None

                        ct = latest_version["content_type"] if latest_version else "unknown"
                        items.append(DataListItem(
                            data_id=metadata["data_id"],
                            current_version=metadata["current_version"],
                            created_at=metadata["created_at"],
                            updated_at=metadata["updated_at"],
                            content_type=ct,
                            size=latest_version["size"] if latest_version else 0,
                            name=metadata.get("name"),
                            description=metadata.get("description"),
                            access=metadata.get("access"),
                            memory_ids=metadata.get("memory_ids"),
                            tags=metadata.get("tags"),
                            url=metadata.get("url"),
                            mime_type=metadata.get("mime_type") or ct,
                            is_downloaded=metadata.get("is_downloaded", False),
                        ))
                    except Exception as e:
                        logger.warning(
                            "Failed to load metadata blob",
                            extra={"blob": info.name, "error": str(e)},
                        )
                        _storage_errors_counter.add(1, {"operation": "list_metadata", "error": type(e).__name__})
                        continue

            # Sort by updated_at descending
            items.sort(key=lambda x: x.updated_at, reverse=True)
            span.set_attribute("items_count", len(items))
            return items

    def list_all_metadata_paginated(
        self,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        tags: Optional[List[str]] = None,
        match_all: bool = False,
        project_id: Optional[str] = None,
    ) -> Tuple[List[DataListItem], int]:
        """List data items with pagination and optional tag filter.

        Returns (items for this page, total count). Default implementation
        uses list_all_metadata then filters, sorts, and slices.
        SupabaseStorage overrides to use a single DB query.
        """
        all_items = self.list_all_metadata(user_id=user_id)
        if tags:
            search_tags = set(tags)
            filtered = []
            for item in all_items:
                item_tags = set(item.tags or [])
                if match_all:
                    if search_tags.issubset(item_tags):
                        filtered.append(item)
                else:
                    if search_tags.intersection(item_tags):
                        filtered.append(item)
            all_items = filtered
        all_items.sort(key=lambda x: x.updated_at, reverse=True)
        total = len(all_items)
        items = all_items[skip : skip + limit]
        return items, total

    # =========================================================================
    # Access Control Methods
    # =========================================================================

    def check_access(self, owner_id: str, data_id: str, user_id: Optional[str] = None, user_role: Optional[str] = None) -> bool:
        """
        Check if a user has access to a data item.
        
        Args:
            owner_id: The ID of the user who owns the data (to find the file).
            data_id: The data item ID.
            user_id: The ID of the user requesting access.
            user_role: The role of the user requesting access.
        """
        metadata = self.get_metadata(data_id, owner_id)
        if metadata is None:
            return False
        
        access = metadata.access
        
        # No access control defined = public access
        if access is None:
            return True
        
        # Empty list = no access
        if len(access) == 0:
            return False
        
        # Check for wildcard
        if "*" in access:
            return True
        
        # Check user-specific access
        if user_id:
            if f"user:{user_id}" in access:
                return True
        
        # Check role-specific access
        if user_role:
            if f"role:{user_role}" in access:
                return True
        
        return False

    def update_access(self, owner_id: str, data_id: str, access: Optional[List[str]]) -> DataMetadata:
        """
        Update access control for a data item.
        
        Args:
            owner_id: The ID of the user who owns the data.
            data_id: The data item ID
            access: New access control list (None for public, ["*"] for all, specific entries)
        """
        metadata = self.get_metadata(data_id, owner_id)
        if metadata is None:
            raise FileNotFoundError(f"Data not found: {data_id}")
        metadata.access = access
        metadata.updated_at = datetime.utcnow().isoformat() + "Z"
        
        self.store_metadata(metadata)
        return metadata

    # =========================================================================
    # Tags Methods
    # =========================================================================

    def update_tags(self, owner_id: str, data_id: str, tags: Optional[List[str]]) -> DataMetadata:
        """
        Update tags for a data item.
        """
        metadata = self.get_metadata(data_id, owner_id)
        if metadata is None:
            raise FileNotFoundError(f"Data not found: {data_id}")
        # Ensure tags are unique
        metadata.tags = list(set(tags)) if tags else None
        metadata.updated_at = datetime.utcnow().isoformat() + "Z"
        
        self.store_metadata(metadata)
        return metadata

    def add_tags(self, owner_id: str, data_id: str, tags: List[str]) -> DataMetadata:
        """
        Add tags to a data item (merges with existing tags).
        """
        metadata = self.get_metadata(data_id, owner_id)
        if metadata is None:
            raise FileNotFoundError(f"Data not found: {data_id}")
        existing_tags = set(metadata.tags) if metadata.tags else set()
        existing_tags.update(tags)
        metadata.tags = list(existing_tags)
        metadata.updated_at = datetime.utcnow().isoformat() + "Z"
        
        self.store_metadata(metadata)
        return metadata

    def remove_tags(self, owner_id: str, data_id: str, tags: List[str]) -> DataMetadata:
        """
        Remove specific tags from a data item.
        """
        metadata = self.get_metadata(data_id, owner_id)
        if metadata is None:
            raise FileNotFoundError(f"Data not found: {data_id}")
        if metadata.tags:
            tags_to_remove = set(tags)
            metadata.tags = [t for t in metadata.tags if t not in tags_to_remove]
            if not metadata.tags:
                metadata.tags = None
        metadata.updated_at = datetime.utcnow().isoformat() + "Z"
        
        self.store_metadata(metadata)
        return metadata

    def search_by_tags(
        self, 
        tags: List[str], 
        match_all: bool = False,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None
    ) -> List[DataListItem]:
        """
        Search data items by tags.
        
        Args:
            tags: Tags to search for
            match_all: If True, item must have ALL tags. If False, item must have ANY tag.
            user_id: Optional user ID for access filtering
            user_role: Optional user role for access filtering
        
        Returns:
            List of matching DataListItem objects
        """
        all_items = self.list_all_metadata()
        matching_items = []
        search_tags = set(tags)
        
        for item in all_items:
            if not item.tags:
                continue
            
            item_tags = set(item.tags)
            
            if match_all:
                # Item must have ALL search tags
                if search_tags.issubset(item_tags):
                    matching_items.append(item)
            else:
                # Item must have ANY search tag
                if search_tags.intersection(item_tags):
                    matching_items.append(item)
        
        # Apply access filtering if user context provided
        if user_id or user_role:
            filtered_items = []
            for item in matching_items:
                # Public access (no restrictions)
                if item.access is None:
                    filtered_items.append(item)
                    continue
                
                # Wildcard access
                if "*" in item.access:
                    filtered_items.append(item)
                    continue
                
                # User-specific access
                if user_id and f"user:{user_id}" in item.access:
                    filtered_items.append(item)
                    continue
                
                # Role-specific access
                if user_role and f"role:{user_role}" in item.access:
                    filtered_items.append(item)
                    continue
            
            return filtered_items
        
        return matching_items

    def get_all_tags(self) -> List[str]:
        """
        Get all unique tags used across all data items.
        
        Returns:
            Sorted list of unique tags
        """
        all_items = self.list_all_metadata()
        all_tags = set()
        
        for item in all_items:
            if item.tags:
                all_tags.update(item.tags)
        
        return sorted(list(all_tags))

    # =========================================================================
    # Data Info Methods (Name, Description)
    # =========================================================================

    def update_info(
        self, 
        data_id: str, 
        name: Optional[str] = None, 
        description: Optional[str] = None,
        user_id: str = config.DEFAULT_USER_ID
    ) -> DataMetadata:
        """
        Update name and/or description for a data item.
        
        Args:
            data_id: The data item ID
            name: New name (None to keep existing, empty string to clear)
            description: New description (None to keep existing, empty string to clear)
            user_id: The user ID (for multi-tenancy)
        
        Returns:
            Updated DataMetadata
        """
        metadata = self.get_metadata(data_id, user_id)
        if metadata is None:
            raise FileNotFoundError(f"Data not found: {data_id}")
        
        # Update name if provided (including empty string to clear)
        if name is not None:
            metadata.name = name if name else None
        
        # Update description if provided (including empty string to clear)
        if description is not None:
            metadata.description = description if description else None
        
        metadata.updated_at = datetime.utcnow().isoformat() + "Z"
        
        self.store_metadata(metadata)
        return metadata

    # ------------------------------------------------------------------
    # Plan 1 — URL download-state helper
    # ------------------------------------------------------------------

    def update_download_state(
        self,
        data_id: str,
        is_downloaded: bool = True,
        mime_type: Optional[str] = None,
        user_id: str = config.DEFAULT_USER_ID,
    ) -> DataMetadata:
        """Mark a data item as downloaded (or not) and optionally update its mime_type.

        Used by the data router after fetching remote content so that
        subsequent queries can tell whether a URL has been materialised.
        """
        metadata = self.get_metadata(data_id, user_id)
        if metadata is None:
            raise FileNotFoundError(f"Data not found: {data_id}")
        metadata.is_downloaded = is_downloaded
        if mime_type is not None:
            metadata.mime_type = mime_type
        metadata.updated_at = datetime.utcnow().isoformat() + "Z"
        self.store_metadata(metadata)
        return metadata

    # ------------------------------------------------------------------
    # Plan 1 — Agent memory helpers
    # ------------------------------------------------------------------

    def get_or_create_agent_memory(self, user_id: str, agent_session_id: str) -> Memory:
        """Idempotently return (or create) a SESSION memory for an AI agent session.

        Lets the AI query layer persist per-session context across turns.
        The canonical ID is ``agent-session-{agent_session_id}``.
        """
        self._check_memories_enabled()
        memory_id = f"agent-session-{agent_session_id}"
        existing = self.get_memory(memory_id, user_id)
        if existing:
            return existing
        return self.create_memory(
            MemoryCreate(
                memory_id=memory_id,
                memory_type=MemoryType.SESSION,
                name=f"Agent session {agent_session_id}",
                user_id=user_id,
                metadata={"agent_session_id": agent_session_id, "auto_created": True},
            ),
            memory_id_override=memory_id,
        )

    # ------------------------------------------------------------------
    # Plan 2 — Conversation memory helper
    # ------------------------------------------------------------------

    def get_or_create_conversation_memory(
        self,
        user_id: str,
        conversation_id: str,
        channel_type: Optional[str] = None,
    ) -> Memory:
        """Idempotently return (or create) a CONVERSATION memory.

        The canonical ID is ``conversation-{conversation_id}``.
        """
        self._check_memories_enabled()
        memory_id = f"conversation-{conversation_id}"
        existing = self.get_memory(memory_id, user_id)
        if existing:
            return existing
        return self.create_memory(
            MemoryCreate(
                memory_id=memory_id,
                memory_type=MemoryType.CONVERSATION,
                name=f"Conversation {conversation_id}",
                user_id=user_id,
                metadata={
                    "conversation_id": conversation_id,
                    "channel_type": channel_type,
                    "auto_created": True,
                },
            ),
            memory_id_override=memory_id,
        )

    def list_accessible_data(self, user_id: Optional[str] = None, user_role: Optional[str] = None) -> List[DataListItem]:
        """
        List data items accessible to a specific user.
        
        Returns all items the user can access based on access control rules.
        """
        all_items = self.list_all_metadata()
        
        # If no user context, only return public items
        if not user_id and not user_role:
            return [item for item in all_items if item.access is None]
        
        accessible = []
        for item in all_items:
            # Public access (no restrictions)
            if item.access is None:
                accessible.append(item)
                continue
            
            # Wildcard access
            if "*" in item.access:
                accessible.append(item)
                continue
            
            # User-specific access
            if user_id and f"user:{user_id}" in item.access:
                accessible.append(item)
                continue
            
            # Role-specific access
            if user_role and f"role:{user_role}" in item.access:
                accessible.append(item)
                continue
        
        return accessible

    def delete_data(self, data_id: str, user_id: str = config.DEFAULT_USER_ID) -> None:
        """Delete all versions of data, metadata, embeddings, and viewpoints.

        Removes blobs under ``{user_id}/{data_id}/`` from all relevant stores,
        then cleans up any reverse index entries.
        """
        with tracer.start_as_current_span("delete_data") as span:
            span.set_attribute("data_id", data_id)
            span.set_attribute("user_id", user_id)

            # Fetch metadata before deleting so we can pass tags to index cleanup
            metadata = self.get_metadata(data_id, user_id)
            tags = metadata.tags if metadata else None

            # Delete all raw data versions (new path: {user_id}/{data_id}/ver_*/data)
            prefix = f"{user_id}/{data_id}/"
            blob_infos = self.raw_store.list_blobs(prefix=prefix)
            for info in blob_infos:
                self.raw_store.delete(info.name)

            # Delete all metadata blobs (latest + all version snapshots)
            for info in self.meta_store.list_blobs(prefix=f"{user_id}/{data_id}/"):
                try:
                    self.meta_store.delete(info.name)
                except Exception:
                    pass

            # Delete embeddings via the storage-specific method (handles both
            # blob-backed and pgvector-backed implementations like SupabaseStorage)
            try:
                self.delete_embeddings(data_id, user_id)
            except Exception as exc:
                logger.warning("delete_embeddings failed for %s: %s", data_id, exc)

            # Also clean up any embedding blobs (for blob-backed stores)
            if self.embeddings_store:
                emb_prefix = f"{user_id}/{data_id}/"
                emb_blobs = list(self.embeddings_store.list_blobs(prefix=emb_prefix))
                if emb_blobs:
                    logger.info("Deleting %d embedding blobs for %s", len(emb_blobs), data_id)
                for info in emb_blobs:
                    try:
                        self.embeddings_store.delete(info.name)
                    except Exception as exc:
                        logger.warning("Failed to delete embedding blob %s: %s", info.name, exc)
            if self.viewpoints_store:
                vp_blobs = list(self.viewpoints_store.list_blobs(prefix=f"{user_id}/{data_id}/"))
                logger.info("Deleting %d viewpoint blobs for %s", len(vp_blobs), data_id)
                for info in vp_blobs:
                    try:
                        self.viewpoints_store.delete(info.name)
                    except Exception as exc:
                        logger.warning("Failed to delete viewpoint blob %s: %s", info.name, exc)

            # Clean up reverse index
            self._delete_data_index(user_id, data_id, tags=tags)

            span.set_attribute("blobs_deleted", len(blob_infos))
            _data_ops_counter.add(1, {"operation": "delete"})
            logger.info("Data deleted", extra={"data_id": data_id, "user_id": user_id, "blobs_deleted": len(blob_infos)})

    # =========================================================================
    # Bulk / Mass Delete Methods
    # =========================================================================

    def delete_bulk_data(self, data_ids: List[str], user_id: str = config.DEFAULT_USER_ID) -> Tuple[List[str], List[str]]:
        """Delete multiple data items by their IDs.

        Returns:
            Tuple of (deleted_ids, failed_ids)
        """
        with tracer.start_as_current_span("delete_bulk_data") as span:
            span.set_attribute("requested_count", len(data_ids))
            span.set_attribute("user_id", user_id)
            deleted_ids = []
            failed_ids = []

            for data_id in data_ids:
                try:
                    self.delete_data(data_id, user_id)
                    deleted_ids.append(data_id)
                except Exception as e:
                    logger.warning(
                        "Failed to delete data item in bulk operation",
                        extra={"data_id": data_id, "error": str(e)},
                    )
                    failed_ids.append(data_id)

            span.set_attribute("deleted_count", len(deleted_ids))
            span.set_attribute("failed_count", len(failed_ids))
            _data_ops_counter.add(len(deleted_ids), {"operation": "bulk_delete"})
            logger.info(
                "Bulk data delete completed",
                extra={"deleted": len(deleted_ids), "failed": len(failed_ids)},
            )
            return deleted_ids, failed_ids

    def delete_all_user_data(self, user: str) -> int:
        """Delete ALL data items for a user (based on their memories).

        Collects data IDs across all memories owned by the user, deletes
        the data items, then deletes the memories themselves.

        Returns:
            Number of data items deleted.
        """
        with tracer.start_as_current_span("delete_all_user_data") as span:
            span.set_attribute("user", user)

            # Collect all data_ids from user's memories
            user_memories, _ = self.list_memories(user_id=user, limit=10000)
            data_ids = set()
            for mem in user_memories:
                data_ids.update(mem.data_ids)

            deleted_count = 0
            for data_id in data_ids:
                try:
                    self.delete_data(data_id, user)
                    deleted_count += 1
                except Exception as e:
                    logger.warning(
                        "Failed to delete user data item",
                        extra={"user": user, "data_id": data_id, "error": str(e)},
                    )

            # Delete all user's memories
            for mem in user_memories:
                try:
                    self.delete_memory(mem.memory_id, user)
                except Exception:
                    pass

            span.set_attribute("deleted_count", deleted_count)
            _data_ops_counter.add(deleted_count, {"operation": "delete_all_user_data"})
            logger.info(
                "All user data deleted",
                extra={"user": user, "deleted_count": deleted_count, "memories_cleared": len(user_memories)},
            )
            return deleted_count

    # (Session-specific delete methods removed -- use delete_memory_data and delete_bulk_memories)

    # =========================================================================
    # Memory Management Methods
    # =========================================================================

    def _record_memory_data_entry(
        self, memory_id: str, data_id: str,
        action: Optional[str] = None, version: Optional[int] = None,
        entry_metadata: Optional[Dict] = None, purpose: Optional[str] = None,
        user_id: str = config.DEFAULT_USER_ID,
    ) -> MemoryDataEntry:
        """Write a MemoryDataEntry into the memories blob store.

        Path: ``{user_id}/{memory_type}/{memory_id}/data/{data_id}.json``
        """
        self._check_memories_enabled()
        timestamp = datetime.utcnow().isoformat() + "Z"
        entry = MemoryDataEntry(
            data_id=data_id,
            memory_id=memory_id,
            action=action,
            version=version,
            associated_at=timestamp,
            purpose=purpose,
            metadata=entry_metadata or {},
        )
        blob_path = self._memory_data_path(user_id, memory_id, data_id)
        self.memories_store.write(
            blob_path,
            json.dumps(entry.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        return entry

    def _update_user_default_timeline_id(self, user: str, timeline_memory_id: str) -> None:
        """Best-effort: set default_timeline_id in user metadata. Never raises."""
        if not config.is_user_management_enabled():
            return
        try:
            u = self.get_user(user)
            if not u:
                return
            meta = dict(u.metadata or {})
            if meta.get("default_timeline_id") == timeline_memory_id:
                return
            meta["default_timeline_id"] = timeline_memory_id
            self.update_user(user, UserUpdate(metadata=meta))
        except Exception as exc:
            logger.debug(
                "Could not update user default_timeline_id: %s",
                exc,
                extra={"user": user, "timeline_memory_id": timeline_memory_id},
            )

    def get_or_create_default_timeline_memory(self, user: str) -> Memory:
        """Return the user's default timeline memory, creating it on first call."""
        self._check_memories_enabled()
        # Convention: default timeline memory_id = "timeline-{user}"
        default_id = f"timeline-{user}"
        existing = self.get_memory(default_id, user)
        if existing:
            self._update_user_default_timeline_id(user, existing.memory_id)
            return existing
        create_req = MemoryCreate(
            memory_type=MemoryType.TIMELINE,
            name="Audit",
            user_id=user,
        )
        memory = self.create_memory(create_req, memory_id_override=default_id)
        self._update_user_default_timeline_id(user, memory.memory_id)
        return memory

    def _resolve_memory_name(
        self,
        name: Optional[str],
        user_id: str,
        memory_type: "MemoryType",
    ) -> str:
        """Return the caller-provided name, or auto-generate ``{username}-{memory_type}``."""
        if name and name.strip():
            return name.strip()
        display = None
        if config.is_user_management_enabled():
            try:
                user = self.get_user(user_id)
                if user:
                    display = user.display_name or user.username
            except Exception:
                pass
        if not display:
            display = "demo" if user_id == config.DEFAULT_USER_ID else user_id[:8]
        mem_type = memory_type.value if hasattr(memory_type, "value") else str(memory_type)
        # Display "audit" instead of "timeline" for timeline memories
        if mem_type == MemoryType.TIMELINE.value:
            mem_type = "audit"
        return f"{display}-{mem_type}"

    def create_memory(
        self, memory_create: MemoryCreate, memory_id_override: Optional[str] = None
    ) -> Memory:
        """Create a new memory container.

        Path: ``{user_id}/{memory_type}/{memory_id}/meta.json``

        When ``memory_create.name`` is ``None`` or blank, auto-generates a
        meaningful name as ``{username}-{memory_type}`` by looking up the
        user's display name / username.
        """
        self._check_memories_enabled()
        now = datetime.utcnow()
        now_str = now.isoformat() + "Z"
        memory_id = memory_id_override or generate_memory_id(memory_create.memory_type)
        user_id = memory_create.user_id or config.DEFAULT_USER_ID

        # Check for duplicate
        if self.get_memory(memory_id, user_id) is not None:
            raise ValueError(f"Memory ID '{memory_id}' already exists")

        duration = MemoryDuration(MEMORY_TYPE_DURATION[memory_create.memory_type])
        category = MEMORY_TYPE_CATEGORY.get(memory_create.memory_type, MemoryCategory.USER)
        category = category.value if hasattr(category, 'value') else str(category)

        resolved_name = self._resolve_memory_name(
            memory_create.name, user_id, memory_create.memory_type,
        )

        # Compute expiry: explicit ttl_hours > no_expiry > default TTL per type
        expires_at = None
        if memory_create.no_expiry:
            expires_at = None
        elif memory_create.ttl_hours is not None:
            expires_at = (now + timedelta(hours=memory_create.ttl_hours)).isoformat() + "Z"
        else:
            default_ttl = DEFAULT_TTL_HOURS.get(memory_create.memory_type)
            if default_ttl is not None:
                expires_at = (now + timedelta(hours=default_ttl)).isoformat() + "Z"

        # Access level defaults to private
        access_level = memory_create.access_level or AccessLevel.PRIVATE.value

        memory = Memory(
            memory_id=memory_id,
            memory_type=memory_create.memory_type,
            duration=duration,
            category=category,
            name=resolved_name,
            description=memory_create.description,
            user_id=memory_create.user_id,
            sub_type=memory_create.sub_type,
            data_ids=[],
            metadata=memory_create.metadata,
            access_level=access_level,
            shared_with=memory_create.shared_with,
            device_id=memory_create.device_id,
            device_info=memory_create.device_info,
            active=True if memory_create.memory_type == MemoryType.SESSION else None,
            expires_at=expires_at,
            created_at=now_str,
            updated_at=now_str,
            org_id=getattr(memory_create, 'org_id', None),
            project_id=getattr(memory_create, 'project_id', None),
        )

        blob_path = self._memory_meta_path(user_id, memory_id)
        self.memories_store.write(
            blob_path,
            json.dumps(memory.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        # Write reverse index entry
        self._write_memory_index(user_id, memory_create.memory_type.value if hasattr(memory_create.memory_type, "value") else str(memory_create.memory_type), memory_id, memory)
        logger.info("Memory created", extra={"memory_id": memory_id, "user_id": user_id, "type": memory_create.memory_type})
        return memory

    def get_memory(
        self, memory_id: str, user_id: str = config.DEFAULT_USER_ID,
        requesting_user_id: Optional[str] = None,
        include_expired: bool = False,
    ) -> Optional[Memory]:
        """Get a memory by ID.

        Path: ``{user_id}/{memory_type}/{memory_id}/meta.json``
        Returns None if not found, expired (unless include_expired), or
        access denied for the requesting user.
        """
        self._check_memories_enabled()
        blob_path = self._memory_meta_path(user_id, memory_id)
        try:
            content = self.memories_store.read(blob_path)
            memory = Memory(**json.loads(content))
        except FileNotFoundError:
            return None

        # Lazy expiry check
        if not include_expired and memory.expires_at:
            try:
                exp = datetime.fromisoformat(memory.expires_at.rstrip("Z"))
                if exp < datetime.utcnow():
                    return None
            except (ValueError, TypeError):
                pass

        # Access level check
        if requesting_user_id and requesting_user_id != user_id:
            al = getattr(memory, "access_level", "private") or "private"
            if al == AccessLevel.PRIVATE.value:
                return None
            if al == AccessLevel.SHARED.value:
                shared = getattr(memory, "shared_with", []) or []
                if requesting_user_id not in shared:
                    return None
            if al == AccessLevel.RESTRICTED.value:
                shared = getattr(memory, "shared_with", []) or []
                if requesting_user_id not in shared:
                    return None
            # public — allow

        return memory

    def update_memory(self, memory_id: str, memory_update: MemoryUpdate, user_id: str = config.DEFAULT_USER_ID) -> Optional[Memory]:
        """Update a memory's metadata."""
        self._check_memories_enabled()
        memory = self.get_memory(memory_id, user_id)
        if not memory:
            return None

        now = datetime.utcnow()
        now_str = now.isoformat() + "Z"

        if memory_update.name is not None:
            memory.name = memory_update.name
        if memory_update.description is not None:
            memory.description = memory_update.description
        if "sub_type" in memory_update.model_dump(exclude_unset=True):
            memory.sub_type = memory_update.sub_type
        if memory_update.metadata is not None:
            memory.metadata = memory_update.metadata
        if memory_update.device_info is not None:
            memory.device_info = memory_update.device_info
        if memory_update.active is not None:
            memory.active = memory_update.active
        if "access_level" in memory_update.model_dump(exclude_unset=True):
            memory.access_level = memory_update.access_level
        if memory_update.shared_with is not None:
            memory.shared_with = memory_update.shared_with
        if "expires_at" in memory_update.model_dump(exclude_unset=True):
            memory.expires_at = memory_update.expires_at
        if memory_update.extend_ttl_hours is not None:
            if memory.expires_at:
                current_expires = datetime.fromisoformat(memory.expires_at.rstrip("Z"))
                new_expires = current_expires + timedelta(hours=memory_update.extend_ttl_hours)
                memory.expires_at = new_expires.isoformat() + "Z"
            else:
                # No existing expiry — set from now
                new_expires = now + timedelta(hours=memory_update.extend_ttl_hours)
                memory.expires_at = new_expires.isoformat() + "Z"

        memory.updated_at = now_str

        blob_path = self._memory_meta_path(user_id, memory_id)
        self.memories_store.write(
            blob_path,
            json.dumps(memory.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        return memory

    def delete_memory(self, memory_id: str, user_id: str = config.DEFAULT_USER_ID) -> bool:
        """Delete a memory and all its data entries. Returns True if existed."""
        self._check_memories_enabled()
        memory = self.get_memory(memory_id, user_id)
        if not memory:
            return False

        prefix = self._memory_prefix(user_id, memory_id)
        blob_infos = self.memories_store.list_blobs(prefix=prefix)
        for info in blob_infos:
            try:
                self.memories_store.delete(info.name)
            except Exception:
                pass

        # Clean up reverse index
        self._delete_memory_index(user_id, memory_id)
        logger.info("Memory deleted", extra={"memory_id": memory_id, "user_id": user_id})
        return True

    def list_memories(
        self,
        user_id: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        duration: Optional[MemoryDuration] = None,
        active: Optional[bool] = None,
        sub_type: Optional[str] = None,
        access_level: Optional[str] = None,
        category: Optional[str] = None,
        include_expired: bool = False,
        project_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Memory], int]:
        """List memories with optional filters.

        When ``user_id`` is provided the scan is scoped to ``{user_id}/`` (or
        ``{user_id}/{memory_type}/`` when type is also specified), avoiding a
        full-bucket scan.

        By default, expired memories are hidden. Set ``include_expired=True``
        to include them.
        """
        self._check_memories_enabled()
        memories: List[Memory] = []
        now = datetime.utcnow()
        # Efficient prefix scan when user context is known
        if user_id and memory_type:
            scan_prefix = f"{user_id}/{memory_type.value}/"
        elif user_id:
            scan_prefix = f"{user_id}/"
        else:
            scan_prefix = ""
        blob_infos = self.memories_store.list_blobs(prefix=scan_prefix)

        for info in blob_infos:
            if not info.name.endswith("/meta.json"):
                continue
            # Skip data entry sub-blobs: path segment before /meta.json must not be "data"
            # Valid memory meta: {user_id}/{memory_type}/{memory_id}/meta.json
            # Skip: {user_id}/{memory_type}/{memory_id}/data/{data_id}/meta.json (no such path, but safety)
            parts = info.name.split("/")
            # Expect exactly 4 parts: user_id / memory_type / memory_id / meta.json
            if len(parts) != 4:
                continue
            try:
                content = self.memories_store.read(info.name)
                mem = Memory(**json.loads(content))

                if user_id is not None and mem.user_id != user_id:
                    continue
                if memory_type is not None and mem.memory_type != memory_type:
                    continue
                if duration is not None and mem.duration != duration:
                    continue
                if active is not None and mem.active != active:
                    continue
                if sub_type is not None and getattr(mem, "sub_type", None) != sub_type:
                    continue
                if access_level is not None and getattr(mem, "access_level", "private") != access_level:
                    continue
                if category is not None and getattr(mem, "category", None) != category:
                    continue
                # When filtering by project_id, include memories explicitly in the project
                # AND memories with no project (unscoped = visible in all projects)
                if project_id is not None:
                    mem_project = getattr(mem, "project_id", None)
                    if mem_project is not None and mem_project != project_id:
                        continue
                # Filter expired memories by default (lazy expiry check)
                if not include_expired and mem.expires_at:
                    try:
                        exp = datetime.fromisoformat(mem.expires_at.rstrip("Z"))
                        if exp < now:
                            continue
                    except (ValueError, TypeError):
                        pass

                memories.append(mem)
            except Exception as e:
                logger.warning("Failed to load memory", extra={"blob": info.name, "error": str(e)})
                _storage_errors_counter.add(1, {"operation": "list_memories", "error": type(e).__name__})
                continue

        memories.sort(key=lambda x: x.updated_at, reverse=True)
        total = len(memories)
        paginated = memories[skip:skip + limit]
        return paginated, total

    def add_data_to_memory(
        self, memory_id: str, data_id: str,
        action: Optional[str] = None, version: Optional[int] = None,
        entry_metadata: Optional[Dict] = None, purpose: Optional[str] = None,
        user_id: str = config.DEFAULT_USER_ID
    ) -> Optional[Memory]:
        """Associate a data item with a memory."""
        self._check_memories_enabled()
        memory = self.get_memory(memory_id, user_id)
        if not memory:
            return None

        # Write the data entry
        self._record_memory_data_entry(
            memory_id, data_id, action, version, entry_metadata, purpose=purpose, user_id=user_id
        )

        # Update cached data_ids
        if data_id not in memory.data_ids:
            memory.data_ids.append(data_id)
            memory.updated_at = datetime.utcnow().isoformat() + "Z"
            blob_path = self._memory_meta_path(user_id, memory_id)
            self.memories_store.write(
                blob_path,
                json.dumps(memory.model_dump(), indent=2).encode("utf-8"),
                "application/json",
            )

        # Also update the data item's memory_ids
        try:
            data_meta = self.get_metadata(data_id, user_id)
            if data_meta:
                current_mids = data_meta.memory_ids or []
                if memory_id not in current_mids:
                    current_mids.append(memory_id)
                    data_meta.memory_ids = current_mids
                    data_meta.updated_at = datetime.utcnow().isoformat() + "Z"
                    self.store_metadata(data_meta)
        except Exception as e:
            logger.warning(
                "Failed to update data metadata with memory_id",
                extra={"memory_id": memory_id, "data_id": data_id, "error": str(e)},
            )

        return memory

    def remove_data_from_memory(self, memory_id: str, data_id: str, user_id: str) -> Optional[Memory]:
        """Remove a data item from a memory."""
        self._check_memories_enabled()
        memory = self.get_memory(memory_id, user_id)
        if not memory:
            return None

        # Delete the data entry
        entry_path = self._memory_data_path(user_id, memory_id, data_id)
        try:
            self.memories_store.delete(entry_path)
        except Exception:
            pass

        # Update cached data_ids
        if data_id in memory.data_ids:
            memory.data_ids.remove(data_id)
            memory.updated_at = datetime.utcnow().isoformat() + "Z"
            blob_path = self._memory_meta_path(user_id, memory_id)
            self.memories_store.write(
                blob_path,
                json.dumps(memory.model_dump(), indent=2).encode("utf-8"),
                "application/json",
            )

        # Also update the data item's memory_ids
        try:
            data_meta = self.get_metadata(data_id, user_id)
            if data_meta and data_meta.memory_ids:
                if memory_id in data_meta.memory_ids:
                    data_meta.memory_ids.remove(memory_id)
                    if not data_meta.memory_ids:
                        data_meta.memory_ids = None
                    data_meta.updated_at = datetime.utcnow().isoformat() + "Z"
                    self.store_metadata(data_meta)
        except Exception as e:
            logger.warning(
                "Failed to update data metadata after memory removal",
                extra={"memory_id": memory_id, "data_id": data_id, "error": str(e)},
            )

        return memory

    def get_memory_data(
        self, memory_id: str, user_id: str, skip: int = 0, limit: int = 100
    ) -> Tuple[List[DataListItem], int]:
        """Get all data items associated with a memory."""
        self._check_memories_enabled()
        memory = self.get_memory(memory_id, user_id)
        if not memory:
            return [], 0

        items: List[DataListItem] = []
        for data_id in memory.data_ids:
            try:
                metadata = self.get_metadata(data_id, user_id)
                if metadata is None:
                    continue
                latest_version = metadata.versions[-1] if metadata.versions else None
                items.append(DataListItem(
                    data_id=metadata.data_id,
                    current_version=metadata.current_version,
                    created_at=metadata.created_at,
                    updated_at=metadata.updated_at,
                    content_type=latest_version.content_type if latest_version else "unknown",
                    size=latest_version.size if latest_version else 0,
                    name=metadata.name,
                    description=metadata.description,
                    access=metadata.access,
                    memory_ids=metadata.memory_ids,
                    tags=metadata.tags,
                    url=metadata.url,
                    mime_type=metadata.mime_type,
                    is_downloaded=metadata.is_downloaded,
                ))
            except Exception:
                continue

        total = len(items)
        paginated = items[skip:skip + limit]
        return paginated, total

    def get_memory_data_entries(self, memory_id: str, user_id: str) -> List[MemoryDataEntry]:
        """Get raw MemoryDataEntry records for a memory (includes action/version)."""
        self._check_memories_enabled()
        entries: List[MemoryDataEntry] = []
        mtype = self._infer_memory_type_from_id(memory_id)
        prefix = f"{user_id}/{mtype}/{memory_id}/data/"
        blob_infos = self.memories_store.list_blobs(prefix=prefix)

        for info in blob_infos:
            if not info.name.endswith(".json"):
                continue
            try:
                content = self.memories_store.read(info.name)
                entries.append(MemoryDataEntry(**json.loads(content)))
            except Exception as e:
                logger.warning("Failed to load memory data entry", extra={"blob": info.name, "error": str(e)})
                continue

        entries.sort(key=lambda x: x.associated_at, reverse=True)
        return entries

    def get_memories_for_data(self, data_id: str, user_id: str) -> List[Memory]:
        """Get all memories that contain a specific data item."""
        self._check_memories_enabled()
        metadata = self.get_metadata(data_id, user_id)
        if not metadata or not metadata.memory_ids:
            return []

        memories = []
        for mid in metadata.memory_ids:
            mem = self.get_memory(mid, user_id)
            if mem:
                memories.append(mem)
        return memories

    def delete_memory_data(self, memory_id: str, user_id: str) -> Tuple[List[str], List[str]]:
        """Delete all data items associated with a memory.

        Returns (deleted_ids, failed_ids).
        """
        self._check_memories_enabled()
        memory = self.get_memory(memory_id, user_id)
        if not memory:
            return [], []

        deleted_ids = []
        failed_ids = []
        for data_id in list(memory.data_ids):
            try:
                self.delete_data(data_id, user_id)
                deleted_ids.append(data_id)
            except Exception as e:
                logger.warning(
                    "Failed to delete memory data item",
                    extra={"memory_id": memory_id, "data_id": data_id, "error": str(e)},
                )
                failed_ids.append(data_id)

        # Clear data entries and update meta
        data_prefix = f"{self._memory_prefix(user_id, memory_id)}data/"
        for info in self.memories_store.list_blobs(prefix=data_prefix):
            try:
                self.memories_store.delete(info.name)
            except Exception:
                pass

        memory.data_ids = [d for d in memory.data_ids if d not in deleted_ids]
        memory.updated_at = datetime.utcnow().isoformat() + "Z"
        blob_path = self._memory_meta_path(user_id, memory_id)
        self.memories_store.write(
            blob_path,
            json.dumps(memory.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

        return deleted_ids, failed_ids

    def delete_bulk_memories(
        self,
        memory_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        delete_data: bool = False,
    ) -> Tuple[int, int]:
        """Delete multiple memories and optionally their associated data.

        Returns (deleted_memories_count, deleted_data_count).
        """
        self._check_memories_enabled()

        target_memories = []
        if memory_ids:
            # If user_id provided, we can fetch directly efficiently
            if user_id:
                for mid in memory_ids:
                    m = self.get_memory(mid, user_id)
                    if m:
                        target_memories.append(m)
            else:
                # Without user_id, we must scan to find which user owns the memory
                # This is inefficient but necessary given the partitioned storage
                all_memories, _ = self.list_memories(limit=10000)
                mid_set = set(memory_ids)
                target_memories = [m for m in all_memories if m.memory_id in mid_set]
        else:
            all_memories, _ = self.list_memories(
                user_id=user_id, memory_type=memory_type, limit=10000
            )
            target_memories = all_memories

        deleted_memories = 0
        deleted_data_items = 0

        for memory in target_memories:
            try:
                mem_user = memory.user_id
                if delete_data and memory.data_ids:
                    for data_id in memory.data_ids:
                        try:
                            self.delete_data(data_id, mem_user)
                            deleted_data_items += 1
                        except Exception as e:
                            logger.warning(
                                "Failed to delete data for memory",
                                extra={"memory_id": memory.memory_id, "data_id": data_id, "error": str(e)},
                            )
                self.delete_memory(memory.memory_id, mem_user)
                deleted_memories += 1
            except Exception as e:
                logger.warning(
                    "Failed to delete memory",
                    extra={"memory_id": memory.memory_id, "error": str(e)},
                )

        return deleted_memories, deleted_data_items

    def create_data(
        self, content: bytes, content_type: str, user: str = config.DEFAULT_USER_ID,
        memory_ids: Optional[List[str]] = None,
        device_info: Optional[DataDeviceInfo] = None,
        tags: Optional[List[str]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        exclusive_memory_ids: bool = False,
        purpose: Optional[str] = None,
        # Plan 1 — provenance / URL fields
        url: Optional[str] = None,
        mime_type: Optional[str] = None,
        is_downloaded: bool = False,
        owner: Optional[DataOwner] = None,
        # Multitenancy / provenance
        provenance: Optional[DataProvenance] = None,
        source_service: Optional[str] = None,
        org_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Tuple[str, int]:
        """Create new data entry and associate with memories. Returns (data_id, version).

        By default, uploaded data is associated with the user's default
        timeline memory and all active session memories, creating any
        of these if necessary.  Any extra ``memory_ids`` supplied by the
        caller are merged in on top of these defaults.

        When ``exclusive_memory_ids`` is ``True`` the auto-association is
        skipped and **only** the explicitly provided ``memory_ids`` are
        used.  This is intended for autonomous agents that manage their
        own session and timeline memories.

        The stored metadata always has ``url``, ``mime_type``, and
        ``is_downloaded`` set; ``mime_type`` defaults to ``content_type``
        when not provided.
        """
        with tracer.start_as_current_span("create_data") as span:
            data_id = generate_data_id()
            version = 1
            timestamp = datetime.utcnow().isoformat() + "Z"

            span.set_attribute("data_id", data_id)
            span.set_attribute("content_type", content_type)
            span.set_attribute("size_bytes", len(content))
            span.set_attribute("user_id", user)

            # Store raw data — get back (size, version_label)
            size, version_label = self.store_raw_data(data_id, version, content, content_type, user)

            # Ensure tags are unique if provided
            unique_tags = list(set(tags)) if tags else None

            # Resolve memory_ids.
            # In exclusive mode, use only the caller-provided IDs.
            # Otherwise merge the user's default timeline + active sessions.
            resolved_memory_ids = list(memory_ids) if memory_ids else []
            if not exclusive_memory_ids and config.is_memories_enabled():
                default_timeline = self.get_or_create_default_timeline_memory(user)
                if default_timeline.memory_id not in resolved_memory_ids:
                    resolved_memory_ids.insert(0, default_timeline.memory_id)
                # Also auto-associate with any active session memories for this user
                active_sessions, _ = self.list_memories(
                    user_id=user, memory_type=MemoryType.SESSION, active=True, limit=100
                )
                for sess_mem in active_sessions:
                    if sess_mem.memory_id not in resolved_memory_ids:
                        resolved_memory_ids.append(sess_mem.memory_id)
            # Resolve owner
            final_owner = owner
            if not final_owner:
                final_owner = DataOwner(user={"user_id": user})
            elif not final_owner.user:
                final_owner.user = {"user_id": user}
            final_owner.user["user_id"] = user

            # Host SaaS / org scoping — explicit args win; else user defaults
            resolved_org_id = org_id
            resolved_project_id = project_id
            if not resolved_project_id or not resolved_org_id:
                try:
                    profile = self.get_user(user)
                    if profile:
                        resolved_org_id = resolved_org_id or getattr(profile, "default_org_id", None)
                        resolved_project_id = resolved_project_id or getattr(
                            profile, "default_project_id", None
                        )
                except Exception:
                    pass

            # Always set url, mime_type, and is_downloaded on metadata (mime_type falls back to content_type).
            effective_mime_type = mime_type if mime_type is not None else content_type
            metadata = DataMetadata(
                data_id=data_id,
                current_version=version,
                versions=[
                    VersionInfo(
                        version=version,
                        timestamp=timestamp,
                        size=size,
                        content_type=content_type,
                        version_label=version_label,
                    )
                ],
                created_at=timestamp,
                updated_at=timestamp,
                name=name,
                description=description,
                access=[f"user:{user}"],
                memory_ids=resolved_memory_ids if resolved_memory_ids else None,
                device_info=device_info,
                tags=unique_tags,
                purpose=purpose or "user_data",
                url=url,
                mime_type=effective_mime_type,
                is_downloaded=is_downloaded,
                owner=final_owner,
                provenance=provenance,
                source_service=source_service or "mem-dog-api",
                data_version_label=version_label,
                org_id=resolved_org_id,
                project_id=resolved_project_id,
            )
            self.store_metadata(metadata)

            # Write reverse data index
            self._write_data_index(user, data_id, metadata)

            # Associate data with each memory
            data_purpose = purpose or "user_data"
            for mid in resolved_memory_ids:
                try:
                    self.add_data_to_memory(
                        mid, data_id, action="create", version=version,
                        purpose=data_purpose, user_id=user
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to associate data with memory",
                        extra={"memory_id": mid, "data_id": data_id, "error": str(e)},
                    )

            _data_ops_counter.add(1, {"operation": "create", "content_type": content_type})
            logger.info("Data created", extra={"data_id": data_id, "size": size, "user": user})
            return data_id, version

    def update_data(
        self, data_id: str, content: bytes, content_type: str, user: str = config.DEFAULT_USER_ID
    ) -> int:
        """Update existing data. Returns new version number.

        Records an 'update' entry in every memory the data belongs to.
        """
        with tracer.start_as_current_span("update_data") as span:
            span.set_attribute("data_id", data_id)
            span.set_attribute("content_type", content_type)
            span.set_attribute("size_bytes", len(content))

            # Get current metadata
            metadata = self.get_metadata(data_id, user)
            if metadata is None:
                raise FileNotFoundError(f"Data not found: {data_id}")

            # Increment version
            new_version = metadata.current_version + 1
            timestamp = datetime.utcnow().isoformat() + "Z"

            # Store new version — get back (size, version_label)
            size, version_label = self.store_raw_data(data_id, new_version, content, content_type, user)

            # Update metadata
            metadata.current_version = new_version
            metadata.versions.append(
                VersionInfo(
                    version=new_version,
                    timestamp=timestamp,
                    size=size,
                    content_type=content_type,
                    version_label=version_label,
                )
            )
            metadata.updated_at = timestamp
            metadata.data_version_label = version_label
            self.store_metadata(metadata)

            # Update reverse data index
            self._write_data_index(user, data_id, metadata)

            # Record update in associated memories
            if metadata.memory_ids and config.is_memories_enabled():
                for mid in metadata.memory_ids:
                    try:
                        self._record_memory_data_entry(
                            mid, data_id, action="update", version=new_version,
                            purpose="user_data", user_id=user
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to record update in memory",
                            extra={"memory_id": mid, "data_id": data_id, "error": str(e)},
                        )

            span.set_attribute("new_version", new_version)
            _data_ops_counter.add(1, {"operation": "update", "content_type": content_type})
            logger.info("Data updated", extra={"data_id": data_id, "version": new_version, "user": user})
            return new_version

    # =========================================================================
    # AI Layer Storage Methods
    # =========================================================================

    # -------------------------------------------------------------------------
    # AI Engine Configuration
    # -------------------------------------------------------------------------

    def store_engine_config(self, engine_config: AIEngineConfig) -> None:
        """Store AI engine configuration for a user."""
        self._check_ai_enabled()
        blob_path = f"{engine_config.user}/engines/{engine_config.engine_id}.json"
        self.ai_config_store.write(
            blob_path,
            json.dumps(engine_config.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

    def get_engine_config(self, user: str, engine_id: str) -> AIEngineConfig:
        """Get AI engine configuration."""
        self._check_ai_enabled()
        blob_path = f"{user}/engines/{engine_id}.json"
        try:
            content = self.ai_config_store.read(blob_path)
            data = json.loads(content)
            return AIEngineConfig(**data)
        except FileNotFoundError:
            raise FileNotFoundError(f"Engine config not found: {engine_id}")

    def list_engine_configs(self, user: str) -> List[AIEngineConfig]:
        """List all AI engine configurations for a user."""
        self._check_ai_enabled()
        configs = []
        prefix = f"{user}/engines/"
        blob_infos = self.ai_config_store.list_blobs(prefix=prefix)

        for info in blob_infos:
            if info.name.endswith(".json"):
                try:
                    content = self.ai_config_store.read(info.name)
                    data = json.loads(content)
                    configs.append(AIEngineConfig(**data))
                except Exception as e:
                    logger.warning("Failed to load engine config", extra={"blob": info.name, "error": str(e)})
                    _storage_errors_counter.add(1, {"operation": "list_engine_configs", "error": type(e).__name__})
                    continue

        return configs

    def delete_engine_config(self, user: str, engine_id: str) -> None:
        """Delete AI engine configuration."""
        self._check_ai_enabled()
        blob_path = f"{user}/engines/{engine_id}.json"
        self.ai_config_store.delete(blob_path)

    # -------------------------------------------------------------------------
    # User AI Preferences
    # -------------------------------------------------------------------------

    def get_user_preferences(self, user: str) -> Optional[UserAIPreferences]:
        """Get user's AI preferences."""
        self._check_ai_enabled()
        blob_path = f"{user}/preferences.json"
        try:
            content = self.ai_config_store.read(blob_path)
            data = json.loads(content)
            return UserAIPreferences(**data)
        except FileNotFoundError:
            return None

    def store_user_preferences(self, preferences: UserAIPreferences) -> None:
        """Store user's AI preferences."""
        self._check_ai_enabled()
        blob_path = f"{preferences.user}/preferences.json"
        self.ai_config_store.write(
            blob_path,
            json.dumps(preferences.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

    # -------------------------------------------------------------------------
    # Global AI Availability
    # -------------------------------------------------------------------------

    def get_global_ai_availability(self) -> GlobalAIAvailability:
        """Get global AI availability configuration."""
        self._check_ai_enabled()
        blob_path = "global/engines.json"
        try:
            content = self.ai_config_store.read(blob_path)
            data = json.loads(content)
            return GlobalAIAvailability(**data)
        except FileNotFoundError:
            return self._get_default_ai_availability()

    def store_global_ai_availability(self, availability: GlobalAIAvailability) -> None:
        """Store global AI availability configuration."""
        self._check_ai_enabled()
        blob_path = "global/engines.json"
        self.ai_config_store.write(
            blob_path,
            json.dumps(availability.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

    def _get_default_ai_availability(self) -> GlobalAIAvailability:
        """
        Return default AI availability configuration.
        
        Native providers: OpenAI, Anthropic, Gemini, Ollama, Bedrock, OpenRouter, 
                         Together, HuggingFace, vLLM, LiteLLM
        
        Via LiteLLM: NVIDIA, Venice, Cloudflare, Vercel, Moonshot, Qwen, GLM,
                    MiniMax, Qianfan, Z.AI, Groq, Mistral, Cohere, and 100+ more.
        See: https://docs.openclaw.ai/providers
        """
        return GlobalAIAvailability(
            available_engines=[
                # --- Tier 1: Major Cloud Providers ---
                GlobalAIEngineInfo(
                    engine_type=AIEngineType.OPENAI,
                    name="OpenAI",
                    requires_api_key=True,
                    default_base_url="https://api.openai.com/v1",
                    models=AIModelCapabilities(
                        embeddings=["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"],
                        completions=["gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo", "o1-preview", "o1-mini"]
                    )
                ),
                GlobalAIEngineInfo(
                    engine_type=AIEngineType.ANTHROPIC,
                    name="Anthropic",
                    requires_api_key=True,
                    default_base_url="https://api.anthropic.com",
                    models=AIModelCapabilities(
                        embeddings=[],  # Anthropic doesn't offer embeddings API
                        completions=["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
                    )
                ),
                GlobalAIEngineInfo(
                    engine_type=AIEngineType.GEMINI,
                    name="Google Gemini",
                    requires_api_key=True,
                    default_base_url="https://generativelanguage.googleapis.com",
                    models=AIModelCapabilities(
                        embeddings=["text-embedding-004", "embedding-001"],
                        completions=["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"]
                    )
                ),
                GlobalAIEngineInfo(
                    engine_type=AIEngineType.BEDROCK,
                    name="Amazon Bedrock",
                    requires_api_key=True,  # Uses AWS credentials
                    default_base_url="https://bedrock-runtime.us-east-1.amazonaws.com",
                    models=AIModelCapabilities(
                        embeddings=["amazon.titan-embed-text-v1", "cohere.embed-english-v3"],
                        completions=["anthropic.claude-3-sonnet", "anthropic.claude-3-haiku", "amazon.titan-text-express-v1", "meta.llama3-70b-instruct-v1"]
                    )
                ),
                # --- Tier 2: Multi-Provider Gateways ---
                GlobalAIEngineInfo(
                    engine_type=AIEngineType.OPENROUTER,
                    name="OpenRouter",
                    requires_api_key=True,
                    default_base_url="https://openrouter.ai/api/v1",
                    models=AIModelCapabilities(
                        embeddings=[],  # Varies by provider
                        completions=["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "google/gemini-pro-1.5", "meta-llama/llama-3.1-405b-instruct"]
                    )
                ),
                GlobalAIEngineInfo(
                    engine_type=AIEngineType.TOGETHER,
                    name="Together AI",
                    requires_api_key=True,
                    default_base_url="https://api.together.xyz/v1",
                    models=AIModelCapabilities(
                        embeddings=["togethercomputer/m2-bert-80M-8k-retrieval", "BAAI/bge-large-en-v1.5"],
                        completions=["meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo", "mistralai/Mixtral-8x22B-Instruct-v0.1", "Qwen/Qwen2-72B-Instruct"]
                    )
                ),
                GlobalAIEngineInfo(
                    engine_type=AIEngineType.HUGGINGFACE,
                    name="Hugging Face",
                    requires_api_key=True,
                    default_base_url="https://api-inference.huggingface.co",
                    models=AIModelCapabilities(
                        embeddings=["sentence-transformers/all-MiniLM-L6-v2", "BAAI/bge-base-en-v1.5"],
                        completions=["meta-llama/Meta-Llama-3-70B-Instruct", "mistralai/Mixtral-8x7B-Instruct-v0.1", "bigcode/starcoder2-15b"]
                    )
                ),
                # --- Tier 3: Local/Self-Hosted ---
                GlobalAIEngineInfo(
                    engine_type=AIEngineType.OLLAMA,
                    name="Ollama",
                    requires_api_key=False,
                    default_base_url="http://localhost:11434",
                    models=AIModelCapabilities(
                        embeddings=["nomic-embed-text", "mxbai-embed-large", "all-minilm"],
                        completions=["llama3.1", "llama3", "mistral", "codellama", "qwen2"]
                    )
                ),
                GlobalAIEngineInfo(
                    engine_type=AIEngineType.VLLM,
                    name="vLLM",
                    requires_api_key=False,
                    default_base_url="http://localhost:8000/v1",
                    models=AIModelCapabilities(
                        embeddings=["configured-at-deployment"],
                        completions=["configured-at-deployment"]
                    )
                ),
                # --- Tier 4: Universal Gateway ---
                GlobalAIEngineInfo(
                    engine_type=AIEngineType.LITELLM,
                    name="LiteLLM (100+ Providers)",
                    requires_api_key=True,
                    default_base_url="http://localhost:4000",
                    models=AIModelCapabilities(
                        embeddings=["configured-at-runtime"],
                        completions=["configured-at-runtime"]
                    )
                )
            ]
        )

    # -------------------------------------------------------------------------
    # Prompts
    # -------------------------------------------------------------------------

    def create_prompt(self, prompt_create) -> "Prompt":
        """Create a new prompt from a PromptCreate request and store it."""
        from app.models import Prompt
        now = datetime.utcnow().isoformat() + "Z"
        prompt = Prompt(
            prompt_id=str(uuid.uuid4()),
            name=prompt_create.name,
            template=prompt_create.template,
            ai_engine=prompt_create.ai_engine,
            model=prompt_create.model,
            parameters=prompt_create.parameters,
            data_id=prompt_create.data_id,
            user=config.DEFAULT_USER_ID,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self.store_prompt(prompt)
        return prompt

    def store_prompt(self, prompt: Prompt) -> None:
        """Store a prompt template in Postgres or the blob store."""
        self._check_ai_enabled()
        if prompt.data_id:
            blob_path = f"{prompt.data_id}/prompts/{prompt.prompt_id}.json"
        else:
            blob_path = f"{prompt.user}/global_prompts/{prompt.prompt_id}.json"
        self.prompts_store.write(
            blob_path,
            json.dumps(prompt.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

    def get_prompt(self, prompt_id: str, data_id: Optional[str] = None, user: str = config.DEFAULT_USER_ID) -> Prompt:
        """Get a prompt by ID."""
        self._check_ai_enabled()
        if data_id:
            blob_path = f"{data_id}/prompts/{prompt_id}.json"
            try:
                content = self.prompts_store.read(blob_path)
                return Prompt(**json.loads(content))
            except FileNotFoundError:
                pass

        # Try user's global prompt
        blob_path = f"{user}/global_prompts/{prompt_id}.json"
        try:
            content = self.prompts_store.read(blob_path)
            return Prompt(**json.loads(content))
        except FileNotFoundError:
            raise FileNotFoundError(f"Prompt not found: {prompt_id}")

    def list_prompts(self, user: str, data_id: Optional[str] = None) -> List[Prompt]:
        """List prompts for a user, optionally scoped to a data item."""
        self._check_ai_enabled()
        prompts = []
        if data_id:
            prefix = f"{data_id}/prompts/"
        else:
            prefix = f"{user}/global_prompts/"

        blob_infos = self.prompts_store.list_blobs(prefix=prefix)
        for info in blob_infos:
            if info.name.endswith(".json"):
                try:
                    content = self.prompts_store.read(info.name)
                    prompts.append(Prompt(**json.loads(content)))
                except Exception as e:
                    logger.warning("Failed to load prompt", extra={"blob": info.name, "error": str(e)})
                    _storage_errors_counter.add(1, {"operation": "list_prompts", "error": type(e).__name__})
                    continue

        prompts.sort(key=lambda x: x.updated_at, reverse=True)
        return prompts

    def delete_prompt(self, prompt_id: str, data_id: Optional[str] = None, user: str = config.DEFAULT_USER_ID) -> None:
        """Delete a prompt."""
        self._check_ai_enabled()
        if data_id:
            blob_path = f"{data_id}/prompts/{prompt_id}.json"
        else:
            blob_path = f"{user}/global_prompts/{prompt_id}.json"
        self.prompts_store.delete(blob_path)

    # -------------------------------------------------------------------------
    # Skills
    # -------------------------------------------------------------------------

    def store_skill(self, skill: Skill) -> None:
        """Store an AI agent skill in Postgres or the blob store."""
        self._check_ai_enabled()
        if skill.data_id:
            blob_path = f"{skill.data_id}/skills/{skill.skill_id}.json"
        else:
            blob_path = f"{skill.user}/global_skills/{skill.skill_id}.json"
        self.skills_store.write(
            blob_path,
            json.dumps(skill.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

    def create_skill(self, skill_create: SkillCreate, user: str = None) -> Skill:
        """Create a new skill from a SkillCreate request."""
        self._check_ai_enabled()
        user = user or config.DEFAULT_USER_ID
        now = datetime.utcnow().isoformat() + "Z"
        skill = Skill(
            skill_id=str(uuid.uuid4()),
            name=skill_create.name,
            description=skill_create.description,
            content=skill_create.content,
            tags=skill_create.tags,
            data_id=skill_create.data_id,
            user=user,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self.store_skill(skill)
        return skill

    def get_skill(self, skill_id: str, data_id: Optional[str] = None, user: str = None) -> Skill:
        """Get a skill by ID."""
        self._check_ai_enabled()
        user = user or config.DEFAULT_USER_ID

        # Try data-specific skill first
        if data_id:
            blob_path = f"{data_id}/skills/{skill_id}.json"
            try:
                content = self.skills_store.read(blob_path)
                return Skill(**json.loads(content))
            except FileNotFoundError:
                pass

        # Try user's global skill
        blob_path = f"{user}/global_skills/{skill_id}.json"
        try:
            content = self.skills_store.read(blob_path)
            return Skill(**json.loads(content))
        except FileNotFoundError:
            raise FileNotFoundError(f"Skill not found: {skill_id}")

    def list_skills(self, user: str = None, data_id: Optional[str] = None, tag: Optional[str] = None) -> List[Skill]:
        """List skills, optionally filtered by user, data item, or tag."""
        self._check_ai_enabled()
        user = user or config.DEFAULT_USER_ID
        skills = []
        if data_id:
            prefix = f"{data_id}/skills/"
        else:
            prefix = f"{user}/global_skills/"

        blob_infos = self.skills_store.list_blobs(prefix=prefix)
        for info in blob_infos:
            if info.name.endswith(".json"):
                try:
                    content = self.skills_store.read(info.name)
                    skill = Skill(**json.loads(content))
                    if tag and tag not in skill.tags:
                        continue
                    skills.append(skill)
                except Exception as e:
                    logger.warning("Failed to load skill", extra={"blob": info.name, "error": str(e)})
                    _storage_errors_counter.add(1, {"operation": "list_skills", "error": type(e).__name__})
                    continue

        skills.sort(key=lambda x: x.updated_at, reverse=True)
        return skills

    def update_skill(self, skill_id: str, skill_update: SkillUpdate, data_id: Optional[str] = None, user: str = None) -> Skill:
        """Update an existing skill."""
        self._check_ai_enabled()
        user = user or config.DEFAULT_USER_ID
        skill = self.get_skill(skill_id, data_id=data_id, user=user)

        update_data = skill_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(skill, field, value)

        skill.version += 1
        skill.updated_at = datetime.utcnow().isoformat() + "Z"
        self.store_skill(skill)
        return skill

    def delete_skill(self, skill_id: str, data_id: Optional[str] = None, user: str = None) -> bool:
        """Delete a skill. Returns True if it existed."""
        self._check_ai_enabled()
        user = user or config.DEFAULT_USER_ID
        if data_id:
            blob_path = f"{data_id}/skills/{skill_id}.json"
        else:
            blob_path = f"{user}/global_skills/{skill_id}.json"

        existed = self.skills_store.exists(blob_path)
        self.skills_store.delete(blob_path)
        return existed

    # =========================================================================
    # Agent Config CRUD (configurable pipeline prompts & skills)
    # =========================================================================

    def _agent_config_path(self, config_id: str, user_id: Optional[str]) -> str:
        """Blob path for an agent config."""
        scope = user_id if user_id else "system"
        return f"{_AGENT_CONFIGS_PREFIX}{scope}/{config_id}.json"

    def create_agent_config(self, create: AgentConfigCreate, user: str = None) -> AgentConfig:
        """Create a new agent config."""
        self._check_ai_enabled()
        from ulid import ULID
        now = datetime.utcnow().isoformat() + "Z"
        cfg = AgentConfig(
            config_id=f"acfg_{ULID()}",
            agent_type=create.agent_type,
            intro=create.intro,
            system_prompt=create.system_prompt,
            output_schema=create.output_schema,
            skills=create.skills,
            model_tier=create.model_tier,
            parameters=create.parameters,
            user_id=create.user_id,
            version=1,
            created_at=now,
            updated_at=now,
        )
        blob_path = self._agent_config_path(cfg.config_id, cfg.user_id)
        self.prompts_store.write(
            blob_path,
            json.dumps(cfg.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        return cfg

    def get_agent_config(self, config_id: str, user_id: Optional[str] = None) -> AgentConfig:
        """Get an agent config by ID."""
        self._check_ai_enabled()
        # Try user-scoped path first, then system
        for uid in ([user_id, None] if user_id else [None]):
            blob_path = self._agent_config_path(config_id, uid)
            try:
                content = self.prompts_store.read(blob_path)
                return AgentConfig(**json.loads(content))
            except FileNotFoundError:
                continue
        raise FileNotFoundError(f"AgentConfig not found: {config_id}")

    def update_agent_config(self, config_id: str, updates: AgentConfigUpdate, user_id: Optional[str] = None) -> AgentConfig:
        """Update an existing agent config."""
        self._check_ai_enabled()
        cfg = self.get_agent_config(config_id, user_id)
        update_data = updates.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(cfg, field, value)
        cfg.version += 1
        cfg.updated_at = datetime.utcnow().isoformat() + "Z"
        blob_path = self._agent_config_path(cfg.config_id, cfg.user_id)
        self.prompts_store.write(
            blob_path,
            json.dumps(cfg.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        return cfg

    def delete_agent_config(self, config_id: str, user_id: Optional[str] = None) -> bool:
        """Delete an agent config. Returns True if it existed."""
        self._check_ai_enabled()
        for uid in ([user_id, None] if user_id else [None]):
            blob_path = self._agent_config_path(config_id, uid)
            if self.prompts_store.exists(blob_path):
                self.prompts_store.delete(blob_path)
                return True
        return False

    def list_agent_configs(self, user_id: Optional[str] = None, agent_type: Optional[str] = None) -> List[AgentConfig]:
        """List agent configs, optionally filtered by user and/or agent_type."""
        self._check_ai_enabled()
        configs: List[AgentConfig] = []
        # Scan both system and user-scoped configs
        prefixes = [f"{_AGENT_CONFIGS_PREFIX}system/"]
        if user_id:
            prefixes.append(f"{_AGENT_CONFIGS_PREFIX}{user_id}/")
        for prefix in prefixes:
            for info in self.prompts_store.list_blobs(prefix=prefix):
                if not info.name.endswith(".json"):
                    continue
                try:
                    content = self.prompts_store.read(info.name)
                    cfg = AgentConfig(**json.loads(content))
                    if agent_type and cfg.agent_type != agent_type:
                        continue
                    configs.append(cfg)
                except Exception as e:
                    logger.warning("Failed to load agent config %s: %s", info.name, e)
                    continue
        configs.sort(key=lambda c: c.updated_at, reverse=True)
        return configs

    def resolve_agent_config(self, agent_type: str, user_id: Optional[str] = None) -> Optional[AgentConfig]:
        """Resolve the best agent config for a given agent_type.

        Priority: user override > system default. Returns None if no config exists.
        """
        self._check_ai_enabled()
        # Check user-specific config first
        if user_id:
            for info in self.prompts_store.list_blobs(prefix=f"{_AGENT_CONFIGS_PREFIX}{user_id}/"):
                if not info.name.endswith(".json"):
                    continue
                try:
                    content = self.prompts_store.read(info.name)
                    cfg = AgentConfig(**json.loads(content))
                    if cfg.agent_type == agent_type:
                        return cfg
                except Exception:
                    continue
        # Fall back to system default
        for info in self.prompts_store.list_blobs(prefix=f"{_AGENT_CONFIGS_PREFIX}system/"):
            if not info.name.endswith(".json"):
                continue
            try:
                content = self.prompts_store.read(info.name)
                cfg = AgentConfig(**json.loads(content))
                if cfg.agent_type == agent_type:
                    return cfg
            except Exception:
                continue
        return None

    def list_all_prompts(self) -> List[Prompt]:
        """List every prompt from the prompts blob store (for dump endpoint)."""
        self._check_ai_enabled()
        if not self.prompts_store:
            return []
        out: List[Prompt] = []
        for info in self.prompts_store.list_blobs():
            if not info.name.endswith(".json") or info.name.startswith(_ANALYSIS_TEMPLATES_PREFIX):
                continue
            try:
                content = self.prompts_store.read(info.name)
                out.append(Prompt(**json.loads(content)))
            except Exception as e:
                logger.warning("Failed to load prompt %s: %s", info.name, e)
                continue
        out.sort(key=lambda x: x.updated_at or "", reverse=True)
        return out

    def list_all_skills(self) -> List[Skill]:
        """List every skill from the skills blob store (for dump endpoint)."""
        self._check_ai_enabled()
        if not self.skills_store:
            return []
        out: List[Skill] = []
        for info in self.skills_store.list_blobs():
            if not info.name.endswith(".json"):
                continue
            try:
                content = self.skills_store.read(info.name)
                out.append(Skill(**json.loads(content)))
            except Exception as e:
                logger.warning("Failed to load skill %s: %s", info.name, e)
                continue
        out.sort(key=lambda x: x.updated_at or "", reverse=True)
        return out

    # -------------------------------------------------------------------------
    # Public LLMs (user-scoped API key storage for Gemini/OpenAI/etc.)
    # -------------------------------------------------------------------------

    _PUBLIC_LLMS_PREFIX = "public_llms/"

    def create_public_llm(
        self,
        provider: str,
        model_id: str,
        display_name: str,
        api_key_encrypted: Optional[str],
        user_id: str,
        api_base_url: Optional[str] = None,
        max_tokens_default: Optional[int] = None,
        temperature_default: Optional[float] = None,
    ) -> dict:
        """Create a new public LLM configuration in the user blob store."""
        self._check_user_management_enabled()
        if not self.user_store:
            raise RuntimeError("User store not configured")
        existing = self.list_public_llms(user_id=user_id, include_deleted=False)
        for e in existing:
            if provider == "custom":
                if e.get("provider") == "custom" and (e.get("api_base_url") or "").strip() == (api_base_url or "").strip():
                    raise ValueError(f"Public LLM entry already exists for {api_base_url}")
            elif e.get("provider") == provider and e.get("model_id") == model_id:
                raise ValueError(f"Public LLM entry already exists for {provider}/{model_id}")
        now = datetime.utcnow().isoformat()
        llm_id = str(uuid.uuid4())
        rec = {
            "id": llm_id,
            "provider": provider,
            "model_id": model_id,
            "display_name": display_name,
            "api_key_encrypted": api_key_encrypted,
            "api_base_url": api_base_url,
            "user_id": user_id,
            "max_tokens_default": max_tokens_default,
            "temperature_default": temperature_default,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        blob_path = f"users/{user_id}/{self._PUBLIC_LLMS_PREFIX}{llm_id}.json"
        self.user_store.write(
            blob_path,
            json.dumps(rec, indent=2).encode("utf-8"),
            "application/json",
        )
        return {k: v for k, v in rec.items() if k != "api_key_encrypted"}

    def list_public_llms(self, user_id: str, include_deleted: bool = False) -> List[dict]:
        """List public LLM configurations for a user."""
        self._check_user_management_enabled()
        if not self.user_store:
            return []
        out: List[dict] = []
        prefix = f"users/{user_id}/{self._PUBLIC_LLMS_PREFIX}"
        for info in self.user_store.list_blobs(prefix=prefix):
            if not info.name.endswith(".json"):
                continue
            try:
                content = self.user_store.read(info.name)
                rec = json.loads(content)
                if not include_deleted and rec.get("deleted_at"):
                    continue
                out.append(self._public_llm_record_to_response(rec, include_key=False))
            except Exception as e:
                logger.warning("Failed to load public LLM %s: %s", info.name, e)
                continue
        out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return out

    def get_public_llm(self, llm_id: str, user_id: str, include_key: bool = False) -> Optional[dict]:
        """Get a public LLM by ID (with user check)."""
        self._check_user_management_enabled()
        if not self.user_store:
            return None
        blob_path = f"users/{user_id}/{self._PUBLIC_LLMS_PREFIX}{llm_id}.json"
        try:
            content = self.user_store.read(blob_path)
            rec = json.loads(content)
            if rec.get("deleted_at"):
                return None
            return self._public_llm_record_to_response(rec, include_key=include_key)
        except FileNotFoundError:
            return None

    def _public_llm_record_to_response(self, rec: dict, include_key: bool = False) -> dict:
        """Convert stored record to API response dict."""
        result = {
            "id": rec.get("id"),
            "provider": rec.get("provider"),
            "model_id": rec.get("model_id"),
            "display_name": rec.get("display_name"),
            "has_api_key": bool(rec.get("api_key_encrypted")),
            "api_base_url": rec.get("api_base_url"),
            "user_id": rec.get("user_id"),
            "max_tokens_default": rec.get("max_tokens_default"),
            "temperature_default": rec.get("temperature_default"),
            "created_at": rec.get("created_at"),
            "updated_at": rec.get("updated_at"),
            "deleted_at": rec.get("deleted_at"),
        }
        if include_key:
            result["api_key_encrypted"] = rec.get("api_key_encrypted")
        return result

    def update_public_llm(
        self,
        llm_id: str,
        user_id: str,
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        display_name: Optional[str] = None,
        api_key_encrypted: Optional[str] = None,
        api_base_url: Optional[str] = None,
        max_tokens_default: Optional[int] = None,
        temperature_default: Optional[float] = None,
    ) -> Optional[dict]:
        """Update a public LLM configuration."""
        self._check_user_management_enabled()
        rec = self.get_public_llm(llm_id, user_id, include_key=True)
        if not rec:
            return None
        blob_path = f"users/{user_id}/{self._PUBLIC_LLMS_PREFIX}{llm_id}.json"
        try:
            content = self.user_store.read(blob_path)
            data = json.loads(content)
        except FileNotFoundError:
            return None
        if provider is not None:
            data["provider"] = provider
        if model_id is not None:
            data["model_id"] = model_id
        if display_name is not None:
            data["display_name"] = display_name
        if api_key_encrypted is not None:
            data["api_key_encrypted"] = api_key_encrypted
        if api_base_url is not None:
            data["api_base_url"] = api_base_url
        if max_tokens_default is not None:
            data["max_tokens_default"] = max_tokens_default
        if temperature_default is not None:
            data["temperature_default"] = temperature_default
        data["updated_at"] = datetime.utcnow().isoformat()
        self.user_store.write(
            blob_path,
            json.dumps(data, indent=2).encode("utf-8"),
            "application/json",
        )
        return self._public_llm_record_to_response(data, include_key=False)

    def delete_public_llm(self, llm_id: str, user_id: str) -> bool:
        """Soft delete a public LLM configuration."""
        self._check_user_management_enabled()
        blob_path = f"users/{user_id}/{self._PUBLIC_LLMS_PREFIX}{llm_id}.json"
        try:
            content = self.user_store.read(blob_path)
            data = json.loads(content)
        except FileNotFoundError:
            return False
        if data.get("deleted_at"):
            return False
        data["deleted_at"] = data["updated_at"] = datetime.utcnow().isoformat()
        self.user_store.write(
            blob_path,
            json.dumps(data, indent=2).encode("utf-8"),
            "application/json",
        )
        return True

    # -------------------------------------------------------------------------
    # Analysis templates (options when user analyzes data)
    # -------------------------------------------------------------------------

    def list_analysis_templates(self, data_type: Optional[str] = None) -> List[AnalysisTemplate]:
        """List analysis templates, optionally filtered by data_type (e.g. csv, json). Stored in blob store."""
        self._check_ai_enabled()
        if not self.prompts_store:
            return []
        out: List[AnalysisTemplate] = []
        for info in self.prompts_store.list_blobs(prefix=_ANALYSIS_TEMPLATES_PREFIX):
            if not info.name.endswith(".json"):
                continue
            try:
                content = self.prompts_store.read(info.name)
                t = AnalysisTemplate(**json.loads(content))
                if data_type and "any" not in t.data_types and data_type not in t.data_types:
                    continue
                out.append(t)
            except Exception as e:
                logger.warning("Failed to load analysis template %s: %s", info.name, e)
                continue
        out.sort(key=lambda x: (x.sort_order, x.updated_at or ""))
        return out

    def get_analysis_template(self, template_id: str) -> AnalysisTemplate:
        """Get a single analysis template by ID."""
        self._check_ai_enabled()
        if not self.prompts_store:
            raise FileNotFoundError("Analysis templates store not configured")
        blob_path = f"{_ANALYSIS_TEMPLATES_PREFIX}{template_id}.json"
        try:
            content = self.prompts_store.read(blob_path)
            return AnalysisTemplate(**json.loads(content))
        except FileNotFoundError:
            raise FileNotFoundError(f"Analysis template not found: {template_id}")

    def create_analysis_template(self, create: AnalysisTemplateCreate) -> AnalysisTemplate:
        """Create a new analysis template."""
        self._check_ai_enabled()
        if not self.prompts_store:
            raise RuntimeError("Analysis templates store not configured (PROMPTS_BUCKET)")
        now = datetime.utcnow().isoformat() + "Z"
        template = AnalysisTemplate(
            template_id=str(uuid.uuid4()),
            data_types=create.data_types,
            kind=create.kind,
            name=create.name,
            description=create.description,
            prompt_id=create.prompt_id,
            skill_id=create.skill_id,
            template_text=create.template_text,
            sort_order=create.sort_order,
            created_at=now,
            updated_at=now,
        )
        blob_path = f"{_ANALYSIS_TEMPLATES_PREFIX}{template.template_id}.json"
        self.prompts_store.write(
            blob_path,
            json.dumps(template.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        return template

    def update_analysis_template(self, template_id: str, update: AnalysisTemplateUpdate) -> AnalysisTemplate:
        """Update an existing analysis template."""
        self._check_ai_enabled()
        template = self.get_analysis_template(template_id)
        data = update.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(template, k, v)
        template.updated_at = datetime.utcnow().isoformat() + "Z"
        blob_path = f"{_ANALYSIS_TEMPLATES_PREFIX}{template_id}.json"
        self.prompts_store.write(
            blob_path,
            json.dumps(template.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        return template

    def delete_analysis_template(self, template_id: str) -> bool:
        """Delete an analysis template. Returns True if it existed."""
        self._check_ai_enabled()
        if not self.prompts_store:
            return False
        blob_path = f"{_ANALYSIS_TEMPLATES_PREFIX}{template_id}.json"
        try:
            existed = self.prompts_store.exists(blob_path)
            self.prompts_store.delete(blob_path)
            return existed
        except Exception:
            return False

    def seed_analysis_templates(self) -> int:
        """Insert default analysis templates into blob store. Idempotent. Returns count inserted."""
        self._check_ai_enabled()
        if not self.prompts_store:
            return 0
        from app.analysis_templates_seed import (
            _DEFAULT_ANALYSIS_TEMPLATES,
            _HIGH_IMPACT_ANALYSIS_TEMPLATES,
            _HIGH_IMPACT_ANALYSIS_SKILLS,
        )
        defaults = (
            _DEFAULT_ANALYSIS_TEMPLATES
            + _HIGH_IMPACT_ANALYSIS_TEMPLATES
            + _HIGH_IMPACT_ANALYSIS_SKILLS
        )
        now = datetime.utcnow().isoformat() + "Z"
        inserted = 0
        for t in defaults:
            template_id = t["template_id"]
            blob_path = f"{_ANALYSIS_TEMPLATES_PREFIX}{template_id}.json"
            if self.prompts_store.exists(blob_path):
                continue
            rec = {
                "template_id": template_id,
                "data_types": t["data_types"],
                "kind": t["kind"],
                "name": t["name"],
                "description": t.get("description", ""),
                "prompt_id": t.get("prompt_id"),
                "skill_id": t.get("skill_id"),
                "template_text": t.get("template_text"),
                "sort_order": t["sort_order"],
                "created_at": now,
                "updated_at": now,
            }
            self.prompts_store.write(
                blob_path,
                json.dumps(rec, indent=2).encode("utf-8"),
                "application/json",
            )
            inserted += 1
        return inserted

    # -------------------------------------------------------------------------
    # Embeddings
    # -------------------------------------------------------------------------

    def store_embedding(self, embedding: Embedding) -> None:
        """Store an embedding (low-level) in the blob store.

        Path: ``{user_id}/{data_id}/{version_label}/embeddings/{id}.json``
        Requires embedding.user_id and embedding.version_label to be set.
        """
        self._check_ai_enabled()
        if not embedding.user_id or not embedding.version_label:
            raise ValueError(f"Embedding {embedding.embedding_id} is missing user_id or version_label — cannot determine storage path")
        blob_path = self._embedding_blob_path(
            embedding.user_id, embedding.data_id,
            embedding.version_label, embedding.embedding_id,
        )
        self.embeddings_store.write(
            blob_path,
            json.dumps(embedding.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

    def get_embeddings(
        self,
        data_id: str,
        user_id: str = "",
        version_label: Optional[str] = None,
    ) -> List[Embedding]:
        """Get all embeddings for a data item (sorted by chunk_index).

        Path: ``{user_id}/{data_id}/{version_label}/embeddings/``
        When version_label is omitted, scans all versions under ``{user_id}/{data_id}/``.
        """
        self._check_ai_enabled()
        if not user_id:
            return []

        embeddings: List[Embedding] = []
        prefix = self._embedding_prefix(user_id, data_id, version_label)
        for info in self.embeddings_store.list_blobs(prefix=prefix):
            if not info.name.endswith(".json") or "/embeddings/" not in info.name:
                continue
            try:
                content = self.embeddings_store.read(info.name)
                embeddings.append(Embedding(**json.loads(content)))
            except Exception as e:
                logger.warning("Failed to load embedding", extra={"blob": info.name, "error": str(e)})
                _storage_errors_counter.add(1, {"operation": "get_embeddings", "error": type(e).__name__})

        return sorted(embeddings, key=lambda x: x.chunk_index)

    def get_embedding_summary(
        self,
        data_id: str,
        user_id: str = "",
        version_label: Optional[str] = None,
    ) -> Optional[EmbeddingSummary]:
        """Get summary of embeddings for a data item."""
        self._check_ai_enabled()
        embeddings = self.get_embeddings(data_id, user_id=user_id, version_label=version_label)

        if not embeddings:
            return None

        first = embeddings[0]
        return EmbeddingSummary(
            data_id=data_id,
            data_version=first.data_version,
            embeddings_count=len(embeddings),
            ai_engine=first.ai_engine,
            model=first.model,
            dimensions=first.dimensions,
            created_at=first.created_at,
            user_id=first.user_id,
            version_label=first.version_label,
        )

    def delete_embeddings(
        self,
        data_id: str,
        user_id: str = "",
        version_label: Optional[str] = None,
    ) -> None:
        """Delete all embeddings for a data item.

        Path: ``{user_id}/{data_id}/{version_label}/embeddings/``
        """
        self._check_ai_enabled()
        if not user_id:
            return
        prefix = self._embedding_prefix(user_id, data_id, version_label)
        for info in self.embeddings_store.list_blobs(prefix=prefix):
            if "/embeddings/" in info.name:
                self.embeddings_store.delete(info.name)

    # -------------------------------------------------------------------------
    # High-level embedding CRUD (called by the embeddings router)
    # -------------------------------------------------------------------------

    def create_embedding(self, embedding_create: EmbeddingCreate) -> Embedding:
        """Generate embeddings for a data item and persist them.

        Prefers Phase 1 parsed artifacts (JSON chunks with page metadata, else
        markdown) over raw/viewpoint text. Chunks are embedded via the configured
        AI endpoint and stored under
        ``{user_id}/{data_id}/{version_label}/embeddings/``.
        """
        self._check_ai_enabled()

        owner = (embedding_create.user_id or "").strip() or config.DEFAULT_USER_ID

        raw = self.get_raw_data(embedding_create.data_id, user_id=owner)
        if raw is None:
            raise FileNotFoundError(f"Data not found: {embedding_create.data_id}")
        content_bytes, content_type = raw

        chunk_size = embedding_create.chunk_size
        chunk_overlap = embedding_create.chunk_overlap
        chunk_specs: List[Dict[str, Any]] = []
        from_parsed = False

        # 1) Prefer parsed JSON chunks (page / section metadata)
        try:
            parsed_json = self.get_parsed_artifact(
                embedding_create.data_id, user_id=owner, fmt="json",
            )
        except Exception:
            parsed_json = None
        if parsed_json:
            try:
                document = json.loads(parsed_json[0].decode("utf-8"))
                if isinstance(document, dict):
                    chunk_specs = _chunk_specs_from_parsed_json(
                        document, chunk_size, chunk_overlap,
                    )
                    from_parsed = bool(chunk_specs)
            except Exception as exc:
                logger.warning(
                    "Failed to load parsed JSON chunks for %s: %s",
                    embedding_create.data_id, exc,
                )

        # 2) Else parsed markdown
        if not chunk_specs:
            try:
                parsed_md = self.get_parsed_artifact(
                    embedding_create.data_id, user_id=owner, fmt="markdown",
                )
            except Exception:
                parsed_md = None
            if parsed_md:
                md_text = parsed_md[0].decode("utf-8", errors="replace")
                if md_text.strip():
                    chunk_specs = _chunk_specs_from_text(
                        md_text, chunk_size, chunk_overlap, embedding_kind="body",
                    )
                    from_parsed = bool(chunk_specs)

        # 3) Else existing text / non-text viewpoint fallbacks
        if not chunk_specs:
            is_text = isinstance(content_type, str) and (
                content_type.startswith("text/")
                or content_type in (
                    "application/json", "application/xml", "application/javascript",
                )
            )
            existing = self.list_viewpoints(
                data_id=embedding_create.data_id, user_id=owner,
            )
            vp_text = (
                existing[0].output_content
                if existing and existing[0].output_content
                else ""
            )
            if is_text:
                raw_text = content_bytes.decode("utf-8", errors="replace")
                if vp_text:
                    text_content = f"{vp_text}\n\n---\n\n{raw_text}"
                else:
                    text_content = raw_text
                chunk_specs = _chunk_specs_from_text(
                    text_content, chunk_size, chunk_overlap, embedding_kind="body",
                )
            else:
                if vp_text:
                    text_content = vp_text
                else:
                    text_content = content_bytes.decode("utf-8", errors="replace")
                chunk_specs = _chunk_specs_from_text(
                    text_content, chunk_size, chunk_overlap, embedding_kind="body",
                )

        # Prepend viewpoint to first body chunk when using parsed artifacts
        if from_parsed and chunk_specs:
            existing = self.list_viewpoints(
                data_id=embedding_create.data_id, user_id=owner,
            )
            if existing and existing[0].output_content:
                vp = existing[0].output_content.strip()
                if vp:
                    first = chunk_specs[0]
                    first["text"] = f"{vp}\n\n---\n\n{first['text']}"

        if not chunk_specs:
            chunk_specs = [{
                "text": "(empty)",
                "page": None,
                "section_path": None,
                "element_type": None,
                "embedding_kind": "body",
            }]

        metadata = self.get_metadata(embedding_create.data_id, user_id=owner)
        data_version = metadata.current_version if metadata else 1
        version_label = (metadata.data_version_label or "") if metadata else ""
        if not version_label:
            version_label = _make_version_label()

        # Prefer explicit EmbeddingCreate scoping, else stamp from data metadata / user defaults
        emb_org_id = embedding_create.org_id or (getattr(metadata, "org_id", None) if metadata else None)
        emb_project_id = embedding_create.project_id or (
            getattr(metadata, "project_id", None) if metadata else None
        )
        if not emb_project_id:
            try:
                user = self.get_user(owner)
                if user:
                    emb_org_id = emb_org_id or getattr(user, "default_org_id", None)
                    emb_project_id = emb_project_id or getattr(user, "default_project_id", None)
            except Exception:
                pass

        engine_type, model, api_key = self._resolve_embedding_engine(
            embedding_create.engine_id
        )
        model = embedding_create.model or model

        chunk_texts = [c["text"] for c in chunk_specs]
        vectors = _generate_embeddings(chunk_texts, engine_type, model, api_key)

        try:
            emb_tokens = sum(len(c.split()) for c in chunk_texts)
            storage_engine_label = _normalize_storage_engine(engine_type)
            self.record_token_usage(TokenUsageRecord(
                user_id=owner,
                prompt_tokens=emb_tokens,
                completion_tokens=0,
                total_tokens=emb_tokens,
                model=f"embedding/{model}",
                agent_type="embedding",
            ))
        except Exception:
            pass

        # Write new embeddings first, then delete prior rows for this version.
        # Avoids delete-then-fail leaving the item with no embeddings.
        old_ids: set[str] = set()
        try:
            for old in self.get_embeddings(
                embedding_create.data_id,
                user_id=owner,
                version_label=version_label,
            ):
                if old.embedding_id:
                    old_ids.add(old.embedding_id)
        except Exception as exc:
            logger.warning(
                "list prior embeddings before recreate failed for %s: %s",
                embedding_create.data_id, exc,
            )

        now = datetime.utcnow().isoformat() + "Z"
        # Map internal engine types to AIEngineType enum values for storage.
        # MODEL_SERVER_URL resolves as "local"; map to a valid AIEngineType.
        storage_engine = _normalize_storage_engine(engine_type)
        sig = AISignature(
            ai_engine=storage_engine,
            model_name=model,
            generated_at=now,
            key_mode=AIKeyMode.SYSTEM if not embedding_create.engine_id else AIKeyMode.CUSTOM,
        )

        stored: List[Embedding] = []
        try:
            for idx, (spec, vector) in enumerate(zip(chunk_specs, vectors)):
                emb = Embedding(
                    embedding_id=str(uuid.uuid4()),
                    data_id=embedding_create.data_id,
                    data_version=data_version,
                    ai_engine=storage_engine,
                    model=model,
                    vector=vector,
                    dimensions=len(vector),
                    chunk_index=idx,
                    chunk_text=spec["text"],
                    created_at=now,
                    version=1,
                    user_id=owner,
                    version_label=version_label,
                    ai_signature=sig,
                    org_id=emb_org_id,
                    project_id=emb_project_id,
                    page=spec.get("page"),
                    section_path=spec.get("section_path"),
                    element_type=spec.get("element_type"),
                    embedding_kind=spec.get("embedding_kind") or "body",
                )
                self.store_embedding(emb)
                stored.append(emb)
        except Exception:
            for emb in stored:
                try:
                    self.delete_embedding(emb.embedding_id, user_id=owner)
                except Exception as cleanup_exc:
                    logger.warning(
                        "rollback of partial embedding rewrite failed for %s: %s",
                        emb.embedding_id, cleanup_exc,
                    )
            raise

        for old_id in old_ids:
            try:
                self.delete_embedding(old_id, user_id=owner)
            except Exception as exc:
                logger.warning(
                    "delete stale embedding %s after rewrite failed: %s",
                    old_id, exc,
                )

        logger.info(
            "Embeddings created",
            extra={
                "data_id": embedding_create.data_id,
                "user_id": owner,
                "version_label": version_label,
                "chunks": len(stored),
                "model": model,
                "from_parsed": from_parsed,
            },
        )
        return stored[0]

    def list_embeddings(
        self,
        data_id: Optional[str] = None,
        user_id: str = "",
    ) -> List[EmbeddingSummary]:
        """Return embedding summaries (without full vector data).

        Filters by data_id when provided; scopes to user_id when given.
        """
        self._check_ai_enabled()
        if data_id:
            embeddings = self.get_embeddings(data_id, user_id=user_id)
            if not embeddings:
                return []
            first = embeddings[0]
            return [
                EmbeddingSummary(
                    data_id=data_id,
                    data_version=first.data_version,
                    embeddings_count=len(embeddings),
                    ai_engine=first.ai_engine,
                    model=first.model,
                    dimensions=first.dimensions,
                    created_at=first.created_at,
                    user_id=first.user_id,
                    version_label=first.version_label,
                )
            ]

        # Global listing — scan all blob prefixes
        summaries: List[EmbeddingSummary] = []
        all_items = self.list_all_metadata(user_id=user_id if user_id else None)
        for item in all_items:
            owner = getattr(item, "owner_user_id", user_id) or user_id
            summary = self.get_embedding_summary(item.data_id, user_id=owner)
            if summary:
                summaries.append(summary)
        return summaries

    def get_embedding(self, embedding_id: str, user_id: str = "") -> Optional[Embedding]:
        """Return a full Embedding by its ID, including vector data."""
        self._check_ai_enabled()
        all_items = self.list_all_metadata(user_id=user_id if user_id else None)
        for item in all_items:
            owner = getattr(item, "owner_user_id", user_id) or user_id
            for emb in self.get_embeddings(item.data_id, user_id=owner):
                if emb.embedding_id == embedding_id:
                    return emb
        return None

    def delete_embedding(self, embedding_id: str, user_id: str = "") -> bool:
        """Delete a single embedding by ID. Returns True if it existed. Uses multitenant path only."""
        self._check_ai_enabled()
        if not user_id:
            return False
        all_items = self.list_all_metadata(user_id=user_id)
        for item in all_items:
            owner = getattr(item, "owner_user_id", user_id) or user_id
            prefix = f"{owner}/{item.data_id}/"
            for info in self.embeddings_store.list_blobs(prefix=prefix):
                if not info.name.endswith(".json") or "/embeddings/" not in info.name:
                    continue
                try:
                    content = self.embeddings_store.read(info.name)
                    emb = json.loads(content)
                    if emb.get("embedding_id") == embedding_id:
                        self.embeddings_store.delete(info.name)
                        return True
                except Exception:
                    continue
        return False

    def similarity_search(
        self, query_vector: List[float], limit: int = 5, user_id: str = "",
        memory_id: str = "",
        project_id: str = "",
    ) -> List[dict]:
        """Return embedding hit dicts via cosine similarity over blob-store embeddings.

        Each dict has ``embedding_id``, ``data_id``, ``chunk_text``, ``similarity``,
        and optional ``page`` when present on the stored embedding.
        When ``project_id`` is set, only embeddings stamped with that project match
        (embeddings with no project_id are excluded).
        """
        self._check_ai_enabled()
        if not self.embeddings_store:
            return []

        def _cosine(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            mag_a = math.sqrt(sum(x * x for x in a))
            mag_b = math.sqrt(sum(x * x for x in b))
            if mag_a == 0 or mag_b == 0:
                return 0.0
            return dot / (mag_a * mag_b)

        scored: List[dict] = []
        for info in self.embeddings_store.list_blobs():
            if not info.name.endswith(".json") or "/embeddings/" not in info.name:
                continue
            try:
                content = self.embeddings_store.read(info.name)
                emb = json.loads(content)
                if user_id and emb.get("user_id") and emb.get("user_id") != user_id:
                    continue
                if project_id and emb.get("project_id") != project_id:
                    continue
                vec = emb.get("vector")
                if not vec:
                    continue
                if isinstance(vec, str):
                    vec = json.loads(vec)
                sim = _cosine(query_vector, vec)
                hit = {
                    "embedding_id": emb.get("embedding_id", ""),
                    "data_id": emb.get("data_id", ""),
                    "chunk_text": emb.get("chunk_text", ""),
                    "similarity": sim,
                }
                if emb.get("page") is not None:
                    hit["page"] = emb.get("page")
                scored.append(hit)
            except Exception:
                continue
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:limit]

    def hybrid_search(
        self, query_vector: List[float], query_text: str, limit: int = 5,
        user_id: str = "", memory_id: str = "",
        vector_weight: float = 0.5, fts_weight: float = 0.5,
        project_id: str = "",
    ) -> List[dict]:
        """Hybrid cosine + BM25 search.

        Default implementation falls back to similarity_search with empty FTS fields.
        """
        results = self.similarity_search(
            query_vector, limit=limit, user_id=user_id, memory_id=memory_id,
            project_id=project_id,
        )
        return [
            {
                "embedding_id": r.get("embedding_id", ""),
                "data_id": r.get("data_id", ""),
                "chunk_text": r.get("chunk_text", ""),
                "similarity": r.get("similarity", 0.0),
                "fts_rank": None,
                "rrf_score": None,
                "search_type": "vector",
                **({"page": r["page"]} if r.get("page") is not None else {}),
            }
            for r in results
        ]

    def fts_search(
        self, query_text: str, limit: int = 5, user_id: str = "", memory_id: str = "",
        project_id: str = "",
    ) -> List[dict]:
        """Full-text search. Default returns empty list (no FTS index in base storage)."""
        return []

    # -------------------------------------------------------------------------
    # AI helper: resolve embedding engine + generate vectors
    # -------------------------------------------------------------------------

    def _resolve_embedding_engine(
        self, engine_id: Optional[str]
    ) -> Tuple[str, str, str]:
        """Return (engine_type, model, api_key) for embedding generation.

        Priority:
        1. If engine_id is supplied and found in the user's engine configs, use it.
        2. Local Ollama when OLLAMA_TIER is on, or when lean has a host URL and
           no cloud/Gemini key (lean overlays often force host.docker.internal).
        3. Ollama Cloud (if OLLAMA_CLOUD_API_KEY is set).
        4. Fall back to the system Gemini key.
        """
        if engine_id:
            try:
                cfg = self.get_engine_config(config.DEFAULT_USER_ID, engine_id)
                if cfg and cfg.is_enabled:
                    api_key = ""
                    if cfg.api_key_encrypted:
                        try:
                            from app.ai_crypto import decrypt_api_key
                            api_key = decrypt_api_key(cfg.api_key_encrypted)
                        except Exception:
                            pass
                    model = (
                        cfg.available_models.embeddings[0]
                        if cfg.available_models.embeddings
                        else "text-embedding-004"
                    )
                    return str(cfg.engine_type), model, api_key
            except Exception:
                pass

        # Local Ollama (in-cluster or host). Skip the k8s default URL when
        # OLLAMA_TIER=false. When lean forces host.docker.internal but a cloud
        # key is present, prefer cloud so the documented cloud-only path works.
        _default_local = "http://ollama.webhook-pipeline.svc.cluster.local:11434"
        has_cloud = bool(
            config.OLLAMA_CLOUD_API_KEY or config.SYSTEM_GEMINI_API_KEY
        )
        use_local = bool(config.OLLAMA_LOCAL_API_BASE) and (
            config.OLLAMA_TIER
            or (
                config.OLLAMA_LOCAL_API_BASE.rstrip("/") != _default_local.rstrip("/")
                and not has_cloud
            )
        )
        if use_local:
            return (
                "ollama_local",
                config.OLLAMA_LOCAL_MODEL_EMBEDDING,
                "",
            )

        # Ollama Cloud primary (when key is set)
        if config.OLLAMA_CLOUD_API_KEY:
            return (
                "ollama_cloud",
                config.OLLAMA_CLOUD_MODEL_EMBEDDING,
                config.OLLAMA_CLOUD_API_KEY,
            )

        # System Gemini fallback
        if config.SYSTEM_GEMINI_API_KEY:
            return (
                AIEngineType.GEMINI.value,
                config.SYSTEM_GEMINI_MODEL_EMBEDDING,
                config.SYSTEM_GEMINI_API_KEY,
            )

        raise RuntimeError(
            "No embedding engine configured. Set OLLAMA_LOCAL_API_BASE, "
            "OLLAMA_CLOUD_API_KEY, SYSTEM_GEMINI_API_KEY, or configure a custom engine."
        )

    # -------------------------------------------------------------------------
    # Viewpoints
    # -------------------------------------------------------------------------

    def store_viewpoint(self, viewpoint: Viewpoint) -> None:
        """Store a viewpoint (low-level) in the blob store.

        Path: ``{user_id}/{data_id}/{version_label}/viewpoints/{id}.json``
        Requires viewpoint.user_id and viewpoint.version_label to be set.
        """
        self._check_ai_enabled()
        if not viewpoint.user_id or not viewpoint.version_label:
            raise ValueError(f"Viewpoint {viewpoint.viewpoint_id} is missing user_id or version_label — cannot determine storage path")
        blob_path = self._viewpoint_blob_path(
            viewpoint.user_id, viewpoint.data_id,
            viewpoint.version_label, viewpoint.viewpoint_id,
        )
        self.viewpoints_store.write(
            blob_path,
            json.dumps(viewpoint.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

    def get_viewpoint(
        self,
        viewpoint_id_or_data_id: str,
        viewpoint_id: Optional[str] = None,
        user_id: str = "",
    ) -> Optional[Viewpoint]:
        """Get a viewpoint by ID.

        Accepts two call styles:
        - ``get_viewpoint(viewpoint_id)``          — router style (single arg)
        - ``get_viewpoint(data_id, viewpoint_id)`` — internal style

        Path: ``{user_id}/{data_id}/{version_label}/viewpoints/{id}.json``
        Scans the user's prefix to find the viewpoint without needing version_label.
        """
        self._check_ai_enabled()
        if viewpoint_id is None:
            return self._scan_blob_viewpoint(viewpoint_id_or_data_id, user_id=user_id)
        else:
            data_id = viewpoint_id_or_data_id
            if not user_id:
                return None
            for info in self.viewpoints_store.list_blobs(prefix=f"{user_id}/{data_id}/"):
                if not info.name.endswith(".json") or "/viewpoints/" not in info.name:
                    continue
                try:
                    content = self.viewpoints_store.read(info.name)
                    vp = Viewpoint(**json.loads(content))
                    if vp.viewpoint_id == viewpoint_id:
                        return vp
                except Exception:
                    continue
            return None

    def _scan_blob_viewpoint(
        self, viewpoint_id: str, user_id: str = ""
    ) -> Optional[Viewpoint]:
        """Scan viewpoints store to find one by viewpoint_id.

        Scoped to ``{user_id}/`` when user_id is provided.
        """
        if not self.viewpoints_store:
            return None

        prefix = f"{user_id}/" if user_id else None
        infos = self.viewpoints_store.list_blobs(prefix=prefix) if prefix else self.viewpoints_store.list_blobs()
        for info in infos:
            if not info.name.endswith(".json") or "/viewpoints/" not in info.name:
                continue
            try:
                content = self.viewpoints_store.read(info.name)
                data = json.loads(content)
                if data.get("viewpoint_id") == viewpoint_id:
                    return Viewpoint(**data)
            except Exception:
                continue
        return None

    def list_viewpoints(
        self,
        data_id: Optional[str] = None,
        user_id: str = "",
        version_label: Optional[str] = None,
    ) -> List[Viewpoint]:
        """List viewpoints, optionally filtered by data_id and/or user_id, newest first.

        Path: ``{user_id}/{data_id}/{version_label}/viewpoints/``
        When version_label is omitted, scans all versions under ``{user_id}/{data_id}/``.
        When data_id is also omitted, scans all of ``{user_id}/``.
        """
        self._check_ai_enabled()

        viewpoints: List[Viewpoint] = []
        if data_id is None:
            prefix = f"{user_id}/" if user_id else None
        else:
            prefix = self._viewpoint_prefix(user_id, data_id, version_label) if user_id else None

        infos = self.viewpoints_store.list_blobs(prefix=prefix) if prefix else self.viewpoints_store.list_blobs()
        for info in infos:
            if not info.name.endswith(".json") or "/viewpoints/" not in info.name:
                continue
            try:
                content = self.viewpoints_store.read(info.name)
                viewpoints.append(Viewpoint(**json.loads(content)))
            except Exception as e:
                logger.warning("Failed to load viewpoint", extra={"blob": info.name, "error": str(e)})
                _storage_errors_counter.add(1, {"operation": "list_viewpoints", "error": type(e).__name__})

        return sorted(viewpoints, key=lambda x: x.updated_at, reverse=True)

    def delete_viewpoint(
        self,
        viewpoint_id_or_data_id: str,
        viewpoint_id: Optional[str] = None,
        user_id: str = "",
    ) -> bool:
        """Delete a viewpoint.

        Accepts two call styles:
        - ``delete_viewpoint(viewpoint_id)``         — router style
        - ``delete_viewpoint(data_id, viewpoint_id)`` — legacy internal style

        """
        self._check_ai_enabled()
        if viewpoint_id is None:
            vid = viewpoint_id_or_data_id
            vp = self._scan_blob_viewpoint(vid, user_id=user_id)
            if vp is None:
                return False
            if not (vp.user_id and vp.version_label):
                return False
            mt_path = self._viewpoint_blob_path(vp.user_id, vp.data_id, vp.version_label, vid)
            try:
                self.viewpoints_store.delete(mt_path)
                return True
            except FileNotFoundError:
                return False
        else:
            data_id = viewpoint_id_or_data_id
            if not user_id:
                return False
            for info in self.viewpoints_store.list_blobs(prefix=f"{user_id}/{data_id}/"):
                if not info.name.endswith(".json") or "/viewpoints/" not in info.name:
                    continue
                try:
                    content = self.viewpoints_store.read(info.name)
                    if json.loads(content).get("viewpoint_id") == viewpoint_id:
                        self.viewpoints_store.delete(info.name)
                        return True
                except Exception:
                    continue
            return False

    # -------------------------------------------------------------------------
    # High-level viewpoint CRUD (called by the viewpoints router)
    # -------------------------------------------------------------------------

    def create_viewpoint(self, viewpoint_create: ViewpointCreate) -> Viewpoint:
        """Generate an AI viewpoint for a data item and persist it.

        Fetches the data content and the requested prompt template, fills the
        template, calls the configured AI completion endpoint, and stores the
        resulting Viewpoint under the multitenant path
        ``{user_id}/{data_id}/{version_label}/viewpoints/``.

        Only one viewpoint per data_id is kept.  If duplicates exist (race
        condition between concurrent requests) the newest is kept and the
        rest are deleted.
        """
        self._check_ai_enabled()

        owner = (viewpoint_create.user_id or "").strip() or config.DEFAULT_USER_ID

        # Return existing viewpoint if one already exists (idempotent)
        existing_vps = self.list_viewpoints(data_id=viewpoint_create.data_id, user_id=owner)
        if existing_vps:
            # Deduplicate: keep the first (newest) and delete the rest
            for dup in existing_vps[1:]:
                try:
                    self.delete_viewpoint(dup.viewpoint_id, user_id=owner)
                    logger.info("Deleted duplicate viewpoint %s for data_id=%s", dup.viewpoint_id, viewpoint_create.data_id)
                except Exception:
                    pass
            logger.info(
                "Viewpoint already exists for data_id=%s, returning existing",
                viewpoint_create.data_id,
            )
            return existing_vps[0]

        raw = self.get_raw_data(viewpoint_create.data_id, user_id=owner)
        if raw is None:
            raise FileNotFoundError(f"Data not found: {viewpoint_create.data_id}")
        content_bytes, content_type = raw

        is_image = isinstance(content_type, str) and content_type.startswith("image/")
        if is_image:
            input_text = f"[Image: {content_type}]"
        else:
            input_text = content_bytes.decode("utf-8", errors="replace")

        metadata = self.get_metadata(viewpoint_create.data_id, user_id=owner)
        data_version = metadata.current_version if metadata else 1
        version_label = (metadata.data_version_label or "") if metadata else ""
        if not version_label:
            version_label = _make_version_label()

        # Resolve engine + model for AI signature.
        # When the caller provides explicit ai_engine / model_name (e.g. the
        # webhook agent passing actual inference provenance), use those instead
        # of re-resolving — this ensures the signature reflects the model that
        # actually ran the inference (Ollama Cloud, Gemini, etc.).
        if viewpoint_create.ai_engine and viewpoint_create.model_name:
            engine_type = viewpoint_create.ai_engine
            model = viewpoint_create.model_name
            api_key = ""  # Not needed — inference already happened
        else:
            engine_type, model, api_key = self._resolve_completion_engine(
                viewpoint_create.engine_id
            )

        if viewpoint_create.output_content:
            # Pre-computed analysis provided — skip LLM call
            output_text = viewpoint_create.output_content
        else:
            # Fetch prompt template
            prompt_template = "(Summarise and analyse the following content.)"
            try:
                prompt = self.get_prompt(viewpoint_create.prompt_id)
                if prompt:
                    prompt_template = prompt.template
            except Exception:
                pass

            # Fill template placeholder
            filled_prompt = prompt_template.replace("{{content}}", input_text)
            if "{{content}}" not in prompt_template:
                filled_prompt = prompt_template + "\n\n" + input_text

            # Call AI completion (pass image data for multimodal support)
            image_kwargs: dict = {}
            if is_image:
                image_kwargs = {"image_bytes": content_bytes, "image_mime_type": content_type}
            output_text = _call_ai_completion(
                prompt=filled_prompt, engine_type=engine_type, model=model, api_key=api_key,
                **image_kwargs,
            )

        now = datetime.utcnow().isoformat() + "Z"
        # MODEL_SERVER_URL resolves as "local"; map to a valid AIEngineType for
        # persistence (same pattern as embedding storage_engine normalization).
        storage_engine = _normalize_storage_engine(engine_type)
        sig = AISignature(
            ai_engine=storage_engine,
            model_name=model,
            generated_at=now,
            key_mode=AIKeyMode.SYSTEM if not viewpoint_create.engine_id else AIKeyMode.CUSTOM,
        )

        viewpoint = Viewpoint(
            viewpoint_id=str(uuid.uuid4()),
            data_id=viewpoint_create.data_id,
            data_version=data_version,
            prompt_id=viewpoint_create.prompt_id,
            user=owner,
            ai_engine=storage_engine,
            model=model,
            input_content=input_text[:2000],  # truncate stored input for space
            output_content=output_text,
            parameters={},
            version=1,
            created_at=now,
            updated_at=now,
            user_id=owner,
            version_label=version_label,
            ai_signature=sig,
        )
        self.store_viewpoint(viewpoint)

        # Post-store dedup: if a concurrent request also stored, keep ours and
        # delete the others so we always end up with exactly one viewpoint.
        all_vps = self.list_viewpoints(data_id=viewpoint_create.data_id, user_id=owner)
        if len(all_vps) > 1:
            for dup in all_vps:
                if dup.viewpoint_id != viewpoint.viewpoint_id:
                    try:
                        self.delete_viewpoint(dup.viewpoint_id, user_id=owner)
                        logger.info("Post-store dedup: deleted viewpoint %s for data_id=%s", dup.viewpoint_id, viewpoint_create.data_id)
                    except Exception:
                        pass

        logger.info(
            "Viewpoint created",
            extra={"data_id": viewpoint_create.data_id, "user_id": owner, "version_label": version_label, "model": model},
        )

        return viewpoint

    def update_viewpoint(
        self,
        viewpoint_id: str,
        viewpoint_update: ViewpointUpdate,
        user_id: str = "",
    ) -> Optional[Viewpoint]:
        """Regenerate a viewpoint with an optionally different engine or prompt.

        Stores the previous version in version_history before updating.
        """
        self._check_ai_enabled()

        viewpoint = self.get_viewpoint(viewpoint_id, user_id=user_id)
        if viewpoint is None:
            return None

        # Resolve engine / prompt overrides
        engine_id = viewpoint_update.engine_id
        prompt_id = viewpoint_update.prompt_id or viewpoint.prompt_id
        engine_type, model, api_key = self._resolve_completion_engine(engine_id)

        # Rebuild prompt
        prompt_template = "(Summarise and analyse the following content.)"
        try:
            prompt = self.get_prompt(prompt_id)
            if prompt:
                prompt_template = prompt.template
        except Exception:
            pass

        filled_prompt = prompt_template.replace("{{content}}", viewpoint.input_content)
        if "{{content}}" not in prompt_template:
            filled_prompt = prompt_template + "\n\n" + viewpoint.input_content

        output_text = _call_ai_completion(
            prompt=filled_prompt, engine_type=engine_type, model=model, api_key=api_key
        )

        # Preserve history
        history = list(viewpoint.version_history or [])
        history.append({
            "version": viewpoint.version,
            "output_content": viewpoint.output_content,
            "updated_at": viewpoint.updated_at,
        })

        now = datetime.utcnow().isoformat() + "Z"
        storage_engine = _normalize_storage_engine(engine_type)
        viewpoint.output_content = output_text
        viewpoint.version += 1
        viewpoint.updated_at = now
        viewpoint.prompt_id = prompt_id
        viewpoint.ai_engine = storage_engine
        viewpoint.model = model
        viewpoint.version_history = history
        viewpoint.ai_signature = AISignature(
            ai_engine=storage_engine,
            model_name=model,
            generated_at=now,
            key_mode=AIKeyMode.SYSTEM if not engine_id else AIKeyMode.CUSTOM,
        )

        self.store_viewpoint(viewpoint)
        return viewpoint

    def _resolve_completion_engine(
        self, engine_id: Optional[str]
    ) -> Tuple[str, str, str]:
        """Return (engine_type, model, api_key) for text completion.

        Priority: user engine config → system Gemini key → model server.
        """
        if engine_id:
            try:
                cfg = self.get_engine_config(config.DEFAULT_USER_ID, engine_id)
                if cfg and cfg.is_enabled:
                    api_key = ""
                    if cfg.api_key_encrypted:
                        try:
                            from app.ai_crypto import decrypt_api_key
                            api_key = decrypt_api_key(cfg.api_key_encrypted)
                        except Exception:
                            pass
                    model = (
                        cfg.available_models.completions[0]
                        if cfg.available_models.completions
                        else "gemini-1.5-flash"
                    )
                    return str(cfg.engine_type), model, api_key
            except Exception:
                pass

        if config.SYSTEM_GEMINI_API_KEY:
            return (
                AIEngineType.GEMINI.value,
                config.SYSTEM_GEMINI_MODEL_COMPLETION,
                config.SYSTEM_GEMINI_API_KEY,
            )

        if config.is_model_server_enabled():
            return (
                "local",
                config.MODEL_SERVER_MODEL,
                "",
            )

        raise RuntimeError(
            "No completion engine configured. Set SYSTEM_GEMINI_API_KEY, "
            "configure a custom engine, or set MODEL_SERVER_URL."
        )

    def list_all_viewpoints_for_user(self, user: str) -> List[Viewpoint]:
        """List all viewpoints created by a user across all data items."""
        self._check_ai_enabled()
        viewpoints = []

        # Get user's timeline to find their data items
        timeline_entries = self.get_timeline(user)
        data_ids = set(entry.data_id for entry in timeline_entries)

        for data_id in data_ids:
            try:
                data_viewpoints = self.list_viewpoints(data_id)
                viewpoints.extend([v for v in data_viewpoints if v.user == user])
            except Exception as e:
                logger.warning("Failed to list viewpoints for data item", extra={"data_id": data_id, "error": str(e)})
                _storage_errors_counter.add(1, {"operation": "list_user_viewpoints", "error": type(e).__name__})
                continue

        viewpoints.sort(key=lambda x: x.updated_at, reverse=True)
        return viewpoints

    # =========================================================================
    # User Management Storage Methods
    # =========================================================================

    _DEFAULT_USERNAME = "demo"

    def ensure_default_user(self) -> None:
        """Create the default user and their default timeline memory if they
        do not already exist.

        The user is created with ``user_id = config.DEFAULT_USER_ID`` (the
        canonical UUID) so that user management profiles and data/memory
        multi-tenancy paths share the same identifier.  The *username* and
        *display_name* are cosmetic labels (e.g. ``"demo"``).

        Called once on startup so the default user is always visible in the
        user management UI and has a timeline memory ready.
        """
        if not config.is_user_management_enabled():
            return

        existing = self.get_user(config.DEFAULT_USER_ID)
        if existing is None:
            logger.info(
                "Creating default user (username=%s, user_id=%s)",
                self._DEFAULT_USERNAME, config.DEFAULT_USER_ID,
            )
            self._create_user_with_id(
                user_id=config.DEFAULT_USER_ID,
                username=self._DEFAULT_USERNAME,
                email=f"{self._DEFAULT_USERNAME}@localhost",
                display_name=self._DEFAULT_USERNAME.capitalize(),
            )

        # Ensure default timeline memory exists
        if config.is_memories_enabled():
            self.get_or_create_default_timeline_memory(config.DEFAULT_USER_ID)

    def _create_user_with_id(
        self, user_id: str, username: str, email: str, display_name: str,
    ) -> User:
        """Create a user with a predetermined user_id (used for the default user)."""
        self._check_user_management_enabled()
        now = datetime.utcnow().isoformat() + "Z"
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            display_name=display_name,
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
            metadata={},
            data_count=0,
            storage_used_bytes=0,
            created_at=now,
            updated_at=now,
            last_active_at=now,
        )
        blob_path = f"users/{user_id}/profile.json"
        self.user_store.write(
            blob_path,
            json.dumps(user.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        index_path = f"index/username/{username}.json"
        self.user_store.write(
            index_path,
            json.dumps({"user_id": user_id}).encode("utf-8"),
            "application/json",
        )
        credentials = UserCredentials(
            user_id=user_id, api_keys=[], created_at=now, updated_at=now,
        )
        creds_path = f"users/{user_id}/credentials.json"
        self.user_store.write(
            creds_path,
            json.dumps(credentials.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        return user

    def create_user(self, user_create: UserCreate) -> User:
        """Create a new user."""
        self._check_user_management_enabled()
        
        # Check if username already exists
        if self._username_exists(user_create.username):
            raise ValueError(f"Username '{user_create.username}' already exists")
        
        now = datetime.utcnow().isoformat() + "Z"
        user_id = user_create.user_id or str(uuid.uuid4())

        user = User(
            user_id=user_id,
            username=user_create.username,
            email=user_create.email,
            display_name=user_create.display_name or user_create.username,
            role=user_create.role,
            status=UserStatus.ACTIVE,
            metadata=user_create.metadata,
            data_count=0,
            storage_used_bytes=0,
            created_at=now,
            updated_at=now,
            last_active_at=now,
            default_org_id=user_create.default_org_id,
            default_project_id=user_create.default_project_id,
        )
        
        # Store user
        blob_path = f"users/{user_id}/profile.json"
        self.user_store.write(
            blob_path,
            json.dumps(user.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

        # Create username -> user_id index for lookups
        index_path = f"index/username/{user_create.username}.json"
        self.user_store.write(
            index_path,
            json.dumps({"user_id": user_id}).encode("utf-8"),
            "application/json",
        )

        # Initialize empty credentials
        credentials = UserCredentials(
            user_id=user_id,
            api_keys=[],
            created_at=now,
            updated_at=now,
        )
        creds_path = f"users/{user_id}/credentials.json"
        self.user_store.write(
            creds_path,
            json.dumps(credentials.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

        return user

    def _username_exists(self, username: str) -> bool:
        """Check if a username already exists."""
        self._check_user_management_enabled()
        index_path = f"index/username/{username}.json"
        return self.user_store.exists(index_path)

    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        self._check_user_management_enabled()
        blob_path = f"users/{user_id}/profile.json"
        try:
            content = self.user_store.read(blob_path)
            return User(**json.loads(content))
        except FileNotFoundError:
            return None

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get a user by username."""
        self._check_user_management_enabled()

        # Look up user_id from index
        index_path = f"index/username/{username}.json"
        try:
            index_content = self.user_store.read(index_path)
            user_id = json.loads(index_content)["user_id"]
            return self.get_user(user_id)
        except FileNotFoundError:
            return None

    def update_user(self, user_id: str, user_update: UserUpdate) -> Optional[User]:
        """Update a user."""
        self._check_user_management_enabled()

        user = self.get_user(user_id)
        if not user:
            return None

        now = datetime.utcnow().isoformat() + "Z"

        # Update fields if provided
        if user_update.username is not None and user_update.username != user.username:
            if self._username_exists(user_update.username):
                raise ValueError(f"Username '{user_update.username}' already exists")
            # Delete old username index, create new one
            old_index = f"index/username/{user.username}.json"
            self.user_store.delete(old_index)
            new_index = f"index/username/{user_update.username}.json"
            self.user_store.write(
                new_index,
                json.dumps({"user_id": user_id}).encode("utf-8"),
                "application/json",
            )
            user.username = user_update.username
        if user_update.email is not None:
            user.email = user_update.email
        if user_update.display_name is not None:
            user.display_name = user_update.display_name
        if user_update.role is not None:
            user.role = user_update.role
        if user_update.status is not None:
            user.status = user_update.status
        if user_update.metadata is not None:
            user.metadata = user_update.metadata

        user.updated_at = now

        # Store updated user
        blob_path = f"users/{user_id}/profile.json"
        self.user_store.write(
            blob_path,
            json.dumps(user.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

        return user

    def delete_user(self, user_id: str) -> bool:
        """Delete a user and all associated data."""
        self._check_user_management_enabled()

        user = self.get_user(user_id)
        if not user:
            return False

        # Delete username index
        index_path = f"index/username/{user.username}.json"
        self.user_store.delete(index_path)

        # Delete all user files
        prefix = f"users/{user_id}/"
        blob_infos = self.user_store.list_blobs(prefix=prefix)
        for info in blob_infos:
            try:
                self.user_store.delete(info.name)
            except Exception:
                pass

        return True

    def list_users(self, limit: int = 50, offset: int = 0) -> Tuple[List[User], int]:
        """List all users with pagination."""
        self._check_user_management_enabled()

        users = []
        prefix = "users/"
        blob_infos = self.user_store.list_blobs(prefix=prefix)

        # Filter to only profile.json files
        profile_infos = [i for i in blob_infos if i.name.endswith("/profile.json")]
        total = len(profile_infos)

        # Sort by name (user_id) for consistent ordering
        profile_infos.sort(key=lambda i: i.name)

        # Apply pagination
        paginated = profile_infos[offset:offset + limit]

        for info in paginated:
            try:
                content = self.user_store.read(info.name)
                users.append(User(**json.loads(content)))
            except Exception as e:
                logger.warning("Failed to load user profile", extra={"blob": info.name, "error": str(e)})
                _storage_errors_counter.add(1, {"operation": "list_users", "error": type(e).__name__})
                continue

        return users, total

    def update_user_activity(self, user_id: str) -> None:
        """Update user's last active timestamp."""
        self._check_user_management_enabled()

        user = self.get_user(user_id)
        if not user:
            return

        now = datetime.utcnow().isoformat() + "Z"
        user.last_active_at = now

        blob_path = f"users/{user_id}/profile.json"
        self.user_store.write(
            blob_path,
            json.dumps(user.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

    def update_user_stats(self, user_id: str, data_count_delta: int = 0, storage_delta: int = 0) -> None:
        """Update user statistics (data count, storage used)."""
        self._check_user_management_enabled()

        user = self.get_user(user_id)
        if not user:
            return

        user.data_count = max(0, user.data_count + data_count_delta)
        user.storage_used_bytes = max(0, user.storage_used_bytes + storage_delta)
        user.updated_at = datetime.utcnow().isoformat() + "Z"

        blob_path = f"users/{user_id}/profile.json"
        self.user_store.write(
            blob_path,
            json.dumps(user.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

    # -------------------------------------------------------------------------
    # API Key Management
    # -------------------------------------------------------------------------

    def get_user_credentials(self, user_id: str) -> Optional[UserCredentials]:
        """Get user credentials."""
        self._check_user_management_enabled()

        creds_path = f"users/{user_id}/credentials.json"
        try:
            content = self.user_store.read(creds_path)
            return UserCredentials(**json.loads(content))
        except FileNotFoundError:
            return None

    def create_api_key(self, user_id: str, key_create: APIKeyCreate) -> Optional[APIKeyResponse]:
        """Create an API key for a user."""
        self._check_user_management_enabled()
        import secrets
        import hashlib
        
        credentials = self.get_user_credentials(user_id)
        if not credentials:
            return None
        
        now = datetime.utcnow().isoformat() + "Z"
        key_id = str(uuid.uuid4())[:8]  # Short key ID
        
        # Generate a secure API key
        raw_key = f"md_{secrets.token_urlsafe(32)}"  # md_ prefix for mem-dog
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Calculate expiry if specified
        expires_at = None
        if key_create.expires_in_days:
            from datetime import timedelta
            expiry_date = datetime.utcnow() + timedelta(days=key_create.expires_in_days)
            expires_at = expiry_date.isoformat() + "Z"
        
        # Add to credentials
        credentials.api_keys.append({
            "key_id": key_id,
            "key_hash": key_hash,
            "name": key_create.name,
            "created_at": now,
            "expires_at": expires_at
        })
        credentials.updated_at = now
        
        # Store updated credentials
        creds_path = f"users/{user_id}/credentials.json"
        self.user_store.write(
            creds_path,
            json.dumps(credentials.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

        return APIKeyResponse(
            key_id=key_id,
            name=key_create.name,
            key=raw_key,  # Only returned once!
            created_at=now,
            expires_at=expires_at,
        )

    def list_api_keys(self, user_id: str) -> List[APIKeyResponse]:
        """List API keys for a user (without the actual keys)."""
        self._check_user_management_enabled()
        
        credentials = self.get_user_credentials(user_id)
        if not credentials:
            return []
        
        return [
            APIKeyResponse(
                key_id=k["key_id"],
                name=k["name"],
                key=None,  # Never return the actual key
                created_at=k["created_at"],
                expires_at=k.get("expires_at")
            )
            for k in credentials.api_keys
        ]

    def delete_api_key(self, user_id: str, key_id: str) -> bool:
        """Delete an API key."""
        self._check_user_management_enabled()
        
        credentials = self.get_user_credentials(user_id)
        if not credentials:
            return False
        
        original_count = len(credentials.api_keys)
        credentials.api_keys = [k for k in credentials.api_keys if k["key_id"] != key_id]
        
        if len(credentials.api_keys) == original_count:
            return False  # Key not found
        
        credentials.updated_at = datetime.utcnow().isoformat() + "Z"
        
        # Store updated credentials
        creds_path = f"users/{user_id}/credentials.json"
        self.user_store.write(
            creds_path,
            json.dumps(credentials.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )

        return True

    def validate_api_key(self, api_key: str) -> Optional[str]:
        """Validate an API key and return the user_id if valid."""
        self._check_user_management_enabled()
        import hashlib
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Search through all users (in production, use an index)
        users, _ = self.list_users(limit=1000, offset=0)
        
        for user in users:
            credentials = self.get_user_credentials(user.user_id)
            if not credentials:
                continue
            
            for key in credentials.api_keys:
                if key["key_hash"] == key_hash:
                    # Check expiry
                    if key.get("expires_at"):
                        expiry = datetime.fromisoformat(key["expires_at"].rstrip("Z"))
                        if datetime.utcnow() > expiry:
                            return None  # Expired
                    return user.user_id
        
        return None

    # (Legacy session methods removed -- use Memory API with type=session)


    # =========================================================================
    # Statistics Methods
    # =========================================================================

    def _compute_data_stats(self) -> DataStats:
        """Scan metadata store and compute data statistics."""
        total_items = 0
        total_size = 0
        content_types: Dict[str, int] = {}
        tag_counts: Dict[str, int] = {}
        total_versions = 0

        items = self.list_all_metadata()
        for item in items:
            total_items += 1
            # Get full metadata to access versions list
            meta = self.get_metadata(item.data_id)
            if meta:
                versions = meta.versions or []
                total_versions += len(versions)
                if versions:
                    total_size += versions[-1].size
                    ct = versions[-1].content_type
                    content_types[ct] = content_types.get(ct, 0) + 1
            for tag in item.tags or []:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        top_tags = dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20])
        avg_versions = (total_versions / total_items) if total_items > 0 else 0.0

        return DataStats(
            total_items=total_items,
            total_size_bytes=total_size,
            items_by_content_type=content_types,
            items_by_tag=top_tags,
            avg_versions_per_item=round(avg_versions, 2),
        )

    def _compute_memory_stats(self) -> MemoryStats:
        """Compute memory statistics from the blob store."""
        if not config.is_memories_enabled():
            return MemoryStats()
        total = 0
        by_type: Dict[str, int] = {}
        by_duration: Dict[str, int] = {}
        active_sessions = 0
        total_data_items = 0

        blob_infos = self.memories_store.list_blobs()
        for info in blob_infos:
            if not info.name.endswith("/meta.json"):
                continue
            try:
                content = self.memories_store.read(info.name)
                mem = json.loads(content)
                total += 1
                mt = mem.get("memory_type", "unknown")
                by_type[mt] = by_type.get(mt, 0) + 1
                dur = mem.get("duration", "unknown")
                by_duration[dur] = by_duration.get(dur, 0) + 1
                total_data_items += len(mem.get("data_ids", []))
                if mt == "session" and mem.get("active", False):
                    active_sessions += 1
            except Exception as e:
                logger.warning("Stats: failed to read memory blob", extra={"blob": info.name, "error": str(e)})
                continue

        return MemoryStats(
            total_memories=total,
            by_type=by_type,
            by_duration=by_duration,
            active_sessions=active_sessions,
            avg_data_per_memory=round(total_data_items / total, 2) if total > 0 else 0.0,
        )

    def _compute_embedding_stats(self) -> EmbeddingStats:
        """Scan embeddings store and compute embedding statistics."""
        if not config.is_ai_enabled():
            return EmbeddingStats()

        total = 0
        engines: Dict[str, int] = {}
        models: Dict[str, int] = {}
        total_dims = 0

        if self.embeddings_store:
            blob_infos = self.embeddings_store.list_blobs()
            for info in blob_infos:
                if not info.name.endswith(".json"):
                    continue
                try:
                    content = self.embeddings_store.read(info.name)
                    emb = json.loads(content)
                    total += 1
                    eng = emb.get("ai_engine", "unknown")
                    engines[eng] = engines.get(eng, 0) + 1
                    mdl = emb.get("model", "unknown")
                    models[mdl] = models.get(mdl, 0) + 1
                    total_dims += emb.get("dimensions", 0)
                except Exception as e:
                    logger.warning("Stats: failed to read embedding blob", extra={"blob": info.name, "error": str(e)})
                    continue

        return EmbeddingStats(
            total_embeddings=total,
            by_engine=engines,
            by_model=models,
            avg_dimensions=round(total_dims / total, 2) if total > 0 else 0.0,
        )

    def _compute_viewpoint_stats(self) -> ViewpointStats:
        """Scan viewpoints store and compute viewpoint statistics."""
        if not config.is_ai_enabled():
            return ViewpointStats()

        total = 0
        engines: Dict[str, int] = {}
        models: Dict[str, int] = {}
        prompts: Dict[str, int] = {}

        if self.viewpoints_store:
            blob_infos = self.viewpoints_store.list_blobs()
            for info in blob_infos:
                if not info.name.endswith(".json"):
                    continue
                try:
                    content = self.viewpoints_store.read(info.name)
                    vp = json.loads(content)
                    total += 1
                    eng = vp.get("ai_engine", "unknown")
                    engines[eng] = engines.get(eng, 0) + 1
                    mdl = vp.get("model", "unknown")
                    models[mdl] = models.get(mdl, 0) + 1
                    pid = vp.get("prompt_id", "unknown")
                    prompts[pid] = prompts.get(pid, 0) + 1
                except Exception as e:
                    logger.warning("Stats: failed to read viewpoint blob", extra={"blob": info.name, "error": str(e)})
                    continue

        return ViewpointStats(
            total_viewpoints=total,
            by_engine=engines,
            by_model=models,
            by_prompt=prompts,
        )

    def _compute_user_summary_stats(self) -> UserSummaryStats:
        """Scan users store and compute user summary statistics."""
        if not config.is_user_management_enabled():
            return UserSummaryStats()

        total = 0
        roles: Dict[str, int] = {}
        statuses: Dict[str, int] = {}
        total_data_count = 0
        total_storage = 0

        blob_infos = self.user_store.list_blobs(prefix="users/")
        for info in blob_infos:
            if not info.name.endswith("/profile.json"):
                continue
            try:
                content = self.user_store.read(info.name)
                user = json.loads(content)
                total += 1
                role = user.get("role", "user")
                roles[role] = roles.get(role, 0) + 1
                status = user.get("status", "active")
                statuses[status] = statuses.get(status, 0) + 1
                total_data_count += user.get("data_count", 0)
                total_storage += user.get("storage_used_bytes", 0)
            except Exception as e:
                logger.warning("Stats: failed to read user blob", extra={"blob": info.name, "error": str(e)})
                continue

        return UserSummaryStats(
            total_users=total,
            by_role=roles,
            by_status=statuses,
            avg_data_per_user=round(total_data_count / total, 2) if total > 0 else 0.0,
            avg_storage_per_user=round(total_storage / total, 2) if total > 0 else 0.0,
        )

    def compute_global_stats(self) -> GlobalStats:
        """Compute and cache global statistics by scanning all buckets."""
        self._check_stats_enabled()
        with tracer.start_as_current_span("compute_global_stats"):
            stats = GlobalStats(
                data=self._compute_data_stats(),
                memories=self._compute_memory_stats(),
                embeddings=self._compute_embedding_stats(),
                viewpoints=self._compute_viewpoint_stats(),
                users=self._compute_user_summary_stats(),
                computed_at=datetime.utcnow().isoformat() + "Z",
            )

            if self.stats_store:
                self.stats_store.write(
                    "global/stats.json",
                    json.dumps(stats.model_dump(), indent=2).encode("utf-8"),
                    "application/json",
                )
            logger.info("Global stats computed and cached")
            return stats

    def get_global_stats(self) -> Optional[GlobalStats]:
        """Read cached global statistics from the stats store."""
        self._check_stats_enabled()
        with tracer.start_as_current_span("get_global_stats"):
            try:
                content = self.stats_store.read("global/stats.json")
                return GlobalStats(**json.loads(content))
            except FileNotFoundError:
                return None

    def _compute_user_embedding_stats(
        self, user_id: str, user_data_ids: set,
    ) -> "PerUserEmbeddingStats":
        """Compute embedding stats by scanning blob store. Overridden by SupabaseStorage."""
        embedding_stats = PerUserEmbeddingStats()
        if config.is_ai_enabled() and self.embeddings_store:
            for data_id in user_data_ids:
                emb_prefix = f"{user_id}/{data_id}/"
                emb_infos = self.embeddings_store.list_blobs(prefix=emb_prefix)
                for info in emb_infos:
                    if not info.name.endswith(".json") or "/embeddings/" not in info.name:
                        continue
                    try:
                        content = self.embeddings_store.read(info.name)
                        emb = json.loads(content)
                        embedding_stats.total_embeddings += 1
                        eng = emb.get("ai_engine", "unknown")
                        embedding_stats.by_engine[eng] = embedding_stats.by_engine.get(eng, 0) + 1
                        mdl = emb.get("model", "unknown")
                        embedding_stats.by_model[mdl] = embedding_stats.by_model.get(mdl, 0) + 1
                    except Exception:
                        continue
        return embedding_stats

    def compute_user_stats(self, user_id: str) -> PerUserStats:
        """Compute and cache statistics for a single user."""
        self._check_stats_enabled()
        with tracer.start_as_current_span("compute_user_stats") as span:
            span.set_attribute("user_id", user_id)

            # Data stats for this user (scan memories to find their data_ids)
            data_stats = PerUserDataStats()
            user_data_ids: set = set()
            now = datetime.utcnow()
            seven_days_ago = now - timedelta(days=7)

            user_memories, _ = self.list_memories(user_id=user_id, limit=10000)
            for mem in user_memories:
                user_data_ids.update(mem.data_ids)
                # Count recent activity from memory data entries
                entries = self.get_memory_data_entries(mem.memory_id, user_id)
                for entry in entries:
                    try:
                        entry_time = datetime.fromisoformat(entry.associated_at.rstrip("Z"))
                        if entry_time >= seven_days_ago:
                            data_stats.recent_activity_7d += 1
                    except Exception:
                        continue

            for data_id in user_data_ids:
                meta = self.get_metadata(data_id, user_id)
                if meta:
                    data_stats.total_items += 1
                    if meta.versions:
                        latest = meta.versions[-1]
                        data_stats.total_size_bytes += latest.size
                        ct = latest.content_type
                        data_stats.items_by_content_type[ct] = data_stats.items_by_content_type.get(ct, 0) + 1
                    for tag in meta.tags or []:
                        data_stats.items_by_tag[tag] = data_stats.items_by_tag.get(tag, 0) + 1

            # Memory stats for this user
            memory_stats = PerUserMemoryStats()
            for mem in user_memories:
                mt = mem.memory_type.value if hasattr(mem.memory_type, 'value') else str(mem.memory_type)
                memory_stats.by_type[mt] = memory_stats.by_type.get(mt, 0) + 1
                memory_stats.total_memories += 1
                if mem.memory_type == MemoryType.SESSION and mem.active:
                    memory_stats.active_sessions += 1

            # Embedding stats for this user's data
            embedding_stats = self._compute_user_embedding_stats(user_id, user_data_ids)

            # Viewpoint stats for this user's data (multitenant path only)
            viewpoint_stats = PerUserViewpointStats()
            if config.is_ai_enabled() and self.viewpoints_store:
                for data_id in user_data_ids:
                    vp_prefix = f"{user_id}/{data_id}/"
                    vp_infos = self.viewpoints_store.list_blobs(prefix=vp_prefix)
                    for info in vp_infos:
                        if not info.name.endswith(".json") or "/viewpoints/" not in info.name:
                            continue
                        try:
                            content = self.viewpoints_store.read(info.name)
                            vp = json.loads(content)
                            if vp.get("user_id") != user_id:
                                continue
                            viewpoint_stats.total_viewpoints += 1
                            eng = vp.get("ai_engine", "unknown")
                            viewpoint_stats.by_engine[eng] = viewpoint_stats.by_engine.get(eng, 0) + 1
                            mdl = vp.get("model", "unknown")
                            viewpoint_stats.by_model[mdl] = viewpoint_stats.by_model.get(mdl, 0) + 1
                        except Exception:
                            continue

            # Token usage stats (accumulated separately via record_token_usage)
            token_stats = self.get_token_usage(user_id)

            per_user = PerUserStats(
                user_id=user_id,
                data=data_stats,
                memories=memory_stats,
                embeddings=embedding_stats,
                viewpoints=viewpoint_stats,
                tokens=token_stats,
                computed_at=datetime.utcnow().isoformat() + "Z",
            )

            if self.stats_store:
                self.stats_store.write(
                    f"users/{user_id}/stats.json",
                    json.dumps(per_user.model_dump(), indent=2).encode("utf-8"),
                    "application/json",
                )
            logger.info("Per-user stats computed", extra={"user_id": user_id})
            return per_user

    def get_user_stats(self, user_id: str) -> Optional[PerUserStats]:
        """Read cached per-user statistics from the stats store."""
        self._check_stats_enabled()
        with tracer.start_as_current_span("get_user_stats") as span:
            span.set_attribute("user_id", user_id)
            try:
                content = self.stats_store.read(f"users/{user_id}/stats.json")
                return PerUserStats(**json.loads(content))
            except FileNotFoundError:
                return None

    # ------------------------------------------------------------------
    # Live agent-type counts (backed by agent_type_counts.json)
    # ------------------------------------------------------------------

    def get_agent_type_counts(self) -> "AgentTypeStats":
        """Read the live agent-type count file.

        Returns an empty :class:`AgentTypeStats` if the file has not been
        created yet (no data has been written by the webhook pipeline).
        """
        from app.models import AgentTypeStats  # local import to avoid circular
        self._check_stats_enabled()
        try:
            content = self.stats_store.read("agent_type_counts.json")
            data = json.loads(content)
            return AgentTypeStats(**data)
        except FileNotFoundError:
            return AgentTypeStats()
        except Exception as exc:
            logger.warning("Failed to read agent_type_counts.json: %s", exc)
            return AgentTypeStats()

    def update_agent_type_count(self, agent_type: str, delta: int) -> "AgentTypeStats":
        """Atomically increment or decrement the count for *agent_type*.

        Uses a read-modify-write pattern.  The count is clamped at 0
        (it will never go negative).

        Args:
            agent_type: The agent type string (e.g. ``"pdf"``).
            delta: ``+1`` to increment, ``-1`` to decrement.

        Returns:
            The updated :class:`AgentTypeStats`.
        """
        from datetime import timezone, datetime
        from app.models import AgentTypeStats  # local import to avoid circular
        self._check_stats_enabled()
        current = self.get_agent_type_counts()
        counts = dict(current.counts)
        existing = counts.get(agent_type, 0)
        counts[agent_type] = max(0, existing + delta)

        updated = AgentTypeStats(
            counts=counts,
            total=sum(counts.values()),
            last_updated=datetime.now(timezone.utc).isoformat(),
        )
        self.stats_store.write(
            "agent_type_counts.json",
            json.dumps(updated.model_dump()).encode(),
        )
        return updated

    # ------------------------------------------------------------------
    # Token usage tracking (backed by users/{user_id}/token_usage.json)
    # ------------------------------------------------------------------

    def record_token_usage(self, record: TokenUsageRecord) -> PerUserTokenStats:
        """Accumulate a token usage event into the per-user token stats file.

        Uses a read-modify-write pattern against
        ``users/{user_id}/token_usage.json`` in the stats store.
        """
        self._check_stats_enabled()
        path = f"users/{record.user_id}/token_usage.json"
        try:
            content = self.stats_store.read(path)
            data = json.loads(content)
            stats = PerUserTokenStats(**data)
        except (FileNotFoundError, Exception):
            stats = PerUserTokenStats()

        stats.total_prompt_tokens += record.prompt_tokens
        stats.total_completion_tokens += record.completion_tokens
        stats.total_tokens += record.total_tokens
        stats.total_requests += 1
        if record.model:
            stats.by_model[record.model] = stats.by_model.get(record.model, 0) + record.total_tokens
        if record.agent_type:
            stats.by_agent_type[record.agent_type] = stats.by_agent_type.get(record.agent_type, 0) + record.total_tokens

        self.stats_store.write(
            path,
            json.dumps(stats.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        return stats

    def get_token_usage(self, user_id: str) -> PerUserTokenStats:
        """Read accumulated token usage stats for a user."""
        self._check_stats_enabled()
        try:
            content = self.stats_store.read(f"users/{user_id}/token_usage.json")
            return PerUserTokenStats(**json.loads(content))
        except (FileNotFoundError, Exception):
            return PerUserTokenStats()

    def delete_token_usage(self, user_id: str) -> PerUserTokenStats:
        """Delete accumulated token usage stats for a user, returning empty stats."""
        self._check_stats_enabled()
        path = f"users/{user_id}/token_usage.json"
        try:
            self.stats_store.delete(path)
        except (FileNotFoundError, Exception):
            pass
        return PerUserTokenStats()

    def refresh_all_stats(self) -> GlobalStats:
        """Recompute global stats and per-user stats for all known users."""
        self._check_stats_enabled()
        with tracer.start_as_current_span("refresh_all_stats"):
            global_stats = self.compute_global_stats()

            if config.is_user_management_enabled():
                blob_infos = self.user_store.list_blobs(prefix="users/")
                for info in blob_infos:
                    if info.name.endswith("/profile.json"):
                        try:
                            content = self.user_store.read(info.name)
                            user = json.loads(content)
                            uid = user.get("user_id")
                            if uid:
                                self.compute_user_stats(uid)
                        except Exception as e:
                            logger.warning("Stats: failed to refresh user stats", extra={"blob": info.name, "error": str(e)})
                            continue

            logger.info("All stats refreshed")
            return global_stats

    # =========================================================================
    # Channel identity correlation (channel <-> user_id)
    # =========================================================================

    _CHANNEL_IDENTITIES_PREFIX = "_channel_identities/"

    def _channel_identity_safe_segment(self, raw: str) -> str:
        """Make a path segment safe (no slashes)."""
        return (raw or "unknown").replace("/", "_").replace("\\", "_").strip()

    def channel_identity_create(self, payload: ChannelIdentityCreate) -> ChannelIdentityRecord:
        """Create or upsert a channel identity binding. Writes by_channel and by_user blobs."""
        store = self.meta_store
        prefix = self._CHANNEL_IDENTITIES_PREFIX
        ct_safe = self._channel_identity_safe_segment(payload.channel_type)
        id_safe = self._channel_identity_safe_segment(payload.channel_unique_id)
        added_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        record = ChannelIdentityRecord(
            channel_type=payload.channel_type,
            channel_unique_id=payload.channel_unique_id,
            user_id=payload.user_id,
            display_name=payload.display_name,
            added_at=added_at,
            metadata=payload.metadata or {},
        )
        body = record.model_dump_json()
        path_by_channel = f"{prefix}by_channel/{ct_safe}/{id_safe}"
        path_by_user = f"{prefix}by_user/{payload.user_id}/{ct_safe}/{id_safe}"
        store.write(path_by_channel, body.encode("utf-8"), "application/json")
        store.write(path_by_user, body.encode("utf-8"), "application/json")
        return record

    def channel_identity_get_by_channel(
        self, channel_type: str, channel_unique_id: str
    ) -> Optional[ChannelIdentityRecord]:
        """Return the channel identity for this channel, or None."""
        store = self.meta_store
        prefix = self._CHANNEL_IDENTITIES_PREFIX
        ct_safe = self._channel_identity_safe_segment(channel_type)
        id_safe = self._channel_identity_safe_segment(channel_unique_id)
        path = f"{prefix}by_channel/{ct_safe}/{id_safe}"
        try:
            raw = store.read(path)
        except FileNotFoundError:
            return None
        data = json.loads(raw.decode("utf-8"))
        return ChannelIdentityRecord(**data)

    def channel_identity_list_by_user(self, user_id: str) -> ChannelIdentityListResponse:
        """List all channel identities linked to this user."""
        store = self.meta_store
        prefix = self._CHANNEL_IDENTITIES_PREFIX
        list_prefix = f"{prefix}by_user/{user_id}/"
        identities: List[ChannelIdentityRecord] = []
        try:
            blobs = store.list_blobs(prefix=list_prefix)
        except Exception:
            return ChannelIdentityListResponse(user_id=user_id, identities=[])
        for info in blobs:
            try:
                raw = store.read(info.name)
                data = json.loads(raw.decode("utf-8"))
                identities.append(ChannelIdentityRecord(**data))
            except Exception:
                continue
        return ChannelIdentityListResponse(user_id=user_id, identities=identities)

    def channel_identity_update(
        self, channel_type: str, channel_unique_id: str, display_name: Optional[str], metadata: Optional[Dict]
    ) -> Optional[ChannelIdentityRecord]:
        """Update display_name and/or metadata. Returns updated record or None if not found."""
        record = self.channel_identity_get_by_channel(channel_type, channel_unique_id)
        if not record:
            return None
        if display_name is not None:
            record.display_name = display_name
        if metadata is not None:
            record.metadata = metadata
        store = self.meta_store
        prefix = self._CHANNEL_IDENTITIES_PREFIX
        ct_safe = self._channel_identity_safe_segment(channel_type)
        id_safe = self._channel_identity_safe_segment(channel_unique_id)
        body = record.model_dump_json()
        store.write(f"{prefix}by_channel/{ct_safe}/{id_safe}", body.encode("utf-8"), "application/json")
        store.write(f"{prefix}by_user/{record.user_id}/{ct_safe}/{id_safe}", body.encode("utf-8"), "application/json")
        return record

    def channel_identity_delete(self, channel_type: str, channel_unique_id: str) -> bool:
        """Remove the binding. Returns True if deleted, False if not found."""
        record = self.channel_identity_get_by_channel(channel_type, channel_unique_id)
        if not record:
            return False
        store = self.meta_store
        prefix = self._CHANNEL_IDENTITIES_PREFIX
        ct_safe = self._channel_identity_safe_segment(channel_type)
        id_safe = self._channel_identity_safe_segment(channel_unique_id)
        store.delete(f"{prefix}by_channel/{ct_safe}/{id_safe}")
        store.delete(f"{prefix}by_user/{record.user_id}/{ct_safe}/{id_safe}")
        return True

    # =========================================================================
    # Channels bucket — per-channel metadata (path <channel>/meta)
    # =========================================================================

    _CHANNELS_PREFIX = "_channels/"

    def _channels_store_and_prefix(self) -> Tuple[BlobStore, str]:
        """Return (store, path_prefix) for channel metadata. Uses channels_store or meta with _channels/."""
        if self.channels_store is not None:
            return self.channels_store, ""
        return self.meta_store, self._CHANNELS_PREFIX

    def _channel_meta_path(self, channel_type: str) -> str:
        """Blob path for a channel's metadata. channel_type is sanitized for path."""
        safe = (channel_type or "unknown").replace("/", "_").replace("\\", "_").strip().lower() or "unknown"
        return f"{safe}/meta.json"

    def channel_meta_get(self, channel_type: str) -> Optional[ChannelMetadata]:
        """Return metadata for a channel, or None if not found."""
        store, prefix = self._channels_store_and_prefix()
        path = prefix + self._channel_meta_path(channel_type)
        try:
            raw = store.read(path)
        except FileNotFoundError:
            return None
        data = json.loads(raw.decode("utf-8"))
        return ChannelMetadata(**data)

    def channel_meta_list(self) -> List[ChannelMetadata]:
        """List all channel metadata records (scan channels store)."""
        store, prefix = self._channels_store_and_prefix()
        out: List[ChannelMetadata] = []
        try:
            blobs = store.list_blobs(prefix=prefix)
        except Exception:
            return []
        seen: set = set()
        for info in blobs:
            if not info.name.endswith("/meta.json"):
                continue
            # path is like "telegram/meta.json" or "_channels/telegram/meta.json"
            rel = info.name[len(prefix):] if prefix else info.name
            parts = rel.split("/")
            if len(parts) >= 2 and parts[-1] == "meta.json":
                ct = parts[0]
                if ct in seen:
                    continue
                seen.add(ct)
                try:
                    raw = store.read(info.name)
                    data = json.loads(raw.decode("utf-8"))
                    out.append(ChannelMetadata(**data))
                except Exception:
                    continue
        return out

    def channel_meta_set(self, channel_type: str, payload: ChannelMetadataCreate) -> ChannelMetadata:
        """Create or update channel metadata. Sets created_at/updated_at."""
        store, prefix = self._channels_store_and_prefix()
        path = prefix + self._channel_meta_path(channel_type)
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        existing = self.channel_meta_get(channel_type)
        if existing:
            record = ChannelMetadata(
                channel_type=channel_type,
                display_name=payload.display_name if payload.display_name is not None else existing.display_name,
                description=payload.description if payload.description is not None else existing.description,
                config=payload.config if payload.config is not None else (existing.config or {}),
                metadata=payload.metadata if payload.metadata is not None else (existing.metadata or {}),
                created_at=existing.created_at,
                updated_at=now,
            )
        else:
            record = ChannelMetadata(
                channel_type=channel_type,
                display_name=payload.display_name,
                description=payload.description,
                config=payload.config or {},
                metadata=payload.metadata or {},
                created_at=now,
                updated_at=now,
            )
        store.write(path, record.model_dump_json().encode("utf-8"), "application/json")
        return record

    def channel_meta_delete(self, channel_type: str) -> bool:
        """Remove channel metadata. Returns True if deleted, False if not found."""
        store, prefix = self._channels_store_and_prefix()
        path = prefix + self._channel_meta_path(channel_type)
        try:
            store.delete(path)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    # =================================================================
    # Organization & Project hierarchy (local JSON; SupabaseStorage overrides)
    # =================================================================

    _ORGS_PREFIX = "orgs/"
    _PROJECTS_PREFIX = "projects/"
    _HOST_BINDINGS_PREFIX = "index/host_bindings/"

    @staticmethod
    def _host_binding_key(external_org_id: str, external_workspace_id: str) -> str:
        def _safe(s: str) -> str:
            return re.sub(r"[^a-zA-Z0-9._-]+", "_", (s or "").strip())[:120] or "x"

        return f"{_safe(external_org_id)}__{_safe(external_workspace_id)}"

    def host_binding_get(
        self, external_org_id: str, external_workspace_id: str
    ) -> Optional[dict]:
        """Return stored host binding dict or None."""
        path = (
            self._HOST_BINDINGS_PREFIX
            + self._host_binding_key(external_org_id, external_workspace_id)
            + ".json"
        )
        try:
            raw = self.meta_store.read(path)
            return json.loads(raw.decode("utf-8"))
        except FileNotFoundError:
            return None
        except Exception as exc:
            logger.warning("host_binding_get failed: %s", exc)
            return None

    def host_binding_put(self, record: dict) -> None:
        """Persist a host binding record (idempotent key from external ids)."""
        key = self._host_binding_key(
            record["external_org_id"], record["external_workspace_id"]
        )
        path = self._HOST_BINDINGS_PREFIX + key + ".json"
        payload = dict(record)
        payload["updated_at"] = datetime.utcnow().isoformat() + "Z"
        if "created_at" not in payload:
            payload["created_at"] = payload["updated_at"]
        self.meta_store.write(
            path, json.dumps(payload, indent=2).encode("utf-8"), "application/json"
        )

    def set_user_defaults(
        self,
        user_id: str,
        *,
        default_org_id: Optional[str] = None,
        default_project_id: Optional[str] = None,
    ) -> Optional[User]:
        """Update a user's default org/project (local profile JSON)."""
        user = self.get_user(user_id)
        if not user:
            return None
        if default_org_id is not None:
            user.default_org_id = default_org_id
        if default_project_id is not None:
            user.default_project_id = default_project_id
        user.updated_at = datetime.utcnow().isoformat() + "Z"
        blob_path = f"users/{user_id}/profile.json"
        self.user_store.write(
            blob_path,
            json.dumps(user.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        return user

    def create_organization(self, org_create, owner_user_id: str):
        from ulid import ULID
        from app.models import Organization, OrgMember, OrgRole

        now = datetime.utcnow().isoformat() + "Z"
        org_id = f"org_{ULID()}"
        org = Organization(
            org_id=org_id,
            name=org_create.name,
            display_name=org_create.display_name or org_create.name,
            owner_user_id=owner_user_id,
            metadata=getattr(org_create, "metadata", None) or {},
            status="active",
            created_at=now,
            updated_at=now,
        )
        path = f"{self._ORGS_PREFIX}{org_id}.json"
        self.meta_store.write(
            path, json.dumps(org.model_dump(), indent=2).encode("utf-8"), "application/json"
        )
        self.add_org_member(org_id, owner_user_id, OrgRole.OWNER)
        return org

    def get_organization(self, org_id: str):
        from app.models import Organization

        path = f"{self._ORGS_PREFIX}{org_id}.json"
        try:
            raw = self.meta_store.read(path)
            return Organization(**json.loads(raw.decode("utf-8")))
        except FileNotFoundError:
            return None

    def list_organizations(self, user_id: str):
        orgs = []
        for info in self.meta_store.list_blobs(prefix=self._ORGS_PREFIX):
            if not info.name.endswith(".json") or "/members/" in info.name:
                continue
            try:
                raw = self.meta_store.read(info.name)
                org = json.loads(raw.decode("utf-8"))
                member = self.get_org_member(org.get("org_id", ""), user_id)
                if member or org.get("owner_user_id") == user_id:
                    from app.models import Organization

                    orgs.append(Organization(**org))
            except Exception:
                continue
        return orgs

    def update_organization(self, org_id: str, org_update):
        org = self.get_organization(org_id)
        if not org:
            return None
        data = org.model_dump()
        for field in ("name", "display_name", "metadata", "status"):
            val = getattr(org_update, field, None)
            if val is not None:
                data[field] = val
        data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        path = f"{self._ORGS_PREFIX}{org_id}.json"
        self.meta_store.write(
            path, json.dumps(data, indent=2).encode("utf-8"), "application/json"
        )
        from app.models import Organization

        return Organization(**data)

    def delete_organization(self, org_id: str):
        path = f"{self._ORGS_PREFIX}{org_id}.json"
        try:
            self.meta_store.delete(path)
        except FileNotFoundError:
            return False
        for info in self.meta_store.list_blobs(prefix=f"{self._ORGS_PREFIX}{org_id}/members/"):
            try:
                self.meta_store.delete(info.name)
            except Exception:
                pass
        for proj in self.list_projects(org_id):
            self.delete_project(proj.project_id)
        return True

    def add_org_member(self, org_id: str, user_id: str, role):
        from app.models import OrgMember, OrgRole

        role_val = role.value if hasattr(role, "value") else str(role)
        now = datetime.utcnow().isoformat() + "Z"
        member = OrgMember(
            org_id=org_id,
            user_id=user_id,
            role=OrgRole(role_val),
            created_at=now,
        )
        path = f"{self._ORGS_PREFIX}{org_id}/members/{user_id}.json"
        self.meta_store.write(
            path, json.dumps(member.model_dump(), indent=2).encode("utf-8"), "application/json"
        )
        return member

    def get_org_member(self, org_id: str, user_id: str):
        from app.models import OrgMember

        path = f"{self._ORGS_PREFIX}{org_id}/members/{user_id}.json"
        try:
            raw = self.meta_store.read(path)
            return OrgMember(**json.loads(raw.decode("utf-8")))
        except FileNotFoundError:
            return None

    def list_org_members(self, org_id: str):
        from app.models import OrgMember

        out = []
        for info in self.meta_store.list_blobs(prefix=f"{self._ORGS_PREFIX}{org_id}/members/"):
            if not info.name.endswith(".json"):
                continue
            try:
                raw = self.meta_store.read(info.name)
                out.append(OrgMember(**json.loads(raw.decode("utf-8"))))
            except Exception:
                continue
        return out

    def update_org_member_role(self, org_id: str, user_id: str, role):
        member = self.get_org_member(org_id, user_id)
        if not member:
            return None
        from app.models import OrgRole

        role_val = role.value if hasattr(role, "value") else str(role)
        member.role = OrgRole(role_val)
        path = f"{self._ORGS_PREFIX}{org_id}/members/{user_id}.json"
        self.meta_store.write(
            path, json.dumps(member.model_dump(), indent=2).encode("utf-8"), "application/json"
        )
        return member

    def remove_org_member(self, org_id: str, user_id: str):
        path = f"{self._ORGS_PREFIX}{org_id}/members/{user_id}.json"
        try:
            self.meta_store.delete(path)
            return True
        except FileNotFoundError:
            return False

    def create_project(self, org_id: str, project_create):
        from ulid import ULID
        from app.models import Project

        now = datetime.utcnow().isoformat() + "Z"
        project_id = f"proj_{ULID()}"
        project = Project(
            project_id=project_id,
            org_id=org_id,
            name=project_create.name,
            display_name=project_create.display_name or project_create.name,
            description=getattr(project_create, "description", None),
            metadata=getattr(project_create, "metadata", None) or {},
            status="active",
            created_at=now,
            updated_at=now,
        )
        path = f"{self._PROJECTS_PREFIX}{project_id}.json"
        self.meta_store.write(
            path, json.dumps(project.model_dump(), indent=2).encode("utf-8"), "application/json"
        )
        return project

    def get_project(self, project_id: str):
        from app.models import Project

        path = f"{self._PROJECTS_PREFIX}{project_id}.json"
        try:
            raw = self.meta_store.read(path)
            return Project(**json.loads(raw.decode("utf-8")))
        except FileNotFoundError:
            return None

    def list_projects(self, org_id: str):
        from app.models import Project

        out = []
        for info in self.meta_store.list_blobs(prefix=self._PROJECTS_PREFIX):
            if not info.name.endswith(".json"):
                continue
            try:
                raw = self.meta_store.read(info.name)
                data = json.loads(raw.decode("utf-8"))
                if data.get("org_id") == org_id:
                    out.append(Project(**data))
            except Exception:
                continue
        return out

    def update_project(self, project_id: str, project_update):
        project = self.get_project(project_id)
        if not project:
            return None
        data = project.model_dump()
        for field in ("name", "display_name", "description", "metadata", "status"):
            val = getattr(project_update, field, None)
            if val is not None:
                data[field] = val
        data["updated_at"] = datetime.utcnow().isoformat() + "Z"
        path = f"{self._PROJECTS_PREFIX}{project_id}.json"
        self.meta_store.write(
            path, json.dumps(data, indent=2).encode("utf-8"), "application/json"
        )
        from app.models import Project

        return Project(**data)

    def delete_project(self, project_id: str):
        path = f"{self._PROJECTS_PREFIX}{project_id}.json"
        try:
            self.meta_store.delete(path)
            return True
        except FileNotFoundError:
            return False


# =============================================================================
# Module-level AI helpers
# =============================================================================

def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks."""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += chunk_size - overlap
    return chunks


def _coalesce_chunk_specs(
    specs: List[Dict[str, Any]],
    chunk_size: int,
) -> List[Dict[str, Any]]:
    """Merge adjacent same-page specs so short Office paragraphs don't explode.

    Specs with different ``page`` values are never merged (PDF page locality).
    Paragraphs with ``page is None`` (DOCX) pack up to ``chunk_size``.
    """
    if not specs:
        return []
    merged: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for spec in specs:
        text = (spec.get("text") or "").strip()
        if not text:
            continue
        if current is None:
            current = {
                "text": text,
                "page": spec.get("page"),
                "section_path": list(spec.get("section_path") or []) or None,
                "element_type": spec.get("element_type"),
                "embedding_kind": spec.get("embedding_kind") or "body",
            }
            continue
        same_page = current.get("page") == spec.get("page")
        same_kind = (current.get("embedding_kind") or "body") == (
            spec.get("embedding_kind") or "body"
        )
        combined = f"{current['text']}\n\n{text}"
        if same_page and same_kind and len(combined) <= chunk_size:
            current["text"] = combined
            sp = spec.get("section_path")
            if sp:
                cur_sp = list(current.get("section_path") or [])
                for part in (sp if isinstance(sp, list) else [sp]):
                    s = str(part)
                    if s and s not in cur_sp:
                        cur_sp.append(s)
                current["section_path"] = cur_sp or None
            continue
        merged.append(current)
        current = {
            "text": text,
            "page": spec.get("page"),
            "section_path": list(spec.get("section_path") or []) or None,
            "element_type": spec.get("element_type"),
            "embedding_kind": spec.get("embedding_kind") or "body",
        }
    if current is not None:
        merged.append(current)
    return merged


def _expand_chunk_specs(
    specs: List[Dict[str, Any]],
    chunk_size: int,
    chunk_overlap: int,
) -> List[Dict[str, Any]]:
    """Split oversized chunk specs with ``_chunk_text``, inheriting metadata."""
    expanded: List[Dict[str, Any]] = []
    for spec in specs:
        text = (spec.get("text") or "").strip()
        if not text:
            continue
        meta = {
            "page": spec.get("page"),
            "section_path": spec.get("section_path"),
            "element_type": spec.get("element_type"),
            "embedding_kind": spec.get("embedding_kind") or "body",
        }
        if len(text) <= chunk_size:
            expanded.append({"text": text, **meta})
            continue
        for piece in _chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap):
            if piece.strip():
                expanded.append({"text": piece, **meta})
    return expanded


def _chunk_specs_from_parsed_json(
    document: Dict[str, Any],
    chunk_size: int,
    chunk_overlap: int,
) -> List[Dict[str, Any]]:
    """Build embedding chunk specs from parsed document JSON chunks."""
    raw_chunks = document.get("chunks")
    if not isinstance(raw_chunks, list) or not raw_chunks:
        return []
    specs: List[Dict[str, Any]] = []
    for ch in raw_chunks:
        if not isinstance(ch, dict):
            continue
        text = ch.get("text") or ""
        if not str(text).strip():
            continue
        page = ch.get("page")
        try:
            page_i = int(page) if page is not None else None
        except (TypeError, ValueError):
            page_i = None
        section_path = ch.get("section_path")
        if section_path is not None and not isinstance(section_path, list):
            section_path = [str(section_path)]
        specs.append(
            {
                "text": str(text),
                "page": page_i,
                "section_path": section_path,
                "element_type": ch.get("element_type"),
                "embedding_kind": "body",
            }
        )
    return _expand_chunk_specs(
        _coalesce_chunk_specs(specs, chunk_size),
        chunk_size,
        chunk_overlap,
    )


def _chunk_specs_from_text(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    *,
    embedding_kind: str = "body",
) -> List[Dict[str, Any]]:
    pieces = _chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
    if not pieces:
        pieces = [text[:chunk_size] or "(empty)"]
    return [
        {
            "text": p,
            "page": None,
            "section_path": None,
            "element_type": None,
            "embedding_kind": embedding_kind,
        }
        for p in pieces
        if p.strip() or p == "(empty)"
    ]


def _generate_embeddings(
    chunks: List[str], engine_type: str, model: str, api_key: str,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> List[List[float]]:
    """Call the appropriate embedding API and return a list of float vectors.

    Supports Ollama Cloud, Gemini, and OpenAI-compatible endpoints.
    When Ollama Cloud is primary and fails, automatically falls back to Gemini.
    Falls back to zero vectors when no API key is available.
    Records embedding telemetry (tokens, latency) on each call.
    """
    import time as _time
    from app import model_telemetry as _mt

    if not api_key and engine_type not in ("local", "ollama_local"):
        logger.warning("No API key for embeddings engine=%s; returning zero vectors", engine_type)
        return [[0.0] * 768 for _ in chunks]

    vectors: List[List[float]] = []

    # Local Ollama embedding via /api/embed (in-cluster, no auth)
    # Retry on 404 — Ollama returns 404 when the model isn't loaded into
    # memory yet (cold start or eviction).  Back off with increasing delays.
    if engine_type == "ollama_local":
        import httpx as _httpx
        api_base = config.OLLAMA_LOCAL_API_BASE
        max_retries = 5
        retry_delays = [2, 5, 10, 15]  # seconds between retries
        last_exc: Exception | None = None
        t0 = _time.monotonic()
        for attempt in range(max_retries):
            try:
                resp = _httpx.post(
                    f"{api_base}/api/embed",
                    json={"model": model, "input": chunks},
                    timeout=120,
                )
                resp.raise_for_status()
                embeddings = resp.json().get("embeddings", [])
                if embeddings and len(embeddings) == len(chunks):
                    latency = int((_time.monotonic() - t0) * 1000)
                    dims = len(embeddings[0]) if embeddings else 0
                    _mt.record_embedding(
                        engine=engine_type, model=model, chunks=len(chunks),
                        dimensions=dims, latency_ms=latency,
                        total_tokens=sum(len(c.split()) for c in chunks),
                    )
                    return embeddings
                logger.warning("Local Ollama embeddings unexpected shape (attempt %d/%d)", attempt + 1, max_retries)
                last_exc = ValueError("unexpected shape")
            except Exception as exc:
                last_exc = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status == 404 and attempt < max_retries - 1:
                    delay = retry_delays[min(attempt, len(retry_delays) - 1)]
                    logger.info("Ollama embed 404 (model loading?), retry %d/%d in %ds", attempt + 1, max_retries, delay)
                    _time.sleep(delay)
                    continue
                logger.warning("Local Ollama embedding failed (attempt %d/%d): %s", attempt + 1, max_retries, exc)
            break

        if last_exc:
            _mt.record_embedding(
                engine=engine_type, model=model, chunks=len(chunks),
                dimensions=0, latency_ms=int((_time.monotonic() - t0) * 1000),
                status_code="ERROR", error=str(last_exc),
            )
        # Fallback to Gemini
        if config.SYSTEM_GEMINI_API_KEY:
            logger.info("Ollama Local embedding failed; falling back to Gemini")
            return _generate_embeddings(
                chunks, AIEngineType.GEMINI.value,
                config.SYSTEM_GEMINI_MODEL_EMBEDDING,
                config.SYSTEM_GEMINI_API_KEY,
                task_type=task_type,
            )
        return [[0.0] * 768 for _ in chunks]

    # Ollama Cloud embedding via /api/embed
    if engine_type == "ollama_cloud":
        import httpx as _httpx
        api_base = config.OLLAMA_CLOUD_API_BASE or "https://api.ollama.com"
        t0 = _time.monotonic()
        try:
            resp = _httpx.post(
                f"{api_base}/api/embed",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "input": chunks},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [])
            if embeddings and len(embeddings) == len(chunks):
                latency = int((_time.monotonic() - t0) * 1000)
                dims = len(embeddings[0]) if embeddings else 0
                _mt.record_embedding(
                    engine=engine_type, model=model, chunks=len(chunks),
                    dimensions=dims, latency_ms=latency,
                    total_tokens=sum(len(c.split()) for c in chunks),
                )
                return embeddings
            # Unexpected response shape — fall through to Gemini
            logger.warning(
                "Ollama Cloud embeddings response unexpected shape "
                "(got %d vectors for %d chunks); falling back to Gemini",
                len(embeddings), len(chunks),
            )
        except Exception as exc:
            logger.warning("Ollama Cloud embedding failed: %s; falling back to Gemini", exc)
            _mt.record_embedding(
                engine=engine_type, model=model, chunks=len(chunks),
                dimensions=0, latency_ms=int((_time.monotonic() - t0) * 1000),
                status_code="ERROR", error=str(exc),
            )

        # Fallback to Gemini
        if config.SYSTEM_GEMINI_API_KEY:
            logger.info("Embedding fallback: Gemini | model=%s", config.SYSTEM_GEMINI_MODEL_EMBEDDING)
            return _generate_embeddings(
                chunks, AIEngineType.GEMINI.value,
                config.SYSTEM_GEMINI_MODEL_EMBEDDING,
                config.SYSTEM_GEMINI_API_KEY,
                task_type=task_type,
            )
        logger.warning("No Gemini fallback for embeddings; returning zero vectors")
        return [[0.0] * 768 for _ in chunks]

    if engine_type in (AIEngineType.GEMINI.value, "gemini"):
        import httpx as _httpx
        t0 = _time.monotonic()
        for chunk in chunks:
            try:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:embedContent?key={api_key}"
                )
                resp = _httpx.post(
                    url,
                    json={
                        "model": f"models/{model}",
                        "content": {"parts": [{"text": chunk}]},
                        "taskType": task_type,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                vector = resp.json()["embedding"]["values"]
                vectors.append(vector)
            except Exception as exc:
                logger.warning("Gemini embedding failed for chunk: %s", exc)
                vectors.append([0.0] * 768)
        latency = int((_time.monotonic() - t0) * 1000)
        dims = len(vectors[0]) if vectors else 0
        _mt.record_embedding(
            engine=engine_type, model=model, chunks=len(chunks),
            dimensions=dims, latency_ms=latency,
            total_tokens=sum(len(c.split()) for c in chunks),
        )
        return vectors

    # OpenAI-compatible endpoint
    if engine_type in (AIEngineType.OPENAI.value, "openai"):
        import httpx as _httpx
        t0 = _time.monotonic()
        try:
            resp = _httpx.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "input": chunks},
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()
            data = result["data"]
            vecs = [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]
            latency = int((_time.monotonic() - t0) * 1000)
            dims = len(vecs[0]) if vecs else 0
            total_tokens = result.get("usage", {}).get("total_tokens", 0)
            _mt.record_embedding(
                engine=engine_type, model=model, chunks=len(chunks),
                dimensions=dims, latency_ms=latency, total_tokens=total_tokens,
            )
            return vecs
        except Exception as exc:
            logger.warning("OpenAI embedding failed: %s", exc)
            _mt.record_embedding(
                engine=engine_type, model=model, chunks=len(chunks),
                dimensions=0, latency_ms=int((_time.monotonic() - t0) * 1000),
                status_code="ERROR", error=str(exc),
            )
            return [[0.0] * 1536 for _ in chunks]

    # Unknown engine — zero vectors
    logger.warning("Unsupported embedding engine=%s; returning zero vectors", engine_type)
    return [[0.0] * 768 for _ in chunks]


def _call_ai_completion(
    prompt: str, engine_type: str, model: str, api_key: str,
    image_bytes: bytes | None = None, image_mime_type: str | None = None,
) -> str:
    """Call the configured AI for a single completion and return the text.

    When *image_bytes* and *image_mime_type* are provided the Gemini branch
    builds a multimodal request with an ``inline_data`` part so the model can
    "see" the image.  Non-Gemini engines receive the text prompt only.
    """
    if engine_type in (AIEngineType.GEMINI.value, "gemini") and api_key:
        import httpx as _httpx
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={api_key}"
            )
            parts: list[dict] = [{"text": prompt}]
            if image_bytes and image_mime_type:
                import base64 as _b64
                parts.append({
                    "inline_data": {
                        "mime_type": image_mime_type,
                        "data": _b64.b64encode(image_bytes).decode(),
                    }
                })
            resp = _httpx.post(
                url,
                json={"contents": [{"parts": parts}]},
                timeout=60,
            )
            if resp.status_code != 200:
                detail = resp.text[:500]
                logger.warning("Gemini completion HTTP %s: %s", resp.status_code, detail)
                # Retry once with truncated prompt if content is too large
                if resp.status_code == 400 and len(prompt) > 30000:
                    truncated = prompt[:30000] + "\n\n[Content truncated]"
                    parts[0] = {"text": truncated}
                    resp = _httpx.post(
                        url,
                        json={"contents": [{"parts": parts}]},
                        timeout=60,
                    )
                    if resp.status_code == 200:
                        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            logger.warning("Gemini completion failed: %s", exc)
            return f"[AI generation failed: {exc}]"

    if engine_type in (AIEngineType.OPENAI.value, "openai") and api_key:
        import httpx as _httpx
        try:
            resp = _httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("OpenAI completion failed: %s", exc)
            return f"[AI generation failed: {exc}]"

    if engine_type == "local" and config.is_model_server_enabled():
        import httpx as _httpx
        try:
            url = config.MODEL_SERVER_URL.rstrip("/") + "/v1/chat/completions"
            resp = _httpx.post(
                url,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 512,
                },
                timeout=config.MODEL_SERVER_TIMEOUT_S,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("Local model server completion failed: %s", exc)
            return f"[AI generation failed: {exc}]"

    return "[AI generation skipped: no engine configured]"


# =============================================================================
# Concrete storage backends
# =============================================================================


class LocalStorage(BaseStorage):
    """Storage backed by the local file system. Uses MEM_DOG_DATA_DIR and _LOCAL_SUBDIRS."""

    def _build_stores(self) -> Dict[str, BlobStore]:
        base = Path(config.MEM_DOG_DATA_DIR)
        stores: Dict[str, BlobStore] = {}
        for key, subdir in _LOCAL_SUBDIRS.items():
            stores[key] = LocalBlobStore(base / subdir)
        return stores


class GCSStorage(BaseStorage):
    """Storage backed by Google Cloud Storage. Uses config bucket env vars."""

    def _build_stores(self) -> Dict[str, BlobStore]:
        project = config.GCP_PROJECT_ID or None
        stores: Dict[str, BlobStore] = {
            "raw": GCSBlobStore(config.RAW_BUCKET, project),
            "meta": GCSBlobStore(config.META_BUCKET, project),
            "memories": GCSBlobStore(config.MEMORIES_BUCKET, project),
        }
        # Dedicated reverse-index bucket (optional; falls back to meta_store under _idx/ prefix in __init__)
        if config.INDEX_BUCKET:
            stores["index"] = GCSBlobStore(config.INDEX_BUCKET, project)
        if config.USER_BUCKET:
            stores["users"] = GCSBlobStore(config.USER_BUCKET, project)
        if config.PROMPTS_BUCKET:
            stores["prompts"] = GCSBlobStore(config.PROMPTS_BUCKET, project)
        if config.EMBEDDINGS_BUCKET:
            stores["embeddings"] = GCSBlobStore(config.EMBEDDINGS_BUCKET, project)
        if config.VIEWPOINTS_BUCKET:
            stores["viewpoints"] = GCSBlobStore(config.VIEWPOINTS_BUCKET, project)
        if config.AI_CONFIG_BUCKET:
            stores["ai_config"] = GCSBlobStore(config.AI_CONFIG_BUCKET, project)
        if config.SKILLS_BUCKET:
            stores["skills"] = GCSBlobStore(config.SKILLS_BUCKET, project)
        if config.STATS_BUCKET:
            stores["stats"] = GCSBlobStore(config.STATS_BUCKET, project)
        if getattr(config, "CHANNELS_BUCKET", "") and config.CHANNELS_BUCKET.strip():
            stores["channels"] = GCSBlobStore(config.CHANNELS_BUCKET.strip(), project)
        return stores


class RedisStorage(BaseStorage):
    """Storage with same blob backend as Local/GCS plus optional Redis and Postgres stores (testing CRUD API)."""

    def _build_stores(self) -> Dict[str, BlobStore]:
        if config.STORAGE_BACKEND == "local":
            base = Path(config.MEM_DOG_DATA_DIR)
            return {k: LocalBlobStore(base / subdir) for k, subdir in _LOCAL_SUBDIRS.items()}
        project = config.GCP_PROJECT_ID or None
        stores: Dict[str, BlobStore] = {
            "raw": GCSBlobStore(config.RAW_BUCKET, project),
            "meta": GCSBlobStore(config.META_BUCKET, project),
            "memories": GCSBlobStore(config.MEMORIES_BUCKET, project),
        }
        if config.INDEX_BUCKET:
            stores["index"] = GCSBlobStore(config.INDEX_BUCKET, project)
        if config.USER_BUCKET:
            stores["users"] = GCSBlobStore(config.USER_BUCKET, project)
        if config.PROMPTS_BUCKET:
            stores["prompts"] = GCSBlobStore(config.PROMPTS_BUCKET, project)
        if config.EMBEDDINGS_BUCKET:
            stores["embeddings"] = GCSBlobStore(config.EMBEDDINGS_BUCKET, project)
        if config.VIEWPOINTS_BUCKET:
            stores["viewpoints"] = GCSBlobStore(config.VIEWPOINTS_BUCKET, project)
        if config.AI_CONFIG_BUCKET:
            stores["ai_config"] = GCSBlobStore(config.AI_CONFIG_BUCKET, project)
        if config.SKILLS_BUCKET:
            stores["skills"] = GCSBlobStore(config.SKILLS_BUCKET, project)
        if config.STATS_BUCKET:
            stores["stats"] = GCSBlobStore(config.STATS_BUCKET, project)
        if getattr(config, "CHANNELS_BUCKET", "") and config.CHANNELS_BUCKET.strip():
            stores["channels"] = GCSBlobStore(config.CHANNELS_BUCKET.strip(), project)
        return stores

    def _build_redis_store(self) -> Optional[Store]:
        if not config.REDIS_URL:
            return None
        try:
            return RedisStore(config.REDIS_URL)
        except Exception as e:
            logger.warning("Redis store init failed (store API will return 503 for redis=true): %s", e)
            return None

    def _build_postgres_store(self) -> Optional[Store]:
        if not config.POSTGRES_URL:
            return None
        try:
            return PostgresStore(config.POSTGRES_URL)
        except Exception as e:
            logger.warning("Postgres store init failed (store API will return 503 for postgres=true): %s", e)
            return None

    def _build_supabase_store(self) -> Optional[Store]:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            return None
        try:
            return SupabaseStore(
                config.SUPABASE_URL,
                config.SUPABASE_KEY,
                api_gateway_key=config.SUPABASE_API_GATEWAY_KEY or None,
            )
        except Exception as e:
            logger.warning("Supabase store init failed (store API will return 503 for supabase=true): %s", e)
            return None

    def _build_gcs_store(self) -> Optional[Store]:
        if not config.STORE_GCS_BUCKET:
            return None
        try:
            return GCSStore(config.STORE_GCS_BUCKET, project=config.GCP_PROJECT_ID or None)
        except Exception as e:
            logger.warning("GCS store init failed (store API will return 503 for gcs=true): %s", e)
            return None

    # -------------------------------------------------------------------------
    # Graph Memory — entity/relationship storage (no-op defaults)
    # -------------------------------------------------------------------------

    def upsert_entity(
        self, *, data_id: str, user_id: str, entity_type: str, entity_name: str,
        confidence: float = 1.0, metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        """Insert or update an entity (dedup by user_id + entity_type + canonical_form). Returns entity dict or None."""
        return None

    def search_entities(
        self, query: str, user_id: str, *, entity_type: Optional[str] = None, limit: int = 20,
    ) -> List[dict]:
        """Search entities by name substring."""
        return []

    def get_data_entities(self, data_id: str, user_id: str) -> List[dict]:
        """Get all entities extracted from a data item."""
        return []

    def get_entity(self, entity_id: str, user_id: str) -> Optional[dict]:
        """Get a single entity by ID."""
        return None

    def get_entity_relationships(self, entity_id: str, user_id: str) -> List[dict]:
        """Get all relationships for an entity."""
        return []

    def create_relationship(
        self, *, user_id: str, data_id: str, source_entity_id: str,
        target_entity_id: str, rel_type: str, strength: float = 1.0,
        description: Optional[str] = None,
    ) -> Optional[dict]:
        """Create a relationship between two entities."""
        return None

    def delete_data_entities(self, data_id: str, user_id: str) -> int:
        """Delete all entities and relationships for a data item. Returns count deleted."""
        return 0

    def find_related_data_ids(self, entity_ids: List[str], user_id: str, limit: int = 50) -> List[str]:
        """Find data_ids related to the given entity IDs."""
        return []

    def hybrid_search(
        self, query_vector: List[float], query_text: str, limit: int = 5,
        user_id: str = "", memory_id: str = "",
        vector_weight: float = 0.5, fts_weight: float = 0.5,
    ) -> List[dict]:
        """Hybrid cosine + BM25 search with RRF fusion.

        Returns list of dicts with keys: embedding_id, data_id, chunk_text,
        similarity, fts_rank, rrf_score, search_type.
        Default implementation falls back to similarity_search with empty FTS fields.
        """
        results = self.similarity_search(query_vector, limit=limit, user_id=user_id, memory_id=memory_id)
        return [
            {
                "embedding_id": r.get("embedding_id", ""),
                "data_id": r.get("data_id", ""),
                "chunk_text": r.get("chunk_text", ""),
                "similarity": r.get("similarity", 0.0),
                "fts_rank": None,
                "rrf_score": None,
                "search_type": "vector",
                **({"page": r["page"]} if r.get("page") is not None else {}),
            }
            for r in results
        ]

    def fts_search(
        self, query_text: str, limit: int = 5, user_id: str = "", memory_id: str = "",
    ) -> List[dict]:
        """BM25 full-text search (no embedding needed).

        Returns list of dicts with keys: embedding_id, data_id, chunk_text, fts_rank.
        Default implementation returns empty list.
        """
        return []


class SupabaseStorage(BaseStorage):
    """Hybrid storage: raw binary data in GCS, all structured data in Supabase.

    Blob routing:
      - ``raw``  → GCSBlobStore (binary blobs stay in GCS)
      - All other stores → SupabaseBlobStore backed by ``mem_dog_blobs``

    Embeddings bypass the generic BlobStore path and use the dedicated
    ``mem_dog_embeddings`` pgvector table with strict multi-tenant isolation
    (every query scopes on ``user_id``).

    Requires ``SUPABASE_URL``, ``SUPABASE_KEY`` (or ``SUPABASE_SERVICE_ROLE_KEY``),
    and ``RAW_BUCKET`` to be configured.  Activated when ``STORAGE_BACKEND=supabase``.
    """

    _EMB_TABLE = "mem_dog_embeddings"

    # Per-store user_id extractors derive the tenant from blob paths so
    # that rows carry an explicit ``user_id`` for RLS and scoped queries.
    _USER_ID_EXTRACTORS = {
        "meta":       lambda p: p.split("/")[0] if p.count("/") >= 1 else None,
        "memories":   lambda p: p.split("/")[0] if p.count("/") >= 1 else None,
        "viewpoints": lambda p: p.split("/")[0] if p.count("/") >= 1 else None,
        "embeddings": lambda p: p.split("/")[0] if p.count("/") >= 1 else None,
        "index":      lambda p: p.split("/")[1] if p.count("/") >= 2 else None,
        "users":      lambda p: p.split("/")[1] if p.count("/") >= 2 else None,
    }

    # ------------------------------------------------------------------
    # BaseStorage overrides — build blob stores and optional KV store
    # ------------------------------------------------------------------

    def _build_stores(self) -> Dict[str, BlobStore]:
        from app.blob_store import _fetch_identity_token

        project = config.GCP_PROJECT_ID or None
        url = config.SUPABASE_URL
        key = config.SUPABASE_KEY
        gw_key = config.SUPABASE_API_GATEWAY_KEY or None

        # Only attempt GCP identity token auth for Cloud Run proxy URLs
        # (*.run.app).  Direct connections to Kong/Supabase (IPs, .svc.cluster.local,
        # supabase.co, localhost) must use the Supabase JWT as-is.
        from urllib.parse import urlparse
        _host = urlparse(url).hostname or ""
        _is_proxy_url = _host.endswith(".run.app")
        use_id_token = _is_proxy_url and not gw_key and bool(_fetch_identity_token(url))
        if use_id_token:
            logger.info("SupabaseStorage: using GCP identity token for proxy auth")
        elif gw_key:
            logger.info("SupabaseStorage: using API Gateway key for proxy auth")
        else:
            logger.info("SupabaseStorage: direct Supabase connection (no proxy)")

        def _sbs(store_name: str) -> SupabaseBlobStore:
            return SupabaseBlobStore(
                store_name=store_name,
                supabase_url=url,
                supabase_key=key,
                api_gateway_key=gw_key,
                use_identity_token=use_id_token,
                user_id_extractor=self._USER_ID_EXTRACTORS.get(store_name),
            )

        return {
            "raw":        GCSBlobStore(config.RAW_BUCKET, project),
            "meta":       _sbs("meta"),
            "memories":   _sbs("memories"),
            "index":      _sbs("index"),
            "users":      _sbs("users"),
            "prompts":    _sbs("prompts"),
            "embeddings": _sbs("embeddings"),
            "viewpoints": _sbs("viewpoints"),
            "ai_config":  _sbs("ai_config"),
            "skills":     _sbs("skills"),
            "stats":      _sbs("stats"),
            "channels":   _sbs("channels"),
        }

    def _build_supabase_store(self) -> Optional[Store]:
        """Wire the key-value Store API to Supabase ``store_kv`` table."""
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            return None
        try:
            return SupabaseStore(
                config.SUPABASE_URL,
                config.SUPABASE_KEY,
                api_gateway_key=config.SUPABASE_API_GATEWAY_KEY or None,
            )
        except Exception as e:
            logger.warning("Supabase KV store init failed: %s", e)
            return None

    def _build_gcs_store(self) -> Optional[Store]:
        if not config.STORE_GCS_BUCKET:
            return None
        try:
            return GCSStore(config.STORE_GCS_BUCKET, project=config.GCP_PROJECT_ID or None)
        except Exception as e:
            logger.warning("GCS KV store init failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Shared Supabase client (for direct table/RPC access)
    # ------------------------------------------------------------------

    @property
    def _supa_client(self):
        """Lazily create a shared Supabase client for direct table operations."""
        if not hasattr(self, "_supa_client_instance"):
            from supabase import create_client
            from supabase.lib.client_options import SyncClientOptions
            from app.blob_store import _fetch_identity_token, _attach_identity_token_hook

            options: Optional[SyncClientOptions] = None
            if config.SUPABASE_API_GATEWAY_KEY:
                options = SyncClientOptions(headers={"x-api-key": config.SUPABASE_API_GATEWAY_KEY})
            self._supa_client_instance = create_client(
                config.SUPABASE_URL, config.SUPABASE_KEY, options=options
            )
            if not config.SUPABASE_API_GATEWAY_KEY and _fetch_identity_token(config.SUPABASE_URL):
                _attach_identity_token_hook(
                    self._supa_client_instance.postgrest, config.SUPABASE_URL
                )
        return self._supa_client_instance

    # ------------------------------------------------------------------
    # Paginated data list — push pagination into DB via RPC
    # ------------------------------------------------------------------

    def list_all_metadata_paginated(
        self,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        tags: Optional[List[str]] = None,
        match_all: bool = False,
        project_id: Optional[str] = None,
    ) -> Tuple[List[DataListItem], int]:
        try:
            params: Dict[str, object] = {
                "p_user_id": user_id,
                "p_skip": skip,
                "p_limit": limit,
                "p_match_all": match_all,
                "p_tags": tags if tags else None,
                "p_project_id": project_id,
            }
            res = self._supa_client.rpc("list_data_paginated", params).execute()
        except Exception as e:
            logger.warning("list_data_paginated RPC failed, falling back: %s", e)
            return super().list_all_metadata_paginated(
                user_id=user_id, skip=skip, limit=limit, tags=tags, match_all=match_all
            )

        items: List[DataListItem] = []
        total = 0
        for row in res.data or []:
            total = int(row.get("total") or 0)
            raw = row.get("content")
            if raw is None:
                continue
            try:
                metadata = json.loads(base64.b64decode(raw).decode("utf-8"))
            except Exception as e:
                logger.warning("Failed to decode list_data_paginated row: %s", e)
                continue
            versions = metadata.get("versions") or []
            latest = versions[-1] if versions else None
            ct = latest.get("content_type", "unknown") if latest else "unknown"
            items.append(DataListItem(
                data_id=metadata.get("data_id", ""),
                current_version=metadata.get("current_version", 0),
                created_at=metadata.get("created_at", ""),
                updated_at=metadata.get("updated_at", ""),
                content_type=ct,
                size=latest.get("size", 0) if latest else 0,
                name=metadata.get("name"),
                description=metadata.get("description"),
                access=metadata.get("access"),
                memory_ids=metadata.get("memory_ids"),
                tags=metadata.get("tags"),
                url=metadata.get("url"),
                mime_type=metadata.get("mime_type") or ct,
                is_downloaded=metadata.get("is_downloaded", False),
            ))
        return items, total

    # ------------------------------------------------------------------
    # Embedding overrides — mem_dog_embeddings pgvector table
    #
    # All queries enforce multi-tenancy via user_id scoping.
    # ------------------------------------------------------------------

    # Set False after first PGRST missing-column response so later upserts
    # skip page metadata without round-tripping failed writes.
    _embedding_page_cols_ok: Optional[bool] = None

    def store_embedding(self, embedding: Embedding) -> None:
        self._check_ai_enabled()
        if not embedding.user_id or not embedding.version_label:
            raise ValueError(
                f"Embedding {embedding.embedding_id} is missing user_id or "
                "version_label — cannot store in multi-tenant table"
            )
        ai_sig = None
        if embedding.ai_signature:
            ai_sig = embedding.ai_signature.model_dump()
        row = {
            "embedding_id": embedding.embedding_id,
            "data_id":      embedding.data_id,
            "data_version": embedding.data_version,
            "version_label": embedding.version_label,
            "user_id":      embedding.user_id,
            "ai_engine":    embedding.ai_engine if isinstance(embedding.ai_engine, str) else embedding.ai_engine.value,
            "model":        embedding.model,
            "dimensions":   embedding.dimensions,
            "chunk_index":  embedding.chunk_index,
            "chunk_text":   embedding.chunk_text,
            "vector":       "[" + ",".join(str(v) for v in embedding.vector) + "]" if embedding.vector else None,
            "ai_signature": ai_sig,
            "created_at":   embedding.created_at,
        }
        if embedding.org_id:
            row["org_id"] = embedding.org_id
        if embedding.project_id:
            row["project_id"] = embedding.project_id
        page_meta = {
            "page": embedding.page,
            "section_path": embedding.section_path,
            "element_type": embedding.element_type,
            "embedding_kind": embedding.embedding_kind,
        }

        def _upsert(payload: dict) -> None:
            self._supa_client.table(self._EMB_TABLE).upsert(
                payload, on_conflict="embedding_id"
            ).execute()

        def _missing_page_column(exc: Exception) -> bool:
            msg = str(exc).lower()
            return any(
                token in msg
                for token in (
                    "page",
                    "section_path",
                    "element_type",
                    "embedding_kind",
                    "pgrst204",
                )
            ) and any(
                token in msg
                for token in ("column", "could not find", "schema cache", "pgrst")
            )

        if self._embedding_page_cols_ok is False:
            _upsert(row)
            return

        try:
            _upsert({**row, **page_meta})
            self._embedding_page_cols_ok = True
        except Exception as exc:
            if self._embedding_page_cols_ok is True or not _missing_page_column(exc):
                raise
            logger.warning(
                "mem_dog_embeddings page columns missing — upserting without "
                "page metadata (apply mem_dog_embeddings_page.sql): %s",
                exc,
            )
            self._embedding_page_cols_ok = False
            _upsert(row)

    def get_embeddings(
        self,
        data_id: str,
        user_id: str = "",
        version_label: Optional[str] = None,
    ) -> List[Embedding]:
        self._check_ai_enabled()
        if not user_id:
            return []
        query = (
            self._supa_client.table(self._EMB_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("data_id", data_id)
        )
        if version_label:
            query = query.eq("version_label", version_label)
        try:
            res = query.order("chunk_index").execute()
        except Exception as exc:
            logger.warning("get_embeddings query failed: %s", exc)
            return []
        embeddings: List[Embedding] = []
        for row in res.data or []:
            try:
                payload = dict(row)
                vec = payload.get("vector")
                if isinstance(vec, str):
                    # pgvector may come back as "[1,2,...]"
                    cleaned = vec.strip()
                    if cleaned.startswith("[") and cleaned.endswith("]"):
                        payload["vector"] = [float(x) for x in cleaned[1:-1].split(",") if x.strip()]
                    else:
                        payload["vector"] = json.loads(vec)
                embeddings.append(Embedding(**payload))
            except Exception as exc:
                logger.warning("Failed to parse embedding row: %s", exc)
        return embeddings

    def get_embedding_summary(
        self,
        data_id: str,
        user_id: str = "",
        version_label: Optional[str] = None,
    ) -> Optional[EmbeddingSummary]:
        """Efficient summary query — fetches only the first row and a count."""
        self._check_ai_enabled()
        if not user_id:
            return None
        query = (
            self._supa_client.table(self._EMB_TABLE)
            .select("data_id, data_version, ai_engine, model, dimensions, created_at, user_id, version_label")
            .eq("user_id", user_id)
            .eq("data_id", data_id)
        )
        if version_label:
            query = query.eq("version_label", version_label)
        try:
            res = query.order("chunk_index").execute()
        except Exception:
            return None
        rows = res.data or []
        if not rows:
            return None
        first = rows[0]
        return EmbeddingSummary(
            data_id=first["data_id"],
            data_version=first["data_version"],
            embeddings_count=len(rows),
            ai_engine=first["ai_engine"],
            model=first["model"],
            dimensions=first["dimensions"],
            created_at=first["created_at"],
            user_id=first.get("user_id"),
            version_label=first.get("version_label"),
        )

    def list_embeddings(
        self,
        data_id: Optional[str] = None,
        user_id: str = "",
    ) -> List[EmbeddingSummary]:
        """List embedding summaries, optionally filtered by data_id.

        Uses a direct DB query on ``mem_dog_embeddings`` grouped by
        ``(data_id, user_id)`` instead of scanning all metadata blobs.
        """
        self._check_ai_enabled()
        if data_id:
            summary = self.get_embedding_summary(data_id, user_id=user_id)
            return [summary] if summary else []

        query = (
            self._supa_client.table(self._EMB_TABLE)
            .select("data_id, data_version, ai_engine, model, dimensions, created_at, user_id, version_label, chunk_index")
        )
        if user_id:
            query = query.eq("user_id", user_id)
        try:
            res = query.order("data_id").order("chunk_index").execute()
        except Exception as exc:
            logger.warning("list_embeddings query failed: %s", exc)
            return []

        groups: Dict[str, list] = {}
        for row in res.data or []:
            key = f"{row.get('user_id', '')}:{row.get('data_id', '')}"
            groups.setdefault(key, []).append(row)

        summaries: List[EmbeddingSummary] = []
        for rows in groups.values():
            first = rows[0]
            summaries.append(EmbeddingSummary(
                data_id=first["data_id"],
                data_version=first["data_version"],
                embeddings_count=len(rows),
                ai_engine=first["ai_engine"],
                model=first["model"],
                dimensions=first["dimensions"],
                created_at=first["created_at"],
                user_id=first.get("user_id"),
                version_label=first.get("version_label"),
            ))
        return summaries

    def delete_embeddings(
        self,
        data_id: str,
        user_id: str = "",
        version_label: Optional[str] = None,
    ) -> None:
        self._check_ai_enabled()
        if not user_id:
            return
        query = (
            self._supa_client.table(self._EMB_TABLE)
            .delete()
            .eq("user_id", user_id)
            .eq("data_id", data_id)
        )
        if version_label:
            query = query.eq("version_label", version_label)
        try:
            query.execute()
        except Exception as exc:
            logger.warning("delete_embeddings failed: %s", exc)

    def get_embedding(self, embedding_id: str, user_id: str = "") -> Optional[Embedding]:
        self._check_ai_enabled()
        query = (
            self._supa_client.table(self._EMB_TABLE)
            .select("*")
            .eq("embedding_id", embedding_id)
        )
        if user_id:
            query = query.eq("user_id", user_id)
        try:
            res = query.limit(1).execute()
        except Exception as exc:
            logger.warning("get_embedding query failed: %s", exc)
            return None
        if not res.data:
            return None
        try:
            return Embedding(**res.data[0])
        except Exception as exc:
            logger.warning("Failed to parse embedding row: %s", exc)
            return None

    def delete_embedding(self, embedding_id: str, user_id: str = "") -> bool:
        self._check_ai_enabled()
        if not user_id:
            return False
        try:
            res = (
                self._supa_client.table(self._EMB_TABLE)
                .delete()
                .eq("embedding_id", embedding_id)
                .eq("user_id", user_id)
                .execute()
            )
            return bool(res.data)
        except Exception as exc:
            logger.warning("delete_embedding failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Agent Config overrides — dedicated ``agent_configs`` table
    # ------------------------------------------------------------------

    _ACFG_TABLE = "agent_configs"

    def _acfg_row_to_model(self, row: dict) -> AgentConfig:
        """Convert a Supabase row dict to an AgentConfig model."""
        return AgentConfig(
            config_id=row["config_id"],
            agent_type=row["agent_type"],
            user_id=row.get("user_id"),
            intro=row.get("intro"),
            system_prompt=row.get("system_prompt"),
            output_schema=row.get("output_schema"),
            skills=row.get("skills") or [],
            model_tier=row.get("model_tier"),
            parameters=row.get("parameters") or {},
            version=row.get("version", 1),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )

    def create_agent_config(self, create: AgentConfigCreate, user: str = None) -> AgentConfig:
        self._check_ai_enabled()
        from ulid import ULID
        now = datetime.utcnow().isoformat() + "Z"
        row = {
            "config_id": f"acfg_{ULID()}",
            "agent_type": create.agent_type,
            "user_id": create.user_id,
            "intro": create.intro,
            "system_prompt": create.system_prompt,
            "output_schema": create.output_schema,
            "skills": create.skills,
            "model_tier": create.model_tier,
            "parameters": create.parameters,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        try:
            res = self._supa_client.table(self._ACFG_TABLE).insert(row).execute()
        except Exception as exc:
            raise RuntimeError(f"Failed to create agent config: {exc}")
        if res.data:
            return self._acfg_row_to_model(res.data[0])
        return self._acfg_row_to_model(row)

    def get_agent_config(self, config_id: str, user_id: Optional[str] = None) -> AgentConfig:
        self._check_ai_enabled()
        try:
            res = (
                self._supa_client.table(self._ACFG_TABLE)
                .select("*")
                .eq("config_id", config_id)
                .execute()
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to get agent config: {exc}")
        if not res.data:
            raise FileNotFoundError(f"AgentConfig not found: {config_id}")
        return self._acfg_row_to_model(res.data[0])

    def update_agent_config(self, config_id: str, updates: AgentConfigUpdate, user_id: Optional[str] = None) -> AgentConfig:
        self._check_ai_enabled()
        cfg = self.get_agent_config(config_id, user_id)
        update_data = updates.model_dump(exclude_unset=True)
        patch: Dict[str, object] = {}
        for field, value in update_data.items():
            if value is not None:
                patch[field] = value
        patch["version"] = cfg.version + 1
        patch["updated_at"] = datetime.utcnow().isoformat() + "Z"
        try:
            res = (
                self._supa_client.table(self._ACFG_TABLE)
                .update(patch)
                .eq("config_id", config_id)
                .execute()
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to update agent config: {exc}")
        if res.data:
            return self._acfg_row_to_model(res.data[0])
        return self.get_agent_config(config_id)

    def delete_agent_config(self, config_id: str, user_id: Optional[str] = None) -> bool:
        self._check_ai_enabled()
        try:
            res = (
                self._supa_client.table(self._ACFG_TABLE)
                .delete()
                .eq("config_id", config_id)
                .execute()
            )
            return bool(res.data)
        except Exception as exc:
            logger.warning("delete_agent_config failed: %s", exc)
            return False

    def list_agent_configs(self, user_id: Optional[str] = None, agent_type: Optional[str] = None) -> List[AgentConfig]:
        self._check_ai_enabled()
        query = self._supa_client.table(self._ACFG_TABLE).select("*")
        if user_id:
            # Include both user-specific and system defaults
            query = query.or_(f"user_id.eq.{user_id},user_id.is.null")
        if agent_type:
            query = query.eq("agent_type", agent_type)
        try:
            res = query.order("updated_at", desc=True).execute()
        except Exception as exc:
            logger.warning("list_agent_configs query failed: %s", exc)
            return []
        return [self._acfg_row_to_model(row) for row in (res.data or [])]

    def resolve_agent_config(self, agent_type: str, user_id: Optional[str] = None) -> Optional[AgentConfig]:
        self._check_ai_enabled()
        # Try user-specific first
        if user_id:
            try:
                res = (
                    self._supa_client.table(self._ACFG_TABLE)
                    .select("*")
                    .eq("agent_type", agent_type)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    return self._acfg_row_to_model(res.data[0])
            except Exception as exc:
                logger.warning("resolve_agent_config user query failed: %s", exc)
        # Fall back to system default (user_id IS NULL)
        try:
            res = (
                self._supa_client.table(self._ACFG_TABLE)
                .select("*")
                .eq("agent_type", agent_type)
                .is_("user_id", "null")
                .limit(1)
                .execute()
            )
            if res.data:
                return self._acfg_row_to_model(res.data[0])
        except Exception as exc:
            logger.warning("resolve_agent_config system query failed: %s", exc)
        return None

    def similarity_search(
        self, query_vector: List[float], limit: int = 5, user_id: str = "",
        memory_id: str = "",
        project_id: str = "",
    ) -> List[dict]:
        """Cosine similarity search using pgvector on ``mem_dog_embeddings``.

        Returns dicts with ``embedding_id``, ``data_id``, ``chunk_text``,
        ``similarity``, and optional ``page``, scoped to ``user_id`` when provided.
        When ``memory_id`` is set, restricts results to that memory's data_ids.
        When ``project_id`` is set, passes ``filter_project_id`` to the RPC when
        available (falls back to base blob-scan with project filter).
        Falls back to the base blob-scan implementation on any error.
        """
        self._check_ai_enabled()

        # Resolve memory_id → data_ids filter
        filter_data_ids: Optional[List[str]] = None
        if memory_id:
            memory = self.get_memory(memory_id, user_id=user_id or config.DEFAULT_USER_ID)
            if not memory or not memory.data_ids:
                return []
            filter_data_ids = memory.data_ids

        try:
            vec_str = "[" + ",".join(str(v) for v in query_vector) + "]"
            rpc_params: Dict[str, object] = {
                "query_embedding": vec_str,
                "match_count": limit,
            }
            if user_id:
                rpc_params["filter_user_id"] = user_id
            if filter_data_ids is not None:
                rpc_params["filter_data_ids"] = filter_data_ids
            if project_id:
                rpc_params["filter_project_id"] = project_id
            res = self._supa_client.rpc("match_embeddings", rpc_params).execute()
            results: List[dict] = []
            for row in res.data or []:
                hit = {
                    "embedding_id": row.get("embedding_id", ""),
                    "data_id": row.get("data_id", ""),
                    "chunk_text": row.get("chunk_text", ""),
                    "similarity": float(row.get("similarity", 0.0)),
                }
                if row.get("page") is not None:
                    hit["page"] = row.get("page")
                results.append(hit)
            return results
        except Exception as exc:
            logger.debug(
                "pgvector similarity_search RPC unavailable (%s), falling back to base implementation",
                exc,
            )
            return super().similarity_search(
                query_vector, limit=limit, memory_id=memory_id, user_id=user_id,
                project_id=project_id,
            )

    def hybrid_search(
        self, query_vector: List[float], query_text: str, limit: int = 5,
        user_id: str = "", memory_id: str = "",
        vector_weight: float = 0.5, fts_weight: float = 0.5,
        project_id: str = "",
    ) -> List[dict]:
        """Hybrid cosine + BM25 search via ``match_embeddings_hybrid`` RPC."""
        self._check_ai_enabled()

        filter_data_ids: Optional[List[str]] = None
        if memory_id:
            memory = self.get_memory(memory_id, user_id=user_id or config.DEFAULT_USER_ID)
            if not memory or not memory.data_ids:
                return []
            filter_data_ids = memory.data_ids

        try:
            vec_str = "[" + ",".join(str(v) for v in query_vector) + "]"
            rpc_params: Dict[str, object] = {
                "query_embedding": vec_str,
                "query_text": query_text,
                "match_count": limit,
                "vector_weight": vector_weight,
                "fts_weight": fts_weight,
            }
            if user_id:
                rpc_params["filter_user_id"] = user_id
            if filter_data_ids is not None:
                rpc_params["filter_data_ids"] = filter_data_ids
            res = self._supa_client.rpc("match_embeddings_hybrid", rpc_params).execute()
            results = [
                {
                    "embedding_id": row.get("embedding_id", ""),
                    "data_id": row.get("data_id", ""),
                    "chunk_text": row.get("chunk_text", ""),
                    "similarity": float(row.get("similarity", 0.0)),
                    "fts_rank": float(row.get("fts_rank", 0.0)) if row.get("fts_rank") is not None else None,
                    "rrf_score": float(row.get("rrf_score", 0.0)) if row.get("rrf_score") is not None else None,
                    "search_type": row.get("search_type", "both"),
                    **({"page": row["page"]} if row.get("page") is not None else {}),
                    **({"project_id": row["project_id"]} if row.get("project_id") is not None else {}),
                }
                for row in res.data or []
            ]
            if project_id:
                results = [r for r in results if r.get("project_id") == project_id]
            return results
        except Exception as exc:
            logger.debug("hybrid_search RPC unavailable (%s), falling back to base", exc)
            return super().hybrid_search(
                query_vector, query_text, limit=limit, user_id=user_id,
                memory_id=memory_id, project_id=project_id,
            )

    def fts_search(
        self, query_text: str, limit: int = 5, user_id: str = "", memory_id: str = "",
    ) -> List[dict]:
        """BM25 full-text search via ``match_embeddings_fts`` RPC."""
        self._check_ai_enabled()

        filter_data_ids: Optional[List[str]] = None
        if memory_id:
            memory = self.get_memory(memory_id, user_id=user_id or config.DEFAULT_USER_ID)
            if not memory or not memory.data_ids:
                return []
            filter_data_ids = memory.data_ids

        try:
            rpc_params: Dict[str, object] = {
                "query_text": query_text,
                "match_count": limit,
            }
            if user_id:
                rpc_params["filter_user_id"] = user_id
            if filter_data_ids is not None:
                rpc_params["filter_data_ids"] = filter_data_ids
            res = self._supa_client.rpc("match_embeddings_fts", rpc_params).execute()
            return [
                {
                    "embedding_id": row.get("embedding_id", ""),
                    "data_id": row.get("data_id", ""),
                    "chunk_text": row.get("chunk_text", ""),
                    "fts_rank": float(row.get("fts_rank", 0.0)),
                    "similarity": 0.0,
                    "rrf_score": None,
                    "search_type": "fts",
                    **({"page": row["page"]} if row.get("page") is not None else {}),
                }
                for row in res.data or []
            ]
        except Exception as exc:
            logger.debug("fts_search RPC unavailable (%s), returning empty", exc)
            return []

    def _compute_user_embedding_stats(
        self, user_id: str, user_data_ids: set,
    ) -> "PerUserEmbeddingStats":
        """Compute embedding stats from the pgvector table instead of blobs."""
        embedding_stats = PerUserEmbeddingStats()
        if not config.is_ai_enabled():
            return embedding_stats
        try:
            res = (
                self._supa_client.table(self._EMB_TABLE)
                .select("ai_engine, model")
                .eq("user_id", user_id)
                .execute()
            )
            for row in res.data or []:
                embedding_stats.total_embeddings += 1
                eng = row.get("ai_engine", "unknown")
                embedding_stats.by_engine[eng] = embedding_stats.by_engine.get(eng, 0) + 1
                mdl = row.get("model", "unknown")
                embedding_stats.by_model[mdl] = embedding_stats.by_model.get(mdl, 0) + 1
        except Exception as exc:
            logger.debug("Supabase embedding stats query failed: %s", exc)
        return embedding_stats

    # ------------------------------------------------------------------
    # User / Profile overrides — dedicated ``profiles`` table
    # ------------------------------------------------------------------

    _PROFILES_TABLE = "profiles"

    @staticmethod
    def _profile_row_to_user(row: dict) -> User:
        """Convert a Supabase ``profiles`` row to a :class:`User` model."""
        return User(
            user_id=row["user_id"],
            username=row["username"],
            email=row.get("email", ""),
            display_name=row.get("display_name"),
            role=row.get("role", "user"),
            status=row.get("status", "active"),
            metadata=row.get("metadata") or {},
            data_count=row.get("data_count", 0),
            storage_used_bytes=row.get("storage_used_bytes", 0),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
            last_active_at=row.get("last_active_at"),
            default_org_id=row.get("default_org_id"),
            default_project_id=row.get("default_project_id"),
        )

    def ensure_default_user(self) -> None:  # type: ignore[override]
        if not config.is_user_management_enabled():
            return
        existing = self.get_user(config.DEFAULT_USER_ID)
        if existing is None:
            logger.info(
                "Creating default user in profiles table (username=%s, user_id=%s)",
                self._DEFAULT_USERNAME, config.DEFAULT_USER_ID,
            )
            now = datetime.utcnow().isoformat() + "Z"
            row = {
                "user_id": config.DEFAULT_USER_ID,
                "username": self._DEFAULT_USERNAME,
                "email": f"{self._DEFAULT_USERNAME}@localhost",
                "display_name": self._DEFAULT_USERNAME.capitalize(),
                "role": "user",
                "status": "active",
                "metadata": {},
                "data_count": 0,
                "storage_used_bytes": 0,
                "created_at": now,
                "updated_at": now,
                "last_active_at": now,
            }
            try:
                self._supa_client.table(self._PROFILES_TABLE).upsert(row).execute()
            except Exception as exc:
                logger.warning("Failed to upsert default user in profiles: %s", exc)

        # Ensure default timeline memory exists
        if config.is_memories_enabled():
            self.get_or_create_default_timeline_memory(config.DEFAULT_USER_ID)

        # Ensure credentials blob exists (kept in blob storage)
        creds_path = f"users/{config.DEFAULT_USER_ID}/credentials.json"
        if not self.user_store.exists(creds_path):
            now = datetime.utcnow().isoformat() + "Z"
            credentials = UserCredentials(
                user_id=config.DEFAULT_USER_ID, api_keys=[], created_at=now, updated_at=now,
            )
            self.user_store.write(
                creds_path,
                json.dumps(credentials.model_dump(), indent=2).encode("utf-8"),
                "application/json",
            )

    def _create_user_with_id(  # type: ignore[override]
        self, user_id: str, username: str, email: str, display_name: str,
    ) -> User:
        self._check_user_management_enabled()
        now = datetime.utcnow().isoformat() + "Z"
        row = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "display_name": display_name,
            "role": "user",
            "status": "active",
            "metadata": {},
            "data_count": 0,
            "storage_used_bytes": 0,
            "created_at": now,
            "updated_at": now,
            "last_active_at": now,
        }
        try:
            res = self._supa_client.table(self._PROFILES_TABLE).insert(row).execute()
        except Exception as exc:
            raise RuntimeError(f"Failed to create user in profiles table: {exc}")
        user = self._profile_row_to_user(res.data[0] if res.data else row)

        # Initialise credentials blob
        credentials = UserCredentials(
            user_id=user_id, api_keys=[], created_at=now, updated_at=now,
        )
        creds_path = f"users/{user_id}/credentials.json"
        self.user_store.write(
            creds_path,
            json.dumps(credentials.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        return user

    def create_user(self, user_create: UserCreate) -> User:  # type: ignore[override]
        self._check_user_management_enabled()
        now = datetime.utcnow().isoformat() + "Z"
        user_id = user_create.user_id or str(uuid.uuid4())
        row = {
            "user_id": user_id,
            "username": user_create.username,
            "email": user_create.email,
            "display_name": user_create.display_name or user_create.username,
            "role": user_create.role.value if hasattr(user_create.role, "value") else user_create.role,
            "status": "active",
            "metadata": user_create.metadata,
            "data_count": 0,
            "storage_used_bytes": 0,
            "created_at": now,
            "updated_at": now,
            "last_active_at": now,
        }
        if user_create.default_org_id:
            row["default_org_id"] = user_create.default_org_id
        if user_create.default_project_id:
            row["default_project_id"] = user_create.default_project_id
        try:
            res = self._supa_client.table(self._PROFILES_TABLE).insert(row).execute()
        except Exception as exc:
            if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
                raise ValueError(f"Username '{user_create.username}' already exists")
            raise RuntimeError(f"Failed to create user: {exc}")
        user = self._profile_row_to_user(res.data[0] if res.data else row)

        # Initialise credentials blob
        credentials = UserCredentials(
            user_id=user_id, api_keys=[], created_at=now, updated_at=now,
        )
        creds_path = f"users/{user_id}/credentials.json"
        self.user_store.write(
            creds_path,
            json.dumps(credentials.model_dump(), indent=2).encode("utf-8"),
            "application/json",
        )
        return user

    def set_user_defaults(
        self,
        user_id: str,
        *,
        default_org_id: Optional[str] = None,
        default_project_id: Optional[str] = None,
    ) -> Optional[User]:
        self._check_user_management_enabled()
        patch: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat() + "Z"}
        if default_org_id is not None:
            patch["default_org_id"] = default_org_id
        if default_project_id is not None:
            patch["default_project_id"] = default_project_id
        try:
            self._supa_client.table(self._PROFILES_TABLE).update(patch).eq(
                "user_id", user_id
            ).execute()
        except Exception as exc:
            logger.warning("set_user_defaults failed: %s", exc)
            return None
        return self.get_user(user_id)

    def get_user(self, user_id: str) -> Optional[User]:  # type: ignore[override]
        self._check_user_management_enabled()
        try:
            res = (
                self._supa_client.table(self._PROFILES_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.warning("get_user from profiles table failed: %s", exc)
            return None
        if not res.data:
            return None
        return self._profile_row_to_user(res.data[0])

    def get_user_by_username(self, username: str) -> Optional[User]:  # type: ignore[override]
        self._check_user_management_enabled()
        try:
            res = (
                self._supa_client.table(self._PROFILES_TABLE)
                .select("*")
                .eq("username", username)
                .execute()
            )
        except Exception as exc:
            logger.warning("get_user_by_username failed: %s", exc)
            return None
        if not res.data:
            return None
        return self._profile_row_to_user(res.data[0])

    def update_user(self, user_id: str, user_update: UserUpdate) -> Optional[User]:  # type: ignore[override]
        self._check_user_management_enabled()
        update_data = user_update.model_dump(exclude_unset=True)
        if not update_data:
            return self.get_user(user_id)

        patch: Dict[str, object] = {}
        for field, value in update_data.items():
            if value is not None:
                # Convert enums to their string values
                patch[field] = value.value if hasattr(value, "value") else value
        patch["updated_at"] = datetime.utcnow().isoformat() + "Z"

        try:
            res = (
                self._supa_client.table(self._PROFILES_TABLE)
                .update(patch)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
                raise ValueError("Username already exists")
            raise RuntimeError(f"Failed to update user: {exc}")
        if not res.data:
            return None
        return self._profile_row_to_user(res.data[0])

    def delete_user(self, user_id: str) -> bool:  # type: ignore[override]
        self._check_user_management_enabled()
        try:
            res = (
                self._supa_client.table(self._PROFILES_TABLE)
                .delete()
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as exc:
            logger.warning("delete_user from profiles failed: %s", exc)
            return False
        if not res.data:
            return False

        # Clean up blob storage (credentials, etc.)
        prefix = f"users/{user_id}/"
        try:
            blob_infos = self.user_store.list_blobs(prefix=prefix)
            for info in blob_infos:
                try:
                    self.user_store.delete(info.name)
                except Exception:
                    pass
        except Exception:
            pass
        return True

    def list_users(self, limit: int = 50, offset: int = 0) -> Tuple[List[User], int]:  # type: ignore[override]
        self._check_user_management_enabled()
        try:
            # Get total count
            count_res = (
                self._supa_client.table(self._PROFILES_TABLE)
                .select("user_id", count="exact")
                .execute()
            )
            total = count_res.count if count_res.count is not None else 0

            # Get paginated results
            res = (
                self._supa_client.table(self._PROFILES_TABLE)
                .select("*")
                .order("created_at")
                .range(offset, offset + limit - 1)
                .execute()
            )
            users = [self._profile_row_to_user(row) for row in (res.data or [])]
            return users, total
        except Exception as exc:
            logger.warning("list_users from profiles failed: %s", exc)
            return [], 0

    def update_user_activity(self, user_id: str) -> None:  # type: ignore[override]
        self._check_user_management_enabled()
        now = datetime.utcnow().isoformat() + "Z"
        try:
            self._supa_client.table(self._PROFILES_TABLE).update(
                {"last_active_at": now}
            ).eq("user_id", user_id).execute()
        except Exception as exc:
            logger.debug("update_user_activity failed: %s", exc)

    def update_user_stats(self, user_id: str, data_count_delta: int = 0, storage_delta: int = 0) -> None:  # type: ignore[override]
        self._check_user_management_enabled()
        user = self.get_user(user_id)
        if not user:
            return
        patch = {
            "data_count": max(0, user.data_count + data_count_delta),
            "storage_used_bytes": max(0, user.storage_used_bytes + storage_delta),
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        try:
            self._supa_client.table(self._PROFILES_TABLE).update(patch).eq("user_id", user_id).execute()
        except Exception as exc:
            logger.debug("update_user_stats failed: %s", exc)

    # ------------------------------------------------------------------
    # API Key overrides — dedicated ``api_keys`` table (O(1) validation)
    # ------------------------------------------------------------------

    _API_KEYS_TABLE = "api_keys"

    def create_api_key(self, user_id: str, key_create: APIKeyCreate) -> Optional[APIKeyResponse]:  # type: ignore[override]
        self._check_user_management_enabled()
        import secrets
        import hashlib

        now = datetime.utcnow().isoformat() + "Z"
        key_id = str(uuid.uuid4())[:8]
        raw_key = f"md_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        expires_at = None
        if key_create.expires_in_days:
            expiry_date = datetime.utcnow() + timedelta(days=key_create.expires_in_days)
            expires_at = expiry_date.isoformat() + "Z"

        row = {
            "key_id": key_id,
            "user_id": user_id,
            "key_hash": key_hash,
            "name": key_create.name,
            "created_at": now,
            "updated_at": now,
        }
        if expires_at:
            row["expires_at"] = expires_at

        try:
            self._supa_client.table(self._API_KEYS_TABLE).insert(row).execute()
        except Exception as exc:
            logger.warning("create_api_key insert failed: %s", exc)
            return None

        return APIKeyResponse(
            key_id=key_id,
            name=key_create.name,
            key=raw_key,
            created_at=now,
            expires_at=expires_at,
        )

    def list_api_keys(self, user_id: str) -> List[APIKeyResponse]:  # type: ignore[override]
        self._check_user_management_enabled()
        try:
            res = (
                self._supa_client.table(self._API_KEYS_TABLE)
                .select("key_id, name, created_at, expires_at")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception as exc:
            logger.warning("list_api_keys query failed: %s", exc)
            return []
        return [
            APIKeyResponse(
                key_id=r["key_id"],
                name=r["name"],
                key=None,
                created_at=r["created_at"],
                expires_at=r.get("expires_at"),
            )
            for r in (res.data or [])
        ]

    def delete_api_key(self, user_id: str, key_id: str) -> bool:  # type: ignore[override]
        self._check_user_management_enabled()
        try:
            res = (
                self._supa_client.table(self._API_KEYS_TABLE)
                .delete()
                .eq("key_id", key_id)
                .eq("user_id", user_id)
                .execute()
            )
            return bool(res.data)
        except Exception as exc:
            logger.warning("delete_api_key failed: %s", exc)
            return False

    def validate_api_key(self, api_key: str) -> Optional[str]:  # type: ignore[override]
        """O(1) validation: hash the key → query the unique index → return user_id."""
        import hashlib

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        try:
            res = (
                self._supa_client.table(self._API_KEYS_TABLE)
                .select("user_id, expires_at")
                .eq("key_hash", key_hash)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            logger.warning("validate_api_key query failed: %s", exc)
            return None
        if not res.data:
            return None
        row = res.data[0]
        # Check expiry
        if row.get("expires_at"):
            from dateutil.parser import isoparse
            try:
                expiry = isoparse(row["expires_at"]).replace(tzinfo=None)
                if datetime.utcnow() > expiry:
                    return None
            except Exception:
                pass
        return row["user_id"]

    # ------------------------------------------------------------------
    # Graph Memory — entity/relationship storage (Supabase overrides)
    # ------------------------------------------------------------------

    _ENTITIES_TABLE = "mem_dog_entities"
    _RELATIONSHIPS_TABLE = "mem_dog_relationships"
    _ENTITY_DATA_MAP_TABLE = "mem_dog_entity_data_mapping"

    def upsert_entity(
        self, *, data_id: str, user_id: str, entity_type: str, entity_name: str,
        confidence: float = 1.0, metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        from ulid import ULID
        canonical = entity_name.strip().lower()
        now = datetime.utcnow().isoformat() + "Z"
        row = {
            "entity_id": f"ent_{ULID()}",
            "data_id": data_id,
            "user_id": user_id,
            "entity_type": entity_type,
            "entity_name": entity_name.strip(),
            "canonical_form": canonical,
            "confidence": confidence,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        try:
            res = (
                self._supa_client.table(self._ENTITIES_TABLE)
                .upsert(row, on_conflict="user_id,entity_type,canonical_form")
                .execute()
            )
            entity = res.data[0] if res.data else row
            # Ensure entity-data mapping exists
            map_row = {
                "mapping_id": f"map_{ULID()}",
                "user_id": user_id,
                "entity_id": entity["entity_id"],
                "data_id": data_id,
                "created_at": now,
            }
            try:
                self._supa_client.table(self._ENTITY_DATA_MAP_TABLE).upsert(
                    map_row, on_conflict="entity_id,data_id"
                ).execute()
            except Exception as exc:
                logger.debug("entity-data mapping upsert failed: %s", exc)
            return entity
        except Exception as exc:
            logger.warning("upsert_entity failed: %s", exc)
            return None

    def search_entities(
        self, query: str, user_id: str, *, entity_type: Optional[str] = None, limit: int = 20,
    ) -> List[dict]:
        try:
            params: Dict[str, object] = {
                "query_text": query,
                "filter_user_id": user_id,
                "match_count": limit,
            }
            if entity_type:
                params["filter_type"] = entity_type
            res = self._supa_client.rpc("search_entities", params).execute()
            return res.data or []
        except Exception as exc:
            logger.warning("search_entities RPC failed: %s", exc)
            return []

    def get_data_entities(self, data_id: str, user_id: str) -> List[dict]:
        try:
            res = (
                self._supa_client.table(self._ENTITIES_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("data_id", data_id)
                .execute()
            )
            return res.data or []
        except Exception as exc:
            logger.warning("get_data_entities failed: %s", exc)
            return []

    def get_entity(self, entity_id: str, user_id: str) -> Optional[dict]:
        try:
            res = (
                self._supa_client.table(self._ENTITIES_TABLE)
                .select("*")
                .eq("entity_id", entity_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            return res.data[0] if res.data else None
        except Exception as exc:
            logger.warning("get_entity failed: %s", exc)
            return None

    def get_entity_relationships(self, entity_id: str, user_id: str) -> List[dict]:
        try:
            res = (
                self._supa_client.table(self._RELATIONSHIPS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .or_(f"source_entity_id.eq.{entity_id},target_entity_id.eq.{entity_id}")
                .execute()
            )
            return res.data or []
        except Exception as exc:
            logger.warning("get_entity_relationships failed: %s", exc)
            return []

    def create_relationship(
        self, *, user_id: str, data_id: str, source_entity_id: str,
        target_entity_id: str, rel_type: str, strength: float = 1.0,
        description: Optional[str] = None,
    ) -> Optional[dict]:
        from ulid import ULID
        now = datetime.utcnow().isoformat() + "Z"
        row = {
            "rel_id": f"rel_{ULID()}",
            "user_id": user_id,
            "data_id": data_id,
            "source_entity_id": source_entity_id,
            "target_entity_id": target_entity_id,
            "rel_type": rel_type,
            "strength": strength,
            "description": description,
            "created_at": now,
        }
        try:
            res = (
                self._supa_client.table(self._RELATIONSHIPS_TABLE)
                .upsert(row, on_conflict="user_id,source_entity_id,target_entity_id,rel_type,data_id")
                .execute()
            )
            return res.data[0] if res.data else row
        except Exception as exc:
            logger.warning("create_relationship failed: %s", exc)
            return None

    def delete_data_entities(self, data_id: str, user_id: str) -> int:
        try:
            res = (
                self._supa_client.table(self._ENTITIES_TABLE)
                .delete()
                .eq("user_id", user_id)
                .eq("data_id", data_id)
                .execute()
            )
            return len(res.data) if res.data else 0
        except Exception as exc:
            logger.warning("delete_data_entities failed: %s", exc)
            return 0

    def find_related_data_ids(self, entity_ids: List[str], user_id: str, limit: int = 50) -> List[str]:
        try:
            res = self._supa_client.rpc("find_related_data", {
                "entity_ids": entity_ids,
                "filter_user_id": user_id,
                "match_count": limit,
            }).execute()
            seen: set = set()
            result: List[str] = []
            for row in res.data or []:
                did = row.get("data_id")
                if did and did not in seen:
                    seen.add(did)
                    result.append(did)
            return result
        except Exception as exc:
            logger.warning("find_related_data_ids RPC failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Organization & Project CRUD (Supabase tables)
    # ------------------------------------------------------------------

    _ORG_TABLE = "organizations"
    _PROJECT_TABLE = "projects"
    _ORG_MEMBERS_TABLE = "org_members"

    def _org_row_to_model(self, row: dict):
        from app.models import Organization
        return Organization(
            org_id=row["org_id"],
            name=row["name"],
            display_name=row.get("display_name"),
            owner_user_id=row["owner_user_id"],
            metadata=row.get("metadata") or {},
            status=row.get("status", "active"),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
        )

    def _project_row_to_model(self, row: dict):
        from app.models import Project
        return Project(
            project_id=row["project_id"],
            org_id=row["org_id"],
            name=row["name"],
            display_name=row.get("display_name"),
            description=row.get("description"),
            metadata=row.get("metadata") or {},
            status=row.get("status", "active"),
            created_at=str(row.get("created_at", "")),
            updated_at=str(row.get("updated_at", "")),
        )

    def _member_row_to_model(self, row: dict):
        from app.models import OrgMember, OrgRole
        return OrgMember(
            org_id=row["org_id"],
            user_id=row["user_id"],
            role=OrgRole(row.get("role", "member")),
            created_at=str(row.get("created_at", "")),
        )

    def create_organization(self, org_create, owner_user_id: str):
        from ulid import ULID
        now = datetime.utcnow().isoformat() + "Z"
        org_id = f"org_{ULID()}"
        row = {
            "org_id": org_id,
            "name": org_create.name,
            "display_name": org_create.display_name or org_create.name,
            "owner_user_id": owner_user_id,
            "metadata": org_create.metadata,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        try:
            res = self._supa_client.table(self._ORG_TABLE).insert(row).execute()
        except Exception as exc:
            if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
                raise ValueError(f"Organization name '{org_create.name}' already exists")
            raise
        # Add owner as member with owner role
        self.add_org_member(org_id, owner_user_id, "owner")
        return self._org_row_to_model(res.data[0] if res.data else row)

    def get_organization(self, org_id: str):
        try:
            res = (
                self._supa_client.table(self._ORG_TABLE)
                .select("*").eq("org_id", org_id).execute()
            )
        except Exception as exc:
            logger.warning("get_organization failed: %s", exc)
            return None
        if not res.data:
            return None
        return self._org_row_to_model(res.data[0])

    def list_organizations(self, user_id: str):
        try:
            # Get org_ids the user belongs to
            mem_res = (
                self._supa_client.table(self._ORG_MEMBERS_TABLE)
                .select("org_id").eq("user_id", user_id).execute()
            )
            org_ids = [r["org_id"] for r in (mem_res.data or [])]
            if not org_ids:
                return []
            res = (
                self._supa_client.table(self._ORG_TABLE)
                .select("*").in_("org_id", org_ids)
                .eq("status", "active").execute()
            )
            return [self._org_row_to_model(r) for r in (res.data or [])]
        except Exception as exc:
            logger.warning("list_organizations failed: %s", exc)
            return []

    def update_organization(self, org_id: str, org_update):
        now = datetime.utcnow().isoformat() + "Z"
        patch = {"updated_at": now}
        if org_update.name is not None:
            patch["name"] = org_update.name
        if org_update.display_name is not None:
            patch["display_name"] = org_update.display_name
        if org_update.metadata is not None:
            patch["metadata"] = org_update.metadata
        if org_update.status is not None:
            patch["status"] = org_update.status
        res = (
            self._supa_client.table(self._ORG_TABLE)
            .update(patch).eq("org_id", org_id).execute()
        )
        return self._org_row_to_model(res.data[0]) if res.data else self.get_organization(org_id)

    def delete_organization(self, org_id: str):
        self._supa_client.table(self._ORG_TABLE).delete().eq("org_id", org_id).execute()

    def add_org_member(self, org_id: str, user_id: str, role):
        now = datetime.utcnow().isoformat() + "Z"
        role_val = role.value if hasattr(role, "value") else str(role)
        row = {
            "org_id": org_id,
            "user_id": user_id,
            "role": role_val,
            "created_at": now,
        }
        try:
            res = self._supa_client.table(self._ORG_MEMBERS_TABLE).upsert(row).execute()
        except Exception as exc:
            if "duplicate key" in str(exc).lower():
                raise ValueError(f"User {user_id} is already a member of org {org_id}")
            raise
        return self._member_row_to_model(res.data[0] if res.data else row)

    def get_org_member(self, org_id: str, user_id: str):
        try:
            res = (
                self._supa_client.table(self._ORG_MEMBERS_TABLE)
                .select("*").eq("org_id", org_id).eq("user_id", user_id).execute()
            )
        except Exception:
            return None
        if not res.data:
            return None
        return self._member_row_to_model(res.data[0])

    def list_org_members(self, org_id: str):
        res = (
            self._supa_client.table(self._ORG_MEMBERS_TABLE)
            .select("*").eq("org_id", org_id).execute()
        )
        return [self._member_row_to_model(r) for r in (res.data or [])]

    def update_org_member_role(self, org_id: str, user_id: str, role):
        role_val = role.value if hasattr(role, "value") else str(role)
        res = (
            self._supa_client.table(self._ORG_MEMBERS_TABLE)
            .update({"role": role_val})
            .eq("org_id", org_id).eq("user_id", user_id).execute()
        )
        if not res.data:
            return None
        return self._member_row_to_model(res.data[0])

    def remove_org_member(self, org_id: str, user_id: str):
        self._supa_client.table(self._ORG_MEMBERS_TABLE).delete().eq("org_id", org_id).eq("user_id", user_id).execute()

    def create_project(self, org_id: str, project_create):
        from ulid import ULID
        now = datetime.utcnow().isoformat() + "Z"
        project_id = f"proj_{ULID()}"
        row = {
            "project_id": project_id,
            "org_id": org_id,
            "name": project_create.name,
            "display_name": project_create.display_name or project_create.name,
            "description": project_create.description,
            "metadata": project_create.metadata,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        try:
            res = self._supa_client.table(self._PROJECT_TABLE).insert(row).execute()
        except Exception as exc:
            if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
                raise ValueError(f"Project name '{project_create.name}' already exists in this org")
            raise
        return self._project_row_to_model(res.data[0] if res.data else row)

    def get_project(self, project_id: str):
        try:
            res = (
                self._supa_client.table(self._PROJECT_TABLE)
                .select("*").eq("project_id", project_id).execute()
            )
        except Exception as exc:
            logger.warning("get_project failed: %s", exc)
            return None
        if not res.data:
            return None
        return self._project_row_to_model(res.data[0])

    def list_projects(self, org_id: str):
        res = (
            self._supa_client.table(self._PROJECT_TABLE)
            .select("*").eq("org_id", org_id)
            .eq("status", "active").execute()
        )
        return [self._project_row_to_model(r) for r in (res.data or [])]

    def update_project(self, project_id: str, project_update):
        now = datetime.utcnow().isoformat() + "Z"
        patch = {"updated_at": now}
        if project_update.name is not None:
            patch["name"] = project_update.name
        if project_update.display_name is not None:
            patch["display_name"] = project_update.display_name
        if project_update.description is not None:
            patch["description"] = project_update.description
        if project_update.metadata is not None:
            patch["metadata"] = project_update.metadata
        if project_update.status is not None:
            patch["status"] = project_update.status
        res = (
            self._supa_client.table(self._PROJECT_TABLE)
            .update(patch).eq("project_id", project_id).execute()
        )
        return self._project_row_to_model(res.data[0]) if res.data else self.get_project(project_id)

    def delete_project(self, project_id: str):
        self._supa_client.table(self._PROJECT_TABLE).delete().eq("project_id", project_id).execute()


# =============================================================================
# Global storage instance
# =============================================================================

storage_instance: Optional[BaseStorage] = None


def get_storage() -> BaseStorage:
    """Get or create the singleton Storage instance (blob storage + optional Redis/Postgres stores)."""
    global storage_instance
    if storage_instance is None:
        if config.STORAGE_BACKEND == "supabase":
            storage_instance = SupabaseStorage()
        elif config.is_redis_store_enabled() or config.is_postgres_store_enabled() or config.is_supabase_store_enabled() or config.is_gcs_store_enabled():
            storage_instance = RedisStorage()
        elif config.STORAGE_BACKEND == "local":
            storage_instance = LocalStorage()
        else:
            storage_instance = GCSStorage()
    return storage_instance


# Type alias for code that types against the storage interface (e.g. tracking.py).
Storage = BaseStorage

from pydantic import BaseModel, model_validator, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


# =============================================================================
# Memory Type System
# =============================================================================

class MemoryType(str, Enum):
    """
    Memory sub-types based on mem0 memory layers.

    Short-term:
    - TIMELINE: Activity log of user actions (replaces old timeline store)
    - SESSION: Short-lived multi-step task context (replaces old sessions store)
    - CONVERSATION: In-flight messages inside a single turn

    Long-term:
    - USER: Long-lived knowledge tied to a person, account, or workspace
    - ORGANIZATIONAL: Shared context available to multiple agents or teams
    - FACTUAL: User preferences, account details, and domain facts
    - EPISODIC: Summaries of past interactions or completed tasks
    - SEMANTIC: Relationships between concepts for reasoning
    - CUSTOM: User-created memories with custom sub_type classification
    - TRACING: Per-invocation trace container for Otel spans
    """
    TIMELINE = "timeline"
    SESSION = "session"
    CONVERSATION = "conversation"
    USER = "user"
    ORGANIZATIONAL = "organizational"
    FACTUAL = "factual"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    CUSTOM = "custom"
    TRACING = "tracing"


class MemoryDuration(str, Enum):
    """Whether a memory type is short-term or long-term."""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


# Mapping from MemoryType to MemoryDuration
MEMORY_TYPE_DURATION: Dict[str, str] = {
    MemoryType.TIMELINE: MemoryDuration.SHORT_TERM,
    MemoryType.SESSION: MemoryDuration.SHORT_TERM,
    MemoryType.CONVERSATION: MemoryDuration.SHORT_TERM,
    MemoryType.USER: MemoryDuration.LONG_TERM,
    MemoryType.ORGANIZATIONAL: MemoryDuration.LONG_TERM,
    MemoryType.FACTUAL: MemoryDuration.LONG_TERM,
    MemoryType.EPISODIC: MemoryDuration.LONG_TERM,
    MemoryType.SEMANTIC: MemoryDuration.LONG_TERM,
    MemoryType.CUSTOM: MemoryDuration.LONG_TERM,
    MemoryType.TRACING: MemoryDuration.SHORT_TERM,
}


class MemoryCategory(str, Enum):
    """Mem0-aligned memory categories grouping the 10 granular types."""
    CONVERSATION = "conversation"
    SESSION = "session"
    USER = "user"
    ORGANIZATIONAL = "organizational"


# Mapping from MemoryType to MemoryCategory (Mem0 alignment)
MEMORY_TYPE_CATEGORY: Dict[str, str] = {
    MemoryType.CONVERSATION: MemoryCategory.CONVERSATION,
    MemoryType.TIMELINE: MemoryCategory.SESSION,
    MemoryType.SESSION: MemoryCategory.SESSION,
    MemoryType.TRACING: MemoryCategory.SESSION,
    MemoryType.USER: MemoryCategory.USER,
    MemoryType.FACTUAL: MemoryCategory.USER,
    MemoryType.EPISODIC: MemoryCategory.USER,
    MemoryType.SEMANTIC: MemoryCategory.USER,
    MemoryType.CUSTOM: MemoryCategory.USER,
    MemoryType.ORGANIZATIONAL: MemoryCategory.ORGANIZATIONAL,
}


class AccessLevel(str, Enum):
    """Access level for memory containers."""
    PRIVATE = "private"
    SHARED = "shared"
    PUBLIC = "public"
    RESTRICTED = "restricted"


# Default TTL in hours per memory type (None = never expires)
DEFAULT_TTL_HOURS: Dict[str, Optional[int]] = {
    MemoryType.CONVERSATION: 1,
    MemoryType.SESSION: 24,
    MemoryType.TIMELINE: 168,   # 7 days
    MemoryType.TRACING: 72,     # 3 days
    MemoryType.USER: None,
    MemoryType.FACTUAL: None,
    MemoryType.EPISODIC: None,
    MemoryType.SEMANTIC: None,
    MemoryType.CUSTOM: None,
    MemoryType.ORGANIZATIONAL: None,
}

# Predetermined sub_types for custom memories (validation and UI)
PREDETERMINED_SUB_TYPES = [
    "legal",
    "hr",
    "customer",
    "finance",
    "engineering",
    "support",
    "sales",
    "marketing",
]


class VersionInfo(BaseModel):
    version: int
    timestamp: str
    size: int
    content_type: str
    # URL-safe version label matching the storage path (e.g. "ver_20250225T143022Z")
    version_label: Optional[str] = None


class DataDeviceInfo(BaseModel):
    """Device information captured when data is uploaded or an event is processed."""
    # Existing fields
    device_type: Optional[str] = None   # desktop, mobile, tablet
    os: Optional[str] = None            # Windows, macOS, Linux, iOS, Android
    browser: Optional[str] = None       # Chrome, Safari, Firefox, Edge
    app_version: Optional[str] = None   # mem-dog UI / client app version
    user_agent: Optional[str] = None    # Raw User-Agent string
    ip_address: Optional[str] = None    # Client IP (if available)
    # Extended fields — collected by the UI via browser APIs
    screen_width: Optional[int] = None          # window.screen.width
    screen_height: Optional[int] = None         # window.screen.height
    timezone: Optional[str] = None              # Intl timezone, e.g. "America/New_York"
    language: Optional[str] = None              # navigator.language, e.g. "en-US"
    cpu_cores: Optional[int] = None             # navigator.hardwareConcurrency
    memory_gb: Optional[float] = None           # navigator.deviceMemory (Chrome only)
    connection_type: Optional[str] = None       # navigator.connection.effectiveType, e.g. "4g"
    device_id: Optional[str] = None             # Persistent per-device UUID from localStorage


class ServiceParticipant(BaseModel):
    """Records one service that handled an event in the processing chain."""
    service_name: str                       # e.g. "mem-dog-api", "webhook-processor"
    service_type: str                       # e.g. "fastapi", "gcp_cloud_function", "gcp_cloud_run_adk"
    service_version: Optional[str] = None  # app/image version
    action: str                             # e.g. "create_data", "route_payload", "write_record"
    timestamp: str                          # ISO-8601 UTC when this service processed the event
    span_id: Optional[str] = None          # OTel span ID for this service's span


# =============================================================================
# Plan 2 — Channel Mapping Models
# =============================================================================

class ChannelType(str, Enum):
    """Supported inbound communication channel types.

    Includes OpenClaw-aligned chat channels (https://docs.openclaw.ai/channels),
    major video conferencing platforms, email providers, and document platforms.
    """
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    MSTEAMS = "msteams"
    EMAIL = "email"
    # Email providers
    GMAIL = "gmail"
    HOTMAIL = "hotmail"
    YAHOO_MAIL = "yahoo_mail"
    OUTLOOK = "outlook"
    SMS = "sms"
    SIGNAL = "signal"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    WEBCHAT = "webchat"
    API = "api"
    # OpenClaw channels
    IRC = "irc"
    FEISHU = "feishu"
    GOOGLE_CHAT = "google_chat"
    MATTERMOST = "mattermost"
    BLUEBUBBLES = "bluebubbles"
    IMESSAGE = "imessage"
    SYNOLOGY_CHAT = "synology_chat"
    LINE = "line"
    NEXTCLOUD_TALK = "nextcloud_talk"
    MATRIX = "matrix"
    NOSTR = "nostr"
    TLON = "tlon"
    TWITCH = "twitch"
    ZALO = "zalo"
    ZALO_PERSONAL = "zalo_personal"
    # Video conferencing
    ZOOM = "zoom"
    GOOGLE_MEET = "google_meet"
    WEBEX = "webex"
    # Document / productivity
    GOOGLE_DOCS = "google_docs"
    MICROSOFT_DOCUMENTS = "microsoft_documents"
    OFFICE_365 = "office_365"
    ONEDRIVE = "onedrive"
    UNKNOWN = "unknown"


class MediaAttachment(BaseModel):
    """A single media attachment carried with a channel message."""
    url: Optional[str] = None
    mime_type: Optional[str] = None
    filename: Optional[str] = None
    size_bytes: Optional[int] = None
    caption: Optional[str] = None


class ChannelMessage(BaseModel):
    """Normalised representation of a message from any chat channel."""
    channel_type: ChannelType = ChannelType.UNKNOWN
    channel_id: Optional[str] = None          # Platform-specific channel / room ID
    thread_id: Optional[str] = None           # Thread / reply chain ID
    peer_id: Optional[str] = None             # Sender identifier on the channel
    message_id: Optional[str] = None          # Platform-assigned message ID
    text: Optional[str] = None
    attachments: List["MediaAttachment"] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChannelRef(BaseModel):
    """Lightweight channel reference embedded in DataSource."""
    channel_type: ChannelType = ChannelType.UNKNOWN
    channel_id: Optional[str] = None
    thread_id: Optional[str] = None
    peer_id: Optional[str] = None


# =============================================================================
# Channel identity correlation (channel <-> user_id)
# =============================================================================

class ChannelIdentityCreate(BaseModel):
    """Payload to create or upsert a channel identity binding."""
    channel_type: str  # ChannelType value or custom string
    channel_unique_id: str
    user_id: str
    display_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChannelIdentityUpdate(BaseModel):
    """Partial update for a channel identity (display_name, metadata)."""
    display_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ChannelIdentityRecord(BaseModel):
    """Single channel identity record (by-channel or list item)."""
    channel_type: str
    channel_unique_id: str
    user_id: str
    display_name: Optional[str] = None
    added_at: str  # ISO8601
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChannelIdentityListResponse(BaseModel):
    """List of channel identities for a user."""
    user_id: str
    identities: List[ChannelIdentityRecord] = Field(default_factory=list)


# =============================================================================
# Channels bucket — per-channel metadata (how to communicate, config)
# =============================================================================

class ChannelMetadata(BaseModel):
    """Metadata for a channel: identity, config, and how to communicate with it.

    Stored at path <channel_type>/meta in the channels bucket.
    """
    channel_type: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    """How to communicate: webhook URL, API base, auth type, etc."""
    config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None  # ISO8601
    updated_at: Optional[str] = None  # ISO8601


class ChannelMetadataCreate(BaseModel):
    """Payload to create or update channel metadata."""
    display_name: Optional[str] = None
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Plan 1 — Data Ownership Models
# =============================================================================

class DataSource(BaseModel):
    """Origin source descriptor attached to DataOwner."""
    channel: Optional[ChannelRef] = None
    device: Optional[Dict[str, Any]] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class DataCorrelation(BaseModel):
    """Cross-service correlation identifiers for a data item."""
    source: Optional[Dict[str, Any]] = None
    external_ids: Dict[str, str] = Field(default_factory=dict)


class DataMemoryDict(BaseModel):
    """Structured map of memory IDs associated with a data item by category."""
    tracing: List[str] = Field(default_factory=list)
    session: List[str] = Field(default_factory=list)
    agent: List[str] = Field(default_factory=list)
    conversation: List[str] = Field(default_factory=list)


class DataOwner(BaseModel):
    """Structured ownership and provenance metadata for a data item."""
    user: Optional[Dict[str, Any]] = None        # {"user_id": "...", "username": "..."}
    source: Optional[DataSource] = None
    correlation: Optional[DataCorrelation] = None
    memory_dict: Optional[DataMemoryDict] = None


class DataProvenance(BaseModel):
    """Rich provenance record — who created the data, on which device, via which services.

    Stored in ``DataMetadata.provenance`` alongside the lightweight ``DataOwner``.
    The ``services`` list is append-only and records every service that touched the
    event in processing order, enabling a full audit trail.
    """
    user: Optional[Dict[str, Any]] = None       # {user_id, username, email, role, display_name}
    device: Optional[DataDeviceInfo] = None     # Full device snapshot at upload/ingest time
    services: List[ServiceParticipant] = Field(default_factory=list)
    source: Optional[DataSource] = None
    correlation: Optional[DataCorrelation] = None
    memory_dict: Optional[DataMemoryDict] = None


class EventMeta(BaseModel):
    """Canonical inter-service event metadata block.

    Every event/message passed between services carries this block inside the
    ``telemetry`` key.  Rules:
    - ``user_id``: defaults to config.DEFAULT_USER_ID when absent.
    - ``data_id``: required when the event concerns a specific data item.
    - ``version``: defaults to latest version of data_id; a new v1 is created if none exists.
    - ``timestamp``: ISO-8601 UTC; auto-filled by the originating service if absent.
    - Each service **appends** itself to ``services`` before forwarding downstream.
    """
    user_id: str = ""           # filled from config.DEFAULT_USER_ID if absent at boundary
    data_id: Optional[str] = None
    version: Optional[int] = None       # None = resolve to latest, or create v1
    version_label: Optional[str] = None # e.g. "ver_20250225T143022Z"
    timestamp: Optional[str] = None     # ISO-8601 UTC; set by first service
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    trace_memory_id: Optional[str] = None
    session_id: Optional[str] = None
    memory_list: Optional[List[str]] = None
    services: List[ServiceParticipant] = Field(default_factory=list)
    device: Optional[DataDeviceInfo] = None


# =============================================================================
# Plan 3 — Universal Data Envelope (UDE) Models
# =============================================================================

class SourceType(str, Enum):
    """High-level classification of where data originates."""
    CHAT = "chat"                      # Chat messages (WhatsApp, Telegram, Slack…)
    EMAIL = "email"                    # Email messages
    CONFERENCING = "conferencing"      # Zoom, Google Meet, Teams…
    DOCUMENT = "document"              # Files, PDFs, Office docs
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    CODE = "code"
    VEHICLE = "vehicle"                # CAN bus, OBD-II, telematics
    SATELLITE = "satellite"            # SAR, optical, hyperspectral imagery
    SENSOR = "sensor"                  # IoT / industrial sensors
    TELEMETRY = "telemetry"            # OTel / device metrics
    GEOSPATIAL = "geospatial"          # GeoJSON, shapefiles, LIDAR
    MEDICAL = "medical"                # DICOM, HL7, FHIR
    FINANCIAL = "financial"            # Trade ticks, order books
    SCIENTIFIC = "scientific"          # Lab results, spectrometry
    INDUSTRIAL = "industrial"          # SCADA, PLC, factory floor
    INFRASTRUCTURE = "infrastructure"  # Kubernetes events, cloud logs
    BINARY = "binary"                  # Unknown / opaque binary
    OTHER = "other"


class GeoPoint(BaseModel):
    """WGS-84 geographic coordinate with optional altitude."""
    lat: float
    lon: float
    alt_m: Optional[float] = None


class OriginDescriptor(BaseModel):
    """Where and who produced the data."""
    source_type: SourceType = SourceType.OTHER
    channel_type: Optional[ChannelType] = None
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    location: Optional[GeoPoint] = None
    timestamp_utc: Optional[str] = None   # ISO-8601 event timestamp (producer time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PayloadDescriptor(BaseModel):
    """What the data is and how it is encoded."""
    mime_type: Optional[str] = None
    encoding: Optional[str] = None         # e.g. "utf-8", "base64", "binary"
    size_bytes: Optional[int] = None
    url: Optional[str] = None              # Canonical URL if content lives remotely
    is_downloaded: bool = False
    checksum_sha256: Optional[str] = None
    extensions: Dict[str, Any] = Field(default_factory=dict)


class ContextDescriptor(BaseModel):
    """Correlation and grouping context for the envelope."""
    session_id: Optional[str] = None
    timeline_id: Optional[str] = None
    conversation_id: Optional[str] = None
    trace_id: Optional[str] = None
    memory_ids: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    # mem-dog data_id when content is already stored (avoids duplicate write in pipeline)
    data_id: Optional[str] = None
    # Host SaaS — org/project scope + idempotent upsert key
    org_id: Optional[str] = None
    project_id: Optional[str] = None
    external_id: Optional[str] = None


class UniversalEnvelope(BaseModel):
    """
    Universal Data Envelope — a single container that can represent any
    data type from any source system.  The ``payload`` field carries the
    actual content (raw text, JSON dict, or base64-encoded binary).
    Extension-specific fields (e.g. vehicle CAN frames, satellite metadata)
    live in ``extensions``.
    """
    envelope_id: Optional[str] = None         # Caller-supplied; auto-generated if absent
    schema_version: str = "1.0"
    origin: OriginDescriptor = Field(default_factory=OriginDescriptor)
    payload: PayloadDescriptor = Field(default_factory=PayloadDescriptor)
    context: ContextDescriptor = Field(default_factory=ContextDescriptor)
    # Actual data — one of these should be set
    content_text: Optional[str] = None        # Decoded text payload
    content_json: Optional[Dict[str, Any]] = None   # Structured JSON payload
    content_b64: Optional[str] = None         # base64-encoded binary payload
    extensions: Dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    """Top-level request body for POST /api/v1/ingest."""
    envelope: UniversalEnvelope
    direct: bool = Field(
        default=False,
        description=(
            "When True, bypass the webhook pipeline and store the envelope "
            "directly in the API. When False (default), forward to the webhook "
            "receiver for full pipeline processing."
        ),
    )


class DataMetadata(BaseModel):
    data_id: str
    current_version: int
    versions: List[VersionInfo]
    created_at: str
    updated_at: str
    # User-friendly name (defaults to filename if uploaded as file)
    name: Optional[str] = None
    # Optional description for the data item
    description: Optional[str] = None
    # Access control: None/undefined = public, ["*"] = all, ["user:id", "role:name"] = specific
    access: Optional[List[str]] = None
    # Memory IDs this data item is associated with (many-to-many)
    memory_ids: Optional[List[str]] = None
    # DEPRECATED: Use memory_ids instead. Kept for deserialization of old data.
    session_id: Optional[str] = None
    # Device info captured at upload time (always passed, may be empty)
    device_info: Optional[DataDeviceInfo] = None
    # Tags: Array of unique tags for search/filtering (user-provided via client)
    tags: Optional[List[str]] = None
    # Purpose of this data (e.g. user_data, otel_span, trace_stage)
    purpose: Optional[str] = None
    # Absolute URL to access this data's content (computed at response time, not stored)
    address: Optional[str] = None
    # Plan 1 — remote URL this data was fetched from (or should be fetched from)
    url: Optional[str] = None
    # Detected or declared MIME type
    mime_type: Optional[str] = None
    # True once the remote URL has been downloaded and content stored locally
    is_downloaded: bool = False
    # Structured ownership / provenance metadata (lightweight, backward-compat)
    owner: Optional[DataOwner] = None
    # Rich provenance: user, device, ordered services audit trail
    provenance: Optional[DataProvenance] = None
    # Which service wrote this data item ("mem-dog-api", "webhook-agent", ...)
    source_service: Optional[str] = None
    # Human-readable version label matching the storage path (ver_20250225T143022Z)
    data_version_label: Optional[str] = None
    # Organization/project scoping (nullable for backward compat)
    org_id: Optional[str] = None
    project_id: Optional[str] = None
    # Host SaaS upsert key (unique per project or owner user)
    external_id: Optional[str] = None


class DataListItem(BaseModel):
    data_id: str
    current_version: int
    created_at: str
    updated_at: str
    content_type: str
    size: int
    # User-friendly name (defaults to filename if uploaded as file)
    name: Optional[str] = None
    # Optional description for the data item
    description: Optional[str] = None
    # Access control: None/undefined = public, ["*"] = all, ["user:id", "role:name"] = specific
    access: Optional[List[str]] = None
    # Memory IDs this data item is associated with
    memory_ids: Optional[List[str]] = None
    # Tags: Array of unique tags for search/filtering
    tags: Optional[List[str]] = None
    # Absolute URL to access this data's content (computed at response time, not stored)
    address: Optional[str] = None
    # Plan 1 — remote source URL and download state
    url: Optional[str] = None
    mime_type: Optional[str] = None
    is_downloaded: bool = False
    # Rich provenance for display in the UI
    provenance: Optional[DataProvenance] = None
    source_service: Optional[str] = None
    data_version_label: Optional[str] = None
    # Organization/project scoping (nullable for backward compat)
    org_id: Optional[str] = None
    project_id: Optional[str] = None
    external_id: Optional[str] = None


class DataListResponse(BaseModel):
    """Paginated response for GET /api/v1/data."""
    items: List[DataListItem]
    total: int
    skip: int
    limit: int


class MarkDownloadedRequest(BaseModel):
    """Request model for PATCH /data/{data_id}/download — marks content as downloaded."""
    data_id: Optional[str] = None  # Ignored; path param used. Kept for symmetry.
    is_downloaded: bool = True


class AccessUpdate(BaseModel):
    """Request model for updating access control on a data item."""
    access: Optional[List[str]] = Field(
        default=None,
        description="Access control list. None=public, ['*']=all, ['user:id','role:name']=specific"
    )


class InfoUpdate(BaseModel):
    """Request model for updating name and description on a data item."""
    name: Optional[str] = Field(
        default=None,
        description="User-friendly name. Set to empty string to clear."
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional description. Set to empty string to clear."
    )


# DEPRECATED: Use MemoryDataEntry instead. Kept for backward compatibility.
class TimelineEntry(BaseModel):
    user: str
    data_id: str
    version: int
    action: str  # create, update, delete
    timestamp: int


# DEPRECATED: Use MemoryDataEntry instead. Kept for backward compatibility.
class TimelineEntryDetail(TimelineEntry):
    content_type: Optional[str] = None
    size: Optional[int] = None


class CreateDataRequest(BaseModel):
    content: Optional[Any] = None
    content_type: Optional[str] = "application/octet-stream"


class CreateDataResponse(BaseModel):
    data_id: str
    version: int
    message: str
    created: bool = True
    updated: bool = False


class ParsedDocumentStoreRequest(BaseModel):
    """Request body for POST /data/{data_id}/parsed (webhook processor)."""
    markdown: str = ""
    document: Dict[str, Any] = Field(default_factory=dict)


class ParsedDocumentStoreResponse(BaseModel):
    data_id: str
    version_label: str
    parse_status: str = "ready"
    markdown_path: str
    json_path: str


class UpdateDataResponse(BaseModel):
    data_id: str
    version: int
    message: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# =============================================================================
# Bulk Delete Models
# =============================================================================

class BulkDeleteRequest(BaseModel):
    """Request model for deleting multiple data items by ID."""
    data_ids: List[str] = Field(
        ...,
        min_length=1,
        description="List of data IDs to delete"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID who owns the data items (required for multi-tenant storage lookup)"
    )


class BulkDeleteResponse(BaseModel):
    """Response model for bulk delete operations."""
    deleted_count: int = Field(description="Number of items successfully deleted")
    failed_count: int = Field(default=0, description="Number of items that failed to delete")
    deleted_ids: List[str] = Field(default_factory=list, description="IDs of successfully deleted items")
    failed_ids: List[str] = Field(default_factory=list, description="IDs of items that failed to delete")
    message: str


class UserDataDeleteResponse(BaseModel):
    """Response model for deleting all data for a user."""
    user: str
    deleted_count: int
    message: str


class SessionDataDeleteResponse(BaseModel):
    """Response model for deleting all data associated with a session."""
    session_id: str
    deleted_count: int
    failed_count: int = 0
    deleted_ids: List[str] = Field(default_factory=list)
    message: str


class BulkSessionDeleteRequest(BaseModel):
    """Request model for deleting multiple sessions."""
    session_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific session IDs to delete. If null, deletes all sessions matching filters."
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Delete all sessions for this user"
    )
    delete_data: bool = Field(
        default=False,
        description="Also delete all data associated with the sessions"
    )


class BulkSessionDeleteResponse(BaseModel):
    """Response model for bulk session delete operations."""
    deleted_sessions: int
    deleted_data_items: int = 0
    message: str


class UserDataItem(BaseModel):
    """Represents a data item owned by a user with all available information."""
    data_id: str
    current_version: int
    created_at: str
    updated_at: str
    content_type: str
    size: int
    # Timeline info
    last_action: Optional[str] = None
    last_action_timestamp: Optional[int] = None


class PaginationInfo(BaseModel):
    """Pagination metadata for list responses."""
    total: int
    limit: int
    offset: int
    has_more: bool


class UserListResponse(BaseModel):
    """Response for user list API with multiple format options."""
    user: str
    format: str  # "timeline", "meta", "raw"
    count: int
    items: List[Any]
    pagination: PaginationInfo


# =============================================================================
# AI Layer Models
# =============================================================================

class AIEngineType(str, Enum):
    """
    Supported AI engine types.
    
    Native Support:
    - openai: OpenAI API (GPT-4, embeddings)
    - anthropic: Anthropic API (Claude models)
    - gemini: Google Gemini API
    - ollama: Local Ollama server
    - bedrock: Amazon Bedrock
    - openrouter: OpenRouter multi-provider gateway
    - together: Together AI
    - huggingface: Hugging Face Inference API
    - vllm: vLLM local server
    - litellm: LiteLLM unified gateway (supports 100+ providers)
    
    Via LiteLLM: NVIDIA, Venice, Cloudflare, Vercel, Moonshot, Qwen, GLM, 
                 MiniMax, Qianfan, Z.AI, Groq, Mistral, Cohere, and more.
    See: https://docs.openclaw.ai/providers
    """
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    OLLAMA_CLOUD = "ollama_cloud"
    BEDROCK = "bedrock"
    OPENROUTER = "openrouter"
    TOGETHER = "together"
    HUGGINGFACE = "huggingface"
    VLLM = "vllm"
    LITELLM = "litellm"


class AIKeyMode(str, Enum):
    """
    Mode for AI API key usage.
    - CUSTOM: User provides and manages their own API keys (user responsibility)
    - SYSTEM: Use system-provided default Gemini key (if available)
    """
    CUSTOM = "custom"
    SYSTEM = "system"


class AIModelCapabilities(BaseModel):
    """Models available for an AI engine."""
    embeddings: List[str] = Field(default_factory=list)
    completions: List[str] = Field(default_factory=list)


class AISignature(BaseModel):
    """
    AI provenance signature - records which AI system generated the content.
    This provides full traceability for all AI-generated artifacts.
    """
    ai_engine: AIEngineType  # e.g., "openai", "gemini", "ollama"
    model_name: str  # e.g., "gpt-4", "gemini-1.5-flash"
    model_version: Optional[str] = None  # e.g., "gpt-4-0125-preview"
    api_version: Optional[str] = None  # API version if applicable
    generated_at: str  # ISO 8601 timestamp when AI generated the content
    generation_id: Optional[str] = None  # Unique ID for this generation (if provided by AI)
    key_mode: AIKeyMode  # "system" or "custom" - indicates key source
    temperature: Optional[float] = None  # Temperature used for generation
    max_tokens: Optional[int] = None  # Max tokens setting
    additional_params: Dict[str, Any] = Field(default_factory=dict)  # Any other params used


# -----------------------------------------------------------------------------
# AI Engine Configuration Models
# -----------------------------------------------------------------------------

class AIEngineConfigBase(BaseModel):
    """Base fields for AI engine configuration."""
    engine_type: AIEngineType
    name: str
    base_url: Optional[str] = None
    is_enabled: bool = True


class AIEngineConfigCreate(AIEngineConfigBase):
    """Request model for creating an AI engine configuration."""
    api_key: Optional[str] = None  # Plain text, will be encrypted before storage


class AIEngineConfigUpdate(BaseModel):
    """Request model for updating an AI engine configuration."""
    name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_enabled: Optional[bool] = None


class AIEngineConfig(AIEngineConfigBase):
    """Stored AI engine configuration."""
    engine_id: str
    user: str
    api_key_encrypted: Optional[str] = None  # Encrypted API key
    available_models: AIModelCapabilities = Field(default_factory=AIModelCapabilities)
    discovered_models: List[str] = Field(default_factory=list)
    last_tested_at: Optional[str] = None
    last_test_status: Optional[str] = None  # "success" | "error"
    last_test_error: Optional[str] = None
    created_at: str
    updated_at: str


class AIEngineConfigResponse(AIEngineConfigBase):
    """Response model for AI engine configuration (excludes sensitive data)."""
    engine_id: str
    user: str
    has_api_key: bool = False
    available_models: AIModelCapabilities = Field(default_factory=AIModelCapabilities)
    discovered_models: List[str] = Field(default_factory=list)
    last_tested_at: Optional[str] = None
    last_test_status: Optional[str] = None
    created_at: str
    updated_at: str


# -----------------------------------------------------------------------------
# User AI Preferences Models
# -----------------------------------------------------------------------------

class UserAIPreferences(BaseModel):
    """
    User's AI preferences and defaults.
    
    The ai_key_mode determines how API keys are sourced:
    - "custom": User must configure their own engine with their own API key
    - "system": Use the system-provided default Gemini key (if available)
    
    Note: When using "custom" mode, users are responsible for their own API usage and costs.
    """
    user: str
    ai_key_mode: AIKeyMode = AIKeyMode.SYSTEM  # Default to system key if available
    default_engine_id: Optional[str] = None  # User's custom engine (used when mode is "custom")
    default_embedding_model: Optional[str] = None
    default_completion_model: Optional[str] = None
    auto_generate_embeddings: bool = False
    preferred_engines: Dict[str, str] = Field(default_factory=dict)  # {"embeddings": "engine_id", "completions": "engine_id"}
    agent_processing_flags: Dict[str, bool] = Field(
        default_factory=dict,
        description="Per-data-type AI processing toggle. Key=agent_type, value=enabled."
    )
    ollama_cloud_model_small: Optional[str] = None
    ollama_cloud_model_medium: Optional[str] = None
    ollama_cloud_model_large: Optional[str] = None
    ollama_cloud_model_multimodal: Optional[str] = None
    smart_routing_overrides: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Per-data-type model overrides. Key=agent_type, value={'primary_model': '...', 'fallback_model': '...'}."
    )
    created_at: str
    updated_at: str


class UserAIPreferencesUpdate(BaseModel):
    """Request model for updating user AI preferences."""
    ai_key_mode: Optional[AIKeyMode] = None
    default_engine_id: Optional[str] = None
    default_embedding_model: Optional[str] = None
    default_completion_model: Optional[str] = None
    auto_generate_embeddings: Optional[bool] = None
    preferred_engines: Optional[Dict[str, str]] = None
    agent_processing_flags: Optional[Dict[str, bool]] = None
    ollama_cloud_model_small: Optional[str] = None
    ollama_cloud_model_medium: Optional[str] = None
    ollama_cloud_model_large: Optional[str] = None
    ollama_cloud_model_multimodal: Optional[str] = None
    smart_routing_overrides: Optional[Dict[str, Dict[str, str]]] = None


# -----------------------------------------------------------------------------
# Global AI Availability Models
# -----------------------------------------------------------------------------

class GlobalAIEngineInfo(BaseModel):
    """Information about an available AI engine type."""
    engine_type: AIEngineType
    name: str
    requires_api_key: bool
    default_base_url: str
    models: AIModelCapabilities


class GlobalAIAvailability(BaseModel):
    """Global configuration of available AI engines."""
    available_engines: List[GlobalAIEngineInfo]
    system_default_available: bool = False  # True if system Gemini key is configured
    system_default_engine: Optional[str] = "gemini"  # The system default is always Gemini
    system_default_models: Optional[AIModelCapabilities] = None


class SystemAIConfigResponse(BaseModel):
    """
    Response model for system AI configuration status.

    This tells users whether they can use the system-provided AI key
    or need to configure their own.
    """
    system_ai_available: bool  # True if Gemini system key or local model server is configured
    system_engine_type: str = "gemini"
    system_embedding_model: str
    system_completion_model: str
    message: str  # Human-readable status message


class ProviderInfo(BaseModel):
    """Static provider catalog entry returned by the registry endpoint."""
    engine_type: str
    display_name: str
    description: str
    icon: str  # String key for UI icon mapping
    requires_api_key: bool = True
    default_base_url: Optional[str] = None
    api_key_placeholder: Optional[str] = None
    litellm_prefix: str = ""
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    models_endpoint: Optional[str] = None
    default_models: List[str] = Field(default_factory=list)
    default_embedding_models: List[str] = Field(default_factory=list)
    category: str = "cloud"  # "cloud" | "local" | "gateway"


class AvailableModelsResponse(BaseModel):
    """Aggregated available models from all configured providers."""
    providers: List[Dict[str, Any]] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Prompt Models
# -----------------------------------------------------------------------------

class PromptBase(BaseModel):
    """Base fields for a prompt template."""
    name: str
    template: str  # Template with {{content}} placeholder
    ai_engine: Optional[AIEngineType] = None
    model: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)  # e.g., {"temperature": 0.7}


class PromptCreate(PromptBase):
    """Request model for creating a prompt."""
    data_id: Optional[str] = None  # If None, prompt is a global template


class PromptUpdate(BaseModel):
    """Request model for updating a prompt."""
    name: Optional[str] = None
    template: Optional[str] = None
    ai_engine: Optional[AIEngineType] = None
    model: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class Prompt(PromptBase):
    """Stored prompt template."""
    prompt_id: str
    data_id: Optional[str] = None
    user: str
    version: int = 1
    created_at: str
    updated_at: str


# -----------------------------------------------------------------------------
# Skill Models
# -----------------------------------------------------------------------------

class SkillBase(BaseModel):
    """Base fields for an AI agent skill."""
    name: str
    description: str
    content: str  # Full skill instructions for the AI agent
    tags: List[str] = Field(default_factory=list)


class SkillCreate(SkillBase):
    """Request model for creating a skill."""
    data_id: Optional[str] = None  # If None, skill is global (user-scoped)


class SkillUpdate(BaseModel):
    """Request model for updating a skill."""
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None


class Skill(SkillBase):
    """Stored AI agent skill."""
    skill_id: str
    data_id: Optional[str] = None
    user: str
    version: int = 1
    created_at: str
    updated_at: str


# -----------------------------------------------------------------------------
# Analysis Template Models (data analysis AI options)
# -----------------------------------------------------------------------------

class AnalysisTemplateKind(str, Enum):
    """Whether the template is a prompt or a skill for data analysis."""
    PROMPT = "prompt"
    SKILL = "skill"


class AnalysisTemplateBase(BaseModel):
    """Base fields for an analysis template shown when user analyzes data."""
    data_types: List[str] = Field(
        default_factory=lambda: ["any"],
        description="Data types this template applies to (e.g. ['csv'], ['json','xml'], or ['any']).",
    )
    kind: AnalysisTemplateKind = AnalysisTemplateKind.PROMPT
    name: str = ""
    description: str = ""
    prompt_id: Optional[str] = None
    skill_id: Optional[str] = None
    template_text: Optional[str] = Field(
        default=None,
        description="Inline prompt or skill content for system templates; used when prompt_id/skill_id are null.",
    )
    sort_order: int = 0


class AnalysisTemplateCreate(AnalysisTemplateBase):
    """Request model for creating an analysis template."""


class AnalysisTemplateUpdate(BaseModel):
    """Request model for updating an analysis template."""
    data_types: Optional[List[str]] = None
    kind: Optional[AnalysisTemplateKind] = None
    name: Optional[str] = None
    description: Optional[str] = None
    prompt_id: Optional[str] = None
    skill_id: Optional[str] = None
    template_text: Optional[str] = None
    sort_order: Optional[int] = None


class AnalysisTemplate(AnalysisTemplateBase):
    """Stored analysis template (prompt or skill) offered when user analyzes data."""
    template_id: str
    created_at: str
    updated_at: str


# -----------------------------------------------------------------------------
# Agent Config Models (configurable pipeline prompts & skills)
# -----------------------------------------------------------------------------

class AgentConfigBase(BaseModel):
    """Base fields for a webhook sub-agent pipeline configuration."""
    agent_type: str                          # e.g. "json", "pdf", "financial"
    intro: Optional[str] = None              # replaces _INTRO[agent_type] in skills.py
    system_prompt: Optional[str] = None      # replaces hardcoded system msg in _run_llm
    output_schema: Optional[str] = None      # replaces _BASE_FIELDS / _AV_EXTRA_FIELDS
    skills: List[str] = Field(default_factory=list)  # skill IDs to attach
    model_tier: Optional[str] = None         # override MODEL_TIER class var
    parameters: Dict[str, Any] = Field(default_factory=dict)  # extra params


class AgentConfigCreate(AgentConfigBase):
    """Request model for creating an agent config."""
    user_id: Optional[str] = None            # null = system default


class AgentConfigUpdate(BaseModel):
    """Request model for partial agent config updates."""
    intro: Optional[str] = None
    system_prompt: Optional[str] = None
    output_schema: Optional[str] = None
    skills: Optional[List[str]] = None
    model_tier: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class AgentConfig(AgentConfigBase):
    """Stored webhook sub-agent pipeline configuration."""
    config_id: str
    user_id: Optional[str] = None            # null = system default
    version: int = 1
    created_at: str
    updated_at: str


# -----------------------------------------------------------------------------
# Embedding Models
# -----------------------------------------------------------------------------

class EmbeddingCreate(BaseModel):
    """Request model for generating embeddings."""
    data_id: str
    engine_id: Optional[str] = None  # If None, use user's default
    model: Optional[str] = None
    chunk_size: int = 1000
    chunk_overlap: int = 200
    # Multitenancy — owner of this data item
    user_id: str = ""
    # Organization/project scoping
    org_id: Optional[str] = None
    project_id: Optional[str] = None


class Embedding(BaseModel):
    """Stored embedding for a data chunk."""
    embedding_id: str
    data_id: str
    data_version: int
    ai_engine: AIEngineType
    model: str
    vector: List[float]
    dimensions: int
    chunk_index: int
    chunk_text: str
    created_at: str
    version: int = 1
    # Multitenancy + per-version storage path
    user_id: str = ""
    version_label: Optional[str] = None
    # AI Signature - provenance information
    ai_signature: Optional[AISignature] = None
    # Organization/project scoping
    org_id: Optional[str] = None
    project_id: Optional[str] = None
    # Parsed-document chunk localization (Phase 2)
    page: Optional[int] = None
    section_path: Optional[List[str]] = None
    element_type: Optional[str] = None
    embedding_kind: Optional[str] = None  # e.g. "body" | "viewpoint"


class EmbeddingSummary(BaseModel):
    """Summary of embeddings for a data item."""
    data_id: str
    data_version: int
    embeddings_count: int
    ai_engine: AIEngineType
    model: str
    dimensions: int
    created_at: str
    # Multitenancy + per-version storage path
    user_id: str = ""
    version_label: Optional[str] = None
    # AI Signature - provenance information
    ai_signature: Optional[AISignature] = None


# -----------------------------------------------------------------------------
# Viewpoint Models
# -----------------------------------------------------------------------------

class ViewpointCreate(BaseModel):
    """Request model for creating a viewpoint (AI analysis)."""
    data_id: str
    prompt_id: str
    engine_id: Optional[str] = None  # If None, use user's default
    # Multitenancy — owner of this data item
    user_id: str = ""
    # Pre-computed analysis text — when provided, skip the LLM call
    output_content: Optional[str] = None
    # Actual inference provenance — set by the webhook agent so the
    # AI signature reflects the model that really ran the inference
    # (rather than falling back to _resolve_completion_engine).
    ai_engine: Optional[str] = None
    model_name: Optional[str] = None


class ViewpointUpdate(BaseModel):
    """Request model for regenerating a viewpoint."""
    engine_id: Optional[str] = None
    prompt_id: Optional[str] = None  # If provided, use different prompt


class Viewpoint(BaseModel):
    """Stored AI viewpoint (analysis/interpretation)."""
    viewpoint_id: str
    data_id: str
    data_version: int
    prompt_id: str
    user: str
    ai_engine: AIEngineType
    model: str
    input_content: str  # The data content that was analyzed
    output_content: str  # The AI-generated analysis
    parameters: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    created_at: str
    updated_at: str
    # Multitenancy + per-version storage path
    user_id: str = ""
    version_label: Optional[str] = None
    # AI Signature - provenance information
    ai_signature: Optional[AISignature] = None


class ViewpointResponse(BaseModel):
    """Response model for viewpoint."""
    viewpoint_id: str
    data_id: str
    data_version: int
    prompt_id: str
    ai_engine: AIEngineType
    model: str
    output_content: str
    version: int
    created_at: str
    updated_at: str
    # Multitenancy + per-version storage path
    user_id: str = ""
    version_label: Optional[str] = None
    # AI Signature - provenance information (who wrote this)
    ai_signature: Optional[AISignature] = None


# -----------------------------------------------------------------------------
# NLP Query Models
# -----------------------------------------------------------------------------

class AIQueryRequest(BaseModel):
    """Request model for NLP querying."""
    query: str
    engine_id: Optional[str] = None
    max_results: int = 5


class AIQuerySource(BaseModel):
    """A source chunk relevant to the query."""
    data_id: str
    chunk_text: str
    score: float


class AIQueryResponse(BaseModel):
    """Response model for NLP query."""
    answer: str
    sources: List[AIQuerySource]
    model: str
    ai_engine: AIEngineType
    # AI Signature - provenance information (who generated this answer)
    ai_signature: Optional[AISignature] = None


class AITimelineQueryRequest(BaseModel):
    """Request model for timeline-based NLP query."""
    query: str
    user: str = "00000000-0000-0000-0000-000000000001"
    time_range: Optional[Dict[str, str]] = None  # {"start": "2024-01-01", "end": "2024-12-31"}
    engine_id: Optional[str] = None


# -----------------------------------------------------------------------------
# AI Engine Test Models
# -----------------------------------------------------------------------------

class AIEngineTestResponse(BaseModel):
    """Response model for testing AI engine connectivity."""
    status: str  # "success" or "error"
    latency_ms: Optional[int] = None
    models_available: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


# =============================================================================
# User Management Models
# =============================================================================

class UserStatus(str, Enum):
    """User account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class UserRole(str, Enum):
    """User roles for access control."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class UserCreate(BaseModel):
    """Request model for creating a user."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str
    display_name: Optional[str] = None
    role: UserRole = UserRole.USER
    metadata: Dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = Field(None, description="Optional user ID. If provided, uses this instead of generating a new one (e.g. for Supabase auth sync).")
    default_org_id: Optional[str] = None
    default_project_id: Optional[str] = None


class UserUpdate(BaseModel):
    """Request model for updating a user."""
    username: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class User(BaseModel):
    """Stored user information."""
    user_id: str  # UUID
    username: str
    email: str
    display_name: Optional[str] = None
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Statistics
    data_count: int = 0
    storage_used_bytes: int = 0
    # Timestamps
    created_at: str
    updated_at: str
    last_active_at: Optional[str] = None
    # Default org/project
    default_org_id: Optional[str] = None
    default_project_id: Optional[str] = None


class UserResponse(BaseModel):
    """Response model for user (excludes sensitive data)."""
    user_id: str
    username: str
    email: str
    display_name: Optional[str] = None
    role: UserRole
    status: UserStatus
    metadata: Dict[str, Any] = Field(default_factory=dict)
    data_count: int = 0
    storage_used_bytes: int = 0
    created_at: str
    updated_at: str
    last_active_at: Optional[str] = None
    # Default org/project
    default_org_id: Optional[str] = None
    default_project_id: Optional[str] = None


class UsersListResponse(BaseModel):
    """Response model for listing users."""
    users: List[UserResponse]
    total: int
    limit: int
    offset: int


class UserCredentials(BaseModel):
    """User credentials for authentication (stored encrypted)."""
    user_id: str
    password_hash: Optional[str] = None  # For future password auth
    # expires_at may be null for non-expiring keys
    api_keys: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str


class APIKeyCreate(BaseModel):
    """Request model for creating an API key."""
    name: str = Field(..., min_length=1, max_length=100)
    expires_in_days: Optional[int] = None  # None = never expires


class APIKeyResponse(BaseModel):
    """Response model for API key (raw ``key`` shown only once on creation)."""
    key_id: str
    name: str
    key: Optional[str] = None  # Only populated on creation / rotate
    key_prefix: Optional[str] = None  # e.g. md_AbCdEf… for list/display
    created_at: str
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None


class HostApiKeyRotateRequest(BaseModel):
    """Create a new workspace key; optionally revoke an old one after."""
    name: str = Field(default="host-rotated", min_length=1, max_length=100)
    revoke_key_id: Optional[str] = Field(
        default=None,
        description="If set, revoke this key_id after the new key is created.",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Target user (platform key only). md_* rotates for itself.",
    )
    expires_in_days: Optional[int] = None


class HostApiKeyRotateResponse(BaseModel):
    """Result of key rotation. ``key`` is returned once."""
    user_id: str
    key_id: str
    key: str
    key_prefix: str
    name: str
    created_at: str
    expires_at: Optional[str] = None
    revoked_key_id: Optional[str] = None


# =============================================================================
# Organization & Project Hierarchy
# =============================================================================


class OrgRole(str, Enum):
    """Roles within an organization."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class OrganizationCreate(BaseModel):
    """Request model for creating an organization."""
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Organization(BaseModel):
    """Stored organization."""
    org_id: str
    name: str
    display_name: Optional[str] = None
    owner_user_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: str
    updated_at: str


class OrganizationUpdate(BaseModel):
    """Request model for updating an organization."""
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    display_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class OrgMember(BaseModel):
    """Organization membership record."""
    org_id: str
    user_id: str
    role: OrgRole = OrgRole.MEMBER
    created_at: str


class OrgMemberAdd(BaseModel):
    """Request model for adding an org member."""
    user_id: str
    role: OrgRole = OrgRole.MEMBER


class OrgMemberUpdate(BaseModel):
    """Request model for changing a member's role."""
    role: OrgRole


class ProjectCreate(BaseModel):
    """Request model for creating a project."""
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Project(BaseModel):
    """Stored project."""
    project_id: str
    org_id: str
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: str
    updated_at: str


class ProjectUpdate(BaseModel):
    """Request model for updating a project."""
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


# =============================================================================
# Host SaaS workspace models
# =============================================================================

class HostWorkspaceCreate(BaseModel):
    """Provision a mem-dog workspace for an external host tenant."""
    external_org_id: str = Field(..., min_length=1, max_length=200)
    external_workspace_id: str = Field(..., min_length=1, max_length=200)
    display_name: Optional[str] = Field(default=None, max_length=200)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HostWorkspaceResponse(BaseModel):
    """Result of host workspace provision. ``api_key`` is set only on create."""
    org_id: str
    project_id: str
    user_id: str
    api_key: Optional[str] = None
    created: bool = True
    external_org_id: str
    external_workspace_id: str
    display_name: Optional[str] = None


# =============================================================================
# Session Management Models (DEPRECATED -- use Memory with type=session)
# =============================================================================

class DeviceInfo(BaseModel):
    """Device information for session/memory tracking."""
    type: Optional[str] = None  # desktop, mobile, tablet
    os: Optional[str] = None
    browser: Optional[str] = None
    app_version: Optional[str] = None


# DEPRECATED: Use MemoryCreate with memory_type=SESSION instead.
class SessionCreate(BaseModel):
    """Request model for creating a session. DEPRECATED: use Memory API."""
    session_id: str = Field(..., description="Unique session ID (generated by UI)")
    user_id: str = Field(..., description="User who owns the session")
    device_id: str = Field(..., description="Device identifier")
    device_info: Optional[DeviceInfo] = None
    ttl_hours: int = Field(default=24, description="Session TTL in hours")
    metadata: Dict[str, Any] = Field(default_factory=dict)


# DEPRECATED: Use MemoryUpdate instead.
class SessionUpdate(BaseModel):
    """Request model for updating a session. DEPRECATED: use Memory API."""
    device_info: Optional[DeviceInfo] = None
    metadata: Optional[Dict[str, Any]] = None
    extend_ttl_hours: Optional[int] = None


# DEPRECATED: Use Memory with type=session instead.
class Session(BaseModel):
    """Stored session information. DEPRECATED: use Memory API."""
    session_id: str
    user_id: str
    device_id: str
    device_info: Optional[DeviceInfo] = None
    active: bool = True
    data_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    last_activity_at: str
    expires_at: str


# DEPRECATED: Use MemoryResponse instead.
class SessionResponse(BaseModel):
    """Response model for session. DEPRECATED: use Memory API."""
    session_id: str
    user_id: str
    device_id: str
    device_info: Optional[DeviceInfo] = None
    active: bool
    data_count: int = 0
    data_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    last_activity_at: str
    expires_at: str


# DEPRECATED: Use MemoryListResponse instead.
class SessionListResponse(BaseModel):
    """Response model for listing sessions. DEPRECATED: use Memory API."""
    items: List[SessionResponse]
    total: int
    skip: int
    limit: int


# DEPRECATED: Use memory_ids on DataMetadata instead.
class SessionReference(BaseModel):
    """Session reference included in data metadata. DEPRECATED: use memory_ids."""
    session_id: str
    user_id: str
    device_id: str


# =============================================================================
# Memory Management Models
# =============================================================================

class MemoryDataEntry(BaseModel):
    """
    Individual data association within a memory's data bucket.

    Stored at: memories/{memory_id}/data/{data_id}.json
    """
    data_id: str
    memory_id: str
    action: Optional[str] = None  # "create", "update", "delete" (for timeline type)
    version: Optional[int] = None  # data version at association time
    associated_at: str  # ISO 8601 timestamp
    purpose: Optional[str] = None  # e.g. data_create, data_update, timeline_entry
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Memory(BaseModel):
    """
    Stored memory entity.

    A memory is a container that groups data items by context type.
    Each memory has two logical sections in storage:
    - meta.json: this model, stored at memories/{memory_id}/meta.json
    - data/: individual MemoryDataEntry files at memories/{memory_id}/data/{data_id}.json

    The data_ids list is a cached denormalization of the data/ entries.
    """
    memory_id: str
    memory_type: MemoryType
    duration: MemoryDuration  # auto-derived from memory_type
    category: Optional[str] = None  # Mem0 category (auto-derived from memory_type)
    name: str
    description: Optional[str] = None
    user_id: str  # owner / user context
    sub_type: Optional[str] = None  # e.g. legal, hr, customer (for CUSTOM type)
    data_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Access control
    access_level: Optional[str] = None  # private, shared, public, restricted
    shared_with: List[str] = Field(default_factory=list)  # user_ids for shared access
    # Session-specific fields (only populated when memory_type=session)
    device_id: Optional[str] = None
    device_info: Optional[DeviceInfo] = None
    active: Optional[bool] = None
    expires_at: Optional[str] = None
    created_at: str
    updated_at: str
    # Organization/project scoping (nullable for backward compat)
    org_id: Optional[str] = None
    project_id: Optional[str] = None


class MemoryCreate(BaseModel):
    """Request model for creating a memory."""
    memory_id: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional caller-specified memory ID. Auto-generated ID (ULID) if omitted.",
    )
    memory_type: MemoryType = Field(..., description="Type of memory to create")
    name: Optional[str] = Field(default=None, max_length=200, description="Human-readable name. Auto-generated as '{username}-{memory_type}' when omitted.")
    description: Optional[str] = Field(default=None, max_length=2000)
    user_id: str = Field(..., description="User who owns this memory")
    sub_type: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Custom sub-type (e.g. legal, hr, customer). Typically used with CUSTOM memory type.",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Type-specific config")
    # Access control
    access_level: Optional[str] = Field(default=None, description="Access level: private, shared, public, restricted. Defaults to private.")
    shared_with: List[str] = Field(default_factory=list, description="User IDs for shared access")
    # Session-specific fields
    device_id: Optional[str] = Field(default=None, description="Device identifier (session type)")
    device_info: Optional[DeviceInfo] = Field(default=None, description="Device details (session type)")
    ttl_hours: Optional[int] = Field(default=None, description="TTL in hours. Applies to all types; overrides the type's default TTL.")
    no_expiry: bool = Field(default=False, description="When True, override default TTL and never expire this memory.")
    # Organization/project scoping
    org_id: Optional[str] = None
    project_id: Optional[str] = None


class MemoryUpdate(BaseModel):
    """Request model for updating a memory."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    sub_type: Optional[str] = Field(default=None, max_length=64, description="Custom sub-type")
    metadata: Optional[Dict[str, Any]] = None
    device_info: Optional[DeviceInfo] = None
    active: Optional[bool] = None
    access_level: Optional[str] = Field(default=None, description="Access level: private, shared, public, restricted")
    shared_with: Optional[List[str]] = Field(default=None, description="User IDs for shared access")
    expires_at: Optional[str] = Field(default=None, description="Set explicit expiry (ISO 8601)")
    extend_ttl_hours: Optional[int] = Field(default=None, description="Extend TTL by N hours (works on any memory type)")


class MemoryResponse(BaseModel):
    """Response model for a memory."""
    memory_id: str
    memory_type: MemoryType
    duration: MemoryDuration
    category: Optional[str] = None
    name: str
    description: Optional[str] = None
    user_id: str
    sub_type: Optional[str] = None
    data_count: int = 0
    data_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    access_level: Optional[str] = None
    shared_with: List[str] = Field(default_factory=list)
    device_id: Optional[str] = None
    device_info: Optional[DeviceInfo] = None
    active: Optional[bool] = None
    expires_at: Optional[str] = None
    created_at: str
    updated_at: str
    # Organization/project scoping
    org_id: Optional[str] = None
    project_id: Optional[str] = None


class MemoryListResponse(BaseModel):
    """Response model for listing memories."""
    items: List[MemoryResponse]
    total: int
    skip: int
    limit: int


class MemoryAddDataRequest(BaseModel):
    """Request model for adding data items to a memory."""
    data_ids: List[str] = Field(..., min_length=1, description="Data IDs to associate")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional per-association metadata")


class MemoryDataDeleteResponse(BaseModel):
    """Response model for deleting all data associated with a memory."""
    memory_id: str
    deleted_count: int
    failed_count: int = 0
    deleted_ids: List[str] = Field(default_factory=list)
    message: str


class BulkMemoryDeleteRequest(BaseModel):
    """Request model for deleting multiple memories."""
    memory_ids: Optional[List[str]] = Field(
        default=None,
        description="Specific memory IDs to delete. If null, deletes all matching filters."
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Delete all memories for this user"
    )
    memory_type: Optional[MemoryType] = Field(
        default=None,
        description="Delete all memories of this type"
    )
    delete_data: bool = Field(
        default=False,
        description="Also delete all data associated with the memories"
    )


class BulkMemoryDeleteResponse(BaseModel):
    """Response model for bulk memory delete operations."""
    deleted_memories: int
    deleted_data_items: int = 0
    message: str


# =============================================================================
# Statistics Models
# =============================================================================

class AgentTypeStats(BaseModel):
    """Live per-agent-type data counts.

    Updated in real-time on every write/delete via the webhook sub-agent
    pipeline.  Unlike the batch-computed :class:`DataStats`, these counts
    are accurate at all times.
    """

    counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Per-agent-type item counts, e.g. {'pdf': 42, 'lidar': 3}",
    )
    total: int = Field(default=0, description="Sum of all per-type counts")
    last_updated: str = Field(default="", description="ISO 8601 timestamp of last update")


class DataStats(BaseModel):
    """Aggregated statistics about stored data items."""
    total_items: int = 0
    total_size_bytes: int = 0
    items_by_content_type: Dict[str, int] = Field(default_factory=dict)
    items_by_tag: Dict[str, int] = Field(default_factory=dict)
    avg_versions_per_item: float = 0.0


class MemoryStats(BaseModel):
    """Aggregated statistics about memories."""
    total_memories: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_duration: Dict[str, int] = Field(default_factory=dict)
    active_sessions: int = 0
    avg_data_per_memory: float = 0.0


# DEPRECATED: Use MemoryStats instead.
class SessionStats(BaseModel):
    """Aggregated statistics about sessions. DEPRECATED: use MemoryStats."""
    total_sessions: int = 0
    active_sessions: int = 0
    avg_data_per_session: float = 0.0
    avg_duration_seconds: float = 0.0


class EmbeddingStats(BaseModel):
    """Aggregated statistics about AI embeddings."""
    total_embeddings: int = 0
    by_engine: Dict[str, int] = Field(default_factory=dict)
    by_model: Dict[str, int] = Field(default_factory=dict)
    avg_dimensions: float = 0.0


class ViewpointStats(BaseModel):
    """Aggregated statistics about AI viewpoints."""
    total_viewpoints: int = 0
    by_engine: Dict[str, int] = Field(default_factory=dict)
    by_model: Dict[str, int] = Field(default_factory=dict)
    by_prompt: Dict[str, int] = Field(default_factory=dict)


class UserSummaryStats(BaseModel):
    """Aggregated statistics about users."""
    total_users: int = 0
    by_role: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    avg_data_per_user: float = 0.0
    avg_storage_per_user: float = 0.0


class GlobalStats(BaseModel):
    """Complete global statistics across all entities."""
    data: DataStats = Field(default_factory=DataStats)
    memories: MemoryStats = Field(default_factory=MemoryStats)
    embeddings: EmbeddingStats = Field(default_factory=EmbeddingStats)
    viewpoints: ViewpointStats = Field(default_factory=ViewpointStats)
    users: UserSummaryStats = Field(default_factory=UserSummaryStats)
    agent_types: AgentTypeStats = Field(
        default_factory=AgentTypeStats,
        description="Live per-agent-type data counts from the webhook routing pipeline",
    )
    computed_at: str = ""


class PerUserDataStats(BaseModel):
    """Per-user data statistics."""
    total_items: int = 0
    total_size_bytes: int = 0
    items_by_content_type: Dict[str, int] = Field(default_factory=dict)
    items_by_tag: Dict[str, int] = Field(default_factory=dict)
    recent_activity_7d: int = 0


class PerUserMemoryStats(BaseModel):
    """Per-user memory statistics."""
    total_memories: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)
    active_sessions: int = 0


# DEPRECATED: Use PerUserMemoryStats instead.
class PerUserSessionStats(BaseModel):
    """Per-user session statistics. DEPRECATED: use PerUserMemoryStats."""
    total_sessions: int = 0
    active_sessions: int = 0
    devices_used: List[str] = Field(default_factory=list)


class PerUserEmbeddingStats(BaseModel):
    """Per-user embedding statistics."""
    total_embeddings: int = 0
    by_engine: Dict[str, int] = Field(default_factory=dict)
    by_model: Dict[str, int] = Field(default_factory=dict)


class PerUserViewpointStats(BaseModel):
    """Per-user viewpoint statistics."""
    total_viewpoints: int = 0
    by_engine: Dict[str, int] = Field(default_factory=dict)
    by_model: Dict[str, int] = Field(default_factory=dict)


class PerUserTokenStats(BaseModel):
    """Per-user LLM token usage statistics."""
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_requests: int = 0
    by_model: Dict[str, int] = Field(default_factory=dict)
    by_agent_type: Dict[str, int] = Field(default_factory=dict)


class TokenUsageRecord(BaseModel):
    """A single token usage event reported by the webhook agent."""
    user_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    agent_type: str = ""
    duration_ms: Optional[float] = None


class PerUserStats(BaseModel):
    """Complete statistics for a single user."""
    user_id: str
    data: PerUserDataStats = Field(default_factory=PerUserDataStats)
    memories: PerUserMemoryStats = Field(default_factory=PerUserMemoryStats)
    embeddings: PerUserEmbeddingStats = Field(default_factory=PerUserEmbeddingStats)
    viewpoints: PerUserViewpointStats = Field(default_factory=PerUserViewpointStats)
    tokens: PerUserTokenStats = Field(default_factory=PerUserTokenStats)
    computed_at: str = ""


# =============================================================================
# Telemetry — OpenTelemetry-compatible span models
# =============================================================================

class SpanKind(str, Enum):
    """OpenTelemetry SpanKind values."""
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    INTERNAL = "INTERNAL"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class SpanStatusCode(str, Enum):
    """OpenTelemetry StatusCode values."""
    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


class SpanStatus(BaseModel):
    """OTel-compatible span status."""
    code: SpanStatusCode = SpanStatusCode.UNSET
    message: Optional[str] = None


class SpanEvent(BaseModel):
    """A timestamped event within a span."""
    name: str
    timestamp: str
    attributes: Dict[str, Any] = Field(default_factory=dict)


class TelemetrySpan(BaseModel):
    """
    OpenTelemetry-compatible span stored inside a ``tracing`` memory.

    One span is written per service stage per webhook invocation.
    All spans for a single webhook share the same ``trace_id``.

    Field mapping to OTel specification:
    - ``trace_id``       → TraceId (128-bit hex, 32 chars)
    - ``span_id``        → SpanId (64-bit hex, 16 chars)
    - ``parent_span_id`` → ParentSpanId (optional; absent on root span)
    - ``name``           → Span name (e.g. ``"webhook.receiver"``)
    - ``kind``           → SpanKind
    - ``status``         → Status (code + optional message)
    - ``start_time``     → StartTimeUnixNano (ISO-8601 string here)
    - ``end_time``       → EndTimeUnixNano (ISO-8601 string here; null if in-progress)
    - ``duration_ms``    → Derived from start/end; convenience field
    - ``attributes``     → Attributes key-value map
    - ``events``         → Events list
    """
    trace_id: str = Field(..., description="128-bit trace identifier (32 hex chars)")
    span_id: str = Field(..., description="64-bit span identifier (16 hex chars)")
    parent_span_id: Optional[str] = Field(None, description="Parent span ID; absent on root span")
    name: str = Field(..., description="Operation name, e.g. 'webhook.receiver'")
    kind: SpanKind = SpanKind.INTERNAL
    service_name: str = Field(..., description="Human-readable service name")
    service_type: str = Field(..., description="GCP service classification")
    status: SpanStatus = Field(default_factory=SpanStatus)
    start_time: str = Field(..., description="ISO-8601 UTC timestamp")
    end_time: Optional[str] = Field(None, description="ISO-8601 UTC timestamp; null if still running")
    duration_ms: Optional[float] = Field(None, description="Wall-clock duration in milliseconds")
    attributes: Dict[str, Any] = Field(default_factory=dict)
    events: List[SpanEvent] = Field(default_factory=list)


# =============================================================================
# VM Instance Models (model categories)
# =============================================================================

class VmInstanceCreate(BaseModel):
    """Request model for creating a VM instance."""
    machine_type: str = Field(..., pattern=r"^(g2-standard-8|g2-standard-24|a2-highgpu-1g|a2-ultragpu-1g)$")
    base_url: str = Field(..., min_length=1, max_length=500, description="HTTP(S) URL to VM's /v1/chat/completions endpoint")
    active_model_id: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, max_length=200)
    labels: Optional[Dict[str, str]] = None
    health_check_url: Optional[str] = Field(None, max_length=500)


class VmInstanceUpdate(BaseModel):
    """Request model for updating a VM instance."""
    base_url: Optional[str] = Field(None, min_length=1, max_length=500)
    active_model_id: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, pattern=r"^(active|stopped|error)$")
    name: Optional[str] = Field(None, max_length=200)
    labels: Optional[Dict[str, str]] = None
    health_check_url: Optional[str] = Field(None, max_length=500)


class VmInstance(BaseModel):
    """VM instance model."""
    id: str
    machine_type: str
    base_url: str
    active_model_id: Optional[str]
    status: str
    name: Optional[str]
    user_id: str
    labels: Dict[str, str]
    health_check_url: Optional[str]
    created_at: str
    updated_at: str
    deleted_at: Optional[str]


class VmInstanceResponse(BaseModel):
    """Response model for VM instance (without internal fields)."""
    id: str
    machine_type: str
    base_url: str
    active_model_id: Optional[str]
    status: str
    name: Optional[str]
    labels: Dict[str, str]
    health_check_url: Optional[str]
    created_at: str
    updated_at: str


# =============================================================================
# LLM Models (model categories)
# =============================================================================

class PublicLlmCreate(BaseModel):
    """Request model for creating an LLM configuration.

    For provider=custom: api_base_url is required; model_id is optional.
    For other providers: model_id is required.
    """
    provider: str = Field(
        ...,
        pattern=r"^(openai|anthropic|gemini|xai|mistral|cohere_chat|groq|deepseek|togetherai|ollama_cloud|openrouter|moonshot|cerebras|zai|huggingface|vercel_ai_gateway|minimax|custom)$",
    )
    model_id: Optional[str] = Field(None, max_length=100, description="Provider-specific model ID; optional for custom")
    display_name: str = Field(..., min_length=1, max_length=200, description="Human-readable name")
    api_key: Optional[str] = Field(None, min_length=1, description="Plain text API key (will be encrypted). Not required for custom (Local Ollama).")
    api_base_url: Optional[str] = Field(None, max_length=500, description="Required for custom; optional override for others")
    max_tokens_default: Optional[int] = Field(None, ge=1, le=100000)
    temperature_default: Optional[float] = Field(None, ge=0.0, le=2.0)

    @model_validator(mode="after")
    def validate_custom_fields(self) -> "PublicLlmCreate":
        if self.provider == "custom":
            if not (self.api_base_url and self.api_base_url.strip()):
                raise ValueError("api_base_url is required for custom provider")
        else:
            if not (self.model_id and self.model_id.strip()):
                raise ValueError("model_id is required for non-custom providers")
        return self


class PublicLlmUpdate(BaseModel):
    """Request model for updating an LLM configuration. model_id can be empty for custom."""
    provider: Optional[str] = Field(
        None,
        pattern=r"^(openai|anthropic|gemini|xai|mistral|cohere_chat|groq|deepseek|togetherai|ollama_cloud|openrouter|moonshot|cerebras|zai|huggingface|vercel_ai_gateway|minimax|custom)$",
    )
    model_id: Optional[str] = Field(None, max_length=100)
    display_name: Optional[str] = Field(None, min_length=1, max_length=200)
    api_key: Optional[str] = Field(None, min_length=10, description="New API key (will be encrypted)")
    api_base_url: Optional[str] = Field(None, max_length=500)
    max_tokens_default: Optional[int] = Field(None, ge=1, le=100000)
    temperature_default: Optional[float] = Field(None, ge=0.0, le=2.0)


class PublicLlm(BaseModel):
    """LLM configuration model (with encrypted key)."""
    id: str
    provider: str
    model_id: str
    display_name: str
    has_api_key: bool
    api_base_url: Optional[str]
    user_id: str
    max_tokens_default: Optional[int]
    temperature_default: Optional[float]
    created_at: str
    updated_at: str
    deleted_at: Optional[str]


class PublicLlmResponse(BaseModel):
    """Response model for LLM (without internal fields or key)."""
    id: str
    provider: str
    model_id: str
    display_name: str
    has_api_key: bool
    api_base_url: Optional[str]
    max_tokens_default: Optional[int]
    temperature_default: Optional[float]
    created_at: str
    updated_at: str


# =============================================================================
# Integration Platform Models (Nango-like provider + connection management)
# =============================================================================

class AuthMode(str, Enum):
    OAUTH2 = "OAUTH2"
    API_KEY = "API_KEY"
    BASIC = "BASIC"
    NONE = "NONE"


class ConnectionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class IntegrationProvider(BaseModel):
    """Provider catalog entry (never exposes client_id/secret)."""
    provider_key: str
    display_name: str
    description: str = ""
    logo_url: str = ""
    category: str = "other"
    app_category: str = "business-ops"
    capabilities: List[str] = Field(default_factory=list)
    channel_key: Optional[str] = None
    auth_mode: str = AuthMode.OAUTH2
    authorization_url: str = ""
    token_url: str = ""
    scope: str = ""
    proxy_base_url: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True
    oauth_configured: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OAuthCredentialsUpdate(BaseModel):
    """Request body for setting a provider's OAuth client credentials."""
    client_id: str = Field(min_length=1, description="OAuth client ID")
    client_secret: str = Field(min_length=1, description="OAuth client secret")


class IntegrationProviderCreate(BaseModel):
    """Request body for creating/updating a provider."""
    display_name: str
    description: str = ""
    logo_url: str = ""
    category: str = "other"
    app_category: str = "business-ops"
    capabilities: List[str] = Field(default_factory=list)
    channel_key: Optional[str] = None
    auth_mode: str = AuthMode.OAUTH2
    authorization_url: str = ""
    token_url: str = ""
    scope: str = ""
    proxy_base_url: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True


class IntegrationConnection(BaseModel):
    """User-provider connection (no secrets)."""
    connection_id: str
    user_id: str
    provider_key: str
    display_name: Optional[str] = ""
    account_id: Optional[str] = ""
    account_email: Optional[str] = ""
    status: str = ConnectionStatus.ACTIVE
    status_message: Optional[str] = ""
    scopes: Optional[str] = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class IntegrationConnectionCreate(BaseModel):
    """Request body for creating an API-key connection."""
    user_id: str
    provider_key: str
    display_name: str = ""
    api_key: str = ""
    account_id: str = ""
    account_email: str = ""
    scopes: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IntegrationCredentials(BaseModel):
    """Decrypted credentials (internal use only)."""
    connection_id: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    api_key: Optional[str] = None
    token_type: str = "bearer"
    expires_at: Optional[str] = None


# -------------------------------------------------------------------------
# Graph Memory — Entities & Relationships
# -------------------------------------------------------------------------

class EntityCreate(BaseModel):
    """Request model for creating an entity."""
    entity_type: str  # person, organization, product, location, date, url, concept, event
    entity_name: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Entity(BaseModel):
    """Stored entity extracted from data."""
    entity_id: str
    data_id: str
    user_id: str
    entity_type: str
    entity_name: str
    canonical_form: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class RelationshipCreate(BaseModel):
    """Request model for creating a relationship between entities."""
    source: str  # entity name (resolved to entity_id server-side)
    target: str  # entity name (resolved to entity_id server-side)
    rel_type: str  # works_at, located_in, part_of, mentions, etc.
    strength: float = 1.0
    description: Optional[str] = None


class Relationship(BaseModel):
    """Stored relationship between two entities."""
    rel_id: str
    user_id: str
    data_id: str
    source_entity_id: str
    target_entity_id: str
    rel_type: str
    strength: float = 1.0
    description: Optional[str] = None
    created_at: str = ""


class EntityBatchRequest(BaseModel):
    """Batch create entities and relationships for a data item."""
    data_id: str
    user_id: str
    entities: List[EntityCreate] = Field(default_factory=list)
    relationships: List[RelationshipCreate] = Field(default_factory=list)


class EntityBatchResponse(BaseModel):
    """Response for batch entity creation."""
    entities_created: int = 0
    relationships_created: int = 0
    entity_ids: List[str] = Field(default_factory=list)


class GraphSearchResult(BaseModel):
    """Search result from entity graph."""
    entity_id: str
    entity_type: str
    entity_name: str
    canonical_form: str
    confidence: float = 1.0
    data_id: str = ""
    related_data_ids: List[str] = Field(default_factory=list)
    relationships: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Memory Compression
# ============================================================================

class CompressMemoryRequest(BaseModel):
    """Request to compress a memory's data items into a summary."""
    archive_originals: bool = False
    max_summary_length: int = 2000

class CompressMemoryResponse(BaseModel):
    """Response from memory compression."""
    memory_id: str
    summary_data_id: str
    original_count: int
    summary_length: int
    archived: bool = False


# ============================================================================
# Webhooks (per-user webhook endpoints)
# ============================================================================

class WebhookStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DELETED = "deleted"


class WebhookCreate(BaseModel):
    """Create a new webhook endpoint."""
    channel_type: str
    name: str = ""
    generate_secret: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)


class WebhookUpdate(BaseModel):
    """Update an existing webhook."""
    name: Optional[str] = None
    channel_type: Optional[str] = None
    status: Optional[WebhookStatus] = None
    config: Optional[Dict[str, Any]] = None


class WebhookResponse(BaseModel):
    """Webhook resource returned to clients."""
    webhook_id: str
    user_id: str
    channel_type: str
    name: str = ""
    status: str = "active"
    url: Optional[str] = None
    secret: Optional[str] = None  # only returned on creation
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WebhookEventResponse(BaseModel):
    """A single webhook event log entry."""
    event_id: str
    webhook_id: str
    user_id: str
    channel_type: str
    status: str
    error_message: Optional[str] = None
    error_stage: Optional[str] = None
    payload_bytes: Optional[int] = None
    latency_ms: Optional[int] = None
    trace_id: Optional[str] = None
    created_at: Optional[str] = None

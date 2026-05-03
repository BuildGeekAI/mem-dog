export interface VersionInfo {
  version: number;
  timestamp: string;
  size: number;
  content_type: string;
  /** URL-safe version label matching the storage path, e.g. "ver_20250225T143022Z" */
  version_label?: string | null;
}

/**
 * Access control list for data items.
 * - null/undefined: Public access (everyone can access)
 * - ["*"]: All authenticated users
 * - ["user:uuid"]: Specific user by ID
 * - ["role:name"]: Specific role (admin, user, viewer)
 */
export type AccessControl = string[] | null;

/**
 * Device information captured when data is uploaded or an event is processed.
 * Extended with browser API fields for rich telemetry.
 */
export interface DataDeviceInfo {
  // Existing fields
  device_type?: string;         // desktop, mobile, tablet
  os?: string;                  // Windows, macOS, Linux, iOS, Android
  browser?: string;             // Chrome, Safari, Firefox, Edge
  app_version?: string;         // mem-dog UI / client app version
  user_agent?: string;          // Raw User-Agent string
  ip_address?: string;          // Client IP (if available)
  // Extended — collected via browser APIs
  screen_width?: number;        // window.screen.width
  screen_height?: number;       // window.screen.height
  timezone?: string;            // Intl timezone, e.g. "America/New_York"
  language?: string;            // navigator.language, e.g. "en-US"
  cpu_cores?: number;           // navigator.hardwareConcurrency
  memory_gb?: number;           // navigator.deviceMemory (Chrome only)
  connection_type?: string;     // navigator.connection.effectiveType
  device_id?: string;           // Persistent per-device UUID from localStorage
}

/** Records one service that handled an event in the processing chain. */
export interface ServiceParticipant {
  service_name: string;          // e.g. "mem-dog-api", "webhook-processor"
  service_type: string;          // e.g. "fastapi", "gcp_cloud_function"
  service_version?: string | null;
  action: string;                // e.g. "create_data", "route_payload"
  timestamp: string;             // ISO-8601 UTC
  span_id?: string | null;
}

/** Rich provenance — user, device, and ordered services audit trail. */
export interface DataProvenance {
  user?: Record<string, unknown> | null;  // {user_id, username, email, role, display_name}
  device?: DataDeviceInfo | null;
  services?: ServiceParticipant[];
  source?: unknown | null;
  correlation?: unknown | null;
  memory_dict?: unknown | null;
}

/** Canonical inter-service event metadata block. */
export interface EventMeta {
  user_id: string;
  data_id?: string | null;
  version?: number | null;
  version_label?: string | null;
  timestamp?: string | null;
  trace_id?: string | null;
  span_id?: string | null;
  parent_span_id?: string | null;
  trace_memory_id?: string | null;
  session_id?: string | null;
  memory_list?: string[] | null;
  services?: ServiceParticipant[];
  device?: DataDeviceInfo | null;
}

/** Structured ownership / provenance metadata (Plan 1). */
export interface DataOwner {
  user?: { user_id?: string; username?: string } | null;
  source?: {
    channel?: {
      channel_type?: string;
      channel_id?: string;
      peer_id?: string;
      thread_id?: string;
    } | null;
    device?: Record<string, unknown> | null;
  } | null;
  correlation?: Record<string, unknown> | null;
  memory_dict?: {
    telemetry?: string[];
    session?: string[];
    agent?: string[];
    conversation?: string[];
  } | null;
}

export interface DataMetadata {
  data_id: string;
  current_version: number;
  versions: VersionInfo[];
  created_at: string;
  updated_at: string;
  name?: string | null;
  description?: string | null;
  access?: AccessControl;
  memory_ids?: string[] | null;
  /** @deprecated Use memory_ids instead. */
  session_id?: string;
  device_info?: DataDeviceInfo;
  tags?: string[] | null;
  /** Absolute URL to access this data's content (computed by the API at response time). */
  address?: string | null;
  /** Plan 1 — remote source URL */
  url?: string | null;
  /** Plan 1 — MIME type declared or detected at ingest */
  mime_type?: string | null;
  /** Plan 1 — true once the remote URL has been downloaded and stored locally */
  is_downloaded?: boolean;
  /** Plan 1 — structured ownership / provenance metadata (lightweight, backward-compat) */
  owner?: DataOwner | null;
  /** Rich provenance: user, device, ordered services audit trail */
  provenance?: DataProvenance | null;
  /** Which service wrote this data item */
  source_service?: string | null;
  /** Human-readable version label matching the storage path (ver_20250225T143022Z) */
  data_version_label?: string | null;
}

export interface DataListItem {
  data_id: string;
  current_version: number;
  created_at: string;
  updated_at: string;
  content_type: string;
  size: number;
  name?: string | null;
  description?: string | null;
  access?: AccessControl;
  memory_ids?: string[] | null;
  tags?: string[] | null;
  /** Absolute URL to access this data's content (computed by the API at response time). */
  address?: string | null;
  /** Plan 1 — remote source URL */
  url?: string | null;
  /** Plan 1 — MIME type declared or detected at ingest */
  mime_type?: string | null;
  /** Plan 1 — true once the remote URL has been downloaded and stored locally */
  is_downloaded?: boolean;
  /** Rich provenance for display in the UI */
  provenance?: DataProvenance | null;
  source_service?: string | null;
  data_version_label?: string | null;
}

/** Paginated response for GET /api/v1/data. */
export interface DataListResponse {
  items: DataListItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface InfoUpdate {
  name?: string | null;
  description?: string | null;
}

export interface InfoResponse {
  data_id: string;
  name: string | null;
  description: string | null;
}

// =============================================================================
// Tags Types
// =============================================================================

export interface TagsResponse {
  data_id: string;
  tags: string[] | null;
}

export interface TagsUpdate {
  tags: string[] | null;
}

export interface TagsAdd {
  tags: string[];
}

export interface TagsRemove {
  tags: string[];
}

export interface TagSearchResult {
  items: DataListItem[];
  total: number;
}

export interface AccessUpdate {
  access: AccessControl;
}

export interface AccessCheckResponse {
  data_id: string;
  has_access: boolean;
  access: AccessControl;
}

/** @deprecated Use MemoryDataEntry via the /memories/{id}/entries endpoint. */
export interface TimelineEntry {
  user: string;
  data_id: string;
  version: number;
  action: string;
  timestamp: number;
}

export interface CreateDataResponse {
  data_id: string;
  version: number;
  message: string;
}

export interface UpdateDataResponse {
  data_id: string;
  version: number;
  message: string;
}

// =============================================================================
// Bulk Delete Types
// =============================================================================

export interface BulkDeleteRequest {
  data_ids: string[];
}

export interface BulkDeleteResponse {
  deleted_count: number;
  failed_count: number;
  deleted_ids: string[];
  failed_ids: string[];
  message: string;
}

export interface UserDataDeleteResponse {
  user: string;
  deleted_count: number;
  message: string;
}

export interface MemoryDataDeleteResponse {
  memory_id: string;
  deleted_count: number;
  failed_count: number;
  deleted_ids: string[];
  message: string;
}

export interface BulkMemoryDeleteRequest {
  memory_ids?: string[] | null;
  user_id?: string | null;
  memory_type?: MemoryType | null;
  delete_data?: boolean;
}

export interface BulkMemoryDeleteResponse {
  deleted_memories: number;
  deleted_data_items: number;
  message: string;
}

// =============================================================================
// AI Layer Types
// =============================================================================

/**
 * Supported AI engine types.
 * 
 * Native Support:
 * - openai: OpenAI API (GPT-4, embeddings)
 * - anthropic: Anthropic API (Claude models)
 * - gemini: Google Gemini API
 * - ollama: Local Ollama server
 * - bedrock: Amazon Bedrock
 * - openrouter: OpenRouter multi-provider gateway
 * - together: Together AI
 * - huggingface: Hugging Face Inference API
 * - vllm: vLLM local server
 * - litellm: LiteLLM unified gateway (supports 100+ providers)
 * 
 * Via LiteLLM: NVIDIA, Venice, Cloudflare, Vercel, Moonshot, Qwen, GLM,
 *              MiniMax, Qianfan, Z.AI, Groq, Mistral, Cohere, and more.
 * See: https://docs.openclaw.ai/providers
 */
export type AIEngineType = 
  | 'openai' 
  | 'anthropic' 
  | 'gemini' 
  | 'ollama' 
  | 'bedrock' 
  | 'openrouter' 
  | 'together' 
  | 'huggingface' 
  | 'vllm' 
  | 'litellm';

export type AIKeyMode = 'system' | 'custom';

/**
 * AI Signature - Records which AI system generated the content.
 * Provides full traceability for all AI-generated artifacts.
 */
export interface AISignature {
  ai_engine: AIEngineType;
  model_name: string;
  model_version?: string;
  api_version?: string;
  generated_at: string;
  generation_id?: string;
  key_mode: AIKeyMode;
  temperature?: number;
  max_tokens?: number;
  additional_params?: Record<string, unknown>;
}

export interface EmbeddingSummary {
  data_id: string;
  data_version: number;
  embeddings_count: number;
  ai_engine: AIEngineType;
  model: string;
  dimensions: number;
  created_at: string;
  ai_signature?: AISignature;
}

export interface ViewpointResponse {
  viewpoint_id: string;
  data_id: string;
  data_version: number;
  prompt_id: string;
  ai_engine: AIEngineType;
  model: string;
  output_content: string;
  version: number;
  created_at: string;
  updated_at: string;
  ai_signature?: AISignature;
}

export interface AIQueryResponse {
  answer: string;
  sources: Array<{
    data_id: string;
    chunk_text: string;
    score: number;
  }>;
  model: string;
  ai_engine: AIEngineType;
  ai_signature?: AISignature;
}

export interface UserAIPreferences {
  user: string;
  ai_key_mode: AIKeyMode;
  default_engine_id?: string;
  default_embedding_model?: string;
  default_completion_model?: string;
  auto_generate_embeddings: boolean;
  preferred_engines?: Record<string, string>;
  created_at: string;
  updated_at: string;
}

// =============================================================================
// User Management Types
// =============================================================================

export type UserStatus = 'active' | 'inactive' | 'suspended';
export type UserRole = 'admin' | 'user' | 'viewer';

export interface UserCreate {
  username: string;
  email: string;
  display_name?: string;
  role?: UserRole;
  metadata?: Record<string, unknown>;
}

export interface UserUpdate {
  username?: string;
  email?: string;
  display_name?: string;
  role?: UserRole;
  status?: UserStatus;
  metadata?: Record<string, unknown>;
}

export interface UserResponse {
  user_id: string;
  username: string;
  email: string;
  display_name?: string;
  role: UserRole;
  status: UserStatus;
  metadata: Record<string, unknown>;
  data_count: number;
  storage_used_bytes: number;
  created_at: string;
  updated_at: string;
  last_active_at?: string;
  default_org_id?: string;
  default_project_id?: string;
}

export interface UserListResponse {
  users: UserResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface APIKeyCreate {
  name: string;
  expires_in_days?: number;
}

export interface APIKeyResponse {
  key_id: string;
  name: string;
  key?: string; // Only shown once on creation
  created_at: string;
  expires_at?: string;
}

// =============================================================================
// Organization & Project Types
// =============================================================================

export type OrgRole = 'owner' | 'admin' | 'member' | 'viewer';

export interface Organization {
  org_id: string;
  name: string;
  display_name?: string | null;
  owner_user_id: string;
  metadata: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Project {
  project_id: string;
  org_id: string;
  name: string;
  display_name?: string | null;
  description?: string | null;
  metadata: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface OrgMember {
  org_id: string;
  user_id: string;
  role: OrgRole;
  created_at: string;
}

// =============================================================================
// Channel identity correlation (channel <-> user_id)
// =============================================================================

export interface ChannelIdentityCreate {
  channel_type: string;
  channel_unique_id: string;
  user_id: string;
  display_name?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ChannelIdentityRecord {
  channel_type: string;
  channel_unique_id: string;
  user_id: string;
  display_name?: string | null;
  added_at: string;
  metadata?: Record<string, unknown>;
}

export interface ChannelIdentityListResponse {
  user_id: string;
  identities: ChannelIdentityRecord[];
}

export interface ChannelIdentityUpdate {
  display_name?: string | null;
  metadata?: Record<string, unknown> | null;
}

// =============================================================================
// Channels bucket — per-channel metadata
// =============================================================================

export interface ChannelMetadata {
  channel_type: string;
  display_name?: string | null;
  description?: string | null;
  config: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ChannelMetadataCreate {
  display_name?: string | null;
  description?: string | null;
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

// =============================================================================
// Memory Management Types
// =============================================================================

export type MemoryType =
  | 'timeline'
  | 'session'
  | 'conversation'
  | 'user'
  | 'organizational'
  | 'factual'
  | 'episodic'
  | 'semantic'
  | 'custom'
  | 'tracing';

export type MemoryCategory = 'conversation' | 'session' | 'user' | 'organizational';

export type AccessLevel = 'private' | 'shared' | 'public' | 'restricted';

// =============================================================================
// Telemetry Types — OpenTelemetry-compatible pipeline span models
// =============================================================================

export type SpanKind = 'SERVER' | 'CLIENT' | 'INTERNAL' | 'PRODUCER' | 'CONSUMER';
export type SpanStatusCode = 'OK' | 'ERROR' | 'UNSET';

export interface SpanStatus {
  code: SpanStatusCode;
  message?: string;
}

export interface SpanEvent {
  name: string;
  timestamp: string;
  attributes?: Record<string, unknown>;
}

/**
 * OpenTelemetry-compatible span stored in a ``telemetry`` memory.
 * One span is written per service stage per webhook invocation.
 */
export interface TelemetrySpan {
  trace_id: string;
  span_id: string;
  parent_span_id?: string | null;
  name: string;
  kind: SpanKind;
  service_name: string;
  service_type: string;
  status: SpanStatus;
  start_time: string;
  end_time?: string | null;
  duration_ms?: number | null;
  pipeline?: string;
  attributes?: Record<string, unknown>;
  events?: SpanEvent[];
  /** UI-assigned field: the data_id of the span's data item in the memory. */
  data_id?: string;
}

/**
 * A group of spans sharing the same trace_id — the full journey of one webhook.
 */
export interface TelemetryTrace {
  trace_id: string;
  spans: TelemetrySpan[];
  start_time: string;
  end_time?: string;
  duration_ms?: number;
  /** Overall status: OK if all spans OK, ERROR if any ERROR, PARTIAL if incomplete. */
  status: 'OK' | 'ERROR' | 'PARTIAL';
  /** Ordered list of service names that participated in this trace. */
  services: string[];
}

export type MemoryDuration = 'short_term' | 'long_term';

export interface DeviceInfo {
  type?: string;  // desktop, mobile, tablet
  os?: string;
  browser?: string;
  app_version?: string;
}

export interface MemoryCreate {
  memory_id?: string;
  memory_type: MemoryType;
  name?: string;
  description?: string;
  user_id: string;
  /** Custom sub-type (e.g. legal, hr, customer). Typically used with custom memory type. */
  sub_type?: string;
  metadata?: Record<string, unknown>;
  access_level?: AccessLevel;
  shared_with?: string[];
  device_id?: string;
  device_info?: DeviceInfo;
  /** TTL in hours. Applies to all types; overrides the type's default TTL. */
  ttl_hours?: number;
  /** When true, override default TTL and never expire this memory. */
  no_expiry?: boolean;
  org_id?: string;
  project_id?: string;
}

export interface MemoryUpdate {
  name?: string;
  description?: string;
  sub_type?: string;
  metadata?: Record<string, unknown>;
  device_info?: DeviceInfo;
  active?: boolean;
  access_level?: AccessLevel;
  shared_with?: string[];
  expires_at?: string;
  extend_ttl_hours?: number;
}

export interface MemoryResponse {
  memory_id: string;
  memory_type: MemoryType;
  duration: MemoryDuration;
  category?: MemoryCategory;
  name: string;
  description?: string;
  user_id: string;
  sub_type?: string;
  data_count: number;
  data_ids: string[];
  metadata: Record<string, unknown>;
  access_level?: AccessLevel;
  shared_with?: string[];
  device_id?: string;
  device_info?: DeviceInfo;
  active?: boolean;
  expires_at?: string;
  created_at: string;
  updated_at: string;
  org_id?: string;
  project_id?: string;
}

export interface MemoryListResponse {
  items: MemoryResponse[];
  total: number;
  skip: number;
  limit: number;
}

export interface MemoryAddDataRequest {
  data_ids: string[];
  metadata?: Record<string, unknown>;
}

export interface MemoryDataEntry {
  data_id: string;
  memory_id: string;
  action?: string;
  version?: number;
  associated_at: string;
  metadata: Record<string, unknown>;
}

// =============================================================================
// Statistics Types
// =============================================================================

export interface DataStats {
  total_items: number;
  total_size_bytes: number;
  items_by_content_type: Record<string, number>;
  items_by_tag: Record<string, number>;
  avg_versions_per_item: number;
}

export interface MemoryStatsData {
  total_memories: number;
  by_type: Record<string, number>;
  by_duration: Record<string, number>;
  active_sessions: number;
  avg_data_per_memory: number;
}

export interface EmbeddingStatsData {
  total_embeddings: number;
  by_engine: Record<string, number>;
  by_model: Record<string, number>;
  avg_dimensions: number;
}

export interface ViewpointStatsData {
  total_viewpoints: number;
  by_engine: Record<string, number>;
  by_model: Record<string, number>;
  by_prompt: Record<string, number>;
}

export interface UserSummaryStats {
  total_users: number;
  by_role: Record<string, number>;
  by_status: Record<string, number>;
  avg_data_per_user: number;
  avg_storage_per_user: number;
}

export interface GlobalStats {
  data: DataStats;
  memories: MemoryStatsData;
  embeddings: EmbeddingStatsData;
  viewpoints: ViewpointStatsData;
  users: UserSummaryStats;
  computed_at: string;
}

export interface PerUserDataStats {
  total_items: number;
  total_size_bytes: number;
  items_by_content_type: Record<string, number>;
  items_by_tag: Record<string, number>;
  recent_activity_7d: number;
}

export interface PerUserMemoryStats {
  total_memories: number;
  by_type: Record<string, number>;
  active_sessions: number;
}

export interface PerUserEmbeddingStats {
  total_embeddings: number;
  by_engine: Record<string, number>;
  by_model: Record<string, number>;
}

export interface PerUserViewpointStats {
  total_viewpoints: number;
  by_engine: Record<string, number>;
  by_model: Record<string, number>;
}

export interface PerUserTokenStats {
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_requests: number;
  by_model: Record<string, number>;
  by_agent_type: Record<string, number>;
}

// =============================================================================
// Analysis Template Types
// =============================================================================

export type AnalysisTemplateKind = 'prompt' | 'skill';

export interface AnalysisTemplate {
  template_id: string;
  data_types: string[];
  kind: AnalysisTemplateKind;
  name: string;
  description: string;
  prompt_id?: string | null;
  skill_id?: string | null;
  template_text?: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface AnalysisTemplateCreate {
  data_types?: string[];
  kind?: AnalysisTemplateKind;
  name: string;
  description?: string;
  prompt_id?: string | null;
  skill_id?: string | null;
  template_text?: string | null;
  sort_order?: number;
}

export interface AnalysisTemplateUpdate {
  data_types?: string[];
  kind?: AnalysisTemplateKind;
  name?: string;
  description?: string;
  prompt_id?: string | null;
  skill_id?: string | null;
  template_text?: string | null;
  sort_order?: number;
}

// =============================================================================
// Agent Config Types (configurable pipeline prompts & skills)
// =============================================================================

export interface AgentConfig {
  config_id: string;
  agent_type: string;
  user_id: string | null;
  intro: string | null;
  system_prompt: string | null;
  output_schema: string | null;
  skills: string[];
  model_tier: string | null;
  parameters: Record<string, any>;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface AgentConfigCreate {
  agent_type: string;
  user_id?: string | null;
  intro?: string | null;
  system_prompt?: string | null;
  output_schema?: string | null;
  skills?: string[];
  model_tier?: string | null;
  parameters?: Record<string, any>;
}

export interface AgentConfigUpdate {
  intro?: string | null;
  system_prompt?: string | null;
  output_schema?: string | null;
  skills?: string[];
  model_tier?: string | null;
  parameters?: Record<string, any>;
}

export interface PerUserStats {
  user_id: string;
  data: PerUserDataStats;
  memories: PerUserMemoryStats;
  embeddings: PerUserEmbeddingStats;
  viewpoints: PerUserViewpointStats;
  tokens: PerUserTokenStats;
  computed_at: string;
}

// =============================================================================
// Integration Platform Types
// =============================================================================

export type AuthMode = 'OAUTH2' | 'API_KEY' | 'BASIC' | 'NONE';
export type ConnectionStatus = 'active' | 'expired' | 'revoked' | 'error';

export interface IntegrationProvider {
  provider_key: string;
  display_name: string;
  description?: string | null;
  logo_url?: string | null;
  category: string;
  app_category: string;
  capabilities: string[];
  channel_key?: string | null;
  auth_mode: AuthMode;
  authorization_url?: string | null;
  token_url?: string | null;
  scope?: string | null;
  proxy_base_url?: string | null;
  config?: Record<string, unknown>;
  is_enabled: boolean;
  /** Whether OAuth client credentials are configured (DB or env vars). Always true for API_KEY providers. */
  oauth_configured: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface IntegrationConnection {
  connection_id: string;
  user_id: string;
  provider_key: string;
  display_name?: string | null;
  account_id?: string | null;
  account_email?: string | null;
  status: ConnectionStatus;
  status_message?: string | null;
  scopes?: string | null;
  metadata?: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface IntegrationConnectionCreate {
  user_id: string;
  provider_key: string;
  display_name?: string;
  api_key?: string;
  account_id?: string;
  account_email?: string;
  scopes?: string;
  metadata?: Record<string, unknown>;
}

// =============================================================================
// Model Garden Types
// =============================================================================

export interface ProviderInfo {
  engine_type: string;
  display_name: string;
  description: string;
  icon: string;
  requires_api_key: boolean;
  default_base_url?: string | null;
  api_key_placeholder?: string | null;
  litellm_prefix: string;
  auth_header: string;
  auth_scheme: string;
  models_endpoint?: string | null;
  default_models: string[];
  default_embedding_models: string[];
  category: 'cloud' | 'local' | 'gateway';
}

export interface EngineConfigResponse {
  engine_id: string;
  user: string;
  engine_type: string;
  name: string;
  base_url?: string | null;
  is_enabled: boolean;
  has_api_key: boolean;
  discovered_models: string[];
  last_tested_at?: string | null;
  last_test_status?: string | null;  // "success" | "error"
  created_at: string;
  updated_at: string;
}

export interface EngineTestResult {
  ok: boolean;
  latency_ms?: number | null;
  error?: string | null;
  tested_at: string;
}

export interface ProviderModels {
  engine_id: string;
  name: string;
  engine_type: string;
  litellm_prefix: string;
  models: string[];
  source: 'user' | 'system';
}

// ============================================================================
// Webhooks (per-user webhook endpoints)
// ============================================================================

export type WebhookStatus = 'active' | 'paused' | 'deleted';

export interface Webhook {
  webhook_id: string;
  user_id: string;
  channel_type: string;
  name: string;
  status: WebhookStatus;
  url?: string | null;
  secret?: string | null;
  config: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface WebhookCreate {
  channel_type: string;
  name?: string;
  generate_secret?: boolean;
  config?: Record<string, unknown>;
}

export interface WebhookUpdate {
  name?: string;
  channel_type?: string;
  status?: WebhookStatus;
  config?: Record<string, unknown>;
}

export interface WebhookEvent {
  event_id: string;
  webhook_id: string;
  user_id: string;
  channel_type: string;
  status: string;
  error_message?: string | null;
  error_stage?: string | null;
  payload_bytes?: number | null;
  latency_ms?: number | null;
  trace_id?: string | null;
  created_at?: string | null;
}

export interface WebhookStats {
  webhook_id: string;
  period: string;
  total: number;
  by_status: Record<string, number>;
  success_rate: number;
}

import type { MemDogConfig, SemanticSearchOptions, ChatOptions } from "./types.js";
import { MemDogError } from "./types.js";

type Params = Record<string, string | number | boolean | undefined>;

/**
 * Full-coverage mem-dog API client (~80 methods).
 *
 * For a simpler 7-method facade see {@link MemDog} in `simple.ts`.
 */
export class MemDogClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly userId?: string;
  private readonly timeout: number;

  constructor(config: MemDogConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, "");
    this.apiKey = config.apiKey;
    this.userId = config.userId;
    this.timeout = config.timeout ?? 30_000;
  }

  // ---------------------------------------------------------------------------
  // Internal helpers
  // ---------------------------------------------------------------------------

  private headers(extra?: Record<string, string>): Record<string, string> {
    const h: Record<string, string> = { ...extra };
    if (this.apiKey) {
      // API keys (platform / md_*) authenticate via x-api-key; JWTs via Bearer.
      // Send both so either credential type works when passed as apiKey.
      h["x-api-key"] = this.apiKey;
      h["Authorization"] = `Bearer ${this.apiKey}`;
    }
    return h;
  }

  private async request(method: string, path: string, opts?: {
    body?: BodyInit;
    headers?: Record<string, string>;
    params?: Params;
  }): Promise<Response> {
    let url = `${this.baseUrl}${path}`;
    if (opts?.params) {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(opts.params)) {
        if (v !== undefined && v !== "") qs.set(k, String(v));
      }
      const s = qs.toString();
      if (s) url += `?${s}`;
    }
    const res = await fetch(url, {
      method,
      headers: this.headers(opts?.headers),
      body: opts?.body,
      signal: AbortSignal.timeout(this.timeout),
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new MemDogError(res.status, body);
    }
    return res;
  }

  private async json<T = unknown>(method: string, path: string, opts?: {
    json?: unknown;
    params?: Params;
  }): Promise<T> {
    const res = await this.request(method, path, {
      body: opts?.json !== undefined ? JSON.stringify(opts.json) : undefined,
      headers: opts?.json !== undefined ? { "Content-Type": "application/json" } : undefined,
      params: opts?.params,
    });
    return (await res.json()) as T;
  }

  private uid(override?: string): string {
    return override ?? this.userId ?? "";
  }

  // ===================== ROOT =====================

  /** GET / */
  async root() { return this.json("GET", "/"); }
  /** GET /health */
  async health() { return this.json("GET", "/health"); }
  /** GET /api/v1/auth/me */
  async getMe() { return this.json("GET", "/api/v1/auth/me"); }

  // ===================== DATA =====================

  /** POST /api/v1/data (multipart) */
  async createData(opts: {
    file?: File | Blob;
    content?: string;
    name?: string;
    description?: string;
    tags?: string[];
    memoryIds?: string[];
    forwardToWebhook?: boolean;
    mimeType?: string;
    ownerUserId?: string;
    orgId?: string;
    projectId?: string;
    /** Idempotent upsert key (same external_id → same data_id). */
    externalId?: string;
  } = {}) {
    const form = new FormData();
    if (opts.content !== undefined) form.append("content", opts.content);
    if (opts.file) form.append("file", opts.file);
    if (opts.name) form.append("name", opts.name);
    if (opts.description) form.append("description", opts.description);
    if (opts.tags?.length) form.append("tags", opts.tags.join(","));
    if (opts.memoryIds?.length) form.append("memory_ids", opts.memoryIds.join(","));
    if (opts.forwardToWebhook) form.append("forward_to_webhook", "true");
    if (opts.mimeType) form.append("mime_type", opts.mimeType);
    if (opts.ownerUserId) form.append("owner_user_id", opts.ownerUserId);
    if (opts.orgId) form.append("org_id", opts.orgId);
    if (opts.projectId) form.append("project_id", opts.projectId);
    if (opts.externalId) form.append("external_id", opts.externalId);
    const res = await this.request("POST", "/api/v1/data", { body: form });
    return (await res.json()) as Record<string, unknown>;
  }

  /** POST /api/v1/data with ``external_id`` for create-or-update. */
  async upsertData(opts: {
    externalId: string;
    file?: File | Blob;
    content?: string;
    name?: string;
    description?: string;
    tags?: string[];
    mimeType?: string;
    ownerUserId?: string;
    orgId?: string;
    projectId?: string;
  }) {
    if (!(opts.externalId || "").trim()) {
      throw new Error("externalId is required for upsertData");
    }
    return this.createData({ ...opts, externalId: opts.externalId.trim() });
  }

  /** GET /api/v1/data */
  async listData(opts: { user?: string; skip?: number; limit?: number; tags?: string; matchAll?: boolean; projectId?: string } = {}) {
    return this.json("GET", "/api/v1/data", { params: { user: opts.user, skip: opts.skip, limit: opts.limit, tags: opts.tags, match_all: opts.matchAll, project_id: opts.projectId } });
  }

  /** GET /api/v1/data/{id} */
  async getData(dataId: string, opts: { version?: number; userId?: string } = {}) {
    const res = await this.request("GET", `/api/v1/data/${dataId}`, { params: { version: opts.version, user_id: opts.userId } });
    const ct = res.headers.get("content-type") ?? "";
    return ct.includes("json") ? res.json() : res.text();
  }

  /** GET /api/v1/data/{id}/metadata */
  async getMetadata(dataId: string) { return this.json("GET", `/api/v1/data/${dataId}/metadata`); }

  /** GET /api/v1/data/{id}/info */
  async getInfo(dataId: string) { return this.json("GET", `/api/v1/data/${dataId}/info`); }

  /** PUT /api/v1/data/{id}/info */
  async updateInfo(dataId: string, opts: { name?: string; description?: string }) {
    return this.json("PUT", `/api/v1/data/${dataId}/info`, { json: opts });
  }

  /** PUT /api/v1/data/{id} */
  async updateData(dataId: string, opts: { file?: File | Blob; content?: string }) {
    const form = new FormData();
    if (opts.content !== undefined) form.append("content", opts.content);
    if (opts.file) form.append("file", opts.file);
    const res = await this.request("PUT", `/api/v1/data/${dataId}`, { body: form });
    return (await res.json()) as Record<string, unknown>;
  }

  /** DELETE /api/v1/data/{id} */
  async deleteData(dataId: string) { await this.request("DELETE", `/api/v1/data/${dataId}`); }

  // ===================== TAGS =====================

  async getTags(dataId: string) { return this.json("GET", `/api/v1/data/${dataId}/tags`); }
  async updateTags(dataId: string, tags: string[]) { return this.json("PUT", `/api/v1/data/${dataId}/tags`, { json: { tags } }); }
  async addTags(dataId: string, tags: string[]) { return this.json("POST", `/api/v1/data/${dataId}/tags/add`, { json: { tags } }); }
  async removeTags(dataId: string, tags: string[]) { return this.json("POST", `/api/v1/data/${dataId}/tags/remove`, { json: { tags } }); }
  async listAllTags() { return this.json("GET", "/api/v1/tags"); }
  async searchByTags(tags: string[], opts: { matchAll?: boolean; userId?: string } = {}) {
    return this.json("GET", "/api/v1/tags/search", { params: { tags: tags.join(","), match_all: opts.matchAll, user_id: opts.userId } });
  }

  // ===================== VERSIONS =====================

  async listVersions(dataId: string) { return this.json("GET", `/api/v1/versions/${dataId}`); }

  // ===================== LIST =====================

  async listUserData(opts: { user?: string; format?: string; limit?: number; offset?: number } = {}) {
    return this.json("GET", "/api/v1/list", { params: { user: opts.user, format: opts.format ?? "meta", limit: opts.limit, offset: opts.offset } });
  }

  // ===================== ACCESS =====================

  async getAccess(dataId: string) { return this.json("GET", `/api/v1/data/${dataId}/access`); }
  async updateAccess(dataId: string, opts: { accessLevel?: string; sharedWith?: string[] }) {
    return this.json("PUT", `/api/v1/data/${dataId}/access`, { json: { access_level: opts.accessLevel, shared_with: opts.sharedWith } });
  }
  async checkAccess(dataId: string, opts: { userId?: string; role?: string } = {}) {
    return this.json("GET", `/api/v1/data/${dataId}/access/check`, { params: { user_id: opts.userId, role: opts.role } });
  }

  // ===================== MEMORIES =====================

  async createMemory(opts: { memoryType: string; name: string; userId?: string; ttlHours?: number; noExpiry?: boolean; accessLevel?: string }) {
    return this.json<Record<string, unknown>>("POST", "/api/v1/memories", {
      json: { memory_type: opts.memoryType, name: opts.name, user_id: opts.userId, ttl_hours: opts.ttlHours, no_expiry: opts.noExpiry, access_level: opts.accessLevel },
    });
  }

  async listMemories(opts: { userId?: string; memoryType?: string; duration?: string; active?: boolean; accessLevel?: string; category?: string; includeExpired?: boolean; projectId?: string; skip?: number; limit?: number } = {}) {
    return this.json("GET", "/api/v1/memories", {
      params: { user_id: opts.userId, memory_type: opts.memoryType, duration: opts.duration, active: opts.active, access_level: opts.accessLevel, category: opts.category, include_expired: opts.includeExpired, project_id: opts.projectId, skip: opts.skip, limit: opts.limit },
    });
  }

  async getMemory(memoryId: string) { return this.json<Record<string, unknown>>("GET", `/api/v1/memories/${memoryId}`); }
  async updateMemory(memoryId: string, payload: Record<string, unknown>) { return this.json("PUT", `/api/v1/memories/${memoryId}`, { json: payload }); }
  async deleteMemory(memoryId: string, opts: { deleteData?: boolean } = {}) { await this.request("DELETE", `/api/v1/memories/${memoryId}`, { params: { delete_data: opts.deleteData } }); }
  async addDataToMemory(memoryId: string, dataIds: string[]) { return this.json("POST", `/api/v1/memories/${memoryId}/data`, { json: { data_ids: dataIds } }); }
  async getMemoryData(memoryId: string, opts: { skip?: number; limit?: number } = {}) { return this.json("GET", `/api/v1/memories/${memoryId}/data`, { params: { skip: opts.skip, limit: opts.limit } }); }
  async removeDataFromMemory(memoryId: string, dataId: string) { await this.request("DELETE", `/api/v1/memories/${memoryId}/data/${dataId}`); }
  async compressMemory(memoryId: string, opts: { archiveOriginals?: boolean; maxSummaryLength?: number; userId?: string } = {}) {
    return this.json<Record<string, unknown>>("POST", `/api/v1/memories/${memoryId}/compress`, {
      json: { archive_originals: opts.archiveOriginals ?? false, max_summary_length: opts.maxSummaryLength ?? 2000 },
      params: { user_id: opts.userId },
    });
  }

  // ===================== USERS =====================

  async listUsers(opts: { limit?: number; offset?: number } = {}) { return this.json("GET", "/api/v1/users", { params: { limit: opts.limit, offset: opts.offset } }); }
  async getUser(userId: string) { return this.json<Record<string, unknown>>("GET", `/api/v1/users/${userId}`); }
  async createUser(payload: Record<string, unknown>) { return this.json<Record<string, unknown>>("POST", "/api/v1/users", { json: payload }); }
  async updateUser(userId: string, payload: Record<string, unknown>) { return this.json("PUT", `/api/v1/users/${userId}`, { json: payload }); }
  async deleteUser(userId: string) { await this.request("DELETE", `/api/v1/users/${userId}`); }
  async getUserByUsername(username: string) { return this.json<Record<string, unknown>>("GET", `/api/v1/users/username/${username}`); }
  async listApiKeys(userId: string) { return this.json("GET", `/api/v1/users/${userId}/api-keys`); }
  async createApiKey(userId: string, name: string) { return this.json<Record<string, unknown>>("POST", `/api/v1/users/${userId}/api-keys`, { json: { name } }); }
  async deleteApiKey(userId: string, keyId: string) { await this.request("DELETE", `/api/v1/users/${userId}/api-keys/${keyId}`); }

  // ===================== HOST SAAS =====================

  /** POST /api/v1/host/workspaces — provision org/project/user/md_* (platform key). */
  async createHostWorkspace(opts: {
    externalOrgId: string;
    externalWorkspaceId: string;
    displayName?: string;
    metadata?: Record<string, unknown>;
  }) {
    const payload: Record<string, unknown> = {
      external_org_id: opts.externalOrgId,
      external_workspace_id: opts.externalWorkspaceId,
    };
    if (opts.displayName !== undefined) payload.display_name = opts.displayName;
    if (opts.metadata !== undefined) payload.metadata = opts.metadata;
    return this.json<Record<string, unknown>>("POST", "/api/v1/host/workspaces", { json: payload });
  }

  /** GET /api/v1/host/workspaces */
  async getHostWorkspace(externalOrgId: string, externalWorkspaceId: string) {
    return this.json<Record<string, unknown>>("GET", "/api/v1/host/workspaces", {
      params: { external_org_id: externalOrgId, external_workspace_id: externalWorkspaceId },
    });
  }

  /** DELETE /api/v1/host/workspaces — sync purge (platform key). */
  async purgeHostWorkspace(
    externalOrgId: string,
    externalWorkspaceId: string,
    opts: { deleteConnections?: boolean; deleteServiceUser?: boolean } = {},
  ) {
    return this.json<Record<string, unknown>>("DELETE", "/api/v1/host/workspaces", {
      params: {
        external_org_id: externalOrgId,
        external_workspace_id: externalWorkspaceId,
        delete_connections: opts.deleteConnections ?? false,
        delete_service_user: opts.deleteServiceUser ?? true,
      },
    });
  }

  /** DELETE /api/v1/host/workspaces/by-project/{projectId} */
  async purgeHostWorkspaceByProject(
    projectId: string,
    opts: { deleteConnections?: boolean; deleteServiceUser?: boolean } = {},
  ) {
    return this.json<Record<string, unknown>>(
      "DELETE",
      `/api/v1/host/workspaces/by-project/${projectId}`,
      {
        params: {
          delete_connections: opts.deleteConnections ?? false,
          delete_service_user: opts.deleteServiceUser ?? true,
        },
      },
    );
  }

  /** GET /api/v1/host/workspaces/export */
  async exportHostWorkspace(externalOrgId: string, externalWorkspaceId: string) {
    return this.json<Record<string, unknown>>("GET", "/api/v1/host/workspaces/export", {
      params: { external_org_id: externalOrgId, external_workspace_id: externalWorkspaceId },
    });
  }

  /** GET /api/v1/host/api-keys — list keys (prefix only). */
  async listHostApiKeys(opts: { userId?: string } = {}) {
    return this.json("GET", "/api/v1/host/api-keys", { params: { user_id: opts.userId } });
  }

  /** POST /api/v1/host/api-keys */
  async createHostApiKey(name: string, opts: { userId?: string; expiresInDays?: number } = {}) {
    const payload: Record<string, unknown> = { name };
    if (opts.expiresInDays !== undefined) payload.expires_in_days = opts.expiresInDays;
    return this.json<Record<string, unknown>>("POST", "/api/v1/host/api-keys", {
      json: payload,
      params: { user_id: opts.userId },
    });
  }

  /** DELETE /api/v1/host/api-keys/{keyId} */
  async revokeHostApiKey(keyId: string, opts: { userId?: string; allowEmpty?: boolean } = {}) {
    await this.request("DELETE", `/api/v1/host/api-keys/${keyId}`, {
      params: { user_id: opts.userId, allow_empty: opts.allowEmpty },
    });
  }

  /** POST /api/v1/host/api-keys/rotate */
  async rotateHostApiKey(opts: {
    name?: string;
    revokeKeyId?: string;
    userId?: string;
    expiresInDays?: number;
  } = {}) {
    const payload: Record<string, unknown> = { name: opts.name ?? "host-rotated" };
    if (opts.revokeKeyId) payload.revoke_key_id = opts.revokeKeyId;
    if (opts.userId) payload.user_id = opts.userId;
    if (opts.expiresInDays !== undefined) payload.expires_in_days = opts.expiresInDays;
    return this.json<Record<string, unknown>>("POST", "/api/v1/host/api-keys/rotate", { json: payload });
  }

  // ===================== ORGANIZATIONS =====================

  async createOrganization(payload: Record<string, unknown>) { return this.json<Record<string, unknown>>("POST", "/api/v1/organizations", { json: payload }); }
  async listOrganizations() { return this.json("GET", "/api/v1/organizations"); }
  async getOrganization(orgId: string) { return this.json<Record<string, unknown>>("GET", `/api/v1/organizations/${orgId}`); }
  async updateOrganization(orgId: string, payload: Record<string, unknown>) { return this.json("PUT", `/api/v1/organizations/${orgId}`, { json: payload }); }
  async deleteOrganization(orgId: string) { await this.request("DELETE", `/api/v1/organizations/${orgId}`); }
  async addOrgMember(orgId: string, userId: string, role = "member") { return this.json("POST", `/api/v1/organizations/${orgId}/members`, { json: { user_id: userId, role } }); }
  async listOrgMembers(orgId: string) { return this.json("GET", `/api/v1/organizations/${orgId}/members`); }
  async updateOrgMember(orgId: string, userId: string, role: string) { return this.json("PUT", `/api/v1/organizations/${orgId}/members/${userId}`, { json: { role } }); }
  async removeOrgMember(orgId: string, userId: string) { await this.request("DELETE", `/api/v1/organizations/${orgId}/members/${userId}`); }

  // ===================== PROJECTS =====================

  async createProject(orgId: string, payload: Record<string, unknown>) { return this.json<Record<string, unknown>>("POST", `/api/v1/organizations/${orgId}/projects`, { json: payload }); }
  async listProjects(orgId: string) { return this.json("GET", `/api/v1/organizations/${orgId}/projects`); }
  async getProject(projectId: string) { return this.json<Record<string, unknown>>("GET", `/api/v1/projects/${projectId}`); }
  async updateProject(projectId: string, payload: Record<string, unknown>) { return this.json("PUT", `/api/v1/projects/${projectId}`, { json: payload }); }
  async deleteProject(projectId: string) { await this.request("DELETE", `/api/v1/projects/${projectId}`); }

  // ===================== AI / SEARCH =====================

  /** POST /api/v1/ai/query */
  async aiQuery(query: string, opts: { dataIds?: string[]; memoryIds?: string[] } = {}) {
    const payload: Record<string, unknown> = { query };
    if (opts.dataIds?.length) payload.data_ids = opts.dataIds;
    if (opts.memoryIds?.length) payload.memory_ids = opts.memoryIds;
    return this.json("POST", "/api/v1/ai/query", { json: payload });
  }

  /** POST /api/v1/ai/query/semantic — 5 search modes + 4 rerankers */
  async semanticSearch(query: string, opts: SemanticSearchOptions = {}) {
    const payload: Record<string, unknown> = { query };
    if (opts.searchMode) payload.search_mode = opts.searchMode;
    if (opts.reranker) payload.reranker = opts.reranker;
    if (opts.limit) payload.limit = opts.limit;
    if (opts.userId) payload.user_id = opts.userId;
    if (opts.projectId) payload.project_id = opts.projectId;
    if (opts.memoryType) payload.memory_type = opts.memoryType;
    if (opts.temporalFilter) payload.temporal_filter = opts.temporalFilter;
    return this.json("POST", "/api/v1/ai/query/semantic", { json: payload });
  }

  /** POST /api/v1/ai/query/chat — RAG chat with [1][2] citations */
  async chat(query: string, opts: ChatOptions = {}) {
    const payload: Record<string, unknown> = { query };
    if (opts.searchMode) payload.search_mode = opts.searchMode;
    if (opts.reranker) payload.reranker = opts.reranker;
    if (opts.conversationHistory) payload.conversation_history = opts.conversationHistory;
    if (opts.memoryType) payload.memory_type = opts.memoryType;
    return this.json("POST", "/api/v1/ai/query/chat", { json: payload });
  }

  async getSystemConfig() { return this.json("GET", "/api/v1/ai/system-config"); }
  async getModelCatalog(opts: { family?: string; role?: string; maxMemoryGb?: number } = {}) {
    return this.json("GET", "/api/v1/ai/model-catalog", { params: { family: opts.family, role: opts.role, max_memory_gb: opts.maxMemoryGb } });
  }

  // ===================== EMBEDDINGS =====================

  async createEmbedding(dataId: string, opts: { engineType?: string; model?: string } = {}) {
    return this.json<Record<string, unknown>>("POST", "/api/v1/ai/embeddings", { json: { data_id: dataId, engine_type: opts.engineType, model: opts.model } });
  }
  async getEmbedding(embeddingId: string) { return this.json("GET", `/api/v1/ai/embeddings/${embeddingId}`); }
  async listEmbeddings(opts: { dataId?: string; userId?: string; limit?: number } = {}) {
    return this.json("GET", "/api/v1/ai/embeddings", { params: { data_id: opts.dataId, user_id: opts.userId, limit: opts.limit } });
  }
  async deleteEmbedding(embeddingId: string) { await this.request("DELETE", `/api/v1/ai/embeddings/${embeddingId}`); }

  // ===================== VIEWPOINTS =====================

  async listViewpoints(opts: { dataId?: string; userId?: string; limit?: number } = {}) {
    return this.json("GET", "/api/v1/ai/viewpoints", { params: { data_id: opts.dataId, user_id: opts.userId, limit: opts.limit } });
  }
  async createViewpoint(payload: Record<string, unknown>) { return this.json<Record<string, unknown>>("POST", "/api/v1/ai/viewpoints", { json: payload }); }
  async getViewpoint(viewpointId: string) { return this.json("GET", `/api/v1/ai/viewpoints/${viewpointId}`); }
  async deleteViewpoint(viewpointId: string) { await this.request("DELETE", `/api/v1/ai/viewpoints/${viewpointId}`); }

  // ===================== AGENT CONFIGS =====================

  async listAgentConfigs(opts: { userId?: string; agentType?: string } = {}) {
    return this.json("GET", "/api/v1/ai/agent-configs", { params: { user_id: opts.userId, agent_type: opts.agentType } });
  }
  async createAgentConfig(payload: Record<string, unknown>) { return this.json<Record<string, unknown>>("POST", "/api/v1/ai/agent-configs", { json: payload }); }
  async resolveAgentConfig(agentType: string, opts: { userId?: string } = {}) {
    return this.json("GET", `/api/v1/ai/agent-configs/resolve/${agentType}`, { params: { user_id: opts.userId } });
  }
  async getAgentConfig(configId: string) { return this.json("GET", `/api/v1/ai/agent-configs/${configId}`); }
  async updateAgentConfig(configId: string, payload: Record<string, unknown>) { return this.json("PUT", `/api/v1/ai/agent-configs/${configId}`, { json: payload }); }
  async deleteAgentConfig(configId: string) { await this.request("DELETE", `/api/v1/ai/agent-configs/${configId}`); }

  // ===================== GRAPH =====================

  async searchEntities(query: string, opts: { userId?: string; entityType?: string; limit?: number } = {}) {
    const data = await this.json<unknown>("GET", "/api/v1/graph/entities", {
      params: { q: query, user_id: this.uid(opts.userId), entity_type: opts.entityType, limit: opts.limit ?? 20 },
    });
    return Array.isArray(data) ? data : [];
  }

  async getEntity(entityId: string, opts: { userId?: string } = {}) {
    return this.json<Record<string, unknown>>("GET", `/api/v1/graph/entities/${entityId}`, { params: { user_id: this.uid(opts.userId) } });
  }

  async getEntityRelationships(entityId: string, opts: { userId?: string } = {}) {
    return this.json("GET", `/api/v1/graph/entities/${entityId}/relationships`, { params: { user_id: this.uid(opts.userId) } });
  }

  async getDataEntities(dataId: string, opts: { userId?: string } = {}) {
    const data = await this.json<unknown>("GET", `/api/v1/graph/data/${dataId}/entities`, { params: { user_id: this.uid(opts.userId) } });
    return Array.isArray(data) ? data : [];
  }

  async batchCreateEntities(payload: Record<string, unknown>) { return this.json("POST", "/api/v1/graph/entities/batch", { json: payload }); }
  async deleteEntity(entityId: string) { await this.request("DELETE", `/api/v1/graph/entities/${entityId}`); }

  async queryFacts(opts: { q?: string; entityId?: string; at?: string; limit?: number } = {}) {
    return this.json("GET", "/api/v1/graph/facts", { params: { q: opts.q, entity_id: opts.entityId, at: opts.at, limit: opts.limit } });
  }

  async getFactTimeline(entityId: string, opts: { limit?: number } = {}) {
    return this.json("GET", "/api/v1/graph/facts/timeline", { params: { entity_id: entityId, limit: opts.limit } });
  }

  // ===================== WEBHOOKS =====================

  async createWebhook(payload: Record<string, unknown>) { return this.json<Record<string, unknown>>("POST", "/api/v1/webhooks", { json: payload }); }
  async listWebhooks(opts: { channelType?: string; status?: string } = {}) { return this.json("GET", "/api/v1/webhooks", { params: { channel_type: opts.channelType, status: opts.status } }); }
  async getWebhook(webhookId: string) { return this.json<Record<string, unknown>>("GET", `/api/v1/webhooks/${webhookId}`); }
  async updateWebhook(webhookId: string, payload: Record<string, unknown>) {
    const res = await this.request("PATCH", `/api/v1/webhooks/${webhookId}`, {
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json" },
    });
    return (await res.json()) as unknown;
  }
  async deleteWebhook(webhookId: string) { await this.request("DELETE", `/api/v1/webhooks/${webhookId}`); }
  async rotateWebhookSecret(webhookId: string) { return this.json<Record<string, unknown>>("POST", `/api/v1/webhooks/${webhookId}/rotate-secret`); }
  async listWebhookEvents(webhookId: string, opts: { status?: string; limit?: number; offset?: number } = {}) {
    return this.json("GET", `/api/v1/webhooks/${webhookId}/events`, { params: { status: opts.status, limit: opts.limit, offset: opts.offset } });
  }
  async getWebhookStats(webhookId: string, opts: { period?: string } = {}) {
    return this.json("GET", `/api/v1/webhooks/${webhookId}/stats`, { params: { period: opts.period } });
  }

  // ===================== INTEGRATIONS =====================

  async listProviders() { return this.json("GET", "/api/v1/integrations/config"); }
  async getProvider(providerKey: string) { return this.json("GET", `/api/v1/integrations/config/${providerKey}`); }
  async listConnections() { return this.json("GET", "/api/v1/integrations/connections"); }
  async createConnection(payload: Record<string, unknown>) { return this.json<Record<string, unknown>>("POST", "/api/v1/integrations/connections", { json: payload }); }
  async getConnection(connectionId: string) { return this.json<Record<string, unknown>>("GET", `/api/v1/integrations/connections/${connectionId}`); }
  async updateConnection(connectionId: string, payload: Record<string, unknown>) {
    const res = await this.request("PATCH", `/api/v1/integrations/connections/${connectionId}`, {
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json" },
    });
    return (await res.json()) as unknown;
  }
  async deleteConnection(connectionId: string) { await this.request("DELETE", `/api/v1/integrations/connections/${connectionId}`); }
  async getOAuthUrl(providerKey: string, redirectUri: string) {
    return this.json("GET", "/api/v1/integrations/oauth/authorize", { params: { provider_key: providerKey, redirect_uri: redirectUri } });
  }

  // ===================== STATS =====================

  async getStats() { return this.json("GET", "/api/v1/stats"); }
  async getUserStats(userId: string) { return this.json("GET", `/api/v1/stats/users/${userId}`); }
  async refreshStats() { return this.json("POST", "/api/v1/stats/refresh"); }
  async getTokenUsage(userId: string) { return this.json("GET", `/api/v1/stats/token-usage/${userId}`); }

  // ===================== BULK =====================

  async bulkDeleteData(dataIds: string[]) { return this.json("POST", "/api/v1/bulk/data/delete", { json: { data_ids: dataIds } }); }
  async bulkDeleteMemories(memoryIds: string[], opts: { deleteData?: boolean } = {}) {
    return this.json("POST", "/api/v1/bulk/memories/delete", { json: { memory_ids: memoryIds, delete_data: opts.deleteData ?? false } });
  }

  // ===================== INGEST =====================

  async ingest(envelope: Record<string, unknown>, opts: { direct?: boolean } = {}) {
    return this.json("POST", "/api/v1/ingest", { json: { envelope, direct: opts.direct ?? false } });
  }

  // ===================== PROMPTS =====================

  async listPrompts(opts: { dataId?: string; category?: string; userId?: string } = {}) {
    return this.json("GET", "/api/v1/ai/prompts", { params: { data_id: opts.dataId, category: opts.category, user_id: opts.userId } });
  }
  async createPrompt(payload: Record<string, unknown>) { return this.json("POST", "/api/v1/ai/prompts", { json: payload }); }
  async getPrompt(promptId: string) { return this.json("GET", `/api/v1/ai/prompts/${promptId}`); }
  async updatePrompt(promptId: string, payload: Record<string, unknown>) { return this.json("PUT", `/api/v1/ai/prompts/${promptId}`, { json: payload }); }
  async deletePrompt(promptId: string) { await this.request("DELETE", `/api/v1/ai/prompts/${promptId}`); }

  // ===================== SKILLS =====================

  async listSkills(opts: { dataId?: string; userId?: string; tag?: string } = {}) {
    return this.json("GET", "/api/v1/ai/skills", { params: { data_id: opts.dataId, user_id: opts.userId, tag: opts.tag } });
  }
  async createSkill(payload: Record<string, unknown>) { return this.json("POST", "/api/v1/ai/skills", { json: payload }); }
  async getSkill(skillId: string) { return this.json("GET", `/api/v1/ai/skills/${skillId}`); }
  async updateSkill(skillId: string, payload: Record<string, unknown>) { return this.json("PUT", `/api/v1/ai/skills/${skillId}`, { json: payload }); }
  async deleteSkill(skillId: string) { await this.request("DELETE", `/api/v1/ai/skills/${skillId}`); }

  // ===================== ANALYSIS TEMPLATES =====================

  async listAnalysisTemplates(opts: { dataType?: string } = {}) {
    return this.json("GET", "/api/v1/ai/analysis-templates", { params: { data_type: opts.dataType } });
  }
  async createAnalysisTemplate(payload: Record<string, unknown>) { return this.json("POST", "/api/v1/ai/analysis-templates", { json: payload }); }
  async seedAnalysisTemplates() { return this.json("POST", "/api/v1/ai/analysis-templates/seed"); }
  async getAnalysisTemplate(templateId: string) { return this.json("GET", `/api/v1/ai/analysis-templates/${templateId}`); }
  async updateAnalysisTemplate(templateId: string, payload: Record<string, unknown>) { return this.json("PUT", `/api/v1/ai/analysis-templates/${templateId}`, { json: payload }); }
  async deleteAnalysisTemplate(templateId: string) { await this.request("DELETE", `/api/v1/ai/analysis-templates/${templateId}`); }

  // ===================== STORE =====================

  async listStoreKeys(opts: { prefix?: string } = {}) {
    return this.json("GET", "/api/v1/store", { params: { prefix: opts.prefix } });
  }
  async getStoreValue(key: string) { return this.json("GET", `/api/v1/store/${key}`); }
  async setStoreValue(key: string, payload: Record<string, unknown>) { return this.json("PUT", `/api/v1/store/${key}`, { json: payload }); }
  async deleteStoreValue(key: string) { await this.request("DELETE", `/api/v1/store/${key}`); }

  // ===================== CHANNELS =====================

  async createChannelIdentity(payload: Record<string, unknown>) { return this.json("POST", "/api/v1/channel-identities", { json: payload }); }
  async getChannelIdentity(channelType: string, channelUniqueId: string) {
    return this.json("GET", "/api/v1/channel-identities/by-channel", { params: { channel_type: channelType, channel_unique_id: channelUniqueId } });
  }
  async updateChannelIdentity(channelType: string, channelUniqueId: string, payload: Record<string, unknown>) {
    const res = await this.request("PATCH", "/api/v1/channel-identities/by-channel", {
      body: JSON.stringify(payload), headers: { "Content-Type": "application/json" },
      params: { channel_type: channelType, channel_unique_id: channelUniqueId },
    });
    return (await res.json()) as unknown;
  }
  async deleteChannelIdentity(channelType: string, channelUniqueId: string) {
    await this.request("DELETE", "/api/v1/channel-identities/by-channel", { params: { channel_type: channelType, channel_unique_id: channelUniqueId } });
  }
  async listUserChannelIdentities(userId: string) { return this.json("GET", `/api/v1/channel-identities/by-user/${userId}`); }
  async listChannels() { return this.json("GET", "/api/v1/channels"); }
  async getChannel(channelType: string) { return this.json("GET", `/api/v1/channels/${channelType}`); }
  async updateChannel(channelType: string, payload: Record<string, unknown>) { return this.json("PUT", `/api/v1/channels/${channelType}`, { json: payload }); }
  async deleteChannel(channelType: string) { await this.request("DELETE", `/api/v1/channels/${channelType}`); }

  // ===================== ADDITIONAL ENDPOINTS =====================

  async getVersion(dataId: string, version: number) { return this.json("GET", `/api/v1/versions/${dataId}/${version}`); }
  async listUserDataItem(dataId: string, opts: { user?: string; format?: string } = {}) {
    return this.json("GET", `/api/v1/list/${dataId}`, { params: { user: opts.user, format: opts.format } });
  }
  async getMemoryEntries(memoryId: string) { return this.json("GET", `/api/v1/memories/${memoryId}/entries`); }
  async dumpUserData() { return this.json("GET", "/api/v1/users/dump"); }
  async getUserData(userId: string) { return this.json("GET", `/api/v1/users/${userId}/data`); }
  async createUserData(userId: string, opts: { file?: File | Blob; content?: string } = {}) {
    const form = new FormData();
    if (opts.content !== undefined) form.append("content", opts.content);
    if (opts.file) form.append("file", opts.file);
    const res = await this.request("POST", `/api/v1/users/${userId}/data`, { body: form });
    return (await res.json()) as Record<string, unknown>;
  }
  async bulkDeleteUserData(user: string) { await this.request("DELETE", `/api/v1/bulk/data/user/${user}`); }
  async bulkDeleteMemoryData(memoryId: string) { await this.request("DELETE", `/api/v1/bulk/data/memory/${memoryId}`); }
  async getDataEmbeddings(dataId: string) { return this.json("GET", `/api/v1/ai/embeddings/data/${dataId}`); }
  async deleteDataEmbeddings(dataId: string) { await this.request("DELETE", `/api/v1/ai/embeddings/data/${dataId}`); }
  async bulkDeleteEmbeddings(payload: Record<string, unknown>) { return this.json("POST", "/api/v1/ai/embeddings/bulk-delete", { json: payload }); }
  async updateViewpoint(viewpointId: string, payload: Record<string, unknown>) { return this.json("PUT", `/api/v1/ai/viewpoints/${viewpointId}`, { json: payload }); }
  async getViewpointHistory(viewpointId: string) { return this.json("GET", `/api/v1/ai/viewpoints/${viewpointId}/history`); }
  async getDataViewpoints(dataId: string) { return this.json("GET", `/api/v1/ai/viewpoints/data/${dataId}`); }
  async bulkDeleteViewpoints(payload: Record<string, unknown>) { return this.json("POST", "/api/v1/ai/viewpoints/bulk-delete", { json: payload }); }
  async deleteDataEntities(dataId: string) { await this.request("DELETE", `/api/v1/graph/data/${dataId}/entities`); }
  async timelineQuery(payload: Record<string, unknown>) { return this.json("POST", "/api/v1/ai/query/timeline", { json: payload }); }
  async aiQueryTest() { return this.json("GET", "/api/v1/ai/query/test"); }
  async getModelDetails(modelId: string) { return this.json("GET", `/api/v1/ai/model-catalog/${modelId}`); }
  async oauthCallback(code: string, state: string) { return this.json("POST", "/api/v1/integrations/oauth/callback", { json: { code, state } }); }
  async getDataStats() { return this.json("GET", "/api/v1/stats/data"); }
  async getMemoryStats() { return this.json("GET", "/api/v1/stats/memories"); }
  async getEmbeddingStats() { return this.json("GET", "/api/v1/stats/embeddings"); }
  async getViewpointStats() { return this.json("GET", "/api/v1/stats/viewpoints"); }
  async refreshUserStats(userId: string) { return this.json("POST", `/api/v1/stats/refresh/users/${userId}`); }
  async getAgentTypeCounts() { return this.json("GET", "/api/v1/stats/agent-types"); }
  async incrementAgentType(agentType: string) { return this.json("POST", `/api/v1/stats/agent-types/${agentType}/increment`); }
  async decrementAgentType(agentType: string) { return this.json("POST", `/api/v1/stats/agent-types/${agentType}/decrement`); }
  async recordTokenUsage(payload: Record<string, unknown>) { return this.json("POST", "/api/v1/stats/token-usage", { json: payload }); }
  async deleteTokenUsage(userId: string) { await this.request("DELETE", `/api/v1/stats/token-usage/${userId}`); }
}

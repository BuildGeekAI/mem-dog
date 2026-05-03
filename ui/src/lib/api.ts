import axios from 'axios';
import { supabase } from './supabase';
import type {
  DataListItem,
  DataListResponse,
  DataMetadata,
  DataDeviceInfo,
  CreateDataResponse,
  UpdateDataResponse,
  VersionInfo,
  MemoryCreate,
  MemoryUpdate,
  MemoryResponse,
  MemoryListResponse,
  MemoryAddDataRequest,
  MemoryDataDeleteResponse,
  BulkMemoryDeleteRequest,
  BulkMemoryDeleteResponse,
  TagsResponse,
  TagsUpdate,
  TagsAdd,
  TagsRemove,
  InfoUpdate,
  InfoResponse,
  BulkDeleteResponse,
  UserDataDeleteResponse,
  UserResponse,
  UserUpdate,
  ChannelIdentityCreate as ChannelIdentityCreateType,
  ChannelIdentityRecord,
  ChannelIdentityListResponse,
  ChannelIdentityUpdate as ChannelIdentityUpdateType,
  ChannelMetadata,
  ChannelMetadataCreate,
  IntegrationProvider,
  IntegrationConnection,
  IntegrationConnectionCreate,
  APIKeyResponse,
} from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

// Log API URL configuration for debugging
console.log('[API Client] NEXT_PUBLIC_API_URL:', process.env.NEXT_PUBLIC_API_URL);
console.log('[API Client] Resolved API_URL:', API_URL || '(empty - using relative URLs via Next.js rewrites)');
if (API_KEY) console.log('[API Client] API key configured (X-API-Key header will be sent)');

export const api = axios.create({
  baseURL: API_URL,
});

// Inject X-API-Key and/or Supabase JWT Bearer token
api.interceptors.request.use(async (config) => {
  if (API_KEY) {
    config.headers = config.headers || {};
    config.headers['x-api-key'] = API_KEY;
  }
  // Attach Supabase JWT if a session exists (browser auth)
  try {
    const { data } = await supabase.auth.getSession();
    if (data.session?.access_token) {
      config.headers = config.headers || {};
      config.headers['authorization'] = `Bearer ${data.session.access_token}`;
    }
  } catch {
    // Supabase not configured or session unavailable — skip
  }
  const fullUrl = config.baseURL ? `${config.baseURL}${config.url}` : config.url;
  console.log(`[API Request] ${config.method?.toUpperCase()} ${fullUrl}`);
  return config;
});

// Add response interceptor to log responses
api.interceptors.response.use(
  (response) => {
    console.log(`[API Response] ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    console.error(`[API Error] ${error.config?.url}:`, error.message);
    return Promise.reject(error);
  }
);

// Data CRUD operations
export interface ListDataOptions {
  skip?: number;
  limit?: number;
  /** Comma-separated or array of tags to filter by. */
  tags?: string[] | string;
  /** If true, items must have ALL tags; otherwise ANY. */
  matchAll?: boolean;
  /** Scope results to a specific project. */
  projectId?: string;
}

/**
 * List data items (paginated). When `user` is provided, returns only data that belongs to that user.
 * Returns { items, total, skip, limit } for pagination.
 */
export async function listData(
  user?: string,
  options?: ListDataOptions
): Promise<DataListResponse> {
  const params: Record<string, string | number | boolean> = {};
  if (user) params.user = user;
  if (options?.skip !== undefined) params.skip = options.skip;
  if (options?.limit !== undefined) params.limit = options.limit;
  if (options?.tags !== undefined) {
    const t = options.tags;
    params.tags = Array.isArray(t) ? t.join(',') : String(t);
  }
  if (options?.matchAll !== undefined) params.match_all = options.matchAll;
  if (options?.projectId) params.project_id = options.projectId;
  const response = await api.get('/api/v1/data', { params });
  return response.data;
}

export async function getData(id: string, version?: number): Promise<Blob> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  if (version != null) params.set('version', String(version));
  const response = await api.get(`/api/v1/data/${id}?${params}`, { responseType: 'blob' });
  return response.data;
}

export async function getDataAsText(id: string, version?: number): Promise<string> {
  const blob = await getData(id, version);
  return await blob.text();
}

export async function getMetadata(id: string): Promise<DataMetadata> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.get(`/api/v1/data/${id}/metadata?${params}`);
  const data = response.data;
  if (!data || !data.data_id) {
    throw new Error('Data not found');
  }
  return data;
}

export interface CreateDataOptions {
  memoryIds?: string[];
  tags?: string[];
  name?: string;
  description?: string;
  /** When true, dispatches a data.uploaded event to the webhook pipeline. Used by Testing tab uploads. */
  forwardToWebhook?: boolean;
  /** User ID for the uploader (in the path). Defaults to current user. Always written to memory. */
  userId?: string;
  // Plan 1 — URL / MIME / download-state fields
  /** Remote URL to fetch content from (triggers Flow B download when isDownloaded is falsy). */
  url?: string;
  /** Declared MIME type override. */
  mimeType?: string;
  /** When true, URL is stored as a reference without downloading (Flow C). */
  isDownloaded?: boolean;
  /** UI context — wired to session-{id} memory automatically. */
  sessionId?: string;
  /** UI context — wired to timeline-{id} memory automatically. */
  timelineId?: string;
}

/**
 * Create data. Tries POST /api/v1/users/{user_id}/data first (user ID in path).
 * On 404/405 falls back to POST /api/v1/data with owner_user_id in the form (legacy path).
 * Both paths are supported by the API; owner is always written to memory.
 */
export async function createData(
  content: string | File | null,
  options?: CreateDataOptions
): Promise<CreateDataResponse> {
  const formData = new FormData();

  if (content !== null) {
    if (typeof content === 'string') {
      formData.append('content', content);
    } else {
      formData.append('file', content);
    }
  }

  // Plan 1 — URL / MIME / download-state
  if (options?.url) {
    formData.append('url', options.url);
  }
  if (options?.mimeType) {
    formData.append('mime_type', options.mimeType);
  }
  if (options?.isDownloaded !== undefined) {
    formData.append('is_downloaded', options.isDownloaded ? 'true' : 'false');
  }
  if (options?.sessionId) {
    formData.append('session_id', options.sessionId);
  }
  if (options?.timelineId) {
    formData.append('timeline_id', options.timelineId);
  }

  // Associate with memories if provided
  if (options?.memoryIds && options.memoryIds.length > 0) {
    formData.append('memory_ids', JSON.stringify(options.memoryIds));
  }

  if (options?.name) {
    formData.append('name', options.name);
  }

  if (options?.description) {
    formData.append('description', options.description);
  }

  if (options?.tags && options.tags.length > 0) {
    formData.append('tags', options.tags.join(','));
  }

  if (options?.forwardToWebhook) {
    formData.append('forward_to_webhook', 'true');
  }

  const ownerUserId = (options?.userId ?? getCurrentUserId()) || DEFAULT_USER_ID;
  formData.append('owner_user_id', ownerUserId);

  // Always include device info (expanded — may have empty fields if detection fails)
  const deviceInfo = getDataDeviceInfo();
  formData.append('device_type', deviceInfo.device_type || '');
  formData.append('device_os', deviceInfo.os || '');
  formData.append('device_browser', deviceInfo.browser || '');
  formData.append('device_app_version', deviceInfo.app_version || '');
  formData.append('device_user_agent', deviceInfo.user_agent || '');
  if (deviceInfo.screen_width != null) formData.append('device_screen_width', String(deviceInfo.screen_width));
  if (deviceInfo.screen_height != null) formData.append('device_screen_height', String(deviceInfo.screen_height));
  if (deviceInfo.timezone) formData.append('device_timezone', deviceInfo.timezone);
  if (deviceInfo.language) formData.append('device_language', deviceInfo.language);
  if (deviceInfo.cpu_cores != null) formData.append('device_cpu_cores', String(deviceInfo.cpu_cores));
  if (deviceInfo.memory_gb != null) formData.append('device_memory_gb', String(deviceInfo.memory_gb));
  if (deviceInfo.connection_type) formData.append('device_connection_type', deviceInfo.connection_type);
  if (deviceInfo.device_id) formData.append('device_id', deviceInfo.device_id);

  const requestConfig = {
    headers: { 'Content-Type': 'multipart/form-data' },
    maxBodyLength: Infinity,
    maxContentLength: Infinity,
  };

  // Prefer path with user ID: POST /api/v1/users/{user_id}/data
  try {
    const response = await api.post(
      `/api/v1/users/${encodeURIComponent(ownerUserId)}/data`,
      formData,
      requestConfig
    );
    return response.data;
  } catch (err: any) {
    const status = err.response?.status;
    // If path-with-user-id is not available (e.g. 405), use legacy path without user ID in URL
    if (status === 405 || status === 404) {
      const legacyResponse = await api.post('/api/v1/data', formData, requestConfig);
      return legacyResponse.data;
    }
    throw err;
  }
}

/**
 * Plan 1 — Mark a data item's download state (PATCH /api/v1/data/{id}/download).
 * Call after manually fetching a URL-referenced item from outside the API.
 */
export async function patchDownloadState(
  dataId: string,
  isDownloaded: boolean,
): Promise<DataMetadata> {
  const response = await api.patch(`/api/v1/data/${dataId}/download`, { is_downloaded: isDownloaded });
  return response.data;
}

/**
 * Get device info for data upload.
 * Always called when data is written to the system.
 * Returns empty fields if detection is not possible.
 */
export function getDataDeviceInfo(): DataDeviceInfo {
  // Check if we're in a browser environment
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return {};
  }

  const ua = navigator.userAgent;

  // Detect device type
  let deviceType: string | undefined;
  try {
    if (/Mobi|Android/i.test(ua)) {
      deviceType = /Tablet|iPad/i.test(ua) ? 'tablet' : 'mobile';
    } else {
      deviceType = 'desktop';
    }
  } catch { deviceType = undefined; }

  // Detect OS
  let os: string | undefined;
  try {
    if (/Windows/i.test(ua)) os = 'Windows';
    else if (/Mac/i.test(ua)) os = 'macOS';
    else if (/Linux/i.test(ua)) os = 'Linux';
    else if (/Android/i.test(ua)) os = 'Android';
    else if (/iOS|iPhone|iPad/i.test(ua)) os = 'iOS';
    else os = undefined;
  } catch { os = undefined; }

  // Detect browser
  let browser: string | undefined;
  try {
    if (/Chrome/i.test(ua) && !/Edg/i.test(ua)) browser = 'Chrome';
    else if (/Safari/i.test(ua) && !/Chrome/i.test(ua)) browser = 'Safari';
    else if (/Firefox/i.test(ua)) browser = 'Firefox';
    else if (/Edg/i.test(ua)) browser = 'Edge';
    else browser = undefined;
  } catch { browser = undefined; }

  // Screen resolution
  let screenWidth: number | undefined;
  let screenHeight: number | undefined;
  try {
    screenWidth = window.screen?.width || undefined;
    screenHeight = window.screen?.height || undefined;
  } catch { /* ignore */ }

  // Timezone
  let timezone: string | undefined;
  try {
    timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch { /* ignore */ }

  // Language
  let language: string | undefined;
  try {
    language = navigator.language || undefined;
  } catch { /* ignore */ }

  // CPU cores (navigator.hardwareConcurrency)
  let cpuCores: number | undefined;
  try {
    cpuCores = (navigator as any).hardwareConcurrency || undefined;
  } catch { /* ignore */ }

  // Device memory GB (navigator.deviceMemory — Chrome only)
  let memoryGb: number | undefined;
  try {
    memoryGb = (navigator as any).deviceMemory || undefined;
  } catch { /* ignore */ }

  // Connection type (Network Information API — Chrome only)
  let connectionType: string | undefined;
  try {
    const conn = (navigator as any).connection;
    connectionType = conn?.effectiveType || conn?.type || undefined;
  } catch { /* ignore */ }

  // Persistent per-device UUID (stored in localStorage)
  let deviceId: string | undefined;
  try {
    const key = '__mem_dog_device_id__';
    deviceId = localStorage.getItem(key) || undefined;
    if (!deviceId) {
      deviceId = crypto.randomUUID();
      localStorage.setItem(key, deviceId);
    }
  } catch { /* ignore */ }

  return {
    device_type: deviceType,
    os,
    browser,
    app_version: process.env.NEXT_PUBLIC_APP_VERSION || undefined,
    user_agent: ua || undefined,
    screen_width: screenWidth,
    screen_height: screenHeight,
    timezone,
    language,
    cpu_cores: cpuCores,
    memory_gb: memoryGb,
    connection_type: connectionType,
    device_id: deviceId,
  };
}

/**
 * Return the current user's info from localStorage / context.
 * Falls back to minimal stub when nothing is stored.
 */
export function getCurrentUserInfo(): { user_id: string; username?: string; display_name?: string; role?: string } {
  const user_id = getCurrentUserId();
  try {
    const stored = localStorage.getItem('mem_dog_user');
    if (stored) {
      const parsed = JSON.parse(stored);
      return {
        user_id: parsed.user_id || user_id,
        username: parsed.username || undefined,
        display_name: parsed.display_name || parsed.name || undefined,
        role: parsed.role || undefined,
      };
    }
  } catch { /* ignore */ }
  return { user_id };
}

export async function updateData(id: string, content: string | File): Promise<UpdateDataResponse> {
  const formData = new FormData();
  formData.append('user_id', getCurrentUserId());

  if (typeof content === 'string') {
    formData.append('content', content);
  } else {
    formData.append('file', content);
  }
  
  const response = await api.put(`/api/v1/data/${id}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function deleteData(id: string): Promise<void> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  await api.delete(`/api/v1/data/${id}?${params}`);
}

// =============================================================================
// Bulk Delete Operations
// =============================================================================

/**
 * Delete multiple data items by their IDs.
 * @param dataIds - Array of data IDs to delete
 */
export async function bulkDeleteData(dataIds: string[]): Promise<BulkDeleteResponse> {
  const response = await api.post('/api/v1/bulk/data/delete', { data_ids: dataIds });
  return response.data;
}

/**
 * Delete ALL data items for a specific user.
 * WARNING: This is irreversible and clears all the user's memories.
 * @param user - User identifier
 */
export async function deleteAllUserData(user: string): Promise<UserDataDeleteResponse> {
  const response = await api.delete(`/api/v1/bulk/data/user/${user}`);
  return response.data;
}

/**
 * Delete all data items associated with a specific memory.
 * The memory itself remains but with an empty data list.
 * @param memoryId - Memory ID
 */
export async function deleteMemoryData(memoryId: string): Promise<MemoryDataDeleteResponse> {
  const response = await api.delete(`/api/v1/bulk/data/memory/${memoryId}`);
  return response.data;
}

/**
 * Delete multiple memories, optionally including their associated data.
 * @param options - Bulk memory delete options
 */
export async function bulkDeleteMemories(options: BulkMemoryDeleteRequest): Promise<BulkMemoryDeleteResponse> {
  const response = await api.post('/api/v1/bulk/memories/delete', options);
  return response.data;
}

// Version operations
export async function getVersions(id: string): Promise<VersionInfo[]> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.get(`/api/v1/versions/${id}?${params}`);
  return response.data;
}

export async function getSpecificVersion(id: string, version: number): Promise<Blob> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.get(`/api/v1/versions/${id}/${version}?${params}`, { responseType: 'blob' });
  return response.data;
}

export async function getSpecificVersionAsText(id: string, version: number): Promise<string> {
  const blob = await getSpecificVersion(id, version);
  return await blob.text();
}

// Memory operations -- see memory management section below

// =============================================================================
// Tags Operations
// =============================================================================

/**
 * Get tags for a specific data item.
 */
export async function getTags(dataId: string): Promise<TagsResponse> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.get(`/api/v1/data/${dataId}/tags?${params}`);
  return response.data;
}

/**
 * Update (replace) all tags for a data item.
 */
export async function updateTags(dataId: string, tags: string[] | null): Promise<DataMetadata> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.put(`/api/v1/data/${dataId}/tags?${params}`, { tags });
  return response.data;
}

/**
 * Add tags to a data item (merge with existing).
 */
export async function addTags(dataId: string, tags: string[]): Promise<DataMetadata> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.post(`/api/v1/data/${dataId}/tags/add?${params}`, { tags });
  return response.data;
}

/**
 * Remove specific tags from a data item.
 */
export async function removeTags(dataId: string, tags: string[]): Promise<DataMetadata> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.post(`/api/v1/data/${dataId}/tags/remove?${params}`, { tags });
  return response.data;
}

/**
 * Get all unique tags used in the system.
 */
export async function listAllTags(): Promise<string[]> {
  const response = await api.get('/api/v1/tags');
  return response.data;
}

/**
 * Search data items by tags.
 * @param tags - Tags to search for
 * @param matchAll - If true, items must have ALL tags. If false, items must have ANY tag.
 * @param userId - Optional user ID for access filtering
 * @param role - Optional role for access filtering
 */
export async function searchByTags(
  tags: string[],
  matchAll: boolean = false,
  userId?: string,
  role?: string
): Promise<DataListItem[]> {
  const params = new URLSearchParams();
  params.append('tags', tags.join(','));
  params.append('match_all', String(matchAll));
  if (userId) params.append('user_id', userId);
  if (role) params.append('role', role);
  
  const response = await api.get(`/api/v1/tags/search?${params.toString()}`);
  return response.data;
}

// =============================================================================
// Info Operations (Name, Description)
// =============================================================================

/**
 * Get name and description for a data item.
 */
export async function getInfo(dataId: string): Promise<InfoResponse> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.get(`/api/v1/data/${dataId}/info?${params}`);
  return response.data;
}

/**
 * Update name and/or description for a data item.
 * @param dataId - The data item ID
 * @param info - Object with name and/or description to update
 */
export async function updateInfo(dataId: string, info: InfoUpdate): Promise<DataMetadata> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.put(`/api/v1/data/${dataId}/info?${params}`, info);
  return response.data;
}

/**
 * Normalize an address URL returned by the API into a browsable URL.
 * The API computes addresses from request.base_url (e.g. the GKE Gateway IP),
 * which is not directly reachable from the user's browser.  Extract the
 * /api/v1/... path and return it as a relative URL that the Next.js rewrite
 * proxy will forward to the backend.
 */
export function normalizeAddress(address: string | null | undefined): string | null {
  if (!address) return null;
  try {
    const url = new URL(address);
    return url.pathname + url.search;
  } catch {
    if (address.startsWith('/')) return address;
    return null;
  }
}

// Utility functions
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

export function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleString();
}

export function formatTimestamp(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleString();
}

// =============================================================================
// Memory Management
// =============================================================================

/**
 * Get device info for memory creation (session-type memories).
 */
export function getDeviceInfo(): { type: string; os: string; browser: string } {
  const ua = navigator.userAgent;
  
  let type = 'desktop';
  if (/Mobi|Android/i.test(ua)) {
    type = /Tablet|iPad/i.test(ua) ? 'tablet' : 'mobile';
  }
  
  let os = 'Unknown';
  if (/Windows/i.test(ua)) os = 'Windows';
  else if (/Mac/i.test(ua)) os = 'macOS';
  else if (/Linux/i.test(ua)) os = 'Linux';
  else if (/Android/i.test(ua)) os = 'Android';
  else if (/iOS|iPhone|iPad/i.test(ua)) os = 'iOS';
  
  let browser = 'Unknown';
  if (/Chrome/i.test(ua) && !/Edg/i.test(ua)) browser = 'Chrome';
  else if (/Safari/i.test(ua) && !/Chrome/i.test(ua)) browser = 'Safari';
  else if (/Firefox/i.test(ua)) browser = 'Firefox';
  else if (/Edg/i.test(ua)) browser = 'Edge';
  
  return { type, os, browser };
}

/**
 * Generate a device ID based on browser fingerprint.
 */
export function getDeviceId(): string {
  const stored = localStorage.getItem('mem_dog_device_id');
  if (stored) return stored;
  
  const deviceId = `device-${crypto.randomUUID().slice(0, 8)}`;
  localStorage.setItem('mem_dog_device_id', deviceId);
  return deviceId;
}

const USER_ID_KEY = 'mem_dog_user_id';

/** Default user ID when none is set (e.g. for AI query and storage). */
export const DEFAULT_USER_ID = '00000000-0000-0000-0000-000000000001';

/**
 * Return the active user ID.
 * Falls back to DEFAULT_USER_ID when no value has been saved to localStorage.
 */
export function getCurrentUserId(): string {
  if (typeof window === 'undefined') return DEFAULT_USER_ID;
  return localStorage.getItem(USER_ID_KEY) || DEFAULT_USER_ID;
}

/**
 * Persist a new user ID so all subsequent API calls use it.
 * Pass an empty string or null to revert to the default UUID.
 */
export function setCurrentUserId(id: string | null): void {
  if (typeof window === 'undefined') return;
  if (id && id.trim() && id.trim() !== DEFAULT_USER_ID) {
    localStorage.setItem(USER_ID_KEY, id.trim());
  } else {
    localStorage.removeItem(USER_ID_KEY);
  }
}

/**
 * Persist a full user object to localStorage so getCurrentUserInfo() can read it.
 * Also calls setCurrentUserId to keep the simple key in sync.
 */
export function setCurrentUserInfo(user: { user_id: string; username?: string; display_name?: string; role?: string }): void {
  if (typeof window === 'undefined') return;
  setCurrentUserId(user.user_id);
  try {
    localStorage.setItem('mem_dog_user', JSON.stringify(user));
  } catch { /* ignore */ }
}

/**
 * Fetch user profile by ID from the backend.
 * Use this on connect to resolve the canonical user_id for webhook and upload.
 * Returns 404 when user management is disabled or the user does not exist.
 */
export async function getUser(userId: string): Promise<UserResponse> {
  const response = await api.get<UserResponse>(`/api/v1/users/${encodeURIComponent(userId)}`);
  return response.data;
}

/**
 * Create a new user in the API. Used to auto-provision Supabase auth users.
 */
export async function createUser(params: {
  user_id: string;
  username: string;
  email: string;
  display_name?: string;
}): Promise<UserResponse> {
  const response = await api.post<UserResponse>('/api/v1/users', params);
  return response.data;
}

/**
 * Update a user profile.
 */
export async function updateUser(userId: string, update: Partial<UserUpdate>): Promise<UserResponse> {
  const response = await api.put<UserResponse>(`/api/v1/users/${encodeURIComponent(userId)}`, update);
  return response.data;
}

// Memory CRUD operations

export async function listMemories(options?: {
  userId?: string;
  memoryType?: string;
  duration?: string;
  active?: boolean;
  subType?: string;
  skip?: number;
  limit?: number;
  projectId?: string;
}): Promise<MemoryListResponse> {
  const params = new URLSearchParams();
  if (options?.userId) params.append('user_id', options.userId);
  if (options?.memoryType) params.append('memory_type', options.memoryType);
  if (options?.duration) params.append('duration', options.duration);
  if (options?.active !== undefined) params.append('active', String(options.active));
  if (options?.subType) params.append('sub_type', options.subType);
  if (options?.skip !== undefined) params.append('skip', String(options.skip));
  if (options?.limit !== undefined) params.append('limit', String(options.limit));
  if (options?.projectId) params.append('project_id', options.projectId);
  
  const query = params.toString();
  const url = query ? `/api/v1/memories?${query}` : '/api/v1/memories';
  const response = await api.get(url);
  return response.data;
}

export async function createMemory(memory: MemoryCreate): Promise<MemoryResponse> {
  const response = await api.post('/api/v1/memories', memory);
  return response.data;
}

export async function getMemory(memoryId: string): Promise<MemoryResponse> {
  const response = await api.get(`/api/v1/memories/${memoryId}?user_id=${encodeURIComponent(getCurrentUserId())}`);
  return response.data;
}

export async function updateMemory(memoryId: string, update: MemoryUpdate): Promise<MemoryResponse> {
  const response = await api.put(`/api/v1/memories/${memoryId}?user_id=${encodeURIComponent(getCurrentUserId())}`, update);
  return response.data;
}

export async function deleteMemory(memoryId: string, deleteData?: boolean): Promise<{ memory_id: string; deleted: boolean; deleted_data_count: number; message: string }> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  if (deleteData) params.append('delete_data', 'true');
  const response = await api.delete(`/api/v1/memories/${memoryId}?${params}`);
  return response.data;
}

export async function addDataToMemory(memoryId: string, request: MemoryAddDataRequest): Promise<MemoryResponse> {
  const response = await api.post(`/api/v1/memories/${memoryId}/data?user_id=${encodeURIComponent(getCurrentUserId())}`, request);
  return response.data;
}

export async function getMemoryData(memoryId: string, options?: {
  skip?: number;
  limit?: number;
}): Promise<{ memory_id: string; items: any[]; total: number; skip: number; limit: number }> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  if (options?.skip !== undefined) params.append('skip', String(options.skip));
  if (options?.limit !== undefined) params.append('limit', String(options.limit));
  const response = await api.get(`/api/v1/memories/${memoryId}/data?${params}`);
  return response.data;
}

export async function getMemoryEntries(memoryId: string): Promise<{ memory_id: string; entries: any[]; total: number }> {
  const response = await api.get(`/api/v1/memories/${memoryId}/entries?user_id=${encodeURIComponent(getCurrentUserId())}`);
  return response.data;
}

export async function removeDataFromMemory(memoryId: string, dataId: string): Promise<{ memory_id: string; data_id: string; message: string }> {
  const response = await api.delete(`/api/v1/memories/${memoryId}/data/${dataId}?user_id=${encodeURIComponent(getCurrentUserId())}`);
  return response.data;
}

// =============================================================================
// AI Configuration
// =============================================================================

export async function getSystemAIConfig(): Promise<any> {
  const response = await api.get('/api/v1/ai/system-config');
  return response.data;
}

export async function getAvailableEngines(): Promise<any[]> {
  const response = await api.get('/api/v1/ai/engines');
  return response.data?.available_engines ?? response.data ?? [];
}

export async function listUserEngines(userId: string): Promise<any[]> {
  const response = await api.get(`/api/v1/ai/users/${userId}/engines`);
  return response.data?.engines ?? response.data ?? [];
}

export async function createUserEngine(userId: string, config: {
  engine_type: string;
  name: string;
  api_key?: string;
  base_url?: string;
  is_enabled?: boolean;
}): Promise<any> {
  const response = await api.post(`/api/v1/ai/users/${userId}/engines`, config);
  return response.data;
}

export async function deleteUserEngine(userId: string, engineId: string): Promise<void> {
  await api.delete(`/api/v1/ai/users/${userId}/engines/${engineId}`);
}

export async function updateUserEngine(userId: string, engineId: string, data: {
  name?: string;
  api_key?: string;
  base_url?: string;
  is_enabled?: boolean;
}): Promise<any> {
  const response = await api.put(`/api/v1/ai/users/${userId}/engines/${engineId}`, data);
  return response.data;
}

export async function getProviderRegistry(): Promise<{ providers: import('@/types').ProviderInfo[] }> {
  const response = await api.get('/api/v1/ai/provider-registry');
  return response.data;
}

export async function testEngine(userId: string, engineId: string): Promise<import('@/types').EngineTestResult> {
  const response = await api.post(`/api/v1/ai/users/${userId}/engines/${engineId}/test`);
  return response.data;
}

export async function discoverEngineModels(userId: string, engineId: string): Promise<{ models: string[]; count: number }> {
  const response = await api.post(`/api/v1/ai/users/${userId}/engines/${engineId}/discover-models`);
  return response.data;
}

export async function getUserAvailableModels(userId: string): Promise<{ providers: import('@/types').ProviderModels[] }> {
  const response = await api.get(`/api/v1/ai/users/${userId}/available-models`);
  return response.data;
}

export async function getUserAIPreferences(userId: string): Promise<any> {
  const response = await api.get(`/api/v1/ai/users/${userId}/preferences`);
  return response.data;
}

export async function updateUserAIPreferences(userId: string, prefs: {
  ai_key_mode?: string;
  default_engine_id?: string;
  default_embedding_model?: string;
  default_completion_model?: string;
  auto_generate_embeddings?: boolean;
  agent_processing_flags?: Record<string, boolean>;
  ollama_cloud_model_small?: string;
  ollama_cloud_model_medium?: string;
  ollama_cloud_model_large?: string;
  smart_routing_overrides?: Record<string, { primary_model: string; fallback_model: string }>;
}): Promise<any> {
  const response = await api.put(`/api/v1/ai/users/${userId}/preferences`, prefs);
  return response.data;
}

export async function getAgentProcessingDefaults(): Promise<Record<string, boolean>> {
  const response = await api.get('/api/v1/ai/agent-processing-defaults');
  return response.data;
}

export async function getPipelineModelConfig(): Promise<{
  primary_provider: string;
  fallback_provider: string;
  tier_models: { small: string; medium: string; large: string };
  fallback_model: string;
  primary_model: string;
}> {
  const response = await api.get('/api/v1/ai/pipeline-models');
  return response.data;
}

export async function testAIEngine(userId: string): Promise<any> {
  const response = await api.post('/api/v1/ai/query/test', { user: userId });
  return response.data;
}

// =============================================================================
// Prompts
// =============================================================================

export async function listPrompts(options?: {
  dataId?: string;
  category?: string;
  userId?: string;
}): Promise<any[]> {
  const params = new URLSearchParams();
  if (options?.dataId) params.append('data_id', options.dataId);
  if (options?.category) params.append('category', options.category);
  if (options?.userId) params.append('user_id', options.userId);
  const query = params.toString();
  const url = query ? `/api/v1/ai/prompts?${query}` : '/api/v1/ai/prompts';
  const response = await api.get(url);
  return response.data?.prompts ?? response.data ?? [];
}

export async function createPrompt(prompt: {
  name: string;
  template: string;
  data_id?: string;
  ai_engine?: string;
  model?: string;
  parameters?: Record<string, any>;
}): Promise<any> {
  const response = await api.post('/api/v1/ai/prompts', prompt);
  return response.data;
}

export async function getPrompt(promptId: string): Promise<any> {
  const response = await api.get(`/api/v1/ai/prompts/${promptId}`);
  return response.data;
}

export async function updatePrompt(promptId: string, update: {
  name?: string;
  template?: string;
  ai_engine?: string;
  model?: string;
  parameters?: Record<string, any>;
}): Promise<any> {
  const response = await api.put(`/api/v1/ai/prompts/${promptId}`, update);
  return response.data;
}

export async function deletePrompt(promptId: string): Promise<void> {
  await api.delete(`/api/v1/ai/prompts/${promptId}`);
}

// =============================================================================
// Skills
// =============================================================================

export async function listSkills(options?: {
  dataId?: string;
  userId?: string;
  tag?: string;
}): Promise<any[]> {
  const params = new URLSearchParams();
  if (options?.dataId) params.append('data_id', options.dataId);
  if (options?.userId) params.append('user_id', options.userId);
  if (options?.tag) params.append('tag', options.tag);
  const query = params.toString();
  const url = query ? `/api/v1/ai/skills?${query}` : '/api/v1/ai/skills';
  const response = await api.get(url);
  return response.data?.skills ?? response.data ?? [];
}

export async function createSkill(skill: {
  name: string;
  description: string;
  content: string;
  tags?: string[];
  data_id?: string;
}): Promise<any> {
  const response = await api.post('/api/v1/ai/skills', skill);
  return response.data;
}

export async function getSkill(skillId: string): Promise<any> {
  const response = await api.get(`/api/v1/ai/skills/${skillId}`);
  return response.data;
}

export async function updateSkill(skillId: string, update: {
  name?: string;
  description?: string;
  content?: string;
  tags?: string[];
}): Promise<any> {
  const response = await api.put(`/api/v1/ai/skills/${skillId}`, update);
  return response.data;
}

export async function deleteSkill(skillId: string): Promise<void> {
  await api.delete(`/api/v1/ai/skills/${skillId}`);
}

// =============================================================================
// Agent Configs
// =============================================================================

export async function listAgentConfigs(options?: {
  userId?: string;
  agentType?: string;
}): Promise<any[]> {
  const params = new URLSearchParams();
  if (options?.userId) params.append('user_id', options.userId);
  if (options?.agentType) params.append('agent_type', options.agentType);
  const query = params.toString();
  const url = query ? `/api/v1/ai/agent-configs?${query}` : '/api/v1/ai/agent-configs';
  const response = await api.get(url);
  return response.data?.configs || [];
}

export async function createAgentConfig(config: {
  agent_type: string;
  user_id?: string | null;
  intro?: string | null;
  system_prompt?: string | null;
  output_schema?: string | null;
  skills?: string[];
  model_tier?: string | null;
  parameters?: Record<string, any>;
}): Promise<any> {
  const response = await api.post('/api/v1/ai/agent-configs', config);
  return response.data;
}

export async function updateAgentConfig(configId: string, updates: {
  intro?: string | null;
  system_prompt?: string | null;
  output_schema?: string | null;
  skills?: string[];
  model_tier?: string | null;
  parameters?: Record<string, any>;
}): Promise<any> {
  const response = await api.put(`/api/v1/ai/agent-configs/${configId}`, updates);
  return response.data;
}

export async function deleteAgentConfig(configId: string): Promise<void> {
  await api.delete(`/api/v1/ai/agent-configs/${configId}`);
}

// =============================================================================
// Embeddings
// =============================================================================

export async function listEmbeddings(dataId?: string): Promise<any[]> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  if (dataId) params.append('data_id', dataId);
  const response = await api.get(`/api/v1/ai/embeddings?${params}`);
  return response.data?.embeddings ?? response.data ?? [];
}

export async function createEmbedding(options: {
  data_id: string;
  engine_id?: string;
  model?: string;
  chunk_size?: number;
  chunk_overlap?: number;
}): Promise<any> {
  const response = await api.post('/api/v1/ai/embeddings', options);
  return response.data;
}

export async function deleteEmbedding(embeddingId: string): Promise<void> {
  await api.delete(`/api/v1/ai/embeddings/${embeddingId}`);
}

export async function deleteDataEmbeddings(dataId: string): Promise<void> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  await api.delete(`/api/v1/ai/embeddings/data/${dataId}?${params}`);
}

export async function bulkDeleteEmbeddings(dataIds: string[]): Promise<{ deleted_count: number; failed_count: number }> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.post(`/api/v1/ai/embeddings/bulk-delete?${params}`, { data_ids: dataIds });
  return response.data;
}

export async function bulkDeleteViewpoints(viewpointIds: string[]): Promise<{ deleted_count: number; failed_count: number }> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.post(`/api/v1/ai/viewpoints/bulk-delete?${params}`, { viewpoint_ids: viewpointIds });
  return response.data;
}

export async function getDataEmbeddings(dataId: string): Promise<any[]> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.get(`/api/v1/ai/embeddings/data/${dataId}?${params}`);
  return response.data?.embeddings ?? response.data ?? [];
}

// =============================================================================
// Viewpoints
// =============================================================================

export async function listViewpoints(dataId?: string): Promise<any[]> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  if (dataId) params.append('data_id', dataId);
  const response = await api.get(`/api/v1/ai/viewpoints?${params}`);
  return response.data?.viewpoints ?? response.data ?? [];
}

export async function createViewpoint(options: {
  data_id: string;
  prompt_id: string;
  engine_id?: string;
}): Promise<any> {
  const response = await api.post('/api/v1/ai/viewpoints', options);
  return response.data;
}

export async function getViewpoint(viewpointId: string): Promise<any> {
  const response = await api.get(`/api/v1/ai/viewpoints/${viewpointId}`);
  return response.data;
}

export async function deleteViewpoint(viewpointId: string): Promise<void> {
  await api.delete(`/api/v1/ai/viewpoints/${viewpointId}`);
}

export async function getDataViewpoints(dataId: string): Promise<any[]> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.get(`/api/v1/ai/viewpoints/data/${dataId}?${params}`);
  return response.data?.viewpoints ?? response.data ?? [];
}

export async function getViewpointHistory(viewpointId: string): Promise<any[]> {
  const params = new URLSearchParams({ user_id: getCurrentUserId() });
  const response = await api.get(`/api/v1/ai/viewpoints/${viewpointId}/history?${params}`);
  return response.data;
}

// =============================================================================
// AI Query
// =============================================================================

export interface SemanticMatchChunk {
  embedding_id: string;
  chunk_text: string;
  similarity: number;
}

export interface SemanticRecord {
  data_id: string;
  name: string | null;
  description: string | null;
  tags: string[] | null;
  mime_type: string | null;
  created_at: string | null;
  address: string | null;
  best_similarity: number;
  matching_chunks: SemanticMatchChunk[];
}

export interface SemanticSearchResponse {
  query: string;
  records: SemanticRecord[];
  answer: string | null;
  model: string | null;
  latency_ms: number;
}

export async function semanticSearch(options: {
  query: string;
  max_results?: number;
  user_id?: string;
}): Promise<SemanticSearchResponse> {
  const response = await api.post('/api/v1/ai/query/semantic', {
    query: options.query,
    max_results: options.max_results ?? 20,
    synthesise: false,
    user_id: options.user_id || '',
  });
  return response.data;
}

// Chat with Data (conversational RAG)

export interface ChatCitation {
  index: number;
  data_id: string;
  name: string | null;
  chunk_text: string;
  similarity: number;
}

export interface ChatWithDataResponse {
  answer: string;
  citations: ChatCitation[];
  model: string | null;
  latency_ms: number;
}

export async function chatWithData(options: {
  message: string;
  history?: { role: 'user' | 'assistant'; content: string }[];
  max_results?: number;
  max_tokens?: number;
  temperature?: number;
  model_tier?: string;
  user_id?: string;
  memory_id?: string;
  search_mode?: 'vector' | 'fts' | 'hybrid' | 'graph' | 'full';
  vector_weight?: number;
  fts_weight?: number;
  rerank?: { method: 'none' | 'rrf' | 'mmr' | 'cross_encoder'; mmr_lambda?: number };
}): Promise<ChatWithDataResponse> {
  const body: Record<string, unknown> = {
    message: options.message,
    history: options.history ?? [],
    max_results: options.max_results ?? 5,
    max_tokens: options.max_tokens ?? 1024,
    temperature: options.temperature ?? 0.3,
    model_tier: options.model_tier ?? 'medium',
    user_id: options.user_id || '',
  };
  if (options.memory_id) {
    body.memory_id = options.memory_id;
  }
  if (options.search_mode) {
    body.search_mode = options.search_mode;
  }
  if (options.vector_weight !== undefined) {
    body.vector_weight = options.vector_weight;
  }
  if (options.fts_weight !== undefined) {
    body.fts_weight = options.fts_weight;
  }
  if (options.rerank) {
    body.rerank = options.rerank;
  }
  // Use dedicated chat proxy route to avoid Next.js rewrite proxy timeout
  // on slow local Ollama inference (~60-120s).
  const response = await api.post('/api/chat-proxy', body, {
    timeout: 180000, // 3 min
  });
  return response.data;
}

export async function queryAI(options: {
  query: string;
  user?: string;
  data_ids?: string[];
  engine_id?: string;
  max_tokens?: number;
  temperature?: number;
}): Promise<any> {
  const response = await api.post('/api/v1/ai/query', options);
  return response.data;
}


// =============================================================================
// Analysis Templates
// =============================================================================

import type {
  AnalysisTemplate,
  AnalysisTemplateCreate,
  AnalysisTemplateUpdate,
} from '@/types';

export async function listAnalysisTemplates(dataType?: string): Promise<AnalysisTemplate[]> {
  const params = new URLSearchParams();
  if (dataType) params.append('data_type', dataType);
  const query = params.toString();
  const url = query ? `/api/v1/ai/analysis-templates?${query}` : '/api/v1/ai/analysis-templates';
  const response = await api.get(url);
  return response.data?.templates ?? response.data ?? [];
}

export async function createAnalysisTemplate(t: AnalysisTemplateCreate): Promise<AnalysisTemplate> {
  const response = await api.post('/api/v1/ai/analysis-templates', t);
  return response.data;
}

export async function updateAnalysisTemplate(id: string, t: AnalysisTemplateUpdate): Promise<AnalysisTemplate> {
  const response = await api.put(`/api/v1/ai/analysis-templates/${encodeURIComponent(id)}`, t);
  return response.data;
}

export async function deleteAnalysisTemplate(id: string): Promise<void> {
  await api.delete(`/api/v1/ai/analysis-templates/${encodeURIComponent(id)}`);
}

export async function seedAnalysisTemplates(): Promise<{ message: string; inserted: number }> {
  const response = await api.post('/api/v1/ai/analysis-templates/seed');
  return response.data;
}

// =============================================================================
// Statistics
// =============================================================================

import type {
  GlobalStats,
  DataStats,
  MemoryStatsData,
  EmbeddingStatsData,
  ViewpointStatsData,
  PerUserStats,
} from '@/types';

export async function getGlobalStats(): Promise<GlobalStats> {
  const response = await api.get('/api/v1/stats');
  return response.data;
}

export async function getDataStats(): Promise<DataStats> {
  const response = await api.get('/api/v1/stats/data');
  return response.data;
}

export async function getMemoryStats(): Promise<MemoryStatsData> {
  const response = await api.get('/api/v1/stats/memories');
  return response.data;
}

export async function getEmbeddingStats(): Promise<EmbeddingStatsData> {
  const response = await api.get('/api/v1/stats/embeddings');
  return response.data;
}

export async function getViewpointStats(): Promise<ViewpointStatsData> {
  const response = await api.get('/api/v1/stats/viewpoints');
  return response.data;
}

export async function getUserStats(userId: string): Promise<PerUserStats> {
  const response = await api.get(`/api/v1/stats/users/${userId}`);
  return response.data;
}

export async function refreshStats(): Promise<GlobalStats> {
  const response = await api.post('/api/v1/stats/refresh');
  return response.data;
}

export async function refreshUserStats(userId: string): Promise<PerUserStats> {
  const response = await api.post(`/api/v1/stats/refresh/users/${userId}`);
  return response.data;
}

export async function dropTokenUsage(userId: string): Promise<void> {
  await api.delete(`/api/v1/stats/token-usage/${encodeURIComponent(userId)}`);
}

// =============================================================================
// Channel identity correlation
// =============================================================================

export async function createChannelIdentity(
  body: ChannelIdentityCreateType
): Promise<ChannelIdentityRecord> {
  const response = await api.post<ChannelIdentityRecord>('/api/v1/channel-identities', body);
  return response.data;
}

export async function getChannelIdentityByChannel(
  channelType: string,
  channelUniqueId: string
): Promise<ChannelIdentityRecord> {
  const response = await api.get<ChannelIdentityRecord>('/api/v1/channel-identities/by-channel', {
    params: { channel_type: channelType, channel_unique_id: channelUniqueId },
  });
  return response.data;
}

export async function listChannelIdentitiesByUser(
  userId: string
): Promise<ChannelIdentityListResponse> {
  const response = await api.get<ChannelIdentityListResponse>(
    `/api/v1/channel-identities/by-user/${encodeURIComponent(userId)}`
  );
  return response.data;
}

export async function updateChannelIdentity(
  channelType: string,
  channelUniqueId: string,
  body: ChannelIdentityUpdateType
): Promise<ChannelIdentityRecord> {
  const response = await api.patch<ChannelIdentityRecord>(
    '/api/v1/channel-identities/by-channel',
    body,
    { params: { channel_type: channelType, channel_unique_id: channelUniqueId } }
  );
  return response.data;
}

export async function deleteChannelIdentity(
  channelType: string,
  channelUniqueId: string
): Promise<void> {
  await api.delete('/api/v1/channel-identities/by-channel', {
    params: { channel_type: channelType, channel_unique_id: channelUniqueId },
  });
}

// =============================================================================
// Channels bucket — per-channel metadata
// =============================================================================

export async function listChannels(): Promise<ChannelMetadata[]> {
  const response = await api.get<ChannelMetadata[]>('/api/v1/channels');
  return response.data;
}

export async function getChannel(channelType: string): Promise<ChannelMetadata> {
  const response = await api.get<ChannelMetadata>(
    `/api/v1/channels/${encodeURIComponent(channelType)}`
  );
  return response.data;
}

export async function putChannel(
  channelType: string,
  body: ChannelMetadataCreate
): Promise<ChannelMetadata> {
  const response = await api.put<ChannelMetadata>(
    `/api/v1/channels/${encodeURIComponent(channelType)}`,
    body
  );
  return response.data;
}

export async function deleteChannel(channelType: string): Promise<void> {
  await api.delete(`/api/v1/channels/${encodeURIComponent(channelType)}`);
}

// =============================================================================
// Smart Routing — Ollama Cloud model cards + per-data-type routing
// =============================================================================

export async function getOllamaCloudModels(refresh = false): Promise<{
  models: any[];
  count: number;
  categories: Record<string, string[]>;
}> {
  const response = await api.get('/api/v1/ai/ollama-cloud-models', {
    params: refresh ? { refresh: true } : undefined,
  });
  return response.data;
}

export async function getSmartRoutingSuggestions(): Promise<{
  suggestions: Record<string, { primary: string; fallback: string; reason: string }>;
  data_type_requirements: Record<string, { min_tier: string; needs: string[] }>;
  categories: Record<string, string[]>;
}> {
  const response = await api.get('/api/v1/ai/smart-routing-suggestions');
  return response.data;
}

export async function getSmartRoutingConfig(userId: string): Promise<{
  routing: Record<string, {
    primary: string;
    fallback: string;
    suggested_primary: string;
    suggested_fallback: string;
    reason: string;
    is_override: boolean;
  }>;
  categories: Record<string, string[]>;
}> {
  const response = await api.get(`/api/v1/ai/smart-routing-config/${encodeURIComponent(userId)}`);
  return response.data;
}

export async function getModelCatalog(): Promise<{
  total: number;
  families: string[];
  roles: string[];
  models: Record<string, any>;
}> {
  const response = await api.get('/api/v1/ai/model-catalog');
  return response.data;
}

// =============================================================================
// Integration Platform
// =============================================================================

export async function listProviders(category?: string): Promise<IntegrationProvider[]> {
  const params: Record<string, string> = {};
  if (category) params.category = category;
  const response = await api.get<IntegrationProvider[]>('/api/v1/integrations/providers', { params });
  return response.data;
}

export async function getProvider(providerKey: string): Promise<IntegrationProvider> {
  const response = await api.get<IntegrationProvider>(
    `/api/v1/integrations/providers/${encodeURIComponent(providerKey)}`
  );
  return response.data;
}

export async function listIntegrationConnections(userId?: string, providerKey?: string): Promise<IntegrationConnection[]> {
  const params: Record<string, string> = {};
  if (userId) params.user_id = userId;
  if (providerKey) params.provider_key = providerKey;
  const response = await api.get<IntegrationConnection[]>('/api/v1/integrations/connections', { params });
  return response.data;
}

export async function createApiKeyConnection(body: IntegrationConnectionCreate): Promise<IntegrationConnection> {
  const response = await api.post<IntegrationConnection>('/api/v1/integrations/connections/api-key', body);
  return response.data;
}

export async function deleteIntegrationConnection(connectionId: string): Promise<void> {
  await api.delete(`/api/v1/integrations/connections/${encodeURIComponent(connectionId)}`);
}

export async function getOAuthAuthorizeUrl(
  providerKey: string,
  userId: string,
  redirectUri: string,
): Promise<{ authorize_url: string; state: string }> {
  const response = await api.get(`/api/v1/integrations/oauth/authorize/${encodeURIComponent(providerKey)}`, {
    params: { user_id: userId, redirect_uri: redirectUri },
  });
  return response.data;
}

export async function setProviderOAuthCredentials(
  providerKey: string,
  clientId: string,
  clientSecret: string,
): Promise<IntegrationProvider> {
  const response = await api.put<IntegrationProvider>(
    `/api/v1/integrations/providers/${encodeURIComponent(providerKey)}/oauth-credentials`,
    { client_id: clientId, client_secret: clientSecret },
  );
  return response.data;
}

export async function clearProviderOAuthCredentials(providerKey: string): Promise<IntegrationProvider> {
  const response = await api.delete<IntegrationProvider>(
    `/api/v1/integrations/providers/${encodeURIComponent(providerKey)}/oauth-credentials`,
  );
  return response.data;
}

export async function refreshIntegrationConnection(connectionId: string): Promise<IntegrationConnection> {
  const response = await api.post<IntegrationConnection>(
    `/api/v1/integrations/oauth/refresh/${encodeURIComponent(connectionId)}`
  );
  return response.data;
}

// =============================================================================
// Per-User API Keys
// =============================================================================

export async function listApiKeys(userId: string): Promise<APIKeyResponse[]> {
  const response = await api.get<APIKeyResponse[]>(
    `/api/v1/users/${encodeURIComponent(userId)}/api-keys`
  );
  return response.data;
}

export async function createApiKey(
  userId: string,
  name: string,
  expiresInDays?: number,
): Promise<APIKeyResponse> {
  const body: Record<string, unknown> = { name };
  if (expiresInDays) body.expires_in_days = expiresInDays;
  const response = await api.post<APIKeyResponse>(
    `/api/v1/users/${encodeURIComponent(userId)}/api-keys`,
    body,
  );
  return response.data;
}

export async function deleteApiKey(userId: string, keyId: string): Promise<void> {
  await api.delete(
    `/api/v1/users/${encodeURIComponent(userId)}/api-keys/${encodeURIComponent(keyId)}`
  );
}

// =============================================================================
// Organizations & Projects
// =============================================================================

import type { Organization, Project, OrgMember } from '@/types';

export async function listOrganizations(): Promise<{ organizations: Organization[]; total: number }> {
  const response = await api.get('/api/v1/organizations');
  return response.data;
}

export async function createOrganization(body: { name: string; display_name?: string }): Promise<Organization> {
  const response = await api.post('/api/v1/organizations', body);
  return response.data;
}

export async function getOrganization(orgId: string): Promise<Organization> {
  const response = await api.get(`/api/v1/organizations/${encodeURIComponent(orgId)}`);
  return response.data;
}

export async function deleteOrganization(orgId: string): Promise<void> {
  await api.delete(`/api/v1/organizations/${encodeURIComponent(orgId)}`);
}

export async function listOrgMembers(orgId: string): Promise<{ members: OrgMember[]; total: number }> {
  const response = await api.get(`/api/v1/organizations/${encodeURIComponent(orgId)}/members`);
  return response.data;
}

export async function addOrgMember(orgId: string, userId: string, role: string = 'member'): Promise<OrgMember> {
  const response = await api.post(`/api/v1/organizations/${encodeURIComponent(orgId)}/members`, { user_id: userId, role });
  return response.data;
}

export async function removeOrgMember(orgId: string, userId: string): Promise<void> {
  await api.delete(`/api/v1/organizations/${encodeURIComponent(orgId)}/members/${encodeURIComponent(userId)}`);
}

export async function listProjects(orgId: string): Promise<{ projects: Project[]; total: number }> {
  const response = await api.get(`/api/v1/organizations/${encodeURIComponent(orgId)}/projects`);
  return response.data;
}

export async function createProject(orgId: string, body: { name: string; display_name?: string; description?: string }): Promise<Project> {
  const response = await api.post(`/api/v1/organizations/${encodeURIComponent(orgId)}/projects`, body);
  return response.data;
}

export async function getProject(projectId: string): Promise<Project> {
  const response = await api.get(`/api/v1/projects/${encodeURIComponent(projectId)}`);
  return response.data;
}

export async function deleteProject(projectId: string): Promise<void> {
  await api.delete(`/api/v1/projects/${encodeURIComponent(projectId)}`);
}

// =============================================================================
// Webhooks (per-user webhook endpoints)
// =============================================================================

import type { Webhook, WebhookCreate, WebhookUpdate, WebhookEvent, WebhookStats } from '@/types';

export async function listWebhooks(channelType?: string, status?: string): Promise<Webhook[]> {
  const params = new URLSearchParams();
  if (channelType) params.set('channel_type', channelType);
  if (status) params.set('status', status);
  const qs = params.toString();
  const response = await api.get<Webhook[]>(`/api/v1/webhooks${qs ? `?${qs}` : ''}`);
  return response.data;
}

export async function createWebhook(body: WebhookCreate): Promise<Webhook> {
  const response = await api.post<Webhook>('/api/v1/webhooks', body);
  return response.data;
}

export async function getWebhook(webhookId: string): Promise<Webhook> {
  const response = await api.get<Webhook>(`/api/v1/webhooks/${encodeURIComponent(webhookId)}`);
  return response.data;
}

export async function updateWebhook(webhookId: string, body: WebhookUpdate): Promise<Webhook> {
  const response = await api.patch<Webhook>(`/api/v1/webhooks/${encodeURIComponent(webhookId)}`, body);
  return response.data;
}

export async function deleteWebhook(webhookId: string): Promise<void> {
  await api.delete(`/api/v1/webhooks/${encodeURIComponent(webhookId)}`);
}

export async function rotateWebhookSecret(webhookId: string): Promise<Webhook> {
  const response = await api.post<Webhook>(`/api/v1/webhooks/${encodeURIComponent(webhookId)}/rotate-secret`);
  return response.data;
}

export async function listWebhookEvents(webhookId: string, status?: string, limit?: number): Promise<WebhookEvent[]> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (limit) params.set('limit', String(limit));
  const qs = params.toString();
  const response = await api.get<WebhookEvent[]>(
    `/api/v1/webhooks/${encodeURIComponent(webhookId)}/events${qs ? `?${qs}` : ''}`
  );
  return response.data;
}

export async function getWebhookStats(webhookId: string, period?: string): Promise<WebhookStats> {
  const params = period ? `?period=${encodeURIComponent(period)}` : '';
  const response = await api.get<WebhookStats>(`/api/v1/webhooks/${encodeURIComponent(webhookId)}/stats${params}`);
  return response.data;
}


/** Configuration for the MemDog client. */
export interface MemDogConfig {
  /** API base URL (e.g. "http://localhost:8080"). */
  baseUrl: string;
  /** API key for Bearer auth. Omit for unauthenticated access. */
  apiKey?: string;
  /** Default user ID scoped to all operations. */
  userId?: string;
  /** Request timeout in milliseconds (default 30000). */
  timeout?: number;
}

// ---------------------------------------------------------------------------
// Enums / union types
// ---------------------------------------------------------------------------

export type SearchMode = 'vector' | 'fts' | 'hybrid' | 'graph' | 'full';
export type RerankerType = 'none' | 'rrf' | 'mmr' | 'cross_encoder';
export type MemoryType = 'timeline' | 'session' | 'conversation' | 'user' | 'organizational' | 'factual' | 'episodic' | 'semantic' | 'custom' | 'tracing';
export type AccessLevel = 'private' | 'shared' | 'public' | 'restricted';
export type EntityTypeName = 'person' | 'organization' | 'product' | 'location' | 'date' | 'url' | 'concept' | 'event';

// ---------------------------------------------------------------------------
// Simple facade option types (kept for backwards compat)
// ---------------------------------------------------------------------------

export interface AddOptions {
  file?: File | Blob;
  tags?: string[];
  name?: string;
  description?: string;
  memoryType?: string;
  memoryId?: string;
  memoryIds?: string[];
  userId?: string;
}

export interface AddResult {
  dataId: string;
  memoryId?: string;
}

export interface SearchOptions {
  limit?: number;
  memoryType?: string;
  memoryIds?: string[];
  useAi?: boolean;
  userId?: string;
}

export interface EntitiesOptions {
  entityType?: string;
  limit?: number;
  userId?: string;
}

export interface RelatedOptions {
  userId?: string;
}

export interface CompressOptions {
  archiveOriginals?: boolean;
  maxSummaryLength?: number;
  userId?: string;
}

export interface CompressResult {
  memoryId: string;
  summaryDataId: string;
  originalCount: number;
  summaryLength: number;
  archived: boolean;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Full client option types
// ---------------------------------------------------------------------------

export interface SemanticSearchOptions {
  searchMode?: SearchMode;
  reranker?: RerankerType;
  limit?: number;
  userId?: string;
  memoryType?: MemoryType;
  temporalFilter?: string;
}

export interface ChatOptions {
  searchMode?: SearchMode;
  reranker?: RerankerType;
  conversationHistory?: Array<{ role: string; content: string }>;
  memoryType?: MemoryType;
}

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

export class MemDogError extends Error {
  status: number;
  body: string;

  constructor(status: number, body: string) {
    super(`MemDog API error ${status}: ${body}`);
    this.name = "MemDogError";
    this.status = status;
    this.body = body;
  }
}

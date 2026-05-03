'use client';

import { useState } from 'react';
import {
  BookOpen, Server, HelpCircle, Database, Brain, Link2, Webhook, Search,
  Users, ChevronRight, ChevronDown, Cpu, Shield, GitBranch, BarChart3,
  MessageSquare, Activity, FolderOpen, Clock, TestTube, Settings,
  Layers, Monitor, Upload, Zap, Key, Box, HardDrive, Tag, Eye,
  FileText, Sparkles, Wrench, Network, Globe, Flower2,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────────

type Section = 'overview' | 'platform' | 'api' | 'faq';

interface Endpoint {
  method: string;
  path: string;
  desc: string;
  params?: string;
  response?: string;
}

interface ApiGroup {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  endpoints: Endpoint[];
}

// ── Section Nav ────────────────────────────────────────────────────────────────

const SECTIONS: { id: Section; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'overview',  label: 'Overview',        icon: BookOpen },
  { id: 'platform',  label: 'Platform Guide',  icon: Monitor },
  { id: 'api',       label: 'API Reference',   icon: Server },
  { id: 'faq',       label: 'FAQ',             icon: HelpCircle },
];

// ── Overview Concepts ──────────────────────────────────────────────────────────

const CONCEPTS = [
  {
    title: 'Data Items',
    icon: Database,
    desc: 'The core unit of storage in Mem-Dog. Every piece of ingested content — text, images, PDFs, JSON, audio, video, and 30+ other MIME types — becomes a data item with a unique ULID-based ID (data_<ulid>). Items support versioning (automatic version history on updates), tagging (arbitrary key-value metadata for organization), and access control lists (per-item read/write permissions). Each item stores its raw content, extracted metadata, MIME type, size, and processing status.',
  },
  {
    title: 'Organizations & Projects',
    icon: Globe,
    desc: 'Multi-tenant hierarchy for scoping data, memories, and embeddings. An Organization (org_<ulid>) represents a team or company. Projects (proj_<ulid>) live inside orgs and scope memories and data. Members have roles: owner (full control), admin (manage members/projects), member (read/write), viewer (read-only). All existing endpoints accept an optional project_id query parameter to scope results. Use Settings → Organizations to manage orgs, projects, and members.',
  },
  {
    title: 'Memories',
    icon: Brain,
    desc: 'Structured representations that organize data into 10 distinct types grouped into 4 Mem0 categories. Short-term: Conversation (1h TTL, dialogue threads), Timeline (7d, chronological events), Session (24h, activity windows), Tracing (3d, debug trails). Long-term (no expiry): User (personal preferences), Organizational (team knowledge), Factual (verified facts), Episodic (experience recollections), Semantic (conceptual knowledge), Custom (user-defined). Each memory can be scoped to a project, has sub-types for finer categorization, access levels (private/shared/public/restricted), and TTL overrides.',
  },
  {
    title: 'AI Pipeline',
    icon: Cpu,
    desc: 'A 40-agent webhook pipeline powered by NATS streaming. When data is ingested, it flows through 6-layer type detection (explicit field → LLM classifier → MIME registry → URL extension → content sniffing → BinaryBlobAgent fallback) to route to the correct specialist agent. Agents use tiered AI models — small (Gemma3:4b) for simple tasks, medium (12b) for standard analysis, large (27b) for complex reasoning, multimodal (Qwen3-VL) for images/video, and omni (Qwen3.5) for cross-modal tasks. Outputs include embeddings, viewpoints (structured analyses), entity extraction, summaries, and classifications.',
  },
  {
    title: 'Apps',
    icon: Webhook,
    desc: '300+ apps across 15 categories, powered by Nango for OAuth, token refresh, and credential management. Inbound apps (Slack, WhatsApp, Telegram, etc.) receive data through per-user webhook endpoints (whk_<ulid>) and normalize it into UniversalEnvelope format. Outbound apps (Salesforce, GitHub, Stripe, etc.) connect via OAuth2 or API keys — Nango handles token refresh automatically and encrypts credentials with AES-256-GCM. Many apps support both directions. The DigiMe agent lives in your channels as an interactive AI, separate from the webhook pipeline.',
  },
  {
    title: 'Search',
    icon: Search,
    desc: 'Five search modes powered by pgvector + Graphiti knowledge graph. Vector: cosine similarity over embeddings. FTS: BM25 full-text keyword search. Hybrid: combines vector + BM25 with Reciprocal Rank Fusion (RRF). Graph: searches the Graphiti temporal knowledge graph using BFS traversal + semantic matching. Full: runs pgvector hybrid + Graphiti graph in parallel, merges with RRF for maximum recall. Four reranking strategies available: RRF (rank fusion), MMR (diversity), cross-encoder (LLM-scored), and none. Temporal filtering lets you query facts valid at a specific point in time. Conversational RAG supports all search modes with inline [1][2] citations.',
  },
  {
    title: 'Knowledge Graph',
    icon: Network,
    desc: 'Dual-layer knowledge graph: Postgres entity tables (zero-infra, entity-aware RAG) + optional Graphiti temporal knowledge graph backed by Neo4j. Entities are extracted automatically during AI enrichment (8 types: person, org, product, location, date, url, concept, event) and dual-written to both stores. Graphiti adds temporal awareness — facts have valid_at/invalid_at timestamps, so you can query what was known at any point in time. The graph powers BFS traversal, community detection, and episode-based fact evolution. Enable by setting NEO4J_URI; without it, Postgres graph works standalone.',
  },
  {
    title: 'Smart Routing',
    icon: Zap,
    desc: 'Intelligent model selection that automatically assigns the right AI model tier based on data characteristics. The 6-layer detection system (explicit field → LLM classifier → MIME registry → URL extension → content sniffing → BinaryBlobAgent fallback) first identifies the data type, then smart routing rules map each type to an optimal model tier: small (Gemma3:4b) for simple text classification, medium (12b) for structured analysis, large (27b) for complex reasoning, multimodal (Qwen3-VL) for images/video, and omni (Qwen3.5) for cross-modal tasks. Routing rules are fully configurable per data type via the AI Config API, and you can set priority overrides to force specific models for certain content categories.',
  },
  {
    title: 'Hosting',
    icon: HardDrive,
    desc: 'Deploy locally with Docker Compose (single command starts all 9 services — UI, API, gateway, NATS, Ollama, and more) or to Google Cloud with GKE (API, webhook pipeline, gateway) and Cloud Run (UI). Storage backends are pluggable: local filesystem for development, GCS for legacy cloud, or Supabase with pgvector for production. Same codebase, same config — just set STORAGE_BACKEND and deploy.',
  },
  {
    title: 'LLM Configuration',
    icon: Wrench,
    desc: 'Fully configurable AI layer with 5 model tiers (Small/Medium/Large/Multimodal/Omni), customizable system prompts per agent, reusable skills and prompt templates, and per-data-type model overrides. Fallback chains (Ollama Cloud → Gemini → self-hosted) ensure reliability. All settings manageable from the UI via Settings → AI Config, including processing flags, smart routing rules, agent prompts, and skill definitions.',
  },
  {
    title: 'Architecture',
    icon: GitBranch,
    desc: 'Data flows from Channels → Per-User Webhooks (whk_<ulid>) → Webhook Gateway → API → Storage + Webhook Pipeline (NATS). The API (FastAPI on GKE) handles storage, auth, and search. Nango (self-hosted) manages OAuth flows, token refresh, and encrypted credential storage for 300+ integrations. The UI (Next.js on Cloud Run) proxies all API calls through server-side rewrites. The Webhook Pipeline (40 typed agents) processes ingested data through 6-layer classification, LLM analysis, entity extraction, and embedding generation. The MCP Server exposes 8 tools over SSE for Claude Desktop, Cursor, and other MCP-compatible agents. Extracted entities dual-write to both Postgres graph tables and Graphiti/Neo4j temporal knowledge graph. Storage backends: local filesystem (dev), GCS (legacy), Supabase + pgvector (production). Neo4j (optional) powers graph search, BFS traversal, and temporal fact queries. All external traffic enters through a GKE Gateway (L7 LB) with path-based routing to API, webhook gateway, MCP server, Nango, and OpenClaw Node.',
  },
  {
    title: 'Model Garden',
    icon: Flower2,
    desc: 'Per-user AI provider management. Configure your own providers (OpenAI, Anthropic, Gemini, Ollama, OpenRouter, Together AI, Hugging Face, Bedrock, vLLM, LiteLLM) with encrypted API key storage. Test connectivity with one click, discover available models automatically, and feed them into the Smart Routing system. Each user has isolated provider configs — API keys are encrypted with Fernet (AES-256) and never returned in API responses. The webhook processor resolves credentials per-request with fallback to system env vars.',
  },
  {
    title: 'MCP Server',
    icon: Server,
    desc: 'Model Context Protocol server exposing mem-dog as 8 tools (search, add, get, delete, entities, chat, memories, list_data) over SSE transport. Connect Claude Desktop, Cursor, or any MCP-compatible agent to your mem-dog instance. Per-user auth via md_* API keys — every tool call scopes to the authenticated user. Deployed on GKE in the mem-dog namespace, proxied via the gateway at /mcp/sse. The MCP server is a thin proxy over the API using the mem_dog_client SDK, so all data access policies and auth apply identically.',
  },
];

// ── Platform Guide ─────────────────────────────────────────────────────────────

const PLATFORM_TABS = [
  {
    title: 'Insights',
    icon: BarChart3,
    desc: 'Dashboard overview of your data and AI processing activity.',
    features: [
      '5 stat cards: total data items, memories, embeddings, viewpoints, and storage used',
      '6 breakdown charts: data by type, memory by type, AI processing status, ingestion timeline, top tags, and channel activity',
      'Token usage tracking: total tokens consumed, cost breakdown by model tier, daily/weekly/monthly trends',
      'Manual refresh button to reload all stats on demand',
      'Responsive grid layout adapts from 1 to 3 columns based on screen size',
    ],
  },
  {
    title: 'AI',
    icon: Sparkles,
    desc: 'Manage AI-generated viewpoints and vector embeddings.',
    features: [
      'Viewpoints sub-tab: browse all AI-generated structured analyses with expand/collapse for full content',
      'Filter viewpoints by agent type, data type, or date range',
      'Bulk delete viewpoints with multi-select checkboxes and confirmation dialog',
      'Embeddings sub-tab: view vector embedding records with metadata (model, dimensions, status)',
      'Bulk delete embeddings with selection mode and batch operations',
      'Pagination controls for large result sets',
    ],
  },
  {
    title: 'Knowledge Chat',
    icon: MessageSquare,
    desc: 'Conversational RAG interface for querying your data using natural language. Available as a sub-tab in the Playground.',
    features: [
      'Chat-based interface with message history and streaming responses',
      'Automatic citation of source data items with clickable links to originals',
      'Memory scope selector: choose which memory types and data to include in context',
      'Suggestion chips: pre-built query shortcuts for common questions',
      'Context-aware follow-up: the AI remembers conversation context for multi-turn queries',
      'Supports markdown rendering in responses including code blocks, tables, and lists',
    ],
  },
  {
    title: 'Telemetry',
    icon: Activity,
    desc: 'Distributed tracing for monitoring webhook pipeline and API performance.',
    features: [
      'Trace list view with search and status/date filters',
      'Span waterfall visualization showing timing breakdown of each processing stage',
      'Auto-refresh toggle for real-time trace monitoring',
      'Detail drawer: click any trace to see full span tree, attributes, events, and errors',
      'Filter by trace ID, service name, operation, status code, or duration range',
      'Color-coded status indicators (success/error/pending) for quick scanning',
    ],
  },
  {
    title: 'Data',
    icon: FolderOpen,
    desc: 'Browse, search, and manage all ingested data items.',
    features: [
      'Paginated data list with configurable page size (10/25/50/100)',
      'Full-text search across data content and metadata',
      'Tag filter sidebar to narrow results by assigned tags',
      'Selection mode: check individual items or select all for bulk operations',
      'Bulk delete selected items with confirmation dialog',
      'Click any item to view full details, metadata, versions, tags, and access control',
      'Download button for binary data items (images, PDFs, files)',
    ],
  },
  {
    title: 'Audit',
    icon: Clock,
    desc: 'Timeline view of system events and data lifecycle activity.',
    features: [
      'Chronological event feed showing all create, update, delete, and process actions',
      'Color-coded action badges: green (create), blue (update), amber (process), red (delete)',
      'Filter by action type, data type, user, or date range',
      'Each event shows timestamp, actor, action, target item, and change summary',
      'Links to affected data items and memories for quick navigation',
    ],
  },
  {
    title: 'Memories',
    icon: Brain,
    desc: 'Create, filter, and manage structured memories across all 10 types, scoped to the selected project.',
    features: [
      'Create new memories with type selector, sub-type, access level, and TTL — automatically scoped to the selected project',
      'Project scope indicator shows which org/project the memory will be created in',
      'Memory type → Mem0 category mapping: conversation→conversation (1h), timeline/session/tracing→session (7d/24h/3d), user/factual/episodic/semantic/custom→user (no expiry), organizational→organizational (no expiry)',
      'Filter by memory type, sub-type, project, access level, category, and expiry status',
      'Bulk operations: select multiple memories for batch delete or type reassignment',
      'Associate/dissociate data items with memories via drag-and-drop or search picker',
      'Project badge on each memory card shows which project it belongs to',
      'Access levels: private (default), shared (specific users), public (all users), restricted (explicit user list)',
    ],
  },
  {
    title: 'Playground',
    icon: TestTube,
    desc: 'Interactive sandbox for testing the full ingestion pipeline, uploading data, and chatting with your knowledge base.',
    features: [
      'Channel to Webhook: simulate webhook messages across 10+ channel types (Slack, Email, WhatsApp, Telegram, Discord, SMS, RSS, API, Webhook, Custom) with file attachments — or select a user-created webhook endpoint (whk_<ulid>) for per-webhook routing',
      'Data Insert: ingest via 6 input modes — text (with dictation), file drag-and-drop, URL import, camera capture, voice recording, and video recording',
      'Knowledge Chat: RAG-powered conversational interface over your stored data with inline citations, memory scope selectors, and multi-turn context',
      'Session management: group related uploads into named sessions',
      'Gateway URL auto-detection from environment with protocol validation',
      'Progress indicators and success/error feedback for each operation',
    ],
  },
  {
    title: 'Settings',
    icon: Settings,
    desc: 'Configure your profile, organizations, AI processing, and app connections.',
    features: [
      'Profile section: view/edit user ID, display name, and API key management',
      'Organizations: create/delete orgs and projects, manage members with role-based access (owner/admin/member/viewer)',
      'Project selector in header: switch between projects to scope data, memories, and insights',
      'AI Config: toggle processing flags (auto-process on ingest, generate embeddings, generate viewpoints)',
      'Model Garden: configure AI providers (OpenAI, Anthropic, Gemini, Ollama, etc.) with encrypted API keys, test connectivity, and discover available models',
      'Smart routing configuration: set model tier preferences per data type — dynamically populated from Model Garden providers',
      'Agent Configs: customize individual AI agent behavior, prompts, and model assignments',
      'Apps: browse 300+ providers across 15 categories, connect via OAuth2 or API key, with inbound/outbound capability badges',
      'Webhooks: create per-user webhook endpoints (whk_<ulid>) with unique URLs, optional HMAC signing secrets, pause/resume, secret rotation, and 24h stats (total, success rate, failures)',
      'OAuth flow management: authorize, refresh tokens, and revoke connections',
      'Connection health monitoring with last-sync timestamps and error indicators',
    ],
  },
  {
    title: 'Hosting',
    icon: HardDrive,
    desc: 'Run locally or deploy to Google Cloud — same codebase, same config.',
    features: [
      'Local: docker compose up starts all 9 services (UI :3000, API :8080, gateway :8070, NATS, Ollama)',
      'Local storage backend with filesystem at /data — no cloud credentials needed',
      'GKE deployment: API + webhook pipeline + gateway across namespaces with L7 gateway routing',
      'Cloud Run deployment for UI with build-time env var baking (Supabase auth, API URL)',
      'Supabase self-hosted on GKE: Postgres+pgvector, GoTrue auth, PostgREST, Kong, Realtime',
      'Automated deploy scripts: ./scripts/manual-deploy.sh with per-component commands',
    ],
  },
  {
    title: 'LLMs & AI Config',
    icon: Sparkles,
    desc: 'Full control over AI models, prompts, skills, and routing — all from the UI.',
    features: [
      '5 model tiers: Small (Gemma3:4b), Medium (12b), Large (27b), Multimodal (Qwen3-VL), Omni (Qwen3.5)',
      'Model Garden: connect 11 AI providers (OpenAI, Anthropic, Gemini, Ollama, OpenRouter, Together, HuggingFace, Bedrock, vLLM, LiteLLM) with per-user encrypted API keys, connectivity testing, and automatic model discovery',
      'Smart routing: per-data-type model assignment dynamically populated from Model Garden providers, with capability cards and priority overrides',
      'Configurable prompts: customize system prompts per agent type for extraction, analysis, and output format',
      'Skills: define reusable AI skills (entity extraction, sentiment, summarization) and attach to agents',
      'Templates: create prompt templates with variable placeholders for consistent agent behavior',
      'Fallback chains: user-configured provider → Ollama Cloud → Gemini → self-hosted Ollama for reliability',
      'Processing flags: toggle auto-process, embedding generation, and viewpoint generation per user',
    ],
  },
];

// ── API Reference ──────────────────────────────────────────────────────────────

const API_GROUPS: ApiGroup[] = [
  {
    title: 'Data',
    icon: Database,
    endpoints: [
      { method: 'POST', path: '/api/v1/data', desc: 'Ingest a new data item', params: 'Body: content (string|file), mime_type, tags (optional), session_id (optional)', response: '201: { id, mime_type, size, created_at }' },
      { method: 'GET', path: '/api/v1/data', desc: 'List all data items with pagination', params: 'Query: page, page_size, tag, mime_type, sort_by, order', response: '200: { items: [...], total, page, page_size }' },
      { method: 'GET', path: '/api/v1/data/{id}', desc: 'Get a single data item by ID', params: 'Path: id (data_<ulid>)', response: '200: { id, content, mime_type, size, tags, metadata, created_at, updated_at }' },
      { method: 'PUT', path: '/api/v1/data/{id}', desc: 'Update a data item (creates new version)', params: 'Path: id; Body: content, mime_type (optional)', response: '200: { id, version, updated_at }' },
      { method: 'DELETE', path: '/api/v1/data/{id}', desc: 'Delete a data item and all versions', params: 'Path: id', response: '204: No content' },
      { method: 'GET', path: '/api/v1/data/{id}/metadata', desc: 'Get item metadata without content', params: 'Path: id', response: '200: { id, mime_type, size, tags, created_at, updated_at, version_count }' },
      { method: 'PUT', path: '/api/v1/data/{id}/metadata', desc: 'Update item metadata only', params: 'Path: id; Body: metadata (object)', response: '200: { id, metadata, updated_at }' },
      { method: 'GET', path: '/api/v1/data/{id}/info', desc: 'Get detailed item info including processing status', params: 'Path: id', response: '200: { id, mime_type, size, processing_status, embedding_status, viewpoint_count }' },
      { method: 'PUT', path: '/api/v1/data/{id}/download-flag', desc: 'Set download availability flag', params: 'Path: id; Body: { downloadable: boolean }', response: '200: { id, downloadable }' },
    ],
  },
  {
    title: 'Tags',
    icon: Tag,
    endpoints: [
      { method: 'GET', path: '/api/v1/data/{id}/tags', desc: 'Get all tags for a data item', params: 'Path: id', response: '200: { tags: [...] }' },
      { method: 'PUT', path: '/api/v1/data/{id}/tags', desc: 'Set tags (replaces existing)', params: 'Path: id; Body: { tags: string[] }', response: '200: { id, tags }' },
      { method: 'POST', path: '/api/v1/data/{id}/tags', desc: 'Add tags to existing set', params: 'Path: id; Body: { tags: string[] }', response: '200: { id, tags }' },
      { method: 'DELETE', path: '/api/v1/data/{id}/tags', desc: 'Remove specific tags', params: 'Path: id; Body: { tags: string[] }', response: '200: { id, tags }' },
      { method: 'GET', path: '/api/v1/tags', desc: 'List all tags in the system', params: 'Query: prefix (optional)', response: '200: { tags: [{ name, count }] }' },
      { method: 'GET', path: '/api/v1/data/by-tag/{tag}', desc: 'Search data items by tag', params: 'Path: tag; Query: page, page_size', response: '200: { items: [...], total }' },
    ],
  },
  {
    title: 'Access Control',
    icon: Shield,
    endpoints: [
      { method: 'GET', path: '/api/v1/data/{id}/acl', desc: 'Get access control list for item', params: 'Path: id', response: '200: { owner, readers: [...], writers: [...] }' },
      { method: 'PUT', path: '/api/v1/data/{id}/acl', desc: 'Set access control list', params: 'Path: id; Body: { readers: string[], writers: string[] }', response: '200: { id, acl }' },
      { method: 'POST', path: '/api/v1/data/{id}/acl/check', desc: 'Check if user has access', params: 'Path: id; Body: { user_id, permission: "read"|"write" }', response: '200: { allowed: boolean }' },
    ],
  },
  {
    title: 'Versions',
    icon: GitBranch,
    endpoints: [
      { method: 'GET', path: '/api/v1/data/{id}/versions', desc: 'List all versions of a data item', params: 'Path: id', response: '200: { versions: [{ version, size, created_at }] }' },
      { method: 'GET', path: '/api/v1/data/{id}/versions/{version}', desc: 'Get a specific version', params: 'Path: id, version (integer)', response: '200: { id, version, content, mime_type, created_at }' },
    ],
  },
  {
    title: 'Memories',
    icon: Brain,
    endpoints: [
      { method: 'POST', path: '/api/v1/memories', desc: 'Create a new memory', params: 'Body: type, sub_type (optional), content, data_ids (optional)', response: '201: { id, type, sub_type, created_at }' },
      { method: 'GET', path: '/api/v1/memories', desc: 'List memories with filtering', params: 'Query: type, sub_type, page, page_size, sort_by', response: '200: { items: [...], total, page }' },
      { method: 'GET', path: '/api/v1/memories/{id}', desc: 'Get a memory by ID', params: 'Path: id (mem_<type>_<ulid>)', response: '200: { id, type, sub_type, content, entries, data_ids, created_at }' },
      { method: 'PUT', path: '/api/v1/memories/{id}', desc: 'Update a memory', params: 'Path: id; Body: content, sub_type (optional)', response: '200: { id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/memories/{id}', desc: 'Delete a memory', params: 'Path: id', response: '204: No content' },
      { method: 'POST', path: '/api/v1/memories/{id}/data', desc: 'Associate data items with memory', params: 'Path: id; Body: { data_ids: string[] }', response: '200: { id, data_ids }' },
      { method: 'DELETE', path: '/api/v1/memories/{id}/data/{data_id}', desc: 'Remove data association', params: 'Path: id, data_id', response: '204: No content' },
      { method: 'GET', path: '/api/v1/memories/{id}/entries', desc: 'List entries in a memory', params: 'Path: id; Query: page, page_size', response: '200: { entries: [...], total }' },
      { method: 'POST', path: '/api/v1/memories/{id}/entries', desc: 'Add entry to a memory', params: 'Path: id; Body: { content, metadata }', response: '201: { entry_id, created_at }' },
      { method: 'DELETE', path: '/api/v1/memories/{id}/entries/{entry_id}', desc: 'Delete a memory entry', params: 'Path: id, entry_id', response: '204: No content' },
      { method: 'POST', path: '/api/v1/memories/bulk-delete', desc: 'Bulk delete memories', params: 'Body: { ids: string[] }', response: '200: { deleted: number }' },
    ],
  },
  {
    title: 'Organizations & Projects',
    icon: Globe,
    endpoints: [
      { method: 'POST', path: '/api/v1/organizations', desc: 'Create organization (caller becomes owner)', params: 'Body: { name, display_name }', response: '201: { org_id, name, owner_user_id }' },
      { method: 'GET', path: '/api/v1/organizations', desc: 'List user\'s organizations', params: 'None (uses auth context)', response: '200: { organizations: [...], total }' },
      { method: 'GET', path: '/api/v1/organizations/{org_id}', desc: 'Get organization details', params: 'Path: org_id', response: '200: { org_id, name, display_name, owner_user_id, status }' },
      { method: 'PUT', path: '/api/v1/organizations/{org_id}', desc: 'Update organization (owner/admin)', params: 'Path: org_id; Body: { name, display_name, metadata }', response: '200: { org_id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/organizations/{org_id}', desc: 'Delete organization (owner only)', params: 'Path: org_id', response: '200: { deleted: true }' },
      { method: 'POST', path: '/api/v1/organizations/{org_id}/members', desc: 'Add member to org (owner/admin)', params: 'Path: org_id; Body: { user_id, role }', response: '201: { org_id, user_id, role }' },
      { method: 'GET', path: '/api/v1/organizations/{org_id}/members', desc: 'List org members', params: 'Path: org_id', response: '200: { members: [...], total }' },
      { method: 'PUT', path: '/api/v1/organizations/{org_id}/members/{user_id}', desc: 'Change member role', params: 'Path: org_id, user_id; Body: { role }', response: '200: { org_id, user_id, role }' },
      { method: 'DELETE', path: '/api/v1/organizations/{org_id}/members/{user_id}', desc: 'Remove member', params: 'Path: org_id, user_id', response: '200: { removed: true }' },
      { method: 'POST', path: '/api/v1/organizations/{org_id}/projects', desc: 'Create project in org', params: 'Path: org_id; Body: { name, display_name, description }', response: '201: { project_id, org_id, name }' },
      { method: 'GET', path: '/api/v1/organizations/{org_id}/projects', desc: 'List projects in org', params: 'Path: org_id', response: '200: { projects: [...], total }' },
      { method: 'GET', path: '/api/v1/projects/{project_id}', desc: 'Get project by ID', params: 'Path: project_id', response: '200: { project_id, org_id, name, display_name, description }' },
      { method: 'PUT', path: '/api/v1/projects/{project_id}', desc: 'Update project', params: 'Path: project_id; Body: { name, display_name, description }', response: '200: { project_id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/projects/{project_id}', desc: 'Delete project', params: 'Path: project_id', response: '200: { deleted: true }' },
    ],
  },
  {
    title: 'Users',
    icon: Users,
    endpoints: [
      { method: 'POST', path: '/api/v1/users', desc: 'Create a new user', params: 'Body: { username, display_name, email (optional) }', response: '201: { id, username, display_name, created_at }' },
      { method: 'GET', path: '/api/v1/users', desc: 'List all users', params: 'Query: page, page_size', response: '200: { users: [...], total }' },
      { method: 'GET', path: '/api/v1/users/{id}', desc: 'Get user by ID', params: 'Path: id', response: '200: { id, username, display_name, email, created_at }' },
      { method: 'PUT', path: '/api/v1/users/{id}', desc: 'Update user profile', params: 'Path: id; Body: { display_name, email }', response: '200: { id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/users/{id}', desc: 'Delete a user', params: 'Path: id', response: '204: No content' },
      { method: 'GET', path: '/api/v1/users/by-username/{username}', desc: 'Lookup user by username', params: 'Path: username', response: '200: { id, username, display_name }' },
      { method: 'POST', path: '/api/v1/users/{id}/api-keys', desc: 'Generate a new API key', params: 'Path: id; Body: { name, expires_in (optional) }', response: '201: { key, name, created_at, expires_at }' },
      { method: 'GET', path: '/api/v1/users/{id}/api-keys', desc: 'List API keys for user', params: 'Path: id', response: '200: { keys: [{ name, prefix, created_at, expires_at }] }' },
      { method: 'DELETE', path: '/api/v1/users/{id}/api-keys/{key_id}', desc: 'Revoke an API key', params: 'Path: id, key_id', response: '204: No content' },
      { method: 'GET', path: '/api/v1/users/{id}/data', desc: 'List data items owned by user', params: 'Path: id; Query: page, page_size', response: '200: { items: [...], total }' },
      { method: 'GET', path: '/api/v1/users/{id}/memories', desc: 'List memories owned by user', params: 'Path: id; Query: type, page, page_size', response: '200: { items: [...], total }' },
      { method: 'GET', path: '/api/v1/users/{id}/stats', desc: 'Get user-level statistics', params: 'Path: id', response: '200: { data_count, memory_count, storage_used, token_usage }' },
    ],
  },
  {
    title: 'AI Query',
    icon: Search,
    endpoints: [
      { method: 'POST', path: '/api/v1/ai/query/semantic', desc: 'Multi-mode semantic search (vector, fts, hybrid, graph, full)', params: 'Body: { query, max_results, search_mode (vector|fts|hybrid|graph|full), vector_weight, fts_weight, rerank: { method, mmr_lambda }, temporal: { valid_at, valid_after, valid_before }, synthesise, user_id }', response: '200: { query, records: [{ data_id, best_similarity, matching_chunks: [{ chunk_text, similarity, fts_rank, rrf_score, search_type }] }], answer, latency_ms }' },
      { method: 'POST', path: '/api/v1/ai/query/chat', desc: 'Conversational RAG with citations and multi-mode search', params: 'Body: { message, history, max_results, search_mode, vector_weight, fts_weight, rerank, temporal, memory_id, user_id }', response: '200: { answer, citations: [{ index, data_id, chunk_text, similarity }], model, latency_ms }' },
      { method: 'POST', path: '/api/v1/ai/query/timeline', desc: 'Query timeline data items', params: 'Body: { query, timeline_data_ids, max_tokens }', response: '200: { query, response, sources, latency_ms }' },
      { method: 'GET', path: '/api/v1/graph/facts', desc: 'Query temporal facts from knowledge graph', params: 'Query: q, entity_id, at (ISO datetime for point-in-time), limit', response: '200: [{ fact, source_entity, target_entity, valid_at, invalid_at }]' },
      { method: 'GET', path: '/api/v1/graph/facts/timeline', desc: 'Fact history timeline for an entity', params: 'Query: entity_id, limit', response: '200: [{ fact, source_entity, target_entity, valid_at, invalid_at }]' },
    ],
  },
  {
    title: 'AI Viewpoints',
    icon: Eye,
    endpoints: [
      { method: 'GET', path: '/api/v1/viewpoints', desc: 'List all viewpoints', params: 'Query: data_id, agent_type, page, page_size', response: '200: { items: [...], total }' },
      { method: 'GET', path: '/api/v1/viewpoints/{id}', desc: 'Get viewpoint by ID', params: 'Path: id', response: '200: { id, data_id, agent_type, content, model, created_at }' },
      { method: 'POST', path: '/api/v1/viewpoints', desc: 'Create a viewpoint manually', params: 'Body: { data_id, agent_type, content, model }', response: '201: { id, created_at }' },
      { method: 'PUT', path: '/api/v1/viewpoints/{id}', desc: 'Update a viewpoint', params: 'Path: id; Body: { content }', response: '200: { id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/viewpoints/{id}', desc: 'Delete a viewpoint', params: 'Path: id', response: '204: No content' },
      { method: 'POST', path: '/api/v1/viewpoints/bulk-delete', desc: 'Bulk delete viewpoints', params: 'Body: { ids: string[] }', response: '200: { deleted: number }' },
      { method: 'GET', path: '/api/v1/viewpoints/history/{data_id}', desc: 'Get viewpoint history for data item', params: 'Path: data_id; Query: page, page_size', response: '200: { items: [...], total }' },
      { method: 'GET', path: '/api/v1/viewpoints/agents', desc: 'List agent types with viewpoint counts', params: 'None', response: '200: { agents: [{ type, count }] }' },
    ],
  },
  {
    title: 'AI Embeddings',
    icon: Layers,
    endpoints: [
      { method: 'GET', path: '/api/v1/embeddings', desc: 'List all embeddings', params: 'Query: data_id, model, page, page_size', response: '200: { items: [...], total }' },
      { method: 'GET', path: '/api/v1/embeddings/{id}', desc: 'Get embedding by ID', params: 'Path: id', response: '200: { id, data_id, model, dimensions, vector (optional), created_at }' },
      { method: 'POST', path: '/api/v1/embeddings', desc: 'Create embedding manually', params: 'Body: { data_id, model, vector }', response: '201: { id, created_at }' },
      { method: 'DELETE', path: '/api/v1/embeddings/{id}', desc: 'Delete an embedding', params: 'Path: id', response: '204: No content' },
      { method: 'POST', path: '/api/v1/embeddings/bulk-delete', desc: 'Bulk delete embeddings', params: 'Body: { ids: string[] }', response: '200: { deleted: number }' },
      { method: 'POST', path: '/api/v1/embeddings/regenerate/{data_id}', desc: 'Regenerate embedding for a data item', params: 'Path: data_id; Body: { model (optional) }', response: '202: { task_id }' },
      { method: 'GET', path: '/api/v1/embeddings/models', desc: 'List available embedding models', params: 'None', response: '200: { models: [{ name, dimensions, description }] }' },
    ],
  },
  {
    title: 'AI Config',
    icon: Settings,
    endpoints: [
      { method: 'GET', path: '/api/v1/ai/config', desc: 'Get system AI configuration', params: 'None', response: '200: { auto_process, generate_embeddings, generate_viewpoints, default_model }' },
      { method: 'PUT', path: '/api/v1/ai/config', desc: 'Update system AI configuration', params: 'Body: { auto_process, generate_embeddings, generate_viewpoints }', response: '200: { updated_at }' },
      { method: 'GET', path: '/api/v1/ai/models', desc: 'Get model catalog', params: 'None', response: '200: { models: [{ id, name, tier, capabilities, context_length }] }' },
      { method: 'GET', path: '/api/v1/ai/models/{model_id}', desc: 'Get model details', params: 'Path: model_id', response: '200: { id, name, tier, provider, capabilities, config }' },
      { method: 'PUT', path: '/api/v1/ai/models/{model_id}', desc: 'Update model configuration', params: 'Path: model_id; Body: { config }', response: '200: { id, updated_at }' },
      { method: 'GET', path: '/api/v1/ai/routing', desc: 'Get smart routing rules', params: 'None', response: '200: { rules: [{ data_type, model_tier, priority }] }' },
      { method: 'PUT', path: '/api/v1/ai/routing', desc: 'Update smart routing rules', params: 'Body: { rules: [...] }', response: '200: { updated_at }' },
      { method: 'GET', path: '/api/v1/ai/engines', desc: 'List AI engine instances', params: 'None', response: '200: { engines: [{ id, type, status, model }] }' },
      { method: 'POST', path: '/api/v1/ai/engines', desc: 'Register a new AI engine', params: 'Body: { type, endpoint, model, config }', response: '201: { id, status }' },
      { method: 'PUT', path: '/api/v1/ai/engines/{id}', desc: 'Update engine configuration', params: 'Path: id; Body: { config, status }', response: '200: { id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/ai/engines/{id}', desc: 'Remove an AI engine', params: 'Path: id', response: '204: No content' },
      { method: 'GET', path: '/api/v1/ai/engines/{id}/health', desc: 'Check engine health', params: 'Path: id', response: '200: { status, latency_ms, last_check }' },
      { method: 'GET', path: '/api/v1/ai/preferences', desc: 'Get user AI preferences', params: 'None', response: '200: { default_model, auto_process, embedding_model }' },
      { method: 'PUT', path: '/api/v1/ai/preferences', desc: 'Update user AI preferences', params: 'Body: { default_model, auto_process, embedding_model }', response: '200: { updated_at }' },
      { method: 'GET', path: '/api/v1/ai/usage', desc: 'Get AI token usage stats', params: 'Query: period (day|week|month)', response: '200: { total_tokens, by_model: [...], by_day: [...] }' },
      { method: 'GET', path: '/api/v1/ai/queue', desc: 'Get AI processing queue status', params: 'None', response: '200: { pending, processing, completed, failed }' },
      { method: 'POST', path: '/api/v1/ai/process/{data_id}', desc: 'Manually trigger AI processing', params: 'Path: data_id; Body: { agents (optional) }', response: '202: { task_id }' },
      { method: 'GET', path: '/api/v1/ai/process/{task_id}/status', desc: 'Check processing task status', params: 'Path: task_id', response: '200: { status, progress, agents_completed, agents_total }' },
    ],
  },
  {
    title: 'AI Agent Configs',
    icon: Wrench,
    endpoints: [
      { method: 'GET', path: '/api/v1/ai/agents', desc: 'List all agent configurations', params: 'None', response: '200: { agents: [{ type, model, enabled, config }] }' },
      { method: 'GET', path: '/api/v1/ai/agents/{type}', desc: 'Get agent config by type', params: 'Path: type', response: '200: { type, model, enabled, prompt, config }' },
      { method: 'PUT', path: '/api/v1/ai/agents/{type}', desc: 'Update agent configuration', params: 'Path: type; Body: { model, enabled, prompt, config }', response: '200: { type, updated_at }' },
      { method: 'POST', path: '/api/v1/ai/agents', desc: 'Create custom agent config', params: 'Body: { type, model, prompt, config }', response: '201: { type, created_at }' },
      { method: 'DELETE', path: '/api/v1/ai/agents/{type}', desc: 'Delete agent configuration', params: 'Path: type', response: '204: No content' },
      { method: 'GET', path: '/api/v1/ai/agents/{type}/effective', desc: 'Get effective config (merged with defaults)', params: 'Path: type', response: '200: { type, model, prompt, config, source }' },
    ],
  },
  {
    title: 'Model Garden',
    icon: Flower2,
    endpoints: [
      { method: 'GET', path: '/api/v1/ai/provider-registry', desc: 'Get static provider catalog (11 providers)', params: 'None', response: '200: { providers: [{ engine_type, display_name, description, requires_api_key, default_base_url, default_models, category }] }' },
      { method: 'GET', path: '/api/v1/ai/users/{uid}/engines', desc: 'List user engine configurations', params: 'Path: uid', response: '200: { engines: [{ engine_id, name, engine_type, has_api_key, discovered_models, last_test_status }] }' },
      { method: 'POST', path: '/api/v1/ai/users/{uid}/engines', desc: 'Create engine config (API key encrypted at rest)', params: 'Path: uid; Body: { engine_type, name, api_key, base_url }', response: '201: { engine_id, name, has_api_key }' },
      { method: 'PUT', path: '/api/v1/ai/users/{uid}/engines/{eid}', desc: 'Update engine config', params: 'Path: uid, eid; Body: { name, api_key, base_url }', response: '200: { engine_id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/ai/users/{uid}/engines/{eid}', desc: 'Delete engine config', params: 'Path: uid, eid', response: '200: { message }' },
      { method: 'POST', path: '/api/v1/ai/users/{uid}/engines/{eid}/test', desc: 'Test provider connectivity', params: 'Path: uid, eid', response: '200: { ok, latency_ms, error, tested_at }' },
      { method: 'POST', path: '/api/v1/ai/users/{uid}/engines/{eid}/discover-models', desc: 'Discover available models from provider', params: 'Path: uid, eid', response: '200: { models: [...], count }' },
      { method: 'GET', path: '/api/v1/ai/users/{uid}/available-models', desc: 'Aggregated models from all user + system providers', params: 'Path: uid', response: '200: { providers: [{ name, engine_type, litellm_prefix, models, source }] }' },
    ],
  },
  {
    title: 'Analysis Templates',
    icon: FileText,
    endpoints: [
      { method: 'GET', path: '/api/v1/ai/templates', desc: 'List analysis templates', params: 'Query: category (optional)', response: '200: { templates: [{ id, name, category, schema }] }' },
      { method: 'GET', path: '/api/v1/ai/templates/{id}', desc: 'Get template by ID', params: 'Path: id', response: '200: { id, name, category, schema, sample_output }' },
      { method: 'POST', path: '/api/v1/ai/templates', desc: 'Create analysis template', params: 'Body: { name, category, schema }', response: '201: { id, created_at }' },
      { method: 'PUT', path: '/api/v1/ai/templates/{id}', desc: 'Update analysis template', params: 'Path: id; Body: { schema }', response: '200: { id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/ai/templates/{id}', desc: 'Delete analysis template', params: 'Path: id', response: '204: No content' },
      { method: 'POST', path: '/api/v1/ai/templates/{id}/run', desc: 'Run template on data item', params: 'Path: id; Body: { data_id }', response: '202: { task_id }' },
    ],
  },
  {
    title: 'Statistics',
    icon: BarChart3,
    endpoints: [
      { method: 'GET', path: '/api/v1/stats', desc: 'Get global system statistics', params: 'None', response: '200: { data_count, memory_count, embedding_count, viewpoint_count, storage_bytes }' },
      { method: 'GET', path: '/api/v1/stats/data', desc: 'Data breakdown by type', params: 'None', response: '200: { by_mime: [...], by_tag: [...], by_date: [...] }' },
      { method: 'GET', path: '/api/v1/stats/memories', desc: 'Memory breakdown by type', params: 'None', response: '200: { by_type: [...], by_subtype: [...] }' },
      { method: 'GET', path: '/api/v1/stats/ai', desc: 'AI processing statistics', params: 'None', response: '200: { processed, pending, failed, by_agent: [...] }' },
      { method: 'GET', path: '/api/v1/stats/tokens', desc: 'Token usage statistics', params: 'Query: period (day|week|month)', response: '200: { total, by_model: [...], by_day: [...], cost }' },
      { method: 'GET', path: '/api/v1/stats/agents', desc: 'Agent type counts and performance', params: 'None', response: '200: { agents: [{ type, count, avg_duration_ms }] }' },
      { method: 'GET', path: '/api/v1/stats/storage', desc: 'Storage usage breakdown', params: 'None', response: '200: { total_bytes, by_mime: [...], by_user: [...] }' },
      { method: 'GET', path: '/api/v1/stats/channels', desc: 'Channel activity statistics', params: 'None', response: '200: { by_channel: [...], by_day: [...], total_messages }' },
      { method: 'GET', path: '/api/v1/stats/ingestion', desc: 'Ingestion timeline', params: 'Query: period, granularity', response: '200: { timeline: [{ date, count, bytes }] }' },
      { method: 'GET', path: '/api/v1/stats/users/{id}', desc: 'Per-user statistics', params: 'Path: id', response: '200: { data_count, memory_count, storage_bytes, token_usage }' },
      { method: 'GET', path: '/api/v1/stats/users/{id}/tokens', desc: 'Per-user token usage', params: 'Path: id; Query: period', response: '200: { total, by_model: [...], cost }' },
      { method: 'GET', path: '/api/v1/stats/users/{id}/activity', desc: 'Per-user activity timeline', params: 'Path: id; Query: period', response: '200: { events: [{ date, action, count }] }' },
      { method: 'GET', path: '/api/v1/stats/search', desc: 'Search usage statistics', params: 'Query: period', response: '200: { total_queries, avg_results, by_type: [...] }' },
      { method: 'GET', path: '/api/v1/stats/integrations', desc: 'Integration usage statistics', params: 'None', response: '200: { connected: number, by_provider: [...], sync_stats }' },
    ],
  },
  {
    title: 'Integrations',
    icon: Link2,
    endpoints: [
      { method: 'GET', path: '/api/v1/integrations/providers', desc: 'List all available providers', params: 'Query: category, app_category, search', response: '200: { providers: [{ id, name, app_category, capabilities, auth_type, logo_url }] }' },
      { method: 'GET', path: '/api/v1/integrations/providers/{id}', desc: 'Get provider details', params: 'Path: id', response: '200: { id, name, app_category, capabilities, channel_key, auth_type, scopes, docs_url }' },
      { method: 'GET', path: '/api/v1/integrations/app-categories', desc: 'List the 15 unified app categories', params: 'None', response: '200: [{ key, label, count }]' },
      { method: 'POST', path: '/api/v1/integrations/connections', desc: 'Create a new connection', params: 'Body: { provider_id, auth_type, credentials }', response: '201: { id, provider_id, status, created_at }' },
      { method: 'GET', path: '/api/v1/integrations/connections', desc: 'List active connections', params: 'Query: provider_id, status', response: '200: { connections: [{ id, provider, status, last_sync }] }' },
      { method: 'GET', path: '/api/v1/integrations/connections/{id}', desc: 'Get connection details', params: 'Path: id', response: '200: { id, provider, status, config, last_sync, error }' },
      { method: 'PUT', path: '/api/v1/integrations/connections/{id}', desc: 'Update connection config', params: 'Path: id; Body: { config }', response: '200: { id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/integrations/connections/{id}', desc: 'Delete a connection', params: 'Path: id', response: '204: No content' },
      { method: 'GET', path: '/api/v1/integrations/oauth/{provider}/authorize', desc: 'Get OAuth authorization URL', params: 'Path: provider; Query: redirect_uri', response: '200: { auth_url }' },
      { method: 'POST', path: '/api/v1/integrations/oauth/{provider}/callback', desc: 'Handle OAuth callback', params: 'Path: provider; Body: { code, state }', response: '200: { connection_id, status }' },
      { method: 'POST', path: '/api/v1/integrations/connections/{id}/refresh', desc: 'Refresh OAuth token', params: 'Path: id', response: '200: { status, expires_at }' },
      { method: 'POST', path: '/api/v1/integrations/connections/{id}/test', desc: 'Test connection health', params: 'Path: id', response: '200: { healthy: boolean, latency_ms }' },
      { method: 'POST', path: '/api/v1/integrations/proxy', desc: 'Proxy API request through connection', params: 'Body: { connection_id, method, path, body }', response: '200: { status, data }' },
      { method: 'GET', path: '/api/v1/integrations/connections/{id}/credentials', desc: 'Get decrypted credentials (admin)', params: 'Path: id', response: '200: { credentials }' },
    ],
  },
  {
    title: 'Webhooks',
    icon: Webhook,
    endpoints: [
      { method: 'POST', path: '/api/v1/webhooks', desc: 'Create a new webhook endpoint', params: 'Body: { channel_type, name, generate_secret, config }', response: '201: { webhook_id, user_id, channel_type, url, secret, status }' },
      { method: 'GET', path: '/api/v1/webhooks', desc: 'List user webhooks', params: 'Query: channel_type, status', response: '200: [{ webhook_id, channel_type, name, status, url, config }]' },
      { method: 'GET', path: '/api/v1/webhooks/{id}', desc: 'Get webhook details', params: 'Path: id', response: '200: { webhook_id, user_id, channel_type, name, status, url, config }' },
      { method: 'PATCH', path: '/api/v1/webhooks/{id}', desc: 'Update webhook', params: 'Path: id; Body: { name, channel_type, status, config }', response: '200: { webhook_id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/webhooks/{id}', desc: 'Soft-delete webhook (revokes URL)', params: 'Path: id', response: '204: No content' },
      { method: 'POST', path: '/api/v1/webhooks/{id}/rotate-secret', desc: 'Regenerate signing secret', params: 'Path: id', response: '200: { webhook_id, secret }' },
      { method: 'GET', path: '/api/v1/webhooks/{id}/events', desc: 'List webhook event log', params: 'Path: id; Query: status, limit, offset', response: '200: [{ event_id, status, error_message, latency_ms, trace_id }]' },
      { method: 'GET', path: '/api/v1/webhooks/{id}/stats', desc: 'Get aggregated webhook stats', params: 'Path: id; Query: period (1h, 24h, 7d, 30d)', response: '200: { total, by_status, success_rate }' },
    ],
  },
  {
    title: 'LLMs',
    icon: Cpu,
    endpoints: [
      { method: 'GET', path: '/api/v1/llms/providers', desc: 'List LLM provider registry', params: 'None', response: '200: { providers: [{ id, name, type, models }] }' },
      { method: 'GET', path: '/api/v1/llms/providers/{id}', desc: 'Get provider details', params: 'Path: id', response: '200: { id, name, type, endpoint, models, config }' },
      { method: 'POST', path: '/api/v1/llms/providers', desc: 'Register a new LLM provider', params: 'Body: { name, type, endpoint, api_key, models }', response: '201: { id, created_at }' },
      { method: 'PUT', path: '/api/v1/llms/providers/{id}', desc: 'Update LLM provider', params: 'Path: id; Body: { endpoint, api_key, config }', response: '200: { id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/llms/providers/{id}', desc: 'Remove LLM provider', params: 'Path: id', response: '204: No content' },
      { method: 'POST', path: '/api/v1/llms/providers/{id}/test', desc: 'Test LLM provider connection', params: 'Path: id', response: '200: { healthy: boolean, latency_ms, model }' },
      { method: 'GET', path: '/api/v1/llms/models', desc: 'List all available models', params: 'Query: provider_id, capability', response: '200: { models: [{ id, name, provider, capabilities }] }' },
      { method: 'GET', path: '/api/v1/llms/ollama/models', desc: 'List Ollama models on machines', params: 'Query: machine_id', response: '200: { models: [{ name, size, modified_at }] }' },
      { method: 'POST', path: '/api/v1/llms/ollama/pull', desc: 'Pull a model to Ollama machine', params: 'Body: { machine_id, model_name }', response: '202: { task_id }' },
      { method: 'DELETE', path: '/api/v1/llms/ollama/models/{model}', desc: 'Delete Ollama model', params: 'Path: model; Query: machine_id', response: '204: No content' },
      { method: 'POST', path: '/api/v1/llms/generate', desc: 'Generate text with specific model', params: 'Body: { model, prompt, max_tokens, temperature }', response: '200: { text, tokens_used, model }' },
    ],
  },
  {
    title: 'Machines',
    icon: HardDrive,
    endpoints: [
      { method: 'POST', path: '/api/v1/machines', desc: 'Register an Ollama machine', params: 'Body: { name, endpoint, gpu_info }', response: '201: { id, name, status }' },
      { method: 'GET', path: '/api/v1/machines', desc: 'List registered machines', params: 'None', response: '200: { machines: [{ id, name, endpoint, status, models }] }' },
      { method: 'DELETE', path: '/api/v1/machines/{id}', desc: 'Remove a machine', params: 'Path: id', response: '204: No content' },
    ],
  },
  {
    title: 'Channels',
    icon: Network,
    endpoints: [
      { method: 'GET', path: '/api/v1/channels', desc: 'List all channels', params: 'Query: type', response: '200: { channels: [{ id, type, name, status }] }' },
      { method: 'POST', path: '/api/v1/channels', desc: 'Create a channel', params: 'Body: { type, name, config }', response: '201: { id, type, created_at }' },
      { method: 'PUT', path: '/api/v1/channels/{id}', desc: 'Update channel config', params: 'Path: id; Body: { config }', response: '200: { id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/channels/{id}', desc: 'Delete a channel', params: 'Path: id', response: '204: No content' },
    ],
  },
  {
    title: 'Channel Identities',
    icon: Users,
    endpoints: [
      { method: 'GET', path: '/api/v1/channel-identities', desc: 'List channel identities', params: 'Query: channel_id, user_id', response: '200: { identities: [{ id, channel_id, external_id, display_name }] }' },
      { method: 'POST', path: '/api/v1/channel-identities', desc: 'Create a channel identity', params: 'Body: { channel_id, external_id, display_name, metadata }', response: '201: { id, created_at }' },
      { method: 'GET', path: '/api/v1/channel-identities/{id}', desc: 'Get identity details', params: 'Path: id', response: '200: { id, channel_id, user_id, external_id, display_name, metadata }' },
      { method: 'PUT', path: '/api/v1/channel-identities/{id}', desc: 'Update channel identity', params: 'Path: id; Body: { display_name, metadata }', response: '200: { id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/channel-identities/{id}', desc: 'Delete channel identity', params: 'Path: id', response: '204: No content' },
    ],
  },
  {
    title: 'Ingest',
    icon: Upload,
    endpoints: [
      { method: 'POST', path: '/api/v1/ingest', desc: 'Universal ingest endpoint (webhook gateway)', params: 'Body: UniversalEnvelope { source, channel, content, attachments, metadata }', response: '202: { id, status: "queued" }' },
    ],
  },
  {
    title: 'Bulk Delete',
    icon: Box,
    endpoints: [
      { method: 'POST', path: '/api/v1/data/bulk-delete', desc: 'Bulk delete data items', params: 'Body: { ids: string[] }', response: '200: { deleted: number }' },
      { method: 'POST', path: '/api/v1/memories/bulk-delete', desc: 'Bulk delete memories', params: 'Body: { ids: string[] }', response: '200: { deleted: number }' },
      { method: 'POST', path: '/api/v1/viewpoints/bulk-delete', desc: 'Bulk delete viewpoints', params: 'Body: { ids: string[] }', response: '200: { deleted: number }' },
      { method: 'POST', path: '/api/v1/embeddings/bulk-delete', desc: 'Bulk delete embeddings', params: 'Body: { ids: string[] }', response: '200: { deleted: number }' },
    ],
  },
  {
    title: 'Store KV',
    icon: Database,
    endpoints: [
      { method: 'GET', path: '/api/v1/store/{key}', desc: 'Get value by key', params: 'Path: key', response: '200: { key, value, updated_at }' },
      { method: 'PUT', path: '/api/v1/store/{key}', desc: 'Set value for key', params: 'Path: key; Body: { value: any }', response: '200: { key, updated_at }' },
      { method: 'DELETE', path: '/api/v1/store/{key}', desc: 'Delete a key', params: 'Path: key', response: '204: No content' },
      { method: 'GET', path: '/api/v1/store', desc: 'List all keys', params: 'Query: prefix (optional)', response: '200: { keys: [{ key, updated_at }] }' },
    ],
  },
];

// ── FAQ ────────────────────────────────────────────────────────────────────────

const FAQ_ITEMS: { q: string; a: string }[] = [
  {
    q: 'What data formats are supported?',
    a: 'Mem-Dog accepts 30+ formats including JSON, plain text, Markdown, HTML, images (PNG, JPEG, GIF, WebP, SVG), PDFs, audio (MP3, WAV, OGG), video (MP4, WebM), code files, CSV, XML, and binary blobs. The webhook pipeline auto-detects the data type using 6-layer detection: explicit field, LLM classifier, MIME registry, URL extension, content sniffing, and fallback to BinaryBlobAgent.',
  },
  {
    q: 'How does AI enrichment work?',
    a: 'When data is ingested, it flows through a 40-agent webhook pipeline powered by NATS. Each agent specializes in a specific data type (e.g., TextAgent, ImageAgent, CodeAgent, MedicalAgent, LegalAgent). Agents classify the content, extract entities, generate summaries, produce structured viewpoints (analysis documents), and create vector embeddings for semantic search. The pipeline runs asynchronously — you can check processing status via the AI queue endpoints.',
  },
  {
    q: 'What are the 10 memory types and how do they map to categories?',
    a: 'Memory types map to 4 Mem0 categories with default TTLs:\n\n• Conversation category: conversation (1h TTL)\n• Session category: timeline (7d), session (24h), tracing (3d)\n• User category: user, factual, episodic, semantic, custom (no expiry)\n• Organizational category: organizational (no expiry)\n\nAll types support ttl_hours override and no_expiry flag. Access levels: private (default), shared, public, restricted. When creating a memory, it\'s automatically scoped to the selected project via the header selector.',
  },
  {
    q: 'How do organizations and projects work?',
    a: 'Organizations (org_<ulid>) represent teams or companies. Projects (proj_<ulid>) live inside orgs and scope data, memories, and embeddings. Members have roles: owner (full control), admin (manage members/projects), member (read/write data), viewer (read-only). Use the project selector in the header to switch contexts — all data, memory, and embedding queries are automatically scoped. Manage orgs/projects/members in Settings → Organizations. Pass ?project_id= on any list endpoint to scope results programmatically.',
  },
  {
    q: 'How do apps work?',
    a: 'Mem-Dog provides 300+ apps across 15 categories, powered by Nango for OAuth and credential management. Inbound apps receive data through per-user webhook endpoints (whk_<ulid>) — create them in Settings → Webhooks. Outbound apps connect via OAuth2 or API keys; Nango handles the full OAuth flow, automatic token refresh, and encrypts credentials with AES-256-GCM. Many apps support both directions. Once connected, you can use the API proxy to make authenticated requests to upstream services.',
  },
  {
    q: 'How is data stored?',
    a: 'The storage backend is configurable via the STORAGE_BACKEND env var. Three options: local filesystem (~/.mem-dog) for development — simple file-based storage with directory structure. Google Cloud Storage (GCS) for production — scalable object storage with automatic backups. Supabase for hybrid storage — PostgreSQL for metadata and structured data, pgvector extension for vector embeddings, and optional blob storage for large files.',
  },
  {
    q: 'How do I authenticate?',
    a: 'API requests use a user ID passed as the X-User-ID header. Each user has a unique UUID. You can create users via POST /api/v1/users and generate API keys via POST /api/v1/users/{id}/api-keys. API keys are passed via the Authorization header (Bearer token). In the UI, the current user is shown in the top-right corner of the Settings tab.',
  },
  {
    q: 'How does versioning work?',
    a: 'Every data item supports automatic versioning. When you update a data item via PUT /api/v1/data/{id}, a new version is created while preserving all previous versions. You can list all versions of an item via GET /api/v1/data/{id}/versions and retrieve any specific version via GET /api/v1/data/{id}/versions/{version}. Version numbers are sequential integers starting at 1. Deleting a data item removes all its versions.',
  },
  {
    q: 'What AI models are supported?',
    a: 'Mem-Dog uses a tiered model system: small (Gemma3:4b) for simple classification and tagging, medium (Gemma3:12b) for standard analysis and summarization, large (Gemma3:27b) for complex reasoning and entity extraction, multimodal (Qwen3-VL) for image and video understanding, and omni (Qwen3.5) for cross-modal tasks. Models run on self-hosted Ollama instances. You can register multiple machines and manage models via the LLMs and Machines API endpoints.',
  },
  {
    q: 'How does the webhook pipeline process data?',
    a: 'Data arrives at the webhook gateway via POST /webhooks/{webhook_id} (per-user webhook endpoints) or POST /webhooks/{channel_type} (legacy). Per-user webhooks (whk_<ulid>) automatically resolve to the correct user and channel type — no identity heuristics needed. The gateway normalizes the payload into a UniversalEnvelope format and publishes it to NATS. The webhook processor receives the envelope and passes it through the 6-layer router to determine the data type. The router selects the appropriate specialist agent (e.g., TextAgent, ImageAgent, CodeAgent). The agent processes the data using the appropriate model tier, then stores results (viewpoints, embeddings, extracted entities) back via the API. Create and manage webhooks from Settings → Webhooks.',
  },
  {
    q: 'How do I use the Chat feature?',
    a: 'The Chat tab provides a conversational RAG (Retrieval-Augmented Generation) interface. Type a question and the system searches your data using semantic search, retrieves relevant items, and generates an AI response with citations. You can control the search scope using the memory scope selector (filter by memory types, date ranges, or specific data items). Suggestion chips provide quick-start queries. The system maintains conversation context for multi-turn discussions — use the conversation_id parameter in the API for programmatic access.',
  },
];

// ── Method Colors ──────────────────────────────────────────────────────────────

const METHOD_COLORS: Record<string, string> = {
  GET:    'text-emerald-400 bg-emerald-400/10',
  POST:   'text-blue-400 bg-blue-400/10',
  PUT:    'text-amber-400 bg-amber-400/10',
  PATCH:  'text-purple-400 bg-purple-400/10',
  DELETE: 'text-red-400 bg-red-400/10',
};

// ── Components ─────────────────────────────────────────────────────────────────

function EndpointRow({ ep }: { ep: Endpoint }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] transition-colors w-full text-left"
      >
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono flex-shrink-0 ${METHOD_COLORS[ep.method] || 'text-white/60'}`}>
          {ep.method}
        </span>
        <code className="text-xs text-white/80 font-mono flex-shrink-0">{ep.path}</code>
        <span className="text-xs text-white/40 ml-auto hidden sm:inline truncate max-w-[200px]">{ep.desc}</span>
        <ChevronRight className={`w-3 h-3 text-white/20 flex-shrink-0 transition-transform duration-200 ${open ? 'rotate-90' : ''}`} />
      </button>
      {open && (
        <div className="ml-4 mt-1 mb-2 px-3 py-2.5 rounded-lg bg-white/[0.02] border border-white/[0.05] space-y-1.5 animate-in">
          <p className="text-xs text-white/60">{ep.desc}</p>
          {ep.params && (
            <div>
              <span className="text-[10px] text-white/30 uppercase tracking-wider">Parameters</span>
              <p className="text-xs text-white/50 font-mono mt-0.5">{ep.params}</p>
            </div>
          )}
          {ep.response && (
            <div>
              <span className="text-[10px] text-white/30 uppercase tracking-wider">Response</span>
              <p className="text-xs text-white/50 font-mono mt-0.5">{ep.response}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ApiGroupCard({ group }: { group: ApiGroup }) {
  const [open, setOpen] = useState(false);
  const Icon = group.icon;
  return (
    <div className="glass-card rounded-2xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2.5 w-full p-5 text-left hover:bg-white/[0.02] transition-colors"
      >
        <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0">
          <Icon className="w-4 h-4 text-primary-400" />
        </div>
        <h3 className="text-sm font-semibold text-white">{group.title}</h3>
        <span className="text-[10px] text-white/30 ml-1">({group.endpoints.length})</span>
        <ChevronDown className={`w-4 h-4 text-white/30 ml-auto transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="px-5 pb-4 space-y-1.5 animate-in">
          {group.endpoints.map((ep) => (
            <EndpointRow key={`${ep.method}-${ep.path}`} ep={ep} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState<Section>('overview');
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Section nav */}
      <div className="flex items-center gap-2 p-1 bg-white/5 rounded-xl">
        {SECTIONS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveSection(id)}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeSection === id
                ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
                : 'text-white/50 hover:text-white/70 hover:bg-white/5'
            }`}
          >
            <Icon className="w-4 h-4" />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {/* ── Overview ──────────────────────────────────────────────────────── */}
      {activeSection === 'overview' && (
        <div className="space-y-6 animate-in">
          <div className="glass-card rounded-2xl p-6">
            <h3 className="text-lg font-semibold gradient-text mb-3">What is Mem-Dog?</h3>
            <p className="text-white/70 leading-relaxed text-sm">
              Mem-Dog is a multi-channel data ingestion and AI enrichment platform designed to capture, organize,
              and understand your data at scale. Data flows from 300+ apps across 15 categories
              through a normalizing webhook gateway, gets stored via a comprehensive REST API with versioning and
              access control, and is automatically processed by a 40-agent AI pipeline for classification, entity
              extraction, summarization, and vector embedding generation. The result is a searchable, queryable
              knowledge base accessible through semantic search, hybrid search, and conversational RAG with citations.
            </p>
          </div>

          {/* ── Architecture Diagram ─────────────────────────────────────── */}
          <div className="glass-card rounded-2xl p-6 overflow-x-auto">
            <h3 className="text-lg font-semibold gradient-text mb-4">System Architecture</h3>
            <svg viewBox="0 0 960 520" className="w-full min-w-[700px]" xmlns="http://www.w3.org/2000/svg">
              <defs>
                {/* Gradient definitions */}
                <linearGradient id="g-violet" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#a78bfa" stopOpacity="0.10" />
                </linearGradient>
                <linearGradient id="g-fuchsia" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#d946ef" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#e879f9" stopOpacity="0.10" />
                </linearGradient>
                <linearGradient id="g-emerald" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#34d399" stopOpacity="0.10" />
                </linearGradient>
                <linearGradient id="g-amber" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#fbbf24" stopOpacity="0.10" />
                </linearGradient>
                <linearGradient id="g-cyan" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.10" />
                </linearGradient>
                <linearGradient id="g-rose" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#fb7185" stopOpacity="0.10" />
                </linearGradient>
                <linearGradient id="g-sky" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.10" />
                </linearGradient>
                <filter id="glow">
                  <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                  <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
                </filter>
                <marker id="arrow" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 3 L 0 6 z" fill="#8b5cf680" />
                </marker>
                <marker id="arrow-emerald" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 3 L 0 6 z" fill="#10b98180" />
                </marker>
                <marker id="arrow-amber" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 3 L 0 6 z" fill="#f59e0b80" />
                </marker>
                <marker id="arrow-cyan" viewBox="0 0 10 6" refX="10" refY="3" markerWidth="8" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 0 L 10 3 L 0 6 z" fill="#06b6d480" />
                </marker>
              </defs>

              {/* ── Background zones ────────────────────────────── */}
              {/* Ingestion zone */}
              <rect x="8" y="8" width="220" height="504" rx="16" fill="white" fillOpacity="0.02" stroke="white" strokeOpacity="0.05" />
              <text x="118" y="32" textAnchor="middle" fill="white" fillOpacity="0.15" fontSize="10" fontWeight="600" letterSpacing="2">INGESTION</text>
              {/* Processing zone */}
              <rect x="248" y="8" width="220" height="504" rx="16" fill="white" fillOpacity="0.02" stroke="white" strokeOpacity="0.05" />
              <text x="358" y="32" textAnchor="middle" fill="white" fillOpacity="0.15" fontSize="10" fontWeight="600" letterSpacing="2">PROCESSING</text>
              {/* Storage zone */}
              <rect x="488" y="8" width="220" height="504" rx="16" fill="white" fillOpacity="0.02" stroke="white" strokeOpacity="0.05" />
              <text x="598" y="32" textAnchor="middle" fill="white" fillOpacity="0.15" fontSize="10" fontWeight="600" letterSpacing="2">STORAGE</text>
              {/* Query zone */}
              <rect x="728" y="8" width="224" height="504" rx="16" fill="white" fillOpacity="0.02" stroke="white" strokeOpacity="0.05" />
              <text x="840" y="32" textAnchor="middle" fill="white" fillOpacity="0.15" fontSize="10" fontWeight="600" letterSpacing="2">SEARCH &amp; QUERY</text>

              {/* ── Connections (drawn first, behind nodes) ──── */}
              {/* Channels → Gateway */}
              <path d="M 118 120 L 118 165" stroke="#8b5cf6" strokeOpacity="0.4" strokeWidth="1.5" markerEnd="url(#arrow)" />
              {/* Gateway → API */}
              <path d="M 168 200 L 298 120" stroke="#8b5cf6" strokeOpacity="0.4" strokeWidth="1.5" markerEnd="url(#arrow)" />
              {/* Gateway → Pipeline */}
              <path d="M 168 215 L 298 260" stroke="#8b5cf6" strokeOpacity="0.4" strokeWidth="1.5" markerEnd="url(#arrow)" />
              {/* UI → API */}
              <path d="M 168 340 L 298 120" stroke="#8b5cf6" strokeOpacity="0.3" strokeWidth="1.5" markerEnd="url(#arrow)" strokeDasharray="4 3" />
              {/* Pipeline → API (results) */}
              <path d="M 358 230 L 358 145" stroke="#10b981" strokeOpacity="0.4" strokeWidth="1.5" markerEnd="url(#arrow-emerald)" />
              {/* API → Supabase */}
              <path d="M 418 105 L 538 105" stroke="#06b6d4" strokeOpacity="0.4" strokeWidth="1.5" markerEnd="url(#arrow-cyan)" />
              {/* API → pgvector */}
              <path d="M 418 120 L 538 200" stroke="#06b6d4" strokeOpacity="0.4" strokeWidth="1.5" markerEnd="url(#arrow-cyan)" />
              {/* API → GCS */}
              <path d="M 418 130 L 538 310" stroke="#06b6d4" strokeOpacity="0.3" strokeWidth="1.5" markerEnd="url(#arrow-cyan)" />
              {/* API → Neo4j (dual-write) */}
              <path d="M 418 135 L 538 420" stroke="#f59e0b" strokeOpacity="0.5" strokeWidth="2" markerEnd="url(#arrow-amber)" strokeDasharray="6 3" />
              {/* API → Postgres Graph */}
              <path d="M 418 125 L 538 155" stroke="#06b6d4" strokeOpacity="0.3" strokeWidth="1.5" markerEnd="url(#arrow-cyan)" />
              {/* Pipeline → API entities */}
              <text x="330" y="185" fill="#10b981" fillOpacity="0.4" fontSize="8" fontStyle="italic">results</text>

              {/* Search connections */}
              {/* pgvector → Search */}
              <path d="M 658 210 L 778 130" stroke="#d946ef" strokeOpacity="0.4" strokeWidth="1.5" markerEnd="url(#arrow)" />
              {/* Neo4j → Search */}
              <path d="M 658 420 L 778 170" stroke="#f59e0b" strokeOpacity="0.5" strokeWidth="2" markerEnd="url(#arrow-amber)" />
              {/* Search → Reranker */}
              <path d="M 840 195 L 840 255" stroke="#d946ef" strokeOpacity="0.4" strokeWidth="1.5" markerEnd="url(#arrow)" />
              {/* Reranker → RAG Chat */}
              <path d="M 840 315 L 840 365" stroke="#d946ef" strokeOpacity="0.4" strokeWidth="1.5" markerEnd="url(#arrow)" />

              {/* Dual-write label */}
              <text x="475" y="310" fill="#f59e0b" fillOpacity="0.6" fontSize="8" fontWeight="600" transform="rotate(-55, 475, 310)">dual-write</text>

              {/* ── Nodes ───────────────────────────────────────── */}

              {/* Channels */}
              <rect x="38" y="55" width="160" height="65" rx="12" fill="url(#g-violet)" stroke="#8b5cf6" strokeOpacity="0.3" />
              <text x="118" y="80" textAnchor="middle" fill="#c4b5fd" fontSize="12" fontWeight="600">Channels</text>
              <text x="118" y="96" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">WhatsApp, Slack, Telegram</text>
              <text x="118" y="108" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">Discord, Email, 300+ apps</text>

              {/* Webhook Gateway */}
              <rect x="38" y="175" width="160" height="55" rx="12" fill="url(#g-violet)" stroke="#8b5cf6" strokeOpacity="0.3" />
              <text x="118" y="198" textAnchor="middle" fill="#c4b5fd" fontSize="11" fontWeight="600">Webhook Gateway</text>
              <text x="118" y="214" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">Normalize → UniversalEnvelope</text>

              {/* UI */}
              <rect x="38" y="310" width="160" height="55" rx="12" fill="url(#g-fuchsia)" stroke="#d946ef" strokeOpacity="0.3" />
              <text x="118" y="333" textAnchor="middle" fill="#f0abfc" fontSize="11" fontWeight="600">UI</text>
              <text x="118" y="349" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">Next.js · Cloud Run</text>

              {/* DigiMe */}
              <rect x="38" y="390" width="160" height="45" rx="12" fill="url(#g-rose)" stroke="#f43f5e" strokeOpacity="0.3" />
              <text x="118" y="410" textAnchor="middle" fill="#fda4af" fontSize="11" fontWeight="600">DigiMe Agent</text>
              <text x="118" y="426" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">OpenClaw · conversational AI</text>

              {/* MCP Server */}
              <rect x="38" y="450" width="160" height="50" rx="12" fill="url(#g-rose)" stroke="#f43f5e" strokeOpacity="0.3" />
              <text x="118" y="471" textAnchor="middle" fill="#fda4af" fontSize="11" fontWeight="600">MCP Server</text>
              <text x="118" y="487" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">Claude Desktop · Cursor · SSE</text>
              {/* MCP → API connection */}
              <path d="M 168 475 L 298 130" stroke="#f43f5e" strokeOpacity="0.3" strokeWidth="1.5" markerEnd="url(#arrow)" strokeDasharray="4 3" />

              {/* API */}
              <rect x="278" y="70" width="160" height="75" rx="12" fill="url(#g-emerald)" stroke="#10b981" strokeOpacity="0.4" />
              <text x="358" y="95" textAnchor="middle" fill="#6ee7b7" fontSize="13" fontWeight="700">API</text>
              <text x="358" y="112" textAnchor="middle" fill="white" fillOpacity="0.4" fontSize="9">FastAPI · GKE</text>
              <text x="358" y="126" textAnchor="middle" fill="white" fillOpacity="0.4" fontSize="9">Auth · Storage · Search</text>

              {/* Webhook Pipeline */}
              <rect x="278" y="240" width="160" height="70" rx="12" fill="url(#g-amber)" stroke="#f59e0b" strokeOpacity="0.3" />
              <text x="358" y="265" textAnchor="middle" fill="#fcd34d" fontSize="11" fontWeight="600">Webhook Pipeline</text>
              <text x="358" y="281" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">NATS · 40 typed agents</text>
              <text x="358" y="295" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">classify → analyze → embed</text>

              {/* Entity Extraction callout */}
              <rect x="278" y="340" width="160" height="50" rx="10" fill="url(#g-amber)" stroke="#f59e0b" strokeOpacity="0.2" strokeDasharray="4 2" />
              <text x="358" y="362" textAnchor="middle" fill="#fbbf24" fillOpacity="0.7" fontSize="9" fontWeight="600">Entity Extraction</text>
              <text x="358" y="378" textAnchor="middle" fill="white" fillOpacity="0.3" fontSize="8">person, org, product, location...</text>
              <path d="M 358 310 L 358 340" stroke="#f59e0b" strokeOpacity="0.3" strokeWidth="1" markerEnd="url(#arrow-amber)" />

              {/* Supabase */}
              <rect x="518" y="70" width="160" height="50" rx="12" fill="url(#g-cyan)" stroke="#06b6d4" strokeOpacity="0.3" />
              <text x="598" y="90" textAnchor="middle" fill="#67e8f9" fontSize="11" fontWeight="600">Supabase Postgres</text>
              <text x="598" y="105" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">metadata, memories, blobs</text>

              {/* Postgres Graph */}
              <rect x="518" y="135" width="160" height="45" rx="10" fill="url(#g-cyan)" stroke="#06b6d4" strokeOpacity="0.2" />
              <text x="598" y="155" textAnchor="middle" fill="#67e8f9" fillOpacity="0.8" fontSize="10" fontWeight="500">Postgres Graph</text>
              <text x="598" y="169" textAnchor="middle" fill="white" fillOpacity="0.3" fontSize="8">entities · relationships</text>

              {/* pgvector */}
              <rect x="518" y="195" width="160" height="55" rx="12" fill="url(#g-sky)" stroke="#0ea5e9" strokeOpacity="0.3" />
              <text x="598" y="216" textAnchor="middle" fill="#7dd3fc" fontSize="11" fontWeight="600">pgvector + BM25</text>
              <text x="598" y="232" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">embeddings · tsvector · cosine</text>
              <text x="598" y="243" textAnchor="middle" fill="white" fillOpacity="0.30" fontSize="8">hybrid RRF search</text>

              {/* GCS */}
              <rect x="518" y="285" width="160" height="50" rx="12" fill="url(#g-cyan)" stroke="#06b6d4" strokeOpacity="0.2" />
              <text x="598" y="306" textAnchor="middle" fill="#67e8f9" fillOpacity="0.7" fontSize="11" fontWeight="500">GCS</text>
              <text x="598" y="321" textAnchor="middle" fill="white" fillOpacity="0.30" fontSize="9">raw binary data</text>

              {/* Neo4j — highlighted as new */}
              <rect x="518" y="390" width="160" height="70" rx="12" fill="url(#g-amber)" stroke="#f59e0b" strokeOpacity="0.5" strokeWidth="1.5" filter="url(#glow)" />
              <text x="598" y="414" textAnchor="middle" fill="#fcd34d" fontSize="12" fontWeight="700">Neo4j</text>
              <text x="598" y="430" textAnchor="middle" fill="#fbbf24" fillOpacity="0.7" fontSize="9" fontWeight="500">Graphiti Knowledge Graph</text>
              <text x="598" y="446" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="8">temporal facts · BFS · episodes</text>
              {/* NEW badge */}
              <rect x="648" y="393" width="28" height="14" rx="7" fill="#f59e0b" fillOpacity="0.3" />
              <text x="662" y="403" textAnchor="middle" fill="#fbbf24" fontSize="7" fontWeight="700">NEW</text>

              {/* Search Engine */}
              <rect x="758" y="90" width="164" height="105" rx="14" fill="url(#g-fuchsia)" stroke="#d946ef" strokeOpacity="0.4" strokeWidth="1.5" />
              <text x="840" y="114" textAnchor="middle" fill="#f0abfc" fontSize="12" fontWeight="700">Multi-Signal Search</text>
              <text x="840" y="132" textAnchor="middle" fill="white" fillOpacity="0.45" fontSize="9">vector · FTS · hybrid</text>
              <text x="840" y="146" textAnchor="middle" fill="white" fillOpacity="0.45" fontSize="9">graph · full</text>
              {/* Mode pills */}
              <rect x="774" y="156" width="44" height="16" rx="8" fill="#8b5cf6" fillOpacity="0.2" />
              <text x="796" y="167" textAnchor="middle" fill="#c4b5fd" fontSize="7" fontWeight="600">cosine</text>
              <rect x="824" y="156" width="36" height="16" rx="8" fill="#0ea5e9" fillOpacity="0.2" />
              <text x="842" y="167" textAnchor="middle" fill="#7dd3fc" fontSize="7" fontWeight="600">BM25</text>
              <rect x="866" y="156" width="40" height="16" rx="8" fill="#f59e0b" fillOpacity="0.2" />
              <text x="886" y="167" textAnchor="middle" fill="#fbbf24" fontSize="7" fontWeight="600">graph</text>
              <rect x="774" y="175" width="132" height="14" rx="7" fill="white" fillOpacity="0.03" />
              <text x="840" y="185" textAnchor="middle" fill="white" fillOpacity="0.25" fontSize="7">Reciprocal Rank Fusion</text>

              {/* Reranker */}
              <rect x="768" y="260" width="144" height="55" rx="12" fill="url(#g-violet)" stroke="#8b5cf6" strokeOpacity="0.3" />
              <text x="840" y="282" textAnchor="middle" fill="#c4b5fd" fontSize="11" fontWeight="600">Reranker</text>
              <text x="840" y="298" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">RRF · MMR · cross-encoder</text>

              {/* RAG Chat */}
              <rect x="768" y="375" width="144" height="65" rx="12" fill="url(#g-emerald)" stroke="#10b981" strokeOpacity="0.3" />
              <text x="840" y="398" textAnchor="middle" fill="#6ee7b7" fontSize="11" fontWeight="600">RAG Chat</text>
              <text x="840" y="414" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">conversational answers</text>
              <text x="840" y="428" textAnchor="middle" fill="white" fillOpacity="0.35" fontSize="9">with [1][2] citations</text>

              {/* Temporal badge on search */}
              <rect x="768" y="455" width="144" height="40" rx="10" fill="url(#g-amber)" stroke="#f59e0b" strokeOpacity="0.2" strokeDasharray="4 2" />
              <text x="840" y="472" textAnchor="middle" fill="#fbbf24" fillOpacity="0.7" fontSize="9" fontWeight="600">Temporal Queries</text>
              <text x="840" y="486" textAnchor="middle" fill="white" fillOpacity="0.3" fontSize="8">point-in-time fact retrieval</text>
              <path d="M 840 440 L 840 455" stroke="#f59e0b" strokeOpacity="0.3" strokeWidth="1" markerEnd="url(#arrow-amber)" />
            </svg>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {CONCEPTS.map(({ title, desc, icon: Icon }) => (
              <div key={title} className="glass-card rounded-xl p-5">
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center">
                    <Icon className="w-4 h-4 text-primary-400" />
                  </div>
                  <h4 className="text-sm font-semibold text-white">{title}</h4>
                </div>
                <p className="text-xs text-white/50 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Platform Guide ────────────────────────────────────────────────── */}
      {activeSection === 'platform' && (
        <div className="space-y-4 animate-in">
          <div className="glass-card rounded-2xl p-6 mb-2">
            <h3 className="text-lg font-semibold gradient-text mb-2">Platform Guide</h3>
            <p className="text-xs text-white/50">
              A comprehensive guide to every tab and feature in the Mem-Dog UI.
            </p>
          </div>
          {PLATFORM_TABS.map(({ title, icon: Icon, desc, features }) => (
            <div key={title} className="glass-card rounded-2xl p-5">
              <div className="flex items-center gap-2.5 mb-2">
                <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center">
                  <Icon className="w-4 h-4 text-primary-400" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-white">{title}</h4>
                  <p className="text-[11px] text-white/40">{desc}</p>
                </div>
              </div>
              <ul className="space-y-1.5 mt-3">
                {features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-white/50">
                    <ChevronRight className="w-3 h-3 text-primary-400/60 mt-0.5 flex-shrink-0" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {/* ── API Reference ─────────────────────────────────────────────────── */}
      {activeSection === 'api' && (
        <div className="space-y-3 animate-in">
          <div className="glass-card rounded-2xl p-6 mb-2">
            <h3 className="text-lg font-semibold gradient-text mb-2">API Reference</h3>
            <p className="text-xs text-white/50">
              {API_GROUPS.reduce((sum, g) => sum + g.endpoints.length, 0)} endpoints across {API_GROUPS.length} groups.
              Click a group to expand, then click any endpoint for details.
            </p>
            <div className="flex items-center gap-3 mt-3">
              {Object.entries(METHOD_COLORS).map(([method, cls]) => (
                <span key={method} className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono ${cls}`}>
                  {method}
                </span>
              ))}
            </div>
          </div>
          {API_GROUPS.map((group) => (
            <ApiGroupCard key={group.title} group={group} />
          ))}
        </div>
      )}

      {/* ── FAQ ────────────────────────────────────────────────────────────── */}
      {activeSection === 'faq' && (
        <div className="space-y-3 animate-in">
          {FAQ_ITEMS.map(({ q, a }, i) => (
            <button
              key={i}
              onClick={() => setOpenFaq(openFaq === i ? null : i)}
              className="glass-card rounded-xl p-5 w-full text-left transition-all hover:bg-white/[0.04]"
            >
              <div className="flex items-center justify-between gap-3">
                <h4 className="text-sm font-medium text-white">{q}</h4>
                <ChevronRight className={`w-4 h-4 text-white/30 flex-shrink-0 transition-transform duration-200 ${openFaq === i ? 'rotate-90' : ''}`} />
              </div>
              {openFaq === i && (
                <p className="mt-3 text-xs text-white/50 leading-relaxed">{a}</p>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

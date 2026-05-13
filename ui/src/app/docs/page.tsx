'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  BookOpen, ArrowLeft, Database, Brain, Cpu, Search, Network, Webhook,
  Zap, Server, Globe, Flower2, Shield, GitBranch, Users, Tag, Eye,
  Layers, Settings, HardDrive, Upload, Box, Key, ChevronRight,
  ChevronDown, MessageSquare, FileText, Wrench, BarChart3, Link2,
  ArrowRight, Code2, Terminal, Package,
} from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────

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

// ── Get Started Cards ─────────────────────────────────────────────────────────

const GET_STARTED = [
  {
    icon: Database,
    title: 'Ingest your first data',
    desc: 'Store text, files, images, or any content via the API or UI.',
    hash: 'api-data',
  },
  {
    icon: Search,
    title: 'Search & query',
    desc: '5 search modes with reranking and temporal knowledge graph.',
    hash: 'api-ai-query',
  },
  {
    icon: Webhook,
    title: 'Connect an app',
    desc: '300+ integrations via OAuth with automatic token refresh.',
    hash: 'api-integrations',
  },
  {
    icon: MessageSquare,
    title: 'RAG chat with citations',
    desc: 'Conversational AI over your data with inline source references.',
    hash: 'api-ai-query',
  },
];

// ── Core Concepts ─────────────────────────────────────────────────────────────

const CONCEPTS = [
  {
    icon: Database,
    title: 'Data Items',
    desc: 'Universal storage for 30+ formats with automatic versioning, tagging, and per-item access control. Every piece of content gets a ULID-based ID (data_<ulid>).',
  },
  {
    icon: Brain,
    title: 'Memories',
    desc: '10 memory types across 4 categories with configurable TTLs. From short-term conversations (1h) to permanent organizational knowledge.',
  },
  {
    icon: Cpu,
    title: 'AI Pipeline',
    desc: '42 specialist agents process data through 6-layer type detection. Five model tiers from 4B to omni handle everything from text to video.',
  },
  {
    icon: Network,
    title: 'Knowledge Graph',
    desc: 'Dual-layer: Postgres entities (always on) + Graphiti/Neo4j temporal facts. Query what was true at any point in time.',
  },
  {
    icon: Search,
    title: '5 Search Modes',
    desc: 'Vector, full-text, hybrid, graph, and full — with RRF, MMR, and cross-encoder reranking. Temporal filtering for point-in-time queries.',
  },
  {
    icon: Globe,
    title: '300+ Integrations',
    desc: 'Nango-powered OAuth2 and API key connections across 15 categories. Per-user webhook endpoints (whk_<ulid>) with HMAC signing.',
  },
  {
    icon: Flower2,
    title: 'Model Garden',
    desc: '10+ AI providers (OpenAI, Anthropic, Gemini, Ollama, etc.) with encrypted API keys, per-user routing, and fallback chains.',
  },
  {
    icon: Server,
    title: 'MCP Server',
    desc: '8 tools over SSE for Claude Desktop, Cursor, and MCP-compatible agents. Per-user auth via API keys.',
  },
];

// ── SDKs ──────────────────────────────────────────────────────────────────────

const SDKS = [
  { lang: 'Python',     icon: Terminal,  desc: '70+ methods via httpx. Mirrors the full REST API.', install: 'pip install mem-dog-client' },
  { lang: 'TypeScript',  icon: Code2,     desc: 'Native fetch, zero dependencies. Full type safety.', install: 'npm install @mem-dog/sdk' },
  { lang: 'Go',         icon: Package,   desc: 'stdlib only. Idiomatic Go with context support.', install: 'go get github.com/mem-dog/sdk-go' },
  { lang: 'Rust',       icon: Package,   desc: 'Async tokio runtime. Fully typed with serde.', install: 'cargo add mem-dog-sdk' },
  { lang: 'Ruby',       icon: Package,   desc: 'Faraday-based client with Ruby conventions.', install: 'gem install mem_dog' },
];

// ── API Reference ─────────────────────────────────────────────────────────────

const API_GROUPS: ApiGroup[] = [
  {
    title: 'Data',
    icon: Database,
    endpoints: [
      { method: 'POST', path: '/api/v1/data', desc: 'Ingest a new data item', params: 'Body: content, mime_type, tags, session_id', response: '201: { id, mime_type, size, created_at }' },
      { method: 'GET', path: '/api/v1/data', desc: 'List all data items with pagination', params: 'Query: page, page_size, tag, mime_type, sort_by', response: '200: { items, total, page }' },
      { method: 'GET', path: '/api/v1/data/{id}', desc: 'Get a single data item', params: 'Path: id', response: '200: { id, content, mime_type, tags, metadata }' },
      { method: 'PUT', path: '/api/v1/data/{id}', desc: 'Update (creates new version)', params: 'Path: id; Body: content', response: '200: { id, version, updated_at }' },
      { method: 'DELETE', path: '/api/v1/data/{id}', desc: 'Delete item and all versions', params: 'Path: id', response: '204' },
    ],
  },
  {
    title: 'Memories',
    icon: Brain,
    endpoints: [
      { method: 'POST', path: '/api/v1/memories', desc: 'Create a new memory', params: 'Body: type, sub_type, content, data_ids', response: '201: { id, type, created_at }' },
      { method: 'GET', path: '/api/v1/memories', desc: 'List with filtering', params: 'Query: type, sub_type, page, page_size', response: '200: { items, total }' },
      { method: 'GET', path: '/api/v1/memories/{id}', desc: 'Get memory by ID', params: 'Path: id', response: '200: { id, type, content, entries, data_ids }' },
      { method: 'PUT', path: '/api/v1/memories/{id}', desc: 'Update a memory', params: 'Path: id; Body: content', response: '200: { id, updated_at }' },
      { method: 'DELETE', path: '/api/v1/memories/{id}', desc: 'Delete a memory', params: 'Path: id', response: '204' },
      { method: 'POST', path: '/api/v1/memories/{id}/data', desc: 'Associate data items', params: 'Body: { data_ids }', response: '200: { id, data_ids }' },
    ],
  },
  {
    title: 'AI Query',
    icon: Search,
    endpoints: [
      { method: 'POST', path: '/api/v1/ai/query/semantic', desc: 'Multi-mode search (vector, fts, hybrid, graph, full)', params: 'Body: query, search_mode, max_results, rerank, temporal', response: '200: { records, answer, latency_ms }' },
      { method: 'POST', path: '/api/v1/ai/query/chat', desc: 'Conversational RAG with citations', params: 'Body: message, history, search_mode, rerank', response: '200: { answer, citations, model }' },
      { method: 'GET', path: '/api/v1/graph/facts', desc: 'Query temporal facts', params: 'Query: q, entity_id, at (ISO datetime)', response: '200: [{ fact, valid_at, invalid_at }]' },
    ],
  },
  {
    title: 'AI Config',
    icon: Settings,
    endpoints: [
      { method: 'GET', path: '/api/v1/ai/config', desc: 'Get AI configuration', response: '200: { auto_process, generate_embeddings }' },
      { method: 'PUT', path: '/api/v1/ai/config', desc: 'Update AI config', params: 'Body: { auto_process, generate_embeddings }', response: '200: { updated_at }' },
      { method: 'GET', path: '/api/v1/ai/routing', desc: 'Get smart routing rules', response: '200: { rules }' },
      { method: 'PUT', path: '/api/v1/ai/routing', desc: 'Update routing rules', params: 'Body: { rules }', response: '200: { updated_at }' },
      { method: 'POST', path: '/api/v1/ai/process/{data_id}', desc: 'Trigger AI processing', params: 'Path: data_id', response: '202: { task_id }' },
    ],
  },
  {
    title: 'Viewpoints',
    icon: Eye,
    endpoints: [
      { method: 'GET', path: '/api/v1/viewpoints', desc: 'List viewpoints', params: 'Query: data_id, agent_type, page', response: '200: { items, total }' },
      { method: 'GET', path: '/api/v1/viewpoints/{id}', desc: 'Get viewpoint', params: 'Path: id', response: '200: { id, data_id, agent_type, content }' },
      { method: 'DELETE', path: '/api/v1/viewpoints/{id}', desc: 'Delete viewpoint', params: 'Path: id', response: '204' },
    ],
  },
  {
    title: 'Embeddings',
    icon: Layers,
    endpoints: [
      { method: 'GET', path: '/api/v1/embeddings', desc: 'List embeddings', params: 'Query: data_id, model, page', response: '200: { items, total }' },
      { method: 'POST', path: '/api/v1/embeddings/regenerate/{data_id}', desc: 'Regenerate embedding', params: 'Path: data_id', response: '202: { task_id }' },
      { method: 'DELETE', path: '/api/v1/embeddings/{id}', desc: 'Delete embedding', params: 'Path: id', response: '204' },
    ],
  },
  {
    title: 'Users',
    icon: Users,
    endpoints: [
      { method: 'POST', path: '/api/v1/users', desc: 'Create user', params: 'Body: username, display_name, email', response: '201: { id, username }' },
      { method: 'GET', path: '/api/v1/users/{id}', desc: 'Get user', params: 'Path: id', response: '200: { id, username, display_name }' },
      { method: 'POST', path: '/api/v1/users/{id}/api-keys', desc: 'Generate API key', params: 'Body: { name }', response: '201: { key, name }' },
    ],
  },
  {
    title: 'Organizations',
    icon: Globe,
    endpoints: [
      { method: 'POST', path: '/api/v1/organizations', desc: 'Create org', params: 'Body: { name, display_name }', response: '201: { org_id, name }' },
      { method: 'GET', path: '/api/v1/organizations', desc: 'List user orgs', response: '200: { organizations }' },
      { method: 'POST', path: '/api/v1/organizations/{org_id}/projects', desc: 'Create project', params: 'Body: { name }', response: '201: { project_id }' },
      { method: 'POST', path: '/api/v1/organizations/{org_id}/members', desc: 'Add member', params: 'Body: { user_id, role }', response: '201' },
    ],
  },
  {
    title: 'Integrations',
    icon: Link2,
    endpoints: [
      { method: 'GET', path: '/api/v1/integrations/providers', desc: 'List 300+ providers', params: 'Query: category, search', response: '200: { providers }' },
      { method: 'POST', path: '/api/v1/integrations/connections', desc: 'Create connection', params: 'Body: { provider_id, credentials }', response: '201: { id, status }' },
      { method: 'GET', path: '/api/v1/integrations/oauth/{provider}/authorize', desc: 'Get OAuth URL', response: '200: { auth_url }' },
      { method: 'POST', path: '/api/v1/integrations/proxy', desc: 'Proxy API request', params: 'Body: { connection_id, method, path }', response: '200: { data }' },
    ],
  },
  {
    title: 'Webhooks',
    icon: Webhook,
    endpoints: [
      { method: 'POST', path: '/api/v1/webhooks', desc: 'Create webhook endpoint', params: 'Body: { channel_type, name }', response: '201: { webhook_id, url }' },
      { method: 'GET', path: '/api/v1/webhooks', desc: 'List user webhooks', response: '200: [{ webhook_id, url, status }]' },
      { method: 'POST', path: '/api/v1/webhooks/{id}/rotate-secret', desc: 'Rotate signing secret', response: '200: { secret }' },
      { method: 'GET', path: '/api/v1/webhooks/{id}/stats', desc: 'Webhook stats', params: 'Query: period', response: '200: { total, success_rate }' },
    ],
  },
  {
    title: 'Model Garden',
    icon: Flower2,
    endpoints: [
      { method: 'GET', path: '/api/v1/ai/provider-registry', desc: 'Provider catalog (11 providers)', response: '200: { providers }' },
      { method: 'POST', path: '/api/v1/ai/users/{uid}/engines', desc: 'Add provider config', params: 'Body: { engine_type, api_key }', response: '201: { engine_id }' },
      { method: 'POST', path: '/api/v1/ai/users/{uid}/engines/{eid}/test', desc: 'Test connectivity', response: '200: { ok, latency_ms }' },
      { method: 'POST', path: '/api/v1/ai/users/{uid}/engines/{eid}/discover-models', desc: 'Discover models', response: '200: { models, count }' },
    ],
  },
  {
    title: 'Statistics',
    icon: BarChart3,
    endpoints: [
      { method: 'GET', path: '/api/v1/stats', desc: 'System statistics', response: '200: { data_count, memory_count, storage_bytes }' },
      { method: 'GET', path: '/api/v1/stats/tokens', desc: 'Token usage', params: 'Query: period', response: '200: { total, by_model, cost }' },
      { method: 'GET', path: '/api/v1/stats/channels', desc: 'Channel activity', response: '200: { by_channel, total_messages }' },
    ],
  },
  {
    title: 'Tags & ACLs',
    icon: Tag,
    endpoints: [
      { method: 'PUT', path: '/api/v1/data/{id}/tags', desc: 'Set tags', params: 'Body: { tags }', response: '200: { id, tags }' },
      { method: 'GET', path: '/api/v1/tags', desc: 'List all tags', response: '200: { tags: [{ name, count }] }' },
      { method: 'PUT', path: '/api/v1/data/{id}/acl', desc: 'Set access control', params: 'Body: { readers, writers }', response: '200: { id, acl }' },
    ],
  },
  {
    title: 'Versions',
    icon: GitBranch,
    endpoints: [
      { method: 'GET', path: '/api/v1/data/{id}/versions', desc: 'List versions', response: '200: { versions }' },
      { method: 'GET', path: '/api/v1/data/{id}/versions/{v}', desc: 'Get specific version', response: '200: { id, version, content }' },
    ],
  },
  {
    title: 'Ingest',
    icon: Upload,
    endpoints: [
      { method: 'POST', path: '/api/v1/ingest', desc: 'Universal ingest (webhook gateway)', params: 'Body: UniversalEnvelope', response: '202: { id, status: "queued" }' },
    ],
  },
];

// ── FAQ ───────────────────────────────────────────────────────────────────────

const FAQ = [
  { q: 'What data formats are supported?', a: '30+ formats: JSON, text, Markdown, HTML, images (PNG, JPEG, GIF, WebP, SVG), PDFs, audio (MP3, WAV), video (MP4, WebM), code files, CSV, XML, and binary blobs. The pipeline auto-detects types via 6-layer detection.' },
  { q: 'How does AI enrichment work?', a: 'Ingested data flows through a 42-agent NATS pipeline. Each agent specializes in a data type (text, image, code, medical, legal, etc.). They classify, extract entities, summarize, generate viewpoints, and create embeddings — all asynchronously.' },
  { q: 'What are the memory types?', a: 'Short-term: conversation (1h), timeline (7d), session (24h), tracing (3d). Long-term (no expiry): user, organizational, factual, episodic, semantic, custom. All support TTL overrides and access levels (private/shared/public/restricted).' },
  { q: 'How do search modes differ?', a: 'Vector: cosine similarity. FTS: BM25 keyword. Hybrid: vector + BM25 via RRF. Graph: Graphiti BFS on Neo4j. Full: all signals merged. Each supports 4 reranking strategies and temporal point-in-time filtering.' },
  { q: 'How do I authenticate?', a: 'JWT from Supabase (sub claim) or per-user API keys (md_* prefix). Generate keys via POST /api/v1/users/{id}/api-keys. Pass via Authorization: Bearer header or X-API-Key header.' },
  { q: 'Can I run it locally?', a: 'Yes. docker compose up starts the full stack: UI (:3000), API (:8080), Gateway (:8070), Neo4j, Redis, PostgreSQL + pgvector, and 3 Ollama instances. No cloud credentials needed.' },
  { q: 'What AI models are used?', a: '5 tiers: small (Gemma3:4b), medium (12b), large (27b), multimodal (Qwen3-VL), omni (Qwen3.5). Self-hosted via Ollama with fallback chains to Ollama Cloud and Gemini.' },
  { q: 'How do integrations work?', a: 'Powered by Nango (self-hosted). OAuth2 and API key auth with automatic token refresh and AES-256-GCM encryption. Per-user webhook endpoints (whk_<ulid>) for inbound data.' },
];

// ── Method badge colors ───────────────────────────────────────────────────────

const METHOD_COLORS: Record<string, string> = {
  GET:    'text-emerald-400 bg-emerald-400/10',
  POST:   'text-blue-400 bg-blue-400/10',
  PUT:    'text-amber-400 bg-amber-400/10',
  PATCH:  'text-purple-400 bg-purple-400/10',
  DELETE: 'text-red-400 bg-red-400/10',
};

// ── Sub-components ────────────────────────────────────────────────────────────

function EndpointRow({ ep }: { ep: Endpoint }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.04] transition-colors w-full text-left group"
      >
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded font-mono flex-shrink-0 ${METHOD_COLORS[ep.method] || 'text-white/60'}`}>
          {ep.method}
        </span>
        <code className="text-xs text-white/70 font-mono">{ep.path}</code>
        <span className="text-xs text-white/30 ml-auto hidden sm:inline truncate max-w-[240px]">{ep.desc}</span>
        <ChevronRight className={`w-3 h-3 text-white/20 flex-shrink-0 transition-transform ${open ? 'rotate-90' : ''}`} />
      </button>
      {open && (
        <div className="ml-4 mt-1 mb-2 px-3 py-2.5 rounded-lg bg-white/[0.02] border border-white/[0.06] space-y-1.5">
          <p className="text-xs text-white/50">{ep.desc}</p>
          {ep.params && (
            <div>
              <span className="text-[10px] text-white/25 uppercase tracking-wider">Parameters</span>
              <p className="text-xs text-white/40 font-mono mt-0.5">{ep.params}</p>
            </div>
          )}
          {ep.response && (
            <div>
              <span className="text-[10px] text-white/25 uppercase tracking-wider">Response</span>
              <p className="text-xs text-white/40 font-mono mt-0.5">{ep.response}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ApiGroupCard({ group, defaultOpen }: { group: ApiGroup; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  const Icon = group.icon;
  return (
    <div id={`api-${group.title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`} className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-3 w-full px-5 py-4 text-left hover:bg-white/[0.02] transition-colors"
      >
        <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0">
          <Icon className="w-4 h-4 text-primary-400" />
        </div>
        <h3 className="text-sm font-semibold text-white">{group.title}</h3>
        <span className="text-[10px] text-white/25 font-mono">{group.endpoints.length} endpoints</span>
        <ChevronDown className={`w-4 h-4 text-white/25 ml-auto transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="px-5 pb-4 space-y-1">
          {group.endpoints.map((ep) => (
            <EndpointRow key={`${ep.method}-${ep.path}`} ep={ep} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Docs() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <main className="min-h-screen">
      {/* ── Sticky Header ────────────────────────────────────────────────── */}
      <div className="sticky top-0 z-30 border-b border-white/[0.06] bg-slate-950/80 backdrop-blur-xl">
        <div className="max-w-4xl mx-auto px-5 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-1.5 text-xs text-white/40 hover:text-white/70 transition-colors">
              <ArrowLeft className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Mem-Dog</span>
            </Link>
            <span className="text-white/10">/</span>
            <div className="flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-primary-400" />
              <span className="text-sm font-semibold text-white">Documentation</span>
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <a href="#get-started" className="text-white/40 hover:text-white/70 transition-colors">Get Started</a>
            <a href="#concepts" className="text-white/40 hover:text-white/70 transition-colors hidden sm:inline">Concepts</a>
            <a href="#sdks" className="text-white/40 hover:text-white/70 transition-colors hidden sm:inline">SDKs</a>
            <a href="#api" className="text-white/40 hover:text-white/70 transition-colors">API</a>
            <a href="#faq" className="text-white/40 hover:text-white/70 transition-colors">FAQ</a>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-5 py-10 space-y-16">

        {/* ── Hero ──────────────────────────────────────────────────────────── */}
        <section className="space-y-4">
          <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
            Mem-Dog Documentation
          </h1>
          <p className="text-base text-white/50 leading-relaxed max-w-2xl">
            <span className="text-white/80 font-medium">Mem-Dog</span> is the private AI memory platform.
            Ingest data from 300+ apps, enrich it with a 42-agent AI pipeline, and query it
            with 5 search modes powered by a temporal knowledge graph.
          </p>
          <div className="flex flex-wrap gap-3 text-xs text-white/40 pt-1">
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06]">
              <Database className="w-3 h-3" /> 70+ API endpoints
            </span>
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06]">
              <Code2 className="w-3 h-3" /> 5 SDKs
            </span>
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06]">
              <Webhook className="w-3 h-3" /> 300+ integrations
            </span>
            <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06]">
              <Server className="w-3 h-3" /> MCP server
            </span>
          </div>
        </section>

        {/* ── Get Started ──────────────────────────────────────────────────── */}
        <section id="get-started" className="space-y-5">
          <h2 className="text-lg font-semibold text-white">Get Started</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {GET_STARTED.map((item) => {
              const Icon = item.icon;
              return (
                <a
                  key={item.title}
                  href={`#${item.hash}`}
                  className="group flex items-start gap-4 p-5 rounded-xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/[0.12] transition-all"
                >
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500/20 to-accent-500/20 flex items-center justify-center flex-shrink-0 group-hover:from-primary-500/30 group-hover:to-accent-500/30 transition-colors">
                    <Icon className="w-5 h-5 text-primary-400" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <h3 className="text-sm font-semibold text-white">{item.title}</h3>
                      <ArrowRight className="w-3 h-3 text-white/20 group-hover:text-white/50 group-hover:translate-x-0.5 transition-all" />
                    </div>
                    <p className="text-xs text-white/40 mt-1 leading-relaxed">{item.desc}</p>
                  </div>
                </a>
              );
            })}
          </div>
        </section>

        {/* ── Quick Start ──────────────────────────────────────────────────── */}
        <section className="space-y-5">
          <h2 className="text-lg font-semibold text-white">Quick Start</h2>
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
            <div className="px-5 py-3 border-b border-white/[0.06] flex items-center gap-2">
              <Terminal className="w-4 h-4 text-white/30" />
              <span className="text-xs text-white/40 font-mono">Local development</span>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <p className="text-xs text-white/40 mb-2">Start the full stack (10 services):</p>
                <pre className="text-sm text-emerald-400 font-mono bg-black/30 rounded-lg px-4 py-3 overflow-x-auto">docker compose up</pre>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.04]">
                  <span className="text-white/30">UI</span>
                  <p className="text-white/60 font-mono mt-0.5">localhost:3000</p>
                </div>
                <div className="px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.04]">
                  <span className="text-white/30">API</span>
                  <p className="text-white/60 font-mono mt-0.5">localhost:8080</p>
                </div>
                <div className="px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.04]">
                  <span className="text-white/30">Gateway</span>
                  <p className="text-white/60 font-mono mt-0.5">localhost:8070</p>
                </div>
                <div className="px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.04]">
                  <span className="text-white/30">Neo4j</span>
                  <p className="text-white/60 font-mono mt-0.5">localhost:7474</p>
                </div>
              </div>
              <div>
                <p className="text-xs text-white/40 mb-2">Or ingest your first item via cURL:</p>
                <pre className="text-sm text-blue-400 font-mono bg-black/30 rounded-lg px-4 py-3 overflow-x-auto whitespace-pre">{`curl -X POST http://localhost:8080/api/v1/data \\
  -H "Content-Type: application/json" \\
  -d '{"content": "Hello, Mem-Dog!", "mime_type": "text/plain"}'`}</pre>
              </div>
            </div>
          </div>
        </section>

        {/* ── Core Concepts ────────────────────────────────────────────────── */}
        <section id="concepts" className="space-y-5">
          <h2 className="text-lg font-semibold text-white">Core Concepts</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {CONCEPTS.map((c) => {
              const Icon = c.icon;
              return (
                <div
                  key={c.title}
                  className="p-5 rounded-xl border border-white/[0.06] bg-white/[0.02] space-y-2.5"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0">
                      <Icon className="w-4 h-4 text-primary-400" />
                    </div>
                    <h3 className="text-sm font-semibold text-white">{c.title}</h3>
                  </div>
                  <p className="text-xs text-white/40 leading-relaxed">{c.desc}</p>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── SDKs ─────────────────────────────────────────────────────────── */}
        <section id="sdks" className="space-y-5">
          <h2 className="text-lg font-semibold text-white">SDKs</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {SDKS.map((sdk) => {
              const Icon = sdk.icon;
              return (
                <div
                  key={sdk.lang}
                  className="p-5 rounded-xl border border-white/[0.06] bg-white/[0.02] space-y-3"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center">
                      <Icon className="w-4 h-4 text-accent-400" />
                    </div>
                    <h3 className="text-sm font-semibold text-white">{sdk.lang}</h3>
                  </div>
                  <p className="text-xs text-white/40 leading-relaxed">{sdk.desc}</p>
                  <code className="block text-[11px] text-white/30 font-mono bg-black/20 rounded-md px-3 py-1.5 truncate">
                    {sdk.install}
                  </code>
                </div>
              );
            })}
          </div>
        </section>

        {/* ── API Reference ────────────────────────────────────────────────── */}
        <section id="api" className="space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">API Reference</h2>
            <span className="text-xs text-white/25 font-mono">
              {API_GROUPS.reduce((sum, g) => sum + g.endpoints.length, 0)} endpoints
            </span>
          </div>
          <p className="text-xs text-white/40">
            Base URL: <code className="text-white/50 bg-white/[0.04] px-1.5 py-0.5 rounded">http://localhost:8080</code> &mdash;
            Auth: <code className="text-white/50 bg-white/[0.04] px-1.5 py-0.5 rounded">X-API-Key: md_...</code> or
            <code className="text-white/50 bg-white/[0.04] px-1.5 py-0.5 rounded ml-1">Authorization: Bearer &lt;jwt&gt;</code>
          </p>
          <div className="space-y-2">
            {API_GROUPS.map((group) => (
              <ApiGroupCard key={group.title} group={group} />
            ))}
          </div>
        </section>

        {/* ── FAQ ──────────────────────────────────────────────────────────── */}
        <section id="faq" className="space-y-5">
          <h2 className="text-lg font-semibold text-white">FAQ</h2>
          <div className="space-y-2">
            {FAQ.map((item, i) => (
              <div key={i} className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="flex items-center justify-between w-full px-5 py-4 text-left hover:bg-white/[0.02] transition-colors"
                >
                  <span className="text-sm text-white/80 font-medium pr-4">{item.q}</span>
                  <ChevronDown className={`w-4 h-4 text-white/25 flex-shrink-0 transition-transform ${openFaq === i ? 'rotate-180' : ''}`} />
                </button>
                {openFaq === i && (
                  <div className="px-5 pb-4">
                    <p className="text-xs text-white/40 leading-relaxed">{item.a}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* ── Footer ───────────────────────────────────────────────────────── */}
        <footer className="border-t border-white/[0.06] pt-6 pb-10 flex items-center justify-between text-xs text-white/20">
          <span>Mem-Dog &middot; Apache 2.0</span>
          <div className="flex items-center gap-4">
            <Link href="/" className="hover:text-white/40 transition-colors">App</Link>
            <a href="https://github.com/BuildGeekAI/mem-dog" className="hover:text-white/40 transition-colors">GitHub</a>
          </div>
        </footer>
      </div>
    </main>
  );
}

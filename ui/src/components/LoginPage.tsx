'use client';

import { useState, useEffect, useRef } from 'react';
import { Mail, Lock, Loader2, ChevronRight, Database, Brain, Zap, Search, Shield, Activity, Terminal, Clock, GitBranch, Cpu, Globe, MessageCircle, Users, FileSearch, ShieldCheck, Radio, Bot, FlaskConical, Upload, Webhook, Server, Sparkles, Wrench, SlidersHorizontal, Flower2, ArrowRight, Cog, Network, Code2, Puzzle, Archive, Check, X, Minus, Briefcase, GraduationCap, Heart, Scale, Camera, Newspaper, Plane, Building2, Mic, BookOpen } from 'lucide-react';
import { motion, AnimatePresence, useInView } from 'framer-motion';
import { useAuth } from '@/lib/auth-context';
import { isReadOnly } from '@/lib/read-only';

/* ─── Data ─── */

const ROTATING_PHRASES = [
  'Your AI. Your hardware. Your rules.',
  'Local models. Real-time speed. Zero data leakage.',
  '40 agents that never phone home.',
  'Enterprise-grade AI on a Mac Mini.',
  'Private by architecture, not by promise.',
];

const CAPABILITIES = [
  { icon: Database, title: 'Versioned Storage', desc: 'Every mutation tracked. Full version history with diffs, rollback, and audit trail out of the box.' },
  { icon: Brain, title: 'AI Enrichment', desc: '40+ specialized agents classify, analyze, and generate embeddings automatically on ingest.' },
  { icon: Globe, title: '300+ Apps', desc: 'Powered by Nango — connect to Slack, WhatsApp, Salesforce, GitHub, and 300+ more services with automatic OAuth token refresh. Per-user webhook endpoints (whk_<ulid>) for inbound channels.' },
  { icon: Cpu, title: 'DigiMe Agent', desc: 'OpenClaw-powered AI agent that lives in your channels — query, search, and ingest data through natural conversation with the mem-dog RAG system.' },
  { icon: Zap, title: 'Real-Time Pipeline', desc: 'NATS-powered streaming with per-user webhook endpoints (whk_<ulid>), 6-layer data classification, and tiered LLM routing (4b → 27b → multimodal).' },
  { icon: Search, title: 'Semantic Search', desc: 'pgvector embeddings with cosine similarity. RAG chat with inline citations across all your data.' },
  { icon: Shield, title: 'Secure by Default', desc: 'Per-user scoping, AES-256 encrypted credentials (Nango + Fernet), per-item ACLs, and full OpenTelemetry observability.' },
];

const INFRA_STATS = [
  { value: '300+', label: 'Apps', sub: '15 categories' },
  { value: '40+', label: 'AI Agents', sub: '6-layer routing pipeline' },
  { value: '5', label: 'Model Tiers', sub: 'Small to multimodal' },
  { value: '10', label: 'Memory Types', sub: 'Timeline to semantic' },
  { value: '70+', label: 'API Endpoints', sub: 'Full REST coverage' },
];

const USE_CASES = [
  { icon: Brain, title: 'Personal Knowledge Base', points: 'Capture from WhatsApp, email, Slack. Semantic search across everything. Never lose a conversation or idea.' },
  { icon: Users, title: 'Team Memory', points: 'Shared org memory across channels. Auto-classify meetings, decisions, action items. Queryable by anyone.' },
  { icon: MessageCircle, title: 'Customer Intelligence', points: 'Ingest support tickets, CRM, chat logs. AI extracts sentiment and trends. 300+ app connections via Nango.' },
  { icon: FileSearch, title: 'Research & Analysis', points: 'Ingest PDFs, papers, web pages, datasets. AI viewpoints and summaries. Semantic connections across sources.' },
  { icon: ShieldCheck, title: 'Compliance & Audit', points: 'Every mutation versioned. OpenTelemetry tracing. Per-item ACLs. Immutable audit trail.' },
  { icon: Radio, title: 'IoT & Sensor Data', points: 'GPS, biometric, weather, industrial sensors. Specialized agents for time-series and geospatial.' },
  { icon: Scale, title: 'Legal & Contract Intelligence', points: 'Ingest contracts, NDAs, legal briefs. AI extracts clauses, obligations, deadlines. Temporal graph tracks amendments over time.' },
  { icon: Heart, title: 'Healthcare & Clinical Notes', points: 'Process medical records, imaging reports, lab results. DICOM-aware agents. Knowledge graph links patients, conditions, treatments.' },
  { icon: GraduationCap, title: 'Education & Training', points: 'Ingest lectures, textbooks, course materials. AI generates study guides and flashcards. Students query their learning history.' },
  { icon: Briefcase, title: 'Sales Enablement', points: 'Connect Salesforce, HubSpot, email. AI summarizes deal history, extracts action items. Search across all customer touchpoints.' },
  { icon: Newspaper, title: 'Media Monitoring', points: 'RSS feeds, social media, news APIs. Real-time sentiment analysis. Track brand mentions across channels with temporal trends.' },
  { icon: Building2, title: 'Real Estate & Property', points: 'Ingest listings, inspections, contracts. AI extracts property details, comparables. Knowledge graph links properties, agents, transactions.' },
  { icon: Mic, title: 'Meeting Intelligence', points: 'Zoom, Teams, Google Meet recordings. AI transcribes, extracts decisions, action items. Searchable meeting memory across your org.' },
  { icon: Camera, title: 'Visual Asset Management', points: 'Ingest photos, videos, design files. Multimodal AI describes and tags visuals. Search images by description or concept.' },
  { icon: BookOpen, title: 'Knowledge Management', points: 'Connect Notion, Confluence, Google Docs. AI indexes and cross-references documentation. Ask questions across all your wikis.' },
  { icon: Plane, title: 'Travel & Logistics', points: 'Ingest itineraries, shipment data, GPS tracks. Geospatial agents plot routes. Temporal graph tracks delivery timelines and delays.' },
];

const AGENT_MESSAGES = [
  { role: 'user' as const, text: "What came out of last week's standup?" },
  { role: 'bot' as const, text: "Here's a summary from the 3 standups last week:\n\n\u2022 **Mon** \u2014 API rate-limiting merged, deploy scheduled for Wed\n\u2022 **Wed** \u2014 Deploy completed, 2 hotfixes pushed same day\n\u2022 **Fri** \u2014 Sprint retro: velocity up 15%, carried over 1 ticket", badges: ['1', '2', '3'] },
  { role: 'user' as const, text: 'Which ticket was carried over?' },
  { role: 'bot' as const, text: '**MEM-247** \u2014 "Add batch ingest endpoint." Blocked on schema review; moved to next sprint with high priority.' },
];

const AI_ENGINE_CARDS = [
  { icon: Zap, title: 'Smart Routing', desc: 'Automatically assigns the right model tier (4b → 12b → 27b → multimodal → omni) based on data type. Per-type overrides via Settings.' },
  { icon: SlidersHorizontal, title: 'Configurable Prompts', desc: 'Customize system prompts per agent type. Tune extraction rules, analysis depth, and output format for each of the 40+ AI agents.' },
  { icon: Wrench, title: 'Skills & Templates', desc: 'Define reusable AI skills and prompt templates. Attach skills to agents for specialized behavior like entity extraction or sentiment analysis.' },
  { icon: Sparkles, title: '5 Model Tiers', desc: 'Small (Gemma3:4b), Medium (12b), Large (27b), Multimodal (Qwen3-VL), and Omni (Qwen3.5). Fallback chains: Ollama Cloud → Gemini → self-hosted.' },
  { icon: Flower2, title: 'Model Garden', desc: 'Connect your own AI providers — OpenAI, Anthropic, Gemini, Ollama, and more. Encrypted API key storage, one-click connectivity tests, and automatic model discovery.' },
];

const TRUST_ITEMS = [
  { icon: Activity, title: 'Real-Time Processing', desc: 'NATS streaming with sub-second latency' },
  { icon: Shield, title: 'Encrypted at Rest', desc: 'Nango AES-256-GCM for integrations, Fernet for AI keys' },
  { icon: GitBranch, title: 'Open Architecture', desc: 'Pluggable storage, models, and agents' },
  { icon: Clock, title: 'OpenTelemetry Traces', desc: 'Distributed tracing with waterfall UI' },
];

const HOSTING_OPTIONS = [
  { icon: Terminal, title: 'Local Development', desc: 'Single command — docker compose up starts all 9 services. UI on :3000, API on :8080, gateway on :8070. Local filesystem storage, self-hosted Ollama for AI, NATS for streaming. Perfect for development and testing.', features: ['Docker Compose with hot-reload', 'Local filesystem storage backend', 'Self-hosted Ollama models', 'No cloud credentials needed'] },
  { icon: Globe, title: 'Google Cloud (GKE + Cloud Run)', desc: 'Production-grade deployment on GKE with Supabase (pgvector), Cloud Run for the UI, and a global L7 load balancer. Automated deploy scripts, Workload Identity, and encrypted secrets.', features: ['API + Pipeline on GKE', 'UI on Cloud Run', 'Supabase with pgvector', 'L7 Gateway with path-based routing'] },
  { icon: Server, title: 'Mac Mini Home Server', desc: 'Run the entire stack on a Mac Mini with Apple Silicon. GKE Autopilot or a local k3s cluster, self-hosted Ollama for on-device AI inference, and full control over your data — no cloud required.', features: ['Apple Silicon GPU for Ollama models', 'Single deploy script from terminal', 'Self-hosted Supabase + pgvector', 'Complete data sovereignty'] },
];

const DEVELOPER_FEATURES = [
  {
    icon: Network,
    title: 'Graph Memory',
    desc: 'Knowledge graph built into Postgres — entities, relationships, and data mappings extracted automatically by the AI pipeline. Entity-aware search boosts RAG results with structured context.',
    code: `m.entities("Google")  # search graph
m.related("data_abc") # linked entities`,
    badges: ['Postgres', 'Auto-Extract', 'Entity-Aware RAG'],
  },
  {
    icon: Code2,
    title: 'Simple SDK',
    desc: 'High-level MemDog facade with 6 methods — add, search, get, delete, entities, compress. Auto-creates daily memories, deserializes responses, and wraps the full 70+ method client.',
    code: `m = MemDog("http://...", user_id="u1")
m.add("Hello", tags=["greeting"])
m.search("hello", use_ai=True)`,
    badges: ['Python', '6 Methods', 'Zero Config'],
  },
  {
    icon: Puzzle,
    title: 'Agent Adapters',
    desc: 'Drop-in memory backends for LangChain (ChatMessageHistory + Retriever), CrewAI (save/search), and OpenAI function calling. Install extras: pip install mem-dog-client[langchain].',
    code: `from mem_dog_client.adapters.langchain \\
  import MemDogChatMessageHistory
history = MemDogChatMessageHistory(m)`,
    badges: ['LangChain', 'CrewAI', 'OpenAI'],
  },
  {
    icon: Archive,
    title: 'Memory Compression',
    desc: 'LLM-powered summarization compresses verbose conversation memories into structured summaries. Archive originals, keep key facts, entities, and action items. Auto-triggers at configurable thresholds.',
    code: `m.compress("mem_conv_xyz",
  archive_originals=True)`,
    badges: ['LLM Summary', 'Auto-Trigger', 'Archive'],
  },
];

const COMPETITORS = ['Mem-Dog', 'Dify.ai', 'Mem0', 'Zep', 'LangMem'] as const;

const COMPARISON_FEATURES: { category: string; features: { name: string; values: ('yes' | 'no' | 'partial' | string)[] }[] }[] = [
  {
    category: 'Core Architecture',
    features: [
      { name: 'Runs fully on-premise / at home', values: ['yes', 'partial', 'no', 'no', 'no'] },
      { name: 'Self-hosted AI models (Ollama)', values: ['yes', 'partial', 'no', 'no', 'no'] },
      { name: 'Near-zero marginal cost per query', values: ['yes', 'no', 'no', 'no', 'no'] },
      { name: 'Data never leaves your network', values: ['yes', 'partial', 'no', 'no', 'no'] },
      { name: 'Single docker compose up', values: ['yes', 'yes', 'no', 'no', 'no'] },
    ],
  },
  {
    category: 'Data & Integrations',
    features: [
      { name: '300+ app integrations (Nango-powered)', values: ['yes', 'no', 'no', 'no', 'no'] },
      { name: 'Per-user webhook endpoints (whk_<ulid>)', values: ['yes', 'no', 'no', 'no', 'no'] },
      { name: 'Multi-channel ingest (WhatsApp, Slack, etc.)', values: ['yes', 'no', 'no', 'no', 'no'] },
      { name: 'File/image/video/audio ingest', values: ['yes', 'yes', 'no', 'no', 'no'] },
      { name: 'Versioned storage with full history', values: ['yes', 'no', 'no', 'no', 'no'] },
      { name: 'Automatic OAuth token refresh', values: ['yes', 'no', 'no', 'no', 'no'] },
    ],
  },
  {
    category: 'AI & Intelligence',
    features: [
      { name: '40+ specialized AI agents', values: ['yes', 'partial', 'no', 'no', 'no'] },
      { name: '5 model tiers with smart routing', values: ['yes', 'partial', 'no', 'no', 'no'] },
      { name: 'Knowledge graph (Neo4j/Graphiti)', values: ['yes', 'no', 'no', 'yes', 'no'] },
      { name: 'Temporal fact tracking (valid_at/invalid_at)', values: ['yes', 'no', 'no', 'yes', 'no'] },
      { name: 'RAG chat with inline citations', values: ['yes', 'yes', 'partial', 'partial', 'no'] },
      { name: 'Model Garden (BYO providers)', values: ['yes', 'yes', 'no', 'no', 'no'] },
    ],
  },
  {
    category: 'Memory & Search',
    features: [
      { name: '10 memory types', values: ['yes', 'no', 'partial', 'partial', 'partial'] },
      { name: '5 search modes (vector, FTS, hybrid, graph, full)', values: ['yes', 'no', 'partial', 'partial', 'no'] },
      { name: 'Memory compression (LLM summarization)', values: ['yes', 'no', 'yes', 'yes', 'yes'] },
      { name: 'Per-user scoping & ACLs', values: ['yes', 'no', 'partial', 'yes', 'no'] },
      { name: 'Memory expiry with configurable TTL', values: ['yes', 'no', 'no', 'partial', 'no'] },
    ],
  },
  {
    category: 'Developer Experience',
    features: [
      { name: 'Python SDK with adapters (LangChain, CrewAI)', values: ['yes', 'yes', 'yes', 'yes', 'yes'] },
      { name: 'Multi-language SDKs (TS, Go, Rust, Ruby)', values: ['yes', 'no', 'partial', 'no', 'no'] },
      { name: 'Built-in conversational agent (DigiMe)', values: ['yes', 'no', 'no', 'no', 'no'] },
      { name: 'Interactive playground in UI', values: ['yes', 'yes', 'no', 'no', 'no'] },
      { name: 'OpenTelemetry distributed tracing', values: ['yes', 'partial', 'no', 'no', 'no'] },
    ],
  },
];

const COMPETITOR_DESCRIPTIONS: { name: string; focus: string; strength: string; gap: string }[] = [
  { name: 'Dify.ai', focus: 'Low-code LLM app builder', strength: 'Beautiful drag-and-drop workflow builder for creating AI applications. Good for prototyping LLM chains quickly. Self-hostable with Docker.', gap: 'No persistent memory layer, no multi-channel ingest, no webhook pipeline, no knowledge graph, no per-user webhook endpoints, no temporal reasoning.' },
  { name: 'Mem0', focus: 'Memory layer for AI agents', strength: 'Clean API for adding long-term memory to LLM applications. Good conversation and user memory primitives. Growing open-source community.', gap: 'Cloud-only for full features, limited to 4 memory categories, no data ingest pipeline, no 300+ app integrations, no AI enrichment agents, no knowledge graph, no versioned storage.' },
  { name: 'Zep', focus: 'Long-term memory for AI assistants', strength: 'Strong temporal knowledge graph with Graphiti fact extraction. Good at tracking how facts change over time. Reranking and triple search.', gap: 'Cloud-managed only, no self-hosting, no data ingest pipeline, no app integrations, no AI enrichment, no webhook endpoints, no built-in UI or playground.' },
  { name: 'LangMem', focus: 'Memory management for LangChain agents', strength: 'Native LangGraph integration. Good primitives for thread-level and cross-thread memory. Backed by LangChain ecosystem.', gap: 'LangChain-only, no multi-channel ingest, no app integrations, no knowledge graph, no versioned storage, no search modes beyond vector, no AI enrichment pipeline.' },
];

const PIPELINE_STEPS = [
  {
    icon: Globe,
    title: 'Data Sources',
    desc: '300+ apps',
    items: ['WhatsApp', 'Slack', 'Email', 'Telegram', 'Discord', 'Nango OAuth', 'Files', 'Webhooks (whk_*)'],
    color: 'from-cyan-400 to-cyan-500',
    glow: 'rgba(68,213,227,0.15)',
  },
  {
    icon: Webhook,
    title: 'Ingest Pipeline',
    desc: 'Normalize & route',
    items: ['Per-User Webhooks', 'Universal Envelope', 'NATS Streaming', 'Nango Credentials'],
    color: 'from-blue-400 to-blue-500',
    glow: 'rgba(95,181,251,0.15)',
  },
  {
    icon: Brain,
    title: 'AI Processing',
    desc: '40+ agents',
    items: ['6-Layer Classification', 'Smart Model Routing', 'Viewpoint Generation', 'Embedding Creation'],
    color: 'from-purple-400 to-purple-500',
    glow: 'rgba(181,150,250,0.15)',
  },
  {
    icon: Database,
    title: 'Memory Layer',
    desc: '10 memory types',
    items: ['Versioned Storage', 'pgvector Embeddings', 'Per-User Scoping', 'Encrypted Credentials'],
    color: 'from-pink-400 to-pink-500',
    glow: 'rgba(254,170,249,0.15)',
  },
  {
    icon: Search,
    title: 'Query & Search',
    desc: 'Semantic RAG',
    items: ['Natural Language', 'Cosine Similarity', 'Inline Citations', 'DigiMe Agent'],
    color: 'from-emerald-400 to-emerald-500',
    glow: 'rgba(52,211,153,0.15)',
  },
  {
    icon: Server,
    title: 'MCP Server',
    desc: 'Agent access',
    items: ['SSE Transport', 'Claude Desktop', 'Cursor Integration', '8 Tools'],
    color: 'from-rose-400 to-rose-500',
    glow: 'rgba(251,113,133,0.15)',
  },
];

/* ─── Accordion ─── */

function SectionAccordion({ id, title, icon: Icon, children, defaultOpen = false }: {
  id: string;
  title: string;
  icon: any;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section id={id} className="max-w-6xl mx-auto px-6 scroll-mt-20">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-4 py-6 border-b border-white/10 group"
      >
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-purple-500/20 border border-white/10 flex items-center justify-center flex-shrink-0">
          <Icon className="w-5 h-5 text-cyan-400/70" />
        </div>
        <h2 className="text-xl sm:text-2xl font-bold text-white/90 text-left flex-1">{title}</h2>
        <ChevronRight className={`w-5 h-5 text-white/30 transition-transform duration-300 ${open ? 'rotate-90' : ''}`} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <div className="py-8">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

/* ─── Helpers ─── */

function AnimatedCounter({ target, suffix = '' }: { target: string; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true, margin: '-50px' });
  const [display, setDisplay] = useState('0');
  const numericPart = parseInt(target);

  useEffect(() => {
    if (!isInView || isNaN(numericPart)) { setDisplay(target); return; }
    let start = 0;
    const duration = 1200;
    const step = 16;
    const inc = numericPart / (duration / step);
    const timer = setInterval(() => {
      start += inc;
      if (start >= numericPart) { setDisplay(target); clearInterval(timer); }
      else setDisplay(Math.floor(start).toString() + suffix);
    }, step);
    return () => clearInterval(timer);
  }, [isInView, numericPart, target, suffix]);

  return <span ref={ref}>{display}</span>;
}

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({ opacity: 1, y: 0, transition: { duration: 0.5, delay: i * 0.08, ease: [0.25, 0.4, 0.25, 1] } }),
};

/* ─── Component ─── */

export default function LoginPage() {
  const { signInWithEmail, signUp, signInWithGoogle } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [activeSection, setActiveSection] = useState('');

  useEffect(() => {
    const interval = setInterval(() => setPhraseIndex(i => (i + 1) % ROTATING_PHRASES.length), 3500);
    return () => clearInterval(interval);
  }, []);

  // Track which section is in view for nav highlighting
  useEffect(() => {
    const ids = ['how-it-works', 'use-cases', 'features', 'developer', 'platform'];
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: '-40% 0px -40% 0px', threshold: 0 }
    );
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { error } = isSignUp ? await signUp(email, password) : await signInWithEmail(email, password);
      if (error) setError(error.message);
    } finally { setLoading(false); }
  };

  const handleGoogle = async () => {
    setError('');
    const { error } = await signInWithGoogle();
    if (error) setError(error.message);
  };

  return (
    <div className="relative bg-black text-white" style={{ overflowX: 'clip' }}>
      {/* Gradient glow — top center */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[600px] pointer-events-none" style={{ background: 'radial-gradient(ellipse at center, rgba(68,213,227,0.12) 0%, rgba(95,181,251,0.08) 30%, rgba(181,150,250,0.06) 60%, transparent 80%)' }} />

      {/* ─── Nav ─── */}
      <div className="sticky top-0 z-50 bg-black/80 backdrop-blur-lg border-b border-white/5">
        <nav className="flex items-center justify-between max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 via-blue-500 to-purple-500 flex items-center justify-center">
              <Brain className="w-4 h-4 text-white" />
            </div>
            <span className="text-lg font-bold tracking-tight">Mem-Dog</span>
          </div>
          <div className="hidden lg:flex items-center gap-6 text-base font-bold">
            {[
              { href: 'how-it-works', label: 'How it Works' },
              { href: 'use-cases', label: 'Use Cases' },
              { href: 'features', label: 'Features' },
              { href: 'developer', label: 'Developer' },
              { href: 'platform', label: 'Platform' },
            ].map(link => (
              <a
                key={link.href}
                href={`#${link.href}`}
                className={`transition-colors ${
                  activeSection === link.href
                    ? 'text-white'
                    : 'text-white/50 hover:text-white/80'
                }`}
              >
                {link.label}
              </a>
            ))}
          </div>
          {!isReadOnly() && (
            <div className="flex items-center gap-3">
              <a href="#login" className="text-sm font-medium text-white/70 hover:text-white transition-colors px-4 py-2">
                Sign in
              </a>
              <a href="#login" className="text-sm font-medium transition-colors bg-gradient-to-r from-cyan-500 to-purple-500 text-white rounded-lg px-4 py-2 hover:opacity-90">
                Sign up
              </a>
            </div>
          )}
        </nav>
      </div>

      {/* ─── Hero ─── */}
      <section className="relative max-w-4xl mx-auto px-6 pt-20 pb-24 text-center">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-white/10 bg-white/5 text-xs text-white/50 mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Private AI System — self-hosted, fast, cost-efficient
          </div>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 }}
          className="text-5xl sm:text-6xl md:text-7xl font-extrabold leading-[1.1] tracking-tight mb-6"
        >
          <span className="nango-gradient-text">The Private</span>
          <br />
          <span className="nango-gradient-text">AI System.</span>
        </motion.h1>

        <div className="h-8 mb-8">
          <AnimatePresence mode="wait">
            <motion.p
              key={phraseIndex}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.35 }}
              className="text-lg text-white/40"
            >
              {ROTATING_PHRASES[phraseIndex]}
            </motion.p>
          </AnimatePresence>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35 }}
          className="flex items-center justify-center gap-4"
        >
          {isReadOnly() ? (
            <a href="https://github.com/BuildGeekAI/mem-dog" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white text-black font-semibold text-sm hover:bg-white/90 transition-colors">
              View on GitHub <ChevronRight className="w-4 h-4" />
            </a>
          ) : (
            <a href="#login" className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white text-black font-semibold text-sm hover:bg-white/90 transition-colors">
              Get started <ChevronRight className="w-4 h-4" />
            </a>
          )}
          <a href="#how-it-works" className="inline-flex items-center gap-2 px-6 py-3 rounded-lg border border-white/15 text-white/70 font-medium text-sm hover:border-white/30 hover:text-white transition-all">
            See how it works
          </a>
        </motion.div>

        {/* The Vision */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.6 }}
          className="mt-20 max-w-2xl mx-auto text-left"
        >
          <div className="p-6 sm:p-8 rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-sm relative overflow-hidden">
            <div className="absolute -inset-4 -z-10 opacity-20" style={{ background: 'radial-gradient(ellipse at 30% 20%, rgba(68,213,227,0.2) 0%, transparent 50%), radial-gradient(ellipse at 70% 80%, rgba(181,150,250,0.15) 0%, transparent 50%)' }} />
            <h3 className="text-lg font-bold text-white mb-4">
              AI should be private. Not as a feature — as the foundation.
            </h3>
            <div className="space-y-3 text-sm text-white/50 leading-relaxed">
              <p>
                Every time you ask an AI a question, your data travels to a distant data center, gets processed on someone else&apos;s hardware, and a record of your query lives on infrastructure you&apos;ll never audit. For individuals, that means your personal thoughts, health records, financial details, and private conversations are one breach away from exposure. For enterprises, it means trade secrets, customer data, and proprietary research flowing through third-party systems with opaque data-retention policies.
              </p>
              <p>
                <span className="text-white font-bold">We&apos;re building Mem-Dog to end that trade-off.</span> A complete AI system — 40 specialized agents, semantic search, a temporal knowledge graph, 300+ integrations — that runs entirely on hardware you control. Your laptop, a Mac Mini on your desk, or a server rack in your office. The AI never phones home because there&apos;s no home to phone.
              </p>
              <p>
                <span className="text-white/80 font-medium">Speed through smarter architecture.</span> Instead of routing every request to a massive cloud model, Mem-Dog uses a 6-layer classification pipeline that matches each piece of data to the smallest model that can handle it well. A simple text note gets a fast 4-billion-parameter model. A complex document gets a 27-billion-parameter one. Multimodal content gets a vision model. This tiered routing means most queries finish in milliseconds on modest hardware — because you&apos;re not waiting for a 200B model to parse a grocery list.
              </p>
              <p>
                <span className="text-white/80 font-medium">Cost efficiency through local inference.</span> Cloud AI bills grow linearly with usage — every token costs money. With local models running on Ollama, the marginal cost of a query is the electricity to run it. For individuals, that means unlimited personal AI for the price of a home server. For enterprises, it means predictable infrastructure costs that don&apos;t scale with headcount or query volume. No per-seat licensing. No surprise invoices.
              </p>
              <p>
                <span className="text-white/80 font-medium">Intelligence through better data processing.</span> Privacy doesn&apos;t have to mean dumb. Mem-Dog&apos;s 40 agents work in concert — classifying, extracting entities, generating embeddings, building knowledge graphs, and creating AI-powered viewpoints — all locally. The result is a system that gets smarter the more you use it, building a private knowledge base that understands relationships between your data, tracks how facts change over time, and surfaces insights through multi-signal search that combines vector similarity, keyword matching, and graph traversal.
              </p>
            </div>
            {/* Key pillars */}
            <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { icon: Shield, label: 'Private by Design', sub: 'Data never leaves your network' },
                { icon: Zap, label: 'Fast Locally', sub: 'Tiered models, millisecond routing' },
                { icon: Cpu, label: 'Cost Efficient', sub: 'No per-token fees, ever' },
                { icon: Brain, label: 'Genuinely Smart', sub: '40 agents, knowledge graph, RAG' },
              ].map(item => (
                <div key={item.label} className="p-3 rounded-lg border border-white/5 bg-white/[0.02] text-center">
                  <item.icon className="w-4 h-4 text-cyan-400/60 mx-auto mb-1.5" />
                  <div className="text-xs font-semibold text-white/70">{item.label}</div>
                  <div className="text-[10px] text-white/30">{item.sub}</div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Trust logos */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.0 }}
          className="mt-16 flex items-center justify-center gap-10 text-white/20"
        >
          {[Terminal, Globe, GitBranch, Cpu, Activity].map((Icon, i) => (
            <Icon key={i} className="w-6 h-6" />
          ))}
        </motion.div>
      </section>

      {/* ─── Login Card (right after hero) ─── */}
      {!isReadOnly() && <section id="login" className="max-w-sm mx-auto px-6 pb-16 scroll-mt-8">
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-6 space-y-5 backdrop-blur-sm">
          <h3 className="text-lg font-semibold text-white text-center">
            {isSignUp ? 'Create account' : 'Sign in'}
          </h3>

          {error && (
            <div className="px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/25" />
              <input
                type="email" placeholder="Email" value={email}
                onChange={e => setEmail(e.target.value)} required
                className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/25 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/30 focus:border-cyan-500/30 transition-all"
              />
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/25" />
              <input
                type="password" placeholder="Password" value={password}
                onChange={e => setPassword(e.target.value)} required minLength={6}
                className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder-white/25 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/30 focus:border-cyan-500/30 transition-all"
              />
            </div>
            <button type="submit" disabled={loading}
              className="w-full py-2.5 rounded-lg bg-white text-black font-semibold text-sm hover:bg-white/90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {isSignUp ? 'Sign up' : 'Sign in'}
            </button>
          </form>

          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-white/10" />
            <span className="text-xs text-white/25">or</span>
            <div className="flex-1 h-px bg-white/10" />
          </div>

          <button onClick={handleGoogle}
            className="w-full py-2.5 rounded-lg bg-white/5 border border-white/10 text-white/70 font-medium text-sm hover:bg-white/10 transition-colors flex items-center justify-center gap-2"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Continue with Google
          </button>

          <p className="text-center text-xs text-white/30">
            {isSignUp ? 'Already have an account?' : "Don't have an account?"}{' '}
            <button onClick={() => { setIsSignUp(!isSignUp); setError(''); }}
              className="text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              {isSignUp ? 'Sign in' : 'Sign up'}
            </button>
          </p>
        </div>
      </section>}

      {/* ─── Accordion Sections ─── */}
      <div className="border-t border-white/5 pt-8">

      <SectionAccordion id="how-it-works" title="How it Works" icon={Cog}>
        <div className="relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">
            How it <span className="nango-gradient-text">works</span>
          </h2>
          <p className="text-white/40 max-w-2xl mx-auto">
            Data flows from any source through a real-time AI pipeline into a private, queryable data layer — all automatic, all configurable.
          </p>
        </motion.div>

        {/* Pipeline flow — horizontal on desktop, vertical on mobile */}
        <div className="relative">
          {/* Desktop: horizontal pipeline */}
          <div className="hidden lg:flex items-start justify-between gap-2">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={step.title} className="flex items-start flex-1">
                <motion.div
                  custom={i}
                  initial="hidden"
                  whileInView="visible"
                  viewport={{ once: true, margin: '-50px' }}
                  variants={fadeUp}
                  className="relative group flex-1"
                >
                  {/* Card */}
                  <div className="relative p-5 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04] transition-all duration-300 h-full">
                    {/* Glow */}
                    <div className="absolute -inset-2 -z-10 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" style={{ background: `radial-gradient(ellipse at center, ${step.glow} 0%, transparent 70%)` }} />
                    {/* Icon */}
                    <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${step.color} flex items-center justify-center mb-4 shadow-lg`}>
                      <step.icon className="w-5 h-5 text-white" />
                    </div>
                    {/* Title + desc */}
                    <h3 className="text-sm font-bold text-white mb-0.5">{step.title}</h3>
                    <p className="text-xs text-white/35 mb-3">{step.desc}</p>
                    {/* Items */}
                    <ul className="space-y-1.5">
                      {step.items.map(item => (
                        <li key={item} className="flex items-center gap-2 text-xs text-white/40">
                          <span className={`w-1 h-1 rounded-full bg-gradient-to-r ${step.color} flex-shrink-0`} />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                </motion.div>
                {/* Arrow connector */}
                {i < PIPELINE_STEPS.length - 1 && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.5 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.3, delay: 0.1 + i * 0.1 }}
                    className="flex items-center justify-center flex-shrink-0 mt-14 mx-1"
                  >
                    <ArrowRight className="w-5 h-5 text-white/15" />
                  </motion.div>
                )}
              </div>
            ))}
          </div>

          {/* Mobile: vertical pipeline */}
          <div className="lg:hidden space-y-4">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={step.title}>
                <motion.div
                  custom={i}
                  initial="hidden"
                  whileInView="visible"
                  viewport={{ once: true, margin: '-30px' }}
                  variants={fadeUp}
                  className="relative group"
                >
                  <div className="relative flex items-start gap-4 p-5 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04] transition-all duration-300">
                    {/* Step number + icon */}
                    <div className="flex flex-col items-center gap-2">
                      <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${step.color} flex items-center justify-center shadow-lg flex-shrink-0`}>
                        <step.icon className="w-5 h-5 text-white" />
                      </div>
                      <span className="text-[10px] font-bold text-white/20">{i + 1}/{PIPELINE_STEPS.length}</span>
                    </div>
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-bold text-white mb-0.5">{step.title}</h3>
                      <p className="text-xs text-white/35 mb-2">{step.desc}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {step.items.map(item => (
                          <span key={item} className="px-2 py-0.5 rounded-md bg-white/5 border border-white/5 text-[10px] text-white/40">
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </motion.div>
                {/* Vertical connector */}
                {i < PIPELINE_STEPS.length - 1 && (
                  <div className="flex justify-center py-1">
                    <div className="w-px h-4 bg-gradient-to-b from-white/10 to-transparent" />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Animated data particle line (desktop only) */}
          <div className="hidden lg:block absolute top-14 left-[10%] right-[10%] h-px -z-10">
            <div className="w-full h-full bg-gradient-to-r from-cyan-500/10 via-purple-500/10 to-emerald-500/10" />
            <motion.div
              className="absolute top-0 w-16 h-px bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent"
              animate={{ left: ['0%', '100%'] }}
              transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
            />
          </div>
        </div>

        {/* Architecture Diagram */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mt-16 mb-8"
        >
          <h3 className="text-lg font-bold text-white/80 text-center mb-6">System Architecture</h3>
          <div className="relative max-w-2xl mx-auto p-6 rounded-xl border border-white/5 bg-white/[0.02]">
            {/* Top row: Sources */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="p-3 rounded-lg border border-cyan-500/20 bg-cyan-500/5 text-center">
                <Globe className="w-4 h-4 text-cyan-400/70 mx-auto mb-1" />
                <div className="text-xs font-semibold text-white/70">300+ Apps</div>
                <div className="text-[10px] text-white/30">Slack, WhatsApp, Email...</div>
              </div>
              <div className="p-3 rounded-lg border border-blue-500/20 bg-blue-500/5 text-center">
                <Terminal className="w-4 h-4 text-blue-400/70 mx-auto mb-1" />
                <div className="text-xs font-semibold text-white/70">Web UI (Next.js)</div>
                <div className="text-[10px] text-white/30">Upload, Chat, Playground</div>
              </div>
            </div>
            {/* Arrow down */}
            <div className="flex justify-center mb-4">
              <div className="flex items-center gap-8">
                <div className="flex flex-col items-center">
                  <div className="w-px h-4 bg-gradient-to-b from-cyan-500/30 to-white/10" />
                  <ChevronRight className="w-3 h-3 text-white/20 rotate-90" />
                </div>
                <div className="flex flex-col items-center">
                  <div className="w-px h-4 bg-gradient-to-b from-blue-500/30 to-white/10" />
                  <ChevronRight className="w-3 h-3 text-white/20 rotate-90" />
                </div>
              </div>
            </div>
            {/* Middle row: Gateway + API */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="p-3 rounded-lg border border-purple-500/20 bg-purple-500/5 text-center">
                <Webhook className="w-4 h-4 text-purple-400/70 mx-auto mb-1" />
                <div className="text-xs font-semibold text-white/70">Webhook Gateway</div>
                <div className="text-[10px] text-white/30">Normalize → Route</div>
              </div>
              <div className="p-3 rounded-lg border border-pink-500/20 bg-pink-500/5 text-center">
                <Server className="w-4 h-4 text-pink-400/70 mx-auto mb-1" />
                <div className="text-xs font-semibold text-white/70">API (FastAPI)</div>
                <div className="text-[10px] text-white/30">Ingest, Query, Manage</div>
              </div>
            </div>
            {/* Arrow connector between gateway and API */}
            <div className="absolute top-[calc(50%-8px)] left-1/2 -translate-x-1/2 hidden sm:block">
              <ArrowRight className="w-3 h-3 text-white/15" />
            </div>
            {/* Arrow down */}
            <div className="flex justify-center mb-4">
              <div className="flex items-center gap-8">
                <div className="flex flex-col items-center">
                  <div className="w-px h-4 bg-gradient-to-b from-purple-500/30 to-white/10" />
                  <ChevronRight className="w-3 h-3 text-white/20 rotate-90" />
                </div>
                <div className="flex flex-col items-center">
                  <div className="w-px h-4 bg-gradient-to-b from-pink-500/30 to-white/10" />
                  <ChevronRight className="w-3 h-3 text-white/20 rotate-90" />
                </div>
              </div>
            </div>
            {/* Bottom row: Storage + Processing */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="p-3 rounded-lg border border-yellow-500/20 bg-yellow-500/5 text-center">
                <Brain className="w-4 h-4 text-yellow-400/70 mx-auto mb-1" />
                <div className="text-xs font-semibold text-white/70">NATS Pipeline</div>
                <div className="text-[10px] text-white/30">40 AI Agents</div>
              </div>
              <div className="p-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 text-center">
                <Database className="w-4 h-4 text-emerald-400/70 mx-auto mb-1" />
                <div className="text-xs font-semibold text-white/70">Supabase</div>
                <div className="text-[10px] text-white/30">Postgres + pgvector</div>
              </div>
              <div className="p-3 rounded-lg border border-orange-500/20 bg-orange-500/5 text-center">
                <Network className="w-4 h-4 text-orange-400/70 mx-auto mb-1" />
                <div className="text-xs font-semibold text-white/70">Neo4j</div>
                <div className="text-[10px] text-white/30">Graphiti KG</div>
              </div>
            </div>
            {/* Arrow down to search */}
            <div className="flex justify-center mb-4">
              <div className="flex flex-col items-center">
                <div className="w-px h-4 bg-gradient-to-b from-emerald-500/30 to-white/10" />
                <ChevronRight className="w-3 h-3 text-white/20 rotate-90" />
              </div>
            </div>
            {/* MCP Server + Search layer */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg border border-white/10 bg-gradient-to-r from-cyan-500/5 via-purple-500/5 to-emerald-500/5 text-center">
                <Search className="w-4 h-4 text-white/50 mx-auto mb-1" />
                <div className="text-xs font-semibold text-white/70">Multi-Signal Search + RAG Chat</div>
                <div className="text-[10px] text-white/30">Vector · FTS · Graph · Hybrid · Citations</div>
              </div>
              <div className="p-3 rounded-lg border border-rose-500/20 bg-rose-500/5 text-center">
                <Server className="w-4 h-4 text-rose-400/70 mx-auto mb-1" />
                <div className="text-xs font-semibold text-white/70">MCP Server</div>
                <div className="text-[10px] text-white/30">Claude Desktop · Cursor · SSE</div>
              </div>
            </div>
            {/* Background glow */}
            <div className="absolute -inset-4 -z-10 rounded-2xl opacity-20" style={{ background: 'radial-gradient(ellipse at center, rgba(181,150,250,0.15) 0%, transparent 70%)' }} />
          </div>
        </motion.div>

        {/* AI Config callout */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mt-16 p-6 rounded-xl border border-white/5 bg-white/[0.02] relative overflow-hidden"
        >
          <div className="absolute -inset-2 -z-10 opacity-30" style={{ background: 'radial-gradient(ellipse at 30% 50%, rgba(181,150,250,0.12) 0%, transparent 60%)' }} />
          <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
            <div className="flex items-center gap-4 flex-shrink-0">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-400 to-pink-500 flex items-center justify-center shadow-lg">
                <Cog className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Fully Configurable AI</h3>
                <p className="text-xs text-white/35">Bring your own models, tune every parameter</p>
              </div>
            </div>
            <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { icon: Flower2, label: 'Model Garden', sub: '10+ providers' },
                { icon: SlidersHorizontal, label: 'Smart Routing', sub: 'Per data-type' },
                { icon: Wrench, label: 'Agent Configs', sub: 'Custom prompts' },
                { icon: Sparkles, label: 'Processing Flags', sub: 'Toggle per type' },
              ].map(item => (
                <div key={item.label} className="flex items-start gap-2">
                  <item.icon className="w-4 h-4 text-white/30 mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="text-xs font-medium text-white/70">{item.label}</div>
                    <div className="text-[10px] text-white/30">{item.sub}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
      </SectionAccordion>

      <SectionAccordion id="use-cases" title="Use Cases" icon={Users}>
        <div className="relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">
            Built for <span className="nango-gradient-text">every use case</span>
          </h2>
          <p className="text-white/40 max-w-xl mx-auto">
            From personal knowledge management to enterprise compliance — one platform, infinite possibilities.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {USE_CASES.map((uc, i) => (
            <motion.div
              key={uc.title}
              custom={i}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-50px' }}
              variants={fadeUp}
              className="group p-6 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04] transition-all duration-300"
            >
              <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center mb-4 group-hover:border-white/20 transition-colors">
                <uc.icon className="w-5 h-5 text-white/50 group-hover:text-white/70 transition-colors" />
              </div>
              <h3 className="text-sm font-semibold text-white mb-2">{uc.title}</h3>
              <p className="text-xs text-white/35 leading-relaxed">{uc.points}</p>
            </motion.div>
          ))}
        </div>
      </div>
      </SectionAccordion>

      <SectionAccordion id="features" title="Features" icon={Sparkles}>
        <div className="relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">
            Flexible. Powerful. <span className="nango-gradient-text">Complete.</span>
          </h2>
          <p className="text-white/40 max-w-xl mx-auto">
            Everything you need to build a private AI system for your data.
          </p>
        </motion.div>

        {/* ── Capabilities ── */}
        <div className="mb-20">
          <motion.h3
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.5 }}
            className="text-xl sm:text-2xl font-bold mb-2 text-center"
          >
            Core <span className="nango-gradient-text">Capabilities</span>
          </motion.h3>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-white/40 text-center mb-10 max-w-xl mx-auto text-sm"
          >
            Versioned storage, AI enrichment, semantic search, and more — all built in.
          </motion.p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {CAPABILITIES.map((cap, i) => (
              <motion.div
                key={cap.title}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, margin: '-50px' }}
                variants={fadeUp}
                className="group p-6 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04] transition-all duration-300"
              >
                <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center mb-4 group-hover:border-white/20 transition-colors">
                  <cap.icon className="w-5 h-5 text-white/50 group-hover:text-white/70 transition-colors" />
                </div>
                <h3 className="text-sm font-semibold text-white mb-2">{cap.title}</h3>
                <p className="text-xs text-white/35 leading-relaxed">{cap.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* ── AI Engine ── */}
        <div>
          <motion.h3
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.5 }}
            className="text-xl sm:text-2xl font-bold mb-2 text-center"
          >
            Intelligent <span className="nango-gradient-text">AI Engine</span>
          </motion.h3>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-white/40 text-center mb-10 max-w-xl mx-auto text-sm"
          >
            5 model tiers, smart routing per data type, configurable prompts, and pluggable skills — all fully customizable from the UI.
          </motion.p>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {AI_ENGINE_CARDS.map((item, i) => (
              <motion.div
                key={item.title}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, margin: '-50px' }}
                variants={fadeUp}
                className="group p-6 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04] transition-all duration-300"
              >
                <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center mb-4 group-hover:border-white/20 transition-colors">
                  <item.icon className="w-5 h-5 text-white/50 group-hover:text-white/70 transition-colors" />
                </div>
                <h3 className="text-sm font-semibold text-white mb-2">{item.title}</h3>
                <p className="text-xs text-white/35 leading-relaxed">{item.desc}</p>
              </motion.div>
            ))}
          </div>

          {/* DigiMe sub-section */}
          <div className="mt-20">
            <motion.h3
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ duration: 0.5 }}
              className="text-2xl sm:text-3xl font-bold mb-2 text-center"
            >
              Meet <span className="nango-gradient-text">DigiMe</span>
            </motion.h3>
            <motion.p
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="text-white/40 text-center mb-12 max-w-xl mx-auto"
            >
              Your AI memory assistant, powered by OpenClaw
            </motion.p>

            <div className="grid md:grid-cols-2 gap-12 items-center">
              <motion.div
                initial={{ opacity: 0, x: -30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: '-80px' }}
                transition={{ duration: 0.6 }}
              >
                <p className="text-white/35 mb-8 leading-relaxed text-sm">
                  DigiMe lives inside your messaging apps as an AI agent — ask questions, search memories, and ingest data through natural conversation with the mem-dog RAG system. No context switching, no extra tools.
                </p>
                <div className="space-y-4">
                  {[
                    { icon: MessageCircle, text: 'Lives in WhatsApp, Telegram, Signal, Slack, Discord, Matrix, 15+ more' },
                    { icon: Search, text: 'Natural language queries against the mem-dog RAG system' },
                    { icon: Brain, text: 'Semantic search across all ingested data' },
                    { icon: Zap, text: 'Ingest new data directly from conversations' },
                    { icon: Database, text: 'Retrieve and summarize memories on demand' },
                  ].map((item, i) => (
                    <motion.div
                      key={item.text}
                      initial={{ opacity: 0, x: -20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.4, delay: 0.2 + i * 0.1 }}
                      className="flex items-start gap-3"
                    >
                      <div className="w-7 h-7 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <item.icon className="w-3.5 h-3.5 text-white/50" />
                      </div>
                      <span className="text-sm text-white/50">{item.text}</span>
                    </motion.div>
                  ))}
                </div>
              </motion.div>

              <motion.div
                initial={{ opacity: 0, x: 30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: '-80px' }}
                transition={{ duration: 0.6, delay: 0.15 }}
                className="relative"
              >
                {/* Chat window */}
                <div className="rounded-xl border border-white/10 bg-[#0d1117] overflow-hidden shadow-2xl shadow-black/50">
                  <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5">
                    <div className="w-3 h-3 rounded-full bg-[#ff5f57]" />
                    <div className="w-3 h-3 rounded-full bg-[#febc2e]" />
                    <div className="w-3 h-3 rounded-full bg-[#28c840]" />
                    <span className="ml-3 text-xs text-white/25 font-mono flex items-center gap-1.5">
                      <Bot className="w-3 h-3" /> DigiMe · WhatsApp
                    </span>
                  </div>
                  <div className="p-4 space-y-3 max-h-[400px] overflow-y-auto">
                    {AGENT_MESSAGES.map((msg, i) => (
                      <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                          msg.role === 'user'
                            ? 'bg-cyan-500/15 border border-cyan-500/20 text-white/80'
                            : 'bg-white/5 border border-white/10 text-white/60'
                        }`}>
                          <div className="whitespace-pre-line">{msg.text}</div>
                          {'badges' in msg && msg.badges && (
                            <div className="flex gap-1.5 mt-2">
                              {msg.badges.map(b => (
                                <span key={b} className="px-1.5 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-[10px] font-mono">
                                  [{b}]
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                {/* Glow behind */}
                <div className="absolute -inset-4 -z-10 rounded-2xl opacity-30" style={{ background: 'radial-gradient(ellipse at center, rgba(68,213,227,0.15) 0%, transparent 70%)' }} />
              </motion.div>
            </div>
          </div>
        </div>
      </div>
      </SectionAccordion>

      <SectionAccordion id="developer" title="Developer" icon={Code2}>
        <div className="relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">
            Built for <span className="nango-gradient-text">developers</span>
          </h2>
          <p className="text-white/40 max-w-xl mx-auto">
            Graph memory, simple SDK, agent framework adapters, and memory compression — drop-in features that close the gap with mem0.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 gap-6">
          {DEVELOPER_FEATURES.map((item, i) => (
            <motion.div
              key={item.title}
              custom={i}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-50px' }}
              variants={fadeUp}
              className="group p-6 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04] transition-all duration-300"
            >
              <div className="flex items-start gap-4 mb-4">
                <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0 group-hover:border-white/20 transition-colors">
                  <item.icon className="w-5 h-5 text-white/50 group-hover:text-white/70 transition-colors" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-white mb-1">{item.title}</h3>
                  <p className="text-xs text-white/35 leading-relaxed">{item.desc}</p>
                </div>
              </div>
              {/* Code preview */}
              <div className="rounded-lg bg-black/40 border border-white/5 p-3 mb-3 font-mono text-[11px] text-cyan-400/70 whitespace-pre overflow-x-auto">
                {item.code}
              </div>
              {/* Badges */}
              <div className="flex flex-wrap gap-1.5">
                {item.badges.map(b => (
                  <span key={b} className="px-2 py-0.5 rounded-md bg-white/5 border border-white/5 text-[10px] text-white/40">
                    {b}
                  </span>
                ))}
              </div>
            </motion.div>
          ))}
        </div>

        {/* ── Playground ── */}
        <div className="mt-20">
          <motion.h3
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.5 }}
            className="text-xl sm:text-2xl font-bold mb-2 text-center"
          >
            Interactive <span className="nango-gradient-text">Playground</span>
          </motion.h3>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-white/40 text-center mb-10 max-w-xl mx-auto text-sm"
          >
            Test the full ingestion pipeline, upload data in any format, and chat with your knowledge base — all from one place.
          </motion.p>
          <div className="grid sm:grid-cols-3 gap-5">
            {[
              { icon: Webhook, title: 'Channel to Webhook', desc: 'Simulate webhook messages across 10+ channel types (Slack, WhatsApp, Email, Telegram, Discord, and more). Test the full gateway-to-pipeline flow with text and file attachments.' },
              { icon: Upload, title: 'Data Insert', desc: 'Ingest data via 6 input modes: text with dictation, file drag-and-drop, URL import, camera capture, voice recording, and video recording. Attach to sessions and memories.' },
              { icon: MessageCircle, title: 'Knowledge Chat', desc: 'RAG-powered chat interface over your stored data. Ask questions in natural language, get AI answers with inline citations, and scope queries to specific memories.' },
            ].map((item, i) => (
              <motion.div
                key={item.title}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, margin: '-50px' }}
                variants={fadeUp}
                className="group p-6 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04] transition-all duration-300"
              >
                <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center mb-4 group-hover:border-white/20 transition-colors">
                  <item.icon className="w-5 h-5 text-white/50 group-hover:text-white/70 transition-colors" />
                </div>
                <h3 className="text-sm font-semibold text-white mb-2">{item.title}</h3>
                <p className="text-xs text-white/35 leading-relaxed">{item.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
      </SectionAccordion>

      <SectionAccordion id="platform" title="Platform" icon={Globe}>
        <div className="relative">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">
            Deploy <span className="nango-gradient-text">anywhere</span>
          </h2>
          <p className="text-white/40 max-w-xl mx-auto">
            Production-grade infrastructure with real-time processing, tenant isolation, and complete observability. Run locally or on Google Cloud.
          </p>
        </motion.div>

        {/* Infrastructure stats */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-6 mb-16">
          {INFRA_STATS.map((stat, i) => (
            <motion.div
              key={stat.label}
              custom={i}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-50px' }}
              variants={fadeUp}
              className="text-center p-6 rounded-xl border border-white/5 bg-white/[0.02]"
            >
              <div className="text-3xl sm:text-4xl font-bold nango-gradient-text mb-1">
                <AnimatedCounter target={stat.value} />
              </div>
              <div className="text-sm font-medium text-white/70 mb-1">{stat.label}</div>
              <div className="text-xs text-white/30">{stat.sub}</div>
            </motion.div>
          ))}
        </div>

        {/* Hosting cards */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
          {HOSTING_OPTIONS.map((item, i) => (
            <motion.div
              key={item.title}
              custom={i}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: '-50px' }}
              variants={fadeUp}
              className="group p-6 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04] transition-all duration-300"
            >
              <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center mb-4 group-hover:border-white/20 transition-colors">
                <item.icon className="w-5 h-5 text-white/50 group-hover:text-white/70 transition-colors" />
              </div>
              <h3 className="text-sm font-semibold text-white mb-2">{item.title}</h3>
              <p className="text-xs text-white/35 leading-relaxed mb-4">{item.desc}</p>
              <ul className="space-y-1.5">
                {item.features.map(f => (
                  <li key={f} className="flex items-center gap-2 text-xs text-white/40">
                    <ChevronRight className="w-3 h-3 text-cyan-400/50 flex-shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>

        {/* Mac Mini callout */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mb-16 p-6 rounded-xl border border-white/5 bg-white/[0.02] relative overflow-hidden"
        >
          <div className="absolute -inset-2 -z-10 opacity-30" style={{ background: 'radial-gradient(ellipse at 70% 50%, rgba(68,213,227,0.12) 0%, transparent 60%)' }} />
          <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
            <div className="flex items-center gap-4 flex-shrink-0">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center shadow-lg">
                <Cpu className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">Runs on a Mac Mini</h3>
                <p className="text-xs text-white/35">Full production stack on your desk</p>
              </div>
            </div>
            <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { icon: Cpu, label: 'Apple Silicon', sub: 'Native GPU inference' },
                { icon: Database, label: 'Self-Hosted DB', sub: 'Supabase + pgvector' },
                { icon: Brain, label: 'Local AI', sub: 'Ollama on-device' },
                { icon: Shield, label: 'Your Data', sub: 'Never leaves home' },
              ].map(item => (
                <div key={item.label} className="flex items-start gap-2">
                  <item.icon className="w-4 h-4 text-white/30 mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="text-xs font-medium text-white/70">{item.label}</div>
                    <div className="text-[10px] text-white/30">{item.sub}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Trust badges */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {TRUST_ITEMS.map((item, i) => (
            <motion.div
              key={item.title}
              custom={i}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
              variants={fadeUp}
              className="text-center p-6 rounded-xl border border-white/5 bg-white/[0.02]"
            >
              <item.icon className="w-6 h-6 text-white/30 mx-auto mb-3" />
              <div className="text-sm font-medium text-white/80 mb-1">{item.title}</div>
              <div className="text-xs text-white/30">{item.desc}</div>
            </motion.div>
          ))}
        </div>

        {/* ── How Mem-Dog Compares ── */}
        <div className="mt-20">
          <motion.h3
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.5 }}
            className="text-xl sm:text-2xl font-bold mb-2 text-center"
          >
            How Mem-Dog <span className="nango-gradient-text">compares</span>
          </motion.h3>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-white/40 text-center mb-10 max-w-2xl mx-auto text-sm"
          >
            Each tool does one thing well. Mem-Dog combines all of them — integrations, AI processing, memory, search, and a knowledge graph — into a single self-hosted system.
          </motion.p>

          {/* Comparison table */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden mb-16"
          >
            <div className="grid grid-cols-6 border-b border-white/10 bg-white/[0.03]">
              <div className="p-4 text-xs font-bold text-white/50">Feature</div>
              {COMPETITORS.map((name, i) => (
                <div key={name} className={`p-4 text-xs font-bold text-center ${i === 0 ? 'text-cyan-400 bg-cyan-500/5' : 'text-white/50'}`}>
                  {name}
                </div>
              ))}
            </div>
            {COMPARISON_FEATURES.map((category) => (
              <div key={category.category}>
                <div className="grid grid-cols-6 border-b border-white/5 bg-white/[0.02]">
                  <div className="col-span-6 px-4 py-2 text-[11px] font-bold text-white/30 uppercase tracking-wider">
                    {category.category}
                  </div>
                </div>
                {category.features.map((feature) => (
                  <div key={feature.name} className="grid grid-cols-6 border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                    <div className="p-3 text-xs text-white/50 flex items-center">{feature.name}</div>
                    {feature.values.map((val, i) => (
                      <div key={i} className={`p-3 flex items-center justify-center ${i === 0 ? 'bg-cyan-500/[0.03]' : ''}`}>
                        {val === 'yes' ? (
                          <Check className="w-4 h-4 text-emerald-400" />
                        ) : val === 'no' ? (
                          <X className="w-4 h-4 text-white/15" />
                        ) : val === 'partial' ? (
                          <Minus className="w-4 h-4 text-yellow-400/60" />
                        ) : (
                          <span className="text-xs text-white/40">{val}</span>
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </motion.div>

          {/* Competitor cards */}
          <div className="grid sm:grid-cols-2 gap-6">
            {COMPETITOR_DESCRIPTIONS.map((comp, i) => (
              <motion.div
                key={comp.name}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, margin: '-50px' }}
                variants={fadeUp}
                className="p-6 rounded-xl border border-white/5 bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04] transition-all duration-300"
              >
                <h3 className="text-base font-bold text-white mb-1">{comp.name}</h3>
                <p className="text-xs text-cyan-400/60 mb-4">{comp.focus}</p>
                <div className="space-y-3">
                  <div>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Check className="w-3 h-3 text-emerald-400/70" />
                      <span className="text-[11px] font-semibold text-white/50 uppercase tracking-wider">Strength</span>
                    </div>
                    <p className="text-xs text-white/40 leading-relaxed">{comp.strength}</p>
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5 mb-1">
                      <ArrowRight className="w-3 h-3 text-cyan-400/70" />
                      <span className="text-[11px] font-semibold text-white/50 uppercase tracking-wider">Where Mem-Dog goes further</span>
                    </div>
                    <p className="text-xs text-white/40 leading-relaxed">{comp.gap}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Summary */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mt-12 p-6 rounded-xl border border-white/10 bg-gradient-to-r from-cyan-500/5 via-purple-500/5 to-emerald-500/5 text-center"
          >
            <p className="text-sm text-white/60 leading-relaxed max-w-2xl mx-auto">
              <span className="text-white/80 font-semibold">Nango</span> connects your apps.{' '}
              <span className="text-white/80 font-semibold">Dify</span> builds AI workflows.{' '}
              <span className="text-white/80 font-semibold">Mem0</span> adds memory.{' '}
              <span className="text-white/80 font-semibold">Zep</span> tracks facts.{' '}
              <span className="text-cyan-400 font-semibold">Mem-Dog</span> does all of it — on hardware you own, at a fraction of the cost.
            </p>
          </motion.div>
        </div>
      </div>
      </SectionAccordion>

      </div>{/* end accordion wrapper */}

      {/* Login card is now at the top — removed duplicate here */}

      {/* ─── Footer ─── */}
      <footer className="border-t border-white/5">
        <div className="max-w-5xl mx-auto px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-white/30 text-sm">
            <div className="w-5 h-5 rounded bg-gradient-to-br from-cyan-400 to-purple-500 flex items-center justify-center">
              <Brain className="w-3 h-3 text-white" />
            </div>
            <span>Mem-Dog</span>
            <span className="text-white/15">|</span>
            <span>Private AI System</span>
          </div>
          <div className="flex items-center gap-6 text-xs text-white/20">
            <a href="#how-it-works" className="hover:text-white/50 transition-colors">How it Works</a>
            <a href="#features" className="hover:text-white/50 transition-colors">Features</a>
            <a href="#developer" className="hover:text-white/50 transition-colors">Developer</a>
            <a href="#platform" className="hover:text-white/50 transition-colors">Platform</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

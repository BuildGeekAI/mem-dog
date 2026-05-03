'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Plus, Check, X, AlertCircle, Loader2, RefreshCw,
  Trash2, Plug, Search, Eye, EyeOff, ChevronDown, ChevronRight,
  Flower2, Cloud, Server, Network, Cpu, Zap, Save, RotateCcw,
  Code, FileText, Globe, CheckCircle,
} from 'lucide-react';
import {
  getProviderRegistry, listUserEngines, createUserEngine, updateUserEngine,
  deleteUserEngine, testEngine, discoverEngineModels, getCurrentUserId,
  getOllamaCloudModels, getSmartRoutingConfig, getModelCatalog,
  getUserAvailableModels, updateUserAIPreferences,
} from '@/lib/api';
import type { ProviderInfo, EngineConfigResponse, EngineTestResult } from '@/types';

// ---------------------------------------------------------------------------
// Provider icon mapping
// ---------------------------------------------------------------------------
const ICON_MAP: Record<string, typeof Cloud> = {
  openai: Cloud,
  anthropic: Cloud,
  gemini: Cloud,
  ollama: Server,
  ollama_cloud: Cloud,
  openrouter: Network,
  together: Cloud,
  huggingface: Cloud,
  bedrock: Cloud,
  vllm: Server,
  litellm: Network,
};

function ProviderIcon({ icon, className }: { icon: string; className?: string }) {
  const Icon = ICON_MAP[icon] || Cloud;
  return <Icon className={className} />;
}

// ---------------------------------------------------------------------------
// Model capabilities (pre-populated for all providers)
// ---------------------------------------------------------------------------
interface ModelCapability {
  name: string;
  displayName: string;
  provider: string;
  tier: 'small' | 'medium' | 'large' | 'embedding';
  multimodal: boolean;
  code: boolean;
  reasoning: boolean;
  structured_output: boolean;
  long_context: boolean;
  context_window: number;
  best_for: string[];
}

const PROVIDER_MODEL_CARDS: Record<string, ModelCapability[]> = {
  gemini: [
    { name: 'gemini-2.5-pro-preview-05-06', displayName: 'Gemini 2.5 Pro', provider: 'gemini', tier: 'large', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 1048576, best_for: ['complex reasoning', 'code generation', 'multimodal analysis'] },
    { name: 'gemini-2.5-flash-preview-05-20', displayName: 'Gemini 2.5 Flash', provider: 'gemini', tier: 'medium', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 1048576, best_for: ['fast inference', 'balanced quality', 'cost-effective'] },
    { name: 'gemini-2.0-flash', displayName: 'Gemini 2.0 Flash', provider: 'gemini', tier: 'medium', multimodal: true, code: true, reasoning: false, structured_output: true, long_context: true, context_window: 1048576, best_for: ['real-time tasks', 'streaming', 'tool use'] },
    { name: 'gemini-1.5-pro', displayName: 'Gemini 1.5 Pro', provider: 'gemini', tier: 'large', multimodal: true, code: true, reasoning: false, structured_output: true, long_context: true, context_window: 2097152, best_for: ['long documents', 'video understanding', 'large codebases'] },
    { name: 'gemini-1.5-flash', displayName: 'Gemini 1.5 Flash', provider: 'gemini', tier: 'small', multimodal: true, code: true, reasoning: false, structured_output: true, long_context: true, context_window: 1048576, best_for: ['high-volume tasks', 'summarization', 'classification'] },
    { name: 'text-embedding-004', displayName: 'Text Embedding 004', provider: 'gemini', tier: 'embedding', multimodal: false, code: false, reasoning: false, structured_output: false, long_context: false, context_window: 2048, best_for: ['semantic search', 'similarity', 'retrieval'] },
  ],
  openai: [
    { name: 'gpt-4o', displayName: 'GPT-4o', provider: 'openai', tier: 'large', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 128000, best_for: ['general purpose', 'vision tasks', 'complex reasoning'] },
    { name: 'gpt-4o-mini', displayName: 'GPT-4o Mini', provider: 'openai', tier: 'small', multimodal: true, code: true, reasoning: false, structured_output: true, long_context: true, context_window: 128000, best_for: ['cost-effective', 'fast responses', 'simple tasks'] },
    { name: 'gpt-4-turbo', displayName: 'GPT-4 Turbo', provider: 'openai', tier: 'large', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 128000, best_for: ['complex analysis', 'long documents', 'code generation'] },
    { name: 'gpt-3.5-turbo', displayName: 'GPT-3.5 Turbo', provider: 'openai', tier: 'small', multimodal: false, code: true, reasoning: false, structured_output: true, long_context: false, context_window: 16385, best_for: ['fast inference', 'simple tasks', 'chat'] },
    { name: 'o1', displayName: 'o1', provider: 'openai', tier: 'large', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 200000, best_for: ['deep reasoning', 'math', 'science', 'complex problems'] },
    { name: 'o1-mini', displayName: 'o1 Mini', provider: 'openai', tier: 'medium', multimodal: false, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 128000, best_for: ['coding', 'math', 'cost-effective reasoning'] },
    { name: 'o3-mini', displayName: 'o3 Mini', provider: 'openai', tier: 'medium', multimodal: false, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 200000, best_for: ['coding', 'reasoning', 'STEM tasks'] },
    { name: 'text-embedding-3-small', displayName: 'Embedding 3 Small', provider: 'openai', tier: 'embedding', multimodal: false, code: false, reasoning: false, structured_output: false, long_context: false, context_window: 8191, best_for: ['semantic search', 'classification', 'retrieval'] },
    { name: 'text-embedding-3-large', displayName: 'Embedding 3 Large', provider: 'openai', tier: 'embedding', multimodal: false, code: false, reasoning: false, structured_output: false, long_context: false, context_window: 8191, best_for: ['high-accuracy embeddings', 'similarity', 'clustering'] },
  ],
  anthropic: [
    { name: 'claude-opus-4-20250514', displayName: 'Claude Opus 4', provider: 'anthropic', tier: 'large', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 200000, best_for: ['complex analysis', 'creative writing', 'research'] },
    { name: 'claude-sonnet-4-20250514', displayName: 'Claude Sonnet 4', provider: 'anthropic', tier: 'medium', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 200000, best_for: ['balanced performance', 'coding', 'analysis'] },
    { name: 'claude-haiku-4-20250414', displayName: 'Claude Haiku 4', provider: 'anthropic', tier: 'small', multimodal: true, code: true, reasoning: false, structured_output: true, long_context: true, context_window: 200000, best_for: ['fast responses', 'classification', 'simple tasks'] },
    { name: 'claude-3-5-sonnet-20241022', displayName: 'Claude 3.5 Sonnet', provider: 'anthropic', tier: 'medium', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 200000, best_for: ['coding', 'analysis', 'general purpose'] },
    { name: 'claude-3-5-haiku-20241022', displayName: 'Claude 3.5 Haiku', provider: 'anthropic', tier: 'small', multimodal: false, code: true, reasoning: false, structured_output: true, long_context: true, context_window: 200000, best_for: ['fast tasks', 'extraction', 'classification'] },
  ],
  ollama: [
    { name: 'llama3.1', displayName: 'Llama 3.1', provider: 'ollama', tier: 'medium', multimodal: false, code: true, reasoning: false, structured_output: true, long_context: true, context_window: 131072, best_for: ['general purpose', 'coding', 'instruction following'] },
    { name: 'gemma3:12b', displayName: 'Gemma 3 12B', provider: 'ollama', tier: 'medium', multimodal: true, code: true, reasoning: false, structured_output: true, long_context: false, context_window: 8192, best_for: ['multimodal', 'classification', 'summarization'] },
    { name: 'gemma3:4b', displayName: 'Gemma 3 4B', provider: 'ollama', tier: 'small', multimodal: true, code: true, reasoning: false, structured_output: true, long_context: false, context_window: 8192, best_for: ['lightweight tasks', 'edge deployment', 'classification'] },
    { name: 'mistral', displayName: 'Mistral 7B', provider: 'ollama', tier: 'small', multimodal: false, code: true, reasoning: false, structured_output: true, long_context: false, context_window: 32768, best_for: ['fast inference', 'coding', 'chat'] },
    { name: 'qwen3:8b', displayName: 'Qwen 3 8B', provider: 'ollama', tier: 'small', multimodal: false, code: true, reasoning: true, structured_output: true, long_context: false, context_window: 32768, best_for: ['multilingual', 'reasoning', 'coding'] },
    { name: 'deepseek-r1', displayName: 'DeepSeek R1', provider: 'ollama', tier: 'large', multimodal: false, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 131072, best_for: ['deep reasoning', 'math', 'coding'] },
    { name: 'nomic-embed-text', displayName: 'Nomic Embed Text', provider: 'ollama', tier: 'embedding', multimodal: false, code: false, reasoning: false, structured_output: false, long_context: false, context_window: 8192, best_for: ['semantic search', 'retrieval', 'clustering'] },
    { name: 'mxbai-embed-large', displayName: 'MxBAI Embed Large', provider: 'ollama', tier: 'embedding', multimodal: false, code: false, reasoning: false, structured_output: false, long_context: false, context_window: 512, best_for: ['similarity', 'embeddings', 'retrieval'] },
  ],
  ollama_cloud: [
    { name: 'llama3.1', displayName: 'Llama 3.1', provider: 'ollama_cloud', tier: 'medium', multimodal: false, code: true, reasoning: false, structured_output: true, long_context: true, context_window: 131072, best_for: ['general purpose', 'coding', 'instruction following'] },
    { name: 'gemma3:12b', displayName: 'Gemma 3 12B', provider: 'ollama_cloud', tier: 'medium', multimodal: true, code: true, reasoning: false, structured_output: true, long_context: false, context_window: 8192, best_for: ['multimodal', 'classification', 'summarization'] },
    { name: 'mistral', displayName: 'Mistral 7B', provider: 'ollama_cloud', tier: 'small', multimodal: false, code: true, reasoning: false, structured_output: true, long_context: false, context_window: 32768, best_for: ['fast inference', 'coding', 'chat'] },
    { name: 'deepseek-r1', displayName: 'DeepSeek R1', provider: 'ollama_cloud', tier: 'large', multimodal: false, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 131072, best_for: ['deep reasoning', 'math', 'coding'] },
  ],
  openrouter: [
    { name: 'openai/gpt-4o', displayName: 'GPT-4o (via OpenRouter)', provider: 'openrouter', tier: 'large', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 128000, best_for: ['general purpose', 'vision', 'complex tasks'] },
    { name: 'anthropic/claude-sonnet-4', displayName: 'Claude Sonnet 4 (via OpenRouter)', provider: 'openrouter', tier: 'medium', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 200000, best_for: ['coding', 'analysis', 'balanced quality'] },
    { name: 'google/gemini-2.5-flash', displayName: 'Gemini 2.5 Flash (via OpenRouter)', provider: 'openrouter', tier: 'medium', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 1048576, best_for: ['fast inference', 'multimodal', 'cost-effective'] },
    { name: 'meta-llama/llama-3.1-70b-instruct', displayName: 'Llama 3.1 70B (via OpenRouter)', provider: 'openrouter', tier: 'large', multimodal: false, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 131072, best_for: ['open-source', 'coding', 'reasoning'] },
  ],
  together: [
    { name: 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo', displayName: 'Llama 3.1 70B Turbo', provider: 'together', tier: 'large', multimodal: false, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 131072, best_for: ['fast large model', 'coding', 'reasoning'] },
    { name: 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo', displayName: 'Llama 3.1 8B Turbo', provider: 'together', tier: 'small', multimodal: false, code: true, reasoning: false, structured_output: true, long_context: true, context_window: 131072, best_for: ['fast inference', 'simple tasks', 'chat'] },
    { name: 'mistralai/Mixtral-8x7B-Instruct-v0.1', displayName: 'Mixtral 8x7B', provider: 'together', tier: 'medium', multimodal: false, code: true, reasoning: false, structured_output: true, long_context: false, context_window: 32768, best_for: ['multilingual', 'coding', 'instruction following'] },
    { name: 'Qwen/Qwen2.5-72B-Instruct-Turbo', displayName: 'Qwen 2.5 72B Turbo', provider: 'together', tier: 'large', multimodal: false, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 131072, best_for: ['multilingual', 'reasoning', 'coding'] },
    { name: 'togethercomputer/m2-bert-80M-8k-retrieval', displayName: 'M2-BERT Retrieval', provider: 'together', tier: 'embedding', multimodal: false, code: false, reasoning: false, structured_output: false, long_context: false, context_window: 8192, best_for: ['retrieval', 'semantic search', 'classification'] },
  ],
  huggingface: [
    { name: 'meta-llama/Meta-Llama-3-8B-Instruct', displayName: 'Llama 3 8B', provider: 'huggingface', tier: 'small', multimodal: false, code: true, reasoning: false, structured_output: true, long_context: false, context_window: 8192, best_for: ['fast inference', 'chat', 'instruction following'] },
    { name: 'mistralai/Mistral-7B-Instruct-v0.3', displayName: 'Mistral 7B v0.3', provider: 'huggingface', tier: 'small', multimodal: false, code: true, reasoning: false, structured_output: true, long_context: false, context_window: 32768, best_for: ['coding', 'chat', 'multilingual'] },
    { name: 'sentence-transformers/all-MiniLM-L6-v2', displayName: 'MiniLM-L6-v2', provider: 'huggingface', tier: 'embedding', multimodal: false, code: false, reasoning: false, structured_output: false, long_context: false, context_window: 512, best_for: ['semantic search', 'similarity', 'sentence embeddings'] },
  ],
  bedrock: [
    { name: 'anthropic.claude-3-sonnet-20240229-v1:0', displayName: 'Claude 3 Sonnet (Bedrock)', provider: 'bedrock', tier: 'medium', multimodal: true, code: true, reasoning: true, structured_output: true, long_context: true, context_window: 200000, best_for: ['enterprise', 'analysis', 'coding'] },
    { name: 'amazon.titan-text-express-v1', displayName: 'Titan Text Express', provider: 'bedrock', tier: 'small', multimodal: false, code: false, reasoning: false, structured_output: true, long_context: false, context_window: 8192, best_for: ['summarization', 'classification', 'chat'] },
    { name: 'amazon.titan-embed-text-v2:0', displayName: 'Titan Embed Text v2', provider: 'bedrock', tier: 'embedding', multimodal: false, code: false, reasoning: false, structured_output: false, long_context: false, context_window: 8192, best_for: ['enterprise embeddings', 'retrieval', 'search'] },
  ],
};

// Provider display names for grouping
const PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  gemini: 'Google Gemini',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  ollama: 'Ollama (Local)',
  ollama_cloud: 'Ollama Cloud',
  openrouter: 'OpenRouter',
  together: 'Together AI',
  huggingface: 'Hugging Face',
  bedrock: 'Amazon Bedrock',
  vllm: 'vLLM',
  litellm: 'LiteLLM',
};

type ModelGroupBy = 'provider' | 'capability' | 'tier';
type CapabilityFilter = 'all' | 'multimodal' | 'code' | 'reasoning' | 'structured_output' | 'long_context' | 'embedding';

// ---------------------------------------------------------------------------
// Badge helpers
// ---------------------------------------------------------------------------
function categoryBadge(category: string) {
  switch (category) {
    case 'cloud': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'local': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    case 'gateway': return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    default: return 'bg-white/10 text-white/60 border-white/20';
  }
}

function statusBadge(status?: string | null) {
  if (status === 'success') return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
  if (status === 'error') return 'bg-red-500/20 text-red-400 border-red-500/30';
  return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
}

function statusLabel(status?: string | null) {
  if (status === 'success') return 'Connected';
  if (status === 'error') return 'Error';
  return 'Not tested';
}

function tierBadge(tier: string) {
  switch (tier) {
    case 'small': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    case 'medium': return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    case 'large': return 'bg-red-500/20 text-red-400 border-red-500/30';
    case 'embedding': return 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30';
    default: return 'bg-white/10 text-white/60 border-white/20';
  }
}

function formatContextWindow(tokens: number): string {
  if (tokens >= 1048576) return `${(tokens / 1048576).toFixed(tokens % 1048576 === 0 ? 0 : 1)}M`;
  if (tokens >= 1024) return `${Math.round(tokens / 1024)}K`;
  return `${tokens}`;
}

// ---------------------------------------------------------------------------
// Routing types
// ---------------------------------------------------------------------------
interface RoutingEntry {
  primary: string;
  fallback: string;
  suggested_primary: string;
  suggested_fallback: string;
  reason: string;
  is_override: boolean;
}

type GardenTab = 'providers' | 'models' | 'routing';

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function ModelGarden() {
  const userId = getCurrentUserId();
  const [activeTab, setActiveTab] = useState<GardenTab>('providers');

  // Provider state
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [engines, setEngines] = useState<EngineConfigResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingEngine, setEditingEngine] = useState<EngineConfigResponse | null>(null);
  const [modalProvider, setModalProvider] = useState<ProviderInfo | null>(null);
  const [formName, setFormName] = useState('');
  const [formApiKey, setFormApiKey] = useState('');
  const [formBaseUrl, setFormBaseUrl] = useState('');
  const [formEngineType, setFormEngineType] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [modalSaving, setModalSaving] = useState(false);
  const [modalTestResult, setModalTestResult] = useState<EngineTestResult | null>(null);
  const [modalTesting, setModalTesting] = useState(false);

  // Inline action states
  const [testingId, setTestingId] = useState<string | null>(null);
  const [discoveringId, setDiscoveringId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Routing state
  const [routing, setRouting] = useState<Record<string, RoutingEntry>>({});
  const [routingCategories, setRoutingCategories] = useState<Record<string, string[]>>({});
  const [allModelNames, setAllModelNames] = useState<{ provider: string; name: string }[]>([]);
  const [edits, setEdits] = useState<Record<string, { primary_model: string; fallback_model: string }>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [expandedRoutingCats, setExpandedRoutingCats] = useState<Set<string>>(new Set());
  const [refreshing, setRefreshing] = useState(false);

  // Models tab state
  const [modelSearch, setModelSearch] = useState('');
  const [modelGroupBy, setModelGroupBy] = useState<ModelGroupBy>('provider');
  const [capabilityFilter, setCapabilityFilter] = useState<CapabilityFilter>('all');

  const fetchData = useCallback(async (refresh = false) => {
    try {
      if (refresh) setRefreshing(true);
      else setLoading(true);
      setError(null);

      const [registryRes, enginesRes, modelsRes, routingRes, catalogRes, availableRes] = await Promise.all([
        getProviderRegistry(),
        listUserEngines(userId),
        getOllamaCloudModels(refresh),
        getSmartRoutingConfig(userId),
        getModelCatalog().catch(() => ({ models: {} } as { models: Record<string, any> })),
        getUserAvailableModels(userId).catch(() => ({ providers: [] })),
      ]);

      setProviders(registryRes.providers || []);
      setEngines(enginesRes || []);
      setRouting(routingRes.routing || {});
      setRoutingCategories(routingRes.categories || modelsRes.categories || {});

      // Build unified model list
      const allModels: { provider: string; name: string }[] = [];
      const seenNames = new Set<string>();

      for (const p of (availableRes.providers || [])) {
        for (const m of (p.models || [])) {
          const fullName = `${p.litellm_prefix}${m}`;
          if (!seenNames.has(fullName)) {
            seenNames.add(fullName);
            allModels.push({ provider: p.name, name: fullName });
          }
        }
      }

      for (const m of (modelsRes.models || [])) {
        if (!seenNames.has(m.name)) {
          seenNames.add(m.name);
          allModels.push({ provider: 'Ollama Cloud', name: m.name });
        }
      }

      for (const [, entry] of Object.entries(catalogRes.models || {})) {
        const catEntry = entry as { ollama_model?: string };
        if (catEntry.ollama_model) {
          const localName = `ollama/${catEntry.ollama_model}`;
          if (!seenNames.has(localName)) {
            seenNames.add(localName);
            allModels.push({ provider: 'Local Ollama', name: localName });
          }
        }
      }

      setAllModelNames(allModels);

      // Initialize edits from current overrides
      const initialEdits: Record<string, { primary_model: string; fallback_model: string }> = {};
      for (const [dt, entry] of Object.entries(routingRes.routing || {})) {
        if (entry.is_override) {
          initialEdits[dt] = { primary_model: entry.primary, fallback_model: entry.fallback };
        }
      }
      setEdits(initialEdits);
      setDirty(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load Model Garden data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [userId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const configuredTypes = new Set(engines.map(e => e.engine_type));

  // -----------------------------------------------------------------------
  // Provider modal helpers
  // -----------------------------------------------------------------------
  function openAddModal(provider: ProviderInfo) {
    setEditingEngine(null);
    setModalProvider(provider);
    setFormEngineType(provider.engine_type);
    setFormName(provider.display_name);
    setFormApiKey('');
    setFormBaseUrl(provider.default_base_url || '');
    setShowApiKey(false);
    setModalTestResult(null);
    setModalOpen(true);
  }

  function openEditModal(engine: EngineConfigResponse) {
    const provider = providers.find(p => p.engine_type === engine.engine_type) || null;
    setEditingEngine(engine);
    setModalProvider(provider);
    setFormEngineType(engine.engine_type);
    setFormName(engine.name);
    setFormApiKey('');
    setFormBaseUrl(engine.base_url || provider?.default_base_url || '');
    setShowApiKey(false);
    setModalTestResult(null);
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditingEngine(null);
    setModalProvider(null);
    setModalTestResult(null);
    setModalTesting(false);
  }

  async function handleSave() {
    try {
      setModalSaving(true);
      if (editingEngine) {
        const data: any = { name: formName, base_url: formBaseUrl || undefined };
        if (formApiKey) data.api_key = formApiKey;
        await updateUserEngine(userId, editingEngine.engine_id, data);
      } else {
        await createUserEngine(userId, {
          engine_type: formEngineType,
          name: formName,
          api_key: formApiKey || undefined,
          base_url: formBaseUrl || undefined,
        });
      }
      closeModal();
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to save engine');
    } finally {
      setModalSaving(false);
    }
  }

  async function handleModalTest() {
    if (!editingEngine) return;
    try {
      setModalTesting(true);
      const result = await testEngine(userId, editingEngine.engine_id);
      setModalTestResult(result);
    } catch (err: any) {
      setModalTestResult({ ok: false, error: err.message, tested_at: new Date().toISOString() });
    } finally {
      setModalTesting(false);
    }
  }

  async function handleTest(engineId: string) {
    try {
      setTestingId(engineId);
      await testEngine(userId, engineId);
      await fetchData();
    } catch {
      // handled by refresh
    } finally {
      setTestingId(null);
    }
  }

  async function handleDiscover(engineId: string) {
    try {
      setDiscoveringId(engineId);
      await discoverEngineModels(userId, engineId);
      await fetchData();
    } catch {
      // handled by refresh
    } finally {
      setDiscoveringId(null);
    }
  }

  async function handleDelete(engineId: string) {
    try {
      await deleteUserEngine(userId, engineId);
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to delete engine');
    }
  }

  // -----------------------------------------------------------------------
  // Routing helpers
  // -----------------------------------------------------------------------
  const handlePrimaryChange = (dataType: string, model: string) => {
    const entry = routing[dataType];
    if (!entry) return;
    setEdits(prev => {
      const next = { ...prev };
      if (model === entry.suggested_primary || model === '') {
        if (next[dataType]) {
          const { fallback_model } = next[dataType];
          if (!fallback_model || fallback_model === entry.suggested_fallback) delete next[dataType];
          else next[dataType] = { primary_model: '', fallback_model };
        }
      } else {
        next[dataType] = { primary_model: model, fallback_model: prev[dataType]?.fallback_model || '' };
      }
      return next;
    });
    setDirty(true);
  };

  const handleFallbackChange = (dataType: string, model: string) => {
    const entry = routing[dataType];
    if (!entry) return;
    setEdits(prev => {
      const next = { ...prev };
      if (model === entry.suggested_fallback || model === '') {
        if (next[dataType]) {
          const { primary_model } = next[dataType];
          if (!primary_model || primary_model === entry.suggested_primary) delete next[dataType];
          else next[dataType] = { primary_model, fallback_model: '' };
        }
      } else {
        next[dataType] = { primary_model: prev[dataType]?.primary_model || '', fallback_model: model };
      }
      return next;
    });
    setDirty(true);
  };

  const handleRoutingSave = async () => {
    try {
      setSaving(true);
      setSaveMessage(null);
      const overrides: Record<string, { primary_model: string; fallback_model: string }> = {};
      for (const [dt, edit] of Object.entries(edits)) {
        if (edit.primary_model || edit.fallback_model) overrides[dt] = edit;
      }
      await updateUserAIPreferences(userId, { smart_routing_overrides: overrides } as any);
      setSaveMessage('Routing overrides saved');
      setDirty(false);
      await fetchData();
    } catch (err: any) {
      setSaveMessage(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMessage(null), 3000);
    }
  };

  const handleRoutingReset = async () => {
    try {
      setSaving(true);
      await updateUserAIPreferences(userId, { smart_routing_overrides: {} } as any);
      setEdits({});
      setDirty(false);
      setSaveMessage('Reset to defaults');
      await fetchData();
    } catch (err: any) {
      setSaveMessage(`Reset failed: ${err.message}`);
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMessage(null), 3000);
    }
  };

  const toggleRoutingCat = (cat: string) => {
    setExpandedRoutingCats(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat); else next.add(cat);
      return next;
    });
  };

  // -----------------------------------------------------------------------
  // Build all models for the Models tab
  // -----------------------------------------------------------------------
  function getAllModels(): ModelCapability[] {
    const allCards: ModelCapability[] = [];
    const seenKeys = new Set<string>();

    // Always show all pre-populated model cards from all providers
    for (const [providerType, cards] of Object.entries(PROVIDER_MODEL_CARDS)) {
      for (const card of cards) {
        const key = `${providerType}:${card.name}`;
        if (!seenKeys.has(key)) {
          seenKeys.add(key);
          allCards.push(card);
        }
      }
    }

    // Add discovered models from configured engines that aren't already known
    for (const engine of engines) {
      const discoveredNames = engine.discovered_models || [];
      const knownNames = new Set((PROVIDER_MODEL_CARDS[engine.engine_type] || []).map(c => c.name));
      for (const m of discoveredNames) {
        const key = `${engine.engine_type}:${m}`;
        if (!seenKeys.has(key) && !knownNames.has(m)) {
          seenKeys.add(key);
          allCards.push({
            name: m, displayName: m, provider: engine.engine_type,
            tier: 'medium', multimodal: false, code: false, reasoning: false,
            structured_output: false, long_context: false, context_window: 0, best_for: [],
          });
        }
      }
    }

    return allCards;
  }

  function getFilteredModels(): ModelCapability[] {
    let models = getAllModels();

    // Search filter
    if (modelSearch.trim()) {
      const q = modelSearch.toLowerCase();
      models = models.filter(m =>
        m.name.toLowerCase().includes(q) ||
        m.displayName.toLowerCase().includes(q) ||
        (PROVIDER_DISPLAY_NAMES[m.provider] || m.provider).toLowerCase().includes(q) ||
        m.best_for.some(b => b.toLowerCase().includes(q))
      );
    }

    // Capability filter
    if (capabilityFilter !== 'all') {
      if (capabilityFilter === 'embedding') {
        models = models.filter(m => m.tier === 'embedding');
      } else {
        models = models.filter(m => m[capabilityFilter]);
      }
    }

    return models;
  }

  function groupModels(models: ModelCapability[]): { label: string; models: ModelCapability[] }[] {
    if (modelGroupBy === 'provider') {
      const groups = new Map<string, ModelCapability[]>();
      for (const m of models) {
        const key = m.provider;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push(m);
      }
      return Array.from(groups.entries()).map(([key, models]) => ({
        label: PROVIDER_DISPLAY_NAMES[key] || key,
        models,
      }));
    }

    if (modelGroupBy === 'tier') {
      const tierOrder = ['large', 'medium', 'small', 'embedding'];
      const groups = new Map<string, ModelCapability[]>();
      for (const tier of tierOrder) groups.set(tier, []);
      for (const m of models) {
        if (!groups.has(m.tier)) groups.set(m.tier, []);
        groups.get(m.tier)!.push(m);
      }
      return Array.from(groups.entries())
        .filter(([, models]) => models.length > 0)
        .map(([key, models]) => ({
          label: key.charAt(0).toUpperCase() + key.slice(1),
          models,
        }));
    }

    // Group by capability
    const capGroups: { label: string; filter: (m: ModelCapability) => boolean }[] = [
      { label: 'Vision / Multimodal', filter: m => m.multimodal },
      { label: 'Reasoning', filter: m => m.reasoning },
      { label: 'Code', filter: m => m.code },
      { label: 'Long Context', filter: m => m.long_context },
      { label: 'Structured Output', filter: m => m.structured_output },
      { label: 'Embedding', filter: m => m.tier === 'embedding' },
    ];
    const result: { label: string; models: ModelCapability[] }[] = [];
    const seen = new Set<string>();
    for (const g of capGroups) {
      const matched = models.filter(m => g.filter(m) && !seen.has(`${m.provider}:${m.name}`));
      if (matched.length > 0) {
        for (const m of matched) seen.add(`${m.provider}:${m.name}`);
        result.push({ label: g.label, models: matched });
      }
    }
    // Uncategorized
    const remaining = models.filter(m => !seen.has(`${m.provider}:${m.name}`));
    if (remaining.length > 0) result.push({ label: 'Other', models: remaining });
    return result;
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 text-primary-400 animate-spin mr-3" />
        <span className="text-white/60 text-sm">Loading Model Garden...</span>
      </div>
    );
  }

  const modelsByProvider = allModelNames.reduce<Record<string, string[]>>((acc, m) => {
    if (!acc[m.provider]) acc[m.provider] = [];
    acc[m.provider].push(m.name);
    return acc;
  }, {});
  for (const names of Object.values(modelsByProvider)) names.sort();

  const allModelsFlat = getAllModels();
  const totalModels = allModelsFlat.length;
  const filteredModels = getFilteredModels();
  const groupedModels = groupModels(filteredModels);

  return (
    <div className="space-y-6">
      {error && (
        <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <span className="text-red-300 text-sm">{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex items-center gap-1.5 p-1.5 bg-white/5 rounded-xl">
        {([
          { id: 'providers' as const, label: 'Providers', icon: Flower2, count: engines.length },
          { id: 'models' as const, label: 'Models', icon: Cpu, count: totalModels },
          { id: 'routing' as const, label: 'Smart Routing', icon: Zap, count: Object.keys(routing).length },
        ]).map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
                : 'text-white/50 hover:text-white/70 hover:bg-white/5'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label} {tab.count > 0 && `(${tab.count})`}
          </button>
        ))}
        <div className="ml-auto">
          <button
            onClick={() => fetchData(true)}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-primary-400 transition-colors hover:bg-white/10"
            disabled={refreshing}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* ================================================================= */}
      {/* PROVIDERS TAB                                                     */}
      {/* ================================================================= */}
      {activeTab === 'providers' && (
        <div className="space-y-8">
          {/* Provider Catalog */}
          <div>
            <h3 className="text-sm font-semibold text-white/40 uppercase tracking-wider mb-4 flex items-center gap-2">
              <Flower2 className="w-4 h-4" /> Provider Catalog
            </h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {providers.map(provider => {
                const isConfigured = configuredTypes.has(provider.engine_type);
                return (
                  <div
                    key={provider.engine_type}
                    className="rounded-xl border border-white/10 bg-white/5 p-4 transition-all duration-200 hover:bg-white/10"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-3">
                        <ProviderIcon icon={provider.icon} className="w-5 h-5 text-white/60" />
                        <div>
                          <h4 className="text-sm font-semibold text-white">{provider.display_name}</h4>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs border mt-1 ${categoryBadge(provider.category)}`}>
                            {provider.category}
                          </span>
                        </div>
                      </div>
                      {isConfigured ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                          <Check className="w-3 h-3" /> Configured
                        </span>
                      ) : (
                        <button
                          onClick={() => openAddModal(provider)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg transition-all"
                        >
                          <Plus className="w-3 h-3" /> Add
                        </button>
                      )}
                    </div>
                    <p className="mt-2 text-xs text-white/40 line-clamp-2">{provider.description}</p>
                    {provider.requires_api_key && (
                      <p className="mt-1.5 text-xs text-amber-400/60">Requires API key</p>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* My Providers */}
          {engines.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-white/40 uppercase tracking-wider mb-4 flex items-center gap-2">
                <Plug className="w-4 h-4" /> My Providers ({engines.length})
              </h3>
              <div className="space-y-2">
                {engines.map(engine => {
                  const isExpanded = expandedId === engine.engine_id;
                  return (
                    <div key={engine.engine_id} className="rounded-xl border border-white/10 bg-white/5">
                      <div className="flex items-center gap-4 px-4 py-3">
                        <button onClick={() => setExpandedId(isExpanded ? null : engine.engine_id)} className="text-white/40 hover:text-white/60">
                          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </button>
                        <ProviderIcon icon={engine.engine_type} className="w-4 h-4 text-white/50" />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm font-medium text-white">{engine.name}</span>
                          <span className="text-xs text-white/30 ml-2">{engine.engine_type}</span>
                        </div>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs border ${statusBadge(engine.last_test_status)}`}>
                          {statusLabel(engine.last_test_status)}
                        </span>
                        {engine.discovered_models.length > 0 && (
                          <span className="text-xs text-white/40">{engine.discovered_models.length} models</span>
                        )}
                        <div className="flex items-center gap-1">
                          <button onClick={() => handleTest(engine.engine_id)} disabled={testingId === engine.engine_id} className="p-1.5 rounded-lg text-white/40 hover:text-white/70 hover:bg-white/10 transition-colors disabled:opacity-50" title="Test Connection">
                            {testingId === engine.engine_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plug className="w-3.5 h-3.5" />}
                          </button>
                          <button onClick={() => handleDiscover(engine.engine_id)} disabled={discoveringId === engine.engine_id} className="p-1.5 rounded-lg text-white/40 hover:text-white/70 hover:bg-white/10 transition-colors disabled:opacity-50" title="Discover Models">
                            {discoveringId === engine.engine_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                          </button>
                          <button onClick={() => openEditModal(engine)} className="p-1.5 rounded-lg text-white/40 hover:text-white/70 hover:bg-white/10 transition-colors" title="Edit">
                            <RefreshCw className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => handleDelete(engine.engine_id)} className="p-1.5 rounded-lg text-white/40 hover:text-red-400 hover:bg-red-500/10 transition-colors" title="Delete">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      {isExpanded && (
                        <div className="px-4 pb-3 border-t border-white/5 pt-3">
                          {engine.last_tested_at && (
                            <p className="text-xs text-white/30 mb-2">Last tested: {new Date(engine.last_tested_at).toLocaleString()}</p>
                          )}
                          {engine.discovered_models.length > 0 ? (
                            <div>
                              <p className="text-xs text-white/40 mb-1.5">Discovered models ({engine.discovered_models.length}):</p>
                              <div className="flex flex-wrap gap-1.5">
                                {engine.discovered_models.slice(0, 30).map(m => (
                                  <span key={m} className="px-2 py-0.5 rounded-md bg-white/5 text-xs text-white/60 font-mono">{m}</span>
                                ))}
                                {engine.discovered_models.length > 30 && (
                                  <span className="text-xs text-white/30">+{engine.discovered_models.length - 30} more</span>
                                )}
                              </div>
                            </div>
                          ) : (
                            <p className="text-xs text-white/30">No models discovered yet. Click the search icon to discover.</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ================================================================= */}
      {/* MODELS TAB                                                        */}
      {/* ================================================================= */}
      {activeTab === 'models' && (
        <div className="space-y-6">
          {totalModels === 0 ? (
            <div className="text-center py-12">
              <Cpu className="w-8 h-8 text-white/20 mx-auto mb-3" />
              <p className="text-white/40 text-sm">No models available.</p>
            </div>
          ) : (
            <>
              {/* Search & Filter Bar */}
              <div className="flex flex-wrap items-center gap-3">
                <div className="relative flex-1 min-w-[200px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input
                    type="text"
                    value={modelSearch}
                    onChange={e => setModelSearch(e.target.value)}
                    placeholder="Search models, providers, capabilities..."
                    className="w-full rounded-xl border border-white/10 bg-white/5 pl-10 pr-4 py-2.5 text-sm text-white outline-none focus:border-primary-500/50 focus:ring-2 focus:ring-primary-500/20"
                  />
                  {modelSearch && (
                    <button onClick={() => setModelSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>

                {/* Group By */}
                <div className="flex items-center gap-1.5 p-1 bg-white/5 rounded-lg">
                  {([
                    { id: 'provider' as const, label: 'Provider' },
                    { id: 'capability' as const, label: 'Capability' },
                    { id: 'tier' as const, label: 'Tier' },
                  ]).map(g => (
                    <button
                      key={g.id}
                      onClick={() => setModelGroupBy(g.id)}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                        modelGroupBy === g.id
                          ? 'bg-primary-500/30 text-primary-300'
                          : 'text-white/40 hover:text-white/60 hover:bg-white/5'
                      }`}
                    >
                      {g.label}
                    </button>
                  ))}
                </div>

                {/* Capability Filter */}
                <select
                  value={capabilityFilter}
                  onChange={e => setCapabilityFilter(e.target.value as CapabilityFilter)}
                  className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white outline-none focus:border-primary-500/50"
                  style={{ colorScheme: 'dark' }}
                >
                  <option value="all">All Capabilities</option>
                  <option value="multimodal">Vision / Multimodal</option>
                  <option value="reasoning">Reasoning</option>
                  <option value="code">Code</option>
                  <option value="long_context">Long Context</option>
                  <option value="structured_output">Structured Output</option>
                  <option value="embedding">Embedding</option>
                </select>

                <span className="text-xs text-white/30">
                  {filteredModels.length} of {totalModels} models
                </span>
              </div>

              {/* Grouped Model Cards */}
              {filteredModels.length === 0 ? (
                <div className="text-center py-8">
                  <Search className="w-6 h-6 text-white/20 mx-auto mb-2" />
                  <p className="text-white/40 text-sm">No models match your search.</p>
                </div>
              ) : (
                groupedModels.map(group => (
                  <div key={group.label}>
                    <h3 className="text-sm font-semibold text-white/40 uppercase tracking-wider mb-4 flex items-center gap-2">
                      {modelGroupBy === 'provider' && <ProviderIcon icon={group.models[0]?.provider || ''} className="w-4 h-4" />}
                      {modelGroupBy === 'capability' && <Zap className="w-4 h-4" />}
                      {modelGroupBy === 'tier' && <Cpu className="w-4 h-4" />}
                      {group.label} ({group.models.length})
                    </h3>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {group.models.map(m => (
                        <div
                          key={`${m.provider}:${m.name}`}
                          className="rounded-xl border border-white/10 bg-white/5 p-4 transition-all duration-200 hover:bg-white/10"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              <ProviderIcon icon={m.provider} className="w-4 h-4 text-white/40 flex-shrink-0" />
                              <h4 className="text-sm font-semibold text-white truncate">{m.displayName}</h4>
                            </div>
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs border flex-shrink-0 ${tierBadge(m.tier)}`}>
                              {m.tier}
                            </span>
                          </div>
                          {m.name !== m.displayName && (
                            <p className="mt-1 text-xs text-white/30 font-mono truncate">{m.name}</p>
                          )}
                          <div className="mt-1 flex items-center gap-2">
                            {modelGroupBy !== 'provider' && (
                              <span className="text-xs text-white/30">{PROVIDER_DISPLAY_NAMES[m.provider] || m.provider}</span>
                            )}
                            {m.context_window > 0 && (
                              <span className="text-xs text-white/50">{formatContextWindow(m.context_window)} ctx</span>
                            )}
                          </div>
                          <div className="mt-2.5 flex flex-wrap gap-1.5">
                            {m.multimodal && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border bg-purple-500/20 text-purple-400 border-purple-500/30">
                                <Eye className="h-3 w-3" /> vision
                              </span>
                            )}
                            {m.structured_output && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border bg-blue-500/20 text-blue-400 border-blue-500/30">
                                <FileText className="h-3 w-3" /> structured
                              </span>
                            )}
                            {m.code && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                                <Code className="h-3 w-3" /> code
                              </span>
                            )}
                            {m.long_context && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border bg-orange-500/20 text-orange-400 border-orange-500/30">
                                <Globe className="h-3 w-3" /> long ctx
                              </span>
                            )}
                            {m.reasoning && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border bg-amber-500/20 text-amber-400 border-amber-500/30">
                                <Zap className="h-3 w-3" /> reasoning
                              </span>
                            )}
                          </div>
                          {m.best_for.length > 0 && (
                            <p className="mt-2 text-xs text-white/40">
                              Best for: {m.best_for.slice(0, 3).join(', ')}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </>
          )}
        </div>
      )}

      {/* ================================================================= */}
      {/* ROUTING TAB                                                       */}
      {/* ================================================================= */}
      {activeTab === 'routing' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-white/10 bg-white/5">
            {saveMessage && (
              <div className="flex items-center justify-end px-5 pt-4">
                <span className={`flex items-center gap-1.5 text-sm font-medium ${saveMessage.includes('failed') ? 'text-red-400' : 'text-emerald-400'}`}>
                  {saveMessage.includes('failed') ? <AlertCircle className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
                  {saveMessage}
                </span>
              </div>
            )}
            <div className="overflow-x-auto">
              {Object.entries(routingCategories).map(([category, dataTypes]) => {
                const isExpanded = expandedRoutingCats.has(category);
                return (
                  <div key={category}>
                    <button
                      onClick={() => toggleRoutingCat(category)}
                      className="flex w-full items-center gap-2.5 border-b border-white/5 px-5 py-3.5 text-left transition-colors duration-200 hover:bg-white/5"
                    >
                      {isExpanded ? <ChevronDown className="h-4 w-4 text-white/50" /> : <ChevronRight className="h-4 w-4 text-white/50" />}
                      <span className="text-base font-semibold text-white">{category}</span>
                      <span className="text-sm text-white/40">({dataTypes.length})</span>
                    </button>
                    {isExpanded && (
                      <table className="table-modern">
                        <thead>
                          <tr>
                            <th>Data Type</th>
                            <th>Primary Model</th>
                            <th>Fallback Model</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dataTypes.filter(dt => routing[dt]).map(dt => {
                            const entry = routing[dt];
                            const edit = edits[dt];
                            const currentPrimary = edit?.primary_model || '';
                            const currentFallback = edit?.fallback_model || '';
                            const isOverridden = !!edit && (!!edit.primary_model || !!edit.fallback_model);
                            return (
                              <tr key={dt} className={isOverridden ? 'bg-amber-500/5' : ''}>
                                <td className="font-medium text-white">{dt}</td>
                                <td>
                                  <select
                                    value={currentPrimary}
                                    onChange={e => handlePrimaryChange(dt, e.target.value)}
                                    className="w-full max-w-[280px] rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none transition-all duration-300 focus:border-primary-500/50 focus:bg-white/10 focus:ring-2 focus:ring-primary-500/20"
                                    style={{ colorScheme: 'dark' }}
                                  >
                                    <option value="">{entry.suggested_primary || '(auto)'}</option>
                                    {Object.entries(modelsByProvider).map(([provider, names]) => (
                                      <optgroup key={provider} label={provider}>
                                        {names.map(name => <option key={name} value={name}>{name}</option>)}
                                      </optgroup>
                                    ))}
                                  </select>
                                </td>
                                <td>
                                  <select
                                    value={currentFallback}
                                    onChange={e => handleFallbackChange(dt, e.target.value)}
                                    className="w-full max-w-[280px] rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none transition-all duration-300 focus:border-primary-500/50 focus:bg-white/10 focus:ring-2 focus:ring-primary-500/20"
                                    style={{ colorScheme: 'dark' }}
                                  >
                                    <option value="">{entry.suggested_fallback || '(auto)'}</option>
                                    {Object.entries(modelsByProvider).map(([provider, names]) => (
                                      <optgroup key={provider} label={provider}>
                                        {names.map(name => <option key={name} value={name}>{name}</option>)}
                                      </optgroup>
                                    ))}
                                  </select>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Routing actions */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleRoutingSave}
              disabled={!dirty || saving}
              className="btn-premium flex items-center gap-2 disabled:opacity-50"
            >
              <span className="relative z-10 flex items-center gap-2">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save Overrides
              </span>
            </button>
            <button
              onClick={handleRoutingReset}
              disabled={saving}
              className="btn-secondary flex items-center gap-2 disabled:opacity-50"
            >
              <RotateCcw className="h-4 w-4" />
              Reset to Defaults
            </button>
          </div>
        </div>
      )}

      {/* ================================================================= */}
      {/* Add/Edit Provider Modal                                           */}
      {/* ================================================================= */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-lg mx-4 rounded-2xl border border-white/10 bg-[#1a1a2e] shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
              <h3 className="text-lg font-semibold text-white">
                {editingEngine ? 'Edit Provider' : 'Add Provider'}
              </h3>
              <button onClick={closeModal} className="text-white/40 hover:text-white/70">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 py-5 space-y-4">
              {!editingEngine && (
                <div>
                  <label className="block text-xs font-medium text-white/50 mb-1.5">Provider</label>
                  <select
                    value={formEngineType}
                    onChange={(e) => {
                      const p = providers.find(pr => pr.engine_type === e.target.value);
                      if (p) {
                        setModalProvider(p);
                        setFormEngineType(p.engine_type);
                        setFormName(p.display_name);
                        setFormBaseUrl(p.default_base_url || '');
                      }
                    }}
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none focus:border-primary-500/50 focus:ring-2 focus:ring-primary-500/20"
                    style={{ colorScheme: 'dark' }}
                  >
                    {providers.map(p => (
                      <option key={p.engine_type} value={p.engine_type}>{p.display_name}</option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-xs font-medium text-white/50 mb-1.5">Display Name</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none focus:border-primary-500/50 focus:ring-2 focus:ring-primary-500/20"
                  placeholder="My OpenAI"
                />
              </div>
              {/* API Key — always show, mark as optional if not required */}
              <div>
                <label className="block text-xs font-medium text-white/50 mb-1.5">
                  API Key {modalProvider?.requires_api_key === false && <span className="text-white/30">(optional)</span>}
                </label>
                <div className="relative">
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    value={formApiKey}
                    onChange={(e) => setFormApiKey(e.target.value)}
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 pr-10 text-sm text-white outline-none focus:border-primary-500/50 focus:ring-2 focus:ring-primary-500/20"
                    placeholder={editingEngine?.has_api_key ? 'Key configured (leave blank to keep)' : (modalProvider?.api_key_placeholder || 'Enter API key')}
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60"
                  >
                    {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-white/50 mb-1.5">Base URL</label>
                <input
                  type="text"
                  value={formBaseUrl}
                  onChange={(e) => setFormBaseUrl(e.target.value)}
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none focus:border-primary-500/50 focus:ring-2 focus:ring-primary-500/20"
                  placeholder={modalProvider?.default_base_url || 'https://api.example.com'}
                />
              </div>
              {editingEngine && (
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleModalTest}
                    disabled={modalTesting}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-white/10 text-white/70 hover:bg-white/20 transition-colors disabled:opacity-50"
                  >
                    {modalTesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plug className="w-4 h-4" />}
                    Test Connection
                  </button>
                  {modalTestResult && (
                    <span className={`text-sm ${modalTestResult.ok ? 'text-emerald-400' : 'text-red-400'}`}>
                      {modalTestResult.ok
                        ? `Connected (${modalTestResult.latency_ms}ms)`
                        : (modalTestResult.error || 'Connection failed')}
                    </span>
                  )}
                </div>
              )}
            </div>
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/10">
              <button onClick={closeModal} className="px-4 py-2 rounded-lg text-sm font-medium text-white/50 hover:text-white/70 hover:bg-white/5 transition-colors">
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={modalSaving || !formName}
                className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg hover:shadow-xl transition-all disabled:opacity-50"
              >
                {modalSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

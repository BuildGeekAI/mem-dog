'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Brain, Eye, MessageSquare, RefreshCw, Loader2, AlertCircle,
  Sparkles, Clock, ChevronDown, ChevronUp, Cpu, FileText, Trash2, Send,
  Wand2, Check, Plus, Layers,
} from 'lucide-react';
import Link from 'next/link';
import {
  getDataViewpoints, deleteViewpoint, queryAI, getCurrentUserId, DEFAULT_USER_ID,
  listPrompts, createPrompt, getAvailableEngines,
  createViewpoint, createEmbedding, getDataEmbeddings, deleteDataEmbeddings, getSystemAIConfig,
} from '@/lib/api';
import ViewpointContent from '@/components/ViewpointContent';

interface DataAIProps {
  dataId: string;
}

type AISubTab = 'query' | 'generate' | 'viewpoints' | 'embeddings';

export default function DataAI({ dataId }: DataAIProps) {
  const [expanded, setExpanded] = useState(false);
  const [subTab, setSubTab] = useState<AISubTab>('query');

  const [viewpoints, setViewpoints] = useState<any[]>([]);
  const [loadingVP, setLoadingVP] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Embeddings state
  const [dataEmbeddings, setDataEmbeddings] = useState<any[]>([]);
  const [loadingEmb, setLoadingEmb] = useState(false);

  // AI Query state
  const [queryText, setQueryText] = useState('');
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryResult, setQueryResult] = useState<any>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  // Generate tab state
  const [prompts, setPrompts] = useState<any[]>([]);
  const [engines, setEngines] = useState<any[]>([]);
  const [loadingPrompts, setLoadingPrompts] = useState(false);
  const [loadingEngines, setLoadingEngines] = useState(false);

  const [promptMode, setPromptMode] = useState<'existing' | 'custom'>('existing');
  const [selectedPromptId, setSelectedPromptId] = useState('');
  const [customPromptName, setCustomPromptName] = useState('');
  const [customPromptTemplate, setCustomPromptTemplate] = useState('');

  const [selectedEngineType, setSelectedEngineType] = useState('');
  const [selectedModel, setSelectedModel] = useState('');

  const [genVPLoading, setGenVPLoading] = useState(false);
  const [genEmbLoading, setGenEmbLoading] = useState(false);
  const [genSuccess, setGenSuccess] = useState<string | null>(null);
  const [genError, setGenError] = useState<string | null>(null);

  // AI system config
  const [aiConfig, setAiConfig] = useState<any>(null);
  const [aiConfigLoading, setAiConfigLoading] = useState(false);
  const aiReady = aiConfig?.system_ai_available === true;

  const fetchAIConfig = useCallback(async () => {
    try {
      setAiConfigLoading(true);
      const config = await getSystemAIConfig();
      setAiConfig(config);
    } catch {
      setAiConfig({ system_ai_available: false, message: 'Failed to check AI configuration.' });
    } finally {
      setAiConfigLoading(false);
    }
  }, []);

  const fetchViewpoints = useCallback(async () => {
    try {
      setLoadingVP(true);
      setError(null);
      const data = await getDataViewpoints(dataId);
      setViewpoints(Array.isArray(data) ? data : []);
    } catch {
      setViewpoints([]);
    } finally {
      setLoadingVP(false);
    }
  }, [dataId]);

  const fetchDataEmbeddings = useCallback(async () => {
    try {
      setLoadingEmb(true);
      const data = await getDataEmbeddings(dataId);
      setDataEmbeddings(Array.isArray(data) ? data : []);
    } catch {
      setDataEmbeddings([]);
    } finally {
      setLoadingEmb(false);
    }
  }, [dataId]);

  const fetchPrompts = useCallback(async () => {
    try {
      setLoadingPrompts(true);
      const data = await listPrompts();
      setPrompts(Array.isArray(data) ? data : []);
    } catch {
      setPrompts([]);
    } finally {
      setLoadingPrompts(false);
    }
  }, []);

  const fetchEngines = useCallback(async () => {
    try {
      setLoadingEngines(true);
      const data = await getAvailableEngines();
      setEngines(Array.isArray(data) ? data : []);
    } catch {
      setEngines([]);
    } finally {
      setLoadingEngines(false);
    }
  }, []);

  useEffect(() => {
    if (!expanded) return;
    if (!aiConfig) fetchAIConfig();
  }, [expanded, aiConfig, fetchAIConfig]);

  useEffect(() => {
    if (!expanded || !aiReady) return;
    if (subTab === 'viewpoints') fetchViewpoints();
    if (subTab === 'embeddings') fetchDataEmbeddings();
    if (subTab === 'generate') {
      fetchPrompts();
      fetchEngines();
    }
  }, [expanded, aiReady, subTab, fetchViewpoints, fetchDataEmbeddings, fetchPrompts, fetchEngines]);

  const handleDeleteViewpoint = async (vpId: string) => {
    if (!confirm('Delete this viewpoint?')) return;
    try {
      await deleteViewpoint(vpId);
      setViewpoints(prev => prev.filter((v: any) => v.viewpoint_id !== vpId));
    } catch (err: any) {
      setError(err.message || 'Failed to delete viewpoint');
    }
  };

  const handleDeleteEmbedding = async (embDataId: string) => {
    if (!confirm('Delete all embeddings for this data item?')) return;
    try {
      await deleteDataEmbeddings(embDataId);
      setDataEmbeddings(prev => prev.filter((e: any) => e.data_id !== embDataId));
    } catch (err: any) {
      setError(err.message || 'Failed to delete embedding');
    }
  };

  const selectedEngine = engines.find((e: any) => e.engine_type === selectedEngineType);
  const completionModels: string[] = selectedEngine?.models?.completions ?? [];
  const embeddingModels: string[] = selectedEngine?.models?.embeddings ?? [];
  const allModels = [...new Set([...completionModels, ...embeddingModels])];

  const clearGenFeedback = () => {
    setGenSuccess(null);
    setGenError(null);
  };

  const handleGenerateViewpoint = async () => {
    clearGenFeedback();
    try {
      setGenVPLoading(true);
      let promptId = selectedPromptId;

      if (promptMode === 'custom') {
        if (!customPromptName.trim() || !customPromptTemplate.trim()) {
          setGenError('Please provide both a prompt name and template.');
          return;
        }
        const newPrompt = await createPrompt({
          name: customPromptName.trim(),
          template: customPromptTemplate.trim(),
          data_id: dataId,
        });
        promptId = newPrompt.prompt_id || newPrompt.id;
        await fetchPrompts();
      }

      if (!promptId) {
        setGenError('Please select or create a prompt first.');
        return;
      }

      await createViewpoint({
        data_id: dataId,
        prompt_id: promptId,
        engine_id: selectedEngineType || undefined,
      });
      setGenSuccess('Viewpoint generated successfully!');
      fetchViewpoints();
    } catch (err: any) {
      setGenError(err?.response?.data?.detail || err.message || 'Failed to generate viewpoint');
    } finally {
      setGenVPLoading(false);
    }
  };

  const handleGenerateEmbedding = async () => {
    clearGenFeedback();
    try {
      setGenEmbLoading(true);
      await createEmbedding({
        data_id: dataId,
        engine_id: selectedEngineType || undefined,
        model: selectedModel || undefined,
      });
      setGenSuccess('Embedding generated successfully!');
    } catch (err: any) {
      setGenError(err?.response?.data?.detail || err.message || 'Failed to generate embedding');
    } finally {
      setGenEmbLoading(false);
    }
  };

  const handleQuery = async () => {
    if (!queryText.trim()) return;
    try {
      setQueryLoading(true);
      setQueryError(null);
      setQueryResult(null);
      const result = await queryAI({
        query: queryText.trim(),
        user: getCurrentUserId() || DEFAULT_USER_ID,
        data_ids: [dataId],
      });
      setQueryResult(result);
    } catch (err: any) {
      setQueryError(err?.response?.data?.detail || err.message || 'AI query failed');
    } finally {
      setQueryLoading(false);
    }
  };

  const handleQueryKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const vpCount = viewpoints.length;

  return (
    <div className="glass-card overflow-hidden mt-6">
      {/* Collapsible Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-6 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div className="text-left">
            <h2 className="text-xl font-semibold text-white">AI Application</h2>
            <p className="text-sm text-white/50">Generate, query &amp; view AI insights for this data</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {!expanded && vpCount > 0 && (
            <div className="flex items-center gap-2 text-xs text-white/40">
              <span className="px-2 py-1 rounded-md bg-violet-500/10 border border-violet-500/30 text-violet-400">{vpCount} viewpoint{vpCount !== 1 ? 's' : ''}</span>
            </div>
          )}
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-white/50" />
          ) : (
            <ChevronDown className="w-5 h-5 text-white/50" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-white/10">
          {/* Loading AI config */}
          {aiConfigLoading && (
            <div className="flex items-center justify-center gap-3 py-12">
              <Loader2 className="w-5 h-5 text-violet-400 animate-spin" />
              <span className="text-sm text-white/50">Checking AI configuration...</span>
            </div>
          )}

          {/* AI not configured */}
          {!aiConfigLoading && !aiReady && (
            <div className="p-8 flex flex-col items-center text-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center">
                <AlertCircle className="w-7 h-7 text-amber-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white mb-1">AI Not Configured</h3>
                <p className="text-sm text-white/50 max-w-md">
                  {aiConfig?.message || 'The AI system is not set up yet. Please configure an AI engine and API keys before using AI features.'}
                </p>
              </div>
              <Link
                href="/?tab=ai"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white font-medium text-sm hover:opacity-90 transition-opacity"
              >
                <Cpu className="w-4 h-4" />
                Go to AI Settings
              </Link>
              <button
                onClick={fetchAIConfig}
                className="text-xs text-white/40 hover:text-white/60 transition-colors flex items-center gap-1"
              >
                <RefreshCw className="w-3 h-3" />
                Re-check
              </button>
            </div>
          )}

          {/* AI ready — show tabs and content */}
          {!aiConfigLoading && aiReady && (
            <>
          {/* Sub-tabs */}
          <div className="flex border-b border-white/10 px-6">
            {([
              { id: 'query' as const, label: 'AI Query', icon: MessageSquare },
              { id: 'generate' as const, label: 'Generate', icon: Wand2 },
              { id: 'viewpoints' as const, label: 'Viewpoints', icon: Eye },
              { id: 'embeddings' as const, label: 'Embeddings', icon: Layers },
            ]).map(tab => (
              <button
                key={tab.id}
                onClick={() => setSubTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  subTab === tab.id
                    ? 'border-violet-400 text-violet-400'
                    : 'border-transparent text-white/50 hover:text-white/70'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Error */}
          {error && (
            <div className="mx-6 mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <div className="p-6">
            {/* AI Query Tab */}
            {subTab === 'query' && (
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <div className="flex-1">
                    <textarea
                      value={queryText}
                      onChange={(e) => setQueryText(e.target.value)}
                      onKeyDown={handleQueryKeyDown}
                      placeholder="Ask a question about this data... (Enter to send)"
                      rows={3}
                      className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 resize-none text-sm"
                    />
                  </div>
                  <button
                    onClick={handleQuery}
                    disabled={queryLoading || !queryText.trim()}
                    className="mt-1 px-4 py-3 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white font-medium hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {queryLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                  </button>
                </div>

                {queryError && (
                  <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {queryError}
                  </div>
                )}

                {queryResult && (
                  <div className="space-y-3">
                    <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                      <div className="flex items-center gap-2 mb-3">
                        <Sparkles className="w-4 h-4 text-violet-400" />
                        <span className="text-sm font-medium text-violet-400">AI Response</span>
                        {queryResult.ai_signature && (
                          <span className="text-xs text-white/40 ml-auto">
                            {queryResult.ai_signature.model_name || queryResult.model || 'AI'}
                          </span>
                        )}
                      </div>
                      <div className="text-white/80 text-sm leading-relaxed whitespace-pre-wrap">
                        {queryResult.answer || queryResult.response || 'No response received.'}
                      </div>
                    </div>

                    {queryResult.sources && queryResult.sources.length > 0 && (
                      <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                        <span className="text-xs font-medium text-white/40 uppercase tracking-wider">Sources</span>
                        <div className="mt-2 space-y-2">
                          {queryResult.sources.map((src: any, i: number) => (
                            <div key={i} className="text-xs text-white/60 p-2 rounded bg-white/5">
                              <span className="text-white/40">Data:</span> {src.data_id?.substring(0, 16)}...
                              {src.score !== undefined && (
                                <span className="ml-2 text-white/40">Score: {(src.score * 100).toFixed(0)}%</span>
                              )}
                              {src.chunk_text && (
                                <p className="mt-1 text-white/50 line-clamp-2">{src.chunk_text}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {!queryResult && !queryError && !queryLoading && (
                  <div className="text-center py-8 text-white/30">
                    <MessageSquare className="w-8 h-8 mx-auto mb-3 opacity-50" />
                    <p className="text-sm">Ask a question about this data item.</p>
                    <p className="text-xs mt-1">The AI will analyze the content and provide insights.</p>
                  </div>
                )}
              </div>
            )}

            {/* Generate Tab */}
            {subTab === 'generate' && (
              <div className="space-y-6">
                {/* Feedback */}
                {genSuccess && (
                  <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm flex items-center gap-2">
                    <Check className="w-4 h-4 flex-shrink-0" />
                    {genSuccess}
                  </div>
                )}
                {genError && (
                  <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    {genError}
                  </div>
                )}

                {/* Prompt Section */}
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-white/40 uppercase tracking-wider">Prompt</h3>
                  <div className="flex gap-2">
                    <button
                      onClick={() => { setPromptMode('existing'); clearGenFeedback(); }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        promptMode === 'existing'
                          ? 'bg-violet-500/20 border border-violet-500/40 text-violet-400'
                          : 'bg-white/5 border border-white/10 text-white/50 hover:text-white/70'
                      }`}
                    >
                      Use Existing
                    </button>
                    <button
                      onClick={() => { setPromptMode('custom'); clearGenFeedback(); }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1 ${
                        promptMode === 'custom'
                          ? 'bg-violet-500/20 border border-violet-500/40 text-violet-400'
                          : 'bg-white/5 border border-white/10 text-white/50 hover:text-white/70'
                      }`}
                    >
                      <Plus className="w-3 h-3" /> Custom
                    </button>
                  </div>

                  {promptMode === 'existing' ? (
                    <div>
                      {loadingPrompts ? (
                        <div className="flex items-center gap-2 text-white/40 text-sm py-2">
                          <Loader2 className="w-4 h-4 animate-spin" /> Loading prompts...
                        </div>
                      ) : prompts.length === 0 ? (
                        <p className="text-sm text-white/30 py-2">No prompts available. Create one using the Custom option or via AI Manager.</p>
                      ) : (
                        <select
                          value={selectedPromptId}
                          onChange={(e) => { setSelectedPromptId(e.target.value); clearGenFeedback(); }}
                          className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 appearance-none"
                        >
                          <option value="" className="bg-zinc-900">Select a prompt...</option>
                          {prompts.map((p: any) => (
                            <option key={p.prompt_id || p.id} value={p.prompt_id || p.id} className="bg-zinc-900">
                              {p.name}{p.data_id ? ' (data-specific)' : ' (global)'}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <input
                        type="text"
                        value={customPromptName}
                        onChange={(e) => setCustomPromptName(e.target.value)}
                        placeholder="Prompt name (e.g. Summarize, Extract Key Facts)"
                        className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50"
                      />
                      <textarea
                        value={customPromptTemplate}
                        onChange={(e) => setCustomPromptTemplate(e.target.value)}
                        placeholder={"Prompt template. Use {{content}} as placeholder for the data content.\n\nExample: Summarize the following content in 3 bullet points:\n\n{{content}}"}
                        rows={4}
                        className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 resize-none"
                      />
                    </div>
                  )}
                </div>

                {/* Engine / Model Section */}
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-white/40 uppercase tracking-wider">Engine &amp; Model</h3>
                  {loadingEngines ? (
                    <div className="flex items-center gap-2 text-white/40 text-sm py-2">
                      <Loader2 className="w-4 h-4 animate-spin" /> Loading engines...
                    </div>
                  ) : engines.length === 0 ? (
                    <p className="text-sm text-white/30 py-2">No AI engines available. Configure one in AI Manager.</p>
                  ) : (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-white/40 mb-1 block">Engine</label>
                        <select
                          value={selectedEngineType}
                          onChange={(e) => { setSelectedEngineType(e.target.value); setSelectedModel(''); clearGenFeedback(); }}
                          className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 appearance-none"
                        >
                          <option value="" className="bg-zinc-900">Default (system)</option>
                          {engines.map((eng: any) => (
                            <option key={eng.engine_type} value={eng.engine_type} className="bg-zinc-900">
                              {eng.name || eng.engine_type}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs text-white/40 mb-1 block">Model</label>
                        <select
                          value={selectedModel}
                          onChange={(e) => { setSelectedModel(e.target.value); clearGenFeedback(); }}
                          disabled={!selectedEngineType}
                          className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 disabled:opacity-40 disabled:cursor-not-allowed appearance-none"
                        >
                          <option value="" className="bg-zinc-900">{selectedEngineType ? 'Default model' : 'Select engine first'}</option>
                          {allModels.map((m: string) => (
                            <option key={m} value={m} className="bg-zinc-900">
                              {m}
                              {completionModels.includes(m) && embeddingModels.includes(m)
                                ? ' (completion + embedding)'
                                : completionModels.includes(m)
                                  ? ' (completion)'
                                  : ' (embedding)'}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-3 pt-2 border-t border-white/10">
                  <button
                    onClick={handleGenerateViewpoint}
                    disabled={genVPLoading || genEmbLoading || (promptMode === 'existing' && !selectedPromptId) || (promptMode === 'custom' && (!customPromptName.trim() || !customPromptTemplate.trim()))}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {genVPLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                    Generate Viewpoint
                  </button>
                  <button
                    onClick={handleGenerateEmbedding}
                    disabled={genVPLoading || genEmbLoading}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 text-white font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {genEmbLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Sparkles className="w-4 h-4" />
                    )}
                    Generate Embedding
                  </button>
                </div>

                {/* Idle Hint */}
                {!genSuccess && !genError && !genVPLoading && !genEmbLoading && (
                  <div className="text-center py-4 text-white/25">
                    <p className="text-xs">Select a prompt and engine, then generate a viewpoint or embedding for this data.</p>
                  </div>
                )}
              </div>
            )}

            {/* Viewpoints Tab */}
            {subTab === 'viewpoints' && (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-white/40 uppercase tracking-wider flex items-center gap-2">
                    <Eye className="w-4 h-4" /> Viewpoints ({vpCount})
                  </h3>
                  <button
                    onClick={fetchViewpoints}
                    disabled={loadingVP}
                    className="p-2 rounded-lg hover:bg-white/10 transition-colors text-white/40 hover:text-white/70"
                  >
                    <RefreshCw className={`w-4 h-4 ${loadingVP ? 'animate-spin' : ''}`} />
                  </button>
                </div>

                {loadingVP ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 text-violet-400 animate-spin" />
                  </div>
                ) : vpCount === 0 ? (
                  <div className="text-center py-8 text-white/30">
                    <Eye className="w-8 h-8 mx-auto mb-3 opacity-50" />
                    <p className="text-sm">No viewpoints for this data yet.</p>
                    <p className="text-xs mt-1">Viewpoints are AI-generated analyses and interpretations.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {viewpoints.map((vp: any) => (
                      <div key={vp.viewpoint_id || vp.id} className="p-4 rounded-xl bg-white/5 border border-white/10 hover:border-white/20 transition-colors">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <Sparkles className="w-4 h-4 text-violet-400" />
                            <span className="text-sm font-medium text-white">
                              {vp.ai_engine || 'AI'} / {vp.model || 'model'}
                            </span>
                            {vp.version && (
                              <span className="text-xs px-1.5 py-0.5 rounded bg-white/10 text-white/50">v{vp.version}</span>
                            )}
                          </div>
                          <button
                            onClick={() => handleDeleteViewpoint(vp.viewpoint_id || vp.id)}
                            className="p-1.5 rounded-lg hover:bg-red-500/20 text-white/30 hover:text-red-400 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        <ViewpointContent content={vp.output_content || vp.content || ''} />
                        <div className="flex items-center gap-3 mt-3 text-xs text-white/30">
                          {vp.prompt_id && (
                            <span className="flex items-center gap-1">
                              <FileText className="w-3 h-3" />
                              Prompt: {vp.prompt_id.substring(0, 12)}...
                            </span>
                          )}
                          {vp.created_at && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {formatDate(vp.created_at)}
                            </span>
                          )}
                          {vp.ai_signature && (
                            <span className="flex items-center gap-1">
                              <Cpu className="w-3 h-3" />
                              {vp.ai_signature.key_mode === 'system' ? 'System Key' : 'Custom Key'}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Embeddings Tab */}
            {subTab === 'embeddings' && (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-white/40 uppercase tracking-wider flex items-center gap-2">
                    <Layers className="w-4 h-4" /> Embeddings ({dataEmbeddings.length})
                  </h3>
                  <button
                    onClick={fetchDataEmbeddings}
                    disabled={loadingEmb}
                    className="p-2 rounded-lg hover:bg-white/10 transition-colors text-white/40 hover:text-white/70"
                  >
                    <RefreshCw className={`w-4 h-4 ${loadingEmb ? 'animate-spin' : ''}`} />
                  </button>
                </div>

                {loadingEmb ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 text-violet-400 animate-spin" />
                  </div>
                ) : dataEmbeddings.length === 0 ? (
                  <div className="text-center py-8 text-white/30">
                    <Layers className="w-8 h-8 mx-auto mb-3 opacity-50" />
                    <p className="text-sm">No embeddings for this data yet.</p>
                    <p className="text-xs mt-1">Generate embeddings from the Generate tab.</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {dataEmbeddings.map((emb: any) => {
                      return (
                        <div key={emb.data_id} className="flex items-center justify-between px-4 py-3 rounded-xl bg-white/5 border border-white/10 hover:border-white/20 transition-colors group">
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="w-8 h-8 rounded-lg bg-cyan-500/15 flex items-center justify-center flex-shrink-0">
                              <Layers className="w-4 h-4 text-cyan-400" />
                            </div>
                            <div className="min-w-0">
                              <span className="text-sm text-white/80 block">{emb.model || emb.embedding_model || 'model'}</span>
                              <div className="flex items-center gap-3 text-xs text-white/30">
                                {emb.dimensions != null && <span>{emb.dimensions}d</span>}
                                {emb.chunk_count != null && <span>{emb.chunk_count} chunks</span>}
                                {emb.ai_engine && <span className="uppercase">{emb.ai_engine}</span>}
                                {emb.created_at && (
                                  <span className="flex items-center gap-1">
                                    <Clock className="w-3 h-3" />
                                    {formatDate(emb.created_at)}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={() => handleDeleteEmbedding(emb.data_id)}
                            className="p-1.5 rounded-lg hover:bg-red-500/20 text-white/30 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

          </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

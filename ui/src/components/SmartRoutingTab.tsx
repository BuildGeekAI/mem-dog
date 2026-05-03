'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Cpu, RefreshCw, Save, RotateCcw, ChevronDown, ChevronRight,
  Eye, Zap, Code, FileText, Globe, Loader2, CheckCircle, AlertCircle,
} from 'lucide-react';
import {
  getOllamaCloudModels,
  getSmartRoutingConfig,
  getModelCatalog,
  getUserAvailableModels,
  updateUserAIPreferences,
  getCurrentUserId,
} from '@/lib/api';

interface ModelCard {
  name: string;
  tier: string;
  param_b: number;
  multimodal: boolean;
  structured_output: boolean;
  code: boolean;
  long_context: boolean;
  reasoning: boolean;
  context_window: number;
  best_for: string[];
  benchmark_scores: Record<string, number>;
  size: number;
  modified_at: string;
}

interface RoutingEntry {
  primary: string;
  fallback: string;
  suggested_primary: string;
  suggested_fallback: string;
  reason: string;
  is_override: boolean;
}

export default function SmartRoutingTab() {
  const [models, setModels] = useState<ModelCard[]>([]);
  const [routing, setRouting] = useState<Record<string, RoutingEntry>>({});
  const [categories, setCategories] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'models' | 'routing'>('models');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  // Edits: data_type -> { primary_model, fallback_model }
  const [edits, setEdits] = useState<Record<string, { primary_model: string; fallback_model: string }>>({});
  const [dirty, setDirty] = useState(false);

  const userId = getCurrentUserId();

  // All model names from all providers, grouped
  const [allModelNames, setAllModelNames] = useState<{ provider: string; name: string }[]>([]);

  const fetchData = useCallback(async (refresh = false) => {
    try {
      if (refresh) setRefreshing(true);
      else setLoading(true);
      setError(null);

      const [modelsRes, routingRes, catalogRes, availableRes] = await Promise.all([
        getOllamaCloudModels(refresh),
        getSmartRoutingConfig(userId),
        getModelCatalog().catch(() => ({ models: {} } as { models: Record<string, any> })),
        getUserAvailableModels(userId).catch(() => ({ providers: [] })),
      ]);

      setModels(modelsRes.models || []);
      setRouting(routingRes.routing || {});
      setCategories(routingRes.categories || modelsRes.categories || {});

      // Build unified model list — prefer user-configured providers from Model Garden
      const allModels: { provider: string; name: string }[] = [];
      const seenNames = new Set<string>();

      // User-configured + system providers from available-models endpoint
      for (const p of (availableRes.providers || [])) {
        for (const m of (p.models || [])) {
          const fullName = `${p.litellm_prefix}${m}`;
          if (!seenNames.has(fullName)) {
            seenNames.add(fullName);
            allModels.push({ provider: p.name, name: fullName });
          }
        }
      }

      // Ollama Cloud models (always include for routing)
      for (const m of (modelsRes.models || [])) {
        if (!seenNames.has(m.name)) {
          seenNames.add(m.name);
          allModels.push({ provider: 'Ollama Cloud', name: m.name });
        }
      }

      // Local Ollama models from catalog (self-hostable)
      for (const [_id, entry] of Object.entries(catalogRes.models || {})) {
        const catEntry = entry as { ollama_model?: string; family?: string };
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
          initialEdits[dt] = {
            primary_model: entry.primary,
            fallback_model: entry.fallback,
          };
        }
      }
      setEdits(initialEdits);
      setDirty(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load smart routing data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [userId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handlePrimaryChange = (dataType: string, model: string) => {
    const entry = routing[dataType];
    if (!entry) return;

    setEdits(prev => {
      const next = { ...prev };
      if (model === entry.suggested_primary || model === '') {
        // Removing override
        if (next[dataType]) {
          const { fallback_model } = next[dataType];
          if (!fallback_model || fallback_model === entry.suggested_fallback) {
            delete next[dataType];
          } else {
            next[dataType] = { primary_model: '', fallback_model };
          }
        }
      } else {
        next[dataType] = {
          primary_model: model,
          fallback_model: prev[dataType]?.fallback_model || '',
        };
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
          if (!primary_model || primary_model === entry.suggested_primary) {
            delete next[dataType];
          } else {
            next[dataType] = { primary_model, fallback_model: '' };
          }
        }
      } else {
        next[dataType] = {
          primary_model: prev[dataType]?.primary_model || '',
          fallback_model: model,
        };
      }
      return next;
    });
    setDirty(true);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setSaveMessage(null);
      // Build overrides: only include entries with actual overrides
      const overrides: Record<string, { primary_model: string; fallback_model: string }> = {};
      for (const [dt, edit] of Object.entries(edits)) {
        if (edit.primary_model || edit.fallback_model) {
          overrides[dt] = edit;
        }
      }
      await updateUserAIPreferences(userId, { smart_routing_overrides: overrides } as any);
      setSaveMessage('Routing overrides saved');
      setDirty(false);
      // Refresh to reflect saved state
      await fetchData();
    } catch (err: any) {
      setSaveMessage(`Save failed: ${err.message}`);
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMessage(null), 3000);
    }
  };

  const handleReset = async () => {
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

  const toggleCategory = (cat: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  const tierBadge = (tier: string) => {
    switch (tier) {
      case 'small': return 'badge badge-success';
      case 'medium': return 'badge badge-warning';
      case 'large': return 'badge badge-danger';
      default: return 'badge badge-info';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="spinner" />
        <span className="ml-3 text-sm text-white/60">Loading smart routing...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-error">
        <div className="flex items-center gap-2">
          <AlertCircle className="h-5 w-5" />
          <p>{error}</p>
        </div>
        <button onClick={() => fetchData()} className="mt-2 text-sm underline hover:text-white">Retry</button>
      </div>
    );
  }

  // Group models by provider for optgroup display
  const modelsByProvider = allModelNames.reduce<Record<string, string[]>>((acc, m) => {
    if (!acc[m.provider]) acc[m.provider] = [];
    acc[m.provider].push(m.name);
    return acc;
  }, {});
  // Sort names within each group
  for (const names of Object.values(modelsByProvider)) names.sort();

  return (
    <div className="space-y-6">
      {/* Horizontal Tabs */}
      <div className="flex items-center gap-1.5 p-1.5 bg-white/5 rounded-xl">
        <button
          onClick={() => setActiveTab('models')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'models'
              ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
              : 'text-white/50 hover:text-white/70 hover:bg-white/5'
          }`}
        >
          <Cpu className="h-4 w-4" />
          Models ({models.length})
        </button>
        <button
          onClick={() => setActiveTab('routing')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'routing'
              ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
              : 'text-white/50 hover:text-white/70 hover:bg-white/5'
          }`}
        >
          <Zap className="h-4 w-4" />
          Routing Table
        </button>
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

      {/* Models Tab */}
      {activeTab === 'models' && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {models.map((m) => (
            <div
              key={m.name}
              className="rounded-xl border border-white/10 bg-white/5 p-4 transition-all duration-200 hover:bg-white/10"
            >
              <div className="flex items-start justify-between gap-2">
                <h4 className="text-base font-semibold text-white">{m.name}</h4>
                <span className={tierBadge(m.tier)}>{m.tier}</span>
              </div>
              {m.param_b > 0 && (
                <p className="mt-1.5 text-sm text-white/60">{m.param_b}B params</p>
              )}
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {m.multimodal && (
                  <span className="badge bg-purple-500/20 text-purple-400 border border-purple-500/30">
                    <Eye className="h-3 w-3" /> vision
                  </span>
                )}
                {m.structured_output && (
                  <span className="badge bg-blue-500/20 text-blue-400 border border-blue-500/30">
                    <FileText className="h-3 w-3" /> structured
                  </span>
                )}
                {m.code && (
                  <span className="badge bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    <Code className="h-3 w-3" /> code
                  </span>
                )}
                {m.long_context && (
                  <span className="badge bg-orange-500/20 text-orange-400 border border-orange-500/30">
                    <Globe className="h-3 w-3" /> long ctx
                  </span>
                )}
                {m.reasoning && (
                  <span className="badge bg-amber-500/20 text-amber-400 border border-amber-500/30">
                    <Zap className="h-3 w-3" /> reasoning
                  </span>
                )}
              </div>
              {m.best_for && m.best_for.length > 0 && (
                <p className="mt-2 text-sm text-white/40">
                  Best for: {m.best_for.slice(0, 3).join(', ')}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Routing Table Tab */}
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
              {Object.entries(categories).map(([category, dataTypes]) => {
                const isExpanded = expandedCategories.has(category);
                return (
                  <div key={category}>
                    <button
                      onClick={() => toggleCategory(category)}
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
                              <tr
                                key={dt}
                                className={isOverridden ? 'bg-amber-500/5' : ''}
                              >
                                <td className="font-medium text-white">{dt}</td>
                                <td>
                                  <select
                                    value={currentPrimary}
                                    onChange={(e) => handlePrimaryChange(dt, e.target.value)}
                                    className="w-full max-w-[280px] rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none transition-all duration-300 focus:border-primary-500/50 focus:bg-white/10 focus:ring-2 focus:ring-primary-500/20"
                                    style={{ colorScheme: 'dark' }}
                                  >
                                    <option value="">{entry.suggested_primary || '(auto)'}</option>
                                    {Object.entries(modelsByProvider).map(([provider, names]) => (
                                      <optgroup key={provider} label={provider}>
                                        {names.map(name => (
                                          <option key={name} value={name}>{name}</option>
                                        ))}
                                      </optgroup>
                                    ))}
                                  </select>
                                </td>
                                <td>
                                  <select
                                    value={currentFallback}
                                    onChange={(e) => handleFallbackChange(dt, e.target.value)}
                                    className="w-full max-w-[280px] rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white outline-none transition-all duration-300 focus:border-primary-500/50 focus:bg-white/10 focus:ring-2 focus:ring-primary-500/20"
                                    style={{ colorScheme: 'dark' }}
                                  >
                                    <option value="">{entry.suggested_fallback || '(auto)'}</option>
                                    {Object.entries(modelsByProvider).map(([provider, names]) => (
                                      <optgroup key={provider} label={provider}>
                                        {names.map(name => (
                                          <option key={name} value={name}>{name}</option>
                                        ))}
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

          {/* Actions */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={!dirty || saving}
              className="btn-premium flex items-center gap-2 disabled:opacity-50"
            >
              <span className="relative z-10 flex items-center gap-2">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save Overrides
              </span>
            </button>
            <button
              onClick={handleReset}
              disabled={saving}
              className="btn-secondary flex items-center gap-2 disabled:opacity-50"
            >
              <RotateCcw className="h-4 w-4" />
              Reset to Defaults
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

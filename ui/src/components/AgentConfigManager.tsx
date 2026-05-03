'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Settings, Cpu, Plus, Trash2, X, AlertCircle, Loader2, Edit3,
  Save, ChevronDown, ChevronUp, Check, RotateCcw,
} from 'lucide-react';
import {
  listAgentConfigs, createAgentConfig, updateAgentConfig, deleteAgentConfig,
} from '@/lib/api';

const KNOWN_AGENT_TYPES = [
  'json', 'xml', 'csv', 'yaml', 'markdown', 'html_doc', 'code',
  'log_file', 'log_stream', 'web_page', 'feed', 'email', 'chat',
  'calendar', 'channel_message', 'sensor', 'iot_sensor', 'gps',
  'biometric', 'time_series', 'geospatial', 'lidar', 'model_3d',
  'archive', 'pdf', 'office_doc', 'image', 'image_batch',
  'medical_imaging', 'video_url', 'video_stream', 'audio_url',
  'audio_stream', 'binary_blob', 'conferencing', 'vehicle_telemetry',
  'satellite', 'scientific', 'financial', 'industrial', 'infrastructure',
  'url_download',
];

const MODEL_TIERS = ['small', 'medium', 'large', 'very-large', 'multimodal', 'omni'];

interface AgentConfigManagerProps {
  apiBaseUrl: string;
}

export default function AgentConfigManager({ apiBaseUrl }: AgentConfigManagerProps) {
  const [configs, setConfigs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [scopeFilter, setScopeFilter] = useState<'all' | 'system' | 'user'>('all');

  const [createForm, setCreateForm] = useState({
    agent_type: '',
    user_id: '',
    intro: '',
    system_prompt: '',
    output_schema: '',
    model_tier: '',
    parameters: '',
  });
  const [createLoading, setCreateLoading] = useState(false);

  const [editForm, setEditForm] = useState({
    intro: '',
    system_prompt: '',
    output_schema: '',
    model_tier: '',
    parameters: '',
  });
  const [editLoading, setEditLoading] = useState(false);

  const fetchConfigs = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listAgentConfigs();
      setConfigs(Array.isArray(data) ? data : []);
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 503 && detail?.includes('not configured')) {
        setError('AI features are not configured. Please set the required environment variables to enable agent configs.');
      } else if (detail) {
        setError(detail);
      } else {
        setError(err.message || 'Failed to load agent configs');
      }
      setConfigs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfigs();
  }, [fetchConfigs]);

  const filteredConfigs = configs.filter(c => {
    if (scopeFilter === 'system') return !c.user_id;
    if (scopeFilter === 'user') return !!c.user_id;
    return true;
  });

  const handleCreate = async () => {
    if (!createForm.agent_type) return;
    try {
      setCreateLoading(true);
      setError(null);
      let params = {};
      if (createForm.parameters.trim()) {
        try {
          params = JSON.parse(createForm.parameters);
        } catch {
          setError('Parameters must be valid JSON');
          setCreateLoading(false);
          return;
        }
      }
      await createAgentConfig({
        agent_type: createForm.agent_type,
        user_id: createForm.user_id || null,
        intro: createForm.intro || null,
        system_prompt: createForm.system_prompt || null,
        output_schema: createForm.output_schema || null,
        model_tier: createForm.model_tier || null,
        parameters: params,
      });
      setCreateForm({ agent_type: '', user_id: '', intro: '', system_prompt: '', output_schema: '', model_tier: '', parameters: '' });
      setShowCreateForm(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      await fetchConfigs();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to create config');
    } finally {
      setCreateLoading(false);
    }
  };

  const startEdit = (cfg: any) => {
    setEditingId(cfg.config_id);
    setEditForm({
      intro: cfg.intro || '',
      system_prompt: cfg.system_prompt || '',
      output_schema: cfg.output_schema || '',
      model_tier: cfg.model_tier || '',
      parameters: cfg.parameters ? JSON.stringify(cfg.parameters, null, 2) : '',
    });
  };

  const handleEdit = async (configId: string) => {
    try {
      setEditLoading(true);
      setError(null);
      let params: Record<string, any> | undefined;
      if (editForm.parameters.trim()) {
        try {
          params = JSON.parse(editForm.parameters);
        } catch {
          setError('Parameters must be valid JSON');
          setEditLoading(false);
          return;
        }
      }
      await updateAgentConfig(configId, {
        intro: editForm.intro || null,
        system_prompt: editForm.system_prompt || null,
        output_schema: editForm.output_schema || null,
        model_tier: editForm.model_tier || null,
        ...(params !== undefined ? { parameters: params } : {}),
      });
      setEditingId(null);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      await fetchConfigs();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to update config');
    } finally {
      setEditLoading(false);
    }
  };

  const handleDelete = async (configId: string) => {
    if (!confirm('Delete this agent config?')) return;
    try {
      setError(null);
      await deleteAgentConfig(configId);
      await fetchConfigs();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to delete config');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Cpu className="w-6 h-6 text-primary-400" />
          <div>
            <h2 className="text-xl font-semibold text-white">Agent Configs</h2>
            <p className="text-sm text-white/50">Configure webhook sub-agent prompts and skills per agent type</p>
          </div>
        </div>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-primary-500 to-accent-500 text-white text-sm font-medium hover:opacity-90 transition-opacity"
        >
          {showCreateForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
          {showCreateForm ? 'Cancel' : 'New Config'}
        </button>
      </div>

      {/* Status banners */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}
      {saved && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm">
          <Check className="w-4 h-4" />
          Changes saved successfully
        </div>
      )}

      {/* Scope filter */}
      <div className="flex items-center gap-2">
        {(['all', 'system', 'user'] as const).map(scope => (
          <button
            key={scope}
            onClick={() => setScopeFilter(scope)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              scopeFilter === scope
                ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                : 'text-white/40 hover:text-white/60 border border-white/10'
            }`}
          >
            {scope === 'all' ? 'All' : scope === 'system' ? 'System Defaults' : 'User Overrides'}
          </button>
        ))}
        <span className="text-white/30 text-xs ml-2">{filteredConfigs.length} config{filteredConfigs.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Create form */}
      {showCreateForm && (
        <div className="glass-card p-6 space-y-4">
          <h3 className="text-lg font-medium text-white">New Agent Config</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-white/60 mb-1">Agent Type *</label>
              <select
                value={createForm.agent_type}
                onChange={e => setCreateForm(f => ({ ...f, agent_type: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm"
              >
                <option value="">Select agent type...</option>
                {KNOWN_AGENT_TYPES.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-1">User ID (blank = system default)</label>
              <input
                type="text"
                value={createForm.user_id}
                onChange={e => setCreateForm(f => ({ ...f, user_id: e.target.value }))}
                placeholder="Leave blank for system default"
                className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-1">Model Tier</label>
              <select
                value={createForm.model_tier}
                onChange={e => setCreateForm(f => ({ ...f, model_tier: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm"
              >
                <option value="">Default (from agent class)</option>
                {MODEL_TIERS.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm text-white/60 mb-1">Intro Prompt</label>
            <textarea
              value={createForm.intro}
              onChange={e => setCreateForm(f => ({ ...f, intro: e.target.value }))}
              placeholder="e.g. Analyse this JSON content thoroughly"
              rows={2}
              className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono"
            />
          </div>
          <div>
            <label className="block text-sm text-white/60 mb-1">System Prompt</label>
            <textarea
              value={createForm.system_prompt}
              onChange={e => setCreateForm(f => ({ ...f, system_prompt: e.target.value }))}
              placeholder="Override the default system message sent to the LLM"
              rows={3}
              className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono"
            />
          </div>
          <div>
            <label className="block text-sm text-white/60 mb-1">Output Schema</label>
            <textarea
              value={createForm.output_schema}
              onChange={e => setCreateForm(f => ({ ...f, output_schema: e.target.value }))}
              placeholder="Custom JSON schema fields (overrides default _BASE_FIELDS)"
              rows={4}
              className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono"
            />
          </div>
          <div>
            <label className="block text-sm text-white/60 mb-1">Parameters (JSON)</label>
            <textarea
              value={createForm.parameters}
              onChange={e => setCreateForm(f => ({ ...f, parameters: e.target.value }))}
              placeholder='{"temperature": 0.3, "max_tokens": 4096}'
              rows={2}
              className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowCreateForm(false)}
              className="px-4 py-2 rounded-lg text-white/60 hover:text-white text-sm"
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={createLoading || !createForm.agent_type}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-primary-500 to-accent-500 text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
            >
              {createLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Create Config
            </button>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-primary-400" />
        </div>
      )}

      {/* Config list */}
      {!loading && filteredConfigs.length === 0 && (
        <div className="text-center py-12 text-white/40">
          <Settings className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No agent configs found</p>
          <p className="text-xs mt-1">Create one to override default pipeline behavior</p>
        </div>
      )}

      {!loading && filteredConfigs.map(cfg => (
        <div key={cfg.config_id} className="glass-card overflow-hidden">
          {/* Card header */}
          <div
            className="flex items-center justify-between px-5 py-4 cursor-pointer hover:bg-white/5 transition-colors"
            onClick={() => setExpandedId(expandedId === cfg.config_id ? null : cfg.config_id)}
          >
            <div className="flex items-center gap-3">
              <Cpu className="w-5 h-5 text-primary-400" />
              <div>
                <span className="text-white font-medium">{cfg.agent_type}</span>
                <span className={`ml-2 px-2 py-0.5 rounded text-xs ${
                  cfg.user_id
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'bg-emerald-500/20 text-emerald-400'
                }`}>
                  {cfg.user_id ? `user: ${cfg.user_id}` : 'system'}
                </span>
                {cfg.model_tier && (
                  <span className="ml-2 px-2 py-0.5 rounded text-xs bg-white/10 text-white/50">
                    {cfg.model_tier}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-white/30">v{cfg.version}</span>
              {expandedId === cfg.config_id ? (
                <ChevronUp className="w-4 h-4 text-white/40" />
              ) : (
                <ChevronDown className="w-4 h-4 text-white/40" />
              )}
            </div>
          </div>

          {/* Expanded content */}
          {expandedId === cfg.config_id && (
            <div className="px-5 pb-5 border-t border-white/5">
              {editingId === cfg.config_id ? (
                /* Edit mode */
                <div className="space-y-4 pt-4">
                  <div>
                    <label className="block text-sm text-white/60 mb-1">Intro Prompt</label>
                    <textarea
                      value={editForm.intro}
                      onChange={e => setEditForm(f => ({ ...f, intro: e.target.value }))}
                      rows={2}
                      className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-white/60 mb-1">System Prompt</label>
                    <textarea
                      value={editForm.system_prompt}
                      onChange={e => setEditForm(f => ({ ...f, system_prompt: e.target.value }))}
                      rows={3}
                      className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-white/60 mb-1">Output Schema</label>
                    <textarea
                      value={editForm.output_schema}
                      onChange={e => setEditForm(f => ({ ...f, output_schema: e.target.value }))}
                      rows={4}
                      className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono"
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-white/60 mb-1">Model Tier</label>
                      <select
                        value={editForm.model_tier}
                        onChange={e => setEditForm(f => ({ ...f, model_tier: e.target.value }))}
                        className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm"
                      >
                        <option value="">Default</option>
                        {MODEL_TIERS.map(t => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm text-white/60 mb-1">Parameters (JSON)</label>
                      <textarea
                        value={editForm.parameters}
                        onChange={e => setEditForm(f => ({ ...f, parameters: e.target.value }))}
                        rows={2}
                        className="w-full px-3 py-2 rounded-lg bg-black/30 border border-white/10 text-white text-sm font-mono"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => setEditingId(null)}
                      className="px-3 py-1.5 rounded-lg text-white/60 hover:text-white text-sm"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleEdit(cfg.config_id)}
                      disabled={editLoading}
                      className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-primary-500 to-accent-500 text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
                    >
                      {editLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                      Save
                    </button>
                  </div>
                </div>
              ) : (
                /* View mode */
                <div className="space-y-3 pt-4">
                  {cfg.intro && (
                    <div>
                      <span className="text-xs text-white/40 uppercase">Intro</span>
                      <p className="text-sm text-white/80 font-mono mt-1">{cfg.intro}</p>
                    </div>
                  )}
                  {cfg.system_prompt && (
                    <div>
                      <span className="text-xs text-white/40 uppercase">System Prompt</span>
                      <p className="text-sm text-white/80 font-mono mt-1 whitespace-pre-wrap">{cfg.system_prompt}</p>
                    </div>
                  )}
                  {cfg.output_schema && (
                    <div>
                      <span className="text-xs text-white/40 uppercase">Output Schema</span>
                      <pre className="text-sm text-white/80 font-mono mt-1 whitespace-pre-wrap bg-black/20 p-2 rounded">{cfg.output_schema}</pre>
                    </div>
                  )}
                  {cfg.parameters && Object.keys(cfg.parameters).length > 0 && (
                    <div>
                      <span className="text-xs text-white/40 uppercase">Parameters</span>
                      <pre className="text-sm text-white/80 font-mono mt-1 bg-black/20 p-2 rounded">{JSON.stringify(cfg.parameters, null, 2)}</pre>
                    </div>
                  )}
                  {!cfg.intro && !cfg.system_prompt && !cfg.output_schema && (
                    <p className="text-sm text-white/30 italic">No overrides configured — using hardcoded defaults</p>
                  )}
                  <div className="text-xs text-white/30 pt-2">
                    Created {new Date(cfg.created_at).toLocaleString()} | Updated {new Date(cfg.updated_at).toLocaleString()}
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      onClick={(e) => { e.stopPropagation(); startEdit(cfg); }}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/5 text-sm"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      Edit
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(cfg.config_id); }}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-red-400/60 hover:text-red-400 hover:bg-red-500/10 text-sm"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Delete
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

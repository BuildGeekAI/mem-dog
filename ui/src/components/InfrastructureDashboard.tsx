'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Server, Plus, Trash2, Play, Square, RefreshCw, ChevronDown, ChevronUp,
  Cpu, HardDrive, Activity, ScrollText, AlertCircle, Check, Loader2, Scale,
} from 'lucide-react';
import { api } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface K8sPod {
  name: string;
  namespace: string;
  tier: string;
  replicas: number;
  available_replicas: number;
  ready_replicas: number;
  status: string;
  managed: boolean;
  models_to_pull: string[];
  created_at: string | null;
  service_url: string | null;
}

interface PodMetrics {
  pods: { pod: string; cpu: string; memory: string }[];
  error?: string;
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    partial: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    scaled_to_zero: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${colors[status] || colors.error}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Create Pod Modal
// ---------------------------------------------------------------------------

function CreatePodModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('');
  const [tier, setTier] = useState('small');
  const [models, setModels] = useState('');
  const [replicas, setReplicas] = useState(1);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const handleCreate = async () => {
    if (!name.trim()) { setError('Name is required'); return; }
    setCreating(true);
    setError('');
    try {
      const modelsList = models.split(',').map(m => m.trim()).filter(Boolean);
      await api.post('/api/v1/models/k8s-pods', {
        name: name.trim(),
        tier,
        models_to_pull: modelsList,
        replicas,
      });
      onCreated();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to create pod');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-slate-900 border border-white/10 rounded-2xl p-6 w-full max-w-md shadow-2xl" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-white mb-4">Create Model Pod</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-white/60 mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
              placeholder="e.g. embedding-server"
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:border-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm text-white/60 mb-1">Tier</label>
            <select
              value={tier}
              onChange={e => setTier(e.target.value)}
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:border-primary-500"
            >
              <option value="small">Small (CPU: 50m-500m, Mem: 768Mi-2Gi)</option>
              <option value="medium">Medium (CPU: 100m-2, Mem: 1Gi-4Gi)</option>
              <option value="large">Large (CPU: 200m-4, Mem: 2Gi-8Gi)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-white/60 mb-1">Models to pull (comma-separated)</label>
            <input
              type="text"
              value={models}
              onChange={e => setModels(e.target.value)}
              placeholder="e.g. gemma3:4b, embeddinggemma"
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:border-primary-500"
            />
          </div>

          <div>
            <label className="block text-sm text-white/60 mb-1">Replicas</label>
            <input
              type="number"
              min={0}
              max={3}
              value={replicas}
              onChange={e => setReplicas(Number(e.target.value))}
              className="w-20 px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none focus:border-primary-500"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onClose} className="px-4 py-2 text-sm text-white/60 hover:text-white transition-colors">
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="px-4 py-2 bg-gradient-to-r from-primary-500 to-accent-500 text-white text-sm font-medium rounded-lg shadow-lg disabled:opacity-50 flex items-center gap-2"
          >
            {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Logs Modal
// ---------------------------------------------------------------------------

function LogsModal({ name, onClose }: { name: string; onClose: () => void }) {
  const [logs, setLogs] = useState('Loading...');

  useEffect(() => {
    api.get(`/api/v1/models/k8s-pods/${name}/logs?tail=200`)
      .then(res => setLogs(res.data.logs || '(empty)'))
      .catch(err => setLogs(`Error: ${err.message}`));
  }, [name]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-slate-900 border border-white/10 rounded-2xl p-6 w-full max-w-3xl max-h-[80vh] shadow-2xl flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <ScrollText className="w-5 h-5" /> Logs: {name}
          </h3>
          <button onClick={onClose} className="text-white/40 hover:text-white">X</button>
        </div>
        <pre className="flex-1 overflow-auto bg-black/40 rounded-lg p-4 text-xs text-white/80 font-mono whitespace-pre-wrap">
          {logs}
        </pre>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pod Row
// ---------------------------------------------------------------------------

function PodRow({ pod, onRefresh }: { pod: K8sPod; onRefresh: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [metrics, setMetrics] = useState<PodMetrics | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [scaling, setScaling] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadMetrics = useCallback(async () => {
    try {
      const res = await api.get(`/api/v1/models/k8s-pods/${pod.name}/metrics`);
      setMetrics(res.data);
    } catch {
      setMetrics({ pods: [], error: 'Failed to load metrics' });
    }
  }, [pod.name]);

  useEffect(() => {
    if (expanded) loadMetrics();
  }, [expanded, loadMetrics]);

  const handleScale = async (replicas: number) => {
    setScaling(true);
    try {
      await api.patch(`/api/v1/models/k8s-pods/${pod.name}/scale`, { replicas });
      onRefresh();
    } catch {
      // silently fail
    } finally {
      setScaling(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete deployment ${pod.name}? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await api.delete(`/api/v1/models/k8s-pods/${pod.name}`);
      onRefresh();
    } catch {
      // silently fail
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <div className="bg-white/5 border border-white/10 rounded-xl p-4 hover:border-white/20 transition-all">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center border border-white/10">
              <Server className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-white font-medium">{pod.name}</span>
                <StatusBadge status={pod.status} />
                <span className="text-xs text-white/30 px-2 py-0.5 bg-white/5 rounded">{pod.tier}</span>
                {pod.managed ? (
                  <span className="text-[10px] text-primary-400/70 px-1.5 py-0.5 bg-primary-500/10 border border-primary-500/20 rounded">managed</span>
                ) : (
                  <span className="text-[10px] text-amber-400/70 px-1.5 py-0.5 bg-amber-500/10 border border-amber-500/20 rounded">infrastructure</span>
                )}
              </div>
              <div className="text-xs text-white/40 mt-0.5">
                {pod.models_to_pull.length > 0
                  ? `Models: ${pod.models_to_pull.join(', ')}`
                  : 'No models configured'}
                {' · '}
                Replicas: {pod.available_replicas}/{pod.replicas}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Scale buttons — only for managed pods */}
            {pod.managed && pod.status === 'scaled_to_zero' ? (
              <button
                onClick={() => handleScale(1)}
                disabled={scaling}
                className="p-2 rounded-lg text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                title="Wake up (scale to 1)"
              >
                {scaling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              </button>
            ) : pod.managed ? (
              <button
                onClick={() => handleScale(0)}
                disabled={scaling}
                className="p-2 rounded-lg text-amber-400 hover:bg-amber-500/10 transition-colors"
                title="Sleep (scale to 0)"
              >
                {scaling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Square className="w-4 h-4" />}
              </button>
            ) : null}

            {/* Scale selector — managed only */}
            {pod.managed && (
              <select
                value={pod.replicas}
                onChange={e => handleScale(Number(e.target.value))}
                disabled={scaling}
                className="bg-white/5 border border-white/10 rounded-lg text-white text-xs px-2 py-1.5 focus:outline-none"
                title="Set replicas"
              >
                {[0, 1, 2, 3].map(n => (
                  <option key={n} value={n}>{n} replica{n !== 1 ? 's' : ''}</option>
                ))}
              </select>
            )}

            {/* Logs */}
            <button
              onClick={() => setShowLogs(true)}
              className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
              title="View logs"
            >
              <ScrollText className="w-4 h-4" />
            </button>

            {/* Expand */}
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {/* Delete — managed only */}
            {pod.managed && (
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="p-2 rounded-lg text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                title="Delete deployment"
              >
                {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              </button>
            )}
          </div>
        </div>

        {/* Expanded details */}
        {expanded && (
          <div className="mt-4 pt-4 border-t border-white/10 space-y-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-[10px] text-white/40 uppercase tracking-wider">Namespace</div>
                <div className="text-sm text-white mt-1">{pod.namespace}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-[10px] text-white/40 uppercase tracking-wider">Created</div>
                <div className="text-sm text-white mt-1">
                  {pod.created_at ? new Date(pod.created_at).toLocaleDateString() : '-'}
                </div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-[10px] text-white/40 uppercase tracking-wider">Service URL</div>
                <div className="text-xs text-white/60 mt-1 truncate">{pod.service_url || '-'}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-[10px] text-white/40 uppercase tracking-wider">Ready</div>
                <div className="text-sm text-white mt-1">{pod.ready_replicas}/{pod.replicas}</div>
              </div>
            </div>

            {/* Metrics */}
            {metrics && metrics.pods.length > 0 && (
              <div>
                <div className="text-xs text-white/40 uppercase tracking-wider mb-2">Resource Usage</div>
                <div className="space-y-1">
                  {metrics.pods.map(p => (
                    <div key={p.pod} className="flex items-center gap-4 text-xs text-white/60 bg-white/5 rounded-lg px-3 py-2">
                      <span className="text-white/40 w-48 truncate">{p.pod}</span>
                      <span className="flex items-center gap-1"><Cpu className="w-3 h-3" /> {p.cpu}</span>
                      <span className="flex items-center gap-1"><HardDrive className="w-3 h-3" /> {p.memory}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {metrics?.error && (
              <div className="text-xs text-amber-400/60">{metrics.error}</div>
            )}
          </div>
        )}
      </div>

      {showLogs && <LogsModal name={pod.name} onClose={() => setShowLogs(false)} />}
    </>
  );
}

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

export default function InfrastructureDashboard() {
  const [pods, setPods] = useState<K8sPod[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [k8sAvailable, setK8sAvailable] = useState(true);

  const loadPods = useCallback(async () => {
    try {
      const res = await api.get('/api/v1/models/k8s-pods');
      setPods(res.data);
      setK8sAvailable(true);
      setError('');
    } catch (err: any) {
      if (err?.response?.status === 503) {
        setK8sAvailable(false);
        setError('Kubernetes client not available — API may be running outside the cluster.');
      } else {
        setError(err?.response?.data?.detail || err.message || 'Failed to load pods');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPods();
    const interval = setInterval(loadPods, 15000); // auto-refresh every 15s
    return () => clearInterval(interval);
  }, [loadPods]);

  // Summary stats
  const totalPods = pods.length;
  const runningPods = pods.filter(p => p.status === 'running').length;
  const totalModels = new Set(pods.flatMap(p => p.models_to_pull)).size;
  const totalReplicas = pods.reduce((sum, p) => sum + p.available_replicas, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Model Infrastructure</h2>
          <p className="text-sm text-white/40 mt-1">Manage Ollama model pods on Kubernetes</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadPods}
            className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setShowCreate(true)}
            disabled={!k8sAvailable}
            className="px-4 py-2 bg-gradient-to-r from-primary-500 to-accent-500 text-white text-sm font-medium rounded-lg shadow-lg disabled:opacity-50 flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Create Pod
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Deployments', value: totalPods, icon: Server, color: 'from-blue-500/20 to-blue-600/20' },
          { label: 'Running', value: runningPods, icon: Activity, color: 'from-emerald-500/20 to-emerald-600/20' },
          { label: 'Models', value: totalModels, icon: Cpu, color: 'from-purple-500/20 to-purple-600/20' },
          { label: 'Active Replicas', value: totalReplicas, icon: Scale, color: 'from-amber-500/20 to-amber-600/20' },
        ].map(stat => (
          <div key={stat.label} className={`bg-gradient-to-br ${stat.color} border border-white/10 rounded-xl p-4`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-white">{stat.value}</div>
                <div className="text-xs text-white/40 mt-0.5">{stat.label}</div>
              </div>
              <stat.icon className="w-8 h-8 text-white/20" />
            </div>
          </div>
        ))}
      </div>

      {/* Error / Not available */}
      {error && (
        <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Pod List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
        </div>
      ) : pods.length === 0 && k8sAvailable ? (
        <div className="text-center py-12">
          <Server className="w-12 h-12 text-white/20 mx-auto mb-3" />
          <p className="text-white/40">No managed model pods yet</p>
          <p className="text-white/30 text-sm mt-1">Click &quot;Create Pod&quot; to deploy an Ollama instance</p>
        </div>
      ) : (
        <div className="space-y-3">
          {pods.map(pod => (
            <PodRow key={pod.name} pod={pod} onRefresh={loadPods} />
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreate && <CreatePodModal onClose={() => setShowCreate(false)} onCreated={loadPods} />}
    </div>
  );
}

'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Webhook as WebhookIcon, Plus, Trash2, Copy, Check, Loader2, AlertCircle,
  Pause, Play, RefreshCw, ChevronDown, ChevronRight, BarChart3, KeyRound,
} from 'lucide-react';
import {
  listWebhooks, createWebhook, deleteWebhook, updateWebhook,
  rotateWebhookSecret, getWebhookStats,
} from '@/lib/api';
import type { Webhook, WebhookStats } from '@/types';

const CHANNEL_TYPES = [
  'generic', 'slack', 'email', 'telegram', 'discord', 'whatsapp',
  'msteams', 'webchat', 'zoom', 'video', 'signal', 'matrix',
  'irc', 'googlechat', 'line', 'mattermost',
] as const;

const DEFAULT_GATEWAY_URL = typeof process.env.NEXT_PUBLIC_WEBHOOK_GATEWAY_URL === 'string'
  ? process.env.NEXT_PUBLIC_WEBHOOK_GATEWAY_URL
  : '';

function getExternalUrl(webhook: Webhook): string {
  // Use the gateway URL to build a user-facing URL
  if (DEFAULT_GATEWAY_URL) {
    const base = DEFAULT_GATEWAY_URL.replace(/\/+$/, '');
    return `${base}/webhooks/${webhook.webhook_id}`;
  }
  // Fallback to the server-provided URL
  return webhook.url || `<gateway>/webhooks/${webhook.webhook_id}`;
}

function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// ---------- Create Dialog ----------
function CreateDialog({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (webhook: Webhook) => void;
}) {
  const [channelType, setChannelType] = useState('generic');
  const [name, setName] = useState('');
  const [generateSecret, setGenerateSecret] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    setLoading(true);
    setError(null);
    try {
      const wh = await createWebhook({
        channel_type: channelType,
        name: name.trim() || undefined,
        generate_secret: generateSecret,
      });
      onCreate(wh);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create webhook');
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    'w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="glass-card p-6 w-full max-w-md space-y-4" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-white">Create Webhook</h3>

        {error && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-white/70 mb-1.5">Channel Type</label>
          <select value={channelType} onChange={e => setChannelType(e.target.value)} className={inputClass}>
            {CHANNEL_TYPES.map(ch => (
              <option key={ch} value={ch}>{ch.charAt(0).toUpperCase() + ch.slice(1)}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-white/70 mb-1.5">Name</label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g. Acme Slack Bot"
            className={inputClass}
          />
        </div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={generateSecret}
            onChange={e => setGenerateSecret(e.target.checked)}
            className="w-4 h-4 rounded border-white/20 bg-black/30 text-primary-500 focus:ring-primary-500/25"
          />
          <span className="text-sm text-white/70">Generate signing secret (HMAC verification)</span>
        </label>

        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-sm text-white/50 hover:text-white/70 hover:bg-white/5 transition-all">
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25 transition-all disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------- Secret Display ----------
function SecretBanner({ secret, onDismiss }: { secret: string; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(secret);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl px-4 py-3 space-y-2">
      <div className="flex items-center gap-2 text-amber-400 text-sm font-medium">
        <KeyRound className="w-4 h-4" />
        Signing secret — copy now, it won&apos;t be shown again
      </div>
      <div className="flex items-center gap-2">
        <code className="flex-1 text-xs font-mono text-white/80 bg-black/30 rounded-lg px-3 py-2 break-all">{secret}</code>
        <button onClick={copy} className="p-2 rounded-lg hover:bg-white/10 transition-colors" title="Copy">
          {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-white/50" />}
        </button>
      </div>
      <button onClick={onDismiss} className="text-xs text-white/40 hover:text-white/60">Dismiss</button>
    </div>
  );
}

// ---------- Webhook Card ----------
function WebhookCard({
  webhook,
  onDelete,
  onToggleStatus,
  onRotateSecret,
}: {
  webhook: Webhook;
  onDelete: (id: string) => void;
  onToggleStatus: (id: string, status: 'active' | 'paused') => void;
  onRotateSecret: (id: string) => void;
}) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [stats, setStats] = useState<WebhookStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);

  const url = getExternalUrl(webhook);
  const isActive = webhook.status === 'active';

  const copyUrl = () => {
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const loadStats = async () => {
    if (stats) return;
    setLoadingStats(true);
    try {
      const s = await getWebhookStats(webhook.webhook_id, '24h');
      setStats(s);
    } catch { /* ignore */ }
    setLoadingStats(false);
  };

  const toggleExpand = () => {
    const next = !expanded;
    setExpanded(next);
    if (next) loadStats();
  };

  return (
    <div className={`glass-card overflow-hidden transition-all ${!isActive ? 'opacity-60' : ''}`}>
      <div className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
              isActive
                ? 'bg-gradient-to-br from-primary-500 to-accent-500'
                : 'bg-white/10'
            }`}>
              <WebhookIcon className="w-5 h-5 text-white" />
            </div>
            <div className="min-w-0">
              <h4 className="text-sm font-semibold text-white truncate">
                {webhook.name || webhook.webhook_id}
              </h4>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-white/60">
                  {webhook.channel_type}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  isActive
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'bg-amber-500/20 text-amber-400'
                }`}>
                  {webhook.status}
                </span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => onToggleStatus(webhook.webhook_id, isActive ? 'paused' : 'active')}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors"
              title={isActive ? 'Pause' : 'Resume'}
            >
              {isActive
                ? <Pause className="w-4 h-4 text-white/50" />
                : <Play className="w-4 h-4 text-emerald-400" />
              }
            </button>
            <button
              onClick={() => onRotateSecret(webhook.webhook_id)}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors"
              title="Rotate secret"
            >
              <RefreshCw className="w-4 h-4 text-white/50" />
            </button>
            <button
              onClick={() => onDelete(webhook.webhook_id)}
              className="p-2 rounded-lg hover:bg-red-500/20 transition-colors"
              title="Delete"
            >
              <Trash2 className="w-4 h-4 text-red-400/70" />
            </button>
          </div>
        </div>

        {/* URL */}
        <div className="flex items-center gap-2">
          <code className="flex-1 text-xs font-mono text-white/50 bg-black/20 rounded-lg px-3 py-2 truncate">
            {url}
          </code>
          <button onClick={copyUrl} className="p-2 rounded-lg hover:bg-white/10 transition-colors flex-shrink-0" title="Copy URL">
            {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4 text-white/40" />}
          </button>
        </div>

        {/* ID and timestamps */}
        <div className="flex items-center justify-between text-[10px] text-white/30">
          <span className="font-mono">{webhook.webhook_id}</span>
          <span>Created {timeAgo(webhook.created_at)}</span>
        </div>

        {/* Expandable stats */}
        <button onClick={toggleExpand} className="flex items-center gap-1.5 text-xs text-white/40 hover:text-white/60 transition-colors">
          {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          <BarChart3 className="w-3.5 h-3.5" />
          Stats (24h)
        </button>

        {expanded && (
          <div className="bg-black/20 rounded-xl p-3 space-y-2">
            {loadingStats ? (
              <div className="flex items-center gap-2 text-xs text-white/40">
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading stats...
              </div>
            ) : stats ? (
              <>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <div className="text-lg font-bold text-white">{stats.total}</div>
                    <div className="text-[10px] text-white/40">Total</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold text-emerald-400">
                      {Math.round(stats.success_rate * 100)}%
                    </div>
                    <div className="text-[10px] text-white/40">Success</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold text-red-400">
                      {Object.entries(stats.by_status)
                        .filter(([k]) => k.includes('fail') || k === 'error')
                        .reduce((sum, [, v]) => sum + v, 0)}
                    </div>
                    <div className="text-[10px] text-white/40">Failed</div>
                  </div>
                </div>
                {Object.keys(stats.by_status).length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(stats.by_status).map(([status, count]) => (
                      <span key={status} className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-white/50">
                        {status}: {count}
                      </span>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="text-xs text-white/40">No data</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Main Component ----------
export default function WebhookManager() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newSecret, setNewSecret] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const whs = await listWebhooks();
      setWebhooks(whs);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load webhooks');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = (wh: Webhook) => {
    if (wh.secret) setNewSecret(wh.secret);
    setShowCreate(false);
    load();
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteWebhook(id);
      setWebhooks(prev => prev.filter(w => w.webhook_id !== id));
    } catch { /* ignore */ }
  };

  const handleToggleStatus = async (id: string, status: 'active' | 'paused') => {
    try {
      await updateWebhook(id, { status });
      load();
    } catch { /* ignore */ }
  };

  const handleRotateSecret = async (id: string) => {
    try {
      const wh = await rotateWebhookSecret(id);
      if (wh.secret) setNewSecret(wh.secret);
    } catch { /* ignore */ }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
            <WebhookIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Webhooks</h3>
            <p className="text-sm text-white/50">Manage inbound webhook endpoints</p>
          </div>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25 transition-all"
        >
          <Plus className="w-4 h-4" />
          Create Webhook
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {newSecret && (
        <SecretBanner secret={newSecret} onDismiss={() => setNewSecret(null)} />
      )}

      {/* Webhook list */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-white/40">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />
          Loading webhooks...
        </div>
      ) : webhooks.length === 0 ? (
        <div className="glass-card p-8 text-center space-y-3">
          <WebhookIcon className="w-12 h-12 text-white/20 mx-auto" />
          <p className="text-white/50 text-sm">No webhooks yet</p>
          <p className="text-white/30 text-xs">Create a webhook to get a unique URL for receiving messages</p>
        </div>
      ) : (
        <div className="grid gap-4 grid-cols-1 lg:grid-cols-2">
          {webhooks.map(wh => (
            <WebhookCard
              key={wh.webhook_id}
              webhook={wh}
              onDelete={handleDelete}
              onToggleStatus={handleToggleStatus}
              onRotateSecret={handleRotateSecret}
            />
          ))}
        </div>
      )}

      {showCreate && (
        <CreateDialog onClose={() => setShowCreate(false)} onCreate={handleCreate} />
      )}
    </div>
  );
}

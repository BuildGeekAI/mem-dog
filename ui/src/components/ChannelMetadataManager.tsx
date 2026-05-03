'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Radio,
  Plus,
  Trash2,
  Check,
  AlertCircle,
  Loader2,
  Pencil,
  X,
} from 'lucide-react';
import {
  listChannels,
  getChannel,
  putChannel,
  deleteChannel,
} from '@/lib/api';
import type { ChannelMetadata, ChannelMetadataCreate } from '@/types';

const CHANNEL_TYPE_SUGGESTIONS = [
  'telegram', 'slack', 'discord', 'whatsapp', 'teams', 'zoom', 'google_meet', 'webex',
  'gmail', 'hotmail', 'yahoo_mail', 'outlook', 'email',
  'google_docs', 'microsoft_documents', 'office_365', 'onedrive',
  'irc', 'feishu', 'google_chat', 'mattermost', 'signal', 'webchat', 'api', 'custom',
];

interface ChannelMetadataManagerProps {
  apiBaseUrl: string;
}

export function ChannelMetadataManager({ apiBaseUrl }: ChannelMetadataManagerProps) {
  const [channels, setChannels] = useState<ChannelMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [form, setForm] = useState<ChannelMetadataCreate & { channel_type: string }>({
    channel_type: 'telegram',
    display_name: null,
    description: null,
    config: {},
    metadata: {},
  });
  const [configJson, setConfigJson] = useState('{}');
  const [metadataJson, setMetadataJson] = useState('{}');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const list = await listChannels();
      setChannels(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load channels');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const startEdit = async (channelType: string) => {
    try {
      const c = await getChannel(channelType);
      setForm({
        channel_type: c.channel_type,
        display_name: c.display_name ?? null,
        description: c.description ?? null,
        config: c.config ?? {},
        metadata: c.metadata ?? {},
      });
      setConfigJson(JSON.stringify(c.config ?? {}, null, 2));
      setMetadataJson(JSON.stringify(c.metadata ?? {}, null, 2));
      setEditing(channelType);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load channel');
    }
  };

  const startAdd = () => {
    setForm({
      channel_type: 'telegram',
      display_name: null,
      description: null,
      config: {},
      metadata: {},
    });
    setConfigJson('{}');
    setMetadataJson('{}');
    setShowAdd(true);
    setEditing(null);
    setError(null);
  };

  const parseJson = (raw: string, label: string): Record<string, unknown> => {
    const t = raw.trim();
    if (!t) return {};
    try {
      const v = JSON.parse(t);
      return typeof v === 'object' && v !== null ? v : {};
    } catch {
      throw new Error(`Invalid ${label}: must be valid JSON object`);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const channelType = form.channel_type.trim().toLowerCase().replace(/\s+/g, '_');
    if (!channelType) {
      setError('Channel type is required.');
      return;
    }
    try {
      const config = parseJson(configJson, 'config');
      const metadata = parseJson(metadataJson, 'metadata');
      setError(null);
      await putChannel(channelType, {
        display_name: form.display_name || null,
        description: form.description || null,
        config,
        metadata,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      setEditing(null);
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  const handleDelete = async (channelType: string) => {
    try {
      setDeleting(channelType);
      await deleteChannel(channelType);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="glass-card p-6 max-w-3xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
            <Radio className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Channel metadata</h3>
            <p className="text-sm text-white/50">Configure how to communicate with each channel (webhook, API, etc.)</p>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5 mb-4">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}
        {saved && (
          <div className="flex items-center gap-2 text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-2.5 mb-4">
            <Check className="w-4 h-4 flex-shrink-0" />
            Channel saved.
          </div>
        )}

        {!showAdd && !editing && (
          <button
            type="button"
            onClick={startAdd}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-white/10 text-white hover:bg-white/20 transition-all mb-4"
          >
            <Plus className="w-4 h-4" />
            Add channel
          </button>
        )}

        {(showAdd || editing) && (
          <form onSubmit={handleSave} className="space-y-4 p-4 bg-white/5 rounded-xl border border-white/10 mb-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-white/70 mb-1">Channel type</label>
                <input
                  type="text"
                  value={form.channel_type}
                  onChange={(e) => setForm((f) => ({ ...f, channel_type: e.target.value }))}
                  list="channel-type-list"
                  placeholder="e.g. telegram, slack"
                  className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
                  readOnly={!!editing}
                />
                <datalist id="channel-type-list">
                  {CHANNEL_TYPE_SUGGESTIONS.map((c) => (
                    <option key={c} value={c} />
                  ))}
                </datalist>
              </div>
              <div>
                <label className="block text-sm font-medium text-white/70 mb-1">Display name</label>
                <input
                  type="text"
                  value={form.display_name ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value || null }))}
                  placeholder="e.g. Company Slack"
                  className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-white/70 mb-1">Description</label>
              <input
                type="text"
                value={form.description ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value || null }))}
                placeholder="Short description of this channel"
                className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-white/70 mb-1">Config (JSON) — webhook URL, API base, auth, etc.</label>
              <textarea
                value={configJson}
                onChange={(e) => setConfigJson(e.target.value)}
                rows={4}
                className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm font-mono placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
                placeholder='{"webhook_url": "https://...", "api_base": "https://api.example.com"}'
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-white/70 mb-1">Metadata (JSON)</label>
              <textarea
                value={metadataJson}
                onChange={(e) => setMetadataJson(e.target.value)}
                rows={2}
                className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm font-mono placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
                placeholder="{}"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25"
              >
                <Check className="w-4 h-4" />
                {editing ? 'Update' : 'Add'}
              </button>
              <button
                type="button"
                onClick={() => { setShowAdd(false); setEditing(null); setError(null); }}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-white/10 text-white hover:bg-white/20"
              >
                <X className="w-4 h-4" />
                Cancel
              </button>
            </div>
          </form>
        )}

        <div>
          <h4 className="text-sm font-medium text-white/70 mb-2">Channels</h4>
          {loading ? (
            <div className="flex items-center gap-2 text-white/50 text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading…
            </div>
          ) : channels.length === 0 ? (
            <p className="text-white/40 text-sm">No channel metadata yet. Add one to describe how to communicate with a channel.</p>
          ) : (
            <ul className="space-y-2">
              {channels.map((c) => (
                <li
                  key={c.channel_type}
                  className="flex items-center justify-between gap-4 py-2.5 px-4 bg-white/5 rounded-xl border border-white/10"
                >
                  <div className="min-w-0 flex-1">
                    <span className="font-medium text-white capitalize">{c.channel_type.replace(/_/g, ' ')}</span>
                    {c.display_name && (
                      <span className="text-white/50 ml-2">— {c.display_name}</span>
                    )}
                    {c.description && (
                      <p className="text-white/40 text-xs mt-0.5 truncate">{c.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => startEdit(c.channel_type)}
                      className="p-2 rounded-lg text-white/70 hover:bg-white/10"
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(c.channel_type)}
                      disabled={deleting === c.channel_type}
                      className="p-2 rounded-lg text-red-400 hover:bg-red-500/20 disabled:opacity-50"
                      title="Delete"
                    >
                      {deleting === c.channel_type ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

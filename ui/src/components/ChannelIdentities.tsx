'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  MessageCircle,
  Plus,
  Trash2,
  Check,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import {
  getCurrentUserId,
  listChannelIdentitiesByUser,
  createChannelIdentity,
  deleteChannelIdentity,
} from '@/lib/api';
import type { ChannelIdentityRecord, ChannelIdentityCreate } from '@/types';

/** Channel types for dropdown (chat, video, email, documents, custom). */
const CHANNEL_TYPES = [
  // Chat
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'slack', label: 'Slack' },
  { value: 'discord', label: 'Discord' },
  { value: 'teams', label: 'Microsoft Teams' },
  { value: 'msteams', label: 'MS Teams (Bot)' },
  { value: 'irc', label: 'IRC' },
  { value: 'feishu', label: 'Feishu' },
  { value: 'google_chat', label: 'Google Chat' },
  { value: 'mattermost', label: 'Mattermost' },
  { value: 'signal', label: 'Signal' },
  { value: 'bluebubbles', label: 'BlueBubbles (iMessage)' },
  { value: 'imessage', label: 'iMessage (legacy)' },
  { value: 'synology_chat', label: 'Synology Chat' },
  { value: 'line', label: 'LINE' },
  { value: 'nextcloud_talk', label: 'Nextcloud Talk' },
  { value: 'matrix', label: 'Matrix' },
  { value: 'nostr', label: 'Nostr' },
  { value: 'twitch', label: 'Twitch' },
  { value: 'zalo', label: 'Zalo' },
  { value: 'zalo_personal', label: 'Zalo Personal' },
  { value: 'webchat', label: 'WebChat' },
  // Video conferencing
  { value: 'zoom', label: 'Zoom' },
  { value: 'google_meet', label: 'Google Meet' },
  { value: 'webex', label: 'Webex' },
  // Email providers
  { value: 'gmail', label: 'Gmail' },
  { value: 'hotmail', label: 'Hotmail' },
  { value: 'yahoo_mail', label: 'Yahoo Mail' },
  { value: 'outlook', label: 'Outlook' },
  { value: 'email', label: 'Email (generic)' },
  // Documents / productivity
  { value: 'google_docs', label: 'Google Docs' },
  { value: 'microsoft_documents', label: 'Microsoft Documents' },
  { value: 'office_365', label: 'Office 365' },
  { value: 'onedrive', label: 'OneDrive' },
  // Other
  { value: 'api', label: 'API' },
  { value: 'custom', label: 'Custom…' },
];

interface ChannelIdentitiesProps {
  apiBaseUrl: string;
}

export function ChannelIdentities({ apiBaseUrl }: ChannelIdentitiesProps) {
  const [userId, setUserId] = useState('');
  const [identities, setIdentities] = useState<ChannelIdentityRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [form, setForm] = useState<ChannelIdentityCreate>({
    channel_type: 'telegram',
    channel_unique_id: '',
    user_id: '',
    display_name: null,
    metadata: {},
  });
  /** When channel_type is "custom", this is the user-entered channel type name sent to the API. */
  const [customChannelTypeName, setCustomChannelTypeName] = useState('');

  const load = useCallback(async () => {
    const uid = getCurrentUserId();
    setUserId(uid);
    if (!uid) {
      setIdentities([]);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const res = await listChannelIdentitiesByUser(uid);
      setIdentities(res.identities);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load channel identities');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const uid = getCurrentUserId();
    if (!uid) {
      setError('Set an active user in Profile first.');
      return;
    }
    const trimmed = form.channel_unique_id.trim();
    if (!trimmed) {
      setError('Channel unique ID is required.');
      return;
    }
    const channelType =
      form.channel_type === 'custom'
        ? customChannelTypeName.trim().toLowerCase().replace(/\s+/g, '_') || undefined
        : form.channel_type;
    if (form.channel_type === 'custom' && !channelType) {
      setError('Custom channel type name is required.');
      return;
    }
    try {
      setError(null);
      await createChannelIdentity({
        ...form,
        user_id: uid,
        channel_type: channelType!,
        channel_unique_id: trimmed,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      setShowAdd(false);
      setForm({ channel_type: 'telegram', channel_unique_id: '', user_id: uid, display_name: null, metadata: {} });
      setCustomChannelTypeName('');
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add channel identity');
    }
  };

  const handleDelete = async (rec: ChannelIdentityRecord) => {
    const key = `${rec.channel_type}/${rec.channel_unique_id}`;
    try {
      setDeleting(key);
      await deleteChannelIdentity(rec.channel_type, rec.channel_unique_id);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    } finally {
      setDeleting(null);
    }
  };

  if (!userId) {
    return (
      <div className="glass-card p-6 max-w-lg">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
            <MessageCircle className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Channel identities</h3>
            <p className="text-sm text-white/50">Link channel identities to your user</p>
          </div>
        </div>
        <p className="text-white/60 text-sm">Set an active User ID in the Profile tab first.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="glass-card p-6 max-w-3xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
            <MessageCircle className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Channel identities</h3>
            <p className="text-sm text-white/50">Correlate channel identities with user <strong>{userId}</strong></p>
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
            Channel identity added.
          </div>
        )}

        {!showAdd ? (
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-white/10 text-white hover:bg-white/20 transition-all"
          >
            <Plus className="w-4 h-4" />
            Add channel identity
          </button>
        ) : (
          <form onSubmit={handleAdd} className="space-y-4 p-4 bg-white/5 rounded-xl border border-white/10">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-white/70 mb-1">Channel type</label>
                <select
                  value={form.channel_type}
                  onChange={(e) => setForm((f) => ({ ...f, channel_type: e.target.value }))}
                  className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-primary-500/50"
                >
                  {CHANNEL_TYPES.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              {form.channel_type === 'custom' && (
                <div>
                  <label className="block text-sm font-medium text-white/70 mb-1">Custom channel type name</label>
                  <input
                    type="text"
                    value={customChannelTypeName}
                    onChange={(e) => setCustomChannelTypeName(e.target.value)}
                    placeholder="e.g. my_internal_bot, acme_chat"
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
                  />
                </div>
              )}
              <div className={form.channel_type === 'custom' ? 'sm:col-span-2' : ''}>
                <label className="block text-sm font-medium text-white/70 mb-1">Channel unique ID</label>
                <input
                  type="text"
                  value={form.channel_unique_id}
                  onChange={(e) => setForm((f) => ({ ...f, channel_unique_id: e.target.value }))}
                  placeholder="e.g. Telegram user id, Slack user id"
                  className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-white/70 mb-1">Display name (optional)</label>
              <input
                type="text"
                value={form.display_name ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value || null }))}
                placeholder="My Telegram"
                className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25"
              >
                <Check className="w-4 h-4" />
                Add
              </button>
              <button
                type="button"
                onClick={() => { setShowAdd(false); setError(null); setCustomChannelTypeName(''); }}
                className="px-4 py-2.5 rounded-xl text-sm font-medium bg-white/10 text-white hover:bg-white/20"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        <div className="mt-6">
          <h4 className="text-sm font-medium text-white/70 mb-2">Linked identities</h4>
          {loading ? (
            <div className="flex items-center gap-2 text-white/50 text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading…
            </div>
          ) : identities.length === 0 ? (
            <p className="text-white/40 text-sm">No channel identities linked yet. Add one above.</p>
          ) : (
            <ul className="space-y-2">
              {identities.map((rec) => (
                <li
                  key={`${rec.channel_type}/${rec.channel_unique_id}`}
                  className="flex items-center justify-between gap-4 py-2.5 px-4 bg-white/5 rounded-xl border border-white/10"
                >
                  <div className="min-w-0">
                    <span className="font-medium text-white capitalize">{rec.channel_type.replace(/_/g, ' ')}</span>
                    <span className="text-white/50 mx-2">·</span>
                    <span className="text-white/70 text-sm truncate">{rec.channel_unique_id}</span>
                    {rec.display_name && (
                      <span className="text-white/40 text-sm ml-2">({rec.display_name})</span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDelete(rec)}
                    disabled={deleting === `${rec.channel_type}/${rec.channel_unique_id}`}
                    className="p-2 rounded-lg text-red-400 hover:bg-red-500/20 disabled:opacity-50"
                    title="Remove"
                  >
                    {deleting === `${rec.channel_type}/${rec.channel_unique_id}` ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

'use client';

import { useState, useEffect } from 'react';
import { Key, Plus, Trash2, Copy, Check, AlertCircle, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { getCurrentUserId, listApiKeys, createApiKey, deleteApiKey } from '@/lib/api';
import type { APIKeyResponse } from '@/types';

export default function ApiKeysManager() {
  const [keys, setKeys] = useState<APIKeyResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form
  const [name, setName] = useState('');
  const [expiryDays, setExpiryDays] = useState<number | undefined>(undefined);
  const [creating, setCreating] = useState(false);

  // Newly created key (shown once)
  const [newKey, setNewKey] = useState<APIKeyResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [showUsage, setShowUsage] = useState(false);

  const userId = getCurrentUserId();

  const refresh = () => {
    setLoading(true);
    listApiKeys(userId)
      .then(setKeys)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, []);

  const handleCreate = async () => {
    const trimmed = name.trim();
    if (!trimmed) { setError('Name is required'); return; }
    setCreating(true);
    setError(null);
    try {
      const created = await createApiKey(userId, trimmed, expiryDays);
      setNewKey(created);
      setName('');
      setExpiryDays(undefined);
      refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create key');
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (keyId: string) => {
    try {
      await deleteApiKey(userId, keyId);
      setKeys((prev) => prev.filter((k) => k.key_id !== keyId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to revoke key');
    }
  };

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const inputClass =
    'w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all';

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
            <Key className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">API Keys</h3>
            <p className="text-sm text-white/50">Create personal keys for API access</p>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5 mb-4">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Create form */}
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-sm font-medium text-white/70 mb-1.5">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); setError(null); }}
              placeholder="e.g. CI Pipeline"
              className={inputClass}
            />
          </div>
          <div className="w-40">
            <label className="block text-sm font-medium text-white/70 mb-1.5">Expires</label>
            <select
              value={expiryDays ?? ''}
              onChange={(e) => setExpiryDays(e.target.value ? Number(e.target.value) : undefined)}
              className={inputClass}
            >
              <option value="">Never</option>
              <option value="30">30 days</option>
              <option value="90">90 days</option>
              <option value="365">1 year</option>
            </select>
          </div>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25 transition-all disabled:opacity-50 whitespace-nowrap"
          >
            {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Create
          </button>
        </div>
      </div>

      {/* Newly created key banner */}
      {newKey?.key && (
        <div className="glass-card p-5 border border-emerald-500/30 bg-emerald-500/5">
          <p className="text-sm text-emerald-400 font-medium mb-2">
            Key created — copy it now, it won&apos;t be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-black/40 text-white/90 rounded-lg px-4 py-2 text-sm font-mono break-all select-all">
              {newKey.key}
            </code>
            <button
              onClick={() => handleCopy(newKey.key!)}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors text-white/60 hover:text-white"
              title="Copy to clipboard"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
        </div>
      )}

      {/* Key list */}
      <div className="glass-card p-6">
        <h4 className="text-sm font-medium text-white/70 mb-4">Active Keys</h4>
        {loading ? (
          <div className="flex items-center justify-center py-8 text-white/40">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading...
          </div>
        ) : keys.length === 0 ? (
          <p className="text-sm text-white/30 py-4">No API keys yet.</p>
        ) : (
          <div className="space-y-2">
            {keys.map((k) => (
              <div
                key={k.key_id}
                className="flex items-center justify-between gap-4 px-4 py-3 rounded-xl bg-white/5 border border-white/5"
              >
                <div className="min-w-0">
                  <p className="text-sm text-white font-medium truncate">{k.name}</p>
                  <p className="text-xs text-white/40">
                    {k.key_id} &middot; Created {new Date(k.created_at).toLocaleDateString()}
                    {k.expires_at && ` \u00b7 Expires ${new Date(k.expires_at).toLocaleDateString()}`}
                  </p>
                </div>
                <button
                  onClick={() => handleRevoke(k.key_id)}
                  className="p-2 rounded-lg text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                  title="Revoke key"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Usage instructions */}
      <div className="glass-card p-6">
        <button
          onClick={() => setShowUsage(!showUsage)}
          className="flex items-center justify-between w-full text-left"
        >
          <h4 className="text-sm font-medium text-white/70">How to use API keys</h4>
          {showUsage
            ? <ChevronUp className="w-4 h-4 text-white/40" />
            : <ChevronDown className="w-4 h-4 text-white/40" />}
        </button>
        {showUsage && (
          <div className="mt-4 space-y-4 text-sm text-white/60">
            <p>
              Pass your key in the <code className="bg-white/10 px-1.5 py-0.5 rounded text-white/80">X-API-Key</code> header on every request.
              Your key is scoped to your user account.
            </p>

            <div>
              <p className="text-white/50 mb-1.5">Upload data:</p>
              <pre className="bg-black/40 rounded-lg px-4 py-3 text-xs text-white/70 overflow-x-auto whitespace-pre">{`curl -X POST /api/v1/data \\
  -H "X-API-Key: md_your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{"content": "Hello world", "user_id": "YOUR_USER_ID"}'`}</pre>
            </div>

            <div>
              <p className="text-white/50 mb-1.5">List your data:</p>
              <pre className="bg-black/40 rounded-lg px-4 py-3 text-xs text-white/70 overflow-x-auto whitespace-pre">{`curl /api/v1/data?user_id=YOUR_USER_ID \\
  -H "X-API-Key: md_your_key_here"`}</pre>
            </div>

            <div>
              <p className="text-white/50 mb-1.5">Python SDK:</p>
              <pre className="bg-black/40 rounded-lg px-4 py-3 text-xs text-white/70 overflow-x-auto whitespace-pre">{`from mem_dog_client import MemDogClient

client = MemDogClient(
    base_url="https://your-api-url",
    api_key="md_your_key_here",
)`}</pre>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 space-y-1.5">
              <p className="text-white/70 font-medium">Tips</p>
              <ul className="list-disc list-inside space-y-1 text-white/50">
                <li>Keys start with <code className="bg-white/10 px-1 py-0.5 rounded text-white/70">md_</code> and are unique to your account</li>
                <li>The raw key is only shown once at creation &mdash; store it securely</li>
                <li>Set an expiry for CI/CD keys; use &ldquo;Never&rdquo; for long-lived personal keys</li>
                <li>Revoke a key immediately if it is compromised</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

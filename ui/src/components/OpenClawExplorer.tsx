'use client';

import { useState, useCallback, useEffect } from 'react';
import {
  Users, Database, Layers, Cpu, BarChart3, Radio,
  Loader2, RefreshCw, AlertTriangle, ChevronDown, ChevronRight,
  Search, X,
} from 'lucide-react';

interface OpenClawExplorerProps {
  gatewayUrl: string;
  apiKey: string;
}

type Resource = 'users' | 'data' | 'memories' | 'embeddings' | 'stats' | 'channels';

const RESOURCES: { id: Resource; label: string; icon: React.ComponentType<{ className?: string }>; path: string }[] = [
  { id: 'users',      label: 'Users',      icon: Users,     path: '/api/v1/users'         },
  { id: 'data',       label: 'Data',       icon: Database,  path: '/api/v1/data'          },
  { id: 'memories',   label: 'Memories',   icon: Layers,    path: '/api/v1/memories'      },
  { id: 'embeddings', label: 'Embeddings', icon: Cpu,       path: '/api/v1/ai/embeddings' },
  { id: 'stats',      label: 'Stats',      icon: BarChart3, path: '/api/v1/stats'         },
  { id: 'channels',   label: 'Channels',   icon: Radio,     path: '/channels'             },
];

function JsonValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 1);

  if (value === null || value === undefined) {
    return <span className="text-white/30 italic">null</span>;
  }
  if (typeof value === 'boolean') {
    return <span className="text-amber-400">{String(value)}</span>;
  }
  if (typeof value === 'number') {
    return <span className="text-blue-400">{value}</span>;
  }
  if (typeof value === 'string') {
    if (value.length > 120) {
      return <span className="text-emerald-400 break-all">&quot;{value.slice(0, 120)}&hellip;&quot;</span>;
    }
    return <span className="text-emerald-400 break-all">&quot;{value}&quot;</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-white/40">[]</span>;
    return (
      <span>
        <button onClick={() => setExpanded(e => !e)} className="inline-flex items-center gap-0.5 text-white/50 hover:text-white/80">
          {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          <span className="text-xs">[{value.length}]</span>
        </button>
        {expanded && (
          <div className="pl-4 border-l border-white/10 ml-1 mt-0.5 space-y-0.5">
            {value.map((item, i) => (
              <div key={i} className="flex gap-1">
                <span className="text-white/20 text-xs shrink-0">{i}:</span>
                <JsonValue value={item} depth={depth + 1} />
              </div>
            ))}
          </div>
        )}
      </span>
    );
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span className="text-white/40">{'{}'}</span>;
    return (
      <span>
        <button onClick={() => setExpanded(e => !e)} className="inline-flex items-center gap-0.5 text-white/50 hover:text-white/80">
          {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          <span className="text-xs">{'{'}...{'}'}</span>
        </button>
        {expanded && (
          <div className="pl-4 border-l border-white/10 ml-1 mt-0.5 space-y-0.5">
            {entries.map(([k, v]) => (
              <div key={k} className="flex gap-1">
                <span className="text-purple-400 text-xs shrink-0">{k}:</span>
                <JsonValue value={v} depth={depth + 1} />
              </div>
            ))}
          </div>
        )}
      </span>
    );
  }
  return <span className="text-white/50">{String(value)}</span>;
}

function ResultRow({ item, index }: { item: Record<string, unknown>; index: number }) {
  const [expanded, setExpanded] = useState(false);

  const id = (item.user_id || item.data_id || item.memory_id || item.embedding_id || item.channel_type || '') as string;
  const name = (item.username || item.display_name || item.name || item.memory_type || item.channel_type || '') as string;
  const detail = (item.email || item.description || item.content_type || item.duration || '') as string;
  const date = (item.created_at || item.updated_at || '') as string;

  return (
    <>
      <tr
        onClick={() => setExpanded(e => !e)}
        className="border-b border-white/[0.06] hover:bg-white/5 cursor-pointer transition-colors"
      >
        <td className="px-3 py-2.5 text-xs text-white/30 w-8">{index + 1}</td>
        <td className="px-3 py-2.5 text-xs font-mono text-white/70 max-w-[180px] truncate">{id || '—'}</td>
        <td className="px-3 py-2.5 text-sm text-white/90 max-w-[200px] truncate">{name || '—'}</td>
        <td className="px-3 py-2.5 text-xs text-white/50 max-w-[200px] truncate">{detail || '—'}</td>
        <td className="px-3 py-2.5 text-xs text-white/30 whitespace-nowrap">
          {date ? new Date(date).toLocaleDateString() : '—'}
        </td>
        <td className="px-3 py-2.5 w-6">
          {expanded ? <ChevronDown className="w-3.5 h-3.5 text-white/30" /> : <ChevronRight className="w-3.5 h-3.5 text-white/30" />}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-white/[0.06]">
          <td colSpan={6} className="px-4 py-3 bg-white/[0.02]">
            <div className="text-xs font-mono max-h-64 overflow-auto">
              <JsonValue value={item} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function OpenClawExplorer({ gatewayUrl, apiKey }: OpenClawExplorerProps) {
  const [resource, setResource] = useState<Resource>('users');
  const [userId, setUserId] = useState('');
  const [results, setResults] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetchCount, setFetchCount] = useState(0);

  const needsUserId = resource === 'data' || resource === 'memories' || resource === 'embeddings';

  const fetchData = useCallback(async () => {
    if (!gatewayUrl) return;
    setLoading(true);
    setError(null);

    const res = RESOURCES.find(r => r.id === resource)!;
    let targetUrl = `${gatewayUrl.replace(/\/+$/, '')}${res.path}`;

    const targetParams = new URLSearchParams();
    if (needsUserId && userId.trim()) {
      targetParams.set(resource === 'data' ? 'user' : 'user_id', userId.trim());
    }
    const qs = targetParams.toString();
    if (qs) targetUrl += `?${qs}`;

    const proxyParams = new URLSearchParams({ url: targetUrl });
    if (apiKey) proxyParams.set('apiKey', apiKey);

    try {
      const resp = await fetch(`/api/gateway-proxy?${proxyParams.toString()}`);
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${text.slice(0, 200)}`);
      }
      const data = await resp.json();
      if (data.error && resp.status >= 400) {
        throw new Error(data.error);
      }
      setResults(data);
      setFetchCount(c => c + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, [gatewayUrl, apiKey, resource, userId, needsUserId]);

  useEffect(() => {
    if (gatewayUrl) fetchData();
  }, [resource]); // eslint-disable-line react-hooks/exhaustive-deps

  const items = extractItems(results);
  const total = extractTotal(results);

  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-18rem)]">
      {/* Resource selector */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {RESOURCES.map(r => (
          <button
            key={r.id}
            onClick={() => setResource(r.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              resource === r.id
                ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-md'
                : 'bg-white/5 text-white/50 hover:text-white/80 hover:bg-white/10 border border-white/10'
            }`}
          >
            <r.icon className="w-3.5 h-3.5" />
            {r.label}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        {needsUserId && (
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/25" />
            <input
              type="text"
              value={userId}
              onChange={e => setUserId(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && fetchData()}
              placeholder="user_id (leave empty for all)"
              className="w-full pl-9 pr-8 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
            />
            {userId && (
              <button onClick={() => { setUserId(''); }} className="absolute right-2 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60">
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )}
        <button
          onClick={fetchData}
          disabled={loading || !gatewayUrl}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white/70 hover:text-white hover:bg-white/10 disabled:opacity-30 transition-all"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          Fetch
        </button>
        {!gatewayUrl && (
          <span className="text-xs text-amber-400/60">Configure Gateway URL above</span>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span className="break-all">{error}</span>
        </div>
      )}

      {/* Results */}
      <div className="flex-1 overflow-auto glass-card">
        {loading && !results && (
          <div className="flex items-center justify-center py-12 text-white/40">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading...
          </div>
        )}

        {!loading && results === null && !error && (
          <div className="flex flex-col items-center justify-center py-12 text-white/30 gap-2">
            <Database className="w-8 h-8" />
            <p className="text-sm">Select a resource and fetch data</p>
          </div>
        )}

        {results !== null && items.length > 0 && (
          <>
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-white/30 w-8">#</th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-white/30">ID</th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-white/30">Name</th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-white/30">Detail</th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-white/30">Date</th>
                  <th className="px-3 py-2 w-6"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <ResultRow key={i} item={item as Record<string, unknown>} index={i} />
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 text-xs text-white/30 border-t border-white/[0.06]">
              Showing {items.length}{total !== null && total !== items.length ? ` of ${total}` : ''} results
              {fetchCount > 0 && <span className="ml-2">via Webhook Gateway</span>}
            </div>
          </>
        )}

        {results !== null && items.length === 0 && !Array.isArray(results) && typeof results === 'object' && (
          <div className="p-4 text-xs font-mono max-h-[500px] overflow-auto">
            <JsonValue value={results} />
          </div>
        )}

        {results !== null && items.length === 0 && Array.isArray(results) && (
          <div className="flex flex-col items-center justify-center py-12 text-white/30 gap-2">
            <Database className="w-8 h-8" />
            <p className="text-sm">No results</p>
          </div>
        )}
      </div>
    </div>
  );
}

function extractItems(data: unknown): unknown[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (typeof data === 'object' && data !== null) {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.items)) return obj.items;
    if (Array.isArray(obj.users)) return obj.users;
    if (Array.isArray(obj.embeddings)) return obj.embeddings;
    if (Array.isArray(obj.data)) return obj.data;
    if (Array.isArray(obj.memories)) return obj.memories;
    if (Array.isArray(obj.channels)) return obj.channels;
  }
  return [];
}

function extractTotal(data: unknown): number | null {
  if (!data || typeof data !== 'object') return null;
  const obj = data as Record<string, unknown>;
  if (typeof obj.total === 'number') return obj.total;
  return null;
}

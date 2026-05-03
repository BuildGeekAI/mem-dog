'use client';

import { useState, useCallback } from 'react';
import {
  Globe, Loader2, Link2, Key, CheckCircle, XCircle, Search,
} from 'lucide-react';
import { getCurrentUserId } from '@/lib/api';

interface CrawlResult {
  status: 'idle' | 'loading' | 'success' | 'error';
  data_ids?: string[];
  memory_id?: string;
  discovered_count?: number;
  error?: string;
}

const ENV_GATEWAY_URL = typeof process.env.NEXT_PUBLIC_WEBHOOK_GATEWAY_URL === 'string'
  ? process.env.NEXT_PUBLIC_WEBHOOK_GATEWAY_URL
  : '';
const ENV_API_KEY = typeof process.env.NEXT_PUBLIC_WEBHOOK_API_KEY === 'string'
  ? process.env.NEXT_PUBLIC_WEBHOOK_API_KEY
  : '';

export default function UrlImport() {
  const [gatewayUrl, setGatewayUrl] = useState(ENV_GATEWAY_URL);
  const [apiKey, setApiKey] = useState(ENV_API_KEY);
  const [url, setUrl] = useState('');
  const [maxDepth, setMaxDepth] = useState(1);
  const [memoryName, setMemoryName] = useState('');
  const [filterPrompt, setFilterPrompt] = useState('');
  const [showConfig, setShowConfig] = useState(!ENV_GATEWAY_URL);
  const [result, setResult] = useState<CrawlResult>({ status: 'idle' });

  const submit = useCallback(async () => {
    if (!url.trim() || !gatewayUrl.trim()) return;

    setResult({ status: 'loading' });

    const userId = getCurrentUserId();
    const crawl: Record<string, unknown> = { max_depth: maxDepth };
    if (memoryName.trim()) crawl.memory_name = memoryName.trim();

    const payload = {
      data: { event: 'url.crawl' },
      telemetry: {
        user_id: userId,
        url: url.trim(),
        crawl,
        ...(filterPrompt.trim() ? { prompt: filterPrompt.trim() } : {}),
      },
    };

    // Use gateway URL as-is if it already has a path (e.g. .../webhook),
    // otherwise append the default webhook path.
    const trimmed = gatewayUrl.replace(/\/+$/, '');
    const hasPath = (() => {
      try { return new URL(trimmed).pathname !== '/'; } catch { return false; }
    })();
    const proxyUrl = hasPath ? trimmed : `${trimmed}/webhooks/generic`;
    const proxyBody: Record<string, unknown> = { url: proxyUrl, payload };
    if (apiKey) proxyBody.apiKey = apiKey;

    try {
      const res = await fetch('/api/webhook-proxy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(proxyBody),
      });

      if (!res.ok) {
        const text = await res.text();
        setResult({ status: 'error', error: `HTTP ${res.status}: ${text.slice(0, 200)}` });
        return;
      }

      const proxyResp = await res.json();

      // The webhook-proxy wraps the upstream response:
      // { status: 200, statusText: "OK", body: "<JSON string>", duration: 123 }
      if (proxyResp.status && proxyResp.status >= 400) {
        setResult({ status: 'error', error: `Gateway HTTP ${proxyResp.status}: ${(proxyResp.body || proxyResp.statusText || '').slice(0, 200)}` });
        return;
      }

      let upstream: any = {};
      if (typeof proxyResp.body === 'string') {
        try { upstream = JSON.parse(proxyResp.body); } catch { upstream = {}; }
      } else if (typeof proxyResp.body === 'object') {
        upstream = proxyResp.body;
      }

      // Extract from nested response structure
      const record = upstream?.record || upstream?.process || upstream || {};
      setResult({
        status: 'success',
        data_ids: record.data_ids || (record.data_id ? [record.data_id] : []),
        memory_id: record.memory_id,
        discovered_count: record.discovered_count ?? record.data_ids?.length ?? 0,
      });
    } catch (err) {
      setResult({ status: 'error', error: String(err) });
    }
  }, [url, gatewayUrl, apiKey, maxDepth, memoryName, filterPrompt]);

  return (
    <div className="space-y-4 max-w-2xl">
      {/* Gateway config (collapsible) */}
      <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] overflow-hidden">
        <button
          onClick={() => setShowConfig(v => !v)}
          className="w-full flex items-center justify-between px-4 py-3 text-sm"
        >
          <div className="flex items-center gap-2 text-white/60">
            <Globe className="w-4 h-4" />
            <span className="font-mono text-xs truncate max-w-md">
              {gatewayUrl || 'Configure Gateway URL'}
            </span>
            {apiKey && <span title="API key set"><Key className="w-3.5 h-3.5 text-emerald-400/60" /></span>}
          </div>
          <span className="text-white/30 text-xs">{showConfig ? 'Hide' : 'Configure'}</span>
        </button>

        {showConfig && (
          <div className="px-4 pb-4 space-y-3 border-t border-white/10 pt-3">
            <div>
              <label className="block text-xs font-medium text-white/50 mb-1">Gateway URL</label>
              <input
                type="url"
                value={gatewayUrl}
                onChange={e => setGatewayUrl(e.target.value)}
                placeholder="http://<GKE_GATEWAY_IP> or http://localhost:8070"
                className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-white/50 mb-1">API Key (optional)</label>
              <input
                type="password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder="Bearer token or API key"
                className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
              />
            </div>
          </div>
        )}
      </div>

      {/* URL Input */}
      <div className="rounded-xl bg-white/[0.03] border border-white/[0.06] p-4 space-y-4">
        <div>
          <label className="block text-xs font-medium text-white/50 mb-1">URL to crawl</label>
          <input
            type="url"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://example.com/docs"
            className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
          />
        </div>

        {/* Depth slider */}
        <div>
          <label className="block text-xs font-medium text-white/50 mb-1">
            Crawl depth: {maxDepth}
          </label>
          <input
            type="range"
            min={1}
            max={3}
            value={maxDepth}
            onChange={e => setMaxDepth(Number(e.target.value))}
            className="w-full accent-primary-500"
          />
          <div className="flex justify-between text-[10px] text-white/25 mt-0.5">
            <span>1 (links on page)</span>
            <span>2</span>
            <span>3 (deep)</span>
          </div>
        </div>

        {/* Memory name */}
        <div>
          <label className="block text-xs font-medium text-white/50 mb-1">
            Memory name <span className="text-white/25">(optional, auto-generated from domain)</span>
          </label>
          <input
            type="text"
            value={memoryName}
            onChange={e => setMemoryName(e.target.value)}
            placeholder="e.g. Project Docs"
            className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
          />
        </div>

        {/* Filter prompt */}
        <div>
          <label className="block text-xs font-medium text-white/50 mb-1">
            Filter prompt <span className="text-white/25">(optional)</span>
          </label>
          <input
            type="text"
            value={filterPrompt}
            onChange={e => setFilterPrompt(e.target.value)}
            placeholder="e.g. PDF documents only"
            className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
          />
        </div>

        {/* Submit */}
        <button
          onClick={submit}
          disabled={!url.trim() || !gatewayUrl.trim() || result.status === 'loading'}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gradient-to-r from-primary-500 to-accent-500 text-white text-sm font-medium shadow-lg shadow-primary-500/20 disabled:opacity-30 disabled:shadow-none hover:brightness-110 transition-all"
        >
          {result.status === 'loading' ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Crawling...
            </>
          ) : (
            <>
              <Search className="w-4 h-4" />
              Crawl &amp; Import
            </>
          )}
        </button>
      </div>

      {/* Results */}
      {result.status === 'success' && (
        <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-4 space-y-2">
          <div className="flex items-center gap-2 text-emerald-400 text-sm font-medium">
            <CheckCircle className="w-4 h-4" />
            Crawl complete
          </div>
          <div className="text-xs text-white/60 space-y-1">
            <p>Discovered: <span className="text-white/80 font-mono">{result.discovered_count}</span> documents</p>
            <p>Imported: <span className="text-white/80 font-mono">{result.data_ids?.length ?? 0}</span> items</p>
            {result.memory_id && (
              <p>Memory: <span className="text-white/80 font-mono">{result.memory_id}</span></p>
            )}
            {result.data_ids && result.data_ids.length > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer text-white/40 hover:text-white/60">Data IDs</summary>
                <ul className="mt-1 space-y-0.5 pl-2">
                  {result.data_ids.map(id => (
                    <li key={id} className="font-mono text-[10px] text-white/50">{id}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        </div>
      )}

      {result.status === 'error' && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-4 space-y-2">
          <div className="flex items-center gap-2 text-red-400 text-sm font-medium">
            <XCircle className="w-4 h-4" />
            Crawl failed
          </div>
          <p className="text-xs text-white/50">{result.error}</p>
        </div>
      )}
    </div>
  );
}

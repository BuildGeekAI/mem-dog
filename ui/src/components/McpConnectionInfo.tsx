'use client';

import { useState, useEffect } from 'react';
import { Check, Copy, Loader2, AlertCircle, Server } from 'lucide-react';
import { listApiKeys, getCurrentUserId } from '@/lib/api';
import type { APIKeyResponse } from '@/types';

export default function McpConnectionInfo() {
  const [apiKeys, setApiKeys] = useState<APIKeyResponse[]>([]);
  const [selectedKeyId, setSelectedKeyId] = useState('');
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const gatewayUrl = process.env.NEXT_PUBLIC_WEBHOOK_GATEWAY_URL || '';
  const mcpEndpoint = gatewayUrl ? `${gatewayUrl}/mcp/sse` : '/mcp/sse';
  const systemApiKey = process.env.NEXT_PUBLIC_API_KEY || '';

  useEffect(() => {
    const userId = getCurrentUserId();
    listApiKeys(userId)
      .then((keys) => {
        setApiKeys(keys);
        if (keys.length > 0) {
          setSelectedKeyId(keys[0].key_id);
        }
      })
      .catch((err) => setError(`Failed to load API keys: ${err.message}`))
      .finally(() => setLoading(false));
  }, []);

  const selectedKey = apiKeys.find((k) => k.key_id === selectedKeyId);
  // Use the system baked-in API key if available, otherwise show the selected key prefix
  const keyForConfig = systemApiKey || (selectedKey ? `md_${selectedKey.key_id.slice(0, 8)}...` : 'md_YOUR_API_KEY');
  const keyIsComplete = !!systemApiKey;

  const configJson = {
    mcpServers: {
      'mem-dog': {
        url: mcpEndpoint,
        headers: {
          'x-api-key': keyForConfig,
        },
      },
    },
  };

  const configStr = JSON.stringify(configJson, null, 2);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(configStr);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = configStr;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const inputClass =
    'w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all';

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
            <Server className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">MCP Server</h3>
            <p className="text-sm text-white/50">
              Connect Claude Desktop, Cursor, or any MCP-compatible agent to mem-dog
            </p>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5 mb-4">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Endpoint URL */}
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-white/70 mb-1.5">SSE Endpoint</label>
            <input type="text" value={mcpEndpoint} readOnly className={inputClass} />
          </div>

          {/* API Key */}
          <div>
            <label className="block text-sm font-medium text-white/70 mb-1.5">API Key</label>
            {keyIsComplete ? (
              <>
                <input type="text" value={keyForConfig} readOnly className={inputClass} />
                <p className="text-xs text-emerald-400/70 mt-1">
                  System API key detected — config is ready to use.
                </p>
              </>
            ) : loading ? (
              <div className="flex items-center gap-2 text-white/40 text-sm py-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading keys...
              </div>
            ) : apiKeys.length > 0 ? (
              <>
                <select
                  value={selectedKeyId}
                  onChange={(e) => setSelectedKeyId(e.target.value)}
                  className={inputClass}
                >
                  {apiKeys.map((k) => (
                    <option key={k.key_id} value={k.key_id}>
                      {k.name} (md_{k.key_id.slice(0, 8)}...)
                    </option>
                  ))}
                </select>
                <p className="text-xs text-white/30 mt-1">
                  Replace the truncated key below with your full API key (shown once at creation).
                </p>
              </>
            ) : (
              <p className="text-sm text-white/40 py-2">
                No API keys found. Create one in Settings &gt; <span className="text-primary-400">API Keys</span> first.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Config snippet */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-medium text-white/70">Claude Desktop / Cursor Config</h4>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 hover:bg-white/10 text-white/70 hover:text-white transition-all"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                Copy config
              </>
            )}
          </button>
        </div>
        <pre className="bg-black/40 border border-white/10 rounded-xl p-4 text-sm text-white/80 overflow-x-auto font-mono">
          {configStr}
        </pre>
        <p className="text-xs text-white/30 mt-2">
          Paste into ~/.claude/claude_desktop_config.json (Claude Desktop) or Cursor MCP settings.
        </p>
      </div>

      {/* Available tools */}
      <div className="glass-card p-6">
        <h4 className="text-sm font-medium text-white/70 mb-3">Available Tools</h4>
        <div className="grid grid-cols-2 gap-2">
          {[
            { name: 'search', desc: 'Semantic/hybrid search' },
            { name: 'add', desc: 'Store text content' },
            { name: 'get', desc: 'Retrieve by ID' },
            { name: 'delete', desc: 'Delete data item' },
            { name: 'entities', desc: 'Knowledge graph search' },
            { name: 'chat', desc: 'RAG chat with citations' },
            { name: 'memories', desc: 'List/create memories' },
            { name: 'list_data', desc: 'Browse stored items' },
          ].map((tool) => (
            <div
              key={tool.name}
              className="flex items-center gap-2 px-3 py-2 bg-white/5 rounded-lg"
            >
              <span className="text-sm font-mono text-primary-400">{tool.name}</span>
              <span className="text-xs text-white/40">{tool.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

'use client';

import { useState, useRef, useEffect, useCallback, KeyboardEvent } from 'react';
import {
  Send, Server, Loader2, Copy, Check, ChevronDown, ChevronUp,
  Search, Plus, FileText, Trash2, Brain, MessageCircle, Database, List,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { api } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ToolName = 'chat' | 'search' | 'add' | 'get' | 'delete' | 'entities' | 'memories' | 'list_data';

interface ToolResult {
  tool: ToolName;
  params: Record<string, string>;
  result: string;
  error?: boolean;
  latencyMs: number;
}

interface ChatMsg {
  role: 'user' | 'assistant';
  content: string;
}

const TOOL_DEFS: { id: ToolName; label: string; icon: typeof Server; desc: string; params: { name: string; placeholder: string; required?: boolean }[] }[] = [
  {
    id: 'chat', label: 'Chat', icon: MessageCircle, desc: 'RAG chat with citations',
    params: [
      { name: 'message', placeholder: 'Ask a question...', required: true },
      { name: 'search_mode', placeholder: 'hybrid' },
      { name: 'max_results', placeholder: '5' },
    ],
  },
  {
    id: 'search', label: 'Search', icon: Search, desc: 'Semantic/hybrid search',
    params: [
      { name: 'query', placeholder: 'Search query...', required: true },
      { name: 'max_results', placeholder: '5' },
      { name: 'search_mode', placeholder: 'hybrid' },
    ],
  },
  {
    id: 'add', label: 'Add', icon: Plus, desc: 'Store text content',
    params: [
      { name: 'content', placeholder: 'Content to store...', required: true },
      { name: 'name', placeholder: 'Item name' },
      { name: 'tags', placeholder: 'tag1,tag2' },
      { name: 'description', placeholder: 'Description' },
      { name: 'memory_type', placeholder: 'conversation' },
    ],
  },
  {
    id: 'get', label: 'Get', icon: FileText, desc: 'Retrieve by ID',
    params: [{ name: 'data_id', placeholder: 'data_01HXYZ...', required: true }],
  },
  {
    id: 'delete', label: 'Delete', icon: Trash2, desc: 'Delete data item',
    params: [{ name: 'data_id', placeholder: 'data_01HXYZ...', required: true }],
  },
  {
    id: 'entities', label: 'Entities', icon: Brain, desc: 'Knowledge graph',
    params: [
      { name: 'query', placeholder: 'Entity search...', required: true },
      { name: 'entity_type', placeholder: 'person, organization...' },
      { name: 'limit', placeholder: '20' },
    ],
  },
  {
    id: 'memories', label: 'Memories', icon: Database, desc: 'List/create memories',
    params: [
      { name: 'action', placeholder: 'list or create' },
      { name: 'memory_type', placeholder: 'conversation' },
      { name: 'name', placeholder: 'Memory name' },
      { name: 'limit', placeholder: '20' },
    ],
  },
  {
    id: 'list_data', label: 'List Data', icon: List, desc: 'Browse stored items',
    params: [
      { name: 'limit', placeholder: '20' },
      { name: 'offset', placeholder: '0' },
    ],
  },
];

// ---------------------------------------------------------------------------
// Tool API calls — goes through the mem-dog API directly (same auth)
// ---------------------------------------------------------------------------

async function callTool(tool: ToolName, params: Record<string, string>): Promise<string> {
  switch (tool) {
    case 'chat': {
      const res = await api.post('/api/v1/ai/query/chat', {
        message: params.message,
        search_mode: params.search_mode || 'hybrid',
        max_results: parseInt(params.max_results || '5'),
      });
      const d = res.data;
      let answer = d.answer || 'No answer generated.';
      if (d.citations?.length) {
        answer += '\n\n**Sources:**\n' + d.citations.map((c: any) =>
          `  [${c.index}] ${c.name || c.data_id} (${(c.similarity * 100).toFixed(0)}%)`
        ).join('\n');
      }
      return answer;
    }
    case 'search': {
      const res = await api.post('/api/v1/ai/query/semantic', {
        query: params.query,
        max_results: parseInt(params.max_results || '5'),
        search_mode: params.search_mode || 'hybrid',
      });
      const records = res.data.records || [];
      if (!records.length) return 'No results found.';
      return records.map((r: any) => {
        const chunk = r.matching_chunks?.[0];
        const sim = chunk?.similarity ? ` (${(chunk.similarity * 100).toFixed(0)}%)` : '';
        const text = chunk?.text?.slice(0, 200) || '';
        return `**${r.name || r.data_id}**${sim}\n${text}`;
      }).join('\n\n');
    }
    case 'add': {
      const formData = new FormData();
      formData.append('content', params.content);
      if (params.name) formData.append('name', params.name);
      if (params.tags) formData.append('tags', params.tags);
      if (params.description) formData.append('description', params.description);
      const res = await api.post('/api/v1/data', formData);
      return `Created: **${res.data.data_id}**`;
    }
    case 'get': {
      const [contentRes, metaRes] = await Promise.all([
        api.get(`/api/v1/data/${params.data_id}`),
        api.get(`/api/v1/data/${params.data_id}/metadata`).catch(() => ({ data: {} })),
      ]);
      const meta = metaRes.data || {};
      let content = typeof contentRes.data === 'string' ? contentRes.data : JSON.stringify(contentRes.data, null, 2);
      if (content.length > 2000) content = content.slice(0, 2000) + '... (truncated)';
      const header = [
        `**ID:** ${params.data_id}`,
        meta.name ? `**Name:** ${meta.name}` : '',
        meta.tags?.length ? `**Tags:** ${meta.tags.join(', ')}` : '',
      ].filter(Boolean).join('\n');
      return `${header}\n\n${content}`;
    }
    case 'delete': {
      await api.delete(`/api/v1/data/${params.data_id}`);
      return `Deleted **${params.data_id}**`;
    }
    case 'entities': {
      const res = await api.get('/api/v1/graph/entities', {
        params: { q: params.query, entity_type: params.entity_type || undefined, limit: parseInt(params.limit || '20') },
      });
      const entities = Array.isArray(res.data) ? res.data : [];
      if (!entities.length) return 'No entities found.';
      return entities.map((e: any) =>
        `**${e.name || e.entity_id}** (${e.entity_type || 'unknown'})`
      ).join('\n');
    }
    case 'memories': {
      if (params.action === 'create') {
        const res = await api.post('/api/v1/memories', {
          memory_type: params.memory_type || 'conversation',
          name: params.name || undefined,
        });
        return `Created memory: **${res.data.memory_id}** (${res.data.memory_type})`;
      }
      const res = await api.get('/api/v1/memories', {
        params: { memory_type: params.memory_type || undefined, limit: parseInt(params.limit || '20') },
      });
      const items = res.data.items || res.data || [];
      if (!items.length) return 'No memories found.';
      return items.map((m: any) =>
        `**${m.name || m.memory_id}** (${m.memory_type}, ${m.data_count ?? '?'} items)`
      ).join('\n');
    }
    case 'list_data': {
      const res = await api.get('/api/v1/list', {
        params: { format: 'meta', limit: parseInt(params.limit || '20'), offset: parseInt(params.offset || '0') },
      });
      const items = res.data.items || res.data || [];
      if (!items.length) return 'No data items found.';
      return items.map((item: any) => {
        const tags = item.tags?.length ? ` [${item.tags.join(', ')}]` : '';
        return `**${item.name || item.data_id}**${tags}`;
      }).join('\n');
    }
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function McpPlayground() {
  const [mode, setMode] = useState<'chat' | 'tools'>('chat');

  // Chat mode state
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);

  // Tool mode state
  const [selectedTool, setSelectedTool] = useState<ToolName>('search');
  const [toolParams, setToolParams] = useState<Record<string, string>>({});
  const [toolResults, setToolResults] = useState<ToolResult[]>([]);
  const [toolLoading, setToolLoading] = useState(false);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, chatLoading]);

  // Auto-resize textarea (keep single-line height matched to send button)
  useEffect(() => {
    const ta = chatInputRef.current;
    if (ta) {
      ta.style.height = '2.5rem';
      if (ta.scrollHeight > 40) {
        ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
      }
    }
  }, [chatInput]);

  // Chat send
  const sendChat = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || chatLoading) return;

    setChatMessages((prev) => [...prev, { role: 'user', content: trimmed }]);
    setChatInput('');
    setChatLoading(true);

    try {
      const result = await callTool('chat', { message: trimmed, search_mode: 'hybrid', max_results: '5' });
      setChatMessages((prev) => [...prev, { role: 'assistant', content: result }]);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Request failed';
      setChatMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${msg}` }]);
    } finally {
      setChatLoading(false);
    }
  }, [chatLoading]);

  const handleChatKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChat(chatInput);
    }
  };

  // Tool run
  const runTool = useCallback(async () => {
    if (toolLoading) return;
    setToolLoading(true);
    const start = Date.now();
    try {
      const result = await callTool(selectedTool, toolParams);
      setToolResults((prev) => [{ tool: selectedTool, params: { ...toolParams }, result, latencyMs: Date.now() - start }, ...prev]);
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Request failed';
      setToolResults((prev) => [{ tool: selectedTool, params: { ...toolParams }, result: msg, error: true, latencyMs: Date.now() - start }, ...prev]);
    } finally {
      setToolLoading(false);
    }
  }, [selectedTool, toolParams, toolLoading]);

  const toolDef = TOOL_DEFS.find((t) => t.id === selectedTool)!;

  return (
    <div className="flex flex-col flex-1 min-h-0 h-full">
      {/* Mode toggle */}
      <div className="flex items-center gap-3 mb-4 flex-shrink-0">
        <div className="flex items-center gap-1 p-1 bg-white/5 rounded-xl">
          <button
            onClick={() => setMode('chat')}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              mode === 'chat'
                ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
                : 'text-white/50 hover:text-white/70 hover:bg-white/5'
            }`}
          >
            <MessageCircle className="w-4 h-4" />
            Chat
          </button>
          <button
            onClick={() => setMode('tools')}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              mode === 'tools'
                ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
                : 'text-white/50 hover:text-white/70 hover:bg-white/5'
            }`}
          >
            <Server className="w-4 h-4" />
            Tools
          </button>
        </div>
        <span className="text-xs text-white/30">MCP Server Playground</span>
      </div>

      {mode === 'chat' ? (
        /* ----------------------------------------------------------------- */
        /* Chat Mode                                                         */
        /* ----------------------------------------------------------------- */
        <div className="flex flex-col flex-1 min-h-0">
          <div className="flex-1 min-h-0 overflow-y-auto px-2">
            {chatMessages.length === 0 && !chatLoading ? (
              <div className="flex flex-col items-center justify-center h-full text-center px-4">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500/20 to-fuchsia-500/20 border border-violet-500/20 flex items-center justify-center mb-6">
                  <Server className="w-8 h-8 text-violet-400" />
                </div>
                <h3 className="text-lg font-semibold text-white/80 mb-2">MCP Chat</h3>
                <p className="text-sm text-white/40 mb-8 max-w-md">
                  Chat with your mem-dog data through the MCP server. Ask questions and get answers with citations.
                </p>
                <div className="flex flex-wrap justify-center gap-2 max-w-lg">
                  {['What data do I have stored?', 'Summarize my recent uploads', 'Search for meeting notes'].map((s) => (
                    <button
                      key={s}
                      onClick={() => sendChat(s)}
                      className="px-3.5 py-2 text-sm text-white/60 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-xl transition-all"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="max-w-3xl mx-auto py-4 space-y-4">
                {chatMessages.map((msg, idx) => (
                  <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                        msg.role === 'user'
                          ? 'bg-primary-500/15 border border-primary-500/20 text-white/90'
                          : 'bg-white/5 border border-white/10'
                      }`}
                    >
                      {msg.role === 'user' ? (
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                      ) : (
                        <div className="prose prose-invert prose-sm max-w-none text-white/80 leading-relaxed prose-p:my-1.5 prose-strong:text-white/90 prose-code:text-violet-300 prose-code:bg-white/5 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-a:text-violet-400">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {chatLoading && (
                  <div className="flex justify-start">
                    <div className="bg-white/5 border border-white/10 rounded-2xl px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {[0, 1, 2].map((i) => (
                          <div key={i} className="w-2 h-2 rounded-full bg-violet-400/60 animate-pulse" style={{ animationDelay: `${i * 200}ms` }} />
                        ))}
                        <span className="text-xs text-white/30 ml-1">Thinking...</span>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            )}
          </div>

          {/* Chat input */}
          <div className="flex-shrink-0 border-t border-white/10 bg-white/[0.02] px-2 py-3">
            <div className="max-w-3xl mx-auto flex items-start gap-2">
              <textarea
                ref={chatInputRef}
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={handleChatKey}
                placeholder="Ask about your data..."
                rows={1}
                className="flex-1 box-border min-h-10 max-h-40 resize-none rounded-xl bg-white/5 border border-white/10 focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 px-4 py-2.5 text-sm text-white/90 placeholder-white/30 outline-none transition-all"
              />
              <button
                onClick={() => sendChat(chatInput)}
                disabled={!chatInput.trim() || chatLoading}
                className="flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-500 flex items-center justify-center text-white disabled:opacity-30 disabled:cursor-not-allowed hover:shadow-lg hover:shadow-violet-500/25 transition-all"
              >
                {chatLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* ----------------------------------------------------------------- */
        /* Tools Mode                                                        */
        /* ----------------------------------------------------------------- */
        <div className="flex flex-col flex-1 min-h-0 gap-4">
          {/* Tool selector */}
          <div className="flex flex-wrap gap-1.5">
            {TOOL_DEFS.filter((t) => t.id !== 'chat').map((t) => (
              <button
                key={t.id}
                onClick={() => { setSelectedTool(t.id); setToolParams({}); }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  selectedTool === t.id
                    ? 'bg-violet-500/20 text-violet-300 border border-violet-500/30'
                    : 'bg-white/5 text-white/50 border border-white/10 hover:text-white/70 hover:bg-white/10'
                }`}
              >
                <t.icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            ))}
          </div>

          {/* Params form */}
          <div className="glass-card p-4">
            <div className="flex items-center gap-2 mb-3">
              <toolDef.icon className="w-4 h-4 text-violet-400" />
              <span className="text-sm font-medium text-white/80">{toolDef.label}</span>
              <span className="text-xs text-white/30">{toolDef.desc}</span>
            </div>
            <div className="grid gap-2">
              {toolDef.params.map((p) => (
                <div key={p.name} className="flex items-center gap-2">
                  <label className="text-xs text-white/50 w-24 text-right flex-shrink-0">
                    {p.name}{p.required && <span className="text-red-400">*</span>}
                  </label>
                  <input
                    type="text"
                    value={toolParams[p.name] || ''}
                    onChange={(e) => setToolParams((prev) => ({ ...prev, [p.name]: e.target.value }))}
                    placeholder={p.placeholder}
                    onKeyDown={(e) => { if (e.key === 'Enter') runTool(); }}
                    className="flex-1 bg-black/30 text-white border border-white/10 rounded-lg px-3 py-2 text-sm placeholder:text-white/20 focus:outline-none focus:border-violet-500/50 transition-all"
                  />
                </div>
              ))}
            </div>
            <button
              onClick={runTool}
              disabled={toolLoading}
              className="mt-3 flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white hover:shadow-lg hover:shadow-violet-500/25 transition-all disabled:opacity-50"
            >
              {toolLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Run
            </button>
          </div>

          {/* Results */}
          <div className="flex-1 min-h-0 overflow-y-auto space-y-3">
            {toolResults.map((r, idx) => (
              <div key={idx} className={`glass-card p-4 ${r.error ? 'border-red-500/30' : ''}`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-mono text-violet-400">{r.tool}</span>
                  <span className="text-[10px] text-white/20">{r.latencyMs}ms</span>
                  {Object.entries(r.params).filter(([, v]) => v).map(([k, v]) => (
                    <span key={k} className="text-[10px] text-white/30 bg-white/5 px-1.5 py-0.5 rounded">
                      {k}={v.length > 30 ? v.slice(0, 30) + '...' : v}
                    </span>
                  ))}
                </div>
                <div className={`prose prose-invert prose-sm max-w-none ${r.error ? 'text-red-400' : 'text-white/80'} leading-relaxed prose-p:my-1 prose-strong:text-white/90`}>
                  <ReactMarkdown>{r.result}</ReactMarkdown>
                </div>
              </div>
            ))}
            {toolResults.length === 0 && (
              <div className="text-center text-white/20 text-sm py-8">
                Run a tool to see results here
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

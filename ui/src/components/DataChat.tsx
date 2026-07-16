'use client';

import { useState, useRef, useEffect, useCallback, KeyboardEvent } from 'react';
import { Send, MessageCircle, Sparkles, ChevronDown, ChevronUp, ExternalLink, Loader2, Database, Settings2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { chatWithData, getCurrentUserId, listMemories } from '@/lib/api';
import type { ChatCitation, ChatWithDataResponse } from '@/lib/api';
import type { MemoryResponse } from '@/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatMsg {
  role: 'user' | 'assistant';
  content: string;
  citations?: ChatCitation[];
  model?: string | null;
  latencyMs?: number;
}

// ---------------------------------------------------------------------------
// Citation badge — renders [N] as a clickable violet pill
// ---------------------------------------------------------------------------

function CitationBadge({ n, onClick }: { n: number; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center justify-center min-w-[1.4rem] h-5 px-1 text-[11px] font-semibold rounded-full bg-violet-500/20 text-violet-300 hover:bg-violet-500/30 transition-colors cursor-pointer align-baseline mx-0.5"
    >
      {n}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Citations panel — collapsible list below an assistant message
// ---------------------------------------------------------------------------

function CitationsPanel({ citations, expanded, onToggle }: { citations: ChatCitation[]; expanded: boolean; onToggle: () => void }) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-2">
      <button onClick={onToggle} className="flex items-center gap-1.5 text-xs text-white/40 hover:text-white/60 transition-colors">
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        {citations.length} source{citations.length !== 1 ? 's' : ''}
      </button>
      {expanded && (
        <div className="mt-2 space-y-2">
          {citations.map((c) => (
            <div key={c.index} className="flex gap-2 p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
              <span className="flex-shrink-0 inline-flex items-center justify-center w-5 h-5 text-[10px] font-bold rounded-full bg-violet-500/20 text-violet-300">
                {c.index}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-white/70 truncate">{c.name || c.data_id.substring(0, 12)}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${c.similarity >= 0.8 ? 'bg-emerald-500/15 text-emerald-400' : c.similarity >= 0.6 ? 'bg-amber-500/15 text-amber-400' : 'bg-red-500/15 text-red-400'}`}>
                    {(c.similarity * 100).toFixed(0)}%
                  </span>
                  <a
                    href={`/?tab=data&id=${c.data_id}`}
                    className="text-violet-400/60 hover:text-violet-400 transition-colors"
                    title="View source"
                  >
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                <p className="text-[11px] text-white/35 line-clamp-3 leading-relaxed">{c.chunk_text}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Render assistant message with citation badges inline
// ---------------------------------------------------------------------------

function AssistantMessage({ content, citations, onCitationClick }: { content: string; citations: ChatCitation[]; onCitationClick: () => void }) {
  // Split content on [N] patterns to interleave markdown and citation badges
  const parts = content.split(/(\[\d+\])/g);

  return (
    <div className="prose prose-invert prose-sm max-w-none text-white/80 leading-relaxed
      prose-p:my-1.5 prose-headings:text-white/90 prose-strong:text-white/90
      prose-code:text-violet-300 prose-code:bg-white/5 prose-code:px-1 prose-code:py-0.5 prose-code:rounded
      prose-pre:bg-white/5 prose-pre:border prose-pre:border-white/10 prose-pre:rounded-lg
      prose-a:text-violet-400 prose-ul:my-1.5 prose-li:my-0.5">
      {parts.map((part, i) => {
        const citationMatch = part.match(/^\[(\d+)\]$/);
        if (citationMatch) {
          const n = parseInt(citationMatch[1], 10);
          return <CitationBadge key={i} n={n} onClick={onCitationClick} />;
        }
        return <ReactMarkdown key={i}>{part}</ReactMarkdown>;
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Thinking dots
// ---------------------------------------------------------------------------

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1.5 px-4 py-3">
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-2 h-2 rounded-full bg-violet-400/60 animate-pulse"
            style={{ animationDelay: `${i * 200}ms` }}
          />
        ))}
      </div>
      <span className="text-xs text-white/30 ml-1">Thinking...</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Suggestion chips
// ---------------------------------------------------------------------------

const SUGGESTIONS = [
  'What topics are in my data?',
  'Summarize my most recent uploads',
  'What patterns do you see across my documents?',
  'Find connections between my data items',
];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function DataChat() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [expandedCitations, setExpandedCitations] = useState<Record<number, boolean>>({});
  const [memories, setMemories] = useState<MemoryResponse[]>([]);
  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(null);
  const [searchMode, setSearchMode] = useState<'vector' | 'fts' | 'hybrid' | 'graph' | 'full'>('vector');
  const [rerankMethod, setRerankMethod] = useState<'none' | 'rrf' | 'mmr' | 'cross_encoder'>('none');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Fetch memories on mount
  useEffect(() => {
    const userId = getCurrentUserId();
    if (userId) {
      listMemories({ userId }).then((res) => setMemories(res.items || [])).catch(() => {});
    }
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Auto-resize textarea (keep single-line height matched to send button)
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = '2.5rem';
      if (ta.scrollHeight > 40) {
        ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
      }
    }
  }, [input]);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const userMsg: ChatMsg = { role: 'user', content: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    // Build history from prior messages (last 10 turns)
    const history = [...messages, userMsg]
      .slice(-10)
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      const res: ChatWithDataResponse = await chatWithData({
        message: trimmed,
        history: history.slice(0, -1), // exclude the current message
        user_id: getCurrentUserId(),
        ...(selectedMemoryId ? { memory_id: selectedMemoryId } : {}),
        search_mode: searchMode,
        ...(rerankMethod !== 'none' ? { rerank: { method: rerankMethod } } : {}),
      });

      const assistantMsg: ChatMsg = {
        role: 'assistant',
        content: res.answer,
        citations: res.citations,
        model: res.model,
        latencyMs: res.latency_ms,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorContent = err?.response?.data?.detail || err?.message || 'Something went wrong. Please try again.';
      setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${errorContent}` }]);
    } finally {
      setLoading(false);
    }
  }, [messages, loading, selectedMemoryId, searchMode, rerankMethod]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const toggleCitations = (msgIdx: number) => {
    setExpandedCitations((prev) => ({ ...prev, [msgIdx]: !prev[msgIdx] }));
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex flex-col flex-1 min-h-0 h-full">
      {/* Messages area */}
      <div className="flex-1 min-h-0 overflow-y-auto px-2 md:px-4">
        {isEmpty && !loading ? (
          /* Welcome state */
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500/20 to-fuchsia-500/20 border border-violet-500/20 flex items-center justify-center mb-6">
              <MessageCircle className="w-8 h-8 text-violet-400" />
            </div>
            <h3 className="text-lg font-semibold text-white/80 mb-2">Chat with your data</h3>
            <p className="text-sm text-white/40 mb-8 max-w-md">
              Ask questions about your stored data and get answers with citations linking back to source documents.
            </p>
            <div className="flex flex-wrap justify-center gap-2 max-w-lg">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="px-3.5 py-2 text-sm text-white/60 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-xl transition-all"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Message list */
          <div className="max-w-3xl mx-auto py-4 space-y-4">
            {messages.map((msg, idx) => (
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
                    <>
                      <AssistantMessage
                        content={msg.content}
                        citations={msg.citations || []}
                        onCitationClick={() => toggleCitations(idx)}
                      />
                      {msg.citations && msg.citations.length > 0 && (
                        <CitationsPanel
                          citations={msg.citations}
                          expanded={!!expandedCitations[idx]}
                          onToggle={() => toggleCitations(idx)}
                        />
                      )}
                      {(msg.model || msg.latencyMs) && (
                        <div className="mt-2 flex items-center gap-2 text-[10px] text-white/20">
                          {msg.model && <span>{msg.model}</span>}
                          {msg.latencyMs && <span>{(msg.latencyMs / 1000).toFixed(1)}s</span>}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white/5 border border-white/10 rounded-2xl">
                  <ThinkingDots />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="flex-shrink-0 border-t border-white/10 bg-white/[0.02] px-2 md:px-4 py-3">
        {/* Search controls row */}
        <div className="max-w-3xl mx-auto mb-2">
          <div className="flex items-center gap-3 flex-wrap">
            {/* Memory scope */}
            {memories.length > 0 && (
              <div className="flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-white/30" />
                <select
                  value={selectedMemoryId || ''}
                  onChange={(e) => setSelectedMemoryId(e.target.value || null)}
                  className="text-xs bg-white/5 border border-white/10 rounded-lg px-2 py-1.5 text-white/70 outline-none focus:border-violet-500/50 cursor-pointer"
                >
                  <option value="">All Data</option>
                  {memories.map((m) => (
                    <option key={m.memory_id} value={m.memory_id}>
                      {m.name} ({m.data_count} items)
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Search mode selector */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-white/30 uppercase tracking-wider">Search</span>
              <div className="flex rounded-lg border border-white/10 overflow-hidden">
                {(['vector', 'hybrid', 'graph', 'full'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setSearchMode(mode)}
                    className={`px-2 py-1 text-[11px] transition-colors ${
                      searchMode === mode
                        ? 'bg-violet-500/20 text-violet-300 font-medium'
                        : 'text-white/40 hover:text-white/60 hover:bg-white/5'
                    }`}
                  >
                    {mode === 'vector' ? 'Vector' : mode === 'hybrid' ? 'Hybrid' : mode === 'graph' ? 'Graph' : 'Full'}
                  </button>
                ))}
              </div>
            </div>

            {/* Advanced toggle */}
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-1 text-[10px] text-white/30 hover:text-white/50 transition-colors"
            >
              <Settings2 className="w-3 h-3" />
              {showAdvanced ? 'Less' : 'More'}
            </button>
          </div>

          {/* Advanced options (collapsed by default) */}
          {showAdvanced && (
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-white/30">Rerank</span>
                <select
                  value={rerankMethod}
                  onChange={(e) => setRerankMethod(e.target.value as any)}
                  className="text-xs bg-white/5 border border-white/10 rounded-lg px-2 py-1 text-white/70 outline-none focus:border-violet-500/50 cursor-pointer"
                >
                  <option value="none">None</option>
                  <option value="rrf">RRF</option>
                  <option value="mmr">MMR (diversity)</option>
                  <option value="cross_encoder">Cross-encoder</option>
                </select>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-white/30">FTS</span>
                <button
                  onClick={() => setSearchMode('fts')}
                  className={`px-2 py-0.5 text-[11px] rounded border transition-colors ${
                    searchMode === 'fts'
                      ? 'border-violet-500/40 bg-violet-500/20 text-violet-300'
                      : 'border-white/10 text-white/40 hover:text-white/60'
                  }`}
                >
                  BM25 only
                </button>
              </div>
            </div>
          )}
        </div>
        <div className="max-w-3xl mx-auto flex items-start gap-2">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your data..."
              rows={1}
              className="w-full box-border min-h-10 max-h-40 resize-none rounded-xl bg-white/5 border border-white/10 focus:border-violet-500/50 focus:ring-2 focus:ring-violet-500/20 px-4 py-2.5 pr-12 text-sm text-white/90 placeholder-white/30 outline-none transition-all"
            />
          </div>
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-500 flex items-center justify-center text-white disabled:opacity-30 disabled:cursor-not-allowed hover:shadow-lg hover:shadow-violet-500/25 transition-all"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}

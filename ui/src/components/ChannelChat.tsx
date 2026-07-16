'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import {
  Send, Loader2, Paperclip, X, MessageSquare, Globe, Key,
  CheckCircle, XCircle, AlertTriangle, FileText, Image, Film,
} from 'lucide-react';
import { getCurrentUserId, createData, listWebhooks } from '@/lib/api';
import type { Webhook } from '@/types';

const CHANNELS = [
  'webchat', 'generic', 'telegram', 'slack', 'discord',
  'whatsapp', 'msteams', 'email', 'signal', 'matrix',
] as const;

const DEFAULT_GATEWAY_URL = typeof process.env.NEXT_PUBLIC_WEBHOOK_GATEWAY_URL === 'string'
  ? process.env.NEXT_PUBLIC_WEBHOOK_GATEWAY_URL
  : '';

interface Attachment {
  file: File;
  preview?: string;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'system';
  text: string;
  attachments?: { name: string; type: string; size: number }[];
  timestamp: Date;
  status?: 'sending' | 'accepted' | 'error';
  traceId?: string;
  messageId?: string;
  channelType?: string;
  error?: string;
}

function fileIcon(type: string) {
  if (type.startsWith('image/')) return Image;
  if (type.startsWith('video/')) return Film;
  return FileText;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ChannelChat() {
  const [gatewayUrl, setGatewayUrl] = useState(DEFAULT_GATEWAY_URL);
  const [apiKey, setApiKey] = useState('');
  const [channelType, setChannelType] = useState<string>('webchat');
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [sending, setSending] = useState(false);
  const [showConfig, setShowConfig] = useState(true);

  // Webhook ID support
  const [userWebhooks, setUserWebhooks] = useState<Webhook[]>([]);
  const [selectedWebhookId, setSelectedWebhookId] = useState<string>('');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load user's webhooks
  useEffect(() => {
    listWebhooks().then(whs => setUserWebhooks(whs.filter(w => w.status === 'active'))).catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addFile = useCallback((files: FileList | null) => {
    if (!files) return;
    const newAttachments: Attachment[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const att: Attachment = { file };
      if (file.type.startsWith('image/')) {
        att.preview = URL.createObjectURL(file);
      }
      newAttachments.push(att);
    }
    setAttachments(prev => [...prev, ...newAttachments]);
  }, []);

  const removeAttachment = useCallback((idx: number) => {
    setAttachments(prev => {
      const next = [...prev];
      if (next[idx].preview) URL.revokeObjectURL(next[idx].preview!);
      next.splice(idx, 1);
      return next;
    });
  }, []);

  const apiBaseUrl = (typeof process.env.NEXT_PUBLIC_API_URL === 'string' && process.env.NEXT_PUBLIC_API_URL)
    || '';

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text && attachments.length === 0) return;
    if (!gatewayUrl) return;

    const msgId = crypto.randomUUID();
    const userId = getCurrentUserId();

    const userMsg: ChatMessage = {
      id: msgId,
      role: 'user',
      text,
      attachments: attachments.map(a => ({
        name: a.file.name,
        type: a.file.type,
        size: a.file.size,
      })),
      timestamp: new Date(),
      status: 'sending',
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    const currentAttachments = [...attachments];
    setAttachments([]);
    setSending(true);

    try {
      const uploadedAttachments = await Promise.all(
        currentAttachments.map(async (a) => {
          const result = await createData(a.file, {
            name: a.file.name,
            tags: ['source:channel_chat', `channel:${channelType}`],
            forwardToWebhook: true,
          });
          const contentUrl = `${apiBaseUrl}/api/v1/data/${result.data_id}?user_id=${encodeURIComponent(userId)}`;
          return {
            name: a.file.name,
            type: a.file.type,
            size: a.file.size,
            data_id: result.data_id,
            url: contentUrl,
          };
        }),
      );

      const payload: Record<string, unknown> = {
        text,
        user_id: userId,
        session_id: `webchat-${userId}`,
        message_id: msgId,
        channel_id: 'webchat-ui',
      };
      if (uploadedAttachments.length > 0) {
        payload.attachments = uploadedAttachments;
      }

      let trimmed = gatewayUrl.replace(/\/+$/, '');
      // Auto-prepend http:// if no protocol specified
      if (trimmed && !/^https?:\/\//i.test(trimmed)) {
        trimmed = `http://${trimmed}`;
      }
      // Validate it's a proper URL before sending
      try {
        new URL(trimmed);
      } catch {
        throw new Error(`Invalid Gateway URL: "${gatewayUrl}". Please enter a valid URL like http://34.36.80.165 or https://your-gateway.example.com`);
      }
      const hasPath = (() => { try { return new URL(trimmed).pathname !== '/'; } catch { return false; } })();
      const webhookPath = selectedWebhookId || channelType;
      const url = hasPath ? trimmed : `${trimmed}/webhooks/${webhookPath}`;

      const proxyBody: Record<string, unknown> = { url, payload };
      if (apiKey) proxyBody.apiKey = apiKey;

      const res = await fetch('/api/webhook-proxy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(proxyBody),
      });

      const data = await res.json();

      if (data.status >= 200 && data.status < 300) {
        const body = typeof data.body === 'string' ? JSON.parse(data.body) : data.body;
        setMessages(prev =>
          prev.map(m =>
            m.id === msgId ? { ...m, status: 'accepted' as const, traceId: body.trace_id, messageId: body.message_id, channelType: body.channel_type } : m,
          ),
        );
        const sysMsg: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'system',
          text: `Accepted via ${body.channel_type || channelType}`,
          timestamp: new Date(),
          traceId: body.trace_id,
          messageId: body.message_id,
        };
        setMessages(prev => [...prev, sysMsg]);
      } else {
        const errorText = data.body || data.statusText || 'Unknown error';
        setMessages(prev =>
          prev.map(m =>
            m.id === msgId ? { ...m, status: 'error' as const, error: `HTTP ${data.status}: ${errorText}` } : m,
          ),
        );
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Network error';
      setMessages(prev =>
        prev.map(m =>
          m.id === msgId ? { ...m, status: 'error' as const, error: errMsg } : m,
        ),
      );
    } finally {
      setSending(false);
      currentAttachments.forEach(a => {
        if (a.preview) URL.revokeObjectURL(a.preview);
      });
      inputRef.current?.focus();
    }
  }, [input, attachments, gatewayUrl, apiKey, channelType, selectedWebhookId, apiBaseUrl]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    },
    [sendMessage],
  );

  return (
    <div className="flex flex-col h-[calc(100vh-16rem)] max-h-[700px]">
      {/* Config bar */}
      <div className="glass-card mb-4">
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
              <label className="block text-xs font-medium text-white/50 mb-1">API Key</label>
              <div className="relative">
                <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/25" />
                <input
                  type="password"
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  placeholder="Leave empty if gateway is in open mode"
                  className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-white/50 mb-1">Channel Type</label>
              <select
                value={channelType}
                onChange={e => setChannelType(e.target.value)}
                disabled={!!selectedWebhookId}
                className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50 disabled:opacity-40"
              >
                {CHANNELS.map(ch => (
                  <option key={ch} value={ch}>{ch.charAt(0).toUpperCase() + ch.slice(1)}</option>
                ))}
              </select>
            </div>
            {userWebhooks.length > 0 && (
              <div>
                <label className="block text-xs font-medium text-white/50 mb-1">
                  Webhook Endpoint
                  <span className="text-white/30 ml-1">(overrides channel type)</span>
                </label>
                <select
                  value={selectedWebhookId}
                  onChange={e => {
                    setSelectedWebhookId(e.target.value);
                    // Sync channel type display from webhook
                    const wh = userWebhooks.find(w => w.webhook_id === e.target.value);
                    if (wh) setChannelType(wh.channel_type);
                  }}
                  className="w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50"
                >
                  <option value="">Use channel type (legacy)</option>
                  {userWebhooks.map(wh => (
                    <option key={wh.webhook_id} value={wh.webhook_id}>
                      {wh.name || wh.webhook_id} ({wh.channel_type})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto glass-card p-4 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-white/30 gap-3">
            <MessageSquare className="w-10 h-10" />
            <p className="text-sm">Send a message through a channel webhook</p>
            <p className="text-xs text-white/20">Messages are forwarded through the webhook pipeline</p>
          </div>
        )}

        {messages.map(msg => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                msg.role === 'user'
                  ? 'bg-gradient-to-r from-primary-500/80 to-accent-500/80 text-white'
                  : 'bg-white/5 border border-white/10 text-white/70'
              }`}
            >
              {msg.text && <p className="whitespace-pre-wrap break-words">{msg.text}</p>}

              {msg.attachments && msg.attachments.length > 0 && (
                <div className="mt-2 space-y-1">
                  {msg.attachments.map((a, i) => {
                    const Icon = fileIcon(a.type);
                    return (
                      <div key={i} className="flex items-center gap-2 text-xs opacity-80">
                        <Icon className="w-3.5 h-3.5" />
                        <span className="truncate">{a.name}</span>
                        <span className="text-white/40">{formatSize(a.size)}</span>
                      </div>
                    );
                  })}
                </div>
              )}

              <div className="flex items-center gap-1.5 mt-1.5">
                <span className="text-[10px] opacity-50">
                  {msg.timestamp.toLocaleTimeString()}
                </span>
                {msg.status === 'sending' && <Loader2 className="w-3 h-3 animate-spin opacity-50" />}
                {msg.status === 'accepted' && <CheckCircle className="w-3 h-3 text-emerald-400" />}
                {msg.status === 'error' && <XCircle className="w-3 h-3 text-red-400" />}
                {msg.traceId && (
                  <span className="text-[10px] font-mono opacity-30" title="Trace ID">
                    {msg.traceId.substring(0, 8)}
                  </span>
                )}
              </div>

              {msg.error && (
                <div className="mt-1.5 flex items-start gap-1.5 text-xs text-red-400/80">
                  <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                  <span className="break-all">{msg.error}</span>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Attachment preview */}
      {attachments.length > 0 && (
        <div className="flex gap-2 px-2 py-2 mt-2 overflow-x-auto">
          {attachments.map((att, idx) => (
            <div
              key={idx}
              className="relative flex-shrink-0 rounded-lg border border-white/10 bg-white/5 p-2 flex items-center gap-2 max-w-[200px]"
            >
              {att.preview ? (
                <img src={att.preview} alt="" className="w-8 h-8 rounded object-cover" />
              ) : (
                (() => { const Icon = fileIcon(att.file.type); return <Icon className="w-5 h-5 text-white/40" />; })()
              )}
              <div className="min-w-0">
                <p className="text-xs text-white/70 truncate">{att.file.name}</p>
                <p className="text-[10px] text-white/30">{formatSize(att.file.size)}</p>
              </div>
              <button
                onClick={() => removeAttachment(idx)}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500/80 flex items-center justify-center hover:bg-red-400"
              >
                <X className="w-3 h-3 text-white" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input bar */}
      <div className="flex items-start gap-2 mt-3">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={e => addFile(e.target.files)}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex-shrink-0 w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white/50 hover:text-white hover:bg-white/10 transition-colors"
          title="Attach files"
        >
          <Paperclip className="w-4 h-4" />
        </button>

        <div className="flex-1 relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={gatewayUrl ? 'Type a message...' : 'Configure the Gateway URL first'}
            disabled={!gatewayUrl || sending}
            rows={1}
            className="w-full box-border min-h-10 max-h-32 px-4 py-2.5 pr-12 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-primary-500/50 resize-none disabled:opacity-40"
            onInput={e => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = 'auto';
              target.style.height = `${Math.min(target.scrollHeight, 128)}px`;
            }}
          />
        </div>

        <button
          onClick={sendMessage}
          disabled={(!input.trim() && attachments.length === 0) || !gatewayUrl || sending}
          className="flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-r from-primary-500 to-accent-500 flex items-center justify-center text-white shadow-lg shadow-primary-500/30 disabled:opacity-30 disabled:shadow-none hover:brightness-110 transition-all"
        >
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}

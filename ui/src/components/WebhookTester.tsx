'use client';

import { useState, useCallback } from 'react';
import { Send, CheckCircle, XCircle, Loader2, Copy, RotateCcw, Globe, Key, FileJson, Mic, MicOff, AlertCircle } from 'lucide-react';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
import { getCurrentUserId, listMemories } from '@/lib/api';

const DEFAULT_BACKEND_URL = typeof process.env.NEXT_PUBLIC_WEBHOOK_GATEWAY_URL === 'string'
  ? process.env.NEXT_PUBLIC_WEBHOOK_GATEWAY_URL
  : '';
const DEFAULT_API_KEY = typeof process.env.NEXT_PUBLIC_WEBHOOK_API_KEY === 'string'
  ? process.env.NEXT_PUBLIC_WEBHOOK_API_KEY
  : '';

/** Canonical two-part payload: data + telemetry only. */
const DEFAULT_PLAIN_PAYLOAD = {
  data: { event: 'test', hello: 'world' },
  telemetry: {},
};

/** Build minimal Universal Data Envelope with current user ID for webhook testing. */
function buildEnvelopeTemplate(userId: string) {
  return {
    data: {
      schema_version: '1.0',
      origin: { source_type: 'other', user_id: userId },
      payload: { mime_type: 'text/plain' },
      context: {},
      content_text: 'Test message from UI (universal envelope)',
      extensions: {},
    },
    telemetry: { source_type: 'other', user_id: userId },
  };
}

export default function WebhookTester() {
  const [backendUrl, setBackendUrl] = useState(DEFAULT_BACKEND_URL);
  const [apiKey, setApiKey] = useState(DEFAULT_API_KEY);
  const [payload, setPayload] = useState(
    () => JSON.stringify(DEFAULT_PLAIN_PAYLOAD, null, 2),
  );
  const [sending, setSending] = useState(false);
  const [response, setResponse] = useState<{
    status: number;
    statusText: string;
    body: string;
    duration: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Dictation support -- accumulates raw speech, then wraps it into JSON
  // when the user stops listening.
  const [dictationText, setDictationText] = useState('');

  const {
    isSupported: speechSupported,
    isListening,
    interimTranscript,
    error: speechError,
    startListening: rawStartListening,
    stopListening: rawStopListening,
  } = useSpeechRecognition({
    onResult: (transcript) => {
      setDictationText((prev) => (prev ? prev + ' ' + transcript : transcript));
    },
  });

  const handleStartDictation = () => {
    setDictationText('');
    rawStartListening();
  };

  const handleStopDictation = () => {
    rawStopListening();
    // Convert accumulated dictation into a JSON payload
    const text = (dictationText + (interimTranscript ? ' ' + interimTranscript : '')).trim();
    if (text) {
      const jsonPayload = JSON.stringify(
        {
          data: { event: 'dictation', message: text },
          telemetry: { source: 'voice', timestamp: new Date().toISOString(), user_id: getCurrentUserId() },
        },
        null,
        2,
      );
      setPayload(jsonPayload);
    }
  };

  const handleSend = useCallback(async () => {
    if (!backendUrl.trim()) {
      setError('Backend URL is required');
      return;
    }

    try {
      JSON.parse(payload);
    } catch {
      setError('Invalid JSON payload');
      return;
    }

    setError(null);
    setResponse(null);
    setSending(true);

    try {
      const parsedPayload = JSON.parse(payload) as { data?: Record<string, unknown>; telemetry?: Record<string, unknown> };
      // Always inject the current user_id into telemetry so the webhook
      // pipeline stores data under the correct user (not the env-var default).
      parsedPayload.telemetry = parsedPayload.telemetry ?? {};
      const tel = parsedPayload.telemetry as Record<string, unknown>;
      if (!tel.user_id) {
        tel.user_id = getCurrentUserId();
      }
      // Add current active session to telemetry so the webhook associates the test with this session
      try {
        const { items } = await listMemories({ memoryType: 'session', active: true, limit: 1 });
        const activeSession = items[0];
        if (activeSession?.memory_id) {
          parsedPayload.telemetry = parsedPayload.telemetry ?? {};
          const telemetry = parsedPayload.telemetry as Record<string, unknown>;
          telemetry.session_id = activeSession.memory_id;
          const existingList = Array.isArray(telemetry.memory_list) ? telemetry.memory_list as string[] : [];
          if (!existingList.includes(activeSession.memory_id)) {
            telemetry.memory_list = [...existingList, activeSession.memory_id];
          }
        }
      } catch {
        // No session or API unreachable; send without session
      }

      const res = await fetch('/api/webhook-proxy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: backendUrl.trim(),
          apiKey: apiKey.trim() || undefined,
          payload: parsedPayload,
        }),
      });

      const data = await res.json();

      if (data.error && !data.status) {
        setError(data.error);
        setResponse({ status: 0, statusText: 'Proxy Error', body: data.error, duration: 0 });
      } else {
        setResponse({
          status: data.status,
          statusText: data.statusText,
          body: data.body,
          duration: data.duration,
        });
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Request failed';
      setError(message);
      setResponse({ status: 0, statusText: 'Network Error', body: message, duration: 0 });
    } finally {
      setSending(false);
    }
  }, [backendUrl, apiKey, payload]);

  const handleReset = () => {
    setBackendUrl(DEFAULT_BACKEND_URL);
    setApiKey(DEFAULT_API_KEY);
    setPayload(JSON.stringify(DEFAULT_PLAIN_PAYLOAD, null, 2));
    setResponse(null);
    setError(null);
  };

  const handleLoadEnvelopeTemplate = () => {
    setPayload(JSON.stringify(buildEnvelopeTemplate(getCurrentUserId()), null, 2));
    setError(null);
  };

  const handleCopyCurl = () => {
    const apiKeyHeader = apiKey.trim()
      ? `\\\n     -H 'x-api-key: ${apiKey.trim()}' `
      : '';
    const curl = `curl -X POST ${backendUrl.trim()} ${apiKeyHeader}\\\n     -H 'Content-Type: application/json' \\\n     -d '${payload.replace(/\n/g, '').replace(/\s{2,}/g, ' ')}'`;
    navigator.clipboard.writeText(curl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isSuccess = response && response.status >= 200 && response.status < 300;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Send className="w-5 h-5 text-primary-400" />
              Webhook Tester
            </h2>
            <p className="text-sm text-white/50 mt-1">
              Send test webhook requests to your backend endpoint
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCopyCurl}
              disabled={!backendUrl.trim()}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <Copy className="w-4 h-4" />
              {copied ? 'Copied!' : 'Copy as cURL'}
            </button>
            <button
              onClick={handleLoadEnvelopeTemplate}
              type="button"
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-all"
              title="Load envelope template (data + telemetry with origin, payload, context, content_text)"
            >
              <FileJson className="w-4 h-4" />
              Envelope template
            </button>
            <button
              onClick={handleReset}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-all"
            >
              <RotateCcw className="w-4 h-4" />
              Reset
            </button>
          </div>
        </div>

        {/* Form */}
        <div className="space-y-4">
          {/* Backend URL */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-white/70 mb-2">
              <Globe className="w-4 h-4 text-primary-400" />
              Backend URL
            </label>
            <input
              type="url"
              value={backendUrl}
              onChange={e => setBackendUrl(e.target.value)}
              placeholder="https://mem-dog-webhook-gw-dev-2lyzlc04.uc.gateway.dev/webhook"
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/25 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 font-mono text-sm transition-all"
            />
          </div>

          {/* API Key */}
          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-white/70 mb-2">
              <Key className="w-4 h-4 text-accent-400" />
              API Key
              <span className="text-white/30 text-xs">(optional)</span>
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="Your x-api-key value"
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/25 focus:outline-none focus:ring-2 focus:ring-accent-500/50 focus:border-accent-500/50 font-mono text-sm transition-all"
            />
          </div>

          {/* JSON Payload */}
          <div>
            <div className="flex items-center justify-between gap-4 mb-2">
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-white/70">
                  <FileJson className="w-4 h-4 text-emerald-400" />
                  JSON Payload
                </label>
                <p className="text-xs text-white/40 mt-1">
                  Default is plain <code className="bg-white/10 px-1 rounded">event</code>/<code className="bg-white/10 px-1 rounded">data</code>. Use &quot;Envelope template&quot; for Universal format.
                </p>
              </div>
              {speechSupported && (
                <div className="flex items-center gap-2">
                  {isListening && (
                    <span className="flex items-center gap-1.5 text-xs text-accent-400 animate-pulse">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                      Listening... (stop to convert to JSON)
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={isListening ? handleStopDictation : handleStartDictation}
                    disabled={sending}
                    title={isListening ? 'Stop and convert to JSON' : 'Dictate — speech will be wrapped into JSON'}
                    className={`
                      flex items-center justify-center gap-2 px-3 h-9 rounded-xl transition-all duration-300 text-xs font-medium
                      ${isListening
                        ? 'bg-red-500/20 text-red-400 border border-red-500/30 shadow-lg shadow-red-500/10 animate-pulse'
                        : 'bg-white/5 text-white/50 border border-white/10 hover:bg-white/10 hover:text-white/80'
                      }
                      disabled:opacity-40 disabled:cursor-not-allowed
                    `}
                  >
                    {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                    {isListening ? 'Stop' : 'Dictate'}
                  </button>
                </div>
              )}
            </div>

            {speechError && (
              <div className="flex items-center gap-2 text-xs text-red-400 mb-2">
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                <span>{speechError}</span>
              </div>
            )}

            {/* Live dictation preview while listening */}
            {isListening && (
              <div className="mb-3 px-4 py-3 rounded-xl bg-accent-500/5 border border-accent-500/20">
                <p className="text-xs font-medium text-accent-400 mb-1.5">Dictating:</p>
                <p className="text-sm text-white/80 min-h-[1.5rem]">
                  {dictationText}
                  {interimTranscript && (
                    <span className="text-white/30 italic"> {interimTranscript}</span>
                  )}
                  {!dictationText && !interimTranscript && (
                    <span className="text-white/30">Speak now...</span>
                  )}
                </p>
              </div>
            )}

            <textarea
              value={payload}
              onChange={e => setPayload(e.target.value)}
              rows={6}
              spellCheck={false}
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-white/25 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50 font-mono text-sm transition-all resize-y"
            />

            {!speechSupported && (
              <p className="text-white/25 text-xs mt-1.5">
                Dictation requires Chrome or Edge.
              </p>
            )}
          </div>

          {/* Error */}
          {error && !response && (
            <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              <XCircle className="w-4 h-4 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Send Button */}
          <button
            onClick={handleSend}
            disabled={sending}
            className="w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-primary-500 to-accent-500 hover:from-primary-400 hover:to-accent-400 shadow-lg shadow-primary-500/25 hover:shadow-primary-500/40 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Sending...
              </>
            ) : (
              <>
                <Send className="w-5 h-5" />
                Send Webhook Request
              </>
            )}
          </button>
        </div>
      </div>

      {/* Response */}
      {response && (
        <div className="glass-card p-6 animate-in">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              Response
              {isSuccess ? (
                <CheckCircle className="w-5 h-5 text-emerald-400" />
              ) : (
                <XCircle className="w-5 h-5 text-red-400" />
              )}
            </h3>
            <span className="text-xs text-white/40 font-mono">{response.duration}ms</span>
          </div>

          {/* Status Badge */}
          <div className="flex items-center gap-3 mb-4">
            <span
              className={`inline-flex items-center px-3 py-1 rounded-lg text-sm font-bold font-mono ${
                isSuccess
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25'
                  : 'bg-red-500/15 text-red-400 border border-red-500/25'
              }`}
            >
              {response.status} {response.statusText}
            </span>
          </div>

          {/* Response Body */}
          <div className="relative">
            <pre className="p-4 rounded-xl bg-black/30 border border-white/5 text-sm text-white/80 font-mono overflow-x-auto whitespace-pre-wrap break-words max-h-80 overflow-y-auto">
              {response.body || '(empty response)'}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

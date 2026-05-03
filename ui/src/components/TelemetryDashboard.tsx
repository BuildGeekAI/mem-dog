'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import {
  Radio, RefreshCw, ChevronDown, ChevronRight, AlertCircle,
  CheckCircle2, Clock, Loader2, Inbox, X, Activity,
  Server, ArrowRight, Zap,
} from 'lucide-react';
import type { TelemetrySpan, TelemetryTrace } from '@/types';
import { listMemories, getMemoryData, getDataAsText, formatDate } from '@/lib/api';

const AUTO_REFRESH_INTERVAL_MS = 10_000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseTagValue(tags: string[], prefix: string): string | undefined {
  const tag = tags?.find((t) => t.startsWith(`${prefix}:`));
  return tag ? tag.slice(prefix.length + 1) : undefined;
}

function buildSpanFromItem(item: {
  data_id: string;
  name?: string | null;
  tags?: string[] | null;
  created_at: string;
}): TelemetrySpan | null {
  const tags = item.tags ?? [];
  const traceId = parseTagValue(tags, 'trace_id');
  const spanId = parseTagValue(tags, 'span_id');
  if (!traceId || !spanId) return null;

  const stage = parseTagValue(tags, 'stage') ?? '';
  const service = parseTagValue(tags, 'service') ?? stage;
  const statusCode = parseTagValue(tags, 'status') as TelemetrySpan['status']['code'] | undefined ?? 'UNSET';
  const kind = parseTagValue(tags, 'kind') as TelemetrySpan['kind'] | undefined ?? 'INTERNAL';
  const parentSpanId = parseTagValue(tags, 'parent_span_id') ?? null;

  return {
    trace_id: traceId,
    span_id: spanId,
    parent_span_id: parentSpanId,
    name: item.name?.split(' | ')[0] ?? stage,
    kind,
    service_name: service,
    service_type: '',
    status: { code: statusCode },
    start_time: item.created_at,
    data_id: item.data_id,
  };
}

function groupIntoTraces(spans: TelemetrySpan[]): TelemetryTrace[] {
  const byTrace = new Map<string, TelemetrySpan[]>();
  for (const span of spans) {
    const arr = byTrace.get(span.trace_id) ?? [];
    arr.push(span);
    byTrace.set(span.trace_id, arr);
  }

  return Array.from(byTrace.entries())
    .map(([traceId, traceSpans]): TelemetryTrace => {
      const sorted = [...traceSpans].sort(
        (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
      );
      const hasError = sorted.some((s) => s.status.code === 'ERROR');
      const rootSpan = sorted.find((s) => !s.parent_span_id) ?? sorted[0];
      const lastSpan = sorted[sorted.length - 1];

      let durationMs: number | undefined;
      if (rootSpan?.start_time && lastSpan?.end_time) {
        durationMs =
          new Date(lastSpan.end_time).getTime() -
          new Date(rootSpan.start_time).getTime();
      } else if (rootSpan?.start_time && lastSpan?.start_time) {
        durationMs =
          new Date(lastSpan.start_time).getTime() -
          new Date(rootSpan.start_time).getTime();
      }

      return {
        trace_id: traceId,
        spans: sorted,
        start_time: rootSpan?.start_time ?? '',
        end_time: lastSpan?.end_time ?? undefined,
        duration_ms: durationMs,
        status: hasError ? 'ERROR' : sorted.length >= 3 ? 'OK' : 'PARTIAL',
        services: [...new Set(sorted.map((s) => s.service_name))],
      };
    })
    .sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime());
}

function buildTree(
  spans: TelemetrySpan[]
): Array<TelemetrySpan & { depth: number }> {
  const byId = new Map(spans.map((s) => [s.span_id, s]));
  const children = new Map<string | null, TelemetrySpan[]>();
  for (const span of spans) {
    const parent = span.parent_span_id ?? null;
    const arr = children.get(parent) ?? [];
    arr.push(span);
    children.set(parent, arr);
  }

  const result: Array<TelemetrySpan & { depth: number }> = [];
  const visit = (spanId: string | null, depth: number) => {
    const kids = children.get(spanId) ?? [];
    for (const kid of kids) {
      result.push({ ...kid, depth });
      visit(kid.span_id, depth + 1);
    }
  };
  visit(null, 0);

  if (result.length === 0) {
    spans.forEach((s, i) => result.push({ ...s, depth: i }));
  }
  return result;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ code }: { code: string }) {
  if (code === 'OK')
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
        <CheckCircle2 className="w-3 h-3" /> OK
      </span>
    );
  if (code === 'ERROR')
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/15 text-red-400 border border-red-500/20">
        <AlertCircle className="w-3 h-3" /> ERROR
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-500/15 text-amber-400 border border-amber-500/20">
      <Clock className="w-3 h-3" /> {code}
    </span>
  );
}

function KindBadge({ kind }: { kind: string }) {
  const map: Record<string, string> = {
    SERVER: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
    CLIENT: 'bg-purple-500/15 text-purple-400 border-purple-500/20',
    CONSUMER: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/20',
    PRODUCER: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
    INTERNAL: 'bg-slate-500/15 text-slate-400 border-slate-500/20',
  };
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${map[kind] ?? map['INTERNAL']}`}>
      {kind}
    </span>
  );
}

function DurationPill({ ms }: { ms?: number | null }) {
  if (ms == null) return <span className="text-white/30 text-xs">—</span>;
  const label = ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`;
  return <span className="text-white/50 text-xs font-mono">{label}</span>;
}

function SpanDetailPanel({
  span,
  onClose,
}: {
  span: TelemetrySpan;
  onClose: () => void;
}) {
  const [fullSpan, setFullSpan] = useState<TelemetrySpan | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!span.data_id) return;
    setLoading(true);
    getDataAsText(span.data_id)
      .then((text) => {
        try {
          setFullSpan({ ...JSON.parse(text), data_id: span.data_id });
        } catch {
          setFullSpan(span);
        }
      })
      .catch(() => setFullSpan(span))
      .finally(() => setLoading(false));
  }, [span.data_id]);

  const s = fullSpan ?? span;

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-md z-50 flex flex-col glass-card border-l border-white/10 shadow-2xl animate-in">
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-primary-400" />
          <span className="font-semibold text-sm text-white truncate max-w-xs">{s.name}</span>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-white/10 text-white/50 hover:text-white">
          <X className="w-4 h-4" />
        </button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-10">
          <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />
        </div>
      )}

      {!loading && (
        <div className="flex-1 overflow-y-auto p-5 space-y-5 text-sm">
          {/* Identity */}
          <div className="flex flex-wrap gap-2 items-center">
            <KindBadge kind={s.kind} />
            <StatusBadge code={s.status.code} />
            <DurationPill ms={s.duration_ms} />
          </div>

          {/* IDs */}
          <div className="space-y-2">
            {[
              ['trace_id', s.trace_id],
              ['span_id', s.span_id],
              ['parent_span_id', s.parent_span_id ?? '—'],
            ].map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <span className="text-white/40 font-mono text-xs w-28 flex-shrink-0">{k}</span>
                <span className="text-white/70 font-mono text-xs break-all">{v}</span>
              </div>
            ))}
          </div>

          {/* Timing */}
          <div className="space-y-1 border-t border-white/5 pt-4">
            <p className="text-white/30 text-xs uppercase tracking-wider mb-2">Timing</p>
            {[
              ['start_time', s.start_time],
              ['end_time', s.end_time ?? '—'],
            ].map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <span className="text-white/40 font-mono text-xs w-28 flex-shrink-0">{k}</span>
                <span className="text-white/70 text-xs">{v ? formatDate(v as string) : '—'}</span>
              </div>
            ))}
          </div>

          {/* Service */}
          <div className="space-y-1 border-t border-white/5 pt-4">
            <p className="text-white/30 text-xs uppercase tracking-wider mb-2">Service</p>
            <div className="flex gap-2">
              <span className="text-white/40 text-xs w-28">name</span>
              <span className="text-white/70 text-xs">{s.service_name}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-white/40 text-xs w-28">type</span>
              <span className="text-white/70 text-xs font-mono">{s.service_type || '—'}</span>
            </div>
          </div>

          {/* Attributes */}
          {s.attributes && Object.keys(s.attributes).length > 0 && (
            <div className="border-t border-white/5 pt-4">
              <p className="text-white/30 text-xs uppercase tracking-wider mb-2">Attributes</p>
              <div className="space-y-1.5">
                {Object.entries(s.attributes).map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <span className="text-white/40 font-mono text-xs w-36 flex-shrink-0">{k}</span>
                    <span className="text-white/70 text-xs break-all">
                      {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Events */}
          {s.events && s.events.length > 0 && (
            <div className="border-t border-white/5 pt-4">
              <p className="text-white/30 text-xs uppercase tracking-wider mb-2">
                Events ({s.events.length})
              </p>
              <div className="space-y-2">
                {s.events.map((ev, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <Zap className="w-3 h-3 text-primary-400 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-white/80 text-xs font-medium">{ev.name}</p>
                      <p className="text-white/30 text-[10px] font-mono">{ev.timestamp}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SpanRow({
  span,
  depth,
  traceDurationMs,
  onClick,
}: {
  span: TelemetrySpan;
  depth: number;
  traceDurationMs: number;
  onClick: () => void;
}) {
  const barWidthPct =
    traceDurationMs > 0 && span.duration_ms
      ? Math.max(4, Math.min(100, (span.duration_ms / traceDurationMs) * 100))
      : null;

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-2 px-4 py-2 hover:bg-white/5 transition-colors text-left group"
    >
      <div style={{ width: depth * 16 }} className="flex-shrink-0" />
      <div className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{
          background:
            span.status.code === 'OK'
              ? '#34d399'
              : span.status.code === 'ERROR'
              ? '#f87171'
              : '#fbbf24',
        }}
      />
      <span className="text-white/80 text-xs font-mono group-hover:text-white transition-colors w-52 truncate">
        {span.name}
      </span>
      <KindBadge kind={span.kind} />
      <StatusBadge code={span.status.code} />
      {barWidthPct !== null && (
        <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden mx-2">
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary-500 to-accent-500 opacity-70"
            style={{ width: `${barWidthPct}%` }}
          />
        </div>
      )}
      {barWidthPct === null && <div className="flex-1" />}
      <DurationPill ms={span.duration_ms} />
    </button>
  );
}

function TraceRow({
  trace,
  onSpanClick,
}: {
  trace: TelemetryTrace;
  onSpanClick: (span: TelemetrySpan) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const tree = buildTree(trace.spans);
  const traceDuration = trace.duration_ms ?? 0;

  return (
    <div className="glass-card rounded-xl overflow-hidden border border-white/10">
      {/* Trace header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 px-5 py-3.5 hover:bg-white/5 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-4 h-4 text-white/40 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-white/40 flex-shrink-0" />
        )}

        <span className="font-mono text-xs text-primary-300 w-20 flex-shrink-0">
          {trace.trace_id.slice(0, 8)}…
        </span>

        <span className="text-white/40 text-xs flex-shrink-0">
          {trace.spans.length} span{trace.spans.length !== 1 ? 's' : ''}
        </span>

        <div className="flex items-center gap-1 flex-1 min-w-0 overflow-hidden">
          {trace.services.map((svc, i) => (
            <span key={svc} className="flex items-center gap-1">
              <span className="text-white/60 text-xs truncate max-w-[120px]">{svc}</span>
              {i < trace.services.length - 1 && (
                <ArrowRight className="w-3 h-3 text-white/20 flex-shrink-0" />
              )}
            </span>
          ))}
        </div>

        <DurationPill ms={trace.duration_ms} />

        <div className="flex-shrink-0">
          {trace.status === 'OK' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          ) : trace.status === 'ERROR' ? (
            <AlertCircle className="w-4 h-4 text-red-400" />
          ) : (
            <Clock className="w-4 h-4 text-amber-400" />
          )}
        </div>

        <span className="text-white/30 text-xs flex-shrink-0 w-24 text-right">
          {formatDate(trace.start_time)}
        </span>
      </button>

      {/* Span waterfall */}
      {expanded && (
        <div className="border-t border-white/5 bg-black/10">
          {tree.map((span) => (
            <SpanRow
              key={span.span_id}
              span={span}
              depth={span.depth}
              traceDurationMs={traceDuration}
              onClick={() => onSpanClick(span)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function TelemetryDashboard() {
  const [traces, setTraces] = useState<TelemetryTrace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OK' | 'ERROR'>('ALL');
  const [stageFilter, setStageFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSpan, setSelectedSpan] = useState<TelemetrySpan | null>(null);
  const autoRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadTelemetry = useCallback(async (isRefresh = false) => {
    try {
      isRefresh ? setRefreshing(true) : setLoading(true);
      setError(null);

      const memoriesResp = await listMemories({ memoryType: 'tracing', limit: 50 });
      const memories = memoriesResp.items ?? [];

      const allSpans: TelemetrySpan[] = [];
      for (const mem of memories) {
        try {
          const resp = await getMemoryData(mem.memory_id, { limit: 200 });
          const items = resp.items ?? [];
          const spans = items
            .map((item: Parameters<typeof buildSpanFromItem>[0]) => buildSpanFromItem(item))
            .filter(Boolean) as TelemetrySpan[];
          allSpans.push(...spans);
        } catch {
          // skip memories that fail to load
        }
      }

      setTraces(groupIntoTraces(allSpans));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (!isRefresh) setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadTelemetry();
  }, [loadTelemetry]);

  useEffect(() => {
    if (autoRefreshRef.current) clearInterval(autoRefreshRef.current);
    if (autoRefresh) {
      autoRefreshRef.current = setInterval(() => loadTelemetry(true), AUTO_REFRESH_INTERVAL_MS);
    }
    return () => {
      if (autoRefreshRef.current) clearInterval(autoRefreshRef.current);
    };
  }, [autoRefresh, loadTelemetry]);

  // Derived stats
  const totalTraces = traces.length;
  const okTraces = traces.filter((t) => t.status === 'OK').length;
  const errorTraces = traces.filter((t) => t.status === 'ERROR').length;
  const successRate = totalTraces > 0 ? Math.round((okTraces / totalTraces) * 100) : 0;
  const avgDuration =
    traces.length > 0
      ? traces.reduce((acc, t) => acc + (t.duration_ms ?? 0), 0) / traces.length
      : 0;

  // All stages present across all spans
  const allStages = [
    'ALL',
    ...Array.from(new Set(traces.flatMap((t) => t.spans.map((s) => s.name.split('.')[1] ?? s.service_name)))),
  ];

  // Filter
  const filtered = traces.filter((t) => {
    if (statusFilter !== 'ALL' && t.status !== statusFilter) return false;
    if (stageFilter !== 'ALL' && !t.spans.some((s) => s.name.includes(stageFilter) || s.service_name.includes(stageFilter))) return false;
    if (searchQuery && !t.trace_id.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-primary-400 animate-spin mr-3" />
        <span className="text-white/60">Loading telemetry…</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-primary-500/20 to-accent-500/20 border border-primary-500/30">
            <Radio className="w-5 h-5 text-primary-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Pipeline Telemetry</h2>
            <p className="text-sm text-white/40">OTel-compatible spans · tracing memories</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              autoRefresh
                ? 'bg-emerald-500/20 border border-emerald-500/30 text-emerald-400'
                : 'bg-white/5 border border-white/10 text-white/50 hover:text-white'
            }`}
          >
            <Activity className={`w-4 h-4 ${autoRefresh ? 'animate-pulse' : ''}`} />
            {autoRefresh ? 'Live (10s)' : 'Auto-refresh'}
          </button>
          <button
            onClick={() => loadTelemetry(true)}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white/60 hover:text-white text-sm transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total Traces', value: totalTraces, icon: Server, color: 'text-primary-400' },
          { label: 'Success Rate', value: `${successRate}%`, icon: CheckCircle2, color: 'text-emerald-400' },
          { label: 'Errors', value: errorTraces, icon: AlertCircle, color: errorTraces > 0 ? 'text-red-400' : 'text-white/30' },
          { label: 'Avg Duration', value: avgDuration >= 1000 ? `${(avgDuration / 1000).toFixed(1)}s` : `${Math.round(avgDuration)}ms`, icon: Clock, color: 'text-accent-400' },
        ].map((stat) => (
          <div key={stat.label} className="glass-card rounded-xl p-4 border border-white/10">
            <div className="flex items-center gap-2 mb-1">
              <stat.icon className={`w-4 h-4 ${stat.color}`} />
              <span className="text-white/40 text-xs">{stat.label}</span>
            </div>
            <p className="text-2xl font-bold text-white">{stat.value}</p>
          </div>
        ))}
      </div>

      {error && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <div>
            <p className="font-medium text-sm">Could not load tracing memories</p>
            <p className="text-xs opacity-70 mt-0.5">{error}</p>
            <p className="text-xs opacity-50 mt-1">Tracing memories are created automatically when webhooks are processed.</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 p-1 bg-white/5 rounded-lg">
          {(['ALL', 'OK', 'ERROR'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setStatusFilter(f)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                statusFilter === f
                  ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow'
                  : 'text-white/50 hover:text-white'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        <select
          value={stageFilter}
          onChange={(e) => setStageFilter(e.target.value)}
          className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white/70 text-xs focus:outline-none focus:border-primary-500/50"
        >
          {allStages.map((s) => (
            <option key={s} value={s} className="bg-slate-900">
              {s === 'ALL' ? 'All stages' : s}
            </option>
          ))}
        </select>

        <input
          type="text"
          placeholder="Search trace ID…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white/70 text-xs placeholder-white/25 focus:outline-none focus:border-primary-500/50 w-48"
        />

        {(statusFilter !== 'ALL' || stageFilter !== 'ALL' || searchQuery) && (
          <button
            onClick={() => { setStatusFilter('ALL'); setStageFilter('ALL'); setSearchQuery(''); }}
            className="text-xs text-white/40 hover:text-white flex items-center gap-1"
          >
            <X className="w-3 h-3" /> Clear
          </button>
        )}

        <span className="ml-auto text-xs text-white/30">
          {filtered.length} of {totalTraces} trace{totalTraces !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Trace list */}
      {!error && filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Inbox className="w-10 h-10 text-white/20 mb-3" />
          <p className="text-white/40 font-medium">No traces found</p>
          <p className="text-white/25 text-sm mt-1">
            {totalTraces === 0
              ? 'Send a webhook to generate telemetry spans.'
              : 'Try adjusting the filters.'}
          </p>
        </div>
      )}

      <div className="space-y-3">
        {filtered.map((trace) => (
          <TraceRow
            key={trace.trace_id}
            trace={trace}
            onSpanClick={setSelectedSpan}
          />
        ))}
      </div>

      {/* Span detail panel */}
      {selectedSpan && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
            onClick={() => setSelectedSpan(null)}
          />
          <SpanDetailPanel span={selectedSpan} onClose={() => setSelectedSpan(null)} />
        </>
      )}
    </div>
  );
}

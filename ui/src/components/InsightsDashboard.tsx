'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  BarChart3, Database, Layers, Brain, Eye, RefreshCw,
  FileType, Cpu, Loader2, AlertCircle, Zap, Trash2,
} from 'lucide-react';
import type { PerUserStats } from '@/types';
import { getUserStats, refreshUserStats, getCurrentUserId, dropTokenUsage, listData, listMemories } from '@/lib/api';
import { useProject } from '@/lib/project-context';
import { FolderOpen } from 'lucide-react';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatTokens(tokens: number): string {
  if (tokens === 0) return '0';
  if (tokens < 1_000) return tokens.toString();
  if (tokens < 1_000_000) return `${(tokens / 1_000).toFixed(1)}K`;
  return `${(tokens / 1_000_000).toFixed(2)}M`;
}

function StatCard({ icon: Icon, label, value, sub, color }: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sub?: string;
  color: string;
}) {
  return (
    <div className="glass-card p-5">
      <div className="relative z-10 flex items-start gap-4">
        <div className={`flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center shadow-lg`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
        <div className="min-w-0">
          <p className="text-sm text-white/50 font-medium">{label}</p>
          <p className="text-2xl font-bold text-white mt-0.5">{value}</p>
          {sub && <p className="text-xs text-white/40 mt-1">{sub}</p>}
        </div>
      </div>
    </div>
  );
}

function BreakdownBar({ items }: { items: Record<string, number> }) {
  const entries = Object.entries(items).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  if (total === 0) return <p className="text-sm text-white/40">No data</p>;

  const colors = [
    'from-indigo-500 to-purple-500',
    'from-cyan-500 to-blue-500',
    'from-pink-500 to-rose-500',
    'from-amber-500 to-orange-500',
    'from-emerald-500 to-teal-500',
    'from-violet-500 to-fuchsia-500',
    'from-lime-500 to-green-500',
    'from-red-500 to-pink-500',
  ];

  return (
    <div className="space-y-2">
      {entries.slice(0, 8).map(([key, count], idx) => {
        const pct = Math.round((count / total) * 100);
        return (
          <div key={key}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="text-white/70 truncate max-w-[60%]">{key}</span>
              <span className="text-white/50 font-mono text-xs">{count} ({pct}%)</span>
            </div>
            <div className="h-2 rounded-full bg-white/5 overflow-hidden">
              <div
                className={`h-full rounded-full bg-gradient-to-r ${colors[idx % colors.length]}`}
                style={{ width: `${Math.max(pct, 2)}%` }}
              />
            </div>
          </div>
        );
      })}
      {entries.length > 8 && (
        <p className="text-xs text-white/30">+{entries.length - 8} more</p>
      )}
    </div>
  );
}

function SectionCard({ title, icon: Icon, children }: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className="glass-card p-6">
      <div className="relative z-10">
        <div className="flex items-center gap-2 mb-4">
          <Icon className="w-5 h-5 text-white/60" />
          <h3 className="text-lg font-semibold text-white">{title}</h3>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function InsightsDashboard() {
  const [stats, setStats] = useState<PerUserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dropConfirm, setDropConfirm] = useState(false);
  const [dropping, setDropping] = useState(false);
  const [projectStats, setProjectStats] = useState<{ dataCount: number; memoryCount: number } | null>(null);

  const userId = getCurrentUserId();
  const { selectedProjectId, projects } = useProject();
  const selectedProject = projects.find(p => p.project_id === selectedProjectId);

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      // Try cached stats first; if 404, compute them
      let data: PerUserStats;
      try {
        data = await getUserStats(userId);
      } catch (err: any) {
        if (err?.response?.status === 404) {
          data = await refreshUserStats(userId);
        } else {
          throw err;
        }
      }
      setStats(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || (err instanceof Error ? err.message : 'Failed to load insights'));
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchStats();
    const id = setInterval(fetchStats, 60_000);
    return () => clearInterval(id);
  }, [fetchStats]);

  // Fetch project-scoped counts
  useEffect(() => {
    if (!selectedProjectId) {
      setProjectStats(null);
      return;
    }
    (async () => {
      try {
        const [dataRes, memRes] = await Promise.all([
          listData(undefined, { limit: 1, projectId: selectedProjectId }),
          listMemories({ projectId: selectedProjectId, limit: 1 }),
        ]);
        setProjectStats({ dataCount: dataRes.total, memoryCount: memRes.total });
      } catch {
        setProjectStats(null);
      }
    })();
  }, [selectedProjectId]);

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      setError(null);
      await refreshUserStats(userId);
      const data = await getUserStats(userId);
      setStats(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || (err instanceof Error ? err.message : 'Failed to refresh insights'));
    } finally {
      setRefreshing(false);
    }
  };

  const handleDropTokens = async () => {
    try {
      setDropping(true);
      setError(null);
      await dropTokenUsage(userId);
      setDropConfirm(false);
      await fetchStats();
    } catch (err: any) {
      setError(err?.response?.data?.detail || (err instanceof Error ? err.message : 'Failed to drop token usage'));
    } finally {
      setDropping(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 text-white/40 animate-spin" />
        <span className="ml-3 text-white/40">Loading insights...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-6 h-6" />
            Insights
          </h2>
          {stats?.computed_at && (
            <p className="text-sm text-white/40 mt-1">
              Last computed: {new Date(stats.computed_at).toLocaleString()}
            </p>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium text-sm transition-all duration-300 bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg shadow-primary-500/30 hover:shadow-primary-500/50 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Computing...' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div className="glass-card p-4 border-amber-500/30">
          <div className="relative z-10 flex items-center gap-3 text-amber-400">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <p className="text-sm">{error}</p>
          </div>
        </div>
      )}

      {stats && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard
              icon={Database}
              label="Data Items"
              value={stats.data.total_items.toLocaleString()}
              sub={formatBytes(stats.data.total_size_bytes)}
              color="from-indigo-500 to-purple-500"
            />
            <StatCard
              icon={Layers}
              label="Memories"
              value={stats.memories.total_memories.toLocaleString()}
              sub={`${stats.memories.active_sessions} active sessions`}
              color="from-cyan-500 to-blue-500"
            />
            <StatCard
              icon={Eye}
              label="Viewpoints"
              value={stats.viewpoints.total_viewpoints.toLocaleString()}
              sub={`${Object.keys(stats.viewpoints.by_engine).length} engines`}
              color="from-amber-500 to-orange-500"
            />
            <StatCard
              icon={Brain}
              label="Embeddings"
              value={stats.embeddings.total_embeddings.toLocaleString()}
              sub={`${Object.keys(stats.embeddings.by_engine).length} engines`}
              color="from-pink-500 to-rose-500"
            />
            <StatCard
              icon={Zap}
              label="LLM Tokens"
              value={formatTokens(stats.tokens?.total_tokens ?? 0)}
              sub={`${(stats.tokens?.total_requests ?? 0).toLocaleString()} requests`}
              color="from-emerald-500 to-teal-500"
            />
          </div>

          {/* Project-scoped insights */}
          {selectedProject && projectStats && (
            <div className="glass-card p-5">
              <div className="relative z-10">
                <div className="flex items-center gap-2 mb-3">
                  <FolderOpen className="w-4 h-4 text-white/50" />
                  <h3 className="text-sm font-semibold text-white/80">
                    Project: {selectedProject.display_name || selectedProject.name}
                  </h3>
                  <span className="text-[10px] font-mono text-white/30 bg-white/5 px-1.5 py-0.5 rounded">
                    {selectedProject.project_id}
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-white/40">Data Items</p>
                    <p className="text-lg font-bold text-white">{projectStats.dataCount.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-xs text-white/40">Memories</p>
                    <p className="text-lg font-bold text-white">{projectStats.memoryCount.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-xs text-white/40">Organization</p>
                    <p className="text-sm font-medium text-white/70">{selectedProject.org_id}</p>
                  </div>
                  <div>
                    <p className="text-xs text-white/40">Status</p>
                    <p className="text-sm font-medium text-emerald-400">{selectedProject.status}</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Breakdown Sections */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <SectionCard title="Data by Type" icon={FileType}>
              <BreakdownBar items={stats.data.items_by_content_type} />
            </SectionCard>

            <SectionCard title="Memories by Type" icon={Layers}>
              <BreakdownBar items={stats.memories.by_type} />
            </SectionCard>

            <SectionCard title="Viewpoints by Engine" icon={Eye}>
              <BreakdownBar items={stats.viewpoints.by_engine} />
              {Object.keys(stats.viewpoints.by_model).length > 0 && (
                <div className="mt-4 pt-4 border-t border-white/10">
                  <p className="text-sm text-white/50 mb-2">By Model</p>
                  <BreakdownBar items={stats.viewpoints.by_model} />
                </div>
              )}
            </SectionCard>

            <SectionCard title="Embeddings by Engine" icon={Cpu}>
              <BreakdownBar items={stats.embeddings.by_engine} />
              {Object.keys(stats.embeddings.by_model).length > 0 && (
                <div className="mt-4 pt-4 border-t border-white/10">
                  <p className="text-sm text-white/50 mb-2">By Model</p>
                  <BreakdownBar items={stats.embeddings.by_model} />
                </div>
              )}
            </SectionCard>

            <SectionCard title="Tokens by Model" icon={Zap}>
              <BreakdownBar items={stats.tokens?.by_model ?? {}} />
            </SectionCard>

            <SectionCard title="Tokens by Agent Type" icon={Zap}>
              <BreakdownBar items={stats.tokens?.by_agent_type ?? {}} />
                {/* Drop Tokens */}
                <div className="mt-4 pt-4 border-t border-white/10">
                  {!dropConfirm ? (
                    <button
                      onClick={() => setDropConfirm(true)}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl font-medium text-sm transition-all duration-300 bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30"
                    >
                      <Trash2 className="w-4 h-4" />
                      Drop Tokens
                    </button>
                  ) : (
                    <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20">
                      <div className="flex items-center gap-3">
                        <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                        <p className="text-sm text-red-300 font-medium">Reset all token usage counters to zero?</p>
                      </div>
                      <div className="flex items-center gap-2 mt-3">
                        <button
                          onClick={() => setDropConfirm(false)}
                          disabled={dropping}
                          className="btn-secondary text-sm"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={handleDropTokens}
                          disabled={dropping}
                          className="flex items-center gap-2 px-4 py-2 rounded-xl font-medium text-sm bg-red-500 text-white hover:bg-red-600 transition-colors disabled:opacity-50"
                        >
                          {dropping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                          {dropping ? 'Dropping...' : 'Confirm'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
            </SectionCard>
          </div>
        </>
      )}
    </div>
  );
}

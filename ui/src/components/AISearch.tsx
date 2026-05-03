'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Eye, Layers, Loader2, Trash2,
  Sparkles, Clock, ChevronDown, ChevronUp,
  RefreshCw, ExternalLink,
} from 'lucide-react';
import {
  listViewpoints, listEmbeddings,
  deleteViewpoint, deleteDataEmbeddings, bulkDeleteViewpoints, bulkDeleteEmbeddings, formatDate,
} from '@/lib/api';
import ViewpointContent from '@/components/ViewpointContent';

type AISubTab = 'viewpoints' | 'embeddings';

interface AISearchProps {
  initialSubTab?: AISubTab;
}

export default function AISearch({ initialSubTab }: AISearchProps) {
  const [subTab, setSubTab] = useState<AISubTab>(initialSubTab ?? 'viewpoints');

  // ── Viewpoints state ──
  const [viewpoints, setViewpoints] = useState<any[]>([]);
  const [vpLoading, setVpLoading] = useState(false);
  const [vpFilter, setVpFilter] = useState('');
  const [expandedVp, setExpandedVp] = useState<string | null>(null);

  // ── Embeddings state ──
  const [embeddings, setEmbeddings] = useState<any[]>([]);
  const [embLoading, setEmbLoading] = useState(false);
  const [embFilter, setEmbFilter] = useState('');

  // ── Bulk selection ──
  const [selectedVpIds, setSelectedVpIds] = useState<Set<string>>(new Set());
  const [selectedEmbDataIds, setSelectedEmbDataIds] = useState<Set<string>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // ── Viewpoints ──
  const fetchViewpoints = useCallback(async () => {
    try {
      setVpLoading(true);
      const data = await listViewpoints();
      setViewpoints(Array.isArray(data) ? data : []);
    } catch {
      setViewpoints([]);
    } finally {
      setVpLoading(false);
    }
  }, []);

  const handleDeleteViewpoint = async (vpId: string) => {
    if (!confirm('Delete this viewpoint?')) return;
    try {
      await deleteViewpoint(vpId);
      setViewpoints(prev => prev.filter(v => (v.viewpoint_id || v.id) !== vpId));
    } catch { /* ignore */ }
  };

  // ── Embeddings ──
  const fetchEmbeddings = useCallback(async () => {
    try {
      setEmbLoading(true);
      const data = await listEmbeddings();
      setEmbeddings(Array.isArray(data) ? data : []);
    } catch {
      setEmbeddings([]);
    } finally {
      setEmbLoading(false);
    }
  }, []);

  const handleDeleteEmbedding = async (dataId: string) => {
    if (!confirm('Delete all embeddings for this data item?')) return;
    try {
      await deleteDataEmbeddings(dataId);
      setEmbeddings(prev => prev.filter(e => e.data_id !== dataId));
    } catch { /* ignore */ }
  };

  const handleBulkDeleteViewpoints = async () => {
    if (selectedVpIds.size === 0) return;
    if (!confirm(`Delete ${selectedVpIds.size} selected viewpoint${selectedVpIds.size !== 1 ? 's' : ''}?`)) return;
    try {
      setBulkDeleting(true);
      await bulkDeleteViewpoints(Array.from(selectedVpIds));
      setViewpoints(prev => prev.filter(v => !selectedVpIds.has(v.viewpoint_id || v.id)));
      setSelectedVpIds(new Set());
    } catch { /* ignore */ }
    finally { setBulkDeleting(false); }
  };

  const handleBulkDeleteEmbeddings = async () => {
    if (selectedEmbDataIds.size === 0) return;
    if (!confirm(`Delete embeddings for ${selectedEmbDataIds.size} selected data item${selectedEmbDataIds.size !== 1 ? 's' : ''}?`)) return;
    try {
      setBulkDeleting(true);
      await bulkDeleteEmbeddings(Array.from(selectedEmbDataIds));
      setEmbeddings(prev => prev.filter(e => !selectedEmbDataIds.has(e.data_id)));
      setSelectedEmbDataIds(new Set());
    } catch { /* ignore */ }
    finally { setBulkDeleting(false); }
  };

  const toggleVpSelection = (vpId: string) => {
    setSelectedVpIds(prev => {
      const next = new Set(prev);
      if (next.has(vpId)) next.delete(vpId); else next.add(vpId);
      return next;
    });
  };

  const toggleEmbSelection = (dataId: string) => {
    setSelectedEmbDataIds(prev => {
      const next = new Set(prev);
      if (next.has(dataId)) next.delete(dataId); else next.add(dataId);
      return next;
    });
  };

  const toggleAllVp = () => {
    if (selectedVpIds.size === filteredViewpoints.length) {
      setSelectedVpIds(new Set());
    } else {
      setSelectedVpIds(new Set(filteredViewpoints.map((v: any) => v.viewpoint_id || v.id)));
    }
  };

  const toggleAllEmb = () => {
    if (selectedEmbDataIds.size === filteredEmbeddings.length) {
      setSelectedEmbDataIds(new Set());
    } else {
      setSelectedEmbDataIds(new Set(filteredEmbeddings.map((e: any) => e.data_id)));
    }
  };

  // Fetch data when switching sub-tabs
  useEffect(() => {
    if (subTab === 'viewpoints') fetchViewpoints();
    if (subTab === 'embeddings') fetchEmbeddings();
  }, [subTab, fetchViewpoints, fetchEmbeddings]);

  const filteredViewpoints = vpFilter
    ? viewpoints.filter(v => (v.data_id || '').toLowerCase().includes(vpFilter.toLowerCase()))
    : viewpoints;

  const filteredEmbeddings = embFilter
    ? embeddings.filter(e => (e.data_id || '').toLowerCase().includes(embFilter.toLowerCase()))
    : embeddings;

  return (
    <div className="space-y-6">
      {/* Sub-tab toggle */}
      <div className="flex items-center gap-2 p-1 bg-white/5 rounded-xl max-w-lg">
        {([
          { id: 'viewpoints' as const, label: 'Viewpoints', icon: Eye },
          { id: 'embeddings' as const, label: 'Embeddings', icon: Layers },
        ]).map(tab => (
          <button
            key={tab.id}
            onClick={() => setSubTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all ${
              subTab === tab.id
                ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
                : 'text-white/50 hover:text-white/70 hover:bg-white/5'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* ══════════════════════════════════════════════════════════════════ */}
      {/* Viewpoints Sub-tab */}
      {/* ══════════════════════════════════════════════════════════════════ */}
      {subTab === 'viewpoints' && (
        <div className="space-y-4">
          {/* Filter + refresh + bulk actions */}
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={vpFilter}
              onChange={e => setVpFilter(e.target.value)}
              placeholder="Filter by data_id..."
              className="flex-1 max-w-sm px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50"
            />
            <button
              onClick={fetchViewpoints}
              disabled={vpLoading}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors text-white/40 hover:text-white/70"
            >
              <RefreshCw className={`w-4 h-4 ${vpLoading ? 'animate-spin' : ''}`} />
            </button>
            {selectedVpIds.size > 0 && (
              <button
                onClick={handleBulkDeleteViewpoints}
                disabled={bulkDeleting}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-all disabled:opacity-50"
              >
                {bulkDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                Delete {selectedVpIds.size} selected
              </button>
            )}
            <span className="text-xs text-white/30">{filteredViewpoints.length} viewpoint{filteredViewpoints.length !== 1 ? 's' : ''}</span>
          </div>

          {vpLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-violet-400 animate-spin" />
            </div>
          ) : filteredViewpoints.length === 0 ? (
            <div className="text-center py-12 text-white/30">
              <Eye className="w-8 h-8 mx-auto mb-3 opacity-50" />
              <p className="text-sm">{vpFilter ? 'No viewpoints match this filter.' : 'No viewpoints generated yet.'}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Select all */}
              {filteredViewpoints.length > 0 && (
                <label className="flex items-center gap-2 text-xs text-white/40 cursor-pointer hover:text-white/60 transition-colors px-1">
                  <input
                    type="checkbox"
                    checked={selectedVpIds.size === filteredViewpoints.length && filteredViewpoints.length > 0}
                    onChange={toggleAllVp}
                    className="rounded border-white/20 bg-white/5 text-violet-500 focus:ring-violet-500/50"
                  />
                  Select all
                </label>
              )}
              {filteredViewpoints.map((vp: any) => {
                const vpId = vp.viewpoint_id || vp.id;
                const isExpanded = expandedVp === vpId;
                const isSelected = selectedVpIds.has(vpId);
                return (
                  <div key={vpId} className={`rounded-xl bg-white/5 border transition-colors overflow-hidden ${isSelected ? 'border-violet-500/40' : 'border-white/10 hover:border-white/20'}`}>
                    <div className="flex items-start justify-between p-4">
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleVpSelection(vpId)}
                          className="mt-1 rounded border-white/20 bg-white/5 text-violet-500 focus:ring-violet-500/50 flex-shrink-0"
                        />
                      <button onClick={() => setExpandedVp(isExpanded ? null : vpId)} className="flex-1 text-left min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Sparkles className="w-4 h-4 text-violet-400 flex-shrink-0" />
                          <span className="text-sm font-medium text-white">
                            {vp.ai_engine || vp.engine || 'AI'} / {vp.model || 'model'}
                          </span>
                          {vp.prompt_id && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-white/10 text-white/40">
                              {vp.prompt_id.substring(0, 12)}...
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-white/30 mt-1">
                          {vp.data_id && (
                            <a
                              href={`/data/${vp.data_id}`}
                              onClick={e => e.stopPropagation()}
                              className="flex items-center gap-1 hover:text-violet-400 transition-colors"
                            >
                              <ExternalLink className="w-3 h-3" />
                              {vp.data_id.substring(0, 16)}...
                            </a>
                          )}
                          {vp.created_at && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {formatDate(vp.created_at)}
                            </span>
                          )}
                        </div>
                        {!isExpanded && (
                          <p className="text-sm text-white/50 mt-2 line-clamp-2">
                            {(() => {
                              const raw = vp.output_content || vp.content || '(empty)';
                              try { const j = JSON.parse(raw); return j.summary || j.category || raw; } catch { return raw; }
                            })()}
                          </p>
                        )}
                      </button>
                      </div>
                      <div className="flex items-center gap-1 ml-3 flex-shrink-0">
                        <button
                          onClick={() => handleDeleteViewpoint(vpId)}
                          className="p-1.5 rounded-lg hover:bg-red-500/20 text-white/30 hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setExpandedVp(isExpanded ? null : vpId)}
                          className="p-1.5 rounded-lg hover:bg-white/10 text-white/30 hover:text-white/60 transition-colors"
                        >
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>
                    {isExpanded && (
                      <div className="px-4 pb-4 border-t border-white/10 pt-3">
                        <ViewpointContent content={vp.output_content || vp.content || ''} />
                        {vp.ai_signature && (
                          <div className="mt-3 p-3 rounded-lg bg-white/5 border border-white/10">
                            <span className="text-xs font-medium text-white/40 uppercase tracking-wider">AI Signature</span>
                            <div className="mt-1.5 grid grid-cols-2 gap-2 text-xs text-white/50">
                              {vp.ai_signature.model_name && <div><span className="text-white/30">Model:</span> {vp.ai_signature.model_name}</div>}
                              {vp.ai_signature.engine_type && <div><span className="text-white/30">Engine:</span> {vp.ai_signature.engine_type}</div>}
                              {vp.ai_signature.key_mode && <div><span className="text-white/30">Key:</span> {vp.ai_signature.key_mode}</div>}
                              {vp.ai_signature.token_usage && <div><span className="text-white/30">Tokens:</span> {JSON.stringify(vp.ai_signature.token_usage)}</div>}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════ */}
      {/* Embeddings Sub-tab */}
      {/* ══════════════════════════════════════════════════════════════════ */}
      {subTab === 'embeddings' && (
        <div className="space-y-4">
          {/* Filter + refresh */}
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={embFilter}
              onChange={e => setEmbFilter(e.target.value)}
              placeholder="Filter by data_id..."
              className="flex-1 max-w-sm px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50"
            />
            <button
              onClick={fetchEmbeddings}
              disabled={embLoading}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors text-white/40 hover:text-white/70"
            >
              <RefreshCw className={`w-4 h-4 ${embLoading ? 'animate-spin' : ''}`} />
            </button>
            {selectedEmbDataIds.size > 0 && (
              <button
                onClick={handleBulkDeleteEmbeddings}
                disabled={bulkDeleting}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-all disabled:opacity-50"
              >
                {bulkDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                Delete {selectedEmbDataIds.size} selected
              </button>
            )}
            <span className="text-xs text-white/30">{filteredEmbeddings.length} embedding{filteredEmbeddings.length !== 1 ? 's' : ''}</span>
          </div>

          {embLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-violet-400 animate-spin" />
            </div>
          ) : filteredEmbeddings.length === 0 ? (
            <div className="text-center py-12 text-white/30">
              <Layers className="w-8 h-8 mx-auto mb-3 opacity-50" />
              <p className="text-sm">{embFilter ? 'No embeddings match this filter.' : 'No embeddings generated yet.'}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="py-3 px-4">
                      <input
                        type="checkbox"
                        checked={selectedEmbDataIds.size === filteredEmbeddings.length && filteredEmbeddings.length > 0}
                        onChange={toggleAllEmb}
                        className="rounded border-white/20 bg-white/5 text-violet-500 focus:ring-violet-500/50"
                      />
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-semibold text-white/40 uppercase tracking-wider">Data ID</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold text-white/40 uppercase tracking-wider">Model</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold text-white/40 uppercase tracking-wider">Dimensions</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold text-white/40 uppercase tracking-wider">Chunks</th>
                    <th className="text-left py-3 px-4 text-xs font-semibold text-white/40 uppercase tracking-wider">Created</th>
                    <th className="text-right py-3 px-4 text-xs font-semibold text-white/40 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEmbeddings.map((emb: any) => {
                    const isSelected = selectedEmbDataIds.has(emb.data_id);
                    return (
                      <tr key={emb.data_id} className={`border-b border-white/5 hover:bg-white/5 transition-colors ${isSelected ? 'bg-violet-500/5' : ''}`}>
                        <td className="py-3 px-4">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleEmbSelection(emb.data_id)}
                            className="rounded border-white/20 bg-white/5 text-violet-500 focus:ring-violet-500/50"
                          />
                        </td>
                        <td className="py-3 px-4">
                          {emb.data_id ? (
                            <a href={`/data/${emb.data_id}`} className="text-violet-400 hover:text-violet-300 transition-colors font-mono text-xs">
                              {emb.data_id.substring(0, 16)}...
                            </a>
                          ) : (
                            <span className="text-white/30">-</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-white/60 text-xs">{emb.model || emb.embedding_model || '-'}</td>
                        <td className="py-3 px-4 text-white/60 text-xs font-mono">{emb.dimensions || emb.dimension_count || '-'}</td>
                        <td className="py-3 px-4 text-white/60 text-xs font-mono">{emb.chunk_count ?? '-'}</td>
                        <td className="py-3 px-4 text-white/40 text-xs">{emb.created_at ? formatDate(emb.created_at) : '-'}</td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => handleDeleteEmbedding(emb.data_id)}
                            className="p-1.5 rounded-lg hover:bg-red-500/20 text-white/30 hover:text-red-400 transition-colors"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


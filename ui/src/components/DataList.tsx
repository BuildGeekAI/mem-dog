'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { RefreshCw, ChevronRight, ChevronLeft, Package, AlertCircle, Inbox, Loader2, Shield, Globe, Users, Tag, Trash2, CheckSquare, Square, XCircle, HardDrive, Link, Copy, Download, ExternalLink, Search, Sparkles, Layers } from 'lucide-react';
import type { DataListItem, DataStats, AccessControl } from '@/types';
import { listData, formatBytes, formatDate, bulkDeleteData, deleteAllUserData, getDataStats, getCurrentUserId, normalizeAddress, listViewpoints, listEmbeddings } from '@/lib/api';

// Compact badge for access display in the list
function AccessBadge({ access }: { access?: AccessControl }) {
  const getLabel = () => {
    if (!access || access.length === 0) return 'Public';
    if (access.includes('*')) return 'All Users';
    return `${access.length} ${access.length === 1 ? 'entry' : 'entries'}`;
  };

  const getIcon = () => {
    if (!access || access.length === 0) return <Globe className="w-3 h-3" />;
    if (access.includes('*')) return <Users className="w-3 h-3" />;
    return <Shield className="w-3 h-3" />;
  };

  const getStyle = () => {
    if (!access || access.length === 0) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    if (access.includes('*')) return 'bg-blue-500/10 text-blue-400 border-blue-500/30';
    return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
  };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border text-xs font-medium ${getStyle()}`}>
      {getIcon()}
      {getLabel()}
    </span>
  );
}

// Compact tags display for the list
function TagsDisplay({ tags }: { tags?: string[] | null }) {
  if (!tags || tags.length === 0) {
    return <span className="text-white/30 text-xs">—</span>;
  }

  const displayTags = tags.slice(0, 2);
  const remaining = tags.length - 2;

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {displayTags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30 text-xs"
        >
          <Tag className="w-2.5 h-2.5" />
          {tag}
        </span>
      ))}
      {remaining > 0 && (
        <span className="text-white/40 text-xs">+{remaining}</span>
      )}
    </div>
  );
}

const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

export default function DataList() {
  const router = useRouter();
  const [items, setItems] = useState<DataListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Inline stats
  const [dataStatsInfo, setDataStatsInfo] = useState<DataStats | null>(null);

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectionMode, setSelectionMode] = useState(false);

  // Bulk delete state
  const [deleteConfirm, setDeleteConfirm] = useState<'none' | 'selected' | 'all'>('none');
  const [deleting, setDeleting] = useState(false);
  const [deleteResult, setDeleteResult] = useState<string | null>(null);

  // AI indicators (viewpoints & embeddings per data_id)
  const [vpDataIds, setVpDataIds] = useState<Set<string>>(new Set());
  const [embDataIds, setEmbDataIds] = useState<Set<string>>(new Set());

  // Search by tags
  const [tagFilter, setTagFilter] = useState('');
  const [matchAllTags, setMatchAllTags] = useState(false);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasPrev = page > 0;
  const hasNext = page < totalPages - 1;

  const handlePageSizeChange = useCallback((newSize: number) => {
    setPageSize(newSize);
    loadData(0, false, newSize);
  }, []);

  useEffect(() => {
    loadData(0);
    getDataStats().then(setDataStatsInfo).catch(() => {});
    // Fetch AI indicators (best-effort, non-blocking)
    listViewpoints().then(vps => {
      const ids = new Set<string>();
      for (const vp of vps) if (vp.data_id) ids.add(vp.data_id);
      setVpDataIds(ids);
    }).catch(() => {});
    listEmbeddings().then(embs => {
      const ids = new Set<string>();
      for (const e of embs) if (e.data_id) ids.add(e.data_id);
      setEmbDataIds(ids);
    }).catch(() => {});
  }, []);

  const loadData = async (
    pageIndex: number,
    isRefresh = false,
    limitOverride?: number,
    tagsOverride?: string[] | null,
    matchAllOverride?: boolean
  ) => {
    const effectiveLimit = limitOverride ?? pageSize;
    const useTags = tagsOverride !== undefined
      ? (tagsOverride?.length ? tagsOverride : undefined)
      : (tagFilter.trim() ? tagFilter.split(',').map((t) => t.trim()).filter(Boolean) : undefined);
    const useMatchAll = matchAllOverride ?? matchAllTags;
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);
      const res = await listData(getCurrentUserId(), {
        skip: pageIndex * effectiveLimit,
        limit: effectiveLimit,
        tags: useTags,
        matchAll: useTags?.length ? useMatchAll : undefined,
      });
      setItems(res.items);
      setTotal(res.total);
      setPage(pageIndex);
      setSelectedIds(new Set());
    } catch (err: any) {
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const applyTagFilter = useCallback(() => {
    loadData(0);
  }, []);

  const clearTagFilter = useCallback(() => {
    setTagFilter('');
    setMatchAllTags(false);
    loadData(0, false, undefined, [], false);
  }, []);

  const handleRowClick = (id: string) => {
    if (selectionMode) {
      toggleSelection(id);
    } else {
      router.push(`/data/${id}`);
    }
  };

  // Selection handlers
  const toggleSelection = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(items.map((item) => item.data_id)));
  }, [items]);

  const deselectAll = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const toggleSelectionMode = useCallback(() => {
    if (selectionMode) {
      setSelectedIds(new Set());
      setDeleteConfirm('none');
    }
    setSelectionMode(prev => !prev);
  }, [selectionMode]);

  // Bulk delete handlers
  const handleBulkDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    setDeleteResult(null);
    try {
      const result = await bulkDeleteData(Array.from(selectedIds));
      setDeleteResult(result.message);
      setDeleteConfirm('none');
      setSelectedIds(new Set());
      await loadData(page, true);
      getDataStats().then(setDataStatsInfo).catch(() => {});
    } catch (err: any) {
      setDeleteResult(`Error: ${err.message || 'Failed to delete'}`);
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteAllUserData = async () => {
    setDeleting(true);
    setDeleteResult(null);
    try {
      const result = await deleteAllUserData(getCurrentUserId());
      setDeleteResult(result.message);
      setDeleteConfirm('none');
      setSelectedIds(new Set());
      setSelectionMode(false);
      await loadData(0, true);
      getDataStats().then(setDataStatsInfo).catch(() => {});
    } catch (err: any) {
      setDeleteResult(`Error: ${err.message || 'Failed to delete'}`);
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="glass-card p-12">
        <div className="flex flex-col items-center justify-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary-500/20 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
          </div>
          <p className="text-white/60">Loading your data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card p-8">
        <div className="flex flex-col items-center justify-center gap-4 text-center">
          <div className="w-14 h-14 rounded-xl bg-red-500/20 flex items-center justify-center">
            <AlertCircle className="w-7 h-7 text-red-400" />
          </div>
          <div>
            <p className="text-red-400 font-medium">{error}</p>
            <p className="text-white/50 text-sm mt-1">Please try again</p>
          </div>
          <button onClick={() => loadData(0)} className="btn-secondary">
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="glass-card p-12">
        <div className="flex flex-col items-center justify-center gap-4 text-center">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary-500/20 to-accent-500/20 flex items-center justify-center">
            <Inbox className="w-10 h-10 text-white/40" />
          </div>
          <div>
            <h3 className="text-xl font-semibold text-white">No Data Yet</h3>
            <p className="text-white/50 mt-1">Upload your first data item to get started</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-5 border-b border-white/10">
        <div className="flex items-center gap-4">
          <p className="text-sm text-white/50">
            <span className="font-semibold text-white">{total}</span> item{total !== 1 ? 's' : ''}
            {dataStatsInfo && dataStatsInfo.total_size_bytes > 0 && (
              <span className="inline-flex items-center gap-1 ml-2 text-white/40">
                <HardDrive className="w-3 h-3" />
                {formatBytes(dataStatsInfo.total_size_bytes)}
              </span>
            )}
            {selectionMode && selectedIds.size > 0 && (
              <span className="text-primary-400 ml-2">
                ({selectedIds.size} selected)
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Selection Mode Toggle */}
          <button
            onClick={toggleSelectionMode}
            className={`btn-secondary flex items-center gap-2 ${selectionMode ? 'ring-2 ring-primary-500/50 bg-primary-500/10' : ''}`}
          >
            {selectionMode ? <XCircle className="w-4 h-4" /> : <CheckSquare className="w-4 h-4" />}
            {selectionMode ? 'Cancel' : 'Select'}
          </button>
          
          {/* Bulk Delete Buttons (visible in selection mode) */}
          {selectionMode && (
            <>
              <button
                onClick={selectAll}
                className="btn-secondary flex items-center gap-2 text-xs"
              >
                Select All
              </button>
              <button
                onClick={deselectAll}
                disabled={selectedIds.size === 0}
                className="btn-secondary flex items-center gap-2 text-xs"
              >
                Deselect All
              </button>
              <button
                onClick={() => setDeleteConfirm('selected')}
                disabled={selectedIds.size === 0 || deleting}
                className="flex items-center gap-2 px-4 py-2 rounded-xl font-medium text-sm transition-all duration-300 bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Trash2 className="w-4 h-4" />
                Delete Selected ({selectedIds.size})
              </button>
              <button
                onClick={() => setDeleteConfirm('all')}
                disabled={total === 0 || deleting}
                className="flex items-center gap-2 px-4 py-2 rounded-xl font-medium text-sm transition-all duration-300 bg-red-600/20 text-red-300 border border-red-600/30 hover:bg-red-600/30 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Trash2 className="w-4 h-4" />
                Delete All Data
              </button>
            </>
          )}
          
          <button
            onClick={() => loadData(page, true)}
            disabled={refreshing}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Confirmation Dialog */}
      {deleteConfirm !== 'none' && (
        <div className="px-6 py-4 bg-red-500/10 border-b border-red-500/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-400" />
              <div>
                <p className="text-red-300 font-medium">
                  {deleteConfirm === 'selected'
                    ? `Permanently delete ${selectedIds.size} selected item${selectedIds.size !== 1 ? 's' : ''}?`
                    : `Permanently delete ALL ${total} data items?`}
                </p>
                <p className="text-red-400/60 text-sm mt-0.5">
                  This action cannot be undone. All versions will be removed.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setDeleteConfirm('none')}
                disabled={deleting}
                className="btn-secondary text-sm"
              >
                Cancel
              </button>
              <button
                onClick={deleteConfirm === 'selected' ? handleBulkDeleteSelected : handleDeleteAllUserData}
                disabled={deleting}
                className="flex items-center gap-2 px-4 py-2 rounded-xl font-medium text-sm bg-red-500 text-white hover:bg-red-600 transition-colors disabled:opacity-50"
              >
                {deleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                {deleting ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Result Banner */}
      {deleteResult && (
        <div className={`px-6 py-3 border-b ${deleteResult.startsWith('Error') ? 'bg-red-500/10 border-red-500/20' : 'bg-emerald-500/10 border-emerald-500/20'}`}>
          <div className="flex items-center justify-between">
            <p className={`text-sm font-medium ${deleteResult.startsWith('Error') ? 'text-red-400' : 'text-emerald-400'}`}>
              {deleteResult}
            </p>
            <button
              onClick={() => setDeleteResult(null)}
              className="text-white/40 hover:text-white/60"
            >
              <XCircle className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Search by tags - top */}
      <div className="flex flex-wrap items-center gap-3 px-6 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="flex items-center gap-2 min-w-[200px] flex-1">
          <Search className="w-4 h-4 text-white/40 flex-shrink-0" />
          <input
            type="text"
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applyTagFilter()}
            placeholder="Filter by tags (comma-separated)"
            className="flex-1 min-w-0 bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus:ring-1 focus:ring-primary-500/50"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-white/60 cursor-pointer">
          <input
            type="checkbox"
            checked={matchAllTags}
            onChange={(e) => setMatchAllTags(e.target.checked)}
            className="rounded border-white/20 bg-white/5 text-primary-500 focus:ring-primary-500/50"
          />
          Match all tags
        </label>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={applyTagFilter}
            disabled={loading}
            className="btn-secondary flex items-center gap-1.5 px-3 py-2 text-sm disabled:opacity-50"
          >
            <Search className="w-3.5 h-3.5" />
            Search
          </button>
          {tagFilter.trim() && (
            <button
              type="button"
              onClick={clearTagFilter}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm border border-white/20 text-white/60 hover:text-white hover:bg-white/10 disabled:opacity-50"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Pagination (limit + page) - top */}
      {total > 0 && (
        <div className="flex items-center justify-between px-6 py-3 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-4">
            <p className="text-sm text-white/50">
              Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
            </p>
            <label className="flex items-center gap-2 text-sm text-white/50">
              <span>Per page</span>
              <select
                value={pageSize}
                onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                disabled={loading}
                className="bg-white/10 border border-white/20 rounded-lg px-2.5 py-1.5 text-sm text-white focus:outline-none focus:ring-1 focus:ring-primary-500/50 disabled:opacity-50"
              >
                {PAGE_SIZE_OPTIONS.map((n) => (
                  <option key={n} value={n} className="bg-gray-900 text-white">
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => loadData(page - 1)}
                disabled={!hasPrev || loading}
                className="btn-secondary flex items-center gap-1.5 px-3 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
                Previous
              </button>
              <span className="text-sm text-white/60 px-2">
                Page {page + 1} of {totalPages}
              </span>
              <button
                onClick={() => loadData(page + 1)}
                disabled={!hasNext || loading}
                className="btn-secondary flex items-center gap-1.5 px-3 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="table-modern">
          <thead>
            <tr>
              {selectionMode && (
                <th className="w-12">
                  <button
                    onClick={selectedIds.size === items.length ? deselectAll : selectAll}
                    className="flex items-center justify-center"
                  >
                    {selectedIds.size === items.length && items.length > 0 ? (
                      <CheckSquare className="w-4 h-4 text-primary-400" />
                    ) : (
                      <Square className="w-4 h-4 text-white/40" />
                    )}
                  </button>
                </th>
              )}
              <th>Name / ID</th>
              <th>Version</th>
              <th>Tags</th>
              <th>AI</th>
              <th>Access</th>
              <th>Type</th>
              <th>Size</th>
              <th>Updated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, index) => (
              <tr
                key={item.data_id}
                onClick={() => handleRowClick(item.data_id)}
                className={`group ${selectionMode && selectedIds.has(item.data_id) ? 'bg-primary-500/5 border-l-2 border-l-primary-500' : ''}`}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                {selectionMode && (
                  <td className="w-12" onClick={(e) => { e.stopPropagation(); toggleSelection(item.data_id); }}>
                    <div className="flex items-center justify-center">
                      {selectedIds.has(item.data_id) ? (
                        <CheckSquare className="w-4 h-4 text-primary-400" />
                      ) : (
                        <Square className="w-4 h-4 text-white/40 group-hover:text-white/60" />
                      )}
                    </div>
                  </td>
                )}
                <td>
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
                      <Package className="w-4 h-4 text-white/60" />
                    </div>
                    <div className="flex flex-col">
                      {item.name ? (
                        <>
                          <span className="text-white font-medium text-sm truncate max-w-[200px]" title={item.name}>
                            {item.name}
                          </span>
                          <code className="text-xs text-white/40">
                            {item.data_id.substring(0, 8)}...
                          </code>
                        </>
                      ) : (
                        <code className="text-xs text-primary-400 bg-primary-500/10 px-2 py-1 rounded-md">
                          {item.data_id.substring(0, 12)}...
                        </code>
                      )}
                    </div>
                    {item.address && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          const rel = normalizeAddress(item.address!) ?? item.address!;
                          navigator.clipboard.writeText(`${window.location.origin}${rel}`);
                        }}
                        className="p-1 rounded-md opacity-0 group-hover:opacity-100 hover:bg-white/10 transition-all"
                        title={`Copy address: ${normalizeAddress(item.address!) ?? item.address}`}
                      >
                        <Link className="w-3.5 h-3.5 text-teal-400/70" />
                      </button>
                    )}
                  </div>
                </td>
                <td>
                  <span className="badge badge-info">v{item.current_version}</span>
                </td>
                <td>
                  <TagsDisplay tags={item.tags} />
                </td>
                <td>
                  <div className="flex items-center gap-1">
                    {vpDataIds.has(item.data_id) && (
                      <span
                        title="Has viewpoints"
                        className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/30 text-[9px] font-semibold"
                      >
                        <Sparkles className="w-2.5 h-2.5" />
                        VP
                      </span>
                    )}
                    {embDataIds.has(item.data_id) && (
                      <span
                        title="Has embeddings"
                        className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 text-[9px] font-semibold"
                      >
                        <Layers className="w-2.5 h-2.5" />
                        EMB
                      </span>
                    )}
                    {!vpDataIds.has(item.data_id) && !embDataIds.has(item.data_id) && (
                      <span className="text-white/20 text-xs">—</span>
                    )}
                  </div>
                </td>
                <td>
                  <AccessBadge access={item.access} />
                </td>
                <td>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-white/70 font-mono text-xs">{item.mime_type || item.content_type}</span>
                    {item.url && !item.is_downloaded && (
                      <span
                        title={`Source URL (not yet downloaded): ${item.url}`}
                        className="inline-flex items-center gap-0.5 px-1 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[9px] font-semibold"
                      >
                        <ExternalLink className="w-2.5 h-2.5" />
                        REF
                      </span>
                    )}
                    {item.url && item.is_downloaded && (
                      <span
                        title={`Downloaded from: ${item.url}`}
                        className="inline-flex items-center gap-0.5 px-1 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/20 text-[9px] font-semibold"
                      >
                        <Download className="w-2.5 h-2.5" />
                        DL
                      </span>
                    )}
                  </div>
                </td>
                <td>
                  <span className="text-white/70">{formatBytes(item.size)}</span>
                </td>
                <td>
                  <span className="text-white/60 text-sm">{formatDate(item.updated_at)}</span>
                </td>
                <td>
                  <ChevronRight className="w-5 h-5 text-white/30 group-hover:text-white/60 group-hover:translate-x-1 transition-all" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

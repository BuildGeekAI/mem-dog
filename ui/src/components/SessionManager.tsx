'use client';

import { useState, useEffect, useCallback } from 'react';
import { Layers, Plus, RefreshCw, ChevronRight, ChevronLeft, Clock, Smartphone, User, Hash, Package, Trash2, X, AlertCircle, Loader2, CheckCircle, XCircle, Eye, Activity, CheckSquare, Square, Search, Lock, Users, Globe, FolderOpen } from 'lucide-react';
import { MemoryResponse, MemoryStatsData, MemoryType, AccessLevel } from '@/types';
import { listMemories, createMemory, deleteMemory, updateMemory, getMemoryData, getDeviceId, getDeviceInfo, getMemoryStats, bulkDeleteMemories, getCurrentUserId, getCurrentUserInfo } from '@/lib/api';
import { useProject } from '@/lib/project-context';

interface MemoryManagerProps {
  apiBaseUrl: string;
}

const MEMORY_TYPES: MemoryType[] = ['timeline', 'conversation', 'user', 'organizational', 'factual', 'episodic', 'semantic', 'custom', 'tracing'];

/** Display label for memory types (timeline → audit). */
function memoryTypeLabel(t: string): string {
  return t === 'timeline' ? 'audit' : t;
}

/** Access level icon and label. */
function accessLevelIcon(level?: string) {
  switch (level) {
    case 'shared': return { Icon: Users, label: 'Shared', color: 'text-blue-400' };
    case 'public': return { Icon: Globe, label: 'Public', color: 'text-green-400' };
    case 'restricted': return { Icon: Lock, label: 'Restricted', color: 'text-orange-400' };
    default: return { Icon: Lock, label: 'Private', color: 'text-white/30' };
  }
}

/** Format relative expiry from ISO string. */
function formatExpiry(expiresAt?: string): string | null {
  if (!expiresAt) return null;
  const exp = new Date(expiresAt);
  const now = new Date();
  const diffMs = exp.getTime() - now.getTime();
  if (diffMs <= 0) return 'Expired';
  const hours = Math.floor(diffMs / 3600000);
  const days = Math.floor(hours / 24);
  if (days > 0) return `${days}d ${hours % 24}h left`;
  const mins = Math.floor((diffMs % 3600000) / 60000);
  if (hours > 0) return `${hours}h ${mins}m left`;
  return `${mins}m left`;
}

/** Predetermined sub_types for custom memories (matches API PREDETERMINED_SUB_TYPES). */
const PREDETERMINED_SUB_TYPES = ['legal', 'hr', 'customer', 'finance', 'engineering', 'support', 'sales', 'marketing'];

/**
 * Manages memories (the unified replacement for sessions/timelines).
 * Lists, creates, inspects, and deletes memories and their associated data.
 * Supports bulk delete via selection mode (Select → Select All / Deselect All → Delete Selected).
 */
export function MemoryManager({ apiBaseUrl }: MemoryManagerProps) {
  const { selectedOrgId, selectedProjectId, projects, orgs } = useProject();
  const selectedProject = projects.find(p => p.project_id === selectedProjectId);
  const selectedOrg = orgs.find(o => o.org_id === selectedOrgId);
  const [memories, setMemories] = useState<MemoryResponse[]>([]);
  const [selectedMemory, setSelectedMemory] = useState<MemoryResponse | null>(null);
  const [memoryData, setMemoryData] = useState<any[]>([]);
  const [memoryDataTotal, setMemoryDataTotal] = useState(0);
  const [memoryDataPage, setMemoryDataPage] = useState(0);
  const memoryDataPageSize = 10;
  const [loading, setLoading] = useState(true);
  const [dataLoading, setDataLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [filterActive, setFilterActive] = useState<boolean | undefined>(undefined);
  const [memoryStatsInfo, setMemoryStatsInfo] = useState<MemoryStatsData | null>(null);

  const [formUserId, setFormUserId] = useState(() => getCurrentUserId());
  const [formName, setFormName] = useState('');
  const [formMemoryType, setFormMemoryType] = useState<MemoryType>('timeline');
  const [formSubType, setFormSubType] = useState('');
  const [formAccessLevel, setFormAccessLevel] = useState<string>('private');
  const [formSharedWith, setFormSharedWith] = useState('');
  const [formTtlHours, setFormTtlHours] = useState('');
  const [formNoExpiry, setFormNoExpiry] = useState(false);
  const [filterMemoryType, setFilterMemoryType] = useState<string>('');
  const [filterSubType, setFilterSubType] = useState<string>('');
  const [searchName, setSearchName] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<MemoryResponse | null>(null);
  const [deleteWithData, setDeleteWithData] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleteConfirm, setBulkDeleteConfirm] = useState(false);
  const [bulkDeleteWithData, setBulkDeleteWithData] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  const fetchMemories = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await listMemories({
        userId: getCurrentUserId(),
        active: filterActive,
        memoryType: filterMemoryType || undefined,
        subType: filterSubType || undefined,
        projectId: selectedProjectId || undefined,
      });
      setMemories(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load memories');
    } finally {
      setLoading(false);
    }
  }, [filterActive, filterMemoryType, filterSubType]);

  const fetchMemoryData = useCallback(async (memoryId: string, pageIndex = 0) => {
    try {
      setDataLoading(true);
      const response = await getMemoryData(memoryId, {
        skip: pageIndex * memoryDataPageSize,
        limit: memoryDataPageSize,
      });
      setMemoryData(response.items);
      setMemoryDataTotal(response.total);
      setMemoryDataPage(pageIndex);
    } catch (err) {
      console.error('Failed to fetch memory data:', err);
      setMemoryData([]);
      setMemoryDataTotal(0);
      setMemoryDataPage(0);
    } finally {
      setDataLoading(false);
    }
  }, []);

  useEffect(() => { fetchMemories(); }, [fetchMemories]);

  useEffect(() => {
    getMemoryStats().then(setMemoryStatsInfo).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedMemory) {
      fetchMemoryData(selectedMemory.memory_id, 0);
    }
  }, [selectedMemory, fetchMemoryData]);

  const memoryDataTotalPages = Math.max(1, Math.ceil(memoryDataTotal / memoryDataPageSize));
  const memoryDataHasPrev = memoryDataPage > 0;
  const memoryDataHasNext = memoryDataPage < memoryDataTotalPages - 1;

  const handleCreateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCreating(true);
      setError(null);
      const deviceId = getDeviceId();
      const deviceInfo = getDeviceInfo();

      const sharedWithList = formSharedWith.trim()
        ? formSharedWith.split(',').map(s => s.trim()).filter(Boolean)
        : [];

      await createMemory({
        memory_type: formMemoryType,
        name: formName.trim() || undefined,
        user_id: formUserId.trim() || getCurrentUserId(),
        sub_type: formMemoryType === 'custom' && formSubType ? formSubType : undefined,
        device_id: deviceId,
        device_info: deviceInfo,
        access_level: formAccessLevel as any,
        shared_with: sharedWithList.length > 0 ? sharedWithList : undefined,
        ttl_hours: formTtlHours ? parseInt(formTtlHours, 10) : undefined,
        no_expiry: formNoExpiry || undefined,
        org_id: selectedOrgId || undefined,
        project_id: selectedProjectId || undefined,
      });

      setShowCreateForm(false);
      setFormUserId(getCurrentUserId());
      setFormName('');
      setFormMemoryType('timeline');
      setFormSubType('');
      setFormAccessLevel('private');
      setFormSharedWith('');
      setFormTtlHours('');
      setFormNoExpiry(false);
      fetchMemories();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create memory');
    } finally {
      setCreating(false);
    }
  };

  const handleDeactivateMemory = async (memoryId: string) => {
    if (!confirm('Deactivate this memory? Data will be preserved.')) return;
    try {
      await updateMemory(memoryId, { active: false });
      if (selectedMemory?.memory_id === memoryId) {
        setSelectedMemory(null);
        setMemoryData([]);
      }
      fetchMemories();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to deactivate memory');
    }
  };

  const handleDeleteMemory = async () => {
    if (!deleteTarget) return;
    try {
      setDeleting(true);
      setError(null);
      await bulkDeleteMemories({
        memory_ids: [deleteTarget.memory_id],
        delete_data: deleteWithData,
      });
      if (selectedMemory?.memory_id === deleteTarget.memory_id) {
        setSelectedMemory(null);
        setMemoryData([]);
      }
      setDeleteTarget(null);
      setDeleteWithData(false);
      fetchMemories();
      getMemoryStats().then(setMemoryStatsInfo).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete memory');
    } finally {
      setDeleting(false);
    }
  };

  const toggleSelection = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(memories.map(m => m.memory_id)));
  }, [memories]);

  const deselectAll = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const toggleSelectionMode = useCallback(() => {
    if (selectionMode) {
      setSelectedIds(new Set());
      setBulkDeleteConfirm(false);
    }
    setSelectionMode(prev => !prev);
  }, [selectionMode]);

  const handleBulkDeleteMemories = async () => {
    if (selectedIds.size === 0) return;
    try {
      setBulkDeleting(true);
      setError(null);
      await bulkDeleteMemories({
        memory_ids: Array.from(selectedIds),
        delete_data: bulkDeleteWithData,
      });
      const removed = selectedIds.has(selectedMemory?.memory_id ?? '');
      if (removed) {
        setSelectedMemory(null);
        setMemoryData([]);
      }
      setBulkDeleteConfirm(false);
      setBulkDeleteWithData(false);
      setSelectedIds(new Set());
      setSelectionMode(false);
      fetchMemories();
      getMemoryStats().then(setMemoryStatsInfo).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete memories');
    } finally {
      setBulkDeleting(false);
    }
  };

  const filteredMemories = searchName.trim()
    ? memories.filter(m => m.name.toLowerCase().includes(searchName.trim().toLowerCase()))
    : memories;

  const selectedDataCount = memories
    .filter(m => selectedIds.has(m.memory_id))
    .reduce((sum, m) => sum + (m.data_count ?? 0), 0);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const timeAgo = (dateString: string) => {
    const diff = Date.now() - new Date(dateString).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-primary-400 animate-spin mr-3" />
        <span className="text-white/60">Loading memories...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Error Banner */}
      {error && (
        <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <span className="text-red-300 text-sm">{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-2 p-1 bg-white/5 rounded-xl">
            {[
              { label: 'All', value: undefined },
              { label: 'Active', value: true },
              { label: 'Ended', value: false },
            ].map((filter) => (
              <button
                key={filter.label}
                onClick={() => setFilterActive(filter.value)}
                className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  filterActive === filter.value
                    ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
                    : 'text-white/50 hover:text-white/70 hover:bg-white/5'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
          <select
            value={filterMemoryType}
            onChange={e => setFilterMemoryType(e.target.value)}
            className="bg-black/30 text-white border border-white/10 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-primary-500/50"
          >
            <option value="">All types</option>
            {MEMORY_TYPES.map(t => (
              <option key={t} value={t}>{memoryTypeLabel(t)}</option>
            ))}
          </select>
          <select
            value={filterSubType}
            onChange={e => setFilterSubType(e.target.value)}
            className="bg-black/30 text-white border border-white/10 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-primary-500/50"
          >
            <option value="">All sub-types</option>
            {PREDETERMINED_SUB_TYPES.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/30 pointer-events-none" />
          <input
            type="text"
            value={searchName}
            onChange={e => setSearchName(e.target.value)}
            placeholder="Search by name..."
            className="pl-8 pr-3 py-1.5 w-48 bg-black/30 text-white text-xs border border-white/10 rounded-lg placeholder:text-white/25 focus:outline-none focus:border-primary-500/50 transition-all"
          />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleSelectionMode}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
              selectionMode
                ? 'border-primary-500/50 bg-primary-500/10 text-primary-400'
                : 'text-white/50 border-white/10 hover:bg-white/5 hover:text-white/70'
            }`}
          >
            {selectionMode ? <Square className="w-3.5 h-3.5" /> : <CheckSquare className="w-3.5 h-3.5" />}
            {selectionMode ? 'Cancel' : 'Select'}
          </button>
          {selectionMode && (
            <>
              <button
                onClick={selectAll}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white/50 border border-white/10 hover:bg-white/5 hover:text-white/70 transition-all"
              >
                Select All
              </button>
              <button
                onClick={deselectAll}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white/50 border border-white/10 hover:bg-white/5 hover:text-white/70 transition-all"
              >
                Deselect All
              </button>
              <button
                onClick={() => setBulkDeleteConfirm(true)}
                disabled={selectedIds.size === 0}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete Selected ({selectedIds.size})
              </button>
            </>
          )}
          <button
            onClick={() => fetchMemories()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white/50 border border-white/10 hover:bg-white/5 hover:text-white/70 transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
          <button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25 transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            New Memory
          </button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6">
        {/* Memory List */}
        <div className="glass-card p-0 overflow-hidden">
          <div className="px-5 py-4 border-b border-white/10 flex items-center gap-2">
            <Layers className="w-4 h-4 text-primary-400" />
            <span className="text-sm font-semibold text-white/80 uppercase tracking-wider">Memories</span>
            <span className="ml-1 text-xs bg-white/10 text-white/50 px-2 py-0.5 rounded-full">{filteredMemories.length}{searchName.trim() ? ` / ${memories.length}` : ''}</span>
            {memoryStatsInfo && memoryStatsInfo.active_sessions > 0 && (
              <span className="ml-1 inline-flex items-center gap-1 text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                <Activity className="w-3 h-3" />
                {memoryStatsInfo.active_sessions} active
              </span>
            )}
          </div>

          <div className="p-2 max-h-[600px] overflow-y-auto">
            {filteredMemories.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 px-4">
                <div className="w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center mb-4">
                  {searchName.trim() ? <Search className="w-7 h-7 text-white/20" /> : <Layers className="w-7 h-7 text-white/20" />}
                </div>
                <p className="text-white/40 text-sm text-center">{searchName.trim() ? `No memories matching "${searchName.trim()}"` : 'No memories found'}</p>
                <p className="text-white/25 text-xs mt-1">{searchName.trim() ? 'Try a different search term' : 'Create a memory to start grouping data'}</p>
              </div>
            ) : (
              <div className="space-y-1">
                {filteredMemories.map(memory => {
                  const isSelected = selectedMemory?.memory_id === memory.memory_id;
                  const isChecked = selectedIds.has(memory.memory_id);
                  return (
                    <button
                      key={memory.memory_id}
                      onClick={() => selectionMode ? toggleSelection(memory.memory_id) : setSelectedMemory(memory)}
                      className={`w-full text-left px-3 py-3 rounded-xl transition-all duration-200 group ${
                        selectionMode
                          ? isChecked
                            ? 'bg-primary-500/15 border border-primary-500/30'
                            : 'hover:bg-white/5 border border-transparent'
                          : isSelected
                            ? 'bg-gradient-to-r from-primary-500/20 to-accent-500/10 border border-primary-500/30 shadow-lg shadow-primary-500/10'
                            : 'hover:bg-white/5 border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        {selectionMode ? (
                          <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 bg-white/5">
                            {isChecked ? (
                              <CheckSquare className="w-5 h-5 text-primary-400" />
                            ) : (
                              <Square className="w-5 h-5 text-white/30" />
                            )}
                          </div>
                        ) : (
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                          memory.active
                            ? isSelected ? 'bg-emerald-500/30' : 'bg-emerald-500/15 group-hover:bg-emerald-500/20'
                            : isSelected ? 'bg-white/10' : 'bg-white/5 group-hover:bg-white/10'
                        } transition-colors`}>
                          <Layers className={`w-5 h-5 ${memory.active ? 'text-emerald-400' : 'text-white/30'}`} />
                        </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={`font-semibold text-sm truncate ${(selectionMode ? isChecked : isSelected) ? 'text-white' : 'text-white/80'}`}>
                              {memory.name || '(unnamed)'}
                            </span>
                            <span className="text-[10px] text-white/30 bg-white/5 px-1.5 py-0.5 rounded">{memoryTypeLabel(memory.memory_type)}</span>
                            {memory.category && (
                              <span className="text-[10px] text-white/20 bg-white/5 px-1.5 py-0.5 rounded">{memory.category}</span>
                            )}
                            {memory.sub_type && (
                              <span className="text-[10px] text-white/25 bg-white/5 px-1.5 py-0.5 rounded border border-white/5">{memory.sub_type}</span>
                            )}
                            {(() => { const a = accessLevelIcon(memory.access_level); return (
                              <span className={`text-[10px] ${a.color} bg-white/5 px-1.5 py-0.5 rounded inline-flex items-center gap-0.5`}>
                                <a.Icon className="w-2.5 h-2.5" />{a.label}
                              </span>
                            ); })()}
                            {memory.project_id && (
                              <span className="text-[10px] text-primary-400/60 bg-primary-500/10 px-1.5 py-0.5 rounded inline-flex items-center gap-0.5">
                                <FolderOpen className="w-2.5 h-2.5" />{memory.project_id.substring(0, 16)}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <code className="text-[10px] text-white/25 font-mono truncate max-w-[140px]">{memory.memory_id}</code>
                            <span className="text-white/10">|</span>
                            <Package className="w-3 h-3 text-white/30" />
                            <span className="text-xs text-white/40">{memory.data_count} items</span>
                            {formatExpiry(memory.expires_at) && (
                              <>
                                <span className="text-white/10">|</span>
                                <Clock className="w-3 h-3 text-white/30" />
                                <span className={`text-[10px] ${formatExpiry(memory.expires_at) === 'Expired' ? 'text-red-400' : 'text-white/40'}`}>{formatExpiry(memory.expires_at)}</span>
                              </>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1.5">
                          <div className="flex items-center gap-1.5">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[10px] font-semibold uppercase tracking-wider ${
                              memory.active
                                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                                : 'bg-white/5 text-white/30 border-white/10'
                            }`}>
                              {memory.active ? <CheckCircle className="w-2.5 h-2.5" /> : <XCircle className="w-2.5 h-2.5" />}
                              {memory.active ? 'Active' : 'Ended'}
                            </span>
                            {!selectionMode && (
                            <button
                              onClick={(e) => { e.stopPropagation(); setDeleteTarget(memory); }}
                              className="p-1 rounded-md text-white/20 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
                              title="Delete memory"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                            )}
                          </div>
                          <span className="text-[10px] text-white/25">{timeAgo(memory.updated_at)}</span>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Memory Detail */}
        <div className="glass-card p-0 overflow-hidden">
          {selectedMemory ? (
            <>
              {/* Detail Header */}
              <div className="relative px-6 py-5 border-b border-white/10">
                <div className="absolute inset-0 bg-gradient-to-r from-primary-600/5 via-accent-500/5 to-transparent" />
                <div className="relative flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-2xl flex items-center justify-center border border-white/10 ${
                      selectedMemory.active
                        ? 'bg-gradient-to-br from-emerald-500/30 to-emerald-600/20'
                        : 'bg-white/5'
                    }`}>
                      <Layers className={`w-6 h-6 ${selectedMemory.active ? 'text-emerald-400' : 'text-white/30'}`} />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-white">{selectedMemory.name || '(unnamed)'}</h3>
                      <div className="flex items-center gap-3 mt-0.5">
                        <code className="text-xs text-white/40 font-mono">{selectedMemory.memory_id}</code>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[10px] font-semibold uppercase ${
                          selectedMemory.active
                            ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                            : 'bg-white/5 text-white/30 border-white/10'
                        }`}>
                          {selectedMemory.active ? 'Active' : 'Ended'}
                        </span>
                        <span className="text-[10px] text-white/30 bg-white/5 px-1.5 py-0.5 rounded">{memoryTypeLabel(selectedMemory.memory_type)}</span>
                        {selectedMemory.category && (
                          <span className="text-[10px] text-white/20 bg-white/5 px-1.5 py-0.5 rounded">{selectedMemory.category}</span>
                        )}
                        {selectedMemory.sub_type && (
                          <span className="text-[10px] text-white/25 bg-white/5 px-1.5 py-0.5 rounded border border-white/5">{selectedMemory.sub_type}</span>
                        )}
                        {(() => { const a = accessLevelIcon(selectedMemory.access_level); return (
                          <span className={`text-[10px] ${a.color} bg-white/5 px-1.5 py-0.5 rounded inline-flex items-center gap-0.5`}>
                            <a.Icon className="w-2.5 h-2.5" />{a.label}
                          </span>
                        ); })()}
                        {formatExpiry(selectedMemory.expires_at) && (
                          <span className={`text-[10px] ${formatExpiry(selectedMemory.expires_at) === 'Expired' ? 'text-red-400' : 'text-white/40'} bg-white/5 px-1.5 py-0.5 rounded inline-flex items-center gap-0.5`}>
                            <Clock className="w-2.5 h-2.5" />{formatExpiry(selectedMemory.expires_at)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedMemory.active && (
                      <button
                        onClick={() => handleDeactivateMemory(selectedMemory.memory_id)}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-colors text-xs font-medium"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        Deactivate
                      </button>
                    )}
                    <button
                      onClick={() => setDeleteTarget(selectedMemory)}
                      className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors text-xs font-medium"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Delete
                    </button>
                  </div>
                </div>
              </div>

              <div className="p-6 space-y-6 max-h-[550px] overflow-y-auto">
                {/* Info Cards */}
                <div>
                  <h4 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <Hash className="w-3.5 h-3.5" /> Info
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="bg-gradient-to-br from-accent-500/10 to-accent-600/5 rounded-xl px-4 py-3 border border-accent-500/10">
                      <div className="flex items-center gap-2 mb-1">
                        <Layers className="w-3 h-3 text-white/30" />
                        <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Name</span>
                      </div>
                      <span className="text-sm text-white/90 font-semibold truncate block">{selectedMemory.name || '(unnamed)'}</span>
                    </div>
                    <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                      <div className="flex items-center gap-2 mb-1">
                        <User className="w-3 h-3 text-white/30" />
                        <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">User</span>
                      </div>
                      <span className="text-sm text-white/80 font-medium">{selectedMemory.user_id}</span>
                    </div>
                    {selectedMemory.sub_type && (
                      <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                        <div className="flex items-center gap-2 mb-1">
                          <Layers className="w-3 h-3 text-white/30" />
                          <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Sub-type</span>
                        </div>
                        <span className="text-sm text-white/80 font-medium">{selectedMemory.sub_type}</span>
                      </div>
                    )}
                    <div className="bg-gradient-to-br from-primary-500/10 to-primary-600/5 rounded-xl px-4 py-3 border border-primary-500/10">
                      <div className="flex items-center gap-2 mb-1">
                        <Package className="w-3 h-3 text-white/30" />
                        <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Data Items</span>
                      </div>
                      <span className="text-xl font-bold text-white">{selectedMemory.data_count}</span>
                    </div>
                    <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                      <div className="flex items-center gap-2 mb-1">
                        <Clock className="w-3 h-3 text-white/30" />
                        <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Created</span>
                      </div>
                      <span className="text-xs text-white/60">{formatDate(selectedMemory.created_at)}</span>
                    </div>
                    <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                      <div className="flex items-center gap-2 mb-1">
                        <Clock className="w-3 h-3 text-white/30" />
                        <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Last Updated</span>
                      </div>
                      <span className="text-xs text-white/60">{formatDate(selectedMemory.updated_at)}</span>
                    </div>
                    <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                      <div className="flex items-center gap-2 mb-1">
                        {(() => { const a = accessLevelIcon(selectedMemory.access_level); return <a.Icon className={`w-3 h-3 ${a.color}`} />; })()}
                        <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Access</span>
                      </div>
                      <span className="text-sm text-white/80 font-medium capitalize">{selectedMemory.access_level || 'private'}</span>
                      {selectedMemory.shared_with && selectedMemory.shared_with.length > 0 && (
                        <p className="text-[10px] text-white/40 mt-1 truncate" title={selectedMemory.shared_with.join(', ')}>
                          Shared with: {selectedMemory.shared_with.join(', ')}
                        </p>
                      )}
                    </div>
                    <div className={`rounded-xl px-4 py-3 border ${
                      selectedMemory.expires_at
                        ? formatExpiry(selectedMemory.expires_at) === 'Expired'
                          ? 'bg-red-500/10 border-red-500/20'
                          : 'bg-amber-500/10 border-amber-500/20'
                        : 'bg-white/5 border-white/5'
                    }`}>
                      <div className="flex items-center gap-2 mb-1">
                        <Clock className={`w-3 h-3 ${
                          selectedMemory.expires_at
                            ? formatExpiry(selectedMemory.expires_at) === 'Expired' ? 'text-red-400' : 'text-amber-400'
                            : 'text-white/30'
                        }`} />
                        <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Expiry</span>
                      </div>
                      {selectedMemory.expires_at ? (
                        <>
                          <span className={`text-sm font-medium ${
                            formatExpiry(selectedMemory.expires_at) === 'Expired' ? 'text-red-400' : 'text-amber-300'
                          }`}>{formatExpiry(selectedMemory.expires_at)}</span>
                          <p className="text-[10px] text-white/30 mt-0.5">{new Date(selectedMemory.expires_at).toLocaleString()}</p>
                        </>
                      ) : (
                        <span className="text-sm text-white/60 font-medium">Never</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Device Info */}
                {selectedMemory.device_info && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3 flex items-center gap-2">
                      <Smartphone className="w-3.5 h-3.5" /> Device
                    </h4>
                    <div className="grid grid-cols-3 gap-3">
                      {selectedMemory.device_info.type && (
                        <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                          <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold block mb-1">Type</span>
                          <span className="text-sm text-white/70">{selectedMemory.device_info.type}</span>
                        </div>
                      )}
                      {selectedMemory.device_info.os && (
                        <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                          <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold block mb-1">OS</span>
                          <span className="text-sm text-white/70">{selectedMemory.device_info.os}</span>
                        </div>
                      )}
                      {selectedMemory.device_info.browser && (
                        <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                          <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold block mb-1">Browser</span>
                          <span className="text-sm text-white/70">{selectedMemory.device_info.browser}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Memory Data */}
                <div>
                  <h4 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <Package className="w-3.5 h-3.5" /> Data Items ({memoryDataTotal})
                  </h4>
                  {dataLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="w-5 h-5 text-primary-400 animate-spin mr-2" />
                      <span className="text-white/40 text-sm">Loading data...</span>
                    </div>
                  ) : memoryData.length === 0 ? (
                    <div className="bg-white/[0.02] rounded-xl border border-dashed border-white/10 px-4 py-8 text-center">
                      <Package className="w-8 h-8 text-white/10 mx-auto mb-2" />
                      <p className="text-white/30 text-sm">No data in this memory</p>
                      <p className="text-white/20 text-xs mt-1">Upload data with this memory ID to associate it</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {memoryData.map((item: any) => (
                        <div key={item.data_id} className="flex items-center justify-between px-4 py-3 bg-white/5 rounded-xl border border-white/5 group hover:border-white/10 transition-colors">
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="w-8 h-8 rounded-lg bg-accent-500/10 flex items-center justify-center flex-shrink-0">
                              <Package className="w-4 h-4 text-accent-400" />
                            </div>
                            <div className="min-w-0">
                              <span className="text-sm font-medium text-white/80 block truncate">
                                {item.name || item.data_id.substring(0, 12) + '...'}
                              </span>
                              <div className="flex items-center gap-2 text-[10px] text-white/30 font-mono">
                                <span>{item.content_type}</span>
                                <span className="text-white/10">|</span>
                                <span>{formatBytes(item.size)}</span>
                                <span className="text-white/10">|</span>
                                <span>v{item.current_version}</span>
                              </div>
                            </div>
                          </div>
                          <a
                            href={`/data/${item.data_id}`}
                            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-primary-400/60 hover:text-primary-400 hover:bg-primary-500/10 transition-all opacity-0 group-hover:opacity-100"
                          >
                            <Eye className="w-3 h-3" />
                            View
                          </a>
                        </div>
                      ))}
                    </div>
                  )}
                  {selectedMemory && memoryDataTotal > memoryDataPageSize && (
                    <div className="flex items-center justify-between mt-3 pt-3 border-t border-white/10">
                      <p className="text-xs text-white/40">
                        {memoryDataPage * memoryDataPageSize + 1}–{Math.min((memoryDataPage + 1) * memoryDataPageSize, memoryDataTotal)} of {memoryDataTotal}
                      </p>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => fetchMemoryData(selectedMemory.memory_id, memoryDataPage - 1)}
                          disabled={!memoryDataHasPrev || dataLoading}
                          className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs border border-white/10 text-white/60 hover:text-white hover:bg-white/5 disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          <ChevronLeft className="w-3.5 h-3.5" /> Prev
                        </button>
                        <span className="text-xs text-white/40 px-1">Page {memoryDataPage + 1} of {memoryDataTotalPages}</span>
                        <button
                          type="button"
                          onClick={() => fetchMemoryData(selectedMemory.memory_id, memoryDataPage + 1)}
                          disabled={!memoryDataHasNext || dataLoading}
                          className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs border border-white/10 text-white/60 hover:text-white hover:bg-white/5 disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          Next <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Metadata */}
                {selectedMemory.metadata && Object.keys(selectedMemory.metadata).length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3">Metadata</h4>
                    <pre className="bg-black/30 rounded-xl p-4 text-xs text-white/60 font-mono overflow-x-auto border border-white/5">
                      {JSON.stringify(selectedMemory.metadata, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 px-6">
              <div className="w-20 h-20 rounded-3xl bg-white/5 flex items-center justify-center mb-5 border border-white/5">
                <Layers className="w-10 h-10 text-white/10" />
              </div>
              <p className="text-white/30 text-base font-medium">Select a memory</p>
              <p className="text-white/20 text-sm mt-1">Choose from the list to view details and associated data</p>
            </div>
          )}
        </div>
      </div>

      {/* Bulk Delete Memories Confirmation Modal */}
      {bulkDeleteConfirm && selectedIds.size > 0 && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => { setBulkDeleteConfirm(false); setBulkDeleteWithData(false); }}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md" onClick={e => e.stopPropagation()}>
            <div className="glass-card p-6 border-white/15 shadow-2xl">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center">
                    <Trash2 className="w-5 h-5 text-red-400" />
                  </div>
                  <h3 className="text-lg font-bold text-white">Delete Memories</h3>
                </div>
                <button onClick={() => { setBulkDeleteConfirm(false); setBulkDeleteWithData(false); }} className="text-white/30 hover:text-white/60 transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div className="bg-red-500/5 border border-red-500/20 rounded-xl px-4 py-3">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm text-red-300 font-medium">This action is irreversible</p>
                      <p className="text-xs text-red-300/60 mt-1">
                        {selectedIds.size} memor{selectedIds.size === 1 ? 'y' : 'ies'} will be permanently deleted.
                      </p>
                    </div>
                  </div>
                </div>

                {selectedDataCount > 0 && (
                  <label className="flex items-start gap-3 px-4 py-3 bg-white/5 rounded-xl border border-white/5 cursor-pointer hover:border-white/10 transition-colors">
                    <input
                      type="checkbox"
                      checked={bulkDeleteWithData}
                      onChange={(e) => setBulkDeleteWithData(e.target.checked)}
                      className="mt-0.5 rounded border-white/20 bg-white/5 text-red-500 focus:ring-red-500/25"
                    />
                    <div>
                      <span className="text-sm text-white/80 font-medium">Also delete associated data</span>
                      <p className="text-xs text-white/40 mt-0.5">
                        Permanently removes {selectedDataCount} data item{selectedDataCount !== 1 ? 's' : ''} linked to selected memories.
                      </p>
                    </div>
                  </label>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => { setBulkDeleteConfirm(false); setBulkDeleteWithData(false); }}
                    className="flex-1 px-4 py-2.5 rounded-xl border border-white/10 text-white/60 hover:bg-white/5 text-sm font-medium transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleBulkDeleteMemories}
                    disabled={bulkDeleting}
                    className="flex-1 px-4 py-2.5 rounded-xl bg-red-500/80 text-white text-sm font-semibold hover:bg-red-500 transition-all disabled:opacity-50"
                  >
                    {bulkDeleting ? (
                      <span className="flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Deleting...
                      </span>
                    ) : bulkDeleteWithData ? 'Delete Memories & Data' : 'Delete Memories'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Memory Confirmation Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => { setDeleteTarget(null); setDeleteWithData(false); }}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md" onClick={e => e.stopPropagation()}>
            <div className="glass-card p-6 border-white/15 shadow-2xl">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center">
                    <Trash2 className="w-5 h-5 text-red-400" />
                  </div>
                  <h3 className="text-lg font-bold text-white">Delete Memory</h3>
                </div>
                <button onClick={() => { setDeleteTarget(null); setDeleteWithData(false); }} className="text-white/30 hover:text-white/60 transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div className="bg-red-500/5 border border-red-500/20 rounded-xl px-4 py-3">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm text-red-300 font-medium">This action is irreversible</p>
                      <p className="text-xs text-red-300/60 mt-1">
                        Memory <code className="bg-black/30 px-1.5 py-0.5 rounded text-red-300/80">{deleteTarget.memory_id.substring(0, 20)}...</code> will be permanently deleted.
                      </p>
                    </div>
                  </div>
                </div>

                {deleteTarget.data_count > 0 && (
                  <label className="flex items-start gap-3 px-4 py-3 bg-white/5 rounded-xl border border-white/5 cursor-pointer hover:border-white/10 transition-colors">
                    <input
                      type="checkbox"
                      checked={deleteWithData}
                      onChange={(e) => setDeleteWithData(e.target.checked)}
                      className="mt-0.5 rounded border-white/20 bg-white/5 text-red-500 focus:ring-red-500/25"
                    />
                    <div>
                      <span className="text-sm text-white/80 font-medium">Also delete associated data</span>
                      <p className="text-xs text-white/40 mt-0.5">
                        Permanently removes {deleteTarget.data_count} data item{deleteTarget.data_count !== 1 ? 's' : ''} linked to this memory.
                      </p>
                    </div>
                  </label>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => { setDeleteTarget(null); setDeleteWithData(false); }}
                    className="flex-1 px-4 py-2.5 rounded-xl border border-white/10 text-white/60 hover:bg-white/5 text-sm font-medium transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDeleteMemory}
                    disabled={deleting}
                    className="flex-1 px-4 py-2.5 rounded-xl bg-red-500/80 text-white text-sm font-semibold hover:bg-red-500 transition-all disabled:opacity-50"
                  >
                    {deleting ? (
                      <span className="flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Deleting...
                      </span>
                    ) : deleteWithData ? 'Delete Memory & Data' : 'Delete Memory'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create Memory Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowCreateForm(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md" onClick={e => e.stopPropagation()}>
            <div className="glass-card p-6 border-white/15 shadow-2xl">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500/30 to-accent-500/30 flex items-center justify-center">
                    <Plus className="w-5 h-5 text-primary-300" />
                  </div>
                  <h3 className="text-lg font-bold text-white">New Memory</h3>
                </div>
                <button onClick={() => setShowCreateForm(false)} className="text-white/30 hover:text-white/60 transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <form onSubmit={handleCreateMemory} className="space-y-4">
                {/* Project scope indicator */}
                {selectedProject && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary-500/10 border border-primary-500/20">
                    <FolderOpen className="w-3.5 h-3.5 text-primary-400" />
                    <span className="text-xs text-primary-300">
                      Creating in{' '}
                      <span className="font-semibold">{selectedOrg?.display_name || selectedOrg?.name}</span>
                      {' / '}
                      <span className="font-semibold">{selectedProject.display_name || selectedProject.name}</span>
                    </span>
                  </div>
                )}
                {!selectedProject && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20">
                    <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                    <span className="text-xs text-amber-300">No project selected — memory will not be scoped to a project</span>
                  </div>
                )}
                <div>
                  <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Name</label>
                  <input
                    type="text"
                    value={formName}
                    onChange={e => setFormName(e.target.value)}
                    placeholder={`e.g. ${getCurrentUserInfo().display_name || getCurrentUserInfo().username || 'user'}-${memoryTypeLabel(formMemoryType)}`}
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                  />
                  <p className="text-[11px] text-white/25 mt-1.5">Leave blank to auto-name as <span className="text-white/40">{getCurrentUserInfo().display_name || getCurrentUserInfo().username || 'user'}-{memoryTypeLabel(formMemoryType)}</span></p>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Memory Type</label>
                  <select
                    value={formMemoryType}
                    onChange={e => setFormMemoryType(e.target.value as MemoryType)}
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                  >
                    {MEMORY_TYPES.map(t => (
                      <option key={t} value={t}>{memoryTypeLabel(t)}</option>
                    ))}
                  </select>
                </div>
                {formMemoryType === 'custom' && (
                  <div>
                    <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Sub-type</label>
                    <select
                      value={formSubType}
                      onChange={e => setFormSubType(e.target.value)}
                      className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                    >
                      <option value="">—</option>
                      {PREDETERMINED_SUB_TYPES.map(s => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                      <option value="other">Other</option>
                    </select>
                  </div>
                )}
                <div>
                  <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">User ID</label>
                  <input
                    type="text"
                    value={formUserId}
                    onChange={e => setFormUserId(e.target.value)}
                    placeholder={getCurrentUserId()}
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                  />
                  <p className="text-white/25 text-xs mt-1.5">Defaults to active user ID. Device info is captured automatically.</p>
                </div>

                {/* Expiry */}
                <div>
                  <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Expiry</label>
                  <div className="flex items-center gap-3">
                    <input
                      type="number"
                      min="1"
                      value={formTtlHours}
                      onChange={e => { setFormTtlHours(e.target.value); if (e.target.value) setFormNoExpiry(false); }}
                      disabled={formNoExpiry}
                      placeholder="TTL in hours"
                      className="flex-1 bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all disabled:opacity-30"
                    />
                    <label className="flex items-center gap-2 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={formNoExpiry}
                        onChange={e => { setFormNoExpiry(e.target.checked); if (e.target.checked) setFormTtlHours(''); }}
                        className="w-4 h-4 rounded border-white/20 bg-black/30 text-primary-500 focus:ring-primary-500/25"
                      />
                      <span className="text-xs text-white/50">Never expire</span>
                    </label>
                  </div>
                  <p className="text-[11px] text-white/25 mt-1.5">Leave blank to use the default TTL for this type</p>
                </div>

                {/* Access Level */}
                <div>
                  <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Access Level</label>
                  <select
                    value={formAccessLevel}
                    onChange={e => setFormAccessLevel(e.target.value)}
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                  >
                    <option value="private">Private — only you</option>
                    <option value="shared">Shared — specific users</option>
                    <option value="public">Public — everyone</option>
                    <option value="restricted">Restricted — specific users only</option>
                  </select>
                </div>

                {/* Shared With (visible when shared or restricted) */}
                {(formAccessLevel === 'shared' || formAccessLevel === 'restricted') && (
                  <div>
                    <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Share With</label>
                    <input
                      type="text"
                      value={formSharedWith}
                      onChange={e => setFormSharedWith(e.target.value)}
                      placeholder="user_id_1, user_id_2, ..."
                      className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                    />
                    <p className="text-[11px] text-white/25 mt-1.5">Comma-separated user IDs who can access this memory</p>
                  </div>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowCreateForm(false)}
                    className="flex-1 px-4 py-2.5 rounded-xl border border-white/10 text-white/60 hover:bg-white/5 text-sm font-medium transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creating}
                    className="flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-primary-500 to-accent-500 text-white text-sm font-semibold hover:shadow-lg hover:shadow-primary-500/25 transition-all disabled:opacity-50"
                  >
                    {creating ? (
                      <span className="flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Creating...
                      </span>
                    ) : 'Create Memory'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MemoryManager;

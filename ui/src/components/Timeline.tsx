'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  RefreshCw, Plus, RefreshCcw, Trash2, AlertCircle,
  Activity, ExternalLink, Loader2, Inbox, Search, ChevronDown,
  Database, Lock, Users, Globe, Clock,
} from 'lucide-react';
import type { MemoryDataEntry, MemoryResponse } from '@/types';
import { listMemories, getMemoryEntries, formatDate } from '@/lib/api';

/**
 * Displays an activity timeline by loading all timeline-type memories,
 * letting the user search/select a specific one, and rendering its
 * entries (data associations with action/version metadata).
 */
export default function Timeline() {
  const [timelineMemories, setTimelineMemories] = useState<MemoryResponse[]>([]);
  const [filteredMemories, setFilteredMemories] = useState<MemoryResponse[]>([]);
  const [selectedMemory, setSelectedMemory] = useState<MemoryResponse | null>(null);
  const [entries, setEntries] = useState<MemoryDataEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    loadTimelineMemories();
  }, []);

  useEffect(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) {
      setFilteredMemories(timelineMemories);
    } else {
      setFilteredMemories(
        timelineMemories.filter(
          (m) =>
            m.name.toLowerCase().includes(q) ||
            m.memory_id.toLowerCase().includes(q) ||
            (m.description ?? '').toLowerCase().includes(q)
        )
      );
    }
  }, [searchQuery, timelineMemories]);

  const loadTimelineMemories = async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      const memoriesResponse = await listMemories({ memoryType: 'timeline', limit: 200 });
      setTimelineMemories(memoriesResponse.items);
      setFilteredMemories(memoriesResponse.items);

      if (memoriesResponse.items.length > 0) {
        const current = selectedMemory
          ? memoriesResponse.items.find((m) => m.memory_id === selectedMemory.memory_id) ?? memoriesResponse.items[0]
          : memoriesResponse.items[0];
        setSelectedMemory(current);
        await loadEntries(current.memory_id);
      } else {
        setSelectedMemory(null);
        setEntries([]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load timeline memories');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const loadEntries = useCallback(async (memoryId: string) => {
    try {
      setEntriesLoading(true);
      const entriesResponse = await getMemoryEntries(memoryId);
      setEntries(entriesResponse.entries ?? []);
    } catch (err: any) {
      setError(err.message || 'Failed to load timeline entries');
    } finally {
      setEntriesLoading(false);
    }
  }, []);

  const handleSelectMemory = async (memory: MemoryResponse) => {
    setSelectedMemory(memory);
    setDropdownOpen(false);
    setSearchQuery('');
    await loadEntries(memory.memory_id);
  };

  const getActionConfig = (action: string | undefined) => {
    switch (action) {
      case 'create':
        return {
          icon: Plus,
          gradient: 'from-emerald-500 to-teal-500',
          bgColor: 'bg-emerald-500/20',
          textColor: 'text-emerald-400',
          borderColor: 'border-emerald-500/30',
          label: 'Created',
        };
      case 'update':
        return {
          icon: RefreshCcw,
          gradient: 'from-blue-500 to-cyan-500',
          bgColor: 'bg-blue-500/20',
          textColor: 'text-blue-400',
          borderColor: 'border-blue-500/30',
          label: 'Updated',
        };
      case 'delete':
        return {
          icon: Trash2,
          gradient: 'from-red-500 to-rose-500',
          bgColor: 'bg-red-500/20',
          textColor: 'text-red-400',
          borderColor: 'border-red-500/30',
          label: 'Deleted',
        };
      default:
        return {
          icon: Activity,
          gradient: 'from-gray-500 to-slate-500',
          bgColor: 'bg-gray-500/20',
          textColor: 'text-gray-400',
          borderColor: 'border-gray-500/30',
          label: action || 'associated',
        };
    }
  };

  if (loading) {
    return (
      <div className="glass-card p-12">
        <div className="flex flex-col items-center justify-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary-500/20 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
          </div>
          <p className="text-white/60">Loading audit log...</p>
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
          <button onClick={() => loadTimelineMemories()} className="btn-secondary flex items-center gap-2">
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (timelineMemories.length === 0) {
    return (
      <div className="glass-card p-12">
        <div className="flex flex-col items-center justify-center gap-4 text-center">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary-500/20 to-accent-500/20 flex items-center justify-center">
            <Inbox className="w-10 h-10 text-white/40" />
          </div>
          <div>
            <h3 className="text-xl font-semibold text-white">No Audit Memories Yet</h3>
            <p className="text-white/50 mt-1">Audit memories will appear here when data is uploaded</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-5 border-b border-white/10">
        <p className="text-sm text-white/50">
          <span className="font-semibold text-white">{timelineMemories.length}</span> audit memor{timelineMemories.length !== 1 ? 'ies' : 'y'} available
        </p>
        <button
          onClick={() => loadTimelineMemories(true)}
          disabled={refreshing}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Timeline Memory Selector */}
      <div className="p-6 border-b border-white/10">
        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="w-full flex items-center justify-between gap-3 px-4 py-3 rounded-xl
              bg-white/5 border border-white/10 hover:border-white/20 transition-colors text-left"
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500/30 to-accent-500/30 flex items-center justify-center flex-shrink-0">
                <Database className="w-4 h-4 text-primary-400" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">
                  {selectedMemory?.name ?? 'Select an audit memory'}
                </p>
                <p className="text-xs text-white/40 truncate">
                  {selectedMemory?.memory_id} &middot; {selectedMemory?.data_count ?? 0} items
                  {selectedMemory?.access_level && selectedMemory.access_level !== 'private' && (
                    <> &middot; {selectedMemory.access_level}</>
                  )}
                </p>
              </div>
            </div>
            <ChevronDown className={`w-4 h-4 text-white/50 flex-shrink-0 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
          </button>

          {dropdownOpen && (
            <div className="absolute z-20 mt-2 w-full rounded-xl bg-gray-900 border border-white/10 shadow-2xl overflow-hidden">
              {/* Search input */}
              <div className="p-3 border-b border-white/10">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search audit memories..."
                    className="w-full pl-10 pr-4 py-2 rounded-lg bg-white/5 border border-white/10
                      text-sm text-white placeholder-white/30 focus:outline-none focus:border-primary-500/50"
                    autoFocus
                  />
                </div>
              </div>

              {/* Dropdown list */}
              <div className="max-h-64 overflow-y-auto">
                {filteredMemories.length === 0 ? (
                  <div className="px-4 py-6 text-center text-sm text-white/40">
                    No matching audit memories
                  </div>
                ) : (
                  filteredMemories.map((memory) => (
                    <button
                      key={memory.memory_id}
                      onClick={() => handleSelectMemory(memory)}
                      className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/5 transition-colors
                        ${selectedMemory?.memory_id === memory.memory_id ? 'bg-primary-500/10 border-l-2 border-primary-500' : ''}`}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-white truncate">{memory.name}</p>
                        <p className="text-xs text-white/40 truncate">
                          {memory.memory_id} &middot; {memory.data_count} items &middot; {formatDate(memory.created_at)}
                        </p>
                        {memory.description && (
                          <p className="text-xs text-white/30 truncate mt-0.5">{memory.description}</p>
                        )}
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Close dropdown on outside click */}
      {dropdownOpen && (
        <div className="fixed inset-0 z-10" onClick={() => { setDropdownOpen(false); setSearchQuery(''); }} />
      )}

      {/* Entries */}
      {entriesLoading ? (
        <div className="p-12">
          <div className="flex flex-col items-center justify-center gap-4">
            <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
            <p className="text-white/60 text-sm">Loading entries...</p>
          </div>
        </div>
      ) : entries.length === 0 ? (
        <div className="p-12">
          <div className="flex flex-col items-center justify-center gap-4 text-center">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500/20 to-accent-500/20 flex items-center justify-center">
              <Inbox className="w-8 h-8 text-white/40" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">No Events</h3>
              <p className="text-white/50 text-sm mt-1">This audit memory has no recorded events yet</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-6">
          <p className="text-sm text-white/50 mb-4">
            {entries.length} event{entries.length !== 1 ? 's' : ''} recorded
          </p>
          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-[19px] top-0 bottom-0 w-0.5 bg-gradient-to-b from-primary-500/50 via-accent-500/30 to-transparent" />

            <div className="space-y-6">
              {entries.map((entry, index) => {
                const config = getActionConfig(entry.action);
                const Icon = config.icon;

                return (
                  <div
                    key={`${entry.data_id}-${entry.associated_at}-${index}`}
                    className="relative pl-12 animate-in"
                    style={{ animationDelay: `${index * 100}ms` }}
                  >
                    {/* Icon */}
                    <div className={`
                      absolute left-0 top-0 w-10 h-10 rounded-xl 
                      bg-gradient-to-br ${config.gradient}
                      flex items-center justify-center shadow-lg
                    `}>
                      <Icon className="w-5 h-5 text-white" />
                    </div>

                    {/* Content Card */}
                    <div className={`
                      rounded-xl border ${config.borderColor} ${config.bgColor}
                      p-4 transition-all duration-300 hover:scale-[1.01]
                    `}>
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <span className={`font-semibold ${config.textColor}`}>
                            {config.label}
                          </span>
                          <span className="text-white/50 text-sm ml-2">
                            {formatDate(entry.associated_at)}
                          </span>
                        </div>
                        {entry.version != null && (
                          <span className="badge badge-info">v{entry.version}</span>
                        )}
                      </div>

                      <div className="space-y-2 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="text-white/50">Data ID:</span>
                          <code className="text-xs text-primary-400 bg-primary-500/10 px-2 py-1 rounded-md">
                            {entry.data_id.substring(0, 20)}...
                          </code>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-white/50">Memory:</span>
                          <code className="text-xs text-white/60 bg-white/5 px-2 py-1 rounded-md break-all">
                            {entry.memory_id}
                          </code>
                        </div>
                      </div>

                      {entry.action !== 'delete' && (
                        <Link
                          href={`/data/${entry.data_id}`}
                          className="
                            inline-flex items-center gap-1.5 mt-4 text-sm font-medium
                            text-primary-400 hover:text-primary-300 transition-colors
                          "
                        >
                          View Details
                          <ExternalLink className="w-4 h-4" />
                        </Link>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

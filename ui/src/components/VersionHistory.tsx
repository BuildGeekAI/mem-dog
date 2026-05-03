'use client';

import { History, CheckCircle2, Clock, FileCode, HardDrive } from 'lucide-react';
import type { VersionInfo } from '@/types';
import { formatBytes, formatDate } from '@/lib/api';

interface VersionHistoryProps {
  versions: VersionInfo[];
  currentVersion: number;
  selectedVersion: number | null;
  onVersionSelect: (version: number) => void;
}

export default function VersionHistory({
  versions,
  currentVersion,
  selectedVersion,
  onVersionSelect,
}: VersionHistoryProps) {
  return (
    <div className="glass-card overflow-hidden h-fit sticky top-6">
      {/* Header */}
      <div className="flex items-center gap-3 p-5 border-b border-white/10">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center">
          <History className="w-4 h-4 text-white" />
        </div>
        <div>
          <h3 className="font-semibold text-white">Version History</h3>
          <p className="text-xs text-white/50">{versions.length} version{versions.length !== 1 ? 's' : ''}</p>
        </div>
      </div>

      {/* Versions List */}
      <div className="p-4 space-y-3 max-h-[500px] overflow-y-auto">
        {versions.slice().reverse().map((v, index) => {
          const isSelected = selectedVersion === v.version;
          const isCurrent = v.version === currentVersion;
          
          return (
            <button
              key={v.version}
              onClick={() => onVersionSelect(v.version)}
              className={`
                w-full text-left rounded-xl p-4 transition-all duration-300 border
                ${isSelected
                  ? 'bg-primary-500/20 border-primary-500/50 shadow-lg shadow-primary-500/10'
                  : 'bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/20'
                }
              `}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              {/* Version Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={`
                    text-lg font-bold
                    ${isSelected ? 'text-primary-400' : 'text-white'}
                  `}>
                    v{v.version}
                  </span>
                  {isCurrent && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-[10px] font-bold uppercase tracking-wide border border-emerald-500/30">
                      <CheckCircle2 className="w-3 h-3" />
                      Current
                    </span>
                  )}
                </div>
                {isSelected && (
                  <div className="w-2 h-2 rounded-full bg-primary-400 animate-pulse" />
                )}
              </div>

              {/* Version Details */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <HardDrive className="w-3.5 h-3.5 text-white/40" />
                  <span className="text-white/60">{formatBytes(v.size)}</span>
                </div>
                
                <div className="flex items-center gap-2 text-sm">
                  <Clock className="w-3.5 h-3.5 text-white/40" />
                  <span className="text-white/60">{formatDate(v.timestamp)}</span>
                </div>
                
                <div className="flex items-center gap-2">
                  <FileCode className="w-3.5 h-3.5 text-white/40" />
                  <span className="
                    text-xs font-mono px-2 py-0.5 rounded-md
                    bg-white/10 text-white/60
                  ">
                    {v.content_type}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Footer hint */}
      <div className="p-4 border-t border-white/10 bg-white/5">
        <p className="text-xs text-white/40 text-center">
          Click a version to view its content
        </p>
      </div>
    </div>
  );
}

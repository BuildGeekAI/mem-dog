'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Tag, Users, Hash, FileText, HelpCircle, Mic, Film } from 'lucide-react';

/** Labels and icons for known viewpoint JSON sections */
const SECTION_META: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; color: string }> = {
  category:   { label: 'Category',   icon: Tag,          color: 'text-amber-400' },
  entities:   { label: 'Entities',   icon: Users,        color: 'text-cyan-400' },
  keywords:   { label: 'Keywords',   icon: Hash,          color: 'text-emerald-400' },
  summary:    { label: 'Summary',    icon: FileText,     color: 'text-violet-400' },
  queries:    { label: 'Queries',    icon: HelpCircle,   color: 'text-pink-400' },
  transcript: { label: 'Transcript', icon: Mic,          color: 'text-blue-400' },
  scenes:     { label: 'Scenes',     icon: Film,         color: 'text-orange-400' },
};

/** Canonical display order */
const SECTION_ORDER = ['category', 'summary', 'entities', 'keywords', 'queries', 'transcript', 'scenes'];

interface ViewpointContentProps {
  content: string;
  /** Which sections are open by default. Defaults to ['category', 'summary']. */
  defaultOpen?: string[];
}

/**
 * Renders viewpoint output_content as collapsible sections.
 * Handles both JSON (structured) and plain text (legacy) content.
 */
export default function ViewpointContent({ content, defaultOpen = ['category', 'summary'] }: ViewpointContentProps) {
  const parsed = tryParseJSON(content);

  if (!parsed) {
    // Legacy plain-text viewpoint — render as-is
    return (
      <div className="text-sm text-white/70 leading-relaxed whitespace-pre-wrap">
        {content || '(empty)'}
      </div>
    );
  }

  // Sort sections: known order first, then any extras
  const keys = Object.keys(parsed);
  const ordered = [
    ...SECTION_ORDER.filter(k => keys.includes(k)),
    ...keys.filter(k => !SECTION_ORDER.includes(k)),
  ];

  return (
    <div className="space-y-1">
      {ordered.map(key => (
        <CollapsibleSection
          key={key}
          sectionKey={key}
          value={parsed[key]}
          defaultOpen={defaultOpen.includes(key)}
        />
      ))}
    </div>
  );
}

function CollapsibleSection({
  sectionKey,
  value,
  defaultOpen,
}: {
  sectionKey: string;
  value: any;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const meta = SECTION_META[sectionKey] || {
    label: sectionKey.charAt(0).toUpperCase() + sectionKey.slice(1),
    icon: FileText,
    color: 'text-white/60',
  };
  const Icon = meta.icon;
  const Chevron = open ? ChevronDown : ChevronRight;

  return (
    <div className="rounded-lg border border-white/[0.06] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/5 transition-colors"
      >
        <Chevron className="w-3.5 h-3.5 text-white/30 flex-shrink-0" />
        <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${meta.color}`} />
        <span className="text-xs font-semibold uppercase tracking-wider text-white/50">
          {meta.label}
        </span>
        {!open && (
          <span className="text-xs text-white/30 truncate ml-auto max-w-[60%]">
            {preview(value)}
          </span>
        )}
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1">
          <SectionValue value={value} color={meta.color} />
        </div>
      )}
    </div>
  );
}

function SectionValue({ value, color }: { value: any; color: string }) {
  if (Array.isArray(value)) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {value.map((item, i) => (
          <span
            key={i}
            className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs bg-white/5 border border-white/[0.08] ${color}`}
          >
            {String(item)}
          </span>
        ))}
        {value.length === 0 && (
          <span className="text-xs text-white/30 italic">None</span>
        )}
      </div>
    );
  }

  return (
    <p className="text-sm text-white/70 leading-relaxed whitespace-pre-wrap">
      {String(value || '(empty)')}
    </p>
  );
}

function preview(value: any): string {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.slice(0, 3).join(', ') + (value.length > 3 ? '...' : '') : '(none)';
  }
  const s = String(value || '');
  return s.length > 80 ? s.slice(0, 80) + '...' : s;
}

function tryParseJSON(content: string): Record<string, any> | null {
  if (!content) return null;
  const trimmed = content.trim();
  if (!trimmed.startsWith('{')) return null;
  try {
    let obj = JSON.parse(trimmed);
    if (typeof obj === 'object' && obj !== null && !Array.isArray(obj)) {
      // Unwrap double-encoded: {"summary": "{\"category\":...}"} → parse inner
      if (Object.keys(obj).length === 1 && typeof obj.summary === 'string' && obj.summary.trim().startsWith('{')) {
        try {
          const inner = JSON.parse(obj.summary);
          if (typeof inner === 'object' && inner !== null && !Array.isArray(inner) && Object.keys(inner).length > 1) {
            obj = inner;
          }
        } catch {
          // Inner not valid JSON, keep outer
        }
      }
      return obj;
    }
  } catch {
    // Not valid JSON
  }
  return null;
}

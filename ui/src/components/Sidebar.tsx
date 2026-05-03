'use client';

import { Database, Clock, Sparkles, Zap, Settings, Layers, FlaskConical, Radio, BarChart3, BookOpen, X } from 'lucide-react';

export type TabId = 'data' | 'timeline' | 'memories' | 'ai' | 'insights' | 'telemetry' | 'testing' | 'docs' | 'settings';

interface NavSection {
  label: string;
  items: { id: TabId; label: string; icon: React.ComponentType<{ className?: string }> }[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    label: 'Knowledge',
    items: [
      { id: 'data',     label: 'Data',     icon: Database },
      { id: 'memories', label: 'Memories', icon: Layers   },
    ],
  },
  {
    label: 'AI Studio',
    items: [
      { id: 'ai',       label: 'AI Studio', icon: Sparkles },
    ],
  },
  {
    label: 'Monitor',
    items: [
      { id: 'insights',   label: 'Insights',   icon: BarChart3 },
      { id: 'telemetry',  label: 'Telemetry',  icon: Radio     },
    ],
  },
  {
    label: 'Develop',
    items: [
      { id: 'testing', label: 'Playground', icon: FlaskConical },
    ],
  },
  {
    label: 'Resources',
    items: [
      { id: 'docs', label: 'Docs', icon: BookOpen },
    ],
  },
];

interface SidebarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  isOpen?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ activeTab, onTabChange, isOpen, onClose }: SidebarProps) {
  const handleTabChange = (tab: TabId) => {
    onTabChange(tab);
    onClose?.();
  };

  const sidebarContent = (
    <aside className="flex flex-col w-56 flex-shrink-0 border-r border-white/10 bg-white/5 backdrop-blur-xl h-full overflow-y-auto">
      {/* Branding */}
      <div className="relative overflow-hidden px-4 pt-6 pb-4 border-b border-white/10">
        <div className="absolute inset-0 bg-gradient-to-b from-primary-600/10 via-accent-500/10 to-transparent" />
        <div className="relative flex items-center gap-3">
          <div className="relative flex-shrink-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 via-accent-500 to-pink-500 flex items-center justify-center shadow-lg shadow-primary-500/30">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-emerald-400 rounded-full border-2 border-slate-900 flex items-center justify-center">
              <Zap className="w-2.5 h-2.5 text-slate-900" />
            </div>
          </div>
          <div className="flex-1">
            <h1 className="text-lg font-bold tracking-tight leading-none">
              <span className="gradient-text">Mem-Dog</span>
            </h1>
            <p className="text-[10px] text-white/40 mt-0.5 leading-tight">
              Data &amp; Memory Platform
            </p>
          </div>
          {/* Close button — mobile only */}
          {onClose && (
            <button
              onClick={onClose}
              className="md:hidden p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      {/* Sectioned Navigation */}
      <nav className="flex flex-col flex-1 px-3 py-3 overflow-y-auto">
        {NAV_SECTIONS.map((section, sectionIdx) => (
          <div key={section.label}>
            {sectionIdx > 0 && <div className="mx-2 my-2 border-t border-white/[0.06]" />}
            <p className="px-3 pt-2 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-white/25">
              {section.label}
            </p>
            <div className="flex flex-col gap-0.5">
              {section.items.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => handleTabChange(id)}
                  className={`
                    flex items-center gap-2.5 w-full px-3 py-2 rounded-xl text-sm font-medium transition-all duration-300
                    ${activeTab === id
                      ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg shadow-primary-500/30'
                      : 'text-white/60 hover:text-white hover:bg-white/5'
                    }
                  `}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  {label}
                </button>
              ))}
            </div>
          </div>
        ))}

        {/* Settings pinned at the bottom of navigation */}
        <div className="mt-auto pt-2">
          <div className="mx-2 mb-2 border-t border-white/[0.06]" />
          <button
            onClick={() => handleTabChange('settings')}
            className={`
              flex items-center gap-2.5 w-full px-3 py-2 rounded-xl text-sm font-medium transition-all duration-300
              ${activeTab === 'settings'
                ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg shadow-primary-500/30'
                : 'text-white/60 hover:text-white hover:bg-white/5'
              }
            `}
          >
            <Settings className="w-4 h-4 flex-shrink-0" />
            Settings
          </button>
        </div>
      </nav>
    </aside>
  );

  return (
    <>
      {/* Desktop: normal fixed sidebar */}
      <div className="hidden md:flex h-full">
        {sidebarContent}
      </div>

      {/* Mobile: overlay sidebar */}
      {isOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          {/* Slide-in panel */}
          <div className="relative h-full w-56 animate-slide-in-left">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}

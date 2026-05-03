'use client';

import { useState } from 'react';
import {
  MessageSquare, Flower2, GitBranch, Cpu, Server,
} from 'lucide-react';
import AISearch from './AISearch';
import ModelGarden from './ModelGarden';
import SmartRoutingTab from './SmartRoutingTab';
import AgentConfigManager from './AgentConfigManager';
import ProcessingFlags from './ProcessingFlags';
import InfrastructureDashboard from './InfrastructureDashboard';

interface AIStudioProps {
  apiBaseUrl: string;
}

type StudioTab = 'search' | 'models' | 'routing' | 'agents' | 'infrastructure';

const TABS: { id: StudioTab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'search',         label: 'Search & Chat',   icon: MessageSquare },
  { id: 'models',         label: 'Models',           icon: Flower2       },
  { id: 'routing',        label: 'Routing',          icon: GitBranch     },
  { id: 'agents',         label: 'Agents',           icon: Cpu           },
  { id: 'infrastructure', label: 'Infrastructure',   icon: Server        },
];

export default function AIStudio({ apiBaseUrl }: AIStudioProps) {
  const [activeTab, setActiveTab] = useState<StudioTab>('search');

  return (
    <div className="space-y-6">
      {/* Sub-tab Navigation */}
      <div className="flex items-center gap-1.5 p-1.5 bg-white/5 rounded-xl overflow-x-auto">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center justify-center gap-2 whitespace-nowrap px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
                : 'text-white/50 hover:text-white/70 hover:bg-white/5'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'search' && <AISearch />}

      {activeTab === 'models' && (
        <div className="glass-card p-6">
          <ModelGarden />
        </div>
      )}

      {activeTab === 'routing' && <SmartRoutingTab />}

      {activeTab === 'agents' && (
        <div className="space-y-6">
          <ProcessingFlags />
          <AgentConfigManager apiBaseUrl={apiBaseUrl} />
        </div>
      )}

      {activeTab === 'infrastructure' && <InfrastructureDashboard />}
    </div>
  );
}

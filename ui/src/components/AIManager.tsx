'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Zap, Settings, X, AlertCircle, Loader2,
  CheckCircle, Flower2, Server,
} from 'lucide-react';
import AgentConfigManager from './AgentConfigManager';
import ModelGarden from './ModelGarden';
import InfrastructureDashboard from './InfrastructureDashboard';
import {
  getUserAIPreferences, updateUserAIPreferences,
  getCurrentUserId,
  getAgentProcessingDefaults,
} from '@/lib/api';

interface AIManagerProps {
  apiBaseUrl: string;
}

type AISubTab = 'processing' | 'model-garden' | 'agent-configs' | 'pods';

export function AIManager({ apiBaseUrl }: AIManagerProps) {
  const [subTab, setSubTab] = useState<AISubTab>('processing');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Agent processing flags state
  const [processingDefaults, setProcessingDefaults] = useState<Record<string, boolean>>({});
  const [processingFlags, setProcessingFlags] = useState<Record<string, boolean>>({});
  const [processingDirty, setProcessingDirty] = useState(false);
  const [processingSaving, setProcessingSaving] = useState(false);

  const userId = getCurrentUserId();

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [prefs, procDefaults] = await Promise.allSettled([
        getUserAIPreferences(userId),
        getAgentProcessingDefaults(),
      ]);

      if (procDefaults.status === 'fulfilled') {
        setProcessingDefaults(procDefaults.value);
        // Merge: user overrides on top of defaults
        const userFlags = prefs.status === 'fulfilled' ? (prefs.value?.agent_processing_flags || {}) : {};
        setProcessingFlags({ ...procDefaults.value, ...userFlags });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load AI configuration');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-primary-400 animate-spin mr-3" />
        <span className="text-white/60">Loading AI configuration...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Error */}
      {error && (
        <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <span className="text-red-300 text-sm">{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Sub-tab Navigation */}
      <div className="flex items-center gap-1.5 p-1.5 bg-white/5 rounded-xl overflow-x-auto">
        {([
          { id: 'processing', label: 'Processing Flags', icon: Zap },
          { id: 'model-garden', label: 'Model Garden', icon: Flower2 },
          { id: 'agent-configs', label: 'Agent Configs', icon: Settings },
          { id: 'pods', label: 'Pods', icon: Server },
        ] as const).map(tab => (
          <button
            key={tab.id}
            onClick={() => setSubTab(tab.id)}
            className={`flex items-center justify-center gap-2 whitespace-nowrap px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${
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

      {/* PROCESSING TAB */}
      {subTab === 'processing' && (
        <div className="glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-white/40 uppercase tracking-wider flex items-center gap-2">
                <Zap className="w-4 h-4" /> AI Processing per Data Type
              </h3>
              <p className="text-xs text-white/30 mt-1">
                Checked types get AI analysis (viewpoint + embedding). All data is recorded regardless.
              </p>
            </div>
            <button
              disabled={!processingDirty || processingSaving}
              onClick={async () => {
                setProcessingSaving(true);
                try {
                  const overrides: Record<string, boolean> = {};
                  for (const [k, v] of Object.entries(processingFlags)) {
                    if (processingDefaults[k] !== v) overrides[k] = v;
                  }
                  await updateUserAIPreferences(userId, { agent_processing_flags: overrides });
                  setProcessingDirty(false);
                } finally {
                  setProcessingSaving(false);
                }
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                processingDirty
                  ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg hover:shadow-xl'
                  : 'bg-white/5 text-white/30 cursor-not-allowed'
              }`}
            >
              {processingSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
              Save
            </button>
          </div>

          {Object.keys(processingFlags).length === 0 ? (
            <div className="text-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-white/30 mx-auto mb-2" />
              <p className="text-white/30 text-sm">Loading processing defaults…</p>
            </div>
          ) : (
            <div className="space-y-5">
              {Object.entries({
                'Media': ['video_url', 'video_stream', 'audio_url', 'audio_stream', 'image', 'image_batch'],
                'Documents': ['pdf', 'office_doc', 'markdown', 'html_doc'],
                'Structured': ['json', 'xml', 'csv', 'yaml'],
                'Code / Logs': ['code', 'log_stream', 'log_file'],
                'Communication': ['email', 'chat', 'channel_message', 'web_page', 'feed', 'calendar'],
                'Sensor': ['sensor', 'iot_sensor', 'gps', 'biometric'],
                'Spatial': ['model_3d', 'lidar', 'geospatial'],
                'Binary': ['binary_blob', 'archive', 'time_series', 'medical_imaging'],
                'Specialized': ['vehicle_telemetry', 'infrastructure', 'satellite', 'conferencing', 'scientific', 'industrial', 'financial', 'url_download'],
              } as Record<string, string[]>).map(([category, types]) => (
                <div key={category}>
                  <h4 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">{category}</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-1.5">
                    {types.filter(t => t in processingFlags).map(agentType => (
                      <label
                        key={agentType}
                        className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer group"
                      >
                        <input
                          type="checkbox"
                          checked={processingFlags[agentType] ?? false}
                          onChange={(e) => {
                            setProcessingFlags(prev => ({ ...prev, [agentType]: e.target.checked }));
                            setProcessingDirty(true);
                          }}
                          className="w-4 h-4 rounded border-white/20 bg-white/5 text-emerald-500 focus:ring-emerald-500/30 focus:ring-offset-0 cursor-pointer"
                        />
                        <span className="text-xs text-white/60 font-mono group-hover:text-white/80 transition-colors">{agentType}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {subTab === 'model-garden' && (
        <div className="glass-card p-6">
          <ModelGarden />
        </div>
      )}

      {subTab === 'agent-configs' && (
        <AgentConfigManager apiBaseUrl={apiBaseUrl} />
      )}

      {subTab === 'pods' && (
        <InfrastructureDashboard />
      )}
    </div>
  );
}

export default AIManager;

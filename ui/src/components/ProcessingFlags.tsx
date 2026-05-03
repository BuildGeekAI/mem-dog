'use client';

import { useState, useEffect, useCallback } from 'react';
import { Zap, Loader2, CheckCircle } from 'lucide-react';
import {
  getUserAIPreferences, updateUserAIPreferences,
  getCurrentUserId, getAgentProcessingDefaults,
} from '@/lib/api';

const CATEGORIES: Record<string, string[]> = {
  'Media': ['video_url', 'video_stream', 'audio_url', 'audio_stream', 'image', 'image_batch'],
  'Documents': ['pdf', 'office_doc', 'markdown', 'html_doc'],
  'Structured': ['json', 'xml', 'csv', 'yaml'],
  'Code / Logs': ['code', 'log_stream', 'log_file'],
  'Communication': ['email', 'chat', 'channel_message', 'web_page', 'feed', 'calendar'],
  'Sensor': ['sensor', 'iot_sensor', 'gps', 'biometric'],
  'Spatial': ['model_3d', 'lidar', 'geospatial'],
  'Binary': ['binary_blob', 'archive', 'time_series', 'medical_imaging'],
  'Specialized': ['vehicle_telemetry', 'infrastructure', 'satellite', 'conferencing', 'scientific', 'industrial', 'financial', 'url_download'],
};

export default function ProcessingFlags() {
  const [loading, setLoading] = useState(true);
  const [processingDefaults, setProcessingDefaults] = useState<Record<string, boolean>>({});
  const [processingFlags, setProcessingFlags] = useState<Record<string, boolean>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  const userId = getCurrentUserId();

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const [prefs, procDefaults] = await Promise.allSettled([
        getUserAIPreferences(userId),
        getAgentProcessingDefaults(),
      ]);
      if (procDefaults.status === 'fulfilled') {
        setProcessingDefaults(procDefaults.value);
        const userFlags = prefs.status === 'fulfilled' ? (prefs.value?.agent_processing_flags || {}) : {};
        setProcessingFlags({ ...procDefaults.value, ...userFlags });
      }
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const overrides: Record<string, boolean> = {};
      for (const [k, v] of Object.entries(processingFlags)) {
        if (processingDefaults[k] !== v) overrides[k] = v;
      }
      await updateUserAIPreferences(userId, { agent_processing_flags: overrides });
      setDirty(false);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 text-primary-400 animate-spin mr-3" />
        <span className="text-white/60">Loading processing flags...</span>
      </div>
    );
  }

  return (
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
          disabled={!dirty || saving}
          onClick={handleSave}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            dirty
              ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg hover:shadow-xl'
              : 'bg-white/5 text-white/30 cursor-not-allowed'
          }`}
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
          Save
        </button>
      </div>

      {Object.keys(processingFlags).length === 0 ? (
        <div className="text-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-white/30 mx-auto mb-2" />
          <p className="text-white/30 text-sm">Loading processing defaults...</p>
        </div>
      ) : (
        <div className="space-y-5">
          {Object.entries(CATEGORIES).map(([category, types]) => (
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
                        setDirty(true);
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
  );
}

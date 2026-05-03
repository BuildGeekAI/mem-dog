'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Upload, FileText, File, Check, AlertCircle, Loader2, Sparkles,
  Tag, ChevronDown, ChevronUp, Layers, Play, Square, Activity,
  Mic, MicOff, Camera, AudioLines, Video, Link2, Download, ExternalLink,
} from 'lucide-react';
import { createData, listMemories, createMemory, updateMemory, getDeviceId, getDeviceInfo, getCurrentUserId } from '@/lib/api';
import { useProject } from '@/lib/project-context';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
import CameraCapture from '@/components/CameraCapture';
import VoiceRecorder from '@/components/VoiceRecorder';
import VideoRecorder from '@/components/VideoRecorder';
import type { MemoryResponse, MemoryCreate } from '@/types';

interface UploadFormProps {
  onSuccess: () => void;
}

/**
 * Upload form for creating new data entries.
 *
 * The name / description / tags / memories section is shown expanded at the
 * top by default, with the user's timeline and active session pre-selected.
 * The backend **always** auto-associates uploads with the user's default
 * timeline and all active session memories, but the UI pre-checks them so
 * the user can see what they're uploading into.  Additional memories can be
 * toggled on in the same picker.
 */
export default function UploadForm({ onSuccess }: UploadFormProps) {
  const { selectedProjectId } = useProject();
  const [mode, setMode] = useState<'text' | 'file' | 'url' | 'camera' | 'voice' | 'video'>('text');
  const [textContent, setTextContent] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [capturedPhoto, setCapturedPhoto] = useState<File | null>(null);
  const [recordedAudio, setRecordedAudio] = useState<File | null>(null);
  const [recordedVideo, setRecordedVideo] = useState<File | null>(null);
  const [urlInput, setUrlInput] = useState('');
  const [urlMimeType, setUrlMimeType] = useState('');
  const [urlDownloadNow, setUrlDownloadNow] = useState(true);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [tagsInput, setTagsInput] = useState('');
  const [showDetails, setShowDetails] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [filePreviewUrl, setFilePreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Memory state – timeline + active sessions are pre-selected; user can
  // add/remove additional memories.  The pre-selected IDs are tracked in
  // `autoMemoryIds` so the UI can mark them as "(auto)".
  const [memories, setMemories] = useState<MemoryResponse[]>([]);
  const [selectedMemoryIds, setSelectedMemoryIds] = useState<Set<string>>(new Set());
  const [autoMemoryIds, setAutoMemoryIds] = useState<Set<string>>(new Set());
  const [memoriesLoading, setMemoriesLoading] = useState(true);

  // Dictation (Web Speech API)
  const {
    isSupported: speechSupported,
    isListening,
    interimTranscript,
    error: speechError,
    startListening,
    stopListening,
  } = useSpeechRecognition({
    onResult: (transcript) => {
      setTextContent((prev) => (prev ? prev + ' ' + transcript : transcript));
    },
  });

  // Session bar state
  const [activeSession, setActiveSession] = useState<MemoryResponse | null>(null);
  const [sessionCreating, setSessionCreating] = useState(false);
  const [sessionEnding, setSessionEnding] = useState(false);
  const [showNewSessionInput, setShowNewSessionInput] = useState(false);
  const [newSessionName, setNewSessionName] = useState('');

  // Fetch all memories, derive active session, and pre-select timeline + sessions
  const fetchMemories = useCallback(async () => {
    try {
      setMemoriesLoading(true);
      const response = await listMemories({ userId: getCurrentUserId(), projectId: selectedProjectId || undefined, limit: 200 });
      setMemories(response.items);

      // Find the most recent active session
      const activeSessions = response.items
        .filter(m => m.memory_type === 'session' && m.active)
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

      const currentSession = activeSessions[0] ?? null;
      setActiveSession(currentSession);

      // Pre-select timeline + active sessions so the user sees them checked
      const autoIds = new Set<string>();
      const timelineMemory = response.items.find(m => m.memory_type === 'timeline');
      if (timelineMemory) autoIds.add(timelineMemory.memory_id);
      for (const sess of activeSessions) {
        autoIds.add(sess.memory_id);
      }
      setAutoMemoryIds(autoIds);
      setSelectedMemoryIds(new Set(autoIds));
    } catch {
      // Non-critical
    } finally {
      setMemoriesLoading(false);
    }
  }, []);

  useEffect(() => { fetchMemories(); }, [fetchMemories]);

  // Generate a default name with a given prefix and a UUID suffix
  const generateDefaultName = (prefix: string) =>
    `${prefix}_${crypto.randomUUID()}`;

  // Auto-populate name when the mode switches to text (including on initial mount)
  useEffect(() => {
    if (mode === 'text') {
      setName(generateDefaultName('text'));
    }
  }, [mode]);

  // Auto-populate name when a file is selected via the file picker / drag-and-drop
  useEffect(() => {
    if (!file) return;
    let prefix = 'file';
    if (file.type.startsWith('image/')) prefix = 'image';
    else if (file.type.startsWith('video/')) prefix = 'video';
    else if (file.type.startsWith('audio/')) prefix = 'audio';
    setName(generateDefaultName(prefix));
  }, [file]);

  // Auto-populate name when a photo is taken with the camera
  useEffect(() => {
    if (!capturedPhoto) return;
    setName(generateDefaultName('photo'));
  }, [capturedPhoto]);

  // Auto-populate name when an audio clip is recorded
  useEffect(() => {
    if (!recordedAudio) return;
    setName(generateDefaultName('audio'));
  }, [recordedAudio]);

  // Auto-populate name when a video clip is recorded
  useEffect(() => {
    if (!recordedVideo) return;
    setName(generateDefaultName('video'));
  }, [recordedVideo]);

  // Create an object URL for the selected file preview and clean it up when it changes
  useEffect(() => {
    if (!file) {
      setFilePreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setFilePreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Start a new session
  const handleStartSession = async () => {
    try {
      setSessionCreating(true);
      setError(null);

      // End current active session first
      if (activeSession) {
        await updateMemory(activeSession.memory_id, { active: false });
      }

      const sessionName = newSessionName.trim() || `Session ${new Date().toLocaleString()}`;
      const payload: MemoryCreate = {
        memory_type: 'session',
        name: sessionName,
        user_id: getCurrentUserId(),
        device_id: getDeviceId(),
        device_info: getDeviceInfo(),
      };
      await createMemory(payload);

      setNewSessionName('');
      setShowNewSessionInput(false);
      await fetchMemories();
    } catch (err: any) {
      setError(err.message || 'Failed to start session');
    } finally {
      setSessionCreating(false);
    }
  };

  // End the active session
  const handleEndSession = async () => {
    if (!activeSession) return;
    try {
      setSessionEnding(true);
      setError(null);
      await updateMemory(activeSession.memory_id, { active: false });
      await fetchMemories();
    } catch (err: any) {
      setError(err.message || 'Failed to end session');
    } finally {
      setSessionEnding(false);
    }
  };

  const toggleMemory = (memoryId: string) => {
    setSelectedMemoryIds(prev => {
      const next = new Set(prev);
      if (next.has(memoryId)) {
        next.delete(memoryId);
      } else {
        next.add(memoryId);
      }
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      const userTags = tagsInput.trim()
        ? tagsInput.split(',').map(t => t.trim()).filter(Boolean)
        : [];

      const userId = getCurrentUserId();
      const userIdTag = `user_id:${userId}`;
      if (!userTags.includes(userIdTag)) {
        userTags.push(userIdTag);
      }

      // Resolve effective MIME type based on upload mode
      let effectiveMime: string | undefined;
      if (mode === 'text') effectiveMime = 'application/json';
      else if (mode === 'file' && file) effectiveMime = file.type || undefined;
      else if (mode === 'url') effectiveMime = urlMimeType.trim() || undefined;
      else if (mode === 'camera' && capturedPhoto) effectiveMime = capturedPhoto.type || undefined;
      else if (mode === 'voice' && recordedAudio) effectiveMime = recordedAudio.type || undefined;
      else if (mode === 'video' && recordedVideo) effectiveMime = recordedVideo.type || undefined;

      if (effectiveMime) {
        const mimeTag = `mime_type:${effectiveMime.replace('/', '_')}`;
        if (!userTags.includes(mimeTag)) {
          userTags.push(mimeTag);
        }
      }

      const tags = userTags.length > 0 ? userTags : undefined;

      // Only pass additional memory IDs. The backend always auto-includes
      // the user's timeline + active sessions on top of whatever we send.
      const memoryIds = selectedMemoryIds.size > 0
        ? Array.from(selectedMemoryIds)
        : undefined;

      const options = {
        name: name.trim() || undefined,
        description: description.trim() || undefined,
        tags,
        memoryIds,
        forwardToWebhook: true,
      };

      const upload = (c: string | File | null, o?: typeof options & { url?: string; mimeType?: string; isDownloaded?: boolean }) => createData(c, o);

      if (mode === 'text') {
        if (!textContent.trim()) {
          setError('Please enter some text content');
          return;
        }
        await upload(textContent, { ...options, mimeType: effectiveMime });
      } else if (mode === 'url') {
        if (!urlInput.trim()) {
          setError('Please enter a URL');
          return;
        }
        await upload(null, {
          ...options,
          url: urlInput.trim(),
          mimeType: urlMimeType.trim() || undefined,
          isDownloaded: !urlDownloadNow ? false : undefined,
        });
      } else if (mode === 'file') {
        if (!file) {
          setError('Please select a file');
          return;
        }
        await upload(file, { ...options, mimeType: effectiveMime });
      } else if (mode === 'camera') {
        if (!capturedPhoto) {
          setError('Please take a photo first');
          return;
        }
        await upload(capturedPhoto, { ...options, mimeType: effectiveMime });
      } else if (mode === 'voice') {
        if (!recordedAudio) {
          setError('Please record audio first');
          return;
        }
        await upload(recordedAudio, { ...options, mimeType: effectiveMime });
      } else if (mode === 'video') {
        if (!recordedVideo) {
          setError('Please record a video first');
          return;
        }
        await upload(recordedVideo, { ...options, mimeType: effectiveMime });
      }

      setSuccess('Data uploaded successfully!');
      setTextContent('');
      setUrlInput('');
      setUrlMimeType('');
      setUrlDownloadNow(true);
      setFile(null);
      setFilePreviewUrl(null);
      setCapturedPhoto(null);
      setRecordedAudio(null);
      setRecordedVideo(null);
      setName('');
      setDescription('');
      setTagsInput('');
      onSuccess();

      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to upload data');
    } finally {
      setLoading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      setFile(droppedFile);
      setMode('file');
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Group non-session memories by type for the picker
  const memoryGroups: Record<string, MemoryResponse[]> = {};
  for (const mem of memories) {
    const group = mem.memory_type;
    if (!memoryGroups[group]) memoryGroups[group] = [];
    memoryGroups[group].push(mem);
  }

  const typeOrder = ['timeline', 'session', 'conversation', 'user', 'organizational', 'factual', 'episodic', 'semantic'];
  const sortedGroupKeys = Object.keys(memoryGroups).sort((a, b) => {
    const ai = typeOrder.indexOf(a);
    const bi = typeOrder.indexOf(b);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

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

  return (
    <div className="space-y-4">
      {/* ── Session Bar ─────────────────────────────────────────────────── */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${
              activeSession
                ? 'bg-emerald-500/20'
                : 'bg-white/5'
            }`}>
              {activeSession
                ? <Activity className="w-4.5 h-4.5 text-emerald-400" />
                : <Layers className="w-4.5 h-4.5 text-white/30" />
              }
            </div>

            {activeSession ? (
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-white">{activeSession.name}</span>
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 uppercase tracking-wider">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    Active
                  </span>
                </div>
                <p className="text-[11px] text-white/35 mt-0.5">
                  Started {timeAgo(activeSession.created_at)} &middot; {activeSession.data_count} items &middot; Uploads go here + audit
                </p>
              </div>
            ) : (
              <div>
                <span className="text-sm font-medium text-white/50">No active session</span>
                <p className="text-[11px] text-white/25 mt-0.5">
                  Uploads go to your audit memory. Start a session to also group them.
                </p>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            {activeSession ? (
              <button
                type="button"
                onClick={handleEndSession}
                disabled={sessionEnding}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-all disabled:opacity-50"
              >
                {sessionEnding ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Square className="w-3.5 h-3.5" />
                )}
                End Session
              </button>
            ) : showNewSessionInput ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={newSessionName}
                  onChange={(e) => setNewSessionName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleStartSession(); if (e.key === 'Escape') setShowNewSessionInput(false); }}
                  placeholder="Session name (optional)"
                  autoFocus
                  className="w-48 bg-black/30 text-white border border-white/10 rounded-lg px-3 py-1.5 text-xs placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                />
                <button
                  type="button"
                  onClick={handleStartSession}
                  disabled={sessionCreating}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25 transition-all disabled:opacity-50"
                >
                  {sessionCreating ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Check className="w-3.5 h-3.5" />
                  )}
                  Start
                </button>
                <button
                  type="button"
                  onClick={() => { setShowNewSessionInput(false); setNewSessionName(''); }}
                  className="px-2 py-1.5 rounded-lg text-xs text-white/40 hover:text-white/60 hover:bg-white/5 transition-all"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowNewSessionInput(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-emerald-500 to-emerald-600 text-white hover:shadow-lg hover:shadow-emerald-500/25 transition-all"
              >
                <Play className="w-3.5 h-3.5" />
                Start Session
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Upload Card ─────────────────────────────────────────────────── */}
      <div className="glass-card p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
            <Upload className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white">Upload New Data</h2>
            <p className="text-sm text-white/50">Store text, files, photos or voice recordings</p>
          </div>
        </div>

        {/* Alerts */}
        {error && (
          <div className="alert alert-error flex items-center gap-3 mb-6">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="alert alert-success flex items-center gap-3 mb-6">
            <Check className="w-5 h-5 flex-shrink-0" />
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* ── Metadata & Memories (shown first, expanded by default) ───── */}
          <div className="mb-6">
            <button
              type="button"
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-2 text-sm text-white/50 hover:text-white/70 transition-colors mb-3"
            >
              {showDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              <span>Name, description, tags & memories</span>
              {(name || description || tagsInput || selectedMemoryIds.size > autoMemoryIds.size) && (
                <span className="w-2 h-2 rounded-full bg-primary-400" />
              )}
            </button>

            {showDetails && (
              <div className="space-y-4 p-4 rounded-xl bg-white/[0.03] border border-white/5">
                {/* Name */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium text-white/70">Name</label>
                    {name && (file || capturedPhoto || recordedAudio) && (
                      <span className="text-[10px] text-white/30 italic">auto-generated · you can edit</span>
                    )}
                  </div>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Give your data a name"
                    disabled={loading}
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-white/70 mb-2">Description</label>
                  <input
                    type="text"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Brief description of the data"
                    disabled={loading}
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                  />
                </div>

                {/* Tags */}
                <div>
                  <label className="block text-sm font-medium text-white/70 mb-2">
                    <span className="flex items-center gap-1.5">
                      <Tag className="w-3.5 h-3.5" />
                      Tags
                    </span>
                  </label>
                  <input
                    type="text"
                    value={tagsInput}
                    onChange={(e) => setTagsInput(e.target.value)}
                    placeholder="Comma-separated tags, e.g. notes, important, project-x"
                    disabled={loading}
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                  />
                  {tagsInput && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {tagsInput.split(',').map(t => t.trim()).filter(Boolean).map((tag, i) => (
                        <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-primary-500/10 text-primary-300 border border-primary-500/20 text-xs">
                          <Tag className="w-2.5 h-2.5" />
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Memory Picker */}
                <div>
                  <label className="block text-sm font-medium text-white/70 mb-2">
                    <span className="flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5" />
                      Associate with Memories
                    </span>
                  </label>

                  {memoriesLoading ? (
                    <div className="flex items-center gap-2 py-3 text-white/40 text-sm">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Loading memories...
                    </div>
                  ) : memories.length === 0 ? (
                    <p className="text-white/30 text-sm py-2">
                      No memories found. Start a session above or create a memory in the Memories tab.
                    </p>
                  ) : (
                    <div className="max-h-56 overflow-y-auto rounded-xl border border-white/10 bg-black/20">
                      {sortedGroupKeys.map(groupType => (
                        <div key={groupType}>
                          <div className="sticky top-0 px-3 py-1.5 bg-white/5 border-b border-white/5 backdrop-blur-sm z-10">
                            <span className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">{groupType === 'timeline' ? 'audit' : groupType}</span>
                          </div>
                          {memoryGroups[groupType].map(mem => {
                            const isSelected = selectedMemoryIds.has(mem.memory_id);
                            const isAuto = autoMemoryIds.has(mem.memory_id);
                            return (
                              <label
                                key={mem.memory_id}
                                className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors ${
                                  isSelected ? 'bg-primary-500/10' : 'hover:bg-white/5'
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => toggleMemory(mem.memory_id)}
                                  disabled={loading}
                                  className="rounded border-white/20 bg-white/5 text-primary-500 focus:ring-primary-500/25 flex-shrink-0"
                                />
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm text-white/80 truncate">
                                      {mem.name || mem.memory_id.substring(0, 20)}
                                    </span>
                                    {isAuto && (
                                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold bg-blue-500/15 text-blue-400 border border-blue-500/20">
                                        AUTO
                                      </span>
                                    )}
                                    {mem.active && (
                                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                                        ACTIVE
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-2 text-[10px] text-white/30">
                                    <span>{mem.user_id}</span>
                                    <span className="text-white/10">|</span>
                                    <span>{mem.data_count} items</span>
                                  </div>
                                </div>
                              </label>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  )}
                  <p className="text-white/25 text-xs mt-1.5">
                    Audit and active session are pre-selected and always included by the backend. You can select additional memories above.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* ── Mode Toggle ────────────────────────────────────────────────── */}
          <div className="grid grid-cols-6 gap-1.5 p-1 bg-white/5 rounded-xl mb-6">
            {([
              { id: 'text'   as const, label: 'Text',   icon: FileText   },
              { id: 'file'   as const, label: 'File',   icon: File       },
              { id: 'url'    as const, label: 'URL',    icon: Link2      },
              { id: 'camera' as const, label: 'Camera', icon: Camera     },
              { id: 'voice'  as const, label: 'Voice',  icon: AudioLines },
              { id: 'video'  as const, label: 'Video',  icon: Video      },
            ]).map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setMode(id)}
                className={`
                  flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg font-medium text-sm transition-all duration-300
                  ${mode === id
                    ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
                    : 'text-white/60 hover:text-white hover:bg-white/5'
                  }
                `}
              >
                <Icon className="w-4 h-4" />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </div>

          {/* ── Content Input ──────────────────────────────────────────────── */}
          {mode === 'url' && (
            <div className="mb-6 space-y-4">
              {/* URL field */}
              <div>
                <label className="block text-sm font-medium text-white/70 mb-2">
                  <span className="flex items-center gap-1.5">
                    <Link2 className="w-3.5 h-3.5" />
                    Remote URL
                  </span>
                </label>
                <input
                  type="url"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  placeholder="https://example.com/file.pdf"
                  disabled={loading}
                  className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                />
              </div>

              {/* MIME type override */}
              <div>
                <label className="block text-sm font-medium text-white/70 mb-2">
                  MIME type <span className="text-white/30 font-normal">(optional — auto-detected if blank)</span>
                </label>
                <input
                  type="text"
                  value={urlMimeType}
                  onChange={(e) => setUrlMimeType(e.target.value)}
                  placeholder="e.g. application/pdf, image/png"
                  disabled={loading}
                  className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                />
              </div>

              {/* Download mode toggle */}
              <div className="flex items-start gap-3 p-4 rounded-xl bg-white/[0.03] border border-white/5">
                <div className="flex flex-col gap-2 w-full">
                  <label className="text-sm font-medium text-white/70">How should the URL be stored?</label>
                  <div className="flex flex-col gap-2">
                    <label className="flex items-center gap-2.5 cursor-pointer">
                      <input
                        type="radio"
                        name="urlMode"
                        checked={urlDownloadNow}
                        onChange={() => setUrlDownloadNow(true)}
                        disabled={loading}
                        className="text-primary-500 focus:ring-primary-500/25"
                      />
                      <div className="flex items-center gap-1.5">
                        <Download className="w-3.5 h-3.5 text-primary-400" />
                        <span className="text-sm text-white/80">Download & store content now</span>
                      </div>
                    </label>
                    <label className="flex items-center gap-2.5 cursor-pointer">
                      <input
                        type="radio"
                        name="urlMode"
                        checked={!urlDownloadNow}
                        onChange={() => setUrlDownloadNow(false)}
                        disabled={loading}
                        className="text-primary-500 focus:ring-primary-500/25"
                      />
                      <div className="flex items-center gap-1.5">
                        <ExternalLink className="w-3.5 h-3.5 text-amber-400" />
                        <span className="text-sm text-white/80">Store as reference only <span className="text-white/40">(URL is saved, content is not fetched)</span></span>
                      </div>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}

          {mode === 'text' && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-white/70">
                  Content <span className="text-white/40">(JSON, plain text, etc.)</span>
                </label>

                {/* Dictation button */}
                {speechSupported && (
                  <div className="flex items-center gap-2">
                    {isListening && (
                      <span className="flex items-center gap-1.5 text-xs text-accent-400 animate-pulse">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                        Listening...
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={isListening ? stopListening : startListening}
                      disabled={loading}
                      title={isListening ? 'Stop dictation' : 'Start dictation'}
                      className={`
                        flex items-center justify-center w-9 h-9 rounded-xl transition-all duration-300
                        ${isListening
                          ? 'bg-red-500/20 text-red-400 border border-red-500/30 shadow-lg shadow-red-500/10 animate-pulse'
                          : 'bg-white/5 text-white/50 border border-white/10 hover:bg-white/10 hover:text-white/80'
                        }
                        disabled:opacity-40 disabled:cursor-not-allowed
                      `}
                    >
                      {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                    </button>
                  </div>
                )}
              </div>

              {(speechError) && (
                <div className="flex items-center gap-2 text-xs text-red-400 mb-2">
                  <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                  <span>{speechError}</span>
                </div>
              )}

              <div className="relative">
                <textarea
                  className="textarea-modern"
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  placeholder={isListening ? 'Speak now...' : '{"example": "Enter your data here", "type": "json"}'}
                  disabled={loading}
                />
                {/* Interim transcript ghost overlay */}
                {isListening && interimTranscript && (
                  <div className="absolute bottom-3 left-4 right-4 pointer-events-none">
                    <span className="text-sm text-white/25 italic">{interimTranscript}</span>
                  </div>
                )}
              </div>

              {!speechSupported && (
                <p className="text-white/25 text-xs mt-1.5">
                  Dictation requires Chrome or Edge. Use the textarea to type your content.
                </p>
              )}
            </div>
          )}

          {mode === 'file' && (
            <div className="mb-6">
              <label className="block text-sm font-medium text-white/70 mb-2">
                Select or Drop File
              </label>
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`
                  relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-300
                  ${isDragging
                    ? 'border-primary-500 bg-primary-500/10'
                    : file
                      ? 'border-emerald-500/50 bg-emerald-500/5'
                      : 'border-white/20 hover:border-white/40 hover:bg-white/5'
                  }
                `}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  disabled={loading}
                />

                {file ? (
                  <div className="flex flex-col items-center gap-3 w-full" onClick={(e) => e.stopPropagation()}>
                    {/* Media preview */}
                    {filePreviewUrl && file.type.startsWith('image/') && (
                      <img
                        src={filePreviewUrl}
                        alt="Preview"
                        className="max-h-48 max-w-full rounded-lg object-contain shadow-lg"
                      />
                    )}
                    {filePreviewUrl && file.type.startsWith('video/') && (
                      <video
                        src={filePreviewUrl}
                        controls
                        className="max-h-48 max-w-full rounded-lg shadow-lg"
                        onClick={(e) => e.stopPropagation()}
                      />
                    )}
                    {filePreviewUrl && file.type.startsWith('audio/') && (
                      <div className="w-full px-2">
                        <audio
                          src={filePreviewUrl}
                          controls
                          className="w-full"
                          onClick={(e) => e.stopPropagation()}
                        />
                      </div>
                    )}
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                        <Check className="w-5 h-5 text-emerald-400" />
                      </div>
                      <div className="text-left">
                        <p className="font-medium text-white text-sm">{file.name}</p>
                        <p className="text-xs text-white/50 mt-0.5">{formatFileSize(file.size)}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setFile(null); }}
                      className="text-sm text-red-400 hover:text-red-300"
                    >
                      Remove file
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-14 h-14 rounded-xl bg-white/10 flex items-center justify-center">
                      <Upload className="w-7 h-7 text-white/50" />
                    </div>
                    <div>
                      <p className="font-medium text-white/70">
                        Drop your file here, or <span className="text-primary-400">browse</span>
                      </p>
                      <p className="text-sm text-white/40 mt-1">Supports all file types</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Camera ────────────────────────────────────────────────────── */}
          {mode === 'camera' && (
            <div className="mb-6">
              <label className="block text-sm font-medium text-white/70 mb-2">
                <span className="flex items-center gap-1.5">
                  <Camera className="w-3.5 h-3.5" />
                  Take a Photo
                </span>
              </label>
              <CameraCapture
                capturedFile={capturedPhoto}
                onCapture={setCapturedPhoto}
              />
            </div>
          )}

          {/* ── Voice ─────────────────────────────────────────────────────── */}
          {mode === 'voice' && (
            <div className="mb-6">
              <label className="block text-sm font-medium text-white/70 mb-2">
                <span className="flex items-center gap-1.5">
                  <Mic className="w-3.5 h-3.5" />
                  Record Voice
                </span>
              </label>
              <VoiceRecorder
                recordedFile={recordedAudio}
                onRecording={setRecordedAudio}
              />
            </div>
          )}

          {/* ── Video Record ───────────────────────────────────────────────── */}
          {mode === 'video' && (
            <div className="mb-6">
              <label className="block text-sm font-medium text-white/70 mb-2">
                <span className="flex items-center gap-1.5">
                  <Video className="w-3.5 h-3.5" />
                  Record Video
                </span>
              </label>
              <VideoRecorder
                recordedFile={recordedVideo}
                onRecording={setRecordedVideo}
              />
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-premium w-full flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5" />
                <span>Upload Data</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

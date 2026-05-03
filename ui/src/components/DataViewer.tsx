'use client';

import { useEffect, useState, useMemo } from 'react';
import { FileText, Edit3, Save, X, Trash2, Download, Upload, AlertCircle, Check, Loader2, Eye, Lock, FileQuestion, Code, FileImage, FileType, Shield, ChevronDown, ChevronUp, Tag, Plus, Info, Pencil, Link, Copy, Film, Music } from 'lucide-react';
import type { DataMetadata, AccessControl as AccessControlType } from '@/types';
import {
  getDataAsText,
  updateData,
  deleteData,
  getData,
  updateTags,
  addTags,
  removeTags,
  updateInfo,
  normalizeAddress,
} from '@/lib/api';
import { AccessControl } from './AccessControl';

interface DataViewerProps {
  dataId: string;
  version: number | null;
  metadata: DataMetadata;
  onUpdate: () => void;
  onDelete: () => void;
}

// Content type detection utilities
const getContentCategory = (contentType: string | undefined): 'json' | 'markdown' | 'code' | 'image' | 'video' | 'audio' | 'text' | 'binary' => {
  if (!contentType) return 'binary';
  
  if (contentType === 'application/json') return 'json';
  if (contentType === 'text/markdown' || contentType === 'text/x-markdown') return 'markdown';
  if (contentType.startsWith('image/')) return 'image';
  if (contentType.startsWith('video/')) return 'video';
  if (contentType.startsWith('audio/')) return 'audio';
  if (contentType.startsWith('text/')) return 'text';
  
  // Code file detection
  const codeTypes = [
    'application/javascript',
    'application/typescript',
    'application/x-python',
    'application/xml',
    'application/x-yaml',
    'application/x-sh',
  ];
  if (codeTypes.includes(contentType)) return 'code';
  
  return 'binary';
};

// JSON syntax highlighter
const highlightJSON = (json: string): string => {
  return json
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, (match) => {
      let cls = 'text-amber-400'; // number
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          cls = 'text-blue-400'; // key
        } else {
          cls = 'text-green-400'; // string
        }
      } else if (/true|false/.test(match)) {
        cls = 'text-purple-400'; // boolean
      } else if (/null/.test(match)) {
        cls = 'text-red-400'; // null
      }
      return `<span class="${cls}">${match}</span>`;
    });
};

// Simple markdown to HTML converter
const renderMarkdown = (markdown: string): string => {
  let html = markdown
    // Escape HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Headers
    .replace(/^### (.*$)/gm, '<h3 class="text-lg font-semibold text-white mt-4 mb-2">$1</h3>')
    .replace(/^## (.*$)/gm, '<h2 class="text-xl font-semibold text-white mt-6 mb-3">$1</h2>')
    .replace(/^# (.*$)/gm, '<h1 class="text-2xl font-bold text-white mt-6 mb-4">$1</h1>')
    // Bold
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-white">$1</strong>')
    // Italic
    .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>')
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="bg-black/30 rounded-lg p-4 my-4 overflow-x-auto"><code class="text-sm font-mono text-green-400">$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="bg-white/10 px-1.5 py-0.5 rounded text-sm font-mono text-primary-400">$1</code>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-primary-400 hover:underline" target="_blank" rel="noopener">$1</a>')
    // Unordered lists
    .replace(/^\s*[-*]\s+(.*)$/gm, '<li class="ml-4 list-disc">$1</li>')
    // Ordered lists
    .replace(/^\s*\d+\.\s+(.*)$/gm, '<li class="ml-4 list-decimal">$1</li>')
    // Blockquotes
    .replace(/^>\s*(.*$)/gm, '<blockquote class="border-l-4 border-primary-500 pl-4 italic text-white/70 my-2">$1</blockquote>')
    // Horizontal rule
    .replace(/^---$/gm, '<hr class="border-white/20 my-6" />')
    // Line breaks / paragraphs
    .replace(/\n\n/g, '</p><p class="mb-4">')
    .replace(/\n/g, '<br />');
  
  return `<div class="markdown-preview text-white/80 leading-relaxed"><p class="mb-4">${html}</p></div>`;
};

export default function DataViewer({
  dataId,
  version,
  metadata,
  onUpdate,
  onDelete,
}: DataViewerProps) {
  const [content, setContent] = useState<string>('');
  const [editedContent, setEditedContent] = useState<string>('');
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isBinary, setIsBinary] = useState(false);
  const [binaryUrl, setBinaryUrl] = useState<string | null>(null);
  const [showPreview, setShowPreview] = useState(true);
  const [showAccessControl, setShowAccessControl] = useState(false);
  const [currentAccess, setCurrentAccess] = useState<AccessControlType>(metadata.access || null);
  const [showTags, setShowTags] = useState(false);
  const [currentTags, setCurrentTags] = useState<string[]>(metadata.tags || []);
  const [newTag, setNewTag] = useState('');
  const [savingTags, setSavingTags] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const [currentName, setCurrentName] = useState<string>(metadata.name || '');
  const [currentDescription, setCurrentDescription] = useState<string>(metadata.description || '');
  const [editingInfo, setEditingInfo] = useState(false);
  const [savingInfo, setSavingInfo] = useState(false);

  // API base URL for AccessControl component
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || '/api';

  const isCurrentVersion = version === metadata.current_version;
  const currentVersionInfo = metadata.versions.find((v) => v.version === version);
  const contentType = currentVersionInfo?.content_type;
  const contentCategory = getContentCategory(contentType);
  const isTextContent = contentCategory !== 'binary' && contentCategory !== 'image' && contentCategory !== 'video' && contentCategory !== 'audio';
  const isImageContent = contentCategory === 'image';
  const isVideoContent = contentCategory === 'video';
  const isAudioContent = contentCategory === 'audio';
  const hasPreview = contentCategory === 'json' || contentCategory === 'markdown' || contentCategory === 'image';

  // Direct streaming URL for video/audio — avoids loading the whole file into memory as a blob
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
  const streamingUrl = version != null ? `${API_BASE}/api/v1/data/${dataId}?version=${version}` : `${API_BASE}/api/v1/data/${dataId}`;

  useEffect(() => {
    loadContent();
    return () => {
      if (binaryUrl) {
        URL.revokeObjectURL(binaryUrl);
      }
    };
  }, [dataId, version]);

  const loadContent = async () => {
    if (!version) return;

    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      if (isTextContent) {
        const text = await getDataAsText(dataId, version);
        setContent(text);
        setEditedContent(text);
        setIsBinary(false);
      } else if (isVideoContent || isAudioContent) {
        // Video and audio use the streaming URL directly — no blob loading needed.
        // This prevents the browser from buffering the entire file into memory.
        setIsBinary(false);
      } else {
        // Load binary/image content as blob
        const blob = await getData(dataId, version);
        const url = URL.createObjectURL(blob);
        setBinaryUrl(url);
        setIsBinary(!isImageContent);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load content');
    } finally {
      setLoading(false);
    }
  };

  // Memoized formatted content for preview
  const formattedContent = useMemo(() => {
    if (!content) return '';
    
    if (contentCategory === 'json') {
      try {
        const parsed = JSON.parse(content);
        const formatted = JSON.stringify(parsed, null, 2);
        return highlightJSON(formatted);
      } catch {
        return content;
      }
    }
    
    if (contentCategory === 'markdown') {
      return renderMarkdown(content);
    }
    
    return content;
  }, [content, contentCategory]);

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);
      await updateData(dataId, editedContent);
      setSuccess('Data updated successfully!');
      setIsEditing(false);
      onUpdate();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to update data');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this data and all its versions?')) {
      return;
    }

    try {
      setError(null);
      await deleteData(dataId);
      onDelete();
    } catch (err: any) {
      setError(err.message || 'Failed to delete data');
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setError(null);
      setSuccess(null);
      await updateData(dataId, file);
      setSuccess('File updated successfully!');
      onUpdate();
      loadContent();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to update file');
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedContent(content);
  };

  const handleAccessUpdate = (newAccess: AccessControlType) => {
    setCurrentAccess(newAccess);
    // Trigger parent update to refresh metadata
    onUpdate();
  };

  const handleAddTag = async () => {
    const trimmedTag = newTag.trim().toLowerCase();
    if (!trimmedTag || currentTags.includes(trimmedTag)) {
      setNewTag('');
      return;
    }
    
    try {
      setSavingTags(true);
      await addTags(dataId, [trimmedTag]);
      setCurrentTags([...currentTags, trimmedTag]);
      setNewTag('');
      onUpdate();
    } catch (err: any) {
      setError(err.message || 'Failed to add tag');
    } finally {
      setSavingTags(false);
    }
  };

  const handleRemoveTag = async (tagToRemove: string) => {
    try {
      setSavingTags(true);
      await removeTags(dataId, [tagToRemove]);
      setCurrentTags(currentTags.filter(t => t !== tagToRemove));
      onUpdate();
    } catch (err: any) {
      setError(err.message || 'Failed to remove tag');
    } finally {
      setSavingTags(false);
    }
  };

  const handleTagKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddTag();
    }
  };

  const handleSaveInfo = async () => {
    try {
      setSavingInfo(true);
      await updateInfo(dataId, {
        name: currentName || null,
        description: currentDescription || null,
      });
      setEditingInfo(false);
      onUpdate();
      setSuccess('Info updated successfully!');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to update info');
    } finally {
      setSavingInfo(false);
    }
  };

  const handleCancelInfoEdit = () => {
    setCurrentName(metadata.name || '');
    setCurrentDescription(metadata.description || '');
    setEditingInfo(false);
  };

  if (loading) {
    return (
      <div className="glass-card p-12">
        <div className="flex flex-col items-center justify-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary-500/20 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
          </div>
          <p className="text-white/60">Loading content...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-6 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
            {isBinary ? <FileQuestion className="w-5 h-5 text-white" />
              : isVideoContent ? <Film className="w-5 h-5 text-white" />
              : isAudioContent ? <Music className="w-5 h-5 text-white" />
              : <FileText className="w-5 h-5 text-white" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-semibold text-white">Content</h2>
              {version && (
                <span className="badge badge-info">v{version}</span>
              )}
            </div>
            {!isCurrentVersion && (
              <div className="flex items-center gap-1.5 mt-1 text-sm text-amber-400">
                <Lock className="w-3.5 h-3.5" />
                Read-only (historical version)
              </div>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Preview Toggle - only show for content types that support preview */}
          {hasPreview && !isEditing && (
            <button
              onClick={() => setShowPreview(!showPreview)}
              className={`btn-secondary flex items-center gap-2 ${showPreview ? 'bg-primary-500/20 border-primary-500/50' : ''}`}
              title={showPreview ? 'Show raw content' : 'Show preview'}
            >
              {showPreview ? (
                <>
                  <Eye className="w-4 h-4" />
                  Preview
                </>
              ) : (
                <>
                  <Code className="w-4 h-4" />
                  Raw
                </>
              )}
            </button>
          )}
          {isCurrentVersion && !isBinary && !isEditing && !isImageContent && !isVideoContent && !isAudioContent && (
            <button
              onClick={() => setIsEditing(true)}
              className="btn-secondary flex items-center gap-2"
            >
              <Edit3 className="w-4 h-4" />
              Edit
            </button>
          )}
          {isEditing && (
            <>
              <button
                onClick={handleCancelEdit}
                className="btn-secondary flex items-center gap-2"
              >
                <X className="w-4 h-4" />
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="btn-premium flex items-center gap-2 !py-2.5"
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                <span>{saving ? 'Saving...' : 'Save'}</span>
              </button>
            </>
          )}
          {isCurrentVersion && (
            <button
              onClick={handleDelete}
              className="btn-danger flex items-center gap-2"
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </button>
          )}
        </div>
      </div>

      {/* Alerts */}
      <div className="px-6 pt-4">
        {error && (
          <div className="alert alert-error flex items-center gap-3 mb-4">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
        
        {success && (
          <div className="alert alert-success flex items-center gap-3 mb-4">
            <Check className="w-5 h-5 flex-shrink-0" />
            <span>{success}</span>
          </div>
        )}
      </div>

      {/* Info Section (Name & Description) */}
      {isCurrentVersion && (
        <div className="mx-6 mb-4">
          <button
            onClick={() => setShowInfo(!showInfo)}
            className="w-full flex items-center justify-between p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center">
                <Info className="w-4 h-4 text-blue-400" />
              </div>
              <div className="text-left">
                <span className="text-white font-medium">Name &amp; Description</span>
                <span className="ml-2 text-xs text-white/50">
                  {metadata.name || 'Unnamed'}
                </span>
              </div>
            </div>
            {showInfo ? (
              <ChevronUp className="w-5 h-5 text-white/50" />
            ) : (
              <ChevronDown className="w-5 h-5 text-white/50" />
            )}
          </button>
          
          {showInfo && (
            <div className="mt-2 p-4 rounded-xl bg-slate-900/50 border border-white/10">
              {editingInfo ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm text-white/60 mb-2">Name</label>
                    <input
                      type="text"
                      value={currentName}
                      onChange={(e) => setCurrentName(e.target.value)}
                      placeholder="Enter a name..."
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-white/60 mb-2">Description</label>
                    <textarea
                      value={currentDescription}
                      onChange={(e) => setCurrentDescription(e.target.value)}
                      placeholder="Enter a description..."
                      rows={3}
                      className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder:text-white/30 focus:outline-none focus:ring-2 focus:ring-blue-500/50 resize-none"
                    />
                  </div>
                  <div className="flex items-center gap-2 justify-end">
                    <button
                      onClick={handleCancelInfoEdit}
                      className="btn-secondary text-sm py-1.5 px-3"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSaveInfo}
                      disabled={savingInfo}
                      className="btn-primary text-sm py-1.5 px-3 flex items-center gap-2"
                    >
                      {savingInfo ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Save className="w-3 h-3" />
                      )}
                      Save
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-sm text-white/60 mb-1">Name</div>
                      <div className="text-white">
                        {metadata.name || <span className="text-white/40 italic">No name set</span>}
                      </div>
                    </div>
                    <button
                      onClick={() => setEditingInfo(true)}
                      className="text-blue-400 hover:text-blue-300 p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                  </div>
                  <div>
                    <div className="text-sm text-white/60 mb-1">Description</div>
                    <div className="text-white">
                      {metadata.description || <span className="text-white/40 italic">No description set</span>}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Address Section */}
      {metadata.address && (() => {
        const displayPath = normalizeAddress(metadata.address) ?? metadata.address;
        const openData = async (e: React.MouseEvent) => {
          e.preventDefault();
          try {
            const blob = await getData(dataId, version ?? undefined);
            const blobUrl = URL.createObjectURL(blob);
            window.open(blobUrl, '_blank');
          } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to open data');
          }
        };
        return (
          <div className="mx-6 mb-4">
            <div className="flex items-center gap-3 p-4 rounded-xl bg-white/5 border border-white/10">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-teal-500/20 to-emerald-500/20 flex items-center justify-center flex-shrink-0">
                <Link className="w-4 h-4 text-teal-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-white/50 mb-0.5">Address</div>
                <a
                  href={displayPath}
                  onClick={openData}
                  className="text-sm text-teal-400 hover:text-teal-300 font-mono truncate block transition-colors cursor-pointer"
                  title={displayPath}
                >
                  {displayPath}
                </a>
              </div>
              <button
                onClick={async () => {
                  const fullUrl = `${window.location.origin}${displayPath}`;
                  await navigator.clipboard.writeText(fullUrl);
                  setSuccess('Address copied!');
                  setTimeout(() => setSuccess(null), 2000);
                }}
                className="p-2 rounded-lg hover:bg-white/10 transition-colors flex-shrink-0"
                title="Copy address"
              >
                <Copy className="w-4 h-4 text-white/40 hover:text-white/60" />
              </button>
            </div>
          </div>
        );
      })()}

      {/* Access Control Section */}
      {isCurrentVersion && (
        <div className="mx-6 mb-4">
          <button
            onClick={() => setShowAccessControl(!showAccessControl)}
            className="w-full flex items-center justify-between p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500/20 to-orange-500/20 flex items-center justify-center">
                <Shield className="w-4 h-4 text-amber-400" />
              </div>
              <div className="text-left">
                <span className="text-white font-medium">Access Control</span>
                <span className="ml-2 text-xs text-white/50">
                  {!currentAccess || currentAccess.length === 0 
                    ? 'Public' 
                    : currentAccess.includes('*') 
                      ? 'All Authenticated Users' 
                      : `${currentAccess.length} restricted`}
                </span>
              </div>
            </div>
            {showAccessControl ? (
              <ChevronUp className="w-5 h-5 text-white/50" />
            ) : (
              <ChevronDown className="w-5 h-5 text-white/50" />
            )}
          </button>
          
          {showAccessControl && (
            <div className="mt-2 p-4 rounded-xl bg-slate-900/50 border border-white/10">
              <AccessControl
                dataId={dataId}
                access={currentAccess}
                onUpdate={handleAccessUpdate}
                apiBaseUrl={apiBaseUrl}
              />
            </div>
          )}
        </div>
      )}

      {/* Tags Section */}
      {isCurrentVersion && (
        <div className="mx-6 mb-4">
          <button
            onClick={() => setShowTags(!showTags)}
            className="w-full flex items-center justify-between p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
                <Tag className="w-4 h-4 text-purple-400" />
              </div>
              <div className="text-left">
                <span className="text-white font-medium">Tags</span>
                <span className="ml-2 text-xs text-white/50">
                  {currentTags.length === 0 
                    ? 'No tags' 
                    : `${currentTags.length} tag${currentTags.length === 1 ? '' : 's'}`}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {currentTags.length > 0 && !showTags && (
                <div className="flex items-center gap-1">
                  {currentTags.slice(0, 3).map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30 text-xs"
                    >
                      {tag}
                    </span>
                  ))}
                  {currentTags.length > 3 && (
                    <span className="text-white/40 text-xs">+{currentTags.length - 3}</span>
                  )}
                </div>
              )}
              {showTags ? (
                <ChevronUp className="w-5 h-5 text-white/50" />
              ) : (
                <ChevronDown className="w-5 h-5 text-white/50" />
              )}
            </div>
          </button>
          
          {showTags && (
            <div className="mt-2 p-4 rounded-xl bg-slate-900/50 border border-white/10">
              {/* Current Tags */}
              <div className="flex flex-wrap gap-2 mb-4">
                {currentTags.length === 0 ? (
                  <span className="text-white/40 text-sm">No tags yet. Add some tags to organize your data.</span>
                ) : (
                  currentTags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/30 text-sm group"
                    >
                      <Tag className="w-3 h-3" />
                      {tag}
                      <button
                        onClick={() => handleRemoveTag(tag)}
                        disabled={savingTags}
                        className="ml-1 p-0.5 rounded hover:bg-purple-500/20 transition-colors"
                        title="Remove tag"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))
                )}
              </div>
              
              {/* Add Tag Input */}
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Tag className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                  <input
                    type="text"
                    value={newTag}
                    onChange={(e) => setNewTag(e.target.value)}
                    onKeyDown={handleTagKeyDown}
                    placeholder="Add a tag..."
                    className="input-modern pl-10 py-2"
                    disabled={savingTags}
                  />
                </div>
                <button
                  onClick={handleAddTag}
                  disabled={savingTags || !newTag.trim()}
                  className="btn-secondary flex items-center gap-2 py-2"
                >
                  {savingTags ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Plus className="w-4 h-4" />
                  )}
                  Add
                </button>
              </div>
              
              <p className="mt-3 text-xs text-white/40">
                Press Enter to add a tag. Tags are case-insensitive and automatically deduplicated.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Content */}
      <div className="p-6 pt-2">
        {/* Image Content Preview */}
        {isImageContent && binaryUrl && (
          <div className="space-y-4">
            {showPreview ? (
              <div className="relative rounded-xl overflow-hidden bg-black/20 border border-white/10">
                <div className="absolute top-3 right-3 flex items-center gap-1.5 px-2 py-1 rounded-md bg-black/50 text-white/70 text-xs backdrop-blur-sm">
                  <FileImage className="w-3.5 h-3.5" />
                  Image Preview
                </div>
                <div className="flex items-center justify-center p-4 min-h-[200px] max-h-[600px]">
                  <img
                    src={binaryUrl}
                    alt={`Preview of ${dataId}`}
                    className="max-w-full max-h-[560px] object-contain rounded-lg shadow-lg"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                      setError('Failed to load image preview');
                    }}
                  />
                </div>
              </div>
            ) : (
              <div className="text-center py-8 bg-black/20 rounded-xl border border-white/10">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-primary-500/20 to-accent-500/20 flex items-center justify-center">
                  <FileImage className="w-8 h-8 text-white/50" />
                </div>
                <p className="text-white/70 mb-2">Image File</p>
                <p className="text-sm text-white/40 mb-2 font-mono">{contentType}</p>
                <p className="text-xs text-white/30">
                  {currentVersionInfo?.size ? `${(currentVersionInfo.size / 1024).toFixed(1)} KB` : ''}
                </p>
              </div>
            )}
            <div className="flex justify-center gap-3">
              <a
                href={binaryUrl}
                download={`${dataId}-v${version}.${contentType?.split('/')[1] || 'bin'}`}
                className="btn-premium flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                <span>Download Image</span>
              </a>
              {isCurrentVersion && (
                <label className="btn-secondary flex items-center gap-2 cursor-pointer">
                  <Upload className="w-4 h-4" />
                  Upload New Version
                  <input
                    type="file"
                    className="hidden"
                    accept="image/*"
                    onChange={handleFileUpload}
                  />
                </label>
              )}
            </div>
          </div>
        )}

        {/* Video Content Preview */}
        {isVideoContent && (
          <div className="space-y-4">
            <div className="relative rounded-xl overflow-hidden bg-black/20 border border-white/10">
              <div className="absolute top-3 right-3 flex items-center gap-1.5 px-2 py-1 rounded-md bg-black/50 text-white/70 text-xs backdrop-blur-sm z-10">
                <Film className="w-3.5 h-3.5" />
                Video Preview
              </div>
              <div className="flex items-center justify-center p-4 min-h-[200px]">
                <video
                  src={streamingUrl}
                  controls
                  controlsList="nodownload"
                  className="max-w-full max-h-[500px] rounded-lg shadow-lg"
                  onError={() => setError('Failed to load video preview')}
                >
                  Your browser does not support the video tag.
                </video>
              </div>
            </div>
            <div className="flex justify-center gap-3">
              <a
                href={streamingUrl}
                download={`${dataId}-v${version}.${contentType?.split('/')[1] || 'mp4'}`}
                className="btn-premium flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                <span>Download Video</span>
              </a>
              {isCurrentVersion && (
                <label className="btn-secondary flex items-center gap-2 cursor-pointer">
                  <Upload className="w-4 h-4" />
                  Upload New Version
                  <input
                    type="file"
                    className="hidden"
                    accept="video/*"
                    onChange={handleFileUpload}
                  />
                </label>
              )}
            </div>
          </div>
        )}

        {/* Audio Content Preview */}
        {isAudioContent && (
          <div className="space-y-4">
            <div className="rounded-xl bg-black/20 border border-white/10 p-6">
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center">
                  <Music className="w-4 h-4 text-purple-400" />
                </div>
                <span className="text-sm text-white/70 font-medium">Audio Preview</span>
                {contentType && (
                  <span className="text-xs text-white/40 font-mono ml-auto">{contentType}</span>
                )}
              </div>
              <audio
                src={streamingUrl}
                controls
                className="w-full"
                onError={() => setError('Failed to load audio preview')}
              >
                Your browser does not support the audio tag.
              </audio>
              {currentVersionInfo?.size && (
                <p className="text-xs text-white/30 mt-3 text-right">
                  {(currentVersionInfo.size / 1024).toFixed(1)} KB
                </p>
              )}
            </div>
            <div className="flex justify-center gap-3">
              <a
                href={streamingUrl}
                download={`${dataId}-v${version}.${contentType?.split('/')[1] || 'mp3'}`}
                className="btn-premium flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                <span>Download Audio</span>
              </a>
              {isCurrentVersion && (
                <label className="btn-secondary flex items-center gap-2 cursor-pointer">
                  <Upload className="w-4 h-4" />
                  Upload New Version
                  <input
                    type="file"
                    className="hidden"
                    accept="audio/*"
                    onChange={handleFileUpload}
                  />
                </label>
              )}
            </div>
          </div>
        )}

        {/* Binary Content (non-image, non-video, non-audio) */}
        {isBinary && !isImageContent && (
          <div className="text-center py-8">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-primary-500/20 to-accent-500/20 flex items-center justify-center">
              <FileQuestion className="w-8 h-8 text-white/50" />
            </div>
            <p className="text-white/70 mb-2">Binary File</p>
            <p className="text-sm text-white/40 mb-6 font-mono">
              {contentType}
            </p>
            <div className="flex justify-center gap-3">
              <a
                href={binaryUrl || '#'}
                download={`data-${dataId}-v${version}`}
                className="btn-premium flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                <span>Download File</span>
              </a>
              {isCurrentVersion && (
                <label className="btn-secondary flex items-center gap-2 cursor-pointer">
                  <Upload className="w-4 h-4" />
                  Upload New Version
                  <input
                    type="file"
                    className="hidden"
                    onChange={handleFileUpload}
                  />
                </label>
              )}
            </div>
          </div>
        )}

        {/* Provenance Section */}
        {metadata.provenance && (
          <div className="mt-4 p-4 rounded-xl bg-black/20 border border-white/10">
            <h4 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5" />
              Provenance
            </h4>
            {metadata.provenance.user && (
              <div className="mb-2 text-xs text-white/60">
                <span className="font-medium text-white/80">User:</span>{' '}
                {String((metadata.provenance.user as any).user_id || '')}
                {(metadata.provenance.user as any).display_name && ` (${(metadata.provenance.user as any).display_name})`}
              </div>
            )}
            {metadata.provenance.device && (
              <div className="mb-2 text-xs text-white/60">
                <span className="font-medium text-white/80">Device:</span>{' '}
                {[
                  metadata.provenance.device.device_type,
                  metadata.provenance.device.os,
                  metadata.provenance.device.browser,
                ].filter(Boolean).join(' · ')}
                {metadata.provenance.device.screen_width && ` · ${metadata.provenance.device.screen_width}×${metadata.provenance.device.screen_height}`}
                {metadata.provenance.device.timezone && ` · ${metadata.provenance.device.timezone}`}
                {metadata.provenance.device.language && ` · ${metadata.provenance.device.language}`}
              </div>
            )}
            {metadata.data_version_label && (
              <div className="mb-2 text-xs text-white/60">
                <span className="font-medium text-white/80">Version label:</span>{' '}
                <span className="font-mono">{metadata.data_version_label}</span>
              </div>
            )}
            {metadata.source_service && (
              <div className="mb-2 text-xs text-white/60">
                <span className="font-medium text-white/80">Source service:</span>{' '}
                {metadata.source_service}
              </div>
            )}
            {metadata.provenance.services && metadata.provenance.services.length > 0 && (
              <div className="mt-2">
                <span className="text-xs font-medium text-white/80">Service chain:</span>
                <div className="mt-1 space-y-1">
                  {metadata.provenance.services.map((svc, idx) => (
                    <div key={idx} className="text-xs text-white/50 font-mono pl-2 border-l border-white/10">
                      {svc.service_name} <span className="text-white/30">·</span> {svc.action} <span className="text-white/30">·</span> {svc.timestamp}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Text Content (JSON, Markdown, Code, Plain Text) */}
        {isTextContent && !isBinary && (
          <div>
            {isEditing ? (
              <textarea
                className="textarea-modern min-h-[400px]"
                value={editedContent}
                onChange={(e) => setEditedContent(e.target.value)}
              />
            ) : (
              <div className="relative group">
                {/* Content Type Badge */}
                <div className="absolute top-3 right-3 flex items-center gap-1.5 px-2 py-1 rounded-md bg-black/50 text-white/70 text-xs backdrop-blur-sm z-10">
                  {contentCategory === 'json' && <Code className="w-3.5 h-3.5" />}
                  {contentCategory === 'markdown' && <FileType className="w-3.5 h-3.5" />}
                  {contentCategory === 'code' && <Code className="w-3.5 h-3.5" />}
                  {contentCategory === 'text' && <FileText className="w-3.5 h-3.5" />}
                  <span className="capitalize">{contentCategory}</span>
                  {showPreview && hasPreview && <span className="text-primary-400 ml-1">• Preview</span>}
                </div>

                {/* JSON Preview with Syntax Highlighting */}
                {contentCategory === 'json' && showPreview ? (
                  <pre 
                    className="code-block min-h-[200px] max-h-[600px] overflow-auto whitespace-pre"
                    dangerouslySetInnerHTML={{ __html: formattedContent }}
                  />
                ) : contentCategory === 'markdown' && showPreview ? (
                  /* Markdown Rendered Preview */
                  <div 
                    className="prose-preview min-h-[200px] max-h-[600px] overflow-auto p-6 bg-black/20 rounded-xl border border-white/10"
                    dangerouslySetInnerHTML={{ __html: formattedContent }}
                  />
                ) : (
                  /* Raw Content View */
                  <pre className="code-block min-h-[200px] max-h-[600px] whitespace-pre-wrap break-words overflow-auto">
                    {content}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

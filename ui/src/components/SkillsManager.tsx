'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  BookOpen, Plus, Trash2, X, AlertCircle, Loader2, Edit3, Tag, Clock,
  Save, ChevronDown, ChevronUp, Search,
} from 'lucide-react';
import { listSkills, createSkill, updateSkill, deleteSkill } from '@/lib/api';

export default function SkillsManager() {
  const [skills, setSkills] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingSkillId, setEditingSkillId] = useState<string | null>(null);
  const [expandedSkillId, setExpandedSkillId] = useState<string | null>(null);
  const [filterTag, setFilterTag] = useState('');
  const [searchText, setSearchText] = useState('');

  const [createForm, setCreateForm] = useState({
    name: '',
    description: '',
    content: '',
    tags: '',
    data_id: '',
  });
  const [createLoading, setCreateLoading] = useState(false);

  const [editForm, setEditForm] = useState({
    name: '',
    description: '',
    content: '',
    tags: '',
  });
  const [editLoading, setEditLoading] = useState(false);

  const fetchSkills = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listSkills({ tag: filterTag || undefined });
      setSkills(Array.isArray(data) ? data : []);
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 503 && detail?.includes('not configured')) {
        setError('AI features are not configured. Please set the required environment variables (SKILLS_BUCKET, etc.) to enable skills.');
      } else if (detail) {
        setError(detail);
      } else if (err.message === 'Network Error') {
        setError('Cannot reach the API server. Please check that the backend is running.');
      } else {
        setError(err.message || 'Failed to load skills');
      }
      setSkills([]);
    } finally {
      setLoading(false);
    }
  }, [filterTag]);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  const allTags = Array.from(new Set(skills.flatMap((s: any) => s.tags || [])));

  const filteredSkills = searchText
    ? skills.filter((s: any) =>
        s.name.toLowerCase().includes(searchText.toLowerCase()) ||
        s.description.toLowerCase().includes(searchText.toLowerCase())
      )
    : skills;

  const handleCreate = async () => {
    if (!createForm.name.trim() || !createForm.content.trim()) return;
    try {
      setCreateLoading(true);
      setError(null);
      const tags = createForm.tags
        .split(',')
        .map((t: string) => t.trim())
        .filter(Boolean);
      await createSkill({
        name: createForm.name.trim(),
        description: createForm.description.trim(),
        content: createForm.content.trim(),
        tags,
        data_id: createForm.data_id.trim() || undefined,
      });
      setCreateForm({ name: '', description: '', content: '', tags: '', data_id: '' });
      setShowCreateForm(false);
      await fetchSkills();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to create skill');
    } finally {
      setCreateLoading(false);
    }
  };

  const startEdit = (skill: any) => {
    setEditingSkillId(skill.skill_id || skill.id);
    setEditForm({
      name: skill.name || '',
      description: skill.description || '',
      content: skill.content || '',
      tags: (skill.tags || []).join(', '),
    });
  };

  const cancelEdit = () => {
    setEditingSkillId(null);
  };

  const handleUpdate = async (skillId: string) => {
    try {
      setEditLoading(true);
      setError(null);
      const tags = editForm.tags
        .split(',')
        .map((t: string) => t.trim())
        .filter(Boolean);
      await updateSkill(skillId, {
        name: editForm.name.trim() || undefined,
        description: editForm.description.trim() || undefined,
        content: editForm.content.trim() || undefined,
        tags,
      });
      setEditingSkillId(null);
      await fetchSkills();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to update skill');
    } finally {
      setEditLoading(false);
    }
  };

  const handleDelete = async (skillId: string) => {
    if (!confirm('Delete this skill? This action cannot be undone.')) return;
    try {
      setError(null);
      await deleteSkill(skillId);
      setSkills(prev => prev.filter((s: any) => (s.skill_id || s.id) !== skillId));
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to delete skill');
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">AI Agent Skills</h2>
              <p className="text-sm text-white/50">Define roles and capabilities for AI agents</p>
            </div>
          </div>
          <button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-medium text-sm hover:opacity-90 transition-opacity"
          >
            <Plus className="w-4 h-4" />
            New Skill
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mx-6 mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)} className="p-1 hover:bg-white/10 rounded">
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Toolbar: Search + Tag Filter */}
      <div className="px-6 pt-4 flex flex-col sm:flex-row gap-3">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search skills..."
            className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          />
        </div>
        {allTags.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setFilterTag('')}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                !filterTag
                  ? 'bg-emerald-500/20 border border-emerald-500/40 text-emerald-400'
                  : 'bg-white/5 border border-white/10 text-white/50 hover:text-white/70'
              }`}
            >
              All
            </button>
            {allTags.map((tag: string) => (
              <button
                key={tag}
                onClick={() => setFilterTag(filterTag === tag ? '' : tag)}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  filterTag === tag
                    ? 'bg-emerald-500/20 border border-emerald-500/40 text-emerald-400'
                    : 'bg-white/5 border border-white/10 text-white/50 hover:text-white/70'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Create Form Modal */}
      {showCreateForm && (
        <div className="mx-6 mt-4 p-5 rounded-xl bg-white/5 border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider">Create New Skill</h3>
            <button onClick={() => setShowCreateForm(false)} className="p-1 rounded hover:bg-white/10 text-white/40">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="space-y-3">
            <input
              type="text"
              value={createForm.name}
              onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Skill name (e.g. Code Reviewer, Data Analyst)"
              className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
            />
            <input
              type="text"
              value={createForm.description}
              onChange={(e) => setCreateForm(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Short description of what this skill does"
              className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
            />
            <textarea
              value={createForm.content}
              onChange={(e) => setCreateForm(prev => ({ ...prev, content: e.target.value }))}
              placeholder="Full skill instructions for the AI agent..."
              rows={6}
              className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
            />
            <div className="grid grid-cols-2 gap-3">
              <input
                type="text"
                value={createForm.tags}
                onChange={(e) => setCreateForm(prev => ({ ...prev, tags: e.target.value }))}
                placeholder="Tags (comma-separated, e.g. coding, review)"
                className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
              <input
                type="text"
                value={createForm.data_id}
                onChange={(e) => setCreateForm(prev => ({ ...prev, data_id: e.target.value }))}
                placeholder="Data ID (optional, leave empty for global)"
                className="w-full px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
            </div>
            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={() => setShowCreateForm(false)}
                className="px-4 py-2 rounded-xl text-sm text-white/50 hover:text-white/70 hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={createLoading || !createForm.name.trim() || !createForm.content.trim()}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {createLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Create Skill
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Skills List */}
      <div className="p-6">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-emerald-400 animate-spin" />
          </div>
        ) : filteredSkills.length === 0 ? (
          <div className="text-center py-12 text-white/30">
            <BookOpen className="w-10 h-10 mx-auto mb-3 opacity-50" />
            <p className="text-sm">{searchText || filterTag ? 'No skills match your filters.' : 'No skills created yet.'}</p>
            <p className="text-xs mt-1">Skills define roles and capabilities for AI agents.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredSkills.map((skill: any) => {
              const id = skill.skill_id || skill.id;
              const isExpanded = expandedSkillId === id;
              const isEditing = editingSkillId === id;

              return (
                <div key={id} className="rounded-xl bg-white/5 border border-white/10 hover:border-white/20 transition-colors overflow-hidden">
                  {/* Skill Header */}
                  <div className="flex items-center gap-3 p-4">
                    <button
                      onClick={() => setExpandedSkillId(isExpanded ? null : id)}
                      className="flex-1 flex items-start gap-3 text-left"
                    >
                      <div className="w-9 h-9 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <BookOpen className="w-4 h-4 text-emerald-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-white truncate">{skill.name}</span>
                          {skill.data_id && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-400 flex-shrink-0">data-specific</span>
                          )}
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-white/40 flex-shrink-0">v{skill.version}</span>
                        </div>
                        <p className="text-xs text-white/50 mt-0.5 line-clamp-1">{skill.description}</p>
                        {skill.tags && skill.tags.length > 0 && (
                          <div className="flex gap-1.5 mt-1.5 flex-wrap">
                            {skill.tags.map((tag: string) => (
                              <span key={tag} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 text-[10px]">
                                <Tag className="w-2.5 h-2.5" />{tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-white/30 flex-shrink-0 mt-1" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-white/30 flex-shrink-0 mt-1" />
                      )}
                    </button>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button
                        onClick={() => isEditing ? cancelEdit() : startEdit(skill)}
                        className="p-1.5 rounded-lg hover:bg-white/10 text-white/30 hover:text-white/60 transition-colors"
                        title={isEditing ? 'Cancel edit' : 'Edit skill'}
                      >
                        {isEditing ? <X className="w-3.5 h-3.5" /> : <Edit3 className="w-3.5 h-3.5" />}
                      </button>
                      <button
                        onClick={() => handleDelete(id)}
                        className="p-1.5 rounded-lg hover:bg-red-500/20 text-white/30 hover:text-red-400 transition-colors"
                        title="Delete skill"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Expanded Content or Edit Form */}
                  {isExpanded && (
                    <div className="border-t border-white/10 p-4">
                      {isEditing ? (
                        <div className="space-y-3">
                          <input
                            type="text"
                            value={editForm.name}
                            onChange={(e) => setEditForm(prev => ({ ...prev, name: e.target.value }))}
                            placeholder="Skill name"
                            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                          />
                          <input
                            type="text"
                            value={editForm.description}
                            onChange={(e) => setEditForm(prev => ({ ...prev, description: e.target.value }))}
                            placeholder="Description"
                            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                          />
                          <textarea
                            value={editForm.content}
                            onChange={(e) => setEditForm(prev => ({ ...prev, content: e.target.value }))}
                            placeholder="Skill content / instructions"
                            rows={8}
                            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none font-mono"
                          />
                          <input
                            type="text"
                            value={editForm.tags}
                            onChange={(e) => setEditForm(prev => ({ ...prev, tags: e.target.value }))}
                            placeholder="Tags (comma-separated)"
                            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                          />
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={cancelEdit}
                              className="px-3 py-1.5 rounded-lg text-xs text-white/50 hover:text-white/70 hover:bg-white/5"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => handleUpdate(id)}
                              disabled={editLoading}
                              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 text-xs font-medium hover:bg-emerald-500/30 disabled:opacity-40"
                            >
                              {editLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                              Save
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div>
                          <pre className="text-sm text-white/70 leading-relaxed whitespace-pre-wrap font-mono bg-white/[0.03] rounded-lg p-3 max-h-80 overflow-auto">
                            {skill.content}
                          </pre>
                          <div className="flex items-center gap-4 mt-3 text-xs text-white/30">
                            {skill.user && (
                              <span>Owner: {skill.user}</span>
                            )}
                            {skill.created_at && (
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {formatDate(skill.created_at)}
                              </span>
                            )}
                            {skill.data_id && (
                              <span>Data: {skill.data_id.substring(0, 16)}...</span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

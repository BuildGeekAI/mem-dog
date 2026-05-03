'use client';

import { useState, useEffect, useCallback } from 'react';
import { Building2, FolderOpen, Plus, Trash2, Users, Loader2, AlertCircle, Check, RefreshCw } from 'lucide-react';
import {
  listOrganizations, createOrganization, deleteOrganization,
  listProjects, createProject, deleteProject,
  listOrgMembers, addOrgMember, removeOrgMember,
} from '@/lib/api';
import { useProject } from '@/lib/project-context';
import type { Organization, Project, OrgMember } from '@/types';

export default function OrgProjectManager() {
  const { refresh: refreshContext } = useProject();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Create forms
  const [newOrgName, setNewOrgName] = useState('');
  const [newOrgDisplayName, setNewOrgDisplayName] = useState('');
  const [creatingOrg, setCreatingOrg] = useState(false);
  const [newProjName, setNewProjName] = useState('');
  const [newProjDisplayName, setNewProjDisplayName] = useState('');
  const [newProjDesc, setNewProjDesc] = useState('');
  const [creatingProj, setCreatingProj] = useState(false);
  const [newMemberUserId, setNewMemberUserId] = useState('');
  const [newMemberRole, setNewMemberRole] = useState('member');
  const [addingMember, setAddingMember] = useState(false);

  const fetchOrgs = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await listOrganizations();
      setOrgs(res.organizations);
      if (res.organizations.length > 0 && !selectedOrg) {
        setSelectedOrg(res.organizations[0]);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load organizations');
    } finally {
      setLoading(false);
    }
  }, [selectedOrg]);

  const fetchOrgDetails = useCallback(async (orgId: string) => {
    try {
      const [projRes, memRes] = await Promise.all([
        listProjects(orgId),
        listOrgMembers(orgId),
      ]);
      setProjects(projRes.projects);
      setMembers(memRes.members);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => { fetchOrgs(); }, []);
  useEffect(() => {
    if (selectedOrg) fetchOrgDetails(selectedOrg.org_id);
  }, [selectedOrg, fetchOrgDetails]);

  const showSuccess = (msg: string) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(null), 3000);
  };

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newOrgName.trim()) return;
    try {
      setCreatingOrg(true);
      setError(null);
      const org = await createOrganization({
        name: newOrgName.trim(),
        display_name: newOrgDisplayName.trim() || undefined,
      });
      setNewOrgName('');
      setNewOrgDisplayName('');
      await fetchOrgs();
      setSelectedOrg(org);
      refreshContext();
      showSuccess(`Organization "${org.display_name || org.name}" created`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create organization');
    } finally {
      setCreatingOrg(false);
    }
  };

  const handleDeleteOrg = async (orgId: string) => {
    if (!confirm('Delete this organization and all its projects? This cannot be undone.')) return;
    try {
      setError(null);
      await deleteOrganization(orgId);
      if (selectedOrg?.org_id === orgId) setSelectedOrg(null);
      await fetchOrgs();
      refreshContext();
      showSuccess('Organization deleted');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to delete');
    }
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrg || !newProjName.trim()) return;
    try {
      setCreatingProj(true);
      setError(null);
      await createProject(selectedOrg.org_id, {
        name: newProjName.trim(),
        display_name: newProjDisplayName.trim() || undefined,
        description: newProjDesc.trim() || undefined,
      });
      setNewProjName('');
      setNewProjDisplayName('');
      setNewProjDesc('');
      await fetchOrgDetails(selectedOrg.org_id);
      refreshContext();
      showSuccess('Project created');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create project');
    } finally {
      setCreatingProj(false);
    }
  };

  const handleDeleteProject = async (projectId: string) => {
    if (!confirm('Delete this project?')) return;
    try {
      setError(null);
      await deleteProject(projectId);
      if (selectedOrg) await fetchOrgDetails(selectedOrg.org_id);
      refreshContext();
      showSuccess('Project deleted');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to delete');
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrg || !newMemberUserId.trim()) return;
    try {
      setAddingMember(true);
      setError(null);
      await addOrgMember(selectedOrg.org_id, newMemberUserId.trim(), newMemberRole);
      setNewMemberUserId('');
      setNewMemberRole('member');
      await fetchOrgDetails(selectedOrg.org_id);
      showSuccess('Member added');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to add member');
    } finally {
      setAddingMember(false);
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!selectedOrg || !confirm('Remove this member?')) return;
    try {
      setError(null);
      await removeOrgMember(selectedOrg.org_id, userId);
      await fetchOrgDetails(selectedOrg.org_id);
      showSuccess('Member removed');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to remove member');
    }
  };

  const inputClass = 'w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all';

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-white/40">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading organizations...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-2.5">
          <Check className="w-4 h-4 flex-shrink-0" />
          {success}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Org list + create */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider flex items-center gap-2">
              <Building2 className="w-4 h-4" /> Organizations
            </h3>
            <button onClick={fetchOrgs} className="p-1 text-white/30 hover:text-white/60 transition-colors">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          {orgs.map(org => (
            <button
              key={org.org_id}
              onClick={() => setSelectedOrg(org)}
              className={`w-full text-left p-3 rounded-xl border transition-all ${
                selectedOrg?.org_id === org.org_id
                  ? 'bg-primary-500/10 border-primary-500/30 text-white'
                  : 'bg-white/[0.02] border-white/[0.06] text-white/70 hover:bg-white/5'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{org.display_name || org.name}</p>
                  <p className="text-[10px] font-mono text-white/30 mt-0.5">{org.org_id}</p>
                </div>
                {org.org_id !== 'org_default' && (
                  <button
                    onClick={e => { e.stopPropagation(); handleDeleteOrg(org.org_id); }}
                    className="p-1 text-white/20 hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </button>
          ))}

          {/* Create org form */}
          <form onSubmit={handleCreateOrg} className="glass-card p-4 space-y-3">
            <p className="text-xs font-semibold text-white/40 uppercase tracking-wider">New Organization</p>
            <input
              type="text"
              value={newOrgName}
              onChange={e => setNewOrgName(e.target.value)}
              placeholder="Slug (e.g. my-team)"
              className={inputClass}
              required
            />
            <input
              type="text"
              value={newOrgDisplayName}
              onChange={e => setNewOrgDisplayName(e.target.value)}
              placeholder="Display name (optional)"
              className={inputClass}
            />
            <button
              type="submit"
              disabled={creatingOrg || !newOrgName.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg disabled:opacity-50 transition-all"
            >
              {creatingOrg ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              Create Organization
            </button>
          </form>
        </div>

        {/* Middle: Projects */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider flex items-center gap-2">
            <FolderOpen className="w-4 h-4" /> Projects
            {selectedOrg && <span className="text-white/30 font-normal normal-case">in {selectedOrg.display_name || selectedOrg.name}</span>}
          </h3>

          {!selectedOrg ? (
            <p className="text-sm text-white/30 py-4">Select an organization</p>
          ) : (
            <>
              {projects.map(p => (
                <div key={p.project_id} className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                  <div className="flex items-center justify-between">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-white/80 truncate">{p.display_name || p.name}</p>
                      <p className="text-[10px] font-mono text-white/30 mt-0.5">{p.project_id}</p>
                      {p.description && <p className="text-xs text-white/40 mt-1">{p.description}</p>}
                    </div>
                    {p.project_id !== 'proj_default' && (
                      <button
                        onClick={() => handleDeleteProject(p.project_id)}
                        className="p-1 text-white/20 hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))}

              <form onSubmit={handleCreateProject} className="glass-card p-4 space-y-3">
                <p className="text-xs font-semibold text-white/40 uppercase tracking-wider">New Project</p>
                <input
                  type="text"
                  value={newProjName}
                  onChange={e => setNewProjName(e.target.value)}
                  placeholder="Slug (e.g. my-app)"
                  className={inputClass}
                  required
                />
                <input
                  type="text"
                  value={newProjDisplayName}
                  onChange={e => setNewProjDisplayName(e.target.value)}
                  placeholder="Display name (optional)"
                  className={inputClass}
                />
                <input
                  type="text"
                  value={newProjDesc}
                  onChange={e => setNewProjDesc(e.target.value)}
                  placeholder="Description (optional)"
                  className={inputClass}
                />
                <button
                  type="submit"
                  disabled={creatingProj || !newProjName.trim()}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg disabled:opacity-50 transition-all"
                >
                  {creatingProj ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Create Project
                </button>
              </form>
            </>
          )}
        </div>

        {/* Right: Members */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider flex items-center gap-2">
            <Users className="w-4 h-4" /> Members
          </h3>

          {!selectedOrg ? (
            <p className="text-sm text-white/30 py-4">Select an organization</p>
          ) : (
            <>
              {members.map(m => (
                <div key={m.user_id} className="flex items-center justify-between p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                  <div className="min-w-0">
                    <p className="text-sm font-mono text-white/70 truncate">{m.user_id.substring(0, 12)}...</p>
                    <span className={`inline-block mt-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${
                      m.role === 'owner' ? 'bg-amber-500/20 text-amber-400' :
                      m.role === 'admin' ? 'bg-purple-500/20 text-purple-400' :
                      m.role === 'viewer' ? 'bg-white/10 text-white/50' :
                      'bg-blue-500/20 text-blue-400'
                    }`}>
                      {m.role}
                    </span>
                  </div>
                  {m.role !== 'owner' && (
                    <button
                      onClick={() => handleRemoveMember(m.user_id)}
                      className="p-1 text-white/20 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}

              <form onSubmit={handleAddMember} className="glass-card p-4 space-y-3">
                <p className="text-xs font-semibold text-white/40 uppercase tracking-wider">Add Member</p>
                <input
                  type="text"
                  value={newMemberUserId}
                  onChange={e => setNewMemberUserId(e.target.value)}
                  placeholder="User ID"
                  className={inputClass}
                  required
                />
                <select
                  value={newMemberRole}
                  onChange={e => setNewMemberRole(e.target.value)}
                  className={inputClass}
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                  <option value="viewer">Viewer</option>
                </select>
                <button
                  type="submit"
                  disabled={addingMember || !newMemberUserId.trim()}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg disabled:opacity-50 transition-all"
                >
                  {addingMember ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Add Member
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

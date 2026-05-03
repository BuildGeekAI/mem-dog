'use client';

import { useState, useEffect, useCallback } from 'react';
import { Users, UserPlus, Shield, Eye, Crown, Key, Copy, Trash2, X, Mail, Hash, Clock, HardDrive, Activity, ChevronRight, AlertCircle, Loader2 } from 'lucide-react';
import { UserResponse, UserCreate, UserUpdate, UserRole, UserStatus, APIKeyResponse, APIKeyCreate } from '@/types';
import { api } from '@/lib/api';

interface UserManagementProps {
  apiBaseUrl: string;
}

export function UserManagement({ apiBaseUrl }: UserManagementProps) {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);
  const [apiKeys, setApiKeys] = useState<APIKeyResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showCreateKeyForm, setShowCreateKeyForm] = useState(false);
  const [newApiKey, setNewApiKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [formData, setFormData] = useState<UserCreate>({
    username: '',
    email: '',
    display_name: '',
    role: 'user',
    metadata: {}
  });

  const [keyFormData, setKeyFormData] = useState<APIKeyCreate>({
    name: '',
    expires_in_days: undefined
  });

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get('/api/v1/users');
      setUsers(response.data.users);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchApiKeys = useCallback(async (userId: string) => {
    try {
      const response = await api.get(`/api/v1/users/${encodeURIComponent(userId)}/api-keys`);
      setApiKeys(response.data);
    } catch (err) {
      console.error('Failed to fetch API keys:', err);
      setApiKeys([]);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  useEffect(() => {
    if (selectedUser) fetchApiKeys(selectedUser.user_id);
  }, [selectedUser, fetchApiKeys]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/api/v1/users', formData);
      setShowCreateForm(false);
      setFormData({ username: '', email: '', display_name: '', role: 'user', metadata: {} });
      fetchUsers();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create user');
    }
  };

  const handleUpdateUser = async (userId: string, update: UserUpdate) => {
    try {
      const response = await api.put(`/api/v1/users/${encodeURIComponent(userId)}`, update);
      setSelectedUser(response.data);
      fetchUsers();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to update user');
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (!confirm('Are you sure you want to delete this user? This action cannot be undone.')) return;
    try {
      await api.delete(`/api/v1/users/${encodeURIComponent(userId)}`);
      setSelectedUser(null);
      fetchUsers();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to delete user');
    }
  };

  const handleCreateApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    try {
      const response = await api.post(`/api/v1/users/${encodeURIComponent(selectedUser.user_id)}/api-keys`, keyFormData);
      setNewApiKey(response.data.key);
      setShowCreateKeyForm(false);
      setKeyFormData({ name: '', expires_in_days: undefined });
      fetchApiKeys(selectedUser.user_id);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create API key');
    }
  };

  const handleDeleteApiKey = async (keyId: string) => {
    if (!selectedUser) return;
    if (!confirm('Are you sure you want to revoke this API key?')) return;
    try {
      await api.delete(`/api/v1/users/${encodeURIComponent(selectedUser.user_id)}/api-keys/${encodeURIComponent(keyId)}`);
      fetchApiKeys(selectedUser.user_id);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to delete API key');
    }
  };

  const handleCopyKey = () => {
    if (newApiKey) {
      navigator.clipboard.writeText(newApiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  };

  const getStatusStyle = (status: UserStatus) => {
    switch (status) {
      case 'active': return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
      case 'inactive': return 'bg-white/5 text-white/40 border-white/10';
      case 'suspended': return 'bg-red-500/15 text-red-400 border-red-500/30';
      default: return 'bg-white/5 text-white/40 border-white/10';
    }
  };

  const getRoleBadge = (role: UserRole) => {
    switch (role) {
      case 'admin': return { icon: <Crown className="w-3.5 h-3.5" />, style: 'bg-amber-500/15 text-amber-400 border-amber-500/30', label: 'Admin' };
      case 'user': return { icon: <Shield className="w-3.5 h-3.5" />, style: 'bg-blue-500/15 text-blue-400 border-blue-500/30', label: 'User' };
      case 'viewer': return { icon: <Eye className="w-3.5 h-3.5" />, style: 'bg-purple-500/15 text-purple-400 border-purple-500/30', label: 'Viewer' };
      default: return { icon: <Shield className="w-3.5 h-3.5" />, style: 'bg-blue-500/15 text-blue-400 border-blue-500/30', label: 'User' };
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-primary-400 animate-spin mr-3" />
        <span className="text-white/60">Loading users...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Error Banner */}
      {error && (
        <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <span className="text-red-300 text-sm">{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* New API Key Banner */}
      {newApiKey && (
        <div className="glass-card p-5 border-emerald-500/30">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
              <Key className="w-5 h-5 text-emerald-400" />
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="text-emerald-300 font-semibold text-sm mb-1">API Key Created</h4>
              <p className="text-white/50 text-xs mb-3">Copy this key now. You won&apos;t be able to see it again.</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 block bg-black/30 text-emerald-300 px-3 py-2 rounded-lg text-xs font-mono break-all border border-emerald-500/20">
                  {newApiKey}
                </code>
                <button
                  onClick={handleCopyKey}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 text-xs font-medium transition-colors flex-shrink-0"
                >
                  <Copy className="w-3.5 h-3.5" />
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>
            <button onClick={() => setNewApiKey(null)} className="text-white/30 hover:text-white/60 transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6">
        {/* User List Panel */}
        <div className="glass-card p-0 overflow-hidden">
          <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-primary-400" />
              <span className="text-sm font-semibold text-white/80 uppercase tracking-wider">Users</span>
              <span className="ml-1 text-xs bg-white/10 text-white/50 px-2 py-0.5 rounded-full">{users.length}</span>
            </div>
            <button
              onClick={() => setShowCreateForm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25 transition-all"
            >
              <UserPlus className="w-3.5 h-3.5" />
              New
            </button>
          </div>

          <div className="p-2 max-h-[600px] overflow-y-auto">
            {users.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 px-4">
                <div className="w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center mb-4">
                  <Users className="w-7 h-7 text-white/20" />
                </div>
                <p className="text-white/40 text-sm text-center">No users yet</p>
                <p className="text-white/25 text-xs mt-1">Create your first user to get started</p>
              </div>
            ) : (
              <div className="space-y-1">
                {users.map(user => {
                  const isSelected = selectedUser?.user_id === user.user_id;
                  const role = getRoleBadge(user.role);
                  return (
                    <button
                      key={user.user_id}
                      onClick={() => setSelectedUser(user)}
                      className={`w-full text-left px-3 py-3 rounded-xl transition-all duration-200 group ${
                        isSelected
                          ? 'bg-gradient-to-r from-primary-500/20 to-accent-500/10 border border-primary-500/30 shadow-lg shadow-primary-500/10'
                          : 'hover:bg-white/5 border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                          isSelected ? 'bg-primary-500/30' : 'bg-white/5 group-hover:bg-white/10'
                        } transition-colors`}>
                          <span className="text-lg">{role.icon}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={`font-medium text-sm truncate ${isSelected ? 'text-white' : 'text-white/80'}`}>
                              {user.display_name || user.username}
                            </span>
                          </div>
                          <span className="text-xs text-white/40 font-mono">@{user.username}</span>
                        </div>
                        <div className="flex flex-col items-end gap-1.5">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[10px] font-semibold uppercase tracking-wider ${getStatusStyle(user.status)}`}>
                            {user.status}
                          </span>
                          <ChevronRight className={`w-3.5 h-3.5 transition-colors ${isSelected ? 'text-primary-400' : 'text-white/15 group-hover:text-white/30'}`} />
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* User Detail Panel */}
        <div className="glass-card p-0 overflow-hidden">
          {selectedUser ? (
            <>
              {/* Detail Header */}
              <div className="relative px-6 py-5 border-b border-white/10">
                <div className="absolute inset-0 bg-gradient-to-r from-primary-600/5 via-accent-500/5 to-transparent" />
                <div className="relative flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary-500/30 to-accent-500/30 flex items-center justify-center border border-white/10">
                      {getRoleBadge(selectedUser.role).icon}
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-white">{selectedUser.display_name || selectedUser.username}</h3>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-sm text-white/40 font-mono">@{selectedUser.username}</span>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[10px] font-semibold uppercase ${getRoleBadge(selectedUser.role).style}`}>
                          {getRoleBadge(selectedUser.role).label}
                        </span>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[10px] font-semibold uppercase ${getStatusStyle(selectedUser.status)}`}>
                          {selectedUser.status}
                        </span>
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteUser(selectedUser.user_id)}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors text-xs font-medium"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete
                  </button>
                </div>
              </div>

              <div className="p-6 space-y-6 max-h-[550px] overflow-y-auto">
                {/* Profile Section */}
                <div>
                  <h4 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <Shield className="w-3.5 h-3.5" /> Profile
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                      <div className="flex items-center gap-2 mb-1">
                        <Hash className="w-3 h-3 text-white/30" />
                        <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">User ID</span>
                      </div>
                      <code className="text-xs text-white/60 font-mono break-all">{selectedUser.user_id}</code>
                    </div>
                    <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                      <div className="flex items-center gap-2 mb-1">
                        <Mail className="w-3 h-3 text-white/30" />
                        <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Email</span>
                      </div>
                      <span className="text-sm text-white/80">{selectedUser.email}</span>
                    </div>
                    <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                      <div className="flex items-center gap-2 mb-1.5">
                        <Crown className="w-3 h-3 text-white/30" />
                        <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Role</span>
                      </div>
                      <select
                        value={selectedUser.role}
                        onChange={(e) => handleUpdateUser(selectedUser.user_id, { role: e.target.value as UserRole })}
                        className="w-full bg-black/30 text-white/80 text-sm border border-white/10 rounded-lg px-3 py-1.5 focus:outline-none focus:border-primary-500/50 transition-colors"
                      >
                        <option value="admin">Admin</option>
                        <option value="user">User</option>
                        <option value="viewer">Viewer</option>
                      </select>
                    </div>
                    <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                      <div className="flex items-center gap-2 mb-1.5">
                        <Activity className="w-3 h-3 text-white/30" />
                        <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold">Status</span>
                      </div>
                      <select
                        value={selectedUser.status}
                        onChange={(e) => handleUpdateUser(selectedUser.user_id, { status: e.target.value as UserStatus })}
                        className="w-full bg-black/30 text-white/80 text-sm border border-white/10 rounded-lg px-3 py-1.5 focus:outline-none focus:border-primary-500/50 transition-colors"
                      >
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                        <option value="suspended">Suspended</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Statistics Section */}
                <div>
                  <h4 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <Activity className="w-3.5 h-3.5" /> Statistics
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="bg-gradient-to-br from-primary-500/10 to-primary-600/5 rounded-xl px-4 py-3 border border-primary-500/10">
                      <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold block mb-1">Data Items</span>
                      <span className="text-xl font-bold text-white">{selectedUser.data_count}</span>
                    </div>
                    <div className="bg-gradient-to-br from-accent-500/10 to-accent-600/5 rounded-xl px-4 py-3 border border-accent-500/10">
                      <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold block mb-1">Storage</span>
                      <span className="text-xl font-bold text-white">{formatBytes(selectedUser.storage_used_bytes)}</span>
                    </div>
                    <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                      <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold block mb-1">Created</span>
                      <span className="text-xs text-white/60">{formatDate(selectedUser.created_at)}</span>
                    </div>
                    <div className="bg-white/5 rounded-xl px-4 py-3 border border-white/5">
                      <span className="text-[10px] uppercase tracking-wider text-white/30 font-semibold block mb-1">Last Active</span>
                      <span className="text-xs text-white/60">{selectedUser.last_active_at ? formatDate(selectedUser.last_active_at) : 'Never'}</span>
                    </div>
                  </div>
                </div>

                {/* API Keys Section */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-xs font-semibold text-white/40 uppercase tracking-wider flex items-center gap-2">
                      <Key className="w-3.5 h-3.5" /> API Keys
                    </h4>
                    <button
                      onClick={() => setShowCreateKeyForm(true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/5 text-white/60 border border-white/10 hover:bg-white/10 hover:text-white/80 transition-all"
                    >
                      <Key className="w-3 h-3" />
                      New Key
                    </button>
                  </div>
                  {apiKeys.length === 0 ? (
                    <div className="bg-white/[0.02] rounded-xl border border-dashed border-white/10 px-4 py-8 text-center">
                      <Key className="w-8 h-8 text-white/10 mx-auto mb-2" />
                      <p className="text-white/30 text-sm">No API keys</p>
                      <p className="text-white/20 text-xs mt-1">Create a key to authenticate API requests</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {apiKeys.map(key => (
                        <div key={key.key_id} className="flex items-center justify-between px-4 py-3 bg-white/5 rounded-xl border border-white/5 group hover:border-white/10 transition-colors">
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center flex-shrink-0">
                              <Key className="w-4 h-4 text-amber-400" />
                            </div>
                            <div className="min-w-0">
                              <span className="text-sm font-medium text-white/80 block truncate">{key.name}</span>
                              <span className="text-[10px] text-white/30 font-mono">
                                {key.key_id}
                                {key.expires_at && <span className="ml-2 text-white/20">Expires {formatDate(key.expires_at)}</span>}
                              </span>
                            </div>
                          </div>
                          <button
                            onClick={() => handleDeleteApiKey(key.key_id)}
                            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-all opacity-0 group-hover:opacity-100"
                          >
                            <Trash2 className="w-3 h-3" />
                            Revoke
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 px-6">
              <div className="w-20 h-20 rounded-3xl bg-white/5 flex items-center justify-center mb-5 border border-white/5">
                <Users className="w-10 h-10 text-white/10" />
              </div>
              <p className="text-white/30 text-base font-medium">Select a user</p>
              <p className="text-white/20 text-sm mt-1">Choose from the list to view their profile and manage settings</p>
            </div>
          )}
        </div>
      </div>

      {/* Create User Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowCreateForm(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md" onClick={e => e.stopPropagation()}>
            <div className="glass-card p-6 border-white/15 shadow-2xl">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500/30 to-accent-500/30 flex items-center justify-center">
                    <UserPlus className="w-5 h-5 text-primary-300" />
                  </div>
                  <h3 className="text-lg font-bold text-white">Create User</h3>
                </div>
                <button onClick={() => setShowCreateForm(false)} className="text-white/30 hover:text-white/60 transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <form onSubmit={handleCreateUser} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Username *</label>
                  <input
                    type="text"
                    value={formData.username}
                    onChange={e => setFormData({ ...formData, username: e.target.value })}
                    required minLength={3} maxLength={50}
                    placeholder="johndoe"
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Email *</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={e => setFormData({ ...formData, email: e.target.value })}
                    required placeholder="john@example.com"
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Display Name</label>
                  <input
                    type="text"
                    value={formData.display_name}
                    onChange={e => setFormData({ ...formData, display_name: e.target.value })}
                    placeholder="John Doe"
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Role</label>
                  <select
                    value={formData.role}
                    onChange={e => setFormData({ ...formData, role: e.target.value as UserRole })}
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-primary-500/50 transition-all"
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                    <option value="viewer">Viewer</option>
                  </select>
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowCreateForm(false)}
                    className="flex-1 px-4 py-2.5 rounded-xl border border-white/10 text-white/60 hover:bg-white/5 text-sm font-medium transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-primary-500 to-accent-500 text-white text-sm font-semibold hover:shadow-lg hover:shadow-primary-500/25 transition-all"
                  >
                    Create User
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Create API Key Modal */}
      {showCreateKeyForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setShowCreateKeyForm(false)}>
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
          <div className="relative w-full max-w-md" onClick={e => e.stopPropagation()}>
            <div className="glass-card p-6 border-white/15 shadow-2xl">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center">
                    <Key className="w-5 h-5 text-amber-400" />
                  </div>
                  <h3 className="text-lg font-bold text-white">Create API Key</h3>
                </div>
                <button onClick={() => setShowCreateKeyForm(false)} className="text-white/30 hover:text-white/60 transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <form onSubmit={handleCreateApiKey} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Key Name *</label>
                  <input
                    type="text"
                    value={keyFormData.name}
                    onChange={e => setKeyFormData({ ...keyFormData, name: e.target.value })}
                    required placeholder="My App Key"
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/25 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Expires In (days)</label>
                  <input
                    type="number"
                    value={keyFormData.expires_in_days || ''}
                    onChange={e => setKeyFormData({
                      ...keyFormData,
                      expires_in_days: e.target.value ? parseInt(e.target.value) : undefined
                    })}
                    placeholder="Leave empty for no expiry"
                    min={1}
                    className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-amber-500/50 focus:ring-1 focus:ring-amber-500/25 transition-all"
                  />
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowCreateKeyForm(false)}
                    className="flex-1 px-4 py-2.5 rounded-xl border border-white/10 text-white/60 hover:bg-white/5 text-sm font-medium transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white text-sm font-semibold hover:shadow-lg hover:shadow-amber-500/25 transition-all"
                  >
                    Create Key
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserManagement;

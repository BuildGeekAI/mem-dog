'use client';

import { useState, useEffect } from 'react';
import { UserCircle, Plug, Key, Check, AlertCircle, Loader2, Building2, Webhook } from 'lucide-react';
import IntegrationsManager from './IntegrationsManager';
import ApiKeysManager from './ApiKeysManager';
import OrgProjectManager from './OrgProjectManager';
import WebhookManager from './WebhookManager';
import { getCurrentUserId, setCurrentUserInfo, getUser, updateUser, createUser } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import type { UserResponse } from '@/types';

interface SettingsManagerProps {
  apiBaseUrl: string;
}

type SettingsSubTab = 'profile' | 'organizations' | 'integrations' | 'webhooks' | 'api-keys';

function ProfileSettings() {
  const { session } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<UserResponse | null>(null);

  // Editable form fields
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');

  useEffect(() => {
    const userId = getCurrentUserId();
    getUser(userId)
      .then((user) => {
        setProfile(user);
        setDisplayName(user.display_name || '');
        setEmail(user.email || '');
        setUsername(user.username || '');
      })
      .catch(async (err) => {
        // Auto-provision profile if 404 and we have a Supabase session
        if (err.response?.status === 404 && session?.user) {
          try {
            const uname = session.user.email?.split('@')[0] || 'user';
            const user = await createUser({
              user_id: session.user.id,
              username: uname,
              email: session.user.email || '',
              display_name: session.user.user_metadata?.full_name || uname,
            });
            setProfile(user);
            setDisplayName(user.display_name || '');
            setEmail(user.email || '');
            setUsername(user.username || '');
            setCurrentUserInfo({ user_id: user.user_id, username: user.username, display_name: user.display_name });
            return;
          } catch (createErr: any) {
            // If duplicate username, user already exists under a different ID — show original error
            if (!createErr?.response?.data?.detail?.includes('already exists')) {
              setError(`Failed to create profile: ${createErr.message}`);
              return;
            }
          }
        }
        setError(`Failed to load profile: ${err.response?.status === 404 ? 'User not found' : err.message}`);
      })
      .finally(() => setLoading(false));
  }, [session]);

  const handleSave = async () => {
    if (!profile) return;
    const trimmedUsername = username.trim();
    if (!trimmedUsername) {
      setError('Username cannot be empty.');
      return;
    }

    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await updateUser(profile.user_id, {
        display_name: displayName.trim() || undefined,
        email: email.trim(),
        username: trimmedUsername,
      });
      setProfile(updated);
      setDisplayName(updated.display_name || '');
      setEmail(updated.email || '');
      setUsername(updated.username || '');
      // Sync localStorage so the rest of the UI picks up changes
      setCurrentUserInfo({
        user_id: updated.user_id,
        username: updated.username,
        display_name: updated.display_name || undefined,
        role: updated.role,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Save failed';
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const inputClass =
    'w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50 focus:ring-1 focus:ring-primary-500/25 transition-all';
  const readonlyClass =
    'w-full bg-black/10 text-white/50 border border-white/5 rounded-xl px-4 py-2.5 text-sm cursor-not-allowed';

  return (
    <div className="glass-card p-6 max-w-lg space-y-5">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
          <UserCircle className="w-5 h-5 text-white" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-white">Profile</h3>
          <p className="text-sm text-white/50">Manage your account details</p>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {saved && (
        <div className="flex items-center gap-2 text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-2.5">
          <Check className="w-4 h-4 flex-shrink-0" />
          Profile saved
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8 text-white/40">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />
          Loading profile...
        </div>
      ) : profile ? (
        <div className="space-y-4">
          {/* Read-only fields */}
          <div>
            <label className="block text-sm font-medium text-white/70 mb-1.5">User ID</label>
            <input type="text" value={profile.user_id} readOnly className={readonlyClass} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-white/70 mb-1.5">Role</label>
              <input type="text" value={profile.role} readOnly className={readonlyClass} />
            </div>
            <div>
              <label className="block text-sm font-medium text-white/70 mb-1.5">Status</label>
              <input type="text" value={profile.status} readOnly className={readonlyClass} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-white/70 mb-1.5">Created</label>
            <input
              type="text"
              value={profile.created_at ? new Date(profile.created_at).toLocaleString() : '—'}
              readOnly
              className={readonlyClass}
            />
          </div>

          {/* Editable fields */}
          <hr className="border-white/10" />
          <div>
            <label className="block text-sm font-medium text-white/70 mb-1.5">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => { setUsername(e.target.value); setError(null); setSaved(false); }}
              placeholder="username"
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-white/70 mb-1.5">Display Name</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => { setDisplayName(e.target.value); setError(null); setSaved(false); }}
              placeholder="Display Name"
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-white/70 mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => { setEmail(e.target.value); setError(null); setSaved(false); }}
              placeholder="user@example.com"
              className={inputClass}
            />
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25 transition-all disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      ) : (
        <p className="text-white/40 text-sm py-4">No profile found. Check that user management is enabled.</p>
      )}
    </div>
  );
}

export function SettingsManager({ apiBaseUrl }: SettingsManagerProps) {
  const [subTab, setSubTab] = useState<SettingsSubTab>('profile');

  const tabs = [
    { id: 'profile' as const, label: 'Profile', icon: UserCircle },
    { id: 'organizations' as const, label: 'Organizations', icon: Building2 },
    { id: 'integrations' as const, label: 'Apps', icon: Plug },
    { id: 'webhooks' as const, label: 'Webhooks', icon: Webhook },
    { id: 'api-keys' as const, label: 'API Keys', icon: Key },
  ];

  return (
    <div className="space-y-6">
      {/* Sub-tab Navigation */}
      <div className="inline-flex items-center gap-1.5 p-1.5 bg-white/5 rounded-xl">
        {tabs.map(tab => (
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

      {/* Content */}
      {subTab === 'profile' && <ProfileSettings />}
      {subTab === 'organizations' && <OrgProjectManager />}
      {subTab === 'integrations' && (
        <IntegrationsManager apiBaseUrl={apiBaseUrl} />
      )}
      {subTab === 'webhooks' && <WebhookManager />}
      {subTab === 'api-keys' && <ApiKeysManager />}
    </div>
  );
}

export default SettingsManager;

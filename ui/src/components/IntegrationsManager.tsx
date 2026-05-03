'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Plug, Search, AlertCircle, Check, X, Key, ExternalLink,
  RefreshCw, Trash2, Loader2, Settings,
} from 'lucide-react';
import {
  listProviders,
  listIntegrationConnections,
  createApiKeyConnection,
  deleteIntegrationConnection,
  getOAuthAuthorizeUrl,
  refreshIntegrationConnection,
  setProviderOAuthCredentials,
  getCurrentUserId,
} from '@/lib/api';
import type { IntegrationProvider, IntegrationConnection } from '@/types';

// ---------------------------------------------------------------------------
// Category display config
// ---------------------------------------------------------------------------
const CATEGORIES: { key: string; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'chat', label: 'Chat' },
  { key: 'messaging', label: 'Messaging' },
  { key: 'email', label: 'Email' },
  { key: 'video', label: 'Video & Meetings' },
  { key: 'social', label: 'Social Media' },
  { key: 'crm', label: 'CRM & Sales' },
  { key: 'productivity', label: 'Productivity' },
  { key: 'devtools', label: 'Dev Tools' },
  { key: 'cloud', label: 'Cloud & Storage' },
  { key: 'finance', label: 'Finance' },
  { key: 'support', label: 'Support' },
  { key: 'hr', label: 'HR & People' },
  { key: 'data-ai', label: 'Data & AI' },
  { key: 'commerce', label: 'Commerce & Content' },
  { key: 'business-ops', label: 'Operations' },
];

const AUTH_BADGE_COLORS: Record<string, string> = {
  OAUTH2: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  API_KEY: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  BASIC: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  NONE: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

const STATUS_COLORS: Record<string, string> = {
  active: 'text-emerald-400',
  expired: 'text-amber-400',
  revoked: 'text-red-400',
  error: 'text-red-400',
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ProviderCard({
  provider,
  connection,
  onConnect,
  onDisconnect,
  onRefresh,
  onConfigure,
  isDisconnecting,
}: {
  provider: IntegrationProvider;
  connection?: IntegrationConnection;
  onConnect: (p: IntegrationProvider) => void;
  onDisconnect: (c: IntegrationConnection) => void;
  onRefresh: (c: IntegrationConnection) => void;
  onConfigure: (p: IntegrationProvider) => void;
  isDisconnecting: string | null;
}) {
  const IMPLEMENTED_PROVIDERS = new Set([
    'slack', 'google-mail', 'google-drive', 'zoom',
    'google', 'google-calendar', 'gmail', 'jira', 'github',
    'whatsapp', 'whatsapp-business', 'twilio',
    'notion', 'linear', 'hubspot', 'stripe', 'asana', 'salesforce',
    'pagerduty', 'datadog', 'sentry', 'grafana', 'opsgenie',
    'yelp', 'google-business', 'trustpilot', 'g2', 'tripadvisor', 'appstore', 'capterra',
  ]);
  const isImplemented = IMPLEMENTED_PROVIDERS.has(provider.provider_key);
  const isConnected = !!connection && connection.status === 'active';
  const hasError = !!connection && (connection.status === 'error' || connection.status === 'expired');
  const needsOAuthSetup = provider.auth_mode === 'OAUTH2' && !provider.oauth_configured;

  return (
    <div className={`glass-card p-4 flex flex-col gap-3 transition-colors ${isImplemented ? 'hover:bg-white/[0.04]' : 'opacity-40 pointer-events-none'}`}>
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg font-bold flex-shrink-0 ${
          isConnected
            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
            : 'bg-white/10 text-white/50 border border-white/10'
        }`}>
          {provider.display_name.charAt(0)}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-white truncate">{provider.display_name}</h3>
          <p className="text-xs text-white/40 line-clamp-2 mt-0.5">{provider.description}</p>
        </div>
      </div>

      {/* Badges */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-[10px] px-2 py-0.5 rounded-full border ${AUTH_BADGE_COLORS[provider.auth_mode] || AUTH_BADGE_COLORS.NONE}`}>
          {provider.auth_mode === 'API_KEY' ? 'API Key' : provider.auth_mode}
        </span>
        {provider.capabilities?.includes('inbound') && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
            Inbound
          </span>
        )}
        {provider.capabilities?.includes('outbound') && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-400 border border-blue-500/20">
            Outbound
          </span>
        )}
        {connection && (
          <span className={`text-[10px] font-medium ${STATUS_COLORS[connection.status] || 'text-white/40'}`}>
            {connection.status}
          </span>
        )}
        {needsOAuthSetup && isImplemented && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-orange-500/15 text-orange-400 border border-orange-500/20">
            Not configured
          </span>
        )}
        {!isImplemented && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-white/30 border border-white/10">
            Coming Soon
          </span>
        )}
      </div>

      {/* Connection info */}
      {connection?.account_email && (
        <p className="text-xs text-white/30 truncate">{connection.account_email}</p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 mt-auto pt-1">
        {isConnected ? (
          <>
            {provider.auth_mode === 'OAUTH2' && (
              <button
                onClick={() => onRefresh(connection!)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/10 text-white hover:bg-white/20 transition-colors"
              >
                <RefreshCw className="w-3 h-3" />
                Refresh
              </button>
            )}
            <button
              onClick={() => onDisconnect(connection!)}
              disabled={isDisconnecting === connection!.connection_id}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
            >
              {isDisconnecting === connection!.connection_id ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Trash2 className="w-3 h-3" />
              )}
              Disconnect
            </button>
          </>
        ) : hasError ? (
          <>
            <button
              onClick={() => onConnect(provider)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 transition-colors"
            >
              <RefreshCw className="w-3 h-3" />
              Reconnect
            </button>
            <button
              onClick={() => onDisconnect(connection!)}
              disabled={isDisconnecting === connection!.connection_id}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </>
        ) : (
          <div className="flex items-center gap-1.5">
            {provider.auth_mode === 'OAUTH2' && (
              <button
                onClick={() => onConfigure(provider)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/70 transition-colors"
                title="Set OAuth credentials"
              >
                <Settings className="w-3 h-3" />
              </button>
            )}
            <button
              onClick={() => onConnect(provider)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25 transition-all"
            >
              <Plug className="w-3 h-3" />
              Connect
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ConnectDialog({
  provider,
  onClose,
  onApiKeySubmit,
  onOAuthStart,
  loading,
  error,
}: {
  provider: IntegrationProvider;
  onClose: () => void;
  onApiKeySubmit: (apiKey: string, displayName: string) => void;
  onOAuthStart: () => void;
  loading: boolean;
  error: string | null;
}) {
  const [apiKey, setApiKey] = useState('');
  const [displayName, setDisplayName] = useState('');

  const isOAuth = provider.auth_mode === 'OAUTH2';

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] p-4 overflow-y-auto">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative glass-card p-6 w-full max-w-md animate-in">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
              <Plug className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">Connect {provider.display_name}</h3>
              <p className="text-xs text-white/40">{provider.auth_mode === 'API_KEY' ? 'Enter your API key' : 'OAuth2 authorization'}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/10">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5 mb-4">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {isOAuth ? (
          <div className="space-y-4">
            <p className="text-sm text-white/60">
              You will be redirected to {provider.display_name} to authorize access.
            </p>
            {provider.scope && (
              <div className="bg-white/5 rounded-xl border border-white/10 p-3">
                <p className="text-xs text-white/40 mb-1">Requested scopes:</p>
                <p className="text-xs text-white/60 font-mono break-all">{provider.scope}</p>
              </div>
            )}
            <button
              onClick={onOAuthStart}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25 transition-all disabled:opacity-50"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />}
              Authorize with {provider.display_name}
            </button>
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              onApiKeySubmit(apiKey, displayName);
            }}
            className="space-y-4"
          >
            <div>
              <label className="block text-xs font-medium text-white/50 mb-1.5">Display Name (optional)</label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder={`My ${provider.display_name}`}
                className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-white/50 mb-1.5">API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your API key..."
                required
                className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !apiKey.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25 transition-all disabled:opacity-50"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
              Connect
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

function ConfigureDialog({
  provider,
  onClose,
  onSubmit,
  loading,
  error,
}: {
  provider: IntegrationProvider;
  onClose: () => void;
  onSubmit: (clientId: string, clientSecret: string) => void;
  loading: boolean;
  error: string | null;
}) {
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] p-4 overflow-y-auto">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative glass-card p-6 w-full max-w-md animate-in">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-orange-500/20 border border-orange-500/30 flex items-center justify-center">
              <Settings className="w-5 h-5 text-orange-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">Configure {provider.display_name}</h3>
              <p className="text-xs text-white/40">Set OAuth client credentials</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/10">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5 mb-4">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <p className="text-sm text-white/50 mb-4">
          Enter the OAuth client ID and secret from your {provider.display_name} developer console. These will be encrypted and stored securely.
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit(clientId, clientSecret);
          }}
          className="space-y-4"
        >
          <div>
            <label className="block text-xs font-medium text-white/50 mb-1.5">Client ID</label>
            <input
              type="text"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="Enter OAuth client ID..."
              required
              className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-white/50 mb-1.5">Client Secret</label>
            <input
              type="password"
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              placeholder="Enter OAuth client secret..."
              required
              className="w-full bg-black/30 text-white border border-white/10 rounded-xl px-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !clientId.trim() || !clientSecret.trim()}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-gradient-to-r from-primary-500 to-accent-500 text-white hover:shadow-lg hover:shadow-primary-500/25 transition-all disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
            Save Credentials
          </button>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

interface IntegrationsManagerProps {
  apiBaseUrl: string;
}

export default function IntegrationsManager({ apiBaseUrl }: IntegrationsManagerProps) {
  const [providers, setProviders] = useState<IntegrationProvider[]>([]);
  const [connections, setConnections] = useState<IntegrationConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Dialog state
  const [connectingProvider, setConnectingProvider] = useState<IntegrationProvider | null>(null);
  const [configuringProvider, setConfiguringProvider] = useState<IntegrationProvider | null>(null);
  const [dialogLoading, setDialogLoading] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);

  const userId = getCurrentUserId();

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [provs, conns] = await Promise.all([
        listProviders(),
        listIntegrationConnections(userId),
      ]);
      setProviders(provs);
      setConnections(conns);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load apps');
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { load(); }, [load]);

  // Build connection map: provider_key -> connection
  const connectionMap = new Map<string, IntegrationConnection>();
  for (const conn of connections) {
    connectionMap.set(conn.provider_key, conn);
  }

  // Filter providers
  const visibleCategories = CATEGORIES;

  const filteredProviders = providers.filter((p) => {
    if (selectedCategory !== 'all' && p.app_category !== selectedCategory) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        p.display_name.toLowerCase().includes(q) ||
        p.provider_key.includes(q) ||
        (p.description?.toLowerCase().includes(q) ?? false) ||
        p.category.toLowerCase().includes(q) ||
        p.app_category.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const connectedCount = connections.filter((c) => c.status === 'active').length;

  // Handlers
  const handleConnect = (provider: IntegrationProvider) => {
    setConnectingProvider(provider);
    setDialogError(null);
  };

  const handleApiKeySubmit = async (apiKey: string, displayName: string) => {
    if (!connectingProvider) return;
    setDialogLoading(true);
    setDialogError(null);
    try {
      await createApiKeyConnection({
        user_id: userId,
        provider_key: connectingProvider.provider_key,
        display_name: displayName || connectingProvider.display_name,
        api_key: apiKey,
      });
      setConnectingProvider(null);
      await load();
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setDialogLoading(false);
    }
  };

  const handleOAuthStart = async () => {
    if (!connectingProvider) return;
    setDialogLoading(true);
    setDialogError(null);
    try {
      const redirectUri = `${window.location.origin}/api/v1/integrations/oauth/callback`;
      const { authorize_url } = await getOAuthAuthorizeUrl(
        connectingProvider.provider_key,
        userId,
        redirectUri,
      );
      window.open(authorize_url, '_blank', 'width=600,height=700');
      setConnectingProvider(null);
      // Poll for new connection after a delay
      setTimeout(() => load(), 5000);
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : 'Failed to start OAuth flow');
    } finally {
      setDialogLoading(false);
    }
  };

  const handleDisconnect = async (connection: IntegrationConnection) => {
    setDisconnecting(connection.connection_id);
    try {
      await deleteIntegrationConnection(connection.connection_id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect');
    } finally {
      setDisconnecting(null);
    }
  };

  const handleRefresh = async (connection: IntegrationConnection) => {
    try {
      await refreshIntegrationConnection(connection.connection_id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh connection');
    }
  };

  const handleConfigure = (provider: IntegrationProvider) => {
    setConfiguringProvider(provider);
    setDialogError(null);
  };

  const handleConfigureSubmit = async (clientId: string, clientSecret: string) => {
    if (!configuringProvider) return;
    setDialogLoading(true);
    setDialogError(null);
    try {
      await setProviderOAuthCredentials(configuringProvider.provider_key, clientId, clientSecret);
      setConfiguringProvider(null);
      await load();
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : 'Failed to save credentials');
    } finally {
      setDialogLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
              <Plug className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">Apps</h3>
              <p className="text-sm text-white/50">
                {providers.length} providers available
                {connectedCount > 0 && ` · ${connectedCount} connected`}
              </p>
            </div>
          </div>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/10 text-white/60 hover:text-white hover:bg-white/20 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Search */}
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search providers..."
            className="w-full bg-black/30 text-white border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm placeholder:text-white/20 focus:outline-none focus:border-primary-500/50"
          />
        </div>

        {/* Category filter */}
        <div className="flex items-center gap-2 flex-wrap">
          {visibleCategories.map((cat) => (
            <button
              key={cat.key}
              onClick={() => setSelectedCategory(cat.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedCategory === cat.key
                  ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg shadow-primary-500/20'
                  : 'bg-white/5 text-white/50 hover:text-white hover:bg-white/10'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-400/60 hover:text-red-400">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Loading */}
      {loading && providers.length === 0 && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-primary-400 animate-spin mr-3" />
          <span className="text-white/60">Loading apps...</span>
        </div>
      )}

      {/* Provider Grid */}
      {!loading && filteredProviders.length === 0 && (
        <div className="text-center py-12 text-white/40 text-sm">
          No providers found{searchQuery ? ` matching "${searchQuery}"` : ''}.
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filteredProviders.map((provider) => (
          <ProviderCard
            key={provider.provider_key}
            provider={provider}
            connection={connectionMap.get(provider.provider_key)}
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
            onRefresh={handleRefresh}
            onConfigure={handleConfigure}
            isDisconnecting={disconnecting}
          />
        ))}
      </div>

      {/* Connect dialog */}
      {connectingProvider && (
        <ConnectDialog
          provider={connectingProvider}
          onClose={() => setConnectingProvider(null)}
          onApiKeySubmit={handleApiKeySubmit}
          onOAuthStart={handleOAuthStart}
          loading={dialogLoading}
          error={dialogError}
        />
      )}

      {/* Configure OAuth credentials dialog */}
      {configuringProvider && (
        <ConfigureDialog
          provider={configuringProvider}
          onClose={() => setConfiguringProvider(null)}
          onSubmit={handleConfigureSubmit}
          loading={dialogLoading}
          error={dialogError}
        />
      )}
    </div>
  );
}

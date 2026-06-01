'use client';

import { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  Upload, Loader2, MessageSquare, MessageCircle, Database, Clock, Layers,
  Radio, FlaskConical, Settings, User, Sparkles, BarChart3, BookOpen, Menu, LogOut, Server,
} from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import type { TabId } from '@/components/Sidebar';
import DataList from '@/components/DataList';
import UploadForm from '@/components/UploadForm';
import Timeline from '@/components/Timeline';
import MemoryManager from '@/components/SessionManager';
import SettingsManager from '@/components/SettingsManager';
import DocsPage from '@/components/DocsPage';

import AIStudio from '@/components/AIStudio';
import ChannelChat from '@/components/ChannelChat';
import TelemetryDashboard from '@/components/TelemetryDashboard';
import InsightsDashboard from '@/components/InsightsDashboard';
import DataChat from '@/components/DataChat';
import McpPlayground from '@/components/McpPlayground';
import { getCurrentUserId, setCurrentUserInfo, getUser, createUser } from '@/lib/api';
import { isReadOnly } from '@/lib/read-only';
import { useAuth } from '@/lib/auth-context';
import { useProject } from '@/lib/project-context';
import LoginPage from '@/components/LoginPage';
import type { UserResponse } from '@/types';
import { FolderOpen, ChevronDown } from 'lucide-react';

const VALID_TABS: TabId[] = ['insights', 'ai', 'telemetry', 'data', 'timeline', 'memories', 'testing', 'docs', 'settings'];

const TAB_META: Record<TabId, { title: string; description: string; icon: React.ComponentType<{ className?: string }> }> = {
  insights:   { title: 'Insights',   description: 'Data, memory, viewpoint, and embedding breakdowns',  icon: BarChart3    },
  ai:         { title: 'AI Studio',  description: 'Search, models, routing, agents, and infrastructure', icon: Sparkles      },
  // chat tab moved into playground as "Knowledge Chat" sub-tab
  telemetry:  { title: 'Telemetry',  description: 'Pipeline traces and span-level observability',       icon: Radio         },
  data:       { title: 'Data',       description: 'Browse, search, and manage stored data items',       icon: Database     },
  timeline:   { title: 'Audit',      description: 'Chronological view of all data activity',            icon: Clock        },
  memories:   { title: 'Memories',   description: 'Organize data into timelines, conversations, and custom collections', icon: Layers },
  testing:    { title: 'Playground',  description: 'Send test webhooks and upload sample data',          icon: FlaskConical },
  docs:       { title: 'Docs',       description: 'Product overview, API reference, and FAQ',     icon: BookOpen },
  settings:   { title: 'Settings',   description: 'Profile, AI configuration, and integrations', icon: Settings },
};

const DEFAULT_USER_NAME = 'demo';
const DEFAULT_USER_ID = '00000000-0000-0000-0000-000000000001';

function TabSync({ onTab }: { onTab: (tab: TabId) => void }) {
  const searchParams = useSearchParams();
  useEffect(() => {
    const tab = searchParams.get('tab') as TabId | null;
    if (tab && VALID_TABS.includes(tab)) {
      onTab(tab);
    }
  }, [searchParams, onTab]);
  return null;
}

type MarketingTab = 'home' | 'docs';

function MarketingSite() {
  const [activeTab, setActiveTab] = useState<MarketingTab>('home');

  return (
    <main className="flex flex-col min-h-screen">
      {/* Top Navigation */}
      <nav className="sticky top-0 z-50 flex items-center justify-between px-6 py-3 border-b border-white/10 bg-slate-950/90 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 via-accent-500 to-pink-500 flex items-center justify-center shadow-lg shadow-primary-500/30">
            <Sparkles className="w-4.5 h-4.5 text-white" />
          </div>
          <span className="text-lg font-bold tracking-tight gradient-text">Mem-Dog</span>
        </div>
        <div className="flex items-center gap-1 p-1 bg-white/5 rounded-xl">
          {([
            { id: 'home' as const, label: 'Home' },
            { id: 'docs' as const, label: 'Docs' },
          ]).map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
                  : 'text-white/50 hover:text-white/70 hover:bg-white/5'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="w-[120px]" /> {/* Spacer for centering */}
      </nav>

      {/* Content */}
      <div className="flex-1">
        {activeTab === 'home' && <LoginPage />}
        {activeTab === 'docs' && (
          <div className="px-4 py-8 md:px-6">
            <DocsPage />
          </div>
        )}
      </div>
    </main>
  );
}

export default function Home() {
  const { session, loading: authLoading, signOut } = useAuth();
  const { orgs, projects, selectedOrgId, selectedProjectId, setSelectedOrgId, setSelectedProjectId } = useProject();
  const [activeTab, setActiveTab] = useState<TabId>('insights');
  const [testingSubTab, setTestingSubTab] = useState<'chat' | 'upload' | 'knowledge' | 'mcp'>('chat');
  const [refreshKey, setRefreshKey] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [ready, setReady] = useState(false);
  const [currentUser, setCurrentUser] = useState<Pick<UserResponse, 'user_id' | 'username' | 'display_name'> | null>(null);
  const initRef = useRef(false);

  // When session changes, update user info
  useEffect(() => {
    if (authLoading) return;

    // No session and Supabase is configured — don't init app
    const supabaseConfigured = !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!session && supabaseConfigured) {
      setReady(true);
      return;
    }

    if (initRef.current) return;
    initRef.current = true;

    (async () => {
      try {
        // If we have a Supabase session, use that user ID
        if (session?.user) {
          setCurrentUserInfo({
            user_id: session.user.id,
            username: session.user.email?.split('@')[0] || 'user',
            display_name: session.user.user_metadata?.full_name || session.user.email?.split('@')[0] || 'User',
          });
        }

        try {
          const userId = session?.user?.id || getCurrentUserId();
          let user;
          try {
            user = await getUser(userId);
          } catch (err: any) {
            // Auto-provision user in API on first Supabase login
            if (err.response?.status === 404 && session?.user) {
              let username = session.user.email?.split('@')[0] || 'user';
              const displayName = session.user.user_metadata?.full_name || username;
              try {
                user = await createUser({
                  user_id: session.user.id,
                  username,
                  email: session.user.email || '',
                  display_name: displayName,
                });
              } catch (createErr: any) {
                // Username taken — retry with suffix
                username = `${username}-${session.user.id.substring(0, 6)}`;
                user = await createUser({
                  user_id: session.user.id,
                  username,
                  email: session.user.email || '',
                  display_name: displayName,
                });
              }
            } else {
              throw err;
            }
          }
          setCurrentUserInfo({ user_id: user.user_id, username: user.username, display_name: user.display_name });
          setCurrentUser({ user_id: user.user_id, username: user.username, display_name: user.display_name });
        } catch {
          // User management disabled or API unreachable
          if (session?.user) {
            setCurrentUser({
              user_id: session.user.id,
              username: session.user.email?.split('@')[0] || 'user',
              display_name: session.user.user_metadata?.full_name || session.user.email?.split('@')[0] || 'User',
            });
          }
        }
      } catch {
        // API might be unreachable
      } finally {
        setReady(true);
      }
    })();
  }, [session, authLoading]);

  // Reset init ref when session changes (e.g. sign out → sign in as different user)
  useEffect(() => {
    initRef.current = false;
  }, [session?.user?.id]);

  // Read-only mode: render marketing site instead of full app
  if (isReadOnly()) {
    return <MarketingSite />;
  }

  // Show login page when Supabase is configured and no session
  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-6 h-6 text-primary-400 animate-spin" />
      </div>
    );
  }

  const supabaseConfigured = !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!session && supabaseConfigured) {
    return <LoginPage />;
  }

  // API base URL for components that need direct fetch
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || '/api';

  const handleUploadSuccess = () => {
    setRefreshKey(prev => prev + 1);
  };

  return (
    <main className="flex h-screen overflow-hidden">
      <Suspense fallback={null}>
        <TabSync onTab={setActiveTab} />
      </Suspense>

      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Top bar */}
        <div className="flex-shrink-0 flex items-center justify-between px-4 md:px-6 py-3 border-b border-white/10 bg-white/[0.02]">
          {/* Page context */}
          <div className="flex items-center gap-3 min-w-0">
            {/* Hamburger — mobile only */}
            <button
              onClick={() => setSidebarOpen(true)}
              className="md:hidden p-1.5 -ml-1 rounded-lg text-white/60 hover:text-white hover:bg-white/10 transition-colors flex-shrink-0"
            >
              <Menu className="w-5 h-5" />
            </button>
            {(() => {
              const meta = TAB_META[activeTab];
              const Icon = meta.icon;
              return (
                <>
                  <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0">
                    <Icon className="w-4 h-4 text-white/50" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-sm font-semibold text-white leading-tight">{meta.title}</h2>
                    <p className="text-[11px] text-white/35 leading-tight truncate hidden sm:block">{meta.description}</p>
                  </div>
                </>
              );
            })()}
          </div>

          {/* Project selector + User pill */}
          <div className="flex items-center gap-2 pl-4 flex-shrink-0">
            {/* Org / Project selector */}
            {orgs.length > 0 && (
              <div className="flex items-center gap-1.5">
                {orgs.length > 1 ? (
                  <select
                    value={selectedOrgId || ''}
                    onChange={e => setSelectedOrgId(e.target.value || null)}
                    className="text-xs bg-white/5 border border-white/[0.06] rounded-lg px-2 py-1.5 text-white/70 focus:outline-none focus:ring-1 focus:ring-primary-500/50 appearance-none cursor-pointer"
                    title="Organization"
                  >
                    {orgs.map(o => (
                      <option key={o.org_id} value={o.org_id} className="bg-slate-900">{o.display_name || o.name}</option>
                    ))}
                  </select>
                ) : (
                  <span className="text-xs text-white/40 hidden sm:inline" title={orgs[0]?.org_id}>
                    {orgs[0]?.display_name || orgs[0]?.name}
                  </span>
                )}
                <span className="text-white/15 hidden sm:inline">/</span>
                {projects.length > 0 ? (
                  <div className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-white/5 border border-white/[0.06]">
                    <FolderOpen className="w-3 h-3 text-white/40" />
                    <select
                      value={selectedProjectId || ''}
                      onChange={e => setSelectedProjectId(e.target.value || null)}
                      className="text-xs bg-transparent text-white/70 focus:outline-none appearance-none cursor-pointer pr-3"
                      title="Project"
                    >
                      {projects.map(p => (
                        <option key={p.project_id} value={p.project_id} className="bg-slate-900">{p.display_name || p.name}</option>
                      ))}
                    </select>
                    <ChevronDown className="w-3 h-3 text-white/30 -ml-2" />
                  </div>
                ) : (
                  <span className="text-xs text-white/30">no projects</span>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/[0.06]">
              <User className="w-3.5 h-3.5 text-white/40" />
              <span className="text-xs font-medium text-white/70 hidden sm:inline">
                {currentUser ? (currentUser.display_name || currentUser.username) : DEFAULT_USER_NAME}
              </span>
              <span className="text-white/15 hidden sm:inline">|</span>
              <span className="text-[10px] font-mono text-white/30" title="User ID">
                {(currentUser ? currentUser.user_id : DEFAULT_USER_ID).substring(0, 8)}
              </span>
              {session && (
                <button
                  onClick={() => signOut()}
                  className="ml-1 p-1 rounded text-white/30 hover:text-white/60 hover:bg-white/10 transition-colors"
                  title="Sign out"
                >
                  <LogOut className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4 md:px-6 md:py-8">
          {!ready ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-6 h-6 text-primary-400 animate-spin mr-3" />
              <span className="text-white/60">Connecting...</span>
            </div>
          ) : (
            <>
              {activeTab === 'data' && (
                <div className="animate-in">
                  <DataList key={refreshKey} />
                </div>
              )}

              {activeTab === 'timeline' && (
                <div className="animate-in">
                  <Timeline />
                </div>
              )}

              {activeTab === 'memories' && (
                <div className="animate-in">
                  <MemoryManager apiBaseUrl={apiBaseUrl} />
                </div>
              )}

              {activeTab === 'ai' && (
                <div className="animate-in">
                  <AIStudio apiBaseUrl={apiBaseUrl} />
                </div>
              )}

              {activeTab === 'insights' && (
                <div className="animate-in">
                  <InsightsDashboard />
                </div>
              )}

              {activeTab === 'telemetry' && (
                <div className="animate-in">
                  <TelemetryDashboard />
                </div>
              )}

              {activeTab === 'testing' && (
                <div className="space-y-6 animate-in">
                  {/* Testing Sub-tab Toggle */}
                  <div className="flex items-center gap-2 p-1 bg-white/5 rounded-xl max-w-lg">
                    {([
                      { id: 'chat'       as const, label: 'Channel to Webhook',  icon: MessageSquare },
                      { id: 'upload'     as const, label: 'Data Insert',         icon: Upload        },
                      { id: 'knowledge'  as const, label: 'Knowledge Chat',      icon: MessageCircle },
                      { id: 'mcp'        as const, label: 'MCP',                 icon: Server        },
                    ]).map(tab => (
                      <button
                        key={tab.id}
                        onClick={() => setTestingSubTab(tab.id)}
                        className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all ${
                          testingSubTab === tab.id
                            ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-lg'
                            : 'text-white/50 hover:text-white/70 hover:bg-white/5'
                        }`}
                      >
                        <tab.icon className="w-4 h-4" />
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  {testingSubTab === 'chat' && <ChannelChat />}

                  {testingSubTab === 'upload' && (
                    <UploadForm onSuccess={handleUploadSuccess} />
                  )}

                  {testingSubTab === 'knowledge' && (
                    <div className="h-[calc(100vh-200px)]">
                      <DataChat />
                    </div>
                  )}

                  {testingSubTab === 'mcp' && <McpPlayground />}

                </div>
              )}

              {activeTab === 'docs' && (
                <div className="animate-in">
                  <DocsPage />
                </div>
              )}

              {activeTab === 'settings' && (
                <div className="animate-in">
                  <SettingsManager apiBaseUrl={apiBaseUrl} />
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <footer className="border-t border-white/[0.06] flex-shrink-0">
          <div className="px-6 py-2.5 flex items-center justify-between text-[11px] text-white/25">
            <span>Mem-Dog</span>
            <span className="font-mono">
              {currentUser ? currentUser.user_id : DEFAULT_USER_ID}
            </span>
          </div>
        </footer>
      </div>
    </main>
  );
}

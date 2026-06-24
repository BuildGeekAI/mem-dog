import * as fs from 'fs';
import * as path from 'path';
import { createRequire } from 'module';

const RECORDING_ROOT = path.resolve(__dirname);
const REPO_ROOT = path.resolve(RECORDING_ROOT, '../../..');

/** Relative RECORDING_OUTPUT_DIR is resolved from repo root (not process.cwd()). */
function resolveRecordingOutputDir(raw: string | undefined): string {
  const fallback = path.join(RECORDING_ROOT, 'recordings');
  if (!raw || !raw.trim()) return fallback;
  const trimmed = raw.trim();
  return path.isAbsolute(trimmed) ? trimmed : path.resolve(REPO_ROOT, trimmed);
}

function loadRecordingEnv(): void {
  const envCandidates = [
    path.join(REPO_ROOT, '.env.recording'),
    path.join(RECORDING_ROOT, '.env.recording'),
  ];

  const envPath = envCandidates.find((p) => fs.existsSync(p));
  if (!envPath) return;

  // Resolve dotenv from the command's working directory (e.g. ui/).
  try {
    const requireFromCwd = createRequire(path.join(process.cwd(), 'package.json'));
    const dotenv = requireFromCwd('dotenv') as { config: (opts: { path: string }) => void };
    dotenv.config({ path: envPath });
  } catch {
    // No hard dependency on dotenv: scripts still run with process env.
  }
}

loadRecordingEnv();

export type RecordingProfile = 'gcp' | 'local';

export interface RecordingConfig {
  profile: RecordingProfile;
  baseUrl: string;
  apiUrl: string;
  gatewayUrl: string;
  email: string;
  password: string;
  outputDir: string;
  sessionStoragePath: string;
  seedStatePath: string;
  slowMo: number;
  videoSettings: { width: number; height: number };
  timing: Record<string, number>;
  /** Max waits for app shell (local uses shorter caps). */
  appTimeouts: {
    sidebarMs: number;
    connectingMs: number;
    appSettleMs: number;
    sidebarClickMs: number;
  };
  selectors: {
    login: { email: string; password: string; submit: string };
    sidebar: (tab: string) => string;
    playground: { channel: string; upload: string; knowledge: string; mcp: string };
    upload: { textarea: string; submit: string; success: string };
    knowledgeChat: { input: string; send: string; hybridMode: string };
    channelWebhook: { gatewayInput: string; messageInput: string; send: string };
    settings: { apiKeysTab: string; keyName: string; createButton: string };
  };
}

const profile = (process.env.RECORDING_PROFILE || 'gcp') as RecordingProfile;
const isLocal = profile === 'local';
const scale = isLocal ? 0.7 : 1;

function ms(gcp: number): number {
  return Math.round(gcp * scale);
}

const GCP_TIMING = {
  login: 20000,
  insights: 25000,
  orgProject: 20000,
  marketingLanding: 30000,
  inAppDocs: 40000,
  standaloneDocs: 25000,
  dataInsertText: 40000,
  dataInsertFile: 35000,
  dataInsertUrl: 35000,
  dataInsertMedia: 50000,
  dataList: 30000,
  dataDetail: 25000,
  dataEdit: 35000,
  dataVersions: 40000,
  dataDelete: 25000,
  memoryOverview: 30000,
  memoryCreate: 40000,
  memoryLinked: 25000,
  auditTimeline: 40000,
  knowledgeChat: 90000,
  graphSearch: 60000,
  dataAiQuery: 50000,
  dataAiGenerate: 120000,
  aiStudioSearch: 30000,
  aiStudioModels: 45000,
  aiStudioRouting: 35000,
  aiStudioAgents: 35000,
  aiStudioInfra: 25000,
  channelWebhook: 75000,
  telemetry: 35000,
  insightsDelta: 15000,
  settingsProfile: 25000,
  settingsOrgs: 40000,
  settingsIntegrations: 45000,
  settingsWebhooks: 35000,
  settingsApiKeys: 30000,
  mcpPlayground: 50000,
  swagger: 25000,
  defaultDelay: 1000,
  navigationWait: 1000,
  scrollDelay: 1000,
  hoverDelay: 1000,
};

const timing: Record<string, number> = {};
for (const [key, value] of Object.entries(GCP_TIMING)) {
  timing[key] = ms(value);
}

/** Pause between recording actions (local and GCP use the same 1s pacing). */
timing.defaultDelay = 1000;
timing.navigationWait = 1000;
timing.scrollDelay = 1000;
timing.hoverDelay = 1000;

const appTimeouts = isLocal
  ? { sidebarMs: 12_000, connectingMs: 5_000, appSettleMs: 200, sidebarClickMs: 2_500 }
  : { sidebarMs: 60_000, connectingMs: 90_000, appSettleMs: 800, sidebarClickMs: 8_000 };

export const config: RecordingConfig = {
  profile,
  baseUrl: process.env.RECORDING_BASE_URL || (isLocal ? 'http://localhost:3000' : ''),
  apiUrl: process.env.RECORDING_API_URL || (isLocal ? 'http://localhost:8080' : ''),
  gatewayUrl: process.env.RECORDING_GATEWAY_URL || (isLocal ? 'http://localhost:8070' : ''),
  email: process.env.RECORDING_EMAIL || '',
  password: process.env.RECORDING_PASSWORD || '',
  outputDir: resolveRecordingOutputDir(process.env.RECORDING_OUTPUT_DIR),
  sessionStoragePath: path.join(RECORDING_ROOT, 'recordings', '.session'),
  seedStatePath: path.join(RECORDING_ROOT, 'recordings', '.seed-state.json'),
  slowMo: isLocal ? 80 : 350,
  videoSettings: { width: 1920, height: 1080 },
  timing,
  appTimeouts,
  selectors: {
    login: {
      email: '[data-testid="login-email"]',
      password: '[data-testid="login-password"]',
      submit: '[data-testid="login-submit"]',
    },
    sidebar: (tab: string) => `[data-testid="sidebar-tab-${tab}"]`,
    playground: {
      channel: '[data-testid="playground-tab-channel"]',
      upload: '[data-testid="playground-tab-upload"]',
      knowledge: '[data-testid="playground-tab-knowledge"]',
      mcp: '[data-testid="playground-tab-mcp"]',
    },
    upload: {
      textarea: '[data-testid="upload-textarea"]',
      submit: '[data-testid="upload-submit"]',
      success: '.alert-success',
    },
    knowledgeChat: {
      input: '[data-testid="knowledge-chat-input"]',
      send: '[data-testid="knowledge-chat-send"]',
      hybridMode: 'button:has-text("Hybrid")',
    },
    channelWebhook: {
      gatewayInput: '[data-testid="channel-gateway-url"]',
      messageInput: '[data-testid="channel-message-input"]',
      send: '[data-testid="channel-send"]',
    },
    settings: {
      apiKeysTab: '[data-testid="settings-tab-api-keys"]',
      keyName: '[data-testid="api-key-name"]',
      createButton: '[data-testid="api-key-create"]',
    },
  },
};

export function sceneDuration(timingKey: keyof typeof GCP_TIMING): number {
  return config.timing[timingKey] ?? config.timing.defaultDelay;
}

/** Standard 1s pause between steps in every scene. */
export function scenePauseMs(): number {
  const fromEnv = process.env.RECORDING_PAUSE_MS;
  if (fromEnv !== undefined && fromEnv !== '') {
    const n = Number(fromEnv);
    if (!Number.isNaN(n) && n >= 0) return n;
  }
  return config.timing.defaultDelay;
}

/** Max scene length — all scenes pad only up to this total (no 20–90s tails). */
export function sceneMaxDurationMs(): number {
  const fromEnv =
    process.env.RECORDING_SCENE_MS ?? process.env.RECORDING_STUB_SCENE_MS;
  if (fromEnv !== undefined && fromEnv !== '') {
    const n = Number(fromEnv);
    if (!Number.isNaN(n) && n > 0) return n;
  }
  return 4000;
}

/** Scene target for fillSceneDuration / paceSceneRemainder (timingKey kept for logs only). */
export function sceneTargetDurationMs(
  _timingKey?: keyof typeof GCP_TIMING,
): number {
  return sceneMaxDurationMs();
}

/** @deprecated Use sceneMaxDurationMs */
export function sceneStubDurationMs(): number {
  return sceneMaxDurationMs();
}

export function requiresAuth(): boolean {
  return config.profile === 'gcp' || !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
}

if (config.profile === 'gcp' && !config.baseUrl) {
  console.warn('⚠️  RECORDING_BASE_URL is required for GCP profile');
}
if (config.profile === 'gcp' && (!config.email || !config.password)) {
  console.warn('⚠️  RECORDING_EMAIL and RECORDING_PASSWORD recommended for GCP profile');
}

import type { SceneDefinition } from './types';
import { profilesFor } from './types';
import { sceneA0 } from './a0-login';
import { sceneA1 } from './a1-insights';
import { sceneB1 } from './b1-text-ingest';
import { sceneB5 } from './b5-browse-list';
import { sceneD1 } from './d1-knowledge-chat';
import { sceneE1 } from './e1-channel-webhook';
import { sceneE2 } from './e2-telemetry';
import { sceneF5 } from './f5-api-keys';
import { createStubScene } from './stub-factory';
import { config } from '../config';

export const ALL_SCENES: SceneDefinition[] = [
  sceneA0,
  sceneA1,
  createStubScene('A2', 'Org / project switcher', 'orgProject', { tab: 'insights' }),
  createStubScene('A3', 'Marketing landing (logged out)', 'marketingLanding', { url: '/' }, {
    profiles: ['gcp'],
    optional: true,
  }),
  createStubScene('A4', 'In-app docs', 'inAppDocs', { tab: 'docs' }),
  createStubScene('A5', 'Docs (in-app)', 'standaloneDocs', { tab: 'docs' }, { optional: true }),

  sceneB1,
  createStubScene('B2', 'File ingest', 'dataInsertFile', { tab: 'testing', playground: 'upload' }),
  createStubScene('B3', 'URL ingest', 'dataInsertUrl', { tab: 'testing', playground: 'upload' }),
  createStubScene('B4', 'Camera / voice ingest', 'dataInsertMedia', { tab: 'testing', playground: 'upload' }, {
    optional: true,
  }),
  sceneB5,
  createStubScene('B6', 'Data detail', 'dataDetail', { tab: 'data' }),
  createStubScene('B7', 'Edit data → v2', 'dataEdit', { tab: 'data' }),
  createStubScene('B8', 'Version history', 'dataVersions', { tab: 'data' }),
  createStubScene('B9', 'Delete data', 'dataDelete', { tab: 'data' }),

  createStubScene('C1', 'Memory overview', 'memoryOverview', { tab: 'memories' }),
  createStubScene('C2', 'Create memory', 'memoryCreate', { tab: 'memories' }),
  createStubScene('C3', 'Linked data', 'memoryLinked', { tab: 'memories' }),
  createStubScene('C4', 'Audit timeline', 'auditTimeline', { tab: 'timeline' }),

  sceneD1,
  createStubScene('D2', 'Graph search', 'graphSearch', { tab: 'testing', playground: 'knowledge' }, {
    optional: true,
  }),
  createStubScene('D3', 'Per-item AI query', 'dataAiQuery', { tab: 'data' }),
  createStubScene('D4', 'Generate enrichment', 'dataAiGenerate', { tab: 'data' }),
  createStubScene('D5', 'AI Studio Search', 'aiStudioSearch', { tab: 'ai' }),
  createStubScene('D6', 'Model Garden', 'aiStudioModels', { tab: 'ai' }),
  createStubScene('D7', 'Smart routing', 'aiStudioRouting', { tab: 'ai' }),
  createStubScene('D8', 'Agents', 'aiStudioAgents', { tab: 'ai' }),
  createStubScene('D9', 'Infrastructure', 'aiStudioInfra', { tab: 'ai' }),

  sceneE1,
  sceneE2,
  createStubScene('E3', 'Insights delta', 'insightsDelta', { tab: 'insights' }),

  createStubScene('F1', 'Profile settings', 'settingsProfile', { tab: 'settings', settingsLabel: 'Profile' }),
  createStubScene('F2', 'Organizations', 'settingsOrgs', { tab: 'settings', settingsLabel: 'Organizations' }),
  createStubScene('F3', 'Integrations', 'settingsIntegrations', { tab: 'settings', settingsLabel: 'Apps' }, {
    optional: true,
  }),
  createStubScene('F4', 'Webhooks', 'settingsWebhooks', { tab: 'settings', settingsLabel: 'Webhooks' }),
  sceneF5,

  createStubScene('G1', 'MCP Playground', 'mcpPlayground', { tab: 'testing', playground: 'mcp' }),
  createStubScene('G2', 'Swagger / API docs', 'swagger', { tab: 'docs' }, { optional: true }),
];

export function scenesForProfile(profile = config.profile): SceneDefinition[] {
  return ALL_SCENES.filter((s) => profilesFor(s).includes(profile));
}

export function getSceneById(id: string): SceneDefinition | undefined {
  return ALL_SCENES.find((s) => s.id.toUpperCase() === id.toUpperCase());
}

export const NARRATION: Record<string, string> = {
  A0: 'Sign in to Mem-Dog with your recording account to access the full data and memory platform.',
  A1: 'The Insights dashboard summarizes your data, memories, embeddings, and AI usage at a glance.',
  B1: 'Ingest structured text through the Playground Data Insert flow with tags and memory associations.',
  B5: 'Browse and search your data catalog with pagination, tags, and quick navigation to details.',
  D1: 'Ask questions in Knowledge Chat using hybrid search with citations from your ingested content.',
  E1: 'Send a channel message through the webhook gateway to trigger the 40-agent enrichment pipeline.',
  E2: 'Inspect pipeline telemetry and traces to see how messages flow through NATS and the API.',
  F5: 'Create personal API keys for programmatic access to Mem-Dog REST endpoints.',
};

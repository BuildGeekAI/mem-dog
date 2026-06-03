import * as fs from 'fs';
import * as path from 'path';
import { config } from './config';
import type { SeedState } from './helpers';

const TAG_PREFIX = 'recording-seed';

export interface SeedOptions {
  apiUrl: string;
  userId?: string;
  authHeader?: string;
}

async function apiFetch(
  opts: SeedOptions,
  method: string,
  apiPath: string,
  init?: RequestInit,
): Promise<Response> {
  const url = `${opts.apiUrl.replace(/\/$/, '')}${apiPath}`;
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string>),
  };
  if (opts.userId) headers['X-User-ID'] = opts.userId;
  if (opts.authHeader) headers['Authorization'] = opts.authHeader;
  return fetch(url, { method, ...init, headers });
}

async function findByTag(opts: SeedOptions, tag: string): Promise<string | null> {
  const user = opts.userId || 'demo';
  const res = await apiFetch(opts, 'GET', `/api/v1/data?user=${encodeURIComponent(user)}&limit=100`);
  if (!res.ok) return null;
  const body = (await res.json()) as { items?: Array<{ data_id: string; tags?: string[] }> };
  const item = body.items?.find((i) => i.tags?.includes(tag));
  return item?.data_id ?? null;
}

export async function runSeed(opts: SeedOptions): Promise<SeedState> {
  const userId = opts.userId || process.env.RECORDING_USER_ID || 'demo';
  const state: SeedState = { tags: [] };

  console.log(`🌱 Seeding API at ${opts.apiUrl} (user: ${userId})`);

  const health = await apiFetch(opts, 'GET', '/');
  if (!health.ok) {
    throw new Error(`API health check failed: HTTP ${health.status}`);
  }

  const tagVersioned = `${TAG_PREFIX}-versioned`;
  const tagRag = `${TAG_PREFIX}-rag`;
  const tagList = `${TAG_PREFIX}-list`;

  let versionedId = await findByTag(opts, tagVersioned);
  if (!versionedId) {
    const fd = new FormData();
    fd.append('content', JSON.stringify({ seed: 'versioned', v: 1 }));
    fd.append('name', 'Recording Versioned Item');
    fd.append('tags', tagVersioned);
    fd.append('owner_user_id', userId);
    const res = await apiFetch(opts, 'POST', '/api/v1/data', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`Create versioned data failed: ${res.status}`);
    const created = (await res.json()) as { data_id: string };
    versionedId = created.data_id;

    for (const v of [2, 3]) {
      const upd = new FormData();
      upd.append('content', JSON.stringify({ seed: 'versioned', v }));
      upd.append('user_id', userId);
      await apiFetch(opts, 'PUT', `/api/v1/data/${versionedId}`, { method: 'PUT', body: upd });
    }
    console.log(`  ✓ Versioned item ${versionedId} (v1–v3)`);
  } else {
    console.log(`  ↳ Versioned item exists: ${versionedId}`);
  }
  state.versionedDataId = versionedId;
  state.tags?.push(tagVersioned);

  let ragId = await findByTag(opts, tagRag);
  if (!ragId) {
    const ragContent = [
      'Mem-Dog is a multi-channel data ingestion and AI enrichment platform.',
      'It supports vector search, hybrid BM25+vector retrieval, and knowledge graph queries.',
      'Webhook pipeline runs 40 typed sub-agents for classification and embedding.',
    ].join('\n');
    const fd = new FormData();
    fd.append('content', ragContent);
    fd.append('name', 'Recording RAG Corpus');
    fd.append('description', 'Seed text for Knowledge Chat demo scenes');
    fd.append('tags', `${tagRag},demo,rag`);
    fd.append('owner_user_id', userId);
    const res = await apiFetch(opts, 'POST', '/api/v1/data', { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`Create RAG data failed: ${res.status}`);
    ragId = ((await res.json()) as { data_id: string }).data_id;
    console.log(`  ✓ RAG item ${ragId}`);
  } else {
    console.log(`  ↳ RAG item exists: ${ragId}`);
  }
  state.ragDataId = ragId;
  state.tags?.push(tagRag);

  const listIds: string[] = [];
  for (let i = 1; i <= 5; i++) {
    const tag = `${tagList}-${i}`;
    let id = await findByTag(opts, tag);
    if (!id) {
      const fd = new FormData();
      fd.append('content', JSON.stringify({ seed: 'list', index: i }));
      fd.append('name', `Recording List Item ${i}`);
      fd.append('tags', tag);
      fd.append('owner_user_id', userId);
      const res = await apiFetch(opts, 'POST', '/api/v1/data', { method: 'POST', body: fd });
      if (!res.ok) continue;
      id = ((await res.json()) as { data_id: string }).data_id;
    }
    if (id) listIds.push(id);
  }
  state.listDataIds = listIds;
  console.log(`  ✓ List seed items: ${listIds.length}`);

  const memRes = await apiFetch(
    opts,
    'GET',
    `/api/v1/memories?user_id=${encodeURIComponent(userId)}&memory_type=timeline&limit=5`,
  );
  if (memRes.ok) {
    const memBody = (await memRes.json()) as { items?: Array<{ memory_id: string }> };
    if (memBody.items?.length) {
      console.log(`  ✓ Timeline memories: ${memBody.items.length}`);
    }
  }

  await warmUserStats(opts);

  const outDir = path.dirname(config.seedStatePath);
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(config.seedStatePath, JSON.stringify(state, null, 2));
  console.log(`💾 Seed state written to ${config.seedStatePath}`);
  return state;
}

/** Pre-compute cached stats so Insights loads quickly during recording. */
export async function warmUserStats(opts: SeedOptions): Promise<void> {
  const userId = opts.userId || process.env.RECORDING_USER_ID || '00000000-0000-0000-0000-000000000001';
  const res = await apiFetch(
    opts,
    'POST',
    `/api/v1/stats/refresh/users/${encodeURIComponent(userId)}`,
  );
  if (!res.ok) {
    console.warn(`  ⚠️ Stats warm-up failed: HTTP ${res.status}`);
    return;
  }
  console.log(`  ✓ Insights stats pre-computed for ${userId}`);
}

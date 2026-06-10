import { config } from './config';

interface Check {
  name: string;
  url: string;
  ok?: boolean;
  status?: number;
  error?: string;
}

async function checkUrl(name: string, url: string): Promise<Check> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
    return { name, url, ok: res.ok, status: res.status };
  } catch (err) {
    return {
      name,
      url,
      ok: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

async function main(): Promise<void> {
  const gateway = (config.gatewayUrl || process.env.RECORDING_GATEWAY_URL || '').replace(/\/$/, '');
  const baseUrl = config.baseUrl;

  console.log('🔍 Mem-Dog GCP recording preflight\n');

  if (!baseUrl) {
    console.error('❌ RECORDING_BASE_URL is required');
    process.exit(1);
  }

  const checks: Check[] = [
    await checkUrl('UI (Cloud Run)', baseUrl),
  ];

  if (gateway) {
    checks.push(
      await checkUrl('Gateway health', `${gateway}/health`),
      await checkUrl('GKE API health', `${gateway}/gke-api/health`),
      await checkUrl('Auth health', `${gateway}/auth/v1/health`),
    );
  } else {
    console.warn('⚠️  RECORDING_GATEWAY_URL not set — skipping gateway checks');
  }

  let failed = 0;
  for (const c of checks) {
    if (c.ok) {
      console.log(`  ✓ ${c.name} → HTTP ${c.status}`);
    } else {
      failed++;
      console.log(`  ✗ ${c.name} → ${c.error || `HTTP ${c.status}`}`);
      console.log(`    ${c.url}`);
    }
  }

  if (!config.email || !config.password) {
    console.warn('\n⚠️  RECORDING_EMAIL / RECORDING_PASSWORD not set (required for A0 Login)');
  }

  console.log(failed === 0 ? '\n✅ Preflight passed' : `\n❌ ${failed} check(s) failed`);
  process.exit(failed > 0 ? 1 : 0);
}

main();

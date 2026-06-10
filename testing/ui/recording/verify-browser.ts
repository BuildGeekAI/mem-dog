#!/usr/bin/env npx tsx
import { createRequire } from 'module';
import * as path from 'path';
import {
  buildRecordingLaunchOptions,
  getRecordingBrowserChannel,
  verifyRecordingBrowserLaunch,
} from './browser-launch';

function getPlaywrightVersion(): string {
  try {
    const requireFromCwd = createRequire(path.join(process.cwd(), 'package.json'));
    return requireFromCwd('playwright/package.json').version as string;
  } catch {
    return 'unknown';
  }
}

async function main(): Promise<void> {
  const channel = getRecordingBrowserChannel();
  const opts = buildRecordingLaunchOptions({ headless: true });
  console.log('🔍 Verifying Playwright browser launch');
  console.log(`   playwright: ${getPlaywrightVersion()}`);
  console.log(`   channel: ${channel ?? 'bundled chromium'}`);
  if (!channel && opts.args) {
    console.log(`   args: ${opts.args.join(' ')}`);
  }

  await verifyRecordingBrowserLaunch();
  console.log('✅ Browser launch OK');
}

main().catch((err) => {
  console.error('❌ Browser verification failed:', err instanceof Error ? err.message : err);
  process.exit(1);
});

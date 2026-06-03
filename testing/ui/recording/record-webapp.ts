#!/usr/bin/env npx tsx
import type { Browser, BrowserContext, Page } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';
import * as readline from 'readline';
import { config } from './config';
import {
  ensureBundledChromiumInstalled,
  isMissingBrowserExecutable,
  launchRecordingBrowser,
  printInstallBrowsersHelp,
} from './browser-launch';
import {
  authenticate,
  delay,
  ensureOutputDir,
  ensureRecordingUser,
  loadSession,
  saveSession,
  setActivePage,
  waitForAppReady,
  waitForMainAppContent,
  warmInsightsStatsApi,
  type SceneResult,
} from './helpers';
import { agentLog } from './agent-log';
import { debug, debugNext, debugWait, isRecordingDebug, setDebugScene } from './debug';
import {
  attachRecordingCursorOnNavigation,
  ensureRecordingCursor,
  installRecordingCursor,
} from './recording-cursor';
import { NARRATION, scenesForProfile } from './scenes';

/** Open the first scene's tab instead of default Insights when possible. */
function recordingStartUrl(firstSceneId: string): string {
  const tabByScene: Record<string, string> = {
    A1: 'insights',
    A2: 'insights',
    A4: 'docs',
    E3: 'insights',
    B1: 'testing',
    B2: 'testing',
    B3: 'testing',
    B4: 'testing',
    B5: 'data',
    B6: 'data',
    B7: 'data',
    B8: 'data',
    B9: 'data',
    C1: 'memories',
    C2: 'memories',
    C3: 'memories',
    C4: 'timeline',
    D1: 'testing',
    D2: 'testing',
    D3: 'data',
    D4: 'data',
    D5: 'ai',
    D6: 'ai',
    D7: 'ai',
    D8: 'ai',
    D9: 'ai',
    E1: 'testing',
    E2: 'telemetry',
    F1: 'settings',
    F2: 'settings',
    F3: 'settings',
    F4: 'settings',
    F5: 'settings',
    G1: 'testing',
    G2: 'docs',
    A5: 'docs',
  };
  const tab = tabByScene[firstSceneId];
  const base = config.baseUrl.replace(/\/$/, '');
  return tab ? `${base}/?tab=${tab}` : base || config.baseUrl;
}

function promptSceneSelection(): Promise<Set<string>> {
  const available = scenesForProfile();
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    console.log('\n📋 Select scenes to record (Mem-Dog):');
    available.forEach((s, i) => {
      const opt = s.optional ? ' [optional]' : '';
      console.log(`  ${String(i + 1).padStart(2)}. ${s.id} — ${s.title}${opt}`);
    });
    console.log(`  ${String(available.length + 1).padStart(2)}. All scenes for ${config.profile} profile`);
    console.log('\nEnter scene numbers or IDs (comma-separated), e.g. 1,5,8 or A1,B1,D1:');
    if (config.profile === 'local') {
      console.log('  (local profile: scene 1 is A1 Insights; A0 Login is GCP-only)');
    }

    rl.question('> ', (answer) => {
      rl.close();
      const selected = new Set<string>();
      const input = answer.trim();
      if (!input) {
        resolve(selected);
        return;
      }

      if (input.toLowerCase() === 'all' || input === String(available.length + 1)) {
        available.forEach((s) => selected.add(s.id));
        resolve(selected);
        return;
      }

      for (const part of input.split(',').map((p) => p.trim())) {
        const num = parseInt(part, 10);
        if (!Number.isNaN(num) && num >= 1 && num <= available.length) {
          selected.add(available[num - 1].id);
          continue;
        }
        const match = available.find(
          (s) => s.id.toLowerCase() === part.toLowerCase() || s.title.toLowerCase() === part.toLowerCase(),
        );
        if (match) selected.add(match.id);
      }
      resolve(selected);
    });
  });
}

async function main(): Promise<void> {
  console.log('🎬 Mem-Dog Demo Recording');
  console.log(`   Profile: ${config.profile}`);
  console.log(`   Base URL: ${config.baseUrl || '(not set)'}`);
  if (isRecordingDebug()) {
    console.log('   Debug: ON (set RECORDING_DEBUG=0 to disable)');
  }
  console.log('═══════════════════════════════════════\n');

  const selectedIds = await promptSceneSelection();
  if (selectedIds.size === 0) {
    console.log('\n⚠️  No scenes selected. Exiting.');
    return;
  }

  const scenes = scenesForProfile().filter((s) => selectedIds.has(s.id));
  const needsAuth = scenes.some((s) => s.id !== 'A0' && s.id !== 'A3');
  const includesLogin = selectedIds.has('A0');

  console.log(`\n✅ Recording: ${scenes.map((s) => s.id).join(', ')}`);
  ensureBundledChromiumInstalled();
  ensureOutputDir();

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
  const narrationPath = path.join(config.outputDir, `narration-data-${timestamp}.json`);
  const narrationLog: Array<{
    sceneId: string;
    title: string;
    narration: string;
    durationMs: number;
    success: boolean;
    waitCut?: SceneResult['waitCut'];
  }> = [];

  let browser: Browser | null = null;
  let context: BrowserContext | null = null;
  let page: Page | null = null;

  try {
    debugNext('launch browser', process.env.RECORDING_BROWSER_CHANNEL || 'bundled chromium');
    browser = await launchRecordingBrowser({
      headless: false,
      slowMo: config.slowMo,
    });
    // #region agent log
    agentLog('H5', 'record-webapp.ts:main', 'browser_launched', { slowMo: config.slowMo });
    // #endregion

    context = await browser.newContext({
      viewport: config.videoSettings,
      recordVideo: {
        dir: config.outputDir,
        size: config.videoSettings,
      },
      userAgent:
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      hasTouch: false,
    });

    await installRecordingCursor(context);

    page = await context.newPage();
    attachRecordingCursorOnNavigation(page);
    // Local headed recording: UI is often visible before Playwright isVisible() passes; avoid 3s false negatives.
    page.setDefaultTimeout(config.profile === 'local' ? 10_000 : 30_000);
    setActivePage(page);

    if (config.apiUrl) {
      await ensureRecordingUser(config.apiUrl);
    }

    const hasSession = await loadSession(context);
    if (!hasSession && needsAuth && !includesLogin) {
      const ok = await authenticate(page, context);
      if (!ok) throw new Error('Authentication required');
    } else if (!hasSession && includesLogin) {
      await page.goto(config.baseUrl, { waitUntil: 'domcontentloaded' });
    } else {
      const startUrl = recordingStartUrl(scenes[0].id);
      debugNext('goto session start URL', startUrl);
      await page.goto(startUrl, { waitUntil: 'domcontentloaded' });
      await ensureRecordingCursor(page);
      if (!includesLogin) {
        await waitForAppReady(page);
        if (startUrl.includes('tab=insights')) {
          await waitForMainAppContent(page);
        }
      }
    }

    if (selectedIds.has('A1') && config.apiUrl) {
      console.log('\n📊 Pre-warming insights stats (avoids long loading spinner)...');
      await warmInsightsStatsApi(config.apiUrl);
    }

    for (const scene of scenes) {
      console.log(`\n── ${scene.id}: ${scene.title} ──`);
      setDebugScene(scene.id);
      debug(`── scene start (timingKey=${scene.timingKey}) ──`);
      if (scene.id === 'A0') {
        const ok = await authenticate(page, context);
        if (!ok) {
          narrationLog.push({
            sceneId: scene.id,
            title: scene.title,
            narration: NARRATION[scene.id] || '',
            durationMs: 0,
            success: false,
          });
          continue;
        }
      }

      debugNext(`run scene.record()`, scene.id);
      const result = await scene.record(page);
      narrationLog.push({
        sceneId: scene.id,
        title: scene.title,
        narration: NARRATION[scene.id] || `Scene ${scene.id}: ${scene.title}`,
        durationMs: result.duration,
        success: result.success,
        waitCut: result.waitCut,
      });

      if (result.waitCut) {
        console.log(
          `  ✂️  wait-cut: ${result.waitCut.startOffsetMs}ms – ${result.waitCut.endOffsetMs}ms`,
        );
      }
      if (!result.success) {
        console.error(`  ❌ ${result.error}`);
      } else {
        console.log(`  ✅ ${(result.duration / 1000).toFixed(1)}s`);
      }
      const gap = config.timing.defaultDelay;
      debugWait('gap before next scene', { timeoutMs: gap, next: 'next scene or close browser' });
      await delay(gap);
    }

    await saveSession(context);
    fs.writeFileSync(narrationPath, JSON.stringify({ recordedAt: timestamp, scenes: narrationLog }, null, 2));
    console.log(`\n📝 Narration export: ${narrationPath}`);
  } catch (err) {
    if (isMissingBrowserExecutable(err)) {
      printInstallBrowsersHelp();
      process.exit(1);
    }
    throw err;
  } finally {
    if (page && context) {
      const video = page.video();
      await page.close();
      if (video) {
        const videoPath = await video.path();
        console.log(`\n📹 Video saved: ${videoPath}`);
      }
    }
    await context?.close();
    await browser?.close();
  }

  console.log('\n✅ Recording session complete');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

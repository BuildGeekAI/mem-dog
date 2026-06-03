import type { Page } from 'playwright';
import { agentLog } from '../agent-log';
import { config, sceneTargetDurationMs } from '../config';
import { debug, debugDone, debugInsightsState, debugNext } from '../debug';
import type { SceneResult } from '../helpers';
import {
  delay,
  goToTab,
  insightsLooksReady,
  paceSceneRemainder,
  probeInsightsDom,
  recordingHover,
  scrollMainContent,
  waitForInsightsReady,
} from '../helpers';
import type { SceneDefinition } from './types';

const SIDEBAR_TOUR_TABS = ['data', 'memories', 'ai', 'telemetry'] as const;

async function sidebarTour(page: Page): Promise<void> {
  const t0 = Date.now();
  debugNext('sidebar tour', SIDEBAR_TOUR_TABS.join(' → '));
  for (const tab of SIDEBAR_TOUR_TABS) {
    debugNext(`tour: open tab "${tab}"`);
    await goToTab(page, tab);
    await delay();
  }
  debugDone('sidebar tour complete');
  // #region agent log
  agentLog('H2', 'a1-insights.ts:sidebarTour', 'exit', {
    elapsedMs: Date.now() - t0,
    tabs: [...SIDEBAR_TOUR_TABS],
  });
  // #endregion
}

async function interactWithInsightsContent(page: Page): Promise<void> {
  const t0 = Date.now();
  const statWaitMs = config.profile === 'local' ? 8_000 : 20_000;
  debugNext('wait for stat cards or dashboard in DOM (not Playwright isVisible)');
  await page
    .waitForFunction(
      () =>
        document.querySelectorAll('[data-testid="insights-stat-card"]').length > 0 ||
        !!document.querySelector('[data-testid="insights-dashboard"]') ||
        Array.from(document.querySelectorAll('button')).some((b) =>
          /refresh/i.test((b.textContent || '').trim()),
        ),
      { timeout: statWaitMs },
    )
    .catch(() => undefined);
  debugNext('hover stat cards (up to 5)');
  const statCards = page.locator('[data-testid="insights-stat-card"]');
  let statCount = await statCards.count();
  if (statCount === 0) {
    const glassCards = page.locator('main .glass-card');
    statCount = await glassCards.count();
    debug(`no testid stat cards — using ${statCount} .glass-card in main`);
    for (let i = 0; i < Math.min(statCount, 5); i++) {
      const card = glassCards.nth(i);
      await card.scrollIntoViewIfNeeded().catch(() => undefined);
      await recordingHover(page, card, { force: true });
      await delay();
    }
  } else {
    console.log(`  📊 Stat cards: ${statCount}`);
    debug(`found ${statCount} stat cards`);
    for (let i = 0; i < Math.min(statCount, 5); i++) {
      debugNext(`hover stat card ${i + 1}/${Math.min(statCount, 5)}`);
      const card = statCards.nth(i);
      await card.scrollIntoViewIfNeeded();
      await recordingHover(page, card, { force: true });
      await delay();
    }
  }
  const refreshBtn = page.getByRole('button', { name: /refresh/i }).first();
  if ((await refreshBtn.count()) > 0) {
    debugNext('hover Refresh button (visible in headed browser)');
    await recordingHover(page, refreshBtn, { force: true });
    await delay();
  }

  debugNext('scroll main content +320px');
  await scrollMainContent(page, 320);
  await delay();

  const sections = page.locator('[data-testid="insights-section-card"]');
  const sectionCount = await sections.count();
  debugNext(`hover section cards (up to 3, found ${sectionCount})`);
  for (let i = 0; i < Math.min(sectionCount, 3); i++) {
    const section = sections.nth(i);
    await section.scrollIntoViewIfNeeded();
    await recordingHover(page, section, { force: true });
    await delay();
  }

  debugNext('scroll main content +420px');
  await scrollMainContent(page, 420);
  await delay();

  debugNext('scroll main content -280px');
  await scrollMainContent(page, -280);
  await delay();

  const firstStat = statCards.first();
  if (await firstStat.isVisible().catch(() => false)) {
    debugNext('hover first stat card again');
    await recordingHover(page, firstStat, { force: true });
    await delay();
  }
  debugDone('insights dashboard interactions');
  // #region agent log
  agentLog('H5', 'a1-insights.ts:interactWithInsightsContent', 'exit', {
    elapsedMs: Date.now() - t0,
    statCount,
  });
  // #endregion
}

async function record(page: Page): Promise<SceneResult> {
  const start = Date.now();
  try {
    console.log('🎬 A1 — Insights overview');
    // #region agent log
    agentLog('H1', 'a1-insights.ts:record', 'enter', {
      targetSceneMs: sceneTargetDurationMs('insights'),
      slowMo: config.slowMo,
      profile: config.profile,
    });
    // #endregion

    // Session often starts on ?tab=insights — skip repeat sidebar hover+click.
    debugNext('ensure Insights tab (no motion if already active)');
    await goToTab(page, 'insights');
    await delay();
    let probe = await probeInsightsDom(page);
    await debugInsightsState(page);
    let ready = insightsLooksReady(probe);
    if (!ready) {
      debugNext('DOM probe not ready yet — waitForInsightsReady');
      ready = await waitForInsightsReady(page);
      probe = await probeInsightsDom(page);
      ready = ready || insightsLooksReady(probe);
    }
    // #region agent log
    agentLog('H3', 'a1-insights.ts:record', 'ready_check', {
      ready,
      probe,
      elapsedMs: Date.now() - start,
    }, 'post-fix');
    // #endregion

    if (ready) {
      console.log('  ✓ Insights detected in DOM — running dashboard actions');
      debugNext('branch: ready → interactWithInsightsContent');
      await interactWithInsightsContent(page);
      debugNext('branch: ready → sidebarTour');
      await sidebarTour(page);
      await goToTab(page, 'insights');
      await delay();
    } else {
      console.warn('  ⚠️ Insights DOM probe empty — minimal motion only');
      debug(`final probe: ${JSON.stringify(probe)}`);
    }

    const paceTarget = sceneTargetDurationMs('insights');
    // #region agent log
    agentLog('H1', 'a1-insights.ts:record', 'before_pace', {
      ready,
      paceTargetMs: paceTarget,
      elapsedBeforePaceMs: Date.now() - start,
    });
    // #endregion
    debugNext(`paceSceneRemainder to ${paceTarget}ms`);
    await paceSceneRemainder(page, paceTarget, start);
    const totalMs = Date.now() - start;
    // #region agent log
    agentLog('H1', 'a1-insights.ts:record', 'exit', { totalMs, branch: ready ? 'ready' : 'not_ready' });
    // #endregion
    return { success: true, duration: totalMs };
  } catch (error) {
    return {
      success: false,
      duration: Date.now() - start,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export const sceneA1: SceneDefinition = {
  id: 'A1',
  title: 'Insights overview',
  profiles: 'both',
  timingKey: 'insights',
  record,
};

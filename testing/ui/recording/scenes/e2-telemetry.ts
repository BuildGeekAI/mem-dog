import type { Page } from 'playwright';
import { sceneTargetDurationMs } from '../config';
import { debugNext } from '../debug';
import type { SceneResult } from '../helpers';
import { delay, fillSceneDuration, goToTab } from '../helpers';
import type { SceneDefinition } from './types';

async function record(page: Page): Promise<SceneResult> {
  const start = Date.now();
  try {
    console.log('🎬 E2 — Telemetry');
    debugNext('open Telemetry tab');
    await goToTab(page, 'telemetry');
    await delay();
    const trace = page.locator('button, [role="button"]').filter({ hasText: /trace|span|expand/i }).first();
    if (await trace.isVisible().catch(() => false)) {
      debugNext('click trace/expand control');
      await trace.click();
      await delay();
    }
    const row = page.locator('tr, [class*="trace"], [class*="span"]').first();
    if (await row.isVisible().catch(() => false)) {
      debugNext('click first trace row');
      await row.click().catch(() => undefined);
      await delay();
    }
    await fillSceneDuration(page, sceneTargetDurationMs('telemetry'), start);
    return { success: true, duration: Date.now() - start };
  } catch (error) {
    return {
      success: false,
      duration: Date.now() - start,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export const sceneE2: SceneDefinition = {
  id: 'E2',
  title: 'Telemetry',
  profiles: 'both',
  timingKey: 'telemetry',
  record,
};

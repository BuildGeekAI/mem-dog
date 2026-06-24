import type { Page } from 'playwright';
import { sceneTargetDurationMs } from '../config';
import { debugNext, debugWait } from '../debug';
import type { SceneResult } from '../helpers';
import { delay, fillSceneDuration, goToTab, scrollMainContent } from '../helpers';
import type { SceneDefinition } from './types';

async function record(page: Page): Promise<SceneResult> {
  const start = Date.now();
  try {
    console.log('🎬 B5 — Browse data list');
    debugNext('open Data tab');
    await goToTab(page, 'data');
    debugWait('table visible', { timeoutMs: 30000, next: 'scroll and search' });
    await page.waitForSelector('table', { timeout: 30000 }).catch(() => undefined);
    await delay();
    debugNext('scroll data list');
    await scrollMainContent(page, 200);
    await delay();
    const search = page.getByPlaceholder(/search/i).first();
    if (await search.isVisible().catch(() => false)) {
      debugNext('fill search "recording"');
      await search.fill('recording');
      await delay();
      debugNext('clear search');
      await search.fill('');
      await delay();
    }
    const rows = page.locator('table tbody tr');
    const count = await rows.count();
    debugNext(`hover table rows (found ${count})`);
    if (count > 0) {
      await rows.first().hover();
      await delay();
      if (count > 1) await rows.nth(1).hover();
      await delay();
    }
    await fillSceneDuration(page, sceneTargetDurationMs('dataList'), start);
    return { success: true, duration: Date.now() - start };
  } catch (error) {
    return {
      success: false,
      duration: Date.now() - start,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export const sceneB5: SceneDefinition = {
  id: 'B5',
  title: 'Browse data list',
  profiles: 'both',
  timingKey: 'dataList',
  record,
};

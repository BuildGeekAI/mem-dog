import type { Page } from 'playwright';
import { sceneTargetDurationMs } from '../config';
import { debugNext, debugWait } from '../debug';
import type { SceneResult } from '../helpers';
import { delay, fillSceneDuration, goToPlaygroundSubTab } from '../helpers';
import type { SceneDefinition } from './types';

async function record(page: Page): Promise<SceneResult> {
  const start = Date.now();
  try {
    console.log('🎬 B1 — Text ingest (Playground → Data Insert)');
    debugNext('Playground → Data Insert sub-tab');
    await goToPlaygroundSubTab(page, 'upload');
    const content = JSON.stringify(
      {
        demo: 'recording',
        topic: 'Mem-Dog data platform',
        timestamp: new Date().toISOString(),
      },
      null,
      2,
    );
    debugNext('fill upload textarea', '[data-testid="upload-textarea"]');
    await page.locator('[data-testid="upload-textarea"]').fill(content);
    await delay();
    const tags = page.locator('input[placeholder*="tag" i], input[placeholder*="Tags" i]').first();
    if (await tags.isVisible().catch(() => false)) {
      debugNext('fill tags field');
      await tags.fill('recording,demo,playground');
      await delay();
    }
    debugNext('click upload submit', '[data-testid="upload-submit"]');
    await page.locator('[data-testid="upload-submit"]').click();
    debugWait('.alert-success visible', { timeoutMs: 60000, next: 'fillSceneDuration' });
    await page.locator('.alert-success').waitFor({ state: 'visible', timeout: 60000 });
    await delay();
    await fillSceneDuration(page, sceneTargetDurationMs('dataInsertText'), start);
    return { success: true, duration: Date.now() - start };
  } catch (error) {
    return {
      success: false,
      duration: Date.now() - start,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export const sceneB1: SceneDefinition = {
  id: 'B1',
  title: 'Text ingest',
  profiles: 'both',
  timingKey: 'dataInsertText',
  record,
};

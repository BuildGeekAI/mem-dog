import type { Page } from 'playwright';
import { config, sceneTargetDurationMs } from '../config';
import { debugNext, debugWait } from '../debug';
import type { SceneResult } from '../helpers';
import { delay, fillSceneDuration, goToPlaygroundSubTab } from '../helpers';
import type { SceneDefinition } from './types';

async function record(page: Page): Promise<SceneResult> {
  const start = Date.now();
  let waitStart = 0;
  let waitEnd = 0;
  try {
    console.log('🎬 D1 — Knowledge Chat');
    debugNext('Playground → Knowledge Chat');
    await goToPlaygroundSubTab(page, 'knowledge');
    const hybrid = page.locator(config.selectors.knowledgeChat.hybridMode).first();
    if (await hybrid.isVisible().catch(() => false)) {
      debugNext('click Hybrid mode', config.selectors.knowledgeChat.hybridMode);
      await hybrid.click();
      await delay();
    }
    const full = page.locator('button:has-text("Full")').first();
    if (await full.isVisible().catch(() => false)) {
      debugNext('click Full search mode');
      await full.click();
      await delay();
    }
    const question =
      'What is Mem-Dog and how does hybrid search work for knowledge retrieval?';
    debugNext('fill chat input', config.selectors.knowledgeChat.input);
    await page.locator(config.selectors.knowledgeChat.input).fill(question);
    await delay();
    waitStart = Date.now() - start;
    debugNext('click send', config.selectors.knowledgeChat.send);
    await page.locator(config.selectors.knowledgeChat.send).click();
    debugWait('chat response visible', {
      timeoutMs: 120000,
      next: 'fillSceneDuration',
    });
    await page
      .locator('[class*="prose"], .markdown, [data-testid="knowledge-chat-response"]')
      .first()
      .waitFor({ state: 'visible', timeout: 120000 })
      .catch(() => page.waitForTimeout(15000));
    waitEnd = Date.now() - start;
    await delay();
    await fillSceneDuration(page, sceneTargetDurationMs('knowledgeChat'), start);
    return {
      success: true,
      duration: Date.now() - start,
      waitCut:
        waitEnd > waitStart
          ? { startOffsetMs: waitStart, endOffsetMs: waitEnd }
          : undefined,
    };
  } catch (error) {
    return {
      success: false,
      duration: Date.now() - start,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export const sceneD1: SceneDefinition = {
  id: 'D1',
  title: 'Knowledge Chat',
  profiles: 'both',
  timingKey: 'knowledgeChat',
  record,
};

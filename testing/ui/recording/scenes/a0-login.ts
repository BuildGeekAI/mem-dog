import type { Page } from 'playwright';
import { config, sceneTargetDurationMs } from '../config';
import { debugNext, debugWait } from '../debug';
import type { SceneResult } from '../helpers';
import { delay, fillSceneDuration } from '../helpers';
import type { SceneDefinition } from './types';

async function record(page: Page): Promise<SceneResult> {
  const start = Date.now();
  try {
    console.log('🎬 A0 — Login');
    debugNext('goto login', config.baseUrl);
    await page.goto(config.baseUrl, { waitUntil: 'domcontentloaded' });
    debugWait('login email field', { timeoutMs: 20000, next: 'fill credentials' });
    await page.waitForSelector(config.selectors.login.email, { timeout: 20000 });
    await delay();
    debugNext('fill email');
    await page.fill(config.selectors.login.email, config.email);
    await delay();
    debugNext('fill password');
    await page.fill(config.selectors.login.password, config.password);
    await delay();
    debugNext('click submit', config.selectors.login.submit);
    await page.click(config.selectors.login.submit);
    debugWait('sidebar after login', { timeoutMs: 30000, next: 'fillSceneDuration' });
    await page.waitForSelector('[data-testid^="sidebar-tab-"]', { timeout: 30000 });
    await fillSceneDuration(page, sceneTargetDurationMs('login'), start);
    return { success: true, duration: Date.now() - start };
  } catch (error) {
    return {
      success: false,
      duration: Date.now() - start,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export const sceneA0: SceneDefinition = {
  id: 'A0',
  title: 'Login',
  profiles: ['gcp'],
  timingKey: 'login',
  record,
};

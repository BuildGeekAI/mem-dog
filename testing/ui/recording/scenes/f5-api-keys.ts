import type { Page } from 'playwright';
import { config, sceneTargetDurationMs } from '../config';
import { debugNext, debugWait } from '../debug';
import type { SceneResult } from '../helpers';
import { delay, fillSceneDuration, goToSettingsSubTab } from '../helpers';
import type { SceneDefinition } from './types';

async function record(page: Page): Promise<SceneResult> {
  const start = Date.now();
  try {
    console.log('🎬 F5 — API Keys');
    debugNext('Settings → API Keys');
    await goToSettingsSubTab(page, 'API Keys');
    await delay();
    debugNext('fill key name', config.selectors.settings.keyName);
    const nameInput = page.locator(config.selectors.settings.keyName);
    await nameInput.fill(`demo-recording-${Date.now().toString(36)}`);
    await delay();
    debugNext('click create', config.selectors.settings.createButton);
    await page.locator(config.selectors.settings.createButton).click();
    debugWait('key created confirmation', {
      timeoutMs: 30000,
      next: 'fillSceneDuration',
    });
    await page
      .locator('text=/Key created|won\'t be shown again/i')
      .first()
      .waitFor({ state: 'visible', timeout: 30000 })
      .catch(() => delay());
    await delay();
    await fillSceneDuration(page, sceneTargetDurationMs('settingsApiKeys'), start);
    return { success: true, duration: Date.now() - start };
  } catch (error) {
    return {
      success: false,
      duration: Date.now() - start,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

export const sceneF5: SceneDefinition = {
  id: 'F5',
  title: 'API Keys',
  profiles: 'both',
  timingKey: 'settingsApiKeys',
  record,
};

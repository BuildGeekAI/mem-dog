import type { Page } from 'playwright';
import { config, sceneTargetDurationMs } from '../config';
import { debugNext } from '../debug';
import type { SceneResult } from '../helpers';
import {
  delay,
  fillSceneDuration,
  goToPlaygroundSubTab,
  goToSettingsSubTab,
  goToTab,
  scrollMainContent,
} from '../helpers';
import type { SceneDefinition } from './types';

type NavTarget =
  | { tab: string }
  | { tab: string; settingsLabel: string }
  | { tab: string; playground: 'channel' | 'upload' | 'knowledge' | 'mcp' }
  | { url: string };

export function createStubScene(
  id: string,
  title: string,
  timingKey: string,
  nav: NavTarget,
  opts?: { optional?: boolean; profiles?: SceneDefinition['profiles'] },
): SceneDefinition {
  return {
    id,
    title,
    profiles: opts?.profiles ?? 'both',
    optional: opts?.optional,
    timingKey,
    record: async (page: Page): Promise<SceneResult> => {
      const start = Date.now();
      console.log(`🎬 ${id} — ${title} (stub — TODO polish)`);
      try {
        if ('url' in nav) {
          const url = nav.url.startsWith('http') ? nav.url : `${config.baseUrl}${nav.url}`;
          debugNext('goto URL', url);
          await page.goto(url, { waitUntil: 'domcontentloaded' });
          await delay();
        } else if ('settingsLabel' in nav && nav.settingsLabel) {
          await goToSettingsSubTab(page, nav.settingsLabel);
        } else if ('playground' in nav && nav.playground) {
          await goToPlaygroundSubTab(page, nav.playground);
        } else {
          await goToTab(page, nav.tab);
        }

        debugNext('stub content scroll');
        await scrollMainContent(page, 100);
        await delay();

        const duration = sceneTargetDurationMs(timingKey as Parameters<typeof sceneTargetDurationMs>[0]);
        debugNext(`fillSceneDuration ${duration}ms (scene cap)`);
        await fillSceneDuration(page, duration, start);
        return { success: true, duration: Date.now() - start };
      } catch (error) {
        return {
          success: false,
          duration: Date.now() - start,
          error: error instanceof Error ? error.message : String(error),
        };
      }
    },
  };
}

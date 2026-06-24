import type { Page } from 'playwright';
import { config, sceneTargetDurationMs } from '../config';
import { debug, debugNext, debugWait } from '../debug';
import type { SceneResult } from '../helpers';
import { delay, fillSceneDuration, goToPlaygroundSubTab } from '../helpers';
import type { SceneDefinition } from './types';

async function record(page: Page): Promise<SceneResult> {
  const start = Date.now();
  let waitStart = 0;
  let waitEnd = 0;
  try {
    console.log('🎬 E1 — Channel to Webhook');
    debugNext('Playground → Channel to Webhook');
    await goToPlaygroundSubTab(page, 'channel');
    if (config.gatewayUrl) {
      const gw = page.locator(config.selectors.channelWebhook.gatewayInput);
      if (await gw.isVisible().catch(() => false)) {
        debugNext('fill gateway URL', config.selectors.channelWebhook.gatewayInput);
        await gw.fill(config.gatewayUrl);
        await delay();
      }
    }
    const message = `Demo webhook message ${new Date().toISOString()}`;
    debugNext('fill channel message', config.selectors.channelWebhook.messageInput);
    await page.locator(config.selectors.channelWebhook.messageInput).fill(message);
    await delay();
    waitStart = Date.now() - start;
    const send = page.locator(config.selectors.channelWebhook.send);
    if (await send.isEnabled().catch(() => false)) {
      debugNext('click send', config.selectors.channelWebhook.send);
      await send.click();
      debugWait('send success indicator', {
        timeoutMs: 120000,
        next: 'fillSceneDuration',
      });
      await page
        .locator('text=/sent|success|delivered|envelope/i')
        .first()
        .waitFor({ state: 'visible', timeout: 120000 })
        .catch(() => page.waitForTimeout(20000));
    } else {
      debug('send button disabled — skipping click');
      console.warn('  ⚠️  Send disabled — configure gateway URL');
      await delay();
    }
    waitEnd = Date.now() - start;
    await fillSceneDuration(page, sceneTargetDurationMs('channelWebhook'), start);
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

export const sceneE1: SceneDefinition = {
  id: 'E1',
  title: 'Channel to Webhook',
  profiles: 'both',
  timingKey: 'channelWebhook',
  record,
};

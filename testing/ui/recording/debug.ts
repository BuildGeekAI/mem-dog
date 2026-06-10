import type { Page } from 'playwright';

let activeSceneId = 'session';

/** Debug logs on by default; set RECORDING_DEBUG=0 to disable. */
export function isRecordingDebug(): boolean {
  return process.env.RECORDING_DEBUG !== '0';
}

function timestamp(): string {
  return new Date().toISOString().slice(11, 23);
}

function prefix(): string {
  return `[${timestamp()} debug ${activeSceneId}]`;
}

export function setDebugScene(sceneId: string): void {
  activeSceneId = sceneId;
}

export function debug(message: string): void {
  if (!isRecordingDebug()) return;
  console.log(`  ${prefix()} ${message}`);
}

export function debugWait(
  waitingFor: string,
  opts?: { timeoutMs?: number; next?: string },
): void {
  if (!isRecordingDebug()) return;
  const timeout =
    opts?.timeoutMs !== undefined ? ` (max ${opts.timeoutMs}ms)` : '';
  console.log(`  ${prefix()} ⏳ WAIT: ${waitingFor}${timeout}`);
  if (opts?.next) {
    console.log(`  ${prefix()} ▶ NEXT (after wait): ${opts.next}`);
  }
}

export function debugNext(action: string, detail?: string): void {
  if (!isRecordingDebug()) return;
  const extra = detail ? ` — ${detail}` : '';
  console.log(`  ${prefix()} ▶ NEXT: ${action}${extra}`);
}

export function debugDone(message: string): void {
  if (!isRecordingDebug()) return;
  console.log(`  ${prefix()} ✓ DONE: ${message}`);
}

/** Log elapsed time since startMs (from Date.now()). */
export function debugElapsed(label: string, startMs: number): void {
  if (!isRecordingDebug()) return;
  console.log(`  ${prefix()} ⏱ ${label}: ${Date.now() - startMs}ms`);
}

export async function debugInsightsState(page: Page): Promise<void> {
  if (!isRecordingDebug()) return;
  const { probeInsightsDom } = await import('./helpers');
  const probe = await probeInsightsDom(page).catch(() => null);
  const quick = { timeout: 500 };
  const pwLoading = await page
    .locator('[data-testid="insights-loading"]')
    .isVisible(quick)
    .catch(() => false);
  const pwDashboard = await page
    .locator('[data-testid="insights-dashboard"]')
    .isVisible(quick)
    .catch(() => false);
  const refresh = page.locator('[data-testid="insights-refresh"]');
  const pwRefreshVisible = await refresh.isVisible(quick).catch(() => false);
  const url = page.url();
  debug(
    `insights: url=${url} dom=${JSON.stringify(probe)} pw={loading:${pwLoading} dashboard:${pwDashboard} refreshVisible:${pwRefreshVisible}}`,
  );
}

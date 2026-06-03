import type { BrowserContext, Locator, Page } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';
import { config, scenePauseMs } from './config';
import { agentLog } from './agent-log';
import {
  debug,
  debugDone,
  debugElapsed,
  debugInsightsState,
  debugNext,
  debugWait,
  isRecordingDebug,
} from './debug';
import {
  ensureRecordingCursor,
  recordingClick,
  recordingHover,
  showRecordingCursor,
} from './recording-cursor';

export { ensureRecordingCursor, recordingClick, recordingHover, showRecordingCursor };

function currentTabFromUrl(pageUrl: string): string | null {
  try {
    return new URL(pageUrl).searchParams.get('tab');
  } catch {
    return null;
  }
}

export interface WaitCutSegment {
  startOffsetMs: number;
  endOffsetMs: number;
}

export interface SceneResult {
  success: boolean;
  duration: number;
  error?: string;
  waitCut?: WaitCutSegment;
  waitCuts?: WaitCutSegment[];
}

export interface SeedState {
  versionedDataId?: string;
  listDataIds?: string[];
  ragDataId?: string;
  orgId?: string;
  projectId?: string;
  tags?: string[];
}

export function loadSeedState(): SeedState {
  try {
    if (fs.existsSync(config.seedStatePath)) {
      return JSON.parse(fs.readFileSync(config.seedStatePath, 'utf-8')) as SeedState;
    }
  } catch {
    /* ignore */
  }
  return {};
}

export function ensureOutputDir(): void {
  if (!fs.existsSync(config.outputDir)) {
    fs.mkdirSync(config.outputDir, { recursive: true });
  }
}

/** Default pause between recording steps (1s unless RECORDING_PAUSE_MS is set). */
export async function scenePause(): Promise<void> {
  await delay(scenePauseMs());
}

export async function delay(ms?: number): Promise<void> {
  const page = globalPage;
  const wait = ms ?? scenePauseMs();
  const t0 = Date.now();
  if (isRecordingDebug() && wait >= 300) {
    debug(`pause ${wait}ms`);
  }
  if (page) {
    await page.waitForTimeout(wait);
  } else {
    await new Promise((r) => setTimeout(r, wait));
  }
  const actualMs = Date.now() - t0;
  // #region agent log
  agentLog('P1', 'helpers.ts:delay', 'step_pause', {
    configuredMs: wait,
    actualMs,
    explicitMs: ms !== undefined,
    within50ms: Math.abs(actualMs - wait) <= 50,
    isOneSecond: wait === 1000,
  }, 'pause-audit');
  // #endregion
}

let globalPage: Page | null = null;

export const RECORDING_DEFAULT_USER_ID = '00000000-0000-0000-0000-000000000001';

export function setActivePage(page: Page): void {
  globalPage = page;
}

/** Fast optional checks (skip waits). Do not use for readiness gates. */
export const QUICK_LOCATOR_MS = 500;

/** How long to wait for Insights UI when the headed browser already shows it. */
export function insightsWaitMs(): number {
  return config.profile === 'local' ? 12_000 : 25_000;
}

/** DOM probe — Playwright isVisible() often false while the headed UI looks ready (animations, overflow panels). */
export type InsightsDomProbe = {
  refreshAttached: boolean;
  refreshInLayout: boolean;
  refreshDisabled: boolean;
  refreshLabel: string;
  loadingAttached: boolean;
  dashboardAttached: boolean;
  statCards: number;
  sidebarTabs: number;
  refreshByTextAttached: boolean;
  insightsHeading: boolean;
  navShell: boolean;
  connecting: boolean;
};

/** True when the headed browser already shows Insights (ignore Playwright isVisible). */
export function insightsLooksReady(probe: InsightsDomProbe): boolean {
  if (probe.connecting) return false;
  return (
    probe.statCards > 0 ||
    probe.dashboardAttached ||
    probe.refreshInLayout ||
    probe.refreshByTextAttached ||
    (probe.insightsHeading && probe.navShell)
  );
}

export async function probeInsightsDom(page: Page): Promise<InsightsDomProbe> {
  return page.evaluate(() => {
    const refreshEl = document.querySelector(
      '[data-testid="insights-refresh"]',
    ) as HTMLButtonElement | null;
    const refreshByText = Array.from(document.querySelectorAll('button')).find((b) =>
      /refresh/i.test((b.textContent || '').trim()),
    );
    const body = document.body?.innerText || '';
    const insightsHeading = Array.from(document.querySelectorAll('h1,h2,h3')).some((h) =>
      /^insights$/i.test((h.textContent || '').trim()),
    );
    const navShell =
      document.querySelectorAll('[data-testid^="sidebar-tab-"]').length > 0 ||
      (/\bInsights\b/.test(body) &&
        /\b(Data|Memories|AI|Telemetry|Settings)\b/.test(body));
    return {
      refreshAttached: !!refreshEl,
      refreshInLayout: !!(refreshEl && refreshEl.offsetParent !== null),
      refreshDisabled: refreshEl?.disabled ?? true,
      refreshLabel: (refreshEl?.textContent || '').trim(),
      loadingAttached: !!document.querySelector('[data-testid="insights-loading"]'),
      dashboardAttached: !!document.querySelector('[data-testid="insights-dashboard"]'),
      statCards: document.querySelectorAll('[data-testid="insights-stat-card"]').length,
      sidebarTabs: document.querySelectorAll('[data-testid^="sidebar-tab-"]').length,
      refreshByTextAttached: !!refreshByText,
      insightsHeading,
      navShell,
      connecting: body.includes('Connecting...'),
    };
  });
}

export async function ensureRecordingUser(apiUrl: string): Promise<void> {
  const userId = process.env.RECORDING_USER_ID || RECORDING_DEFAULT_USER_ID;
  const base = apiUrl.replace(/\/$/, '');
  try {
    const getRes = await fetch(`${base}/api/v1/users/${encodeURIComponent(userId)}`);
    if (getRes.ok) return;
    const postRes = await fetch(`${base}/api/v1/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-ID': userId },
      body: JSON.stringify({
        user_id: userId,
        username: 'demo',
        email: 'demo@local.mem-dog',
        display_name: 'Demo User',
      }),
    });
    if (postRes.ok) {
      debug(`provisioned recording user ${userId}`);
    }
  } catch {
    /* non-fatal */
  }
}

/** Main panel past "Connecting…" with Insights UI mounted (DOM attached, not Playwright visible). */
export async function waitForMainAppContent(page: Page): Promise<boolean> {
  const t0 = Date.now();
  const maxMs = config.profile === 'local' ? 20_000 : 45_000;

  debugWait('app shell (sidebar + Insights DOM)', { timeoutMs: maxMs });
  try {
    await page.waitForFunction(
      () => {
        const body = document.body?.innerText || '';
        if (body.includes('Connecting...')) return false;
        const nav =
          document.querySelector('[data-testid^="sidebar-tab-"]') ||
          (/\bInsights\b/.test(body) && /\b(Data|Memories|AI|Telemetry)\b/.test(body));
        const insights =
          document.querySelector('[data-testid="insights-refresh"]') ||
          document.querySelector('[data-testid="insights-loading"]') ||
          document.querySelector('[data-testid="insights-dashboard"]') ||
          Array.from(document.querySelectorAll('button')).find((b) =>
            /refresh/i.test((b.textContent || '').trim()),
          ) ||
          Array.from(document.querySelectorAll('h1,h2,h3')).find((h) =>
            /^insights$/i.test((h.textContent || '').trim()),
          );
        return !!nav && !!insights;
      },
      { timeout: maxMs },
    );
    const probe = await probeInsightsDom(page);
    // #region agent log
    agentLog('H8', 'helpers.ts:waitForMainAppContent', 'ok', probe, 'post-fix');
    // #endregion
    debug(`waitForMainAppContent probe: ${JSON.stringify(probe)}`);
    debugElapsed('waitForMainAppContent', t0);
    return true;
  } catch {
    const probe = await probeInsightsDom(page).catch(() => null);
    // #region agent log
    agentLog('H8', 'helpers.ts:waitForMainAppContent', 'timeout', { probe }, 'post-fix');
    // #endregion
    debug(`waitForMainAppContent: timed out — probe=${JSON.stringify(probe)}`);
    debugElapsed('waitForMainAppContent', t0);
    return false;
  }
}

export async function authenticate(page: Page, context: BrowserContext): Promise<boolean> {
  if (config.profile === 'local' && !config.email) {
    console.log('ℹ️  Local profile without credentials — using anonymous demo user');
    await page.goto(config.baseUrl, { waitUntil: 'domcontentloaded' });
    await delay(config.timing.navigationWait);
    return true;
  }

  if (!config.email || !config.password) {
    console.error('❌ RECORDING_EMAIL and RECORDING_PASSWORD required');
    return false;
  }

  try {
    console.log('🔐 Authenticating...');
    debugNext('goto login page', config.baseUrl);
    await page.goto(config.baseUrl, { waitUntil: 'domcontentloaded' });
    debugWait('login email field', {
      timeoutMs: 15000,
      next: `fill ${config.selectors.login.email}`,
    });
    await page.waitForSelector(config.selectors.login.email, { timeout: 15000 });
    debugNext('fill credentials and submit', config.selectors.login.submit);
    await page.fill(config.selectors.login.email, config.email);
    await page.fill(config.selectors.login.password, config.password);
    await recordingClick(page, config.selectors.login.submit);
    debugWait('sidebar after login', { timeoutMs: 30000, next: 'save session' });
    await page.waitForSelector('[data-testid^="sidebar-tab-"]', { timeout: 30000 });
    await delay(config.timing.navigationWait);
    await saveSession(context);
    console.log('✅ Authentication successful');
    return true;
  } catch (error) {
    console.error('❌ Authentication failed:', error);
    return false;
  }
}

export async function loadSession(context: BrowserContext): Promise<boolean> {
  try {
    const sessionPath = config.sessionStoragePath;
    if (!fs.existsSync(sessionPath)) return false;

    const session = JSON.parse(fs.readFileSync(sessionPath, 'utf-8'));
    await context.addCookies(session.cookies);
    await context.addInitScript((storage) => {
      if (storage.localStorage) {
        for (const [key, value] of Object.entries(storage.localStorage)) {
          window.localStorage.setItem(key, value as string);
        }
      }
      if (storage.sessionStorage) {
        for (const [key, value] of Object.entries(storage.sessionStorage)) {
          window.sessionStorage.setItem(key, value as string);
        }
      }
    }, session.storage);
    console.log('✅ Session loaded');
    return true;
  } catch (error) {
    console.warn('⚠️  Failed to load session:', error);
    return false;
  }
}

export async function saveSession(context: BrowserContext): Promise<void> {
  try {
    const sessionPath = config.sessionStoragePath;
    const sessionDir = path.dirname(sessionPath);
    if (!fs.existsSync(sessionDir)) fs.mkdirSync(sessionDir, { recursive: true });

    const cookies = await context.cookies();
    const page = context.pages()[0] ?? (await context.newPage());
    const storage = await page.evaluate(() => ({
      localStorage: { ...window.localStorage },
      sessionStorage: { ...window.sessionStorage },
    }));

    fs.writeFileSync(
      sessionPath,
      JSON.stringify({ cookies, storage, timestamp: new Date().toISOString() }, null, 2),
    );
    console.log('💾 Session saved');
  } catch (error) {
    console.warn('⚠️  Failed to save session:', error);
  }
}

/** Keep ?tab= in sync after sidebar clicks (app state updates without a full reload). */
export async function syncTabQueryParam(page: Page, tab: string): Promise<void> {
  await page.evaluate((t) => {
    const u = new URL(window.location.href);
    u.searchParams.set('tab', t);
    const next = `${u.pathname}${u.search}${u.hash}`;
    window.history.replaceState({}, '', next);
  }, tab);
}

export type GoToTabOptions = {
  /** Click sidebar even when URL already matches (re-highlight for video). */
  force?: boolean;
  /** When already on tab: one smooth click on sidebar (default: skip — no repeat motion). */
  highlight?: boolean;
};

export async function goToTab(page: Page, tab: string, opts?: GoToTabOptions): Promise<void> {
  const t0 = Date.now();
  const current = currentTabFromUrl(page.url());
  const force = opts?.force === true;
  const highlight = opts?.highlight === true;

  if (current === tab && !force) {
    if (highlight) {
      const sel = config.selectors.sidebar(tab);
      const btn = page.locator(sel);
      if (await btn.isVisible({ timeout: QUICK_LOCATOR_MS }).catch(() => false)) {
        debugNext(`highlight tab "${tab}" (already active — single click)`);
        await recordingClick(page, btn, { skipMove: false });
        await syncTabQueryParam(page, tab);
      }
    } else {
      debugDone(`already on tab "${tab}" — skip sidebar motion (${page.url()})`);
    }
    // #region agent log
    agentLog('N2', 'helpers.ts:goToTab', highlight ? 'highlight_same_tab' : 'skip_same_tab', {
      tab,
      url: page.url(),
      elapsedMs: Date.now() - t0,
    }, 'nav-quality');
    // #endregion
    return;
  }

  const url = `${config.baseUrl}/?tab=${tab}`;
  const sel = config.selectors.sidebar(tab);
  const btn = page.locator(sel);
  const clickTimeout = config.appTimeouts.sidebarClickMs;
  let navMethod: 'sidebar_click' | 'goto_fallback' = 'sidebar_click';

  try {
    await btn.waitFor({ state: 'visible', timeout: clickTimeout });
    debugNext(`click sidebar tab "${tab}"`, sel);
    await recordingClick(page, btn);
    await syncTabQueryParam(page, tab);
  } catch {
    navMethod = 'goto_fallback';
    debugNext(`goto tab "${tab}" (sidebar not clickable in ${clickTimeout}ms)`, url);
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await ensureRecordingCursor(page);
  }

  const settle = config.timing.navigationWait;
  if (settle > 0) {
    debugWait(`navigation settle`, { timeoutMs: settle, next: `tab "${tab}"` });
    await delay(settle);
  }
  debugElapsed(`goToTab("${tab}")`, t0);
  debugDone(`on tab "${tab}" — ${page.url()}`);
  const cursorAfterNav = await page.evaluate((tid) => {
    const cur = document.getElementById('mem-dog-recording-cursor');
    const pos = cur
      ? { x: parseFloat(cur.style.left || '0'), y: parseFloat(cur.style.top || '0') }
      : null;
    const target = tid ? document.querySelector(`[data-testid="${tid}"]`) : null;
    const tr = target?.getBoundingClientRect();
    const targetCenterY = tr ? Math.round(tr.y + tr.height / 2) : null;
    return { pos, targetCenterY, viewportCenterY: Math.round(window.innerHeight / 2) };
  }, `sidebar-tab-${tab}`);
  // #region agent log
  agentLog('C2', 'helpers.ts:goToTab', 'cursor_after_nav', {
    tab,
    navMethod,
    ...cursorAfterNav,
  }, 'cursor-sidebar');
  agentLog('N3', 'helpers.ts:goToTab', 'navigated', {
    tab,
    fromTab: current,
    force,
    navMethod,
    settleMs: config.timing.navigationWait,
    elapsedMs: Date.now() - t0,
    url: page.url(),
  }, 'nav-quality');
  // #endregion
}

export async function goToPlaygroundSubTab(
  page: Page,
  sub: 'channel' | 'upload' | 'knowledge' | 'mcp',
): Promise<void> {
  debugNext('open Playground (testing tab)');
  await goToTab(page, 'testing');
  const key = sub === 'channel' ? 'channel' : sub;
  const sel = config.selectors.playground[key as keyof typeof config.selectors.playground];
  debugNext(`click playground sub-tab "${sub}"`, sel);
  await recordingClick(page, sel);
  await delay();
  debugDone(`playground sub-tab "${sub}"`);
  // #region agent log
  agentLog('N4', 'helpers.ts:goToPlaygroundSubTab', 'done', { sub, url: page.url() }, 'nav-quality');
  // #endregion
}

export async function goToSettingsSubTab(page: Page, label: string): Promise<void> {
  debugNext('open Settings');
  await goToTab(page, 'settings');
  debugNext(`click settings section "${label}"`);
  await recordingClick(page, page.getByRole('button', { name: label, exact: true }));
  await delay();
  debugDone(`settings "${label}"`);
  // #region agent log
  agentLog('N5', 'helpers.ts:goToSettingsSubTab', 'done', { label, url: page.url() }, 'nav-quality');
  // #endregion
}

/** App shell ready — any main nav tab, not Insights-specific. */
export async function waitForAppReady(page: Page): Promise<void> {
  const t0 = Date.now();
  const sidebarMs = config.profile === 'local' ? 4_000 : config.appTimeouts.sidebarMs;
  const { appSettleMs } = config.appTimeouts;
  const sidebar = page.locator('[data-testid^="sidebar-tab-"]').first();

  await page.waitForLoadState('domcontentloaded').catch(() => undefined);

  if (await sidebar.isVisible({ timeout: QUICK_LOCATOR_MS }).catch(() => false)) {
    debug('sidebar already visible — skip sidebar wait');
  } else {
    debugWait('sidebar tabs visible', {
      timeoutMs: sidebarMs,
      next: 'waitForMainAppContent',
    });
    await sidebar.waitFor({ state: 'visible', timeout: sidebarMs }).catch(() => undefined);
    debugElapsed('sidebar visible', t0);
  }

  const contentOk = await waitForMainAppContent(page);
  if (!contentOk) {
    debug('app shell up but Insights UI not mounted yet');
  }

  if (appSettleMs > 0) {
    await delay(appSettleMs);
  }
  debugElapsed('waitForAppReady total', t0);
  debugDone(`app shell ready — ${page.url()}`);
}

/** Insights mounted in the DOM (matches what you see in the headed browser). */
export async function isInsightsMounted(page: Page): Promise<boolean> {
  const probe = await probeInsightsDom(page);
  const ok =
    probe.dashboardAttached ||
    probe.loadingAttached ||
    probe.refreshAttached ||
    probe.refreshByTextAttached;
  debug(`isInsightsMounted(dom): ${JSON.stringify(probe)} => ${ok}`);
  // #region agent log
  agentLog('H8', 'helpers.ts:isInsightsMounted', 'probe', { ...probe, ok }, 'post-fix');
  // #endregion
  return ok;
}

/** Insights ready for demo actions — prefer DOM layout over Playwright isVisible(). */
export async function isInsightsInteractive(page: Page): Promise<boolean> {
  const probe = await probeInsightsDom(page);
  if (insightsLooksReady(probe)) {
    debug(`isInsightsInteractive: dom ready — ${JSON.stringify(probe)}`);
    return true;
  }
  if (probe.loadingAttached) {
    debug('isInsightsInteractive: still loading (dom)');
    return false;
  }
  debug(`isInsightsInteractive: not ready — probe=${JSON.stringify(probe)}`);
  return false;
}

/** Wait until Insights UI is in the DOM, then usable for recording. */
export async function waitForInsightsReady(page: Page, timeoutMs?: number): Promise<boolean> {
  const waitMs = timeoutMs ?? insightsWaitMs();
  const t0 = Date.now();
  // #region agent log
  agentLog('H3', 'helpers.ts:waitForInsightsReady', 'enter', { timeoutMs: waitMs }, 'post-fix');
  // #endregion
  await debugInsightsState(page);

  debugWait('Insights mounted in DOM', { timeoutMs: waitMs });
  try {
    await page.waitForFunction(
      () => {
        const dash = document.querySelector('[data-testid="insights-dashboard"]');
        const load = document.querySelector('[data-testid="insights-loading"]');
        const ref = document.querySelector('[data-testid="insights-refresh"]');
        const btn = Array.from(document.querySelectorAll('button')).find((b) =>
          /refresh/i.test((b.textContent || '').trim()),
        );
        return !!(dash || load || ref || btn);
      },
      { timeout: waitMs },
    );
  } catch {
    await debugInsightsState(page);
    debugElapsed('waitForInsightsReady (mount timeout)', t0);
    // #region agent log
    agentLog('H3', 'helpers.ts:waitForInsightsReady', 'exit', {
      ok: false,
      path: 'mount_timeout',
      elapsedMs: Date.now() - t0,
    }, 'post-fix');
    // #endregion
    return false;
  }

  const deadline = Date.now() + Math.min(waitMs, 8_000);
  while (Date.now() < deadline) {
    if (await isInsightsInteractive(page)) {
      await debugInsightsState(page);
      debugElapsed('waitForInsightsReady', t0);
      debugDone('insights ready (dom probe)');
      // #region agent log
      agentLog('H3', 'helpers.ts:waitForInsightsReady', 'exit', {
        ok: true,
        path: 'dom',
        elapsedMs: Date.now() - t0,
      }, 'post-fix');
      // #endregion
      return true;
    }
    await page.waitForTimeout(400);
  }

  await debugInsightsState(page);
  debugElapsed('waitForInsightsReady (not interactive)', t0);
  // #region agent log
  agentLog('H3', 'helpers.ts:waitForInsightsReady', 'exit', {
    ok: false,
    path: 'not_interactive',
    elapsedMs: Date.now() - t0,
  }, 'post-fix');
  // #endregion
  return false;
}

export async function fillSceneDuration(page: Page, targetMs: number, startedAt: number): Promise<void> {
  const elapsedBeforePad = Date.now() - startedAt;
  const remaining = targetMs - elapsedBeforePad;
  let padActualMs = 0;
  if (remaining > 500) {
    debugWait(`scene duration padding (not a step pause)`, {
      timeoutMs: remaining,
      next: 'end scene',
    });
    const padT0 = Date.now();
    await page.waitForTimeout(remaining);
    padActualMs = Date.now() - padT0;
  }
  const totalMs = Date.now() - startedAt;
  // #region agent log
  agentLog('P2', 'helpers.ts:fillSceneDuration', 'scene_end', {
    targetMs,
    elapsedBeforePadMs: elapsedBeforePad,
    paddingMs: remaining > 500 ? remaining : 0,
    paddingActualMs: padActualMs,
    totalMs,
  }, 'pause-audit');
  // #endregion
  debugDone(`scene total ${totalMs}ms (target ${targetMs}ms, actions ${elapsedBeforePad}ms)`);
}

export async function warmInsightsStatsApi(
  apiUrl: string,
  userId = process.env.RECORDING_USER_ID || RECORDING_DEFAULT_USER_ID,
): Promise<void> {
  const base = apiUrl.replace(/\/$/, '');
  try {
    const res = await fetch(
      `${base}/api/v1/stats/refresh/users/${encodeURIComponent(userId)}`,
      { method: 'POST' },
    );
    if (res.ok) {
      console.log(`  ✓ Pre-warmed insights stats for ${userId}`);
    } else {
      console.warn(`  ⚠️ Insights stats warm-up: HTTP ${res.status}`);
    }
  } catch (error) {
    console.warn('  ⚠️ Insights stats warm-up failed:', error);
  }
}

export async function scrollPage(page: Page, distance = 400): Promise<void> {
  await page.evaluate((d) => window.scrollBy({ top: d, behavior: 'smooth' }), distance);
  await delay(config.timing.scrollDelay);
}

/** Scroll the main app content panel (not window — layout uses overflow-y-auto). */
export async function scrollMainContent(page: Page, distance: number): Promise<void> {
  debugNext(`scroll main panel ${distance > 0 ? '+' : ''}${distance}px`);
  const scrollResult = await page.evaluate((d) => {
    const main = document.querySelector('main');
    // Do not use main .overflow-y-auto — the first match is the *sidebar* nav, not content.
    const contentCol =
      main?.querySelector(':scope > div.flex-col.flex-1') ??
      main?.querySelector(':scope > div.flex-1');
    const panel =
      contentCol?.querySelector(':scope > div.flex-1.overflow-y-auto') ??
      contentCol?.querySelector('.overflow-y-auto') ??
      contentCol;
    const sidebarNav = main?.querySelector('aside nav.overflow-y-auto');
    let scrolled = null;
    if (panel && panel !== sidebarNav) {
      panel.scrollBy({ top: d, behavior: 'smooth' });
      scrolled = panel;
    } else {
      window.scrollBy({ top: d, behavior: 'smooth' });
    }
    const el = scrolled || contentCol || main;
    let cursor = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    if (el) {
      const r = el.getBoundingClientRect();
      cursor = {
        x: r.left + r.width / 2,
        y: r.top + Math.min(r.height * 0.35, r.height - 40),
      };
    }
    var insightsBtn = document.querySelector('[data-testid="sidebar-tab-insights"]');
    var telemetryBtn = document.querySelector('[data-testid="sidebar-tab-telemetry"]');
    var insightsRowY = null;
    var telemetryRowY = null;
    if (insightsBtn) {
      var ir = insightsBtn.getBoundingClientRect();
      insightsRowY = Math.round(ir.y + ir.height / 2);
    }
    if (telemetryBtn) {
      var tr = telemetryBtn.getBoundingClientRect();
      telemetryRowY = Math.round(tr.y + tr.height / 2);
    }
    return {
      cursor: cursor,
      panelTag: scrolled ? scrolled.tagName : null,
      panelClass: scrolled && scrolled.className ? String(scrolled.className).slice(0, 80) : null,
      isSidebarNav: scrolled === sidebarNav,
      insightsRowY: insightsRowY,
      telemetryRowY: telemetryRowY,
    };
  }, distance);
  // #region agent log
  agentLog('C3', 'helpers.ts:scrollMainContent', 'scroll_target', scrollResult, 'cursor-sidebar');
  // #endregion
  await showRecordingCursor(page, scrollResult.cursor.x, scrollResult.cursor.y);
  await scenePause();
}

/** Pad scene time with gentle scrolls instead of a frozen idle wait. */
export async function paceSceneRemainder(
  page: Page,
  targetMs: number,
  startedAt: number,
): Promise<void> {
  const paceStart = Date.now();
  const elapsedAtEntry = paceStart - startedAt;
  let scrollLoops = 0;
  debugNext(`pace scene to ${targetMs}ms with scroll steps`);
  while (Date.now() - startedAt < targetMs - 700) {
    scrollLoops += 1;
    debugNext('scroll main content +90px (pace remainder)');
    await scrollMainContent(page, 90);
    await scenePause();
  }
  const remaining = targetMs - (Date.now() - startedAt);
  if (remaining > 0) {
    debugWait('final scene duration padding', { timeoutMs: remaining });
    await page.waitForTimeout(remaining);
  }
  debugDone(`paced scene to ~${targetMs}ms`);
  // #region agent log
  agentLog('H1', 'helpers.ts:paceSceneRemainder', 'exit', {
    targetMs,
    elapsedAtEntryMs: elapsedAtEntry,
    scrollLoops,
    finalPadMs: Math.max(0, remaining),
    pacePhaseMs: Date.now() - paceStart,
    totalSceneMs: Date.now() - startedAt,
  });
  // #endregion
}


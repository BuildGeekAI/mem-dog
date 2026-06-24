import type { BrowserContext, Locator, Page } from 'playwright';
import { agentLog } from './agent-log';
import { debug } from './debug';

/** Playwright recordVideo does not include the system pointer — inject a visible one. */
export function isRecordingCursorEnabled(): boolean {
  return process.env.RECORDING_CURSOR !== '0';
}

const DEFAULT_MOVE_MS = 320;

/**
 * String script (not a function reference) — context.addInitScript(fn) was not
 * executing in our Chrome recording runs; evaluate + content init both work.
 */
export const RECORDING_CURSOR_SCRIPT = `
(() => {
  const style = document.createElement('style');
  style.id = 'mem-dog-recording-cursor-style';
  style.textContent = \`
    html, html * { cursor: none !important; }
    #mem-dog-recording-cursor {
      position: fixed;
      left: 0;
      top: 0;
      width: 44px;
      height: 44px;
      z-index: 2147483647;
      pointer-events: none;
      transform: translate(-10px, -8px);
      transition: none;
      filter: drop-shadow(0 0 6px rgba(250,204,21,0.9)) drop-shadow(0 2px 4px rgba(0,0,0,0.8));
    }
    #mem-dog-recording-cursor.smooth {
      transition: left 0.32s ease-out, top 0.32s ease-out;
    }
    #mem-dog-recording-cursor-ring.smooth {
      transition: left 0.32s ease-out, top 0.32s ease-out;
    }
    #mem-dog-recording-cursor.click { transform: translate(-10px, -8px) scale(0.7); }
    #mem-dog-recording-cursor-ring {
      position: fixed;
      left: 0;
      top: 0;
      width: 52px;
      height: 52px;
      margin: -26px 0 0 -26px;
      border: 4px solid #facc15;
      border-radius: 50%;
      z-index: 2147483646;
      pointer-events: none;
      opacity: 0;
      transform: scale(0.35);
      box-shadow: 0 0 12px rgba(250,204,21,0.8);
      transition: none;
    }
    #mem-dog-recording-cursor-ring.active {
      opacity: 1;
      transform: scale(1);
      transition: opacity 0.1s, transform 0.18s ease-out;
    }
  \`;

  const ring = document.createElement('div');
  ring.id = 'mem-dog-recording-cursor-ring';

  const cursor = document.createElement('div');
  cursor.id = 'mem-dog-recording-cursor';
  cursor.innerHTML = '<svg width="44" height="44" viewBox="0 0 24 24"><path fill="#facc15" stroke="#000" stroke-width="1.5" d="M5 3l12 8.5-5.2.8 3.4 6.8-2.4 1.2-3.4-6.8L5 19z"/></svg>';

  let ignoreMouse = false;

  const applyPos = (px, py) => {
    cursor.style.left = px + 'px';
    cursor.style.top = py + 'px';
    ring.style.left = px + 'px';
    ring.style.top = py + 'px';
  };

  const moveInstant = (x, y) => {
    cursor.classList.remove('smooth');
    ring.classList.remove('smooth');
    cursor.style.transition = 'none';
    ring.style.transition = 'none';
    applyPos(Math.round(x), Math.round(y));
  };

  const smoothMoveTo = (x, y, ms) => {
    const dur = ms || 320;
    cursor.classList.add('smooth');
    ring.classList.add('smooth');
    cursor.style.transition = 'left ' + dur + 'ms ease-out, top ' + dur + 'ms ease-out';
    ring.style.transition = 'left ' + dur + 'ms ease-out, top ' + dur + 'ms ease-out';
    applyPos(Math.round(x), Math.round(y));
  };

  const pulse = () => {
    cursor.classList.add('click');
    ring.classList.add('active');
    setTimeout(() => {
      cursor.classList.remove('click');
      ring.classList.remove('active');
    }, 240);
  };

  const mount = () => {
    const root = document.body || document.documentElement;
    if (!document.getElementById('mem-dog-recording-cursor-style')) {
      document.documentElement.appendChild(style);
    }
    if (!document.getElementById('mem-dog-recording-cursor-ring')) {
      root.appendChild(ring);
    }
    const isNew = !document.getElementById('mem-dog-recording-cursor');
    if (isNew) {
      root.appendChild(cursor);
      moveInstant(window.innerWidth / 2, window.innerHeight / 2);
    }
  };

  window.__memDogCursor = {
    mount,
    move: moveInstant,
    smoothMoveTo,
    pulse,
    setIgnoreMouse: (v) => { ignoreMouse = !!v; },
  };
  mount();

  if (!window.__memDogCursorListeners) {
    window.__memDogCursorListeners = true;
    document.addEventListener('mousemove', (e) => {
      if (ignoreMouse) return;
      moveInstant(e.clientX, e.clientY);
    }, true);
    const observer = new MutationObserver(() => {
      if (document.body && !document.getElementById('mem-dog-recording-cursor')) mount();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }
})();
`;

export async function injectRecordingCursor(page: Page): Promise<boolean> {
  if (!isRecordingCursorEnabled()) return false;
  try {
    await page.evaluate(RECORDING_CURSOR_SCRIPT);
    return true;
  } catch (err) {
    debug(`injectRecordingCursor failed: ${err instanceof Error ? err.message : String(err)}`);
    return false;
  }
}

async function ensureCursorInjected(page: Page): Promise<void> {
  const has = await page.evaluate(() => !!document.getElementById('mem-dog-recording-cursor'));
  if (!has) await injectRecordingCursor(page);
}

export async function installRecordingCursor(context: BrowserContext): Promise<void> {
  if (!isRecordingCursorEnabled()) {
    debug('recording cursor overlay disabled (RECORDING_CURSOR=0)');
    return;
  }
  await context.addInitScript({ content: RECORDING_CURSOR_SCRIPT });
  for (const page of context.pages()) {
    await injectRecordingCursor(page);
  }
  debug('recording cursor overlay installed (evaluate + init script)');
}

/** Re-inject after navigation — init script alone was unreliable in headed Chrome. */
export async function ensureRecordingCursor(page: Page): Promise<void> {
  if (!isRecordingCursorEnabled()) return;
  await ensureCursorInjected(page);
}

/** Center of element — matches Playwright click position (avoids post-click twitch). */
export function recordingCursorPoint(box: { x: number; y: number; width: number; height: number }): {
  x: number;
  y: number;
} {
  return {
    x: box.x + box.width / 2,
    y: box.y + box.height / 2,
  };
}

/** One CSS ease-out glide (no stepped Playwright loop). */
export async function smoothMoveRecordingCursor(
  page: Page,
  toX: number,
  toY: number,
  durationMs = DEFAULT_MOVE_MS,
): Promise<void> {
  if (!isRecordingCursorEnabled()) return;
  await ensureCursorInjected(page);
  await page.evaluate(
    ({ x, y, ms }) => {
      const w = window as Window & {
        __memDogCursor?: {
          setIgnoreMouse: (v: boolean) => void;
          smoothMoveTo: (a: number, b: number, c: number) => void;
        };
      };
      w.__memDogCursor?.setIgnoreMouse(true);
      w.__memDogCursor?.smoothMoveTo(x, y, ms);
    },
    { x: toX, y: toY, ms: durationMs },
  );
  await page.waitForTimeout(durationMs + 30);
  await page.mouse.move(toX, toY);
  await page.evaluate(() => {
    (window as Window & { __memDogCursor?: { setIgnoreMouse: (v: boolean) => void } }).__memDogCursor?.setIgnoreMouse(
      false,
    );
  });
}

export async function showRecordingCursor(page: Page, x: number, y: number): Promise<void> {
  if (!isRecordingCursorEnabled()) return;
  await ensureCursorInjected(page);
  await page.mouse.move(x, y);
  await page.evaluate(
    ({ px, py }) => {
      (window as Window & { __memDogCursor?: { move: (a: number, b: number) => void } }).__memDogCursor?.move(px, py);
    },
    { px: x, py: y },
  );
}

export async function pulseRecordingClick(page: Page): Promise<void> {
  if (!isRecordingCursorEnabled()) return;
  await ensureCursorInjected(page);
  await page.evaluate(() => {
    (window as Window & { __memDogCursor?: { pulse: () => void } }).__memDogCursor?.pulse();
  });
}

/** @deprecated Use smoothMoveRecordingCursor — kept for callers that import animateRecordingCursor */
export async function animateRecordingCursor(
  page: Page,
  toX: number,
  toY: number,
  _steps?: number,
): Promise<void> {
  await smoothMoveRecordingCursor(page, toX, toY);
}

export async function recordingHover(
  page: Page,
  locator: Locator,
  opts?: { force?: boolean },
): Promise<void> {
  if (!isRecordingCursorEnabled()) {
    await locator.hover(opts);
    return;
  }
  await locator.scrollIntoViewIfNeeded().catch(() => undefined);
  const box = await locator.boundingBox();
  if (box) {
    const { x, y } = recordingCursorPoint(box);
    const dist = await cursorDistance(page, x, y);
    if (dist > 12) {
      await smoothMoveRecordingCursor(page, x, y, 280);
    } else {
      await showRecordingCursor(page, x, y);
    }
  } else {
    await ensureCursorInjected(page);
  }
  await locator.hover({ ...opts, force: opts?.force ?? true });
}

export type RecordingClickOptions = { force?: boolean; /** Skip glide when already near target */ skipMove?: boolean };

export async function recordingClick(
  page: Page,
  target: Locator | string,
  opts?: RecordingClickOptions,
): Promise<void> {
  const locator = typeof target === 'string' ? page.locator(target) : target;
  if (!isRecordingCursorEnabled()) {
    await locator.click(opts);
    return;
  }
  await locator.scrollIntoViewIfNeeded().catch(() => undefined);
  const box = await locator.boundingBox();
  if (box && !opts?.skipMove) {
    const { x, y } = recordingCursorPoint(box);
    const dist = await cursorDistance(page, x, y);
    if (dist > 12) {
      await smoothMoveRecordingCursor(page, x, y);
    } else {
      await showRecordingCursor(page, x, y);
    }
    await pulseRecordingClick(page);
    await page.evaluate(
      ({ px, py }) => {
        (window as Window & { __memDogCursor?: { move: (a: number, b: number) => void } }).__memDogCursor?.move(px, py);
        (window as Window & { __memDogCursor?: { setIgnoreMouse: (v: boolean) => void } }).__memDogCursor?.setIgnoreMouse(
          true,
        );
      },
      { px: x, py: y },
    );
    await locator.click({
      force: opts?.force,
      position: { x: box.width / 2, y: box.height / 2 },
    });
    await page.evaluate(() => {
      (window as Window & { __memDogCursor?: { setIgnoreMouse: (v: boolean) => void } }).__memDogCursor?.setIgnoreMouse(
        false,
      );
    });
  } else {
    await pulseRecordingClick(page);
    await locator.click(opts);
  }
}

async function cursorDistance(page: Page, x: number, y: number): Promise<number> {
  return page.evaluate(
    ({ tx, ty }) => {
      const el = document.getElementById('mem-dog-recording-cursor');
      if (!el) return 9999;
      const left = parseFloat(el.style.left || '0') || 0;
      const top = parseFloat(el.style.top || '0') || 0;
      return Math.hypot(left - tx, top - ty);
    },
    { tx: x, ty: y },
  );
}

/** Call on every page load during recording. */
export function attachRecordingCursorOnNavigation(page: Page): void {
  if (!isRecordingCursorEnabled()) return;
  page.on('load', () => {
    injectRecordingCursor(page).catch(() => undefined);
  });
}

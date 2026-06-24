import type { Browser, LaunchOptions } from 'playwright';
import * as fs from 'fs';
import { createRequire } from 'module';
import * as path from 'path';

/** Chromium flags that reduce GPU/sandbox crashes on recent macOS. */
export const MAC_STABLE_CHROMIUM_ARGS = [
  '--disable-dev-shm-usage',
  '--disable-gpu',
  '--disable-software-rasterizer',
];

export type RecordingBrowserChannel = 'chrome' | 'msedge' | undefined;

export function getRecordingBrowserChannel(): RecordingBrowserChannel {
  const raw = (process.env.RECORDING_BROWSER_CHANNEL || '').trim().toLowerCase();
  if (raw === 'chrome' || raw === 'msedge') return raw;
  return undefined;
}

export function buildRecordingLaunchOptions(opts: {
  headless: boolean;
  slowMo?: number;
}): LaunchOptions {
  const channel = getRecordingBrowserChannel();
  if (channel) {
    return {
      headless: opts.headless,
      slowMo: opts.slowMo,
      channel,
    };
  }
  return {
    headless: opts.headless,
    slowMo: opts.slowMo,
    args: MAC_STABLE_CHROMIUM_ARGS,
  };
}

export function getChromiumBrowserType(): {
  executablePath: (options?: { channel?: string }) => string;
  launch: (options?: LaunchOptions) => Promise<Browser>;
} {
  const requireFromCwd = createRequire(path.join(process.cwd(), 'package.json'));
  try {
    return requireFromCwd('playwright').chromium;
  } catch {
    return requireFromCwd('@playwright/test').chromium;
  }
}

export function printInstallBrowsersHelp(): void {
  console.error('\n❌ Playwright Chromium is not installed.');
  console.error('   From ui/, run:\n');
  console.error('     npm run record:install-browsers\n');
  console.error('   Or:\n');
  console.error('     npx playwright install chromium\n');
}

export function printChromeChannelHelp(): void {
  console.error('\n⚠️  Bundled Chromium crashed on this Mac.');
  console.error('   Use installed Google Chrome instead:\n');
  console.error('     RECORDING_BROWSER_CHANNEL=chrome npm run record:webapp\n');
}

export function isMissingBrowserExecutable(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return (
    msg.includes("Executable doesn't exist") ||
    msg.includes('npx playwright install') ||
    msg.includes('playwright install')
  );
}

export function isLikelyChromiumCrash(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return (
    msg.includes('SEGV') ||
    msg.includes('signal 11') ||
    msg.includes('UniversalExceptionRaise') ||
    msg.includes('Target page, context or browser has been closed')
  );
}

export function ensureBundledChromiumInstalled(): void {
  const channel = getRecordingBrowserChannel();
  if (channel) {
    console.log(`ℹ️  Using system browser channel: ${channel}`);
    return;
  }

  const chromium = getChromiumBrowserType();
  let executable: string;
  try {
    executable = chromium.executablePath();
  } catch {
    printInstallBrowsersHelp();
    process.exit(1);
  }
  if (!fs.existsSync(executable)) {
    printInstallBrowsersHelp();
    process.exit(1);
  }
}

export async function launchRecordingBrowser(opts: {
  headless: boolean;
  slowMo?: number;
}): Promise<Browser> {
  const chromium = getChromiumBrowserType();
  const launchOptions = buildRecordingLaunchOptions(opts);
  try {
    return await chromium.launch(launchOptions);
  } catch (err) {
    if (isMissingBrowserExecutable(err)) {
      printInstallBrowsersHelp();
      process.exit(1);
    }
    if (!getRecordingBrowserChannel() && isLikelyChromiumCrash(err)) {
      printChromeChannelHelp();
    }
    throw err;
  }
}

export async function verifyRecordingBrowserLaunch(): Promise<void> {
  const browser = await launchRecordingBrowser({ headless: true });
  await browser.close();
}

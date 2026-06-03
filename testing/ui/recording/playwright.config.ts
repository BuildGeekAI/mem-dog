import { defineConfig, devices } from '@playwright/test';
import path from 'path';
import { config as recordingConfig } from './config';

const isGcp = recordingConfig.profile === 'gcp';
const baseURL = recordingConfig.baseUrl || 'http://localhost:3000';

export default defineConfig({
  testDir: '.',
  testMatch: '**/*.spec.ts',
  timeout: 600_000,
  expect: { timeout: 60_000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL,
    trace: 'off',
    video: {
      mode: 'on',
      size: recordingConfig.videoSettings,
    },
    viewport: recordingConfig.videoSettings,
    launchOptions: {
      slowMo: recordingConfig.slowMo,
    },
    actionTimeout: 60_000,
    navigationTimeout: 90_000,
  },
  projects: [
    {
      name: 'chromium-recording',
      use: {
        ...devices['Desktop Chrome'],
        headless: false,
      },
    },
  ],
  webServer: isGcp || process.env.RECORDING_BASE_URL
    ? undefined
    : {
        command: 'npm run dev',
        url: 'http://localhost:3000',
        reuseExistingServer: !process.env.CI,
        cwd: path.resolve(__dirname, '../../../ui'),
      },
});

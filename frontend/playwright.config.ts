import { defineConfig, devices } from '@playwright/test';

const FRONTEND_URL = process.env.PLAYWRIGHT_FRONTEND_URL ?? 'http://localhost:5173';
const BACKEND_URL = process.env.PLAYWRIGHT_BACKEND_URL ?? 'http://localhost:8000';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: FRONTEND_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  globalSetup: './tests/global-setup.ts',
  // Boot backend + frontend before tests so a clean checkout (and CI)
  // can ``npm test`` without manually starting either server. When
  // someone is already running them locally, ``reuseExistingServer``
  // skips the boot.
  webServer: [
    {
      command: 'cd ../backend && .venv/bin/uvicorn app.main:app --port 8000',
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      stdout: 'pipe',
      stderr: 'pipe',
    },
    {
      command: 'npm run dev',
      url: FRONTEND_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      stdout: 'pipe',
      stderr: 'pipe',
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'tests/.auth/user.json',
      },
    },
  ],
});

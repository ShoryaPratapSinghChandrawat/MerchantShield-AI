import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';
import { BACKEND_DIR, E2E_BASE_URL, E2E_DB_FILE, E2E_HOST, E2E_PORT, FRONTEND_DIR } from './e2e/paths';

/**
 * Capture-only Playwright config.
 *
 * Deliberately separate from playwright.config.ts:
 *   - one desktop project instead of two viewports;
 *   - no globalSetup, no HTML/JSON reporters, no console-failure harness;
 *   - its own database file, so a capture run can never disturb the seeded
 *     state the verified suite uses.
 *
 * `npx playwright test` (the command the README documents and the browser suite
 * that is reported as 30/30) still uses playwright.config.ts and is untouched.
 */
function launchOptions(): { executablePath: string; args: string[] } | undefined {
  const explicit = process.env['MS_CHROMIUM_PATH'];
  if (explicit === undefined || explicit === '') {
    return undefined;
  }
  return { executablePath: explicit, args: ['--no-sandbox', '--disable-dev-shm-usage'] };
}

const opts = launchOptions();
const LAUNCH = opts === undefined ? {} : { launchOptions: opts };

const PYTHON = process.env['MS_PYTHON'] ?? path.join(FRONTEND_DIR, '..', '.venv', 'bin', 'python3');

export default defineConfig({
  testDir: path.join(FRONTEND_DIR, 'capture'),
  outputDir: path.join(FRONTEND_DIR, '..', 'artifacts', 'video', 'playwright-output'),
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  reporter: [['list']],
  use: {
    baseURL: E2E_BASE_URL,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    ...LAUNCH,
  },
  projects: [{ name: 'capture-desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1500, height: 900 } } }],
  webServer: {
    command: `${PYTHON} -m uvicorn app.main:app --host ${E2E_HOST} --port ${E2E_PORT} --log-level warning`,
    cwd: BACKEND_DIR,
    url: `${E2E_BASE_URL}/api/health`,
    reuseExistingServer: false,
    timeout: 180_000,
    stdout: 'pipe',
    stderr: 'pipe',
    env: {
      DEMO_MODE: 'true',
      PAYPAL_MODE: 'mock',
      DATABASE_URL: `sqlite:///${E2E_DB_FILE.replace(/\.sqlite3$/, '-capture.sqlite3').split(path.sep).join('/')}`,
      PYTHONPATH: BACKEND_DIR,
      PYTHONUNBUFFERED: '1',
    },
  },
});

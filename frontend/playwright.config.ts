import { defineConfig, devices } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {
  ARTIFACT_DIR,
  BACKEND_DIR,
  DEV_PORT,
  E2E_BASE_URL,
  E2E_DB_FILE,
  E2E_HOST,
  E2E_PORT,
  FRONTEND_DIR,
  REPO_ROOT,
} from './tests/paths';

/**
 * Pinned Playwright version: 1.64.1 (see frontend/package.json).
 * Browser: Chromium only, installed with `npx playwright install chromium`.
 *
 * Windows safety:
 *   - the webServer command is a single executable plus flags, with no `&&`,
 *     no `export`, no shell quoting tricks and no POSIX-only utilities;
 *   - all environment variables are passed through the `env` object rather
 *     than being prefixed onto the command line;
 *   - every path is absolute and built with `node:path`.
 *
 * The server under test is the *production* arrangement: FastAPI serving the
 * built SPA from frontend/dist on one port. That means these tests exercise
 * the same SPA-fallback code path a judge would hit, not a dev-only proxy.
 */
/**
 * Find the Python that has the backend dependencies installed.
 *
 * Order: an explicit MS_PYTHON, then the project's own .venv, then whatever
 * `python` resolves to on PATH.
 *
 * The .venv step matters on Windows. `npm test` is normally run from a
 * terminal sitting in frontend/, which may not have `.\.venv\Scripts\
 * Activate.ps1` applied. Without this, the webServer would launch the system
 * Python, fail with "No module named uvicorn", and surface as an opaque
 * "Timed out waiting 120000ms from config.webServer".
 */
function resolvePython(): string {
  const explicit = process.env['MS_PYTHON'];
  if (explicit !== undefined && explicit !== '') {
    return quoteIfNeeded(explicit);
  }

  const isWindows = process.platform === 'win32';
  const venvCandidates = isWindows
    ? [path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe')]
    : [
        path.join(REPO_ROOT, '.venv', 'bin', 'python3'),
        path.join(REPO_ROOT, '.venv', 'bin', 'python'),
      ];

  for (const candidate of venvCandidates) {
    if (fs.existsSync(candidate)) {
      return quoteIfNeeded(candidate);
    }
  }

  // Deliberately NOT falling back to `python` on PATH. A system interpreter
  // without the backend dependencies produces "No module named uvicorn",
  // which Playwright surfaces only as "Timed out waiting 180000ms from
  // config.webServer" - pointing the reader at entirely the wrong problem.
  // Failing here, with instructions, is far cheaper than that.
  const expected = venvCandidates[0] ?? '(unknown)';
  const createCmd = isWindows
    ? 'py -3.11 -m venv .venv'
    : 'python3.11 -m venv .venv';
  const pipCmd = isWindows
    ? '.venv\\Scripts\\python.exe -m pip install -r backend\\requirements.txt'
    : '.venv/bin/python -m pip install -r backend/requirements.txt';

  throw new Error(
    [
      '',
      'MerchantShield: no Python virtual environment found.',
      '',
      `  Looked for: ${expected}`,
      '',
      'The Playwright run starts the FastAPI backend itself, so it needs an',
      'interpreter that has the backend dependencies installed.',
      '',
      'Create one from the project root:',
      `  ${createCmd}`,
      `  ${pipCmd}`,
      '',
      'Or point at an existing interpreter:',
      isWindows
        ? '  $env:MS_PYTHON = "C:\\path\\to\\python.exe"'
        : '  export MS_PYTHON=/path/to/python',
      '',
    ].join('\n'),
  );
}

/** Absolute Windows paths routinely contain spaces (C:\Users\First Last\...). */
function quoteIfNeeded(value: string): string {
  return value.includes(' ') && !value.startsWith('"') ? `"${value}"` : value;
}

/**
 * Is something already listening on host:port?
 *
 * This has to be answered SYNCHRONOUSLY, here at config-load time, because
 * Playwright starts `webServer` before `globalSetup` runs - so by the time
 * globalSetup executes, our own uvicorn owns the port and any check there
 * would always report "busy". Node has no synchronous socket API, so a short
 * child process does the async part and reports through its exit code.
 *
 * Exit 1 = busy, 0 = free. Any problem running the probe itself fails open:
 * a diagnostic must never be the thing that blocks the suite, and Playwright
 * still has its own built-in "port is already used" check behind this.
 */
function portIsBusy(host: string, port: number): boolean {
  const probe = [
    "const net = require('node:net');",
    'const s = net.createConnection({ host: process.argv[1], port: Number(process.argv[2]) });',
    'const done = (code) => { s.destroy(); process.exit(code); };',
    's.setTimeout(1500);',
    "s.on('connect', () => done(1));",
    "s.on('error', () => done(0));",
    "s.on('timeout', () => done(0));",
  ].join('\n');

  const result = spawnSync(process.execPath, ['-e', probe, host, String(port)], {
    timeout: 5_000,
    stdio: 'ignore',
  });

  if (result.error !== undefined || result.status === null) {
    return false; // fail open
  }
  return result.status === 1;
}

/**
 * True inside a Playwright worker process.
 *
 * Playwright loads this config file again in every worker it spawns. By then
 * our own uvicorn is listening on E2E_PORT, so running the pre-flight there
 * would fail every single test with "port is already in use" - a false alarm
 * caused by the check itself. The probe therefore runs only in the main
 * runner process, which is the only place it is meaningful.
 */
function isWorkerProcess(): boolean {
  return process.env['TEST_WORKER_INDEX'] !== undefined;
}

function assertPortIsFree(host: string, port: number): void {
  if (isWorkerProcess()) {
    return;
  }
  if (!portIsBusy(host, port)) {
    return;
  }
  throw new Error(
    [
      '',
      `MerchantShield: port ${port} on ${host} is already in use.`,
      '',
      'This run refuses to reuse a server it did not start, because a leftover',
      'process would be running OLD code and the suite would report PASS',
      'against it. Do not "fix" this by setting reuseExistingServer: true.',
      '',
      'Find the owner (Windows PowerShell):',
      `  Get-NetTCPConnection -LocalPort ${port},${DEV_PORT} | Select-Object LocalPort,OwningProcess`,
      '  Get-Process -Id <OwningProcess>',
      '',
      'Stop it:',
      '  Stop-Process -Id <OwningProcess>',
      '',
      'Or use a different port:',
      '  $env:MS_E2E_PORT = "8011"',
      '',
    ].join('\n'),
  );
}

const PYTHON = resolvePython();
const isCI = Boolean(process.env['CI']);

assertPortIsFree(E2E_HOST, E2E_PORT);

export default defineConfig({
  testDir: path.join(FRONTEND_DIR, 'tests'),
  globalSetup: path.join(FRONTEND_DIR, 'tests', 'global-setup.ts'),
  outputDir: path.join(ARTIFACT_DIR, 'playwright-output'),

  fullyParallel: false,
  forbidOnly: isCI,
  retries: 0,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 10_000 },

  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(ARTIFACT_DIR, 'playwright-report'), open: 'never' }],
    ['json', { outputFile: path.join(ARTIFACT_DIR, 'playwright-results.json') }],
  ],

  use: {
    baseURL: E2E_BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },

  projects: [
    {
      name: 'desktop-1500x900',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1500, height: 900 } },
    },
    {
      name: 'mobile-390x844',
      use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 } },
    },
  ],

  webServer: {
    command: `${PYTHON} -m uvicorn app.main:app --host ${E2E_HOST} --port ${E2E_PORT} --log-level warning`,
    cwd: BACKEND_DIR,
    url: `${E2E_BASE_URL}/api/health`,
    // Never reuse a server we did not start. A stale uvicorn left over from an
    // earlier session would be running OLD code, and the suite would report
    // PASS against it - the worst possible failure mode for a verification
    // run. globalSetup checks the port first and explains how to free it.
    reuseExistingServer: false,
    // 180s, not the Playwright default of 60s. On Windows the first run pays
    // for Defender scanning a brand-new .venv, cold NTFS caches and Python's
    // first import of FastAPI/SQLAlchemy. A slow cold start is not a failure.
    timeout: 180_000,
    stdout: 'pipe',
    stderr: 'pipe',
    env: {
      DEMO_MODE: 'true',
      PAYPAL_MODE: 'mock',
      DATABASE_URL: `sqlite:///${E2E_DB_FILE.split(path.sep).join('/')}`,
      PYTHONPATH: BACKEND_DIR,
      PYTHONUNBUFFERED: '1',
    },
  },
});

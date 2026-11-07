import { test as base, expect } from '@playwright/test';
import type { ConsoleMessage, Page, TestInfo } from '@playwright/test';
import fs from 'node:fs';
import { artifactPath, ensureArtifactDir } from './paths';

/**
 * Phase 0 browser check - the "walking skeleton".
 *
 * What this proves, and nothing more:
 *   1. the backend answers GET /api/health;
 *   2. the built SPA renders the seeded order's heading;
 *   3. the provenance chip shows the exact label stored in the database;
 *   4. no unexpected console error or uncaught page error occurred.
 *
 * Evidence is written to artifacts/phase-0/<env>/, which this file creates
 * itself, recursively, so a freshly extracted ZIP with no artifacts/ folder
 * works on the first run.
 *
 * Evidence capture is failure-proof: the console log is written from a
 * fixture teardown inside a `finally`, so it survives a failed assertion, a
 * failed navigation or a browser crash. A screenshot is also captured on
 * failure, and screenshots already written are never overwritten or deleted.
 */

/** Console messages we tolerate. Empty: Phase 0 expects a silent console. */
const ALLOWED_CONSOLE_PATTERNS: readonly RegExp[] = [];

interface Recorder {
  readonly lines: string[];
  readonly problems: string[];
}

/** Log files already truncated this run, so each project appends after that. */
const initialisedLogs = new Set<string>();

function attachListeners(page: Page): Recorder {
  const lines: string[] = [];
  const problems: string[] = [];

  page.on('console', (message: ConsoleMessage) => {
    const entry = `[console.${message.type()}] ${message.text()}`;
    lines.push(entry);
    if (message.type() === 'error' || message.type() === 'warning') {
      const tolerated = ALLOWED_CONSOLE_PATTERNS.some((p) => p.test(message.text()));
      if (!tolerated) {
        problems.push(entry);
      }
    }
  });

  page.on('pageerror', (error: Error) => {
    const entry = `[pageerror] ${error.name}: ${error.message}`;
    lines.push(entry);
    problems.push(entry);
  });

  page.on('requestfailed', (request) => {
    const entry = `[requestfailed] ${request.method()} ${request.url()} - ${
      request.failure()?.errorText ?? 'unknown error'
    }`;
    lines.push(entry);
    problems.push(entry);
  });

  return { lines, problems };
}

function writeConsoleLog(testInfo: TestInfo, recorder: Recorder): string {
  const project = testInfo.project.name;
  const file = artifactPath(`console-${project}.log`);

  const isFirst = !initialisedLogs.has(file);
  if (isFirst) {
    initialisedLogs.add(file);
    fs.writeFileSync(
      file,
      [
        '# MerchantShield AI - Phase 0 browser console log',
        `# project : ${project}`,
        `# started : ${new Date().toISOString()}`,
        '',
      ].join('\n'),
      'utf8',
    );
  }

  const body = [
    `--- test: ${testInfo.title}`,
    `    status   : ${testInfo.status ?? 'unknown'}`,
    `    duration : ${testInfo.duration}ms`,
    `    messages : ${recorder.lines.length}`,
    recorder.lines.length > 0
      ? recorder.lines.map((l) => `    ${l}`).join('\n')
      : '    (no console output)',
    '',
  ].join('\n');

  fs.appendFileSync(file, body, 'utf8');
  return file;
}

/**
 * `recorder` depends on `page`, so Playwright tears it down BEFORE the page is
 * closed. That is what makes the finally block able to still screenshot.
 */
const test = base.extend<{ recorder: Recorder }>({
  recorder: async ({ page }, use, testInfo) => {
    ensureArtifactDir();
    const recorder = attachListeners(page);
    try {
      await use(recorder);
    } finally {
      // 1. The console log is written no matter how the test ended.
      let logFile: string | null = null;
      try {
        logFile = writeConsoleLog(testInfo, recorder);
      } catch {
        // Never let evidence-writing mask the real test failure.
      }
      if (logFile !== null) {
        await testInfo
          .attach(`console-${testInfo.project.name}`, {
            path: logFile,
            contentType: 'text/plain',
          })
          .catch(() => undefined);
      }

      // 2. On failure, capture a clearly-named screenshot. This NEVER
      //    overwrites a success screenshot taken earlier in the test.
      if (testInfo.status !== 'passed' && testInfo.status !== 'skipped') {
        const failShot = artifactPath(
          `screenshot-${testInfo.project.name}-FAILED-${slug(testInfo.title)}.png`,
        );
        try {
          await page.screenshot({ path: failShot, fullPage: true });
        } catch {
          // Page may already be gone (crash / navigation failure). A missing
          // screenshot is reported as missing - it is never fabricated.
        }
      }
    }
  },
});

function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 40);
}

test.beforeAll(() => {
  // Create artifacts/phase-0/<env>/ before anything writes into it.
  ensureArtifactDir();
});

test('seeded order renders with its exact source chip and a clean console', async ({
  page,
  recorder,
}, testInfo) => {
  // ---- 1. wait for the API before touching the UI --------------------------
  await expect
    .poll(
      async () => {
        const response = await page.request.get('/api/health');
        return response.status();
      },
      {
        message: 'backend did not become healthy',
        timeout: 30_000,
        intervals: [250, 500, 1000],
      },
    )
    .toBe(200);

  const health = (await (await page.request.get('/api/health')).json()) as {
    status: string;
    phase: string;
    demo_mode: boolean;
  };
  expect(health.status).toBe('ok');
  expect(health.phase).toBe('0');
  expect(health.demo_mode).toBe(true);

  // ---- 2. the SPA renders the seeded order ---------------------------------
  await page.goto('/', { waitUntil: 'networkidle' });

  const heading = page.getByTestId('order-heading');
  await expect(heading).toBeVisible();

  // ---- 3. screenshot BEFORE the strict assertions --------------------------
  // If an assertion below fails we still have the picture of what was on
  // screen, which is the whole point of capturing it.
  const screenshotFile = artifactPath(`screenshot-${testInfo.project.name}.png`);
  await page.screenshot({ path: screenshotFile, fullPage: true });
  await testInfo.attach(`screenshot-${testInfo.project.name}`, {
    path: screenshotFile,
    contentType: 'image/png',
  });

  // ---- 4. the assertions ---------------------------------------------------
  await expect(heading).toHaveText('Order MS-1001');
  await expect(page.getByTestId('order-item')).toHaveText(
    'Aurora X2 Noise-Cancelling Headphones',
  );

  const chip = page.getByTestId('source-chip');
  await expect(chip).toBeVisible();
  // Exact text, not a substring: "SIMULATED" must never read as "PAYPAL_SANDBOX".
  await expect(chip).toHaveText('SIMULATED');
  await expect(chip).toHaveAttribute('data-source', 'SIMULATED');

  const apiOrder = (await (await page.request.get('/api/orders/1')).json()) as {
    source: string;
    created_at: string;
  };
  expect(await chip.innerText()).toBe(apiOrder.source);
  expect(apiOrder.created_at.endsWith('Z')).toBe(true);

  // ---- 5. fail on unexpected console or page errors ------------------------
  expect(
    recorder.problems,
    `Unexpected browser console/page errors:\n${recorder.problems.join('\n')}`,
  ).toEqual([]);
});

test('deep links fall back to the SPA instead of 404ing', async ({ page, recorder }) => {
  const response = await page.goto('/orders/1', { waitUntil: 'networkidle' });
  expect(response?.status()).toBe(200);
  await expect(page.getByTestId('order-heading')).toHaveText('Order MS-1001');

  expect(recorder.problems, recorder.problems.join('\n')).toEqual([]);
});

test('an unmatched /api path returns JSON 404, never SPA html', async ({ page, recorder }) => {
  const response = await page.request.get('/api/definitely-not-a-route');
  expect(response.status()).toBe(404);
  expect(response.headers()['content-type']).toContain('application/json');
  const body = (await response.json()) as { detail: string };
  expect(body.detail).toContain('No API route for');

  expect(recorder.problems, recorder.problems.join('\n')).toEqual([]);
});

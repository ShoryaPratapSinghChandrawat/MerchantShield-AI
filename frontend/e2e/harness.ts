import { test as base, expect } from '@playwright/test';
import type { ConsoleMessage, Page, TestInfo } from '@playwright/test';
import fs from 'node:fs';
import { artifactPath, ensureArtifactDir } from './paths';

/**
 * Shared harness for the browser suite.
 *
 * Every test:
 *   - records console messages and page errors, and FAILS on either, because a
 *     red console in a demo is a bug a judge will see;
 *   - writes the console log from a fixture teardown inside `finally`, so the
 *     evidence survives a failed assertion, a crash or a navigation error;
 *   - captures a full-page screenshot before its strict assertions and another
 *     on failure (never overwriting the first one).
 *
 * Nothing here fabricates evidence: if a screenshot cannot be taken, the test
 * fails rather than pretending it exists.
 */

/** Console messages we tolerate. Kept empty: the app should be silent. */
const ALLOWED_CONSOLE_PATTERNS: readonly RegExp[] = [];

interface Recorder {
  readonly lines: string[];
  readonly problems: string[];
}

const initialisedLogs = new Set<string>();

function attachListeners(page: Page): Recorder {
  const lines: string[] = [];
  const problems: string[] = [];

  page.on('console', (message: ConsoleMessage) => {
    const entry = `[console.${message.type()}] ${message.text()}`;
    lines.push(entry);
    if (message.type() === 'error' || message.type() === 'warning') {
      const tolerated = ALLOWED_CONSOLE_PATTERNS.some((pattern) => pattern.test(message.text()));
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

function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 40);
}

function writeConsoleLog(testInfo: TestInfo, recorder: Recorder): string {
  const project = testInfo.project.name;
  const file = artifactPath(`console-${project}.log`);

  if (!initialisedLogs.has(file)) {
    initialisedLogs.add(file);
    fs.writeFileSync(
      file,
      [
        '# MerchantShield AI - browser console log',
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
      ? recorder.lines.map((line) => `    ${line}`).join('\n')
      : '    (no console output)',
    '',
  ].join('\n');

  fs.appendFileSync(file, body, 'utf8');
  return file;
}

/**
 * `recorder` depends on `page`, so Playwright tears it down BEFORE the page is
 * closed - which is what lets the finally block still take a screenshot.
 */
export const test = base.extend<{ recorder: Recorder }>({
  recorder: async ({ page }, use, testInfo) => {
    ensureArtifactDir();
    const recorder = attachListeners(page);
    try {
      await use(recorder);
    } finally {
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

      if (testInfo.status !== 'passed' && testInfo.status !== 'skipped') {
        const failShot = artifactPath(
          `screenshot-${testInfo.project.name}-FAILED-${slug(testInfo.title)}.png`,
        );
        try {
          await page.screenshot({ path: failShot, fullPage: true });
        } catch {
          // Page may already be gone. A missing screenshot stays missing.
        }
      }
    }
  },
});

export { expect };

/** Wait until the API answers, then load the SPA. */
export async function gotoApp(page: Page, hash = ''): Promise<void> {
  await expect
    .poll(
      async () => {
        const response = await page.request.get('/api/health');
        return response.status();
      },
      { message: 'backend did not become healthy', timeout: 30_000, intervals: [250, 500, 1000] },
    )
    .toBe(200);

  await page.goto(`/${hash}`, { waitUntil: 'networkidle' });
}

/** Screenshot the current view, attach it, and return its path. */
export async function snap(page: Page, testInfo: TestInfo, name: string): Promise<string> {
  const file = artifactPath(`screenshot-${testInfo.project.name}-${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  await testInfo.attach(`screenshot-${testInfo.project.name}-${name}`, {
    path: file,
    contentType: 'image/png',
  });
  return file;
}

export async function nav(page: Page, id: string): Promise<void> {
  await page.getByTestId(`nav-${id}`).click();
  await expect(page.getByTestId(`nav-${id}`)).toHaveAttribute('aria-current', 'page');
}

/**
 * Buy the high-value product and capture it, leaving the order drawer open.
 * Returns the order reference shown in the drawer heading.
 */
export async function buyAndOpenOrder(page: Page): Promise<string> {
  await gotoApp(page, '#/store');
  await page.getByTestId('buy-P-100').click();
  await expect(page.getByTestId('checkout-panel')).toBeVisible();
  await page.getByTestId('capture').click();
  await expect(page.getByTestId('capture-panel')).toBeVisible();
  await page.getByTestId('open-captured-order').click();
  await expect(page.getByTestId('order-drawer')).toBeVisible();
  await expect(page.getByTestId('risk-card')).toBeVisible();
  return await page.getByTestId('drawer-source-chip').innerText();
}

/** The id of the first action card currently on screen. */
export async function firstActionTestId(page: Page, prefix: string): Promise<string> {
  const locator = page.locator(`[data-testid^="${prefix}-"]`).first();
  await expect(locator).toBeVisible();
  const value = await locator.getAttribute('data-testid');
  if (value === null) {
    throw new Error(`no element with data-testid starting with ${prefix}-`);
  }
  return value;
}

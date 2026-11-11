/**
 * Capture real screenshots of the running app for the explainer video.
 *
 * Every image this writes comes from the app actually rendering in Chromium —
 * no mock-ups, no redrawn UI. The video builder (scripts/build_video.py) then
 * animates these stills and adds narration.
 *
 * This file lives outside e2e/ on purpose: it is NOT part of the verified
 * browser suite and must not change its test count. It is a capture tool.
 *
 * Usage (from frontend/):
 *   npx playwright test --config playwright.capture.config.ts
 *
 * Output: ../artifacts/video/frames/NN-name.png
 */
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { REPO_ROOT } from '../e2e/paths';

const OUT = path.join(REPO_ROOT, 'artifacts', 'video', 'frames');

test.beforeAll(() => {
  fs.rmSync(OUT, { recursive: true, force: true });
  fs.mkdirSync(OUT, { recursive: true });
});

test('capture the story frames', async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 900 });

  let n = 0;
  const shot = async (name: string): Promise<void> => {
    n += 1;
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(OUT, `${String(n).padStart(2, '0')}-${name}.png`) });
  };
  /** Scroll a known card to the top of the viewport, then shoot. */
  const shotCard = async (name: string, testId: string): Promise<void> => {
    await page.getByTestId(testId).scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await shot(name);
  };

  // ---------------------------------------------------------------- overview
  await page.goto('/#/overview');
  await page.waitForSelector('text=Highest-risk orders');
  await shot('overview');

  // ------------------------------------------------------------------ orders
  await page.goto('/#/orders');
  await page.waitForSelector('tbody tr');
  await shot('orders');

  // ------------------------------------------------- order drawer: the case
  await page.locator('tbody tr').first().click();
  await page.waitForSelector('[data-testid="risk-card"]');
  await shot('order-facts');
  await shotCard('risk-reasons', 'risk-card');
  await shotCard('model-estimate', 'ml-card');
  await shotCard('evidence-checklist', 'evidence-card');

  // ------------------------------------------------------ planner proposals
  await page.getByTestId('run-agent').click();
  await page.waitForTimeout(1800);
  await shotCard('planner-proposals', 'actions-card');

  const approve = page.getByRole('button', { name: 'Approve', exact: true }).first();
  if ((await approve.count()) > 0) {
    await approve.click();
    await page.waitForTimeout(1100);
    await shotCard('proposal-approved', 'actions-card');
    const execute = page.getByRole('button', { name: 'Execute', exact: true }).first();
    if ((await execute.count()) > 0) {
      await execute.click();
      await page.waitForTimeout(1800);
      await shotCard('proposal-executed', 'actions-card');
    }
  }

  // ------------------------------- the guided story creates a real dispute
  // The drawer is closed first: executing an action reloads the order and the
  // scroll position of a long drawer is not stable enough to capture from.
  await page.goto('/#/walkthrough');
  await page.waitForTimeout(800);
  await shot('walkthrough');
  await page.getByTestId('walkthrough-run').click();
  await expect(page.getByTestId('story-card')).toBeVisible({ timeout: 25_000 });
  await page.waitForTimeout(800);
  await shot('walkthrough-story');

  await page.getByTestId('walkthrough-open-dispute').click();
  await expect(page.getByTestId('dispute-detail')).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(600);
  await shot('dispute-packet');

  const generate = page.getByTestId('generate-draft');
  if ((await generate.count()) > 0) {
    await generate.click();
    await page.waitForTimeout(2000);
    await shotCard('draft-template', 'drafts-card');

    const approveDraft = page.getByTestId('approve-draft');
    if ((await approveDraft.count()) > 0) {
      await approveDraft.click();
      await page.waitForTimeout(1200);
      await shotCard('draft-approved', 'drafts-card');
      const submit = page.getByTestId('submit-dispute');
      if ((await submit.count()) > 0) {
        await submit.click();
        await page.waitForTimeout(1600);
        await shotCard('submit-simulated', 'drafts-card');
      }
    }
  }

  // ------------------------------------------------------------------- audit
  await page.goto('/#/audit');
  await page.waitForSelector('table');
  await shot('audit');

  // ------------------------------------------------------------- methodology
  await page.goto('/#/about');
  await page.waitForTimeout(900);
  await shot('methodology');
  await page.mouse.move(750, 500);
  await page.mouse.wheel(0, 700);
  await page.waitForTimeout(500);
  await shot('methodology-more');
  await page.mouse.wheel(0, 900);
  await page.waitForTimeout(500);
  await shot('methodology-limits');

  const files = fs.readdirSync(OUT).sort();
  // eslint-disable-next-line no-console
  console.log(`captured ${String(files.length)} frames:\n${files.join('\n')}`);
  expect(files.length).toBeGreaterThanOrEqual(14);
});

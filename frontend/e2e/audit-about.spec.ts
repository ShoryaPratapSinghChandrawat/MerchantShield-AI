import { expect, gotoApp, nav, snap, test } from './harness';

test('the methodology page prints the stored metrics and baselines', async ({ page, recorder }, testInfo) => {
  await gotoApp(page, '#/about');

  await expect(page.getByTestId('about-page')).toBeVisible();
  await expect(page.getByTestId('metrics-card')).toContainText('SYNTHETIC DATA');
  await expect(page.getByTestId('metrics-card')).toContainText('Majority class');
  await expect(page.getByTestId('metrics-card')).toContainText('Phase-1 rule score');
  await expect(page.getByTestId('metrics-card')).toContainText('ROC AUC');
  await expect(page.getByTestId('metrics-card')).toContainText('Confusion matrix');

  // The three labels are listed with their real counts.
  await expect(page.getByTestId('label-PAYPAL_SANDBOX')).toBeVisible();
  await expect(page.getByTestId('label-SIMULATED')).toBeVisible();
  await expect(page.getByTestId('label-MOCK')).toBeVisible();

  // And the page states what is NOT built.
  await expect(page.getByTestId('honesty-card')).toContainText('What is not built');
  await expect(page.getByTestId('honesty-card')).toContainText('No production PayPal access');

  await snap(page, testInfo, 'methodology');
  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

test('the audit log filters by event and keeps its source labels', async ({ page, recorder }, testInfo) => {
  await gotoApp(page, '#/audit');

  await expect(page.getByTestId('audit-page')).toBeVisible();
  const table = page.getByTestId('audit-table');
  await expect(table).toBeVisible();

  // Seeded demo writes an audit row, so the table is never empty here.
  const rows = page.locator('tr[data-testid^="audit-row-"]');
  await expect(rows.first()).toBeVisible();
  const before = await rows.count();
  expect(before).toBeGreaterThan(0);

  await page.getByTestId('audit-event-filter').fill('demo_seeded');
  await expect(page.locator('tr[data-testid^="audit-row-"]').first()).toBeVisible();
  const filtered = page.locator('tr[data-testid^="audit-row-"]');
  const filteredCount = await filtered.count();
  expect(filteredCount).toBeGreaterThan(0);
  expect(filteredCount).toBeLessThanOrEqual(before);

  // Every visible row carries a real provenance chip.
  const chips = page.locator('[data-testid^="audit-row-source-"]');
  expect(await chips.count()).toBe(filteredCount);

  await snap(page, testInfo, 'audit');
  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

test('the audit log is not editable from the UI', async ({ page, recorder }) => {
  await gotoApp(page, '#/audit');

  // No create/edit/delete affordance exists on the page.
  await expect(page.getByRole('button', { name: /delete|edit|clear/i })).toHaveCount(0);

  await nav(page, 'audit');
  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

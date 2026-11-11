import { expect, gotoApp, nav, snap, test } from './harness';

test('the dashboard renders real numbers and a clean console', async ({ page, recorder }, testInfo) => {
  await gotoApp(page, '#/overview');

  await expect(page.getByTestId('dashboard')).toBeVisible();
  await expect(page.getByTestId('stat-orders')).toBeVisible();
  await expect(page.getByTestId('stat-high-risk')).toBeVisible();
  await expect(page.getByTestId('stat-awaiting')).toBeVisible();
  await expect(page.getByTestId('stat-disputes')).toBeVisible();

  // The three provenance labels are always explained, never colour-only.
  await expect(page.getByTestId('legend-sandbox')).toHaveText('PAYPAL_SANDBOX');
  await expect(page.getByTestId('legend-simulated')).toHaveText('SIMULATED');
  await expect(page.getByTestId('legend-mock')).toHaveText('MOCK');

  // The runtime card reports the mode this instance is actually in.
  await expect(page.getByTestId('runtime-card')).toContainText('PayPal mode');
  await expect(page.getByTestId('runtime-card')).toContainText('mock');

  // Every seeded order row carries a risk badge with a real level.
  const rows = page.locator('[data-testid^="dashboard-order-row-"]');
  await expect(rows.first()).toBeVisible();
  const badges = page.locator('[data-testid="risk-badge"]');
  expect(await badges.count()).toBeGreaterThan(0);
  const firstRisk = await badges.first().getAttribute('data-risk');
  expect(['LOW', 'MEDIUM', 'HIGH']).toContain(firstRisk);

  await snap(page, testInfo, 'dashboard');

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

test('every section in the navigation loads', async ({ page, recorder }) => {
  await gotoApp(page, '#/overview');

  await nav(page, 'orders');
  await expect(page.getByTestId('orders-table')).toBeVisible();

  await nav(page, 'store');
  await expect(page.getByTestId('product-P-100')).toBeVisible();

  await nav(page, 'disputes');
  await expect(page.getByTestId('disputes-page')).toBeVisible();

  await nav(page, 'audit');
  await expect(page.getByTestId('audit-page')).toBeVisible();

  await nav(page, 'walkthrough');
  await expect(page.getByTestId('walkthrough-page')).toBeVisible();

  await nav(page, 'about');
  await expect(page.getByTestId('about-page')).toBeVisible();
  await expect(page.getByTestId('metrics-card')).toBeVisible();

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

import { expect, gotoApp, snap, test } from './harness';

test('the guided story runs every stage and labels each one', async ({ page, recorder }, testInfo) => {
  await gotoApp(page, '#/walkthrough');

  await page.getByTestId('walkthrough-run').click();

  const story = page.getByTestId('story-card');
  await expect(story).toBeVisible({ timeout: 20_000 });

  const sourceChips = page.locator('[data-testid^="walkthrough-source-"]');
  await expect(sourceChips.first()).toBeVisible();
  const steps = await sourceChips.count();
  expect(steps).toBeGreaterThanOrEqual(8);

  // Each chip is one of the three real labels - no fourth "unknown" state.
  for (let index = 0; index < steps; index += 1) {
    const text = await sourceChips.nth(index).innerText();
    expect(['PAYPAL_SANDBOX', 'SIMULATED', 'MOCK']).toContain(text);
  }

  // The story executed at least one action and opened a dispute.
  await expect(story).toContainText(/action\(s\) executed/);

  await snap(page, testInfo, 'walkthrough-story');

  await page.getByTestId('walkthrough-open-dispute').click();
  await expect(page.getByTestId('dispute-detail')).toBeVisible();

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

test('reset demo reports what it deleted and keeps live rows', async ({ page, recorder }) => {
  await gotoApp(page, '#/walkthrough');

  // Read the state from the API itself rather than assuming an order of tests:
  // this suite shares one database, and a previous spec may already have reset
  // and re-seeded it.
  interface OrderRow {
    order_ref: string;
    is_demo: boolean;
  }
  const readOrders = async (): Promise<OrderRow[]> => {
    const response = await page.request.get('/api/orders');
    expect(response.status()).toBe(200);
    const body = (await response.json()) as { items: OrderRow[] };
    return body.items;
  };

  const before = await readOrders();
  const demoBefore = before.filter((order) => order.order_ref.startsWith('MS-2')).length;
  const liveBefore = before.filter((order) => order.is_demo === false).length;

  await page.getByTestId('walkthrough-reset').click();

  const summary = page.getByTestId('reset-summary');
  await expect(summary).toBeVisible();
  await expect(summary).toContainText('Deleted');
  await expect(summary).toContainText('Live orders kept');

  // Every demo story order is gone; a storefront order is not.
  const afterReset = await readOrders();
  expect(afterReset.filter((order) => order.order_ref.startsWith('MS-2'))).toHaveLength(0);
  expect(afterReset.filter((order) => order.is_demo === false).length).toBe(liveBefore);

  // The reported count is the real count, not a constant.
  await expect(summary).toContainText(`Deleted ${demoBefore} orders`);

  // Re-seeding is honest about what it did. The API seeds only into an empty
  // database, so "Seeded 0" is the CORRECT answer on a shared run, and the UI
  // must report it rather than claim 15.
  await page.getByTestId('walkthrough-seed').click();
  await expect(summary).toContainText(/Seeded \d+ demo orders/);
  const seeded = Number(/Seeded (\d+) demo orders/.exec(await summary.innerText())?.[1] ?? '-1');
  expect(seeded).toBeGreaterThanOrEqual(0);

  const afterSeed = await readOrders();
  expect(afterSeed.filter((order) => order.order_ref.startsWith('MS-2'))).toHaveLength(seeded);

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

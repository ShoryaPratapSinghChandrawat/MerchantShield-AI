import { buyAndOpenOrder, expect, firstActionTestId, gotoApp, snap, test } from './harness';

/**
 * The full action protocol through the UI: propose -> PENDING -> approve ->
 * APPROVED -> execute -> EXECUTED, with the before/after diff and the real
 * MOCK label on the external call.
 */
test('a tracking action goes propose -> approve -> execute, once', async ({ page, recorder }, testInfo) => {
  const source = await buyAndOpenOrder(page);
  // A mock-mode build labels a storefront order MOCK; a Sandbox build labels it
  // PAYPAL_SANDBOX. Either is fine - an unlabelled record would not be.
  expect(['MOCK', 'PAYPAL_SANDBOX']).toContain(source);

  // The fresh order has no tracking, so the risk card must be there.
  await expect(page.getByTestId('risk-card')).toContainText('tracking');

  await page.getByTestId('propose-tracking-input').fill('1Z999AA10123456784');
  await page.getByTestId('propose-tracking').click();

  const approveTestId = await firstActionTestId(page, 'approve');
  const actionId = approveTestId.replace('approve-', '');

  await expect(page.getByTestId(`action-status-${actionId}`)).toHaveText('PENDING');
  await snap(page, testInfo, 'action-pending');

  await page.getByTestId(`approve-${actionId}`).click();
  await expect(page.getByTestId(`action-status-${actionId}`)).toHaveText('APPROVED');

  await page.getByTestId(`execute-${actionId}`).click();
  await expect(page.getByTestId(`action-status-${actionId}`)).toHaveText('EXECUTED', {
    timeout: 15_000,
  });

  // The external call is labelled with its real source, not implied to be live.
  const sourceChip = page.getByTestId(`action-source-${actionId}`);
  await expect(sourceChip).toBeVisible();
  // Regression: this chip used to render PAYPAL_SANDBOX for any non-MOCK result
  // source, including SIMULATED (see BUG-0020). A mock-mode build must never
  // show a Sandbox chip on an action it served itself.
  await expect(sourceChip).toHaveAttribute('data-source', /^(MOCK|PAYPAL_SANDBOX|SIMULATED)$/);
  if (process.env['PAYPAL_MODE'] !== 'sandbox') {
    await expect(sourceChip).not.toHaveAttribute('data-source', 'PAYPAL_SANDBOX');
  }

  // The diff is on screen: before null, after the tracking number.
  const card = page.getByTestId(`action-${actionId}`);
  await expect(card).toContainText('tracking_number');
  await expect(card).toContainText('1Z999AA10123456784');

  await snap(page, testInfo, 'action-executed');

  // The audit trail records the execution against this order.
  await expect(page.getByTestId('order-audit-card')).toContainText('action_executed');

  // There is no execute button on an EXECUTED action: it cannot run twice.
  await expect(page.getByTestId(`execute-${actionId}`)).toHaveCount(0);

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

test('the planner proposes PENDING actions and cannot approve them', async ({ page, recorder }) => {
  await gotoApp(page, '#/orders');

  const firstRow = page.locator('[data-testid^="order-row-"]').first();
  await expect(firstRow).toBeVisible();
  await firstRow.click();
  await expect(page.getByTestId('order-drawer')).toBeVisible();

  await page.getByTestId('run-agent').click();

  const statuses = page.locator('[data-testid^="action-status-"]');
  await expect(statuses.first()).toBeVisible();
  const count = await statuses.count();
  expect(count).toBeGreaterThan(0);
  for (let index = 0; index < count; index += 1) {
    await expect(statuses.nth(index)).toHaveText('PENDING');
  }

  // The approval buttons exist (a human can act) but nothing is auto-approved.
  await expect(page.locator('[data-testid^="approve-"]').first()).toBeVisible();

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

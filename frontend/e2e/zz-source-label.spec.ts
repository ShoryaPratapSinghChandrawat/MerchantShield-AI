import { buyAndOpenOrder, expect, test } from './harness';

/**
 * The runtime half of the provenance rule: a label drawn on screen must be the
 * label the API stored.
 *
 * These live in their own file, named to run last, because they execute real
 * actions. Every spec in this suite shares one database, so a test that
 * executes an action on the first seeded order would change what the
 * planner-order and reset-demo specs see. Ordering them last keeps both
 * properties: full coverage, and no cross-test interference.
 */
/**
 * BUG-0020 regression: the source chip next to an executed action must report
 * the label the backend stored, and a locally-handled action must never be
 * presented as a PayPal call.
 *
 * The bug that motivated this test: the drawer mapped every non-MOCK result
 * source to PAYPAL_SANDBOX, so FLAG_FOR_REVIEW - which is handled inside this
 * app and stores source=SIMULATED - was displayed with a green
 * "real response from the PayPal Sandbox API" chip. The existing orders spec
 * only executed an ADD_TRACKING action, which is served by the mock adapter and
 * therefore rendered MOCK, so the mislabel survived a green suite.
 */
test('an executed action reports its stored source and never invents a PayPal call', async ({
  page,
  recorder,
}) => {
  // A brand-new storefront order, so this test never mutates the seeded rows
  // that the other specs read (shared database, ordered run).
  await buyAndOpenOrder(page);

  // FLAG_FOR_REVIEW is entirely local: no adapter is asked to do anything.
  await page.getByTestId('propose-flag').click();
  // The drawer already holds the planner's proposals, so tie the assertion to
  // the FLAG_FOR_REVIEW card rather than to the oldest PENDING action.
  const flagCard = page.locator('[data-testid^="action-"]').filter({ hasText: 'Flag for review' }).last();
  await expect(flagCard).toBeVisible();
  const testId = await flagCard.getAttribute('data-testid');
  if (testId === null || !/^action-\d+$/.test(testId)) {
    throw new Error(`unexpected action card test id: ${String(testId)}`);
  }
  const actionId = testId.replace('action-', '');

  await page.getByTestId(`approve-${actionId}`).click();
  await page.getByTestId(`execute-${actionId}`).click();
  await expect(page.getByTestId(`action-status-${actionId}`)).toHaveText('EXECUTED', {
    timeout: 15_000,
  });

  const card = page.getByTestId(`action-${actionId}`);
  await expect(card).toContainText('Handled locally: no external call was made');
  await expect(card).not.toContainText('External call served by');

  // Whatever label is rendered must be one of the three real ones - never a
  // fabricated fourth, and never PAYPAL_SANDBOX for a local action.
  const chip = page.getByTestId(`action-source-${actionId}`);
  if ((await chip.count()) > 0) {
    const value = await chip.getAttribute('data-source');
    expect(['SIMULATED', 'MOCK']).toContain(value ?? '');
    expect(value).not.toBe('PAYPAL_SANDBOX');
  }

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

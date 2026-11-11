import { expect, gotoApp, nav, snap, test } from './harness';

/**
 * Checkout -> capture -> order. In a mock-mode build the approval step must be
 * an in-app screen that says MOCK, never a pretend PayPal page.
 */
test('checkout and capture create a labelled order', async ({ page, recorder }, testInfo) => {
  await gotoApp(page, '#/store');

  await expect(page.getByTestId('product-P-100')).toContainText('Aurora X2');
  await expect(page.getByTestId('product-P-100')).toContainText('high value');

  await page.getByTestId('buy-P-100').click();
  await expect(page.getByTestId('checkout-panel')).toBeVisible();
  await expect(page.getByTestId('checkout-source')).toHaveText('MOCK');
  await expect(page.getByTestId('checkout-panel')).toContainText('there is no PayPal page here');
  await expect(page.getByTestId('checkout-panel')).toContainText('MOCK-ORDER-');

  await snap(page, testInfo, 'store-checkout');

  await page.getByTestId('capture').click();
  await expect(page.getByTestId('capture-panel')).toBeVisible();
  await expect(page.getByTestId('capture-source')).toHaveText('MOCK');
  await expect(page.getByTestId('capture-panel')).toContainText('no PayPal account was contacted');

  await snap(page, testInfo, 'store-captured');

  // The captured order exists as a real order behind the drawer.
  await page.getByTestId('open-captured-order').click();
  await expect(page.getByTestId('order-drawer')).toBeVisible();
  await expect(page.getByTestId('order-detail')).toContainText('COMPLETED');

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

test('an unknown product is a visible error, not a silent no-op', async ({ page, recorder }) => {
  await gotoApp(page, '#/store');
  await nav(page, 'store');

  // Ask the API directly: the UI never offers an unknown product, so the 422
  // contract is checked at the boundary it actually protects.
  const response = await page.request.post('/api/store/checkout', {
    data: { product_id: 'NOT-A-PRODUCT' },
  });
  expect(response.status()).toBe(422);

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

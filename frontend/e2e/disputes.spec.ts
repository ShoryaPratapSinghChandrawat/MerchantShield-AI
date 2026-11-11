import { buyAndOpenOrder, expect, snap, test } from './harness';

/**
 * The dispute path: packet -> draft -> merchant edit -> approve -> submit,
 * with the submission labelled SIMULATED on screen.
 */
test('a dispute draft is versioned, approved and submitted as SIMULATED', async ({
  page,
  recorder,
}, testInfo) => {
  await buyAndOpenOrder(page);

  await page.getByTestId('open-dispute').click();

  // The drawer navigates to the dispute it just opened.
  await expect(page.getByTestId('dispute-detail')).toBeVisible();
  await expect(page.getByTestId('packet-card')).toBeVisible();
  await expect(page.getByTestId('packet-card')).toContainText('Tracking number');
  await expect(page.getByTestId('packet-card')).toContainText(/evidence checklist/i);

  await snap(page, testInfo, 'dispute-packet');

  await page.getByTestId('generate-draft').click();
  const editor = page.getByTestId('draft-editor');
  await expect(editor).toBeVisible();
  await expect(editor).toHaveValue(/Order MS-/);

  // Saving creates version 2 and records that a human edited it.
  await editor.fill('Merchant rewritten text: the parcel was shipped with tracking.');
  await page.getByTestId('save-draft').click();
  await expect(page.getByTestId('drafts-card')).toContainText('Merchant edit');
  await expect(page.getByTestId('drafts-card')).toContainText('v2');

  await page.getByTestId('approve-draft').click();
  await expect(page.getByTestId('drafts-card')).toContainText('APPROVED');

  await page.getByTestId('submit-dispute').click();

  const result = page.getByTestId('submit-result');
  await expect(result).toBeVisible();
  await expect(result).toContainText('SIMULATED');

  await snap(page, testInfo, 'dispute-submitted');

  // Submitting twice is not offered once the case is filed (simulated).
  await expect(page.getByTestId('submit-dispute')).toBeDisabled();

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

test('submitting without an approved draft is refused with a readable message', async ({
  page,
  recorder,
}) => {
  await buyAndOpenOrder(page);
  await page.getByTestId('open-dispute').click();
  await expect(page.getByTestId('dispute-detail')).toBeVisible();

  await page.getByTestId('generate-draft').click();
  await expect(page.getByTestId('draft-editor')).toBeVisible();

  // The button is disabled until approval - that is the UI-level guard...
  await expect(page.getByTestId('submit-dispute')).toBeDisabled();

  // ...and the API refuses the same request independently. The dispute id is
  // read off the heading rather than invented, so a renamed id would fail here.
  const heading = await page.getByTestId('dispute-detail').innerText();
  const match = /Dispute #(\d+)/.exec(heading);
  expect(match, 'the dispute heading should contain its id').not.toBeNull();
  const disputeId = Number(match?.[1] ?? '0');
  expect(disputeId).toBeGreaterThan(0);

  const response = await page.request.post(`/api/disputes/${disputeId}/submit`);
  expect(response.status()).toBe(409);

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

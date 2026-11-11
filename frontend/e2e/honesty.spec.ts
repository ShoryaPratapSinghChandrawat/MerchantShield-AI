import { expect, gotoApp, nav, test } from './harness';

/**
 * The rendered-text half of the honesty check (MASTER 10.9). The backend test
 * scans the source files; this one scans what a judge actually reads on screen.
 *
 * A banned phrase is allowed only inside a sentence that denies it - the same
 * rule as the backend scanner, so a page cannot slip a claim through by
 * re-wording the surrounding paragraph.
 */
const BANNED = [
  'win probability',
  'chance to win',
  'money protected',
  'fewer disputes',
  'fully validated',
  'exactly-once',
];

const DENIALS = ['not', 'no', 'never', 'cannot', 'does not'];

const PAGES = ['overview', 'orders', 'store', 'disputes', 'audit', 'walkthrough', 'about'] as const;

function violations(text: string): string[] {
  const sentences = text.split(/(?<=[.!?])\s+|\n+/).filter((part) => part.trim() !== '');
  const found: string[] = [];
  for (const sentence of sentences) {
    const lowered = sentence.toLowerCase();
    for (const phrase of BANNED) {
      if (!lowered.includes(phrase)) {
        continue;
      }
      const denies = DENIALS.some((word) => lowered.includes(word));
      if (!denies) {
        found.push(`"${phrase}" in: ${sentence.trim().slice(0, 160)}`);
      }
    }
  }
  return found;
}

test('no page makes an unmeasured claim', async ({ page, recorder }) => {
  await gotoApp(page, '#/overview');

  for (const id of PAGES) {
    await nav(page, id);
    // Let the page finish its own fetches before reading the text.
    await page.waitForLoadState('networkidle');
    const text = await page.locator('main').innerText();
    const found = violations(text);
    expect(found, `page ${id} contains an unmeasured claim:\n${found.join('\n')}`).toHaveLength(0);
  }

  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

test('the scanner would catch a planted claim', async ({ page, recorder }) => {
  // Prove the check can fail: feed it a sentence that a marketing page would
  // plausibly ship, and require it to be flagged.
  const planted = 'MerchantShield gives you an 80% win probability on every dispute.';
  expect(violations(planted).length).toBeGreaterThan(0);

  await gotoApp(page, '#/overview');
  expect(recorder.problems, `console problems:\n${recorder.problems.join('\n')}`).toHaveLength(0);
});

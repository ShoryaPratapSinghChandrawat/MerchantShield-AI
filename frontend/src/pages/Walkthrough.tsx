import { useState } from 'react';
import { ApiRequestError, resetDemo, runStory, seedDemo } from '../api/client';
import { SourceChip } from '../components/SourceChip';
import { Button, Card, CardHeader, ErrorBanner, Pill } from '../components/ui';
import type { StoryRun } from '../types';

const STAGES = [
  {
    title: '1. A buyer pays',
    body: 'A PayPal order is created from the storefront and captured. With no credentials configured the mock adapter answers, and every record says MOCK. With Sandbox credentials the same code path talks to api-m.sandbox.paypal.com.',
  },
  {
    title: '2. The clock moves',
    body: 'The demo fast-forwards the order to 41 days old with no tracking number - the exact shape of a dispute that is about to happen.',
  },
  {
    title: '3. The rules score it',
    body: 'Twenty-five hand-written rules over your own order fields produce a 0-1 score and a list of reasons, each with a direction and a point value. Nothing is a black box.',
  },
  {
    title: '4. The planner proposes',
    body: 'The agent reads the assessment and proposes actions - add tracking, message the buyer, flag for review. It cannot approve or execute anything: proposals arrive PENDING.',
  },
  {
    title: '5. You approve, it executes',
    body: 'Execution is claimed with a single conditional UPDATE, so eight concurrent clicks produce one claim and one external call. The before/after diff is stored on the action.',
  },
  {
    title: '6. If the outcome is unclear',
    body: 'A timeout is UNKNOWN, not FAILED. A blind retry is never offered; you reconcile against PayPal, and only then does the action move.',
  },
  {
    title: '7. The dispute arrives',
    body: 'An evidence packet lists the seven documents a merchant needs, what is present, what is missing and what to do about each one.',
  },
  {
    title: '8. A draft, then your words',
    body: 'A deterministic template or (with a key) a Gemini draft that passes a hallucination guard. Every version records whether it was an AI draft, a template, or your edit.',
  },
  {
    title: '9. Submit - labelled honestly',
    body: 'Submission is recorded as SIMULATED. No PayPal dispute API call is made, and the screen says so rather than implying a case was filed.',
  },
];

export function WalkthroughPage({
  onOpenOrder,
  onGotoDispute,
}: {
  readonly onOpenOrder: (orderId: number) => void;
  readonly onGotoDispute: (disputeId: number) => void;
}): React.JSX.Element {
  const [story, setStory] = useState<StoryRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<'story' | 'reset' | 'seed' | null>(null);
  const [resetSummary, setResetSummary] = useState<string | null>(null);

  async function run(which: 'story' | 'reset' | 'seed'): Promise<void> {
    setBusy(which);
    setError(null);
    try {
      if (which === 'story') {
        setStory(await runStory());
      } else if (which === 'reset') {
        const result = await resetDemo();
        const deleted = (result['deleted'] ?? {}) as Record<string, number>;
        const kept = (result['kept_live_orders'] ?? []) as number[];
        setStory(null);
        setResetSummary(
          `Deleted ${Object.entries(deleted)
            .map(([table, count]) => `${count} ${table}`)
            .join(', ')}. Live orders kept: ${kept.length === 0 ? 'none to keep' : kept.join(', ')}.`,
        );
      } else {
        const result = await seedDemo();
        setResetSummary(`Seeded ${String(result['inserted'] ?? 0)} demo orders.`);
      }
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'That action failed.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4" data-testid="walkthrough-page">
      <Card>
        <CardHeader
          title="Guided walkthrough"
          subtitle="The nine stages a dispute actually travels through, and what this build does at each one."
          action={
            <div className="flex flex-wrap gap-2">
              <Button tone="primary" busy={busy === 'story'} testId="walkthrough-run" onClick={() => void run('story')}>
                Run it live
              </Button>
              <Button tone="secondary" busy={busy === 'seed'} testId="walkthrough-seed" onClick={() => void run('seed')}>
                Seed demo
              </Button>
              <Button tone="danger" busy={busy === 'reset'} testId="walkthrough-reset" onClick={() => void run('reset')}>
                Reset demo
              </Button>
            </div>
          }
        />
        <div className="px-4 py-3">
          {error !== null && <ErrorBanner message={error} />}
          {resetSummary !== null && (
            <p className="mb-3 rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700" data-testid="reset-summary">
              {resetSummary}
            </p>
          )}
          <p className="text-xs text-slate-600">
            “Reset demo” deletes only rows this app created as demo data. An order that came from a
            real PayPal Sandbox response is kept, together with its audit trail - that rule is
            covered by its own test.
          </p>
        </div>
      </Card>

      {story !== null && (
        <Card testId="story-card">
          <CardHeader
            title={`Story ${story.run_id}`}
            subtitle={`${story.order_ref} · ${story.executed_action_ids.length} action(s) executed · dispute #${story.dispute_id}`}
            action={<Pill tone="info">{story.steps.length} steps</Pill>}
          />
          <ol className="divide-y divide-slate-100">
            {story.steps.map((step, index) => (
              <li key={`${step.step}-${index}`} className="flex items-start gap-3 px-4 py-2">
                <span className="mt-0.5 w-5 flex-none font-mono text-[11px] text-slate-400">
                  {index + 1}
                </span>
                <div className="flex-1">
                  <p className="text-xs font-semibold text-slate-800">{step.title}</p>
                  <p className="text-[11px] text-slate-600">{step.detail}</p>
                </div>
                <SourceChip source={step.source} testId={`walkthrough-source-${index}`} />
              </li>
            ))}
          </ol>
          <div className="flex flex-wrap gap-2 border-t border-slate-100 px-4 py-3">
            <Button tone="secondary" onClick={() => onOpenOrder(story.order_id)} testId="walkthrough-open-order">
              Open the order
            </Button>
            <Button tone="secondary" onClick={() => onGotoDispute(story.dispute_id)} testId="walkthrough-open-dispute">
              Open the dispute
            </Button>
          </div>
          <p className="border-t border-slate-100 px-4 py-2 text-[11px] text-slate-500">{story.note}</p>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {STAGES.map((stage) => (
          <Card key={stage.title} className="p-4">
            <p className="text-sm font-semibold text-slate-900">{stage.title}</p>
            <p className="mt-1 text-xs text-slate-600">{stage.body}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}

import { useCallback, useEffect, useState } from 'react';
import {
  ApiRequestError,
  fetchActions,
  fetchDisputes,
  fetchHealth,
  fetchOrders,
  runStory,
} from '../api/client';
import { SourceChip } from '../components/SourceChip';
import { Button, Card, CardHeader, ErrorBanner, Loading, RiskBadge, Stat } from '../components/ui';
import { money } from '../lib/format';
import type { ActionRecord, DisputeSummary, Health, OrderRow, StoryRun } from '../types';

interface DashboardData {
  readonly health: Health;
  readonly orders: OrderRow[];
  readonly actions: ActionRecord[];
  readonly disputes: DisputeSummary[];
}

export function Dashboard({
  onOpenOrder,
  onGoto,
}: {
  readonly onOpenOrder: (orderId: number) => void;
  readonly onGoto: (page: string) => void;
}): React.JSX.Element {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [story, setStory] = useState<StoryRun | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (): Promise<void> => {
    setError(null);
    try {
      const [health, orders, actions, disputes] = await Promise.all([
        fetchHealth(),
        fetchOrders(),
        fetchActions(),
        fetchDisputes(),
      ]);
      setData({ health, orders, actions, disputes });
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'Could not load the dashboard.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function runDemo(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const result = await runStory();
      setStory(result);
      await load();
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'The demo story could not run.');
    } finally {
      setBusy(false);
    }
  }

  if (error !== null) {
    return <ErrorBanner title="Dashboard unavailable" message={error} onRetry={() => void load()} />;
  }

  if (data === null) {
    return <Loading label="Loading dashboard…" />;
  }

  const { health, orders, actions, disputes } = data;
  const highRisk = orders.filter((order) => order.risk_level === 'HIGH');
  const awaiting = actions.filter((action) => action.status === 'PENDING');
  const unknown = actions.filter((action) => action.status === 'UNKNOWN');
  const openDisputes = disputes.filter((dispute) => dispute.status !== 'SUBMITTED');
  const exposure = highRisk.reduce((total, order) => total + Number.parseFloat(order.amount), 0);

  return (
    <div className="space-y-5" data-testid="dashboard">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="Orders in view"
          value={orders.length}
          hint={orders.some((order) => order.is_demo) ? 'demo data only' : 'no demo data loaded'}
          testId="stat-orders"
        />
        <Stat
          label="High risk"
          value={highRisk.length}
          hint={`${money(String(exposure.toFixed(2)), 'USD')} of order value`}
          testId="stat-high-risk"
        />
        <Stat
          label="Awaiting your approval"
          value={awaiting.length}
          hint="Nothing executes without it"
          testId="stat-awaiting"
        />
        <Stat
          label="Open disputes"
          value={openDisputes.length}
          hint={unknown.length > 0 ? `${unknown.length} action(s) UNKNOWN` : 'none needing reconcile'}
          testId="stat-disputes"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2" testId="risk-queue">
          <CardHeader
            title="Highest-risk orders"
            subtitle="Rule score from your own order fields - HIGH at 0.66 and above."
            action={
              <Button tone="ghost" onClick={() => onGoto('orders')} testId="goto-orders">
                All orders →
              </Button>
            }
          />
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm" data-testid="dashboard-order-table">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-2 font-semibold">Order</th>
                  <th className="px-4 py-2 font-semibold">Buyer</th>
                  <th className="px-4 py-2 font-semibold">Amount</th>
                  <th className="px-4 py-2 font-semibold">Risk</th>
                  <th className="px-4 py-2 font-semibold">Top reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {[...orders]
                  .sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))
                  .slice(0, 8)
                  .map((order) => (
                    <tr
                      key={order.id}
                      data-testid={`dashboard-order-row-${order.id}`}
                      className="cursor-pointer hover:bg-slate-50"
                      onClick={() => onOpenOrder(order.id)}
                    >
                      <td className="px-4 py-2 font-mono text-xs text-slate-700">{order.order_ref}</td>
                      <td className="px-4 py-2 text-slate-800">{order.buyer_name}</td>
                      <td className="px-4 py-2 tabular-nums text-slate-800">
                        {money(order.amount, order.currency)}
                      </td>
                      <td className="px-4 py-2">
                        <RiskBadge level={order.risk_level ?? 'LOW'} score={order.risk_score} />
                      </td>
                      <td className="max-w-xs px-4 py-2 text-xs text-slate-600">
                        {order.reasons[0]?.label ?? '—'}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="space-y-5">
          <Card testId="runtime-card">
            <CardHeader title="Runtime" subtitle="What this instance actually is." />
            <dl className="space-y-2 px-4 py-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <dt className="text-slate-500">Demo mode</dt>
                <dd className="font-mono text-slate-800">{health.demo_mode ? 'on' : 'off'}</dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="text-slate-500">PayPal mode</dt>
                <dd className="font-mono text-slate-800">{health.paypal_mode}</dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="text-slate-500">Credentials</dt>
                <dd className="font-mono text-slate-800">
                  {health.paypal_credentials_present ? 'present' : 'not configured'}
                </dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="text-slate-500">LLM provider</dt>
                <dd className="font-mono text-slate-800">{health.llm_provider}</dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="text-slate-500">Server time</dt>
                <dd className="font-mono text-slate-800">{health.server_time}</dd>
              </div>
            </dl>
            <p className="border-t border-slate-100 px-4 py-2 text-[11px] text-slate-500">
              Without PayPal credentials every PayPal call is served by a local mock and labelled
              MOCK. With credentials, only the Sandbox host is allowed.
            </p>
          </Card>

          <Card testId="demo-card">
            <CardHeader
              title="Guided walkthrough"
              subtitle="Checkout → capture → scan → approve → execute → dispute → draft → submit."
            />
            <div className="space-y-3 px-4 py-3">
              <p className="text-xs text-slate-600">
                Runs the whole story against your local database and labels every step with where its
                data came from. Nothing is emailed, filed or charged.
              </p>
              <Button tone="primary" onClick={() => void runDemo()} busy={busy} testId="run-story">
                Run the story
              </Button>
              {story !== null && (
                <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs">
                  <p className="font-semibold text-slate-800">
                    Story {story.run_id} on {story.order_ref}
                  </p>
                  <ul className="mt-2 space-y-1">
                    {story.steps.map((step) => (
                      <li key={step.step} className="flex items-start gap-2">
                        <SourceChip source={step.source} testId={`story-source-${step.step}`} />
                        <span className="text-slate-700">{step.title}</span>
                      </li>
                    ))}
                  </ul>
                  <Button
                    tone="secondary"
                    onClick={() => onOpenOrder(story.order_id)}
                    testId="open-story-order"
                  >
                    Open {story.order_ref}
                  </Button>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

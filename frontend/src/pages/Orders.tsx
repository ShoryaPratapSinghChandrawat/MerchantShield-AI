import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ApiRequestError,
  approveAction,
  executeAction,
  fetchOrder,
  fetchOrders,
  openDispute,
  proposeAction,
  reconcileAction,
  rejectAction,
  retryAction,
  runAgent,
  scanOrder,
} from '../api/client';
import { SourceChip } from '../components/SourceChip';
import {
  Button,
  Card,
  CardHeader,
  Drawer,
  EmptyState,
  ErrorBanner,
  Field,
  Loading,
  Pill,
  ProgressBar,
  RiskBadge,
  type PillTone,
} from '../components/ui';
import { dateTime, humanise, money, percent } from '../lib/format';
import { isSourceLabel } from '../types';
import type {
  ActionRecord,
  ActionStatus,
  ActionType,
  DisputeSummary,
  EvidenceCheck,
  OrderDetail,
  OrderRow,
  RiskLevel,
  SourceLabel,
} from '../types';

const STATUS_TONES: Readonly<Record<ActionStatus, PillTone>> = {
  PENDING: 'warn',
  APPROVED: 'info',
  EXECUTING: 'info',
  EXECUTED: 'good',
  FAILED: 'bad',
  UNKNOWN: 'violet',
  REJECTED: 'neutral',
};

const ACTION_LABELS: Readonly<Record<ActionType, string>> = {
  ADD_TRACKING: 'Add tracking number',
  MESSAGE_BUYER: 'Message the buyer',
  FLAG_FOR_REVIEW: 'Flag for review',
};

export function OrdersPage({
  selectedId,
  onSelect,
  onGotoDispute,
}: {
  readonly selectedId: number | null;
  readonly onSelect: (orderId: number | null) => void;
  readonly onGotoDispute: (disputeId: number) => void;
}): React.JSX.Element {
  const [rows, setRows] = useState<OrderRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [level, setLevel] = useState<'ALL' | RiskLevel>('ALL');

  const load = useCallback(async (): Promise<void> => {
    setError(null);
    try {
      setRows(await fetchOrders());
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'Could not load orders.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const visible = useMemo(() => {
    const list = rows ?? [];
    const needle = query.trim().toLowerCase();
    return [...list]
      .filter((order) => (level === 'ALL' ? true : order.risk_level === level))
      .filter(
        (order) =>
          needle.length === 0 ||
          order.order_ref.toLowerCase().includes(needle) ||
          order.buyer_name.toLowerCase().includes(needle) ||
          order.item_name.toLowerCase().includes(needle),
      )
      .sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0));
  }, [rows, query, level]);

  return (
    <div className="space-y-4" data-testid="orders-page">
      <Card>
        <CardHeader
          title="Orders"
          subtitle="Sorted by rule score, highest first. Every row is labelled with its real source."
          action={
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search ref, buyer or item"
                aria-label="Search orders"
                data-testid="orders-search"
                className="w-56 rounded-md border border-slate-300 px-2.5 py-1.5 text-xs"
              />
              <select
                value={level}
                onChange={(event) => setLevel(event.target.value as 'ALL' | RiskLevel)}
                aria-label="Filter by risk"
                data-testid="orders-risk-filter"
                className="rounded-md border border-slate-300 px-2 py-1.5 text-xs"
              >
                <option value="ALL">All risk levels</option>
                <option value="HIGH">High only</option>
                <option value="MEDIUM">Medium only</option>
                <option value="LOW">Low only</option>
              </select>
            </div>
          }
        />
        {error !== null && (
          <div className="p-4">
            <ErrorBanner message={error} onRetry={() => void load()} />
          </div>
        )}
        {rows === null && error === null && (
          <div className="p-4">
            <Loading label="Loading orders…" />
          </div>
        )}
        {rows !== null && visible.length === 0 && (
          <div className="p-4">
            <EmptyState
              title="No orders match"
              body="Clear the search or start the guided walkthrough on the Overview page to create one."
            />
          </div>
        )}
        {visible.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm" data-testid="orders-table">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-2 font-semibold">Order</th>
                  <th className="px-4 py-2 font-semibold">Buyer</th>
                  <th className="px-4 py-2 font-semibold">Item</th>
                  <th className="px-4 py-2 font-semibold">Amount</th>
                  <th className="px-4 py-2 font-semibold">Risk</th>
                  <th className="px-4 py-2 font-semibold">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {visible.map((order) => (
                  <tr
                    key={order.id}
                    data-testid={`order-row-${order.id}`}
                    onClick={() => onSelect(order.id)}
                    className={`cursor-pointer hover:bg-slate-50 ${selectedId === order.id ? 'bg-slate-100' : ''}`}
                  >
                    <td className="px-4 py-2 font-mono text-xs text-slate-700">{order.order_ref}</td>
                    <td className="px-4 py-2 text-slate-800">{order.buyer_name}</td>
                    <td className="max-w-[18rem] truncate px-4 py-2 text-slate-700">
                      {order.item_name}
                    </td>
                    <td className="px-4 py-2 tabular-nums text-slate-800">
                      {money(order.amount, order.currency)}
                    </td>
                    <td className="px-4 py-2">
                      <RiskBadge level={order.risk_level ?? 'LOW'} score={order.risk_score} />
                    </td>
                    <td className="px-4 py-2">
                      <SourceChip source={order.source} testId={`order-source-${order.id}`} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {selectedId !== null && (
        <OrderDrawer
          orderId={selectedId}
          onClose={() => onSelect(null)}
          onGotoDispute={onGotoDispute}
          onChanged={() => void load()}
        />
      )}
    </div>
  );
}

function EvidenceList({ items }: { readonly items: EvidenceCheck[] }): React.JSX.Element {
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((item) => (
        <li key={item.kind} className="flex items-start gap-2 px-4 py-2 text-xs">
          <span
            aria-hidden
            className={`mt-0.5 inline-flex h-4 w-4 flex-none items-center justify-center rounded-full text-[10px] font-bold ${
              item.present ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'
            }`}
          >
            {item.present ? '✓' : '·'}
          </span>
          <div>
            <p className="font-medium text-slate-800">
              {item.label}
              {item.value !== '' && <span className="ml-2 font-mono text-[11px]">{item.value}</span>}
            </p>
            {!item.present && <p className="text-slate-600">{item.what_to_do}</p>}
          </div>
        </li>
      ))}
    </ul>
  );
}

/**
 * What actually served this action's external call.
 *
 * The previous version mapped "not MOCK" to PAYPAL_SANDBOX, which meant an
 * action served locally (result source SIMULATED) was displayed with a green
 * "real PayPal Sandbox response" chip - the single worst possible mislabel in
 * this product. It now renders the stored label and refuses to invent one.
 */
function resultSource(action: ActionRecord): SourceLabel | null {
  const value = action.result['source'];
  return isSourceLabel(value) ? value : null;
}

/**
 * What actually served this action's external call - or the fact that nothing
 * did.
 *
 * Two mislabels are possible here and both are forbidden by rule R5:
 *   1. mapping "not MOCK" to PAYPAL_SANDBOX, which painted a locally-handled
 *      action green and implied PayPal had answered (BUG-0020);
 *   2. showing "External call served by" at all for an action that never left
 *      the machine.
 *
 * So the label is read from the stored result and rendered as-is, and an action
 * with no external call says so in words.
 */
function ActionResultSource({ action }: { readonly action: ActionRecord }): React.JSX.Element {
  const source = resultSource(action);
  const externalCall = action.result['external_call'] === true;

  if (!externalCall) {
    return (
      <p
        className="mt-2 flex flex-wrap items-center gap-2 rounded border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-700"
        data-testid={`action-local-${action.id}`}
      >
        Handled locally: no external call was made.
        {source === null ? null : <SourceChip source={source} testId={`action-source-${action.id}`} />}
      </p>
    );
  }

  if (source === null) {
    // An external call with no readable label is a bug, and saying so is
    // better than drawing a guess.
    return (
      <p className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-[11px] text-red-900">
        This action reported an external call with no provenance label. That is a defect.
      </p>
    );
  }

  return (
    <p className="mt-2 flex items-center gap-2 text-[11px] text-slate-600">
      External call served by
      <SourceChip source={source} testId={`action-source-${action.id}`} />
    </p>
  );
}

function DiffTable({ action }: { readonly action: ActionRecord }): React.JSX.Element | null {
  const keys = new Set([...Object.keys(action.before), ...Object.keys(action.after)]);
  if (keys.size === 0) {
    return null;
  }
  return (
    <table className="mt-2 w-full text-[11px]">
      <thead>
        <tr className="text-left uppercase tracking-wide text-slate-500">
          <th className="py-1 font-semibold">Field</th>
          <th className="py-1 font-semibold">Before</th>
          <th className="py-1 font-semibold">After</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {[...keys].map((key) => (
          <tr key={key}>
            <td className="py-1 font-mono text-slate-700">{key}</td>
            <td className="py-1 font-mono text-slate-500">{JSON.stringify(action.before[key])}</td>
            <td className="py-1 font-mono text-emerald-800">{JSON.stringify(action.after[key])}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ActionCard({
  action,
  onChange,
  onError,
}: {
  readonly action: ActionRecord;
  readonly onChange: () => void;
  readonly onError: (message: string) => void;
}): React.JSX.Element {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [confirmNotApplied, setConfirmNotApplied] = useState(false);

  async function run(work: () => Promise<void>): Promise<void> {
    setBusy(true);
    setNote(null);
    try {
      await work();
      onChange();
    } catch (cause: unknown) {
      onError(cause instanceof ApiRequestError ? cause.message : 'The action failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <li
      data-testid={`action-${action.id}`}
      data-status={action.status}
      className="rounded-lg border border-slate-200 bg-white p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Pill tone={STATUS_TONES[action.status]} testId={`action-status-${action.id}`}>
            {action.status}
          </Pill>
          <span className="text-sm font-semibold text-slate-800">{ACTION_LABELS[action.type]}</span>
          <span className="text-[11px] text-slate-500">by {action.proposed_by}</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {action.status === 'PENDING' && (
            <>
              <Button
                tone="primary"
                busy={busy}
                testId={`approve-${action.id}`}
                onClick={() => void run(async () => approveAction(action.id).then(() => undefined))}
              >
                Approve
              </Button>
              <Button
                tone="danger"
                busy={busy}
                testId={`reject-${action.id}`}
                onClick={() => void run(async () => rejectAction(action.id).then(() => undefined))}
              >
                Reject
              </Button>
            </>
          )}
          {action.status === 'APPROVED' && (
            <Button
              tone="primary"
              busy={busy}
              testId={`execute-${action.id}`}
              onClick={() =>
                void run(async () => {
                  const result = await executeAction(action.id);
                  setNote(
                    result.status === 'EXECUTED'
                      ? `Executed via ${String(result.result['source'] ?? 'unknown')}.`
                      : `Outcome: ${result.status}. ${result.error ?? ''}`.trim(),
                  );
                })
              }
            >
              Execute
            </Button>
          )}
          {action.can_retry && (
            <Button
              tone="secondary"
              busy={busy}
              testId={`retry-${action.id}`}
              onClick={() => void run(async () => retryAction(action.id).then(() => undefined))}
            >
              Retry
            </Button>
          )}
        </div>
      </div>

      {action.rationale !== '' && <p className="mt-1 text-xs text-slate-600">{action.rationale}</p>}

      {Object.keys(action.payload).length > 0 && (
        <p className="mt-1 font-mono text-[11px] text-slate-600">
          {Object.entries(action.payload)
            .map(([key, value]) => `${key}=${value}`)
            .join('  ')}
        </p>
      )}

      {action.error !== null && (
        <p className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-[11px] text-red-900">
          {action.error}
        </p>
      )}
      {note !== null && (
        <p className="mt-2 rounded border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-700">
          {note}
        </p>
      )}

      <DiffTable action={action} />

      {action.status === 'EXECUTED' ? <ActionResultSource action={action} /> : null}

      <p className="mt-2 font-mono text-[10px] text-slate-400">
        idempotency {action.idempotency_key} · attempts {action.attempts}
      </p>

      {action.status === 'UNKNOWN' && (
        <div className="mt-2 rounded border border-violet-200 bg-violet-50 p-2">
          <p className="text-[11px] text-violet-900">
            We could not establish whether this reached PayPal, so a retry is deliberately not
            offered - it could create a duplicate tracking number. Check the order in PayPal, then
            reconcile:
          </p>
          <label className="mt-2 flex items-center gap-2 text-[11px] text-violet-900">
            <input
              type="checkbox"
              checked={confirmNotApplied}
              onChange={(event) => setConfirmNotApplied(event.target.checked)}
              data-testid={`confirm-not-applied-${action.id}`}
            />
            I checked PayPal and it was <strong>not</strong> applied
          </label>
          <div className="mt-2 flex gap-2">
            <Button
              tone="secondary"
              busy={busy}
              testId={`reconcile-${action.id}`}
              onClick={() =>
                void run(async () => {
                  const result = await reconcileAction(action.id, confirmNotApplied);
                  setNote(`Reconciled: ${result.outcome}. Action is now ${result.action_status}.`);
                })
              }
            >
              Reconcile
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

function ProposeBar({
  order,
  onChanged,
  onError,
}: {
  readonly order: OrderDetail['order'];
  readonly onChanged: () => void;
  readonly onError: (message: string) => void;
}): React.JSX.Element {
  const [tracking, setTracking] = useState('');
  const [carrier, setCarrier] = useState('UPS');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function propose(type: ActionType, payload: Record<string, string>): Promise<void> {
    setBusy(true);
    try {
      await proposeAction(order.id, type, payload, 'Proposed from the order screen');
      onChanged();
    } catch (cause: unknown) {
      onError(cause instanceof ApiRequestError ? cause.message : 'Could not propose the action.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3 border-t border-slate-200 bg-slate-50 p-3" data-testid="propose-bar">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr,7rem,auto]">
        <input
          value={tracking}
          onChange={(event) => setTracking(event.target.value)}
          placeholder="Tracking number"
          aria-label="Tracking number"
          data-testid="propose-tracking-input"
          className="rounded-md border border-slate-300 px-2 py-1.5 text-xs"
        />
        <select
          value={carrier}
          onChange={(event) => setCarrier(event.target.value)}
          aria-label="Carrier"
          data-testid="propose-carrier-input"
          className="rounded-md border border-slate-300 px-2 py-1.5 text-xs"
        >
          {['UPS', 'FedEx', 'USPS', 'DHL'].map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
        <Button
          tone="secondary"
          busy={busy}
          testId="propose-tracking"
          onClick={() =>
            void propose('ADD_TRACKING', { tracking_number: tracking.trim(), carrier })
          }
        >
          Propose tracking
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr,auto]">
        <input
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Message to the buyer (logged, not emailed)"
          aria-label="Message to the buyer"
          data-testid="propose-message-input"
          className="rounded-md border border-slate-300 px-2 py-1.5 text-xs"
        />
        <Button
          tone="secondary"
          busy={busy}
          testId="propose-message"
          onClick={() => void propose('MESSAGE_BUYER', { body: message.trim() })}
        >
          Propose message
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          tone="secondary"
          busy={busy}
          testId="propose-flag"
          onClick={() => void propose('FLAG_FOR_REVIEW', {})}
        >
          Propose flag for review
        </Button>
        <Button
          tone="primary"
          busy={busy}
          testId="run-agent"
          onClick={() => {
            setBusy(true);
            runAgent(order.id)
              .then(() => onChanged())
              .catch((cause: unknown) =>
                onError(
                  cause instanceof ApiRequestError ? cause.message : 'The planner could not run.',
                ),
              )
              .finally(() => setBusy(false));
          }}
        >
          Ask the planner
        </Button>
        <span className="text-[11px] text-slate-500">
          Every proposal waits for your approval. The planner has no write access.
        </span>
      </div>
    </div>
  );
}

function OrderDrawer({
  orderId,
  onClose,
  onGotoDispute,
  onChanged,
}: {
  readonly orderId: number;
  readonly onClose: () => void;
  readonly onGotoDispute: (disputeId: number) => void;
  readonly onChanged: () => void;
}): React.JSX.Element {
  const [detail, setDetail] = useState<OrderDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (): Promise<void> => {
    setError(null);
    try {
      setDetail(await fetchOrder(orderId));
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'Could not load the order.');
    }
  }, [orderId]);

  useEffect(() => {
    setDetail(null);
    void load();
  }, [load]);

  async function rescan(): Promise<void> {
    setBusy(true);
    try {
      setDetail(await scanOrder(orderId));
      onChanged();
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'The rescan failed.');
    } finally {
      setBusy(false);
    }
  }

  async function startDispute(): Promise<void> {
    setBusy(true);
    try {
      const dispute: DisputeSummary = await openDispute(orderId);
      onChanged();
      onGotoDispute(dispute.id);
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'Could not open a dispute.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Drawer
      title={detail === null ? `Order #${orderId}` : `Order ${detail.order.order_ref}`}
      subtitle={detail === null ? undefined : `${detail.order.buyer_name} · ${detail.order.item_name}`}
      onClose={onClose}
      testId="order-drawer"
    >
      {error !== null && (
        <div className="mb-3">
          <ErrorBanner message={error} onRetry={() => void load()} />
        </div>
      )}
      {detail === null && error === null && <Loading label="Loading order…" />}

      {detail !== null && (
        <div className="space-y-4" data-testid="order-detail">
          <Card>
            <CardHeader
              title="Order facts"
              subtitle={`${money(detail.order.amount, detail.order.currency)} · ${detail.order.status}`}
              action={<SourceChip source={detail.order.source} testId="drawer-source-chip" />}
            />
            <dl className="grid grid-cols-2 gap-3 px-4 py-3 sm:grid-cols-3">
              <Field label="Buyer" value={detail.order.buyer_name} />
              <Field label="Buyer email" value={detail.order.buyer_email} />
              <Field label="Buyer country" value={detail.order.buyer_country} />
              <Field label="Your country" value={detail.order.merchant_country} />
              <Field label="Category" value={detail.order.category} />
              <Field label="First-time buyer" value={detail.order.is_first_time_buyer ? 'yes' : 'no'} />
              <Field label="Tracking" value={detail.order.tracking_number ?? 'not on file'} mono />
              <Field label="Carrier" value={detail.order.carrier ?? 'not on file'} />
              <Field label="Created" value={dateTime(detail.order.created_at)} />
              <Field label="Shipped" value={detail.order.shipped_at === null ? 'not on file' : dateTime(detail.order.shipped_at)} />
              <Field label="Delivery confirmed" value={detail.order.delivery_confirmed ? 'yes' : 'no'} />
              <Field label="Demo record" value={detail.order.is_demo ? 'yes' : 'no'} />
            </dl>
          </Card>

          <Card testId="risk-card">
            <CardHeader
              title="Risk"
              subtitle={detail.risk.estimate_note}
              action={<RiskBadge level={detail.risk.risk_level} score={detail.risk.risk_score} />}
              level={3}
            />
            <ul className="divide-y divide-slate-100">
              {detail.risk.reasons.map((reason) => (
                <li key={reason.code} className="flex items-start justify-between gap-3 px-4 py-2">
                  <span className="text-xs text-slate-700">{reason.label}</span>
                  <span
                    className={`flex-none font-mono text-[11px] font-semibold ${
                      reason.direction === '+' ? 'text-red-700' : 'text-emerald-700'
                    }`}
                  >
                    {reason.direction}
                    {reason.points}
                  </span>
                </li>
              ))}
            </ul>
          </Card>

          {detail.ml_risk_estimate !== null && (
            <Card testId="ml-card">
              <CardHeader
                title="Model estimate"
                subtitle={detail.ml_risk_estimate.note}
                action={<Pill tone="violet">ESTIMATE</Pill>}
                level={3}
              />
              <div className="px-4 py-3">
                <div className="flex items-baseline gap-3">
                  <p className="text-2xl font-semibold tabular-nums text-slate-900">
                    {percent(detail.ml_risk_estimate.estimate, 1)}
                  </p>
                  <p className="text-xs text-slate-500">from the logistic-regression prototype</p>
                </div>
                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-red-700">
                      Raised by
                    </p>
                    <ul className="mt-1 space-y-0.5 text-xs text-slate-700">
                      {detail.ml_risk_estimate.raised_by.length === 0 && <li>nothing notable</li>}
                      {detail.ml_risk_estimate.raised_by.map((factor) => (
                        <li key={factor.feature}>
                          {factor.label}{' '}
                          <span className="font-mono text-[11px] text-slate-500">
                            {factor.weight.toFixed(2)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-700">
                      Lowered by
                    </p>
                    <ul className="mt-1 space-y-0.5 text-xs text-slate-700">
                      {detail.ml_risk_estimate.lowered_by.length === 0 && <li>nothing notable</li>}
                      {detail.ml_risk_estimate.lowered_by.map((factor) => (
                        <li key={factor.feature}>
                          {factor.label}{' '}
                          <span className="font-mono text-[11px] text-slate-500">
                            {factor.weight.toFixed(2)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </Card>
          )}

          <Card testId="evidence-card">
            <CardHeader
              title="Evidence you hold"
              subtitle={detail.evidence_strength.note}
              action={
                <span className="font-mono text-xs text-slate-600">
                  {detail.evidence_strength.score}/{detail.evidence_strength.max}
                </span>
              }
              level={3}
            />
            <div className="px-4 pt-3">
              <ProgressBar
                value={detail.evidence_strength.score}
                max={detail.evidence_strength.max}
                label="Evidence strength"
              />
            </div>
            <EvidenceList items={detail.evidence_items} />
          </Card>

          <Card testId="actions-card">
            <CardHeader
              title="Actions"
              subtitle="Proposals wait for approval; execution is claimed once and recorded."
              action={
                <Button tone="ghost" onClick={() => void rescan()} busy={busy} testId="rescan">
                  Re-scan
                </Button>
              }
              level={3}
            />
            {detail.actions.length === 0 ? (
              <div className="p-4">
                <EmptyState
                  title="No actions yet"
                  body="Propose one below, or ask the planner to suggest the next steps."
                />
              </div>
            ) : (
              <ul className="space-y-2 p-3">
                {detail.actions.map((action) => (
                  <ActionCard
                    key={action.id}
                    action={action}
                    onChange={() => {
                      void load();
                      onChanged();
                    }}
                    onError={setError}
                  />
                ))}
              </ul>
            )}
            <ProposeBar
              order={detail.order}
              onChanged={() => {
                void load();
                onChanged();
              }}
              onError={setError}
            />
          </Card>

          <Card testId="messages-card">
            <CardHeader title="Buyer messages" subtitle="Logged locally; nothing is emailed." level={3} />
            {detail.messages.length === 0 ? (
              <p className="px-4 py-3 text-xs text-slate-600">No messages recorded.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {detail.messages.map((message) => (
                  <li key={message.id} className="px-4 py-2">
                    <div className="flex items-center gap-2 text-[11px] text-slate-500">
                      <Pill tone={message.direction === 'BUYER' ? 'warn' : 'info'}>
                        {message.direction}
                      </Pill>
                      <span>{dateTime(message.sent_at)}</span>
                      <SourceChip source={message.source} testId={`message-source-${message.id}`} />
                    </div>
                    <p className="mt-1 text-xs text-slate-800">{message.body}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card testId="order-disputes-card">
            <CardHeader
              title="Disputes"
              subtitle={humanise('Buyer protection case')}
              action={
                <Button tone="secondary" onClick={() => void startDispute()} busy={busy} testId="open-dispute">
                  Open dispute
                </Button>
              }
              level={3}
            />
            {detail.disputes.length === 0 ? (
              <p className="px-4 py-3 text-xs text-slate-600">No dispute recorded for this order.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {detail.disputes.map((dispute) => (
                  <li key={dispute.id} className="flex items-center justify-between gap-2 px-4 py-2">
                    <div className="text-xs text-slate-700">
                      #{dispute.id} · {humanise(dispute.reason)} · {dispute.status}
                    </div>
                    <Button
                      tone="ghost"
                      onClick={() => onGotoDispute(dispute.id)}
                      testId={`goto-dispute-${dispute.id}`}
                    >
                      Open →
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card testId="order-audit-card">
            <CardHeader title="Audit trail" subtitle="Newest first, append-only." level={3} />
            {detail.audit.length === 0 ? (
              <p className="px-4 py-3 text-xs text-slate-600">No audit rows yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {detail.audit.slice(0, 20).map((row) => (
                  <li key={row.id} className="flex flex-wrap items-center gap-2 px-4 py-2 text-[11px]">
                    <span className="font-mono text-slate-500">{dateTime(row.created_at)}</span>
                    <Pill tone="neutral" mono>
                      {row.event}
                    </Pill>
                    <span className="text-slate-700">{row.message}</span>
                    <SourceChip source={row.source} testId={`audit-source-${row.id}`} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </Drawer>
  );
}

import { useEffect, useState } from 'react';
import { ApiRequestError, fetchHealth, fetchOrder } from './api/client';
import { SourceChip } from './components/SourceChip';
import type { Health, Order } from './types';

type LoadState =
  | { readonly kind: 'loading' }
  | { readonly kind: 'error'; readonly message: string }
  | { readonly kind: 'ready'; readonly order: Order; readonly health: Health };

const PHASE0_ORDER_ID = 1;

function Field({ label, value }: { readonly label: string; readonly value: string }): React.JSX.Element {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-900">{value}</dd>
    </div>
  );
}

export function App(): React.JSX.Element {
  const [state, setState] = useState<LoadState>({ kind: 'loading' });

  useEffect(() => {
    let cancelled = false;

    async function load(): Promise<void> {
      try {
        const [health, order] = await Promise.all([fetchHealth(), fetchOrder(PHASE0_ORDER_ID)]);
        if (!cancelled) {
          setState({ kind: 'ready', order, health });
        }
      } catch (error: unknown) {
        if (cancelled) {
          return;
        }
        const message =
          error instanceof ApiRequestError
            ? error.message
            : 'Something went wrong loading the dashboard.';
        setState({ kind: 'error', message });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-col gap-1 px-4 py-5 sm:px-6">
          <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">MerchantShield AI</h1>
          <p className="text-sm text-slate-600">
            Stops PayPal disputes before they happen, and helps small merchants answer the ones
            that do.
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6" data-testid="app-main">
        {state.kind === 'loading' && (
          <p data-testid="loading-state" className="text-sm text-slate-600">
            Loading order&hellip;
          </p>
        )}

        {state.kind === 'error' && (
          <div
            role="alert"
            data-testid="error-state"
            className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-900"
          >
            <p className="font-semibold">Could not load the dashboard</p>
            <p className="mt-1">{state.message}</p>
          </div>
        )}

        {state.kind === 'ready' && (
          <OrderPanel order={state.order} health={state.health} />
        )}
      </main>
    </div>
  );
}

function OrderPanel({
  order,
  health,
}: {
  readonly order: Order;
  readonly health: Health;
}): React.JSX.Element {
  return (
    <section
      data-testid="order-panel"
      aria-labelledby="order-heading"
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="order-heading" data-testid="order-heading" className="text-lg font-semibold">
          Order {order.order_ref}
        </h2>
        <SourceChip source={order.source} />
      </div>

      <p className="mt-1 text-sm text-slate-600" data-testid="order-item">
        {order.item_name}
      </p>

      <dl className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Buyer" value={order.buyer_name} />
        <Field label="Buyer email" value={order.buyer_email} />
        <Field label="Amount" value={`${order.amount} ${order.currency}`} />
        <Field label="Order status" value={order.status} />
        <Field label="Created (UTC)" value={order.created_at} />
        <Field label="Demo record" value={order.is_demo ? 'yes' : 'no'} />
      </dl>

      <footer
        data-testid="honesty-footer"
        className="mt-6 border-t border-slate-200 pt-4 text-xs text-slate-600"
      >
        <p>
          Data source for this record: <SourceChip source={order.source} testId="footer-source-chip" />{' '}
          &mdash; nothing on this screen is a PayPal production transaction.
        </p>
        <p className="mt-1" data-testid="runtime-mode">
          Phase {health.phase} &middot; DEMO_MODE {health.demo_mode ? 'on' : 'off'} &middot; PayPal
          mode {health.paypal_mode} &middot; credentials{' '}
          {health.paypal_credentials_present ? 'present' : 'not configured'}
        </p>
      </footer>
    </section>
  );
}

import { useCallback, useEffect, useState } from 'react';
import { ApiRequestError, capture, checkout, fetchProducts } from '../api/client';
import { SourceChip } from '../components/SourceChip';
import { Button, Card, CardHeader, ErrorBanner, Loading, Pill } from '../components/ui';
import { money } from '../lib/format';
import type { CaptureResult, CheckoutResult, Product } from '../types';

/**
 * The storefront exists so that a PayPal order can be created by the app
 * itself, not just seeded. In MOCK mode the "approval" is an in-app screen and
 * is labelled MOCK everywhere; there is no pretend PayPal page.
 */
export function StorePage({
  onOpenOrder,
}: {
  readonly onOpenOrder: (orderId: number) => void;
}): React.JSX.Element {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkoutResult, setCheckoutResult] = useState<CheckoutResult | null>(null);
  const [captureResult, setCaptureResult] = useState<CaptureResult | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    setError(null);
    try {
      setProducts(await fetchProducts());
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'Could not load the store.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function start(productId: string): Promise<void> {
    setBusyId(productId);
    setError(null);
    setCaptureResult(null);
    try {
      setCheckoutResult(await checkout(productId));
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'Checkout failed.');
    } finally {
      setBusyId(null);
    }
  }

  async function pay(): Promise<void> {
    if (checkoutResult === null) {
      return;
    }
    setBusyId('capture');
    setError(null);
    try {
      setCaptureResult(await capture(checkoutResult.paypal_order_id));
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'Capture failed.');
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4" data-testid="store-page">
      <Card>
        <CardHeader
          title="Storefront"
          subtitle="A real checkout flow: a PayPal order is created, then captured. In MOCK mode nothing leaves this machine."
        />
        {error !== null && (
          <div className="p-4">
            <ErrorBanner message={error} onRetry={() => void load()} />
          </div>
        )}
        {products === null && error === null && (
          <div className="p-4">
            <Loading label="Loading products…" />
          </div>
        )}
        {products !== null && (
          <ul className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2">
            {products.map((product) => (
              <li
                key={product.id}
                data-testid={`product-${product.id}`}
                className="flex flex-col justify-between rounded-lg border border-slate-200 bg-white p-3"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">{product.name}</p>
                    {product.high_value && <Pill tone="warn">high value</Pill>}
                  </div>
                  <p className="mt-1 text-xs text-slate-600">{product.blurb}</p>
                </div>
                <div className="mt-3 flex items-center justify-between">
                  <span className="text-sm font-semibold tabular-nums text-slate-900">
                    {money(product.price, 'USD')}
                  </span>
                  <Button
                    tone="primary"
                    busy={busyId === product.id}
                    testId={`buy-${product.id}`}
                    onClick={() => void start(product.id)}
                  >
                    Check out
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {checkoutResult !== null && (
        <Card testId="checkout-panel">
          <CardHeader
            title="Checkout created"
            subtitle={`${checkoutResult.order_ref} · ${checkoutResult.product.name}`}
            action={<SourceChip source={checkoutResult.source} testId="checkout-source" />}
          />
          <div className="space-y-3 px-4 py-3 text-xs text-slate-700">
            <p>
              PayPal order id <span className="font-mono">{checkoutResult.paypal_order_id}</span>
            </p>
            {checkoutResult.mock ? (
              <div className="rounded-md border border-slate-300 bg-slate-50 p-3">
                <p className="font-semibold text-slate-800">MOCK: there is no PayPal page here.</p>
                <p className="mt-1">
                  This build has no PayPal credentials configured, so the mock adapter created the
                  order locally. In Sandbox mode this button would send you to the real PayPal
                  Sandbox approval page.
                </p>
              </div>
            ) : (
              <a
                href={checkoutResult.approval_url}
                className="inline-block rounded-md bg-slate-900 px-3 py-1.5 font-semibold text-white"
                target="_blank"
                rel="noreferrer"
              >
                Approve in the PayPal Sandbox
              </a>
            )}
            <Button tone="primary" busy={busyId === 'capture'} testId="capture" onClick={() => void pay()}>
              {checkoutResult.mock ? 'Simulate buyer approval and capture' : 'Capture the approved order'}
            </Button>
          </div>
        </Card>
      )}

      {captureResult !== null && (
        <Card testId="capture-panel">
          <CardHeader
            title="Payment captured"
            subtitle={captureResult.note}
            action={<SourceChip source={captureResult.source} testId="capture-source" />}
          />
          <div className="flex flex-wrap items-center gap-2 px-4 py-3 text-xs text-slate-700">
            <span className="font-mono">{captureResult.order_ref}</span>
            <Button tone="secondary" onClick={() => onOpenOrder(captureResult.order_id)} testId="open-captured-order">
              Open the order →
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

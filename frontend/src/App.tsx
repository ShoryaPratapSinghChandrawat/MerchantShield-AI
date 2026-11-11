import { useCallback, useEffect, useState } from 'react';
import { ApiRequestError, fetchHealth } from './api/client';
import { SourceChip } from './components/SourceChip';
import { Pill } from './components/ui';
import { AboutPage } from './pages/About';
import { AuditPage } from './pages/Audit';
import { Dashboard } from './pages/Dashboard';
import { DisputesPage } from './pages/Disputes';
import { OrdersPage } from './pages/Orders';
import { StorePage } from './pages/Store';
import { WalkthroughPage } from './pages/Walkthrough';
import type { Health } from './types';

/**
 * Routing is a hash plus one piece of state. That is deliberate: the whole app
 * is served by FastAPI as static files with an SPA fallback, and adding a router
 * dependency buys nothing here except another thing that can drift out of sync
 * with the API.
 */
const PAGES = [
  { id: 'overview', label: 'Overview' },
  { id: 'orders', label: 'Orders' },
  { id: 'store', label: 'Storefront' },
  { id: 'disputes', label: 'Disputes' },
  { id: 'audit', label: 'Audit log' },
  { id: 'walkthrough', label: 'Walkthrough' },
  { id: 'about', label: 'Methodology' },
] as const;

type PageId = (typeof PAGES)[number]['id'];

function pageFromHash(): PageId {
  const raw = window.location.hash.replace(/^#\/?/, '');
  const match = PAGES.find((page) => page.id === raw);
  return match?.id ?? 'overview';
}

export function App(): React.JSX.Element {
  const [page, setPage] = useState<PageId>(pageFromHash);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [orderId, setOrderId] = useState<number | null>(null);
  const [disputeId, setDisputeId] = useState<number | null>(null);

  const go = useCallback((next: PageId) => {
    window.location.hash = `#/${next}`;
    setPage(next);
  }, []);

  useEffect(() => {
    const onHashChange = (): void => setPage(pageFromHash());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((cause: unknown) =>
        setHealthError(
          cause instanceof ApiRequestError ? cause.message : 'Could not reach the API.',
        ),
      );
  }, []);

  const openOrder = useCallback(
    (id: number) => {
      setOrderId(id);
      go('orders');
    },
    [go],
  );

  const openDispute = useCallback(
    (id: number) => {
      setDisputeId(id);
      go('disputes');
    },
    [go],
  );

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-4 sm:px-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">MerchantShield AI</h1>
              <p className="text-sm text-slate-600">
                Stops PayPal disputes before they happen, and helps small merchants answer the ones
                that do.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <Pill tone={health?.demo_mode === true ? 'warn' : 'neutral'} mono>
                demo {health?.demo_mode === true ? 'on' : 'off'}
              </Pill>
              <Pill tone="info" mono>
                paypal {health?.paypal_mode ?? '…'}
              </Pill>
              <Pill tone="neutral" mono>
                llm {health?.llm_provider ?? '…'}
              </Pill>
              <Pill tone="neutral" mono>
                phase {health?.phase ?? '…'}
              </Pill>
            </div>
          </div>
          {healthError !== null && (
            <p role="alert" className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-xs text-amber-900">
              {healthError}
            </p>
          )}
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:flex-row">
        <nav aria-label="Sections" className="lg:w-48 lg:flex-none">
          <ul className="flex gap-1 overflow-x-auto lg:flex-col" data-testid="nav">
            {PAGES.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  data-testid={`nav-${item.id}`}
                  aria-current={page === item.id ? 'page' : undefined}
                  onClick={() => go(item.id)}
                  className={`w-full whitespace-nowrap rounded-md px-3 py-2 text-left text-sm font-medium ${
                    page === item.id
                      ? 'bg-slate-900 text-white'
                      : 'text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-3 hidden rounded-md border border-slate-200 bg-white p-2 text-[11px] leading-relaxed text-slate-600 lg:block">
            <span className="font-semibold text-slate-800">Labels on every record</span>
            <br />
            <SourceChip source="PAYPAL_SANDBOX" testId="legend-sandbox" /> real Sandbox response
            <br />
            <SourceChip source="SIMULATED" testId="legend-simulated" /> made locally, nothing
            contacted
            <br />
            <SourceChip source="MOCK" testId="legend-mock" /> mock adapter stood in for PayPal
          </p>
        </nav>

        <main className="min-w-0 flex-1" data-testid="app-main">
          {page === 'overview' && <Dashboard onOpenOrder={openOrder} onGoto={(id) => go(id as PageId)} />}
          {page === 'orders' && (
            <OrdersPage selectedId={orderId} onSelect={setOrderId} onGotoDispute={openDispute} />
          )}
          {page === 'store' && <StorePage onOpenOrder={openOrder} />}
          {page === 'disputes' && <DisputesPage selectedId={disputeId} onSelect={setDisputeId} />}
          {page === 'audit' && <AuditPage />}
          {page === 'walkthrough' && <WalkthroughPage onOpenOrder={openOrder} onGotoDispute={openDispute} />}
          {page === 'about' && <AboutPage />}
        </main>
      </div>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-3 text-[11px] text-slate-500 sm:px-6">
          PayPal Sandbox only. Nothing here moves real money, files a real dispute, or sends a real
          email. Built for the PayPal AI Hackathon.
        </div>
      </footer>
    </div>
  );
}

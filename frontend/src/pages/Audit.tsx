import { useCallback, useEffect, useState } from 'react';
import { ApiRequestError, fetchAudit } from '../api/client';
import { SourceChip } from '../components/SourceChip';
import { Card, CardHeader, EmptyState, ErrorBanner, Loading, Pill } from '../components/ui';
import { dateTime } from '../lib/format';
import type { AuditItem } from '../types';

const EVENT_TONES: Readonly<Record<string, 'neutral' | 'info' | 'good' | 'warn' | 'bad' | 'violet'>> = {
  action_proposed: 'neutral',
  action_approved: 'info',
  action_executed: 'good',
  action_failed: 'bad',
  action_unknown: 'violet',
  action_reconciled: 'info',
  order_scanned: 'neutral',
  dispute_opened: 'warn',
  dispute_submitted: 'good',
};

export function AuditPage(): React.JSX.Element {
  const [rows, setRows] = useState<AuditItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [event, setEvent] = useState('');
  const [limit, setLimit] = useState(100);

  const load = useCallback(async (): Promise<void> => {
    setError(null);
    try {
      setRows(await fetchAudit({ event: event === '' ? undefined : event, limit }));
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'Could not load the audit log.');
    }
  }, [event, limit]);

  useEffect(() => {
    void load();
  }, [load]);

  const events = [...new Set((rows ?? []).map((row) => row.event))].sort();

  return (
    <div className="space-y-4" data-testid="audit-page">
      <Card>
        <CardHeader
          title="Audit log"
          subtitle="Append-only. Every state change records who did it, what happened, and where the data came from."
          action={
            <div className="flex items-center gap-2">
              <input
                value={event}
                onChange={(changeEvent) => setEvent(changeEvent.target.value)}
                placeholder="Filter by event"
                aria-label="Filter by event"
                data-testid="audit-event-filter"
                list="audit-events"
                className="w-48 rounded-md border border-slate-300 px-2 py-1.5 text-xs"
              />
              <datalist id="audit-events">
                {events.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
              <select
                value={limit}
                onChange={(changeEvent) => setLimit(Number(changeEvent.target.value))}
                aria-label="Row limit"
                data-testid="audit-limit"
                className="rounded-md border border-slate-300 px-2 py-1.5 text-xs"
              >
                {[50, 100, 250, 500].map((value) => (
                  <option key={value} value={value}>
                    {value} rows
                  </option>
                ))}
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
            <Loading label="Loading audit rows…" />
          </div>
        )}
        {rows !== null && rows.length === 0 && (
          <div className="p-4">
            <EmptyState
              title="Nothing recorded yet"
              body="Seed the demo or run the guided story, and the audit trail fills in."
            />
          </div>
        )}
        {rows !== null && rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm" data-testid="audit-table">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-2 font-semibold">When</th>
                  <th className="px-4 py-2 font-semibold">Event</th>
                  <th className="px-4 py-2 font-semibold">Actor</th>
                  <th className="px-4 py-2 font-semibold">Message</th>
                  <th className="px-4 py-2 font-semibold">Links</th>
                  <th className="px-4 py-2 font-semibold">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => (
                  <tr key={row.id} data-testid={`audit-row-${row.id}`}>
                    <td className="whitespace-nowrap px-4 py-2 font-mono text-[11px] text-slate-600">
                      {dateTime(row.created_at)}
                    </td>
                    <td className="px-4 py-2">
                      <Pill tone={EVENT_TONES[row.event] ?? 'neutral'} mono>
                        {row.event}
                      </Pill>
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-700">{row.actor}</td>
                    <td className="px-4 py-2 text-xs text-slate-700">{row.message}</td>
                    <td className="px-4 py-2 font-mono text-[11px] text-slate-500">
                      {[
                        row.order_id === null ? null : `order ${row.order_id}`,
                        row.action_id === null ? null : `action ${row.action_id}`,
                        row.dispute_id === null ? null : `dispute ${row.dispute_id}`,
                      ]
                        .filter((value): value is string => value !== null)
                        .join(' · ') || '—'}
                    </td>
                    <td className="px-4 py-2">
                      <SourceChip source={row.source} testId={`audit-row-source-${row.id}`} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <p className="text-[11px] text-slate-500">
        This log is the product's own record. It is not a PayPal report, and it is not tamper-evident:
        it is an append-only table in the local SQLite database.
      </p>
    </div>
  );
}

import { useCallback, useEffect, useState } from 'react';
import {
  ApiRequestError,
  approveDraft,
  createDraft,
  fetchDispute,
  fetchDisputes,
  fetchPacket,
  submitDispute,
} from '../api/client';
import { SourceChip } from '../components/SourceChip';
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  Loading,
  Pill,
  ProgressBar,
} from '../components/ui';
import { dateTime, humanise, money } from '../lib/format';
import type { DisputeDetail, DisputeSummary, EvidencePacket } from '../types';

const STATUS_TONE = {
  OPEN: 'warn',
  UNDER_REVIEW: 'info',
  SUBMITTED: 'good',
} as const;

export function DisputesPage({
  selectedId,
  onSelect,
}: {
  readonly selectedId: number | null;
  readonly onSelect: (disputeId: number | null) => void;
}): React.JSX.Element {
  const [rows, setRows] = useState<DisputeSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    setError(null);
    try {
      setRows(await fetchDisputes());
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'Could not load disputes.');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-4" data-testid="disputes-page">
      <Card>
        <CardHeader
          title="Disputes"
          subtitle="Open a case from any order screen. Nothing is filed with PayPal: submission is SIMULATED and labelled."
        />
        {error !== null && (
          <div className="p-4">
            <ErrorBanner message={error} onRetry={() => void load()} />
          </div>
        )}
        {rows === null && error === null && (
          <div className="p-4">
            <Loading label="Loading disputes…" />
          </div>
        )}
        {rows !== null && rows.length === 0 && (
          <div className="p-4">
            <EmptyState
              title="No disputes yet"
              body="Open an order, press “Open dispute”, and a case with an evidence packet appears here."
            />
          </div>
        )}
        {rows !== null && rows.length > 0 && (
          <ul className="divide-y divide-slate-100">
            {rows.map((dispute) => (
              <li
                key={dispute.id}
                data-testid={`dispute-row-${dispute.id}`}
                className={`flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm hover:bg-slate-50 ${
                  selectedId === dispute.id ? 'bg-slate-100' : ''
                }`}
              >
                <div>
                  <p className="font-semibold text-slate-900">
                    {dispute.order_ref} · {humanise(dispute.reason)}
                  </p>
                  <p className="text-xs text-slate-600">
                    {money(dispute.amount, dispute.currency)} · opened {dateTime(dispute.opened_at)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Pill tone={STATUS_TONE[dispute.status as keyof typeof STATUS_TONE] ?? 'neutral'}>
                    {dispute.status}
                  </Pill>
                  <span className="font-mono text-[11px] text-slate-500">
                    evidence {dispute.evidence_strength}/100
                  </span>
                  <SourceChip source={dispute.source} testId={`dispute-source-${dispute.id}`} />
                  <Button tone="secondary" onClick={() => onSelect(dispute.id)} testId={`open-dispute-${dispute.id}`}>
                    Open
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {selectedId !== null && <DisputePanel disputeId={selectedId} onChanged={() => void load()} />}
    </div>
  );
}

function DisputePanel({
  disputeId,
  onChanged,
}: {
  readonly disputeId: number;
  readonly onChanged: () => void;
}): React.JSX.Element {
  const [detail, setDetail] = useState<DisputeDetail | null>(null);
  const [packet, setPacket] = useState<EvidencePacket | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editorText, setEditorText] = useState('');

  const load = useCallback(async (): Promise<void> => {
    setError(null);
    try {
      const [nextDetail, nextPacket] = await Promise.all([
        fetchDispute(disputeId),
        fetchPacket(disputeId),
      ]);
      setDetail(nextDetail);
      setPacket(nextPacket);
      const latest = nextDetail.drafts[0];
      if (latest !== undefined) {
        setEditorText(latest.body);
      }
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'Could not load the dispute.');
    }
  }, [disputeId]);

  useEffect(() => {
    setDetail(null);
    setPacket(null);
    void load();
  }, [load]);

  async function act(work: () => Promise<unknown>): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await work();
      await load();
      onChanged();
    } catch (cause: unknown) {
      setError(cause instanceof ApiRequestError ? cause.message : 'That step failed.');
    } finally {
      setBusy(false);
    }
  }

  if (error !== null && detail === null) {
    return <ErrorBanner message={error} onRetry={() => void load()} />;
  }
  if (detail === null || packet === null) {
    return <Loading label="Loading the evidence packet…" />;
  }

  const latest = detail.drafts[0];
  const submitted = detail.status === 'SUBMITTED';

  return (
    <div className="space-y-4" data-testid="dispute-detail">
      {/* A failed approve/submit must be visible: an error that only exists in
          state is indistinguishable from a button that did nothing. */}
      {error !== null && <ErrorBanner message={error} />}
      <Card>
        <CardHeader
          title={`Dispute #${detail.id} · ${detail.order_ref}`}
          subtitle={`${humanise(detail.reason)} · ${money(detail.amount, detail.currency)}`}
          action={<SourceChip source={detail.source} testId="dispute-detail-source" />}
        />
        <dl className="grid grid-cols-2 gap-3 px-4 py-3 sm:grid-cols-4">
          <Field label="Status" value={detail.status} />
          <Field label="Opened" value={dateTime(detail.opened_at)} />
          <Field label="Submitted" value={detail.submitted_at === null ? 'not submitted' : dateTime(detail.submitted_at)} />
          <Field label="Evidence" value={`${detail.evidence_strength}/100`} />
        </dl>
        <p className="border-t border-slate-100 px-4 py-2 text-xs text-slate-700">
          <span className="font-semibold">Buyer claim:</span> {detail.buyer_claim}
        </p>
      </Card>

      <Card testId="packet-card">
        <CardHeader
          title="Evidence packet"
          subtitle={packet.note}
          action={<span className="font-mono text-xs text-slate-600">{packet.evidence_strength.score}/100</span>}
        />
        <div className="px-4 pt-3">
          <ProgressBar
            value={packet.evidence_strength.score}
            max={packet.evidence_strength.max}
            label="Evidence strength"
          />
        </div>
        <ul className="mt-2 divide-y divide-slate-100">
          {packet.evidence.map((item) => (
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
        <div className="border-t border-slate-100 px-4 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Timeline</p>
          <ul className="mt-1 space-y-0.5 text-[11px] text-slate-700">
            {packet.timeline.map((entry) => (
              <li key={`${entry.label}-${entry.at}`}>
                <span className="font-mono text-slate-500">{dateTime(entry.at)}</span> · {entry.label}
              </li>
            ))}
          </ul>
        </div>
      </Card>

      <Card testId="drafts-card">
        <CardHeader
          title="Response draft"
          subtitle="Every save is a new version. Origin is recorded per version; you always send your own words."
          action={
            latest === undefined ? (
              <Button tone="primary" busy={busy} testId="generate-draft" onClick={() => void act(() => createDraft(disputeId))}>
                Generate draft
              </Button>
            ) : (
              <Pill tone={latest.label === null ? 'neutral' : 'violet'}>
                {latest.origin} · v{latest.version}
              </Pill>
            )
          }
        />
        {latest === undefined ? (
          <div className="p-4">
            <EmptyState
              title="No draft yet"
              body="Generate one: the deterministic template is always available, and with a Gemini key configured the model drafts it instead - with a hallucination guard before anything is saved."
            />
          </div>
        ) : (
          <div className="space-y-3 px-4 py-3">
            {latest.label !== null && (
              <p className="rounded border border-violet-200 bg-violet-50 p-2 text-[11px] text-violet-900">
                {latest.label}
              </p>
            )}
            <p className="text-[11px] text-slate-600">
              <span className="font-semibold">Strategy:</span> {latest.strategy_note}
            </p>
            <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-500" htmlFor="draft-editor">
              Draft text
            </label>
            <textarea
              id="draft-editor"
              data-testid="draft-editor"
              value={editorText}
              onChange={(event) => setEditorText(event.target.value)}
              rows={14}
              className="w-full rounded-md border border-slate-300 p-2 font-mono text-xs"
              disabled={submitted}
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                tone="secondary"
                busy={busy}
                disabled={submitted}
                testId="save-draft"
                onClick={() => void act(() => createDraft(disputeId, editorText))}
              >
                Save as a new version
              </Button>
              <Button
                tone="primary"
                busy={busy}
                disabled={submitted || latest.status === 'APPROVED'}
                testId="approve-draft"
                onClick={() => void act(() => approveDraft(disputeId, latest.id))}
              >
                Approve v{latest.version}
              </Button>
              <Button
                tone="secondary"
                busy={busy}
                disabled={submitted || latest.status !== 'APPROVED'}
                testId="submit-dispute"
                onClick={() => void act(() => submitDispute(disputeId))}
              >
                Submit response
              </Button>
              <span className="text-[11px] text-slate-500">
                Submission is recorded as SIMULATED: no PayPal dispute API call is made.
              </span>
            </div>
            {detail.submit_result !== null && (
              <div className="rounded border border-emerald-200 bg-emerald-50 p-2 text-[11px] text-emerald-900" data-testid="submit-result">
                <p className="font-semibold">
                  Recorded with submission mode{' '}
                  <span className="font-mono">{detail.submit_result.submission_mode ?? 'SIMULATED'}</span>
                </p>
                <p className="mt-0.5">{detail.submit_result.note}</p>
              </div>
            )}
          </div>
        )}

        {detail.drafts.length > 1 && (
          <div className="border-t border-slate-100 px-4 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Version history
            </p>
            <ul className="mt-1 space-y-1 text-[11px] text-slate-700">
              {detail.drafts.map((draft) => (
                <li key={draft.id} className="flex flex-wrap items-center gap-2">
                  <span className="font-mono">v{draft.version}</span>
                  <Pill tone={draft.label === null ? 'neutral' : 'violet'}>{draft.origin}</Pill>
                  <span>{dateTime(draft.created_at)}</span>
                  <span className="text-slate-500">{draft.status}</span>
                  <Button tone="ghost" onClick={() => setEditorText(draft.body)} testId={`view-draft-${draft.version}`}>
                    Load into editor
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { ApiRequestError, fetchMethodology } from '../api/client';
import { SourceChip } from '../components/SourceChip';
import { Card, CardHeader, ErrorBanner, Loading, Pill, Stat } from '../components/ui';
import type { Methodology } from '../types';

/** Percentages rendered with one decimal, from the stored metrics only. */
function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function AboutPage(): React.JSX.Element {
  const [data, setData] = useState<Methodology | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMethodology()
      .then((methodology) => {
        if (!cancelled) {
          setData(methodology);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(
            cause instanceof ApiRequestError ? cause.message : 'Could not load the methodology.',
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error !== null) {
    return <ErrorBanner message={error} />;
  }
  if (data === null) {
    return <Loading label="Loading methodology…" />;
  }

  const metrics = data.ml_estimate.metrics;
  const confusion = metrics.model.confusion_matrix;

  return (
    <div className="space-y-4" data-testid="about-page">
      <Card>
        <CardHeader
          title="What this is"
          subtitle="Three scores, three different kinds of honesty about what they mean."
        />
        <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-3">
          <div className="rounded-lg border border-slate-200 p-3">
            <p className="text-sm font-semibold text-slate-900">Rule score</p>
            <p className="mt-1 text-xs text-slate-700">{data.rule_score.what}</p>
            <p className="mt-1 text-[11px] text-slate-500">{data.rule_score.range}</p>
            <p className="mt-1 text-[11px] font-semibold text-red-700">{data.rule_score.is_not}</p>
          </div>
          <div className="rounded-lg border border-slate-200 p-3">
            <p className="text-sm font-semibold text-slate-900">Model estimate</p>
            <p className="mt-1 text-xs text-slate-700">{data.ml_estimate.what}</p>
            <p className="mt-1 text-[11px] text-slate-500">{data.ml_estimate.trained_on}</p>
            <p className="mt-1 text-[11px] font-semibold text-red-700">{data.ml_estimate.is_not}</p>
          </div>
          <div className="rounded-lg border border-slate-200 p-3">
            <p className="text-sm font-semibold text-slate-900">Evidence strength</p>
            <p className="mt-1 text-xs text-slate-700">{data.evidence_strength.what}</p>
            <p className="mt-1 text-[11px] font-semibold text-red-700">
              {data.evidence_strength.is_not}
            </p>
          </div>
        </div>
      </Card>

      <Card testId="metrics-card">
        <CardHeader
          title="Model metrics, as stored"
          subtitle={metrics.data.note}
          action={<Pill tone="warn">SYNTHETIC DATA</Pill>}
        />
        <div className="grid grid-cols-2 gap-3 p-4 lg:grid-cols-4">
          <Stat label="Accuracy" value={pct(metrics.model.accuracy)} hint={metrics.model.name} />
          <Stat label="ROC AUC" value={metrics.model.roc_auc.toFixed(3)} />
          <Stat label="Training rows" value={metrics.rows_train} hint={`${metrics.rows_total} total, ${metrics.positives} positive`} />
          <Stat label="Seed" value={metrics.data.seed} hint="deterministic re-runs" />
        </div>
        <div className="overflow-x-auto border-t border-slate-100">
          <table className="min-w-full text-xs">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
                <th className="px-4 py-2 font-semibold">Baseline</th>
                <th className="px-4 py-2 font-semibold">Accuracy</th>
                <th className="px-4 py-2 font-semibold">ROC AUC</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <tr>
                <td className="px-4 py-2">Majority class (always predict the common label)</td>
                <td className="px-4 py-2 tabular-nums">{pct(metrics.baselines.majority_class.accuracy)}</td>
                <td className="px-4 py-2 text-slate-500">n/a</td>
              </tr>
              <tr>
                <td className="px-4 py-2">Phase-1 rule score</td>
                <td className="px-4 py-2 tabular-nums">{pct(metrics.baselines.phase_1_rule_score.accuracy)}</td>
                <td className="px-4 py-2 tabular-nums">
                  {metrics.baselines.phase_1_rule_score.roc_auc?.toFixed(3) ?? 'n/a'}
                </td>
              </tr>
              <tr className="bg-slate-50 font-semibold">
                <td className="px-4 py-2">This model</td>
                <td className="px-4 py-2 tabular-nums">{pct(metrics.model.accuracy)}</td>
                <td className="px-4 py-2 tabular-nums">{metrics.model.roc_auc.toFixed(3)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="border-t border-slate-100 px-4 py-2 text-[11px] text-slate-600">
          Confusion matrix on the held-out split: true negatives {confusion.tn}, false positives{' '}
          {confusion.fp}, false negatives {confusion.fn}, true positives {confusion.tp}. Features:{' '}
          <span className="font-mono">{metrics.features.join(', ')}</span>.
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card testId="source-labels-card">
          <CardHeader title="Source labels" subtitle="Every record on screen carries exactly one." />
          <ul className="divide-y divide-slate-100">
            {(Object.keys(data.source_labels) as (keyof typeof data.source_labels)[]).map((label) => (
              <li key={label} className="flex items-start gap-2 px-4 py-2 text-xs">
                <SourceChip source={label} testId={`label-${label}`} />
                <span className="text-slate-700">{data.source_labels[label]}</span>
                <span className="ml-auto font-mono text-[11px] text-slate-500">
                  {data.counts_by_source[label] ?? 0} record(s)
                </span>
              </li>
            ))}
          </ul>
          <p className="border-t border-slate-100 px-4 py-2 text-[11px] text-slate-500">
            Actions executed so far: {data.actions_executed}. PayPal mode:{' '}
            <span className="font-mono">{data.paypal.mode}</span> ({data.paypal.source_label}),
            credentials {data.paypal.credentials_present ? 'present' : 'not configured'}. LLM
            provider: <span className="font-mono">{data.llm.provider}</span> — {data.llm.fallback}
          </p>
        </Card>

        <Card testId="honesty-card">
          <CardHeader title="Rules this app holds itself to" subtitle="Enforced in code and tests, not just here." />
          <ul className="list-disc space-y-1 px-8 py-3 text-xs text-slate-700">
            {data.honesty_rules.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
          <div className="border-t border-slate-100 px-4 py-2 text-[11px] text-slate-600">
            <p className="font-semibold text-slate-800">What is not built</p>
            <p className="mt-0.5">
              No production PayPal access, no dispute filing against PayPal's Disputes API, no
              carrier API lookups, no email sending, no training on real PayPal data. Every external
              call in this build goes to a local mock or the PayPal Sandbox, and says so.
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}

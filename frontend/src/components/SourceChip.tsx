import type { SourceLabel } from '../types';

/**
 * Rule R5 / section 10: the UI must clearly distinguish the three provenance
 * labels and must never imply a mock response came from PayPal.
 *
 * The chip text is the raw label, so what a judge sees on screen is exactly
 * what is stored in the database - no friendly re-wording that could blur
 * "we called PayPal" and "we made this up locally".
 */
const STYLES: Readonly<Record<SourceLabel, string>> = {
  PAYPAL_SANDBOX: 'bg-emerald-100 text-emerald-900 border-emerald-400',
  SIMULATED: 'bg-amber-100 text-amber-900 border-amber-400',
  MOCK: 'bg-slate-200 text-slate-800 border-slate-400',
};

const EXPLANATIONS: Readonly<Record<SourceLabel, string>> = {
  PAYPAL_SANDBOX: 'Real response from the PayPal Sandbox API (never production).',
  SIMULATED: 'Generated locally by MerchantShield. No external system was contacted.',
  MOCK: 'Produced by the mock PayPal adapter standing in for a real call.',
};

interface SourceChipProps {
  readonly source: SourceLabel;
  readonly testId?: string;
}

export function SourceChip({ source, testId = 'source-chip' }: SourceChipProps): React.JSX.Element {
  return (
    <span
      data-testid={testId}
      data-source={source}
      title={EXPLANATIONS[source]}
      aria-label={`Data source: ${source}. ${EXPLANATIONS[source]}`}
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-xs font-semibold tracking-wide ${STYLES[source]}`}
    >
      {source}
    </span>
  );
}

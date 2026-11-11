import type { ReactNode } from 'react';
import type { RiskLevel } from '../types';

export function Card({
  children,
  className = '',
  testId,
}: {
  readonly children: ReactNode;
  readonly className?: string;
  readonly testId?: string;
}): React.JSX.Element {
  return (
    <section
      data-testid={testId}
      className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}
    >
      {children}
    </section>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
  level = 2,
}: {
  readonly title: ReactNode;
  readonly subtitle?: ReactNode;
  readonly action?: ReactNode;
  readonly level?: 2 | 3;
}): React.JSX.Element {
  const Heading = level === 2 ? 'h2' : 'h3';
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3 sm:px-5">
      <div>
        <Heading className="text-sm font-semibold tracking-tight text-slate-900">{title}</Heading>
        {subtitle !== undefined && <p className="mt-0.5 text-xs text-slate-600">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

const RISK_STYLES: Readonly<Record<RiskLevel, string>> = {
  HIGH: 'bg-red-100 text-red-900 border-red-300',
  MEDIUM: 'bg-amber-100 text-amber-900 border-amber-300',
  LOW: 'bg-emerald-100 text-emerald-900 border-emerald-300',
};

export function RiskBadge({
  level,
  score,
}: {
  readonly level: RiskLevel;
  readonly score?: number | null;
}): React.JSX.Element {
  return (
    <span
      data-testid="risk-badge"
      data-risk={level}
      title="Rule-based score from your own order fields. Not a probability."
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${RISK_STYLES[level]}`}
    >
      {level}
      {score !== null && score !== undefined && (
        <span className="font-mono text-[11px] opacity-80">{score.toFixed(2)}</span>
      )}
    </span>
  );
}

const PILL_TONES = {
  neutral: 'bg-slate-100 text-slate-700 border-slate-300',
  info: 'bg-sky-100 text-sky-900 border-sky-300',
  good: 'bg-emerald-100 text-emerald-900 border-emerald-300',
  warn: 'bg-amber-100 text-amber-900 border-amber-300',
  bad: 'bg-red-100 text-red-900 border-red-300',
  violet: 'bg-violet-100 text-violet-900 border-violet-300',
} as const;

export type PillTone = keyof typeof PILL_TONES;

export function Pill({
  children,
  tone = 'neutral',
  mono = false,
  testId,
}: {
  readonly children: ReactNode;
  readonly tone?: PillTone;
  readonly mono?: boolean;
  readonly testId?: string;
}): React.JSX.Element {
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${PILL_TONES[tone]} ${mono ? 'font-mono' : ''}`}
    >
      {children}
    </span>
  );
}

export function Stat({
  label,
  value,
  hint,
  testId,
}: {
  readonly label: string;
  readonly value: ReactNode;
  readonly hint?: string;
  readonly testId?: string;
}): React.JSX.Element {
  return (
    <div data-testid={testId} className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-slate-900">{value}</p>
      {hint !== undefined && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function Field({
  label,
  value,
  mono = false,
}: {
  readonly label: string;
  readonly value: ReactNode;
  readonly mono?: boolean;
}): React.JSX.Element {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className={`text-sm text-slate-900 ${mono ? 'font-mono text-xs' : ''}`}>{value}</dd>
    </div>
  );
}

export function ProgressBar({
  value,
  max,
  tone = 'sky',
  label,
}: {
  readonly value: number;
  readonly max: number;
  readonly tone?: 'sky' | 'emerald' | 'amber';
  readonly label: string;
}): React.JSX.Element {
  const width = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  const bar = { sky: 'bg-sky-500', emerald: 'bg-emerald-500', amber: 'bg-amber-500' }[tone];
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      className="h-2 w-full overflow-hidden rounded-full bg-slate-200"
    >
      <div className={`h-full rounded-full ${bar}`} style={{ width: `${width}%` }} />
    </div>
  );
}

export function ErrorBanner({
  title = 'Something went wrong',
  message,
  onRetry,
}: {
  readonly title?: string;
  readonly message: string;
  readonly onRetry?: () => void;
}): React.JSX.Element {
  return (
    <div
      role="alert"
      data-testid="error-banner"
      className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-900"
    >
      <p className="font-semibold">{title}</p>
      <p className="mt-1">{message}</p>
      {onRetry !== undefined && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md border border-red-400 bg-white px-3 py-1.5 text-xs font-semibold text-red-800 hover:bg-red-100"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function Loading({ label = 'Loading…' }: { readonly label?: string }): React.JSX.Element {
  return (
    <p data-testid="loading-state" className="animate-pulse text-sm text-slate-500">
      {label}
    </p>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  readonly title: string;
  readonly body: string;
  readonly action?: ReactNode;
}): React.JSX.Element {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center">
      <p className="text-sm font-semibold text-slate-800">{title}</p>
      <p className="mx-auto mt-1 max-w-md text-xs text-slate-600">{body}</p>
      {action !== undefined && <div className="mt-3 flex justify-center">{action}</div>}
    </div>
  );
}

type ButtonTone = 'primary' | 'secondary' | 'danger' | 'ghost';

const BUTTON_STYLES: Readonly<Record<ButtonTone, string>> = {
  primary: 'bg-slate-900 text-white hover:bg-slate-800 border-slate-900',
  secondary: 'bg-white text-slate-800 hover:bg-slate-100 border-slate-300',
  danger: 'bg-white text-red-700 hover:bg-red-50 border-red-300',
  ghost: 'bg-transparent text-slate-700 hover:bg-slate-100 border-transparent',
};

export function Button({
  children,
  onClick,
  tone = 'secondary',
  disabled = false,
  busy = false,
  testId,
  type = 'button',
}: {
  readonly children: ReactNode;
  readonly onClick?: () => void;
  readonly tone?: ButtonTone;
  readonly disabled?: boolean;
  readonly busy?: boolean;
  readonly testId?: string;
  readonly type?: 'button' | 'submit';
}): React.JSX.Element {
  return (
    <button
      type={type}
      data-testid={testId}
      onClick={onClick}
      disabled={disabled || busy}
      aria-busy={busy}
      className={`inline-flex items-center justify-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${BUTTON_STYLES[tone]}`}
    >
      {busy ? 'Working…' : children}
    </button>
  );
}

export function Drawer({
  title,
  subtitle,
  onClose,
  children,
  testId = 'drawer',
}: {
  readonly title: ReactNode;
  readonly subtitle?: ReactNode;
  readonly onClose: () => void;
  readonly children: ReactNode;
  readonly testId?: string;
}): React.JSX.Element {
  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Close panel"
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/30"
      />
      <div
        data-testid={testId}
        className="relative flex h-full w-full max-w-3xl flex-col overflow-hidden bg-slate-50 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3">
          <div>
            <h2 className="text-base font-semibold text-slate-900">{title}</h2>
            {subtitle !== undefined && <p className="mt-0.5 text-xs text-slate-600">{subtitle}</p>}
          </div>
          <Button tone="ghost" onClick={onClose} testId="drawer-close">
            Close
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto px-4 py-4">{children}</div>
      </div>
    </div>
  );
}

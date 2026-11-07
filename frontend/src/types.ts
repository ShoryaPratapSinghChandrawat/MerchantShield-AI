/**
 * Types mirroring the backend API. Kept hand-written and narrow on purpose:
 * `strict` TypeScript with no `any` means an unexpected payload shows up as a
 * compile error or a runtime guard failure, not as `undefined` in the UI.
 */

/** Rule R5: the only three provenance labels that exist. */
export const SOURCE_LABELS = ['PAYPAL_SANDBOX', 'SIMULATED', 'MOCK'] as const;

export type SourceLabel = (typeof SOURCE_LABELS)[number];

export function isSourceLabel(value: unknown): value is SourceLabel {
  return typeof value === 'string' && (SOURCE_LABELS as readonly string[]).includes(value);
}

export interface Order {
  readonly id: number;
  readonly order_ref: string;
  readonly buyer_name: string;
  readonly buyer_email: string;
  readonly item_name: string;
  /** Fixed 2-decimal string, e.g. "189.99". Never a float. */
  readonly amount: string;
  readonly currency: string;
  readonly status: string;
  readonly source: SourceLabel;
  readonly is_demo: boolean;
  readonly demo_run_id: string | null;
  /** ISO-8601 UTC, always ending in "Z". */
  readonly created_at: string;
  readonly updated_at: string;
}

export interface Health {
  readonly status: string;
  readonly phase: string;
  readonly demo_mode: boolean;
  readonly paypal_mode: string;
  readonly paypal_credentials_present: boolean;
  readonly server_time: string;
}

export interface ApiError {
  readonly detail: string;
}

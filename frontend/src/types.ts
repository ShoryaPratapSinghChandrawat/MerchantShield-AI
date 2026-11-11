/**
 * Types mirroring the backend API. Kept hand-written and narrow on purpose:
 * `strict` TypeScript with no `any` means an unexpected payload shows up as a
 * compile error or a guarded runtime failure, not as `undefined` in the UI.
 */

/** Rule R5: the only three provenance labels that exist. */
export const SOURCE_LABELS = ['PAYPAL_SANDBOX', 'SIMULATED', 'MOCK'] as const;

export type SourceLabel = (typeof SOURCE_LABELS)[number];

export function isSourceLabel(value: unknown): value is SourceLabel {
  return typeof value === 'string' && (SOURCE_LABELS as readonly string[]).includes(value);
}

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export type ActionType = 'ADD_TRACKING' | 'MESSAGE_BUYER' | 'FLAG_FOR_REVIEW';

export type ActionStatus =
  | 'PENDING'
  | 'APPROVED'
  | 'REJECTED'
  | 'EXECUTING'
  | 'EXECUTED'
  | 'FAILED'
  | 'UNKNOWN';

export type ReconcileOutcome = 'APPLIED' | 'NOT_APPLIED' | 'INDETERMINATE';

export interface Health {
  readonly status: string;
  readonly phase: string;
  readonly demo_mode: boolean;
  readonly paypal_mode: string;
  readonly paypal_credentials_present: boolean;
  readonly llm_provider: string;
  readonly server_time: string;
}

export interface RiskReason {
  readonly code: string;
  readonly label: string;
  /** "+" pushes risk up, "-" pulls it down. */
  readonly direction: string;
  readonly points: number;
}

export interface EvidenceCheck {
  readonly kind: string;
  readonly label: string;
  readonly present: boolean;
  readonly value: string;
  readonly what_to_do: string;
}

export interface EvidenceStrength {
  readonly score: number;
  readonly max: number;
  readonly present: string[];
  readonly missing: string[];
  readonly what_to_upload: { readonly label: string; readonly hint: string }[];
  readonly note: string;
}

export interface MlFactor {
  readonly feature: string;
  readonly label: string;
  readonly direction: string;
  readonly weight: number;
  readonly value: number;
}

export interface MlEstimate {
  readonly estimate: number;
  readonly label: string;
  readonly raised_by: MlFactor[];
  readonly lowered_by: MlFactor[];
  readonly note: string;
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
  readonly tracking_number: string | null;
  readonly carrier: string | null;
  readonly shipped_at: string | null;
  readonly delivered_at: string | null;
  readonly delivery_confirmed: boolean;
  readonly item_description_on_file: boolean;
  readonly policy_on_file: boolean;
  readonly buyer_country: string;
  readonly merchant_country: string;
  readonly is_first_time_buyer: boolean;
  readonly buyer_negative_history: number;
  readonly category: string;
  readonly flagged_for_review: boolean;
  readonly paypal_order_id: string | null;
  readonly risk_score: number | null;
  readonly risk_level: RiskLevel | null;
  readonly source: SourceLabel;
  readonly is_demo: boolean;
  readonly demo_run_id: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface RiskAssessment {
  readonly risk_score: number;
  readonly risk_level: RiskLevel;
  readonly risk_points: number;
  readonly reasons: RiskReason[];
  readonly missing_evidence: EvidenceCheck[];
  readonly estimate_note: string;
}

export interface OrderRow extends Order {
  readonly reasons: RiskReason[];
}

export interface ActionRecord {
  readonly id: number;
  readonly order_id: number;
  readonly type: ActionType;
  readonly status: ActionStatus;
  readonly payload: Record<string, string>;
  readonly rationale: string;
  readonly proposed_by: string;
  readonly executed_at: string | null;
  readonly claimed_at: string | null;
  readonly before: Record<string, unknown>;
  readonly after: Record<string, unknown>;
  readonly result: Record<string, unknown>;
  readonly error: string | null;
  readonly reconcile_outcome: ReconcileOutcome | null;
  readonly attempts: number;
  readonly idempotency_key: string;
  readonly source: SourceLabel;
  readonly is_demo: boolean;
  readonly demo_run_id: string | null;
  readonly created_at: string;
  readonly updated_at: string;
  readonly can_execute: boolean;
  readonly can_retry: boolean;
  readonly can_reconcile: boolean;
  readonly created?: boolean | undefined;
  readonly already_executed?: boolean | undefined;
}

export interface BuyerMessage {
  readonly id: number;
  readonly direction: string;
  readonly body: string;
  readonly sent_at: string;
  readonly intent: string | null;
  readonly source: SourceLabel;
}

export interface AuditItem {
  readonly id: number;
  readonly order_id: number | null;
  readonly action_id: number | null;
  readonly dispute_id: number | null;
  readonly actor: string;
  readonly event: string;
  readonly message: string;
  readonly detail: Record<string, unknown>;
  readonly source: SourceLabel;
  readonly is_demo: boolean;
  readonly demo_run_id: string | null;
  readonly created_at: string;
}

export interface DisputeSummary {
  readonly id: number;
  readonly order_id: number;
  readonly order_ref: string;
  readonly reason: string;
  readonly status: string;
  readonly amount: string;
  readonly currency: string;
  readonly evidence_strength: number;
  readonly buyer_claim: string;
  readonly opened_at: string;
  readonly submitted_at: string | null;
  readonly source: SourceLabel;
  readonly is_demo: boolean;
  readonly demo_run_id: string | null;
}

export interface DisputeDraft {
  readonly id: number;
  readonly version: number;
  readonly body: string;
  readonly origin: string;
  readonly strategy_note: string;
  readonly missing_evidence: string[];
  readonly status: string;
  readonly created_at: string;
  readonly label: string | null;
}

export interface DisputeDetail extends DisputeSummary {
  readonly submit_result: {
    readonly submission_mode?: string | undefined;
    readonly note?: string | undefined;
    readonly source?: SourceLabel | undefined;
  } | null;
  readonly drafts: DisputeDraft[];
}

export interface EvidencePacket {
  readonly dispute_id: number;
  readonly order_ref: string;
  readonly reason: string;
  readonly status: string;
  readonly amount: string;
  readonly buyer_claim: string;
  readonly evidence_strength: EvidenceStrength;
  readonly evidence: EvidenceCheck[];
  readonly timeline: { readonly label: string; readonly at: string }[];
  readonly source: SourceLabel;
  readonly note: string;
}

export interface OrderDetail {
  readonly order: Order;
  readonly risk: RiskAssessment;
  readonly ml_risk_estimate: MlEstimate | null;
  readonly evidence_strength: EvidenceStrength;
  readonly actions: ActionRecord[];
  readonly messages: BuyerMessage[];
  readonly evidence_items: EvidenceCheck[];
  readonly audit: AuditItem[];
  readonly disputes: DisputeSummary[];
}

export interface Product {
  readonly id: string;
  readonly name: string;
  readonly price: string;
  readonly category: string;
  readonly blurb: string;
  readonly high_value: boolean;
}

export interface CheckoutResult {
  readonly order_id: number;
  readonly order_ref: string;
  readonly paypal_order_id: string;
  readonly approval_url: string;
  readonly source: SourceLabel;
  readonly mock: boolean;
  readonly product: Product;
}

export interface CaptureResult {
  readonly captured: boolean;
  readonly order_id: number;
  readonly order_ref: string;
  readonly source: SourceLabel;
  readonly note: string;
}

export interface StoryStep {
  readonly step: string;
  readonly title: string;
  readonly detail: string;
  readonly source: SourceLabel;
}

export interface StoryRun {
  readonly run_id: string;
  readonly order_id: number;
  readonly order_ref: string;
  readonly steps: StoryStep[];
  readonly executed_action_ids: number[];
  readonly dispute_id: number;
  readonly note: string;
}

export interface Methodology {
  readonly rule_score: { readonly what: string; readonly range: string; readonly is_not: string };
  readonly ml_estimate: {
    readonly what: string;
    readonly trained_on: string;
    readonly metrics: {
      readonly rows_total: number;
      readonly rows_train: number;
      readonly rows_test: number;
      readonly positives: number;
      readonly features: string[];
      readonly model: {
        readonly name: string;
        readonly accuracy: number;
        readonly roc_auc: number;
        readonly confusion_matrix: { tn: number; fp: number; fn: number; tp: number };
      };
      readonly baselines: {
        readonly majority_class: { readonly accuracy: number };
        readonly phase_1_rule_score: { readonly accuracy: number; readonly roc_auc?: number };
      };
      readonly data: { readonly kind: string; readonly note: string; readonly seed: number };
    };
    readonly is_not: string;
  };
  readonly evidence_strength: { readonly what: string; readonly is_not: string };
  readonly source_labels: Record<SourceLabel, string>;
  readonly counts_by_source: Record<SourceLabel, number>;
  readonly actions_executed: number;
  readonly llm: { readonly provider: string; readonly model: string | null; readonly fallback: string };
  readonly paypal: {
    readonly mode: string;
    readonly source_label: SourceLabel;
    readonly credentials_present: boolean;
    readonly base_url: string;
  };
  readonly honesty_rules: string[];
}

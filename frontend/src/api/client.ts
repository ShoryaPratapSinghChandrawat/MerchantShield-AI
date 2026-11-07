import type { Health, Order } from '../types';
import { isSourceLabel } from '../types';

/**
 * Relative URLs only. The browser is never told where the backend lives -
 * in dev Vite proxies /api, in production FastAPI serves the SPA from the
 * same origin. This is also what keeps the app working behind a reverse
 * proxy without a wildcard CORS policy.
 */
const API_BASE = '/api';

export class ApiRequestError extends Error {
  public readonly status: number;

  public constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
  }
}

async function getJson(path: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: 'application/json' },
    });
  } catch (cause) {
    throw new ApiRequestError(
      `Could not reach the MerchantShield API at ${API_BASE}${path}. Is the backend running?`,
      0,
    );
  }

  const text = await response.text();
  let parsed: unknown = null;
  if (text.length > 0) {
    try {
      parsed = JSON.parse(text) as unknown;
    } catch {
      throw new ApiRequestError(
        `The API returned a non-JSON response (HTTP ${response.status}).`,
        response.status,
      );
    }
  }

  if (!response.ok) {
    const detail =
      typeof parsed === 'object' && parsed !== null && 'detail' in parsed
        ? String((parsed as { detail: unknown }).detail)
        : `Request failed with HTTP ${response.status}.`;
    throw new ApiRequestError(detail, response.status);
  }

  return parsed;
}

function asRecord(value: unknown, what: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new ApiRequestError(`Malformed ${what} payload from the API.`, 500);
  }
  return value as Record<string, unknown>;
}

export async function fetchHealth(): Promise<Health> {
  const raw = asRecord(await getJson('/health'), 'health');
  return {
    status: String(raw['status'] ?? ''),
    phase: String(raw['phase'] ?? ''),
    demo_mode: raw['demo_mode'] === true,
    paypal_mode: String(raw['paypal_mode'] ?? ''),
    paypal_credentials_present: raw['paypal_credentials_present'] === true,
    server_time: String(raw['server_time'] ?? ''),
  };
}

export async function fetchOrder(orderId: number): Promise<Order> {
  const raw = asRecord(await getJson(`/orders/${orderId}`), 'order');

  const source = raw['source'];
  if (!isSourceLabel(source)) {
    // Refuse to render an unlabelled record rather than guess its provenance.
    throw new ApiRequestError(
      `Order ${orderId} has an unrecognised source label: ${String(source)}`,
      500,
    );
  }

  const demoRunId = raw['demo_run_id'];

  return {
    id: Number(raw['id']),
    order_ref: String(raw['order_ref'] ?? ''),
    buyer_name: String(raw['buyer_name'] ?? ''),
    buyer_email: String(raw['buyer_email'] ?? ''),
    item_name: String(raw['item_name'] ?? ''),
    amount: String(raw['amount'] ?? ''),
    currency: String(raw['currency'] ?? ''),
    status: String(raw['status'] ?? ''),
    source,
    is_demo: raw['is_demo'] === true,
    demo_run_id: typeof demoRunId === 'string' ? demoRunId : null,
    created_at: String(raw['created_at'] ?? ''),
    updated_at: String(raw['updated_at'] ?? ''),
  };
}

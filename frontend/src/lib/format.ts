/**
 * Presentation-only formatting. Amounts arrive as fixed 2-decimal strings from
 * the API on purpose (never floats), so they are formatted as strings here too.
 */

export function money(amount: string, currency: string): string {
  const numeric = Number.parseFloat(amount);
  if (!Number.isFinite(numeric)) {
    return `${amount} ${currency}`.trim();
  }
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      maximumFractionDigits: 2,
    }).format(numeric);
  } catch {
    return `${amount} ${currency}`.trim();
  }
}

export function percent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** "2026-09-22T09:00:00.000Z" -> "22 Sep 2026, 09:00 UTC" */
export function dateTime(iso: string): string {
  if (!iso) {
    return '—';
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  const formatted = new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
    hour12: false,
  }).format(date);
  return `${formatted} UTC`;
}

/** "MS-2001" -> "Order MS-2001". Kept for consistent headings. */
export function orderTitle(ref: string): string {
  return `Order ${ref}`;
}

/** "MERCHANDISE_OR_SERVICE_NOT_RECEIVED" -> "Merchandise or service not received" */
export function humanise(value: string): string {
  if (!value) {
    return '';
  }
  const lower = value.replace(/_/g, ' ').toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

export function truncate(value: string, max = 80): string {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}

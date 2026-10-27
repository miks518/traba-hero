/**
 * The findings' ranking tiers, shared by every consumer of a finding's code.
 *
 * The scan emits no severity (`docs/decisions/scan-severity-removal.md`); what
 * a finding carries is its taxonomy `code`. These tiers restate the scan
 * prompt's own selection rule — rank by what the posting asks the reader to
 * give up — as code, so the verify cap, the card icon, and the card colour all
 * read the same order from one definition instead of three.
 *
 *   3 — a demand for money or account access: fees, purchases, deposits,
 *       forwarded payments, account credentials.
 *   2 — identity exposure, an authority claim, or a labour scheme: documents
 *       via a third party, a government/company impersonation, paid tasks.
 *   1 — the ordinary applicant packet, `OTHER`, or no code at all.
 */
export const DEMAND_CODES = new Set([
  'FEE_MANDATORY',
  'FEE_CONDITIONAL',
  'PURCHASE_REQUIRED',
  'DEPOSIT_REQUIRED',
  'PAYMENT_FORWARDING',
  'ACCOUNT_CREDENTIALS',
]);

export const EXPOSURE_CODES = new Set([
  'DOCUMENTS_VIA_THIRD_PARTY',
  'IMPERSONATES_AUTHORITY',
  'TASK_FOR_EARNING',
]);

export type FindingTier = 3 | 2 | 1;

export function findingTier(code?: string): FindingTier {
  if (code && DEMAND_CODES.has(code)) return 3;
  if (code && EXPOSURE_CODES.has(code)) return 2;
  return 1;
}

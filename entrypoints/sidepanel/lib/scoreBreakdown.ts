import type { RiskScoreBreakdown } from '../types';

/**
 * The backend's `score_breakdown`, before translation.
 *
 * `verification_score` is the wire's name for the employer stage. What it now
 * holds is a refutation sum — see `RiskScoreBreakdown.refutationScore` — and
 * the wire key was left alone because the panel reads it. Renaming the client's
 * field and translating here keeps the wire stable (stored scans and a deployed
 * backend both depend on it) while the name a reader of the panel meets is the
 * one that describes the quantity.
 */
interface ScoreBreakdownWire {
  source?: string;
  high_count?: number;
  mid_count?: number;
  low_count?: number;
  weights?: Record<string, number>;
  posting_score?: number;
  verification_score?: number | null;
  final_score?: number | null;
  sources?: string[];
}

/**
 * The one place the breakdown crosses from the wire into the panel.
 *
 * Every field is mapped rather than spread. A spread would carry
 * `verification_score` through alongside `refutationScore`, so the old name
 * would still be readable on a `ScanResult` — and reading it is exactly the
 * mistake the rename exists to prevent.
 *
 * `undefined` in, `undefined` out: a scan taken before the posting stage scored
 * anything carries no breakdown at all, and inventing an empty one would make
 * "nothing was measured" look like "nothing contributed".
 */
export function toScoreBreakdown(raw: unknown): RiskScoreBreakdown | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const wire = raw as ScoreBreakdownWire;

  const breakdown: RiskScoreBreakdown = {};
  if (wire.source !== undefined) breakdown.source = wire.source;
  if (wire.high_count !== undefined) breakdown.highCount = wire.high_count;
  if (wire.mid_count !== undefined) breakdown.midCount = wire.mid_count;
  if (wire.low_count !== undefined) breakdown.lowCount = wire.low_count;
  if (wire.weights !== undefined) breakdown.weights = wire.weights;
  if (wire.posting_score !== undefined) breakdown.postingScore = wire.posting_score;
  if (wire.verification_score !== undefined) breakdown.refutationScore = wire.verification_score;
  if (wire.final_score !== undefined) breakdown.finalScore = wire.final_score;
  if (wire.sources !== undefined) breakdown.sources = wire.sources;

  return breakdown;
}

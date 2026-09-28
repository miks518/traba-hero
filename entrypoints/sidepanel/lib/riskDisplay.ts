export interface UnverifiedEmployerInput {
  isJobPosting: boolean;
  companyName: string | null | undefined;
  redFlagCount: number;
}

/**
 * True when a posting names no employer and raised no red flags.
 *
 * The score from the posting stage is 0 in this case, and rendering "0 / Low
 * Risk" would claim the post was cleared. We did check it and found nothing in
 * it, but the employer itself was never checked, so the panel says so rather
 * than implying a clean bill of health.
 *
 * Deliberately narrow: a red flag is real evidence about the post, so it is
 * scored on its severity, and a named employer can be verified normally.
 */
export function isUnverifiedEmployer({
  isJobPosting,
  companyName,
  redFlagCount,
}: UnverifiedEmployerInput): boolean {
  if (!isJobPosting) return false;
  if (redFlagCount > 0) return false;
  return !companyName || companyName.trim().length === 0;
}

/** The levels that put the evidence above the prose. */
export const ELEVATED_LEVELS = ['high', 'critical'] as const;

/** Just the fields a decision about layout depends on. */
export interface ElevationInput {
  riskLevel: 'low' | 'moderate' | 'high' | 'critical' | null;
  verificationLoading?: boolean;
  offerAnalysisLoading?: boolean;
}

/**
 * True when a settled high or critical score should lead with the evidence.
 *
 * Waiting for the level to settle is the point of the `loading` checks. The
 * scan returns a posting-stage score, then external verification blends an
 * employer score into it, so a posting can read "high" and settle at
 * "moderate". Reordering on the intermediate value would move the reader's
 * evidence out from under them and then put it back.
 *
 * A failed verification still promotes, because the posting stage's score is
 * real and the evidence is already known — what is missing is the employer
 * lookup, not the red flags. An unverified level never promotes: "Unverified"
 * is an absent measurement, not a high one.
 */
export function shouldElevateEvidence({
  riskLevel,
  verificationLoading,
  offerAnalysisLoading,
}: ElevationInput): boolean {
  if (verificationLoading || offerAnalysisLoading) return false;
  return riskLevel === 'high' || riskLevel === 'critical';
}

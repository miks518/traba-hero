export interface UnverifiedEmployerInput {
  isJobPosting: boolean;
  companyName: string | null | undefined;
  anomalyCount: number;
}

/**
 * True when a posting names no employer and raised no anomalies.
 *
 * The score from the posting stage is 0 in this case, and rendering "0 / Low
 * Risk" would claim the post was cleared. We did check it and found nothing in
 * it, but the employer itself was never checked, so the panel says so rather
 * than implying a clean bill of health.
 *
 * Deliberately narrow: an anomaly is real evidence about the post, so it is
 * scored on its severity, and a named employer can be verified normally.
 */
export function isUnverifiedEmployer({
  isJobPosting,
  companyName,
  anomalyCount,
}: UnverifiedEmployerInput): boolean {
  if (!isJobPosting) return false;
  if (anomalyCount > 0) return false;
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
 * lookup, not the anomalies. An unverified level never promotes: "Unverified"
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

/**
 * Whether the employer lookup *ran*, as distinct from whether it moved the
 * number.
 *
 * These are different questions and the distinction is the whole point. The
 * refutation stage returns `null` rather than 0 when it refutes nothing — so
 * "learned nothing" stays distinct from "measured zero" — which means the
 * breakdown's `sources` list reads `['posting']` after a lookup that ran and
 * confirmed every claim. Reading `sources` to decide whether the employer was
 * checked told readers their employer had never been looked up, after it had
 * been, and that was the overwhelmingly common successful outcome.
 *
 *   never    no verification result at all
 *   failed   a result arrived carrying `searchOk: false`
 *   refuted  a result arrived with at least one `red`
 *   confirmed a result arrived and nothing was refuted
 */
export type VerificationRun = 'never' | 'failed' | 'refuted' | 'confirmed';

/**
 * The one line under the gauge saying what the number rests on.
 *
 * Collapsed from two stacked sentences. The older one — "Based only on what the
 * offer itself states" — said the same thing as the newer one in every state,
 * and in the state it got wrong it contradicted it: one sentence claimed the
 * employer was unchecked while the one below credited web evidence that had
 * just been gathered. Two sentences making incompatible claims is worse than
 * one, because the reader has no way to tell which to believe.
 *
 * Each state gets its own sentence because they are four different facts:
 *
 *   never     nothing was looked up — a gap in the input, not a clean result
 *   failed    the lookup was attempted and could not complete
 *   confirmed the lookup ran and no source contradicted a claim the posting made
 *   refuted   a retrieved source contradicted a claim the posting made
 *
 * `confirmed` deliberately does not say the employer was unchecked, and does not
 * claim the web evidence raised the number. Verification withholds trust and
 * never grants it, so a lookup that found nothing contradictory confirms the
 * posting's claims without making the posting safe — and saying so is the most
 * honest thing this line can do.
 */
export function describeScoreBasis({
  riskScore,
  verificationRun,
}: {
  riskScore: number;
  verificationRun: VerificationRun;
}): string {
  const score = `${riskScore}/100`;

  switch (verificationRun) {
    case 'refuted':
      return `Posting findings and web evidence: ${score}. A retrieved source contradicted a claim the posting made.`;
    case 'confirmed':
      return `Posting findings and web evidence: ${score}. The employer was looked up and no source contradicted a claim the posting made.`;
    case 'failed':
      return `Posting findings only: ${score}. The employer lookup did not complete, so nothing online was established.`;
    case 'never':
    default:
      return `Posting findings only: ${score}. The employer was not checked.`;
  }
}

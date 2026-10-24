/** Just the fields a decision about rendering a check depends on. */
export interface VisibleCheckInput {
  label: string;
  status: 'green' | 'yellow' | 'red';
}

/**
 * True when a check should be rendered.
 *
 * One case is hidden: Reputation when nothing confirmed or contradicted it.
 *
 * The reasoning is about the *sentence*, not the status. A `yellow` Company
 * Existence says something a reader can use — this employer has no online
 * footprint — and it carries the sources that establish it. A `yellow`
 * Reputation could only say that the results contained no reviews, which is a
 * restatement of the absence rather than a fact about the employer, and it was
 * phrased as one: "The search results do not contain any scam reports, fraud
 * warnings, formal complaints, or employee reviews for <company>". That puts
 * the words *scam* and *fraud* beside a named company in reader-facing text to
 * report that nothing was found, which is the opposite of what the prompt rules
 * exist to prevent. The verify prompt now asks for an empty finding there, so
 * there is nothing left to render.
 *
 * Scoped to this one case on purpose, and both exclusions are load-bearing:
 *
 *   - `red` Reputation is shown. It carries 7 of the 50 refutation points and is
 *     one of the few checks that can raise the score, so a rule that swallowed it
 *     would hide the finding that matters most.
 *   - `yellow` on every other category is shown. Those cards summarise what the
 *     search actually returned, sources included, which is why an all-`yellow`
 *     result still reads as a summary rather than as nothing.
 *
 * Matched case-insensitively because the labeled-text fallback parser takes
 * whatever label the model wrote. It deliberately does *not* carry a legacy
 * alias table: the backend already keeps `_LEGACY_LABELS` for this, and a second
 * copy here is a table that can drift from the first and silently stop hiding.
 */
export function shouldShowCheck({ label, status }: VisibleCheckInput): boolean {
  if (status !== 'yellow') return true;
  return label.trim().toLowerCase() !== 'reputation';
}

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

/** The verdicts that put the evidence above the prose. */
export const ELEVATED_VERDICTS = ['stop', 'caution'] as const;

/** Just the fields a decision about layout depends on. */
export interface ElevationInput {
  verdict: 'clear' | 'note' | 'caution' | 'stop' | null;
  verificationLoading?: boolean;
  offerAnalysisLoading?: boolean;
}

/**
 * True when a settled stop or caution verdict should lead with the evidence.
 *
 * Waiting for the verdict to settle is the point of the `loading` checks. The
 * scan returns a posting-stage verdict, then external verification blends an
 * employer score into it, so a posting can read "caution" and settle at
 * "note". Reordering on the intermediate value would move the reader's
 * evidence out from under them and then put it back.
 *
 * A failed verification still promotes, because the posting stage's verdict is
 * real and the evidence is already known — what is missing is the employer
 * lookup, not the anomalies. An unverdicted result never promotes: "Unverified"
 * is an absent measurement, not a high one.
 */
export function shouldElevateEvidence({
  verdict,
  verificationLoading,
  offerAnalysisLoading,
}: ElevationInput): boolean {
  if (verificationLoading || offerAnalysisLoading) return false;
  return verdict === 'stop' || verdict === 'caution';
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

// `describeScoreBasis` was deleted with the score. It was the one line under the
// gauge saying what the number rested on, and a number it can no longer be
// attached to. Its reasoning is not lost — it is the reasoning behind
// `VerificationRun` above, and behind the four states `WhatWeChecked` derives its
// heading from, which is where the distinction it was protecting actually lives
// now.

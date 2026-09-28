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

/**
 * Every word the assessment block and the action block say.
 *
 * **All of it is authored here, in code, and looked up by assessment.** Nothing in
 * this file may ever be written by a model. That is the whole point of the file
 * existing, and it is not a stylistic preference:
 *
 * 1. **It cannot drift between runs.** A generated phrase is a fresh variance
 *    source on every scan, and assessment stability is a thing this project
 *    measures. An authored table makes phrase stability trivially constant, so
 *    the measurement that remains is assessment stability — a better thing to measure,
 *    since a phrase is not comparable across two postings in any case.
 * 2. **It keeps the libel guardrail in code.** These are instructions read by
 *    someone deciding about their own money and documents. Four reviewed strings
 *    cannot assert something the evidence does not support; a model-written
 *    headline can, on any given run, with no acceptable failure rate.
 *
 * Source: `docs/decisions/report-panel-redesign.md` "Assessment phrases are
 * authored, not generated"; `docs/superpowers/specs/2026-10-17-report-panel-architecture.md`
 * §3.
 */

import type { Assessment } from '../../types';

/**
 * Three tones for three assessments.
 *
 * `red` gets the critical tone. `yellow` gets the caution tone — it is
 * uncertainty, from either grid rule. `green` gets the verified tone, which is
 * a statement about the search's outcome and never a clearance: the employer
 * may still be unestablished. `unknown` gets the unknown tone (grey) for
 * missing employer / in-flight.
 */
export type AssessmentTone = 'critical' | 'caution' | 'verified' | 'unknown';

export interface AssessmentCopy {
  /** The chip word. The reader acts on the sentence below it. */
  headline: string;
  tone: AssessmentTone;
}

/**
 * The phrase table. Three assessments, three reviewed strings.
 *
 * The words report the evidence relation, not a verdict: "Contradicted" is the
 * headline for `red` only, and `red` requires a contradiction. "Caution" is the
 * one advisory word, backed by the grid rule in the breakdown. "Nothing found
 * against it" claims only that the search found nothing — never that the
 * posting is safe.
 */
const ASSESSMENT_TABLE: Record<Assessment, AssessmentCopy> = {
  red: {
    headline: 'Contradicted',
    tone: 'critical',
  },
  yellow: {
    headline: 'Caution',
    tone: 'caution',
  },
  green: {
    headline: 'Nothing found against it',
    tone: 'verified',
  },
};

/**
 * The one state with no assessment behind it.
 *
 * Reached when the posting named no employer, so the employer check could not
 * run. **Not** rendered as a clean result: the posting stage scores zero when a
 * posting raises no indicators, and showing that as reassurance would claim the
 * post was cleared when it was unchecked. This is the panel's answer to the same
 * question `CompanyNameNeeded` answers in prose — that state still exists as its
 * own component, and the banner here only declines to assert a assessment.
 */
export const NO_ASSESSMENT: AssessmentCopy = {
  headline: 'No assessment on this one',
  tone: 'unknown',
};

/**
 * What the banner says while the employer lookup is still running.
 *
 * The tone is `unknown` rather than the posting stage's own level, on purpose.
 * The scan returns a assessment from the posting alone, but the settled assessment can
 * move once verification blends in — a posting can read `caution` and settle at
 * `note`. Showing the intermediate value as though it were the assessment is the
 * same overclaim as showing the retired score, in a new place: the reader is told
 * where to stop before anything has checked who is asking.
 *
 * The copy asserts only that a check is in progress, which is the one thing that
 * is true. "We are checking whether this company is real" — not a assessment, and
 * not a reassurance.
 */
export const VERIFYING: AssessmentCopy = {
  headline: 'Checking this job post',
  tone: 'unknown',
};

/**
 * What the banner says when the run could not complete.
 *
 * **Distinct from `VERIFYING` on purpose.** The sticky session flag folded a
 * failed lookup into the in-flight prop, so a run that died mid-verification
 * kept saying "Checking this job post" with its "In progress" ping forever —
 * above the same panel's honest sentence that the result could not be read.
 * The two states are now two words.
 *
 * The tone is `unknown` for the same reason `VERIFYING`'s is: no assessment was
 * settled, so the banner must not borrow one. The sentence asserts only what is
 * true — the run stopped — and names the one action available: run it again.
 * It is authored here, like every banner string, so it cannot drift between
 * runs and asserts nothing about the employer.
 */
export const INTERRUPTED: AssessmentCopy = {
  headline: 'Scan has been interrupted, please try again',
  tone: 'unknown',
};

/**
 * The previous procedure's words, for scans recorded before the change. They
 * map onto the colour whose grid cell they would have been, so an old history
 * renders the right copy instead of crashing on a key the table no longer has.
 */
const LEGACY_ASSESSMENT: Record<string, Assessment> = {
  clear: 'green',
  note: 'yellow',
  caution: 'yellow',
  stop: 'red',
};

export function assessmentFor(assessment: Assessment | null | undefined): AssessmentCopy {
  if (!assessment) return NO_ASSESSMENT;
  if (assessment in ASSESSMENT_TABLE) return ASSESSMENT_TABLE[assessment];
  const legacy = LEGACY_ASSESSMENT[assessment];
  return legacy ? ASSESSMENT_TABLE[legacy] : NO_ASSESSMENT;
}

/**
 * The two instruction lines in the action block.
 *
 * Authored per assessment family, and keyed to the family rather than the exact
 * grid rule on purpose: `red` needs the reader to stop; the merged `yellow`
 * covers both of its rules with the same two moves — ask what the offer wants,
 * confirm who is asking. The breakdown carries the rule for anything finer.
 *
 * The second line is the one that keeps this from being a lecture. It tells the
 * reader what to do *next*, which is a thing they can act on today.
 */
export interface ActionLines {
  /** The lead instruction, rendered in bold inside the line. */
  lead: string;
  /** The rest of the sentence. */
  rest: string;
  /** A second instruction, on its own row. */
  secondLead: string;
  secondRest: string;
  /**
   * The bullet's fill, following the assessment's tone.
   *
   * **Which token, and why it differs per tone.** For critical and verified the
   * plain token *is* the saturated brand colour, so `bg-assessment-critical` and
   * `bg-assessment-verified` are the obvious choice. For caution it is not: the
   * plain `--color-assessment-caution` is the text-safe dark gold `#7c5800`, which
   * exists so body copy clears AA on an amber fill. A 10px dot is not body copy —
   * it needs to read as the caution identity at a glance, and dark gold reads as
   * brown. So the dot takes `--color-assessment-caution-container`, the `#feb700`
   * the banner itself is filled with, which is what "matches the assessment colour"
   * has to mean if the panel is to read as one thing.
   *
   * Unknown takes the plain grey rather than its container. The unknown
   * container is `#e2e8f8`, a near-surface tint chosen as a *background* — a dot
   * in it would be invisible.
   */
  bullet: string;
}

const ACTION_TABLE: Record<Assessment | 'unknown', ActionLines> = {
  red: {
    lead: 'Do not send money or documents.',
    rest: 'Even if the request says the fee is refundable, do not send money or identity documents. Stop the application and do not reply to the recruiter until you have checked the company yourself.',
    secondLead: 'Check the company yourself',
    secondRest: 'through an official channel before you apply for anything.',
    bullet: 'bg-assessment-critical',
  },
  yellow: {
    lead: 'Ask what the offer asks for and why.',
    rest: 'An offer that asks for something before a contract is the pattern the rules prohibit.',
    secondLead: 'Confirm the employer\'s identity',
    secondRest: 'through an official channel before you send anything.',
    bullet: 'bg-assessment-caution-container',
  },
  green: {
    lead: 'Continue with the application.',
    rest: 'The posting asks for nothing the rules prohibit, and nothing found contradicts it.',
    secondLead: 'Keep the conversation on the company\'s own domain.',
    secondRest: 'If they switch to a personal email or a messaging app, that is worth asking about before you send anything.',
    bullet: 'bg-assessment-verified',
  },
  unknown: {
    lead: 'No assessment on this one.',
    rest: 'The employer was not looked up, so nothing was assessed.',
    secondLead: 'Check the company name',
    secondRest: 'and scan again when you have one.',
    bullet: 'bg-assessment-unknown',
  },
};

/**
 * The bullet colour when there is no assessment to follow.
 *
 * Neutral, deliberately. `ActionBlock` is asked for a bullet even when the
 * assessment is "no assessment on this one", and an amber bullet there would attach an
 * alarm to a state that is an absent measurement rather than a finding — which
 * is the same reason `assessment-unknown` is grey rather than caution.
 */
export const NO_ASSESSMENT_BULLET = 'bg-assessment-unknown';

export function actionsFor(assessment: Assessment | null | undefined): ActionLines {
  if (!assessment) return ACTION_TABLE.unknown;
  if (assessment in ACTION_TABLE) return ACTION_TABLE[assessment];
  const legacy = LEGACY_ASSESSMENT[assessment];
  return legacy ? ACTION_TABLE[legacy] : ACTION_TABLE.unknown;
}

/**
 * The "Do not share" chips.
 *
 * **Deliberately absent from this build.** The decision record is explicit that
 * these are keyed to the anomaly *code families* the scan emits, and that
 * rendering them generically is a known failure:
 *
 *   > Rendered generically they would be identical for every posting, which is
 *   > the same failure as the state-3 "Good habits" list — advice that does not
 *   > refer to the thing being assessed.
 *
 * The codes are a field the backend does not emit yet
 * (`docs/superpowers/specs/2026-10-17-anomaly-code-set.md`, "draft for review.
 * Nothing here is implemented"). So this returns nothing, the row is not
 * rendered, and the slot comes back the moment the codes land. It is absent
 * rather than empty because a chip row reading "Bank details · ID photos" on
 * every posting in the panel is advice about nothing in particular.
 *
 * The signature is the seam. When `code` exists on `Anomaly`, the chips come
 * from a code → family lookup and this stops being a decision.
 */
export function shareChipsFor(_codes: string[] | undefined): string[] {
  return [];
}
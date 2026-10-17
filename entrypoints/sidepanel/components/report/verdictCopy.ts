/**
 * Every word the verdict block and the action block say.
 *
 * **All of it is authored here, in code, and looked up by level.** Nothing in
 * this file may ever be written by a model. That is the whole point of the file
 * existing, and it is not a stylistic preference:
 *
 * 1. **It cannot drift between runs.** A generated phrase is a fresh variance
 *    source on every scan, and verdict stability is a thing this project
 *    measures. An authored table makes phrase stability trivially constant, so
 *    the measurement that remains is level stability — a better thing to measure,
 *    since a phrase is not comparable across two postings in any case.
 * 2. **It keeps the libel guardrail in code.** These are instructions read by
 *    someone deciding about their own money and documents. Four reviewed strings
 *    cannot assert something the evidence does not support; a model-written
 *    headline can, on any given run, with no acceptable failure rate.
 *
 * Source: `docs/decisions/report-panel-redesign.md` "Verdict phrases are
 * authored, not generated"; `docs/superpowers/specs/2026-10-17-report-panel-architecture.md`
 * §3.
 */

import type { ScanRiskLevel } from '../../types';

/**
 * Three tones for four levels.
 *
 * `low` and `moderate` are both "proceed, with something to check", so they share
 * the caution fill and are told apart by the headline rather than by the colour.
 * Designing eight distinct phrases across four levels would make the panel look
 * more precise than the evidence is — four levels is a coarse label, and the
 * panel should not pretend to more.
 */
export type VerdictTone = 'critical' | 'caution' | 'verified' | 'unknown';

export interface VerdictCopy {
  /** Short imperative instruction. The reader acts on this. */
  headline: string;
  tone: VerdictTone;
}

/**
 * The phrase table. Four levels, four reviewed strings.
 *
 * Written as imperatives addressed to the reader, because the design settles
 * this: *the verdict is a short instruction plus a one-line reason, not a number
 * or a level word*. "Low Risk" tells a reader where they landed; "Proceed, with
 * a quick check" tells them what to do.
 */
const VERDICT_TABLE: Record<ScanRiskLevel, VerdictCopy> = {
  critical: {
    headline: 'Do not proceed',
    tone: 'critical',
  },
  high: {
    headline: 'Do not proceed without checking first',
    tone: 'critical',
  },
  moderate: {
    headline: 'Proceed with caution',
    tone: 'caution',
  },
  low: {
    headline: 'Proceed, with a quick check',
    // Deliberately caution, not verified. A low result means we found little,
    // which is not the same as having confirmed the posting is safe — and a
    // green banner on a scan that checked one page of a link would overclaim
    // exactly as badly as a red one overclaims the other way. The distinction is
    // carried by the headline's "with a quick check", which is not optional
    // phrasing.
    tone: 'caution',
  },
};

/**
 * The one state with no level behind it.
 *
 * Reached when the posting named no employer, so the employer check could not
 * run. **Not** rendered as a clean result: the posting stage scores zero when a
 * posting raises no indicators, and showing that as reassurance would claim the
 * post was cleared when it was unchecked. This is the panel's answer to the same
 * question `CompanyNameNeeded` answers in prose — that state still exists as its
 * own component, and the banner here only declines to assert a level.
 */
export const NO_VERDICT: VerdictCopy = {
  headline: 'No verdict on this one',
  tone: 'unknown',
};

/**
 * What the banner says while the employer lookup is still running.
 *
 * The tone is `unknown` rather than the posting stage's own level, on purpose.
 * The scan returns a level from the posting alone, but the settled level can move
 * once verification blends in — a posting can read `high` and settle at
 * `moderate`. Showing the intermediate value as though it were the verdict is the
 * same overclaim as showing the retired score, in a new place: the reader is told
 * where to stop before anything has checked who is asking.
 *
 * The copy asserts only that a check is in progress, which is the one thing that
 * is true. "We are checking whether this company is real" — not a verdict, and
 * not a reassurance.
 */
export const VERIFYING: VerdictCopy = {
  headline: 'Checking this company',
  tone: 'unknown',
};

export function verdictFor(level: ScanRiskLevel | null | undefined): VerdictCopy {
  if (!level) return NO_VERDICT;
  return VERDICT_TABLE[level];
}

/**
 * The two instruction lines in the action block.
 *
 * Authored per verdict family, and keyed to the family rather than the exact
 * level on purpose: a `critical` and a `high` posting need the reader to stop,
 * and the difference between them is what the anomalies below say, not what the
 * reader should do next. Telling a `high` reader to "proceed with caution" while
 * a `critical` reader is told to stop would make the panel's instruction less
 * precise, not more, because the two levels are one decision.
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
   * The bullet's fill, following the verdict's tone.
   *
   * **Which token, and why it differs per tone.** For critical and verified the
   * plain token *is* the saturated brand colour, so `bg-verdict-critical` and
   * `bg-verdict-verified` are the obvious choice. For caution it is not: the
   * plain `--color-verdict-caution` is the text-safe dark gold `#7c5800`, which
   * exists so body copy clears AA on an amber fill. A 10px dot is not body copy —
   * it needs to read as the caution identity at a glance, and dark gold reads as
   * brown. So the dot takes `--color-verdict-caution-container`, the `#feb700`
   * the banner itself is filled with, which is what "matches the verdict colour"
   * has to mean if the panel is to read as one thing.
   *
   * Unknown takes the plain grey rather than its container. The unknown
   * container is `#e2e8f8`, a near-surface tint chosen as a *background* — a dot
   * in it would be invisible.
   */
  bullet: string;
}

const ACTION_TABLE: Record<'stop' | 'proceed', ActionLines> = {
  stop: {
    lead: 'Stop the application.',
    rest: 'Do not send money, and do not send identity documents, even if the request says the fee is refundable.',
    secondLead: 'Do not reply',
    secondRest: 'to the recruiter until you have checked the company yourself.',
    bullet: 'bg-verdict-critical',
  },
  proceed: {
    lead: 'Keep the conversation on the company’s own domain.',
    rest: 'If they switch to a personal email or a messaging app, that is worth asking about before you send anything.',
    secondLead: 'Check the role yourself',
    secondRest: 'on the company’s careers page before you apply for anything.',
    bullet: 'bg-verdict-caution-container',
  },
};

/**
 * The bullet colour when there is no level to follow.
 *
 * Neutral, deliberately. `ActionBlock` is asked for a bullet even when the
 * verdict is "no verdict on this one", and an amber bullet there would attach an
 * alarm to a state that is an absent measurement rather than a finding — which
 * is the same reason `verdict-unknown` is grey rather than caution.
 */
export const NO_VERDICT_BULLET = 'bg-verdict-unknown';

export function actionsFor(level: ScanRiskLevel | null | undefined): ActionLines {
  if (level === 'high' || level === 'critical') return ACTION_TABLE.stop;
  return ACTION_TABLE.proceed;
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

/**
 * Every word the verdict block and the action block say.
 *
 * **All of it is authored here, in code, and looked up by verdict.** Nothing in
 * this file may ever be written by a model. That is the whole point of the file
 * existing, and it is not a stylistic preference:
 *
 * 1. **It cannot drift between runs.** A generated phrase is a fresh variance
 *    source on every scan, and verdict stability is a thing this project
 *    measures. An authored table makes phrase stability trivially constant, so
 *    the measurement that remains is verdict stability — a better thing to measure,
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

import type { Verdict } from '../../types';

/**
 * Four tones for four verdicts.
 *
 * `stop` gets the critical tone (red). `caution` gets the caution tone (amber).
 * `note` gets the verified tone (green) because the employer is confirmed/supported.
 * `clear` gets the verified tone (green) because the request is ordinary.
 * `unknown` gets the unknown tone (grey) for missing employer / in-flight.
 */
export type VerdictTone = 'critical' | 'caution' | 'verified' | 'unknown';

export interface VerdictCopy {
  /** Short imperative instruction. The reader acts on this. */
  headline: string;
  tone: VerdictTone;
}

/**
 * The phrase table. Four verdicts, four reviewed strings.
 *
 * Written as imperatives addressed to the reader, because the design settles
 * this: *the verdict is a short instruction plus a one-line reason, not a number
 * or a level word*. "Proceed" tells a reader what to do; "Low Risk" tells them
 * where they landed — and the latter overclaims when the posting was unchecked.
 *
 * "Do not proceed" is the ace card: it is the headline for `stop` only, and
 * `stop` requires a contradiction. Every other verdict states what was found
 * and what the record showed.
 */
const VERDICT_TABLE: Record<Verdict, VerdictCopy> = {
  stop: {
    headline: 'Do not proceed',
    tone: 'critical',
  },
  caution: {
    headline: 'Caution — settle the fee recipient and reason first',
    tone: 'caution',
  },
  note: {
    headline: 'Note — check the employer\'s own site for the stated fee',
    tone: 'verified',
  },
  clear: {
    headline: 'Proceed',
    tone: 'verified',
  },
};

/**
 * The one state with no verdict behind it.
 *
 * Reached when the posting named no employer, so the employer check could not
 * run. **Not** rendered as a clean result: the posting stage scores zero when a
 * posting raises no indicators, and showing that as reassurance would claim the
 * post was cleared when it was unchecked. This is the panel's answer to the same
 * question `CompanyNameNeeded` answers in prose — that state still exists as its
 * own component, and the banner here only declines to assert a verdict.
 */
export const NO_VERDICT: VerdictCopy = {
  headline: 'No verdict on this one',
  tone: 'unknown',
};

/**
 * What the banner says while the employer lookup is still running.
 *
 * The tone is `unknown` rather than the posting stage's own level, on purpose.
 * The scan returns a verdict from the posting alone, but the settled verdict can
 * move once verification blends in — a posting can read `caution` and settle at
 * `note`. Showing the intermediate value as though it were the verdict is the
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

export function verdictFor(verdict: Verdict | null | undefined): VerdictCopy {
  if (!verdict) return NO_VERDICT;
  return VERDICT_TABLE[verdict];
}

/**
 * The two instruction lines in the action block.
 *
 * Authored per verdict family, and keyed to the family rather than the exact
 * verdict on purpose: `stop` needs the reader to stop; `caution` needs the
 * reader to settle the fee; `note` needs the reader to check the employer's site;
 * `clear` needs the reader to proceed.
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

const ACTION_TABLE: Record<Verdict | 'unknown', ActionLines> = {
  stop: {
    lead: 'Do not send money or documents.',
    rest: 'Even if the request says the fee is refundable, do not send money or identity documents. Stop the application and do not reply to the recruiter until you have checked the company yourself.',
    secondLead: 'Check the company yourself',
    secondRest: 'through an official channel before you apply for anything.',
    bullet: 'bg-verdict-critical',
  },
  caution: {
    lead: 'Ask who receives the fee and why.',
    rest: 'A fee to a personal account or an agency before a contract is the pattern the rules prohibit.',
    secondLead: 'Confirm the employer\'s identity',
    secondRest: 'through an official channel before you send anything.',
    bullet: 'bg-verdict-caution-container',
  },
  note: {
    lead: 'Check the employer\'s official site for the stated fee.',
    rest: 'The employer is confirmed and the fee is stated on their site.',
    secondLead: 'Proceed with the application',
    secondRest: 'through the company\'s own domain.',
    bullet: 'bg-verdict-verified',
  },
  clear: {
    lead: 'Proceed with the application.',
    rest: 'The posting asks for nothing the rules prohibit.',
    secondLead: 'Keep the conversation on the company\'s own domain.',
    secondRest: 'If they switch to a personal email or a messaging app, that is worth asking about before you send anything.',
    bullet: 'bg-verdict-verified',
  },
  unknown: {
    lead: 'No verdict on this one.',
    rest: 'The employer was not looked up, so nothing was assessed.',
    secondLead: 'Check the company name',
    secondRest: 'and scan again when you have one.',
    bullet: 'bg-verdict-unknown',
  },
};

/**
 * The bullet colour when there is no verdict to follow.
 *
 * Neutral, deliberately. `ActionBlock` is asked for a bullet even when the
 * verdict is "no verdict on this one", and an amber bullet there would attach an
 * alarm to a state that is an absent measurement rather than a finding — which
 * is the same reason `verdict-unknown` is grey rather than caution.
 */
export const NO_VERDICT_BULLET = 'bg-verdict-unknown';

export function actionsFor(verdict: Verdict | null | undefined): ActionLines {
  if (!verdict) return ACTION_TABLE.unknown;
  return ACTION_TABLE[verdict];
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
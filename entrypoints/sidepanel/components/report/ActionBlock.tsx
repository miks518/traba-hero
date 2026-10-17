import React from 'react';
import { Icon } from '../common';
import { actionsFor, shareChipsFor, NO_VERDICT_BULLET } from './verdictCopy';
import type { ScanRiskLevel } from '../../types';

export interface ActionBlockProps {
  level: ScanRiskLevel | null;
  /** Anomaly codes, once the backend emits them. See `shareChipsFor`. */
  codes?: string[];
}

/**
 * What to do now — the instructions, and the gate on what not to hand over.
 *
 * **Authored, per verdict family, and never model-written.** This block is a set
 * of instructions to the reader about their own money and their identity
 * documents. A model writing "send ₱500 to confirm" is a failure mode with no
 * acceptable frequency, so the strings live in `verdictCopy.ts` and are looked up.
 *
 * **The mark is a bullet, and it is not operable.** It was a 16px square outline,
 * which is the universal checkbox affordance, and it was not a checkbox: nothing
 * here records that the reader did the thing. There is no persistence layer in
 * this product at all (Task 2.2, zero-retention), so an operable box would
 * silently discard the only signal that the instructions were followed. It read
 * as an input the reader had failed to fill in, which is the opposite of what the
 * block is for.
 *
 * The colour follows the verdict's tone so the bullets, the banner above them and
 * the anomaly chips below all agree about how serious this is. It used to be a
 * hardcoded critical red, so a `low` result showed two red checkboxes beside
 * advice to go ahead and apply — the one place on the panel where the chrome
 * contradicted the content.
 */
export function ActionBlock({ level, codes }: ActionBlockProps) {
  const actions = actionsFor(level);
  const chips = shareChipsFor(codes);

  // No level to follow, so the bullet is the neutral grey rather than a tone.
  // An amber bullet beside "No verdict on this one" would attach an alarm to a
  // state that is an absent measurement.
  const bullet = level ? actions.bullet : NO_VERDICT_BULLET;

  return (
    <section className="flex flex-col gap-2" data-role="action-block">
      <h3 className="text-headline-sm font-headline font-bold px-1">What to do now</h3>

      <div className="tactile-card bg-surface-container-lowest border border-outline-variant/20 p-4 flex flex-col gap-3">
        <div className="flex items-start gap-3">
          <span aria-hidden className={`mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ${bullet}`} />
          <p className="text-body-sm leading-relaxed text-on-surface min-w-0">
            <strong className="font-bold">{actions.lead}</strong> {actions.rest}
          </p>
        </div>

        <div className="flex items-start gap-3">
          <span aria-hidden className={`mt-1.5 w-2.5 h-2.5 rounded-full shrink-0 ${bullet}`} />
          <p className="text-body-sm leading-relaxed text-on-surface min-w-0">
            <strong className="font-bold">{actions.secondLead}</strong> {actions.secondRest}
          </p>
        </div>

        {/*
          The "Do not share" row renders only when there is something specific to
          withhold. It is absent for now and that absence is deliberate — see
          `shareChipsFor`. The generic version of this row was rejected on the
          grounds that advice which does not refer to the thing being assessed is
          the same failure as the "Good habits" list it replaced.
        */}
        {chips.length > 0 && (
          <>
            <hr className="border-outline-variant/20" />
            <div className="flex flex-col gap-2">
              <span className="text-body-sm font-semibold text-on-surface">Do not share</span>
              <div className="flex flex-wrap gap-2">
                {chips.map((chip) => (
                  <span
                    key={chip}
                    className="chip-critical px-2.5 py-1 text-body-sm font-medium rounded-full border border-outline-variant/20"
                  >
                    {chip}
                  </span>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/*
        The report control is deliberately not rendered.

        The design draws a "Report this post" button, and the reason it cannot
        ship is the same reason the subject line cannot say where the posting came
        from: the extension screenshots a region of a page and has no idea whether
        it is a job board, a Facebook group, or a forwarded message. There is
        therefore nothing to report it *to*. A link to nowhere reads as a working
        feature and silently discards the one signal that would tell us the verdict
        taxonomy is wrong — the same failure as a score the system never measured.
        See `docs/decisions/report-panel-redesign.md`, "Two slots have no possible
        source".
      */}
    </section>
  );
}

export default ActionBlock;

import React from 'react';
import { Icon, FormattedText } from '../common';

/**
 * The verdict: our reading of the posting, written for someone deciding whether
 * to reply. It carries a judgement and one action, and it is the one passage in
 * the results stack the reader is meant to act on.
 *
 * It is the raised card of the two: a title band across the top and the
 * `tactile-card` depth, on the largest radius in the shape scale. `JobSummary`
 * below is the same width with a flat face and its label sitting inline in the
 * body. Band, depth and radius are shape cues, so the difference registers
 * before any of the text is read — which is the point, since the two fields sit
 * next to each other and answer different questions.
 *
 * The band is tonal, not chromatic. This field ranges from "the posting states
 * nothing alarming" to "it asks the applicant for money before work", so any
 * colour here would either pre-judge the text or restate the RiskGauge above,
 * which already carries the severity. It is also not `secondary`: that is green
 * in both themes, and green already reads as a positive verification result.
 *
 * The title stays a 12px label and the body 13px, matching every other card in
 * the panel. Deliberately not a larger headline — at 380px wide a second type
 * scale on top of the band costs more legibility than the emphasis buys.
 */
export function PostingAnalysis({ text }: { text?: string }) {
  if (!text) return null;

  return (
    <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest tactile-card">
      <header className="flex items-center gap-2 rounded-t-xl bg-surface-container-high border-b border-outline-variant/20 px-4 py-2.5">
        <Icon name="description" className="text-base text-on-surface" />
        <h3 className="text-label-md text-on-surface">Posting Analysis</h3>
      </header>
      <div className="px-4 py-3">
        <FormattedText
          text={text}
          bodyClassName="text-body-sm text-on-surface"
          bulletClassName="text-outline-variant mt-0.5 shrink-0"
        />
      </div>
    </section>
  );
}

export default PostingAnalysis;

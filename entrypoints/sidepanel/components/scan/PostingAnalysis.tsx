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
 * The green is a *role* colour, not a risk colour. It appears identically
 * whether this verdict is "states nothing alarming" or "asks for money before
 * work" — it marks the field as the one carrying our judgement, and nothing
 * more. The severity lives in the RiskGauge above. Do not let it drift toward
 * `error` when a post reads badly, and do not read it as a positive signal:
 * green means "found / verified" in the verification section below, and if that
 * collision turns out to matter, `tertiary` is the neutral swap.
 *
 * The title stays a 12px label and the body 13px, matching every other card in
 * the panel. Deliberately not a larger headline — at 380px wide a second type
 * scale on top of the band costs more legibility than the emphasis buys.
 *
 * Body text is `on-surface` rather than the matched `on-secondary-container`,
 * which only reaches 4.6:1 on the light face. The fill comes from the container
 * token; the contrast comes from the text token, and they do not have to pair.
 */
export function PostingAnalysis({ text }: { text?: string }) {
  if (!text) return null;

  return (
    <section className="rounded-xl border border-secondary tactile-card">
      <header className="flex items-center gap-2 rounded-t-xl bg-secondary px-4 py-2">
        <Icon name="description" className="text-base text-on-secondary" />
        <h3 className="text-label-md text-on-secondary">Posting Analysis</h3>
      </header>
      <div className="px-4 py-3">
        <FormattedText
          text={text}
          bodyClassName="text-body-sm text-on-surface"
          bulletClassName="text-on-surface mt-0.5 shrink-0"
        />
      </div>
    </section>
  );
}

export default PostingAnalysis;

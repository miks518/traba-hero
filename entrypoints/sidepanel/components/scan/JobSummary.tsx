import React from 'react';
import { Icon, FormattedText } from '../common';

/**
 * The record: what the posting itself said. The prompt contract for this field
 * is "no risk language, no red-flag reasoning, no invented details", so it is
 * reproduced matter rather than assessment — the material a reader checks the
 * verdict above it against.
 *
 * It is the flat card of the two. No title band, no `tactile-card` depth, and
 * the smaller `rounded-lg` radius, with the label sitting inline in the body on
 * a recessed `surface-container-low` face. Against the raised, banded card above,
 * that reads at a glance as a filed document rather than a highlighted
 * conclusion, which is exactly the relationship between the two: the summary is
 * what the analysis reasons over.
 *
 * Treated as reference material, not demoted. Same 13px body and 12px label as
 * the verdict card, one step of text tone lighter so the two separate without
 * either becoming harder to read.
 */
export function JobSummary({ text }: { text?: string }) {
  if (!text) return null;

  return (
    <section className="rounded-lg border border-outline-variant/20 bg-surface-container-low p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Icon name="work" className="text-base text-on-surface-variant" />
        <h3 className="text-label-md text-on-surface-variant">Job Summary</h3>
      </div>
      <FormattedText
        text={text}
        bodyClassName="text-body-sm text-on-surface-variant"
        bulletClassName="text-outline-variant mt-0.5 shrink-0"
      />
    </section>
  );
}

export default JobSummary;

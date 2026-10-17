import React from 'react';
import { Icon } from '../common';
import type { Anomaly } from '../../types';

export interface AnomalyCardsProps {
  anomalies: Anomaly[];
}

const SEVERITY_CHIP: Record<string, { cls: string; label: string }> = {
  high: { cls: 'chip-critical', label: 'Critical' },
  mid: { cls: 'chip-caution', label: 'Serious' },
  low: { cls: 'chip-verified', label: 'Minor' },
};

/**
 * The findings, one card each.
 *
 * Three things this component does *not* do, each load-bearing.
 *
 * **No count of "checks".** The design's "3 found" line is here and it counts
 * anomalies, and nothing else is counted alongside it. A non-finding inside a
 * count of findings makes the count a lie, and the count is what the false-
 * negative rate gets measured against.
 *
 * **No code pill yet.** The design puts a monospaced rule code
 * (`ASKS_PAYMENT`, `EMAIL_MISMATCH`) at the top right of every card. That field
 * does not exist on the wire — `docs/superpowers/specs/2026-10-17-anomaly-code-set.md`
 * is a draft with nothing implemented — so the slot is absent rather than filled
 * with the model's free-text `flag`. A code pill that is really a sentence in a
 * monospace font would be the one place on the panel where a reader looks up a
 * taxonomy and finds prose instead.
 *
 * **No quote block yet.** This is the biggest missing piece in the whole panel
 * and the design's credibility rests on it: the credibility argument is quoting
 * the posting and highlighting the span that decided the finding. The scan
 * returns `flag`, `reasoning` and `severity` — three free-text fields, none of
 * which is required to be present in the posting, and one of which the prompt
 * explicitly permits to be "closely paraphrased". A paraphrase cannot be
 * rendered as a quotation. When `quote` lands it must be *bound*: a span that
 * cannot be located in the posting is not evidence, and the card degrades to the
 * explanation alone rather than showing a reconstruction.
 *
 * The phrase in the card body is `anomaly.title`, which is the model's own prose
 * today. Under the code set it becomes a lookup, for the same reason the verdict
 * headline is one: it is read by someone deciding about money, and it must not
 * vary between two runs of the same scan.
 */
export function AnomalyCards({ anomalies }: AnomalyCardsProps) {
  if (anomalies.length === 0) return null;

  return (
    <section className="flex flex-col gap-3" data-role="anomaly-cards">
      <div className="flex items-center justify-between gap-2 px-1">
        <h3 className="text-headline-sm font-headline font-bold text-on-surface">Anomalies detected</h3>
        {/* min-w-0 on the heading side so one long word cannot push the count out
            of a narrow panel. The count is the figure Phase 6.3 measures, so it
            has to survive the layout rather than being the first thing dropped. */}
        <span className="text-body-sm font-semibold text-on-surface-variant shrink-0">
          {anomalies.length} found
        </span>
      </div>

      {anomalies.map((anomaly) => {
        const chip = SEVERITY_CHIP[anomaly.severity ?? 'mid'] ?? SEVERITY_CHIP.mid;
        return (
          <article
            key={anomaly.id}
            className="tactile-card bg-surface-container-lowest border border-outline-variant/20 rounded-lg p-4 flex flex-col gap-2.5"
          >
            <div className="flex items-center justify-between gap-2">
              <span
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold ${chip.cls}`}
              >
                <Icon name="warning" className="text-[11px] leading-none" />
                {chip.label}
              </span>
              {/* Reserved for the rule code. Absent rather than empty — see the
                  note above. */}
            </div>

            <div className="flex flex-col gap-1 min-w-0">
              <h4 className="text-headline-xs font-headline font-bold text-on-surface break-words">
                {anomaly.title}
              </h4>
              <p className="text-body-sm text-on-surface-variant leading-normal break-words">
                {anomaly.description}
              </p>
            </div>
          </article>
        );
      })}
    </section>
  );
}

export default AnomalyCards;

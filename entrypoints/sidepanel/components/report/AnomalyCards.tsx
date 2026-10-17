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
 * **The rule code, when there is one.** `ASKS_PAYMENT`-style IDs come from
 * `ANOMALY_CODES` and are model-emitted from a closed set, so the panel can be
 * compared across runs and a gold set can be labelled with them. Absent for a
 * scan predating the field, which is a different state from `OTHER` — the escape
 * valve is shown, because its frequency is the drift signal.
 *
 * **The posting's own words, when they survived screening.** The credibility of
 * this panel rests on quoting the posting rather than summarising it, and the
 * backend drops a span it cannot vouch for (`quote_is_clean`, and on the text
 * path a span it cannot locate). An absent quote degrades the card to its
 * explanation; a fabricated one is never rendered. The design also bolds the
 * deciding phrase inside the quotation, and no field says which phrase that was
 * — so the quote reads plainly rather than carrying a highlight that would be
 * decoration pretending to be analysis.
 *
 * The phrase in the card body is `anomaly.title`, which is still the model's own
 * prose. Under a fuller code set it becomes a lookup, for the same reason the
 * verdict headline is one: it is read by someone deciding about money, and it
 * must not vary between two runs of the same scan.
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

              {/*
                The rule code, when the scan carried one.

                Absent for a scan taken before the field existed, and that is a
                different state from `OTHER` — `OTHER` means the model answered
                the escape valve deliberately, and it is shown, because the
                frequency of escape-valve answers is the drift signal the
                taxonomy exists to produce. An absent code is a scan from before
                the taxonomy and gets no pill at all.

                Monospaced and recessed because it is metadata a reader looks up,
                not prose they read.
              */}
              {anomaly.code && (
                <span className="code-pill px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase shrink-0">
                  {anomaly.code}
                </span>
              )}
            </div>

            <div className="flex flex-col gap-1 min-w-0">
              <h4 className="text-headline-xs font-headline font-bold text-on-surface break-words">
                {anomaly.title}
              </h4>
              <p className="text-body-sm text-on-surface-variant leading-normal break-words">
                {anomaly.description}
              </p>
            </div>

            {/*
              The posting's own words, in a recessed well.

              This is the most load-bearing thing on the card: a finding a reader
              cannot check against the posting is a claim, and a claim about a
              named employer is the exact exposure this product's prompt rules
              exist to prevent. Showing the span that decided it is what makes the
              finding checkable.

              **It renders only when the backend passed screening.** `quote_is_clean`
              drops a span carrying a word the posting could not have written about
              itself, and the text path additionally drops one that cannot be
              located in the submitted text. An absent quote therefore means "we
              could not show you the posting's words", and the card falls back to
              its explanation — which is the honest degradation. The reverse is not
              available: a fabricated quote is never rendered.

              Note this is weaker than the citation binding on the verification
              side. The extension scans an *image*, so a span cannot be located in
              the posting and only its wording can be checked.
            */}
            {anomaly.quote && (
              <div className="quote-well p-3 flex flex-col gap-1">
                <span className="text-[10px] font-bold text-on-surface-variant tracking-wider uppercase">
                  From the post
                </span>
                {/*
                  Rendered as one span, not highlighted.

                  The design bolds the deciding phrase inside the quotation, and
                  there is no field for which phrase that was. The wire carries
                  the span itself and nothing about its parts. Highlighting the
                  whole quote would be decoration pretending to be an analysis;
                  highlighting a guess at the middle of it would be worse. So the
                  quote reads plainly, and a future field naming the deciding
                  offset is what unblocks the highlight.

                  `.quote-badge` stays commented out in `tailwind.css` for the same
                  reason - styling for a slot that cannot render is a trap for the
                  next reader.
                */}
                <p className="text-body-sm text-on-surface leading-relaxed break-words">
                  {anomaly.quote}
                </p>
              </div>
            )}
          </article>
        );
      })}
    </section>
  );
}

export default AnomalyCards;

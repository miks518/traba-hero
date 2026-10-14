import React from 'react';
import { Icon } from '../common/Icon';
import { AnomalyCard } from './AnomalyCard';
import type { Anomaly } from '../../types';

export interface AnomaliesListProps {
  /**
   * The heading element, so a caller can scroll to where the anomalies actually
   * are rather than to the top of whatever container this list happens to sit
   * in. The provenance button under the gauge uses it.
   */
  headingRef?: React.Ref<HTMLDivElement>;
  anomalies: Anomaly[];
  critical: boolean;
}

/**
 * Renders the anomalies reported in a posting.
 *
 * The heading is neutral on purpose. "Red Flags" was a conclusion delivered
 * before the reader reached any evidence, so a low-severity note about
 * formatting was announced with the same force as a request for an advance fee.
 * "Anomaly" asserts only that the posting differs from the ordinary case;
 * whether that difference matters is the reader's to judge.
 *
 * What it does NOT do is vary the heading by severity — see
 * docs/superpowers/specs/2026-10-07-framing-origin-false-positives-design.md
 * §1. A low finding still renders under the same heading as a high one. That
 * is an open question, not an oversight: the noun is constant and only the
 * per-card border and chip differentiate, so the container still over-announces
 * weak findings. Fixing it is a judgement call about visual weight.
 */
export function AnomaliesList({ anomalies, critical, headingRef }: AnomaliesListProps) {
  if (anomalies.length === 0) return null;
  return (
    <section className="flex flex-col gap-stack-sm">
      <div ref={headingRef} data-role="anomalies-heading" className="flex items-center justify-between gap-2 mb-1">
        {/* min-w-0 lets this half compress. Without it the flex default of
            min-width:auto floors the row at the heading's own width, and the
            badge is pushed out of a narrow panel. */}
        <div className="flex items-center gap-2 min-w-0">
          <Icon name="flag" className="text-error text-sm shrink-0" />
          <h3 className="font-headline-md text-lg text-error font-bold truncate">
            Anomalies ({anomalies.length})
          </h3>
        </div>
        {critical && (
          <span className="bg-error text-on-error px-2 py-0.5 rounded-full font-label-sm text-[10px] font-bold shrink-0">
            HIGH SEVERITY
          </span>
        )}
      </div>
      {anomalies.map((anomaly) => (
        <AnomalyCard key={anomaly.id} anomaly={anomaly} />
      ))}
    </section>
  );
}

export default AnomaliesList;

import React from 'react';
import { Icon } from '../common/Icon';
import type { OfferAnalysis } from '../../types';

export interface OfferAnalysisCardProps {
  analysis?: OfferAnalysis;
  loading?: boolean;
}

/**
 * The verdict for an offer that names no employer, so external verification
 * could not run. Everything here comes from the offer's own content — no
 * statement about a company it does not name.
 */
export function OfferAnalysisCard({ analysis, loading }: OfferAnalysisCardProps) {
  if (loading) {
    return (
      <section className="bg-surface-container-low border border-outline-variant/20 rounded-xl p-4 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-secondary animate-ping" />
          <h3 className="text-label-md font-bold text-on-surface">Assessing the offer…</h3>
        </div>
        <p className="text-body-sm text-on-surface-variant">Reading what the offer asks for.</p>
      </section>
    );
  }

  if (!analysis) return null;

  const rows = [
    { label: 'What it asks', value: analysis.whatItAsks, icon: 'payments' as const },
    { label: 'What it offers', value: analysis.whatItOffers, icon: 'handshake' as const },
    { label: 'What to check', value: analysis.whatToCheck, icon: 'search' as const },
  ];

  return (
    <section className="bg-surface-container-low border border-outline-variant/20 rounded-xl p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Icon name="search" className="text-secondary" />
        <h3 className="text-label-md font-bold text-on-surface">Offer Analysis</h3>
        {analysis.kind && analysis.kind !== 'NOT_OFFER' && (
          <span className="ml-auto inline-flex items-center px-2 py-0.5 rounded-full bg-surface-container-high text-label-sm text-on-surface-variant border border-outline-variant/20">
            {analysis.kind}
          </span>
        )}
      </div>

      <p className="text-body-sm text-on-surface leading-relaxed">{analysis.verdict}</p>

      <div className="flex flex-col gap-2">
        {rows.filter((r) => r.value && r.value.toLowerCase() !== 'not stated').map((row) => (
          <div key={row.label} className="flex items-start gap-2">
            <Icon name={row.icon} className="text-label-md text-on-surface-variant shrink-0 mt-0.5" />
            <div className="flex flex-col min-w-0">
              <span className="text-label-sm text-on-surface-variant uppercase tracking-wider">{row.label}</span>
              <span className="text-body-sm text-on-surface/90 leading-snug">{row.value}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default OfferAnalysisCard;

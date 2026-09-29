import React from 'react';
import { Icon } from '../common';
import type { VerificationItem, IconName } from '../../types';

/**
 * `yellow` is a neutral, not a positive: it means the search returned nothing
 * about this category. It is amber rather than the accent green, for two
 * reasons that pointed opposite ways.
 *
 * Not the accent: in the dark theme `secondary` is #4ade80, identical to the
 * green a positive finding uses, so the most common outcome looked identical to
 * a good result.
 *
 * Not grey, though — it was `bg-outline/10` until this changed, a 10% grey wash
 * on a surface that is already grey. That is not a weak colour but an absent
 * one, and `yellow` is the most common status the panel produces: a small
 * employer with a thin online footprint returns it on most of the three
 * categories. The most frequent card rendered as if it carried no status.
 *
 * Amber does collide with the `moderate` risk level, which is why the gauge's
 * *unverified* ring stays grey — see RiskGauge.tsx. That is a deliberate scope
 * limit, not an oversight. The two states are genuinely different claims about
 * the employer: "nothing was measured" against "we looked and could not
 * confirm". Here the three statuses are a self-contained traffic light, so the
 * colour reads as a status rather than as a score.
 */
const STATUS_CONFIG: Record<VerificationItem['status'], { dot: string; bg: string; icon: IconName; label: string }> = {
  green: {
    dot: 'bg-green-500',
    bg: 'bg-green-500/10',
    icon: 'gpp_good',
    label: 'Found in results',
  },
  yellow: {
    dot: 'bg-amber-500',
    bg: 'bg-amber-500/10',
    icon: 'gpp_maybe',
    label: 'Not confirmed',
  },
  red: {
    dot: 'bg-error',
    bg: 'bg-error-container/10',
    icon: 'gpp_bad',
    label: 'Reported in results',
  },
};

interface VerificationCardProps {
  item: VerificationItem;
}

export function VerificationCard({ item }: VerificationCardProps) {
  const config = STATUS_CONFIG[item.status] || STATUS_CONFIG.yellow;

  return (
    <div className={`flex flex-col gap-1 p-2.5 rounded-lg ${config.bg}`}>
      <div className="flex items-center gap-2">
        <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${config.dot}`} />
        <span className="text-body-sm font-bold text-on-surface min-w-0">{item.label}</span>
        <span className={`text-label-sm font-bold px-1.5 py-0.5 rounded ml-auto shrink-0 ${
          item.status === 'green' ? 'bg-green-500/20 text-green-400' :
          item.status === 'yellow' ? 'bg-amber-500/20 text-amber-400' :
          'bg-error/20 text-error'
        }`}>
          {config.label}
        </span>
      </div>
      <p className="text-body-sm text-on-surface-variant leading-relaxed pl-5">
        {item.explanation}
      </p>
      {item.source_url && (
        <a
          href={item.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-label-sm text-secondary hover:underline break-all pl-5 flex items-center gap-1"
          title={item.source_title || item.source_url}
        >
          <Icon name="open_in_new" className="text-[10px] shrink-0" />
          {item.source_title || item.source_url}
        </a>
      )}
    </div>
  );
}

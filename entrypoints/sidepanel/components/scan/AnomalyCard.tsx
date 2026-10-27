import React from 'react';
import { Icon } from '../common/Icon';
import { findingTier } from '../../lib/findingTiers';
import type { Anomaly } from '../../types';

export interface AnomalyCardProps {
  anomaly: Anomaly;
}

const TIER_STYLES: Record<number, { bg: string; text: string; border: string }> = {
  // Theme-resolvable tokens, not the raw palette. The tier-2 and tier-1 rows
  // were authored for the dark theme (`text-amber-400` on an amber wash) and in
  // light mode put pale ink on a pale fill. The fills are the chip `--bg`
  // tokens — the same pale fills the report's status cards sit on — and the
  // translucent borders are declared in `assets/tailwind.css`, because a custom
  // token with an opacity variant silently generates no class at all
  // (`bg-error/20` below used to be exactly that: an icon circle with no fill).
  //
  // Full opacity, not a translucent wash, for the tier-3 border. A 1px line at
  // 40% over this surface was effectively invisible — the reader reported the
  // border as white, and it was falling back to Tailwind's preflight grey
  // because the translucent class had never been generated at all. The
  // money-demand outline is the alarm, so it is the one place in the panel that
  // gets full-strength colour.
  //
  // The tiers come from the finding's taxonomy code (`lib/findingTiers.ts`),
  // not from a model judgement: the scan emits no severity. Tier 3 is a demand
  // for money or account access, tier 2 an identity or labour exposure, tier 1
  // the ordinary packet — and a finding with no code styles as tier 2, the old
  // default, because an unclassified finding is not known to be minor.
  3: { bg: 'bg-chip-critical-bg', text: 'text-error', border: 'border-error' },
  2: { bg: 'bg-chip-caution-bg', text: 'text-assessment-caution', border: 'border-assessment-caution/40' },
  1: { bg: 'bg-chip-verified-bg', text: 'text-assessment-verified', border: 'border-assessment-verified/30' },
};

export function AnomalyCard({ anomaly }: AnomalyCardProps) {
  const style = TIER_STYLES[findingTier(anomaly.code)] ?? TIER_STYLES[2];
  return (
    // The container carries the tier border, not just the icon. It used to
    // hold `border-outline-variant/10` whatever the finding, so a fee demand
    // was signalled only by a 32px dot — the smallest thing on the card. A
    // reader scanning for which of these asks for money had nothing to scan.
    // `tactile-card` is the original 3D treatment and is kept: the flat
    // containers elsewhere on the panel are the departure, not this one.
    <div className={`bg-surface-container-low border-2 rounded-lg p-3 flex gap-3 tactile-card hover:bg-surface-container transition-colors ${style.border}`}>
      <div className={`${style.bg} ${style.text} h-8 w-8 rounded-full flex items-center justify-center shrink-0 border ${style.border}`}>
        <Icon name={anomaly.icon} className="text-sm" />
      </div>
      {/* min-w-0 is what lets this column compress. A flex item defaults to
          min-width:auto, which refuses to shrink below the min-content width of
          its contents — so one long anomaly title, or one long unbroken word,
          sets a floor the card cannot go below and the panel scrolls sideways
          instead of wrapping. */}
      <div className="flex flex-col gap-0.5 min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <h4 className="font-label-md text-on-surface font-bold min-w-0">{anomaly.title}</h4>
        </div>
        <p className="font-label-sm text-on-surface-variant leading-tight break-words">{anomaly.description}</p>
      </div>
    </div>
  );
}

export default AnomalyCard;

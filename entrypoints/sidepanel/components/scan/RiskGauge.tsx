import React from 'react';
import type { ScanRiskLevel } from '../../types';

export interface RiskGaugeProps {
  score: number | null;
  maxScore?: number;
  riskLevel?: ScanRiskLevel | null;
  riskLabel?: string;
  /** Why there is no score yet. Shown instead of the default note. */
  pendingNote?: string;
  /**
   * The posting named no employer, so the employer itself was never checked.
   * A posting-stage score of 0 would otherwise render as "0 / Low Risk", which
   * claims the post was cleared rather than unchecked. Shown in the same shape
   * as an unscored gauge so no number is displayed that we did not measure.
   */
  unverified?: boolean;
}

function scoreColor(score: number): string {
  const hue = Math.max(0, 120 - (score / 100) * 120);
  return `hsl(${hue}, 78%, 44%)`;
}

// The unverified ring uses the neutral outline grey rather than a level colour:
// nothing was measured, and amber already means the 'moderate' level.

function levelColor(level: ScanRiskLevel | null): string {
  switch (level) {
    case 'critical': return 'hsl(0, 78%, 44%)';
    case 'high': return 'hsl(25, 78%, 44%)';
    case 'moderate': return 'hsl(45, 78%, 44%)';
    default: return scoreColor(15);
  }
}

export function RiskGauge({
  score,
  maxScore = 100,
  riskLevel = null,
  riskLabel,
  pendingNote,
  unverified = false,
}: RiskGaugeProps) {
  const radius = 52;
  const strokeWidth = 14;
  const circumference = 2 * Math.PI * radius;
  const isScored = typeof score === 'number';

  if (unverified) {
    // overflow-hidden on the card keeps the ring's glow inside it. Without it
    // the drop-shadow bleeds past the rounded edge and the card's border draws
    // a hard line across the glow.
    return (
      <section className="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-5 mb-stack-md tactile-card overflow-hidden">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="relative w-[132px] h-[132px] flex items-center justify-center shrink-0">
            <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 128 128">
              <circle
                cx="64" cy="64"
                fill="transparent"
                r={radius}
                stroke="currentColor"
                strokeWidth={strokeWidth}
                className="text-surface-container-high"
              />
              {/* Grey, not amber: nothing was measured, and amber already means
                  the 'moderate' level. Full circle, gently pulsing. */}
              <circle
                cx="64" cy="64"
                fill="transparent"
                r={radius}
                stroke="currentColor"
                strokeWidth={strokeWidth}
                strokeDasharray={circumference}
                strokeLinecap="round"
                className="ring-pulse text-outline"
                style={{ ['--ring-glow-color' as string]: 'var(--color-outline)' }}
              />
            </svg>
            <div className="flex flex-col items-center">
              <span
                className="text-2xl font-extrabold tracking-tight leading-none text-on-surface-variant"
              >
                &mdash;
              </span>
              <span className="font-label-md text-label-md text-on-surface-variant mt-0.5">RISK</span>
            </div>
          </div>
          <div className="flex flex-col gap-1.5 min-w-0">
            <span className="font-headline-xs font-bold inline-flex items-center justify-center gap-1.5 text-on-surface">
              <span className="w-2 h-2 rounded-full shrink-0 bg-outline" />
              Unverified
            </span>
            <span className="text-label-sm text-on-surface-variant text-center max-w-[240px]">
              This post raised no red flags, but it names no employer either, so the company
              could not be checked. Applying blind is its own risk.
            </span>
          </div>
        </div>
      </section>
    );
  }

  if (!isScored) {
    return (
      <section className="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-5 mb-stack-md tactile-card">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="relative w-[132px] h-[132px] flex items-center justify-center shrink-0">
            <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 128 128">
              <circle
                cx="64" cy="64"
                fill="transparent"
                r={radius}
                stroke="currentColor"
                strokeWidth={strokeWidth}
                className="text-surface-container-high"
              />
            </svg>
            <div className="flex flex-col items-center">
              <span className="text-2xl font-extrabold tracking-tight leading-none text-on-surface-variant">—</span>
              <span className="font-label-md text-label-md text-on-surface-variant mt-0.5">RISK</span>
            </div>
          </div>
          <div className="flex flex-col gap-1.5 min-w-0">
            <span className="font-headline-xs font-bold inline-flex items-center justify-center gap-1.5 text-on-surface-variant">
              <span className="w-2 h-2 rounded-full shrink-0 bg-surface-container-highest" />
              Not scored
            </span>
            <span className="text-label-sm text-on-surface-variant text-center">
              {pendingNote ?? 'A risk score is calculated after external verification.'}
            </span>
          </div>
        </div>
      </section>
    );
  }

  const normalized = Math.min(score / maxScore, 1);
  const pct = Math.round(normalized * 100);
  const color = levelColor(riskLevel);
  const dashOffset = circumference * (1 - normalized);

  // overflow-hidden for the same reason as the unverified card: the glow must
  // not bleed past the border and leave a hard line through it.
  return (
    <section className="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-5 mb-stack-md tactile-card overflow-hidden">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="relative w-[132px] h-[132px] flex items-center justify-center shrink-0">
          <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 128 128">
            <circle
              cx="64" cy="64"
              fill="transparent"
              r={radius}
              stroke="currentColor"
              strokeWidth={strokeWidth}
              className="text-surface-container-high"
            />
            <circle
              cx="64" cy="64"
              fill="transparent"
              r={radius}
              stroke={color}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              className="ring-pulse transition-all duration-1000 ease-out"
              style={{ ['--ring-glow-color' as string]: color }}
            />
          </svg>
          <div className="flex flex-col items-center">
            <span className="text-3xl font-extrabold tracking-tight leading-none" style={{ color }}>{pct}</span>
            <span className="font-label-md text-label-md text-on-surface-variant mt-0.5">RISK</span>
          </div>
        </div>
        <div className="flex flex-col gap-1.5 min-w-0">
          <span
            className="font-headline-xs font-bold inline-flex items-center justify-center gap-1.5"
            style={{ color }}
          >
            <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
            {riskLabel ?? 'Low Risk'}
          </span>
        </div>
      </div>
    </section>
  );
}

export default RiskGauge;

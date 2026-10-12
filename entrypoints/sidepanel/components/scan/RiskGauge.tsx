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
  /**
   * How many anomalies the posting stage reported.
   *
   * Only used for the provenance line. The score is not recomputed here â€” it
   * travels from `risk_calculator.py` and this panel never synthesises a
   * number the system did not measure. What this adds is the *reason* the
   * score is what it is, which is what a reader needs in order to act on it.
   */
  anomalyCount?: number;
  /**
   * Scroll the reader to the Evidence Summary, which is where the anomalies
   * this line counts are listed.
   *
   * Passed in rather than looked up here, because the evidence group belongs to
   * `ScamScanView` and it already holds the ref. A component reaching into the
   * document for a node it does not own is how two places end up disagreeing
   * about what the anchor is called.
   *
   * Optional: without it the provenance line renders as the plain sentence it
   * was, because a button that does nothing is worse than no button.
   */
  onShowEvidence?: () => void;
}

function scoreColor(score: number): string {
  const hue = Math.max(0, 120 - (score / 100) * 120);
  // Inside the low band only. At score 15 the hue is 102, which is exactly
  // --color-risk-low, so the helper below returns that token for this case and
  // the inline form is never actually produced.
  return hue < 120 ? 'var(--color-risk-low)' : `hsl(${hue}, 78%, 44%)`;
}

// The unverified ring uses the neutral outline grey rather than a level colour:
// nothing was measured, and amber already means the 'moderate' level.

function levelColor(level: ScanRiskLevel | null): string {
  switch (level) {
    case 'critical': return 'var(--color-risk-critical)';
    case 'high': return 'var(--color-risk-high)';
    case 'moderate': return 'var(--color-risk-moderate)';
    default: return scoreColor(15);
  }
}

/**
 * The tactile variant whose `--tactile-base` is this level's colour.
 *
 * A compound class rather than an inline style so the button keeps the shipped
 * treatment: DESIGN.md builds the gradient, the border, the extrusion and the
 * press from one variable, and a component that sets its own background or
 * shadow has diverged from it. Setting the variable inline would do the same
 * thing more quietly.
 *
 * `low` is the default `--color-secondary`, a slightly deeper green than the
 * ring's. It gets no variant rather than a near-duplicate one: the two greens are
 * close enough that a fourth compound class would exist only to be
 * indistinguishable.
 */
function levelButtonClass(level: ScanRiskLevel | null): string {
  switch (level) {
    case 'critical': return 'tactile-btn-risk-critical';
    case 'high': return 'tactile-btn-risk-high';
    case 'moderate': return 'tactile-btn-risk-moderate';
    default: return '';
  }
}

/** Where the level bands start, as a fraction of the full ring. */
const BAND_STARTS = [30, 50, 75];

/**
 * One sentence saying what produced the score, in the reader's words.
 *
 * This existed nowhere before. A bare number with no stated basis is why a
 * first-time tester read "12" as meaningless: nothing connected it to
 * anything about their own posting. The count is not a second score — it is
 * the observable fact the score was built from.
 *
 * It is a button, because it names a number the reader has not been shown yet.
 * Saying "3 things differ from normal" and leaving the reader to scroll to find
 * them is a sentence pointing at something off-screen; making it operable closes
 * the loop without a second instruction.
 *
 * Only when the count is above zero. At zero it reads "Nothing in this post
 * stands out", there is nothing below to go to, and a control that scrolls
 * nowhere is worse than the plain sentence it replaced.
 */
function provenanceLine(anomalyCount: number | undefined): string | null {
  if (anomalyCount === undefined) return null;
  if (anomalyCount === 0) return "Nothing in this post stands out.";
  return anomalyCount === 1
    ? "1 thing in this post differs from normal."
    : `${anomalyCount} things in this post differ from normal.`;
}

export function RiskGauge({
  score,
  maxScore = 100,
  riskLevel = null,
  riskLabel,
  pendingNote,
  unverified = false,
  anomalyCount,
  onShowEvidence,
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
              This post raised no anomalies, but it names no employer either, so the company
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
              <span className="text-2xl font-extrabold tracking-tight leading-none text-on-surface-variant">â€”</span>
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
  const color = levelColor(riskLevel);
  const dashOffset = circumference * (1 - normalized);
  const provenance = provenanceLine(anomalyCount);

  // The card does not clip here, so the ring gives its own glow room to render
  // in: p-2 inside the card's p-5, against a glow that peaks at 11px. The
  // unverified card above clips instead; either way the border stays clear.
  return (
    <section className="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-5 mb-stack-md tactile-card">
      <div className="flex flex-col items-center gap-4 text-center">
        {/* Added p-2 to give the glowing shadow space around the 132px circle */}
        <div className="relative w-[132px] h-[132px] p-2 flex items-center justify-center shrink-0">
          {/* Added overflow-visible so the SVG filter/glow isn't clipped */}
          <svg className="absolute inset-0 w-full h-full -rotate-90 overflow-visible" viewBox="0 0 128 128">
            <circle
              cx="64" cy="64"
              fill="transparent"
              r={radius}
              stroke="currentColor"
              strokeWidth={strokeWidth}
              className="text-surface-container-high"
            />
            {/* Band markers. A ring with no marks is a progress bar, so the
                number in the middle read as a dial position â€” which is why a
                tester asked what "12" was out of. Three hairlines at the band
                boundaries make it an instrument with a scale, and they carry
                the same thresholds `_level_for` uses rather than inventing
                new ones. Short and low-contrast: they are gradations, not
                labels, and must not compete with the number. */}
            {BAND_STARTS.map((band) => {
              const angle = ((band / 100) * 2 * Math.PI) - Math.PI / 2;
              const inner = radius - strokeWidth / 2 - 1;
              const outer = radius + strokeWidth / 2 + 1;
              return (
                <line
                  key={band}
                  data-band={band}
                  x1={64 + inner * Math.cos(angle)}
                  y1={64 + inner * Math.sin(angle)}
                  x2={64 + outer * Math.cos(angle)}
                  y2={64 + outer * Math.sin(angle)}
                  stroke="currentColor"
                  strokeWidth="1"
                  className="text-surface-container-lowest"
                  opacity="0.55"
                />
              );
            })}
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
          {/* The number and the ring show the same quantity, and the unit says
              so. It reads as `/ 100` rather than a percentage sign on purpose:
              the score is an index built by summing weighted severities, not a
              calibrated probability, and a bare "%" would claim the latter. */}
          <div className="flex flex-col items-center">
            <span className="text-3xl font-extrabold tracking-tight leading-none" style={{ color }}>
              {score}
              <span className="text-sm font-bold align-baseline opacity-70 ml-0.5">
                /{maxScore}
              </span>
            </span>
            <span className="font-label-md text-xs font-bold text-on-surface-variant mt-0.5">
              RISK INDEX
            </span>
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
          {provenance &&
            (onShowEvidence && anomalyCount && anomalyCount > 0 ? (
              /* A real button, with the tactile treatment and its press.
                 DESIGN.md is explicit that a button without a press is a
                 container, and this one sits directly under a ring that is
                 obviously not interactive, so the affordance has to be carried
                 by the control itself.

                 `type="button"` because the shell renders forms and a bare
                 button defaults to submit.

                 The label stays the sentence it was. Adding "View details"
                 would say nothing the count has not already said, and would
                 make the button wider than the line it replaces. */
              <button
                type="button"
                data-role="provenance-jump"
                onClick={onShowEvidence}
                className={`tactile-btn-accent ${levelButtonClass(riskLevel)} max-w-[280px] rounded-lg px-4 py-2 font-label-sm cursor-pointer`}
              >
                {provenance}
              </button>
            ) : (
              <span className="text-label-sm text-on-surface-variant text-center max-w-[240px]">
                {provenance}
              </span>
            ))}
        </div>
      </div>
    </section>
  );
}

export default RiskGauge;

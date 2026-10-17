import React from 'react';
import { Icon, type IconName } from '../common';
import { verdictFor, NO_VERDICT, VERIFYING, type VerdictTone } from './verdictCopy';
import type { ScanRiskLevel } from '../../types';

export interface VerdictBlockProps {
  /**
   * The settled level, or null when there is none to report.
   *
   * Null covers two different situations and the banner answers them the same
   * way on purpose. One is a posting that named no employer, so nothing about the
   * company was checked. The other is a verification that could not complete. In
   * both, the system measured something about the posting and nothing about the
   * employer, and a banner that picked between them would be asserting a
   * distinction the evidence does not support.
   */
  level: ScanRiskLevel | null;
  /** The employer lookup is still running. Suppresses the level entirely. */
  verifying?: boolean;
  /**
   * The one-line reason.
   *
   * **Absent in this build.** No field on the wire carries a short reason, and
   * the architecture is explicit that the nearest candidate must not be reused:
   *
   *   > A short reason needs to be either emitted under its own length cap by the
   *   > verification prompt, or composed from the code set. Do not reuse `report`
   *   > and let the container grow.
   *
   * `VerificationResult.report` exists and is multi-sentence prose. Dropping it in
   * here would fill three lines of a one-line slot and quietly reassert a finding
   * the level does not support, which is the failure the slot exists to avoid.
   */
  reason?: string;
}

const TONE_CLASS: Record<VerdictTone, string> = {
  critical: 'tactile-verdict tactile-verdict-critical',
  caution: 'tactile-verdict tactile-verdict-caution',
  verified: 'tactile-verdict tactile-verdict-verified',
  unknown: 'tactile-verdict',
};

const TONE_ICON: Record<VerdictTone, IconName> = {
  critical: 'gpp_bad',
  caution: 'gpp_maybe',
  verified: 'gpp_good',
  unknown: 'help',
};

/**
 * The verdict banner — the slot that replaces the risk gauge.
 *
 * **No number, and no magnitude.** The retired 0–100 index asserted a precision
 * no stage could defend, invited "how did you get 80?" with no answer available,
 * and was summed from parts that were not commensurable. What replaces it is a
 * short authored instruction plus, once the backend carries one, a one-line
 * reason — so the reader is told what to do, and the panel never has to defend a
 * figure it cannot reproduce.
 */
export function VerdictBlock({ level, verifying, reason }: VerdictBlockProps) {
  const copy = verifying ? VERIFYING : level ? verdictFor(level) : NO_VERDICT;
  const toneClass = TONE_CLASS[copy.tone];

  return (
    <section className={`${toneClass} p-4`} data-role="verdict-block" data-tone={copy.tone}>
      <div className="flex items-center gap-2">
        <Icon
          name={verifying ? 'search' : TONE_ICON[copy.tone]}
          filled={!verifying}
          className="text-lg leading-none"
          aria-hidden
        />
        <span className="text-label-sm font-bold tracking-widest uppercase opacity-90">
          Verdict
        </span>
        {verifying && (
          <span className="ml-auto inline-flex items-center gap-1.5 text-label-sm opacity-90">
            <span className="w-1.5 h-1.5 rounded-full bg-current animate-ping" />
            In progress
          </span>
        )}
      </div>

      <h2
        className="text-headline-md font-headline font-extrabold tracking-tight leading-snug mt-1"
        data-role="verdict-headline"
      >
        {copy.headline}
      </h2>

      {/*
        The reason is optional in the markup as well as in the contract. A banner
        carrying only its headline is complete — the instruction stands on its own
        — so an absent reason leaves no gap that reads as something withheld.
      */}
      {reason && (
        <p className="text-body-sm mt-1 leading-relaxed opacity-95" data-role="verdict-reason">
          {reason}
        </p>
      )}
    </section>
  );
}

export default VerdictBlock;

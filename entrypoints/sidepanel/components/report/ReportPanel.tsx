import React from 'react';
import { JobMeta } from './JobMeta';
import { VerdictBlock } from './VerdictBlock';
import { ActionBlock } from './ActionBlock';
import { AnomalyCards } from './AnomalyCards';
import { WhatWeChecked } from './WhatWeChecked';
import { FullDetails } from './FullDetails';
import { ReportFooter } from './ReportFooter';
import { VERIFYING, verdictFor } from './verdictCopy';
import { CompanyNameNeeded, InvalidContentError, OfferAnalysisCard } from '../scan';
import { useFlipReorder } from '../../lib/useFlipReorder';
import type { ScanResult } from '../../types';

export interface ReportPanelProps {
  result: ScanResult;
  /** The employer lookup is still running. */
  verifying: boolean;
  verificationError: boolean;
  currentQuery: string;
  /**
   * The one-line reason, once verification has produced one.
   *
   * Held by the caller rather than read off `result` because it arrives *after*
   * the banner first renders: the scan lands, the banner shows its authored
   * headline, and the reason only exists once the employer lookup settles.
   */
  verdictReason?: string;
  /** When this was scanned. Absent for a live scan. */
  timestamp?: string;
  /** The role, as the posting states it. */
  title?: string;
  /**
   * The posting named no employer, so the employer itself was never checked.
   *
   * A missing input rather than a finding, and the two are not allowed to look
   * alike: this replaces the checks section outright and says what was *not*
   * checked, so a reader cannot mistake it for a result.
   */
  needsCompanyName: boolean;
  /**
   * Settled high or critical, and the level is no longer moving.
   *
   * See `shouldElevateEvidence`. The waiting states matter: the scan returns a
   * level from the posting alone and verification can move it, so reordering on
   * the intermediate value would pull the reader's evidence out from under them
   * and put it back a second later.
   */
  elevate: boolean;
}

/**
 * The report — the whole slot stack, in one fixed order.
 *
 * Architecture: `docs/superpowers/specs/2026-10-17-report-panel-architecture.md`
 * §1. Visual source: `jobposts/stitch/01-do-not-proceed.html`, which is the
 * complete state; the caution and verified screens differ only in fill colour.
 *
 * **What is deliberately missing**, each because the panel cannot yet support the
 * claim it would make. Every one of these is an absent slot rather than an empty
 * one — see the note on conditional rendering below.
 *
 *   - the provenance line in the subject ("posted 2 days ago on a job board") —
 *     the system does not know where the posting came from
 *   - the "Do not share" chips — keyed to code families the backend does not
 *     yet emit
 *   - the report control — nothing to report the post *to*, for the same reason
 *     as the provenance line
 *   - the coverage count — its denominator must be a backend constant, or the
 *     count drifts with whatever the panel happens to render
 *   - "Was this accurate?" — no database, no destination for the answer. A click
 *     with nowhere to go reads as a working feature and silently discards the
 *     only signal that would tell us the verdict taxonomy is wrong.
 *
 * The three slots that used to be on this list now ship: the one-line verdict
 * reason (`verdict_reason`), the anomaly rule code (`Anomaly.code`), and the
 * quote block on each anomaly card (`Anomaly.quote`). Each was held back until
 * there was a real field behind it, because a slot filled from a paraphrase is
 * the same failure as a score the system never measured.
 *
 * **The disclosure now carries the model's per-check sentences.** `WhatWeChecked`
 * shows labels in three buckets; `FullDetails` shows the same checks with what
 * each one found, sharing the grouping so a label above matches its sentence
 * below. Until this, `VerificationItem.explanation` reached the client and was
 * never rendered — the panel asserted contradictions it gave no account of. The
 * disclosure wears the banner's tone for the same reason it sits here: it is the
 * same report, not a separate artefact.
 *
 * **Conditional rendering is load-bearing.** Slots 5–7 are absent in some states
 * and their absence is meaningful. An empty container is not a neutral
 * placeholder: "Anomalies detected — 0 found" asserts that we looked for
 * anomalies and found none, which is a claim about the posting, and on a posting
 * that was never fully assessed it is false.
 */
export function ReportPanel({
  result,
  verifying,
  verificationError,
  currentQuery,
  verdictReason,
  timestamp,
  title,
  needsCompanyName,
  elevate,
}: ReportPanelProps) {
  // The FLIP dependency is the flag itself: the two groups move because this
  // changed, and re-measuring on any other change would replay the animation for
  // reasons unrelated to order.
  const flip = useFlipReorder(elevate);

  const level = result.riskLevel;

  // The banner's tone, resolved once here and handed to both the banner and the
  // disclosure below it. `VerdictBlock` looks this up for itself from the same
  // two inputs, so there is one rule rather than two — but it is a lookup from
  // the authored table, not a second definition of which level means what, and
  // the two components have to agree or the panel reads as two objects.
  const tone = (verifying ? VERIFYING : verdictFor(level)).tone;

  // `VALID: false` is a state of its own, not an empty report. The scan found no
  // offer of work to assess, so there is no verdict, no findings and no checks
  // — and saying so is the content.
  if (!result.isJobPosting) {
    return (
      <div className="flex flex-col gap-stack-md">
        <InvalidContentError onRetry={() => {}} />
      </div>
    );
  }

  return (
    <article className="flex flex-col gap-stack-md" data-role="report-panel">
      <JobMeta timestamp={timestamp} title={title} employer={result.companyName} />

      <VerdictBlock level={level} verifying={verifying} reason={verdictReason} />

      <ActionBlock level={level} />

      {/*
        Two sibling groups, both always mounted, one visible at a time by `order`.

        **Promotion is restated, not kept.** The old scheme reordered a pair of
        groups to move *evidence up*. Here the verdict and the instructions
        already occupy the top, so there is nothing above them to promote, and
        what promotion means has changed: the neutral context — what we checked,
        where it came from — drops *below* the findings. A reader who has just
        been told not to send money does not need the coverage count in their
        first viewport.

        Both groups stay mounted so an unmounted block loses neither its state nor
        anything to animate: a collapsed disclosure that re-expanded itself on
        every level change would be worse than no animation. `display: contents`
        would read as the tidier way to drop a wrapper, but it generates no box,
        and `order` has no effect on a box that does not exist.
      */}
      <div
        className={`flex flex-col gap-stack-md ${elevate ? 'order-1' : 'order-2'}`}
        data-group="findings"
        ref={flip.register('findings')}
      >
        <AnomalyCards
          anomalies={result.anomalies}
          // `verificationLoading`, not the caller's sticky `verifying`: that flag
          // stays true after a failed lookup, and a spinner that never stops is
          // worse than an honest "not checked".
          checking={Boolean(result.verificationLoading)}
          needsCompanyName={needsCompanyName}
          verificationError={verificationError}
          assessmentRun={Boolean(result.anomalyAssessmentRun)}
        />

        {/*
          The no-employer path. The posting stage still produced a level and its
          own findings, so those render; the offer analysis is the verdict for
          this reading, and it reports what the post asks for and offers rather
          than anything about a company.
        */}
        {!needsCompanyName && (
          <OfferAnalysisCard analysis={result.offerAnalysis} loading={result.offerAnalysisLoading} />
        )}
      </div>

      <div
        className={`flex flex-col gap-stack-md ${elevate ? 'order-2' : 'order-1'}`}
        data-group="context"
        ref={flip.register('context')}
      >
        {needsCompanyName ? (
          <CompanyNameNeeded />
        ) : (
          <WhatWeChecked
            result={result.verificationResult}
            loading={verifying}
            error={verificationError}
            currentQuery={currentQuery}
          />
        )}

        {!needsCompanyName && (
          <FullDetails result={result.verificationResult} tone={tone} />
        )}
      </div>

      <ReportFooter />
    </article>
  );
}

export default ReportPanel;

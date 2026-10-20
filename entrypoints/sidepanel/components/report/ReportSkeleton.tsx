import React from 'react';

export interface ReportSkeletonProps {
  /** How far the scan has got, as the streaming endpoint reports it. */
  progressPercent: number;
  /**
   * How many finding cards to draw. The report draws one per finding and the
   * count is not known until the scan settles, so this is only a shape — two is
   * enough to say "there will be a list here" without pretending to know its
   * length.
   */
  cardCount?: number;
}

/**
 * The placeholder for a scan that has not settled yet.
 *
 * **It mirrors the report, not the old loader.** The loader was a centred
 * circle and three lines, which told the reader that something was happening but
 * not what was coming. This draws the same slots in the same order as
 * `ReportPanel` — subject, verdict, instructions, findings, details — so the
 * panel does not jump when the real content lands and the reader can see the
 * shape of the answer while they wait.
 *
 * **Grey and pulsing, never a verdict colour.** A skeleton in the critical red
 * would assert a severity before anything was measured, which is the failure the
 * whole panel is built to avoid. The fill is the grey container scale:
 * `surface-container-highest` bars on `surface-container-high` wells, including
 * the card that will become the verdict banner.
 *
 * The two unbuilt slots — "Was this accurate?" and "Report this post" — are
 * deliberately absent. A skeleton is a promise about what is coming; drawing a
 * control that will never arrive is a worse lie than drawing nothing.
 */
export function ReportSkeleton({ progressPercent, cardCount = 2 }: ReportSkeletonProps) {
  // One step lighter than the containers below, so a block on a
  // `surface-container-high` well is still visible rather than blending into it.
  const bar = 'rounded bg-surface-container-highest animate-pulse';
  const percent = Math.max(0, Math.min(100, Math.round(progressPercent)));

  return (
    <article
      className="flex flex-col gap-stack-md"
      data-role="report-skeleton"
      aria-busy="true"
      aria-label="Reading the job post"
    >
      {/* Subject: the scan time, the role, the employer. The progress line takes
          the timestamp slot, which is the same line and weight. */}
      <section className="px-1 flex flex-col gap-1.5">
        <div className="flex items-center gap-2 text-on-surface-variant" role="status">
          <span aria-hidden className="w-1.5 h-1.5 rounded-full bg-on-surface-variant animate-pulse" />
          <span className="text-label-sm font-label">
            Scanning… {percent}%
          </span>
        </div>
        <div className="flex flex-col gap-1.5" aria-hidden>
          <div className={`${bar} h-5 w-3/4`} />
          <div className={`${bar} h-3 w-1/2`} />
        </div>
      </section>

      {/* Verdict banner. Tall and neutral; the real one carries the colour. */}
      <section
        className="rounded-xl border border-outline-variant/30 bg-surface-container-high p-4 flex flex-col gap-3"
        aria-hidden
      >
        <div className="flex items-center gap-2">
          <div className={`${bar} h-4 w-4 rounded-full`} />
          <div className={`${bar} h-2.5 w-16`} />
        </div>
        <div className={`${bar} h-6 w-11/12`} />
        <div className={`${bar} h-3 w-full`} />
        <div className={`${bar} h-3 w-2/3`} />
      </section>

      {/* What to do now. */}
      <section className="flex flex-col gap-2" aria-hidden>
        <div className={`${bar} h-4 w-32 mx-1`} />
        <div className="rounded-lg border border-outline-variant/20 bg-surface-container-lowest p-4 flex flex-col gap-3">
          <div className="flex items-start gap-3">
            <div className={`${bar} mt-1 h-2.5 w-2.5 rounded-full shrink-0`} />
            <div className="flex-1 flex flex-col gap-1.5">
              <div className={`${bar} h-3 w-full`} />
              <div className={`${bar} h-3 w-4/5`} />
            </div>
          </div>
          <div className="flex items-start gap-3">
            <div className={`${bar} mt-1 h-2.5 w-2.5 rounded-full shrink-0`} />
            <div className="flex-1 flex flex-col gap-1.5">
              <div className={`${bar} h-3 w-full`} />
              <div className={`${bar} h-3 w-3/5`} />
            </div>
          </div>
        </div>
      </section>

      {/* Findings: heading, count, then one card per finding. */}
      <section className="flex flex-col gap-3" aria-hidden>
        <div className="flex items-center justify-between gap-2 px-1">
          <div className={`${bar} h-4 w-40`} />
          <div className={`${bar} h-3 w-12`} />
        </div>

        {Array.from({ length: cardCount }, (_, index) => (
          <div
            key={index}
            className="rounded-lg border border-outline-variant/20 bg-surface-container-lowest p-4 flex flex-col gap-2.5"
          >
            <div className="flex items-center justify-between gap-2">
              <div className={`${bar} h-5 w-20 rounded-full`} />
              <div className={`${bar} h-4 w-24`} />
            </div>
            <div className={`${bar} h-4 w-5/6`} />
            <div className={`${bar} h-3 w-full`} />
            <div className={`${bar} h-3 w-2/3`} />
            {/* The quote well, then the evidence strip that replaces it. */}
            <div className="rounded-md bg-surface-container-high p-3 flex flex-col gap-1.5">
              <div className={`${bar} h-2.5 w-20`} />
              <div className={`${bar} h-3 w-full`} />
              <div className={`${bar} h-3 w-4/5`} />
            </div>
            <div className="rounded-md border border-outline-variant/30 bg-surface-container-high p-3 flex flex-col gap-1.5">
              <div className={`${bar} h-2.5 w-28`} />
              <div className={`${bar} h-3 w-full`} />
            </div>
          </div>
        ))}
      </section>

      {/* What we checked / full details, collapsed. */}
      <section
        className="rounded-lg border border-outline-variant/20 bg-surface-container-lowest p-4 flex flex-col gap-2.5"
        aria-hidden
      >
        <div className={`${bar} h-4 w-36`} />
        <div className={`${bar} h-3 w-full`} />
        <div className={`${bar} h-3 w-5/6`} />
        <div className={`${bar} h-3 w-2/3`} />
      </section>

      <div className="flex flex-col gap-1.5 px-1" aria-hidden>
        <div className={`${bar} h-2.5 w-full`} />
        <div className={`${bar} h-2.5 w-3/4`} />
      </div>
    </article>
  );
}

export default ReportSkeleton;

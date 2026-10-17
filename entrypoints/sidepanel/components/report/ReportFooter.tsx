import React from 'react';

export interface ReportFooterProps {
  /**
   * A short id for this scan.
   *
   * **Absent in this build** — no backend field carries one yet. The value of it
   * is not cosmetic: it is the join key that lets a gold-set label, a reader
   * rating, and a backend log line all refer to the same scan. Without it a
   * rating captured later cannot be traced back to what was actually on screen.
   */
  scanId?: string;
}

/**
 * Which ruleset produced this reading.
 *
 * A constant rather than a field, deliberately. It is a property of the prompts
 * and taxonomy in the build, not of the scan, so it travels with the code that
 * contains it and cannot drift away from the prompts it names. Bumping it is a
 * deliberate act — the whole point is that a reader holding two reports can tell
 * whether the same rules produced both.
 */
const RULESET_VERSION = '2026.10.2';

/**
 * The disclaimer, and the one place the panel is allowed to state its own limits.
 *
 * Kept as authored prose rather than generated, for the same reason as the verdict:
 * it is a claim about what this product can and cannot do, and that claim has to
 * survive a run in which every other string on the panel came from a model.
 */
const DISCLAIMER =
  'This is a risk assessment, not proof of fraud or legitimacy. A scan can miss a convincing fake.';

/**
 * The report footer — slot 10.
 *
 * Sits at the end of the report rather than in the app shell, because it is
 * scoped to *this* reading: the ruleset that produced it and the id of the scan.
 * A global footer carrying those would be claiming they apply to the Match tab,
 * which ran a different endpoint against different prompts.
 */
export function ReportFooter({ scanId }: ReportFooterProps) {
  return (
    <footer className="flex flex-col gap-1 pt-4 pb-2 text-left" data-role="report-footer">
      <p className="text-label-sm text-on-surface-variant leading-relaxed">{DISCLAIMER}</p>
      <p className="text-label-sm text-on-surface-variant">
        Ruleset {RULESET_VERSION}
        {/* The id is omitted entirely rather than rendered blank. "Ruleset
            2026.10.2 ·" with nothing after it reads as a truncated value; the
            line reads as a complete statement either way. */}
        {scanId ? ` · Scan ${scanId}` : ''}
      </p>
    </footer>
  );
}

export default ReportFooter;

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
 * The assessment's own limits, and the one place the panel is allowed to state them.
 *
 * Kept as authored prose rather than generated, for the same reason as the assessment:
 * it is a claim about what this product can and cannot do, and that claim has to
 * survive a run in which every other string on the panel came from a model.
 *
 * **Not a disclaimer.** Nothing here disclaims liability or speaks for a lawyer;
 * the sentence bounds what the reading can establish — an assessment, not proof,
 * and one that can miss a convincing fake. The code calls it what it is.
 */
const ASSESSMENT_LIMITATION =
  'This is a risk assessment, not proof of fraud or legitimacy. A scan can miss a convincing fake.';

/**
 * The report footer — slot 10.
 *
 * Sits at the end of the report rather than in the app shell, because it is
 * scoped to *this* reading: the id of the scan, when the backend carries one.
 * A global footer would be claiming that applies to the Match tab, which ran a
 * different endpoint against different prompts.
 *
 * The ruleset version has been dropped. It named a build constant that a reader
 * cannot act on and cannot compare against anything they hold; two reports from
 * the same day carried the same string, two from different builds carried strings
 * that meant nothing without the prompts behind them.
 */
export function ReportFooter({ scanId }: ReportFooterProps) {
  return (
    <footer className="flex flex-col gap-1 pt-4 pb-2 text-left" data-role="report-footer">
      <p className="text-label-sm text-on-surface-variant leading-relaxed">
        {ASSESSMENT_LIMITATION}
      </p>
      {scanId && (
        <p className="text-label-sm text-on-surface-variant">Scan {scanId}</p>
      )}
    </footer>
  );
}

export default ReportFooter;

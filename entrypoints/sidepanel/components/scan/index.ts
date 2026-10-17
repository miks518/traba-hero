/**
 * The capture affordances and the two states that replace the report.
 *
 * **The report itself is not exported from here.** It lives in `../report`, which
 * replaces `RiskGauge`, `AnomaliesList`, `EvidenceSummary`, `VerificationCard`,
 * `PostingAnalysis` and `JobSummary` — all removed. `docs/superpowers/specs/2026-10-17-report-panel-architecture.md`
 * §7 is the migration map and records why each one went.
 *
 * `AnomalyCard` survives and is used by the Match tab, which renders a scan's
 * findings as a compact list rather than as a report. Its two callers want
 * different things from a finding: the report shows phrase, explanation and —
 * once `quote` lands — the span the posting actually contained; the Match tab
 * shows a one-line reminder of why a job scored what it scored.
 */
export { AnomalyCard } from './AnomalyCard';
export { ScanActions } from './ScanActions';
export { PickerButton } from './PickerButton';
export { InvalidContentError } from './InvalidContentError';
export { OfferAnalysisCard } from './OfferAnalysisCard';
export { CompanyNameNeeded } from './CompanyNameNeeded';
export type { OfferAnalysisCardProps } from './OfferAnalysisCard';

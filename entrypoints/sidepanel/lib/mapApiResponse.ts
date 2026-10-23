import type {
  ApiScanResponse,
  Anomaly,
  IconName,
  ScanResult,
  ScanRiskLevel,
} from '../types';
import { isUnverifiedEmployer } from './riskDisplay';

/**
 * Which icon each severity renders. The severity names are the wire's
 * (`low`/`mid`/`high`), not the panel's — the rename to `anomalies` moved the
 * *category* name, not this field, and `docs/decisions/anomaly-terminology.md`
 * records that the legacy paths are deliberate.
 */
const SEVERITY_ICONS: Record<string, IconName> = {
  low: 'info',
  mid: 'warning',
  high: 'warning',
};

/**
 * The level word as prose, for history entries and anything else that needs a
 * label rather than a token.
 *
 * "Not Scored" for a null level rather than a fallback to `low`. A stored scan
 * whose verification never completed has no level, and calling that low would
 * claim the posting was cleared.
 */
export function riskLevelLabel(level: string | null | undefined): string {
  switch (level) {
    case 'low': return 'Low Risk';
    case 'moderate': return 'Moderate Risk';
    case 'high': return 'High Risk';
    case 'critical': return 'Critical Risk';
    default: return 'Not Scored';
  }
}

/**
 * The wire response → the panel's shape.
 *
 * Extracted from `ScamScanView.tsx`, which is where it lived as a
 * module-private function. That made one of this project's standing rules
 * unassertable: "never synthesise a score in the client" is a claim about *this
 * function* — it is the only place the wire's fields become the panel's — and a
 * private function cannot be tested. See `UNFINISHED-WORK.md`, "Scan-mapping
 * tests".
 *
 * Nothing here computes anything the backend did not send. `riskScore` is
 * copied through or left null, and `scoreBreakdown` is passed along whole. The
 * one derived value is `unverifiedEmployer`, and it is a *suppression*, not a
 * measurement: it suppresses a verdict the system cannot support.
 */
export function mapApiResponse(data: ApiScanResponse): ScanResult {
  const isJobPosting = data.valid;

  // Falls back to the pre-rename key so a response captured before the rename
  // still renders its findings rather than showing a clean posting. The wire key
  // is `anomalies`; an older backend still sends `red_flags`.
  const flags =
    data.anomalies ?? (data as { red_flags?: typeof data.anomalies }).red_flags ?? [];

  const hasCritical = flags.some((f) => f.severity === 'high');

  // Absent rather than 0. The backend sends no `risk_score` when it measured
  // none, and `0` would render as the bottom of a scale — a claim that the
  // posting was assessed and came out clean.
  const score = typeof data.risk_score === 'number' ? data.risk_score : null;
  const level: ScanRiskLevel | null = data.risk_level ?? null;

  const anomalies: Anomaly[] = flags.map((f, i) => ({
    id: `anomaly-${i}`,
    title: f.flag,
    description: f.reasoning,
    icon: SEVERITY_ICONS[f.severity] || 'warning',
    severity: f.severity as Anomaly['severity'],
    // Copied through, never defaulted to a value. `''` means the response
    // carried no code, which is a different claim from `OTHER` — the model
    // deliberately answering the escape valve — and the panel shows a pill only
    // for the second. Defaulting an absent code to `OTHER` would put a taxonomy
    // ID on every scan taken before the field existed.
    code: f.code || undefined,
    // Absent rather than `''`, for the reason the backend screens it: a quote
    // that did not survive screening is not a quote, and an empty string in this
    // slot would render as a quotation block with nothing in it.
    quote: f.quote || undefined,
  }));

  return {
    riskLevel: level,
    riskLabel: riskLevelLabel(level),
    // Copied through, never defaulted: `''` means the scan reported no class,
    // which is a missing input rather than an ordinary posting.
    requestClass: data.request_class || undefined,
    riskScored: level !== null || score !== null,
    riskScore: score,
    unverifiedEmployer: isUnverifiedEmployer({
      isJobPosting,
      companyName: data.company_name || null,
      anomalyCount: flags.length,
    }),
    riskDescription: '',
    scanningTarget: 'Scanned Element',
    anomalies,
    flagsCritical: hasCritical,
    isJobPosting,
    companyName: data.company_name || null,
    secRegistration: data.sec_registration || [],
    jobSummary: data.job_summary || undefined,
    postingAnalysis: data.posting_analysis || undefined,
    scoreBreakdown: data.score_breakdown || undefined,
    // Copied through, never defaulted. An empty object here would render as "the
    // posting claimed nothing", which is a claim about the posting; what is true
    // when the scan reports none is that we have nothing to show.
    attributes: data.attributes,
    searchQueries: data.search_queries,
    verificationResult: data.verificationResult,
    verificationLoading: Boolean(data.verification_context?.company_name?.trim()),
    verificationError: data.verificationError,
  };
}

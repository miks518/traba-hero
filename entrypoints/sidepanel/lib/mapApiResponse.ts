import type {
  ApiScanResponse,
  Anomaly,
  IconName,
  ScanResult,
  Assessment,
} from '../types';
import { isUnverifiedEmployer } from './riskDisplay';
import { findingTier } from './findingTiers';

/**
 * Which icon each finding renders, derived from its taxonomy code — the thing
 * the scan actually carries. The scan has no severity to map (`docs/decisions/
 * scan-severity-removal.md`), so a finding that asks the reader for money or
 * account access gets the warning icon and every other finding the info icon.
 * The tiers are shared with the cap ranking and the card colour.
 */
function iconForCode(code?: string): IconName {
  // No code at all renders the warning icon, as every finding did before the
  // taxonomy existed — an unknown finding is not known to be minor.
  if (!code) return 'warning';
  return findingTier(code) === 3 ? 'warning' : 'info';
}

/**
 * The assessment word as prose, for history entries and anything else that needs a
 * label rather than a token.
 */
export function assessmentLabel(assessment: Assessment | null | undefined): string {
  switch (assessment) {
    case 'clear': return 'Proceed';
    case 'note': return 'Note';
    case 'caution': return 'Caution';
    case 'stop': return 'Do not proceed';
    default: return 'Not Assessed';
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
 * Nothing here computes anything the backend did not send. The assessment and
 * breakdown come from the backend's decision grid. The one derived value is
 * `unverifiedEmployer`, and it is a *suppression*, not a measurement: it
 * suppresses a assessment the system cannot support.
 */
export function mapApiResponse(data: ApiScanResponse): ScanResult {
  const isJobPosting = data.valid;

  // Falls back to the pre-rename key so a response captured before the rename
  // still renders its findings rather than showing a clean posting. The wire key
  // is `anomalies`; an older backend still sends `red_flags`.
  const flags =
    data.anomalies ?? (data as { red_flags?: typeof data.anomalies }).red_flags ?? [];

  // The assessment comes from the backend's decision grid.
  const assessment: Assessment | null = data.assessment ?? null;

  const anomalies: Anomaly[] = flags.map((f, i) => ({
    id: `anomaly-${i}`,
    title: f.flag,
    description: f.reasoning,
    icon: iconForCode(f.code),
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
    assessment,
    assessmentLabel: assessmentLabel(assessment),
    // Copied through, never defaulted: `''` means the scan reported no class,
    // which is a missing input rather than an ordinary posting.
    requestClass: data.request_class || undefined,
    assessed: assessment !== null,
    assessmentBreakdown: data.assessment_breakdown || undefined,
    assessmentText: data.assessment_text || undefined,
    riskDescription: '',
    unverifiedEmployer: isUnverifiedEmployer({
      isJobPosting,
      companyName: data.company_name || null,
      anomalyCount: flags.length,
    }),
    scanningTarget: 'Scanned Element',
    anomalies,
    isJobPosting,
    companyName: data.company_name || null,
    secRegistration: data.sec_registration || [],
    jobSummary: data.job_summary || undefined,
    postingAnalysis: data.posting_analysis || undefined,
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

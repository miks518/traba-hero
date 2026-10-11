export type ViewId = 'scan' | 'match';

export type IconName =
  | 'security'
  | 'description'
  | 'help'
  | 'settings'
  | 'contact_support'
  | 'open_in_new'
  | 'warning'
  | 'bolt'
  | 'refresh'
  | 'flag'
  | 'alternate_email'
  | 'payments'
  | 'history_edu'
  | 'phone_disabled'
  | 'picture_as_pdf'
  | 'edit'
  | 'add'
  | 'check_circle'
  | 'rocket_launch'
  | 'close'
  | 'touch_app'
  | 'crop'
  | 'info'
  | 'upload_file'
  | 'delete'
  | 'work'
  | 'dark_mode'
  | 'light_mode'
  | 'smart_toy'
  | 'travel_explore'
  | 'chevron_left'
  | 'chevron_right'
  | 'keyboard_arrow_down'
  | 'history'
  | 'handshake'
  | 'search'
  | 'architecture'
  | 'database'
  | 'shield_person'
  | 'timer'
  | 'calendar_month'
  | 'lock'
  | 'business'
  | 'tips_and_updates'
  | 'arrow_right'
  | 'verified'
  | 'filter_list'
  | 'badge'
  | 'gpp_good'
  | 'gpp_maybe'
  | 'gpp_bad';

export type JobFilterCategory = 'all' | 'verified' | 'suspicious' | 'risky' | 'low' | 'moderate' | 'high' | 'critical';

export interface NavTab {
  id: ViewId;
  label: string;
  title: string;
  icon: IconName;
}

/**
 * Something in a posting that differs from the ordinary case.
 *
 * Named for what it is rather than what it is taken to mean: "red flag" was a
 * conclusion delivered as a category label, so a low-severity note about
 * formatting was announced with the same force as a request for an advance fee.
 * Severity carries the weight; this only says the posting differs.
 */
export interface Anomaly {
  id: string;
  title: string;
  description: string;
  icon: IconName;
  severity?: 'low' | 'mid' | 'high';
}

export interface SkillGap {
  id: string;
  label: string;
}

export interface MatchKeyword {
  id: string;
  label: string;
  matched: boolean;
}

export interface VerificationItem {
  label: string;
  status: 'green' | 'yellow' | 'red';
  explanation: string;
  /** The result the finding came from, copied from the search results. */
  source_title?: string;
  source_url?: string;
  /**
   * The search that surfaced this check, when one was issued for it.
   *
   * Not yet emitted by the backend — `VerificationItem` on the wire carries no
   * such field. Declared so a check that arrives with one is typed rather than
   * read off `unknown`. Nothing renders it yet; when it does, it must be shown
   * as what was searched, never as evidence about the employer.
   */
  source_query?: string;
}

export interface VerificationEvidence {
  title: string;
  url: string;
  snippet: string;
}

export interface VerificationResult {
  items: VerificationItem[];
  evidence?: VerificationEvidence[];
  report: string;
  recommendation: string;
  riskScore?: number;
  riskLevel?: ScanRiskLevel;
  noCompanyName?: boolean;
  /**
   * Whether the web search succeeded. False means the categories are unknown,
   * not that the employer is clean — the panel states this directly rather
   * than depending on the model mentioning it.
   */
  searchOk?: boolean;
  searchError?: string;
  /**
   * One of the two searches failed, so the answer is real but some categories
   * are covered more thinly than they appear. Distinct from `searchOk: false`,
   * which means nothing was retrieved and no category can be judged at all.
   */
  searchPartial?: boolean;
  /** How many queries were issued, and how many of them failed. */
  queriesIssued?: number;
  queriesFailed?: number;
  /**
   * Which of those queries were built from the posting's own stated details
   * rather than from the employer's name. Reported separately from
   * `queriesIssued` because the two families answer different questions.
   * Always present on the wire, possibly empty.
   */
  schemeQueries?: string[];
  /**
   * TEMPORARY DIAGNOSTIC — the provider's raw response body per query, so it
   * can be inspected in the panel. Nothing reads this in normal use. Remove
   * with `SearchOutcome.raw_response` on the backend and the suspended
   * assertion in `test_no_debug_surface.py`.
   */
  debugSearchRaw?: Array<{ query: string; raw: string }>;
}

export type ScanRiskLevel = 'low' | 'moderate' | 'high' | 'critical';

export interface ScanResult {
  riskLevel: ScanRiskLevel | null;
  riskLabel: string;
  /**
   * True when a score was actually calculated. The posting's own indicators
   * always produce one, so this is only false for jobs restored from history
   * that predate that behaviour — those are shown as unverified rather than
   * showing a number the system never measured.
   */
  riskScored: boolean;
  riskScore: number | null;
  /**
   * The posting named no employer and raised no anomalies, so the posting
   * stage scored 0 while the employer was never checked. Shown as "Unverified"
   * rather than "0 / Low Risk", which would claim the post was cleared.
   * An anomaly is real evidence, so it is scored on severity instead.
   */
  unverifiedEmployer?: boolean;
  riskDescription: string;
  scanningTarget: string;
  scoreBreakdown?: RiskScoreBreakdown;
  offerAnalysis?: OfferAnalysis;
  offerAnalysisLoading?: boolean;
  anomalies: Anomaly[];
  flagsCritical: boolean;
  isJobPosting: boolean;
  companyName?: string | null;
  secRegistration?: { company_name: string; sec_no: string; status: string; date_approved: string }[];
  jobSummary?: string;
  postingAnalysis?: string;
  emailVerifications?: {
    email: string;
    domain: string;
    syntaxValid: boolean;
    hasMxRecords: boolean;
    isDisposable: boolean;
    risk: 'low' | 'medium' | 'high';
    reason: string;
  }[];
  verificationResult?: VerificationResult;
  verificationLoading?: boolean;
  verificationError?: boolean;
}

export interface ScannedJob {
  id: string;
  title: string;
  summary: string;
  timestamp: string;
  scanResult: ScanResult;
}

export interface ResumeData {
  skills: string[];
  experience_years: number;
  job_titles: string[];
  industries: string[];
  summary: string;
}

export interface JobMatchItem {
  jobId: string;
  score: number;
  label: string;
  skillGaps: string[];
  matchedSkills: string[];
  reasoning?: string;
  experienceFit?: string;
  industryFit?: string;
  recommendedActions?: string[];
}

export interface MatchResult {
  resume: {
    filename: string;
    lastUpdated: string;
  };
  matchScore: number;
  compatibilityLabel: string;
  skillGaps: SkillGap[];
  topKeywords: MatchKeyword[];
  matches: JobMatchItem[];
}

export interface ApiErrorResponse {
  status: number;
  message: string;
  details?: string;
}

export type ApiStatus = 'idle' | 'loading' | 'success' | 'error';

export interface ApiScanResponse {
  valid: boolean;
  anomalies: { flag: string; reasoning: string; severity: string }[];
  /**
   * What the posting states about itself, in the poster's own words. Only keys
   * the posting actually stated are present — an absent key means it said
   * nothing, which is a missing input rather than a finding.
   *
   * This is what makes dynamic retrieval possible, and until the panel sent it
   * to `/api/verify` nothing was retrieved from it at all: the scheme queries
   * are built server-side from these, so an extension that dropped the field
   * left every verification at two employer queries and `Channel Match` — the
   * one check that can detect an impersonation — structurally unable to fire.
   */
  attributes?: Record<string, string>;
  job_summary: string;
  error?: string | null;
  company_name?: string | null;
  risk_score?: number;
  risk_level?: ScanRiskLevel;
  sec_registration?: { company_name: string; sec_no: string; status: string; date_approved: string }[];
  email_verifications?: {
    email: string;
    domain: string;
    syntax_valid: boolean;
    has_mx_records: boolean;
    is_disposable: boolean;
    risk: 'low' | 'medium' | 'high';
    reason: string;
  }[];
  /**
   * The wire spells the breakdown in snake_case; `consumeSseStream` translates
   * it before the response leaves the SSE reader, so everything downstream of
   * this function sees the client shape. The field name stays snake_case
   * because that is what the endpoint sends.
   */
  score_breakdown?: RiskScoreBreakdown;
  posting_analysis?: string;
  verification_context?: {
    company_name?: string;
    job_summary?: string;
  };
  verificationResult?: VerificationResult;
  verificationLoading?: boolean;
  verificationError?: boolean;
}

/**
 * How a score was reached: which stages contributed, and by how much.
 *
 * Client-shaped rather than wire-shaped. `toScoreBreakdown` in
 * `lib/scoreBreakdown.ts` is the only place that reads the backend's keys, so
 * the rest of the panel never has to know the wire spells them in snake_case.
 */
export interface RiskScoreBreakdown {
  source?: string;
  highCount?: number;
  midCount?: number;
  lowCount?: number;
  weights?: Record<string, number>;
  /** Sum of the posting stage's weighted severities, 0–100. */
  postingScore?: number;
  /**
   * The employer stage's contribution, and it is a **refutation sum** (0–50),
   * not the employer's share of the final score.
   *
   * It used to be a per-category share of a blend, which read as "how much of
   * this number is about the employer". Nothing supports that claim now: only a
   * retrieved source that *contradicts* something the posting stated scores
   * here, so a clean employer record contributes zero and a search that was
   * never able to run contributes `null`. Renamed from `verification_score`
   * because that name is the other reading, and the common case — nothing
   * refuted — is exactly the one it misstates.
   */
  refutationScore?: number | null;
  finalScore?: number | null;
  /** Which stages contributed, as the backend labels them. */
  sources?: string[];
}

export interface OfferAnalysis {
  kind: string;
  verdict: string;
  whatItAsks: string;
  whatItOffers: string;
  whatToCheck: string;
  isOffer: boolean;
}

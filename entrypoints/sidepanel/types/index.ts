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
  | 'gpp_bad'
  | 'question_mark'
  | 'cloud_off';

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
export interface AnomalyAssessment {
  /**
   * 1-based index into the findings list the verify request sent.
   *
   * Only meaningful at the API boundary: `useScanSession` uses it to map the
   * verdict back to the original finding, then attaches the assessment without
   * relying on the index. Kept optional so an assessment stored on an
   * `Anomaly` does not claim an index that stopped being its identity.
   */
  index?: number;
  /**
   * The evidence verdict on this finding.
   *
   * `stale` means a source about this employer accounted for it and the finding
   * no longer stands. `red` means a source contradicts it. `yellow` means the
   * results did not settle it, or nothing could be checked.
   *
   * Not the same vocabulary as the six category checks: those still use
   * `green | yellow | red`. `green` is deliberately absent here — a retired
   * finding is grey, not a success colour.
   */
  status: 'stale' | 'yellow' | 'red';
  /** What the source says, in one plain sentence. */
  finding: string;
  /** The retrieved result the verdict relies on, for stale/red. */
  sourceTitle?: string;
  sourceUrl?: string;
}

export interface Anomaly {
  id: string;
  title: string;
  description: string;
  icon: IconName;
  severity?: 'low' | 'mid' | 'high';
  /**
   * The taxonomy ID from the backend's `ANOMALY_CODES`, or `OTHER` when the
   * model's answer fell outside the set, or `undefined` for a scan recorded
   * before the field existed.
   *
   * `undefined` is not the same as `OTHER`: absent means the response carried
   * no code at all, while `OTHER` means the model deliberately answered the
   * escape valve. Collapsing them would make stored history look like drift.
   *
   * Optional on read — scan history predates this field, so requiring it would
   * render every stored scan unloadable.
   */
  code?: string;
  /**
   * A verbatim span of the posting that decided this finding.
   *
   * Empty or absent when the model emitted none, when the span carried a word
   * the posting could not have written about itself, or — on the text path
   * only — when it could not be found in the submitted text. An absent quote
   * degrades the card to its description; a fabricated one is never rendered,
   * so the card must not treat "no quote" as an error.
   */
  quote?: string;
  /**
   * The verify stage's verdict, when one was recorded for this finding.
   *
   * Absent is a real state, not "stale": the finding may predate the check, the
   * employer may not have been named, or the verification may have failed. The
   * card renders each of those as amber with its own note, never as a retired
   * finding.
   */
  assessment?: AnomalyAssessment;
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
  /**
   * The verify model's verdicts on the findings the request sent. Indices are
   * 1-based against that request's list, which may be a capped subset of the
   * findings on screen; `useScanSession` maps them back to the original list.
   */
  anomalyAssessments?: AnomalyAssessment[];
  /**
   * Whether the backend's response carried the `anomaly_assessments` key at
   * all. `true` with an empty list means the check ran and produced no verdict;
   * `false` means the reading predates the check. The two get different amber
   * notes, and neither is allowed to invent a `stale`.
   */
  anomalyAssessmentRun?: boolean;
  /**
   * One sentence, capped at 140 characters, naming what the posting asks the
   * reader to give up. The panel's one-line reason under the verdict headline.
   *
   * Generated by the model, and screened before it leaves the backend
   * (`clean_verdict_reason`): a hedge, an absolute or an accusation becomes
   * absent rather than shown. That asymmetry is deliberate — a missing reason
   * leaves a banner that still carries its authored headline, whereas a rejected
   * one shown verbatim would put the banned words beside a named employer.
   *
   * **Not the same slot as `report`.** `report` is multi-sentence prose, rendered
   * behind the Full-details disclosure; reusing it here would fill three lines of
   * a one-line slot.
   */
  verdictReason?: string;
  riskScore?: number;
  riskLevel?: ScanRiskLevel;
  /** The posting's request class, carried from the scan unchanged. */
  requestClass?: string;
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
   * Which of those queries the scan model proposed, rather than the one built
   * here from the employer's name. Reported separately from `queriesIssued`
   * because the two families answer different questions.
   * Always present on the wire, possibly empty.
   *
   * Renamed from `schemeQueries`: nothing builds these from attributes any
   * more, and the panel reads this out as *what was searched*.
   */
  modelQueries?: string[];
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
   * What the posting asks for, from the scan. Absent means the reading predates
   * the field; it is never defaulted to `ordinary`.
   */
  requestClass?: string;
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
  verificationResult?: VerificationResult;
  verificationLoading?: boolean;
  verificationError?: boolean;
  /**
   * Whether the verify stage reported on the findings at all. Survives a
   * restored scan; `undefined` is the pre-feature state, and the cards say so
   * rather than guessing.
   */
  anomalyAssessmentRun?: boolean;
  /**
   * The posting's own stated details, verbatim from the scan response.
   *
   * These are the claims the verification categories test, so a scan restored
   * from history without them keeps its conclusions and loses the ground they
   * were drawn from. Copied straight from the response; never reconstructed,
   * and absent rather than empty when the scan reported none — an empty object
   * would assert that the posting claimed nothing.
   */
  attributes?: Record<string, string>;
  /** The searches the scan model proposed, capped at two by the backend. */
  searchQueries?: string[];
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
  anomalies: {
    flag: string;
    reasoning: string;
    severity: string;
    /** Taxonomy ID from the backend's `ANOMALY_CODES`, or `OTHER`. See `Anomaly.code`. */
    code?: string;
    /** A screened verbatim span of the posting. See `Anomaly.quote`. */
    quote?: string;
  }[];
  /**
   * What the posting states about itself, in the poster's own words. Only keys
   * the posting actually stated are present — an absent key means it said
   * nothing, which is a missing input rather than a finding.
   *
   * This is quoted back to the model as the claims its categories test, so
   * dropping it here is not a local loss: `Channel Match` — the one check that
   * can detect an impersonation — would have nothing to reason about.
   */
  attributes?: Record<string, string>;
  /**
   * The searches the scan model proposed, capped at 2. Issued by `/api/verify`
   * alongside the one query the backend builds from the employer's name.
   *
   * An empty array is a real state, not a failure: the model answered the
   * format without proposing a search, and the verification then runs on the
   * employer query alone.
   */
  search_queries?: string[];
  job_summary: string;
  error?: string | null;
  company_name?: string | null;
  risk_score?: number;
  risk_level?: ScanRiskLevel;
  /**
   * What the posting asks for: `ordinary`, `unclassified` or `prohibited`.
   * Decided by the backend from the findings and the posting's own attributes.
   * `''` or absent means the scan reported none — a reading recorded before
   * the field existed — and is never read as `ordinary`.
   */
  request_class?: string;
  sec_registration?: { company_name: string; sec_no: string; status: string; date_approved: string }[];
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

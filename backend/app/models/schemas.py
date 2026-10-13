from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


# How many images one scan may carry.
#
# The extension stops at `MAX_SCREENSHOTS` in `ScamScanView.tsx` and compresses
# each to a JPEG capped at 1280px. The API had no matching limit, so a request
# carrying hundreds of images was a single enormous vision call against a
# reasoning model. Vision tokens scale with pixel area, so the count is what
# bounds cost; the per-item length below only bounds memory.
#
# Kept equal to the frontend's limit on purpose. A backend stricter than the
# client it serves breaks ordinary use to solve a problem nobody has.
MAX_IMAGES_PER_SCAN = 4

# Per-image base64 ceiling. Matches `ResumeAnalysisRequest.file_base64`, so
# there is one convention for "one thing uploaded by a person" rather than two.
MAX_IMAGE_BASE64 = 5_000_000


# How many jobs one match request may carry.
#
# The extension sends `verifiedJobs`, which is `MAX_SCAN_HISTORY` at most — you
# can only match jobs you have scanned, so the two limits are the same number by
# construction. A server cap above that accepts work no real client could ask
# for; a server cap below it breaks ordinary use. A test reads the frontend
# constant and fails if the two drift apart.
MAX_JOBS_PER_MATCH = 20

# Per-field ceilings for one job in the match payload.
#
# A count cap alone does not bound the call: twenty 200KB job descriptions cost
# the same tokens as one enormous one. These are set well above what a scan
# actually produces — `job_summary` is one sentence — because a cap that is
# merely tight enough to be safe is one that breaks a real resume.
MAX_MATCH_JOB_ID = 200
MAX_MATCH_JOB_TITLE = 300
MAX_MATCH_JOB_SUMMARY = 5_000

# The resume half. A caller who cannot afford many jobs can send one job and an
# enormous resume instead, so bounding only the list leaves the cheaper door.
MAX_RESUME_SUMMARY = 5_000
MAX_RESUME_LIST_ITEMS = 100
MAX_RESUME_ITEM_CHARS = 200

# A short string, bounded on both length and count. Written once because
# `skills`, `job_titles` and `industries` are the same field three times over.
ResumeListItem = Annotated[str, StringConstraints(max_length=MAX_RESUME_ITEM_CHARS)]


class ScanRequest(BaseModel):
    # Bounded and rejected, never truncated. Dropping images 5-40 and scanning
    # the first four would return a result describing four images while claiming
    # to describe forty — a lie the reader cannot detect, which is worse than a
    # refusal because a refusal is visible.
    #
    # Both ends are bounded: `max_length` caps how many, and the annotated item
    # caps how large each one may be. Capping only the list leaves a single
    # enormous image through, which is the cheaper door.
    images_base64: list[Annotated[str, StringConstraints(max_length=MAX_IMAGE_BASE64)]] = Field(
        default=[], max_length=MAX_IMAGES_PER_SCAN
    )
    # The legacy spelling, still accepted. Capping only the list would leave the
    # cheapest door open: one call, one enormous image.
    image_base64: str = Field(default="", max_length=MAX_IMAGE_BASE64)
    language: str = "english"


class Anomaly(BaseModel):
    """One thing about a posting that differs from the ordinary case.

    Named for what it is — a divergence from expectation — rather than what it
    is taken to mean. "Red flag" was a conclusion delivered as a category label,
    so a low-severity observation about formatting was announced with the same
    force as a request for an advance fee. An anomaly asserts only that the
    posting contains something unusual; what that means is the reader's to draw.
    The severity field still carries the weight, unchanged.
    """

    flag: str
    reasoning: str
    severity: str
    # The search this finding relates to, when one was issued for it. Carried so
    # the scoring stage can tell "confirms something already counted" from
    # "reveals something new" — without it the double-count returns silently.
    query_ref: str = ""


class ScanResponse(BaseModel):
    valid: bool
    anomalies: list[Anomaly] = []
    # What the posting states about itself, in its own words. Only present keys
    # were stated; an absent key means the posting said nothing, which is a
    # different claim from stating nothing and is never scored.
    attributes: dict[str, str] = {}
    # The searches the scan model proposed, capped at `MAX_SEARCH_QUERIES`.
    # Issued by `/api/verify` in place of the scheme queries this module used to
    # build itself.
    #
    # Absent or empty is a real state, not a failure: a model that answered the
    # format without proposing a search leaves the verification running on the
    # employer query alone. That is thinner coverage reported as an ordinary
    # lookup, so it is worth watching rather than papering over.
    search_queries: list[str] = []
    job_summary: str = ""
    # Assessment of the posting's structure, separate from the role description.
    posting_analysis: str = ""
    error: str | None = None
    company_name: str | None = None
    sec_registration: list[dict] = []
    external_verification: dict = {}
    # Always populated: the posting's own indicators produce a verdict whether or
    # not an employer could be identified or looked up.
    risk_score: int = 0
    risk_level: str = "low"
    score_breakdown: dict = {}


class ScanTextRequest(BaseModel):
    text: str = Field(..., max_length=50_000)
    language: str = "english"


class AnalyzeOfferRequest(BaseModel):
    text: str = Field(..., max_length=50_000)
    company_name: str = ""
    language: str = "english"


class ResumeAnalysisRequest(BaseModel):
    file_base64: str = Field(..., max_length=5_000_000)
    file_type: str


class ResumeData(BaseModel):
    skills: list[ResumeListItem] = Field(default=[], max_length=MAX_RESUME_LIST_ITEMS)
    experience_years: float = 0
    job_titles: list[ResumeListItem] = Field(default=[], max_length=MAX_RESUME_LIST_ITEMS)
    industries: list[ResumeListItem] = Field(default=[], max_length=MAX_RESUME_LIST_ITEMS)
    summary: str = Field(default="", max_length=MAX_RESUME_SUMMARY)


class JobForMatch(BaseModel):
    id: str = Field(..., max_length=MAX_MATCH_JOB_ID)
    title: str = Field(..., max_length=MAX_MATCH_JOB_TITLE)
    summary: str = Field(default="", max_length=MAX_MATCH_JOB_SUMMARY)


class JobMatchResult(BaseModel):
    job_id: str
    score: int
    label: str
    skill_gaps: list[str] = []
    matched_skills: list[str] = []
    reasoning: str = ""
    experience_fit: str = ""
    industry_fit: str = ""
    recommended_actions: list[str] = []


class MatchRequest(BaseModel):
    resume: ResumeData
    # Rejected, never truncated: dropping the 21st job and matching the first
    # twenty returns a ranking of a subset while claiming to rank all of them.
    # The reader cannot tell the difference, which makes it worse than a
    # refusal.
    jobs: list[JobForMatch] = Field(default=[], max_length=MAX_JOBS_PER_MATCH)


class MatchResponse(BaseModel):
    matches: list[JobMatchResult] = []


class VerifyRequest(BaseModel):
    company_name: str = ""
    job_summary: str = ""
    anomalies: list[Anomaly] = []
    # What the scan read off the posting, in the poster's own words. Two uses,
    # and the same constraint binds both: an absent key means the posting said
    # nothing, which is a missing input and never earns a query or a check.
    #
    # It builds the scheme queries, and it is what categories 3, 4 and 6 test
    # their claims against. Without it in the prompt, `Channel Match` — the one
    # check that can tell a real employer from one borrowing its name — has
    # nothing to reason about and reports yellow on every posting.
    #
    # `| None` so an explicit JSON `null` is the same claim as `{}` and as an
    # omitted key. All three say "the posting stated nothing", and rejecting one
    # spelling of a missing input with a 422 fails the whole verification for a
    # detail that carries no verdict.
    attributes: dict[str, str] | None = {}
    # The searches the scan model proposed. `| None` for the same reason as
    # `attributes`: an explicit `null`, an omitted key and an empty list all
    # mean "the model proposed no search", and rejecting one spelling of that
    # with a 422 fails a whole verification over a detail carrying no verdict.
    #
    # Nothing here checks what a query *says*. The rule that a query must not
    # name a conclusion lives in both scan prompts and nowhere else - a
    # deliberate choice, and the reason a query reaching the provider is
    # unfiltered text from a model that read a job posting.
    search_queries: list[str] | None = []


class VerificationItem(BaseModel):
    label: str
    status: str  # "green" | "yellow" | "red"
    explanation: str
    # The result the model relied on, copied from the search results. A reader
    # can click through and check the finding instead of taking it on trust.
    source_title: str = ""
    source_url: str = ""


class VerificationEvidence(BaseModel):
    title: str
    url: str
    snippet: str


class VerificationResponse(BaseModel):
    items: list[VerificationItem] = []
    evidence: list[VerificationEvidence] = []
    report: str = ""
    recommendation: str = ""

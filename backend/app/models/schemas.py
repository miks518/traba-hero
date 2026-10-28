from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


# How many images one scan may carry.
#
# The extension stops at `MAX_SCREENSHOTS` in `hooks/useScanSession.ts` (it was
# in `ScamScanView.tsx` until the view was split into a composition and a
# lifecycle hook) and compresses
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

# The assessment vocabulary is the grid's three colours (`assessment.py`):
# `green`, `yellow`, `red`. The old `low`/`moderate`/`high`/`critical` ladder and
# the model-owned level it weighted are retired - the words were conclusions,
# and "Proceed" claimed a clearance the grid never measured. The panel's chip
# words for the colours are "Nothing found against it", "Caution" and
# "Contradicted", and the rule that produced the colour is in the breakdown.


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


# ── /api/verify ───────────────────────────────────────────────────────────────
#
# The only endpoint that spends from two budgets at once. Every field below is
# caller-supplied and reaches a provider: `company_name` becomes a search query,
# and `job_summary`, `anomalies` and `attributes` are quoted into the
# verification prompt as the claims its categories test.
#
# `anomalies` was the worst of them — an unbounded list of unbounded strings, so
# a caller could send one verification carrying thousands of anomalies with
# pages of text each and have all of it tokenised into a reasoning call.

MAX_VERIFY_COMPANY_NAME = 300
# Equal to `ScanTextRequest.text` on purpose. A verification fed from a posting
# must accept the same text a scan accepted, or a posting that scans fine fails
# to verify — after the reader has already paid for the scan.
MAX_VERIFY_JOB_SUMMARY = 50_000
MAX_VERIFY_ANOMALIES = 20
MAX_VERIFY_ANOMALY_TEXT = 2_000
MAX_VERIFY_ANOMALY_CODE = 100
MAX_VERIFY_ATTRIBUTES = 50
MAX_VERIFY_ATTRIBUTE_KEY = 100
MAX_VERIFY_ATTRIBUTE_VALUE = 2_000
# Each query reaches Tavily verbatim. The *count* is capped at two in
# `verification_flow`, where a client that is not this extension can be refused;
# this caps how long each one may be.
MAX_VERIFY_QUERY_CHARS = 500

VerifyQuery = Annotated[str, StringConstraints(max_length=MAX_VERIFY_QUERY_CHARS)]
AttributeKey = Annotated[str, StringConstraints(max_length=MAX_VERIFY_ATTRIBUTE_KEY)]
AttributeValue = Annotated[str, StringConstraints(max_length=MAX_VERIFY_ATTRIBUTE_VALUE)]


class VerifyAnomaly(BaseModel):
    """One of the posting's findings, as the caller reports them.

    Deliberately not `Anomaly`. That type is what the backend *emits* in a scan
    response, and bounding it here would silently constrain our own output —
    tightening a response schema to protect an input path is how a long but
    legitimate finding turns into a 500 on the way back to the reader.
    """

    flag: str = Field(..., max_length=MAX_VERIFY_ANOMALY_TEXT)
    reasoning: str = Field(default="", max_length=MAX_VERIFY_ANOMALY_TEXT)
    query_ref: str = Field(default="", max_length=MAX_VERIFY_QUERY_CHARS)
    # The taxonomy ID the scan emitted, and the posting span that decided the
    # finding. Both are forwarded so the verify prompt can put the finding and
    # its own quote in front of the model, rather than asking it to assess a
    # paraphrase it cannot see the source of.
    code: str = Field(default="", max_length=MAX_VERIFY_ANOMALY_CODE)
    quote: str = Field(default="", max_length=MAX_VERIFY_ANOMALY_TEXT)


class AnomalyAssessment(BaseModel):
    """The verify stage's assessment on one posting finding.

    Internal shape, not a request model. `index` is 1-based and matches the
    numbered findings block the prompt builds. `status` is one of `stale`,
    `yellow`, `red`; the parser validates it before constructing one, because a
    model that answers with a different word must degrade to amber rather than
    reaching the wire as a status the panel has no rendering for.
    """

    index: int
    status: str
    finding: str = ""
    source_title: str = ""
    source_url: str = ""


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
    # The Advanced-scan toggle. `True` turns the model's reasoning on for this
    # one request, whatever the deployment's `AI_REASONING_ENABLED` says. It
    # costs minutes, not credits - the disclaimer on the checkbox is the honest
    # label for that.
    thinking: bool = False


class Anomaly(BaseModel):
    """One thing about a posting that differs from the ordinary case.

    Named for what it is — a divergence from expectation — rather than what it
    is taken to mean. "Red flag" was a conclusion delivered as a category label,
    so a formatting note was announced with the same force as a request for an
    advance fee. An anomaly asserts only that the posting contains something
    unusual; what that means is the reader's to draw.

    There is no severity field. The scan's own high/mid/low ladder used to ride
    on this object, and nothing downstream decided anything by it: the verify
    assessment is the request-class × establishment grid in `assessment.py`,
    the panel's card states come from the evidence, and the over-cap selection
    ranks by the taxonomy `code`. A model asked to price a judgement nothing
    reads as a price is the shape `docs/decisions/scan-severity-removal.md`
    records.
    """

    flag: str
    reasoning: str
    # The search this finding relates to, when one was issued for it. Carried so
    # the scoring stage can tell "confirms something already counted" from
    # "reveals something new" — without it the double-count returns silently.
    query_ref: str = ""
    # The taxonomy ID from `app.services.anomaly_codes.ANOMALY_CODES`, or OTHER
    # when the model's answer was outside the set, or "" when the response
    # carried no code at all.
    #
    # Optional on read, and that is deliberate: scan history predates this field,
    # so requiring it would render every stored scan unloadable. "" is not folded
    # into OTHER, because absent and OTHER are different claims — see
    # `normalise_code`.
    code: str = ""
    # A verbatim span of the posting that decided this finding, quoted for the
    # reader rather than summarised.
    #
    # Empty when the model emitted none, when the span carried a word the
    # posting could not have written about itself, or — on the text path only —
    # when the span could not be found in the submitted text. An empty quote
    # degrades the card to its explanation; a fabricated one is the failure this
    # field exists to prevent, so it is never rendered.
    quote: str = ""
    # The reason the posting gives for a fee, verbatim. A fact, never a
    # judgement: "medical clearance" is what the posting says.
    fee_reason: str = ""


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
    # Now produced by the verification model over the posting's findings and the
    # retrieved evidence together. It used to be `risk_calculator`'s arithmetic
    # over a severity ladder, which priced the *category* of an anomaly rather
    # than the situation: a processing fee was worth 40 whether it was demanded
    # by a ghost or by a placement agency, because the ladder had no way to ask
    # who was asking. AHP was retired along with it - the method assumes a fixed
    # commensurable variable set, and an unstructured posting does not have one.
    #
    # `None` is a real value and means nothing was assessed - no employer could
    # be named, or the lookup did not complete. It is not "low". The frontend
    # already renders `null` as Unverified and excludes it from resume matching.
    # Both nullable, and both None for the ordinary path: no stage produces a
    # number, and the assessment itself is the grid's colour word carried in the
    # `assessment` field. Kept on the wire because stored scan
    # history carries it, and removing a key needs a migration for that.
    risk_score: int | None = None
    risk_level: str | None = None
    score_breakdown: dict = {}
    # What the posting asks for, decided by `request_class.classify_request`
    # from the findings and the posting's own attributes. "" means the scan did
    # not report one — a response recorded before the field existed — and is
    # never read as `ordinary`.
    request_class: str = ""


class ScanTextRequest(BaseModel):
    text: str = Field(..., max_length=50_000)
    language: str = "english"
    # The Advanced-scan toggle, same meaning as on `ScanRequest`.
    thinking: bool = False


class AnalyzeOfferRequest(BaseModel):
    text: str = Field(..., max_length=50_000)
    company_name: str = ""
    language: str = "english"
    # The Advanced-scan toggle, same meaning as on `ScanRequest`. The offer pass
    # is the scan pipeline's no-employer branch, so the toggle follows it.
    thinking: bool = False
    # The scan's findings, forwarded so the offer pass can compute a request
    # class from them rather than only from the codes the model emits. The
    # model's codes are a second opinion; the scan's anomalies are the
    # primary input, the same way verify reads them.
    anomalies: list[VerifyAnomaly] = Field(default=[], max_length=MAX_VERIFY_ANOMALIES)


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
    company_name: str = Field(default="", max_length=MAX_VERIFY_COMPANY_NAME)
    job_summary: str = Field(default="", max_length=MAX_VERIFY_JOB_SUMMARY)
    anomalies: list[VerifyAnomaly] = Field(default=[], max_length=MAX_VERIFY_ANOMALIES)
    # The Advanced-scan toggle, forwarded from the scan that produced these
    # findings. The whole initiated pipeline follows the button: a scan started
    # with thinking off runs its verification with thinking off too, whatever
    # AI_REASONING_ENABLED says.
    thinking: bool = False
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
    # detail that carries no assessment.
    attributes: dict[AttributeKey, AttributeValue] | None = Field(
        default={}, max_length=MAX_VERIFY_ATTRIBUTES
    )
    # The searches the scan model proposed. `| None` for the same reason as
    # `attributes`: an explicit `null`, an omitted key and an empty list all
    # mean "the model proposed no search", and rejecting one spelling of that
    # with a 422 fails a whole verification over a detail carrying no assessment.
    #
    # Nothing here checks what a query *says*. The rule that a query must not
    # name a conclusion lives in both scan prompts and nowhere else - a
    # deliberate choice, and the reason a query reaching the provider is
    # unfiltered text from a model that read a job posting.
    # Length only, deliberately not the count.
    #
    # The count is capped at `lm_client.MAX_SEARCH_QUERIES` inside
    # `verification_flow`, and that has to stay the only place it is enforced:
    # a schema cap turns an over-long list into a 422, so the flow's own
    # truncation becomes unreachable and the defence against a client that is
    # not this extension is untested. Both gates, but only one of them decides.
    search_queries: list[VerifyQuery] | None = []

    # Original image(s) from the scan, passed through to preserve visual context.
    # Mirrors `ScanRequest.images_base64`: same count and per-image limits.
    images_base64: list[Annotated[str, StringConstraints(max_length=MAX_IMAGE_BASE64)]] = Field(
        default=[], max_length=MAX_IMAGES_PER_SCAN
    )


# The four establishment states, plus the retired-by-the-record state.
# `green`/`yellow`/`red` are retired; they were the model's statuses and
# conflated the observation with the assessment. The new vocabulary is code-owned.
VERIFICATION_STATES = ("confirmed", "supported", "unknown", "contradicted", "stale")


class VerificationItem(BaseModel):
    label: str
    status: Literal[VERIFICATION_STATES]
    explanation: str
    # The result the model relied on, copied from the search results. A reader
    # can click through and check the finding instead of taking it on trust.
    source_title: str = ""
    source_url: str = ""
    # Code-owned, and only used by Channel Match. The values are the rule that
    # produced the status (`government`, `lookalike`, `free_email`,
    # `free_email_with_findings`, `unconfirmed`, `unconfirmed_with_findings`,
    # `match`, `no_data`). Empty on every other category and on a stored response
    # from before the facts split. `assessment.py` reads this for the strong-channel
    # floor; the panel ignores it.
    escalation: str = ""


class VerificationEvidence(BaseModel):
    title: str
    url: str
    snippet: str


class VerificationResponse(BaseModel):
    items: list[VerificationItem] = []
    evidence: list[VerificationEvidence] = []
    report: str = ""
    recommendation: str = ""

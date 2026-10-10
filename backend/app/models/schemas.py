from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    image_base64: str = ""
    images_base64: list[str] = []
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
    # Up to three queries built from those attributes. Empty when the posting
    # stated nothing checkable.
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
    skills: list[str] = []
    experience_years: float = 0
    job_titles: list[str] = []
    industries: list[str] = []
    summary: str = ""


class JobForMatch(BaseModel):
    id: str
    title: str
    summary: str = ""


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
    jobs: list[JobForMatch] = []


class MatchResponse(BaseModel):
    matches: list[JobMatchResult] = []


class VerifyRequest(BaseModel):
    company_name: str = ""
    job_summary: str = ""
    anomalies: list[Anomaly] = []


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

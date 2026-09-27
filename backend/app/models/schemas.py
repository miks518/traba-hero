from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    image_base64: str = ""
    images_base64: list[str] = []
    language: str = "english"


class RedFlag(BaseModel):
    flag: str
    reasoning: str
    severity: str


class ScanResponse(BaseModel):
    valid: bool
    red_flags: list[RedFlag] = []
    job_summary: str = ""
    # Assessment of the posting's structure, separate from the role description.
    posting_analysis: str = ""
    error: str | None = None
    company_name: str | None = None
    sec_registration: list[dict] = []
    web_search: dict = {}
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
    red_flags: list[RedFlag] = []


class VerificationItem(BaseModel):
    label: str
    status: str  # "green" | "yellow" | "red"
    explanation: str


class VerificationResponse(BaseModel):
    items: list[VerificationItem] = []
    report: str = ""
    recommendation: str = ""
    search_log: list[dict] = []


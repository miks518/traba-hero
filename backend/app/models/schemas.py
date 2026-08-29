from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    image_base64: str = Field(..., max_length=5_000_000)
    language: str = "english"


class RedFlag(BaseModel):
    flag: str
    reasoning: str
    severity: str


class ScanResponse(BaseModel):
    valid: bool
    verdict_percentage: int = 0
    red_flags: list[RedFlag] = []
    analysis: str = ""
    job_summary: str = ""
    error: str | None = None


class ScanTextRequest(BaseModel):
    text: str = Field(..., max_length=50_000)
    language: str = "english"


class TestTextRequest(BaseModel):
    text: str = Field(..., max_length=50_000)


class TestTextResponse(BaseModel):
    raw_output: str
    model: str


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


class MatchRequest(BaseModel):
    resume: ResumeData
    jobs: list[JobForMatch] = []


class MatchResponse(BaseModel):
    matches: list[JobMatchResult] = []




import asyncio
import base64
import io
import json
import logging
import time as _time
import zipfile
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.config import settings
from app.models.schemas import (
    ScanRequest, ScanResponse, ScanTextRequest,
    ResumeAnalysisRequest, ResumeData,
    MatchRequest, MatchResponse,
    RedFlag,
)
from app.services.image import decode_base64_image
from app.services.lm_client import chat, chat_json, chat_stream_pieces, _parse_custom, _parse_json
from app.services.web_search import _extract_company_name, search_job_posting, search_job_posting_data
from app.services.sec_api import sec_context, sec_data
from app.services.email_verifier import verify_emails_in_text
from app.exceptions import InvalidImageError
from app.rate_limit import limiter

log = logging.getLogger("trabahero")
router = APIRouter()

def _extract_resume_text(file_base64: str, file_type: str) -> str:
    """Extract raw text from an uploaded resume file (non-image types)."""
    file_type = file_type.lower()
    try:
        raw = base64.b64decode(file_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="The uploaded file could not be read.")

    if file_type == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    if file_type == "txt":
        return raw.decode("utf-8", errors="replace")
    if file_type == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
            xml = re.sub(r"<w:p[ >]", "\n", xml)
            xml = re.sub(r"<[^>]+>", "", xml)
            return xml
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read the .docx file. Convert it to PDF or TXT and try again.")
    raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}. Use PDF, TXT, DOCX, or an image.")

FALLBACK_SYSTEM_PROMPT = """You are a professional job scanner — an expert at verifying job postings and detecting employment scams. Your role is to protect job seekers by analyzing job postings thoroughly before they apply.

Analyze the provided job posting thoroughly. Verify the company name, contact methods, role responsibilities, and compensation to detect any fraud or red flags.

Respond strictly using this labeled section format:

VALID: true
VERDICT_PERCENTAGE: 0
END FLAGS
ANALYSIS:
1-3 sentence verdict explaining the risk assessment and legitimacy of the posting.
END ANALYSIS
JOB SUMMARY:
3-5 sentence extraction of the posting — job title, company, key responsibilities, required skills, and qualifications.
END JOB SUMMARY

Field rules:
- VALID: true if this is a genuine job posting or job advertisement, false if it is not.
- VERDICT_PERCENTAGE: integer from 0 (completely legitimate/safe) to 100 (definite scam). For legitimate jobs, this should be low (e.g. 0-25).
- RED FLAGS:
  * CRITICAL: If the job posting is legitimate or has NO red flags, DO NOT output any RED FLAG lines. Keep the flags section empty by immediately outputting END FLAGS.
  * ONLY output a RED FLAG line if a concrete scam indicator or high-risk issue is genuinely found in the scanned posting.
  * Never invent red flags or output placeholder/default red flags.
  * Format (only when genuine red flags are detected):
    RED FLAG: label | reasoning | severity
    (Severity must be low, mid, or high)
- ANALYSIS: Brief explanation of the risk level and key findings.
- JOB SUMMARY: 3-5 sentence extraction of the posting (job title, company, key responsibilities, required skills, qualifications)."""


def load_system_prompt() -> str:
    """Load system prompt from SYSTEM_PROMPT.md in the project root with fallback."""
    root_prompt_path = Path(__file__).resolve().parents[3] / "SYSTEM_PROMPT.md"
    if root_prompt_path.is_file():
        try:
            content = root_prompt_path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception as e:
            log.warning("Could not read SYSTEM_PROMPT.md at %s: %s", root_prompt_path, e)
    return FALLBACK_SYSTEM_PROMPT


SCAN_OUTPUT_FORMAT = """\
Respond strictly using this labeled section format:

VALID: true
VERDICT_PERCENTAGE: 0
END FLAGS
ANALYSIS:
1-3 sentence verdict explaining the risk assessment and legitimacy of the posting.
END ANALYSIS
JOB SUMMARY:
3-5 sentence extraction of the posting - job title, company, key responsibilities, required skills, qualifications.
END JOB SUMMARY

Field rules:
- VALID: true if the image/text is a job posting, false if it is not a job posting.
- VERDICT_PERCENTAGE: integer from 0 (completely legitimate) to 100 (definitely a scam).
- RED FLAGS:
  * CRITICAL: If the posting is legitimate or has NO red flags, DO NOT output any RED FLAG lines. Keep the flags section empty by immediately outputting END FLAGS.
  * ONLY output a RED FLAG line if a concrete scam indicator or high-risk issue is genuinely found in the scanned posting.
  * Never invent red flags or output placeholder/default red flags.
  * Format (only when genuine red flags are detected):
    RED FLAG: label | reasoning | severity
    (Severity must be low, mid, or high)
- ANALYSIS: brief summary of the risk level and key findings.
- JOB SUMMARY: brief extraction of the posting used to match candidates to the job later."""

IMAGE_SCAN_INSTRUCTION = "Verify this job posting screenshot. First decide if it is actually a job posting (VALID: true) or not (VALID: false). Then analyze it for scam indicators. Extract a concise job_summary (3-5 sentences) covering the job title, company, key responsibilities, required skills, and qualifications."

TEXT_SCAN_INSTRUCTION = "Verify this job posting:\n{text}\n\nFirst decide if it is actually a job posting (VALID: true) or not (VALID: false). Then analyze it for scam indicators.\n\nExtract a concise job_summary (3-5 sentences) covering the job title, company, key responsibilities, required skills, and qualifications."

RESUME_INSTRUCTION = """Analyze this resume and return ONLY valid JSON (no markdown):
{
  "skills": ["Skill 1", "Skill 2", "..."],
  "experience_years": 0.0,
  "job_titles": ["Previous Job Title 1", "..."],
  "industries": ["Industry 1", "..."],
  "summary": "Brief 1-2 sentence summary of the candidate's profile"
}
Extract all technical and soft skills. Estimate experience years from the timeline."""

MATCH_INSTRUCTION = """Compare the candidate's resume against each job posting and return ONLY valid JSON array (no markdown):
[
  {{
    "job_id": "...",
    "score": 0-100,
    "label": "High Compatibility / Medium Compatibility / Low Compatibility",
    "skill_gaps": ["Missing skill 1", "..."],
    "matched_skills": ["Matching skill 1", "..."],
    "reasoning": "Short, clear explanation. Use 1-2 sentences max. Mention what fits and what doesn't.",
    "experience_fit": "Good Fit / Overqualified / Underqualified",
    "industry_fit": "Strong / Moderate / Weak",
    "recommended_actions": ["Specific actionable step 1", "Specific actionable step 2"]
  }}
]
Score based on: skills overlap (primary, compare resume skills against each job's summary), industry fit, experience level.
For reasoning: be concise and specific. State what matches well and what's missing.
For recommended_actions: give concrete steps (e.g., "Add a Python certification", "Include 2 relevant projects in your portfolio").

Candidate Resume:
Skills: {skills}
Experience: {experience} years
Job Titles: {titles}
Industries: {industries}
Summary: {summary}

Jobs to match against:
{jobs}"""

def _red_flags(flags: list) -> list[RedFlag]:
    return [RedFlag(**f) for f in flags]


def _language_instruction(language: str) -> str:
    lang = (language or "").strip().lower()
    if lang in ("tagalog", "filipino", "tl"):
        return "Respond in Tagalog. Write the ANALYSIS, JOB SUMMARY, and all RED FLAG label/reasoning in Tagalog. Keep the VALID, VERDICT_PERCENTAGE, and section labels exactly as shown above."
    return "Respond in English."


def _scan_response(result: dict) -> ScanResponse:
    return ScanResponse(
        valid=result.get("valid", False),
        verdict_percentage=result.get("verdict_percentage", 50),
        red_flags=_red_flags(result.get("red_flags", [])),
        analysis=result.get("analysis", ""),
        job_summary=result.get("job_summary", ""),
        error=result.get("error"),
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _scan_event_stream(messages: list, max_tokens: int = 2048, company_data: dict | None = None, original_text: str = "") -> str:
    """Stream an LM Studio scan, emitting SSE progress events and a final result."""
    yield _sse({"type": "progress", "percent": 5, "stage": "Preparing request"})
    first = True
    pieces: list[str] = []
    token_count = 0
    try:
        deadline = _time.monotonic() + 300.0
        async for piece in chat_stream_pieces(messages, max_tokens, 0.2):
            if _time.monotonic() > deadline:
                raise asyncio.TimeoutError()
            pieces.append(piece)
            token_count += 1
            if first:
                first = False
                yield _sse({"type": "progress", "percent": 30, "stage": "Sent to AI"})
            elif token_count % 4 == 0:
                pct = min(88, 30 + int(token_count / 12))
                yield _sse({"type": "progress", "percent": pct, "stage": "Analyzing"})
    except asyncio.TimeoutError:
        yield _sse({"type": "error", "error": "The AI service took too long to respond. Please try again."})
        return
    except Exception as e:  # noqa: BLE001
        log.error("Scan stream error: %s: %s", type(e).__name__, e)
        yield _sse({"type": "error", "error": "Hmm, I can't scan at the moment. Please try again."})
        return

    message_content = "".join(pieces).strip()
    message_content = re.sub(r"<\|tool_call\|>.*?(?=<\|tool_call\|>|$)", "", message_content, flags=re.DOTALL).strip()
    log.info("Raw model output (first 500 chars): %s", message_content[:500])
    result = _parse_custom(message_content) if message_content else None
    log.info("Parsed custom result: %s", result)
    if isinstance(result, dict):
        yield _sse({"type": "progress", "percent": 95, "stage": "Parsing result"})
        resp = _scan_response(result).model_dump()
        if company_data:
            resp.update(company_data)
        if original_text:
            email_checks = verify_emails_in_text(original_text)
            resp["email_verifications"] = [
                {"email": c.email, "domain": c.domain, "syntax_valid": c.syntax_valid,
                 "has_mx_records": c.has_mx_records, "is_disposable": c.is_disposable,
                 "risk": c.risk, "reason": c.reason}
                for c in email_checks
            ]
        yield _sse({"type": "result", "data": resp})
        return
    fallback = _parse_json(message_content) if message_content else None
    if isinstance(fallback, dict):
        yield _sse({"type": "progress", "percent": 95, "stage": "Parsing result"})
        resp = _scan_response(fallback).model_dump()
        if company_data:
            resp.update(company_data)
        if original_text:
            email_checks = verify_emails_in_text(original_text)
            resp["email_verifications"] = [
                {"email": c.email, "domain": c.domain, "syntax_valid": c.syntax_valid,
                 "has_mx_records": c.has_mx_records, "is_disposable": c.is_disposable,
                 "risk": c.risk, "reason": c.reason}
                for c in email_checks
            ]
        yield _sse({"type": "result", "data": resp})
        return
    yield _sse({"type": "error", "error": "The AI returned an unreadable response. Please try again."})


@router.post("/api/scan")
@limiter.limit("5/minute")
async def scan(req: ScanRequest, request: Request):
    if not req.image_base64:
        raise InvalidImageError()
    try:
        decode_base64_image(req.image_base64)
    except ValueError:
        raise InvalidImageError()

    log.info("Scan: sending image to LM Studio")
    messages = [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": [
            {"type": "text", "text": IMAGE_SCAN_INSTRUCTION + "\n\n" + SCAN_OUTPUT_FORMAT + "\n\n" + _language_instruction(req.language)},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{req.image_base64}"}},
        ]},
    ]
    return StreamingResponse(_scan_event_stream(messages, original_text=""), media_type="text/event-stream")


@router.post("/api/scan-text")
@limiter.limit("5/minute")
async def scan_text(req: ScanTextRequest, request: Request):
    if not req.text.strip():
        return ScanResponse(valid=False, verdict_percentage=100, analysis="No text provided.")
    log.info("Text scan: %d chars to LM Studio", len(req.text))

    # Pre-search: try to find company info before sending to AI
    search_context = search_job_posting(req.text)
    web_data = search_job_posting_data(req.text)
    user_content = TEXT_SCAN_INSTRUCTION.replace("{text}", req.text) + "\n\n" + SCAN_OUTPUT_FORMAT + "\n\n" + _language_instruction(req.language)
    if search_context:
        user_content = search_context + "\n\n" + user_content

    # SEC registry lookup for the extracted company name
    company = _extract_company_name(req.text)
    sec_matches = []
    if company:
        sec = sec_context(company)
        sec_matches = sec_data(company)
        if sec:
            user_content = sec + "\n\n" + user_content

    company_payload = {
        "company_name": web_data.get("company_name") or company,
        "sec_registration": sec_matches,
        "web_search": web_data.get("results", {}),
    }

    messages = [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": user_content},
    ]
    return StreamingResponse(_scan_event_stream(messages, company_data=company_payload, original_text=req.text), media_type="text/event-stream")


@router.post("/api/analyze-resume", response_model=ResumeData)
@limiter.limit("5/minute")
async def analyze_resume_endpoint(req: ResumeAnalysisRequest, request: Request):
    content = []
    if req.file_type.lower() in ("png", "jpg", "jpeg"):
        content.append({"type": "image_url", "image_url": {"url": f"data:image/{req.file_type.lower()};base64,{req.file_base64}"}})
        content.append({"type": "text", "text": RESUME_INSTRUCTION})
    else:
        text = _extract_resume_text(req.file_base64, req.file_type)
        content.append({"type": "text", "text": f"{RESUME_INSTRUCTION}\n\nResume text:\n{text[:8000]}"})
    result = await chat_json([{"role": "user", "content": content}], max_tokens=1024)
    return ResumeData(**(result if isinstance(result, dict) else {}))


@router.post("/api/match-resume", response_model=MatchResponse)
@limiter.limit("10/minute")
async def match_resume_endpoint(req: MatchRequest, request: Request):
    prompt = MATCH_INSTRUCTION.format(
        skills=", ".join(req.resume.skills),
        experience=req.resume.experience_years,
        titles=", ".join(req.resume.job_titles),
        industries=", ".join(req.resume.industries),
        summary=req.resume.summary,
        jobs=json.dumps([{"id": j.id, "title": j.title, "summary": j.summary} for j in req.jobs], indent=2),
    )
    result = await chat_json([{"role": "user", "content": prompt}], max_tokens=2048)
    if isinstance(result, list):
        return MatchResponse(matches=[r for r in result if isinstance(r, dict)])
    if isinstance(result, dict):
        return MatchResponse(matches=[result])
    return MatchResponse()

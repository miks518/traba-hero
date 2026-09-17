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
    JobMatchResult,
    RedFlag,
)
from app.services.image import decode_base64_image
from app.services.lm_client import chat, chat_json, chat_resume, chat_stream_pieces, _parse_custom, _parse_json
from app.services.web_search import _extract_company_name, search_job_posting, search_job_posting_data
from app.services.sec_api import sec_context, sec_data
from app.services.email_verifier import verify_emails_in_text
from app.services.external_verifier import verify_all, verification_to_dict
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
1-2 short sentences. State the verdict and the single most important reason.
END ANALYSIS
JOB SUMMARY:
2-3 short sentences: job title, company, and only the key requirements.
END JOB SUMMARY

Be concise: no greetings, no preamble, no repetition, no markdown.

Field rules:
- VALID: true if this is a genuine job posting or job advertisement, false if it is not.
- VERDICT_PERCENTAGE: integer from 0 (completely legitimate/safe) to 100 (definite scam). For legitimate jobs, this should be low (e.g. 0-25).
- RED FLAGS:
  * CRITICAL: If the posting is legitimate or has NO red flags, DO NOT output any RED FLAG lines. Keep the flags section empty by immediately outputting END FLAGS.
  * ONLY output a RED FLAG line if a concrete scam indicator or high-risk issue is genuinely found in the scanned posting.
  * Never invent red flags or output placeholder/default red flags.
  * Keep each label short (3-6 words) and each reasoning to ONE short sentence (max 15 words).
  * If the posting does NOT mention a salary, do NOT flag "high salary" or "too-good salary" — only flag salary if a specific amount is stated and it is unrealistic for the role.
  * Gmail, Yahoo, and similar free email providers are COMMON and ACCEPTABLE in the Philippines, especially for small businesses, manpower agencies, and direct employers. Do NOT flag Gmail as a red flag by itself — only flag it if the email address is clearly fake, suspicious, or unrelated to the company name.
  * CRITICAL SEVERITY (use "high"): Any mention of upfront fees, payment required, money collection, "processing fee", "training fee", "registration fee", "assessment fee", "medical fee", "uniform fee", or any form of payment from the applicant. Also flag: "will deduct from salary", "refundable deposit", "admin fee", "processing charge". This is ALWAYS a scam — use severity "high".
  * Format (only when genuine red flags are detected):
    RED FLAG: label | reasoning | severity
    (Severity must be low, mid, or high)
- ANALYSIS: 1-2 short sentences only.
- JOB SUMMARY: 2-3 short sentences only."""


def load_system_prompt() -> str:
    """Load system prompt from SYSTEM_PROMPT.md in the project root with fallback."""
    root_prompt_path = Path(__file__).resolve().parents[2] / "SYSTEM_PROMPT.md"
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
1-2 short sentences. State the verdict and the single most important reason.
END ANALYSIS
JOB SUMMARY:
2-3 short sentences: job title, company, and only the key requirements.
END JOB SUMMARY

Be concise: no greetings, no preamble, no repetition, no markdown.

Field rules:
- VALID: true if the image/text is a job posting, false if it is not a job posting.
- VERDICT_PERCENTAGE: integer from 0 (completely legitimate) to 100 (definitely a scam).
- RED FLAGS:
  * CRITICAL: If the posting is legitimate or has NO red flags, DO NOT output any RED FLAG lines. Keep the flags section empty by immediately outputting END FLAGS.
  * ONLY output a RED FLAG line if a concrete scam indicator or high-risk issue is genuinely found in the scanned posting.
  * Never invent red flags or output placeholder/default red flags.
  * Keep each label short (3-6 words) and each reasoning to ONE short sentence (max 15 words).
  * If the posting does NOT mention a salary, do NOT flag "high salary" or "too-good salary" — only flag salary if a specific amount is stated and it is unrealistic for the role.
  * Gmail, Yahoo, and similar free email providers are COMMON and ACCEPTABLE in the Philippines, especially for small businesses, manpower agencies, and direct employers. Do NOT flag Gmail as a red flag by itself — only flag it if the email address is clearly fake, suspicious, or unrelated to the company name.
  * CRITICAL SEVERITY (use "high"): Any mention of upfront fees, payment required, money collection, "processing fee", "training fee", "registration fee", "assessment fee", "medical fee", "uniform fee", or any form of payment from the applicant. Also flag: "will deduct from salary", "refundable deposit", "admin fee", "processing charge". This is ALWAYS a scam — use severity "high".
  * Format (only when genuine red flags are detected):
    RED FLAG: label | reasoning | severity
    (Severity must be low, mid, or high)
- ANALYSIS: 1-2 short sentences only.
- JOB SUMMARY: 2-3 short sentences only."""

IMAGE_SCAN_INSTRUCTION = "Verify this job posting screenshot. First decide if it is actually a job posting (VALID: true) or not (VALID: false). Then analyze it for scam indicators. If several images are provided, treat them as parts of the same posting. Extract a brief job_summary (2-3 sentences) covering the job title, company, and key requirements."

TEXT_SCAN_INSTRUCTION = "Verify this job posting:\n{text}\n\nFirst decide if it is actually a job posting (VALID: true) or not (VALID: false). Then analyze it for scam indicators.\n\nExtract a brief job_summary (2-3 sentences) covering the job title, company, and key requirements."

RESUME_INSTRUCTION = """Analyze this resume and extract candidate details. Respond strictly using this labeled format (NO curly braces or JSON):

SKILLS: skill 1, skill 2, skill 3, skill 4
EXPERIENCE_YEARS: number (e.g. 3.5 or 0)
JOB_TITLES: job title 1, job title 2
INDUSTRIES: industry 1, industry 2
SUMMARY:
1-2 sentence summary of the candidate's professional profile and background.
END SUMMARY

Rules:
- SKILLS: Comma-separated list of all relevant technical and soft skills.
- EXPERIENCE_YEARS: Estimated total years of relevant work experience (number only).
- JOB_TITLES: Comma-separated list of past or target job titles found in the resume.
- INDUSTRIES: Comma-separated list of industries (e.g. Information Technology, Healthcare, Customer Service).
- SUMMARY: Concise 1-2 sentence professional overview."""

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
    out: list[RedFlag] = []
    if not isinstance(flags, list):
        return out
    for f in flags:
        if isinstance(f, str):
            f = {"flag": f}
        if not isinstance(f, dict):
            continue
        name = str(f.get("flag") or "").strip()
        if not name:
            continue
        reasoning = str(f.get("reasoning") or "").strip()
        severity = str(f.get("severity") or "").strip().lower()
        out.append(RedFlag(flag=name, reasoning=reasoning, severity=severity or "mid"))
    return out


# Weighted scoring — placeholder weights (to be replaced with AHP-derived weights after expert survey)
# HIGH=3, MID=2, LOW=1 → max possible = 3×N flags, normalized to 0-100
SEVERITY_WEIGHTS = {"high": 3, "mid": 2, "low": 1}


def _calculate_score(flags: list[RedFlag]) -> tuple[int, dict]:
    """Calculate weighted scam score from red flags. Returns (score, breakdown)."""
    high_count = sum(1 for f in flags if f.severity == "high")
    mid_count = sum(1 for f in flags if f.severity == "mid")
    low_count = sum(1 for f in flags if f.severity == "low")
    raw = (high_count * SEVERITY_WEIGHTS["high"] +
           mid_count * SEVERITY_WEIGHTS["mid"] +
           low_count * SEVERITY_WEIGHTS["low"])
    # Normalize to 0-100: 1 HIGH=3→25, 2 HIGH=6→50, 3 HIGH=9→75
    # Minimum score of 20 when any flags exist so it never reads as "legitimate"
    score = min(100, raw * 25 // 3) if raw > 0 else 0
    if flags and score < 20:
        score = 20
    breakdown = {
        "high_count": high_count,
        "mid_count": mid_count,
        "low_count": low_count,
        "high_weight": SEVERITY_WEIGHTS["high"],
        "mid_weight": SEVERITY_WEIGHTS["mid"],
        "low_weight": SEVERITY_WEIGHTS["low"],
        "formula": f"({high_count}×3) + ({mid_count}×2) + ({low_count}×1) = {raw}",
        "normalized_score": score,
    }
    return score, breakdown


def _language_instruction(language: str) -> str:
    lang = (language or "").strip().lower()
    if lang in ("tagalog", "filipino", "tl"):
        return "Respond in Tagalog. Write the ANALYSIS, JOB SUMMARY, and all RED FLAG label/reasoning in Tagalog. Keep the VALID, VERDICT_PERCENTAGE, and section labels exactly as shown above."
    return "Respond in English."


def _scan_response(result: dict, external: dict | None = None) -> ScanResponse:
    flags = _red_flags(result.get("red_flags", []))
    calc_score, breakdown = _calculate_score(flags)
    return ScanResponse(
        valid=result.get("valid", False),
        verdict_percentage=calc_score,
        red_flags=flags,
        analysis=result.get("analysis", ""),
        job_summary=result.get("job_summary", ""),
        error=result.get("error"),
        score_breakdown=breakdown,
        external_verification=external or {},
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _scan_event_stream(messages: list, max_tokens: int | None = None, company_data: dict | None = None, original_text: str = "") -> str:
    """Stream an AI scan, emitting SSE progress events and a final result."""
    yield _sse({"type": "progress", "percent": 5, "stage": "Preparing request"})
    first = True
    pieces: list[str] = []
    token_count = 0
    try:
        deadline = _time.monotonic() + 300.0
        async for piece in chat_stream_pieces(messages, max_tokens=max_tokens):
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

    try:
        message_content = "".join(pieces).strip()
        # Strip web-search tool-call blocks (opener + closer share the same marker)
        message_content = re.sub(r"<\|tool_call\|>.*?<\|tool_call\|>", "", message_content, flags=re.DOTALL)
        message_content = message_content.replace("<|tool_call|>", "").strip()
        log.info("Raw model output (first 500 chars): %s", message_content[:500])

        result = _parse_custom(message_content) if message_content else None
        if not isinstance(result, dict):
            result = _parse_json(message_content) if message_content else None
        if not isinstance(result, dict):
            yield _sse({"type": "error", "error": "The AI returned an unreadable response. Please try again."})
            return

        log.info("Parsed scan result: %s", result)
        yield _sse({"type": "progress", "percent": 95, "stage": "Parsing result"})

        email_data: list[dict] = []
        ext_verification: dict = {}
        verify_text = original_text or (result.get("job_summary", "") + " " + result.get("analysis", ""))
        if verify_text.strip():
            email_checks = verify_emails_in_text(verify_text)
            email_data = [
                {"email": c.email, "domain": c.domain, "syntax_valid": c.syntax_valid,
                 "has_mx_records": c.has_mx_records, "is_disposable": c.is_disposable,
                 "risk": c.risk, "reason": c.reason}
                for c in email_checks
            ]
            company_name = company_data.get("company_name") if company_data else ""
            ext_verification = verification_to_dict(verify_all(verify_text, company_name))

        resp = _scan_response(result, ext_verification).model_dump()
        if company_data:
            resp.update(company_data)
        resp["email_verifications"] = email_data
        yield _sse({"type": "result", "data": resp})
    except Exception as e:  # noqa: BLE001
        log.error("Scan post-processing error: %s: %s", type(e).__name__, e)
        yield _sse({"type": "error", "error": "The AI returned an unreadable response. Please try again."})


@router.post("/api/scan")
@limiter.limit("5/minute")
async def scan(req: ScanRequest, request: Request):
    images = [img for img in (req.images_base64 or [req.image_base64]) if img]
    if not images:
        raise InvalidImageError()
    for img in images:
        try:
            decode_base64_image(img)
        except ValueError:
            raise InvalidImageError()

    log.info("Scan: sending %d image(s) to LM Studio", len(images))
    content: list[dict] = [
        {"type": "text", "text": IMAGE_SCAN_INSTRUCTION + "\n\n" + SCAN_OUTPUT_FORMAT + "\n\n" + _language_instruction(req.language)},
    ]
    for img in images:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})
    messages = [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": content},
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
    if not isinstance(result, dict):
        return ResumeData()
    data: dict = {}
    for key in ("skills", "job_titles", "industries"):
        val = result.get(key)
        data[key] = [str(x) for x in val if isinstance(x, (str, int, float))] if isinstance(val, list) else []
    try:
        data["experience_years"] = float(result.get("experience_years") or 0)
    except (TypeError, ValueError):
        data["experience_years"] = 0.0
    data["summary"] = str(result.get("summary") or "")
    return ResumeData(**data)


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
    items = result if isinstance(result, list) else ([result] if isinstance(result, dict) else [])
    matches: list[JobMatchResult] = []
    for r in items:
        if not isinstance(r, dict) or not r.get("job_id"):
            continue
        try:
            score = int(float(r.get("score") or 0))
        except (TypeError, ValueError):
            score = 0
        score = max(0, min(100, score))
        matches.append(JobMatchResult(
            job_id=str(r.get("job_id")),
            score=score,
            label=str(r.get("label") or "Low Compatibility"),
            skill_gaps=[str(x) for x in r.get("skill_gaps") or [] if isinstance(x, (str, int, float))],
            matched_skills=[str(x) for x in r.get("matched_skills") or [] if isinstance(x, (str, int, float))],
            reasoning=str(r.get("reasoning") or ""),
            experience_fit=str(r.get("experience_fit") or ""),
            industry_fit=str(r.get("industry_fit") or ""),
            recommended_actions=[str(x) for x in r.get("recommended_actions") or [] if isinstance(x, (str, int, float))],
        ))
    return MatchResponse(matches=matches)

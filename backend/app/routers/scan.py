import asyncio
import base64
import io
import json
import logging
import time as _time
import zipfile
import re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.config import settings
from app.models.schemas import (
    ScanRequest, ScanResponse, ScanTextRequest,
    ResumeAnalysisRequest, ResumeData,
    MatchRequest, MatchResponse,
    JobMatchResult,
    RedFlag,
    VerifyRequest, VerificationItem,
)
from app.services.image import decode_base64_image
from app.services.lm_client import chat, chat_json, chat_match, chat_resume, chat_stream_pieces, _parse_custom, _parse_json, _parse_resume_custom
from app.services.ddg_search import extract_company_name, search_job_posting, search_job_posting_data
from app.services.email_verifier import verify_emails_in_text
from app.exceptions import InvalidImageError
from app.rate_limit import limiter
from app.ai_limiter import ai_limiter
from app.core.auth import require_client_key

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
Include job title, company, key requirements, AND all contact details found in the posting (phone numbers, email addresses, website URLs, social media handles). These details are needed for verification.
END JOB SUMMARY

Be concise: no greetings, no preamble, no repetition, no markdown.

Field rules:
- VALID: true if this is a genuine job posting or job advertisement, false if it is not. If VALID: false, output ONLY the VALID line and stop immediately — do not generate any other fields.
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
- JOB SUMMARY: Include job title, company, key requirements, AND all contact details found in the posting (phone numbers, email addresses, website URLs, social media handles). These details are needed for verification."""


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


def load_resume_prompt() -> str:
    """Load system prompt from RESUME_PROMPT.md in the backend directory with fallback."""
    prompt_path = Path(__file__).resolve().parents[2] / "RESUME_PROMPT.md"
    if prompt_path.is_file():
        try:
            content = prompt_path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception as e:
            log.warning("Could not read RESUME_PROMPT.md at %s: %s", prompt_path, e)
    return "You are a resume analysis assistant. Extract candidate details from the provided resume."


def load_match_prompt() -> str:
    """Load system prompt from MATCH_PROMPT.md in the backend directory with fallback."""
    prompt_path = Path(__file__).resolve().parents[2] / "MATCH_PROMPT.md"
    if prompt_path.is_file():
        try:
            content = prompt_path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception as e:
            log.warning("Could not read MATCH_PROMPT.md at %s: %s", prompt_path, e)
    return "You are a job-match specialist. Evaluate how well a candidate's resume aligns with each job posting."


SCAN_OUTPUT_FORMAT = """\
Respond strictly using this labeled section format:

VALID: true
VERDICT_PERCENTAGE: 0
END FLAGS
ANALYSIS:
1-2 short sentences. State the verdict and the single most important reason.
END ANALYSIS
JOB SUMMARY:
Include job title, company, key requirements, AND all contact details found in the posting (phone numbers, email addresses, website URLs, social media handles). These details are needed for verification.
END JOB SUMMARY

Be concise: no greetings, no preamble, no repetition, no markdown.

Field rules:
- VALID: true if the image/text is a job posting, false if it is not a job posting. If VALID: false, output ONLY the VALID line and stop immediately — do not generate any other fields.
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
- JOB SUMMARY: Include job title, company, key requirements, AND all contact details found in the posting (phone numbers, email addresses, website URLs, social media handles). These details are needed for verification."""

IMAGE_SCAN_INSTRUCTION = "Verify this job posting screenshot. First decide if it is actually a job posting (VALID: true) or not (VALID: false). If it is not a job posting, output only the VALID: false line and stop — do not analyze further. If it is a job posting, then analyze it for scam indicators. If several images are provided, treat them as parts of the same posting. Extract a job_summary that includes the job title, company, key requirements, AND all contact details found in the posting (phone numbers, email addresses, website URLs, social media handles). These details are needed for verification."

TEXT_SCAN_INSTRUCTION = "Verify this job posting:\n{text}\n\nFirst decide if it is actually a job posting (VALID: true) or not (VALID: false). If it is not a job posting, output only the VALID: false line and stop — do not analyze further. If it is a job posting, then analyze it for scam indicators.\n\nExtract a job_summary that includes the job title, company, key requirements, AND all contact details found in the posting (phone numbers, email addresses, website URLs, social media handles). These details are needed for verification."

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

MATCH_INSTRUCTION = """Compare the candidate's resume against each job posting below.

Scoring: 80-100 strong match, 50-79 partial, 0-49 weak.

Candidate Resume:
Skills: {skills}
Experience: {experience} years
Job Titles: {titles}
Industries: {industries}
Summary: {summary}

Jobs to match against:
{jobs}"""

VERIFY_SYSTEM_PROMPT = """You are a job verification assistant. You are given a job posting summary and web search results about the company. Your task is to verify the legitimacy of the job posting based on these search results.

Analyze the search results and determine:
1. Whether the company exists and is legitimate — also verify that the company name provided is real and matches what was found online. If the company name is missing, unclear, or appears to be fabricated, flag this.
2. Whether the company is registered with the Philippine SEC
3. Whether there are any scam reports or fraud warnings
4. Whether the company has a social media presence

Respond with your findings in this EXACT format for each verification:

VERIFY: Company Name
STATUS: green | yellow | red
DETAIL: One sentence confirming whether the company name is legitimate and identifiable from the posting, or flagging it as missing/unclear.
END VERIFY

VERIFY: Company Existence
STATUS: green | yellow | red
DETAIL: One sentence explaining what you found.
END VERIFY

VERIFY: SEC Registration
STATUS: green | yellow | red
DETAIL: One sentence explaining what you found.
END VERIFY

VERIFY: Scam Reports
STATUS: green | yellow | red
DETAIL: One sentence explaining what you found.
END VERIFY

VERIFY: Online Presence
STATUS: green | yellow | red
DETAIL: One sentence explaining what you found.
END VERIFY

STATUS RULES:
- green: Confirmed positive (found, active, no issues)
- yellow: Partial or uncertain (found but with caveats, or not applicable)
- red: Confirmed negative (not found, scam reports, suspicious)

Include a "Company Name" verification category for every job posting. If the company name was unclear or missing from the original posting, set it to red.

Only include verification categories that are relevant to this job posting. Skip categories that do not apply.

After the verification blocks, ALWAYS output these two sections:

REPORT:
2-4 short plain sentences summarizing overall verification findings. Write complete sentences only — no markdown, no bullet points, no headers, no horizontal rules, no asterisks.
END REPORT

RECOMMENDATION:
1-2 short plain sentences stating whether to apply, proceed with caution, or avoid this job. Write complete sentences only — no markdown, no bullet points, no headers, no horizontal rules, no asterisks.
END RECOMMENDATION"""


def _build_verify_prompt(req: VerifyRequest, search_context: str = "") -> str:
    """Build the user prompt for verification."""
    parts = []
    if req.company_name:
        parts.append(f"Company to verify: {req.company_name}")
    parts.append(f"Job Posting Summary:\n{req.job_summary}")
    if req.red_flags:
        flags_text = "\n".join(f"- {f.flag}: {f.reasoning}" for f in req.red_flags)
        parts.append(f"\nRed flags detected:\n{flags_text}")
    if search_context:
        parts.append(f"\n{search_context}")
    return "\n\n".join(parts)


def _parse_verification_result(text: str) -> list[VerificationItem]:
    """Parse the AI's labeled verification output into structured items."""
    items = []
    pattern = re.compile(
        r"VERIFY:\s*(.+?)\s*STATUS:\s*(green|yellow|red)\s*DETAIL:\s*(.+?)\s*END\s*VERIFY",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        items.append(VerificationItem(
            label=match.group(1).strip(),
            status=match.group(2).strip().lower(),
            explanation=match.group(3).strip(),
        ))
    return items


def _parse_verify_section(text: str, name: str) -> str:
    """Extract a labeled REPORT/RECOMMENDATION section body. Returns '' if missing."""
    pattern = re.compile(
        rf"{name}:\s*(.+?)\s*END\s*{name}",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""

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


def _scan_response(result: dict) -> ScanResponse:
    flags = _red_flags(result.get("red_flags", []))
    calc_score, breakdown = _calculate_score(flags)
    ai_score = result.get("verdict_percentage")
    verdict_percentage = ai_score if ai_score is not None else calc_score
    return ScanResponse(
        valid=result.get("valid", False),
        verdict_percentage=verdict_percentage,
        red_flags=flags,
        analysis=result.get("analysis", ""),
        job_summary=result.get("job_summary", ""),
        error=result.get("error"),
        score_breakdown=breakdown,
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


_VALID_LINE_RE = re.compile(r"^\s*VALID\s*:\s*(true|false)\b", re.IGNORECASE | re.MULTILINE)


async def _scan_event_stream(messages: list, max_tokens: int | None = None, company_data: dict | None = None, original_text: str = "", endpoint: str = "scan") -> str:
    """Stream an AI scan, emitting SSE progress events and a final result.

    Early-exits the AI stream as soon as a complete ``VALID: false`` line is
    received so non-job-posting content does not burn tokens on the remaining fields.
    """
    log.info("[%s] Starting scan stream", endpoint)
    yield _sse({"type": "progress", "percent": 5, "stage": "Preparing request"})
    first = True
    pieces: list[str] = []
    token_count = 0
    early_exit = False
    valid_seen = False
    try:
        deadline = _time.monotonic() + 300.0
        stream = chat_stream_pieces(messages, max_tokens=max_tokens)
        try:
            async for piece in stream:
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
                if not valid_seen:
                    m = _VALID_LINE_RE.search("".join(pieces))
                    if m:
                        valid_seen = True
                        if m.group(1).lower() == "false":
                            early_exit = True
                            log.info("[%s] Early exit after VALID: false (tokens=%d)", endpoint, token_count)
                            break
        finally:
            await stream.aclose()
    except asyncio.TimeoutError:
        log.error("[%s] AI timed out after 300s (%d tokens received)", endpoint, token_count)
        yield _sse({"type": "error", "error": "The AI service took too long to respond. Please try again."})
        return
    except Exception as e:  # noqa: BLE001
        log.error("[%s] Stream error: %s: %s (tokens=%d)", endpoint, type(e).__name__, e, token_count)
        yield _sse({"type": "error", "error": "Hmm, I can't scan at the moment. Please try again."})
        return

    try:
        message_content = "".join(pieces).strip()
        # Strip web-search tool-call blocks (opener + closer share the same marker)
        message_content = re.sub(r"<\|tool_call\|>.*?<\|tool_call\|>", "", message_content, flags=re.DOTALL)
        message_content = message_content.replace("<|tool_call|>", "").strip()
        log.info("[%s] Raw model output (tokens=%d, chars=%d, early_exit=%s): %s", endpoint, token_count, len(message_content), early_exit, message_content[:500])

        result = _parse_custom(message_content) if message_content else None
        if not isinstance(result, dict):
            result = _parse_json(message_content) if message_content else None
        if not isinstance(result, dict):
            log.error("[%s] Parse failed after %d tokens. Raw: %s", endpoint, token_count, message_content[:500])
            yield _sse({"type": "error", "error": "The AI returned an unreadable response. Please try again."})
            return

        log.info("[%s] Parsed result: %s", endpoint, result)
        log.info("[%s] valid=%s, verdict_percentage=%s, job_summary_len=%d, red_flags=%d", endpoint, result.get("valid"), result.get("verdict_percentage"), len(str(result.get("job_summary", ""))), len(_red_flags(result.get("red_flags", []))))
        yield _sse({"type": "progress", "percent": 95, "stage": "Parsing result"})

        is_invalid = early_exit or not result.get("valid", True)

        email_data: list[dict] = []
        verify_text = original_text or (result.get("job_summary", "") + " " + result.get("analysis", ""))
        if not is_invalid and verify_text.strip():
            email_checks = verify_emails_in_text(verify_text)
            email_data = [
                {"email": c.email, "domain": c.domain, "syntax_valid": c.syntax_valid,
                 "has_mx_records": c.has_mx_records, "is_disposable": c.is_disposable,
                 "risk": c.risk, "reason": c.reason}
                for c in email_checks
            ]

        resp = _scan_response(result).model_dump()
        if company_data:
            resp.update(company_data)
        resp["email_verifications"] = email_data

        if not is_invalid:
            company_name = ""
            if company_data:
                company_name = company_data.get("company_name", "")
            if not company_name:
                company_name = extract_company_name(verify_text) or ""
            log.info("[%s] is_valid=%s, company_name='%s', verify_text_len=%d", endpoint, not is_invalid, company_name, len(verify_text))
            if company_name:
                resp["verification_context"] = {
                    "company_name": company_name,
                    "job_summary": result.get("job_summary", ""),
                }
                log.info("[%s] verification_context set for: %s", endpoint, company_name)
            else:
                log.warning("[%s] No company_name extracted — verification_context NOT set. job_summary first 200 chars: %s", endpoint, str(result.get("job_summary", ""))[:200])

        yield _sse({"type": "result", "data": resp})
    except Exception as e:  # noqa: BLE001
        log.error("[%s] Post-processing error: %s: %s", endpoint, type(e).__name__, e)
        yield _sse({"type": "error", "error": "The AI returned an unreadable response. Please try again."})


@router.post("/api/scan")
@limiter.limit("5/minute")
async def scan(req: ScanRequest, request: Request, _auth: None = Depends(require_client_key)):
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

    async def _limited_stream():
        await ai_limiter.acquire()
        try:
            async for event in _scan_event_stream(messages, original_text="", endpoint="scan-image"):
                yield event
        finally:
            ai_limiter.release()

    return StreamingResponse(_limited_stream(), media_type="text/event-stream")


@router.post("/api/scan-text")
@limiter.limit("5/minute")
async def scan_text(req: ScanTextRequest, request: Request, _auth: None = Depends(require_client_key)):
    if not req.text.strip():
        return ScanResponse(valid=False, verdict_percentage=100, analysis="No text provided.")
    log.info("Text scan: %d chars to LM Studio", len(req.text))

    # Pre-search: try to find company info before sending to AI
    search_context = search_job_posting(req.text)
    web_data = search_job_posting_data(req.text)
    user_content = TEXT_SCAN_INSTRUCTION.replace("{text}", req.text) + "\n\n" + SCAN_OUTPUT_FORMAT + "\n\n" + _language_instruction(req.language)
    if search_context:
        user_content = search_context + "\n\n" + user_content

    company_payload = {
        "company_name": web_data.get("company_name"),
        "web_search": web_data.get("results", {}),
    }

    messages = [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": user_content},
    ]

    async def _limited_stream():
        await ai_limiter.acquire()
        try:
            async for event in _scan_event_stream(messages, company_data=company_payload, original_text=req.text, endpoint="scan-text"):
                yield event
        finally:
            ai_limiter.release()

    return StreamingResponse(_limited_stream(), media_type="text/event-stream")


async def _resume_event_stream(messages: list, max_tokens: int | None = None, endpoint: str = "resume") -> str:
    """Stream a resume analysis, emitting SSE progress events and a final result."""
    log.info("[%s] Starting resume stream", endpoint)
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
        log.error("[%s] AI timed out after 300s (%d tokens received)", endpoint, token_count)
        yield _sse({"type": "error", "error": "The AI service took too long to respond. Please try again."})
        return
    except Exception as e:  # noqa: BLE001
        log.error("[%s] Stream error: %s: %s (tokens=%d)", endpoint, type(e).__name__, e, token_count)
        yield _sse({"type": "error", "error": "Hmm, I can't analyze the resume at the moment. Please try again."})
        return

    try:
        message_content = "".join(pieces).strip()
        log.info("[%s] Raw model output (tokens=%d, chars=%d): %s", endpoint, token_count, len(message_content), message_content[:500])

        yield _sse({"type": "progress", "percent": 95, "stage": "Parsing result"})

        result = _parse_resume_custom(message_content)
        if not isinstance(result, dict):
            log.warning("[%s] Parse failed after %d tokens. Raw: %s", endpoint, token_count, message_content[:500])
            yield _sse({"type": "result", "data": ResumeData().model_dump()})
            return

        data: dict = {}
        for key in ("skills", "job_titles", "industries"):
            val = result.get(key)
            data[key] = [str(x) for x in val if isinstance(x, (str, int, float))] if isinstance(val, list) else []
        try:
            data["experience_years"] = float(result.get("experience_years") or 0)
        except (TypeError, ValueError):
            data["experience_years"] = 0.0
        data["summary"] = str(result.get("summary") or "")

        yield _sse({"type": "result", "data": data})
    except Exception as e:  # noqa: BLE001
        log.error("[%s] Post-processing error: %s: %s", endpoint, type(e).__name__, e)
        yield _sse({"type": "error", "error": "The AI returned an unreadable response. Please try again."})


async def _match_event_stream(messages: list, max_tokens: int | None = None, endpoint: str = "match") -> str:
    """Stream a resume-job match, emitting SSE progress events and a final result."""
    log.info("[%s] Starting match stream", endpoint)
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
                yield _sse({"type": "progress", "percent": pct, "stage": "Matching"})
    except asyncio.TimeoutError:
        log.error("[%s] AI timed out after 300s (%d tokens received)", endpoint, token_count)
        yield _sse({"type": "error", "error": "The AI service took too long to respond. Please try again."})
        return
    except Exception as e:  # noqa: BLE001
        log.error("[%s] Stream error: %s: %s (tokens=%d)", endpoint, type(e).__name__, e, token_count)
        yield _sse({"type": "error", "error": "Hmm, I can't match resumes at the moment. Please try again."})
        return

    try:
        message_content = "".join(pieces).strip()
        log.info("[%s] Raw model output (tokens=%d, chars=%d): %s", endpoint, token_count, len(message_content), message_content[:500])

        yield _sse({"type": "progress", "percent": 95, "stage": "Parsing result"})

        result = _parse_custom(message_content) if message_content else None
        if not isinstance(result, dict):
            log.error("[%s] Parse failed after %d tokens. Raw: %s", endpoint, token_count, message_content[:500])
            result = _parse_json(message_content) if message_content else None
        if not isinstance(result, dict):
            yield _sse({"type": "error", "error": "The AI returned an unreadable response. Please try again."})
            return

        # Post-process into match result format
        analysis = result.get("analysis", "")
        job_summary = result.get("job_summary", "")
        verdict = result.get("verdict_percentage", 0)
        score = max(0, min(100, int(verdict) if verdict else 0))
        label = "High Compatibility" if score >= 80 else "Medium Compatibility" if score >= 50 else "Low Compatibility"

        skill_gaps: list[str] = []
        matched_skills: list[str] = []
        recommended_actions: list[str] = []
        experience_fit = ""
        if job_summary:
            parts = [p.strip() for p in re.split(r"[.;]", job_summary) if p.strip()]
            for p in parts:
                p_lower = p.lower()
                if "gap" in p_lower or "missing" in p_lower:
                    items = re.split(r":", p, maxsplit=1)
                    if len(items) > 1:
                        skill_gaps = [x.strip() for x in re.split(r"[,;]", items[1]) if x.strip()]
                elif "match" in p_lower:
                    items = re.split(r":", p, maxsplit=1)
                    if len(items) > 1:
                        matched_skills = [x.strip() for x in re.split(r"[,;]", items[1]) if x.strip()]
                elif "fit" in p_lower:
                    experience_fit = p.strip()
                elif "action" in p_lower or "step" in p_lower:
                    items = re.split(r":", p, maxsplit=1)
                    if len(items) > 1:
                        recommended_actions = [x.strip() for x in re.split(r"[,;]", items[1]) if x.strip()]

        data = {
            "matches": [{
                "job_id": "",
                "score": score,
                "label": label,
                "skill_gaps": skill_gaps,
                "matched_skills": matched_skills,
                "reasoning": analysis,
                "experience_fit": experience_fit,
                "industry_fit": "Moderate",
                "recommended_actions": recommended_actions,
            }],
        }

        yield _sse({"type": "result", "data": data})
    except Exception as e:  # noqa: BLE001
        log.error("[%s] Post-processing error: %s: %s", endpoint, type(e).__name__, e)
        yield _sse({"type": "error", "error": "The AI returned an unreadable response. Please try again."})


@router.post("/api/analyze-resume")
@limiter.limit("5/minute")
async def analyze_resume_endpoint(req: ResumeAnalysisRequest, request: Request, _auth: None = Depends(require_client_key)):
    if req.file_type.lower() in ("png", "jpg", "jpeg"):
        content: list[dict] = [
            {"type": "text", "text": RESUME_INSTRUCTION},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{req.file_base64}"}},
        ]
    else:
        text = _extract_resume_text(req.file_base64, req.file_type)
        content = [{"type": "text", "text": f"{RESUME_INSTRUCTION}\n\nResume text:\n{text[:8000]}"}]

    messages = [
        {"role": "system", "content": load_resume_prompt()},
        {"role": "user", "content": content},
    ]

    async def _limited_stream():
        await ai_limiter.acquire()
        try:
            async for event in _resume_event_stream(messages, max_tokens=2048, endpoint="analyze-resume"):
                yield event
        finally:
            ai_limiter.release()

    return StreamingResponse(_limited_stream(), media_type="text/event-stream")


@router.post("/api/match-resume")
@limiter.limit("10/minute")
async def match_resume_endpoint(req: MatchRequest, request: Request, _auth: None = Depends(require_client_key)):
    prompt = MATCH_INSTRUCTION.format(
        skills=", ".join(req.resume.skills),
        experience=req.resume.experience_years,
        titles=", ".join(req.resume.job_titles),
        industries=", ".join(req.resume.industries),
        summary=req.resume.summary,
        jobs=json.dumps([{"id": j.id, "title": j.title, "summary": j.summary} for j in req.jobs], indent=2),
    )
    messages = [
        {"role": "system", "content": load_match_prompt()},
        {"role": "user", "content": prompt},
    ]

    async def _limited_stream():
        await ai_limiter.acquire()
        try:
            async for event in _match_event_stream(messages, max_tokens=2048, endpoint="match-resume"):
                yield event
        finally:
            ai_limiter.release()

    return StreamingResponse(_limited_stream(), media_type="text/event-stream")


@router.post("/api/verify")
@limiter.limit("10/minute")
async def verify_job(req: VerifyRequest, request: Request, _auth: None = Depends(require_client_key)):
    """External verification: one DuckDuckGo search + one AI call. SSE stream."""

    async def _verify_stream():
        await ai_limiter.acquire()
        try:
            yield _sse({"type": "progress", "percent": 5, "stage": "Preparing verification"})

            search_context = ""
            if req.company_name:
                yield _sse({"type": "progress", "percent": 15, "stage": "Searching the web"})
                yield _sse({"type": "search", "query": f"{req.company_name} Philippines", "round": 1})
                search_context = await asyncio.to_thread(search_job_posting, req.company_name)
                yield _sse({"type": "progress", "percent": 40, "stage": "AI analyzing"})

            verify_prompt = _build_verify_prompt(req, search_context)
            messages = [
                {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
                {"role": "user", "content": verify_prompt},
            ]

            final_text = await chat(messages, max_tokens=1024)
            log.info("[verify] Raw AI response (%d chars): %s", len(final_text), final_text[:1000])
            yield _sse({"type": "progress", "percent": 85, "stage": "Analyzing results"})

            items = _parse_verification_result(final_text)
            report = _parse_verify_section(final_text, "REPORT")
            recommendation = _parse_verify_section(final_text, "RECOMMENDATION")

            log.info("[verify] Parsed items=%d, report_len=%d, rec_len=%d", len(items), len(report), len(recommendation))
            if items:
                log.info("[verify] Items: %s", items)
            if report:
                log.info("[verify] Report: %s", report[:200])
            if recommendation:
                log.info("[verify] Recommendation: %s", recommendation[:200])
            if not items and not report and not recommendation:
                log.warning("[verify] All parsed results empty. Raw text first 500 chars: %s", final_text[:500])

            yield _sse({"type": "result", "data": {
                "items": [item.model_dump() for item in items],
                "report": report,
                "recommendation": recommendation,
                "search_log": [{"query": f"{req.company_name} Philippines", "round": 1}] if req.company_name else [],
            }})
        except Exception as e:  # noqa: BLE001
            log.error("[verify] Error: %s: %s", type(e).__name__, e)
            yield _sse({"type": "error", "error": "Verification failed. Please try again."})
        finally:
            ai_limiter.release()

    return StreamingResponse(_verify_stream(), media_type="text/event-stream")

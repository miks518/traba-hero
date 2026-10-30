import base64
import io
import json
import logging
import re
import time as _time
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.ai_limiter import ai_limiter
from app.config import settings
from app.exceptions import InvalidImageError
from app.models.schemas import (
    AnalyzeOfferRequest,
    Anomaly,
    JobMatchResult,
    MatchRequest,
    MatchResponse,
    ResumeAnalysisRequest,
    ResumeData,
    ScanRequest,
    ScanResponse,
    ScanTextRequest,
    VerificationItem,
    VerifyRequest,
)
from app.rate_limit import limiter
from app.services.search import build_queries, clean_company_name, extract_company_name, is_valid_company_name, merge_results, search
from app.services.image import decode_base64_image, sniff_image_mime
from app.services.lm_client import (
    _parse_custom,
    _parse_json,
    _parse_match_custom,
    _parse_resume_custom,
    chat,
    chat_json,
    chat_match,
    chat_resume,
    chat_stream_pieces,
)
from app.services.scanner import (
    ANALYZE_OFFER_SYSTEM_PROMPT,
    FALLBACK_SYSTEM_PROMPT,
    IMAGE_SCAN_INSTRUCTION,
    MATCH_INSTRUCTION,
    RESUME_INSTRUCTION,
    SCAN_OUTPUT_FORMAT,
    TEXT_SCAN_INSTRUCTION,
    VERIFY_SYSTEM_PROMPT,
    _VALID_LINE_RE,
    _anomalies,
    _build_analyze_offer_prompt,
    _build_verify_prompt,
    _extract_resume_text,
    _language_instruction,
    _match_event_stream,
    _parse_analyze_offer,
    _parse_verification_result,
    _today_instruction,
    _parse_verify_section,
    _resume_event_stream,
    _scan_event_stream,
    _sse,
    analyze_offer_event_stream,
    load_match_prompt,
    load_resume_prompt,
    load_system_prompt,
)
from app.services.scanner.dependencies import runtime
from app.services.scanner.scan_result import _build_scan_response
from app.services.scanner.verification_flow import verification_event_stream


log = logging.getLogger("trabahero")
router = APIRouter()


runtime.get_chat_stream = lambda: chat_stream_pieces
runtime.get_extract_company = lambda: extract_company_name
runtime.get_clean_company_name = lambda: clean_company_name
runtime.get_parse_custom = lambda: _parse_custom
runtime.get_parse_json = lambda: _parse_json
runtime.get_company_name_is_valid = lambda: is_valid_company_name
runtime.get_response_factory = lambda: _scan_response
runtime.get_anomalies = lambda: _anomalies
runtime.get_valid_line_re = lambda: _VALID_LINE_RE
runtime.get_sse = lambda: _sse
runtime.get_parse_resume = lambda: _parse_resume_custom
runtime.get_parse_match = lambda: _parse_match_custom
runtime.get_chat = lambda: chat
runtime.get_search = lambda: search
runtime.get_build_queries = lambda: build_queries
runtime.get_merge_results = lambda: merge_results
runtime.get_build_verify_prompt = lambda: _build_verify_prompt
runtime.get_parse_verification_result = lambda: _parse_verification_result
runtime.get_parse_verify_section = lambda: _parse_verify_section
runtime.get_verify_system_prompt = lambda: VERIFY_SYSTEM_PROMPT
runtime.get_ai_limiter = lambda: ai_limiter
runtime.get_analyze_offer_prompt = lambda: ANALYZE_OFFER_SYSTEM_PROMPT
runtime.get_build_analyze_offer_prompt = lambda: _build_analyze_offer_prompt
runtime.get_parse_analyze_offer = lambda: _parse_analyze_offer


def _scan_response(result: dict, company_name: str = "") -> ScanResponse:
    return _build_scan_response(
        result,
        company_name,
        anomalies_factory=_anomalies,
        company_name_validator=is_valid_company_name,
    )


@router.post("/api/scan")
@limiter.limit("5/minute")
async def scan(req: ScanRequest, request: Request):
    images = [img for img in (req.images_base64 or [req.image_base64]) if img]
    if not images:
        raise InvalidImageError()
    # Decoded once and kept: the bytes are needed to identify the format, and
    # decoding twice would be a second pass over up to 20 MB of base64.
    decoded: list[bytes] = []
    for img in images:
        try:
            decoded.append(decode_base64_image(img))
        except ValueError:
            raise InvalidImageError()

    log.info("Scan: sending %d image(s) to %s", len(images), settings.model_name or "AI provider")
    content: list[dict] = [
        {"type": "text", "text": IMAGE_SCAN_INSTRUCTION + "\n\n" + SCAN_OUTPUT_FORMAT + "\n\n" + _today_instruction() + "\n\n" + _language_instruction(req.language)},
    ]
    for img, raw in zip(images, decoded):
        # The label is read off the bytes rather than assumed. It used to be
        # hardcoded `image/png`, which is wrong for every screenshot this product
        # takes: the extension compresses with `toDataURL('image/jpeg', 0.8)` and
        # then strips the data-URL prefix before POSTing, so the backend receives
        # bare base64 JPEG that this announced as PNG. Announcing a format the
        # bytes are not is a request to decode something that is not there.
        mime = sniff_image_mime(raw)
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img}"}})
    messages = [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": content},
    ]

    async def _limited_stream():
        # The acquire happens inside the generator, after the 200 and SSE
        # headers are already sent — so a 503 here cannot change the status
        # code. Raise it bare and Starlette surfaces an ASGI error the client
        # sees as a truncated stream ("Scan Interrupted"). Degrade to an
        # in-stream error event instead, the same shape scan_flow uses for
        # provider failures, so the reader gets the reason. The verify and
        # offer flows already degrade through their own catch-alls.
        try:
            await ai_limiter.acquire()
        except HTTPException as e:
            log.warning("Scan refused at the AI limiter: %s", e.detail)
            yield runtime.get_sse()({"type": "error", "error": e.detail})
            return
        stream = None
        try:
            stream = _scan_event_stream(messages, original_text="", endpoint="scan-image", thinking=req.thinking)
            async for event in stream:
                yield event
        finally:
            try:
                if stream is not None:
                    await stream.aclose()
            finally:
                ai_limiter.release()

    return StreamingResponse(_limited_stream(), media_type="text/event-stream")


@router.post("/api/scan-text")
@limiter.limit("5/minute")
async def scan_text(req: ScanTextRequest, request: Request):
    if not req.text.strip():
        return ScanResponse(valid=False)
    log.info("Text scan: %d chars to %s", len(req.text), settings.model_name or "AI provider")

    user_content = TEXT_SCAN_INSTRUCTION.replace("{text}", req.text) + "\n\n" + SCAN_OUTPUT_FORMAT + "\n\n" + _today_instruction() + "\n\n" + _language_instruction(req.language)

    messages = [
        {"role": "system", "content": load_system_prompt()},
        {"role": "user", "content": user_content},
    ]

    async def _limited_stream():
        # The acquire happens inside the generator, after the 200 and SSE
        # headers are already sent — so a 503 here cannot change the status
        # code. Raise it bare and Starlette surfaces an ASGI error the client
        # sees as a truncated stream ("Scan Interrupted"). Degrade to an
        # in-stream error event instead, the same shape scan_flow uses for
        # provider failures, so the reader gets the reason. The verify and
        # offer flows already degrade through their own catch-alls.
        try:
            await ai_limiter.acquire()
        except HTTPException as e:
            log.warning("Scan refused at the AI limiter: %s", e.detail)
            yield runtime.get_sse()({"type": "error", "error": e.detail})
            return
        stream = None
        try:
            stream = _scan_event_stream(messages, company_data=None, original_text=req.text, endpoint="scan-text", thinking=req.thinking)
            async for event in stream:
                yield event
        finally:
            try:
                if stream is not None:
                    await stream.aclose()
            finally:
                ai_limiter.release()

    return StreamingResponse(_limited_stream(), media_type="text/event-stream")


@router.post("/api/analyze-resume")
@limiter.limit("5/minute")
async def analyze_resume_endpoint(req: ResumeAnalysisRequest, request: Request):
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
        # The acquire happens inside the generator, after the 200 and SSE
        # headers are already sent — so a 503 here cannot change the status
        # code. Raise it bare and Starlette surfaces an ASGI error the client
        # sees as a truncated stream ("Scan Interrupted"). Degrade to an
        # in-stream error event instead, the same shape scan_flow uses for
        # provider failures, so the reader gets the reason. The verify and
        # offer flows already degrade through their own catch-alls.
        try:
            await ai_limiter.acquire()
        except HTTPException as e:
            log.warning("Scan refused at the AI limiter: %s", e.detail)
            yield runtime.get_sse()({"type": "error", "error": e.detail})
            return
        stream = None
        try:
            stream = _resume_event_stream(messages, endpoint="analyze-resume")
            async for event in stream:
                yield event
        finally:
            try:
                if stream is not None:
                    await stream.aclose()
            finally:
                ai_limiter.release()

    return StreamingResponse(_limited_stream(), media_type="text/event-stream")


@router.post("/api/match-resume")
# Was 10/minute. Sized for LM Studio, where inference took minutes; one hosted
# call completes in seconds and a person matches a resume a handful of times, not
# ten times a minute. This is the most expensive single request served - up to
# `MAX_JOBS_PER_MATCH` jobs in one call - so it gets the tightest limit here.
@limiter.limit("3/minute")
async def match_resume_endpoint(req: MatchRequest, request: Request):
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
        # The acquire happens inside the generator, after the 200 and SSE
        # headers are already sent — so a 503 here cannot change the status
        # code. Raise it bare and Starlette surfaces an ASGI error the client
        # sees as a truncated stream ("Scan Interrupted"). Degrade to an
        # in-stream error event instead, the same shape scan_flow uses for
        # provider failures, so the reader gets the reason. The verify and
        # offer flows already degrade through their own catch-alls.
        try:
            await ai_limiter.acquire()
        except HTTPException as e:
            log.warning("Scan refused at the AI limiter: %s", e.detail)
            yield runtime.get_sse()({"type": "error", "error": e.detail})
            return
        stream = None
        try:
            stream = _match_event_stream(messages, endpoint="match-resume")
            async for event in stream:
                yield event
        finally:
            try:
                if stream is not None:
                    await stream.aclose()
            finally:
                ai_limiter.release()

    return StreamingResponse(_limited_stream(), media_type="text/event-stream")


@router.post("/api/verify")
# Was 10/minute, and halved. Same reason as the others — these were sized when
# inference ran locally and took minutes. This one also spends Tavily credits
# on top of the AI call, up to three per verification against a free tier of
# 1,000 a month, so the more expensive door cannot be the more generous one.
# It stays level with `/api/scan`, which a human hits once per posting.
@limiter.limit("5/minute")
async def verify_job(req: VerifyRequest, request: Request):
    """External verification: one Tavily search + one AI call. SSE stream."""
    return StreamingResponse(verification_event_stream(req), media_type="text/event-stream")


@router.post("/api/analyze-offer")
@limiter.limit("5/minute")
async def analyze_offer(req: AnalyzeOfferRequest, request: Request):
    """Post-only analysis: used when a posting names no employer, so there is
    nothing to look up. Assesses the offer on its own terms and returns a
    assessment. One AI call, no search."""
    text = (req.text or "").strip()
    if not text:
        return StreamingResponse(
            iter([_sse({"type": "result", "data": {
                "kind": "NOT_OFFER",
                "assessment": "No content was provided to assess.",
                "what_it_asks": "Nothing",
                "what_it_offers": "Not stated",
                "what_to_check": "Provide the text or image of the offer.",
                "is_offer": False,
            }})]),
            media_type="text/event-stream",
        )

    log.info("[analyze-offer] Assessing %d chars of content", len(text))
    return StreamingResponse(
        analyze_offer_event_stream(text, req.company_name or "", req.anomalies or [], thinking=req.thinking),
        media_type="text/event-stream",
    )

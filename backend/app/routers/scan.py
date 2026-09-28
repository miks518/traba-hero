import asyncio
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
from app.core.auth import require_client_key
from app.exceptions import InvalidImageError
from app.models.schemas import (
    AnalyzeOfferRequest,
    JobMatchResult,
    MatchRequest,
    MatchResponse,
    RedFlag,
    ResumeAnalysisRequest,
    ResumeData,
    ScanRequest,
    ScanResponse,
    ScanTextRequest,
    SearchDebugRequest,
    VerificationItem,
    VerifyRequest,
)
from app.rate_limit import limiter
from app.services.ddg_search import (
    SEARCH_CODE_VERSION,
    _BACKEND_ORDER,
    _ddg_once,
    clean_company_name,
    extract_company_name,
    is_valid_company_name,
    search_job_posting,
    search_job_posting_data,
    search_with_diagnostics,
    verify_company,
)
from app.services.email_verifier import verify_emails_in_text
from app.services.image import decode_base64_image
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
    _build_analyze_offer_prompt,
    _build_verify_prompt,
    _calculate_risk_score_from_verify,
    _combine_scores,
    _extract_resume_text,
    _language_instruction,
    _match_event_stream,
    _parse_analyze_offer,
    _parse_verification_result,
    _parse_verify_section,
    _posting_risk_from_flags,
    _red_flags,
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
runtime.get_verify_emails = lambda: verify_emails_in_text
runtime.get_extract_company = lambda: extract_company_name
runtime.get_clean_company_name = lambda: clean_company_name
runtime.get_parse_custom = lambda: _parse_custom
runtime.get_parse_json = lambda: _parse_json
runtime.get_company_name_is_valid = lambda: is_valid_company_name
runtime.get_response_factory = lambda: _scan_response
runtime.get_red_flags = lambda: _red_flags
runtime.get_valid_line_re = lambda: _VALID_LINE_RE
runtime.get_sse = lambda: _sse
runtime.get_parse_resume = lambda: _parse_resume_custom
runtime.get_parse_match = lambda: _parse_match_custom
runtime.get_verify_company = lambda: verify_company
runtime.get_chat = lambda: chat
runtime.get_build_verify_prompt = lambda: _build_verify_prompt
runtime.get_parse_verification_result = lambda: _parse_verification_result
runtime.get_parse_verify_section = lambda: _parse_verify_section
runtime.get_calculate_risk = lambda: _calculate_risk_score_from_verify
runtime.get_verify_system_prompt = lambda: VERIFY_SYSTEM_PROMPT
runtime.get_ai_limiter = lambda: ai_limiter
runtime.get_posting_risk = lambda: _posting_risk_from_flags
runtime.get_combine_scores = lambda: _combine_scores
runtime.get_analyze_offer_prompt = lambda: ANALYZE_OFFER_SYSTEM_PROMPT
runtime.get_build_analyze_offer_prompt = lambda: _build_analyze_offer_prompt
runtime.get_parse_analyze_offer = lambda: _parse_analyze_offer


def _scan_response(result: dict, company_name: str = "") -> ScanResponse:
    return _build_scan_response(
        result,
        company_name,
        red_flags_factory=_red_flags,
        company_name_validator=is_valid_company_name,
    )


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

    log.info("Scan: sending %d image(s) to %s", len(images), settings.model_name or "AI provider")
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
        stream = None
        try:
            stream = _scan_event_stream(messages, original_text="", endpoint="scan-image")
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
async def scan_text(req: ScanTextRequest, request: Request, _auth: None = Depends(require_client_key)):
    if not req.text.strip():
        return ScanResponse(valid=False)
    log.info("Text scan: %d chars to %s", len(req.text), settings.model_name or "AI provider")

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
        stream = None
        try:
            stream = _scan_event_stream(messages, company_data=company_payload, original_text=req.text, endpoint="scan-text")
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
        stream = None
        try:
            stream = _resume_event_stream(messages, max_tokens=2048, endpoint="analyze-resume")
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
        stream = None
        try:
            stream = _match_event_stream(messages, max_tokens=2048, endpoint="match-resume")
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
@limiter.limit("10/minute")
async def verify_job(req: VerifyRequest, request: Request, _auth: None = Depends(require_client_key)):
    """External verification: extended DuckDuckGo searches + one AI call. SSE stream."""
    return StreamingResponse(verification_event_stream(req), media_type="text/event-stream")


@router.post("/api/debug/search")
@limiter.limit("30/minute")
async def debug_search(req: SearchDebugRequest, request: Request, _auth: None = Depends(require_client_key)):
    """TEMPORARY: run one raw web-search query and return everything about it.

    Streams so the panel can show which engine is being tried and what it
    returned, per engine, rather than only the final answer. No AI call, no
    rate-limit budget beyond this endpoint's own — this exists to diagnose
    retrieval, so it deliberately does not go through the AI limiter.

    Remove together with SearchDebugView and the 'search' tab in the sidepanel.
    """
    query = (req.query or "").strip()
    if not query:
        return StreamingResponse(
            iter([_sse({"type": "error", "error": "Enter a query."})]),
            media_type="text/event-stream",
        )

    async def _stream():
        yield _sse({
            "type": "meta",
            "query": query,
            "codeVersion": SEARCH_CODE_VERSION,
            "backendOrder": list(_BACKEND_ORDER),
            "pinnedBackend": settings.ddg_backend or "",
            "attempts": settings.ddg_search_attempts,
        })

        # Walk the engines ourselves so each one is reported, including the ones
        # that returned nothing. The production path hides those.
        order = [settings.ddg_backend] if settings.ddg_backend else list(_BACKEND_ORDER)
        for backend in order:
            yield _sse({"type": "engine_start", "backend": backend})
            started = _time.monotonic()
            try:
                raw = _ddg_once(query, req.max_results, only=backend)
            except Exception as e:  # noqa: BLE001
                yield _sse({
                    "type": "engine_error",
                    "backend": backend,
                    "error": f"{type(e).__name__}: {e}",
                    "elapsed": round(_time.monotonic() - started, 2),
                })
                continue

            elapsed = round(_time.monotonic() - started, 2)
            yield _sse({"type": "engine_done", "backend": backend, "elapsed": elapsed, "count": len(raw)})
            for r in raw:
                yield _sse({"type": "result", "backend": backend, "item": r})
            if raw:
                break

        # The full retry path, as production runs it.
        yield _sse({"type": "stage", "stage": "Full production path (retries enabled)"})
        outcome = search_with_diagnostics(query, req.max_results)
        yield _sse({
            "type": "outcome",
            "provider": outcome.provider,
            "attempts": outcome.attempts,
            "throttled": outcome.throttled,
            "ok": outcome.ok,
            "error": outcome.error,
            "count": len(outcome.results),
            "results": outcome.results,
        })
        yield _sse({"type": "done"})

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.post("/api/analyze-offer")
@limiter.limit("5/minute")
async def analyze_offer(req: AnalyzeOfferRequest, request: Request, _auth: None = Depends(require_client_key)):
    """Post-only analysis: used when a posting names no employer, so there is
    nothing to look up. Assesses the offer on its own terms and returns a
    verdict. One AI call, no search."""
    text = (req.text or "").strip()
    if not text:
        return StreamingResponse(
            iter([_sse({"type": "result", "data": {
                "kind": "NOT_OFFER",
                "verdict": "No content was provided to assess.",
                "what_it_asks": "Nothing",
                "what_it_offers": "Not stated",
                "what_to_check": "Provide the text or image of the offer.",
                "is_offer": False,
            }})]),
            media_type="text/event-stream",
        )

    log.info("[analyze-offer] Assessing %d chars of content", len(text))
    return StreamingResponse(
        analyze_offer_event_stream(text, req.company_name or ""),
        media_type="text/event-stream",
    )

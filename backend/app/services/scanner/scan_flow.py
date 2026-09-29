import asyncio
import logging
import re
import time as _time

from app.services.lm_client import EmptyModelResponse

from .dependencies import runtime


log = logging.getLogger("trabahero")


async def _scan_event_stream(messages: list, max_tokens: int | None = None, company_data: dict | None = None, original_text: str = "", endpoint: str = "scan") -> str:
    """Stream an AI scan, emitting SSE progress events and a final result.

    Early-exits the AI stream as soon as a complete ``VALID: false`` line is
    received so non-job-posting content does not burn tokens on the remaining fields.
    """
    log.info("[%s] Starting scan stream", endpoint)
    yield runtime.get_sse()({"type": "progress", "percent": 5, "stage": "Preparing request"})
    first = True
    pieces: list[str] = []
    token_count = 0
    early_exit = False
    valid_seen = False
    try:
        deadline = _time.monotonic() + 300.0
        stream = runtime.get_chat_stream()(messages, max_tokens=max_tokens, endpoint="scan")
        try:
            async for piece in stream:
                if _time.monotonic() > deadline:
                    raise asyncio.TimeoutError()
                pieces.append(piece)
                token_count += 1
                if first:
                    first = False
                    yield runtime.get_sse()({"type": "progress", "percent": 30, "stage": "Sent to AI"})
                elif token_count % 4 == 0:
                    pct = min(88, 30 + int(token_count / 12))
                    yield runtime.get_sse()({"type": "progress", "percent": pct, "stage": "Analyzing"})
                if not valid_seen:
                    m = runtime.get_valid_line_re().search("".join(pieces))
                    if m:
                        valid_seen = True
                        if m.group(1).lower() == "false":
                            early_exit = True
                            log.info("[%s] Early exit after VALID: false (tokens=%d)", endpoint, token_count)
                            break
        finally:
            await stream.aclose()
    except EmptyModelResponse as e:
        log.error("[%s] Provider returned no content: %s", endpoint, e)
        yield runtime.get_sse()({"type": "error", "error": "The AI service returned no content. This is usually a temporary provider or rate-limit issue — please try again in a moment."})
        return
    except asyncio.TimeoutError:
        log.error("[%s] AI timed out after 300s (%d tokens received)", endpoint, token_count)
        yield runtime.get_sse()({"type": "error", "error": "The AI service took too long to respond. Please try again."})
        return
    except Exception as e:  # noqa: BLE001
        log.error("[%s] Stream error: %s: %s (tokens=%d)", endpoint, type(e).__name__, e, token_count)
        yield runtime.get_sse()({"type": "error", "error": "Hmm, I can't scan at the moment. Please try again."})
        return

    try:
        message_content = "".join(pieces).strip()
        message_content = re.sub(r"<\|tool_call\|>.*?<\|tool_call\|>", "", message_content, flags=re.DOTALL)
        message_content = message_content.replace("<|tool_call|>", "").strip()
        log.info("[%s] Raw model output (tokens=%d, chars=%d, early_exit=%s): %s", endpoint, token_count, len(message_content), early_exit, message_content[:500])

        result = runtime.get_parse_custom()(message_content) if message_content else None
        if not isinstance(result, dict):
            result = runtime.get_parse_json()(message_content) if message_content else None
        if not isinstance(result, dict):
            log.error("[%s] Parse failed after %d tokens. Raw: %s", endpoint, token_count, message_content[:500])
            yield runtime.get_sse()({"type": "error", "error": "The AI returned an unreadable response. Please try again."})
            return

        log.info("[%s] Parsed result: %s", endpoint, result)
        log.info("[%s] valid=%s, job_summary_len=%d, red_flags=%d", endpoint, result.get("valid"), len(str(result.get("job_summary", ""))), len(runtime.get_red_flags()(result.get("red_flags", []))))
        yield runtime.get_sse()({"type": "progress", "percent": 95, "stage": "Parsing result"})

        is_invalid = early_exit or not result.get("valid", True)

        email_data: list[dict] = []
        verify_text = original_text or result.get("job_summary", "")
        if not is_invalid and verify_text.strip():
            email_checks = runtime.get_verify_emails()(verify_text)
            email_data = [
                {"email": c.email, "domain": c.domain, "syntax_valid": c.syntax_valid,
                 "has_mx_records": c.has_mx_records, "is_disposable": c.is_disposable,
                 "risk": c.risk, "reason": c.reason}
                for c in email_checks
            ]

        company_name = ""
        if not is_invalid:
            if company_data:
                company_name = company_data.get("company_name", "") or ""
            has_missing_company_flag = any(
                "company" in (f.get("flag", "") + " " + f.get("reasoning", "")).lower()
                and any(w in (f.get("flag", "") + " " + f.get("reasoning", "")).lower()
                        for w in ("missing", "unclear", "not provided", "not specified", "not identified", "unnamed", "no company"))
                for f in (result.get("red_flags") or [])
                if isinstance(f, dict)
            )
            if not company_name:
                # Prefer the model's own COMPANY NAME field. The regex over the
                # prose summary is kept as a fallback for older or unusual
                # output, but guessing the employer from a sentence is what
                # produced unrelated search keywords.
                stated = runtime.get_clean_company_name()(result.get("company_name") or "")
                if stated:
                    company_name = stated
            if not company_name and not has_missing_company_flag:
                company_name = runtime.get_clean_company_name()(runtime.get_extract_company()(verify_text) or "")
            if not runtime.get_company_name_is_valid()(company_name):
                company_name = ""

        resp = runtime.get_response_factory()(result, company_name=company_name).model_dump()
        if company_data:
            resp.update(company_data)
        resp["company_name"] = company_name or None
        resp["email_verifications"] = email_data

        if not is_invalid:
            log.info("[%s] is_valid=%s, company_name='%s', verify_text_len=%d", endpoint, not is_invalid, company_name, len(verify_text))
            if company_name:
                resp["verification_context"] = {
                    "company_name": company_name,
                    "job_summary": result.get("job_summary", ""),
                }
                log.info("[%s] verification_context set for: %s", endpoint, company_name)
            else:
                resp.pop("verification_context", None)
                log.warning("[%s] No company_name extracted — verification_context NOT set. job_summary first 200 chars: %s", endpoint, str(result.get("job_summary", ""))[:200])

        yield runtime.get_sse()({"type": "result", "data": resp})
    except Exception as e:  # noqa: BLE001
        log.error("[%s] Post-processing error: %s: %s", endpoint, type(e).__name__, e)
        yield runtime.get_sse()({"type": "error", "error": "The AI returned an unreadable response. Please try again."})

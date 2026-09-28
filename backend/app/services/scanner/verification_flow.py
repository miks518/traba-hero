import asyncio
import logging
from collections.abc import AsyncIterator

from app.models.schemas import VerificationItem, VerifyRequest

from .dependencies import runtime
from .verification_parser import EXPECTED_CATEGORIES


log = logging.getLogger("trabahero")


def _read_verify_output(text: str) -> tuple[list, str, str, bool]:
    """Read the verification result, preferring JSON and falling back to text.

    JSON is the intended shape, but the provider may still answer with prose if
    it does not support structured outputs, so the labeled-text parser remains as
    a fallback rather than being deleted. Returns (items, report, recommendation,
    used_json).
    """
    payload = runtime.get_parse_json()(text)
    if isinstance(payload, dict) and isinstance(payload.get("checks"), list):
        items = []
        for check in payload["checks"]:
            if not isinstance(check, dict):
                continue
            category = str(check.get("category") or "").strip()
            status = str(check.get("status") or "").strip().lower()
            if not category or status not in ("green", "yellow", "red"):
                log.warning("[verify] Ignoring malformed check entry: %r", check)
                continue
            items.append(VerificationItem(
                label=category,
                status=status,
                explanation=str(check.get("detail") or "").strip(),
            ))
        return items, str(payload.get("report") or ""), str(payload.get("recommendation") or ""), True

    log.warning("[verify] Response was not JSON; falling back to the labeled-text parser.")
    items = runtime.get_parse_verification_result()(text)
    report = runtime.get_parse_verify_section()(text, "REPORT")
    recommendation = runtime.get_parse_verify_section()(text, "RECOMMENDATION")
    return items, report, recommendation, False


async def verification_event_stream(req: VerifyRequest) -> AsyncIterator[str]:
    limiter = runtime.get_ai_limiter()
    await limiter.acquire()
    try:
        yield runtime.get_sse()({"type": "progress", "percent": 5, "stage": "Preparing verification"})

        company = (req.company_name or "").strip()
        if not runtime.get_company_name_is_valid()(company):
            log.warning("[verify] No valid company name provided ('%s') — stopping verification endpoint early.", company)
            yield runtime.get_sse()({"type": "progress", "percent": 100, "stage": "Cannot verify company name"})
            # No company name means there is nothing to search for, so there are
            # no verification results and therefore no risk score. The finding
            # is "we could not check", which is absent evidence, not a negative
            # one, so the status is yellow rather than red.
            explanation = "The job posting does not name an employer, so there was nothing to look up."
            items = [
                VerificationItem(
                    label="Company Existence",
                    status="yellow",
                    explanation=explanation,
                )
            ]
            report = (
                "External verification was skipped because the job posting does not name an employer. "
                "The findings below come only from reading the posting itself."
            )
            recommendation = "Confirm who you would be dealing with through an official channel before sending personal details."
            # No employer lookup happened, so the posting's own indicators remain
            # the whole verdict. The score does not move just because the lookup
            # was impossible.
            posting_score, posting_level, breakdown = runtime.get_posting_risk()(req.red_flags or [])
            breakdown["verification_score"] = None
            breakdown["final_score"] = posting_score
            breakdown["sources"] = ["posting"]
            yield runtime.get_sse()({"type": "result", "data": {
                "items": [item.model_dump() for item in items],
                "report": report,
                "recommendation": recommendation,
                "riskScore": posting_score,
                "riskLevel": posting_level,
                "scoreBreakdown": breakdown,
                "search_log": [],
                "no_company_name": True,
            }})
            return

        yield runtime.get_sse()({"type": "progress", "percent": 10, "stage": "Searching company info"})
        search_log = [
            {"query": f"{company} Philippines company", "round": 1},
            {"query": f"{company} SEC registration Philippines", "round": 2},
            {"query": f"{company} scam fraud complaint", "round": 3},
            {"query": f'"{company}" reviews employee', "round": 4},
        ]
        for entry in search_log:
            yield runtime.get_sse()({"type": "search", "query": entry["query"], "round": entry["round"]})

        search_context = await asyncio.to_thread(runtime.get_verify_company(), company)
        yield runtime.get_sse()({"type": "progress", "percent": 45, "stage": "AI analyzing"})

        # TEMPORARY debug payload: the exact text handed to the model, so the
        # search -> prompt -> answer chain can be inspected in the panel. Remove
        # with the SearchRawPanel component.
        verify_prompt = runtime.get_build_verify_prompt()(req, search_context)
        messages = [
            {"role": "system", "content": runtime.get_verify_system_prompt()},
            {"role": "user", "content": verify_prompt},
        ]

        final_text = await runtime.get_chat()(
            messages,
            max_tokens=2048,
            response_format=runtime.get_verify_response_format(),
        )
        log.info("[verify] Raw AI response (%d chars): %s", len(final_text), final_text[:1000])
        yield runtime.get_sse()({"type": "progress", "percent": 85, "stage": "Analyzing results"})

        items, report, recommendation, used_json = _read_verify_output(final_text)

        # A partial parse used to be silent: the panel showed one card while the
        # raw response clearly listed three, with nothing in the log to connect
        # the two. Name what is missing so the next occurrence is diagnosable.
        missing = runtime.get_missing_categories()(items)
        if missing:
            log.warning(
                "[verify] Parsed %d of %d expected categories; missing: %s. raw=%s json=%s",
                len(items),
                len(EXPECTED_CATEGORIES),
                ", ".join(missing),
                used_json,
                final_text[:800],
            )

        if not items:
            log.warning("[verify] Failsafe triggered: No verification items could be parsed from AI response. Raw: %s", final_text[:300])
            items = [
                VerificationItem(
                    label="Company Existence",
                    status="yellow",
                    explanation=f"No structured findings could be read from the search results for '{company}'.",
                )
            ]
            if not report:
                report = f"Structured findings could not be parsed from the search results for '{company}', so no risk score was calculated."
            if not recommendation:
                recommendation = "Confirm the employer independently before submitting personal details."

        posting_score, _posting_level, breakdown = runtime.get_posting_risk()(req.red_flags or [])
        verify_score, _verify_level = runtime.get_calculate_risk()(items)
        risk_score, risk_level = runtime.get_combine_scores()(posting_score, verify_score)

        breakdown["verification_score"] = verify_score
        breakdown["final_score"] = risk_score
        breakdown["sources"] = [
            name
            for name, value in (("posting", posting_score), ("verification", verify_score))
            if value is not None
        ]

        log.info("[verify] Parsed items=%d, report_len=%d, rec_len=%d, posting_score=%s, verify_score=%s, risk_score=%s, risk_level=%s", len(items), len(report), len(recommendation), posting_score, verify_score, risk_score, risk_level)
        if items:
            log.info("[verify] Items: %s", items)
        if report:
            log.info("[verify] Report: %s", report[:200])
        if recommendation:
            log.info("[verify] Recommendation: %s", recommendation[:200])

        yield runtime.get_sse()({"type": "result", "data": {
            "items": [item.model_dump() for item in items],
            "report": report,
            "recommendation": recommendation,
            "riskScore": risk_score,
            "riskLevel": risk_level,
            "scoreBreakdown": breakdown,
            "search_log": search_log,
            # TEMPORARY: the prompt as sent, for debugging retrieval. Not part
            # of the normal response and should be removed once the search
            # behaviour is settled.
            "debug_prompt": verify_prompt,
            "no_company_name": False,
        }})
    except Exception as e:  # noqa: BLE001
        log.error("[verify] Error: %s: %s", type(e).__name__, e)
        yield runtime.get_sse()({"type": "error", "error": "Verification failed. Please try again."})
    finally:
        limiter.release()

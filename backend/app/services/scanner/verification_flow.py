import asyncio
import logging
from collections.abc import AsyncIterator

from app.config import settings
from app.models.schemas import VerificationItem, VerifyRequest

from .dependencies import runtime
from .verification_parser import EXPECTED_CATEGORIES


log = logging.getLogger("trabahero")


def _read_verify_output(text: str) -> tuple[list, str, str, bool, list]:
    """Read the verification result, preferring JSON and falling back to text.

    JSON is the intended shape, but the provider may still answer with prose if
    it does not support structured outputs, so the labeled-text parser remains as
    a fallback rather than being deleted. Returns (items, report, recommendation,
    used_json, evidence).
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
                explanation=str(check.get("finding") or check.get("detail") or "").strip(),
                source_title=str(check.get("source_title") or "").strip(),
                source_url=str(check.get("source_url") or "").strip(),
            ))

        evidence = []
        raw_evidence = payload.get("evidence")
        if isinstance(raw_evidence, list):
            for entry in raw_evidence:
                if not isinstance(entry, dict):
                    continue
                url = str(entry.get("url") or "").strip()
                if not url:
                    continue
                evidence.append({
                    "title": str(entry.get("title") or "").strip(),
                    "url": url,
                    "snippet": str(entry.get("snippet") or "").strip(),
                })
        return items, str(payload.get("report") or ""), str(payload.get("recommendation") or ""), True, evidence

    log.warning("[verify] Response was not JSON; falling back to the labeled-text parser.")
    items = runtime.get_parse_verification_result()(text)
    report = runtime.get_parse_verify_section()(text, "REPORT")
    recommendation = runtime.get_parse_verify_section()(text, "RECOMMENDATION")
    return items, report, recommendation, False, []


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
                "search_ok": False,
                "search_error": "No employer name was given, so nothing was searched.",
                "no_company_name": True,
            }})
            return

        yield runtime.get_sse()({"type": "progress", "percent": 10, "stage": "Searching company info"})
        # Two queries, no category suffixes: the model sorts the merged results
        # into the three categories itself, so nothing here decides what a
        # result is. The second exists because one query cannot serve all three
        # categories — `"<company> Philippines"` ranks the employer's own site
        # first, and those pages do not state registration numbers.
        queries = runtime.get_build_queries()(company)
        collected: list = []
        # TEMPORARY DIAGNOSTIC. The provider's raw body per query, so the panel
        # can show what Tavily actually returned. Remove alongside
        # SearchOutcome.raw_response and the suspended assertion in
        # test_no_debug_surface.py.
        raw_dump: list[dict] = []
        # (query, error) rather than the query alone: the panel is told *why*
        # retrieval failed, and a bare query string would report "Acme
        # Philippines" to the user in place of "TAVILY_API_KEY is not
        # configured", which is both useless and alarming.
        failures: list[tuple[str, str]] = []

        for i, query in enumerate(queries, 1):
            yield runtime.get_sse()({"type": "search", "query": query, "round": i})
            outcome = await asyncio.to_thread(runtime.get_search(), query)
            if outcome.ok:
                collected.append(outcome.results)
            else:
                # One failure is not a total failure: the other query may have
                # worked, and discarding it would understate what was checked.
                failures.append((query, outcome.error))
                log.warning("[verify] Search failed for '%s': %s", query, outcome.error)
            if outcome.raw_response:  # TEMPORARY DIAGNOSTIC
                raw_dump.append({"query": query, "raw": outcome.raw_response})

        ok = bool(collected) or not failures
        partial = bool(failures) and bool(collected)
        first_error = failures[0][1] if failures else ""

        if not collected and not failures:
            log.info("[verify] Searches for '%s' returned no results", company)
        elif partial:
            log.warning(
                "[verify] %d of %d searches failed for '%s'; coverage is partial",
                len(failures), len(queries), company,
            )

        # Dedupe on canonical URL: the employer's own site appears in both
        # result sets, and every result is prompt text competing for a budget
        # shared with the model's reasoning. Capped so the merged list cannot
        # outgrow what one query produced by much.
        merged = runtime.get_merge_results()(
            *collected, cap=settings.tavily_max_results * 2
        )
        search_context = runtime.get_format_results()(
            merged, company, ok, first_error
        )
        yield runtime.get_sse()({"type": "progress", "percent": 45, "stage": "AI analyzing"})

        # The exact text handed to the model, so the search -> prompt -> answer
        # chain can be inspected in the panel. See SearchRawPanel.
        verify_prompt = runtime.get_build_verify_prompt()(req, search_context)
        messages = [
            {"role": "system", "content": runtime.get_verify_system_prompt()},
            {"role": "user", "content": verify_prompt},
        ]

        final_text = await runtime.get_chat()(
            messages,
            response_format=runtime.get_verify_response_format(),
            endpoint="verify",
        )
        log.info("[verify] Raw AI response (%d chars): %s", len(final_text), final_text[:1000])
        yield runtime.get_sse()({"type": "progress", "percent": 85, "stage": "Analyzing results"})

        items, report, recommendation, used_json, evidence = _read_verify_output(final_text)

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
            "evidence": evidence,
            "report": report,
            "recommendation": recommendation,
            "riskScore": risk_score,
            "riskLevel": risk_level,
            "scoreBreakdown": breakdown,
            # On the wire, not left to the model. A prompt instruction to "state
            # that the search did not complete" only works if the model obeys;
            # a model that omits it would render three yellow cards identical to
            # a company with no footprint. The panel states this directly.
            #
            # `search_partial` is the state a single search never had: one of
            # two failed, so the answer is real but some categories are thinner
            # than they look. Reporting `search_ok: true` with no caveat would
            # overstate the coverage, and reporting a total failure would
            # discard a search that worked.
            "search_ok": ok,
            "search_partial": partial,
            "search_error": first_error,
            "search_count": len(merged),
            "queries_issued": len(queries),
            "queries_failed": len(failures),
            "debug_search_raw": raw_dump,  # TEMPORARY DIAGNOSTIC — remove with SearchOutcome.raw_response
            "no_company_name": False,
        }})
    except Exception as e:  # noqa: BLE001
        log.error("[verify] Error: %s: %s", type(e).__name__, e)
        yield runtime.get_sse()({"type": "error", "error": "Verification failed. Please try again."})
    finally:
        limiter.release()

import asyncio
import logging
from collections.abc import AsyncIterator

from app.models.schemas import VerificationItem, VerifyRequest

from .dependencies import runtime


log = logging.getLogger("trabahero")


async def verification_event_stream(req: VerifyRequest) -> AsyncIterator[str]:
    limiter = runtime.get_ai_limiter()
    await limiter.acquire()
    try:
        yield runtime.get_sse()({"type": "progress", "percent": 5, "stage": "Preparing verification"})

        company = (req.company_name or "").strip()
        if not runtime.get_company_name_is_valid()(company):
            log.warning("[verify] No valid company name provided ('%s') — stopping verification endpoint early.", company)
            yield runtime.get_sse()({"type": "progress", "percent": 100, "stage": "Cannot verify company name"})
            explanation = "Cannot verify company name: The company or business name was not identified in the job posting."
            items = [
                VerificationItem(
                    label="Company Name",
                    status="red",
                    explanation=explanation,
                )
            ]
            report = "External verification could not be performed because no company name was identified in the job posting. Legitimate employers clearly identify their organization."
            recommendation = "Treat this posting as high risk. Avoid applying or proceed with extreme caution until the employer's identity can be verified."
            yield runtime.get_sse()({"type": "result", "data": {
                "items": [item.model_dump() for item in items],
                "report": report,
                "recommendation": recommendation,
                "riskScore": 75,
                "riskLevel": "high",
                "search_log": [],
                "no_company_name": True,
            }})
            return

        yield runtime.get_sse()({"type": "progress", "percent": 10, "stage": "Searching company info"})
        yield runtime.get_sse()({"type": "search", "query": f"{company} Philippines", "round": 1})
        yield runtime.get_sse()({"type": "search", "query": f'site:facebook.com "{company}" reviews', "round": 2})
        yield runtime.get_sse()({"type": "search", "query": f'site:reddit.com "{company}" Philippines', "round": 3})
        search_context = await asyncio.to_thread(runtime.get_verify_company(), company)
        search_log = [
            {"query": f"{company} Philippines", "round": 1},
            {"query": f'site:facebook.com "{company}" reviews', "round": 2},
            {"query": f'site:reddit.com "{company}" Philippines', "round": 3},
        ]
        yield runtime.get_sse()({"type": "progress", "percent": 45, "stage": "AI analyzing"})

        verify_prompt = runtime.get_build_verify_prompt()(req, search_context)
        messages = [
            {"role": "system", "content": runtime.get_verify_system_prompt()},
            {"role": "user", "content": verify_prompt},
        ]

        final_text = await runtime.get_chat()(messages, max_tokens=1024)
        log.info("[verify] Raw AI response (%d chars): %s", len(final_text), final_text[:1000])
        yield runtime.get_sse()({"type": "progress", "percent": 85, "stage": "Analyzing results"})

        items = runtime.get_parse_verification_result()(final_text)
        report = runtime.get_parse_verify_section()(final_text, "REPORT")
        recommendation = runtime.get_parse_verify_section()(final_text, "RECOMMENDATION")

        if not items:
            log.warning("[verify] Failsafe triggered: No verification items could be parsed from AI response. Raw: %s", final_text[:300])
            explanation = f"Cannot verify company name: External verification could not parse verification details for '{company}'."
            items = [
                VerificationItem(
                    label="Company Name",
                    status="yellow",
                    explanation=explanation,
                )
            ]
            if not report:
                report = f"External verification details could not be parsed for '{company}'. Search queries were executed, but structured findings were unavailable."
            if not recommendation:
                recommendation = "Proceed with caution. Independently confirm company registration and reputation before submitting personal details."

        risk_score, risk_level = runtime.get_calculate_risk()(items)

        log.info("[verify] Parsed items=%d, report_len=%d, rec_len=%d, risk_score=%d, risk_level=%s", len(items), len(report), len(recommendation), risk_score, risk_level)
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
            "search_log": search_log,
            "no_company_name": False,
        }})
    except Exception as e:  # noqa: BLE001
        log.error("[verify] Error: %s: %s", type(e).__name__, e)
        yield runtime.get_sse()({"type": "error", "error": "Verification failed. Please try again."})
    finally:
        limiter.release()

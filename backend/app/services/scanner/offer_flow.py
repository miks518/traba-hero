import asyncio
import logging
from collections.abc import AsyncIterator

from .dependencies import runtime
from .offer_prompt import NOT_OFFER_KIND
from .request_class import classify_request, facts_from_scan
from .assessment import code_assessment

log = logging.getLogger("trabahero")

# Used when the model output cannot be read. The comment that used to sit here
# said a failsafe cost the user an explanation and not a assessment, because the
# score came from the scan's indicators rather than from this pass. That is no
# longer true: this pass now produces the level, so an unreadable answer yields
# no level, and the cost is exactly a assessment.
FAILSAFE = {
    "kind": "Offer",
    "assessment": "This content was not readable well enough to assess in detail. The indicators listed above were found in the content itself.",
    "what_it_asks": "Not stated",
    "what_it_offers": "Not stated",
    "what_to_check": "Confirm who you would be dealing with before sending money or personal details.",
    "is_offer": True,
    "codes": [],
    "assessment_level": None,
    "assessmentBreakdown": {"assessment": None, "level_source": None},
}


async def analyze_offer_event_stream(text: str, company_name: str = "", anomalies: list = None, thinking: bool | None = None) -> AsyncIterator[str]:
    if anomalies is None:
        anomalies = []
    limiter = runtime.get_ai_limiter()
    await limiter.acquire()
    try:
        yield runtime.get_sse()({"type": "progress", "percent": 10, "stage": "Reading the offer"})

        messages = [
            {"role": "system", "content": runtime.get_analyze_offer_prompt()},
            {"role": "user", "content": runtime.get_build_analyze_offer_prompt()(text, company_name)},
        ]

        final_text = await runtime.get_chat()(
            messages,
            response_format=runtime.get_analyze_offer_response_format(),
            endpoint="offer",
            thinking=thinking,
        )
        log.info("[analyze-offer] Raw model output (%d chars): %s", len(final_text), final_text[:800])

        parsed = _read_offer_output(final_text, anomalies)
        if not parsed:
            log.warning("[analyze-offer] Output could not be read, using failsafe. Raw: %s", final_text[:300])
            parsed = dict(FAILSAFE)

        yield runtime.get_sse()({"type": "progress", "percent": 90, "stage": "Writing the assessment"})
        yield runtime.get_sse()({"type": "result", "data": parsed})
    except Exception as e:  # noqa: BLE001
        log.error("[analyze-offer] Error: %s: %s", type(e).__name__, e)
        yield runtime.get_sse()({"type": "result", "data": dict(FAILSAFE)})
    finally:
        limiter.release()


def _read_offer_output(text: str, anomalies: list = None) -> dict | None:
    if anomalies is None:
        anomalies = []
    """Read the analysis result, preferring JSON and falling back to text."""
    payload = runtime.get_parse_json()(text)
    if isinstance(payload, dict) and payload.get("assessment"):
        kind = str(payload.get("kind") or "").strip()

        # The assessment is code-owned, like the verify path. The model's codes
        # become a request class, and the grid decides the assessment from it and
        # an unknown establishment — the offer path has no employer to look up.
        codes = payload.get("codes") or []
        if not isinstance(codes, list):
            codes = []
        codes = [str(c).strip().upper() for c in codes if str(c).strip()]
        # The scan's anomalies are the primary input — they carry the codes
        # and quotes the scan detected. The model's codes are a second
        # opinion, merged in so a finding the scan missed still counts.
        scan_codes = [getattr(a, "code", "") or "" for a in (anomalies or [])]
        all_codes = list(dict.fromkeys(scan_codes + codes))  # dedupe, scan first
        # Fee recipient/timing: prefer the scan's attributes, but the offer
        # path doesn't receive attributes, so fee-bearing codes resolve to
        # unclassified — the honest reading when the recipient is unnamed.
        all_anomalies = [{"code": c, "quote": ""} for c in all_codes if c]
        request_class = classify_request(facts_from_scan(all_anomalies, {}))

        from .establishment import Establishment
        establishment = Establishment(
            "unknown",
            "Nothing in the record establishes who is behind the posting.",
        )
        assessment, breakdown = code_assessment(
            anomalies,
            [],
            [],
            request_class=request_class,
            establishment=establishment,
        )

        # Task-to-earn via a direct message is a concrete scam pattern: the
        # reader completes work for a stranger and is paid only if the stranger
        # chooses to pay, and the stranger can block them at any point. The grid
        # would read this as "yellow" (prohibited + unestablished employer),
        # but the pattern itself is the strongest signal available to this pass
        # — there is no employer to look up and no search to contradict it, so
        # yellow (which says "uncertain") understates it.
        # Override to "red" when the posting contains TASK_FOR_EARNING.
        if assessment == "yellow" and "TASK_FOR_EARNING" in codes:
            assessment = "red"
            breakdown["assessment"] = "red"
            breakdown["rule"] = "task_for_earning_at_unestablished_employer"

        return {
            "kind": kind or "Offer",
            "assessment": str(payload.get("assessment")).strip(),
            "what_it_asks": str(payload.get("what_it_asks") or "").strip(),
            "what_it_offers": str(payload.get("what_it_offers") or "").strip(),
            "what_to_check": str(payload.get("what_to_check") or "").strip(),
            "is_offer": kind.strip().upper() != NOT_OFFER_KIND if kind else True,
            "codes": codes,
            # Code-owned, like the verify path. The model's risk_level and
            # risk_score are gone — the assessment is what the panel shows, and it
            # is decided by the grid, not by the model's reading of the offer.
            "assessment_level": assessment,
            "assessmentBreakdown": breakdown,
        }

    log.warning("[analyze-offer] Response was not JSON; falling back to the labeled-text parser.")
    parsed = runtime.get_parse_analyze_offer()(text)
    if isinstance(parsed, dict):
        # The labeled-text format has nowhere to carry either, so this path yields
        # None rather than inventing them.
        parsed.setdefault("codes", [])
        parsed.setdefault("assessment_level", None)
        parsed.setdefault("assessmentBreakdown", {"assessment": None, "level_source": None})
    return parsed

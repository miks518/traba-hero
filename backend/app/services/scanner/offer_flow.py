import asyncio
import logging
from collections.abc import AsyncIterator

from .dependencies import runtime
from .offer_prompt import NOT_OFFER_KIND
from .request_class import classify_request, facts_from_scan
from .verdict import code_verdict

log = logging.getLogger("trabahero")

# Used when the model output cannot be read. The comment that used to sit here
# said a failsafe cost the user an explanation and not a verdict, because the
# score came from the scan's indicators rather than from this pass. That is no
# longer true: this pass now produces the level, so an unreadable answer yields
# no level, and the cost is exactly a verdict.
FAILSAFE = {
    "kind": "Offer",
    "verdict": "This content was not readable well enough to assess in detail. The indicators listed above were found in the content itself.",
    "what_it_asks": "Not stated",
    "what_it_offers": "Not stated",
    "what_to_check": "Confirm who you would be dealing with before sending money or personal details.",
    "is_offer": True,
    "codes": [],
    "verdict_level": None,
    "verdictBreakdown": {"verdict": None, "level_source": None},
}


async def analyze_offer_event_stream(text: str, company_name: str = "") -> AsyncIterator[str]:
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
        )
        log.info("[analyze-offer] Raw model output (%d chars): %s", len(final_text), final_text[:800])

        parsed = _read_offer_output(final_text)
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


def _read_offer_output(text: str) -> dict | None:
    """Read the analysis result, preferring JSON and falling back to text."""
    payload = runtime.get_parse_json()(text)
    if isinstance(payload, dict) and payload.get("verdict"):
        kind = str(payload.get("kind") or "").strip()

        # The verdict is code-owned, like the verify path. The model's codes
        # become a request class, and the grid decides the verdict from it and
        # an unknown establishment — the offer path has no employer to look up.
        codes = payload.get("codes") or []
        if not isinstance(codes, list):
            codes = []
        codes = [str(c).strip().upper() for c in codes if str(c).strip()]
        # Fee recipient/timing come from what the posting states about who is
        # paid. The model does not emit attributes here, so fee-bearing codes
        # resolve to unclassified — the honest reading when the recipient is
        # unnamed.
        anomalies = [{"code": c, "quote": ""} for c in codes]
        request_class = classify_request(facts_from_scan(anomalies, {}))

        from .establishment import Establishment
        establishment = Establishment(
            "unknown",
            "Nothing in the record establishes who is behind the posting.",
        )
        verdict, breakdown = code_verdict(
            anomalies,
            [],
            [],
            request_class=request_class,
            establishment=establishment,
        )

        return {
            "kind": kind or "Offer",
            "verdict": str(payload.get("verdict")).strip(),
            "what_it_asks": str(payload.get("what_it_asks") or "").strip(),
            "what_it_offers": str(payload.get("what_it_offers") or "").strip(),
            "what_to_check": str(payload.get("what_to_check") or "").strip(),
            "is_offer": kind.strip().upper() != NOT_OFFER_KIND if kind else True,
            "codes": codes,
            # Code-owned, like the verify path. The model's risk_level and
            # risk_score are gone — the verdict is what the panel shows, and it
            # is decided by the grid, not by the model's reading of the offer.
            "verdict_level": verdict,
            "verdictBreakdown": breakdown,
        }

    log.warning("[analyze-offer] Response was not JSON; falling back to the labeled-text parser.")
    parsed = runtime.get_parse_analyze_offer()(text)
    if isinstance(parsed, dict):
        # The labeled-text format has nowhere to carry either, so this path yields
        # None rather than inventing them.
        parsed.setdefault("codes", [])
        parsed.setdefault("verdict_level", None)
        parsed.setdefault("verdictBreakdown", {"verdict": None, "level_source": None})
    return parsed

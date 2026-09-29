import asyncio
import logging
from collections.abc import AsyncIterator

from .dependencies import runtime
from .offer_prompt import NOT_OFFER_KIND

log = logging.getLogger("trabahero")

# Used when the model output cannot be read. The risk score never depends on this
# pass — it comes from the indicators the scan already reported — so a failsafe
# here costs the user an explanation, not a verdict.
FAILSAFE = {
    "kind": "Offer",
    "verdict": "This content was not readable well enough to assess in detail. The indicators listed above were found in the content itself.",
    "what_it_asks": "Not stated",
    "what_it_offers": "Not stated",
    "what_to_check": "Confirm who you would be dealing with before sending money or personal details.",
    "is_offer": True,
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
        return {
            "kind": kind or "Offer",
            "verdict": str(payload.get("verdict")).strip(),
            "what_it_asks": str(payload.get("what_it_asks") or "").strip(),
            "what_it_offers": str(payload.get("what_it_offers") or "").strip(),
            "what_to_check": str(payload.get("what_to_check") or "").strip(),
            "is_offer": kind.strip().upper() != NOT_OFFER_KIND if kind else True,
        }

    log.warning("[analyze-offer] Response was not JSON; falling back to the labeled-text parser.")
    return runtime.get_parse_analyze_offer()(text)

import asyncio
import logging
from collections.abc import AsyncIterator

from app.models.schemas import RISK_LEVELS

from .dependencies import runtime
from .offer_prompt import NOT_OFFER_KIND

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
    # None, and that is the whole point. The default used to be a score derived
    # from the scan, so the one case where the model's answer could not be read
    # printed the calmest verdict on the panel.
    "risk_level": None,
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
        level = str(payload.get("risk_level") or "").strip().lower()
        if level not in RISK_LEVELS:
            # Unrecognised becomes None, not a guess. `None` is the "not assessed"
            # the panel already renders as Unverified; a misspelt level reaching
            # the wire would put a colour on a posting nobody judged.
            if level:
                log.warning("[analyze-offer] Ignoring unrecognised risk_level %r", level)
            level = None
        return {
            "kind": kind or "Offer",
            "verdict": str(payload.get("verdict")).strip(),
            "what_it_asks": str(payload.get("what_it_asks") or "").strip(),
            "what_it_offers": str(payload.get("what_it_offers") or "").strip(),
            "what_to_check": str(payload.get("what_to_check") or "").strip(),
            "is_offer": kind.strip().upper() != NOT_OFFER_KIND if kind else True,
            "risk_level": level,
        }

    log.warning("[analyze-offer] Response was not JSON; falling back to the labeled-text parser.")
    parsed = runtime.get_parse_analyze_offer()(text)
    if isinstance(parsed, dict):
        # The labeled-text format has nowhere to carry a level, so this path
        # yields None rather than inventing one.
        parsed["risk_level"] = None
    return parsed

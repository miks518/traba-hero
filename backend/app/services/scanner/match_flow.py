import asyncio
import logging
import time as _time

from app.services.lm_client import EmptyModelResponse

from .dependencies import runtime


log = logging.getLogger("trabahero")


async def _match_event_stream(messages: list, max_tokens: int | None = None, endpoint: str = "match") -> str:
    """Stream a resume-job match, emitting SSE progress events and a final result."""
    log.info("[%s] Starting match stream", endpoint)
    yield runtime.get_sse()({"type": "progress", "percent": 5, "stage": "Preparing request"})
    first = True
    pieces: list[str] = []
    token_count = 0
    try:
        deadline = _time.monotonic() + 300.0
        stream = runtime.get_chat_stream()(messages, max_tokens=max_tokens, endpoint=endpoint)
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
                    yield runtime.get_sse()({"type": "progress", "percent": pct, "stage": "Matching"})
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
        yield runtime.get_sse()({"type": "error", "error": "Hmm, I can't match resumes at the moment. Please try again."})
        return

    try:
        message_content = "".join(pieces).strip()
        log.info("[%s] Raw model output (tokens=%d, chars=%d): %s", endpoint, token_count, len(message_content), message_content[:500])

        yield runtime.get_sse()({"type": "progress", "percent": 95, "stage": "Parsing result"})

        result = runtime.get_parse_match()(message_content) if message_content else None
        if not isinstance(result, list):
            log.error("[%s] Parse failed after %d tokens. Raw: %s", endpoint, token_count, message_content[:500])
            result = runtime.get_parse_json()(message_content) if message_content else None
            if isinstance(result, dict):
                result = [result]
            elif not isinstance(result, list):
                yield runtime.get_sse()({"type": "error", "error": "The AI returned an unreadable response. Please try again."})
                return

        matches = []
        for item in result:
            if not isinstance(item, dict) or not item.get("job_id"):
                continue
            analysis = item.get("reasoning", "")
            score_val = item.get("score", 0)
            score = max(0, min(100, int(score_val) if score_val else 0))
            label = item.get("label") or ("High Compatibility" if score >= 80 else "Medium Compatibility" if score >= 50 else "Low Compatibility")
            skill_gaps = item.get("skill_gaps", []) if isinstance(item.get("skill_gaps"), list) else []
            matched_skills = item.get("matched_skills", []) if isinstance(item.get("matched_skills"), list) else []
            experience_fit = item.get("experience_fit", "") or "Moderate"
            industry_fit = item.get("industry_fit", "") or "Moderate"
            recommended_actions = item.get("recommended_actions", []) if isinstance(item.get("recommended_actions"), list) else []

            matches.append({
                "job_id": item["job_id"],
                "score": score,
                "label": label,
                "skill_gaps": skill_gaps,
                "matched_skills": matched_skills,
                "reasoning": analysis,
                "experience_fit": experience_fit,
                "industry_fit": industry_fit,
                "recommended_actions": recommended_actions,
            })

        data = {"matches": matches}
        yield runtime.get_sse()({"type": "result", "data": data})
    except Exception as e:  # noqa: BLE001
        log.error("[%s] Post-processing error: %s: %s", endpoint, type(e).__name__, e)
        yield runtime.get_sse()({"type": "error", "error": "The AI returned an unreadable response. Please try again."})

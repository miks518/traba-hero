import asyncio
import base64
import io
import logging
import re
import time as _time
import zipfile

from fastapi import HTTPException

from app.models.schemas import ResumeData
from app.services.lm_client import EmptyModelResponse

from .dependencies import runtime


log = logging.getLogger("trabahero")


def _extract_resume_text(file_base64: str, file_type: str) -> str:
    """Extract raw text from an uploaded resume file (non-image types)."""
    file_type = file_type.lower()
    try:
        raw = base64.b64decode(file_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="The uploaded file could not be read.")

    if file_type == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    if file_type == "txt":
        return raw.decode("utf-8", errors="replace")
    if file_type == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
            xml = re.sub(r"<w:p[ >]", "\n", xml)
            xml = re.sub(r"<[^>]+>", "", xml)
            return xml
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read the .docx file. Convert it to PDF or TXT and try again.")
    raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}. Use PDF, TXT, DOCX, or an image.")


async def _resume_event_stream(messages: list, max_tokens: int | None = None, endpoint: str = "resume") -> str:
    """Stream a resume analysis, emitting SSE progress events and a final result."""
    log.info("[%s] Starting resume stream", endpoint)
    yield runtime.get_sse()({"type": "progress", "percent": 5, "stage": "Preparing request"})
    first = True
    pieces: list[str] = []
    token_count = 0
    try:
        deadline = _time.monotonic() + 300.0
        stream = runtime.get_chat_stream()(messages, max_tokens=max_tokens)
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
        yield runtime.get_sse()({"type": "error", "error": "Hmm, I can't analyze the resume at the moment. Please try again."})
        return

    try:
        message_content = "".join(pieces).strip()
        log.info("[%s] Raw model output (tokens=%d, chars=%d): %s", endpoint, token_count, len(message_content), message_content[:500])

        yield runtime.get_sse()({"type": "progress", "percent": 95, "stage": "Parsing result"})

        result = runtime.get_parse_resume()(message_content)
        if not isinstance(result, dict):
            log.warning("[%s] Parse failed after %d tokens. Raw: %s", endpoint, token_count, message_content[:500])
            yield runtime.get_sse()({"type": "result", "data": ResumeData().model_dump()})
            return

        data: dict = {}
        for key in ("skills", "job_titles", "industries"):
            val = result.get(key)
            data[key] = [str(x) for x in val if isinstance(x, (str, int, float))] if isinstance(val, list) else []
        try:
            data["experience_years"] = float(result.get("experience_years") or 0)
        except (TypeError, ValueError):
            data["experience_years"] = 0.0
        data["summary"] = str(result.get("summary") or "")

        yield runtime.get_sse()({"type": "result", "data": data})
    except Exception as e:  # noqa: BLE001
        log.error("[%s] Post-processing error: %s: %s", endpoint, type(e).__name__, e)
        yield runtime.get_sse()({"type": "error", "error": "The AI returned an unreadable response. Please try again."})

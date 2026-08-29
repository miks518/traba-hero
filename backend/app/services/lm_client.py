import json
import re
import logging
from openai import AsyncOpenAI
from app.config import settings

log = logging.getLogger("trabahero")


def _fix_unquoted_keys(raw: str) -> str:
    """Fix JSON with unquoted keys that small models sometimes produce."""
    return re.sub(r'(?<=[{,\[])\s*(\w+)\s*:', r'"\1":', raw)


def _parse_json(raw: str) -> dict | list | None:
    if not raw or not raw.strip():
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        text = match.group()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                return json.loads(_fix_unquoted_keys(text))
            except json.JSONDecodeError:
                pass
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        text = match.group()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                return json.loads(_fix_unquoted_keys(text))
            except json.JSONDecodeError:
                pass
    return None


_SEVERITIES = {"low", "mid", "medium", "high", "moderate", "major", "minor", "critical", "severe", "info"}

_SECTION_RE = re.compile(
    r"^\s*(?P<kw>VALID|VERDICT[\s_]*PERCENTAGE|RED\s*FLAG|ANALYSIS|JOB\s*SUMMARY|END\s*(?:FLAGS|ANALYSIS|JOB\s*SUMMARY))\s*:?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)


def _normalize_severity(sev: str) -> str:
    s = (sev or "").strip().lower()
    if s in {"low", "minor", "info"}:
        return "low"
    if s in {"high", "critical", "severe", "major"}:
        return "high"
    return "mid"


def _parse_custom(raw: str) -> dict | None:
    """Parse the scan output format (labeled sections, not JSON)."""
    if not raw or not raw.strip():
        return None
    result: dict = {}
    flags: list[dict] = []
    section: str | None = None
    buf: list[str] = []
    matched_any = False

    def close_section() -> None:
        nonlocal section
        if section and buf:
            result[section] = "\n".join(buf).strip()
        section = None
        buf.clear()

    for line in raw.splitlines():
        m = _SECTION_RE.match(line)
        if not m:
            if section:
                buf.append(line)
            continue
        kw = " ".join(m.group("kw").split()).upper()
        rest = m.group("rest").strip()
        if kw == "END FLAGS":
            continue
        if kw in ("END ANALYSIS", "END JOB SUMMARY"):
            close_section()
            continue
        close_section()
        matched_any = True
        if kw == "VALID":
            val = rest.lower()
            result["valid"] = val in ("true", "yes", "1", "legitimate", "valid")
        elif kw == "VERDICT PERCENTAGE":
            num = re.search(r"\d{1,3}", rest)
            if num:
                result["verdict_percentage"] = int(num.group(0))
        elif kw == "RED FLAG":
            parts = [p.strip() for p in re.split(r"\s*\|\s*", rest) if p.strip()]
            if not parts:
                continue
            reasoning = parts[1] if len(parts) >= 3 else ""
            severity = parts[2] if len(parts) >= 3 else ""
            if len(parts) == 2:
                if parts[1].lower() in _SEVERITIES:
                    severity = parts[1]
                else:
                    reasoning = parts[1]
            flags.append({
                "flag": parts[0],
                "reasoning": reasoning,
                "severity": _normalize_severity(severity or "mid"),
            })
        elif kw in ("ANALYSIS", "JOB SUMMARY"):
            section = kw.lower().replace(" ", "_")
            if rest:
                buf.append(rest)
        else:
            matched_any = False
    close_section()
    if flags:
        result["red_flags"] = flags
    return result if matched_any or flags else None


async def chat(messages: list, max_tokens: int = 2048, temperature: float = 0.2) -> str:
    model = settings.model_name or "local-model"
    async with AsyncOpenAI(
        base_url=settings.lm_studio_url,
        api_key=settings.lm_studio_api_key,
        timeout=300.0,
        max_retries=0,
    ) as client:
        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (completion.choices[0].message.content or "").strip()


async def chat_json(messages: list, max_tokens: int = 2048, temperature: float = 0.2) -> dict | list | None:
    raw = await chat(messages, max_tokens, temperature)
    parsed = _parse_json(raw)
    if parsed is None:
        log.warning("Failed to parse AI JSON from response (%d chars)", len(raw))
    return parsed


async def chat_custom(messages: list, max_tokens: int = 2048, temperature: float = 0.2) -> dict | None:
    """Chat using the labeled-section output format (no JSON braces)."""
    raw = await chat(messages, max_tokens, temperature)
    parsed = _parse_custom(raw)
    if parsed is None:
        parsed = _parse_json(raw)
        if isinstance(parsed, dict):
            log.info("Custom parse failed; fell back to JSON for scan response")
    if parsed is None:
        log.warning("Failed to parse AI scan response (%d chars)", len(raw))
    return parsed if isinstance(parsed, dict) else None


async def chat_stream(messages: list, max_tokens: int = 2048, temperature: float = 0.2) -> str:
    """Stream a chat completion from LM Studio, yielding the full content text."""
    pieces: list[str] = []
    async for piece in chat_stream_pieces(messages, max_tokens, temperature):
        pieces.append(piece)
    return "".join(pieces).strip()


async def chat_stream_pieces(messages: list, max_tokens: int, temperature: float):
    """Async generator yielding each content delta from LM Studio as it arrives."""
    model = settings.model_name or "local-model"
    async with AsyncOpenAI(
        base_url=settings.lm_studio_url,
        api_key=settings.lm_studio_api_key,
        timeout=300.0,
        max_retries=0,
    ) as client:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            piece = chunk.choices[0].delta.content or ""
            if piece:
                yield piece

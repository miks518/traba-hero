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
        elif kw in ("VERDICT PERCENTAGE", "VERDICT_PERCENTAGE"):
            num = re.search(r"\d{1,3}", rest)
            if num:
                result["verdict_percentage"] = int(num.group(0))
        elif kw == "RED FLAG":
            parts = [p.strip() for p in re.split(r"\s*\|\s*", rest) if p.strip()]
            if not parts:
                continue
            flag_title = parts[0]
            flag_lower = flag_title.lower()
            if flag_lower in {
                "none", "no red flags", "no red flags detected", "n/a", "na",
                "no significant red flags", "none detected", "no flags", "no flags detected",
                "legitimate", "no issues found", "nil",
            } or flag_lower.startswith("no red flag") or flag_lower.startswith("no significant"):
                continue

            reasoning = parts[1] if len(parts) >= 3 else ""
            severity = parts[2] if len(parts) >= 3 else ""
            if len(parts) == 2:
                if parts[1].lower() in _SEVERITIES:
                    severity = parts[1]
                else:
                    reasoning = parts[1]
            flags.append({
                "flag": flag_title,
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
    result["red_flags"] = flags
    return result if matched_any or flags else None


async def chat(
    messages: list,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> str:
    model = settings.model_name or "local-model"
    eff_temp = temperature if temperature is not None else settings.ai_temperature
    eff_max_tokens = max_tokens if max_tokens is not None else settings.ai_max_tokens
    eff_top_p = top_p if top_p is not None else settings.ai_top_p

    async with AsyncOpenAI(
        base_url=settings.effective_ai_url,
        api_key=settings.effective_ai_api_key,
        timeout=300.0,
        max_retries=0,
    ) as client:
        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=eff_temp,
            top_p=eff_top_p,
            max_tokens=eff_max_tokens,
        )
        return (completion.choices[0].message.content or "").strip()


async def chat_json(
    messages: list,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> dict | list | None:
    raw = await chat(messages, max_tokens=max_tokens, temperature=temperature, top_p=top_p)
    parsed = _parse_json(raw)
    if parsed is None:
        log.warning("Failed to parse AI JSON from response (%d chars)", len(raw))
    return parsed


def _parse_resume_custom(raw: str) -> dict | None:
    """Parse resume analysis output using labeled section format, with fallback to JSON."""
    if not raw or not raw.strip():
        return None

    # First attempt labeled section parsing
    result: dict = {
        "skills": [],
        "experience_years": 0.0,
        "job_titles": [],
        "industries": [],
        "summary": "",
    }
    summary_lines: list[str] = []
    in_summary = False
    matched_any = False

    resume_section_re = re.compile(
        r"^\s*(?P<kw>SKILLS|EXPERIENCE[\s_]*YEARS|JOB[\s_]*TITLES|INDUSTRIES|SUMMARY|END[\s_]*SUMMARY)\s*:?\s*(?P<rest>.*)$",
        re.IGNORECASE,
    )

    for line in raw.splitlines():
        m = resume_section_re.match(line)
        if not m:
            if in_summary:
                summary_lines.append(line)
            continue

        kw = " ".join(m.group("kw").split()).upper().replace(" ", "_")
        rest = m.group("rest").strip()

        if kw == "END_SUMMARY":
            in_summary = False
            continue

        if kw == "SUMMARY":
            in_summary = True
            matched_any = True
            if rest:
                summary_lines.append(rest)
            continue

        in_summary = False
        matched_any = True

        if kw == "SKILLS":
            items = [s.strip().strip('"\'') for s in re.split(r"[,;|•\n]+", rest) if s.strip()]
            result["skills"].extend([i for i in items if i and i.lower() not in ("none", "n/a")])
        elif kw in ("EXPERIENCE_YEARS", "EXPERIENCE"):
            num = re.search(r"(\d+(?:\.\d+)?)", rest)
            if num:
                try:
                    result["experience_years"] = float(num.group(1))
                except ValueError:
                    pass
        elif kw in ("JOB_TITLES", "TITLES"):
            items = [s.strip().strip('"\'') for s in re.split(r"[,;|•\n]+", rest) if s.strip()]
            result["job_titles"].extend([i for i in items if i and i.lower() not in ("none", "n/a")])
        elif kw == "INDUSTRIES":
            items = [s.strip().strip('"\'') for s in re.split(r"[,;|•\n]+", rest) if s.strip()]
            result["industries"].extend([i for i in items if i and i.lower() not in ("none", "n/a")])

    if summary_lines:
        result["summary"] = "\n".join(summary_lines).strip()

    if matched_any and (result["skills"] or result["job_titles"] or result["summary"]):
        return result

    # Fallback to JSON parsing if model emitted JSON despite instructions
    json_parsed = _parse_json(raw)
    if isinstance(json_parsed, dict):
        log.info("Resume custom parse used JSON fallback")
        return json_parsed

    return None


async def chat_resume(
    messages: list,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> dict | None:
    """Analyze resume using labeled format (no braces) with JSON fallback."""
    raw = await chat(messages, max_tokens=max_tokens, temperature=temperature, top_p=top_p)
    parsed = _parse_resume_custom(raw)
    if parsed is None:
        log.warning("Failed to parse resume response (%d chars). Raw: %s", len(raw), raw[:300])
    return parsed


async def chat_custom(
    messages: list,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> dict | None:
    """Chat using the labeled-section output format (no JSON braces)."""
    raw = await chat(messages, max_tokens=max_tokens, temperature=temperature, top_p=top_p)
    parsed = _parse_custom(raw)
    if parsed is None:
        parsed = _parse_json(raw)
        if isinstance(parsed, dict):
            log.info("Custom parse failed; fell back to JSON for scan response")
    if parsed is None:
        log.warning("Failed to parse AI scan response (%d chars)", len(raw))
    return parsed if isinstance(parsed, dict) else None


async def chat_stream(
    messages: list,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> str:
    """Stream a chat completion from the AI provider, yielding the full content text."""
    pieces: list[str] = []
    async for piece in chat_stream_pieces(messages, max_tokens=max_tokens, temperature=temperature, top_p=top_p):
        pieces.append(piece)
    return "".join(pieces).strip()


async def chat_stream_pieces(
    messages: list,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
):
    """Async generator yielding each content delta from the AI provider as it arrives."""
    model = settings.model_name or "local-model"
    eff_temp = temperature if temperature is not None else settings.ai_temperature
    eff_max_tokens = max_tokens if max_tokens is not None else settings.ai_max_tokens
    eff_top_p = top_p if top_p is not None else settings.ai_top_p

    async with AsyncOpenAI(
        base_url=settings.effective_ai_url,
        api_key=settings.effective_ai_api_key,
        timeout=300.0,
        max_retries=0,
    ) as client:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=eff_temp,
            top_p=eff_top_p,
            max_tokens=eff_max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            piece = chunk.choices[0].delta.content or ""
            if piece:
                yield piece

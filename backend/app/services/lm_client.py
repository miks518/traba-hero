import json
import re
import logging
from openai import AsyncOpenAI
from app.config import settings

log = logging.getLogger("trabahero")

_client: AsyncOpenAI | None = None

# Request parameters the routed provider has rejected, so they are dropped for
# the rest of the process instead of costing a failed request every time.
_unsupported_params: set[str] = set()
_sent_config_logged = False


def _log_sent_config(model: str, eff_max_tokens: int, structured: bool) -> None:
    """Log the generation config once, so a failure can be read against it."""
    global _sent_config_logged
    if _sent_config_logged:
        return
    _sent_config_logged = True
    log.info(
        "[lm] Generation config in use: model=%s max_tokens=%s structured_output=%s "
        "reasoning_enabled=%s reasoning_cap=%s effort=%s dropped_params=%s",
        model,
        eff_max_tokens,
        "on" if structured else "off",
        "unset" if settings.ai_reasoning_enabled is None else settings.ai_reasoning_enabled,
        settings.ai_reasoning_max_tokens or "off",
        settings.ai_reasoning_effort or "off",
        sorted(_unsupported_params) or "none",
    )


def _reasoning_params() -> dict:
    """Build OpenRouter's normalized `reasoning` body, or {} when not configured.

    Reasoning models otherwise draw deliberation from the same max_tokens budget
    that has to hold the answer: with a 2048 cap the model spent the entire
    budget reasoning and returned no content at all. Three ways to stop that:

      enabled: false      turn reasoning off entirely — the cleanest option
      effort: low         reduce it at the source
      max_tokens: N       cap it (truncating can make a provider re-attempt)

    `enabled: false` wins over the other two, because the provider rejects a
    disabled reasoning combined with a high effort level, so sending them
    together risks a 400 for no benefit.
    """
    if settings.ai_reasoning_enabled is False:
        return {"reasoning": {"enabled": False}}

    reasoning: dict = {}
    if settings.ai_reasoning_enabled is True:
        reasoning["enabled"] = True
    if settings.ai_reasoning_max_tokens and settings.ai_reasoning_max_tokens > 0:
        reasoning["max_tokens"] = settings.ai_reasoning_max_tokens
    if settings.ai_reasoning_effort:
        reasoning["effort"] = settings.ai_reasoning_effort
    return {"reasoning": reasoning} if reasoning else {}


def _structured_output_body(schema: dict, name: str) -> dict:
    """Build the `response_format` + `provider` body for schema-enforced output.

    `provider.require_parameters` matters here: a model ID can route to several
    endpoints, and without it the request may land on one that does not support
    structured outputs and come back with prose instead of JSON.
    """
    return {
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": name,
                "strict": True,
                "schema": schema,
            },
        },
        "provider": {"require_parameters": True},
    }


def _request_extra_body(structured: dict | None) -> dict:
    """Assemble the extra request body, omitting anything the provider rejected."""
    body: dict = {}
    if "reasoning" not in _unsupported_params:
        reasoning = _reasoning_params()
        if reasoning:
            body.update(reasoning)
    if structured and "structured" not in _unsupported_params:
        body.update(structured)
    return body


def _rejected_param(exc: Exception) -> str | None:
    """Name the request parameter the provider refused, or None if not that."""
    if getattr(exc, "status_code", None) != 400:
        return None
    text = str(exc).lower()
    if not any(h in text for h in ("reasoning", "response_format", "json_schema", "structured", "schema", "unsupported", "unknown field", "unrecognized", "not allowed", "invalid_request_error")):
        return None
    if any(h in text for h in ("response_format", "json_schema", "structured", "schema")):
        return "structured"
    if "reasoning" in text:
        return "reasoning"
    return None


async def _create_completion(**kwargs):
    """Call the provider, dropping parameters it rejects.

    Not every provider behind an OpenRouter model supports `reasoning` or
    structured outputs. A 400 naming a parameter is a configuration problem, not
    a broken request, so it is retried without that parameter and then left out
    for the rest of the process.
    """
    structured = kwargs.pop("_structured", None)
    _log_sent_config(kwargs.get("model", "?"), kwargs.get("max_tokens", "?"), bool(structured))
    attempted: set[str] = set()
    while True:
        extra_body = _request_extra_body(structured)
        try:
            return await _get_client().chat.completions.create(extra_body=extra_body or None, **kwargs)
        except Exception as e:  # noqa: BLE001
            culprit = _rejected_param(e)
            if culprit is None or culprit in attempted:
                raise
            attempted.add(culprit)
            # Record before recomputing, otherwise the retry sends it again.
            _unsupported_params.add(culprit)
            log.warning(
                "[lm] Provider rejected the %s parameter (%s: %s). Continuing without it. %s",
                culprit,
                type(e).__name__,
                e,
                "Set the relevant setting to 0/blank to silence this warning." if culprit == "reasoning"
                else "Falling back to plain text output for this process.",
            )


class EmptyModelResponse(RuntimeError):
    """The provider returned a successful stream that contained no content.

    Raised instead of letting an empty string reach the output parsers, which
    would otherwise report an "unreadable response" and hide the real cause.
    """


def _chunk_extra(obj) -> dict:
    """Return the non-schema fields the provider attached to a chunk.

    The OpenAI SDK models do not declare OpenRouter's ``error`` object or the
    provider-specific ``reasoning`` field, so those arrive as extras and would
    be invisible unless they are read explicitly.
    """
    extra = getattr(obj, "model_extra", None)
    if isinstance(extra, dict):
        return extra
    return {}


def _describe_empty_chunk(chunk) -> str:
    """Best-effort description of a stream chunk that carried no content."""
    extra = _chunk_extra(chunk)
    error = getattr(chunk, "error", None) or extra.get("error")
    if error is not None:
        if isinstance(error, dict):
            detail = error.get("message") or error.get("code") or json.dumps(error)[:200]
        else:
            detail = str(error)
        return f"provider error frame: {detail}"
    return f"chunk with no choices (extra fields: {sorted(extra.keys()) or 'none'})"


def _describe_refusal(refusal: str) -> str:
    return f"model refusal: {refusal}"


def _get_client() -> AsyncOpenAI:
    """Return a shared AsyncOpenAI client, creating it on first call."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.effective_ai_url,
            api_key=settings.effective_ai_api_key,
            timeout=300.0,
            max_retries=0,
        )
    return _client


def _fix_unquoted_keys(raw: str) -> str:
    """Fix JSON with unquoted keys that small models sometimes produce."""
    return re.sub(r'(?<=[{,\[])\s*(\w+)\s*:', r'"\1":', raw)


def _parse_json(raw: str) -> dict | list | None:
    """Extract the first valid JSON object/array from raw text, tolerating
    surrounding prose and trailing JSON snippets."""
    if not raw or not raw.strip():
        return None
    for candidate in (raw, _fix_unquoted_keys(raw)):
        decoder = json.JSONDecoder()
        for i, ch in enumerate(candidate):
            if ch not in "{[":
                continue
            try:
                obj, _ = decoder.raw_decode(candidate, i)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, (dict, list)):
                return obj
    return None


_SEVERITIES = {"low", "mid", "medium", "high", "moderate", "major", "minor", "critical", "severe", "info"}

_SECTION_RE = re.compile(
    r"^\s*(?P<kw>VALID|RED\s*FLAG|COMPANY\s*NAME|EMPLOYER\s*NAME|POSTING\s*ANALYSIS|JOB\s*SUMMARY|END\s*(?:FLAGS|JOB\s*SUMMARY|POSTING\s*ANALYSIS))\s*:?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)

# Sections whose body runs until their END marker. END FLAGS is deliberately not
# in this set: it is a bare terminator for the red flag lines, and treating it as
# a section end used to reset the parser's matched_any flag.
_SECTION_END_KW = ("END JOB SUMMARY", "END POSTING ANALYSIS")

_HIGH_SEVERITY_KEYWORDS = {
    "upfront fee", "processing fee", "training fee", "registration fee",
    "assessment fee", "medical fee", "uniform fee", "payment required",
    "money collection", "will deduct from salary", "refundable deposit",
    "admin fee", "processing charge", "advance payment", "cash bond",
    "security deposit", "pay to apply", "pay before", "fee required",
    "requires payment", "must pay", "pay first", "initial fee",
}


def _infer_severity(label: str, reasoning: str) -> str:
    """Infer severity from flag content when LLM omits the severity field."""
    text = f"{label} {reasoning}".lower()
    for kw in _HIGH_SEVERITY_KEYWORDS:
        if kw in text:
            return "high"
    return "mid"


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
        if kw in _SECTION_END_KW:
            close_section()
            continue
        close_section()
        matched_any = True
        if kw == "VALID":
            val = rest.lower()
            result["valid"] = val in ("true", "yes", "1", "legitimate", "valid")
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
            if severity:
                final_severity = _normalize_severity(severity)
            else:
                final_severity = _infer_severity(flag_title, reasoning)
            flags.append({
                "flag": flag_title,
                "reasoning": reasoning,
                "severity": final_severity,
            })
        elif kw in ("COMPANY NAME", "EMPLOYER NAME"):
            # The employer name is what the verification step searches on, so the
            # model states it directly instead of leaving a downstream regex to
            # fish it out of the prose summary. EMPLOYER NAME is the current
            # label; COMPANY NAME is still accepted so scans recorded before the
            # rename still parse.
            result["company_name"] = rest.strip()
        elif kw == "POSTING ANALYSIS":
            # Assessment of the posting's structure, kept separate from the job
            # summary so the panel can show the verdict and the role separately.
            section = kw.lower().replace(" ", "_")
            if rest:
                buf.append(rest)
        elif kw == "JOB SUMMARY":
            section = kw.lower().replace(" ", "_")
            if rest:
                buf.append(rest)
        else:
            matched_any = False
    close_section()
    result["red_flags"] = flags
    return result if matched_any or flags else None


_MATCH_SECTION_RE = re.compile(
    r"^\s*(?P<kw>JOB_ID|SCORE|LABEL|SKILL_GAPS|MATCHED_SKILLS|REASONING|EXPERIENCE_FIT|INDUSTRY_FIT|RECOMMENDED_ACTIONS|END\s*JOB)\s*:?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)


def _parse_match_custom(raw: str) -> list[dict] | None:
    """Parse the resume match labeled section format. Returns a list of job match dicts."""
    if not raw or not raw.strip():
        return None
    matches: list[dict] = []
    current: dict = {}
    section: str | None = None
    buf: list[str] = []
    matched_any = False

    def close_section() -> None:
        nonlocal section
        if section and buf:
            current[section] = "\n".join(buf).strip()
        section = None
        buf.clear()

    for line in raw.splitlines():
        m = _MATCH_SECTION_RE.match(line)
        if not m:
            if section:
                buf.append(line)
            continue
        kw = " ".join(m.group("kw").split()).upper()
        rest = m.group("rest").strip()

        if kw == "END JOB":
            close_section()
            if current.get("job_id"):
                matches.append(current)
            current = {}
            matched_any = True
            continue

        close_section()
        matched_any = True

        if kw == "JOB_ID":
            current["job_id"] = rest
        elif kw == "SCORE":
            num = re.search(r"\d{1,3}", rest)
            current["score"] = int(num.group(0)) if num else 0
        elif kw == "LABEL":
            current["label"] = rest or "Low Compatibility"
        elif kw in ("SKILL_GAPS", "MATCHED_SKILLS", "RECOMMENDED_ACTIONS"):
            key = kw.lower()
            items = [x.strip() for x in re.split(r"[,;|\n]", rest) if x.strip()]
            current[key] = items
        elif kw == "REASONING":
            section = "reasoning"
            if rest:
                buf.append(rest)
        elif kw == "EXPERIENCE_FIT":
            current["experience_fit"] = rest or "Good Fit"
        elif kw == "INDUSTRY_FIT":
            current["industry_fit"] = rest or "Moderate"

    close_section()
    if current.get("job_id"):
        matches.append(current)

    return matches if matched_any and matches else None


async def chat(
    messages: list,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    response_format: dict | None = None,
) -> str:
    model = settings.model_name or "local-model"
    eff_temp = temperature if temperature is not None else settings.ai_temperature
    eff_max_tokens = max_tokens if max_tokens is not None else settings.ai_max_tokens
    eff_top_p = top_p if top_p is not None else settings.ai_top_p

    completion = await _create_completion(
        model=model,
        messages=messages,
        temperature=eff_temp,
        top_p=eff_top_p,
        max_tokens=eff_max_tokens,
        _structured=response_format,
    )
    content = (completion.choices[0].message.content or "").strip()
    if not content:
        # A reasoning model can spend the whole budget thinking and return
        # nothing, on the non-streaming path just as much as the streaming one.
        extra = getattr(completion.choices[0].message, "model_extra", None) or {}
        counts = {}
        for field in ("reasoning", "reasoning_content"):
            value = extra.get(field)
            counts[field] = len(value) if isinstance(value, str) else (1 if value else 0)
        mirrored = (
            isinstance(extra.get("reasoning"), str)
            and isinstance(extra.get("reasoning_content"), str)
            and extra.get("reasoning") == extra.get("reasoning_content")
        )
        reasoning_chars = sum(counts.values()) - (min(counts.values()) if mirrored else 0)
        detail = f"the model returned no content for model={model}"
        if reasoning_chars:
            detail += f" (~{reasoning_chars} chars of reasoning-only output; {counts}{', mirrored so counted once' if mirrored else ''})"
        log.error("[lm] %s", detail)
        raise EmptyModelResponse(detail)
    return content


async def chat_json(
    messages: list,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> dict | list | None:
    raw = await chat(messages, max_tokens=max_tokens, temperature=temperature, top_p=top_p)
    parsed = _parse_json(raw)
    if parsed is None:
        log.warning("[chat_json] Failed to parse JSON from AI response (%d chars): %s", len(raw), raw[:300])
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
        log.warning("[chat_resume] Failed to parse labeled-section format from AI (%d chars): %s", len(raw), raw[:300])
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
        log.warning("[chat_custom] Failed to parse labeled-section format from AI (%d chars): %s", len(raw), raw[:300])
    return parsed if isinstance(parsed, dict) else None


async def chat_match(
    messages: list,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> list[dict] | None:
    """Chat using the labeled-section match format with JSON fallback."""
    raw = await chat(messages, max_tokens=max_tokens, temperature=temperature, top_p=top_p)
    parsed = _parse_match_custom(raw)
    if parsed is None:
        fallback = _parse_json(raw)
        if isinstance(fallback, list):
            parsed = fallback
            log.info("Match custom parse failed; fell back to JSON array")
        elif isinstance(fallback, dict):
            parsed = [fallback]
            log.info("Match custom parse failed; fell back to single JSON object")
    if parsed is None:
        log.warning("[chat_match] Failed to parse labeled-section format from AI (%d chars): %s", len(raw), raw[:500])
    return parsed


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
    """Async generator yielding each content delta from the AI provider as it arrives.

    Everything the stream says about why it produced nothing is collected and
    reported. OpenRouter surfaces an upstream provider failure — a rate limit on
    the routed provider, for instance — as a data frame inside an otherwise
    successful 200 response, so a request that was accepted can still end with no
    content at all. Skipping those frames silently turns that into an empty
    string, which the callers then report as an unreadable response.
    """
    model = settings.model_name or "local-model"
    eff_temp = temperature if temperature is not None else settings.ai_temperature
    eff_max_tokens = max_tokens if max_tokens is not None else settings.ai_max_tokens
    eff_top_p = top_p if top_p is not None else settings.ai_top_p

    stream = await _create_completion(
        model=model,
        messages=messages,
        temperature=eff_temp,
        top_p=eff_top_p,
        max_tokens=eff_max_tokens,
        stream=True,
    )

    notes: list[str] = []
    finish_reason = None
    reasoning_by_field = {"reasoning": 0, "reasoning_content": 0}
    content_chars = 0
    no_choice_chunks = 0
    refusals = 0
    mirrored_chunks = 0

    async for chunk in stream:
        if not chunk.choices:
            no_choice_chunks += 1
            notes.append(_describe_empty_chunk(chunk))
            continue

        choice = chunk.choices[0]
        if choice.finish_reason:
            finish_reason = choice.finish_reason

        delta = choice.delta
        extra = _chunk_extra(delta)
        # Some providers mirror the same text into both reasoning fields. When
        # they are identical, count the pair once, or every character is counted
        # twice and a failure looks like the model thinking twice as long. When
        # they differ, both carry real output and both are counted.
        first = extra.get("reasoning_content")
        second = extra.get("reasoning")
        mirrored = isinstance(first, str) and isinstance(second, str) and first == second
        for field, value in (("reasoning_content", first), ("reasoning", second)):
            if value is None:
                continue
            if mirrored and field == "reasoning":
                continue
            if isinstance(value, str):
                reasoning_by_field[field] += len(value)
            elif value:
                reasoning_by_field[field] += 1
        if mirrored:
            mirrored_chunks += 1

        refusal = getattr(delta, "refusal", None)
        if refusal:
            refusals += 1
            notes.append(_describe_refusal(refusal))

        piece = delta.content or ""
        if piece:
            content_chars += len(piece)
            yield piece

    # A provider that mirrors the two fields would otherwise count every
    # character twice, which reads as the model thinking twice as long as it did.
    reasoning_chars = sum(reasoning_by_field.values())

    if content_chars == 0:
        detail = "; ".join(notes) if notes else "the stream contained no content and no error frame"
        if reasoning_chars:
            detail += (
                f" (~{reasoning_chars} chars of reasoning-only output;"
                f" reasoning={reasoning_by_field['reasoning']},"
                f" reasoning_content={reasoning_by_field['reasoning_content']}"
                f"{f', {mirrored_chunks} chunks mirrored so counted once' if mirrored_chunks else ''})"
            )
        log.error(
            "[lm] Stream produced no content. model=%s finish_reason=%s max_tokens=%s reasoning_enabled=%s reasoning_cap=%s effort=%s "
            "chunks_without_choices=%d refusals=%d content_chars=%d reasoning_chars=%d detail=%s",
            model,
            finish_reason,
            eff_max_tokens,
            "unset" if settings.ai_reasoning_enabled is None else settings.ai_reasoning_enabled,
            settings.ai_reasoning_max_tokens or "off",
            settings.ai_reasoning_effort or "off",
            no_choice_chunks,
            refusals,
            content_chars,
            reasoning_chars,
            detail,
        )
        raise EmptyModelResponse(detail)


async def chat_with_tools(
    messages: list,
    tools: list,
    max_rounds: int = 5,
    max_tokens: int | None = None,
) -> tuple[str, list[dict]]:
    """Multi-turn agentic loop with OpenAI-compatible tool calling.

    Returns:
        (final_text, search_log) where search_log is a list of
        {query, round, result_preview} dicts for the frontend.
    """
    from app.services.ai_tools import execute_tool

    model = settings.model_name or "local-model"
    eff_max_tokens = max_tokens if max_tokens is not None else settings.ai_max_tokens
    client = _get_client()
    search_log: list[dict] = []
    last_text = ""

    for round_num in range(1, max_rounds + 1):
        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=settings.ai_temperature,
            top_p=settings.ai_top_p,
            max_tokens=eff_max_tokens,
        )

        choice = completion.choices[0]
        message = choice.message

        if message.content:
            last_text = message.content.strip()

        if not message.tool_calls:
            return last_text, search_log

        messages.append(message.model_dump())

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            result = await execute_tool(fn_name, fn_args)
            query = fn_args.get("query", "")
            search_log.append({
                "query": query,
                "round": round_num,
                "result_preview": result[:200],
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    return last_text, search_log

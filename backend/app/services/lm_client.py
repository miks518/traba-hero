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


def _reasoning_params(thinking: bool | None = None) -> dict:
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

    `thinking` is the per-request override the frontend's Advanced-scan toggle
    sends. It wins over the settings for that one request: `True` turns
    reasoning on even when the deployment defaults it off, `False` turns it off
    even when the deployment defaults it on, and `None` (the default for every
    caller that does not carry the toggle) keeps the configured behaviour.
    """
    if thinking is True:
        reasoning: dict = {"enabled": True}
        if settings.ai_reasoning_effort:
            reasoning["effort"] = settings.ai_reasoning_effort
        return {"reasoning": reasoning}
    if thinking is False:
        return {"reasoning": {"enabled": False}}

    if settings.ai_reasoning_enabled is False:
        return {"reasoning": {"enabled": False}}

    reasoning = {}
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


def _request_extra_body(structured: dict | None, thinking: bool | None = None) -> dict:
    """Assemble the extra request body, omitting anything the provider rejected."""
    body: dict = {}
    if "reasoning" not in _unsupported_params:
        reasoning = _reasoning_params(thinking)
        if reasoning:
            body.update(reasoning)
    if structured and "structured" not in _unsupported_params:
        body.update(structured)
    # Drop provider routing parameter if the provider rejected it (e.g., Groq)
    if "provider" in _unsupported_params and "provider" in body:
        body.pop("provider", None)
    return body


# OpenRouter reports a request it cannot route as a 404, not the 400 a
# provider-issued rejection produces. The message is the only signal: the status
# alone is ambiguous, because 404 is also what a mistyped model ID returns.
_ROUTING_REJECTION_MARKERS = (
    "no endpoints found that can handle the requested parameters",
    "failed_routing_step",
    "filter by parameters",
)

# Tried in order when a routing rejection does not say which parameter caused it.
# `structured` is first because `provider.require_parameters` is the flag that
# makes routing strict in the first place, and it also travels with
# `response_format`, so dropping it clears both. Reasoning is far more widely
# supported and is the last thing to give up.
_ROUTING_FALLBACK_ORDER = ("structured", "reasoning")

# Sampling parameters, which travel as top-level arguments to `create()` rather
# than inside `extra_body`. A provider that refuses them is refusing a
# preference, not a capability, and refusing one of these should cost a scan
# nothing: the model has a default and will use it.
#
# "Reasoning" and "structured" are excluded deliberately. Reasoning changes what
# the model returns and structured output changes the response *shape*, so
# dropping either is a downgrade with consequences. Dropping `temperature` is
# not.
_GENERATION_PARAMS = (
    "temperature",
    "top_p",
    "top_k",
    "frequency_penalty",
    "presence_penalty",
)


def _rejected_param(exc: Exception, attempted: set[str]) -> str | None:
    """Name the request parameter the provider refused, or None if not that."""
    status = getattr(exc, "status_code", None)
    text = str(exc).lower()

    if status == 404 and any(m in text for m in _ROUTING_REJECTION_MARKERS):
        # A routing rejection names the step that failed, not the parameter, so
        # the culprit is worked out from what has already been dropped. When both
        # are gone there is nothing left to remove and the error propagates.
        for param in _ROUTING_FALLBACK_ORDER:
            if param not in attempted:
                return param
        return None

    if status != 400:
        return None

    # Checked before the generic marker gate below, because naming the parameter
    # *is* the signal and requiring a second word like "unsupported" alongside it
    # only loses cases. Deliberately also catches a complaint about the parameter's
    # *value* ("temperature must be between 0 and 2") rather than its existence:
    # omitting the parameter lets the provider use its own default, which is the
    # right degradation for a preference and beats failing the whole scan. The
    # warning names what was dropped, so a genuine misconfiguration is still loud.
    for param in _GENERATION_PARAMS:
        if param in text:
            return param

    if not any(h in text for h in ("reasoning", "response_format", "json_schema", "structured", "schema", "unsupported", "unknown field", "unrecognized", "not allowed", "invalid_request_error", "provider is unsupported", "provider not supported", "property 'provider'", 'property "provider"')):
        return None
    if any(h in text for h in ("response_format", "json_schema", "structured", "schema")):
        return "structured"
    if "reasoning" in text:
        return "reasoning"
    if any(h in text for h in ("provider is unsupported", "provider not supported", "property 'provider'", 'property "provider"')):
        return "provider"
    return None


async def _create_completion(**kwargs):
    """Call the provider, dropping parameters it rejects.

    Not every provider behind an OpenRouter model supports `reasoning` or
    structured outputs. A rejection is a configuration problem, not a broken
    request, so it is retried without that parameter and then left out for the
    rest of the process.

    Two shapes of rejection arrive. A provider-issued one is a 400 that names the
    parameter. An unroutable one is a 404 ("No endpoints found that can handle
    the requested parameters"), which is what a model with no structured-output
    endpoint produces â€” and the more common of the two, since a 404 was previously
    not recognised at all and took the whole request down.
    """
    structured = kwargs.pop("_structured", None)
    thinking = kwargs.pop("_thinking", None)
    # A parameter already found unsupported is not sent again: a second request
    # must not re-pay for the same discovery. `_request_extra_body` does this for
    # reasoning and structured because they travel inside it; these travel as
    # top-level kwargs, so it has to happen here.
    for param in _GENERATION_PARAMS:
        if param in _unsupported_params:
            kwargs.pop(param, None)
    _log_sent_config(kwargs.get("model", "?"), kwargs.get("max_tokens", "?"), bool(structured))
    attempted: set[str] = set()
    while True:
        extra_body = _request_extra_body(structured, thinking)
        try:
            return await _get_client().chat.completions.create(extra_body=extra_body or None, **kwargs)
        except Exception as e:  # noqa: BLE001
            culprit = _rejected_param(e, attempted)
            if culprit is None or culprit in attempted:
                raise
            attempted.add(culprit)
            # Record before recomputing, otherwise the retry sends it again.
            _unsupported_params.add(culprit)
            if culprit in _GENERATION_PARAMS:
                # These are top-level arguments to create(), not entries in
                # extra_body, so the only way to stop sending one is to remove it
                # from the call. `_request_extra_body` cannot do it.
                kwargs.pop(culprit, None)
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


# Alternation order is load-bearing twice over. Regex alternation takes the first
# alternative that lets the whole pattern match, and `\s` does not match the
# underscore these labels are written with, so `COMPANY` before `COMPANY NAME`
# swallows the legacy employer line into an attribute named "NAME: Acme". The
# longer alternative comes first.
#
# `SEARCH QUERIES` / `QUERY` were removed from this alternation rather than left
# dormant. They were parsed, capped at three, shipped on `ScanResponse`, and
# governed by two prompt rules -- and nothing read them. `search.py` builds the
# queries instead, from the posting's own stated attributes, which is both
# deterministic and impossible to write an accusation into. `QUERY_REF` stays:
# it records which posting detail an anomaly relates to, and is not a query.
# `SEARCH QUERIES` / `QUERY` are back, and this time something reads them:
# `VerifyRequest.search_queries` carries them to `/api/verify`, which issues them
# in place of the scheme queries `search.py` used to build. They were deleted in
# 413a2cd for exactly that reason - parsed, capped, shipped, and read by nothing.
#
# The cap is 2, not the 3 it used to be. One query is spent on the employer
# itself ("<company> company or employer"), so three model queries would cost
# four credits per verification on a 1,000/month free tier.
#
# `QUERY` precedes `QUERY_REF` in the alternation for the reason
# `COMPANY NAME` precedes `COMPANY`: the shorter alternative matches first and
# swallows the longer one's value, so `QUERY_REF: Location` would truncate to
# `QUERY` with `_REF: Location` as the query text.
#
# The conclusion-word filter is not here and never was: this regex decides what
# a line *is*, not whether its content is acceptable.
#
# It lives in `scanner/search_planner.py:search_query_is_safe`, and it runs in
# **every mode**: the adaptive planner applies it to its own follow-ups, the
# fixed mode applies it to the model's proposals where they are issued
# (`verification_flow`, before the cap), and the agent's tool calls are
# filtered at the parser (`scanner/agent_protocol.parse_tool_calls`) before
# any credit is spent. An earlier version of this comment said the prompt
# sentence was the only control in `fixed` mode; that record is amended, not
# left to contradict the code. See docs/decisions/search-retrieval.md.
#
# `JOB[_\s]*TITLE` joins the alternation for `JOB[_\s]*SUMMARY`'s reason — neither
# is a prefix of the other, so order is free, and `TITLE` is listed first to match
# the order the prompts emit them in. The `[_\s]` class matters: the prompts emit
# `JOB_TITLE` with an underscore, and `\s` does not match an underscore, so
# `JOB\s*TITLE` would parse as prose. `JOB\s*SUMMARY` had that shape and was
# widened here for the same reason — a model writing `JOB_SUMMARY` had it dropped.
#
# It is here because the alternation is an explicit enumeration: a key in
# `_ATTRIBUTE_KEYWORDS` and absent from this list parses as prose and is dropped
# silently. `test_the_keyword_list_and_the_regex_agree` is what keeps the two
# lists from drifting.
_SECTION_RE = re.compile(
    r"^\s*(?P<kw>VALID|ANOMALY|ANOMALIES|RED\s*FLAG|CODE|QUOTE|FEE_REASON|FEE[_\s]*RECIPIENT|FEE[_\s]*TIMING|MEETING[_\s]*PLACE[_\s]*KIND|ATTRIBUTES|END\s*ATTRIBUTES|COMPANY\s*NAME|COMPANY|JOB[_\s]*TITLE|LOCATION|CONTACT[_\s]*METHOD|CLAIMED[_\s]*TYPE|MEETING[_\s]*SPOT|PAY|REGISTERED[_\s]*AS|QUERY_REF|QUERY|SEARCH\s*QUERIES|END\s*SEARCH\s*QUERIES|EMPLOYER\s*NAME|POSTING\s*ANALYSIS|JOB[_\s]*SUMMARY|END\s*(?:FLAGS|ANOMALIES|JOB\s*SUMMARY|POSTING\s*ANALYSIS))\s*:?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)

# Sections whose body runs until their END marker. END ATTRIBUTES and
# END SEARCH QUERIES are deliberately NOT in this set: they are bare
# terminators, and treating a terminator as a section end resets the
# parser's matched_any flag, which makes a valid scan parse as nothing at all.
_SECTION_END_KW = ("END JOB SUMMARY", "END POSTING ANALYSIS")

# A model emits one of these to mean "nothing found". A surviving placeholder
# becomes a query, and a query for "none" is a credit spent to learn nothing.
# This is a parsing artifact rather than a judgment about query content, which is
# why it survived the removal of the conclusion-word filter: the model answering
# "QUERY: none" is answering the format, not proposing a search.
_QUERY_PLACEHOLDERS = {
    "", "none", "n/a", "na", "nothing", "none found", "no query", "not applicable", "-",
}

# The model's proposals, capped. Two static queries (the employer lookup and,
# when the posting names one, the location) run alongside these, so a ceiling
# of four puts a verification at six requests. A client that is not this
# extension can post a longer list; the cap in `verification_flow` enforces the
# same number where the queries are issued.
MAX_SEARCH_QUERIES = 4

# The keys an ATTRIBUTES block is read for, and the keys `_SECTION_RE` also
# matches anywhere in the response. They are ordinary English words the model
# uses in ordinary sentences, and the colon is optional for every key in
# `_SECTION_RE`, so a section body is full of lines that match them:
# "Company states applicants should bring their own laptop." is prose.
#
# So these five are gated on `in_attributes` and nothing else is. `COMPANY NAME`
# and `EMPLOYER NAME` are deliberately absent -- the employer path has to keep
# parsing outside the block, for scans recorded before the rename.
_ATTRIBUTE_KEYWORDS = (
    "COMPANY", "JOB_TITLE", "LOCATION", "CONTACT_METHOD", "MEETING_SPOT", "PAY",
    "REGISTERED_AS", "CLAIMED_TYPE", "FEE_RECIPIENT", "FEE_TIMING",
    "MEETING_PLACE_KIND",
)

# The keys the scan writes more than once, one line each.
#
# `CONTACT_METHOD` is the only one: a posting may give several ways to apply,
# and the interesting case is precisely when they disagree — the employer's own
# address on one line and a free-mail address on another. With a plain
# `attributes[key] = value` the second line silently replaces the first, so the
# channel that matters disappears from the claims the verifier tests, and
# `Channel Match` compares only the one that matched.
#
# Deliberately not every key. Accumulating all of them would merge two LOCATION
# lines into one unparseable value, which is a worse failure than a last-one-wins
# the prompt already discourages by telling the model to omit the line rather
# than repeat it.
_REPEATABLE_ATTRIBUTE_KEYS = frozenset({"CONTACT_METHOD"})

# What a repeat joins with. A plain string has to survive as a plain string:
# `VerifyRequest.attributes` is `dict[str, str]`, the extension sends
# `Record<string, string>`, and the verify prompt quotes the value back as one
# line under `- CONTACT_METHOD:`. A list would need changing in all three.
_ATTRIBUTE_JOIN = "; "


def _parse_custom(raw: str) -> dict | None:
    """Parse the scan output format (labeled sections, not JSON)."""
    if not raw or not raw.strip():
        return None
    result: dict = {}
    flags: list[dict] = []
    attributes: dict[str, str] = {}
    in_attributes = False
    in_queries = False
    # Opened by an ANOMALY line, closed by END ANOMALIES and by any other
    # keyword. CODE and QUOTE are gated on it because both are ordinary English
    # words; see the gate above.
    in_anomalies = False
    search_queries: list[str] = []
    last_anomaly: dict | None = None
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

        # `_SECTION_RE` accepts the two-word attributes spelled with a space as
        # well as with the underscore the prompt emits. Fold them onto the
        # underscore form so the gate below has one spelling to test. Scoped to
        # the attribute keys: folding `kw` wholesale would turn `COMPANY NAME`
        # into `COMPANY_NAME`, which is a different thing.
        if kw not in _ATTRIBUTE_KEYWORDS:
            underscored = kw.replace(" ", "_")
            if underscored in _ATTRIBUTE_KEYWORDS:
                kw = underscored

        if kw == "END ATTRIBUTES":
            in_attributes = False
            close_section()
            continue
        if kw == "END SEARCH QUERIES":
            # A bare terminator, not a section end: routing it through
            # `close_section` is what used to reset `matched_any` and make a
            # valid scan parse as nothing at all.
            in_queries = False
            continue
        if kw in _SECTION_END_KW:
            in_attributes = False
            close_section()
            continue

        if kw in _ATTRIBUTE_KEYWORDS and not in_attributes:
            if section:
                # Prose, not a key. `Company states applicants should bring their
                # own laptop.` matches `COMPANY`, and a matched keyword closes the
                # section first, so reading it as a key silently truncated the
                # assessment at that line - and could leave JOB SUMMARY absent
                # entirely, since `close_section` writes nothing for an empty
                # buffer. Appended back to the buffer rather than dropped: the
                # line is ordinary text and belongs to the section that is open.
                buf.append(line.rstrip())
                continue

            # No section is open, so this is the first attribute key of the
            # response and the `ATTRIBUTES:` header was omitted. Open the block
            # implicitly rather than discarding the key.
            #
            # The two cases are distinguishable exactly here: a key inside a
            # block is preceded by `ATTRIBUTES:`, and prose can only reach this
            # branch while a *section* is open - never a bare attribute line,
            # since a section body is the only place prose lives.
            #
            # Discarding instead would cost the attributes `build_scheme_queries`
            # reads, leaving zero scheme queries and three claim categories
            # structurally unfireable - the same symptom as the extension never
            # forwarding them, arriving by another route with no error anywhere.
            in_attributes = True

        # The block is opened by ATTRIBUTES and closed by END ATTRIBUTES *and* by
        # any other keyword. Gating on the terminator alone would keep harvesting
        # for the rest of the response - including inside POSTING ANALYSIS, which
        # is where the reported failure came from. An attribute key keeps the
        # block open; anything else ends it.
        if kw == "QUERY" and not in_queries and section:
            # A `QUERY:` line outside the block is prose, and a job summary that
            # happens to contain one is truncated by the branch below - the same
            # hazard the attribute gate handles above, for the same reason.
            # Appended back rather than dropped, so a section body stays whole.
            buf.append(line.rstrip())
            continue

        if kw in ("CODE", "QUOTE", "FEE_REASON") and not in_anomalies and section:
            # `CODE:` and `QUOTE:` are ordinary English words. "Enter CODE: 4471
            # at the gate" inside a job summary matches this regex, and a matched
            # keyword closes the section first - so reading it as a key silently
            # truncated the assessment at that line, which is the documented failure
            # mode for the ATTRIBUTES keys. Appended back, for the same reason
            # and with the same consequence of dropping it.
            buf.append(line.rstrip())
            continue

        if kw == "ATTRIBUTES":
            in_attributes = True
        elif kw not in _ATTRIBUTE_KEYWORDS:
            in_attributes = False

        # The anomaly block closes on any other keyword, exactly as the
        # attributes block does. END ANOMALIES is a non-attribute keyword, so it
        # lands here and clears the flag without needing its own branch — which
        # matters, because a dedicated `continue` for it would also skip the
        # handler chain below and change what `matched_any` ends up as. That is
        # pre-existing behaviour and changing it is a separate question.
        if kw not in ("ANOMALY", "ANOMALIES", "RED FLAG", "CODE", "QUOTE", "FEE_REASON", "QUERY_REF"):
            in_anomalies = False

        close_section()
        matched_any = True

        if kw == "ATTRIBUTES":
            # The body lines are read by the `_ATTRIBUTE_KEYWORDS` branch below.
            # Nothing is stored on the header line itself.
            continue
        if kw == "SEARCH QUERIES":
            # The model may put the first query on the header line itself, and
            # that is not an error - it is the format being answered.
            in_queries = True
            if rest and rest.lower() not in _QUERY_PLACEHOLDERS:
                search_queries.append(rest)
            continue
        if kw == "QUERY":
            if in_queries and rest and rest.lower() not in _QUERY_PLACEHOLDERS:
                search_queries.append(rest)
            continue
        if kw == "VALID":
            val = rest.lower()
            result["valid"] = val in ("true", "yes", "1", "legitimate", "valid")
        elif kw in ("ANOMALY", "ANOMALIES", "RED FLAG"):
            # RED FLAG is still accepted so a scan recorded before the rename
            # parses, the same way EMPLOYER NAME remains accepted alongside
            # COMPANY NAME. The prompt asks for ANOMALY; this is a fallback, not
            # a second supported spelling.
            parts = [p.strip() for p in re.split(r"\s*\|\s*", rest) if p.strip()]
            if not parts:
                continue
            flag_title = parts[0]
            flag_lower = flag_title.lower()
            # Placeholders the model emits to mean "nothing found". Both the
            # anomaly and the legacy red-flag spellings are listed because a
            # model asked for one may answer with either, and a placeholder that
            # survives becomes a finding about nothing.
            if flag_lower in {
                "none", "no red flags", "no red flags detected", "n/a", "na",
                "no significant red flags", "none detected", "no flags", "no flags detected",
                "no anomalies", "no anomalies detected", "no significant anomalies",
                "no anomaly", "legitimate", "no issues found", "nil",
            } or (
                flag_lower.startswith("no red flag")
                or flag_lower.startswith("no significant")
                or flag_lower.startswith("no anomal")
            ):
                continue

            reasoning = parts[1] if len(parts) >= 2 else ""
            last_anomaly = {
                "flag": flag_title,
                "reasoning": reasoning,
                "query_ref": "",
                "code": "",
                "quote": "",
                "fee_reason": "",
            }
            flags.append(last_anomaly)
            in_anomalies = True
        elif kw == "CODE":
            # Which taxonomy entry this finding is. Attaches to the anomaly
            # above it, like QUERY_REF. A CODE line with no anomaly above it is
            # ignored rather than guessed at — there is nothing to label.
            if last_anomaly is not None:
                last_anomaly["code"] = rest.strip()
        elif kw == "QUOTE":
            # The posting's own words for this finding. Kept as written here and
            # screened in `_anomalies`, which is the last gate before the wire.
            if last_anomaly is not None:
                last_anomaly["quote"] = rest.strip()
        elif kw == "FEE_REASON":
            # The reason the posting gives for a fee. A fact the classifier
            # reads, never a judgement: "medical clearance" is what the posting
            # says, not whether the fee is justified.
            if last_anomaly is not None:
                last_anomaly["fee_reason"] = rest.strip()
        elif kw == "QUERY_REF":
            # Which search this finding relates to. Optional: an anomaly judged
            # not worth a query has none, and therefore no corroboration path —
            # which is correct, since a low-severity note is never corroborated.
            if last_anomaly is not None:
                last_anomaly["query_ref"] = rest
        elif kw in _ATTRIBUTE_KEYWORDS:
            # A detail the posting did not state is omitted entirely rather than
            # stored empty. An empty LOCATION would read as "the posting stated
            # no location", which is a different claim, and would generate a
            # query that cannot succeed.
            #
            # Only reachable inside the ATTRIBUTES block: the gate above turns
            # the same words into prose everywhere else.
            if rest and rest.lower() != "not stated":
                # A repeatable key accumulates; every other key is last-one-wins.
                # See `_REPEATABLE_ATTRIBUTE_KEYS` for why the two differ.
                if kw in _REPEATABLE_ATTRIBUTE_KEYS and kw in attributes:
                    attributes[kw] = f"{attributes[kw]}{_ATTRIBUTE_JOIN}{rest}"
                else:
                    attributes[kw] = rest
        elif kw in ("COMPANY NAME", "EMPLOYER NAME"):
            # The employer name is what the verification step searches on, so the
            # model states it directly instead of leaving a downstream regex to
            # fish it out of the prose summary. EMPLOYER NAME is the current
            # label; COMPANY NAME is still accepted so scans recorded before the
            # rename still parse.
            result["company_name"] = rest.strip()
        elif kw == "POSTING ANALYSIS":
            # Assessment of the posting's structure, kept separate from the job
            # summary so the panel can show the assessment and the role separately.
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
    result["anomalies"] = flags
    result["attributes"] = attributes
    result["search_queries"] = search_queries[:MAX_SEARCH_QUERIES]
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
    endpoint: str = "",
    thinking: bool | None = None,
) -> str:
    model = settings.resolve_model(endpoint) or "local-model"
    eff_temp = temperature if temperature is not None else settings.ai_temperature
    eff_max_tokens = max_tokens if max_tokens is not None else settings.resolve_max_tokens(endpoint)
    eff_top_p = top_p if top_p is not None else settings.ai_top_p

    completion = await _create_completion(
        model=model,
        messages=messages,
        temperature=eff_temp,
        top_p=eff_top_p,
        max_tokens=eff_max_tokens,
        _structured=response_format,
        _thinking=thinking,
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


async def chat_turn(
    messages: list,
    *,
    endpoint: str = "assess",
) -> str:
    """One turn of the agent session: the whole transcript in, one text out.

    `chat` already takes a message list; `chat_turn` exists so the agent loop
    has a named seam that says what it is. The transcript is sent whole and
    the caller re-includes the posting on every turn — nothing between here
    and the provider summarises it, which is the whole fix for the scan→verify
    relay. The agent's tool calls arrive as labeled text parsed by
    `agent_protocol`, not a `tools=` parameter: native tool calling is not
    available on this client and is not guaranteed across OpenRouter routes.
    """
    return await chat(messages, endpoint=endpoint)


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
            items = [s.strip().strip('"\'') for s in re.split(r"[,;|â€¢\n]+", rest) if s.strip()]
            result["skills"].extend([i for i in items if i and i.lower() not in ("none", "n/a")])
        elif kw in ("EXPERIENCE_YEARS", "EXPERIENCE"):
            num = re.search(r"(\d+(?:\.\d+)?)", rest)
            if num:
                try:
                    result["experience_years"] = float(num.group(1))
                except ValueError:
                    pass
        elif kw in ("JOB_TITLES", "TITLES"):
            items = [s.strip().strip('"\'') for s in re.split(r"[,;|â€¢\n]+", rest) if s.strip()]
            result["job_titles"].extend([i for i in items if i and i.lower() not in ("none", "n/a")])
        elif kw == "INDUSTRIES":
            items = [s.strip().strip('"\'') for s in re.split(r"[,;|â€¢\n]+", rest) if s.strip()]
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
    endpoint: str = "",
    thinking: bool | None = None,
):
    """Async generator yielding each content delta from the AI provider as it arrives.

    Everything the stream says about why it produced nothing is collected and
    reported. OpenRouter surfaces an upstream provider failure â€” a rate limit on
    the routed provider, for instance â€” as a data frame inside an otherwise
    successful 200 response, so a request that was accepted can still end with no
    content at all. Skipping those frames silently turns that into an empty
    string, which the callers then report as an unreadable response.
    """
    model = settings.resolve_model(endpoint) or "local-model"
    eff_temp = temperature if temperature is not None else settings.ai_temperature
    eff_max_tokens = max_tokens if max_tokens is not None else settings.resolve_max_tokens(endpoint)
    eff_top_p = top_p if top_p is not None else settings.ai_top_p

    stream = await _create_completion(
        model=model,
        messages=messages,
        temperature=eff_temp,
        top_p=eff_top_p,
        max_tokens=eff_max_tokens,
        stream=True,
        _thinking=thinking,
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

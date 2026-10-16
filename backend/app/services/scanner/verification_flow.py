import asyncio
import logging
from collections.abc import AsyncIterator

from app.config import settings
from app.models.schemas import RISK_LEVELS, VerificationItem, VerifyRequest
from app.services.lm_client import MAX_SEARCH_QUERIES
from app.services.search import _canonical_url

from .dependencies import runtime
from .verification_parser import VerificationParseError
from .verification_prompt import expected_categories


log = logging.getLogger("trabahero")


def _bind_to_retrieved(items: list, evidence: list, allowed: frozenset[str]) -> tuple[list, list]:
    """Drop citations the search provider never returned, and demote any `red`
    that nothing backs.

    `VERIFY_PROMPT.md` asks for a `source_url` "copied exactly from the results"
    and calls a constructed one a fabricated citation, but a prompt sentence is
    not a control: both the structured path and the labeled-text fallback copied
    whatever the model wrote, and `search.py:_canonical_url` — the normaliser a
    membership test needs — existed only for the dedupe.

    `allowed` is the set of URLs that were actually retrieved, in any spelling.
    It is canonicalised here rather than at the call site, because a caller that
    forgets and passes pre-canonicalised values would silently drop every
    legitimate citation — a fail-closed failure that looks like the model
    inventing sources.

    A `red` is demoted to `yellow` rather than dropped, because `yellow` already
    carries zero weight in `risk_calculator` and already means "we could not
    confirm this". An unbacked `red` is precisely that, so the existing semantics
    are the ones being enforced and the calculator needs no change. It also
    handles the common case for free: a failed or empty search produces an empty
    `allowed` set, and then nothing is refuted by anything.

    `source_title` is cleared with the URL, because it names the page the reader
    was just sent to.
    """
    permitted = {_canonical_url(u) for u in allowed if u}

    bound: list[VerificationItem] = []
    for item in items:
        url = (item.source_url or "").strip()
        if url and _canonical_url(url) not in permitted:
            log.warning(
                "[verify] Dropped a citation that was not in the retrieved results: %r", url
            )
            url = ""
            item.source_title = ""
        if not url and item.status == "red":
            item.status = "yellow"
        item.source_url = url
        bound.append(item)

    kept: list[dict] = []
    for entry in evidence:
        url = str(entry.get("url") or "").strip()
        if not url or _canonical_url(url) not in permitted:
            continue
        kept.append(entry)
    return bound, kept


def _read_risk_level(raw) -> str | None:
    """The model's overall level, validated against the vocabulary.

    Anything unrecognised becomes `None` rather than being coerced. `None` means
    nothing was assessed, and the panel already has a rendering for it; a
    misspelt level reaching the wire as truth would put a colour on a posting
    that no stage ever judged. The schema's enum makes this unreachable on the
    structured path, but the no-schema path has no enum — only this prompt's
    wording — so the check has to exist.
    """
    level = str(raw or "").strip().lower()
    if level in RISK_LEVELS:
        return level
    if level:
        log.warning("[verify] Ignoring unrecognised risk_level %r", level)
    return None


def _read_verify_output(
    text: str, allowed_urls: frozenset[str] = frozenset()
) -> tuple[list, str, str, bool, list, str | None]:
    """Read the verification result, preferring JSON and falling back to text.

    JSON is the intended shape, but the provider may still answer with prose if
    it does not support structured outputs, so the labeled-text parser remains as
    a fallback rather than being deleted. Returns (items, report, recommendation,
    used_json, evidence, risk_level).

    `allowed_urls` holds the canonical form of every URL the search provider
    actually returned. Anything outside it is dropped, and a `red` left without a
    citation is demoted to `yellow` — see `_bind_to_retrieved`. It defaults to
    empty, which drops every citation: that is the fail-closed answer for a
    caller holding no result set to check against, and nothing should reach the
    wire unbound by accident.

    Raises `VerificationParseError` when the fallback cannot read the response
    either. A request that succeeds and a response nobody can read is a failure,
    and returning an empty item list here would hide it — the panel would render
    its empty-result notice as though the model had reported nothing.
    """
    payload = runtime.get_parse_json()(text)
    if isinstance(payload, dict) and isinstance(payload.get("checks"), list):
        items = []
        for check in payload["checks"]:
            if not isinstance(check, dict):
                continue
            category = str(check.get("category") or "").strip()
            status = str(check.get("status") or "").strip().lower()
            if not category or status not in ("green", "yellow", "red"):
                log.warning("[verify] Ignoring malformed check entry: %r", check)
                continue
            items.append(VerificationItem(
                label=category,
                status=status,
                explanation=str(check.get("finding") or check.get("detail") or "").strip(),
                source_title=str(check.get("source_title") or "").strip(),
                source_url=str(check.get("source_url") or "").strip(),
            ))

        evidence = []
        raw_evidence = payload.get("evidence")
        if isinstance(raw_evidence, list):
            for entry in raw_evidence:
                if not isinstance(entry, dict):
                    continue
                url = str(entry.get("url") or "").strip()
                if not url:
                    continue
                evidence.append({
                    "title": str(entry.get("title") or "").strip(),
                    "url": url,
                    "snippet": str(entry.get("snippet") or "").strip(),
                })
        bound_items, bound_evidence = _bind_to_retrieved(items, evidence, allowed_urls)
        return (
            bound_items,
            str(payload.get("report") or ""),
            str(payload.get("recommendation") or ""),
            True,
            bound_evidence,
            _read_risk_level(payload.get("risk_level")),
        )

    log.warning("[verify] Response was not JSON; falling back to the labeled-text parser.")
    try:
        items = runtime.get_parse_verification_result()(text)
    except VerificationParseError as exc:
        # The request succeeded and the response could not be read. Returning an
        # empty list here would render three empty cards with no error anywhere,
        # so the failure is reported instead.
        log.error("[verify] Response was neither JSON nor readable labeled text: %s. raw=%s",
                  exc, text[:400])
        raise VerificationParseError(str(exc)) from exc
    report = runtime.get_parse_verify_section()(text, "REPORT")
    recommendation = runtime.get_parse_verify_section()(text, "RECOMMENDATION")
    bound_items, _bound_evidence = _bind_to_retrieved(items, [], allowed_urls)
    # None on this path, and that is the honest answer rather than a default: the
    # labeled-text format has no place to carry a level, so nothing was assessed.
    # The panel renders null as Unverified and excludes it from resume matching.
    return bound_items, report, recommendation, False, [], None


async def verification_event_stream(req: VerifyRequest) -> AsyncIterator[str]:
    limiter = runtime.get_ai_limiter()
    await limiter.acquire()
    try:
        yield runtime.get_sse()({"type": "progress", "percent": 5, "stage": "Preparing verification"})

        company = (req.company_name or "").strip()
        if not runtime.get_company_name_is_valid()(company):
            log.warning("[verify] No valid company name provided ('%s') — stopping verification endpoint early.", company)
            yield runtime.get_sse()({"type": "progress", "percent": 100, "stage": "Cannot verify company name"})
            # No company name means there is nothing to search for, so there are
            # no verification results and therefore no risk score. The finding
            # is "we could not check", which is absent evidence, not a negative
            # one, so the status is yellow rather than red.
            explanation = "The job posting does not name an employer, so there was nothing to look up."
            items = [
                VerificationItem(
                    label="Company Existence",
                    status="yellow",
                    explanation=explanation,
                )
            ]
            report = (
                "External verification was skipped because the job posting does not name an employer. "
                "The findings below come only from reading the posting itself."
            )
            recommendation = "Confirm who you would be dealing with through an official channel before sending personal details."
            # No employer lookup happened, so nothing here can be weighed against
            # anything. The level used to fall back to the posting-stage ladder,
            # which meant a posting naming no employer was scored by the one
            # stage that has never seen evidence - and a posting that names no
            # employer is exactly where the posting text is all there is. It now
            # carries no level, and the panel says the lookup did not happen
            # rather than reporting a number derived from the absence of one.
            breakdown = {"sources": [], "verification_score": None, "risk_level": None,
                         "level_source": None}
            yield runtime.get_sse()({"type": "result", "data": {
                "items": [item.model_dump() for item in items],
                "report": report,
                "recommendation": recommendation,
                "riskScore": None,
                "riskLevel": None,
                "scoreBreakdown": breakdown,
                "search_ok": False,
                "search_error": "No employer name was given, so nothing was searched.",
                # Always present, never conditional. A client reading
                # `scheme_queries.length` would otherwise throw on exactly the
                # response that most obviously searched nothing — and there is no
                # query to report, because a stated detail with no employer
                # attached is a place, not an impersonation.
                "scheme_queries": [],
                "no_company_name": True,
            }})
            return

        yield runtime.get_sse()({"type": "progress", "percent": 10, "stage": "Searching company info"})
        # Two query families, one flat result set, one model call. Neither family
        # carries a category suffix: the model sorts the merged results into the
        # categories itself, so nothing here decides what a result is.
        #
        # The company queries find what is published about the employer. Two of
        # them because one cannot serve every category — `"<company> Philippines"`
        # ranks the employer's own site first, and those pages do not state
        # registration numbers.
        #
        # They also find nothing when a scam borrows a real company's name,
        # because the real company's reputation is clean, which is exactly why
        # the impersonation is invisible to them. The scheme queries name a
        # detail the posting itself stated, so they reach the pages that pair
        # the claim with the employer making it.
        #
        # `getattr` because the request may predate the field: a client that
        # never sends `attributes` must produce no scheme query, not an
        # AttributeError halfway through the stream.
        company_queries = runtime.get_build_queries()(company)
        # The model's own proposals, in place of the scheme queries this used to
        # build from `attributes`. Read off the request rather than off the
        # response, because the extension is what carries them across.
        #
        # `getattr` for the same reason as `attributes`: a client that predates
        # the field sends none, and must produce no query rather than an
        # AttributeError halfway through the stream.
        model_queries = list(getattr(req, "search_queries", None) or [])[:MAX_SEARCH_QUERIES]
        # Concatenated, not merged. The loop below was already written to handle
        # a list where some queries succeed and some fail, and that is the shape
        # three queries of mixed provenance produce.
        queries = company_queries + model_queries
        collected: list = []
        # TEMPORARY DIAGNOSTIC. The provider's raw body per query, so the panel
        # can show what Tavily actually returned. Remove alongside
        # SearchOutcome.raw_response and the suspended assertion in
        # test_no_debug_surface.py.
        raw_dump: list[dict] = []
        # (query, error) rather than the query alone: the panel is told *why*
        # retrieval failed, and a bare query string would report "Acme
        # Philippines" to the user in place of "TAVILY_API_KEY is not
        # configured", which is both useless and alarming.
        failures: list[tuple[str, str]] = []

        for i, query in enumerate(queries, 1):
            yield runtime.get_sse()({"type": "search", "query": query, "round": i})
            outcome = await asyncio.to_thread(runtime.get_search(), query)
            if outcome.ok:
                collected.append(outcome.results)
            else:
                # One failure is not a total failure: the other query may have
                # worked, and discarding it would understate what was checked.
                failures.append((query, outcome.error))
                log.warning("[verify] Search failed for '%s': %s", query, outcome.error)
            if outcome.raw_response:  # TEMPORARY DIAGNOSTIC
                raw_dump.append({"query": query, "raw": outcome.raw_response})

        ok = bool(collected) or not failures
        partial = bool(failures) and bool(collected)
        first_error = failures[0][1] if failures else ""

        if not collected and not failures:
            log.info("[verify] Searches for '%s' returned no results", company)
        elif partial:
            log.warning(
                "[verify] %d of %d searches failed for '%s'; coverage is partial",
                len(failures), len(queries), company,
            )

        # Dedupe on canonical URL: the employer's own site appears in both
        # result sets, and every result is prompt text competing for a budget
        # shared with the model's reasoning. Capped so the merged list cannot
        # outgrow what one query produced by much.
        merged = runtime.get_merge_results()(
            *collected, cap=settings.tavily_max_results * 2
        )
        search_context = runtime.get_format_results()(
            merged, company, ok, first_error
        )
        yield runtime.get_sse()({"type": "progress", "percent": 45, "stage": "AI analyzing"})

        # The exact text handed to the model, so the search -> prompt -> answer
        # chain can be inspected in the panel. See SearchRawPanel.
        verify_prompt = runtime.get_build_verify_prompt()(req, search_context)
        messages = [
            {"role": "system", "content": runtime.get_verify_system_prompt()},
            {"role": "user", "content": verify_prompt},
        ]

        final_text = await runtime.get_chat()(
            messages,
            response_format=runtime.get_verify_response_format(),
            endpoint="verify",
        )
        log.info("[verify] Raw AI response (%d chars): %s", len(final_text), final_text[:1000])
        yield runtime.get_sse()({"type": "progress", "percent": 85, "stage": "Analyzing results"})

        # The retrieved set, which `_bind_to_retrieved` needs and which was
        # otherwise never consulted again until `search_count` — that gap is
        # what left the citation unbound.
        retrieved_urls = frozenset(
            r.url for r in merged if getattr(r, "url", "")
        )
        items, report, recommendation, used_json, evidence, risk_level = _read_verify_output(
            final_text, allowed_urls=retrieved_urls
        )

        # A partial parse used to be silent: the panel showed one card while the
        # raw response clearly listed three, with nothing in the log to connect
        # the two. Name what is missing so the next occurrence is diagnosable.
        #
        # The expectation is the *gated* set — what the posting's own claims made
        # testable — not all six categories. Comparing against six would warn on
        # every scan that states no location, and a warning that fires on almost
        # every request is a warning nobody reads.
        expected = expected_categories(req)
        missing = runtime.get_missing_categories()(items, expected)
        if missing:
            log.warning(
                "[verify] Parsed %d of %d expected categories; missing: %s. raw=%s json=%s",
                len(items),
                len(expected),
                ", ".join(missing),
                used_json,
                final_text[:800],
            )

        if not items:
            # Only the readable-but-empty case reaches here: a response nobody
            # could read raised in _read_verify_output, so this branch never
            # reports an unreadable response as a result. The card is a fact
            # about our own output, not a finding about the employer.
            log.warning("[verify] Failsafe triggered: response was readable but carried no usable checks. Raw: %s", final_text[:300])
            items = [
                VerificationItem(
                    label="Company Existence",
                    status="yellow",
                    explanation=f"No structured findings could be read from the search results for '{company}'.",
                )
            ]
            if not report:
                report = f"Structured findings could not be parsed from the search results for '{company}', so no risk score was calculated."
            if not recommendation:
                recommendation = "Confirm the employer independently before submitting personal details."
            # The model produced no usable answer, so it never reached a level.
            # Defaulting to `low` here would put a reassuring colour on the one
            # case where we know least, which is the inverse of what happened
            # before this moved: the ladder scored an empty result as zero.
            risk_level = None

        # The level is the model's, not the calculator's. `risk_calculator` priced
        # the *category* of a finding - a processing fee was worth 40 whoever
        # asked for it - and its Saaty matrix was fitted to justify a dial that
        # had been drawn first. The verification stage holds the one thing the
        # ladder never could: who was asking, and whether they exist. A fee from
        # a business a reader can find is ordinary; the same fee from a name that
        # appears nowhere is not.
        refutation_score = runtime.get_refutation_score()(items)
        risk_score = None
        breakdown: dict = {"sources": ["verification"]}

        # The wire key stays `verification_score`; the value no longer matches
        # the name. It now holds a refutation score -- a 0-50 sum over refuted
        # claims -- where it used to hold a 0-100 share of the final score, and
        # where the common case is now `None` (nothing was refuted) against a key
        # that says "verification". The client translates it to `refutationScore`
        # at the api boundary. Changing the wire key needs a migration for stored
        # scan history, which is why it is not done here.
        breakdown["verification_score"] = refutation_score
        breakdown["risk_level"] = risk_level
        breakdown["level_source"] = "verification"

        log.info("[verify] Parsed items=%d, report_len=%d, rec_len=%d, refutation_score=%s, risk_level=%s", len(items), len(report), len(recommendation), refutation_score, risk_level)
        if items:
            log.info("[verify] Items: %s", items)
        if report:
            log.info("[verify] Report: %s", report[:200])
        if recommendation:
            log.info("[verify] Recommendation: %s", recommendation[:200])

        yield runtime.get_sse()({"type": "result", "data": {
            "items": [item.model_dump() for item in items],
            "evidence": evidence,
            "report": report,
            "recommendation": recommendation,
            "riskScore": None,
            "riskLevel": risk_level,
            "scoreBreakdown": breakdown,
            # On the wire, not left to the model. A prompt instruction to "state
            # that the search did not complete" only works if the model obeys;
            # a model that omits it would render three yellow cards identical to
            # a company with no footprint. The panel states this directly.
            #
            # `search_partial` is the state a single search never had: one of
            # two failed, so the answer is real but some categories are thinner
            # than they look. Reporting `search_ok: true` with no caveat would
            # overstate the coverage, and reporting a total failure would
            # discard a search that worked.
            "search_ok": ok,
            "search_partial": partial,
            "search_error": first_error,
            "search_count": len(merged),
            "queries_issued": len(queries),
            # Which of those queries the scan model proposed, so the panel can
            # say what was looked up. Reported separately from `queries_issued`
            # because the two families answer different questions: one asks
            # about the employer, the other about whether the posting's claims
            # are the employer's own.
            #
            # Renamed from `scheme_queries`: nothing builds these from
            # attributes any more, and the panel reads this out as *what was
            # searched*. A field name describing a mechanism that no longer
            # exists would be a small lie in the one place the user can audit
            # the lookup.
            "model_queries": model_queries,
            "queries_failed": len(failures),
            "debug_search_raw": raw_dump,  # TEMPORARY DIAGNOSTIC — remove with SearchOutcome.raw_response
            "no_company_name": False,
        }})
    except Exception as e:  # noqa: BLE001
        log.error("[verify] Error: %s: %s", type(e).__name__, e)
        yield runtime.get_sse()({"type": "error", "error": "Verification failed. Please try again."})
    finally:
        limiter.release()

import asyncio
import logging
from collections.abc import AsyncIterator

from app.config import settings
from app.models.schemas import (
    RISK_LEVELS,
    AnomalyAssessment,
    VerificationItem,
    VerifyRequest,
)
from app.services.lm_client import MAX_SEARCH_QUERIES
from app.services.search import _canonical_url

from .channel_match import (
    SOURCE_INDEPENDENT_ESCALATIONS,
    apply_channel_rules,
    assess_channel_match,
    has_channel_content,
    read_channel_facts,
    with_official_only_if_retrieved,
)
from .dependencies import runtime
from .request_class import classify_request, facts_from_scan
from .search_planner import (
    classify_signals,
    label_results,
    plan_followups,
    resolve_entity,
    search_query_is_safe,
)
from .verdict import code_verdict
from .verification_parser import VerificationParseError
from .verification_prompt import clean_recommendation, clean_verdict_reason, expected_categories


log = logging.getLogger("trabahero")


async def _search(query: str, scope) -> object:
    """One provider call, with the scope passed only when there is one.

    `search(query, None)` and `search(query)` are equivalent today â€” the second
    positional is `max_results` and `None` falls through to the setting â€” but
    only the second is the call `fixed` mode has always made, and a collaborator
    substituted by a test or a wrapper is entitled to see it unchanged. **The flag
    off must not alter the call, not merely the queries.**
    """
    if scope:
        return await asyncio.to_thread(
            runtime.get_search(), query, include_domains=list(scope)
        )
    return await asyncio.to_thread(runtime.get_search(), query)


async def _issue(queries: list, concurrent: bool = True) -> tuple[list, list, list, list]:
    """Run one round's queries and return what came back.

    Returns `(collected, failures, raw_dump, per_query)`:
      * `collected` â€” one list of results per successful query, for `merge_results`
      * `failures` â€” one `(query, error)` per failure
      * `raw_dump` â€” the raw diagnostic bodies, TEMPORARY
      * `per_query` â€” `(query, outcome)` in the order issued, **including
        failures**

    `per_query` exists so the caller never has to realign `collected` against
    the query list. A query that fails contributes nothing to `collected`, so
    zipping the two pairs a later query's results with an earlier query's name â€”
    which would attribute evidence to a search that did not retrieve it.

    **A planned round runs together, because a follow-up round only exists once
    its questions are known and there is no reason to make a reader wait for the
    first of two questions before the second one starts.** The SSE `search` events
    are emitted by the caller before this is awaited, which keeps the event order
    identical to a sequential loop.

    `concurrent=False` runs them one at a time, and the `fixed` mode uses it.
    That mode is the shipped default, and the promise it makes is that the flag
    off changes nothing â€” so the request *pattern* has to be main's too, not only
    the queries. Two requests that used to go out one after the other would
    otherwise go out at once, which is a change to how the provider is used that
    no test of the queries would notice.
    """
    if not queries:
        return [], [], [], []
    if concurrent:
        outcomes = list(
            await asyncio.gather(
                *(_search(q, scope) for q, scope in queries)
            )
        )
    else:
        outcomes = [await _search(q, scope) for q, scope in queries]

    collected: list = []
    failures: list[tuple[str, str]] = []
    raw_dump: list[dict] = []
    per_query: list = []
    for (query, _scope), outcome in zip(queries, outcomes):
        per_query.append((query, outcome))
        if outcome.ok:
            collected.append(outcome.results)
        else:
            # One failure is not a total failure: another query may have worked,
            # and discarding it would understate what was checked.
            failures.append((query, outcome.error))
            log.warning("[verify] Search failed for '%s': %s", query, outcome.error)
        if outcome.raw_response:  # TEMPORARY DIAGNOSTIC
            raw_dump.append({"query": query, "raw": outcome.raw_response})
    return collected, failures, raw_dump, per_query


def _query_rows(texts: list) -> list:
    """Turn plain query strings into the `(text, scope)` pairs `_issue` takes.

    Round 1 and the `fixed` mode's model queries are unscoped; only a planned
    follow-up may carry a scope.
    """
    return [(t, None) for t in texts]


def _bind_to_retrieved(items: list, evidence: list, allowed: frozenset[str]) -> tuple[list, list]:
    """Drop citations the search provider never returned, and demote any `red`
    that nothing backs.

    `VERIFY_PROMPT.md` asks for a `source_url` "copied exactly from the results"
    and calls a constructed one a fabricated citation, but a prompt sentence is
    not a control: both the structured path and the labeled-text fallback copied
    whatever the model wrote, and `search.py:_canonical_url` â€” the normaliser a
    membership test needs â€” existed only for the dedupe.

    `allowed` is the set of URLs that were actually retrieved, in any spelling.
    It is canonicalised here rather than at the call site, because a caller that
    forgets and passes pre-canonicalised values would silently drop every
    legitimate citation â€” a fail-closed failure that looks like the model
    inventing sources.

    A `red` is demoted to `yellow` rather than dropped, because `yellow` already
    carries zero weight in `risk_calculator` and already means "we could not
    confirm this". An unbacked `red` is precisely that, so the existing semantics
    are the ones being enforced and the calculator needs no change. It also
    handles the common case for free: a failed or empty search produces an empty
    `allowed` set, and then nothing is refuted by anything.

    The demotion has one exception. `SOURCE_INDEPENDENT_ESCALATIONS` names the
    reds that are a claim the posting makes about itself, and the government
    branch is the only one: the posting said it was the office and supplied the
    domain, so there is no retrieved source it could be bound to. Demoting it was
    the corpus's flagship failure - the Fake CHED card said "That is outside the
    .gov.ph domain" and was worth nothing, because the employer lookup searched
    for the forgery's misspelling and never returned `ched.gov.ph`.

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
        if (
            not url
            and item.status == "contradicted"
            and item.escalation not in SOURCE_INDEPENDENT_ESCALATIONS
        ):
            item.status = "unknown"
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
    structured path, but the no-schema path has no enum â€” only this prompt's
    wording â€” so the check has to exist.
    """
    level = str(raw or "").strip().lower()
    if level in RISK_LEVELS:
        return level
    if level:
        log.warning("[verify] Ignoring unrecognised risk_level %r", level)
    return None


def _read_risk_score(raw) -> int | None:
    """The model's magnitude, validated to a 0-100 integer or nothing.

    `None` rather than a coerced default. The score drives the dial and the
    ordering in the match list, so a wrong value is a wrong dial - and the value
    that would be most tempting to substitute, `0`, is the one that says "nothing
    wrong here". Out of range, non-numeric, or absent all mean the model did not
    give one we can use.
    """
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        log.warning("[verify] Ignoring non-numeric risk_score %r", raw)
        return None
    if not 0 <= value <= 100:
        log.warning("[verify] Ignoring out-of-range risk_score %r", value)
        return None
    return value


# The statuses the verification model may write for an anomaly. This is the
# model's input vocabulary, not the wire's: `_read_anomaly_assessments` maps
# every one of these onto the four establishment states.
_ANOMALY_STATUSES = ("stale", "yellow", "red")


def _read_channel_item(payload: dict, allowed_urls: frozenset[str]):
    """Turn the model's Channel Match facts into the code's card.

    The model no longer returns a Channel Match status. This reads the facts and
    asks `channel_match` for the status, so the model cannot make a different
    channel a contradiction on its own. The official side is only usable with the
    result that showed it: an unbound `source_url` clears it, and the comparison
    degrades to yellow rather than asserting an employer's domain the search
    never returned.
    """
    raw = payload.get("channel_match")
    if raw is None:
        return None
    facts = read_channel_facts(raw)
    if not has_channel_content(facts):
        return None

    permitted = {_canonical_url(url) for url in allowed_urls if url}
    retrieved = bool(
        facts.source_url and _canonical_url(facts.source_url) in permitted
    )
    if facts.source_url and not retrieved:
        log.warning(
            "[verify] Dropped a Channel Match citation that was not in the retrieved results: %r",
            facts.source_url,
        )
    facts = with_official_only_if_retrieved(facts, retrieved)
    if not has_channel_content(facts):
        return None
    assessment = assess_channel_match(facts)
    return VerificationItem(
        label="Channel Match",
        status=assessment.status,
        explanation=assessment.explanation,
        source_title=facts.source_title,
        source_url=facts.source_url,
        escalation=assessment.escalation,
    )


def _read_anomaly_assessments(
    payload: dict,
    anomaly_count: int,
    allowed: frozenset[str],
) -> list[AnomalyAssessment]:
    """Read the verify model's verdicts on the numbered posting findings.

    The same source-binding rule as `_bind_to_retrieved` applies, for the same
    reason: a `stale` or `red` is a statement about a named employer and is shown
    only with the result it relies on. An unbacked one is demoted to `yellow`,
    which already means "we could not confirm this". A URL outside the retrieved
    set is dropped, and its title with it.

    Out-of-range and duplicate indices are dropped rather than renumbered. The
    client resolves `index` against the list it sent; inventing an entry for a
    finding that was not assessed would attach a verdict to the wrong claim.
    Missing assessments are left missing, and the client renders its own amber
    "not checked" sentence for them.
    """
    raw = payload.get("anomaly_assessments")
    if raw is None:
        return []
    if not isinstance(raw, list):
        log.warning(
            "[verify] Ignoring anomaly_assessments that was not a list: %r",
            type(raw).__name__,
        )
        return []

    permitted = {_canonical_url(u) for u in allowed if u}
    seen: set[int] = set()
    assessments: list[AnomalyAssessment] = []

    for entry in raw:
        if not isinstance(entry, dict):
            log.warning("[verify] Ignoring non-object anomaly assessment: %r", entry)
            continue

        raw_index = entry.get("index")
        if isinstance(raw_index, bool):
            log.warning("[verify] Ignoring anomaly assessment with a boolean index: %r", raw_index)
            continue
        # `int(1.5)` is 1 and `int("1.0")` raises; accepting the float would
        # attach a verdict to the neighbouring finding. The schema says integer,
        # but the labeled-text path has no schema, so this is the control.
        if isinstance(raw_index, str):
            if not raw_index.strip().isdigit():
                log.warning(
                    "[verify] Ignoring anomaly assessment with a non-integer index: %r",
                    raw_index,
                )
                continue
        elif not isinstance(raw_index, int):
            log.warning(
                "[verify] Ignoring anomaly assessment with a non-integer index: %r",
                raw_index,
            )
            continue
        index = int(raw_index)
        if not 1 <= index <= anomaly_count:
            log.warning(
                "[verify] Ignoring anomaly assessment for out-of-range index %s (there are %d findings)",
                index,
                anomaly_count,
            )
            continue
        if index in seen:
            log.warning("[verify] Ignoring duplicate anomaly assessment for index %d", index)
            continue

        status = str(entry.get("status") or "").strip().lower()
        if status not in _ANOMALY_STATUSES:
            log.warning(
                "[verify] Ignoring anomaly assessment with status %r (index %d)",
                status,
                index,
            )
            continue

        finding = str(entry.get("finding") or "").strip()
        if not finding:
            log.warning(
                "[verify] Ignoring an anomaly assessment with an empty finding (index %d)",
                index,
            )
            continue
        source_title = str(entry.get("source_title") or "").strip()
        source_url = str(entry.get("source_url") or "").strip()
        if source_url and _canonical_url(source_url) not in permitted:
            log.warning(
                "[verify] Dropped an anomaly citation that was not in the retrieved results: %r",
                source_url,
            )
            source_url = ""
            source_title = ""
        # One status vocabulary: the model's `red`/`yellow`/`stale` become the
        # states the panel reads for every other check. `red` is `contradicted`,
        # `yellow` is `unknown`, and `stale` keeps its name because retiring a
        # finding is its own fact. A finding with no source cannot contradict or
        # retire anything, so it lands on `unknown`.
        if status == "red":
            status = "contradicted" if source_url else "unknown"
        elif status == "yellow":
            status = "unknown"
        elif status == "stale" and not source_url:
            status = "unknown"
        if status == "unknown":
            source_title = ""

        seen.add(index)
        assessments.append(AnomalyAssessment(
            index=index,
            status=status,
            finding=finding,
            source_title=source_title,
            source_url=source_url,
        ))

    assessments.sort(key=lambda a: a.index)
    return assessments


def _read_verify_output(
    text: str,
    allowed_urls: frozenset[str] = frozenset(),
    anomaly_count: int = 0,
) -> tuple[list, str, str, bool, list, str | None, int | None, str, list[AnomalyAssessment]]:
    """Read the verification result, preferring JSON and falling back to text.

    JSON is the intended shape, but the provider may still answer with prose if
    it does not support structured outputs, so the labeled-text parser remains as
    a fallback rather than being deleted. Returns (items, report, recommendation,
    used_json, evidence, risk_level, risk_score, verdict_reason,
    anomaly_assessments).

    `anomaly_count` is the number of findings the request sent, which is what
    the assessments' 1-based indices refer to. It defaults to zero, so a caller
    with no request to hand drops every assessment rather than attaching one to
    a finding it cannot name â€” the fail-closed answer, matching `allowed_urls`.

    `allowed_urls` holds the canonical form of every URL the search provider
    actually returned. Anything outside it is dropped, and a `red` left without a
    citation is demoted to `yellow` â€” see `_bind_to_retrieved`. It defaults to
    empty, which drops every citation: that is the fail-closed answer for a
    caller holding no result set to check against, and nothing should reach the
    wire unbound by accident.

    Raises `VerificationParseError` when the fallback cannot read the response
    either. A request that succeeds and a response nobody can read is a failure,
    and returning an empty item list here would hide it â€” the panel would render
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
            # The model emits the old vocabulary; the new establishment states
            # are code-owned. A recorded response that already carries a new
            # state passes through unchanged.
            status_map = {
                "green": "confirmed",
                "yellow": "unknown",
                "red": "contradicted",
                "confirmed": "confirmed",
                "supported": "supported",
                "unknown": "unknown",
                "contradicted": "contradicted",
            }
            if not category or status not in status_map:
                log.warning("[verify] Ignoring malformed check entry: %r", check)
                continue
            items.append(VerificationItem(
                label=category,
                status=status_map[status],
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
        # Channel Match is code-owned. When the response carries the facts
        # object, any model-written Channel Match check is discarded: its status
        # is the thing this split exists to stop trusting. An older response with
        # no facts object keeps its check for compatibility, and the flow demotes
        # it to yellow before the verdict.
        if payload.get("channel_match") is not None:
            items = [item for item in items if item.label != "Channel Match"]
            channel_item = _read_channel_item(payload, allowed_urls)
            if channel_item is not None:
                items.append(channel_item)

        bound_items, bound_evidence = _bind_to_retrieved(items, evidence, allowed_urls)
        return (
            bound_items,
            str(payload.get("report") or ""),
            # Screened like the verdict reason: the recommendation is
            # model-written prose read by someone deciding about their own
            # money, and an accusation in it is the same exposure in a longer
            # slot. A rejected text sends the panel to its authored fallback.
            clean_recommendation(payload.get("recommendation")),
            True,
            bound_evidence,
            _read_risk_level(payload.get("risk_level")),
            _read_risk_score(payload.get("risk_score")),
            clean_verdict_reason(payload.get("verdict_reason")),
            _read_anomaly_assessments(payload, anomaly_count, allowed_urls),
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
    recommendation = clean_recommendation(
        runtime.get_parse_verify_section()(text, "RECOMMENDATION")
    )
    bound_items, _bound_evidence = _bind_to_retrieved(items, [], allowed_urls)
    # None on this path, and that is the honest answer rather than a default: the
    # labeled-text format has no place to carry a level, so nothing was assessed.
    # The panel renders null as Unverified and excludes it from resume matching.
    # Likewise empty for the reason: the labeled-text fallback has no
    # VERDICT_REASON section, and the block degrades to its authored headline
    # rather than the parser inventing a reason from the report prose.
    #
    # The labeled-text format has no anomaly assessment section either, so the
    # list is empty. The key still reaches the wire, which is how the client
    # tells "this backend ran the check and could not carry a verdict" from
    # "this reading predates the check" â€” both render amber, with different
    # notes, and neither invents a stale finding.
    return bound_items, report, recommendation, False, [], None, None, "", []


async def verification_event_stream(req: VerifyRequest) -> AsyncIterator[str]:
    limiter = runtime.get_ai_limiter()
    await limiter.acquire()
    try:
        yield runtime.get_sse()({"type": "progress", "percent": 5, "stage": "Preparing verification"})

        # The class the no-employer branch reports. With an employer it is
        # recomputed after the stale filter, because a finding a retrieved
        # source explained away must not be the finding that makes a free email
        # a pattern. Both computations read the same two inputs: the scan's
        # findings and the posting's own attributes. The verify stage does not
        # re-read the posting, so it must not compute the class from anything
        # else.
        request_class = classify_request(facts_from_scan(req.anomalies, req.attributes))

        company = (req.company_name or "").strip()
        if not runtime.get_company_name_is_valid()(company):
            log.warning("[verify] No valid company name provided ('%s') â€” stopping verification endpoint early.", company)
            yield runtime.get_sse()({"type": "progress", "percent": 100, "stage": "Cannot verify company name"})
            # No company name means there is nothing to search for, so there are
            # no verification results and therefore no risk score. The finding
            # is "we could not check", which is absent evidence, not a negative
            # one, so the status is yellow rather than red.
            explanation = "The job posting does not name an employer, so there was nothing to look up."
            items = [
                VerificationItem(
                    label="Company Existence",
                    status="unknown",
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
            # No verdict from this branch. The grid would read `unknown` and call
            # an ordinary request `clear`, and "clear" is the wrong word for a
            # posting where nobody was looked up at all. That distinction â€” a
            # missing employer is a missing input, not a clean record â€” is Task
            # 12's, and until it lands the panel says the lookup did not happen.
            breakdown = {"verdict": None, "level_source": None}
            yield runtime.get_sse()({"type": "result", "data": {
                "items": [item.model_dump() for item in items],
                "report": report,
                "recommendation": recommendation,
                "verdict": None,
                "verdictBreakdown": breakdown,
                "verdictReason": "",
                "verdictText": "",
                "request_class": request_class,
                "search_ok": False,
                "search_error": "No employer name was given, so nothing was searched.",
                # Always present, never conditional. A client reading
                # `scheme_queries.length` would otherwise throw on exactly the
                # response that most obviously searched nothing â€” and there is no
                # query to report, because a stated detail with no employer
                # attached is a place, not an impersonation.
                "scheme_queries": [],
                # No employer means no search, so no finding could have been
                # checked. The key is present and empty, which the client reads
                # as "the check did not produce a verdict" rather than as a
                # saved reading from before the check existed.
                "anomaly_assessments": [],
                # The same reason, for the same reason. `rounds` is what the
                # other result event carries, and a client reading it must not
                # have to handle its absence on exactly the response that most
                # obviously searched nothing. Nothing was looked up, so the
                # record is empty rather than missing.
                "rounds": [],
                "no_company_name": True,
            }})
            return

        yield runtime.get_sse()({"type": "progress", "percent": 10, "stage": "Searching company info"})
        # One anchor query, then the model's own proposals. One flat result set,
        # one model call. Neither family carries a category suffix: the model
        # sorts the merged results into the categories itself, so nothing here
        # decides what a result is.
        #
        # The anchor query finds what is published about the employer. It used
        # to be two queries, because one could not serve every category â€”
        # `"<company> Philippines"` ranks the employer's own site first, and
        # those pages do not state registration numbers. `build_queries` now
        # returns one: `"<company> company or employer"`, which surfaces the
        # employer's own pages, a PESO listing and a job board post in one
        # result set. The two targeted rankings it replaced were starving each
        # other, and `Official Registration` and `Reputation` now depend on the
        # one query surfacing the right page rather than asking for it by name.
        #
        # It also finds nothing when a scam borrows a real company's name,
        # because the real company's reputation is clean, which is exactly why
        # the impersonation is invisible to it. The model's proposed queries
        # name a detail the posting itself stated, so they reach the pages that
        # pair the claim with the employer making it.
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
        #
        # The conclusion-word filter runs here, before the cap, in every mode:
        # a prompt sentence is not a control, and a refused query must not
        # spend a slot a safe query could have used. The planner applies the
        # same filter to its own follow-ups; this is the fixed mode's copy of
        # the same door.
        model_queries = [
            q for q in (str(raw).strip() for raw in (getattr(req, "search_queries", None) or []))
            if q and search_query_is_safe(q)
        ][:MAX_SEARCH_QUERIES]
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
        # Which query retrieved which URL, so each result can say so. Recorded in
        # both modes; only the adaptive one reads it back, to label results.
        query_of: dict = {}
        # What each issued query was for, and what it returned. Replaces
        # `model_queries` as the record of what was looked up: the adaptive
        # planner's questions have purposes, and a bare list of strings cannot
        # carry them.
        rounds: list[dict] = []
        entity_name = ""
        labels: dict | None = None
        adaptive = settings.resolve_search_mode() == "adaptive"

        def _record(round_numbers: list[int], per_query: list, purpose_for) -> None:
            """Note what each query of a round was for and what it returned.

            A round is recorded whether it succeeded or failed â€” a round that
            did not run is a fact the panel needs as much as one that did.

            `round_numbers` is parallel to `per_query` rather than a single
            number, because the `fixed` mode's model queries are numbered
            individually â€” 2, 3 â€” exactly as the SSE events number them. One
            number for the lot would make the record disagree with the event
            stream the reader is watching.
            """
            for round_number, (query, outcome) in zip(round_numbers, per_query):
                for r in (outcome.results if outcome.ok else ()):
                    url = getattr(r, "url", "") or ""
                    if url and url not in query_of:
                        query_of[url] = query
                rounds.append({
                    "round": round_number,
                    "query": query,
                    "purpose": purpose_for(query),
                    "ok": outcome.ok,
                    "result_count": len(outcome.results) if outcome.ok else 0,
                })

        # â”€â”€ Round 1: the employer-name query. One credit, identical in both modes.
        for query in company_queries:
            yield runtime.get_sse()({"type": "search", "query": query, "round": 1})
        first_collected, first_failures, first_raw, first_per_query = await _issue(
            _query_rows(company_queries)
        )
        collected.extend(first_collected)
        failures.extend(first_failures)
        raw_dump.extend(first_raw)
        _record([1] * len(first_per_query), first_per_query,
                lambda q: "what is published about the employer")

        if adaptive:
            # â”€â”€ Resolve, then Round 2.
            #
            # The planner reads only the scan's own fields and Round 1's
            # results. It is not a second opinion on the employer: it decides
            # which questions are worth a credit, and the verify prompt remains
            # the only thing that makes a claim about anyone.
            signals = classify_signals(company, getattr(req, "attributes", None) or {})
            entity = resolve_entity(signals, [r for batch in first_collected for r in batch])
            planned = plan_followups(
                signals,
                entity,
                round1_ok=not first_failures,
                model_queries=model_queries,
            )
            purposes = {q.text: q.purpose for q in planned}
            for query in planned:
                log.info("[verify] follow-up for '%s': %s", query.text, query.purpose)

            if planned:
                for query in planned:
                    yield runtime.get_sse()({"type": "search", "query": query.text, "round": 2})
                rows = [(q.text, list(q.include_domains) or None) for q in planned]
                follow_collected, follow_failures, follow_raw, follow_per_query = await _issue(rows)
                collected.extend(follow_collected)
                failures.extend(follow_failures)
                raw_dump.extend(follow_raw)
                _record([2] * len(follow_per_query), follow_per_query,
                        lambda q: purposes.get(q, ""))

            # Every result is labelled, including the ones about a different
            # body. A page that never mentions the organisation being verified
            # is not evidence of absence about it â€” it is evidence about a
            # different organisation, and the model can only tell those apart if
            # it is told which is which. Nothing is dropped: dropping is how the
            # entity heuristic goes wrong in the first place.
            everything = [r for batch in collected for r in batch]
            entity_name = entity.name
            labels = {
                url: (label.query, label.describes_entity)
                for url, label in label_results(everything, entity, query_of).items()
            }
        else:
            # The `fixed` path: whatever the scan model proposed, unscoped, with
            # no round between them. Up to two queries of one kind rather than
            # a second round, because nothing here was chosen from a result â€”
            # which is the whole difference between the modes. The ceiling is
            # the anchor plus these, so three credits at `basic` depth.
            for i, query in enumerate(model_queries, len(company_queries) + 1):
                yield runtime.get_sse()({"type": "search", "query": query, "round": i})
            rest_collected, rest_failures, rest_raw, rest_per_query = await _issue(
                _query_rows(model_queries), concurrent=False
            )
            collected.extend(rest_collected)
            failures.extend(rest_failures)
            raw_dump.extend(rest_raw)
            _record(
                list(range(
                    len(company_queries) + 1,
                    len(company_queries) + 1 + len(rest_per_query),
                )),
                rest_per_query,
                lambda q: "a question the scan model proposed",
            )

        # Every query issued, counted from what was actually issued rather than
        # from a list that may not have run.
        queries_issued = len(rounds)
        queries = [r["query"] for r in rounds]

        ok = bool(collected) or not failures
        partial = bool(failures) and bool(collected)
        first_error = failures[0][1] if failures else ""

        if not collected and not failures:
            log.info("[verify] Searches for '%s' returned no results", company)
        elif partial:
            log.warning(
                "[verify] %d of %d searches failed for '%s'; coverage is partial",
                len(failures), queries_issued, company,
            )

        # Dedupe on canonical URL: the employer's own site appears in both
        # result sets, and every result is prompt text competing for a budget
        # shared with the model's reasoning. Capped so the merged list cannot
        # outgrow what one query produced by much.
        merged = runtime.get_merge_results()(
            *collected, cap=settings.tavily_max_results * 2
        )
        search_context = runtime.get_format_results()(
            merged, company, ok, first_error, entity_name, labels
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
        # otherwise never consulted again until `search_count` â€” that gap is
        # what left the citation unbound.
        retrieved_urls = frozenset(
            r.url for r in merged if getattr(r, "url", "")
        )
        (
            items, report, recommendation, used_json, evidence, model_risk_level,
            model_risk_score, verdict_reason, anomaly_assessments,
        ) = _read_verify_output(
            final_text,
            allowed_urls=retrieved_urls,
            anomaly_count=len(req.anomalies),
        )

        # A partial parse used to be silent: the panel showed one card while the
        # raw response clearly listed three, with nothing in the log to connect
        # the two. Name what is missing so the next occurrence is diagnosable.
        #
        # The expectation is the *gated* set â€” what the posting's own claims made
        # testable â€” not all six categories. Comparing against six would warn on
        # every scan that states no location, and a warning that fires on almost
        # every request is a warning nobody reads.
        expected = expected_categories(req)
        # A stale finding is one a retrieved employer-specific source accounts
        # for. It must not escalate a free email to a red combination: the pattern
        # is the finding plus the channel, and the finding no longer stands.
        stale_indices = {
            assessment.index
            for assessment in anomaly_assessments
            if assessment.status == "stale"
        }
        active_anomalies = [
            anomaly
            for index, anomaly in enumerate(req.anomalies, 1)
            if index not in stale_indices
        ]
        # The class the panel shows and the class the channel rule reads must be
        # the same one, and both must be the one that survives the stale filter:
        # a finding a retrieved source explained away must not be the finding
        # that makes a free email a pattern. Recomputed with the same helper the
        # scan used, from the findings that still stand.
        request_class = classify_request(
            facts_from_scan(active_anomalies, req.attributes)
        )
        # Channel Match is the one category the model does not assign. The
        # facts object supplies it, and this step is where a prohibited request
        # can turn a free email into a pattern. It also removes the category
        # when the posting made no channel claim, and refuses an old response's
        # model-assigned status.
        items = apply_channel_rules(items, request_class, expected)
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

        failsafe = False
        if not items:
            # Only the readable-but-empty case reaches here: a response nobody
            # could read raised in _read_verify_output, so this branch never
            # reports an unreadable response as a result. The card is a fact
            # about our own output, not a finding about the employer.
            log.warning("[verify] Failsafe triggered: response was readable but carried no usable checks. Raw: %s", final_text[:300])
            items = [
                VerificationItem(
                    label="Company Existence",
                    status="unknown",
                    explanation=f"No structured findings could be read from the search results for '{company}'.",
                )
            ]
            if not report:
                report = f"Structured findings could not be parsed from the search results for '{company}', so no risk score was calculated."
            if not recommendation:
                recommendation = "Confirm the employer independently before submitting personal details."
            # The model produced no usable answer, so it never reached a level or
            # a score. Defaulting to `low`/`0` here would put a reassuring colour
            # and an empty dial on the one case where we know least, which is the
            # inverse of what happened before this moved: the ladder scored an
            # empty result as zero.
            failsafe = True

        # The verdict is code-owned and it has no number. The model's own
        # `risk_level` and `risk_score` were already not inputs; they are still
        # read by `_read_verify_output` so an old provider response is
        # diagnosable in the log.
        if not ok or failsafe:
            # Two different reasons not to decide, and both mean "we did not
            # assess": the search did not complete, or the response was readable
            # but carried nothing usable. Neither is `clear`, and neither is
            # `stop`.
            risk_level = None
            risk_score = None
            breakdown: dict = {
                "verdict": None,
                "level_source": None,
            }
        else:
            risk_level, breakdown = code_verdict(
                active_anomalies,
                items,
                anomaly_assessments,
                request_class=request_class,
            )
            # There is no number any more. The key stays on the wire until the
            # next task removes it, and `None` says "not scored" rather than 0.
            risk_score = None

        if model_risk_level is not None or model_risk_score is not None:
            log.info(
                "[verify] Ignored model risk fields for the verdict: level=%s score=%s; code verdict=%s rule=%s",
                model_risk_level,
                model_risk_score,
                risk_level,
                breakdown.get("rule"),
            )

        log.info("[verify] Parsed items=%d, report_len=%d, rec_len=%d, rule=%s, verdict=%s", len(items), len(report), len(recommendation), breakdown.get("rule"), risk_level)
        if items:
            log.info("[verify] Items: %s", items)
        if report:
            log.info("[verify] Report: %s", report[:200])
        if recommendation:
            log.info("[verify] Recommendation: %s", recommendation[:200])
        if verdict_reason:
            log.info("[verify] Verdict reason: %s", verdict_reason)
        assessed = {assessment.index for assessment in anomaly_assessments}
        missing = [
            index for index in range(1, len(req.anomalies) + 1)
            if index not in assessed
        ]
        if missing:
            log.warning(
                "[verify] Parsed %d of %d anomaly assessments; missing indices: %s",
                len(anomaly_assessments),
                len(req.anomalies),
                missing,
            )
        else:
            log.info(
                "[verify] Anomaly assessments: %d of %d findings assessed",
                len(anomaly_assessments),
                len(req.anomalies),
            )

        # The statement is authored from the verdict and the structured facts.
        # The backend owns the copy; the model never writes it.
        from .establishment import establishment_from_record
        from .verdict_copy import StatementFacts, statement as render_statement

        establishment = establishment_from_record(items)

        fee_recipient = ""
        fee_reason = ""
        amount = ""
        documents = ""
        if req.attributes:
            fee_recipient = req.attributes.get("FEE_RECIPIENT", "") or ""
            fee_reason = req.attributes.get("FEE_REASON", "") or ""
            amount = req.attributes.get("PAY", "") or ""
            # Documents come from the anomalies' quotes
            for anomaly in req.anomalies or []:
                code = getattr(anomaly, "code", "") or ""
                if code in ("APPLICATION_DOCUMENTS", "DOCUMENTS_VIA_THIRD_PARTY", "ACCOUNT_CREDENTIALS"):
                    quote = getattr(anomaly, "quote", "") or ""
                    if quote and not documents:
                        documents = quote

        facts = StatementFacts(
            amount=amount,
            fee_recipient=fee_recipient,
            fee_reason=fee_reason,
            documents=documents,
        )
        verdict_text = render_statement(
            risk_level,  # risk_level is the verdict string
            request_class=request_class,
            establishment=establishment,
            facts=facts,
        )

        yield runtime.get_sse()({"type": "result", "data": {
            "items": [item.model_dump() for item in items],
            "evidence": evidence,
            "report": report,
            "recommendation": recommendation,
            "verdict": risk_level,
            "verdictBreakdown": breakdown,
            "verdictReason": verdict_reason,
            "verdictText": verdict_text,
            "request_class": request_class,
            # Always present, possibly empty. See the no-company event above for
            # why absence and an empty list are different states to the client.
            "anomaly_assessments": [
                assessment.model_dump() for assessment in anomaly_assessments
            ],
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
            # What the **scan model proposed**, which is not the same as what was
            # looked up. In `fixed` mode every proposal is issued, so the two
            # coincide; in `adaptive` mode the planner chooses and a proposal
            # it had no use for is never issued. `rounds` is the record of what
            # was actually looked up, and it is the accurate one.
            #
            # Reported separately from `queries_issued` because the two answer
            # different questions: one asks about the employer, the other about
            # whether the posting's claims are the employer's own.
            #
            # Renamed from `scheme_queries`: nothing builds these from
            # attributes any more, and the panel reads this out as *what the
            # scan model asked for*. A field name describing a mechanism that no
            # longer exists would be a small lie in the one place the user can
            # audit the lookup.
            "model_queries": model_queries,
            # What each query was for, and what it returned. `queries_issued`
            # says how many lookups happened; this says which questions they
            # answered, which is the only way to tell a deliberate silence from
            # a question nobody thought to ask. In the adaptive mode the
            # follow-ups are chosen in code, so a reader auditing the panel sees
            # the reason rather than a bare string.
            "rounds": rounds,
            "queries_failed": len(failures),
            "debug_search_raw": raw_dump,  # TEMPORARY DIAGNOSTIC â€” remove with SearchOutcome.raw_response
            "no_company_name": False,
        }})
    except Exception as e:  # noqa: BLE001
        log.error("[verify] Error: %s: %s", type(e).__name__, e)
        yield runtime.get_sse()({"type": "error", "error": "Verification failed. Please try again."})
    finally:
        limiter.release()

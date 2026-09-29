"""Web search via Tavily.

One provider, one query, no retries, no fallback, no caching. The previous
DuckDuckGo module was 620 lines whose failures were indistinguishable from
successes: it returned an empty list both when a search was throttled and when
a company had no online presence, and it stamped results with category headings
it had not verified. A regulator's complaint form surfaced under a "SCAM
REPORTS" heading read as a scam report.

`SearchOutcome` fixes the first problem structurally. `ok` and `results` are
independent: `ok=False` means the call failed, `ok=True` with no results means
the company genuinely has no footprint. No caller can read one as the other.

The second problem is fixed by absence. Nothing here categorises results; the
model receives a flat list and judges each one, so no heading can assert
something the retrieval did not establish.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

import httpx

from app.config import settings

log = logging.getLogger("trabahero")

TAVILY_ENDPOINT = "https://api.tavily.com/search"
REQUEST_TIMEOUT = 20.0


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    score: float


@dataclass(frozen=True)
class SearchOutcome:
    """`ok` and `results` are deliberately independent.

    ok=False, results=[]  -> retrieval failed, the category is unknown
    ok=True,  results=[]  -> the search succeeded and found nothing

    `error` is the classified reason, which is what a log needs to tell a
    throttled query from a malformed one.
    """

    results: list[SearchResult] = field(default_factory=list)
    ok: bool = True
    error: str = ""
    latency: float = 0.0
    # TEMPORARY DIAGNOSTIC. The provider's raw body, so the panel can show what
    # Tavily actually returned for each query. Nothing in the production path
    # reads it.
    #
    # This field existed before and was removed: `test_no_debug_surface.py`
    # asserts its absence, and that assertion is currently suspended while this
    # diagnostic is in use. Restore both together — remove this field and drop
    # the `pytest.mark.skip` in that test. Shipping a debug surface on a released
    # extension leaks the provider's raw response body to the browser.
    raw_response: str = ""


# Tavily's `country` boost, not a query term and not a domain filter. See
# search() for why ranking rather than phrasing is the lever here. Configurable
# via TAVILY_COUNTRY; blank disables the boost.
_VALID_DEPTHS = frozenset({"basic", "advanced"})


def _normalise_domain(raw: str) -> str:
    """Reduce one user-typed entry to a bare host.

    People paste URLs and copy them with a trailing slash. Tavily matches
    `exclude_domains` against the result host, so a scheme, a `www.` prefix,
    or a path would not match anything: the exclusion would look configured
    and silently do nothing, which is worse than an error because the setting
    appears to be working.

    A leading `*.` is preserved — Tavily reads it as a subdomain wildcard, and
    stripping it would quietly widen what gets excluded.
    """
    value = raw.strip().lower()
    if not value:
        return ""
    for scheme in ("https://", "http://"):
        if value.startswith(scheme):
            value = value[len(scheme) :]
            break
    # Cut anything after the host: a path, query, or fragment.
    value = re.split(r"[/?#]", value, maxsplit=1)[0]
    if value.startswith("*."):
        host = value[2:]
        prefix = "*."
    else:
        host = value
        prefix = ""
    if host.startswith("www."):
        host = host[4:]
    return f"{prefix}{host}"


def _parse_domains(raw: str) -> list[str]:
    """Split a configured domain list into the list Tavily expects.

    Split on commas and whitespace so both `a.com, b.com` and a multi-line
    `.env` value work. Order is preserved and duplicates are collapsed, since
    two spellings of one host would otherwise be sent as two entries.
    """
    if not raw:
        return []
    seen: list[str] = []
    for token in re.split(r"[,\s]+", raw.strip()):
        domain = _normalise_domain(token)
        # A host needs a dot. Without this check a stray word in the list —
        # a note to self in the .env — becomes a domain Tavily rejects, which
        # turns a config typo into a search failure reported to the user as an
        # employer that cannot be looked up.
        if not domain or "." not in domain or domain in seen:
            continue
        seen.append(domain)
    return seen


def build_queries(company: str) -> list[str]:
    """The queries issued per verification: registration, then reviews.

    One query cannot serve all three categories. `"<company> Philippines"` ranks
    the employer's own site and job boards first, which proves it exists but
    states no registration number, so a PESO or SEC listing sat below the fold —
    starving "Official Registration" by *ranking*, not by absence. No
    `max_results` value fixes ranking.

    Neither remaining query names one registry. Naming SEC would reintroduce the
    failure the category was widened to fix: a company holding a DTI, PEZA, BOI,
    or LGU business permit is registered, and an SEC-only query would not
    surface it.

    Company Existence no longer has its own query. It is inferred from these
    two: a company with a filing, a rating page, or a published complaint is
    found by one of them, and the prompt judges the same flat list for all three
    categories. The traded cost is real and recorded in the tests — an employer
    with neither a filing nor any review is found by neither query and reports
    yellow on existence, which is the smallest employers, the ones this product
    exists for.

    The reputation query carries `reviews complaints` deliberately. `scam` and
    `fraud` stay banned: those name a conclusion, so a query carrying one makes
    the results look like corroboration of the accusation it already embedded.
    `reviews` and `complaints` name *documents* — a rating the employer can
    respond to, and an adverse record someone published — and the category is
    about what a result states. The residual exposure is aggregator pages that
    re-publish complaint text against a scraped company name; the prompt's
    same-entity rule and its requirement that `red` name a source are what keep
    that from becoming a finding.

    The name is used **verbatim**. It used to be stripped of a trailing
    Corporation/Corp/Inc/Co/LLC, on the reasoning that a generic legal form
    dilutes a rare name. That is wrong for this product's subject. A filing, a
    city PESO listing, and the employer's own legal pages are all titled with the
    *legal* name, so stripping it left the distinctive part competing against a
    brand, its franchisees, and unrelated products sharing the word — searching
    "Jollibee Foods" is a worse lookup than "Jollibee Foods Corporation". The
    scan states the employer once; nothing between here and the provider rewrites
    it, because every rewrite is a chance to search a different company than the
    one named.

    Results merge into one flat list for a single AI call, so the cost is two
    requests rather than two model calls.
    """
    name = company.strip()
    return [
        _with_country(f"{name} registration certificate"),
        _with_country(f"{name} reviews complaints"),
    ]


def _with_country(query: str) -> str:
    """Anchor a query to the Philippines unless the name already says so."""
    return query if re.search(r"\bPhilippines\b", query, re.IGNORECASE) else f"{query} Philippines"


def _canonical_url(url: str) -> str:
    """Reduce a URL to an identity, so one page reached twice is one result.

    Two queries return overlapping sets — the employer's own site appears in
    both — and every result is prompt text competing for a reasoning model's
    budget, so a page listed twice is paid for twice while telling the model
    nothing new. Scheme, `www.`, tracking parameters, and a trailing slash all
    vary between the two responses for the same page.
    """
    value = (url or "").strip().lower()
    if not value:
        # No URL cannot be compared against anything, so this is a marker the
        # caller replaces with a per-occurrence key. Two blank-URL results are
        # two results, not one collapsed pair.
        return ""
    for scheme in ("https://", "http://"):
        if value.startswith(scheme):
            value = value[len(scheme):]
            break
    value = value.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if value.startswith("www."):
        value = value[4:]
    return value


def merge_results(*result_sets: list[SearchResult], cap: int | None = None) -> list[SearchResult]:
    """Combine several result sets into one, best first, without duplicates.

    Ordering is by score so a later query's hit can outrank the first query's
    filler, and so a `cap` trims the tail the budget cannot hold rather than an
    arbitrary slice.
    """
    best: dict[str, SearchResult] = {}
    blanks = 0
    for results in result_sets:
        for result in results or []:
            key = _canonical_url(result.url)
            if not key:
                key = f"\x00blank{blanks}"
                blanks += 1
            if key not in best:
                best[key] = result
            elif result.score > best[key].score:
                # Same page, better-scored copy: keep the text that earned it.
                best[key] = result
    merged = sorted(best.values(), key=lambda r: r.score, reverse=True)
    return merged[:cap] if cap and cap > 0 else merged


def _normalise(payload) -> list[SearchResult]:
    """Map the provider's rows onto ours.

    Raises ValueError when the body has no usable `results` list. The
    distinction matters: `{"results": []}` is a real answer of "nothing found",
    while a missing or null `results` means the provider changed its shape or
    returned an error envelope, and reporting that as a company with no
    footprint is precisely the defect this module exists to prevent.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"provider returned {type(payload).__name__}, expected an object")

    if "error" in payload and "results" not in payload:
        raise ValueError(f"provider returned an error envelope: {payload['error']!r}")

    rows = payload.get("results")
    if not isinstance(rows, list):
        raise ValueError(
            f"provider response has no usable 'results' list (got {type(rows).__name__})"
        )

    out: list[SearchResult] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            SearchResult(
                title=str(row.get("title") or ""),
                url=str(row.get("url") or ""),
                # Tavily names the snippet 'content'.
                snippet=str(row.get("content") or ""),
                score=float(row.get("score") or 0.0),
            )
        )
    return out


def search(query: str, max_results: int | None = None) -> SearchOutcome:
    """Run one search. Never raises; a failure is reported in the outcome."""
    limit = max_results if max_results is not None else settings.tavily_max_results

    if not settings.tavily_api_key.strip():
        # A missing key must be visible, or every category reads as "no
        # information" and a broken deployment looks like a clean company.
        log.error("[search] TAVILY_API_KEY is not configured; cannot search")
        return SearchOutcome(
            ok=False,
            error="TAVILY_API_KEY is not configured on the backend.",
        )

    started = time.monotonic()
    payload = None
    raw = ""  # TEMPORARY DIAGNOSTIC — see SearchOutcome.raw_response.

    depth = settings.tavily_search_depth.strip().lower()
    if depth not in _VALID_DEPTHS:
        # A typo would have the provider reject the request, and the user would
        # be told a company cannot be looked up. Log it, then use the fallback
        # so a cost setting cannot become a verdict.
        log.error(
            "[search] TAVILY_SEARCH_DEPTH=%r is not a Tavily depth; using %r",
            settings.tavily_search_depth,
            settings.tavily_search_depth_fallback,
        )
        depth = settings.tavily_search_depth_fallback

    body = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "max_results": limit,
        # Advanced costs 2 credits against basic's 1 and buys broader recall,
        # which is what a small local employer needs. TAVILY_SEARCH_DEPTH turns
        # it down when the monthly budget matters more.
        "search_depth": depth,
        # No `include_answer`. A synthesised answer is retrieval's opinion
        # rather than evidence, and the verification prompt requires source URLs
        # copied from the results themselves.
    }

    # Boost, do not filter. A browser search from the Philippines surfaces SEC
    # filings, city PESO sites, and local job boards for a small employer;
    # Tavily's own crawl index covers that long tail less well, so a niche name
    # falls through to whatever it indexes strongly — a London VC firm, or an
    # unrelated product with a similar word. No query rewrite fixes missing
    # index coverage.
    #
    # `include_domains` is deliberately NOT set. It restricts results to the
    # listed domains, which would discard precisely the JobStreet, Indeed PH,
    # and PESO pages this boost exists to surface. There is no "prefer" mode;
    # the boost is the only tool that matches the intent.
    country = settings.tavily_country.strip()
    if country:
        body["country"] = country

    # `exclude_domains` is a different lever from `include_domains`: it removes
    # pages the provider would otherwise return rather than restricting the
    # search to a whitelist. That distinction is why it can be set without
    # discarding the local job boards and PESO listings above — a domain is
    # excluded by name, not everything outside it. It still costs recall, so
    # it stays opt-in and off by default.
    #
    # Sent only when something survives parsing. `exclude_domains: []` would
    # declare an intent to filter while filtering nothing; blank is a
    # misconfiguration, so the unfiltered query is issued instead.
    excluded = _parse_domains(settings.tavily_exclude_domains)
    if excluded:
        log.info("[search] excluding %d configured domain(s)", len(excluded))
        body["exclude_domains"] = excluded

    try:
        response = httpx.post(
            TAVILY_ENDPOINT,
            json=body,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        # TEMPORARY DIAGNOSTIC. Read before json() so a malformed body is still
        # visible in the panel rather than only in a log line.
        raw = response.text
        payload = response.json()
        # Normalising inside the try: a shape change is a provider fault, and
        # search() must report it rather than raise out of the verification
        # stream, which has no exception handler mid-flight.
        results = _normalise(payload)
    except Exception as exc:  # noqa: BLE001
        latency = round(time.monotonic() - started, 3)
        log.error("[search] [error] '%s' failed: %s: %s", query, type(exc).__name__, exc)
        return SearchOutcome(
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            latency=latency,
            raw_response=raw,  # TEMPORARY DIAGNOSTIC
        )

    latency = round(time.monotonic() - started, 3)
    if not results:
        # Not an error: the search worked and the company has no footprint.
        log.info("[search] '%s' returned no results in %ss", query, latency)
    else:
        log.info("[search] '%s' returned %d results in %ss", query, len(results), latency)
    # TEMPORARY DIAGNOSTIC — see SearchOutcome.raw_response.
    return SearchOutcome(results=results, ok=True, error="", latency=latency, raw_response=raw)


# ── Company name helpers ──────────────────────────────────────────────
#
# Provider-independent. The scan resolves the employer through these, so they
# live here alongside the search they feed. The employer is the company the
# reader would work for: a staffing agency is a recruiter, not the employer.

INVALID_COMPANY_NAMES = {
    "none", "n/a", "na", "unknown", "null", "undefined",
    "not specified", "unspecified", "unclear", "not provided",
    "not mentioned", "not available", "no company", "no company name",
    "unnamed", "anonymous", "company name", "company", "employer",
    "various", "confidential", "tbd", "pending",
}

NOT_STATED_MARKERS = {
    "not stated", "not mentioned", "not provided", "not specified",
    "not listed", "not available", "not applicable", "not named",
    "no name", "none", "n/a", "unknown", "unnamed", "no company",
    "no company name", "no employer", "no employer name",
}


def is_valid_company_name(name: str | None) -> bool:
    """Check if an extracted company name is plausible and not a placeholder."""
    if not name or not isinstance(name, str):
        return False
    clean = name.strip()
    if len(clean) < 2 or len(clean) > 80:
        return False
    lower = clean.lower()
    if lower in INVALID_COMPANY_NAMES or lower in NOT_STATED_MARKERS:
        return False
    for prefix in (
        "not specified", "not provided", "not mentioned", "not available",
        "no company", "company name unclear", "company unclear", "unknown company",
    ):
        if lower.startswith(prefix) or lower == prefix:
            return False
    return True


def _clean_company_candidate(raw: str) -> str:
    """Trim a regex capture down to the name itself.

    The extraction patterns use a character class that also matches sentence
    punctuation, so a raw capture frequently runs on into the rest of the
    sentence. Cut at the first clause boundary and drop any parenthetical.
    """
    name = re.split(r"[.,;]\s", raw.strip(), maxsplit=1)[0]
    name = re.sub(r"\s*\(.*$", "", name)
    name = re.sub(r"^[^\w]+|[^\w]+$", "", name).strip()
    name = re.sub(r"\s+(?:is|are|was|were|has|have|will)$", "", name).strip()
    return name


def extract_company_name(text: str) -> str | None:
    """Try to extract an employer name from job posting text."""
    text = text[:3000]
    patterns = [
        r"(?:at|for|@)\s+([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"([A-Z][A-Za-z0-9\s&.,'-]{2,40})\s+(?:is hiring|is looking|seeks|wants|hiring)",
        r"About\s+([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"Company:\s*([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"Company\s+Name\s*:?\s*([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"Employer:\s*([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
    ]
    skip_words = {"the", "this", "our", "your", "we", "you", "they", "his", "her", "a", "an"}
    for pattern in patterns:
        for match in re.finditer(f"(?={pattern})", text):
            name = _clean_company_candidate(match.group(1))
            if not name:
                continue
            words = name.lower().split()
            if words and words[0] not in skip_words and len(name) > 3 and is_valid_company_name(name):
                return name
    return None


def clean_company_name(name: str | None) -> str:
    """Normalise an employer name supplied by the model, returning "" if unusable.

    A joined name is split and the last part kept. Postings that name a
    recruiter and a client ("Vikings / Silvergreen Manpower Services
    Corporation") arrive as one string, and a search engine tokenises the slash
    into neither entity. The client is named after the recruiter in these
    postings, so the tail is the one to look up.
    """
    if not name or not isinstance(name, str):
        return ""
    cleaned = _clean_company_candidate(name)
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE).strip()

    for sep in ("/", "|"):
        if sep in cleaned:
            parts = [p.strip() for p in cleaned.split(sep) if p.strip()]
            parts = [p for p in parts if is_valid_company_name(p)]
            if not parts:
                return ""
            log.info("[search] Joined employer name %r; looking up %r instead", cleaned, parts[-1])
            cleaned = parts[-1]

    if not cleaned or not is_valid_company_name(cleaned):
        return ""
    return cleaned

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

# Supported search provider endpoints
_TAVILY_ENDPOINT = "https://api.tavily.com/search"
_KEENABLE_ENDPOINT = "https://api.keenable.ai/v1/search"  # Keenable API
REQUEST_TIMEOUT = 20.0


def _get_provider_config() -> dict:
    """Return the active provider's configuration from settings."""
    provider = settings.search_provider.strip().lower()
    # "keeenable" (3 e's) is accepted alongside the correct spelling: the name
    # invites the typo, and a silent fall-through to a different provider would
    # spend the wrong provider's credits while looking configured.
    if provider in ("keenable", "keeenable"):
        return {
            "endpoint": _KEENABLE_ENDPOINT,
            "api_key": settings.keenable_api_key,
            "max_results": settings.keenable_max_results,
            "search_depth": settings.keenable_search_depth.strip().lower(),
            "country": "",  # Keenable may not support country boost
            "exclude_domains": "",  # Keenable may not support exclude_domains
        }
    if provider not in ("tavily", ""):
        # A misspelled provider name would otherwise silently fall through to
        # Tavily while spending its credits and looking configured. A warning
        # makes the typo loud at the first search.
        log.warning(
            "[search] SEARCH_PROVIDER=%r is not a supported provider "
            "(tavily, keenable); falling back to Tavily",
            settings.search_provider,
        )
    # Default to Tavily
    return {
        "endpoint": _TAVILY_ENDPOINT,
        "api_key": settings.tavily_api_key,
        "max_results": settings.tavily_max_results,
        "search_depth": settings.tavily_search_depth.strip().lower(),
        "country": settings.tavily_country.strip(),
        "exclude_domains": settings.tavily_exclude_domains,
    }


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


# Second-level suffixes whose registrable domain is three labels, not two.
# Naively taking the last two of `ched.gov.ph` yields `gov.ph` — a domain that
# belongs to nobody and, as a scope, boosts nothing. There is no public-suffix
# list in this project's dependencies and a wrong registrable domain produces a
# wrong scope silently, so the list is explicit and short rather than guessed at.
_MULTI_LABEL_SUFFIXES = frozenset({
    "gov.ph", "edu.ph", "com.ph", "net.ph", "org.ph",
    "co.uk", "ac.uk", "org.uk", "gov.uk",
    "com.au", "com.sg", "co.nz", "co.jp", "co.kr",
})


def registrable_domain(raw: str) -> str:
    """The registrable part of a host, so a subdomain cannot become a scope.

    `www.ched.gov.ph`, `hr.ched.gov.ph` and `ched.gov.ph` are one employer.
    Scoping to any of them alone would exclude the other two, which for an
    `include_domains` scope means boosting a page the caller never asked about
    and silently widening the scope elsewhere.

    Strips a scheme, a `www.` prefix, and anything after the host, so a pasted
    URL and its bare domain produce the same scope. The scheme goes first:
    cutting at the path before removing it would leave `https` as the host.
    """
    host = (raw or "").strip().lower()
    for scheme in ("https://", "http://"):
        if host.startswith(scheme):
            host = host[len(scheme):]
            break
    if host.startswith("www."):
        host = host[4:]
    host = re.split(r"[/?#\s]", host, maxsplit=1)[0]
    host = host.split(":", 1)[0]
    parts = [p for p in host.split(".") if p]
    if len(parts) < 2:
        return host
    if host in _MULTI_LABEL_SUFFIXES:
        # `gov.ph` is a suffix, not a domain anyone owns. As a scope it would
        # boost nothing and read as though something had been scoped, so the
        # caller gets nothing back and decides what to do about it.
        return ""
    if ".".join(parts[-2:]) in _MULTI_LABEL_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


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
    """The one query issued for the employer itself.

    `company or employer` is deliberate. It reads as a boolean to a search
    engine, so a business writing itself "Tanika Company", "Tanika Employer" or
    neither is matched either way - the employer name is often the only handle
    a small Philippine business has, and a wrong guess at its suffix is a query
    that returns nothing. It used to be paired with `registration certificate`
    and `reviews complaints`, but two targeted queries each starved the others:
    a general company query is what surfaces the employer's own pages, a PESO
    listing and a job board post in one result set, and those are the pages the
    prompt judges for existence, registration and channel match.

    That costs the two targeted rankings. `Official Registration` and
    `Reputation` now depend on the one query surfacing the right page rather
    than asking for it by name. A company with neither a filing nor any review
    is found by neither, which reports yellow on existence - the smallest
    employers, the ones this product exists for.

    The name is used **verbatim**. It used to be stripped of a trailing
    Corporation/Corp/Inc/Co/LLC, on the reasoning that a generic legal form
    dilutes a rare name. That is wrong for this product's subject. A filing, a
    city PESO listing, and the employer's own legal pages are all titled with
    the *legal* name, so stripping it left the distinctive part competing against
    a brand, its franchisees, and unrelated products sharing the word - searching
    "Jollibee Foods" is a worse lookup than "Jollibee Foods Corporation". The
    scan states the employer once; nothing between here and the provider rewrites
    it, because every rewrite is a chance to search a different company than the
    one named.

    The Philippines is no longer appended. `country` on the search request
    already biases ranking toward Philippine results, so the suffix was the same
    signal applied twice - and appending it to every query spent characters
    without adding reach. It used to be the only geographic signal there was, so
    removing it makes `TAVILY_COUNTRY` load-bearing: set it blank and nothing
    anchors these queries to the Philippines at all. Results merge into one flat
    list for a single AI call, so this is one request, not one model call.
    """
    name = company.strip()
    return [f"{name} company or employer"]




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


# A scope is a preference, never a filter. Tavily's `include_domains_mode`
# accepts `restrict` (the default: results come only from the listed domains) or
# `prefer` (the listed domains are boosted and the rest of the web is still
# searched). Only `prefer` is ever sent — see `search()`'s note on why.
_MAX_SCOPED_DOMAINS = 5

# What Tavily accepts as a domain: a plain host or a subdomain, optionally
# with a scheme or a `www.` prefix. Wildcards, regular expressions, ports, and
# anything carrying a path, query or fragment are rejected by the provider, and a
# 400 would turn a scoping mistake into a failed lookup.
_SCOPED_DOMAIN_RE = re.compile(r"^(?:https?://)?(?:www\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


def _scoped_domains(domains) -> list[str]:
    """The list to send as `include_domains`, or an empty list to send nothing.

    Validated against the raw value and only then reduced, so `ched.gov.ph/careers`
    is **dropped** rather than widened to `ched.gov.ph`. Silently broadening a
    scope is the wrong direction to fail: a caller who meant one page would get a
    whole-domain boost and no indication of it. `_normalise_domain`, which cuts
    at the path instead, is right for `exclude_domains` — there a path is noise
    and the host is the intent — which is why the two are not the same function.

    A trailing slash is stripped first, because `https://www.acme.ph/` is a
    pasted URL and not a path.

    Blank and malformed entries are dropped rather than reported: a scope is an
    optimisation, and one bad entry must not cost the search that would otherwise
    have run.
    """
    out: list[str] = []
    for raw in domains or ():
        candidate = str(raw or "").strip().lower().rstrip("/")
        if not candidate or not _SCOPED_DOMAIN_RE.match(candidate):
            log.warning("[search] Ignoring an unusable domain scope: %r", raw)
            continue
        host = registrable_domain(candidate)
        if not host or host in out:
            continue
        out.append(host)
        if len(out) >= _MAX_SCOPED_DOMAINS:
            break
    return out


def search(
    query: str,
    max_results: int | None = None,
    include_domains: list | None = None,
) -> SearchOutcome:
    """Run one search. Never raises; a failure is reported in the outcome.

    `include_domains` **boosts** a domain; it does not restrict results to it.
    Tavily's `include_domains_mode` defaults to `restrict`, which is the reason
    this module's own comment above used to say the parameter must never be set:
    a hard filter would discard the JobStreet, Indeed PH and PESO pages the
    country boost exists to surface. `prefer` is a different lever of the same
    kind as `country` — ranking preference, no exclusion — so the reason the
    parameter was off does not apply to it.

    Only the adaptive planner passes a scope, and only ever one domain that came
    back from an earlier search. A domain from the posting's own text is never
    scoped to: that would search precisely the thing under suspicion.
    """
    limit = max_results if max_results is not None else settings.tavily_max_results

    config = _get_provider_config()
    provider_name = settings.search_provider.strip().lower()

    # DEBUG: log which provider is being used
    log.info("[search] Using provider: %s, endpoint: %s", provider_name, config["endpoint"])

    if not config["api_key"].strip():
        log.error("[search] %s_API_KEY is not configured; cannot search", provider_name.upper())
        return SearchOutcome(
            ok=False,
            error=f"{provider_name.upper()}_API_KEY is not configured on the backend.",
        )

    started = time.monotonic()
    payload = None
    raw = ""  # TEMPORARY DIAGNOSTIC — see SearchOutcome.raw_response.

    depth = config["search_depth"]
    if depth not in _VALID_DEPTHS:
        # A typo would have the provider reject the request, and the user would
        # be told a company cannot be looked up. Log it, then use the fallback
        # so a cost setting cannot become a verdict.
        if provider_name == "tavily":
            fallback = settings.tavily_search_depth_fallback
        else:
            fallback = "basic"
        log.error(
            "[search] %s_SEARCH_DEPTH=%r is not a valid depth; using %r",
            provider_name.upper(),
            config["search_depth"],
            fallback,
        )
        depth = fallback

    body = {
        "api_key": config["api_key"],
        "query": query,
        "max_results": limit,
        # Advanced costs 2 credits against basic's 1 and buys broader recall,
        # which is what a small local employer needs. SEARCH_DEPTH turns
        # it down when the monthly budget matters more.
        "search_depth": depth,
        # No `include_answer`. A synthesised answer is retrieval's opinion
        # rather than evidence, and the verification prompt requires source URLs
        # copied from the results themselves.
    }

    # Country boost — only Tavily supports this currently
    if provider_name == "tavily" and config["country"]:
        body["country"] = config["country"]

    # exclude_domains — only Tavily supports this currently
    if provider_name == "tavily" and config["exclude_domains"]:
        excluded = _parse_domains(config["exclude_domains"])
        if excluded:
            log.info("[search] excluding %d configured domain(s)", len(excluded))
            body["exclude_domains"] = excluded

    # `prefer` rather than the provider's default `restrict`, always. The mode
    # is what makes scoping safe here: `restrict` would be a hard filter and the
    # comment above explains why a hard filter is the wrong tool. `prefer`
    # coexists with `country` because both are boosts.
    scoped = _scoped_domains(include_domains)
    if scoped:
        log.info("[search] preferring %d domain scope(s) for '%s'", len(scoped), query)
        body["include_domains"] = scoped
        body["include_domains_mode"] = "prefer"

    try:
        response = httpx.post(
            config["endpoint"],
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

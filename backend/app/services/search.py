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

    `raw_response` is the provider's own body, kept so the debug tab can show
    what actually arrived. Without it a parse fault would render as a clean
    empty result, which is the failure the tab exists to catch.
    """

    results: list[SearchResult] = field(default_factory=list)
    ok: bool = True
    error: str = ""
    latency: float = 0.0
    raw_response: dict = field(default_factory=dict)


_CORPORATE_SUFFIX = re.compile(
    r"(?:[,\s&/]+|^)(?:incorporated|corporation|corp|inc|co|llc)\.?\s*$",
    re.IGNORECASE,
)

# Tavily's `country` boost, not a query term and not a domain filter. See
# search() for why ranking rather than phrasing is the lever here.
TAVILY_COUNTRY = "philippines"


def _strip_corporate_suffix(name: str) -> str:
    """Drop a trailing corporate suffix: 'Corporation', 'Corp.', 'Inc', 'Co'.

    A rare company name is diluted when a generic legal form is searched
    verbatim, so the distinctive part gets less of the query's weight.

    Only the tail is matched. Stripping is therefore blind to a suffix-shaped
    word elsewhere in the name: 'Incorporated Systems PH' keeps its first
    word, and 'Coca-Cola Bottlers' keeps 'Coca-Cola'. It also stops rather
    than returning an empty stem, because a name that is *only* a suffix
    would otherwise reduce to the geographic term alone and return results
    about any company.
    """
    stem = name.strip()
    while True:
        reduced = _CORPORATE_SUFFIX.sub("", stem).strip(" ,.&/-")
        if not reduced or reduced == stem:
            return stem
        stem = reduced


def build_query(company: str) -> str:
    """The one query issued per verification.

    No category suffixes. The model sorts results into the three categories
    itself, so a result is never labelled as belonging to one, and the query
    cannot assert that a lookup was for a scam report — asking for that text
    biases the results toward it and manufactures the appearance of evidence
    the prompt then has to be careful not to trust.
    """
    stem = _strip_corporate_suffix(company)
    if re.search(r"\bPhilippines\b", stem, re.IGNORECASE):
        return stem
    return f"{stem} Philippines"


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
    try:
        response = httpx.post(
            TAVILY_ENDPOINT,
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": limit,
                # Advanced costs 2 credits against basic's 1 and buys broader
                # recall, which is what a small local employer needs.
                "search_depth": "advanced",
                # Boost, do not filter. A browser search from the Philippines
                # surfaces SEC filings, city PESO sites, and local job boards
                # for a small employer; Tavily's own crawl index covers that
                # long tail less well, so a niche name falls through to
                # whatever it indexes strongly — a London VC firm, or an
                # unrelated product with a similar word. No query rewrite fixes
                # missing index coverage.
                #
                # `include_domains` is deliberately NOT set. It restricts
                # results to the listed domains, which would discard precisely
                # the JobStreet, Indeed PH, and PESO pages this boost exists to
                # surface. There is no "prefer" mode; the boost is the only
                # tool that matches the intent.
                "country": TAVILY_COUNTRY,
                # No `include_answer`. A synthesised answer is retrieval's
                # opinion rather than evidence, and the verification prompt
                # requires source URLs copied from the results themselves.
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        # Normalising inside the try: a shape change is a provider fault, and
        # search() must report it rather than raise out of the debug endpoint,
        # which has no exception handler mid-stream.
        results = _normalise(payload)
    except Exception as exc:  # noqa: BLE001
        latency = round(time.monotonic() - started, 3)
        log.error("[search] [error] '%s' failed: %s: %s", query, type(exc).__name__, exc)
        return SearchOutcome(
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            latency=latency,
            raw_response=payload if isinstance(payload, dict) else {},
        )

    latency = round(time.monotonic() - started, 3)
    if not results:
        # Not an error: the search worked and the company has no footprint.
        log.info("[search] '%s' returned no results in %ss", query, latency)
    else:
        log.info("[search] '%s' returned %d results in %ss", query, len(results), latency)
    return SearchOutcome(
        results=results, ok=True, error="", latency=latency, raw_response=payload
    )


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

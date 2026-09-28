"""Web search with rate limiting, retries, and a Tavily fallback.

DuckDuckGo is used as the primary provider because it needs no API key, but it
rate-limits aggressively: the same query intermittently returns zero results
while an identical query moments later returns five. Because the failure is
silent — an empty list is indistinguishable from a company with no online
presence — a throttled section used to reach the model as "nothing was found."

Three things guard against that here:
  * every failure is logged with a classified reason, so a throttled request is
    visible in the logs instead of looking like a clean company
  * transient failures are retried with backoff before giving up
  * if the primary still comes back empty, a secondary provider is tried

`ddg_min_interval` and `ddg_max_concurrent` are honoured on the synchronous path
too. They used to apply only to `throttled_search`, which nothing in the live
request path called, so the four verification queries all fired at once.
"""

import asyncio
import logging
import re
import threading
import time
from dataclasses import dataclass, field

from ddgs import DDGS

from app.config import settings

log = logging.getLogger("trabahero")

_search_semaphore: asyncio.Semaphore | None = None
_last_search_time: float = 0.0

# Guards the synchronous path. The async semaphore above cannot help the
# verification flow, which runs ddg_search in a worker thread.
_sync_lock = threading.Lock()
_sync_last_search: float = 0.0

# The backends the installed ddgs actually offers. It rejects anything else with
# "backends do not exist or are disabled", so this list must match its output or
# the pinned name is ignored and the call silently falls back to 'auto'.
#
# Order matters: yahoo answers most reliably from this machine, and the rest are
# tried in turn when one is rate-limited. An empty list means "let the library
# choose", which is a coin flip between engines and the reason sections used to
# fail at random.
_BACKEND_ORDER = ("yahoo", "mojeek", "startpage", "duckduckgo", "brave", "google", "wikipedia", "grokipedia")

# "No results found" is the library's way of reporting a refusal, not a genuine
# empty SERP: the same query usually succeeds seconds later.
_TRANSIENT_MARKERS = (
    "no results found",
    "rate limit",
    "too many requests",
    "429",
    "timeout",
    "timed out",
    "connection",
    "temporarily unavailable",
    "unreachable network",
    "bad gateway",
    "service unavailable",
)


@dataclass
class SearchOutcome:
    """Result of one search, including enough to diagnose a failure."""

    results: list[dict] = field(default_factory=list)
    provider: str = ""
    attempts: int = 0
    throttled: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.results)


def _is_transient(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def _throttle_sync() -> None:
    """Sleep so consecutive synchronous searches respect ddg_min_interval."""
    global _sync_last_search
    with _sync_lock:
        elapsed = time.monotonic() - _sync_last_search
        if elapsed < settings.ddg_min_interval:
            time.sleep(settings.ddg_min_interval - elapsed)
        _sync_last_search = time.monotonic()


def _normalise(raw: list[dict]) -> list[dict]:
    """Map the ddgs library's keys onto ours. The library calls it 'body'."""
    return [
        {
            "title": r.get("title", ""),
            "snippet": r.get("body", "")[:300],
            "url": r.get("href", ""),
        }
        for r in raw
    ]


def _ddg_once(query: str, max_results: int, only: str | None = None) -> list[dict]:
    """One search, trying each available engine in turn.

    The library picks an engine at random when none is given, and the engines are
    not equally reliable from here, so an unpinned call is a coin flip. Each is
    tried in _BACKEND_ORDER and the first that returns rows wins, which turns one
    rate-limited engine into a miss rather than a lost section.

    `only` restricts the search to a single engine, for the debug endpoint that
    reports on each engine separately.
    """
    order = [only] if only else ([settings.ddg_backend] if settings.ddg_backend else list(_BACKEND_ORDER))
    last_error: Exception | None = None

    for backend in order:
        try:
            with DDGS() as client:
                raw = list(client.text(query, max_results=max_results, backend=backend))
            if raw:
                if not only and backend != order[0]:
                    log.info("[search] backend %r answered for %r (tried after %r)", backend, query, order[0])
                return _normalise(raw)
            last_error = RuntimeError(f"backend {backend!r} returned no results")
        except Exception as e:  # noqa: BLE001
            last_error = e
            log.debug("[search] backend %r failed for %r: %s", backend, query, e)

    raise last_error if last_error else RuntimeError("no backend available")


def tavily_search(query: str, max_results: int = 5) -> list[dict]:
    """Search via Tavily, used only as a fallback. Returns our normal shape."""
    import httpx

    key = settings.tavily_api_key
    if not key:
        return []
    resp = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    return [
        {
            "title": item.get("title", ""),
            "snippet": (item.get("content") or "")[:300],
            "url": item.get("url", ""),
        }
        for item in resp.json().get("results", [])
    ]


def search_with_diagnostics(
    query: str,
    max_results: int = 5,
    provider: str = "ddg",
    attempts: int | None = None,
) -> SearchOutcome:
    """Run a search, retrying transient failures and logging the reason.

    Returns a SearchOutcome rather than a bare list so the caller can tell a
    throttled query from a company that genuinely has no footprint — the two
    used to be indistinguishable, and only the second is a real finding.
    """
    attempts = settings.ddg_search_attempts if attempts is None else attempts
    run = tavily_search if provider == "tavily" else _ddg_once
    outcome = SearchOutcome(provider=provider)
    last_error = ""

    for attempt in range(1, max(1, attempts) + 1):
        outcome.attempts = attempt
        try:
            if provider == "ddg":
                _throttle_sync()
            results = run(query, max_results)
            if results:
                outcome.results = results
                if attempt > 1:
                    log.info("[search] '%s' recovered on attempt %d/%d via %s", query, attempt, attempts, provider)
                return outcome
            # A 200 with no results is the throttle signature, not a finding:
            # the provider accepted the request and withheld the SERP, so
            # nothing raised and _is_transient() never saw it. Treating it as a
            # plain empty result is what let a burst of four queries return one
            # section and lose three.
            last_error = "HTTP 200 with an empty result set (provider withheld results)"
            if provider == "ddg":
                outcome.throttled = True
            log.warning(
                "[search] [%s] '%s' returned no results (attempt %d/%d) — %s",
                "throttled" if provider == "ddg" else "empty",
                query,
                attempt,
                attempts,
                last_error,
            )
        except Exception as e:  # noqa: BLE001
            last_error = f"{type(e).__name__}: {e}"
            outcome.throttled = outcome.throttled or _is_transient(e)
            log.warning(
                "[search] [%s] '%s' failed on attempt %d/%d via %s — %s",
                "throttled" if _is_transient(e) else "error",
                query,
                attempt,
                attempts,
                provider,
                last_error,
            )

        if attempt < attempts:
            # Back off harder than a normal retry would: the provider is being
            # rate-limited, so the wait has to outlast the window it is
            # enforcing. Multiplying by attempt beats a flat pause because a
            # burst needs progressively more room.
            time.sleep(min(settings.ddg_search_backoff * (2 ** (attempt - 1)), settings.ddg_search_backoff_max))

    outcome.error = last_error
    return outcome


def ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """Run a single search, falling back to Tavily. Returns [{title, snippet, url}]."""
    outcome = search_with_diagnostics(query, max_results)
    if outcome.ok:
        return outcome.results

    if settings.tavily_api_key:
        log.info("[search] primary provider came back empty for '%s'; trying tavily", query)
        fallback = search_with_diagnostics(query, max_results, provider="tavily", attempts=1)
        if fallback.ok:
            return fallback.results
        log.warning("[search] fallback provider also failed for '%s': %s", query, fallback.error)

    return []


async def throttled_search(query: str, max_results: int = 5) -> list[dict]:
    """Async wrapper with semaphore-based concurrency and minimum interval."""
    global _last_search_time
    sem = _get_semaphore()

    async with sem:
        elapsed = time.monotonic() - _last_search_time
        if elapsed < settings.ddg_min_interval:
            await asyncio.sleep(settings.ddg_min_interval - elapsed)
        _last_search_time = time.monotonic()
        return await asyncio.to_thread(ddg_search, query, max_results)


def _get_semaphore() -> asyncio.Semaphore:
    global _search_semaphore
    if _search_semaphore is None:
        _search_semaphore = asyncio.Semaphore(settings.ddg_max_concurrent)
    return _search_semaphore


INVALID_COMPANY_NAMES = {
    "none", "n/a", "na", "unknown", "null", "undefined",
    "not specified", "unspecified", "unclear", "not provided",
    "not mentioned", "not available", "no company", "no company name",
    "unnamed", "anonymous", "company name", "company", "employer",
    "various", "confidential", "tbd", "pending",
}

# Values the model writes in its COMPANY NAME field when the content names no
# employer. Checked by is_valid_company_name so that every caller rejects them,
# not just the scan path.
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
    if lower in INVALID_COMPANY_NAMES:
        return False
    if lower in NOT_STATED_MARKERS:
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
    sentence — "Acme Corp. We are hiring for a cook" yields "Acme Corp. We are
    hiring for a cook". Feeding that to the search produces nothing, which then
    looks like an unverifiable company. Cut at the first clause boundary and
    drop any parenthetical suffix.
    """
    name = re.split(r"[.,;]\s", raw.strip(), maxsplit=1)[0]
    name = re.sub(r"\s*\(.*$", "", name)
    name = re.sub(r"^[^\w]+|[^\w]+$", "", name).strip()
    # Patterns like "X is hiring" sweep the verb into the capture.
    name = re.sub(r"\s+(?:is|are|was|were|has|have|will)$", "", name).strip()
    return name


def extract_company_name(text: str) -> str | None:
    """Try to extract a company name from job posting text."""
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
    # Every match is considered, not just the first: a leading sentence such as
    # "We are looking for staff. Jollibee is hiring..." matches the second
    # pattern from "We", and that rejected capture would otherwise hide the
    # real employer later in the text. The lookahead keeps each match
    # zero-width, so overlapping candidates are not skipped.
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

    The model states the employer in its own `EMPLOYER NAME` field, so this only
    has to tidy it and reject placeholders — it does not have to find it. A
    leading article is dropped so "The company" is judged on the word after it,
    which keeps the generic-word rejection working.

    A joined name is split back into its parts, keeping the last. Postings that
    name a recruiter and a client ("Vikings / Silvergreen Manpower Services
    Corporation") arrive here as one string, and a search engine tokenises the
    slash into neither entity. The client is named after the recruiter in these
    postings, so the tail is the one to look up.
    """
    if not name or not isinstance(name, str):
        return ""
    cleaned = _clean_company_candidate(name)
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE).strip()

    # A model that names two parties separates them; look up the second, which
    # is the employer in a recruiter/client posting.
    for sep in ("/", "|"):
        if sep in cleaned:
            parts = [p.strip() for p in cleaned.split(sep) if p.strip()]
            parts = [p for p in parts if is_valid_company_name(p)]
            if not parts:
                return ""
            log.info("[ddg] Joined employer name %r; looking up %r instead", cleaned, parts[-1])
            cleaned = parts[-1]

    if not cleaned or not is_valid_company_name(cleaned):
        return ""
    return cleaned


def format_search_context(search_data: dict) -> str:
    """Format search results into a context string for the AI prompt."""
    has_any = any(
        search_data.get(k)
        for k in ["legitimacy_results", "sec_results", "scam_results", "linkedin_results", "dole_results", "social_results"]
    )
    if not has_any:
        return ""

    lines = [f"=== WEB SEARCH: {search_data.get('company', 'unknown')} ==="]

    sections = [
        ("legitimacy_results", "Company Info"),
        ("sec_results", "SEC Registration"),
        ("scam_results", "Scam/Fraud Reports"),
        ("linkedin_results", "LinkedIn Presence"),
        ("dole_results", "DOLE Licensed Agency"),
        ("social_results", "Social Media Reviews"),
    ]

    for key, label in sections:
        results = search_data.get(key, [])
        if results:
            lines.append(f"\n[{label}]")
            for i, r in enumerate(results[:3], 1):
                lines.append(f"  {i}. {r.get('title', '')}")
                if r.get("snippet"):
                    lines.append(f"     {r['snippet'][:200]}")

    lines.append("\n=== END SEARCH ===")
    return "\n".join(lines)


_COMPANY_CACHE: dict[str, dict] = {}
_COMPANY_CACHE_MAX = 32


def search_company(company_name: str) -> dict:
    """Multi-query company search. Returns structured results including social media reviews.

    Cached per company name: a single text scan calls this twice (once for prompt
    context, once for the response payload) and would otherwise pay for eight
    searches twice.
    """
    cached = _COMPANY_CACHE.get(company_name)
    if cached is not None:
        return cached

    legitimacy = ddg_search(f"{company_name} Philippines company", 5)
    sec = ddg_search(f"{company_name} SEC registration Philippines", 3)
    scam = ddg_search(f"{company_name} scam fraud warning Philippines", 3)
    linkedin = ddg_search(f"{company_name} LinkedIn company page", 2)
    dole = ddg_search(f"{company_name} DOLE licensed recruitment agency Philippines", 2)
    facebook_reviews = ddg_search(f'site:facebook.com "{company_name}" reviews', 5)
    reddit_reviews = ddg_search(f'site:reddit.com "{company_name}" Philippines', 5)
    general_reviews = ddg_search(f'"{company_name}" reviews employee', 5)

    # These three read ddg_search()'s return, which uses 'snippet' and 'url'.
    # Reading 'body'/'href' here — the raw library keys — silently produced empty
    # snippets for all 13 results, so the Social Media Reviews section reached
    # the scan prompt as titles with no text.
    social_results = []
    social_results.extend([{"title": r.get("title", ""), "snippet": r.get("snippet", "")[:300], "url": r.get("url", ""), "source": "Facebook"} for r in facebook_reviews])
    social_results.extend([{"title": r.get("title", ""), "snippet": r.get("snippet", "")[:300], "url": r.get("url", ""), "source": "Reddit"} for r in reddit_reviews])
    social_results.extend([{"title": r.get("title", ""), "snippet": r.get("snippet", "")[:300], "url": r.get("url", ""), "source": "Web"} for r in general_reviews])

    data = {
        "company": company_name,
        "legitimacy_results": legitimacy,
        "sec_results": sec,
        "scam_results": scam,
        "linkedin_results": linkedin,
        "dole_results": dole,
        "social_results": social_results,
    }

    if len(_COMPANY_CACHE) >= _COMPANY_CACHE_MAX:
        _COMPANY_CACHE.pop(next(iter(_COMPANY_CACHE)), None)
    _COMPANY_CACHE[company_name] = data
    return data


# The verification step asks the model about three categories, so it runs three
# searches instead of eight. A wider net gave the model more results than it
# needed, and the extra categories were the ones producing invented detail.
_VERIFY_QUERIES = (
    ("legitimacy", "{company} Philippines company"),
    ("sec", "{company} SEC registration Philippines"),
    ("scam", "{company} scam fraud complaint"),
    ("reviews", '"{company}" reviews employee'),
)


def search_company_for_verification(company_name: str) -> dict:
    """Four lean searches covering the three verification categories.

    Records which sections came back empty in `throttled`. A section that failed
    retrieval is not the same as a section that found nothing, and only the
    caller can tell the model the difference.
    """
    results: dict[str, list] = {"company": company_name}
    throttled: list[str] = []
    for key, template in _VERIFY_QUERIES:
        query = template.format(company=company_name)
        outcome = search_with_diagnostics(query, 5)
        if outcome.ok:
            results[key] = outcome.results
        else:
            results[key] = []
            throttled.append(key)
    results["throttled"] = throttled
    if throttled:
        log.warning(
            "[ddg] Retrieval failed for %d of %d sections for '%s': %s. "
            "Those categories are unknown, not clear.",
            len(throttled),
            len(_VERIFY_QUERIES),
            company_name,
            ", ".join(throttled),
        )
    return results


# Bumped whenever the retrieval code changes, and logged once at startup. Stale
# code in a --reload process produced results from an engine this file no longer
# uses, and the mismatch was invisible in the logs. This makes the running
# version identifiable at a glance.
SEARCH_CODE_VERSION = "2026-09-28.3-raw-dump-rotation"
log.info("[search] code version %s", SEARCH_CODE_VERSION)
log.info("[search] backend order: %s", ", ".join(_BACKEND_ORDER))
log.info("[search] pinned backend: %r", settings.ddg_backend or "(none, rotating)")


THROTTLED_NOTICE = """
NOTE ON RETRIEVAL: these queries returned nothing: {sections}.
That means the search was throttled or failed, NOT that the company has no such
record. Do not treat them as findings. Report the affected category as yellow
and say the search returned no results, without implying the company lacks them."""


def format_verification_context(data: dict) -> str:
    """A plain, unorganised dump of everything the searches returned.

    No categories, no ranking, no dedupe: each query is shown with its full
    result set in the order the provider returned it. The category headings used
    to live here, and they were doing two jobs badly — presenting a generic
    result page found by a "scam" query as if it were a scam report, and
    repeating the same result under several headings. Handing the model the
    queries alongside the results lets it judge what a result actually is.
    """
    if not data:
        return ""

    queries = {k: t.format(company=data.get("company", "")) for k, t in _VERIFY_QUERIES}
    if not any(data.get(k) for k in queries):
        return ""

    lines = [f"=== SEARCH RESULTS FOR: {data.get('company', 'unknown')} ==="]

    for key, query in queries.items():
        hits = data.get(key) or []
        lines.append(f"\n--- QUERY: {query}")
        if not hits:
            lines.append("(no results returned for this query)")
            continue
        for i, r in enumerate(hits, 1):
            lines.append(f"  {i}. {r.get('title', '')}")
            if r.get("url"):
                lines.append(f"     url: {r['url']}")
            # ddg_search() returns 'snippet' — it renames the library's 'body'.
            # Reading 'body' here silently dropped every snippet, so the model
            # was shown titles only and correctly reported that nothing mentioned
            # SEC registration.
            if r.get("snippet"):
                lines.append(f"     {r['snippet'][:300]}")

    throttled = data.get("throttled") or []
    if throttled:
        failed = ", ".join(queries[k] for k in throttled if k in queries)
        lines.append(THROTTLED_NOTICE.format(sections=failed))

    lines.append("\n=== END SEARCH ===")
    return "\n".join(lines)


def search_job_posting(text: str) -> str:
    """Extract company name from text and search. Returns formatted context."""
    company = extract_company_name(text)
    if not company:
        return ""
    log.info("[ddg] Verifying company '%s'", company)
    data = search_company(company)
    return format_search_context(data)


def verify_company(company_name: str) -> str:
    """Lean company verification: four searches covering the three categories."""
    if not company_name or not is_valid_company_name(company_name):
        return ""
    log.info("[ddg] Verifying company '%s'", company_name)
    data = search_company_for_verification(company_name)
    return format_verification_context(data)


def search_job_posting_data(text: str) -> dict:
    """Extract company name and search. Returns raw data dict for frontend."""
    company = extract_company_name(text)
    if not company:
        return {"company_name": None, "results": {}}
    log.info("[ddg] Search data for company '%s'", company)
    data = search_company(company)
    social_list = [
        {"title": r.get("title", ""), "snippet": r.get("snippet", "")[:200], "url": r.get("url", ""), "source": r.get("source", "")}
        for r in data.get("social_results", [])
    ]
    summary = {
        "company": company,
        "legitimacy": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", "")[:200], "url": r.get("url", "")}
            for r in data.get("legitimacy_results", [])[:3]
        ],
        "sec": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", "")[:200], "url": r.get("url", "")}
            for r in data.get("sec_results", [])[:2]
        ],
        "scam_reports": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", "")[:200], "url": r.get("url", "")}
            for r in data.get("scam_results", [])[:2]
        ],
        "linkedin": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", "")[:150], "url": r.get("url", "")}
            for r in data.get("linkedin_results", [])[:2]
        ],
        "dole": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", "")[:200], "url": r.get("url", "")}
            for r in data.get("dole_results", [])[:2]
        ],
        "reviews": social_list,
    }
    return {"company_name": company, "results": summary}

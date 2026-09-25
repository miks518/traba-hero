"""DuckDuckGo web search with rate limiting."""

import asyncio
import logging
import time

from ddgs import DDGS

from app.config import settings

log = logging.getLogger("trabahero")

_search_semaphore: asyncio.Semaphore | None = None
_last_search_time: float = 0.0


def _get_semaphore() -> asyncio.Semaphore:
    global _search_semaphore
    if _search_semaphore is None:
        _search_semaphore = asyncio.Semaphore(settings.ddg_max_concurrent)
    return _search_semaphore


def ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """Run a single DuckDuckGo search. Returns [{title, snippet, url}]."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            {
                "title": r.get("title", ""),
                "snippet": r.get("body", "")[:300],
                "url": r.get("href", ""),
            }
            for r in results
        ]
    except Exception as e:
        log.warning("[ddg] Search failed for '%s': %s", query, e)
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


INVALID_COMPANY_NAMES = {
    "none", "n/a", "na", "unknown", "null", "undefined",
    "not specified", "unspecified", "unclear", "not provided",
    "not mentioned", "not available", "no company", "no company name",
    "unnamed", "anonymous", "company name", "employer",
    "various", "confidential", "tbd", "pending",
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
    for prefix in (
        "not specified", "not provided", "not mentioned", "not available",
        "no company", "company name unclear", "company unclear", "unknown company",
    ):
        if lower.startswith(prefix) or lower == prefix:
            return False
    return True


def extract_company_name(text: str) -> str | None:
    """Try to extract a company name from job posting text."""
    import re

    text = text[:3000]
    patterns = [
        r"(?:at|for|@)\s+([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"([A-Z][A-Za-z0-9\s&.,'-]{2,40})\s+(?:is hiring|is looking|seeks|wants|hiring)",
        r"About\s+([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"Company:\s*([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"Employer:\s*([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
    ]
    skip_words = {"the", "this", "our", "your", "we", "you", "they", "his", "her", "a", "an"}
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            name = re.sub(r"^[^\w]+|[^\w]+$", "", name).strip()
            words = name.lower().split()
            if words and words[0] not in skip_words and len(name) > 3 and is_valid_company_name(name):
                return name
    return None


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


def search_company(company_name: str) -> dict:
    """Multi-query company search. Returns structured results including social media reviews."""
    legitimacy = ddg_search(f"{company_name} Philippines company", 5)
    sec = ddg_search(f"{company_name} SEC registration Philippines", 3)
    scam = ddg_search(f"{company_name} scam fraud warning Philippines", 3)
    linkedin = ddg_search(f"{company_name} LinkedIn company page", 2)
    dole = ddg_search(f"{company_name} DOLE licensed recruitment agency Philippines", 2)
    facebook_reviews = ddg_search(f'site:facebook.com "{company_name}" reviews', 5)
    reddit_reviews = ddg_search(f'site:reddit.com "{company_name}" Philippines', 5)
    general_reviews = ddg_search(f'"{company_name}" reviews employee', 5)

    social_results = []
    social_results.extend([{"title": r.get("title", ""), "snippet": r.get("body", "")[:300], "url": r.get("href", ""), "source": "Facebook"} for r in facebook_reviews])
    social_results.extend([{"title": r.get("title", ""), "snippet": r.get("body", "")[:300], "url": r.get("href", ""), "source": "Reddit"} for r in reddit_reviews])
    social_results.extend([{"title": r.get("title", ""), "snippet": r.get("body", "")[:300], "url": r.get("href", ""), "source": "Web"} for r in general_reviews])

    return {
        "company": company_name,
        "legitimacy_results": legitimacy,
        "sec_results": sec,
        "scam_results": scam,
        "linkedin_results": linkedin,
        "dole_results": dole,
        "social_results": social_results,
    }


def search_job_posting(text: str) -> str:
    """Extract company name from text and search. Returns formatted context."""
    company = extract_company_name(text)
    if not company:
        return ""
    log.info("[ddg] Verifying company '%s'", company)
    data = search_company(company)
    return format_search_context(data)


def verify_company(company_name: str) -> str:
    """Run extended company verification searches and return formatted context."""
    if not company_name or not is_valid_company_name(company_name):
        return ""
    log.info("[ddg] Verifying company '%s' with extended search", company_name)
    data = search_company(company_name)
    return format_search_context(data)


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

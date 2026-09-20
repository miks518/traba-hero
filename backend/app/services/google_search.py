"""Google Custom Search API — replaces DuckDuckGo for reliable web searches."""

import logging
from urllib.parse import quote_plus

import httpx

from app.config import settings

log = logging.getLogger("trabahero")

GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


def google_search(query: str, num_results: int = 5) -> list[dict]:
    """Run a Google Custom Search query. Returns list of {title, snippet, url}."""
    if not settings.google_search_api_key or not settings.google_search_cx:
        log.warning("Google Search not configured — missing API key or CX")
        return []

    try:
        resp = httpx.get(
            GOOGLE_SEARCH_URL,
            params={
                "key": settings.google_search_api_key,
                "cx": settings.google_search_cx,
                "q": query,
                "num": min(num_results, 10),
            },
            timeout=10,
        )
        if resp.status_code != 200:
            log.warning("Google Search returned %d: %s", resp.status_code, resp.text[:200])
            return []

        data = resp.json()
        items = data.get("items", [])
        return [
            {
                "title": item.get("title", ""),
                "snippet": item.get("snippet", "")[:300],
                "url": item.get("link", ""),
            }
            for item in items
        ]
    except Exception as e:
        log.warning("Google Search failed for '%s': %s", query, e)
        return []


def search_company(company_name: str) -> dict:
    """Search for company info using Google. Returns structured results."""
    legitimacy = google_search(f"{company_name} Philippines company", 5)
    sec = google_search(f"{company_name} SEC registration Philippines", 3)
    scam = google_search(f"{company_name} scam fraud warning Philippines", 3)
    linkedin = google_search(f"{company_name} LinkedIn company page", 2)
    dole = google_search(f"{company_name} DOLE licensed recruitment agency Philippines", 2)
    facebook = google_search(f"{company_name} Facebook page Philippines", 2)

    return {
        "company": company_name,
        "legitimacy_results": legitimacy,
        "sec_results": sec,
        "scam_results": scam,
        "linkedin_results": linkedin,
        "dole_results": dole,
        "facebook_results": facebook,
    }


def format_search_results(search_data: dict) -> str:
    """Format search results into a context string for the AI prompt."""
    has_any = any(
        search_data.get(k)
        for k in ["legitimacy_results", "sec_results", "scam_results", "linkedin_results", "dole_results"]
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
        ("facebook_results", "Facebook Presence"),
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


def search_job_posting(text: str) -> str:
    """Extract company name from text and search. Returns formatted context."""
    from app.services.web_search import _extract_company_name

    company = _extract_company_name(text)
    if not company:
        return ""
    log.info("Google Search: verifying company '%s'", company)
    data = search_company(company)
    return format_search_results(data)


def search_job_posting_data(text: str) -> dict:
    """Extract company name and search. Returns raw data dict for frontend."""
    from app.services.web_search import _extract_company_name

    company = _extract_company_name(text)
    if not company:
        return {"company_name": None, "results": {}}
    log.info("Google Search data: verifying company '%s'", company)
    data = search_company(company)
    summary = {
        "company": company,
        "legitimacy": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("url", "")}
            for r in data.get("legitimacy_results", [])[:3]
        ],
        "sec": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("url", "")}
            for r in data.get("sec_results", [])[:2]
        ],
        "scam_reports": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("url", "")}
            for r in data.get("scam_results", [])[:2]
        ],
        "linkedin": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("url", "")}
            for r in data.get("linkedin_results", [])[:2]
        ],
        "dole": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", ""), "url": r.get("url", "")}
            for r in data.get("dole_results", [])[:2]
        ],
    }
    return {"company_name": company, "results": summary}

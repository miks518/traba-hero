"""Brave Search API — reliable web searches (2000 queries/month free, no credit card)."""

import logging

import httpx

from app.config import settings

log = logging.getLogger("trabahero")

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def brave_search(query: str, num_results: int = 5) -> list[dict]:
    """Run a Brave Search query. Returns list of {title, snippet, url}."""
    if not settings.brave_search_api_key:
        log.warning("Brave Search not configured — missing API key")
        return []

    try:
        resp = httpx.get(
            BRAVE_SEARCH_URL,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": settings.brave_search_api_key,
            },
            params={"q": query, "count": min(num_results, 20)},
            timeout=10,
        )
        if resp.status_code != 200:
            log.warning("Brave Search returned %d: %s", resp.status_code, resp.text[:200])
            return []

        data = resp.json()
        results = data.get("web", {}).get("results", [])
        return [
            {
                "title": item.get("title", ""),
                "snippet": item.get("description", "")[:300],
                "url": item.get("url", ""),
            }
            for item in results
        ]
    except Exception as e:
        log.warning("Brave Search failed for '%s': %s", query, e)
        return []


def search_company(company_name: str) -> dict:
    """Search for company info using Brave. Returns structured results."""
    legitimacy = brave_search(f"{company_name} Philippines company", 5)
    sec = brave_search(f"{company_name} SEC registration Philippines", 3)
    scam = brave_search(f"{company_name} scam fraud warning Philippines", 3)
    dole = brave_search(f"{company_name} DOLE licensed recruitment agency Philippines", 2)

    return {
        "company": company_name,
        "legitimacy_results": legitimacy,
        "sec_results": sec,
        "scam_results": scam,
        "linkedin_results": [],
        "dole_results": dole,
        "facebook_results": [],
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
    log.info("Brave Search: verifying company '%s'", company)
    data = search_company(company)
    return format_search_results(data)


def search_job_posting_data(text: str) -> dict:
    """Extract company name and search. Returns raw data dict for frontend."""
    from app.services.web_search import _extract_company_name

    company = _extract_company_name(text)
    if not company:
        return {"company_name": None, "results": {}}
    log.info("Brave Search data: verifying company '%s'", company)
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

import logging
import re
from duckduckgo_search import DDGS

log = logging.getLogger("trabahero")


def _extract_company_name(text: str) -> str | None:
    """Try to extract a company name from job posting text."""
    text = text[:3000]
    patterns = [
        r"(?:at|for|@)\s+([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"([A-Z][A-Za-z0-9\s&.,'-]{2,40})\s+(?:is hiring|is looking|seeks|wants|hiring)",
        r"About\s+([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"Company:\s*([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
        r"Employer:\s*([A-Z][A-Za-z0-9\s&.,'-]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            skip_words = {"the", "this", "our", "your", "we", "you", "they", "his", "her", "a", "an"}
            words = name.lower().split()
            if words and words[0] not in skip_words and len(name) > 3:
                return name
    return None


def search_company(company_name: str, max_results: int = 5) -> dict:
    """Search DuckDuckGo for company information with Philippine-focused queries."""
    try:
        with DDGS() as ddgs:
            # 1. General legitimacy check
            legitimacy = list(ddgs.text(
                f"{company_name} Philippines company",
                max_results=max_results,
            ))

            # 2. SEC registration check
            sec_results = list(ddgs.text(
                f"{company_name} SEC registration Philippines",
                max_results=3,
            ))

            # 3. Scam/fraud reports
            scam_results = list(ddgs.text(
                f"{company_name} scam fraud warning Philippines",
                max_results=3,
            ))

            # 4. LinkedIn/company presence
            linkedin_results = list(ddgs.text(
                f"{company_name} LinkedIn company page",
                max_results=2,
            ))

            return {
                "company": company_name,
                "legitimacy_results": legitimacy,
                "sec_results": sec_results,
                "scam_results": scam_results,
                "linkedin_results": linkedin_results,
            }
    except Exception as e:
        log.warning("Web search failed for '%s': %s", company_name, e)
        return {
            "company": company_name,
            "legitimacy_results": [],
            "sec_results": [],
            "scam_results": [],
            "linkedin_results": [],
        }


def format_search_results(search_data: dict) -> str:
    """Format search results into a context string for the AI prompt."""
    has_any = any(
        search_data.get(k)
        for k in ["legitimacy_results", "sec_results", "scam_results", "linkedin_results"]
    )
    if not has_any:
        return ""

    lines = [f"=== WEB SEARCH: {search_data.get('company', 'unknown')} ==="]

    if search_data.get("legitimacy_results"):
        lines.append("\n[Company Info]")
        for i, r in enumerate(search_data["legitimacy_results"][:3], 1):
            title = r.get("title", "")
            body = r.get("body", "")[:200]
            lines.append(f"  {i}. {title}")
            if body:
                lines.append(f"     {body}")

    if search_data.get("sec_results"):
        lines.append("\n[SEC Registration]")
        for i, r in enumerate(search_data["sec_results"][:2], 1):
            title = r.get("title", "")
            body = r.get("body", "")[:200]
            lines.append(f"  {i}. {title}")
            if body:
                lines.append(f"     {body}")

    if search_data.get("scam_results"):
        lines.append("\n[Scam/Fraud Reports]")
        for i, r in enumerate(search_data["scam_results"][:2], 1):
            title = r.get("title", "")
            body = r.get("body", "")[:200]
            lines.append(f"  {i}. {title}")
            if body:
                lines.append(f"     {body}")

    if search_data.get("linkedin_results"):
        lines.append("\n[LinkedIn Presence]")
        for i, r in enumerate(search_data["linkedin_results"][:2], 1):
            title = r.get("title", "")
            body = r.get("body", "")[:150]
            lines.append(f"  {i}. {title}")
            if body:
                lines.append(f"     {body}")

    lines.append("\n=== END SEARCH ===")
    return "\n".join(lines)


def search_job_posting(text: str) -> str:
    """Extract company name from text and search for it. Returns formatted context."""
    company = _extract_company_name(text)
    if not company:
        log.info("Could not extract company name from text")
        return ""
    log.info("Web search: verifying company '%s'", company)
    data = search_company(company)
    return format_search_results(data)

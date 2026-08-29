import logging

import httpx

from app.config import settings

log = logging.getLogger("trabahero")

SEC_NUMBER_API_URL = "https://gwwso2.sec.gov.ph/secnumber/1.0.0"

REQUEST_TIMEOUT = 15


def _headers() -> dict:
    headers = {"User-Agent": "trabahero/1.0", "Accept": "application/json"}
    if settings.sec_api_key:
        headers["ApiKey"] = settings.sec_api_key
        headers["Authorization"] = f"Bearer {settings.sec_api_key}"
    return headers


def _get(url: str, params: dict) -> dict:
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.get(url, params=params, headers=_headers())
            if resp.status_code != 200:
                log.warning("SEC API %s returned %s: %s", url, resp.status_code, resp.text[:200])
                return {}
            return resp.json() if resp.headers.get("Content-Type", "").count("json") else {}
    except Exception as e:
        log.warning("SEC API call failed for %s: %s", url, e)
        return {}


def lookup_company_by_name(company_name: str) -> dict:
    """Search SEC registered companies by name. Returns first page of matches."""
    return _get(
        f"{settings.sec_api_url}/cil_name_search.php",
        {"company_name": company_name, "page_no": "1"},
    )


def lookup_company_by_sec_no(sec_no: str) -> dict:
    """Get registration status/details using a SEC number."""
    data = _get(
        f"{settings.sec_api_url}/cil_status.php",
        {"sec_no": sec_no},
    )
    if not data:
        data = _get(
            f"{SEC_NUMBER_API_URL}/client_sec_no_status.php",
            {"sec_no": sec_no},
        )
    return data


def _matches_from(data: dict) -> list:
    if not isinstance(data, dict):
        return []
    inner = data.get("data") or data.get("success") or []
    if isinstance(inner, dict):
        inner = [inner]
    return [m for m in inner if isinstance(m, dict) and m.get("company_name")]


def format_sec_results(company_name: str, data: dict) -> str:
    """Format SEC lookup results into a context string for the AI prompt."""
    matches = _matches_from(data)
    if not matches:
        return ""

    lines = [f"=== SEC REGISTRY (Philippine SEC): {company_name} ==="]
    for i, m in enumerate(matches[:5], 1):
        name = m.get("company_name", "")
        sec_no = m.get("sec_no", "")
        status = m.get("status", m.get("status_id", ""))
        detail = " | ".join(
            v for v in [name, sec_no, status, m.get("date_approved", m.get("term_of_existence", ""))] if v
        )
        lines.append(f"  {i}. {detail}")
    lines.append("=== END SEC REGISTRY ===")
    return "\n".join(lines)


def sec_context(company_name: str) -> str:
    """Full pipeline: name search -> optional sec_no detail. Returns formatted context or ''."""
    if not settings.sec_api_key:
        log.info("SEC API: no API key configured; skipping registry lookup")
        return ""
    log.info("SEC API: looking up '%s'", company_name)
    data = lookup_company_by_name(company_name)
    if not data:
        return ""
    return format_sec_results(company_name, data)


def sec_data(company_name: str) -> list[dict]:
    """Return raw SEC registry matches as list of dicts for frontend."""
    if not settings.sec_api_key:
        return []
    log.info("SEC data: looking up '%s'", company_name)
    data = lookup_company_by_name(company_name)
    matches = _matches_from(data)
    return [
        {
            "company_name": m.get("company_name", ""),
            "sec_no": m.get("sec_no", ""),
            "status": m.get("status", m.get("status_id", "")),
            "date_approved": m.get("date_approved", m.get("term_of_existence", "")),
        }
        for m in matches[:5]
    ]
"""External verifiers — phone, domain, website, social media, government registries."""

import re
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
import whois
from duckduckgo_search import DDGS

log = logging.getLogger("trabahero")

# ── Philippine phone patterns ────────────────────────────────────────────
_PH_MOBILE = re.compile(r"(\+63|0)9\d{9}")
_PH_LANDLINE = re.compile(r"(\+63|0)\d{2,3}\d{7,8}")
_PH_PHONE = re.compile(r"(?:\+63|0)\d{9,10}")

# ── URL / domain extraction ──────────────────────────────────────────────
_URL_RE = re.compile(r"https?://[^\s<>\"']+")
_DOMAIN_RE = re.compile(r"(?:https?://)?(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,})")


@dataclass
class PhoneCheck:
    number: str
    valid_format: bool
    carrier: str
    risk: str  # low | medium | high
    reason: str


@dataclass
class DomainCheck:
    domain: str
    exists: bool
    age_months: int | None
    registrar: str | None
    risk: str
    reason: str


@dataclass
class WebsiteCheck:
    url: str
    alive: bool
    status_code: int | None
    risk: str
    reason: str


@dataclass
class SocialCheck:
    platform: str
    found: bool
    url: str | None
    title: str | None
    risk: str
    reason: str


@dataclass
class GovCheck:
    registry: str  # PhilGEPS | DTI | SEC
    found: bool
    details: str | None
    risk: str
    reason: str


@dataclass
class ScamListCheck:
    found: bool
    count: int
    sources: list[str]
    risk: str
    reason: str


@dataclass
class VerificationResult:
    phones: list[PhoneCheck] = field(default_factory=list)
    domains: list[DomainCheck] = field(default_factory=list)
    websites: list[WebsiteCheck] = field(default_factory=list)
    social: list[SocialCheck] = field(default_factory=list)
    gov: list[GovCheck] = field(default_factory=list)
    scam_lists: list[ScamListCheck] = field(default_factory=list)


# ── Phone validation ─────────────────────────────────────────────────────

_CARRIER_PREFIXES = {
    "0917": "Globe", "0918": "Smart", "0919": "Smart", "0920": "Smart",
    "0921": "Smart", "0922": "Sun/Smart", "0923": "Sun/Smart", "0924": "Sun/Smart",
    "0925": "Sun/Smart", "0926": "Sun/Smart", "0927": "Globe", "0928": "Smart",
    "0929": "Smart", "0930": "Smart", "0931": "Smart", "0932": "Sun/Smart",
    "0933": "Sun/Smart", "0934": "Sun/Smart", "0935": "Globe", "0936": "Globe",
    "0937": "Globe", "0938": "Smart", "0939": "Smart", "0940": "Sun/Smart",
    "0941": "Sun/Smart", "0942": "Sun/Smart", "0943": "Sun/Smart", "0944": "Sun/Smart",
    "0945": "Globe", "0946": "Smart", "0947": "Smart", "0948": "Smart",
    "0949": "Smart", "0950": "Smart", "0951": "Globe", "0952": "Globe",
    "0953": "Globe", "0954": "Globe", "0955": "Globe", "0956": "Globe",
    "0957": "Globe", "0958": "Globe", "0959": "Globe", "0960": "Globe",
    "0961": "DITO", "0962": "DITO", "0963": "DITO", "0964": "DITO",
    "0965": "DITO", "0966": "DITO", "0967": "DITO", "0968": "DITO",
    "0969": "DITO", "0970": "DITO", "0981": "Smart", "0989": "Smart",
}


def _check_phone(raw: str) -> PhoneCheck:
    clean = re.sub(r"[\s\-\(\)]", "", raw)
    is_valid = bool(_PH_PHONE.fullmatch(clean))
    prefix = clean[-10:][:4] if len(clean) >= 10 else ""
    carrier = _CARRIER_PREFIXES.get(prefix, "Unknown")

    if not is_valid:
        return PhoneCheck(raw, False, "", "high", "Invalid Philippine phone format")
    return PhoneCheck(raw, True, carrier, "low", f"Valid {carrier} number")


def verify_phones(text: str) -> list[PhoneCheck]:
    phones = set(_PH_PHONE.findall(text))
    return [_check_phone(p) for p in phones]


# ── Domain age + WHOIS ───────────────────────────────────────────────────

def _check_domain(domain: str) -> DomainCheck:
    try:
        w = whois.whois(domain)
        creation = w.creation_date
        if isinstance(creation, list):
            creation = creation[0]
        if creation:
            from datetime import datetime
            age_days = (datetime.now() - creation).days
            age_months = age_days // 30
        else:
            age_months = None

        registrar = w.registrar or None

        if age_months is not None and age_months < 6:
            return DomainCheck(domain, True, age_months, registrar, "high",
                               f"Domain only {age_months} months old — newly registered")
        if age_months is not None and age_months < 12:
            return DomainCheck(domain, True, age_months, registrar, "medium",
                               f"Domain is {age_months} months old — relatively new")
        return DomainCheck(domain, True, age_months, registrar, "low",
                           f"Domain is {age_months} months old — established")
    except Exception:
        return DomainCheck(domain, False, None, None, "medium",
                           "Could not retrieve domain info")


def _extract_domains(text: str) -> list[str]:
    urls = _URL_RE.findall(text)
    domains = set()
    for url in urls:
        parsed = urlparse(url)
        if parsed.hostname:
            domains.add(parsed.hostname.lower().removeprefix("www."))
    # Also check bare domains in text
    for m in _DOMAIN_RE.finditer(text):
        d = m.group(1).lower()
        if d not in ("com", "ph", "net", "org", "gov", "edu"):
            domains.add(d)
    return list(domains)


def verify_domains(text: str) -> list[DomainCheck]:
    return [_check_domain(d) for d in _extract_domains(text)]


# ── Website alive check ──────────────────────────────────────────────────

def _check_website(url: str) -> WebsiteCheck:
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.head(url)
            if resp.status_code < 400:
                return WebsiteCheck(url, True, resp.status_code, "low", "Website is alive")
            return WebsiteCheck(url, False, resp.status_code, "medium",
                                f"Website returned HTTP {resp.status_code}")
    except Exception:
        return WebsiteCheck(url, False, None, "medium", "Website could not be reached")


def verify_websites(text: str) -> list[WebsiteCheck]:
    urls = list(set(_URL_RE.findall(text)))
    return [_check_website(u) for u in urls[:5]]  # limit to 5


# ── Social media search ──────────────────────────────────────────────────

def _search_social(company: str, platform: str, query: str) -> SocialCheck:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        for r in results:
            title = (r.get("title") or "").lower()
            href = (r.get("href") or "").lower()
            if platform in href or platform in title:
                return SocialCheck(platform, True, r.get("href"), r.get("title"),
                                   "low", f"Found {platform} page for {company}")
        return SocialCheck(platform, False, None, None, "medium",
                           f"No {platform} page found for {company}")
    except Exception as e:
        log.warning("Social search failed for %s: %s", platform, e)
        return SocialCheck(platform, False, None, None, "medium",
                           f"Could not search {platform}")


def verify_social(company: str) -> list[SocialCheck]:
    if not company:
        return []
    checks = [
        _search_social(company, "facebook", f"{company} Philippines Facebook page"),
        _search_social(company, "linkedin", f"{company} LinkedIn company page"),
    ]
    return checks


# ── Government registries ────────────────────────────────────────────────

def _search_gov(company: str, registry: str, query: str) -> GovCheck:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        for r in results:
            title = (r.get("title") or "").lower()
            body = (r.get("body") or "").lower()
            if registry.lower() in title or registry.lower() in body:
                return GovCheck(registry, True, r.get("title"), "low",
                                f"Found in {registry} records")
        return GovCheck(registry, False, None, "medium",
                        f"Not found in {registry} records")
    except Exception as e:
        log.warning("Gov search failed for %s: %s", registry, e)
        return GovCheck(registry, False, None, "medium",
                        f"Could not search {registry}")


def verify_gov(company: str) -> list[GovCheck]:
    if not company:
        return []
    checks = [
        _search_gov(company, "PhilGEPS", f"{company} PhilGEPS registration Philippines"),
        _search_gov(company, "DTI", f"{company} DTI business name registration Philippines"),
    ]
    return checks


# ── Scam list search ─────────────────────────────────────────────────────

def verify_scam_lists(company: str, text: str) -> ScamListCheck:
    if not company:
        return ScamListCheck(False, 0, [], "low", "No company name to check")
    try:
        queries = [
            f"{company} scam Philippines",
            f"{company} fraud warning",
            f"{company} job scam alert",
        ]
        all_results = []
        sources = set()
        with DDGS() as ddgs:
            for q in queries:
                results = list(ddgs.text(q, max_results=3))
                for r in results:
                    title = (r.get("title") or "").lower()
                    body = (r.get("body") or "").lower()
                    if any(w in title + body for w in ["scam", "fraud", "warning", "alert", "beware"]):
                        all_results.append(r)
                        sources.add(r.get("href", "")[:50])

        if len(all_results) >= 2:
            return ScamListCheck(True, len(all_results), list(sources), "high",
                                 f"Found {len(all_results)} scam reports about {company}")
        if len(all_results) == 1:
            return ScamListCheck(True, 1, list(sources), "medium",
                                 f"Found 1 scam mention for {company}")
        return ScamListCheck(False, 0, [], "low", "No scam reports found")
    except Exception as e:
        log.warning("Scam list search failed: %s", e)
        return ScamListCheck(False, 0, [], "medium", "Could not search scam lists")


# ── Main entry point ─────────────────────────────────────────────────────

def verify_all(text: str, company: str = "") -> VerificationResult:
    """Run all external verifiers on the job posting text."""
    result = VerificationResult()
    result.phones = verify_phones(text)
    result.domains = verify_domains(text)
    result.websites = verify_websites(text)
    if company:
        result.social = verify_social(company)
        result.gov = verify_gov(company)
    result.scam_lists = [verify_scam_lists(company, text)]
    return result


def verification_to_dict(result: VerificationResult) -> dict:
    """Convert to dict for API response."""
    return {
        "phones": [
            {"number": p.number, "valid_format": p.valid_format, "carrier": p.carrier,
             "risk": p.risk, "reason": p.reason}
            for p in result.phones
        ],
        "domains": [
            {"domain": d.domain, "exists": d.exists, "age_months": d.age_months,
             "registrar": d.registrar, "risk": d.risk, "reason": d.reason}
            for d in result.domains
        ],
        "websites": [
            {"url": w.url, "alive": w.alive, "status_code": w.status_code,
             "risk": w.risk, "reason": w.reason}
            for w in result.websites
        ],
        "social": [
            {"platform": s.platform, "found": s.found, "url": s.url,
             "title": s.title, "risk": s.risk, "reason": s.reason}
            for s in result.social
        ],
        "gov": [
            {"registry": g.registry, "found": g.found, "details": g.details,
             "risk": g.risk, "reason": g.reason}
            for g in result.gov
        ],
        "scam_lists": [
            {"found": s.found, "count": s.count, "sources": s.sources,
             "risk": s.risk, "reason": s.reason}
            for s in result.scam_lists
        ],
    }

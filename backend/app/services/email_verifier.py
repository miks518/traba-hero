"""Free email verification — syntax check, MX lookup, disposable domain detection."""

import re
import logging
from dataclasses import dataclass

import dns.resolver

log = logging.getLogger("trabahero")

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Known free / disposable email providers (subset — catches most abuse)
_DISPOSABLE_DOMAINS: set[str] = {
    "tempmail.com", "throwaway.email", "guerrillamail.com", "guerrillamail.net",
    "mailinator.com", "yopmail.com", "yopmail.com", "trashmail.com",
    "trashmail.net", "tempail.com", "temp-mail.org", "fakeinbox.com",
    "sharklasers.com", "guerrillamailblock.com", "grr.la", "dispostable.com",
    "maildrop.cc", "discard.email", "discardmail.com", "mailcatch.com",
    "10minutemail.com", "getnada.com", "mohmal.com", "tmpmail.net",
    "tmpmail.org", "burnermail.io", "harakirimail.com", "tmail.io",
    "tmail.ws", "tempmailo.com", "tmpmail.net", "emailondeck.com",
    "33mail.com", "mytemp.email", "spamgourmet.com", "spam4.me",
    "bccto.me", "chacuo.net", "chinairn.com",
}


@dataclass
class EmailCheck:
    email: str
    syntax_valid: bool
    domain: str
    has_mx_records: bool
    is_disposable: bool
    risk: str  # "low" | "medium" | "high"
    reason: str


def _extract_emails(text: str) -> list[str]:
    """Pull all email-like strings from text."""
    raw = _EMAIL_RE.findall(text)
    seen: set[str] = set()
    out: list[str] = []
    for e in raw:
        low = e.lower().strip(".")
        if low not in seen:
            seen.add(low)
            out.append(e)
    return out


def _check_mx(domain: str) -> bool:
    """Return True if domain has MX records."""
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        return len(answers) > 0
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers, dns.exception.Timeout,
            Exception):
        return False


def verify_email(raw_email: str) -> EmailCheck:
    """Run syntax + MX + disposable check on a single email."""
    email = raw_email.strip().lower()
    domain = email.split("@")[-1] if "@" in email else ""

    # Syntax check
    syntax_valid = bool(_EMAIL_RE.fullmatch(email))
    if not syntax_valid or not domain:
        return EmailCheck(
            email=raw_email, syntax_valid=False, domain=domain,
            has_mx_records=False, is_disposable=False,
            risk="high", reason="Invalid email format",
        )

    # MX check
    has_mx = _check_mx(domain)

    # Disposable check
    is_disposable = domain in _DISPOSABLE_DOMAINS

    # Determine risk
    if is_disposable:
        risk, reason = "high", f"Uses disposable/free email provider ({domain})"
    elif not has_mx:
        risk, reason = "high", f"Domain has no mail servers — cannot receive emails"
    else:
        risk, reason = "low", "Domain has valid mail infrastructure"

    return EmailCheck(
        email=raw_email, syntax_valid=True, domain=domain,
        has_mx_records=has_mx, is_disposable=is_disposable,
        risk=risk, reason=reason,
    )


def verify_emails_in_text(text: str) -> list[EmailCheck]:
    """Extract all emails from text and verify each one."""
    emails = _extract_emails(text)
    return [verify_email(e) for e in emails]

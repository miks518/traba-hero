"""Fetch one page, for the agent's `fetch` tool.

The employer's own pages are the fact the verdict needs and the search snippets
cannot give: whether the employer's own site lists this role, on the terms the
posting advertises. `fetch` exists so `confirmed` can be established against
the page itself rather than a model's reading of a snippet.

Everything here is written for a hostile URL, because a search result is
untrusted input and can point anywhere:

- Only `http` and `https`. No cookies, no authentication, no JavaScript.
- The host is resolved before the request and every address is checked against
  the private, reserved, loopback, link-local, multicast and unspecified
  ranges; every redirect hop is resolved and checked again, so a hop to an
  internal address is refused, not followed.
- The body is capped at the caller's byte limit and the text says so — a
  fragment is delivered as a declared fragment, never dressed up as a page.

The fetched text is still untrusted input after all of that. Framing it as
such is the agent prompt's job, not this module's.
"""

from __future__ import annotations

import asyncio
import html
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

log = logging.getLogger("trabahero")

FETCH_TIMEOUT = 15.0
MAX_REDIRECT_HOPS = 3

_HEADERS = {
    # A plain client, no cookies and no credentials. A page that behaves
    # differently for a logged-in browser is not the public record the
    # agent is entitled to quote.
    "User-Agent": "Mozilla/5.0 (compatible; TrabaheroFetch/1.0; job-posting verification)",
}

# The statuses that mean "the content is elsewhere". 305 is deliberately
# absent: a proxy redirect is not a page the reader asked for.
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

# Appended to the text when the body was cut at the byte limit, so the model
# is told it is seeing a fragment and never reads the head of a page as the
# whole page.
TRUNCATION_MARK = (
    "\n\n[The page was cut off at the fetch limit; "
    "this is a fragment, not the whole page.]"
)


class FetchRefused(RuntimeError):
    """The URL was refused by rule, before or during retrieval.

    A refusal is a fact about the request, not a network error: the caller is
    told the fetch did not happen and why, so it can choose another page.
    """


@dataclass(frozen=True)
class FetchedPage:
    """One fetched page: the URL finally fetched, its text, and whether the
    text is a fragment."""

    url: str
    text: str
    truncated: bool


def _resolve_addresses(host: str) -> list[str]:
    """Every address `host` names, deduplicated, in resolution order.

    A literal IP needs no DNS, and skipping the resolver for one keeps the
    private-address check working where the DNS itself is the thing being
    escaped (a test environment blocks resolution outright; a host literal
    must still be checkable). A separate function because it is the module
    boundary the tests fake, and because the SSRF check is only as honest as
    this list.
    """
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return [host]
    out: list[str] = []
    for info in socket.getaddrinfo(host, None):
        address = info[4][0]
        if address not in out:
            out.append(address)
    return out


def _is_forbidden_address(raw: str) -> bool:
    """True for anything that is not a public unicast address.

    An address that cannot be parsed at all counts as forbidden: the rule is
    "fetch nothing you cannot place on the public internet", and a surprise
    literal (a zone id, a hostname that leaked into the address slot) is
    resolved in the safe direction.
    """
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return True
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        # ::ffff:127.0.0.1 is 127.0.0.1 wearing a costume.
        address = address.ipv4_mapped
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _assert_safe_host(url: str) -> str:
    """Refuse anything but http(s) on a public host. Returns the hostname."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise FetchRefused(f"only http and https are fetched, not {parts.scheme!r}")
    host = parts.hostname
    if not host:
        raise FetchRefused(f"the URL names no host: {url!r}")
    try:
        addresses = _resolve_addresses(host)
    except FetchRefused:
        raise
    except OSError as exc:
        # A host that does not resolve cannot be fetched. The test suite's
        # DNS guard raises a RuntimeError of its own, which is deliberately
        # not caught here: a fetch that escapes its fake must fail loudly.
        raise FetchRefused(f"{host!r} does not resolve: {exc}") from exc
    for address in addresses:
        if _is_forbidden_address(address):
            raise FetchRefused(
                f"{host!r} resolves to {address}, a private or reserved address"
            )
    return host


def _html_to_text(body: bytes) -> str:
    """The page's text, approximately the way a reader sees it.

    Deliberately dependency-free and conservative: script, style and comment
    blocks go first, then the tags, then the entities, then the whitespace.
    The text is untrusted input either way — framing it as such is the
    prompt's job — so a missed tag is a formatting artefact, not a wrong fact.
    """
    text = body.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1\s*>", " ", text)
    text = re.sub(r"(?s)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)<[^>]*>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


async def fetch_page(url: str, *, max_bytes: int) -> FetchedPage:
    """Fetch one page and return its text, cut to `max_bytes`.

    Redirects are followed by hand, at most `MAX_REDIRECT_HOPS` of them, so
    every hop's host is resolved and checked exactly like the first — a
    redirect to an internal address is refused, not silently obeyed. The HTTP
    call itself is sync `httpx`, run in a thread the way the search call is:
    one blocking call per fetch, and the agent is capped at four.
    """
    current = url
    for hop in range(MAX_REDIRECT_HOPS + 1):
        _assert_safe_host(current)
        response = await asyncio.to_thread(
            httpx.get,
            current,
            headers=_HEADERS,
            timeout=FETCH_TIMEOUT,
            follow_redirects=False,
        )
        if response.status_code in _REDIRECT_STATUSES:
            location = (response.headers.get("location") or "").strip()
            if not location:
                raise FetchRefused(f"a redirect from {current!r} names no destination")
            if hop == MAX_REDIRECT_HOPS:
                raise FetchRefused(f"more than {MAX_REDIRECT_HOPS} redirects from {url!r}")
            # A relative location resolves against the URL that redirected;
            # the next hop is checked from the top of the loop like any other.
            current = urljoin(current, location)
            continue
        response.raise_for_status()
        content = response.content or b""
        truncated = len(content) > max_bytes
        if truncated:
            content = content[:max_bytes]
        text = _html_to_text(content)
        if truncated:
            text = text.rstrip() + TRUNCATION_MARK
        log.info(
            "[fetch] %s: %d bytes%s",
            response.url or current,
            len(response.content or b""),
            " (truncated)" if truncated else "",
        )
        return FetchedPage(
            url=str(response.url) if response.url else current,
            text=text,
            truncated=truncated,
        )
    raise FetchRefused(f"more than {MAX_REDIRECT_HOPS} redirects from {url!r}")

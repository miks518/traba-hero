"""The fetch tool refuses to touch anything private, and truncates honestly.

Task 14 of the verdict-procedure plan. The suite is offline (conftest's DNS
guard refuses every non-loopback name), so the one test that needs a successful
fetch fakes the two boundaries this module owns — the resolver and the HTTP GET
— exactly as the offline suite fakes Tavily at `app.services.search.httpx.post`.
The refusal tests need no fake: a literal IP never reaches the DNS.
"""

import httpx
import pytest

from app.services import fetch
from app.services.fetch import FetchRefused, fetch_page


def _fake_resolver(host, *args, **kwargs):
    """Stand in for DNS: every name resolves to one genuinely public address.

    Returns the shape the real `_resolve_addresses` returns — a list of
    address strings, not getaddrinfo tuples. TEST-NET (203.0.113.0/24) will
    not do — `ipaddress` counts it private, and the guard would refuse the
    fixture's own stand-in.
    """
    return ["93.184.216.34"]


@pytest.mark.asyncio
async def test_a_private_address_is_refused():
    with pytest.raises(FetchRefused):
        await fetch_page("http://127.0.0.1/admin", max_bytes=1000)


@pytest.mark.asyncio
async def test_a_file_scheme_is_refused():
    with pytest.raises(FetchRefused):
        await fetch_page("file:///etc/passwd", max_bytes=1000)


@pytest.mark.asyncio
async def test_a_link_local_address_is_refused():
    """169.254.169.254 is where a cloud instance keeps its credentials."""
    with pytest.raises(FetchRefused):
        await fetch_page("http://169.254.169.254/latest/meta-data/", max_bytes=1000)


@pytest.mark.asyncio
async def test_a_page_over_the_cap_is_truncated(monkeypatch):
    body = (
        b"<html><body><p>Hiring now: warehouse staff in Cebu.</p>"
        + b"<p>filler paragraph </p>" * 50
        + b"</body></html>"
    )
    response = httpx.Response(
        200,
        content=body,
        request=httpx.Request("GET", "https://docs.example.com/careers"),
    )
    monkeypatch.setattr(fetch, "_resolve_addresses", _fake_resolver)
    monkeypatch.setattr(fetch.httpx, "get", lambda *args, **kwargs: response)
    page = await fetch_page("https://docs.example.com/careers", max_bytes=50)
    assert page.truncated is True
    # The cap is honest because the model is told it is seeing a fragment,
    # never left to read the head of a page as the whole page.
    assert "fragment" in page.text
    assert "Hiring now" in page.text


@pytest.mark.asyncio
async def test_a_redirect_to_a_private_address_is_refused(monkeypatch):
    """Each hop is re-checked; the redirect destination is untrusted input."""
    response = httpx.Response(
        302,
        headers={"location": "http://127.0.0.1/admin"},
        request=httpx.Request("GET", "http://93.184.216.34/"),
    )
    monkeypatch.setattr(fetch.httpx, "get", lambda *args, **kwargs: response)
    with pytest.raises(FetchRefused):
        await fetch_page("http://93.184.216.34/", max_bytes=1000)

"""The rate-limit identity is the socket peer unless the peer is a named proxy.

The five tests this file replaces asserted that X-Forwarded-For wins from any
peer. That was the vulnerability: the key function read a caller-supplied header
before it looked at the connection, so rotating the header gave every request a
fresh rate-limit budget. `docs/security-audit-2026-10-14.md` records the finding.
"""
import pytest
from unittest.mock import MagicMock

from app.config import Settings
from app.rate_limit import (
    _get_client_ip,
    _in_trusted_networks,
    _parse_trusted_proxies,
)


def _make_request(headers: dict = None, client_host: str = "198.18.0.7"):
    """A mock Starlette Request. The default peer is outside every trusted set
    used here, so a test that forgets to set up trust still exercises the
    untrusted path rather than silently passing."""
    request = MagicMock()
    # Starlette headers are case-insensitive; use lowercase to match code
    request.headers = {k.lower(): v for k, v in (headers or {}).items()}
    request.client.host = client_host
    return request


@pytest.fixture
def trusts_nothing(monkeypatch):
    monkeypatch.setattr(
        Settings, "_trusted_networks", property(lambda s: []), raising=False
    )


@pytest.fixture
def trusts_proxy(monkeypatch):
    monkeypatch.setattr(
        Settings,
        "_trusted_networks",
        property(lambda s: _parse_trusted_proxies("10.0.0.0/8")),
        raising=False,
    )


@pytest.fixture
def trusts_localhost(monkeypatch):
    monkeypatch.setattr(
        Settings,
        "_trusted_networks",
        property(lambda s: _parse_trusted_proxies("127.0.0.1")),
        raising=False,
    )


# --- untrusted peer: the header is not evidence -----------------------------


def test_no_headers_uses_the_socket_peer(trusts_nothing):
    assert _get_client_ip(_make_request(client_host="203.0.113.9")) == "203.0.113.9"


def test_forwarded_header_is_ignored_from_an_untrusted_peer(trusts_nothing):
    request = _make_request(headers={"X-Forwarded-For": "1.2.3.4"})
    assert _get_client_ip(request) == "198.18.0.7"


def test_real_ip_is_also_ignored_from_an_untrusted_peer(trusts_nothing):
    request = _make_request(headers={"X-Real-IP": "1.2.3.4"})
    assert _get_client_ip(request) == "198.18.0.7"


# --- trusted peer: the header is evidence -----------------------------------


def test_a_trusted_peer_gets_the_forwarded_for_header(trusts_proxy):
    request = _make_request(
        headers={"X-Forwarded-For": "203.0.113.50"}, client_host="10.1.2.3"
    )
    assert _get_client_ip(request) == "203.0.113.50"


def test_a_trusted_peer_gets_the_x_real_ip_header(trusts_proxy):
    request = _make_request(headers={"X-Real-IP": "203.0.113.50"}, client_host="10.1.2.3")
    assert _get_client_ip(request) == "203.0.113.50"


def test_forwarded_for_wins_over_x_real_ip_for_a_trusted_peer(trusts_proxy):
    """This ordering predates the trust gate and CRITICAL.md records it as
    deliberate, so the gate must not change which header is preferred."""
    request = _make_request(
        headers={"X-Forwarded-For": "203.0.113.50", "X-Real-IP": "198.51.100.22"},
        client_host="10.1.2.3",
    )
    assert _get_client_ip(request) == "203.0.113.50"


def test_the_rightmost_untrusted_hop_is_chosen(trusts_proxy):
    """The leftmost element is whatever the caller sent; the rightmost is what
    the trusted proxy observed. Taking the leftmost would re-create the original
    bypass for any edge that appends to X-Forwarded-For rather than overwriting
    it, which is the common default."""
    request = _make_request(
        headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.50"}, client_host="10.1.2.3"
    )
    assert _get_client_ip(request) == "203.0.113.50"


def test_a_present_but_empty_header_falls_through_to_the_peer(trusts_proxy):
    request = _make_request(headers={"X-Forwarded-For": ""}, client_host="10.1.2.3")
    assert _get_client_ip(request) == "10.1.2.3"


def test_an_ipv4_mapped_ipv6_peer_matches_its_ipv4_trusted_entry(trusts_localhost):
    """uvicorn reports an IPv4 peer as ::ffff:127.0.0.1. Comparing that string
    against a trusted 127.0.0.1 finds nothing, so localhost would be treated as
    untrusted and the header silently dropped in development."""
    request = _make_request(
        headers={"X-Forwarded-For": "203.0.113.50"}, client_host="::ffff:127.0.0.1"
    )
    assert _get_client_ip(request) == "203.0.113.50"


# --- the containment helper on its own --------------------------------------


def test_ipv4_mapped_ipv6_is_unwrapped_before_the_containment_check():
    """CPython does not map ::ffff:127.0.0.1 into an IPv4Network — measured, it
    returns False. The first assertion pins that stdlib behaviour so the reason
    `_in_trusted_networks` exists cannot be mistaken for belt-and-braces."""
    from ipaddress import IPv6Address

    networks = _parse_trusted_proxies("127.0.0.1")
    assert IPv6Address("::ffff:127.0.0.1") not in networks[0]
    assert _in_trusted_networks("::ffff:127.0.0.1", networks)


def test_a_plain_ipv4_peer_matches_directly():
    assert _in_trusted_networks("10.1.2.3", _parse_trusted_proxies("10.0.0.0/8"))


def test_a_genuine_ipv6_peer_is_not_unwrapped_into_ipv4():
    """2001:db8::1 has no ipv4_mapped, so it must be compared as v6 or a v6
    trusted range would silently stop matching."""
    networks = _parse_trusted_proxies("2001:db8::/32")
    assert _in_trusted_networks("2001:db8::5", networks)
    assert not _in_trusted_networks("::ffff:10.1.2.3", networks)


def test_an_unparseable_peer_matches_nothing_rather_than_raising():
    assert not _in_trusted_networks("not-an-ip", _parse_trusted_proxies("10.0.0.0/8"))


def test_no_networks_means_nothing_is_trusted():
    assert not _in_trusted_networks("10.1.2.3", [])

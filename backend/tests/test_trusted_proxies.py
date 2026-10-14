"""Parsing of the TRUSTED_PROXIES operator setting."""
import pytest
from ipaddress import IPv4Address

from app.rate_limit import _parse_trusted_proxies


def test_empty_yields_no_networks():
    assert _parse_trusted_proxies("") == []
    assert _parse_trusted_proxies("   ") == []
    assert _parse_trusted_proxies(None) == []


def test_bare_ip_becomes_a_single_host_network():
    (network,) = _parse_trusted_proxies("203.0.113.7")
    assert network.prefixlen == 32
    assert network.network_address == IPv4Address("203.0.113.7")


def test_cidr_is_preserved():
    (network,) = _parse_trusted_proxies("10.0.0.0/8")
    assert network.prefixlen == 8


def test_comma_and_whitespace_separated_entries_all_parse():
    networks = _parse_trusted_proxies("203.0.113.7, 10.0.0.0/8\t192.0.2.0/24")
    assert [n.prefixlen for n in networks] == [32, 8, 24]


def test_ipv6_is_accepted():
    networks = _parse_trusted_proxies("::1, 2001:db8::/32")
    assert len(networks) == 2
    assert networks[0].version == 6


@pytest.mark.parametrize("bad", ["", " ", "not-an-ip", "999.1.1.1", "10.0.0.0/33", ",,"])
def test_unusable_entries_are_dropped_not_raised(bad):
    # A typo must not raise; the operator's other entries must still load.
    assert _parse_trusted_proxies(bad) == []


def test_one_bad_entry_does_not_discard_the_good_ones():
    networks = _parse_trusted_proxies("203.0.113.7, oops, 10.0.0.0/8")
    assert len(networks) == 2

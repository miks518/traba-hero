import re
from ipaddress import IPv4Network, IPv6Address, IPv6Network, ip_address, ip_network

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import settings


def _parse_trusted_proxies(value: str | None) -> list[IPv4Network | IPv6Network]:
    """Turn the TRUSTED_PROXIES setting into ipaddress networks.

    Entries are separated by commas or whitespace and may be bare IPs or CIDR
    blocks. Anything unparseable is dropped rather than raised: a typo in a
    security setting must not become an outage.
    """
    networks: list[IPv4Network | IPv6Network] = []
    for entry in re.split(r"[,\s]+", value or ""):
        try:
            networks.append(ip_network(entry, strict=False))
        except ValueError:
            continue
    return networks


def _in_trusted_networks(addr: str, networks: list) -> bool:
    """Whether `addr` falls inside any of the parsed trusted-proxy networks.

    An IPv4-mapped IPv6 address is unwrapped first. CPython does not do this for
    us: `IPv6Address("::ffff:127.0.0.1") in ip_network("127.0.0.1")` is False,
    which is why uvicorn's usual `::ffff:127.0.0.1` peer would otherwise never
    match a trusted `127.0.0.1` and localhost would be treated as untrusted.

    An address that does not parse matches nothing rather than raising: a
    malformed peer is not evidence that the caller is a trusted proxy.
    """
    try:
        parsed = ip_address(addr)
    except ValueError:
        return False
    if isinstance(parsed, IPv6Address) and parsed.ipv4_mapped is not None:
        parsed = parsed.ipv4_mapped
    return any(parsed in network for network in networks)


def _get_client_ip(request: Request) -> str:
    """Return the rate-limit identity for `request`.

    A forwarded header is attacker-controlled input, so it is only read when the
    socket peer is an operator-named proxy. Otherwise the identity is
    ``request.client.host``.

    uvicorn's own ``ProxyHeadersMiddleware`` cannot decide this for us: it mutates
    only ``scope["client"]`` and never ``scope["headers"]``, and Starlette builds
    ``Request.headers`` from the latter, so the two never interact.

    ``X-Forwarded-For`` is read rightmost-first. The leftmost element is whatever
    the caller sent; the rightmost is what the trusted proxy observed. An edge
    that appends rather than overwrites — the common default — leaves the
    leftmost under caller control, so choosing it would re-create the bypass this
    gate exists to close.
    """
    peer = request.client.host if request.client is not None else None
    if not peer:
        return get_remote_address(request)

    if not _in_trusted_networks(peer, settings._trusted_networks):
        return peer

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
        if hops:
            for hop in reversed(hops):
                if not _in_trusted_networks(hop, settings._trusted_networks):
                    return hop
            return hops[-1]

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    return peer


limiter = Limiter(key_func=_get_client_ip)

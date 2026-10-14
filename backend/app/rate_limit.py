import re
from ipaddress import IPv4Network, IPv6Network, ip_network

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


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


def _get_client_ip(request: Request) -> str:
    """Return the real client IP, checking proxy headers first.

    When deployed behind Nginx/Cloudflare, ``request.client.host`` returns the
    proxy IP.  This function checks ``X-Forwarded-For`` and ``X-Real-IP``
    headers before falling back to the direct connection IP.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    return get_remote_address(request)


limiter = Limiter(key_func=_get_client_ip)

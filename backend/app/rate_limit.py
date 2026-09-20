from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


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

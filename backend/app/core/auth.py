import logging
from fastapi import Header, HTTPException
from app.config import settings

log = logging.getLogger("trabahero.auth")

EXPECTED_KEY = settings.client_secret_key.strip() if settings.client_secret_key else ""


async def require_client_key(
    x_trabahero_client_key: str = Header(default=""),
) -> None:
    """FastAPI dependency that validates the extension's shared secret key.

    The browser extension sends the ``X-Trabahero-Client-Key`` header on every
    API request.  This dependency compares it against the ``CLIENT_SECRET_KEY``
    environment variable.

    If ``CLIENT_SECRET_KEY`` is empty or unset, authentication is **disabled**
    (development mode) so that local development without configuring a shared
    secret still works out of the box.  In production, always set
    ``CLIENT_SECRET_KEY`` in ``backend/.env``.
    """
    if not EXPECTED_KEY:
        return

    if not x_trabahero_client_key:
        log.warning("Rejected request: missing X-Trabahero-Client-Key header")
        raise HTTPException(status_code=401, detail="Unauthorized: missing client key")

    if x_trabahero_client_key != EXPECTED_KEY:
        log.warning("Rejected request: invalid client key")
        raise HTTPException(status_code=401, detail="Unauthorized: invalid client key")

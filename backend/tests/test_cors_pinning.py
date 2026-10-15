"""CORS is pinned to the extension's origin, and blank means no CORS at all.

`main.py` was `allow_origins=["*"]` with `allow_credentials=True`, which reflects
any request's `Origin` back with credentials permitted. That is not a theoretical
gap: it means any page a user visits can call this backend through their browser,
at the user's own network position and with the user's own IP, and the shared
provider keys pay for it.

The default here is the opposite of the old one. Blank `CORS_ALLOWED_ORIGINS`
installs **no CORS middleware at all**, so a browser blocks the response â€” a
fails-closed direction that is broken until configured rather than open until
configured. It is also deliberately *not* the `CLIENT_SECRET_KEY` shape this
project used to have, where unset meant "disabled and silent"; a removed scheme
should not leave its behaviour behind as the default of its replacement.

`allow_credentials=True` is dropped. The extension sets no `credentials` and no
`mode`, so `fetch` defaults apply and no cookie is ever sent cross-origin. The
flag therefore bought nothing and, combined with a wildcard origin, was the shape
that makes a credentialed-read hole.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import install_cors

EXTENSION = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"


def _app_with(value: str) -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    install_cors(app, configured=value)
    return app


def _probe(app: FastAPI, origin: str):
    async def call():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/ping", headers={"Origin": origin})
            return r.headers.get("access-control-allow-origin"), \
                   r.headers.get("access-control-allow-credentials")

    return pytest.mark.asyncio(call)


@pytest.mark.asyncio
async def test_the_listed_origin_is_allowed(monkeypatch):
    app = _app_with(EXTENSION)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/ping", headers={"Origin": EXTENSION})
    assert r.headers.get("access-control-allow-origin") == EXTENSION


@pytest.mark.asyncio
async def test_any_other_origin_is_refused(monkeypatch):
    """The point of the change. A hostile page gets no readable response."""
    app = _app_with(EXTENSION)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/ping", headers={"Origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
async def test_blank_installs_no_cors_at_all(monkeypatch):
    """Fail-closed: no middleware means a browser blocks the response. Installed
    but empty would also block, so what is pinned here is that the operator is
    told, not that the browser is stopped â€” see the startup log test."""
    app = _app_with("")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/ping", headers={"Origin": EXTENSION})
    assert r.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
async def test_credentials_are_not_permitted(monkeypatch):
    """The extension sends no cookie, so the flag bought nothing and combined
    with a wildcard it is the shape of a credentialed-read hole."""
    app = _app_with(EXTENSION)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/ping", headers={"Origin": EXTENSION})
    assert r.headers.get("access-control-allow-credentials") != "true"


def test_a_wildcard_setting_is_refused_outright():
    """`CORS_ALLOWED_ORIGINS=*` would reinstate the exact hole being closed, and
    it is the value someone reaches for when the error is "requests are being
    blocked". Refusing it loudly beats honouring it."""
    app = FastAPI()
    install_cors(app, configured="*")
    assert not any(
        m.cls.__name__ == "CORSMiddleware" for m in app.user_middleware
    ), "a wildcard origin was installed, reopening the hole"


def test_the_setting_is_documented_in_the_env_example():
    """`test_env_example.py` parses the shipped file and asserts every field
    appears; this names the key the operator has to find."""
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / ".env.example"
    assert "CORS_ALLOWED_ORIGINS" in example.read_text(encoding="utf-8")


def test_blank_says_so_out_loud(caplog):
    """Blank is fail-closed and therefore *breaks the extension*, so it has to be
    visible at startup. A silent refusal would present as "the panel cannot reach
    the backend" with nothing to act on.

    `configured=""` rather than relying on the setting, because this suite runs
    against the developer's real `backend/.env` — and a test that reads it fails
    for whoever has a value set, which is the mistake AGENTS.md warns about for
    every other default assertion.
    """
    import logging

    with caplog.at_level(logging.WARNING, logger="trabahero"):
        install_cors(FastAPI(), configured="")
    assert "CORS_ALLOWED_ORIGINS" in caplog.text


@pytest.mark.asyncio
async def test_a_bare_extension_id_is_given_its_scheme():
    """A bare ID is the obvious thing to type and silently matches nothing: a
    browser sends `chrome-extension://<id>`, never `<id>`. An entry left bare is
    dead weight, and the panel fails to connect with no clue why."""
    app = _app_with(EXTENSION.split("://")[1])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/ping", headers={"Origin": EXTENSION})
    assert r.headers.get("access-control-allow-origin") == EXTENSION

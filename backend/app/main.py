import json
import logging
import re
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.routers import health, scan
from app.exceptions import AppError, app_error_handler
from app.rate_limit import limiter
from app.config import settings

# Split by severity, because Railway colours by the stream a line arrived on
# before it reads anything in the text. Its normalisation (docs.railway.app,
# Guides > Logs) sends stderr to level.error and stdout to level.info, and the
# in-line level is only honoured in forms its parser recognises — uvicorn's own
# `INFO: ...` prefix matches, but our `... [INFO] trabahero: ...` after a
# timestamp does not. With basicConfig's default (one StreamHandler, whose
# documented fallback stream is stderr) every app log went to stderr and was
# coloured red, so an ordinary scan looked identical to a real failure in the
# dashboard. INFO and below now leave by stdout and arrive blue; WARNING and
# above leave by stderr and arrive red — which is the colour a warning deserves.
_stdout = logging.StreamHandler(sys.stdout)
_stdout.addFilter(lambda r: r.levelno < logging.WARNING)
_stderr = logging.StreamHandler(sys.stderr)
_stderr.setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", handlers=[_stdout, _stderr])
log = logging.getLogger("trabahero")

app = FastAPI(title="Trabahero Backend")

# The largest body the field caps in `schemas.py` permit is
# `MAX_IMAGES_PER_SCAN * MAX_IMAGE_BASE64` — four images of 5,000,000 base64
# characters, about 20 MB. This sits above that with headroom for JSON framing,
# and must move with it: `test_body_ceiling.py` asserts the relationship rather
# than either number, so raising an image cap without raising this fails a test
# instead of refusing legitimate scans in production.
MAX_REQUEST_BYTES = 25 * 1024 * 1024


def _too_large_detail(max_bytes: int) -> str:
    """The one sentence both refusal paths send.

    Two paths exist because a Content-Length check alone is a check the caller can
    decline to make. They must not be able to disagree about what the limit is,
    or the message becomes a second, undocumented limit.
    """
    return (
        "Request body is too large. This endpoint accepts at most "
        f"{max_bytes // (1024 * 1024)} MB."
    )


class _BodyTooLarge(HTTPException):
    """Raised out of `receive` when the running byte count passes the ceiling.

    An `HTTPException` and not a bare `Exception`, which is load-bearing rather
    than stylistic.

    FastAPI reads the request body inside a `try` whose clauses end
    `except HTTPException: raise` and then `except Exception: raise
    HTTPException(400, "There was an error parsing the body")`. A plain
    exception is therefore caught by the second clause and reported to the caller
    as a malformed body. The ceiling still does its job — buffering stops at the
    limit, which is the whole memory bound — and then describes itself wrongly,
    so an oversized chunked upload is reported as a syntax error in something
    the caller never got to finish sending.

    Subclassing `HTTPException` passes through the re-raise clause untouched,
    and the middleware's own handler below still catches it, so the caller gets
    the 413 and the real reason. It has to be *FastAPI's* HTTPException and not
    Starlette's: that clause catches FastAPI's class, and FastAPI's is the
    subclass, so a Starlette base instance would miss it and be flattened anyway.

    `test_a_chunked_oversized_body_reports_the_ceiling_not_a_parse_error` is the
    test that found this. The middleware's own tests drive a stub downstream app,
    so they exercise the counting but never meet the body handler that swallows
    the exception — they passed against code that answered 400 in production.
    """

    def __init__(self, max_bytes: int):
        super().__init__(status_code=413, detail=_too_large_detail(max_bytes))


class LimitRequestBody:
    """Refuse an oversized request body before the framework buffers it.

    Pydantic caps the fields, but it runs after FastAPI has read and JSON-decoded
    the whole body, so a cap on a field is not a cap on memory. That matters here
    because the per-IP limits are charged after parsing too — `@limiter.limit`
    decorates the endpoint function, and FastAPI resolves the body parameter
    while solving dependencies — so an oversized body is allocated and parsed
    before the limiter even sees the request.

    Two paths, because a Content-Length check on its own is one the caller can
    decline to make: a declared length is refused before a byte is read, and an
    undeclared one is caught while the chunks arrive. Anything that can send a
    large body can do it either way.
    """

    def __init__(self, app, max_bytes: int = MAX_REQUEST_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def _refuse(self, send) -> None:
        body = json.dumps({"detail": _too_large_detail(self.max_bytes)}).encode()
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for key, value in scope.get("headers", ()):
            if key == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        await self._refuse(send)
                        return
                except ValueError:
                    pass
                break

        received = 0
        started = False

        async def counting_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge(self.max_bytes)
            return message

        async def tracking_send(message):
            nonlocal started
            if message.get("type") == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLarge:
            # Nothing can have answered yet: an endpoint cannot respond without
            # the body it was waiting for. If that is ever untrue, the response
            # is already on the wire and the connection is the honest outcome.
            if started:
                raise
            await self._refuse(send)


class DropHealthAccessLogs(logging.Filter):
    """Silences uvicorn access records for GET /health.

    The extension polls /health every few seconds to detect reachability, which
    would otherwise bury real requests in the log. Any other path is untouched.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple):
            for arg in args:
                if isinstance(arg, str) and arg.split("?", 1)[0] == "/health":
                    return False
        return True


logging.getLogger("uvicorn.access").addFilter(DropHealthAccessLogs())

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

def install_cors(app: FastAPI, configured: str | None = None) -> None:
    """Install CORS for the origins the operator named, or for none at all.

    `configured` defaults to the setting and exists so the tests do not have to
    monkeypatch a pydantic model: patching a *class* attribute does not reach an
    existing *instance*, whose value lives in its own `__dict__`, so the patch
    would appear to work and the setting would not move.

    This replaces `allow_origins=["*"]` with `allow_credentials=True`, which
    reflected any request's `Origin` back with credentials permitted. That is not
    a theoretical gap: it let any page a user visited call this backend through
    their own browser, at their own network position, on the operator's keys.

    `allow_credentials` is now False. The extension sets neither `credentials`
    nor `mode`, so `fetch` defaults apply and no cookie is ever sent
    cross-origin — the flag bought nothing, and paired with a wildcard origin it
    is the shape of a credentialed-read hole.

    Blank installs nothing, so a browser blocks the read. That breaks the
    extension until it is configured, which is the point: the old default was
    open-to-everyone, and the failure direction here is "the panel cannot reach
    the backend", which is visible and fixable. A wildcard is refused rather than
    honoured, because it is both the value someone reaches for when requests
    appear blocked and the hole being closed.
    """
    raw = settings.cors_allowed_origins if configured is None else configured
    origins = [o for o in re.split(r"[,\s]+", (raw or "").strip()) if o]

    # Checked before the scheme is filled in below, so a bare `*` is still seen
    # for what it is.
    if "*" in origins:
        log.error(
            "[cors] CORS_ALLOWED_ORIGINS contains '*', which would restore the "
            "hole this setting exists to close. No CORS middleware installed. "
            "List the extension origin instead, e.g. "
            "chrome-extension://<extension-id>."
        )
        return

    # A bare ID is the obvious thing to type and silently matches nothing: a
    # browser sends `chrome-extension://<id>`, never `<id>`, so the entry is dead
    # weight and the panel fails to connect with no clue why. Normalise it, and
    # say so, rather than leaving a setting that looks configured and is not.
    normalised = [o if "://" in o else f"chrome-extension://{o}" for o in origins]
    if normalised != origins:
        log.warning(
            "[cors] CORS_ALLOWED_ORIGINS entries without a scheme were read as "
            "extension ids and given the chrome-extension:// scheme: %s",
            ", ".join(normalised),
        )
    origins = normalised

    if "*" in origins:
        log.error(
            "[cors] CORS_ALLOWED_ORIGINS contains '*', which would restore the "
            "hole this setting exists to close. No CORS middleware installed. "
            "List the extension origin instead, e.g. "
            "chrome-extension://<extension-id>."
        )
        return

    if not origins:
        log.warning(
            "[cors] CORS_ALLOWED_ORIGINS is empty — no CORS middleware is "
            "installed, so a browser will block every cross-origin read and the "
            "extension cannot reach this backend. Set it to the extension's "
            "origin, e.g. chrome-extension://<extension-id>."
        )
        return

    log.info("[cors] Allowing cross-origin reads from: %s", ", ".join(origins))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


install_cors(app)

app.add_exception_handler(AppError, app_error_handler)

# Added last so it runs first: Starlette applies middleware in reverse order of
# registration, so this wraps everything below it and sees the body before the
# router does.
app.add_middleware(LimitRequestBody, max_bytes=MAX_REQUEST_BYTES)

app.include_router(health.router)
app.include_router(scan.router)


def _warn_if_no_trusted_proxies() -> None:
    """Say out loud when the rate-limit identity is the socket peer for everyone.

    Blank TRUSTED_PROXIES is the fail-closed default, and it is correct: a caller
    must not be able to name itself. But behind a proxy it also means every
    caller shares one bucket, and the only symptom is an unexplained 429 for
    users who did nothing wrong. Once, at startup, naming the setting.
    """
    if settings.trusted_proxies.strip():
        return
    log.warning(
        "TRUSTED_PROXIES is empty — forwarded headers are ignored and every "
        "caller shares one rate-limit bucket. If this service is behind a proxy, "
        "set TRUSTED_PROXIES to the proxy's IP ranges or the per-caller limits "
        "will not apply."
    )


_warn_if_no_trusted_proxies()


def run(reload: bool = False) -> None:
    """Serve the API on the host and port from `backend/.env`.

    Exists because `uvicorn app.main:app` does **not** read them. Uvicorn takes
    its own port from the command line and defaults to 8000, so a `PORT` in the
    env file that nothing reads leaves the server on 8000 while the file says
    otherwise — and the only symptom is a port mismatch nobody can explain.
    That is why HOST and PORT were previously decorative.

    Use this, not bare uvicorn, unless you pass `--port` yourself:

        python -m app.main                    # honours HOST and PORT
        uvicorn app.main:app --reload --port 8010   # same thing, explicit

    `reload` is a development convenience. It is a parameter rather than a
    setting so a deployment cannot pick it up from the environment by accident.

    The app is passed as an import string, not as the object, because uvicorn
    refuses to reload anything else: `python -m app.main` exited immediately with
    "You must pass the application as an import string to enable 'reload' or
    'workers'", which made the command documented in AGENTS.md a command that
    does not run. Passing the object still works with reload off, but the string
    works in both modes and re-imports the module in the reloader subprocess,
    which is what reload means anyway.
    """
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=reload)


if __name__ == "__main__":
    run(reload=True)

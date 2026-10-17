# Decision record — security boundaries

No authentication exists. This records what replaced it and what the replacement does
and does not bound.

---

## `backend/app/core/auth.py` — removed

A shared client key shipped inside the extension bundle and was readable from
`chrome://extensions` → service worker → inspect, so it protected nothing while the docs
described it as a security boundary.

**Any credential an extension holds is extractable**, which is why a token would not
have helped either.

The loss is bounded instead:

- per-endpoint rate limits weighted by cost (`test_rate_limit_policy.py`)
- hard input caps on every body (`test_input_limits.py`, `test_match_limits.py`,
  `test_verify_limits.py`)
- a spending ceiling at the provider

**None of it authenticates a caller.**

---

## Rate-limit identity is the socket peer

`backend/app/rate_limit.py`. **The identity is the socket peer, and a forwarded header
is only read when that peer is a proxy the operator named.**

`_get_client_ip` used to return `x-forwarded-for.split(",")[0]` unconditionally, and
slowapi uses that function as the key for all seven routes, so a caller rotating the
header got a fresh budget every request — the bypass `docs/security-audit-2026-10-14.md`
finding 1 records.

It is now gated on `settings.trusted_proxies`: **empty trusts nobody**, so the identity
is always `request.client.host`.

### Two things a future reader will try and must not "fix"

1. **`uvicorn`'s `ProxyHeadersMiddleware` cannot decide this.** It mutates only
   `scope["client"]`, never `scope["headers"]`, and Starlette builds `Request.headers`
   from the latter, so the two never interact.
2. **`X-Forwarded-For` is read rightmost-untrusted, not leftmost.** The leftmost is
   whatever the caller sent, and an edge that appends rather than overwrites (the common
   default) leaves it under caller control.

Also: an IPv4-mapped peer like `::ffff:127.0.0.1` is unwrapped via `.ipv4_mapped`
before the containment check, because CPython does not do it and a naive comparison
would treat localhost as untrusted.

`main.py` logs one warning at startup while `TRUSTED_PROXIES` is blank, because the
fail-closed default collapses every caller into one shared bucket behind a proxy.

Two things still gate the bound rather than being part of it: `TRUSTED_PROXIES` must be
set in the deployed environment, and the provider's ceiling caps total outlay without
capping the rate it is spent at.

Sources: `docs/security-audit-2026-10-14.md`,
`docs/superpowers/plans/2026-10-14-trusted-proxy-rate-limit.md`.

---

## CORS is pinned to the extension origin, and blank means NO CORS middleware at all

`main.py` was `allow_origins=["*"]` with `allow_credentials=True`, which reflected any
request's `Origin` back with credentials permitted — so any page a user visited could
call this backend through their browser, on the operator's keys. A live probe of the
deployment confirmed the reflection (`allow-origin: https://evil.example`,
`allow-credentials: true`).

`install_cors()` now reads `CORS_ALLOWED_ORIGINS` (comma/space separated), and
`allow_credentials` is **False** — the extension sets neither `credentials` nor `mode`,
so `fetch` defaults apply and no cookie is ever sent, which means the flag bought
nothing and paired with a wildcard it is the shape of a credentialed-read hole.

**Blank installs nothing, so the browser blocks the read and the extension cannot reach
the backend.** That is deliberate and it is a breaking change: the old default was open
to every site, and the new failure direction is "the panel cannot connect", which is
visible.

It is deliberately **not** the `CLIENT_SECRET_KEY` shape, where unset meant *disabled and
silent* — **a removed scheme should not leave its behaviour behind as the default of its
replacement.**

`*` is **refused, not honoured**, because it is both the value someone reaches for when
requests look blocked and the exact hole being closed.

`install_cors(app, configured=None)` takes the value as a parameter so tests do not
monkeypatch a pydantic model: patching a *class* attribute does not reach an existing
*instance*, whose value lives in its own `__dict__`, so the patch would appear to work
and the setting would not move.

---

## A model-returned citation is bound to the retrieved set in code

**A `red` without a citation is not a `red`.**

`VERIFY_PROMPT.md` asks for a `source_url` "copied exactly from the results" and calls a
constructed one a fabricated citation, and that sentence was the *whole* of the
enforcement on both the structured path and the labeled-text fallback.
`test_verify.py:test_source_url_must_come_from_the_results` asserts only that a phrase is
present in the prompt string — it never supplies a result set, so it would pass if every
URL were discarded.

**`_bind_to_retrieved` is now the control:** a URL whose `_canonical_url` is not in the
retrieved set is dropped along with its `source_title`, and an item left with no citation
is demoted `red`→`yellow`.

**The demotion needed no `risk_calculator` change, and that is the point** — `yellow` is
already zero-weight and already means "we could not confirm this", so the fix enforces
semantics the calculator already had. `risk_calculator` never read `source_url`; a `red`
citing nothing used to score the full 25.

`allowed_urls` defaults to empty so nothing reaches the wire unbound, which also gets
the common case free: a failed or empty search yields an empty set, and then nothing is
refuted by anything.

`test_citation_binding.py` covers both paths; mutating the filter, the demotion, or the
permitted set each fails it.

---

## `LimitRequestBody` is the only bound on inbound memory, and the field caps are not

`backend/app/main.py`. Pydantic runs *after* FastAPI has read and JSON-decoded the whole
body, so a field cap is not a memory cap — and `@limiter.limit` decorates the endpoint
function, so the rate limit is charged *after* the body is already resident.

The ceiling is `MAX_REQUEST_BYTES = 25 MB`, above the
`MAX_IMAGES_PER_SCAN * MAX_IMAGE_BASE64` (~20 MB) a schema-valid `/api/scan` can reach.

`test_body_ceiling.py` asserts that as a **relationship** rather than either number, so
raising an image cap without raising the ceiling fails a test instead of refusing real
scans in production.

It has **two** paths because a `Content-Length` check alone is a check the caller can
decline to make: a declared length is refused before a byte is read, and an undeclared one
is caught while chunks arrive.

Registered **last** because Starlette applies middleware in reverse order, so the last
registered wraps everything below it.

`test_requirements_declared.py` guards the same shape at the manifest level —
`pytest-asyncio` was installed in the venv but absent from `requirements.txt`, so 85 async
tests passed by accident and a clean install would have collected them without ever
awaiting them.

# Live probe of the deployed backend

**Date:** 2026-10-15
**Target:** `trabahero-production.up.railway.app` (edge reports `railway-hikari`)
**Authorised by:** the operator, owner of the target
**Scope:** one host, endpoints already known, no load, no volumetric traffic
**Provider budget:** 5 calls authorised; **3 used** (1 scan + 2 verify, confirmed
by the operator against the Railway logs)

This is a penetration test of the operator's own service, not an audit of a
third party. It is written up separately from `security-audit-2026-10-14.md`
because that document is a source-code audit and cannot claim runtime
observations.

## Design: free by construction

The probes were split so that everything testable without a provider call could
be answered without one. A `429`, `413`, `404` or `400` costs no credits, so the
rate-limit identity, the body ceiling, the CORS posture and the information
surface were all answerable for free. The budget is enforced in code — every paid
probe goes through a counter that refuses to go below zero — not by intention.

The rate-limit probe uses `GET /health` deliberately: it is a GET, it calls no
provider, and its 30/minute limit is low enough to actually exhaust. Exhausing a
route that costs nothing is how you test a limiter without spending.

## Confirmed fixed: the rate-limit identity

| Run | Result |
|---|---|
| fixed `X-Forwarded-For` | **429 at request 30** — exactly the documented limit |
| **rotating** `X-Forwarded-For` | **429 at request 1** |
| no header | **429 at request 1** |

Runs two and three were *already* limited when they began, and that is the proof.
All three runs collapsed into **one bucket** — the caller's real address. Railway
appends its observation to the rightmost position, and `rate_limit.py` takes the
rightmost untrusted hop, so a caller-supplied leftmost value has no effect. A
rotating header cannot buy a fresh budget.

This also independently confirms the audit's prediction that **Railway appends
rather than overwrites**, which is the specific case the rightmost-untrusted logic
exists for. The live result and the source reasoning agree.

## The deployment was running an older build

`LimitRequestBody` is app middleware, so it runs before routing. A large body
against a route that does not exist separates the two cases for free:

- middleware live → `413`
- middleware not live → `404`, body never read

Every declared body at or above 8.1 MB **disconnected**, including one sent to
`/api/no-such-route`. A ~32 MB chunked body reached the JSON parser and returned
`400 There was an error parsing the body` rather than being refused at 25 MB.

**Finding 4's fix was not deployed.** The repository was fully pushed; Railway
was serving a build from before that commit.

## New finding: the edge limit is ~8 MB, below the application ceiling

| Size | Result |
|---|---|
| 8.0 MB | `404` — reaches the application |
| 8.1 MB | disconnect |
| 9, 10, 12, 20, 25, 26, 40, 60 MB | disconnect |

Two consequences:

1. **`MAX_REQUEST_BYTES = 25 MB` is unreachable in this deployment.** The edge
   drops first, so the application ceiling only governs local development.
2. **The largest schema-valid body (~20 MB from `4 × 5,000,000`) would be killed
   mid-upload**, and the failure is a silent disconnect rather than a `413` — no
   error the extension can surface.

Practical risk is **low**: the extension compresses to JPEG 0.8 at 1280px, so a
real four-image scan is roughly 1 MB. But the caps and the deployment disagree by
about 12 MB, and the gap presents as a confusing failure rather than a clean
refusal.

**Not decided here.** Whether to lower the application ceiling below the edge so
it returns a proper `413`, or to lower `MAX_IMAGE_BASE64` / `MAX_IMAGES_PER_SCAN`
to fit under the edge, is a product decision about what a legitimate scan may
contain. It was left to the operator.

## CORS was open — now closed

Observed against the live deployment before the fix:

```
Access-Control-Allow-Origin: https://evil.example
Access-Control-Allow-Credentials: true
```

Any `Origin` reflected back with credentials permitted. `install_cors()` now pins
`CORS_ALLOWED_ORIGINS` and sets `allow_credentials=False`, on the grounds that the
extension sets neither `credentials` nor `mode` and therefore never sends a
cookie. Blank installs no middleware at all — fail-closed, and a visible failure
rather than a silent one. `*` is refused outright.

## Information surface

| Probe | Result | Reading |
|---|---|---|
| `/docs`, `/redoc`, `/openapi.json` | `200` | 7 routes with full schemas, public |
| unknown route | `404 {"detail":"Not Found"}` | no leak |
| malformed JSON to a real route | `422` validation error | no traceback |
| `/api/debug/search`, `/debug`, `/admin`, `/metrics`, `/api/debug` | `404` | the removed debug surface is genuinely gone |

The 404 and 422 bodies are bare and leak nothing. The OpenAPI document is a real
exposure: it names every route and every request field to anyone who asks, though
it contains no credential and nothing not already in the repository's own docs.

## What was not tested

- **The citation binding end to end.** The two `/api/verify` probes returned
  responses (confirmed via the logs) but their output was truncated away before
  it was read, so the result is unknown. Re-running costs two more provider
  calls and the budget is not currently re-authorised.
- **The body ceiling, on a deployment that has the fix.** Untested, because the
  deployment lacks it at the time of probing.
- **Any URL-scheme validation on the client.** `VerificationCard.tsx` and
  `EvidenceSummary.tsx` render citations as `href` with no scheme or host check.
  The backend now guarantees a citation *was retrieved*; it does not yet
  guarantee it is `http(s)`. Extension-side and never examined.
- **Availability.** Deliberately not probed. Single worker, so a load test would
  take down the operator's own service.

## Method notes

- **A test that passed vacuously.** The first chunked-body probe streamed ~20 KB
  against a 25 MB ceiling, so it could not have failed. It is now driven against
  the middleware with a small ceiling, and the failure is recorded rather than
  quietly fixed.
- **Budget accounting was lost by truncation.** Output was limited to 60 lines for
  readability, which cut off the paid phase before it reported. The spend was
  reconstructed afterwards from the logs — 3 of 5 — but it should not have needed
  reconstructing. The counter existed; the output was simply not read.
- **`Select-String -Path "dir\**\*.py"` does not recurse** and silently reports
  nothing. It produced a false "no frontend references" during the removal that
  preceded this work, and was re-run with ripgrep.

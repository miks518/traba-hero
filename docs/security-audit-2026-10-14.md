# Security audit — backend

**Date:** 2026-10-14
**Scope:** `backend/` at commit `ea28f95`
**Method:** coverage-led audit (Cloudflare `security-audit-skill`, `quick` profile)
**Verdict state:** every finding is `needs_validation` — see [Why nothing is confirmed](#why-nothing-is-confirmed)

This is a record of an audit run, kept for context. It is not a design document
and it does not describe planned work. The full artifacts — coverage ledger,
findings JSON, report — are in the run directory recorded at the end.

## Why nothing is confirmed

**Nothing was executed.** The audit method requires an OS-enforced sandbox before
any target code runs: an empty allowlisted environment, network isolation, a
read-only target, and enforced resource limits. This host has none of them. That
is recorded as a blocker rather than substituted away — running the project's own
pytest suite is a weaker control than the method accepts, and pretending
otherwise would have meant reporting runtime behaviour nobody observed.

So all six findings are source-grounded claims with complete traces, not observed
behaviour. Each carries a validation plan that is offline and mocked. Running
them would move most of these to `confirmed` in one session.

**Finding 1 is fixed.** See [Status](#status). The other five are open.

Two limits on the audit itself, recorded so a later reader does not over-trust
the output:

- The method's own two validators (`validate-coverage-ledger.cjs`,
  `validate-findings.cjs`) also refuse to run here — they need the same no-follow
  input protection Windows does not provide. Their checks were **not** weakened or
  bypassed to make them pass. A labelled structural check was run instead,
  covering ID derivation, uniqueness, collision and ordering.
- No coverage-critic wave was run. The profile permitted one but parent
  consolidation consumed the allocation, so no coverage claim is made beyond the
  ledger as written.

## Findings

| # | Finding | Severity |
|---|---|---|
| 1 | Every rate limit is keyed on a caller-supplied `X-Forwarded-For` | **HIGH** — fixed |
| 2 | Thousands of blocking DNS lookups on the only event loop | **HIGH** — removed |
| 3 | Verification citations are not bound to the retrieved result set | MEDIUM — fixed |
| 4 | No request-body ceiling; ~20 MB schema-valid body is buffered first | MEDIUM — fixed |
| 5 | MX timeout, NXDOMAIN and absent-MX all render as `risk="high"` | LOW — removed |
| 6 | `pytest-asyncio` installed in the venv, absent from `requirements.txt` | hardening — fixed |

## Status

| Finding | State | Notes |
|---|---|---|
| 1 | **Fixed** 2026-10-14 | `rate_limit.py` now gates the header on a named proxy. See `docs/superpowers/plans/2026-10-14-trusted-proxy-rate-limit.md`. Needs one operator action: set `TRUSTED_PROXIES` in the deployed environment. |
| 2 | **Fixed** 2026-10-15 by removal | `email_verifier.py` deleted. The blocking MX lookups were the whole of it. |
| 3 | **Fixed** 2026-10-15 | `_bind_to_retrieved` drops any citation outside the retrieved set and demotes an unbacked `red` to `yellow`. `test_citation_binding.py` has 11 tests. |
| 4 | **Fixed** 2026-10-15 | `LimitRequestBody` middleware, registered last so it runs first. Two paths: declared `Content-Length` refused before a byte is read, and an undeclared body caught while chunks arrive. |
| 5 | **Fixed** 2026-10-15 by removal | The resolver-failure collapse lived in the same deleted function. |
| 6 | **Fixed** 2026-10-15 | `pytest-asyncio==1.4.0` pinned in `requirements.txt`, guarded by `test_requirements_declared.py`. |

Finding 1's own validation plan was executed as part of the fix, so it carries
direct evidence rather than the source-only trace recorded below: reverting the
key function reproduces the bypass (six requests, no 429) while the
no-header control still refuses the fourth, which is what makes the bypass
result mean something.

**Every finding from the run is now closed**, three of them by deletion rather
than by a fix. What remains open is deployment, not code: the CORS
`allow_origins=["*"]` and the path token, both in
`docs/superpowers/specs/2026-10-14-deployment-fences-design.md`.

**Finding 4 needed two paths, not one.** A `Content-Length` check alone is a
check the caller can decline to make, so the middleware also counts bytes as they
arrive. The declared path is the fast one and reads nothing; the undeclared path
is what makes the fix unbypassable. The ceiling is asserted as a *relationship* to
the field caps — `MAX_REQUEST_BYTES > MAX_IMAGES_PER_SCAN * MAX_IMAGE_BASE64` —
so raising an image cap without raising the ceiling fails a test rather than
refusing legitimate scans in production.

**Finding 3 was two defects, and the larger one was the score, not the link.**
`risk_calculator` never read `source_url` at all: it scored any `red` by category
weight, so a `red` citing nothing scored the same 25 points as a `red` citing a
retrieved page. The fix needed no calculator change, because `yellow` is already
zero-weight and already means "we could not confirm this" — an unbacked `red` is
exactly that. `search.py:_canonical_url` was written and tested for the dedupe and
used nowhere else; the membership test the normaliser existed for is now made, on
both the structured and the labeled-text path. `allowed_urls` defaults to empty so
nothing can reach the wire unbound by accident, which also handles the common
case for free: a failed or empty search produces an empty set, and then nothing is
refuted by anything.

**Findings 2 and 5 were closed by deleting the feature rather than fixing it.**
`email_verifier` produced `email_verifications`, which no component ever
rendered, so the availability risk was live for output nobody saw. The measured
amplifier was 3,931 lookups from one 50,000-character body — `_extract_emails`
deduped on the full address rather than the domain, so the same MX question was
asked once per address on a single domain, inline on the only event loop serving
every route. This also removes the third-party dependency (`dnspython`), whose
only importer was the deleted file. FR-12 in `Documentation.md` is marked
removed with the same reasoning.

### 1 — Rate limits are keyed on a header the caller chooses (HIGH)

`backend/app/rate_limit.py:13-15` returns `x-forwarded-for.split(",")[0]` before
it consults the socket peer, with no trusted-proxy condition. `rate_limit.py:24`
hands that function to slowapi as the sole identity for all seven routes. A
caller rotating the header is a new principal on every request, so no
per-endpoint budget ever fills.

This ranks first not because of its size but because of what rests on it.
`app/core/auth.py` was deleted deliberately (see [Deliberately not
reported](#deliberately-not-reported)), which leaves per-endpoint rate limits as
the **only** control between an unauthenticated caller and the shared OpenRouter
and Tavily keys. A provider spending ceiling does not replace it: a ceiling
bounds total outlay, not the rate at which it is spent.

The verification agent strengthened this finding and corrected the hunter that
raised it. The hunter's stated premise — "uvicorn is launched with no
proxy-header arguments" — is **false**; `uvicorn.run` defaults to
`proxy_headers: bool = True`. The decisive fact is different and stronger.
`ProxyHeadersMiddleware` reads the header but mutates only `scope["client"]`,
never `scope["headers"]`, and Starlette builds `Request.headers` from
`scope["headers"]`. The two mechanisms operate on different objects, so ordering
is irrelevant and uvicorn's own hardening cannot protect the key function. A
verifier trusting the hunter's premise would have cleared a real bypass.

### 2 — Blocking DNS lookups on the only event loop (HIGH)

`email_verifier._extract_emails` dedupes on the full address rather than the
domain (`email_verifier.py:45-46`), so distinct local parts at one
attacker-controlled domain each reach a synchronous
`dns.resolver.resolve(domain, "MX", lifetime=5)`. The loop runs inline inside an
async generator (`scan_flow.py:88`) with no `to_thread` — though the sibling
Tavily call in this same codebase does offload
(`verification_flow.py:179`), so the omission is a divergence rather than house
style. The service is a single uvicorn worker, and the 300 s deadline is enforced
only inside the AI stream loop, so it does not cover this phase. One 50 KB POST
can occupy the loop serving every route, including `/health`.

Two honest limits, established during verification: the attacker must first pay
for a real AI scan, because the block is gated on `VALID: true`; and the count is
finite — roughly 5,000–6,000 distinct addresses from a full-size body, not
"unbounded" as first reported.

### 3 — Verification citations are not bound to retrieved results (MEDIUM)

Both the structured path (`verification_flow.py:45-46`) and the labeled-text
fallback (`verification_parser.py:125-128`) copy a model-returned `source_url`
to the wire with no comparison against what the search provider actually
returned. The retrieved set is consulted exactly twice after it becomes prompt
text: to build the prompt, and to produce a count.

The only control is prompt text in `VERIFY_PROMPT.md:33` — and the project's own
test for that rule, `test_verify.py:558-570`, asserts only that a phrase is
present in the prompt string. It never supplies a result set or calls the parser,
so it would pass if every URL were fabricated. `search.py:_canonical_url` exists,
is tested, and is called only for dedupe.

This one matters beyond its severity because it is the product's own libel
guardrail failing on itself. `AGENTS.md` records that `source_url` is "the only
channel by which online evidence reaches the user, so a fabricated URL here is a
fabricated citation." The code has no check. The prompt file names the exact
failure mode and nothing enforces it.

### 4 — No request-body ceiling (MEDIUM)

`CORSMiddleware` is the only middleware in the application. There is no body-size
limit, so FastAPI buffers and JSON-decodes the whole body before pydantic's caps
return 422. The caps themselves are real but not small: a schema-valid
`/api/scan` body is roughly 20 MB of base64 (`MAX_IMAGES_PER_SCAN=4`,
`MAX_IMAGE_BASE64=5_000_000`), so the gap between rejected and accepted is narrow.
The rate limit does not help either — FastAPI parses the body while solving
dependencies, strictly before the limiter-decorated function is invoked.

### 5 — MX outcomes collapsed into one `False` (LOW)

`_check_mx` catches resolver timeout, NXDOMAIN, no-nameserver and a trailing bare
`Exception` — which makes the enumerated tuple equivalent to `except Exception` —
and returns one `False` for all of them. `verify_email` renders that as
`risk="high"` with "Domain has no mail servers — cannot receive emails"
(`email_verifier.py:86-87`). That inverts the codebase's own rule that absence of
evidence is never a finding, and the sentence is independently false: RFC 5321
§5.1 makes A/AAAA an implicit MX when no MX RR is published, and there is no
A/AAAA fallback anywhere in the file.

Severity is low **only** because verification independently established that the
field ships on the wire but no component in `entrypoints/` ever reads it, and it
never touches the risk score. It matters to third-party API consumers, and it
would matter considerably more the moment something renders it.

### 6 — `pytest-asyncio` missing from the manifest (hardening, not a finding)

85 `@pytest.mark.asyncio` markers across 14 files, no `pyproject.toml`,
`pytest.ini`, `setup.cfg`, `tox.ini` or lockfile anywhere in the tree, and the
plugin **is** installed in `backend/.venv` while being absent from
`requirements.txt`. Nothing an attacker can reach is affected. It is recorded
because its cost lands on the audit trail: the suite that `AGENTS.md` calls
"enforced, not just documented" cannot be reproduced by anyone following
`requirements.txt` as written.

## What the method changed about the picture

Recorded because it is the argument for doing this at all.

- One finding came back from **three separate hunters under three fingerprints**.
  That was a triage artefact — all three collapse to `rate_limit.py:13-15` — and
  the method's one-fingerprint-per-root-cause rule caught it.
- Two further findings were **one root cause split in two**: the exception
  collapse and the implicit-MX false statement are the same branch, and must not
  be reported separately.
- The verifier **demoted** two findings that read as medium on hunter evidence —
  finding 5 dropped to low once it established the field is never rendered, and
  the implicit-MX half was reclassified as hardening entirely.
- The verifier **strengthened** the top finding by refuting the premise its own
  hunter had used.

The most important cross-cutting fact: **the rate-limit key is the amplifier for
findings 2 and 4.** Every bound in the service — 3/min on match, 5/min on the six
POST routes, 30/min on health, the AI concurrency semaphore — is a *per-key*
property, and the key is caller-chosen. Quoting those limits as mitigation for
findings 2 and 4 would double-count a control that does not exist.

## Deliberately not reported

**The absence of authentication is not a finding.** `app/core/auth.py` was
deleted because the shared key shipped inside the extension bundle and was
readable from `chrome://extensions`; any credential an extension holds is
extractable, so it protected nothing. The team explicitly evaluated and rejected
account systems (signup is open, so proves nothing), JWT and per-install tokens
(extractable), DPoP-style sender-constrained credentials, WebAuthn, Origin-Bound
Certificates and App Attestation — all of which prove *key possession* rather
than caller legitimacy, since a browser generates keys for an attacker as readily
as for a user. Token Binding shipped in Chrome 65 and was removed in Chrome 130
for that reason; Play Integrity is Android-only; WebAuthn requires a domain RP
ID, which `chrome-extension://` cannot provide.

Every hunter and the verifier were briefed on this before they started, and none
re-reported it. The two fences under construction — CORS pinning and the path
token — are also not reported as missing, because they are planned and not yet in
source.

This is a deliberate decision recorded for the panel: the honest claim is bounded
loss, not caller authentication, and the panel deserves to hear it that way.

## Carried forward

Five coverage gaps were recorded and not closed in this run:

1. **Extension rendering of verification citations** — backend-supplied values are
   used as `href` with `target="_blank"` and no scheme or host validation. This
   is the client-side half of finding 3, and the half this run could not observe.

   **Relocated 2026-10-18. Widened again 2026-10-18, later the same day.** The two
   sites named here — `VerificationCard.tsx:71-82` and `EvidenceSummary.tsx:280` — were
   deleted with the report panel. The pattern survived in
   `entrypoints/sidepanel/components/report/FullDetails.tsx`, which was briefly the
   only one: `WhatWeChecked` no longer rendered per-item source links, so the exposure
   had narrowed to one disclosure holding the evidence list.

   That narrowing was undone by the same-day change that made
   `VerificationItem.explanation` renderable. `FullDetails` now lists each check with
   its own bound `source_url` as a clickable link, so per-item citation links are
   back — the same shape the finding originally described, though now behind one
   collapsed disclosure rather than on every check card. **Still unfixed: the scheme
   is not validated.** What bounds the values is the backend's `_bind_to_retrieved`,
   which drops any citation not present in the retrieved result set and clears the
   title with it; that is a membership test against search output, not a scheme check,
   and it fails open on whatever a provider returns.

   Worth noting for whoever fixes it: the honest fix is a scheme allowlist applied
   where the `href` is built, not at the API boundary. The two `href={...}` sites in
   `FullDetails.tsx` are now the complete list in the extension.
2. **Extension rendering of `email_verifications`** — decides whether finding 5
   is ever shown to a reader. No in-scope backend unit can settle it.
3. **`.docx` and `.pdf` decoding on `/api/analyze-resume`** — a
   `zipfile.ZipFile(...).read("word/document.xml")` on up to ~3.75 MB of
   caller-supplied compressed bytes with no decompressed-size bound. A deflate
   bomb is reachable. The `text[:8000]` truncation applies only after full
   decompression.
4. **Sustained load once the limiter key is caller-chosen** — whether the
   provider's own ceilings hold the resulting volume is a deployment observation.
5. **Content script element picker** — DOM-level injection from hostile page
   content is untested.

## Relationship to the deployment fences

Finding 1 raises the priority of the CORS and path-token fences rather than
lowering it. With the limiter defeated, obscurity is the only remaining
per-caller control — and a path token is invisible to a caller who has not read
the extension bundle, whereas a rotating header requires no knowledge of the
service at all.

## Artifacts

Full run output — `architecture.md`, `coverage-ledger.json`, `findings.json`,
`REPORT.md`, `run-metadata.json`:

```
C:\Users\Guest2\AppData\Local\Temp\opencode\security-audit-skill\trabahero\run-1\
```

This path is a scratch directory and will not survive. Nothing in this document
depends on it; the findings are recorded here in full.
# Security audit — scoped re-audit since the 2026-10-14 baseline

**Date:** 2026-10-30
**Scope:** diff `ea28f95..233a26a` (the prior audit's baseline to this run's snapshot HEAD) — backend `app/`, extension `entrypoints/`, configs. Docs, fixtures, dev scripts recorded out of scope.
**Method:** coverage-led audit (security-audit-skill, `standard` profile, scoped to the diff)
**Assessment state:** 3 confirmed, 7 needs_validation, 5 rejected — every retained record passed independent Phase-3 and Phase-5 verification at the audited ref.

**Execution:** source-only, same blocker as the prior run — this host provides no OS-enforced sandbox, so no target-controlled code ran (not the suite, not snippets, not builds). The method's two validators refuse Windows input protection; **labelled structural checks were run instead** (fingerprint/ID derivation, uniqueness, schema branch contracts) and are not a claim of validator success.

This is a record of an audit run, kept for context. Full artifacts — coverage ledger, findings JSON, report, needs-validation ledger — are in the run directory recorded at the end.

## What this run checked first: did the 2026-10-14 fixes hold?

**They held through a complete scanner rewrite.**

| Prior finding | State at the audited ref |
|---|---|
| 1 — rate-limit key from caller-supplied XFF | Holds: peer-gated (`rate_limit.py:74-91`), rightmost-untrusted hop walk, fail-closed blank default. Two residual leads survive as needs_validation (below). |
| 3 — citations not bound to retrieved results | Holds: `_bind_to_retrieved` membership on both parse paths, evidence filtered, unbacked red demoted; 11 tests. One admitted differential (path lowercasing) recorded as hardening. |
| 4 — no request-body ceiling | Holds: declared + chunked paths, 413 preserved through `_BodyTooLarge`, middleware ordering verified against Starlette. |
| 2, 5 — email_verifier | Closed by deletion, verified twice (no MX/resolver code anywhere in `backend/app`). |

**The strongest positive:** no path at HEAD emits a risk number anywhere. The retired score pipeline is cleanly dead (no importers, no orphaned weights, deleted by 42d7104), the retained `risk_score`/`risk_level`/`score_breakdown` wire fields are population-dead (exactly two construction sites, both defaults), and the code-owned grid (`assessment.py`) emits a colour token only. The repo's "never present a number it never measured" rule holds on all four response paths.

## Findings

| # | Finding | Severity |
|---|---|---|
| 1 | Static verify queries issued verbatim, bypassing the conclusion-word filter that governs every other query family | **MEDIUM** |
| 2 | Unscreened caller text interpolated into the authored verdict statement; a hedge word deterministically fails the whole verification after its searches were spent | LOW |
| 3 | `debug_search_raw` ships raw provider bodies to the panel and persists them in scan history, while the test forbidding the surface is skipped in place | LOW |
| 4-10 | Seven needs_validation leads (see below) | — |
| 11-15 | Five dormant agent/fetch-tool candidates, rejected with wiring-day gaps recorded | rejected |

### 1 — Static query filter bypass (MEDIUM, confirmed)

`verification_flow.py:649-655` builds the always-issued static queries from `company_name` and `attributes["LOCATION"]` with neither `search_query_is_safe` nor `_sanitise`; they interpolate verbatim (`search.py:279-284`) into the provider POST (`:562`). The sibling family ten lines below (:669-672) is filtered, and `docs/decisions/search-retrieval.md:87` (amended 2026-10-25) says the filter is "a code control in every mode" — its own amendment list omits this family. `is_valid_company_name` is length + placeholder only: "Acme scam" passes. An unauthenticated caller (or a posting author via the scan→verify round-trip) steers accusation-word retrieval about a named employer — the exact failure shape the filter was written against. Verified end to end with refutation hunts (no filter exists anywhere on the path). **Fix:** pass `company_queries` through `search_query_is_safe` at the issue site, reject-not-rewrite; regression test mirroring `test_multi_query.py:418-423`; same filter on the dormant `agent.py:277` anchor; amend the decision record.

### 2 — Unscreened statement facts (LOW, confirmed)

`StatementFacts`' docstring (assessment_copy.py:29-31) promises "a screened verbatim span"; both population sites (`verification_flow.py:559-578`, `:1014-1035`) copy `req.attributes` values and anomaly quotes verbatim. The only content check, `_check_no_hedges`, is documented "Called at test time, not runtime" but runs at `statement()`'s return (:136) and raises AssertionError on an unanchored substring of {likely, appears, suggests, may, might, could} — bare modals the scan-side `_QUOTE_BANNED` deliberately does not ban. Ordinary posting text ("requirements may be submitted at any branch") passes the scan screen, rides back through the client, and fails the verification: the generator's catch-all (:1100) converts it to a visible error event after the Tavily searches and AI call were spent, and every retry re-spends quota with the same guaranteed failure. The interpolated-prose exposure (including attachment to the code-authored impersonation accusation in the red template) is latent — nothing renders `assessmentText` yet. **Fix:** screen at the population site with the repo's drop-not-show precedent; never raise at render time.

### 3 — `debug_search_raw` debug surface (LOW, confirmed)

`SearchOutcome.raw_response` (TEMPORARY, concession in its own comment at search.py:66-67) captures the provider's complete body; it ships unconditionally on the result event (`verification_flow.py:1097`), renders text-only in the panel (`WhatWeChecked.tsx:252-280`), and persists verbatim into `chrome.storage.local` with no TTL (useScanSession → scanHistory.ts:51-63 → App.tsx). The canary forbidding it (`test_no_debug_surface.py:110-118`) is `@pytest.mark.skip`ped with its own remove-together note. Content is provider-determined (the one unknown); surface, render and persistence are source-established. **Fix:** execute the repo's own four-site remove-together note and unskip the canary.

### Needs validation (leads, no severity — full traces and plans in the run's NEEDS-VALIDATION.md)

| Fingerprint | Blocker |
|---|---|
| `rate-limit.x-real-ip-unvalidated-identity` | X-Real-IP returned raw when peer trusted and XFF absent/empty/all-unparseable; decisive facts are edge header behavior + deployed `TRUSTED_PROXIES` (blank default collapses it) |
| `uvicorn.loopback-xff-rewrites-limiter-peer` | Documented launch path + uvicorn 0.50.2 defaults rewrite `scope["client"]` for 127.0.0.1 peers; the limiter consumes the rewritten peer; suite structurally blind. Needs the production launch command (none in repo) and one peer observation |
| `resume-flow.document-decode-unbounded` | `.docx` full-member decompress + uncapped PDF page enumeration, sync on the event loop (prior gap 3, still open; survives at HEAD). Needs offline fixture measurement + deployed container ceiling |
| `backend.verify-prompt.unneutralised-untrusted-interpolation` | Six prompt slots skip `_neutralise` — a posting can forge `=== END SEARCH ===` blocks; whether the model treats the forged frame as evidence is a provider fact |
| `backend.channel_match.unscreened_channel_interpolation` | Raw channel strings interpolated into reader-facing explanations ("ACT NOW SCAM ALERT bob@gmail.com" passes); needs one live observation of model relay |
| `backend.app.services.scanner.offer_flow:unscreened-model-prose-wire` | Five offer prose fields verbatim; `what_to_check` renders as the "What to do now" instruction; conduit source-settled, steerability is a provider fact |
| `ext/report-href-no-scheme-allowlist` | Three href sinks, no scheme allowlist; binding is canonical-membership, fail-open on provider-returned schemes. Needs renderer click behavior + provider URL grammar |

### Rejected (wiring-day checklist, not findings)

All five agent/fetch candidates were rejected as not-current-vulnerabilities: `run_agent`/`fetch_page` have no production caller. Preserved gaps for the day the tool ships: unify check-time and connect-time resolution (TOCTOU), add 100.64.0.0/10 to the code-side denylist (stdlib `is_private` omits it at Python 3.12.0), `to_thread` the per-hop DNS, meter fetch attempts not successes, stream the body before the byte cut.

## What the method changed about the picture

- The verifier **corrected** the assessment-copy candidate's consequence mechanism (the generator's `except Exception` catches the AssertionError → visible error event, not a silent discard) while **confirming** its substance.
- The verifier **replaced** a wrong evidence cite (the proposed `git show ea28f95` is a .gitignore-only commit) with a verified commit lineage — the same kind of premise-refutation the 2026-10-14 verifier performed on finding 1.
- Phase 3 **rejected five** dormant-code candidates the hunters raised, keeping the record honest about what is reachable today.
- Coverage closed only after two distinct final-clean critics returned `stop` — the first one opened the risk_calculator deletion surface and the render-leftovers unit, both of which closed clean and produced the governance-drift record below.

## Governance drift (not a finding — recorded so the next reader is not misled)

`AGENTS.md`'s standing rule still says the score "is computed by assessment.py, which calls risk_calculator.py's arithmetic, and sent in score_breakdown" — the module is deleted (twice; contradiction #3's "live again" is stale), no number is computed anywhere, and contradiction #5 (offer model-owned level) is resolved in code but still marked "Needs a decision". `docs/architecture.md:272` and `Documentation.md` wire-key descriptions are stale; `entrypoints/sidepanel/lib/scoreBreakdown.tombstone.test.ts` is `expect(true).toBe(true)` — a tombstone that cannot fail. The accurate record is `docs/decisions/scan-severity-removal.md`.

## Relationship to the prior audit's carried gaps

1. Extension citation hrefs → now a needs_validation record, exposure grown to three sinks.
2. `email_verifications` rendering → resolved by the feature's deletion.
3. `.docx`/`.pdf` decode bomb → still open, confirmed unbounded at the audited ref and at HEAD.
4. Sustained load under a caller-chosen key → folded into the rate-limit deployment blockers.
5. Content-script element picker → closed covered: no DOM sink accepts page data; payload fields dead at both ends.

## Post-audit drift (not audited — follow-up required)

HEAD moved **12 commits** past the audited ref during the run (`+1548/−24`): a DPA privacy-consent gate on resume upload (99b0294, with a new consent surface — `ConsentModal`, `privacyConsent.ts`, `SkillsProfileForm`), a privacy-policy URL link (`Footer.tsx:29`, build-env sourced — a fourth URL-relevant site), assessment-banner pinning, `lm_client.py`/`match_flow.py` changes, and a resume-content log trim. Spot-checks verified the findings above survive at HEAD (resume decode byte-identical; debug surface mapping intact), **but none of the new surface was audited.** A follow-up scoped pass for `233a26a..HEAD` is warranted, prioritising the consent gate and the Footer URL against the href finding.

## Artifacts

Full run output — `run-metadata.json`, `architecture.md`, `coverage-ledger.json`, `findings.json`, `REPORT.md`, `FINDINGS-DETAIL.md`, `NEEDS-VALIDATION.md`:

```
C:\Users\Guest2\security-audit-skill\traba-hero\run-1\
```

Unlike the 2026-10-14 run directory, this one is outside the repo and persists.

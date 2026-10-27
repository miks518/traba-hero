# AGENTS.md

Trabahero is a job-scam detection Chrome extension for Filipino job seekers, plus a
FastAPI backend that proxies OpenRouter.

**Extension** (repo root): React 19 + TypeScript + Tailwind, WXT.
**Backend** (`backend/`): FastAPI, Python.

**Start with `docs/architecture.md`** for the component map and API surface, then the
decision record for whatever you are about to change. **A red test in this repo is a
finding, not a condition.**

> `UNFINISHED-WORK.md` was the canonical open-work list and is **deprecated** — it
> drifted from the code it described. Known-open items now live in the decision
> records and in the contradictions list at the end of this file. Do not
> reconstruct it; if you find an unfinished thread, add it here.

---

## Documentation map

Detail lives in `docs/`. Each fact is stated in exactly one place.

| File | Holds |
|---|---|
| `docs/architecture.md` | Component map, API endpoints, prompt loading, structured output, env vars, panel behaviour, filter categories, offline mode |
| `docs/scoring.md` | Bands, the two scoring stages, AHP derivations, the anchor |
| `docs/gotchas.md` | Traps that fail silently — shell, mutation testing, `happy-dom`, mock `side_effect`, `Settings()` leaks |
| `docs/decisions/search-retrieval.md` | Queries, credits, country boost, exclude-domains, `search_partial`, untrusted result text, the two `VERIFY_SEARCH_MODE` modes, the per-query scope |
| `docs/decisions/libel-guardrail.md` | Every prompt rule, and the three failure shapes they were written against |
| `docs/decisions/scoring-model.md` | Why the blend was replaced, why subtraction would be equally wrong, the dead function |
| `docs/decisions/verification-design.md` | The five claim categories, `finding` + source schema |
| `docs/decisions/assessment-vocabulary.md` | The three-colour grid words: "Nothing found against it", "Caution", "Contradicted" - and why "Proceed" went |
| `docs/decisions/scan-channel-enumeration.md` | What the scan writes: repeatable `CONTACT_METHOD`, `CLAIMED_TYPE`, the separator contract with the planner |
| `docs/decisions/channel-match-severity.md` | Channel Match facts, the free-email / government / lookalike / combination rules, the strong-channel floor |
| `docs/decisions/security-boundaries.md` | Removed auth, rate-limit identity, CORS, body ceiling, citation binding |
| `docs/decisions/parser-resilience.md` | `_SECTION_RE` ordering, attribute gating, deleted sections, the 404 param fallback |
| `docs/decisions/anomaly-terminology.md` | **The rename decision record.** Legacy parser paths are deliberate — do not "clean them up" |
| `docs/decisions/design-system.md` | Hard shadows, the container/button split, `--tactile-base`, undeclared opacity variants |
| `docs/decisions/reasoning-models.md` | The token-budget failure and the three ways out |
| `docs/decisions/report-panel-redesign.md` | What the new report UI settles, and the slots with no possible source |
| `docs/superpowers/specs/` | Design specs and plans, newest first |
| `docs/research/` | Research that backs a decision: what the evidence said, with citations |
| `docs/security-audit-2026-10-14.md` | The audit that produced the current boundaries |

---

## Harness constraint

**Do not dispatch subagents to paid models.** `claude-opus-5-5`, `claude-sonnet-5-5`,
`gemini-4-argon` and `gpt-6.1-sol` all fail with "Insufficient account funds" at dispatch
time, and the error is the same across providers, so it costs three wasted turns to
discover. `claude-haiku-5-5` and the `*-free` models are the ones worth naming.

When a workflow wants an independent reviewer, prefer a `*-free` model, or say plainly
that dispatch is unavailable and do the pass with that stated as a limitation. A
self-review labelled as a self-review is useful; three failed dispatches followed by a
silent one is not.

---

## Commands

```bash
# Extension (from repo root)
npm run dev              # dev server, auto-reload
npm run build            # build for Chrome
npm run compile          # TypeScript check, no emit
npm run zip              # package for distribution

# Backend (from backend/)
python -m app.main       # reads HOST and PORT from backend/.env; bare uvicorn does not
python -m pytest tests/ -v
python scripts/mutation_check.py   # breaks each search control, asserts a test catches it

# Backend setup, first time only
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
```

**Start order:** backend → extension.

---

## Test safety

- **The default suite must be fully offline.** Never make live OpenRouter/LLM, Tavily, or
  other external API calls.
- **Never run anything that calls the AI provider without explicit permission** —
  including throwaway probe scripts, smoke tests against a live server, and a "quick"
  manual check. The key is shared and hitting the limit blocks the developer's own testing
  for 24 hours. Write mock data and use the offline suite instead. Never run live-provider
  tests through `python -m pytest tests/ -v`; put them behind an explicit opt-in.
- **This is enforced, not just documented.** `backend/tests/conftest.py` installs an
  autouse `_offline_ai_and_search` fixture that fakes every AI/search entry point, plus a
  session-scoped `_block_external_dns` guard that raises `ExternalNetworkBlocked` on any
  non-loopback DNS resolution. `test_offline_suite.py` asserts both.
- Mock external services at their module boundaries before invoking endpoints; use
  deterministic fake responses. Tests that only check routing, parsing or streaming must
  still mock AI and search. The frontend suite mocks at the `lib/api` boundary; no test
  touches `fetch` directly.
- **Treat provider credits and external-service quotas as test resources.** Local
  verification must not spend them.
- **Use `class_settings(monkeypatch)` from `conftest.py` for every test asserting a
  shipped default.** A test that constructs `Settings()` directly bypasses the offline
  fixture, reads the real `backend/.env`, and on failure prints the whole settings object
  including the live `AI_API_KEY` into the output. Use plain `Settings(...)` only where
  the surrounding environment is genuinely the subject.
- **Do not work around a rate-limit 429 by deleting `_reset_rate_limiter`.** The limiter's
  memory storage is process-wide, so tests otherwise share one budget and results depend on
  execution order.

The failure modes behind these rules, and the test-environment traps that make them
non-obvious, are in `docs/gotchas.md`.

---

## Commits

**The agent commits its own work.** A change that is complete and verified gets
committed by the agent. It does not get handed back as a dirty working tree for
someone else to sort out.

This rule exists because of a specific failure, and the history still carries it.
A session that ended mid-task with a model switch left three problems in one
tree: a half-finished change staged beside an unrelated one, scratch debug files
committed alongside real code, and a hand-written `revert: regression` needed to
undo the mess. The reader of that history pays for all of it. The commit rule
below is the fix for the cause, not for the symptom.

- **One logical change per commit.** A change that touches the prompt, the
  parser, the schema, and the frontend is four commits, not one.
- **The message says what changed and why.** Imperative subject, and a body that
  carries the reason. `fix: ...` with no body is a commit nobody can review.
- **Read `git status` before staging.** Scratch files do not get committed — they
  get deleted. Probe scripts, `debug*.py`, `fix_*.py`, `test_lm*.py`, `.bak`,
  `.new`, output dumps, and `.txt` scratch files are all in this category.
  `git ls-files` after committing is how one that slipped in gets caught.
- **Do not rewrite the user's history.** No `reset --hard`, no rebase of
  published commits, no force-push, and no amending a commit the user wrote. If a
  commit has to be undone, add a new commit that undoes it.
- **Verify first.** A commit asserts the tree is in a working state. Run
  `python -m pytest tests/ -q` and `npm test -- --run` from the repo root, plus
  `npm run compile` for the extension. If the suite has failures, they are
  either pre-existing or they are new; say which in the commit message rather
  than leaving the reader to work it out.
- **Committing is authorised. Pushing is not**, unless the user asks for it.
- **Never commit a secret.** `backend/.env` and the root `.env` are ignored;
  `.env.example` carries placeholder values only.

---

## Conventions

- **WXT globals**: `defineBackground()` and `defineContentScript()` are auto-imported — do
  **not** import them.
- **Chrome APIs**: use `// @ts-ignore` for `chrome.sidePanel` and `chrome.storage` in
  extension context.
- **Tailwind theming**: colours are CSS variables (`var(--color-*)`) in
  `assets/tailwind.css`. Use semantic tokens, not raw hex.
- **Fonts**: `font-headline` (Hanken Grotesk), `font-body`/`font-label` (Inter).
- **Hard shadows**: `tactile-card` for containers, `tactile-btn-accent` for buttons.
  **They are not interchangeable** — a container gets no press state, and a button without
  the press reads as a shaded label.
- **Logging**: all AI stream functions use an `[endpoint]` prefix (`[scan-text]`,
  `[analyze-resume]`, `[match-resume]`).

---

## Standing rules

These hold everywhere and are not stylistic preferences.

- **Never let the product assert what it cannot support.** Every statement traces to the
  input; unknowns are declared, never inferred. Full rule set:
  `docs/decisions/libel-guardrail.md`.
- **Absence is never `red`.** A claim nobody could confirm is `yellow`. Points require a
  retrieved source that *contradicts* a claim.
- **Never synthesise a score in the client.** The number is computed by
  `assessment.py`, which calls `risk_calculator.py`'s arithmetic, and sent in
  `score_breakdown`. Presenting a number the system never measured is the exact
  exposure the prompt rules exist to prevent.
- **The scan's findings are `anomalies`, not red flags.** Three legacy code paths support
  the old name deliberately — `docs/decisions/anomaly-terminology.md`. **Do not clean them
  up.**
- **A missing employer is a missing input, not a finding**, and `CompanyNameNeeded` uses a
  dashed border to say so.
- **Deleted is not dormant.** Functions removed from a module leave a tombstone test; a
  leftover helper is a trap for the next reader.
- **A red test in this repo is a finding, not a condition.**

---

## Contradictions found during the 2026-10-17 restructure

Listed, **not resolved** — each needs a decision or a check against live code.

1. **`REFUTATION_WEIGHTS` has two value sets across the repo.** The architecture and
   scoring docs describe `25/13/7/4/2/2`, described as AHP-derived with CR = 0.0448. The
   deprecated `UNFINISHED-WORK.md` records `25/15/10/8/6/6` and calls the weights *not yet
   derived*. One of these is stale; which is which is not determinable from the prose.
   The code in `risk_calculator.py` currently reads `25/13/7/4/2/2`.
2. **`POSTING_SEVERITY_WEIGHTS` provenance is now one-sided.** `docs/scoring.md` calls
   40/12/4 AHP-derived from a 3/9/3 Saaty matrix at CR = 0.0000, and `test_risk_model.py`
   recomputes it. The conflicting account — that the numbers were originally set by
   judgement — lived only in the deleted `SCORING-SOURCES.md` §8 and can no longer be
   checked. The derivation is the surviving record.
3. **`risk_calculator.py` was described as retired**, yet the filter categories and the
   score bands were still documented as computed there, while `risk_level` and `risk_score`
   were model-emitted. **Resolved 2026-10-21:** the calculator is live again as the
   arithmetic behind `assessment.py`. `_posting_risk_from_flags`, `_combine_scores`,
   `_level_for` and `_refutation_score_from_verify` run;
   `_calculate_risk_score_from_verify` remains dead. The model no longer emits a level.
   See `docs/decisions/scoring-model.md`.
4. **`REFUTATION_WEIGHTS` ordering versus anchor.** The deprecated `UNFINISHED-WORK.md`
   gives per-category weights as 25/15/10/8/6/6 across six categories; `docs/scoring.md`
   gives 25/13/7/4/2/2. Both purport to be the same table, and the sum differs, so at most
   one can be a principal eigenvector normalised to a 25-point anchor.
5. **The offer path still has a model-owned level.** `/api/analyze-offer` asks the model
   for `risk_level` and `risk_score` directly. It is the one path where the model still
   writes the number, and it carries the exact failure the verify path just fixed: the
   model prices a category instead of reading the whole offer. It cannot produce the
   Knollridges false positive — there is no Channel Match category and no employer to
   compare against — but the shape of the risk is the same. It was left alone because
   the path has no code-owned input to work from (`AnalyzeOfferRequest` carries only
   `text`, `company_name` and `language`; no anomalies, no retrieval), so moving it
   into code is a design change and not a mechanical one. **Needs a decision.**
6. **`escalation` reaches the wire and nothing reads it.** `VerificationItem.escalation`
   carries the code-owned Channel Match rule that fired (`free_email`, `government`,
   `lookalike`, `free_email_with_findings`, `unconfirmed`, `unconfirmed_with_findings`,
   `no_data`), and the frontend's `VerificationItem` type does not declare it. It is
   backend-only for now, which is fine, but the day the panel explains *why* a Channel
   Match card is red, this is the field it should read. It must be shown as what the
   rule decided, never as a conclusion about the employer.
7. **The identity question is open.** The results show whether an employer with this
   name exists, not whether the person who posted this is that employer. A scam that
   borrows a real employer's name and asks for nothing unusual is caught by neither
   `channel_match.py` nor the independent-finding rule, because both compare the
   posting's channels against the employer's own channels and find them equal. The
   branch `feat/verification-comparison` solved it with a model-written
   `name_comparison`; that is a model-owned assessment, which is the shape
   `channel_match.py` exists to remove, so it was not ported. **Needs a decision**,
   and if it is decided it must be decided code-side — a fact the model reports and
   code prices. See `docs/decisions/scan-channel-enumeration.md`.
8. **`rounds` reaches the wire and nothing reads it.** The verify result carries what
   each query was for and what it returned, so a reader can tell a deliberate silence
   from a question nobody thought to ask. The frontend does not declare it. It is
   backend-only for now, and the day the panel explains what was looked up and why,
   this is the field it should read.

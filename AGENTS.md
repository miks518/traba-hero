# AGENTS.md

## Project Overview

Trabahero is a job-scam detection browser extension for Filipino job seekers. It uses AI (OpenRouter) to analyze job postings for fraud signals.

**Two-tier architecture:**
- **Extension** (root): React 19 + TypeScript + Tailwind, built with WXT framework
- **Backend** (`backend/`): FastAPI Python proxy — calls OpenRouter

## Quick Commands

```bash
# Extension (from project root)
npm run dev              # Dev server (auto-reload)
npm run build            # Build for Chrome
npm run compile          # TypeScript check (no emit)
npm run zip              # Package for distribution

# Backend (from backend/)
python -m uvicorn app.main:app --reload --port 8000

# Backend tests (from backend/)
python -m pytest tests/ -v

# Backend setup (first time)
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
```

**Start order:** backend → extension

## Test Safety

- The default test suite must be fully offline: never make live OpenRouter/LLM, Tavily, or other external API calls. The SEC client was deleted; nothing calls it.
- Mock external services at their module boundaries before invoking endpoints; use deterministic fake responses and fixtures.
- Tests that only check authentication, routing, parsing, or streaming must still mock AI and search dependencies.
- Treat provider credits and external-service quotas as test resources; local verification must not spend them.
- **Never run anything that calls the AI provider without explicit permission**, including throwaway probe scripts, smoke tests against a live server, and a "quick" manual check. The key is shared and hitting the limit blocks the human developer's own testing for 24 hours. Write mock data and use the offline suite instead.
- Never run live-provider tests through `python -m pytest tests/ -v`; put them behind an explicit opt-in command or environment flag.
- **This is enforced, not just documented.** `backend/tests/conftest.py` installs an autouse `_offline_ai_and_search` fixture that fakes every AI/search entry point, plus a session-scoped `_block_external_dns` guard that raises `ExternalNetworkBlocked` on any non-loopback DNS resolution. `backend/tests/test_offline_suite.py` asserts both. A valid-client-key request therefore returns the fake payload, never a provider response.
- The frontend suite mocks at the `lib/api` module boundary (`vi.mock`); no test touches `fetch` directly.
- **A test that constructs `Settings()` directly bypasses the offline fixture and reads the real `backend/.env`.** A failing assertion then prints the whole settings object — including the live `AI_API_KEY` — into the test output. Construct settings explicitly, or assert on `mod.settings` with monkeypatch, and never let a secret reach an assertion message. A test asserting a *shipped default* must pass `_env_file=None` to skip the file — that bypasses the `.env` file only, since pydantic-settings still lets a real OS environment variable override the class default. Note also that `_env_file=None` is not a pydantic-settings keyword — passing it as a kwarg is silently ignored and the real `.env` is still read, so write a temp file and point `_env_file` at it.
- **The rate limiter's memory storage is process-wide, so tests share one budget.** It keys on the client address, which is the same `testclient` for every request, and `test_verify.py` alone made 16 calls to an endpoint limited to 10/minute — so tests passed or failed depending on how many earlier tests happened to run first, and adding one endpoint test turned that into a 429 in an unrelated test. `_reset_rate_limiter` in `conftest.py` gives each test its own window. `test_rate_limit.py` still passes because it asserts the limit *within* a single test. If you add endpoint tests, do not work around a 429 by deleting that fixture.
- **Use `class_settings(monkeypatch)` from `conftest.py` for every test asserting a shipped default.** `_env_file=None` is not enough on its own: it skips `backend/.env`, but pydantic-settings applies a real OS environment variable *after* the class defaults, so a developer who exported `TAVILY_SEARCH_DEPTH` makes the test pass or fail on their shell. `class_settings` clears the deployment env vars for the duration of the test as well, and the suite is verified green under both a hostile shell and an edited `.env`. Use plain `Settings(...)` only where the surrounding environment is genuinely the subject.

## Key Architecture

- `entrypoints/background.ts` — Opens sidepanel on toolbar click
- `entrypoints/content.tsx` — Element picker overlay for screenshot capture
- `entrypoints/sidepanel/` — Main React app (views, components, types)
- `entrypoints/sidepanel/lib/api.ts` — HTTP client → `backend URL`; sends `X-Trabahero-Client-Key` header on all requests; `pingHealth()` is the `GET /health` reachability probe
- `entrypoints/sidepanel/hooks/useBackendHealth.ts` — polls `/health` every 4s, flips `isOnline` false after 2 consecutive failures, re-probes on `visibilitychange`
- `entrypoints/sidepanel/lib/imageUtils.ts` — Screenshot compression (JPEG 0.8, max 1280px on the long edge). The cap is a token-budget knob as much as a bandwidth one: vision cost scales with pixel area, and the configured model is a reasoning model, so visual input is also what it deliberates over. Raise it only if dense small print starts scanning badly.
- `entrypoints/sidepanel/lib/scanHistory.ts` — `migrateScannedJobs()` clears risk scores stored before the posting stage produced a real score, so invented numbers are never displayed as findings. `updateScannedJob()` replaces a stored entry's whole `scanResult` once a later stage produces one
- `entrypoints/sidepanel/views/ScamScanView.tsx` — Job scanning with progress streaming; follows up with `/api/verify` when an employer was named and `/api/analyze-offer` when one was not. `isOnline` prop disables the Scan button. Owns the evidence-promotion layout described below
- `entrypoints/sidepanel/views/ResumeMatchView.tsx` — Resume analysis + job matching with progress; `isOnline` prop disables Match and the resume uploader
- `entrypoints/sidepanel/components/shell/OfflineBanner.tsx` — "Server Unreachable" strip below the top app bar with a Retry button
- `entrypoints/sidepanel/components/scan/OfferAnalysisCard.tsx` — Verdict for offers that name no employer: what it asks, what it offers, what to check
- `entrypoints/sidepanel/components/scan/VerificationSection.tsx` - External verification cards, the search-unavailable notice, and the clickable sources list
- `entrypoints/sidepanel/components/scan/VerificationCard.tsx` - Per-category status card. **`yellow` is amber, deliberately, and it used to be a neutral grey** (`bg-outline/10`) — a 10% grey wash on an already-grey surface, which is an absent colour rather than a weak one, and `yellow` is the most common status the panel produces. It was never the accent `secondary`, which is #4ade80 in the dark theme, byte-identical to the positive status. Amber collides with the `moderate` level, so the scope limit matters: the gauge's *unverified* ring stays **grey**, because "nothing was measured" and "searched and could not confirm" are different claims. That rule lives in `RiskGauge.tsx` and is covered there by a real render test.
- `entrypoints/sidepanel/components/scan/CompanyNameNeeded.tsx` - The prompt shown when a posting names no employer; its dashed border is what separates a missing input from a finding
- `entrypoints/sidepanel/lib/riskDisplay.ts` — `isUnverifiedEmployer()` and `shouldElevateEvidence()`; the two pure decisions the scan panel's layout turns on
- `entrypoints/sidepanel/lib/riskAccent.ts` - Token-based risk colour for chrome (headers, borders, button). Never returns a hex or hsl literal; body prose deliberately has no entry
- `entrypoints/sidepanel/lib/useFlipReorder.ts` — FLIP animation so promoted blocks travel to their new position instead of jumping
- `UNFINISHED-WORK.md` — **Read this first in a new session.** Canonical list of what is known-incomplete, the manual output-quality checklist, and the reasoning-model notes.
- `backend/app/services/search.py` � Tavily web search. One function, `search(query) -> SearchOutcome`, plus the company-name helpers (`extract_company_name`, `clean_company_name`, `is_valid_company_name`) the scan resolves the employer through.   **`build_queries()` issues two queries per verification: a `registration certificate` variant, then a `reviews complaints` variant.** One query cannot serve all three categories. `Philippines` is appended to both, and **the employer name is used verbatim — no part of it is rewritten.**

  **The corporate-suffix strip is gone, and it was wrong.** A trailing Corporation/Corp/Inc/Co/LLC used to be removed on the reasoning that a generic legal form dilutes a rare name. For a Philippine employer that is backwards: an SEC filing, a city PESO listing, and the employer's own legal pages are all titled with the *legal* name, so stripping it left the distinctive part competing against a brand, its franchisees, and unrelated products sharing the word. Searching `"Jollibee Foods"` is a worse lookup than `"Jollibee Foods Corporation"`. `_strip_corporate_suffix` and `build_query` are deleted rather than left dormant, since a stripper left in the module is a trap for the next reader. `TestQueryBuildingMovedOut` in `test_search.py` is the tombstone; `test_multi_query.py` owns the query tests.

  **Company Existence no longer has its own query.** It was the original single query, and it starved "Official Registration" by *ranking*, not by absence: `"<company> Philippines"` ranks the employer's own site and job boards first, and those pages prove existence without stating a registration number, so a PESO or SEC listing sat below them. No `max_results` value fixes ranking. Existence is now inferred from the other two searches — a company with a filing, a rating page, or a published complaint is found by one of them. **The traded cost is real and recorded in `test_multi_query.py`:** an employer with neither a filing nor any review is found by neither query and reports yellow on existence, which is the smallest employers, the ones this product exists for.

  **The registration query names no specific registry.** Naming SEC would reintroduce the failure the category was widened to fix: a company holding a DTI, PEZA, BOI, or LGU permit is registered, and an SEC-only query would not surface it. `test_multi_query.py` asserts no query names SEC, DTI, or PEZA.

  **`reviews complaints` is a deliberate decision, and `scam` and `fraud` remain banned.** The ban is on terms that name a *conclusion*, because a query carrying one makes its results look like corroboration of the accusation it already embedded. `reviews` and `complaints` name *documents* — a rating the employer can respond to, and an adverse record someone published — and the category is about what a result states. The residual exposure is aggregator pages that re-publish complaint text against a scraped company name, which is why the prompt's same-entity rule and its requirement that `red` name a source are load-bearing here. The prompt's `yellow is the default` instruction is also what makes Reputation read as inert, since the existence query never surfaced adverse pages for it.

  **Results merge into one flat list for one AI call**, so the cost is two requests, not two model calls. `merge_results()` dedupes on canonical URL (`_canonical_url()` drops the scheme, `www.`, query, and trailing slash) keeping the higher-scoring copy, sorts by score, and caps at `TAVILY_MAX_RESULTS * 2`. Dedupe is not tidiness: the employer's own site appears in both result sets, and every result is prompt text competing for a budget shared with the model's reasoning. **No category heading is applied to the merged list** — stamping the registration query's results with a REGISTRATION heading is exactly the bug `format_results` was written to prevent.

  **`search_partial` is the state one search never had.** With one query, either it worked or it did not. With two, one can fail while the other succeeds: the findings are real but some categories were checked by a thinner search than the others. `ok` is true (there *is* usable data), `search_partial` is true, and `VerificationSection` says "N of M searches failed … this is not a finding about the employer". Reporting plain `ok: true` would overstate coverage; reporting a total failure would discard a search that worked. Both queries failing is still the existing `search_ok: false` state. Note that failures are collected as `(query, error)` pairs, not queries — `search_error` carries the *reason*, and putting the query there once reported "Acme Philippines" to the user in place of "TAVILY_API_KEY is not configured".

  **`SearchOutcome.ok` and `.results` are independent, and that is the whole point.** `ok=False` with no results means the search failed; `ok=True` with no results means the company has no online footprint. The previous module returned `[]` for both, so a throttled query was indistinguishable from a clean company and the model reported "nothing found" when the truth was "we could not look". Never collapse these two states. A missing `TAVILY_API_KEY` is a **failure**, not an empty success, so a broken deployment cannot look like a clean employer.

  **No retries, no fallback provider, no caching, no engine rotation.** The old DuckDuckGo module was 620 lines of policy layered on scraping, and the failures were the policy's fault rather than the provider's. One call, one outcome, reported honestly.

  **No category headings in the prompt.** The old `format_verification_context()` stamped each result with the category whose query had found it, which asserted something retrieval never established — a regulator's complaint form under a `[SCAM REPORTS]` heading read as a scam report. `format_results()` emits a flat list with URLs and the model judges each result. This is also why the query carries no `SEC`/`scam`/`hiring` tokens: asking for that text biases retrieval toward it and manufactures the appearance of evidence the prompt then has to be careful not to trust.

  **Relevance is a ranking problem, so fix it with ranking.** A small Philippine employer's SEC filing, city PESO listing, and JobStreet page are well covered by a browser search from the Philippines but only thinly by Tavily's own crawl index, so a niche name falls through to whatever that index holds strongly — a London VC firm, or an unrelated product with a similar word. `search()` therefore sends `country="philippines"` and `search_depth="advanced"`. `country` is a **boost**; `include_domains` is a **filter** and must stay unset, since restricting the result set to named domains would discard exactly the job boards and PESO pages the boost exists to surface — the job here is to fact-check a company, and the sites that fact-check it are the ones a whitelist cannot name in advance. Tavily does offer `include_domains_mode: "prefer"`, which searches the listed domains *and* the rest of the web; it is not used, because it still requires naming domains up front, and the boost exists precisely so a deployment need not predict which sites will mention a small Philippine employer. Advanced depth costs 2 credits against basic's 1, halving the 1,000/month free budget — the deliberate trade for a niche lookup. `include_answer` is never set: a synthesised answer is retrieval's opinion, not evidence, and the prompt requires source URLs copied from the results.

  **The credit knobs are env values, not constants.** `TAVILY_SEARCH_DEPTH` (`basic` | `advanced`, default basic) and `TAVILY_COUNTRY` (default `philippines`, blank disables the boost) live in `backend/.env`, because the recall-versus-budget trade is a deployment decision and should not require a code change. An unrecognised depth logs an error and falls back to advanced rather than being sent: the provider would reject it, and a rejected search is reported to the user as a company that cannot be looked up, so a typo in a cost setting must never become a verdict. A blank country is dropped from the request rather than sent as `""`. **The default is `basic` because there are now two queries per verification** — 2 × basic = 2 credits, which is exactly what one advanced request cost before the split. Setting `advanced` now doubles the price to 4 per verification, which is not obvious from the knob's own name.

  **`TAVILY_EXCLUDE_DOMAINS` is a different lever from `include_domains`, and the difference is the entire reason it is allowed.** `include_domains` restricts the result set to a whitelist and so would discard the very pages the country boost exists to surface; it stays unset. `exclude_domains` *removes named pages* from an otherwise unfiltered set, so it does not conflict — a domain is dropped by name, not everything outside it.

  **The default list is `wikipedia.org` and nothing else, and that is an evidence rule rather than a noise rule.** A crowd-edited entry is unattributed and often wrong about a company, and the panel is required to state facts about a named employer with a source behind each one; a citation nobody can trace back to whoever asserted it is not defensible. Every other entry is a deployment decision, made when a domain has actually been seen displacing a real source — SEO farms and scrapers that hijack a company name are the usual case, and each one removed is a result the verification prompt no longer gets to judge. `test_the_default_list_keeps_the_sources_the_boost_targets` exists because the obvious overcorrection (excluding the job boards and PESO sites) would spend the recall the boost buys on getting rid of it.

  `_parse_domains()` takes a comma- or whitespace-separated value and normalises each entry to a bare host. `_normalise_domain()` strips a scheme, a `www.`, and any path or query, because Tavily matches on the host: `https://www.Example.com/jobs` as a filter would silently exclude nothing while still looking configured, which is worse than an error. A leading `*.` is preserved, since flattening it would widen what gets dropped. Entries without a dot are discarded, so a stray word in a `.env` cannot become a domain Tavily rejects — the same typo-becomes-a-verdict failure the depth fallback exists to prevent. A blank value is dropped from the request rather than sent as `[]`.

  **Credits are per request, not per result, so every other recall lever is free.** `max_results`, `chunks_per_source`, `country`, `exclude_domains`, and `include_domains_mode` all change what comes back at the same 1-or-2 credit cost. Only `search_depth` moves the price, and only a second `POST /search` adds another charge — the API takes a single `query` per request, so "several queries" means several requests, and the documented sub-query pattern would have tripled the monthly verification count on a 1,000-credit budget. It is also the wrong shape for this product: the query is deliberately unadorned so no category bias is introduced, and three queries' worth of chunks would crowd out a reasoning model already sharing `AI_MAX_TOKENS` with its own answer.

  **A recruiter is not the employer.** The scan's employer field is `EMPLOYER NAME:` and the rules require the company the reader would work for, with a staffing agency named only when the posting is for the agency's own staff. A joined name reaches `clean_company_name()` as `Vikings / Silvergreen Manpower Services Corporation`, and a search engine tokenises the slash into neither entity, so it is split and the last part is looked up. The parser accepts `COMPANY NAME` as well so scans recorded before the rename still parse.

  **Result text is untrusted input.** A search snippet is whatever a page said, and it can read like an instruction or assert a green status. `VERIFY_PROMPT.md`'s `OUTPUT RULES` say so explicitly and require a result to concern the same entity as the company being verified — a common-word name returns a mixed bag. `format_results()` labels the block as data and strips `===` from result text so a page cannot forge the block terminator and append its own findings. Do not remove any of the three.
- `backend/VERIFY_PROMPT.md` — Verification system prompt. **This file is what the backend loads**; the in-module copy is a fallback. `scanner/verification_prompt.py` also owns `VERIFY_RESPONSE_SCHEMA`, the three category/weight definitions, and the search-context formatters.
- `backend/app/routers/scan.py` — Compatibility facade for all API endpoints + SSE streaming helpers; `/api/verify` includes raw AI response logging
- `backend/app/services/scanner/` — Modular prompts, SSE, scan, resume, match, parsing, risk, and verification workflows
- `backend/app/services/lm_client.py` — OpenAI-compatible client (OpenRouter). `chat_stream_pieces` logs and raises `EmptyModelResponse` when a stream yields no content, because a mid-stream provider error frame (rate limits included) arrives inside a successful 200 and is otherwise indistinguishable from an empty answer. `_create_completion` sends OpenRouter's `reasoning` parameter and falls back once if the provider rejects it. See **Reasoning Models** below.
- **A parameter rejection arrives as a 404, not only a 400.** `_rejected_param` recognises two shapes. A provider-issued rejection is a 400 naming the parameter. An *unroutable* one is a 404 — `'No endpoints found that can handle the requested parameters'`, `failed_routing_step: Filter by Parameters` — which is what a model with no schema-capable endpoint produces, and the more common of the two. The 404 branch was missing entirely, so a scan that succeeded on a new model took `/api/verify` down with it, since only verify sends `response_format`. The status alone is not enough to match on: a 404 is also what a mistyped `MODEL_NAME` returns, and treating that as a capability gap would report the wrong problem, so the message markers are required and a genuine 404 still propagates. When the message does not name the parameter, the culprit is worked out from what has already been dropped, `_ROUTING_FALLBACK_ORDER` trying `structured` first (it travels with `provider.require_parameters`, the flag that makes routing strict) and `reasoning` last. `verification_parser` then reads the plain-text response, so a model without structured output degrades rather than fails. `test_lm_param_fallback.py` uses the real error body from a failing deployment, and covers the 404, the genuine-404, the 429, and the give-up path.
- `backend/app/services/scanner/verification_prompt.py` — Loads `VERIFY_PROMPT.md` (keeping a full fallback copy); owns the request prompt, the response schema, and the search-context formatters. Asks for exactly three categories, forbids inventing a fourth, and treats search results as untrusted data that must concern the company being verified
- `backend/app/services/scanner/offer_prompt.py`, `offer_parser.py`, `offer_flow.py` — Post-only analysis for offers naming no employer; its own endpoint and parser so it cannot break the scan or verify paths
- `backend/app/services/scanner/risk_calculator.py` — Two-stage scoring. `final = min(100, posting_score + verification_penalty)`, where the posting stage counts the indicators the scan reported (high 40, mid 12, low 4, capped 100) and the verification stage is a **penalty that only `red` contributes to**, weighted 40/25/35 by category.
- **The two stages are additive and asymmetric: verification can only raise the number, never lower it.** This replaced a 60/40 blend, and the blend was wrong in a way that inverted the meaning of the score. A posting that had already maxed out — three high-severity flags, 100 — was pulled to **60** by a clean employer record, because averaging lets corroborating evidence outvote the thing the reader asked about. A published scam report then added only 14 points over that clean record, so **negative evidence moved the number far less than the absence of it**. And "we found nothing at all" scored 100, tying "three damming categories". What an employer record establishes is that a company exists, is registered, and has what published about it — none of which makes an advance-fee posting less dangerous. `test_risk_model.py` pins each of these.
- **A blend was the wrong shape, and so would have been subtraction.** The instinct that verification should be able to pull a bad posting down is sound; deducting for a clean employer record is not. It can reach zero on a posting that demands an advance fee — the worst failure this product can have — "green reduces" is incoherent per category (green on Reputation can be a one-star employee account), and subtraction rewards an employer with no online footprint, making unverifiable look safer.
- **`yellow` carries no weight, which is a change from the blend.** It used to count for half, because something had to pull a blend's average down. Added to a posting it would penalise a check that found nothing, so it now contributes zero and an unconfirmed or verified-clean employer leaves the posting's own number untouched. `green` is zero for a stronger reason: green means a result stated a fact, not that the fact was reassuring. The all-yellow short-circuit to `(None, None)` is unchanged. The three category-weighing tests in `test_verify.py` and `test_scanner_package.py` probe the weight with **red** items for this reason — a yellow would score 0 for every label and could not tell the registration weight apart from the default of 10, so those tests would have passed without guarding the rename at all.
- **A missing stage is absent, not zero.** A posting that could not be looked up is not penalised for the failed lookup, and a posting with no indicators is not raised by a clean employer record.
- `backend/app/config.py` — Settings via pydantic-settings, loads from `backend/.env`. A blank `AI_REASONING_ENABLED` reads as unset rather than raising: `.env.example` ships that key blank and tells the reader to leave it blank, which a bare `bool | None` cannot parse, so a fresh copy used to crash at import. Only blank is coerced — `maybe` still raises, because silently treating nonsense as unset would leave reasoning at the provider default while the operator believed they had set it. `test_env_example.py` parses the shipped example and asserts every model field appears in it, since nothing else in the repo executes that file.
- `backend/app/core/auth.py` — Client key validation (`require_client_key` dependency)
- `backend/app/rate_limit.py` — Rate limiting with proxy-safe IP detection (X-Forwarded-For/X-Real-IP)
- `backend/app/ai_limiter.py` — Concurrency control (semaphore + queue depth)

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/scan` | POST | Scan job posting image (SSE stream) |
| `/api/scan-text` | POST | Scan job posting text (SSE stream) |
| `/api/analyze-resume` | POST | Parse resume into structured data (SSE stream) |
| `/api/match-resume` | POST | Match resume against job postings (SSE stream) |
| `/api/verify` | POST | External verification via Tavily + AI (SSE stream) |
| `/api/analyze-offer` | POST | Post-only analysis for offers naming no employer (SSE stream) |
| `/health` | GET | Reachability probe; no client key required, rate limited to 30/minute |

All endpoints return `text/event-stream` with progress events (`percent`, `stage`) and a final `result` event.

`/api/scan` and `/api/scan-text` assess **offers of work or income**, not just
formatted job adverts. Chat messages, forwarded paragraphs, and recruitment
pitches are in scope; `VALID: false` means the content offers no work or income
at all.

**Verification flow:** After a successful scan, the backend adds `verification_context` to the scan response only if a company name was extracted. The name comes from the scan's own `COMPANY NAME:` field, preferred over the `extract_company_name()` regex fallback. If no company name is found, `verification_context` is absent and the frontend never calls `/api/verify`; it calls `POST /api/analyze-offer` instead, which assesses the offer on its own terms and returns a verdict. Either path produces a score; the employer check only ever adds to one. The `/api/verify` endpoint logs the raw AI response and parsed results for debugging.

## System Prompts

| Prompt | Used By | Loaded By |
|---|---|---|
| `SYSTEM_PROMPT.md` | Job scan (scan, scan-text) | `load_system_prompt()` in `prompts.py` |
| `VERIFY_PROMPT.md` + `VERIFY_RESPONSE_SCHEMA` | External verification (/api/verify) | `load_verify_prompt()` in `scanner/verification_prompt.py` |
| `RESUME_PROMPT.md` | Resume analysis | `load_resume_prompt()` in `prompts.py` |
| `MATCH_PROMPT.md` | Resume-job matching | `load_match_prompt()` in `prompts.py` |

All four prompt files are in `backend/` root, resolved via `Path(__file__).resolve().parents[3]`.

**`VERIFY_PROMPT.md` is the source of truth, and the module keeps a full fallback copy.** The prose used to be a constant in `verification_prompt.py`, which meant editing a prompt meant editing Python. It moved because this is the longest prompt and its rules are the libel guardrail, so it needs to be readable and diffable in a text file. `_FALLBACK_VERIFY_PROMPT` is kept complete rather than reduced to a role line: a deployment shipping without the file must not verify against a stub. **The two can drift** — that is the known risk, and `test_verify_prompt_file.py` asserts they currently agree, re-asserts the guardrails against the file the backend loads, and checks the loader follows the file rather than the constant. `VERIFY_SYSTEM_PROMPT = load_verify_prompt()` is evaluated at import, so editing the file needs a restart, exactly as with the other three.

The verify prompt asks for exactly three categories: **Company
Existence** (weight 40), **Official Registration** (25), and **Reputation** (35).
"Company Name" and "Online Presence" were removed as redundant — the scan
already establishes whether a name was present, and the endpoint cannot run at
all without one — and "Scam Reports" + "Social Reputation" were merged into
Reputation. Fewer categories means fewer searches and less invented detail.

**Registration is not the same as the SEC.** The category was `SEC Registration`
until a test showed a company holding a DTI/PEZA/BOI/LGU registration being
reported as inconclusive. It is now `Official Registration`, and the prompt names
SEC, DTI, PEZA, BOI, a local government unit business permit and government portal
listings as equally valid. Scoring "no SEC number" against a company that has a
DTI registration is a false negative that made the card useless rather than
merely cautious. `risk_calculator` maps the legacy `SEC Registration` label to the
same weight, and `verification_parser._LEGACY_LABELS` keeps stored results from
logging a phantom missing category.

**Each check returns the fact and its source, not a 20-word summary.** The old
`detail` cap discarded almost everything retrieval found: roughly 3,000
characters of results became three details of at most 20 words. The schema now
carries `finding` (the one fact that decided the status, uncapped),
`source_title` and `source_url` (copied exactly from the provided results, never
constructed), plus a top-level `evidence` list the panel renders as clickable
sources. This is the only channel by which online evidence reaches the user, so
a fabricated URL here is a fabricated citation.

`verification_parser.py` splits the response into per-`VERIFY` blocks and
extracts `STATUS` and `DETAIL` from each independently, rather than matching the
whole shape in one regex — a single missing `END VERIFY` used to make one match
span two blocks and swallow a category. It is now the **fallback** parser, used
only when the provider does not honour structured output.

**Both structured prompts must state the output format in prose as well as in the
schema.** `VERIFY_SYSTEM_PROMPT` and `ANALYZE_OFFER_SYSTEM_PROMPT` each carry an
`OUTPUT FORMAT:` line naming their keys, because a model with no schema-capable
endpoint drops the schema (see the 404 fallback in `lm_client.py`) and the prompt
is then the only thing specifying the shape. Without that line the model writes
prose, `_parse_json` finds nothing, and the panel renders empty cards with no
Sources, no report, and no recommendation — **silently, because the request
itself succeeded**. Their "plain sentences only" rules are scoped to the values
for that reason. `test_verify_unschemaed.py` covers the schema-less path.

`verification_flow`
logs `[verify] Parsed N of 3 expected categories; missing: ...` so a partial parse
is never silent. `risk_calculator`'s weight table knows the three canonical labels
plus the legacy `SEC Registration`; any other legacy label such as "Scam Reports"
parses and renders but falls back to the default weight.

## Structured Output

`/api/verify` and `/api/analyze-offer` use OpenRouter's `response_format` with a
JSON Schema instead of a labeled text format. The custom text format existed
because the native model web search broke on curly braces; searches now run in
the backend and the model only reads the results, so structured output is safe.

- `chat()` takes an optional `response_format`. `_structured_output_body(schema, name)`
  builds the `json_schema` envelope with `strict: true` and
  `provider.require_parameters: true`. **That provider flag matters for a `:free`
  model**, which can route to an endpoint that does not support structured
  outputs and answer with prose instead.
- A strict schema must list every property in `required` and set
  `additionalProperties: false`, or the provider rejects the request.
- If the provider rejects `reasoning` or `response_format`, `_create_completion`
  drops that parameter, logs the rejection, and never sends it again. A 429 or an
  unrelated 400 propagates. The one-time `[lm] Generation config in use:` line
  reports `structured_output` and `dropped_params`.
- The JSON schema constrains the *shape* only, never the wording. Every rule
  about what may be claimed still lives in the prompt prose.
- `/api/scan`, `/api/scan-text`, `/api/analyze-resume`, and `/api/match-resume`
  still use labeled text. They stream, and the scan path relies on
  `_VALID_LINE_RE` finding `VALID: false` mid-stream to stop early; JSON would
  have to be buffered whole, giving that up.

## Prompt Rules (libel guardrail)

These are not stylistic preferences — they keep the product from asserting things
it cannot support, which is the legal exposure for the project.

- **Observational only.** Every statement must trace to the input. Unknowns are declared, never inferred. All four prompts carry an `OUTPUT RULES` block saying so.
- **Never accuse.** No prompt may describe a named company or person as a scam, fraud, or criminal — only what a posting asks for or what a search result states.
- **No hedging, no absolutes.** Banned inference words (likely, appears, suggests, probably…) and banned absolutes (always, never, definitely, 100%).
- **Absence is never `red`.** In verification, `red` requires a provided search result that actually states a negative, and the `DETAIL` must name that source. "Not found" is `yellow`. See `risk_calculator.py`, which weights `yellow` at half.
- **The scan prompt's field rules live in `SYSTEM_PROMPT.md` only.** `SCAN_OUTPUT_FORMAT` is the bare format skeleton. They were once duplicated into the user message, which is wasted context and gives a reasoning model more to deliberate over. `OUTPUT_RULES` and `SCAN_FIELD_RULES` in `prompts.py` now build only `FALLBACK_SYSTEM_PROMPT`, so the two copies can still drift; nothing enforces that yet (see `UNFINISHED-WORK.md`).
- **The employer name is stated, not inferred.** The scan outputs a dedicated `EMPLOYER NAME:` field, and `scan_flow` prefers it over the regex fallback. Asking the model to state the name in prose and then regexing a sentence out of the summary is what produced unrelated search keywords. `clean_company_name()` rejects "Not stated" and other placeholders, and drops a leading article so "The company" is judged on the word after it.
- **The recommendation is addressed to a job seeker, not an auditor.** The field rule must name its reader. Without that, the model — steeped in the prompt's own SEC/DTI/PEZA vocabulary — hands the reader a registry lookup: "Confirm the registration number on the SEC site" is technically actionable and practically useless, because nobody applying for a job queries a government portal. The rule says to build on what the results showed and give one step from an ordinary hiring exchange, and forbids naming a registry, a government website, or a permit check. `RETRIEVAL_FAILED` needs the same treatment: it is read as an instruction, so it tells the reader to hold off on money or personal details rather than to "confirm the employer through an official channel".
- **A prompt may contradict itself, and the severity list is where it hides.** `SYSTEM_PROMPT.md` once offered "low: something like a missing employer name" as an example while a later bullet banned flagging a missing employer — the model followed the example, and low severity scores 4 in `risk_calculator`. A long prompt drifts, so any rule stated in a *list of examples* must be restated as an explicit prohibition at the point of use. `test_severity_list_never_offers_a_missing_name_as_an_example` parses the severity block by indentation and inspects only the text after each severity's colon, so a line may name the phrase to forbid it but not offer it as an example.
- **A prohibition with no matching permission is a dead end, and that is how a task-scam DM scored low risk.** The severity ladder is anchored on the *employer demanding something* — money, goods, a deposit, a purchase. A "do this task and then earn a reward" DM asks for no payment, so nothing matched, and the only things marking it as not-a-job were the absences the prompt forbids flagging. The model had a prohibition and no permission, which is why it regressed across models rather than being a weak-model problem. **`task-for-earning` is now a named pattern with a concrete element** — discrete tasks, orders, or referrals completed for payment rather than a role with duties — plus a `mid` severity example, because `mid` previously carried exactly one example and anything else fell back to `low` (which scores 4). **The fix is a positive anchor, not an enumeration of flaggable things**, which would be a whitelist wearing different clothes: the next scam shape would be invisible to it. Two guards are load-bearing alongside it. The element must be text the posting *contains* (the unit of work), never the reader's ignorance of a role, or the absence-flag bug returns. And work-followed-by-payment must be stated as the ordinary order, because "do the task, then get paid" reads as the reverse of work-before-money and most jobs are paid that way — without that sentence, every job posting becomes flaggable. `TestTaskForEarningIsFlaggable` checks all three against **both** prompt copies.

## Environment Variables

**Extension** (root `.env`):
- `WXT_API_BASE` — Backend URL (e.g. `https://traba-hero-production.up.railway.app`)
- `WXT_CLIENT_KEY` — Shared secret for backend auth; must match `CLIENT_SECRET_KEY` in `backend/.env`

**Backend** (`backend/.env`):
- `AI_API_KEY` — OpenRouter API key
- `AI_API_URL` — AI provider URL (e.g. `https://openrouter.ai/api/v1`)
- `MODEL_NAME` — Model ID (e.g. `deepseek/deepseek-flash-latest`)
- `AI_MODEL_SCAN`, `AI_MODEL_VERIFY` — Optional per-endpoint model overrides, blank by default and falling back to `MODEL_NAME`. The scan wants prose in a labelled format; `/api/verify` and `/api/analyze-offer` want a JSON object matching a schema, and only some models have an endpoint OpenRouter can route that to. `Settings.resolve_model()` treats blank and an unrecognised endpoint name as unset, because an empty model ID is itself a 404. This is an optimisation, not the fix for a model that cannot do structured output — see the 404 fallback in `lm_client.py`.
- `AI_TEMPERATURE`, `AI_TOP_P`, `AI_MAX_TOKENS` — Generation controls. **`AI_MAX_TOKENS` was ignored by four of the five endpoints** until `resolve_max_tokens()` replaced the hardcoded literals at the call sites; they were all set to the same value as the default, which is what hid it. `AI_MAX_TOKENS_SCAN` / `AI_MAX_TOKENS_VERIFY` override it per endpoint (the offer call follows verify — both request schema-enforced JSON), and anything that is not a positive integer reads as unset so a typo costs answer length rather than becoming a provider rejection.
- `AI_REASONING_ENABLED`, `AI_REASONING_MAX_TOKENS`, `AI_REASONING_EFFORT` — Reasoning-model controls, mapped to OpenRouter's normalized `reasoning` parameter. `AI_REASONING_ENABLED=false` turns reasoning off outright and is the cleanest option; blank/blank/0 sends nothing. See Reasoning Models.
- `AI_MAX_CONCURRENT`, `AI_MAX_QUEUE_DEPTH` — Concurrency limits
- `CLIENT_SECRET_KEY` — Shared secret for extension auth; leave empty to disable (dev mode)
- `TAVILY_API_KEY` - Tavily search key; free tier is 1,000 credits/month, no card (https://tavily.com)
- `TAVILY_MAX_RESULTS` - Results requested per verification (default: 4). Free in credits — cost is per *request* — but every snippet is prompt text for a model sharing `AI_MAX_TOKENS` with its own reasoning, so raise it only if you raise that.
- `TAVILY_SEARCH_DEPTH` (`basic` | `advanced`, default **basic**) and `TAVILY_COUNTRY` (default `philippines`, blank disables the boost) — the recall-versus-budget trade. A verification runs **two** queries, so `basic` costs 2 credits per verification and `advanced` costs 4.
- `TAVILY_EXCLUDE_DOMAINS` — comma- or space-separated domains to drop from the result set. Defaults to `wikipedia.org` (crowd-edited and unattributed, so not a defensible source); a blank value excludes nothing. Removes named pages rather than restricting the search to a whitelist, so it does not conflict with the country boost. Each entry is normalised to a bare host; entries without a dot are dropped.

## Reasoning Models

`MODEL_NAME` may point at a reasoning model, which changes how a request fails.
Deliberation is drawn from the same `max_tokens` budget that has to hold the
answer, so a long think can consume the whole budget and return **nothing**.
`chat_stream_pieces` and `chat` both detect this and raise `EmptyModelResponse`
naming the model, `finish_reason`, and the reasoning character count, instead of
handing an empty string to a parser.

An empty response has three causes, all previously indistinguishable:
a mid-stream provider error frame, a model refusal, and reasoning-only output.
The log now names which one.

Three ways to stop the budget being eaten, best first. All map to OpenRouter's
normalized `reasoning` parameter and are off unless set:

- **`AI_REASONING_ENABLED=false` turns reasoning off entirely.** This is the
  cleanest option and the one to try first. It overrides the other two, because a
  provider rejects a disabled reasoning combined with a high effort level, so
  sending them together would risk a 400 for no benefit.
- **`AI_REASONING_EFFORT=low`** reduces the thinking at the source. The scan
  completes at `AI_MAX_TOKENS=2048` with this.
- **`AI_REASONING_MAX_TOKENS=N`** only truncates it, and a truncated reasoning
  phase can make a provider re-attempt, so it is the weakest of the three.

Note that `exclude: true` is *not* a way to save tokens — it only hides the
reasoning from the response while still paying for it.

Not every model supports disabling reasoning. If the provider rejects the
parameter, `_create_completion` retries once without it, logs
`[lm] Provider rejected the reasoning parameter`, and stops sending it for the
rest of the process. The one-time `[lm] Generation config in use:` line records
the config actually in force — grep for it when a failure happens.

Keep `AI_MAX_TOKENS` above the reasoning budget. Lowering it guarantees the
failure it is meant to prevent.

When counting reasoning characters for your own diagnosis, note that some
providers mirror the same text into both `reasoning` and `reasoning_content`.
The counter counts an identical pair once; a failure reporting exactly double
the previous figure is the instrumentation, not the model.

## Design System

See `DESIGN.md` for the full design system: colors (light/dark themes), typography, spacing, elevation, shapes, components, and Tailwind configuration. Use semantic tokens (`bg-background`, `text-on-surface`) — never raw hex values.

## Conventions

- **WXT globals**: `defineBackground()`, `defineContentScript()` are auto-imported by WXT — do NOT import them
- **Chrome APIs**: Use `// @ts-ignore` for `chrome.sidePanel`, `chrome.storage` in extension context
- **Tailwind theming**: Colors use CSS variables (`var(--color-*)`) defined in `assets/tailwind.css`. Use semantic tokens like `bg-background`, `text-on-surface`, not raw hex
- **Custom fonts**: `font-headline` (Hanken Grotesk), `font-body`/`font-label` (Inter)
- **Tactile shadows**: Use `tactile-card`, `tactile-btn-gold` for 3D button/card effects
- **TypeScript**: `tsconfig.json` extends `.wxt/tsconfig.json` (auto-generated by `wxt prepare`)
- **Logging**: All AI stream functions use `[endpoint]` prefix in logs (e.g. `[scan-text]`, `[analyze-resume]`, `[match-resume]`)

## Gotchas

- `wxt prepare` runs on `postinstall` — generates `.wxt/` directory with tsconfig and types
- `.wxt/` and `.output/` are gitignored — never commit them
- `WXT_API_BASE` is a build-time variable — restart `npm run dev` after changing `.env`
- `WXT_CLIENT_KEY` must match `CLIENT_SECRET_KEY` in `backend/.env` — also a build-time variable
- OpenRouter model IDs have no `~` prefix — the `~` in the UI copy snippet is decorative
- Backend prompt files are in `backend/` root, NOT the project root
- `python -m pytest tests/ -v` is fully offline and should stay under a few seconds; if it suddenly takes tens of seconds, a test has started reaching the network
- `ai_verified` reasoning scripts I wrote as throwaway probes were deleted after use — the cases they covered belong in the suite, not in scratch files
- No lint/format commands configured — `npm run compile` (types) and `npm test` (vitest) are the only gates
- **`happy-dom` performs no flex layout and zeroes every `getBoundingClientRect()`.** Visual position, FLIP animation, and ring glow cannot be asserted in a unit test; assert the class or order value that produces the effect instead, and say so in the test's docstring. `@testing-library/user-event` is not installed — use `fireEvent`, as the existing tests do.
- **Mutation-check a change in both directions.** A test that still passes after you deliberately break the production code was testing nothing. Check the *overcorrection* too: `order-last` and `order-3` both "keep the action bar at the bottom", and only one is right.
- `Select-String -Path "dir\**\*.py"` does **not** recurse in PowerShell and silently reports nothing found. It once produced a false "this field is never populated" conclusion. Grep or read the file before concluding a symbol is unwired.
- A `Set-Content` round-trip can normalise an em dash to a hyphen, which turns a mutation into a silent no-op. Print whether the substitution actually changed the file before trusting the result.
- Dark mode is toggled via `document.documentElement.classList.toggle('dark')` — Tailwind uses `darkMode: 'class'`

## Filter Categories (ResumeMatchView)

| Filter | Icon | Condition |
|---|---|---|
| All | `work` | Always shown |
| Verified | `verified` (green) | `riskLevel === 'low'` AND `isJobPosting` |
| Unverified | `info` (neutral) | `riskLevel === null` — excluded from matching |
| Moderate | `warning` (amber) | `riskLevel === 'moderate'` |
| High/Critical | `shield_person` (red) | `riskLevel === 'high'` OR `riskLevel === 'critical'` |

Risk scores (0-100): Low (0-30), Moderate (31-50), High (51-75), Critical (76-100), computed in `risk_calculator.py`. High/Critical jobs are excluded from resume matching.

A job's score always exists. It is built in two stages and **summed** in
`_combine_scores` as `min(100, posting + verification_penalty)`. Verification is
asymmetric: it can only raise the number.

- **Posting stage (always runs).** `_posting_risk_from_flags` counts the
  indicators the scan actually reported — high 40, mid 12, low 4, capped at 100.
  This depends on nothing but the posting, so an offer that names no employer,
  or one that cannot be looked up, still gets a verdict.
- **Employer stage (only when a name exists).** `_calculate_risk_score_from_verify`
  is a **penalty** that only `red` contributes to, weighted 40/25/35 by category.
  It returns `(None, None)` when every item is `yellow` — the search confirmed
  nothing either way, so it contributes nothing at all. `green` also contributes
  nothing: it means a result stated a fact, not that the fact was reassuring.
- A missing stage is **absent, not zero**. A posting that could not be looked up
  is not penalised for the missing lookup, and a posting with no reported
  indicators is not raised by a clean employer record.

Never synthesise a score from the red-flag count in the client. The number the
panel shows is computed in `risk_calculator.py` and sent in `score_breakdown`,
which records which stages contributed. Presenting a number the system never
measured is the exact exposure the prompt rules exist to prevent.

## Evidence Promotion (ScamScanView)

A high or critical score reorders the results so the evidence leads:

```
Normal:        Gauge → Posting Analysis → Job Summary → [shots] → [Red Flags · Offer · Verification]
High/Critical: Gauge → [Red Flags · Offer · Verification] → Posting Analysis → Job Summary → [shots]
```

- **A high/critical score moves the reader's answer to their first question.** They open a panel wanting to know why it is dangerous, and the flags and the employer check are what say so. Everything else is context for after that decision.
- **`shouldElevateEvidence()` waits for the level to settle.** The scan returns a posting-stage score that verification then adds a penalty to, so a posting can read "high" and settle at "critical". Promoting on the intermediate value would move the evidence out from under the reader and put it back a moment later. `verificationLoading` and `offerAnalysisLoading` both gate it. A *failed* verification still promotes, because the posting stage's score is real.
- **Both groups stay mounted; `order` on the flex parent decides which leads.** Unmounting to reorder would give FLIP nothing to animate and would reset a collapsed Sources disclosure on every score change. `display: contents` is the trap here: it looks like the tidier way to drop a wrapper, but it generates no box and `order` has no effect on a box that does not exist.
- **`order` reorders every sibling, not just the pair.** An element with no order value sorts at `0`, so the groups on `order-1`/`order-2` pushed the `sticky bottom-0` action bar above the results. It carries `order-3` and the capture preview `order-4`. `order-last` is not the fix — a later sibling swaps with it.
- **`useFlipReorder` animates the move, both directions.** A fade cannot express a reorder: the content dissolves and reappears elsewhere, which reads as a glitch. Skipped under `prefers-reduced-motion`, matching `.ring-pulse`.
- **Colour is chrome, not prose.** `riskAccent()` tints headers, borders, and the primary button. Body prose has no entry on purpose: long blocks of red or amber on a light surface are the hardest thing on the panel to read, and this is where someone reads a verdict carefully enough to act on it. The accent is temporary by construction — it rides on the displayed result, which `resetAll()` already clears when a new element is picked, so there is no timer.
- **Tests assert the mechanism, not the pixels.** `happy-dom` performs no flex layout and zeroes every rect, so `ScamScanView.elevate.test.tsx` asserts the `order-*` and accent classes. The FLIP delta arithmetic is unit-tested separately, and whether the animation *looks* fluid is not verified by the suite.

## Verification Guardrails

- If no company name is extracted from the job posting, `verification_context` is absent from the scan response
- The frontend renders `CompanyNameNeeded` instead of the verification section when `isValidJob && !companyName`
- **A missing employer is a missing input, not a finding.** It is deliberately not a red flag: it contradicted the "never flag the absence of something" rule in the same prompt list, and it added risk-score weight for an input we lacked rather than for something wrong with the post. The panel asks the reader for the name instead.
- `CompanyNameNeeded` is styled with a **dashed** border where every result container uses a solid one, so a missing input cannot be misread as a finding. It states what was and was not checked, and says explicitly that it is not a warning about the post — a fact about our own output rather than a claim about how common nameless posts are.
- **Scans are always screenshots** (`ScamScanView` calls `/api/scan`; `scanTextStream` is exported but has no caller), so this state is never about a missing image. It is about the captured region not containing a logo, letterhead or sender name.
- There is **no text input** for the company name. A typed name would flow straight into the verification prompt, which produces a verdict naming a real company; guidance only, by decision.
- **The risk gauge shows "Unverified" instead of "0 / Low Risk", for a nameless post with no red flags.** The posting stage scores 0 when a post raises no indicators, and "Low Risk" would claim the post was cleared when the employer was never checked at all. `isUnverifiedEmployer()` in `sidepanel/lib/riskDisplay.ts` derives this from `isJobPosting && !companyName && redFlags.length === 0`; the gauge renders the same empty-ring shape as an unscored result so no figure is displayed that was not measured. A red flag is real evidence about the post, so it is scored on severity instead, and a named employer is verified normally. The unverified ring is the neutral `outline` grey, **not** amber: amber is the `moderate` level, and borrowing it would read as a mid risk score rather than an unchecked one.
- **Every ring breathes.** `.ring-pulse` in `assets/tailwind.css` animates a `drop-shadow` whose colour comes from a per-ring `--ring-glow-color`, so one keyframe serves every risk level and the unverified state. The scored ring sets it to its level colour and the unverified ring to the outline grey. It is decoration, so it is disabled under `prefers-reduced-motion: reduce`. It replaced a static inline `filter`, which conflicted with the keyframe.
- **POSTING ANALYSIS must not contain "scam", "legitimate", "suspicious", "genuine", "fraudulent" or "honest".** The ban appears in the field rule itself, not only in the prompt preamble, because a long prompt drifts and the field rule is what the model weights when writing the verdict. It also gives the allowed phrasing — describe what the posting asks for, not what it is. A verdict naming a post a scam is the libel exposure the whole prompt rule set exists to prevent.
- `/api/verify` logs raw AI response and parsed items at INFO/WARNING level for debugging
- `extract_company_name()` in `search.py` runs every pattern over the text as zero-width lookaheads and trims each capture at the first clause boundary, so "Acme Corp. We are hiring" does not become a company name. Evaluate new patterns against that rule — a greedy capture that runs into the next sentence produces a name the search cannot resolve, which then looks like an unverifiable company.

## Offline Mode

- `useBackendHealth()` is the single source of truth for reachability and is mounted once in `App.tsx`; views receive `isOnline` as a prop (default `true`)
- Poll cadence is 4s (~15 requests/min) to stay under the backend's `30/minute` limit on `GET /health`; probes are skipped while `document.hidden` and never overlap
- `isOnline` starts `true` and flips false only after 2 consecutive failed probes — never surface a false offline banner from one slow response
- The first successful probe restores online state, so the banner clears itself on recovery; the Retry button only forces an immediate check
- Offline disables network actions only (Scan, Match, resume upload). Element picking, cropping, and scan history stay usable because they are local-only
- In-flight scans are **not** aborted when the backend drops; they keep their existing 240s/300s timeouts

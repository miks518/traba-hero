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

- The default test suite must be fully offline: never make live OpenRouter/LLM, DuckDuckGo, SEC, or other external API calls.
- Mock external services at their module boundaries before invoking endpoints; use deterministic fake responses and fixtures.
- Tests that only check authentication, routing, parsing, or streaming must still mock AI and search dependencies.
- Treat provider credits and external-service quotas as test resources; local verification must not spend them.
- **Never run anything that calls the AI provider without explicit permission**, including throwaway probe scripts, smoke tests against a live server, and a "quick" manual check. The key is shared and hitting the limit blocks the human developer's own testing for 24 hours. Write mock data and use the offline suite instead.
- Never run live-provider tests through `python -m pytest tests/ -v`; put them behind an explicit opt-in command or environment flag.
- **This is enforced, not just documented.** `backend/tests/conftest.py` installs an autouse `_offline_ai_and_search` fixture that fakes every AI/search entry point, plus a session-scoped `_block_external_dns` guard that raises `ExternalNetworkBlocked` on any non-loopback DNS resolution. `backend/tests/test_offline_suite.py` asserts both. A valid-client-key request therefore returns the fake payload, never a provider response.
- The frontend suite mocks at the `lib/api` module boundary (`vi.mock`); no test touches `fetch` directly.

## Key Architecture

- `entrypoints/background.ts` — Opens sidepanel on toolbar click
- `entrypoints/content.tsx` — Element picker overlay for screenshot capture
- `entrypoints/sidepanel/` — Main React app (views, components, types)
- `entrypoints/sidepanel/lib/api.ts` — HTTP client → `backend URL`; sends `X-Trabahero-Client-Key` header on all requests; `pingHealth()` is the `GET /health` reachability probe
- `entrypoints/sidepanel/hooks/useBackendHealth.ts` — polls `/health` every 4s, flips `isOnline` false after 2 consecutive failures, re-probes on `visibilitychange`
- `entrypoints/sidepanel/lib/imageUtils.ts` — Screenshot compression (JPEG 0.8, max 1280px on the long edge). The cap is a token-budget knob as much as a bandwidth one: vision cost scales with pixel area, and the configured model is a reasoning model, so visual input is also what it deliberates over. Raise it only if dense small print starts scanning badly.
- `entrypoints/sidepanel/lib/scanHistory.ts` — `migrateScannedJobs()` clears risk scores stored before the posting stage produced a real score, so invented numbers are never displayed as findings
- `entrypoints/sidepanel/views/ScamScanView.tsx` — Job scanning with progress streaming; follows up with `/api/verify` when an employer was named and `/api/analyze-offer` when one was not. `isOnline` prop disables the Scan button
- `entrypoints/sidepanel/views/ResumeMatchView.tsx` — Resume analysis + job matching with progress; `isOnline` prop disables Match and the resume uploader
- `entrypoints/sidepanel/components/shell/OfflineBanner.tsx` — "Server Unreachable" strip below the top app bar with a Retry button
- `entrypoints/sidepanel/components/scan/OfferAnalysisCard.tsx` — Verdict for offers that name no employer: what it asks, what it offers, what to check
- `entrypoints/sidepanel/components/scan/VerificationSection.tsx` — External verification cards + the "Analysis Only" notice shown when no employer was named
- `UNFINISHED-WORK.md` — **Read this first in a new session.** Canonical list of what is known-incomplete, the manual output-quality checklist, and the reasoning-model notes.
- `backend/app/services/search.py` � Tavily web search. One function, `search(query) -> SearchOutcome`, plus the company-name helpers (`extract_company_name`, `clean_company_name`, `is_valid_company_name`) the scan resolves the employer through. `build_query(company)` is the only query shape issued: `"{company} Philippines"`.

  **`SearchOutcome.ok` and `.results` are independent, and that is the whole point.** `ok=False` with no results means the search failed; `ok=True` with no results means the company has no online footprint. The previous module returned `[]` for both, so a throttled query was indistinguishable from a clean company and the model reported "nothing found" when the truth was "we could not look". Never collapse these two states. A missing `TAVILY_API_KEY` is a **failure**, not an empty success, so a broken deployment cannot look like a clean employer.

  **No retries, no fallback provider, no caching, no engine rotation.** The old DuckDuckGo module was 620 lines of policy layered on scraping, and the failures were the policy's fault rather than the provider's. One call, one outcome, reported honestly.

  **No category headings in the prompt.** The old `format_verification_context()` stamped each result with the category whose query had found it, which asserted something retrieval never established — a regulator's complaint form under a `[SCAM REPORTS]` heading read as a scam report. `format_results()` emits a flat list with URLs and the model judges each result.

  **A recruiter is not the employer.** The scan's employer field is `EMPLOYER NAME:` and the rules require the company the reader would work for, with a staffing agency named only when the posting is for the agency's own staff. A joined name reaches `clean_company_name()` as `Vikings / Silvergreen Manpower Services Corporation`, and a search engine tokenises the slash into neither entity, so it is split and the last part is looked up. The parser accepts `COMPANY NAME` as well so scans recorded before the rename still parse.

  **Result text is untrusted input.** A search snippet is whatever a page said, and it can read like an instruction or assert a green status. `VERIFY_SYSTEM_PROMPT`'s `OUTPUT RULES` say so explicitly and require a result to concern the same entity as the company being verified — a common-word name returns a mixed bag. `format_results()` labels the block as data and strips `===` from result text so a page cannot forge the block terminator and append its own findings. Do not remove any of the three.
- `backend/app/routers/scan.py` — Compatibility facade for all API endpoints + SSE streaming helpers; `/api/verify` includes raw AI response logging
- `backend/app/services/scanner/` — Modular prompts, SSE, scan, resume, match, parsing, risk, and verification workflows
- `backend/app/services/lm_client.py` — OpenAI-compatible client (OpenRouter). `chat_stream_pieces` logs and raises `EmptyModelResponse` when a stream yields no content, because a mid-stream provider error frame (rate limits included) arrives inside a successful 200 and is otherwise indistinguishable from an empty answer. `_create_completion` sends OpenRouter's `reasoning` parameter and falls back once if the provider rejects it. See **Reasoning Models** below.
- `backend/app/services/scanner/verification_prompt.py` — Verification system prompt and request prompt; asks for exactly three categories, forbids inventing a fourth, and treats search results as untrusted data that must concern the company being verified
- `backend/app/services/scanner/offer_prompt.py`, `offer_parser.py`, `offer_flow.py` — Post-only analysis for offers naming no employer; its own endpoint and parser so it cannot break the scan or verify paths
- `backend/app/services/scanner/risk_calculator.py` — Two-stage scoring: posting indicators, employer verification, and the 60/40 blend
- `backend/app/config.py` — Settings via pydantic-settings, loads from `backend/.env`
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
| `SYSTEM_PROMPT.md` | Job scan (scan, scan-text) | `load_system_prompt()` |
| `VERIFY_SYSTEM_PROMPT` + `VERIFY_RESPONSE_SCHEMA` | External verification (/api/verify) | `scanner/verification_prompt.py` |
| `RESUME_PROMPT.md` | Resume analysis | `load_resume_prompt()` |
| `MATCH_PROMPT.md` | Resume-job matching | `load_match_prompt()` |

All prompts are in `backend/` root, resolved via `Path(__file__).resolve().parents[2]`.

The `VERIFY_SYSTEM_PROMPT` asks for exactly three categories: **Company
Existence** (weight 40), **SEC Registration** (25), and **Reputation** (35).
"Company Name" and "Online Presence" were removed as redundant — the scan
already establishes whether a name was present, and the endpoint cannot run at
all without one — and "Scam Reports" + "Social Reputation" were merged into
Reputation. Fewer categories means fewer searches (4, down from 8) and less
invented detail. The prompt explicitly forbids inventing a separate category.

`verification_parser.py` splits the response into per-`VERIFY` blocks and
extracts `STATUS` and `DETAIL` from each independently, rather than matching the
whole shape in one regex — a single missing `END VERIFY` used to make one match
span two blocks and swallow a category. It is now the **fallback** parser, used
only when the provider does not honour structured output. `verification_flow`
logs `[verify] Parsed N of 3 expected categories; missing: ...` so a partial parse
is never silent. Note that `risk_calculator`'s weight table only knows the three
canonical labels; a legacy label such as "Scam Reports" parses and renders but
falls back to the default weight.

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
- **The employer name is stated, not inferred.** The scan outputs a dedicated `COMPANY NAME:` field, and `scan_flow` prefers it over the regex fallback. Asking the model to state the name in prose and then regexing a sentence out of the summary is what produced unrelated search keywords. `clean_company_name()` rejects "Not stated" and other placeholders, and drops a leading article so "The company" is judged on the word after it.

## Environment Variables

**Extension** (root `.env`):
- `WXT_API_BASE` — Backend URL (e.g. `https://traba-hero-production.up.railway.app`)
- `WXT_CLIENT_KEY` — Shared secret for backend auth; must match `CLIENT_SECRET_KEY` in `backend/.env`

**Backend** (`backend/.env`):
- `AI_API_KEY` — OpenRouter API key
- `AI_API_URL` — AI provider URL (e.g. `https://openrouter.ai/api/v1`)
- `MODEL_NAME` — Model ID (e.g. `deepseek/deepseek-flash-latest`)
- `AI_TEMPERATURE`, `AI_TOP_P`, `AI_MAX_TOKENS` — Generation controls
- `AI_REASONING_ENABLED`, `AI_REASONING_MAX_TOKENS`, `AI_REASONING_EFFORT` — Reasoning-model controls, mapped to OpenRouter's normalized `reasoning` parameter. `AI_REASONING_ENABLED=false` turns reasoning off outright and is the cleanest option; blank/blank/0 sends nothing. See Reasoning Models.
- `AI_MAX_CONCURRENT`, `AI_MAX_QUEUE_DEPTH` — Concurrency limits
- `CLIENT_SECRET_KEY` — Shared secret for extension auth; leave empty to disable (dev mode)
- `TAVILY_API_KEY` - Tavily search key; free tier is 1,000 credits/month, no card (https://tavily.com)
- `TAVILY_MAX_RESULTS` - Results requested per verification (default: 8)

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

A job's score always exists. It is built in two stages and blended in
`_combine_scores`, with the posting carrying 60% and external verification 40%:

- **Posting stage (always runs).** `_posting_risk_from_flags` counts the
  indicators the scan actually reported — high 40, mid 12, low 4, capped at 100.
  This depends on nothing but the posting, so an offer that names no employer,
  or one that cannot be looked up, still gets a verdict.
- **Employer stage (only when a name exists).** `_calculate_risk_score_from_verify`
  weights verification items. It returns `(None, None)` when every item is
  `yellow` — the search confirmed nothing either way. Summing half-weights there
  produced a constant ~49 "Moderate Risk" that measured the search, not the
  posting. Absence of evidence produces no score.
- A missing stage is **absent, not zero**. A posting that could not be looked up
  is not penalised for the missing lookup, and a posting with no reported
  indicators is not raised by a clean employer record.

Never synthesise a score from the red-flag count in the client. The number the
panel shows is computed in `risk_calculator.py` and sent in `score_breakdown`,
which records which stages contributed. Presenting a number the system never
measured is the exact exposure the prompt rules exist to prevent.

## Verification Guardrails

- If no company name is extracted from the job posting, `verification_context` is absent from the scan response
- Frontend checks `data.verification_context?.company_name` before calling `/api/verify`
- If missing, `VerificationSection` renders a neutral "Analysis Only" notice stating the findings come only from the posting, and points the user at the part of the page that names the employer
- `/api/verify` logs raw AI response and parsed items at INFO/WARNING level for debugging
- `extract_company_name()` in `search.py` runs every pattern over the text as zero-width lookaheads and trims each capture at the first clause boundary, so "Acme Corp. We are hiring" does not become a company name. Evaluate new patterns against that rule — a greedy capture that runs into the next sentence produces a name the search cannot resolve, which then looks like an unverifiable company.

## Offline Mode

- `useBackendHealth()` is the single source of truth for reachability and is mounted once in `App.tsx`; views receive `isOnline` as a prop (default `true`)
- Poll cadence is 4s (~15 requests/min) to stay under the backend's `30/minute` limit on `GET /health`; probes are skipped while `document.hidden` and never overlap
- `isOnline` starts `true` and flips false only after 2 consecutive failed probes — never surface a false offline banner from one slow response
- The first successful probe restores online state, so the banner clears itself on recovery; the Retry button only forces an immediate check
- Offline disables network actions only (Scan, Match, resume upload). Element picking, cropping, and scan history stay usable because they are local-only
- In-flight scans are **not** aborted when the backend drops; they keep their existing 240s/300s timeouts

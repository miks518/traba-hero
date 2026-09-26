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
- Never run live-provider tests through `python -m pytest tests/ -v`; put them behind an explicit opt-in command or environment flag.
- **This is enforced, not just documented.** `backend/tests/conftest.py` installs an autouse `_offline_ai_and_search` fixture that fakes every AI/search entry point, plus a session-scoped `_block_external_dns` guard that raises `ExternalNetworkBlocked` on any non-loopback DNS resolution. `backend/tests/test_offline_suite.py` asserts both. A valid-client-key request therefore returns the fake payload, never a provider response.
- The frontend suite mocks at the `lib/api` module boundary (`vi.mock`); no test touches `fetch` directly.

## Key Architecture

- `entrypoints/background.ts` — Opens sidepanel on toolbar click
- `entrypoints/content.tsx` — Element picker overlay for screenshot capture
- `entrypoints/sidepanel/` — Main React app (views, components, types)
- `entrypoints/sidepanel/lib/api.ts` — HTTP client → `backend URL`; sends `X-Trabahero-Client-Key` header on all requests; `pingHealth()` is the `GET /health` reachability probe
- `entrypoints/sidepanel/hooks/useBackendHealth.ts` — polls `/health` every 4s, flips `isOnline` false after 2 consecutive failures, re-probes on `visibilitychange`
- `entrypoints/sidepanel/lib/imageUtils.ts` — Screenshot compression (JPEG 0.8, max 1920px)
- `entrypoints/sidepanel/views/ScamScanView.tsx` — Job scanning with progress streaming + async verification trigger; `isOnline` prop disables the Scan button
- `entrypoints/sidepanel/views/ResumeMatchView.tsx` — Resume analysis + job matching with progress; `isOnline` prop disables Match and the resume uploader
- `entrypoints/sidepanel/components/shell/OfflineBanner.tsx` — "Server Unreachable" strip below the top app bar with a Retry button
- `entrypoints/sidepanel/components/scan/VerificationSection.tsx` — External verification cards + missing company name guardrail (red "Unable to Verify" banner)
- `backend/app/services/ddg_search.py` — DuckDuckGo search with rate limiting, `extract_company_name()` for company name extraction
- `backend/app/routers/scan.py` — Compatibility facade for all API endpoints + SSE streaming helpers; `/api/verify` includes raw AI response logging
- `backend/app/services/scanner/` — Modular prompts, SSE, scan, resume, match, parsing, risk, and verification workflows
- `backend/app/services/lm_client.py` — OpenAI-compatible client (OpenRouter) with tool calling support
- `backend/app/services/ai_tools.py` — Tool schema definitions + execution dispatcher for verification
- `backend/app/services/scanner/verification_prompt.py` — Verification system prompt and request prompt; requires Company Name verification as the first category
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
| `/api/verify` | POST | External verification via DuckDuckGo + AI (SSE stream) |
| `/health` | GET | Reachability probe; no client key required, rate limited to 30/minute |

All endpoints return `text/event-stream` with progress events (`percent`, `stage`) and a final `result` event.

**Verification flow:** After a successful scan, the backend adds `verification_context` to the scan response only if a company name was extracted (via `extract_company_name()` or `company_data`). If no company name is found, `verification_context` is absent and the frontend never calls `/api/verify`, instead showing a red "Unable to Verify" warning banner. The `/api/verify` endpoint logs the raw AI response and parsed results for debugging.

## System Prompts

| Prompt File | Used By | Loaded By |
|---|---|---|
| `SYSTEM_PROMPT.md` | Job scan (scan, scan-text) | `load_system_prompt()` |
| `VERIFY_SYSTEM_PROMPT` | External verification (/api/verify) | Defined inline in `scan.py` |
| `RESUME_PROMPT.md` | Resume analysis | `load_resume_prompt()` |
| `MATCH_PROMPT.md` | Resume-job matching | `load_match_prompt()` |

All prompts are in `backend/` root, resolved via `Path(__file__).resolve().parents[2]`.

The `VERIFY_SYSTEM_PROMPT` requires the AI to verify **Company Name** as the first category. If the company name is missing or unclear from the original posting, it returns `red` for that category.

## Environment Variables

**Extension** (root `.env`):
- `WXT_API_BASE` — Backend URL (e.g. `https://traba-hero-production.up.railway.app`)
- `WXT_CLIENT_KEY` — Shared secret for backend auth; must match `CLIENT_SECRET_KEY` in `backend/.env`

**Backend** (`backend/.env`):
- `AI_API_KEY` — OpenRouter API key
- `AI_API_URL` — AI provider URL (e.g. `https://openrouter.ai/api/v1`)
- `MODEL_NAME` — Model ID (e.g. `deepseek/deepseek-flash-latest`)
- `AI_TEMPERATURE`, `AI_TOP_P`, `AI_MAX_TOKENS` — Generation controls
- `AI_MAX_CONCURRENT`, `AI_MAX_QUEUE_DEPTH` — Concurrency limits
- `CLIENT_SECRET_KEY` — Shared secret for extension auth; leave empty to disable (dev mode)
- `DDG_MAX_CONCURRENT` — Max concurrent DuckDuckGo searches (default: 2)
- `DDG_MIN_INTERVAL` — Min seconds between searches (default: 1.5)
- `DDG_MAX_PER_VERIFY` — Max searches per verification request (default: 10)

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
- No lint/format commands configured — `npm run compile` (types) and `npm test` (vitest) are the only gates
- Dark mode is toggled via `document.documentElement.classList.toggle('dark')` — Tailwind uses `darkMode: 'class'`

## Filter Categories (ResumeMatchView)

| Filter | Icon | Condition |
|---|---|---|
| All | `work` | Always shown |
| Verified | `verified` (green) | `riskLevel === 'low'` AND `isJobPosting` |
| Moderate | `warning` (amber) | `riskLevel === 'moderate'` |
| High/Critical | `shield_person` (red) | `riskLevel === 'high'` OR `riskLevel === 'critical'` |

Risk scores (0-100): Low (0-15), Moderate (16-45), High (46-75), Critical (76-100). High/Critical jobs are excluded from resume matching.

## Verification Guardrails

- If no company name is extracted from the job posting, `verification_context` is absent from the scan response
- Frontend checks `data.verification_context?.company_name` before calling `/api/verify`
- If missing, `VerificationSection` renders a red "Unable to Verify" banner with risk caution
- `/api/verify` logs raw AI response and parsed items at INFO/WARNING level for debugging
- `extract_company_name()` in `ddg_search.py` uses regex patterns to find company names; if it fails, verification is skipped silently (intentional guardrail)

## Offline Mode

- `useBackendHealth()` is the single source of truth for reachability and is mounted once in `App.tsx`; views receive `isOnline` as a prop (default `true`)
- Poll cadence is 4s (~15 requests/min) to stay under the backend's `30/minute` limit on `GET /health`; probes are skipped while `document.hidden` and never overlap
- `isOnline` starts `true` and flips false only after 2 consecutive failed probes — never surface a false offline banner from one slow response
- The first successful probe restores online state, so the banner clears itself on recovery; the Retry button only forces an immediate check
- Offline disables network actions only (Scan, Match, resume upload). Element picking, cropping, and scan history stay usable because they are local-only
- In-flight scans are **not** aborted when the backend drops; they keep their existing 240s/300s timeouts

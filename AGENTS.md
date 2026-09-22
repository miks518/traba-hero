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

## Key Architecture

- `entrypoints/background.ts` — Opens sidepanel on toolbar click
- `entrypoints/content.tsx` — Element picker overlay for screenshot capture
- `entrypoints/sidepanel/` — Main React app (views, components, types)
- `entrypoints/sidepanel/lib/api.ts` — HTTP client → `backend URL`; sends `X-Trabahero-Client-Key` header on all requests
- `entrypoints/sidepanel/lib/imageUtils.ts` — Screenshot compression (JPEG 0.8, max 1920px)
- `entrypoints/sidepanel/views/ScamScanView.tsx` — Job scanning with progress streaming + async verification trigger
- `entrypoints/sidepanel/views/ResumeMatchView.tsx` — Resume analysis + job matching with progress
- `entrypoints/sidepanel/components/scan/VerificationSection.tsx` — Traffic-light verification cards (async from /api/verify)
- `backend/app/routers/scan.py` — All API endpoints + SSE streaming helpers
- `backend/app/services/lm_client.py` — OpenAI-compatible client (OpenRouter) with tool calling support
- `backend/app/services/ddg_search.py` — DuckDuckGo search with rate limiting (replaces old web_search, brave_search, sec_api)
- `backend/app/services/ai_tools.py` — Tool schema definitions + execution dispatcher for verification
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
| `/api/verify` | POST | AI-driven external verification via DuckDuckGo tool calling (SSE stream) |

All endpoints return `text/event-stream` with progress events (`percent`, `stage`) and a final `result` event.

## System Prompts

| Prompt File | Used By | Loaded By |
|---|---|---|
| `SYSTEM_PROMPT.md` | Job scan (scan, scan-text) | `load_system_prompt()` |
| `RESUME_PROMPT.md` | Resume analysis | `load_resume_prompt()` |
| `MATCH_PROMPT.md` | Resume-job matching | `load_match_prompt()` |

All prompts are in `backend/` root, resolved via `Path(__file__).resolve().parents[2]`.

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
- No lint/format/test commands configured — only `npm run compile` for type checking
- Dark mode is toggled via `document.documentElement.classList.toggle('dark')` — Tailwind uses `darkMode: 'class'`

## Filter Categories (ResumeMatchView)

| Filter | Icon | Condition |
|---|---|---|
| All | `work` | Always shown |
| Verified | `verified` (green) | `status === 'legitimate'` AND `riskScore < 40` AND `isJobPosting` |
| Suspicious | `warning` (amber) | `status === 'suspicious'` OR `riskScore 40-69` |
| Risky | `shield_person` (red) | `status === 'scam'` OR `riskScore >= 70` |

Risky/Verified jobs are excluded from resume matching.

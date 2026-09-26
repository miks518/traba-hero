# Trabahero

Trabahero helps Filipino job seekers spot job scams. The extension sends screenshots and text to a FastAPI backend, which relays them to an AI model through OpenRouter to check postings for fraud signals.

## Features

- Scan job posting screenshots or pasted text for scam indicators.
- Match a resume with job openings and review skill gaps.
- Check company details with DuckDuckGo or the SEC Philippines API.

## Quick Start

### Prerequisites

| Tool | Install |
|---|---|
| Node.js ≥ 18 | https://nodejs.org |
| Python ≥ 3.10 | https://python.org |
| OpenRouter API key | https://openrouter.ai/keys |

### 1. Clone and install dependencies

```powershell
git clone https://github.com/miks518/traba-hero.git
cd traba-hero
npm install
npm run build
```

### 2. Set up the backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
```

### 3. Configure the AI provider

Open `backend/.env` and fill in three values:

1. `AI_API_KEY` — your key from https://openrouter.ai/keys
2. `AI_API_URL` — `https://openrouter.ai/api/v1` (already set in `.env.example`)
3. `MODEL_NAME` — a multimodal model ID from https://openrouter.ai/models

The system prompts (`SYSTEM_PROMPT.md`, `RESUME_PROMPT.md`, `MATCH_PROMPT.md`) live in `backend/` and are loaded by the backend at request time — nothing to paste anywhere.

### 4. Run the app

```powershell
# Terminal 1: Backend
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: Extension dev server (from project root)
npm run dev
```

Load the built extension in Chrome:

1. Open `chrome://extensions` and enable Developer mode.
2. Choose "Load unpacked" and select the `.output/` folder.

## Architecture

```
entrypoints/          # WXT browser extension (React 19 + TypeScript + Tailwind)
  background.ts       # Opens sidepanel on toolbar click
  content.tsx         # Element picker overlay
  sidepanel/          # Main React app
    views/            # ScamScanView, ResumeMatchView
    lib/api.ts        # HTTP client → localhost:8000
backend/              # FastAPI proxy for the AI provider (OpenRouter)
  app/routers/        # /api/scan, /api/analyze-resume, /api/match-resume, /health
  app/services/       # OpenAI-compatible AI client, web search, SEC API
```

## Commands

| Action | Command |
|---|---|
| Dev server | `npm run dev` |
| Build | `npm run build` |
| Typecheck | `npm run compile` |
| Extension tests | `npm test` |
| Backend dev | `cd backend && uvicorn app.main:app --reload` |
| Backend tests | `cd backend && python -m pytest tests/ -v` |

**Start order:** backend → extension

# Trabahero

Trabahero helps Filipino job seekers spot job scams. The extension sends screenshots and text to a local LM Studio model, which checks postings for fraud signals.

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
| LM Studio | https://lmstudio.ai |

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

### 3. Start LM Studio

1. Open LM Studio and go to the Discover tab.
2. Download Gemma 3 12B.
3. Open the Developer tab, load the model, and start the server on port 1234.
4. Paste the contents of `SYSTEM_PROMPT.md` into LM Studio's System Prompt field.

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
backend/              # FastAPI proxy for LM Studio
  app/routers/        # /api/scan, /api/analyze-resume, /api/match-resume
  app/services/       # LM Studio client, web search, SEC API
```

## Commands

| Action | Command |
|---|---|
| Dev server | `npm run dev` |
| Build | `npm run build` |
| Typecheck | `npm run compile` |
| Backend dev | `cd backend && uvicorn app.main:app --reload` |

**Start order:** LM Studio → backend → extension

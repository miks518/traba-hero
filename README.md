# Trabahero

A job-scam detection browser extension for Filipino job seekers. Uses local AI (LM Studio) to analyze job postings for fraud signals — no cloud API needed.

**Features:**
- Scan job posting screenshots or text for scam indicators
- Resume-to-job matching with skill gap analysis
- SEC Philippines company verification via DuckDuckGo + (optional) SEC API

## Quick Start

### Prerequisites

| Tool | Install |
|---|---|
| Node.js ≥ 18 | https://nodejs.org |
| Python ≥ 3.10 | https://python.org |
| LM Studio | https://lmstudio.ai |

### 1. Clone & install extension

```powershell
git clone https://github.com/miks518/traba-hero.git
cd traba-hero
npm install
npm run build
```

### 2. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
```

### 3. LM Studio

1. Open LM Studio → Discover tab → download a model (Gemma 3 12B recommended)
2. Load the model → Developer tab → Start Server (port 1234)
3. Paste `SYSTEM_PROMPT.md` content into LM Studio's System Prompt field

### 4. Run

```powershell
# Terminal 1: Backend
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: Extension dev server (from project root)
npm run dev
```

Or load the built extension manually:
1. Open `chrome://extensions` → Enable Developer mode
2. Click "Load unpacked" → select the `.output/` folder

## Architecture

```
entrypoints/          # WXT browser extension (React 19 + TypeScript + Tailwind)
  background.ts       # Opens sidepanel on toolbar click
  content.tsx         # Element picker overlay
  sidepanel/          # Main React app
    views/            # ScamScanView, ResumeMatchView
    lib/api.ts        # HTTP client → localhost:8000
backend/              # FastAPI thin proxy (no AI logic)
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

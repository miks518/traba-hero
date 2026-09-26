# Trabahero — Automated Setup Guide

> This document is designed for another agentic AI (or a human) to follow linearly. Each step must succeed before moving to the next.

---

## Prerequisites

Check these are installed before starting:

```powershell
node --version   # ≥ 18 (tested with 22)
python --version # ≥ 3.10 (tested with 3.12)
git --version    # any recent version
```

**Download & install** (if missing):

| Tool | URL |
|---|---|
| Node.js | https://nodejs.org (LTS) |
| Python | https://python.org (3.10+) |
| Git | https://git-scm.com |
| OpenRouter account | https://openrouter.ai (free tier available; API key required) |

---

## Step 1: Clone

```powershell
git clone https://github.com/miks518/traba-hero.git
cd traba-hero
```

---

## Step 2: Extension Setup

Run in the project root:

```powershell
npm install
```

> `postinstall` automatically runs `wxt prepare` — this generates `.wxt/tsconfig.json` required by TypeScript.

```powershell
npm run compile
```

> Runs `tsc --noEmit`. Must pass with zero errors. If it fails, double-check that `npm install` completed successfully (`.wxt/` directory must exist).

```powershell
npm run build
```

> Produces `./.output/` — the unpacked extension directory. This is what Chrome loads.

---

## Step 3: Backend Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Create `.env` (copy from example):

```powershell
Copy-Item .env.example .env
```

Verify the contents (defaults should work):

```ini
HOST=0.0.0.0
PORT=8000
AI_API_KEY=
AI_API_URL=https://openrouter.ai/api/v1
MODEL_NAME=
SEC_API_URL=https://gwwso2.sec.gov.ph/companyinformationlookup/1.0.0
SEC_API_KEY=
```

> `.env` lives **inside** `backend/`, not in the project root. The backend reads it from there automatically.
> `AI_API_KEY` and `MODEL_NAME` are filled in during Step 4. `SEC_API_KEY` is optional — company lookup still works without it.

Verify imports:

```powershell
.venv\Scripts\python -c "import openai, fastapi, uvicorn; print('Backend deps OK')"
```

Run the offline test suite (no live AI or search calls):

```powershell
.venv\Scripts\python -m pytest tests/ -v
```

Return to root:

```powershell
cd ..
```

---

## Step 4: OpenRouter Setup

This is the AI layer. The backend is a thin proxy — **all OCR, analysis, and web search tool calls** happen inside the model.

### 4.1 Get an API key

1. Sign in at https://openrouter.ai
2. Open https://openrouter.ai/keys and create a key
3. Copy it — it is shown only once

### 4.2 Choose a model

1. Browse https://openrouter.ai/models
2. Pick a **multimodal (vision-capable)** model — image scans send screenshots, so a text-only model will fail
3. Copy the exact model ID (e.g. `deepseek/deepseek-flash-latest`)
4. Note the price per million tokens; a scan consumes one multimodal request

### 4.3 Configure `backend/.env`

```ini
AI_API_KEY=sk-or-v1-...
AI_API_URL=https://openrouter.ai/api/v1
MODEL_NAME=deepseek/deepseek-flash-latest
```

> `MODEL_NAME` must match the provider's model ID exactly, including the `vendor/` prefix. There is no `~` prefix — the `~` in some UI copy is decorative.

### 4.4 Configure the client key

The extension authenticates to the backend with a shared secret. Set the same value in both places:

```ini
# backend/.env
CLIENT_SECRET_KEY=choose-a-long-random-string
```

```ini
# project root .env
WXT_API_BASE=http://localhost:8000
WXT_CLIENT_KEY=choose-a-long-random-string
```

> `WXT_API_BASE` and `WXT_CLIENT_KEY` are build-time variables — restart `npm run dev` after changing them. Leave `CLIENT_SECRET_KEY` empty to disable auth in local development only.

> The system prompts (`SYSTEM_PROMPT.md`, `RESUME_PROMPT.md`, `MATCH_PROMPT.md`) live in `backend/` and are loaded at request time. Nothing needs to be pasted into any external tool.

---

## Step 5: Start Everything

**Must follow this order:**

### 5.1 Backend

In a new terminal:

```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Wait for output:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 5.2 Extension

In a second terminal (or the root terminal):

```powershell
npm run dev
```

> This starts the WXT development server with hot-reload. The extension loads automatically into a Chrome instance if one is available, or you load it manually from `./.output/`.

---

## Step 6: Verification

### 6.1 Backend Health

```powershell
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

> The extension polls this endpoint every 4 seconds to detect backend reachability, so it is filtered out of the server access log.

### 6.2 Load Extension in Chrome

1. Open `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `./.output/` directory
5. Pin the Trabahero icon to the toolbar

### 6.3 Run a Scan

1. Navigate to any job posting website
2. Click the Trabahero toolbar icon → sidepanel opens
3. Click **Pick Element** → click on a job posting on the page
4. Wait for scan results

---

## File Reference

| File | Purpose |
|---|---|
| `backend/SYSTEM_PROMPT.md` | Job-scan system prompt, loaded by `load_system_prompt()` |
| `backend/RESUME_PROMPT.md` | Resume analysis prompt |
| `backend/MATCH_PROMPT.md` | Resume-to-job matching prompt |
| `backend/.env` | Backend configuration (copy from `backend/.env.example`) |
| `.env` | Extension build-time config (`WXT_API_BASE`, `WXT_CLIENT_KEY`) |
| `AGENTS.md` | Developer guide with commands, conventions, and gotchas |
| `CRITICAL.md` | Prioritized implementation roadmap and task status |
| `.output/` | Built extension (generated by `npm run build`) |
| `.wxt/` | WXT build artifacts (generated by `postinstall`) |

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `npm run compile` fails — `.wxt/` not found | `postinstall` didn't run | `npx wxt prepare` |
| `npm run compile` fails — type errors | Wrong TypeScript version | `npm install` again, check Node.js ≥ 18 |
| `python -m venv .venv` fails | Python not in PATH | Reinstall Python, check "Add to PATH" |
| `pip install` fails | Wrong Python (system Python, not venv) | Use `.venv\Scripts\pip` explicitly |
| Backend can't reach the AI provider | `AI_API_KEY` missing, invalid, or out of credit | Check `AI_API_KEY` in `backend/.env` and your key status at https://openrouter.ai/keys |
| Backend returns 401 | `CLIENT_SECRET_KEY` and `WXT_CLIENT_KEY` do not match | They must be identical; both are build/env-time values |
| Backend returns 502 | AI provider errored or rejected the request | Check the backend log for the provider's error body, then verify the key has credit |
| Backend returns 504 | Model too slow for the request | Pick a faster model or reduce `AI_MAX_TOKENS` |
| AI returns no usable output | `MODEL_NAME` is wrong or the model is not multimodal | Copy the exact ID from https://openrouter.ai/models; image scans need vision support |
| "Server Unreachable" banner in the panel | Backend is down or the extension points at the wrong URL | Confirm Step 5.1 is running and `WXT_API_BASE` matches; restart `npm run dev` after changing it |
| Scan returns "Invalid Content" | Selected element is not a job posting | Try selecting a different area of the page |
| Extension doesn't load in Chrome | Built with wrong config | Run `npm run build` first, reload extension |
| CORS error in console | Backend not running | Start the backend with uvicorn |
| `wxt` command not found | Dependencies not installed | Run `npm install` from project root |

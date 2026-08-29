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
| LM Studio | https://lmstudio.ai (latest) |

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
LM_STUDIO_URL=http://localhost:1234/v1
LM_STUDIO_API_KEY=lm-studio
MODEL_NAME=
SEC_API_URL=https://gwwso2.sec.gov.ph/companyinformationlookup/1.0.0
SEC_API_KEY=
```

> `.env` lives **inside** `backend/`, not in the project root. The backend reads it from there automatically.

Verify imports:

```powershell
.venv\Scripts\python -c "import openai, fastapi, uvicorn; print('Backend deps OK')"
```

Return to root:

```powershell
cd ..
```

---

## Step 4: LM Studio Setup

This is the AI layer. The backend is a thin proxy — **all OCR, analysis, and web search tool calls** happen inside the model.

### 4.1 Install & Launch

1. Download LM Studio from https://lmstudio.ai
2. Install and open it
3. Go to the **Discover** tab and download a model that supports tool calling. Recommended:
   - **Gemma 3 12B** — best quality, needs ~8 GB VRAM
   - **Llama 3.2 3B** — lightweight, works on CPU
   - **Qwen 2.5 7B** — good tool use, balanced
   - **Mistral 7B** — solid all-rounder
4. Load the model (click the model name → "Load Model")
5. Go to the **Developer** tab
6. Click **Start Server** — ensure it runs on `http://localhost:1234` (the default port)

### 4.2 Configure System Prompt

LM Studio does not send system prompts via API automatically. You must paste it manually:

1. In LM Studio, open the **Server** configuration panel
2. Find the **System Prompt** field (may be under "Advanced" or "Server Config")
3. Open `SYSTEM_PROMPT.md` from the project root
4. Copy **only the content inside the triple backticks** (the actual prompt, not the markdown wrapper)
5. Paste into LM Studio's System Prompt field

### 4.3 (Optional) Configure Response Schema

LM Studio may support JSON schema enforcement for structured output:

1. In LM Studio's Server configuration, find the **Response Schema** or **JSON Schema** field
2. Open `response-schema.json` from the project root
3. Copy the entire file content
4. Paste into the schema field

> This is optional — the model is instructed via the system prompt to return JSON. The schema helps enforce the shape.

### 4.4 Verify

```powershell
curl http://localhost:1234/v1/models
```

Should return a JSON object with a `data` array containing at least one model.

---

## Step 5: Start Everything

**Must follow this order:**

### 5.1 LM Studio

Ensure the server is running on `http://localhost:1234`. Keep the window open.

### 5.2 Backend

In a new terminal:

```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Wait for output:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 5.3 Extension

In a third terminal (or the root terminal):

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
{"status":"ok","model":"<detected model name>"}
```

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
| `SYSTEM_PROMPT.md` | Instructions to paste into LM Studio's System Prompt field |
| `response-schema.json` | Expected JSON shape the model must return |
| `backend/.env` | Backend configuration (copy from `.env.example`) |
| `AGENTS.md` | Developer guide with commands, conventions, and gotchas |
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
| Backend can't connect to LM Studio | LM Studio not running | Open LM Studio, start server on port 1234 |
| Backend returns 502 | LM Studio not responding | Check `curl http://localhost:1234/v1/models` |
| Backend returns 504 | Model too slow / not loaded | Load a smaller model or reduce request size |
| LM Studio returns empty models list | No model loaded | Go to Discover tab, download + load a model |
| Scan returns "Invalid Content" | Selected element is not a job posting | Try selecting a different area of the page |
| Extension doesn't load in Chrome | Built with wrong config | Run `npm run build` first, reload extension |
| CORS error in console | Backend not running | Start the backend with uvicorn |
| `wxt` command not found | Dependencies not installed | Run `npm install` from project root |

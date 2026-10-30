# Deploying the Trabahero backend to Railway

The Chrome extension talks to this backend over HTTPS. The backend is **not**
inside the extension package — it is deployed separately, here.

Files added for this:
- `backend/Procfile` — start command
- `backend/railway.json` — Nixpacks build + start command + healthcheck
- `backend/.python-version` — pins Python 3.12

> **Important:** the start command is `uvicorn app.main:app --host 0.0.0.0 --port $PORT`,
> **not** `python -m app.main`. The module entrypoint runs with `reload=True`
> (a dev convenience), which you do not want on a host. Passing `$PORT`
> explicitly is required because bare uvicorn defaults to 8000 and ignores
> `backend/.env`.

---

## 1. Create the service

1. Railway → **New Project** → **Deploy from GitHub repo** → pick `miks518/traba-hero`.
2. Open the service → **Settings** → **Root Directory** → set it to **`backend`**.
   (This is what makes `app.main` importable.)
3. Railway auto-detects Python from `requirements.txt` and reads `backend/Procfile`
   / `backend/railway.json` for the start command and healthcheck.

## 2. Set environment variables

Service → **Variables** → add these. Values come from your local `backend/.env`.
**Never commit secrets.**

| Variable | Value / notes |
|----------|---------------|
| `AI_API_KEY` | Your provider key (OpenRouter etc.) — **required** |
| `AI_API_URL` | e.g. `https://openrouter.ai/api/v1` |
| `MODEL_NAME` | A **vision** model ID (image scans need vision) |
| `AI_MODEL_SCAN` | optional per-endpoint override (blank = `MODEL_NAME`) |
| `AI_MODEL_VERIFY` | optional per-endpoint override (blank = `MODEL_NAME`) |
| `TAVILY_API_KEY` | Tavily key (free tier = 1,000 credits/mo) — **required for employer verification** |
| `CORS_ALLOWED_ORIGINS` | `chrome-extension://hdmdhiojgdoomcjfhbkidbhkifmokkop` — **required, or the panel cannot read responses** |
| `TRUSTED_PROXIES` | `100.0.0.0/8` (Railway's proxy range). Blank = every caller shares one rate-limit bucket |
| `AI_REASONING_EFFORT` | `low` (recommended for reasoning models) |
| `AI_MAX_TOKENS` | `16384` |
| `SEARCH_PROVIDER` | `tavily` |
| `VERIFY_SEARCH_MODE` | `fixed` |

Do **not** set `PORT` or `HOST` — Railway injects `PORT`, and the app binds
`0.0.0.0` by default.

> `CORS_ALLOWED_ORIGINS` must match the **published** extension's ID. The ID is
> pinned by the public key in `wxt.config.ts` to
> `hdmdhiojgdoomcjfhbkidbhkifmokkop` for dev builds. If the Chrome Web Store
> assigns a different ID on first upload, update this value to match — the panel
> will otherwise show "Server Unreachable".

## 3. Add a domain and verify

1. Service → **Settings** → **Networking** → **Generate Domain**.
2. Confirm it is live:
   ```
   curl https://<your-domain>/health
   → {"status":"ok"}
   ```

## 4. Point the extension at it

Set the extension's build-time default and rebuild:

```
# E:\traba-hero\.env
WXT_API_BASE=https://<your-domain>
```

Then `npm run build` and re-upload the zip.

**Or, without rebuilding:** the extension now has a runtime override (Settings
page, added in `apiBase.ts` / `entrypoints/options/`). Open the extension's
**Settings** and set the Backend URL there — it is stored in
`chrome.storage.local` and takes effect immediately.

> Note: the manifest still lists `http://localhost:8010/*` in `host_permissions`.
> `<all_urls>` already covers the hosted origin, so requests work — but for the
> store build replace the localhost entry with your production origin for
> cleanliness.

## 5. Cost control

- Enable **App Sleeping** (Settings → scale to zero when idle) so memory is not
  billed while the service is unused — this is what keeps a small deployment
  inside the $5 Hobby credit.
- Set a **usage/spend cap** so it cannot overrun.
- Keep 1 replica at ~512 MB.

## Alternative: Render (free)

Root Directory `backend`, Start Command
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`, same env vars. Free tier
spins down after ~15 min idle (30–60s cold start).

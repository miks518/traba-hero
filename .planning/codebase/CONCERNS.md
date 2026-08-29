# Codebase Concerns — Backend Audit

**Analysis Date:** 2026-07-07

**Scope:** All Python files under `backend/`

---

## Structured Findings

### F-01 (HIGH) — Synchronous OpenAI client blocks ASGI event loop

**Description:** All three service files (`prefilter.py`, `ai_service.py`) create a synchronous `OpenAI` client (`from openai import OpenAI`) at module level and call `client.chat.completions.create()` inside `async def` functions. This is a blocking, synchronous I/O call that stalls the ASGI event loop. Under concurrent requests, every request waits for the previous AI call to finish. FastAPI/Uvicorn uses a single-threaded event loop per worker; a single blocking call blocks ALL requests in that worker.

**Files:**
- `backend/app/services/ai_service.py:46` — `completion = client.chat.completions.create(...)` in `analyze_job_post`
- `backend/app/services/ai_service.py:90` — same in `analyze_resume`
- `backend/app/services/ai_service.py:129` — same in `match_resume_to_jobs`
- `backend/app/services/prefilter.py:17` — same in `is_job_post`

**Fix:** Replace `from openai import OpenAI` with `from openai import AsyncOpenAI` in both files, change instantiation to `client = AsyncOpenAI(...)`, and `await` all `.create()` calls:
```python
from openai import AsyncOpenAI
client = AsyncOpenAI(base_url=settings.api_base_url, api_key=settings.api_key)
completion = await client.chat.completions.create(...)
```

---

### F-02 (HIGH) — Missing input size validation for base64 fields

**Description:** `ScanRequest.image_base64`, `TestAIRequest.image_base64`, and `ResumeAnalysisRequest.file_base64` are typed as `str` with no max-length constraint. A malicious or malformed client can send multi-megabyte base64 strings, causing:
- Memory exhaustion on the server when decoding (e.g., a 100MB base64 → ~75MB raw bytes)
- Triggering expensive AI API calls with huge payloads
- No early rejection before processing

**Files:**
- `backend/app/models/schemas.py:5` — `image_base64: str` (no max_length)
- `backend/app/models/schemas.py:26` — `image_base64: str | None = None` (no max_length)
- `backend/app/models/schemas.py:35` — `file_base64: str` (no max_length)

**Fix:** Add Pydantic `max_length` validation to limit payload size:
```python
from pydantic import BaseModel, Field

class ScanRequest(BaseModel):
    image_base64: str = Field(..., max_length=5_000_000)  # ~3.75MB raw
```

---

### F-03 (HIGH) — "no-key-required" fallback sends known-invalid API key

**Description:** Three locations pass `"no-key-required"` to the OpenAI client when `settings.api_key` is empty. This is not a valid OpenRouter API key. Instead of failing fast with a clear message, it sends a guaranteed-to-fail request and returns a confusing upstream error (e.g., `401 Unauthorized` or an HTML error page from OpenRouter). This pattern also breaks the "fail closed" security principle — the system should refuse to operate without a valid key.

**Files:**
- `backend/app/services/prefilter.py:12`
- `backend/app/services/ai_service.py:41`
- `backend/app/routers/scan.py:36`

**Fix:** Validate the API key at startup and raise immediately if missing:
```python
# In app/config.py or a startup check
if not settings.api_key:
    raise RuntimeError("OPENROUTER_API_KEY is not set in .env")
```
Remove the `if settings.api_key else "no-key-required"` pattern from all three files and pass `settings.api_key` unconditionally.

---

### F-04 (HIGH) — Duplicate OpenAI client initialization

**Description:** Both `prefilter.py` and `ai_service.py` create an identical module-level `OpenAI` client with the exact same configuration. This duplicates the connection pool and doubles the overhead. Additionally, changes to one (e.g., adding timeout config) must be manually replicated to the other.

**Files:**
- `backend/app/services/prefilter.py:10-13`
- `backend/app/services/ai_service.py:39-42`

**Fix:** Create a shared client factory or singleton in a common location (e.g., `app/services/__init__.py` or a new `app/services/client.py`):
```python
# backend/app/services/client.py
from openai import AsyncOpenAI
from app.config import settings

ai_client = AsyncOpenAI(
    base_url=settings.api_base_url,
    api_key=settings.api_key,
    timeout=60.0,
)
```
Both `prefilter.py` and `ai_service.py` import and reuse `ai_client` from this module.

---

### F-05 (MEDIUM) — JSON parse failures silently produce misleading responses

**Description:** When the AI returns malformed JSON (which happens frequently with LLM outputs), all three service functions degrade silently but produce misleading results:

- `analyze_job_post` (line 66): Returns `ScanResponse(valid=True, verdict_percentage=50, error=...)` — sets `valid=True` as a default, which means "this looks legitimate" when the AI actually failed. The error field is populated but callers (`scan.py` router) never check it; the response gets returned to the client as a successful scan.
- `analyze_resume` (line 101): Returns `ResumeData(summary="Failed to parse...")` — puts an error message inside a field intended for a prose summary.
- `match_resume_to_jobs` (line 140): Returns `[]` — the caller receives an empty match list indistinguishable from "no matches found."

**Files:**
- `backend/app/services/ai_service.py:66` — `valid=True` hardcoded on parse failure
- `backend/app/services/ai_service.py:101` — error message injected into `summary` field
- `backend/app/services/ai_service.py:140` — empty list returned, all errors lost

**Fix:** Return proper error responses instead of silent fallbacks:
```python
# For analyze_job_post — re-raise or return an explicit error model
raise AIServiceError(detail=f"AI returned invalid JSON: {raw[:200]}")
```
Or add a dedicated error field in the response model that callers MUST check. Never put `valid=True` when processing failed.

---

### F-06 (MEDIUM) — Bare `except Exception` in base64 decoder

**Description:** `decode_base64_image` wraps `base64.b64decode()` in a bare `except Exception` that catches absolutely everything, including `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`. This masks fatal errors and violates Python best practices.

**File:** `backend/app/services/image.py:11`

**Fix:** Catch only the specific exceptions that `b64decode` can raise:
```python
import binascii
# ...
try:
    return base64.b64decode(data)
except (ValueError, binascii.Error):
    raise ValueError("Invalid base64 image data")
```

---

### F-07 (MEDIUM) — Hardcoded `data:image/png;base64,` MIME type

**Description:** When constructing image URLs for the OpenAI API, the code always uses `data:image/png;base64,` as the prefix, even though:
1. The `decode_base64_image` function strips any existing `data:image/...` prefix generically
2. Screenshots captured via `chrome.tabs.captureVisibleTab` default to PNG, but it's not guaranteed
3. The `analyze_resume` function (line 82) correctly uses `data:image/{file_type};base64,` — showing the inconsistency

**Files:**
- `backend/app/routers/scan.py:48` — `f"data:image/png;base64,{req.image_base64}"`
- `backend/app/services/ai_service.py:53` — same hardcoded string

**Fix:** Detect or accept the MIME type. Either:
- Require callers to pass the MIME type alongside the base64 data
- Inspect the base64 header to determine image type (the existing `decode_base64_image` function already strips it — preserve the MIME type from the original `data:image/...` prefix)

---

### F-08 (MEDIUM) — No input validation on AI response `verdict_percentage`

**Description:** The `verdict_percentage` value from the AI's JSON response is used as-is without bounds checking. If the AI returns `150`, `-5`, or `"abc"`, it would be stored as-is or coerce to a potentially invalid value. The model says `"verdict_percentage": 0-100` but the LLM can and will deviate.

**File:** `backend/app/services/ai_service.py:70`

**Fix:** Clamp the value:
```python
raw_pct = parsed.get("verdict_percentage", 50)
verdict_percentage = max(0, min(100, int(raw_pct))) if isinstance(raw_pct, (int, float)) else 50
```

---

### F-09 (MEDIUM) — Inline imports inconsistent with codebase conventions

**Description:** Two files use function-scoped imports that break the project convention of module-level imports:

- `scan.py:32-33`: `from openai import OpenAI` and `from app.config import settings` inside `test_ai()`
- `ai_service.py:86`: `import base64` inside `analyze_resume()`

The `test_ai` function creates an entirely separate OpenAI client inline, duplicating the client initialization from `ai_service.py` and `prefilter.py`. Every call to `/api/test-ai` re-executes these imports and creates a new client, wasting resources.

**Files:**
- `backend/app/routers/scan.py:32-33`
- `backend/app/services/ai_service.py:86`

**Fix:** Move all imports to module level. For `test_ai`, either reuse the shared client (see F-04) or delete the endpoint if it's only for debugging (it uses a stale `/api/chat` endpoint convention; see F-14).

---

### F-10 (MEDIUM) — Private API import from slowapi

**Description:** `_rate_limit_exceeded_handler` is imported by its private (underscore-prefixed) name. Private APIs have no stability guarantees and may break on slowapi updates. There is no public alternative exposed by the library for this handler.

**File:** `backend/app/main.py:3`

**Fix:** Either vendor the handler locally (it's ~3 lines), pin slowapi to a specific version in `requirements.txt`, or write a custom handler:
```python
# Custom handler
from slowapi.errors import RateLimitExceeded
async def rate_limit_handler(request, exc):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
```

---

### F-11 (MEDIUM) — `analyze_resume` misidentifies file type when target URL still uses `image/png`

**Description:** In `analyze_resume` (ai_service.py:80), when `file_type` is in `("png", "jpg", "jpeg")`, it constructs `data:image/{file_type};base64,{file_base64}`. This correctly uses the dynamic file type. However, the `ScanRequest` (scan.py:48) and `analyze_job_post` (ai_service.py:53) always hardcode `image/png` — this is inconsistent with the `analyze_resume` pattern that got it right. Additionally, `file_type` values `"jpg"` and `"jpeg"` are accepted by `analyze_resume` but the `scan` endpoint has no equivalent file type handling.

**File:** `backend/app/services/ai_service.py:80`

**Note:** The `analyze_resume` function's handling is actually *correct* here — it's the other locations (F-07) that are wrong. This finding documents the inconsistency.

---

### F-12 (MEDIUM) — Redundant dictionary transformation for job matching

**Description:** The caller (`scan.py:74`) transforms `JobForMatch` Pydantic models into plain dicts:
```python
jobs_dict = [{"id": j.id, "title": j.title, "tags": j.tags} for j in req.jobs]
```
Then `match_resume_to_jobs` (ai_service.py:113-115) immediately re-iterates and rebuilds the same dicts:
```python
for j in jobs:
    jobs_data.append({"id": j["id"], "title": j["title"], "tags": j["tags"]})
```
This is an unnecessary O(n) pass that copies data identically.

**Files:**
- `backend/app/routers/scan.py:74`
- `backend/app/services/ai_service.py:113-115`

**Fix:** Pass the `jobs_dict` directly and remove the loop in `match_resume_to_jobs`. Or better, pass `list[JobForMatch]` directly to `match_resume_to_jobs` and access attributes instead of dict keys.

---

### F-13 (LOW) — Redundant `python-dotenv` in requirements.txt

**Description:** `pydantic-settings` already depends on `python-dotenv >= 0.21.0` for `.env` file loading. Listing `python-dotenv` separately in `requirements.txt` is redundant and could drift out of sync with the version required by `pydantic-settings`.

**File:** `backend/requirements.txt:6`

**Fix:** Remove `python-dotenv` from `requirements.txt`. It will be pulled in automatically as a transitive dependency of `pydantic-settings`.

---

### F-14 (LOW) — `/api/test-ai` endpoint uses stale/openai-direct pattern

**Description:** The `/api/test-ai` endpoint was presumably a debugging tool. It creates its own `OpenAI` client inline, bypassing the service layer entirely. The AGENTS.md notes "AiTestView.tsx uses the old `/api/chat` endpoint which no longer exists on the backend" — meaning this endpoint may have been renamed or replaced but the frontend still references the old path. The inline client initialization also lacks the async fix (F-01).

**File:** `backend/app/routers/scan.py:31-62`

**Fix:** Either:
- Delete `/api/test-ai` if it's unused (verify no frontend code calls it)
- Or refactor to use the shared `AsyncOpenAI` client and route through `ai_service.py`
- Update the frontend to match the actual endpoint URL

---

### F-15 (LOW) — `MatchRequest.jobs` defaults to empty list

**Description:** `jobs: list[JobForMatch] = []` means a valid request with no jobs produces a successful response with `matches: []`. This silently succeeds instead of returning a 422 validation error or a meaningful message. Callers may not realize they sent empty job data.

**File:** `backend/app/models/schemas.py:63`

**Fix:** Either remove the default to require at least one job, or add explicit validation:
```python
class MatchRequest(BaseModel):
    resume: ResumeData
    jobs: list[JobForMatch]  # no default — must be provided

    @field_validator("jobs")
    @classmethod
    def check_not_empty(cls, v):
        if not v:
            raise ValueError("At least one job is required")
        return v
```

---

### F-16 (LOW) — Health endpoint is superficial

**Description:** The `/health` endpoint only returns `{"status": "ok"}` with no verification that backend dependencies (AI provider reachability, API key validity) are actually functional. A "health" check that doesn't verify connectivity to the external AI service provides false confidence.

**File:** `backend/app/routers/health.py:8-11`

**Fix:** Add a lightweight connectivity check (e.g., list models from OpenRouter with a short timeout):
```python
async def health(request: Request):
    try:
        await asyncio.wait_for(ai_client.models.list(), timeout=5.0)
    except Exception:
        return JSONResponse({"status": "degraded", "ai_service": "unreachable"}, status_code=503)
    return JSONResponse({"status": "ok", "ai_service": "reachable"})
```

---

### F-17 (LOW) — `get_remote_address` rate-limits by proxy IP behind reverse proxy

**Description:** `slowapi.util.get_remote_address` uses `request.client.host`. When deployed behind a reverse proxy (Nginx, Cloudflare, etc.), this returns the proxy's IP address, not the end user's. All users would share the same rate limit bucket.

**File:** `backend/app/rate_limit.py:4`

**Fix:** Either use `slowapi`'s `key_func` that respects `X-Forwarded-For`, or configure FastAPI's `ProxyHeadersMiddleware` with a trusted proxy list:
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
# Or use slowapi's get_remote_address with proper middleware
```

---

### F-18 (LOW) — Missing timeout on OpenAI client

**Description:** The `OpenAI` client is created without a `timeout` parameter. If the AI provider becomes unresponsive (network partition, provider outage), the HTTP request will hang indefinitely until the underlying default timeout (usually 300s for httpx). This ties up server resources and blocks the event loop.

**Files:**
- `backend/app/services/prefilter.py:10-13`
- `backend/app/services/ai_service.py:39-42`
- `backend/app/routers/scan.py:34-37`

**Fix:** Add an explicit timeout:
```python
client = AsyncOpenAI(base_url=..., api_key=..., timeout=30.0)
```

---

### F-19 (LOW) — `scan.py:23` await on sync function (F-01 will fix this)

**File:** `backend/app/routers/scan.py:23`
After F-01 is fixed, `await is_job_post()` will properly await the async version. Currently the call to `is_job_post` works because the function is `async def` but internally calls sync `client.chat.completions.create()` — so it's async-wrapped but still blocking. F-01 resolves this entirely.

---

### F-20 (LOW) — Undocumented `HOST` and `PORT` env vars in `.env.example`

**Description:** `config.py:8-9` defines `host: str = "0.0.0.0"` and `port: int = 8000` from environment variables, but `.env.example` does not document these. The `.env.example` mentions only `API_BASE_URL`, `API_KEY`, and `MODEL_NAME`.

**File:**
- `backend/app/config.py:8-9`
- `backend/.env.example` (missing entries)

**Fix:** Add to `.env.example`:
```
HOST=0.0.0.0
PORT=8000
```

---

### F-21 (LOW) — `AppError.detail` is a class attribute, not an instance attribute

**Description:** `AppError.status_code` and `AppError.detail` are class-level attributes. If an exception handler ever mutates them (unlikely but possible), the change would propagate to all instances. The `exceptions.py` module is otherwise well-designed; this is a minor Python style concern.

**File:** `backend/app/exceptions.py:5-7`

**Fix:** Use instance attributes for safety (if the pattern ever expands to include dynamic detail):
```python
class AppError(Exception):
    def __init__(self, status_code: int = 500, detail: str = "Internal server error"):
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.detail)
```

---

## Summary by Severity

| Severity | Count | Finding IDs |
|----------|-------|-------------|
| HIGH     | 4     | F-01, F-02, F-03, F-04 |
| MEDIUM   | 8     | F-05, F-06, F-07, F-08, F-09, F-10, F-11, F-12 |
| LOW      | 9     | F-13, F-14, F-15, F-16, F-17, F-18, F-19, F-20, F-21 |

**Priority fix order:** F-01 → F-04 → F-03 → F-02 → F-05 → F-06 → (remaining MEDIUM) → (remaining LOW)

---

## Cross-Cutting Patterns

1. **No logging whatsoever** — There are zero `import logging` statements anywhere in the backend. Every AI API call, every error, every request is invisible in production. Consider adding structured logging with `structlog` or even just `logging`.

2. **No testing infrastructure** — No `test_*.py` files found, no `pytest` or `pytest-cov` in `requirements.txt`. The entire backend has zero tests for any endpoint or service function.

3. **No Pydantic `model_validator` / `field_validator` usage** — Despite using Pydantic v2 for schemas, no validators are used anywhere. Input data passes through unfiltered beyond basic type coercion.

4. **No error propagation chain** — When `analyze_job_post` encounters an AI parse error, it sets `valid=True` and returns an error string. The router (`scan.py`) never inspects the error field. This creates a false-positive scenario where the client receives `valid=True` for a failed scan.

---

*Concerns audit: 2026-07-07*

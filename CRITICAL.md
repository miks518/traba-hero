# Critical Implementation & Refactoring Roadmap

> **Agent Instructions:** Read this document sequentially. Work on **one task at a time**. After completing each task, run the test/lint quality gate, verify execution, and check off the completed checkbox before proceeding to the next task.

---

## Phase 1: Security & API Protection

### [x] Task 1.1: Extension-to-Backend Request Authentication
- **Objective:** Prevent unauthorized external users from draining LLM API credits by calling backend endpoints directly.
- **Frontend Changes (`entrypoints/`):**
  - Create an API key or session token generator in `chrome.storage.local`.
  - Include a custom security header (`X-Trabahero-Client-Key`) in all fetch requests in `api.ts`.
- **Backend Changes (`backend/`):**
  - Create a lightweight middleware or FastAPI dependency (`backend/app/core/auth.py`) to validate incoming headers against an environment variable (`CLIENT_SECRET_KEY`).
- **Verification:** Unit test `POST /api/scan` without the key to confirm it returns `401 Unauthorized`.
- **Implemented:** Shared secret key generated per extension instance via `crypto.randomUUID()`, stored in `chrome.storage.local`, sent as `X-Trabahero-Client-Key` header. Backend validates via `require_client_key` FastAPI dependency. Auth disabled when `CLIENT_SECRET_KEY` is empty (dev mode). 13 pytest tests pass. TypeScript compiles clean.

---

### [x] Task 1.2: Client-Side Image Compression
- **Objective:** Prevent high-resolution screenshots from triggering HTTP 413 (Payload Too Large) or slowing down network requests.
- **Frontend Changes (`entrypoints/content/capture.ts`):**
  - Before converting canvas screenshots to base64, compress images to JPEG format with a quality parameter (e.g., `canvas.toDataURL('image/jpeg', 0.8)`).
  - Enforce a maximum dimension constraint (e.g., max width/height of 1280px) before sending payload to `POST /api/scan`.
- **Verification:** Test multi-screenshot capture on high-DPI displays and verify total request size stays under 4MB.
- **Implemented:** Created `imageUtils.ts` with `compressImage()` that scales to 1280px max and outputs JPEG at 0.8 quality. `ScamScanView.tsx` compresses each screenshot before storing in state. TypeScript compiles clean. The cap was later lowered from 1920px to 1280px: with a native reasoning model, visual input is what it deliberates over, and a 4-image scan at 1920px sent ~8.3M pixels against 3.7M at 1280px.

---

### [x] Task 1.3: Reverse-Proxy Safe Rate Limiting
- **Objective:** Prevent `slowapi` rate limiter from blocking all users when deployed behind Nginx/Cloudflare proxies.
- **Backend Changes (`backend/app/core/rate_limit.py`):**
  - Update the key function for `slowapi` to check for `X-Forwarded-For` or `X-Real-IP` headers first before defaulting to `request.client.host`.
- **Verification:** Test local requests with simulated `X-Forwarded-For` headers to ensure IP tracking functions correctly.
- **Implemented:** Custom `_get_client_ip` key function in `rate_limit.py` checks `X-Forwarded-For` (first IP), then `X-Real-IP`, then falls back to `get_remote_address`. 6 pytest tests pass covering single/multi IP, priority, whitespace handling.

---

## Phase 2: Data Privacy & Philippine Compliance (DPA)

### [ ] Task 2.1: Data Privacy Consent Modal
- **Objective:** Comply with National Privacy Commission (NPC) rules for handling personal resume details.
- **Frontend Changes (`entrypoints/sidepanel/`):**
  - Add a `ConsentModal.tsx` component that triggers before a user uploads a resume for the first time.
  - Explain explicitly that resume text will be processed in-memory by AI models and not stored permanently.
  - Persist user consent status (`hasConsentedPrivacy`) in `chrome.storage.local`.
- **Verification:** Clear storage, launch extension, and confirm resume upload is blocked until consent is accepted.

---

### [ ] Task 2.2: Backend In-Memory Processing & Zero-Retention Guarantee
- **Objective:** Ensure no PII (Personally Identifiable Information) or screenshots are persisted to disk or logs.
- **Backend Changes (`backend/`):**
  - Review all FastAPI endpoints (`scan.py`, `resume.py`) to confirm temporary uploaded files are deleted immediately after reading into memory.
  - Audit logging configuration (`logger.py`) to strip or omit raw prompt texts, base64 payloads, and user emails from application log outputs.
- **Verification:** Run a full scan and resume match cycle, then check server logs and file system to ensure zero leftover files or logged PII.

---

### [~] Task 2.3: Defamation-Safe AI Output
- **Objective:** Stop the assistant from asserting accusations it cannot support, so the tool informs job seekers without exposing its developers to cyber-libel claims. Tighten the system prompts and field rules across all endpoints, and stop the UI from presenting numbers and verdicts the system never measured.
- **Backend Changes (`backend/`):**
  - Add a shared observational rule set to every prompt: report only what the input states, declare unknowns as unknown, never infer intent, never name a company or person as a scam/fraud/criminal, and drop hedging and absolutes.
  - Fix verification status semantics so absence of a result is `yellow` (not confirmed) rather than `red`; reserve `red` for a negative fact a provided search result actually states.
  - Remove dead or contradictory prompt text: "check the job post online" (the scan endpoint has no tool, so it licensed fabrication), the unused `COMPANY NAME` output field, and the `RISK_SCORE`/`RISK_LEVEL` block the server computes itself and discards.
  - Reclassify a missing employer name as a low-severity stated fact instead of "a strong scam indicator", and ask the model to check logos and letterheads for a name before concluding there is none.
- **Frontend Changes (`entrypoints/sidepanel/`):**
  - Never present a risk number the system did not measure. The score is built in two stages and blended server-side: the posting's own indicators (always available) and the external employer check (only when a name exists), 60/40. A stage that did not run is absent, not zero, so an unlookable posting keeps its own verdict.
  - Widen the scanner beyond formatted job adverts to all offers of work or income, including chat messages, forwarded paragraphs, and recruitment pitches. `VALID: false` now means the content offers no work or income at all.
  - Add a post-only analysis flow for offers that name no employer: `POST /api/analyze-offer` produces a verdict from the offer's own content, so the user is never left without one.
  - De-escalate user-facing copy that asserted conclusions ("Risk Protection Active", "Verified safe opportunity", "Treat this as high-risk", "Issue Found") to state findings instead.
  - Migrate stored scan history so previously synthesised scores are cleared on load rather than displayed as findings.
- **Verification:** `python -m pytest tests/ -v` (160 pass, fully offline), `npm run compile`, `npm test`, `npm run build`. Live pipeline confirmed manually by the developer (scan completes, employer name extracted, verification runs, score returned). The systematic output-quality checklist in `UNFINISHED-WORK.md` is still outstanding and must be run by the developer — it needs live provider calls.
- **Implemented:** All of the above is in place. The scan and verification wire formats are unchanged — only the rules around them were tightened, so `_parse_custom`, `_parse_match_custom`, `_parse_resume_custom`, `_parse_verification_result`, and `_VALID_LINE_RE` were not touched; the new analysis pass has its own endpoint and parser, so it cannot break the existing paths. The scan prompt's rules were deduplicated into `OUTPUT_RULES` / `SCAN_FIELD_RULES` constants in `prompts.py`, because the same defective text had been copy-pasted into `FALLBACK_SYSTEM_PROMPT` and `SCAN_OUTPUT_FORMAT`. `risk_calculator.py` gained `_posting_risk_from_flags` and `_combine_scores`; the dead `RISK_SCORE` block the verify prompt asked for was removed because the server computes the score itself. Also fixed `extract_company_name` over-capturing into the next sentence, which made verification search for garbage and return an all-yellow result, and added a dedicated `COMPANY NAME:` field so the employer is stated rather than regexed out of prose. Remaining work — prompt-contract tests, permanent scoring/extraction tests, and the live output-quality pass — is listed in `UNFINISHED-WORK.md`.

---

## Phase 3: Resilience & Fault Tolerance

### [x] Task 3.1: Offline Mode & Network Health Monitoring
- **Objective:** Provide instant feedback if the backend server or user internet drops, avoiding long 240-second timeout hangs.
- **Frontend Changes (`entrypoints/sidepanel/`):**
  - Create a health-check polling hook (`useBackendHealth.ts`) that pings `GET /health` periodically.
  - Add a non-intrusive banner (`OfflineBanner.tsx`) at the top of the side panel when the server is unreachable.
  - Disable scan buttons while offline and display a clean "Server Unreachable" message.
- **Verification:** Shut down the backend service while the extension is open; verify the UI immediately shows offline state without freezing.
- **Implemented:** `pingHealth()` in `lib/api.ts` (3s timeout, always resolves to a boolean, reuses the client-key header). `useBackendHealth()` polls every 4s (~15/min, under the backend's 30/min `/health` cap), skips probes while `document.hidden`, re-probes on `visibilitychange`, never overlaps requests, and flips offline only after 2 consecutive failures so a single slow response cannot trigger a false alarm. The first successful probe restores the online state, so the banner clears itself on recovery. `OfflineBanner` renders below the top app bar with error-tint styling and a Retry button that triggers an immediate check. `App.tsx` owns the hook and passes `isOnline` to both views; `ScamScanView` disables/relabels the Scan button, `ResumeMatchView` disables Match and the resume uploader, and `ResumeUploader` now honors `disabled` for click, drag, and change (it previously only disabled the hidden input). Element picking, cropping, and history stay usable since they are local-only, and in-flight scans are left to finish on their existing timeouts. No backend changes were needed — `GET /health` already existed. 10 new vitest tests plus `npm run compile` and `npm run build` pass.

---

### [ ] Task 3.2: Resilient SEC Philippines Verification
- **Objective:** Prevent official SEC lookup timeouts from breaking the overall scan flow.
- **Backend Changes (`backend/app/services/sec_api.py`):**
  - Wrap SEC API HTTP calls with a strict 5-second timeout.
  - If the SEC endpoint fails or times out, fall back seamlessly to a Tavily query (`site:sec.gov.ph "<Company Name>"` via `app/services/search.py`) instead of throwing an error. Note the search must be reported as a retrieval failure if the key is missing, never as a clean company.
- **Verification:** Mock a failed SEC API response and confirm that the company scan still completes successfully using web search fallbacks.

---

## Phase 4: User Feedback Loop

### [ ] Task 4.1: Misclassification / False Positive Reporting
- **Objective:** Allow users to report incorrect risk scores or false positives.
- **Frontend Changes (`entrypoints/sidepanel/components/`):**
  - Add a "Report Incorrect Verdict" button to `ScanResult.tsx`.
  - Create a simple modal (`ReportModal.tsx`) allowing users to select a feedback reason (e.g., "Legitimate company marked as scam" or "Scam missed").
- **Backend Changes (`backend/app/routers/report.py`):**
  - Create endpoint `POST /api/report` to log misclassifications anonymously for future prompt tuning.
- **Verification:** Submit a sample report from the side panel and check backend receipt.
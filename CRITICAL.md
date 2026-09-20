# Critical Implementation & Refactoring Roadmap

> **Agent Instructions:** Read this document sequentially. Work on **one task at a time**. After completing each task, run the test/lint quality gate, verify execution, and check off the completed checkbox before proceeding to the next task.

---

## Phase 1: Security & API Protection

### [ ] Task 1.1: Extension-to-Backend Request Authentication
- **Objective:** Prevent unauthorized external users from draining LLM API credits by calling backend endpoints directly.
- **Frontend Changes (`entrypoints/`):**
  - Create an API key or session token generator in `chrome.storage.local`.
  - Include a custom security header (`X-Trabahero-Client-Key`) in all fetch requests in `api.ts`.
- **Backend Changes (`backend/`):**
  - Create a lightweight middleware or FastAPI dependency (`backend/app/core/auth.py`) to validate incoming headers against an environment variable (`CLIENT_SECRET_KEY`).
- **Verification:** Unit test `POST /api/scan` without the key to confirm it returns `401 Unauthorized`.

---

### [ ] Task 1.2: Client-Side Image Compression
- **Objective:** Prevent high-resolution screenshots from triggering HTTP 413 (Payload Too Large) or slowing down network requests.
- **Frontend Changes (`entrypoints/content/capture.ts`):**
  - Before converting canvas screenshots to base64, compress images to JPEG format with a quality parameter (e.g., `canvas.toDataURL('image/jpeg', 0.8)`).
  - Enforce a maximum dimension constraint (e.g., max width/height of 1920px) before sending payload to `POST /api/scan`.
- **Verification:** Test multi-screenshot capture on high-DPI displays and verify total request size stays under 4MB.

---

### [ ] Task 1.3: Reverse-Proxy Safe Rate Limiting
- **Objective:** Prevent `slowapi` rate limiter from blocking all users when deployed behind Nginx/Cloudflare proxies.
- **Backend Changes (`backend/app/core/rate_limit.py`):**
  - Update the key function for `slowapi` to check for `X-Forwarded-For` or `X-Real-IP` headers first before defaulting to `request.client.host`.
- **Verification:** Test local requests with simulated `X-Forwarded-For` headers to ensure IP tracking functions correctly.

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

## Phase 3: Resilience & Fault Tolerance

### [ ] Task 3.1: Offline Mode & Network Health Monitoring
- **Objective:** Provide instant feedback if the backend server or user internet drops, avoiding long 240-second timeout hangs.
- **Frontend Changes (`entrypoints/sidepanel/`):**
  - Create a health-check polling hook (`useBackendHealth.ts`) that pings `GET /health` periodically.
  - Add a non-intrusive banner (`OfflineBanner.tsx`) at the top of the side panel when the server is unreachable.
  - Disable scan buttons while offline and display a clean "Server Unreachable" message.
- **Verification:** Shut down the backend service while the extension is open; verify the UI immediately shows offline state without freezing.

---

### [ ] Task 3.2: Resilient SEC Philippines Verification
- **Objective:** Prevent official SEC lookup timeouts from breaking the overall scan flow.
- **Backend Changes (`backend/app/services/sec_api.py`):**
  - Wrap SEC API HTTP calls with a strict 5-second timeout.
  - If the SEC endpoint fails or times out, fall back seamlessly to DuckDuckGo search query fallback (`site:sec.gov.ph "<Company Name>"`) instead of throwing an error.
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
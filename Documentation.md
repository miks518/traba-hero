# Trabahero — Functional & Non-Functional Requirements

**Project:** Trabahero — A Universal Visual Job-Scam Detection System for Filipino Job Seekers
**Version:** 0.5.0
**Last Updated:** 2026-09-29

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Functional Requirements](#3-functional-requirements)
   - FR-01: Extension Shell & Navigation
   - FR-02: Element Picker & Screenshot Capture
   - FR-03: Manual Crop Selection
   - FR-04: Floating Action Button
   - FR-05: Job Posting Scan (Image)
   - FR-06: Job Posting Scan (Text)
   - FR-07: AI-Powered Scam Analysis
   - FR-08: Risk Score Calculation
   - FR-09: Red Flag Detection & Display
   - FR-10: Company Verification (Web Search)
   - FR-11: Company Registration Evidence
   - FR-12: Email Verification
   - FR-13: External Verification (Phones, Domains, Websites, Social, Gov)
   - FR-14: Resume Upload & Parsing
   - FR-15: Resume-to-Job Matching
   - FR-16: Job History Management
   - FR-17: Job Filtering & Risk Categories
   - FR-18: Theme Toggle (Dark/Light)
   - FR-19: Text Size Scaling
   - FR-20: Toast Notifications
   - FR-21: Confirmation Dialogs
   - FR-22: Multi-Screenshot Support
   - FR-23: Lightbox Preview
   - FR-24: Progress Streaming (SSE)
   - FR-25: Backend API Endpoints
   - FR-26: AI Concurrency Control
   - FR-27: Rate Limiting
   - FR-28: Invalid Content Handling
   - FR-29: Clear History & Resume
   - FR-30: Popup UI
   - FR-31: Postings With No Employer Name
   - FR-32: Risk-Ordered Result Layout
4. [Non-Functional Requirements](#4-non-functional-requirements)
   - NFR-01: Performance
   - NFR-02: Reliability & Fault Tolerance
   - NFR-03: Security
   - NFR-04: Usability & Accessibility
   - NFR-05: Compatibility
   - NFR-06: Maintainability
   - NFR-07: Scalability
   - NFR-08: Privacy & Data Protection
   - NFR-09: Localization
   - NFR-10: Configuration & Environment
   - NFR-11: Test Isolation & External Service Safety
 5. [Data Models](#5-data-models)
6. [API Reference](#6-api-reference)
7. [Traceability Matrix](#7-traceability-matrix)

---

## 1. Project Overview

Trabahero is a Chrome browser extension that protects Filipino job seekers from employment scams. It uses AI (via OpenRouter) to analyze job postings for fraud signals, looks the named employer up through a web search to check whether the company exists and is registered, and matches user resumes against scanned job postings.

**Target Users:** Filipino job seekers browsing online job boards (e.g., JobStreet, Indeed, Facebook Jobs).

**Core Value Proposition:** Safety through Simplicity — one click should be enough to get a safety verdict.

**Two principles shape the whole system:**

1. **A finding must be evidence.** A red flag describes something the posting contains; a verification finding carries a source URL copied from the search results. The system reports what it checked and, when a check did not happen, says so rather than presenting silence as a clean result.
2. **A missing input is not a finding.** A posting that names no employer cannot be verified. That is stated as a gap in what was checked, never as a risk score or a red flag.

---

## 2. System Architecture

| Layer | Technology | Location |
|-------|-----------|----------|
| Browser Extension (Frontend) | React 19, TypeScript, Tailwind CSS 3.4, WXT Framework | `entrypoints/` |
| Backend API | Python 3.10+, FastAPI, Pydantic | `backend/` |
| Scanner services | Prompt loading, SSE streaming, parsing, risk scoring, and verification workflows | `backend/app/services/scanner/` |
| AI Provider | OpenRouter (cloud, OpenAI-compatible API) | External |
| Web Search | Tavily Search API (LLM-grounded results) | External |
| Email Verification | Local DNS/MX lookups (`email_verifier.py`) | Internal |

**Communication:** The extension communicates with the backend via HTTP REST + SSE (Server-Sent Events) for streaming progress updates. The content script communicates with the side panel via Chrome `runtime.sendMessage` / `tabs.sendMessage`.

---

## 3. Functional Requirements

### FR-01: Extension Shell & Navigation

| Attribute | Value |
|-----------|-------|
| **ID** | FR-01 |
| **Priority** | Critical |
| **Component** | `TopAppBar`, `SideNav`, `Footer`, `App.tsx` |

**Description:** The extension shall provide a side panel UI with a top app bar, left side navigation, and bottom footer.

**Acceptance Criteria:**
- AC-01: The side panel opens when the user clicks the extension toolbar icon.
- AC-02: The top app bar displays the Trabahero logo, help button, text size selector, theme toggle, and close button.
- AC-03: The side navigation shows two tabs: "Scan" (security icon) and "Match" (description icon).
- AC-04: The active tab is visually highlighted with a gradient background (`nav-item-active`).
- AC-05: The footer displays Legal and Privacy links and copyright text.
- AC-06: Clicking a tab switches the main content view without unmounting the previous view (state preservation).
- AC-07: The side panel displays a scanned jobs count badge in the side navigation.
- AC-08: A live scanning progress indicator appears in the side navigation during active scans.

---

### FR-02: Element Picker & Screenshot Capture

| Attribute | Value |
|-----------|-------|
| **ID** | FR-02 |
| **Priority** | Critical |
| **Component** | `content.tsx`, `PickerButton.tsx`, `capture.ts` |

**Description:** The extension shall allow users to click on a job posting element on any webpage to capture it as a screenshot for scanning.

**Acceptance Criteria:**
- AC-01: Clicking "Pick a Job Post" activates an element picker overlay on the current tab.
- AC-02: The cursor changes to crosshair and a blue overlay follows the hovered element.
- AC-03: A toast notification displays "Click the job post to scan" upon activation.
- AC-04: Clicking an element captures its bounding box and triggers a screenshot via `tabs.captureVisibleTab`.
- AC-05: The screenshot is cropped to the selected element's bounds using canvas.
- AC-06: Elements extending beyond the visible viewport are rejected with an error toast.
- AC-07: Pressing Escape cancels the picker and restores the original cursor.
- AC-08: The picker deactivates automatically after an element is selected.
- AC-09: The captured screenshot is sent to the side panel for scanning.

---

### FR-03: Manual Crop Selection

| Attribute | Value |
|-----------|-------|
| **ID** | FR-03 |
| **Priority** | High |
| **Component** | `content.tsx`, `PickerButton.tsx`, `capture.ts` |

**Description:** The extension shall allow users to manually select an area of the page by dragging a selection box.

**Acceptance Criteria:**
- AC-01: Clicking "Manual Crop" activates a semi-transparent backdrop overlay.
- AC-02: The user can click and drag to draw a dashed-border selection rectangle.
- AC-03: The selection displays a "Drag to select the area to scan" toast.
- AC-04: Selections smaller than 10×10 pixels are ignored.
- AC-05: On mouse-up, the selected area coordinates are captured and a screenshot is taken.
- AC-06: The screenshot is cropped to the manual selection bounds.
- AC-07: Pressing Escape cancels the manual crop.
- AC-08: Activating the element picker while manual crop is active cancels the crop (mutual exclusion).

---

### FR-04: Floating Action Button

| Attribute | Value |
|-----------|-------|
| **ID** | FR-04 |
| **Priority** | Medium |
| **Component** | `content.tsx` |

**Description:** The extension shall inject a floating action button (FAB) on web pages for quick access to the scanning feature.

**Acceptance Criteria:**
- AC-01: A green shield icon FAB is injected at the bottom-right corner (24px from edges).
- AC-02: The FAB is 52×52px with 14px border-radius and a 3D tactile shadow.
- AC-03: The FAB adapts to the current theme (dark/light) using `chrome.storage.local`.
- AC-04: Clicking the FAB activates the element picker and opens the side panel.
- AC-05: The FAB can be toggled on/off from the popup UI.
- AC-06: The FAB is not injected in iframes (`window !== window.top`).
- AC-07: The FAB has a press-down animation on mousedown.

---

### FR-05: Job Posting Scan (Image)

| Attribute | Value |
|-----------|-------|
| **ID** | FR-05 |
| **Priority** | Critical |
| **Component** | `ScamScanView.tsx`, `api.ts`, `scan.py` |

**Description:** The system shall scan job posting screenshots for scam indicators using AI analysis.

**Acceptance Criteria:**
- AC-01: The user can scan up to 4 screenshots of the same job posting.
- AC-02: Screenshots are converted to base64 and sent to `POST /api/scan`.
- AC-03: A progress bar and skeleton loading card are displayed during scanning.
- AC-04: The scan streams progress events via SSE (percent + stage).
- AC-05: The scan timeout is 240 seconds; on timeout, a user-friendly error is shown.
- AC-06: The AI response is parsed into a structured `ScanResult` with status, risk score, red flags, analysis, and job summary.
- AC-07: The scan result is stored in the scanned jobs history.
- AC-08: If the image is not a valid job posting, an `InvalidContentError` card is displayed.

---

### FR-06: Job Posting Scan (Text)

| Attribute | Value |
|-----------|-------|
| **ID** | FR-06 |
| **Priority** | Medium (backend-only; no extension caller) |
| **Component** | `api.ts`, `scan.py` |

**Description:** The backend exposes a text-scanning endpoint. The extension does not currently call it — every scan is a screenshot — but the endpoint is supported and tested.

**Acceptance Criteria:**
- AC-01: Text content is sent to `POST /api/scan-text`.
- AC-02: **No web search is performed for a text scan.** The scan reads the posting only; online evidence is used exclusively by `/api/verify`.
- AC-03: The same SSE streaming progress and result format as image scan.
- AC-04: Text scan supports up to 50,000 characters.
- AC-05: Empty text returns an immediate error response.

---

### FR-07: AI-Powered Scam Analysis

| Attribute | Value |
|-----------|-------|
| **ID** | FR-07 |
| **Priority** | Critical |
| **Component** | `lm_client.py`, `services/scanner/`, `SYSTEM_PROMPT.md`, `verification_prompt.py` |

**Description:** The backend shall use an AI model to analyze job postings for fraud indicators and produce a structured verdict. External verification runs on a separate `/api/verify` endpoint using one Tavily search + one AI call.

**Acceptance Criteria:**
- AC-01: The AI model receives the job posting content (image and/or text) with a system prompt.
- AC-02: The system prompt defines the labeled output format: `VALID`, `RED FLAG` lines, `END FLAGS`, `EMPLOYER NAME`, `POSTING ANALYSIS`, `JOB SUMMARY`.
- AC-03: The AI returns a validity flag (true when the content offers work, income, a business opportunity, or training for work; false when it does not).
- AC-04: `VALID: false` ends the response immediately; the scan relies on a mid-stream regex to stop early and save tokens.
- AC-05: Red flags are reported only for something observable in the posting, each with a label, reasoning, and severity (low/mid/high).
- AC-06: **A red flag never describes something the posting does not contain.** Absence is not evidence: "it does not ask for a processing fee" is a clean posting, not a warning. A scam pattern may be named only when the posting contains that pattern's concrete element.
- AC-07: The system prompt also forbids flagging a free email domain, a missing office address, a generic job title, "no experience needed", or an unstated salary.
- AC-08: **`POSTING ANALYSIS` must not contain the words "scam", "legitimate", "suspicious", "genuine", "fraudulent", or "honest".** The ban is repeated in the field rule itself, not only the prompt preamble, because a long prompt drifts. The field rule also supplies the allowed phrasing: describe what the posting asks for, not what it is.
- AC-09: The employer name is stated in a dedicated `EMPLOYER NAME:` field, preferring the company the reader would work for. A staffing or manpower agency is the recruiter, not the employer, unless the posting is for the agency's own staff.
- AC-10: The backend talks to the AI provider through an OpenAI-compatible client, so any provider or model ID can be configured without code changes.
- AC-11: Scan output uses a labeled text format, parsed block-wise with a JSON fallback. Structured output is reserved for `/api/verify` and `/api/analyze-offer`, which do not stream.
- AC-12: Unreadable AI responses return a user-friendly error message.

---

### FR-08: Risk Score Calculation

| Attribute | Value |
|-----------|-------|
| **ID** | FR-08 |
| **Priority** | Critical |
| **Component** | `scan.py`, `RiskGauge.tsx` |

**Description:** The system shall calculate a risk score from two stages and display it as a circular gauge. The posting stage always produces a score; the verification stage is added only when the employer could be checked.

**Acceptance Criteria:**
- AC-01: **Posting stage (always runs).** Severity weights: HIGH=40, MID=12, LOW=4, capped at 100. It depends on nothing but the posting, so an offer with no employer name still gets a number.
- AC-02: **Verification stage (only when a name exists).** Category weights: Company Existence=40, Official Registration=25, Reputation=35. RED contributes full weight, YELLOW contributes half. The legacy label "SEC Registration" maps to the registration weight.
- AC-03: The verification stage returns **no score when every item is yellow.** Absence of evidence produces no number, so an unchecked company cannot be reported as a risk figure.
- AC-04: The two stages are blended **60% posting / 40% verification**. Whichever stage is missing is treated as absent, not as zero: a posting that could not be looked up is not penalised for the missing lookup, and a clean employer record does not raise a post with no indicators.
- AC-05: The score is displayed as a circular SVG arc gauge with colour transitions.
- AC-06: The gauge shows the numeric score in the centre and a risk label below.
- AC-07: Risk categories: **Low Risk** (0–30), **Moderate Risk** (31–50), **High Risk** (51–75), **Critical Risk** (76–100).
- AC-08: A score breakdown records which stages contributed, the per-severity counts, and the weights used.
- AC-09: **Unverified state.** A posting that names no employer and raised no red flags shows "Unverified" on a grey pulsing ring with no number, not "0 / Low Risk", which would claim the post was cleared when the employer was never checked. A red flag is real evidence and is scored on severity instead.
- AC-10: Every ring carries a slow breathing glow (`.ring-pulse`) whose colour follows the risk level, or the neutral outline grey when unverified. The animation is disabled under `prefers-reduced-motion`.

**Risk Label Mapping:**
| Score Range | Label |
|-------------|-------|
| 0–30 | Low Risk |
| 31–50 | Moderate Risk |
| 51–75 | High Risk |
| 76–100 | Critical Risk |

---

### FR-09: Red Flag Detection & Display

| Attribute | Value |
|-----------|-------|
| **ID** | FR-09 |
| **Priority** | Critical |
| **Component** | `RedFlagsList.tsx`, `RedFlagCard.tsx`, `SYSTEM_PROMPT.md` |

**Description:** The system shall detect and display red flags with severity indicators. A red flag is always evidence of something the posting contains.

**Acceptance Criteria:**
- AC-01: Red flags are displayed as a list of cards with icon, title, severity badge, and description.
- AC-02: Severity levels have distinct visual styling: high (red), mid (amber), low (neutral).
- AC-03: A "CRITICAL" badge is shown if any high-severity flags exist.
- AC-04: The total flag count is displayed.
- AC-05: Flags are prioritized by severity (high first, then mid, then low).
- AC-06: The system never invents red flags — only genuine scam indicators from the AI are shown.
- AC-07: Upfront fees are always flagged as HIGH severity (per system prompt rules).
- AC-08: **A missing company name is NOT a red flag.** It is a missing input, not a finding: it would contradict the "never flag an absence" rule and would add score weight for something wrong with our inputs rather than with the post. It is surfaced separately as the Unverified gauge state and the CompanyNameNeeded panel (FR-31).
- AC-09: **The severity list must not offer a missing employer as an example.** A rule stated only as a ban elsewhere in the prompt is not enough: the severity list is where the model looks when choosing what to flag, and an example there reads as sanctioned. A test parses the severity block by indentation and checks only the text after each severity's colon, so the phrase may appear in a prohibition but not as an example.

---

### FR-10: Company Verification (Web Search)

| Attribute | Value |
|-----------|-------|
| **ID** | FR-10 |
| **Priority** | High |
| **Component** | `search.py`, `verification_flow.py`, `verification_prompt.py` |

**Description:** The system shall look an employer up through the Tavily search API and report what the results actually show. A verification issues **two** queries — `registration`, then `reviews complaints` — and sends one merged result list to one AI call.

**Acceptance Criteria:**
- AC-01: `search(query) -> SearchOutcome` is the single search entry point. `SearchOutcome.ok` and `SearchOutcome.results` are **independent fields**: `ok=False` with no results means retrieval failed; `ok=True` with no results means the company genuinely has no online footprint.
- AC-01b: **Two queries per verification, neither rigged.** Neither names a specific registry, because the category is deliberately broader than the SEC. Neither carries `scam` or `fraud`: those name a conclusion, so a query carrying one makes its results look like corroboration of the accusation it already embedded. `reviews` and `complaints` name *documents* and are allowed. The residual exposure is aggregator pages that re-publish complaint text against a scraped company name, which is why a result must concern the same entity and `red` must name a source.
- AC-01c: **Company Existence is inferred, not separately queried.** The original single query was existence-tuned and starved Official Registration by *ranking*. Existence is now judged from the same merged list. **Known limitation:** an employer with neither a filing nor any review is found by neither query and reports yellow on existence — the smallest employers, which is who this product exists for.
- AC-01d: Results from both queries are **merged into one flat list with no category headings**, then deduped on canonical URL keeping the higher-scoring copy. The employer's own site appears in both result sets, and every result is prompt text competing for a budget shared with the model's reasoning. A heading would assert a category retrieval never established.
- AC-01e: **`search_partial` reports partial coverage.** One search failing while the other succeeds means the findings are real but some categories were covered by a thinner search. The panel states "N of M searches failed … this is not a finding about the employer". Reporting plain success would overstate the coverage; reporting a total failure would discard a search that worked. Two failures is the existing `search_ok: false` state.
- AC-02: No caller may read one state as the other. A failed lookup is reported as unknown, never as a clean company.
- AC-03: A missing `TAVILY_API_KEY` is a **failure**, not an empty success, so a broken deployment cannot look like a clean employer.
- AC-04: **The employer name is passed to the provider verbatim**, with only an axis term (`registration certificate` / `reviews complaints`) and `Philippines` appended. No part of the name is rewritten: an SEC filing, a city PESO listing, and the employer's own legal pages are all titled with the *legal* name, so a trailing Corporation/Corp/Inc/Co/LLC is kept. An earlier version stripped it on the reasoning that a generic legal form dilutes a rare name; that was reversed after it was found to change the results, because stripping left the distinctive part competing against a brand, its franchisees, and unrelated products sharing the word. There are no category-suffixed queries and no retries, fallback provider, caching, or engine rotation.
- AC-05: A response with no usable `results` list (error envelope, null, renamed key) is a failure, not a finding — a parse fault must never be reported as an employer with no footprint.
- AC-06: Search results are passed to the model as a **flat list with URLs and no category headings.** A heading would assert that a result belonged to a category when retrieval only established which query surfaced it.
- AC-07: Result text is untrusted web content. The system prompt states it is data and never instructions, requires a result to concern the company being verified, and conditions GREEN on that identity; the emitted block is labelled as data and `===` is stripped so a page cannot forge the block terminator.
- AC-08: Every search failure is logged with its classified reason so a throttled or mis-shaped response is visible rather than inferred.
- AC-09: **Relevance is treated as a ranking problem, not a query-syntax problem.** A browser search from the Philippines covers a small employer's SEC filing, city PESO listing, and JobStreet page well; Tavily's own crawl index covers that long tail less well, so a niche name falls through to whatever it indexes strongly. The request therefore sends `country="philippines"` (a **boost**) and `search_depth="advanced"`.
- AC-10: `include_domains` stays unset. It is a **filter**, so restricting to government domains would discard exactly the job boards and PESO pages the boost exists to surface. There is no `include_domains_mode` and no "prefer" mode to request; the boost is the only tool matching the intent.
- AC-11: Advanced depth costs 2 credits against basic's 1, halving the 1,000/month free budget. That is the accepted trade for a niche lookup, and both the depth and the country are **environment values** (`TAVILY_SEARCH_DEPTH`, `TAVILY_COUNTRY`) so a deployment can change the trade without a code change. An unrecognised depth is logged and falls back rather than being sent, because a rejected request would be reported to the user as a company that cannot be looked up. A blank country is dropped rather than sent as an empty string.
- AC-12: `include_answer` is never set. A synthesised answer is retrieval's opinion rather than evidence, and the prompt requires source URLs copied from the results themselves.

---

### FR-11: Company Registration Evidence

| Attribute | Value |
|-----------|-------|
| **ID** | FR-11 |
| **Priority** | High |
| **Component** | `search.py`, `verification_prompt.py`, `VerificationCard.tsx` |

**Description:** The system shall report whether a company is registered with a Philippine government body. Registration is broader than the SEC.

**Acceptance Criteria:**
- AC-01: The verification category is **"Official Registration"**, not "SEC Registration". SEC is one such body, not the only one.
- AC-02: The prompt names SEC, DTI, PEZA, BOI, a local government unit business permit, and government portal listings as equally valid. Any one of them satisfies the category on its own.
- AC-03: The registration or permit number is reported when a result states one.
- AC-04: A company holding a DTI registration and no SEC filing is **not** reported as unconfirmed. Scoring "no SEC number" against such a company is a false negative.
- AC-05: The legacy "SEC Registration" label maps to the same weight (25) and is not logged as a missing category, so results recorded before the rename still score and render correctly.
- AC-06: The category is evaluated only from the provided search results, never from model training.

---

### FR-12: Email Verification

| Attribute | Value |
|-----------|-------|
| **ID** | FR-12 |
| **Priority** | High |
| **Component** | `email_verifier.py`, `ScamScanView.tsx` |

**Description:** The system shall verify email addresses found in job postings for syntax validity, mail server availability, and disposable domain detection.

**Acceptance Criteria:**
- AC-01: Emails are extracted from the AI-generated job summary and analysis text.
- AC-02: Each email is checked for syntax validity using regex.
- AC-03: Each email domain is checked for MX records via DNS lookup.
- AC-04: Disposable/free email domains are detected against a hardcoded list of 40+ providers.
- AC-05: Risk levels: HIGH (invalid syntax, disposable, no MX), LOW (valid infrastructure).
- AC-06: Gmail, Yahoo, and similar free providers are considered acceptable (not flagged as disposable).
- AC-07: Verification results are displayed in the scan results with email, domain, risk, and reason.

---

### FR-13: External Verification Results

| Attribute | Value |
|-----------|-------|
| **ID** | FR-13 |
| **Priority** | High |
| **Component** | `verification_flow.py`, `verification_prompt.py`, `VerificationSection.tsx`, `VerificationCard.tsx` |

**Description:** The system shall report the outcome of an employer lookup as exactly three categories, each carrying the specific fact found and a source the reader can open.

**Acceptance Criteria:**
- AC-01: After a successful scan with a named employer, the frontend calls `POST /api/verify` with the company name.
- AC-02: The three categories are **Company Existence**, **Official Registration**, and **Reputation**. No fourth category is invented.
- AC-03: `/api/verify` uses a JSON Schema response format with `provider.require_parameters`, so a `:free` model cannot route to an endpoint that does not support structured output. A labeled-text parser remains as a fallback.
- AC-04: Each check returns `status` (green/yellow/red), an uncapped `finding` naming the fact that decided it, and `source_title` / `source_url` **copied exactly from the provided results** — never constructed. This is the only channel by which online evidence reaches the user, so a fabricated URL would be a fabricated citation.
- AC-05: A top-level `evidence` list carries the results a reader would want to check, copied verbatim, capped at six.
- AC-06: Absence of a result is never RED. A search that found nothing about a category is YELLOW, and its finding must say the results do not mention it, so "searched and not found" never reads as "assumed absent".
- AC-07: The panel renders a clickable source under each card, plus a collapsible "Sources" section listing the full evidence set.
- AC-08: **YELLOW is painted amber**, with a wash, dot, and badge all tinted. It was neutral grey, but a 10% grey wash on an already-grey surface is an absent colour rather than a weak one, and YELLOW is the most common status the panel produces — a small employer with a thin footprint returns it on most of the three categories. The most frequent card rendered as if it carried no status. The amber collision with the `moderate` risk level is real but bounded: the gauge's *unverified* ring stays grey, because "nothing was measured" and "searched and could not confirm" are different claims. This is a deliberate scope limit, not an oversight.
- AC-09: `search_ok` / `search_error` travel on the wire so a failed lookup is stated by the panel directly, without depending on the model mentioning it.
- AC-10: When the posting names no employer, `/api/verify` is never called. See FR-31.
- AC-11: **The recommendation is addressed to a job seeker, not an auditor.** It names what the results actually showed and gives one step from an ordinary hiring exchange. It must not tell the reader to check a registry, a government website, or a permit, and must not ask them to verify a registration number — a reader applying for a job does not query a government portal, so such advice is actionable in form and useless in practice. The retrieval-failure variant gets the same treatment, directing the reader to hold off on money or personal details instead.

---

### FR-14: Resume Upload & Parsing

| Attribute | Value |
|-----------|-------|
| **ID** | FR-14 |
| **Priority** | High |
| **Component** | `ResumeUploader.tsx`, `ResumePreview.tsx`, `api.ts`, `scan.py` |

**Description:** The system shall allow users to upload and parse resumes for job matching.

**Acceptance Criteria:**
- AC-01: Users can upload files via drag-and-drop or click-to-upload.
- AC-02: Supported file types: PDF, DOCX, TXT, PNG, JPG, JPEG.
- AC-03: Files are read as base64 and sent to `POST /api/analyze-resume`.
- AC-04: The backend extracts text from PDF (pypdf), DOCX (zip+xml), TXT (direct read), or image (AI vision).
- AC-05: The AI parses the resume into structured data: skills, experience years, job titles, industries, summary.
- AC-06: A confirmation dialog is shown before uploading ("Upload & Scan Resume?").
- AC-07: Progress streaming is shown during analysis (SSE with percent + stage).
- AC-08: Parsed resume data is displayed in `ResumePreview` with skill tags, experience, and summary.
- AC-09: Users can replace or remove the uploaded resume.
- AC-10: Maximum file size: 5MB (base64 encoded).

---

### FR-15: Resume-to-Job Matching

| Attribute | Value |
|-----------|-------|
| **ID** | FR-15 |
| **Priority** | High |
| **Component** | `ResumeMatchView.tsx`, `JobMatchList.tsx`, `api.ts`, `scan.py` |

**Description:** The system shall match the user's resume against scanned job postings and provide compatibility scores.

**Acceptance Criteria:**
- AC-01: The match function sends the resume data and all verified job postings to `POST /api/match-resume`.
- AC-02: Risky (scam) jobs are excluded from matching.
- AC-03: Suspicious jobs are quarantined with a warning banner.
- AC-04: The AI returns a compatibility score (0-100) for each job.
- AC-05: Score labels: High Compatibility (80-100), Medium (50-79), Low (0-49).
- AC-06: Each match includes: score, label, skill gaps, matched skills, reasoning, experience fit, industry fit, recommended actions.
- AC-07: Match results are displayed as cards with score bars, skill chips, and action items.
- AC-08: Progress streaming is shown during matching (SSE with percent + stage).
- AC-09: The "Apply with Match" button is available for matched jobs.

---

### FR-16: Job History Management

| Attribute | Value |
|-----------|-------|
| **ID** | FR-16 |
| **Priority** | Medium |
| **Component** | `ResumeMatchView.tsx`, `App.tsx` |

**Description:** The system shall maintain a history of scanned jobs, where each entry shows the same score as the panel did.

**Acceptance Criteria:**
- AC-01: Each completed scan adds a `ScannedJob` to the history array.
- AC-02: Jobs are displayed in reverse chronological order.
- AC-03: Each job card shows: title, timestamp, risk badge, and match score (if available).
- AC-04: Jobs can be expanded to show full scan details (risk score, summary, red flags).
- AC-05: The job count is displayed in the side navigation badge.
- AC-06: Users can clear all job history with a confirmation dialog.
- AC-07: Job history persists across view switches (scan ↔ match) within the session.
- AC-08: **A job's stored result is replaced, not re-appended, when a later stage produces one.** Verification runs after the scan has been written to history and blends an employer score into the posting score, so an entry saved at scan time would otherwise keep the earlier figure while the panel shows the later one — the same posting reading as two different scores in two places. The whole result is replaced rather than the score patched, because the stage that moves the score also produces the evidence behind it.

---

### FR-17: Job Filtering & Risk Categories

| Attribute | Value |
|-----------|-------|
| **ID** | FR-17 |
| **Priority** | Medium |
| **Component** | `ResumeMatchView.tsx` |

**Description:** The system shall filter scanned jobs by risk category.

**Acceptance Criteria:**
- AC-01: Four filter tabs: All, Verified, Moderate, High/Critical.
- AC-02: Each tab shows a count badge of matching jobs.
- AC-03: **Verified (Low Risk):** `riskLevel === 'low'` AND `isJobPosting`.
- AC-04: **Unverified:** `riskLevel === null` — posts that predate the posting-stage score, shown as unchecked rather than given a number the system never measured.
- AC-05: **Moderate:** `riskLevel === 'moderate'`.
- AC-06: **High/Critical:** `riskLevel === 'high'` OR `riskLevel === 'critical'`.
- AC-07: High/Critical jobs are excluded from resume matching.
- AC-08: A red warning banner appears if high/critical jobs exist.
- AC-09: An amber warning banner appears if moderate jobs exist.
- AC-10: The risk level is derived from the two-stage score: Low (0–30), Moderate (31–50), High (51–75), Critical (76–100).

---

### FR-18: Theme Toggle (Dark/Light)

| Attribute | Value |
|-----------|-------|
| **ID** | FR-18 |
| **Priority** | Medium |
| **Component** | `App.tsx`, `TopAppBar.tsx`, `content.tsx` |

**Description:** The system shall support dark and light themes with persistent user preference.

**Acceptance Criteria:**
- AC-01: Default theme is dark.
- AC-02: The theme toggle button switches between dark and light.
- AC-03: Theme preference is persisted to `chrome.storage.local`.
- AC-04: Theme is applied via `document.documentElement.classList.toggle('dark')`.
- AC-05: Tailwind CSS uses `darkMode: 'class'` for theme-aware styling.
- AC-06: All CSS custom properties (45+ color tokens) switch between themes.
- AC-07: The content script (FAB, toasts) also syncs theme from storage.
- AC-08: The theme persists across browser restarts.

---

### FR-19: Text Size Scaling

| Attribute | Value |
|-----------|-------|
| **ID** | FR-19 |
| **Priority** | Low |
| **Component** | `App.tsx`, `TopAppBar.tsx`, `tailwind.css` |

**Description:** The system shall support three text size presets for accessibility.

**Acceptance Criteria:**
- AC-01: Three presets: default (14px base), big (17px base), largest (20px base).
- AC-02: The text size selector is in the top app bar dropdown.
- AC-03: Selection applies a CSS class (`text-size-default`, `text-size-big`, `text-size-largest`) to the root element.
- AC-04: All typography tokens (headline, body, label) are scaled proportionally.
- AC-05: Preference is persisted to `chrome.storage.local`.

---

### FR-20: Toast Notifications

| Attribute | Value |
|-----------|-------|
| **ID** | FR-20 |
| **Priority** | Medium |
| **Component** | `Toast.tsx`, `content.tsx` |

**Description:** The system shall display toast notifications for user feedback.

**Acceptance Criteria:**
- AC-01: Toast types: info, warning, error, success.
- AC-02: Toasts auto-dismiss after 3.5 seconds with fade+slide animation.
- AC-03: Toasts are stacked vertically with a maximum of 3 visible.
- AC-04: Toasts have themed styling (accent bar, icon, background color).
- AC-05: The content script has its own inline-styled toast system (independent of React).
- AC-06: Content script toasts sync theme from `chrome.storage.local`.
- AC-07: Only one toast is shown at a time in the content script (replaces previous).

---

### FR-21: Confirmation Dialogs

| Attribute | Value |
|-----------|-------|
| **ID** | FR-21 |
| **Priority** | Low |
| **Component** | `ConfirmDialog.tsx` |

**Description:** The system shall display confirmation dialogs for destructive actions.

**Acceptance Criteria:**
- AC-01: Dialogs have a title, message, confirm button, and cancel button.
- AC-02: Two variants: danger (red confirm button) and primary (green confirm button).
- AC-03: Dialogs are modal with a dark overlay backdrop.
- AC-04: Used for: resume upload confirmation, clear history, clear resume.

---

### FR-22: Multi-Screenshot Support

| Attribute | Value |
|-----------|-------|
| **ID** | FR-22 |
| **Priority** | Medium |
| **Component** | `ScamScanView.tsx`, `capture.ts` |

**Description:** The system shall support scanning multiple screenshots of the same job posting.

**Acceptance Criteria:**
- AC-01: Users can capture up to 4 screenshots per scan session.
- AC-02: Screenshots are displayed in a responsive grid (1-4 columns).
- AC-03: Each screenshot has a remove button (X icon).
- AC-04: All screenshots are sent as an array to the backend.
- AC-05: The backend treats multiple images as parts of the same job posting.

---

### FR-23: Lightbox Preview

| Attribute | Value |
|-----------|-------|
| **ID** | FR-23 |
| **Priority** | Low |
| **Component** | `ScamScanView.tsx` |

**Description:** The system shall provide a full-screen lightbox for screenshot preview.

**Acceptance Criteria:**
- AC-01: Clicking a screenshot thumbnail opens a full-screen lightbox.
- AC-02: The lightbox shows the image at full resolution.
- AC-03: Previous/Next navigation arrows are available for multi-screenshot sessions.
- AC-04: Clicking the backdrop or pressing Escape closes the lightbox.
- AC-05: A close button (X) is available in the top-right corner.

---

### FR-24: Progress Streaming (SSE)

| Attribute | Value |
|-----------|-------|
| **ID** | FR-24 |
| **Priority** | Critical |
| **Component** | `api.ts`, `scan.py` |

**Description:** The system shall stream real-time progress updates from the backend to the frontend using Server-Sent Events.

**Acceptance Criteria:**
- AC-01: All AI-powered endpoints return `text/event-stream` responses.
- AC-02: Progress events contain `percent` (0-100) and `stage` (descriptive text).
- AC-03: Stages include: "Preparing request", "Sent to AI", "Analyzing", "Parsing result", "Matching".
- AC-04: A final `result` event contains the complete response data.
- AC-05: Error events contain a user-friendly error message.
- AC-06: The frontend parses SSE lines prefixed with `data: `.
- AC-07: Progress is displayed in the side navigation and view-level progress bars.
- AC-08: The 300-second AI timeout is enforced both client-side and server-side.

---

### FR-25: Backend API Endpoints

| Attribute | Value |
|-----------|-------|
| **ID** | FR-25 |
| **Priority** | Critical |
| **Component** | `backend/app/routers/scan.py` |

**Description:** The backend shall expose the following REST API endpoints.

**Endpoints:**

| Endpoint | Method | Rate Limit | Description |
|----------|--------|-----------|-------------|
| `/api/scan` | POST | 5/min | Scan job posting images (SSE stream) |
| `/api/scan-text` | POST | 5/min | Scan job posting text (SSE stream) |
| `/api/analyze-resume` | POST | 5/min | Parse resume into structured data (SSE stream) |
| `/api/match-resume` | POST | 10/min | Match resume against job postings (SSE stream) |
| `/api/verify` | POST | 10/min | External verification via Tavily + AI (SSE stream) |
| `/api/analyze-offer` | POST | 5/min | Assess an offer naming no employer (SSE stream) |
| `/health` | GET | 30/min | Health check / reachability probe |

**Acceptance Criteria:**
- AC-01: All endpoints use Pydantic models for request/response validation.
- AC-02: All AI endpoints return SSE streaming responses.
- AC-03: Rate limiting is enforced per IP address.
- AC-04: Invalid requests return structured error responses.
- AC-05: The backend runs on FastAPI with async support.
- AC-06: `/api/verify` accepts a `VerifyRequest` with `company_name`, `job_summary`, and `red_flags`. It returns `items`, `evidence`, `report`, `recommendation`, `search_ok`, `search_error`, and the score breakdown.
- AC-07: `/api/verify` logs the raw AI response and parsed results for debugging.
- AC-08: `/api/analyze-offer` is called when a posting names no employer, so the user still receives a verdict on what the post asks for.
- AC-09: If the scan result has no `verification_context` (missing company name), `/api/verify` is never called. See FR-31.

---

### FR-26: AI Concurrency Control

| Attribute | Value |
|-----------|-------|
| **ID** | FR-26 |
| **Priority** | High |
| **Component** | `ai_limiter.py` |

**Description:** The backend shall limit concurrent AI provider calls to prevent overload.

**Acceptance Criteria:**
- AC-01: A semaphore-based limiter caps simultaneous AI calls (default: 2).
- AC-02: A queue depth limit rejects burst overflow with HTTP 503 (default: 10).
- AC-03: Requests wait up to 10 seconds for a semaphore slot before timing out.
- AC-04: Individual AI calls have a 120-second timeout.
- AC-05: The limiter exposes stats: active count, queued count, available slots.
- AC-06: All AI endpoints acquire the limiter before calling the AI provider.

---

### FR-27: Rate Limiting

| Attribute | Value |
|-----------|-------|
| **ID** | FR-27 |
| **Priority** | Medium |
| **Component** | `rate_limit.py` |

**Description:** The backend shall enforce rate limiting on API endpoints.

**Acceptance Criteria:**
- AC-01: Rate limiting uses `slowapi` with IP-based key function.
- AC-02: Scan endpoints: 5 requests per minute.
- AC-03: Match endpoint: 10 requests per minute.
- AC-04: Rate-limited requests receive HTTP 429 responses.

---

### FR-28: Invalid Content Handling

| Attribute | Value |
|-----------|-------|
| **ID** | FR-28 |
| **Priority** | Medium |
| **Component** | `InvalidContentError.tsx`, `scan.py` |

**Description:** The system shall handle cases where the scanned content is not a valid job posting.

**Acceptance Criteria:**
- AC-01: The AI returns `VALID: false` when the content is not a job posting.
- AC-02: The frontend displays an `InvalidContentError` card with a pulsing warning icon.
- AC-03: The error card includes a message explaining the content was not recognized as a job posting.
- AC-04: A "Try Again" action is available to restart the scan.

---

### FR-29: Clear History & Resume

| Attribute | Value |
|-----------|-------|
| **ID** | FR-29 |
| **Priority** | Low |
| **Component** | `ResumeMatchView.tsx`, `App.tsx` |

**Description:** The system shall allow users to clear their scan history and uploaded resume.

**Acceptance Criteria:**
- AC-01: A "Clear History" button is available in the match view.
- AC-02: Clicking it shows a confirmation dialog before deletion.
- AC-03: Clearing history removes all scanned jobs and match results.
- AC-04: Users can remove the uploaded resume via the Remove button.
- AC-05: Removing the resume clears parsed resume data from state.

---

### FR-30: Popup UI

| Attribute | Value |
|-----------|-------|
| **ID** | FR-30 |
| **Priority** | Low |
| **Component** | `entrypoints/popup/` |

**Description:** The extension shall provide a popup UI when the toolbar icon is clicked.

**Acceptance Criteria:**
- AC-01: The popup is 320px wide.
- AC-02: It displays the Trabahero branding and "Open Trabahero" CTA button.
- AC-03: Two feature cards describe Scam Scan and Resume Match capabilities.
- AC-04: A Floating Button toggle switch allows enabling/disabling the FAB.
- AC-05: The FAB toggle state is persisted to `chrome.storage.local`.

### FR-31: Postings With No Employer Name

| Attribute | Value |
|-----------|-------|
| **ID** | FR-31 |
| **Priority** | High |
| **Component** | `CompanyNameNeeded.tsx`, `OfferAnalysisCard.tsx`, `RiskGauge.tsx`, `riskDisplay.ts` |

**Description:** A posting that names no employer cannot be looked up. The system shall say so plainly, ask for the name, and still deliver a verdict on the offer itself.

**Acceptance Criteria:**
- AC-01: When `isValidJob && !companyName`, `/api/verify` is not called and `CompanyNameNeeded` replaces the verification section entirely.
- AC-02: The panel is styled with a **dashed** border where every result container uses a solid one, so a missing input cannot be misread as a finding.
- AC-03: The panel states what was and was not checked, and says explicitly that it is **not a warning about the post** — a fact about our own output rather than a claim about how common nameless posts are.
- AC-04: The panel tells the reader to pick the part of the page showing a logo, letterhead, or sender name and scan again.
- AC-05: Scans are always screenshots, so this state is never about a missing image. It is about the captured region not containing an employer name.
- AC-06: **There is no text input for the company name.** A typed name flows straight into the verification prompt, which produces a verdict naming a real company. Guidance only, by decision.
- AC-07: `/api/analyze-offer` still assesses the offer on its own terms, so the user receives what the post asks for, what it offers, and what to check.
- AC-08: The risk gauge shows "Unverified" (FR-08, AC-09) rather than a score, because the employer was never checked.

### FR-32: Risk-Ordered Result Layout

| Attribute | Value |
|-----------|-------|
| **ID** | FR-32 |
| **Priority** | High |
| **Component** | `ScamScanView.tsx`, `riskDisplay.ts`, `riskAccent.ts`, `useFlipReorder.ts` |

**Description:** When a settled score is high or critical, the panel shall lead with the evidence for that score rather than with explanatory prose.

**Acceptance Criteria:**
- AC-01: A high or critical score reorders the results so the evidence group (Red Flags, Offer Analysis, External Verification) sits directly below the risk gauge, above Posting Analysis, Job Summary, and the screenshot thumbnails.
- AC-02: The reordering applies only once verification and offer analysis have both finished. The scan returns a posting-stage score that the employer stage blends into, so promoting on the intermediate value would move the evidence out from under the reader and then move it back.
- AC-03: A **failed** verification still promotes. The posting-stage score is real, and what is missing is the employer lookup rather than the red flags.
- AC-04: An unverified or low or moderate score never promotes, and keeps the normal order.
- AC-05: Both orderings remain mounted; which one leads is expressed as `order` on the panel's flex column. Remounting would reset a collapsed Sources disclosure and would leave nothing to animate.
- AC-06: The reorder is animated in both directions so the blocks travel to their new positions. A fade is not used: dissolving and reappearing elsewhere reads as a glitch. The animation is disabled under `prefers-reduced-motion`.
- AC-07: The action bar remains pinned to the bottom of the panel. `order` applies to every sibling of the flex column, so the bar and the capture preview carry explicit order values ahead of neither the promoted nor the demoted group.
- AC-08: The risk level is reflected in the chrome — the verification section's header, border, and surface, and the primary action button — using semantic design tokens, never a literal colour value.
- AC-09: **Body prose is never recoloured by risk level.** Long blocks of red or amber on a light surface are the hardest thing on the panel to read, and the panel is where a reader reads a verdict carefully enough to act on it.
- AC-10: The accent applies only while a result is displayed and is removed automatically when a new element is picked, with no timer of its own.

---

## 4. Non-Functional Requirements

### NFR-01: Performance

| Attribute | Value |
|-----------|-------|
| **ID** | NFR-01 |
| **Category** | Performance |

**Requirements:**

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| Side panel open time | < 500ms | Time from toolbar click to side panel fully rendered |
| Screenshot capture | < 200ms | Time from element selection to base64 image available |
| AI scan latency (cloud) | < 60s typical | Time from request to first SSE progress event |
| AI scan latency (local model) | < 30s typical | Time from request to first SSE progress event (self-hosted OpenAI-compatible endpoint) |
| Resume parsing | < 45s typical | Time from upload to structured data returned |
| Resume matching | < 60s typical | Time from match request to results |
| UI render (side panel) | < 100ms | Time for view switch animation |
| SSE progress update interval | ≤ 500ms | Frequency of progress events from backend |
| Content script injection | < 100ms | Time for FAB to appear after page load |
| Extension bundle size | < 500KB | Total extension size (excluding AI models) |
| Screenshot payload | < 1MB per image | JPEG compression at 0.8 quality, max 1280px dimension |

---

### NFR-02: Reliability & Fault Tolerance

| Attribute | Value |
|-----------|-------|
| **ID** | NFR-02 |
| **Category** | Reliability |

**Requirements:**

| Requirement | Description |
|-------------|-------------|
| AI timeout handling | 300-second timeout on AI calls; graceful error message on timeout |
| Network failure recovery | API errors display user-friendly messages; no crashes |
| Backend unavailability | Extension remains functional; scan buttons show error toasts |
| Parse failure recovery | Malformed AI responses return "unreadable response" error |
| Graceful degradation | A failed web search is reported as **unknown**, never as a clean company. `SearchOutcome.ok` is separate from `.results` so a retrieval failure cannot be read as an absence of findings, and the verification score is omitted entirely when every category is unconfirmed. |
| Concurrent request handling | Bounded semaphore prevents AI provider overload |
| Queue overflow protection | HTTP 503 returned when queue depth exceeded |
| Invalid input handling | Non-image inputs, empty text, oversized files rejected with clear errors |
| Content script isolation | Picker/crop functionality cleaned up on deactivation |
| State preservation | View state preserved across tab switches (no unmounting) |

---

### NFR-03: Security

| Attribute | Value |
|-----------|-------|
| **ID** | NFR-03 |
| **Category** | Security |

**Requirements:**

| Requirement | Description |
|-------------|-------------|
| Manifest V3 | Extension uses Manifest V3 for enhanced security |
| Minimal permissions | Only `activeTab`, `storage`, `tabs`, `sidePanel` requested |
| Host permissions | Scoped to `<all_urls>` (required for content script) + backend URL |
| No secrets in code | API keys stored in `backend/.env`, never committed |
| Input validation | All API inputs validated via Pydantic models |
| CORS configuration | Backend restricts cross-origin access |
| Content Security Policy | Default CSP enforced by Manifest V3 |
| HTTPS enforcement | API calls to backend use HTTP (local) or HTTPS (production) |
| No eval() usage | No dynamic code execution in extension or backend |
| Sanitized output | AI responses are parsed, not rendered as raw HTML |
| Client authentication | Extension sends `X-Trabahero-Client-Key` header; backend validates via `require_client_key` dependency against `CLIENT_SECRET_KEY` env var; returns 401 on mismatch |

---

### NFR-04: Usability & Accessibility

| Attribute | Value |
|-----------|-------|
| **ID** | NFR-04 |
| **Category** | Usability |

**Requirements:**

| Requirement | Description |
|-------------|-------------|
| One-click scanning | FAB + element picker requires minimal user interaction |
| Visual feedback | Progress bars, loading skeletons, toast notifications for all operations |
| Error messaging | All errors use friendly, actionable language (no technical jargon) |
| Text size scaling | Three presets (default/big/largest) for readability |
| Dark/light themes | High-contrast themes for different lighting conditions |
| Consistent design | Material Design 3 semantic tokens used throughout |
| Responsive layout | Side panel adapts to Chrome's resizable side panel (320-500px) |
| Keyboard navigation | Escape key cancels picker/crop/lightbox |
| Click-outside-to-close | Dropdowns and dialogs close on outside click |
| Filipino context | System prompts aware of Philippine email/phone/government norms |

---

### NFR-05: Compatibility

| Attribute | Value |
|-----------|-------|
| **ID** | NFR-05 |
| **Category** | Compatibility |

**Requirements:**

| Requirement | Description |
|-------------|-------------|
| Browser | Google Chrome 114+ (sidePanel API support) |
| OS | Windows, macOS, Linux (Chrome is cross-platform) |
| Manifest | Manifest V3 (required for sidePanel API) |
| AI providers | OpenRouter (OpenAI-compatible API); any compatible endpoint can be swapped in via config |
| AI models | Model ID configurable via `MODEL_NAME`; multimodal model required for image scans |
| File formats | PDF, DOCX, TXT, PNG, JPG, JPEG for resume upload |
| Python | 3.10+ required for backend |
| Node.js | 18+ required for extension build |
| WXT Framework | 0.20.x (web extension tooling) |

---

### NFR-06: Maintainability

| Attribute | Value |
|-----------|-------|
| **ID** | NFR-06 |
| **Category** | Maintainability |

**Requirements:**

| Requirement | Description |
|-------------|-------------|
| Modular architecture | Backend uses router/service/model separation, with scanner workflows under `backend/app/services/scanner/` |
| TypeScript strict mode | Extension uses TypeScript with strict type checking |
| Component-based UI | React components with clear separation of concerns |
| Centralized types | All TypeScript interfaces in `types/index.ts` |
| CSS variables | Theme tokens defined in `tailwind.css`, not hardcoded |
| Semantic tokens | Tailwind classes use `bg-background`, `text-on-surface`, never raw hex |
| Configurable prompts | System prompts loaded from `.md` files, not hardcoded |
| Environment config | Backend settings via `pydantic-settings` + `.env` |
| No build-time codegen | WXT handles manifest generation automatically |
| Type checking | `npm run compile` (tsc --noEmit) for type validation |

---

### NFR-07: Scalability

| Attribute | Value |
|-----------|-------|
| **ID** | NFR-07 |
| **Category** | Scalability |

**Requirements:**

| Requirement | Description |
|-------------|-------------|
| Concurrent users | Backend supports 2+ simultaneous AI calls (configurable) |
| Queue depth | Up to 10 queued requests before 503 (configurable) |
| Horizontal scaling | FastAPI async design supports multiple worker processes |
| AI provider flexibility | Provider and model are configuration only (`AI_API_URL`, `MODEL_NAME`); no code changes required |
| Rate limiting | Per-IP rate limits prevent abuse (5-10 req/min); proxy-safe via X-Forwarded-For/X-Real-IP header inspection |
| Stateless backend | No session state stored server-side |
| Configurable limits | All concurrency/queue/timeout values in `backend/.env` |

---

### NFR-08: Privacy & Data Protection

| Attribute | Value |
|-----------|-------|
| **ID** | NFR-08 |
| **Category** | Privacy |

**Requirements:**

| Requirement | Description |
|-------------|-------------|
| No user accounts | No authentication or user registration required |
| No persistent storage | All data stored in-memory or `chrome.storage.local` (session-only) |
| No analytics tracking | No telemetry, analytics, or tracking scripts |
| AI provider isolation | The extension never calls the AI provider directly; all model traffic is proxied through the backend, which holds the API key |
| Minimal data collection | Only job posting content and resume data are processed |
| No data sharing | AI provider receives only the scanned content, no user identifiers |
| Screenshot retention | Screenshots exist only in memory; not saved to disk |
| Resume data | Parsed resume data is held in React state; not persisted |
| Backend logging | Server logs contain no personally identifiable information |
| Tavily API key | Stored in `backend/.env`, not exposed to the frontend |

---

### NFR-09: Localization

| Attribute | Value |
|-----------|-------|
| **ID** | NFR-09 |
| **Category** | Localization |

**Requirements:**

| Requirement | Description |
|-------------|-------------|
| English (default) | All UI text and AI prompts in English |
| Tagalog/Filipino support | Backend accepts `language: "tagalog"` parameter for AI responses |
| Philippine-aware | System prompts aware of Philippine email norms (Gmail acceptable), phone formats, and SEC/DTI/PEZA/BOI/LGU registration norms |
| Filipino job context | AI trained on Philippine job market scam patterns |
| Currency awareness | Scoring logic aware of Philippine salary ranges |

---

### NFR-10: Configuration & Environment

| Attribute | Value |
|-----------|-------|
| **ID** | NFR-10 |
| **Category** | Configuration |

**Requirements:**

| Requirement | Description |
|-------------|-------------|
| Extension env | `WXT_API_BASE` — backend URL (build-time variable) |
| Extension env | `WXT_CLIENT_KEY` — shared secret for backend auth; must match `CLIENT_SECRET_KEY` |
| Backend env | `AI_API_KEY`, `AI_API_URL`, `MODEL_NAME` — AI provider config |
| Backend env | `TAVILY_API_KEY`, `TAVILY_MAX_RESULTS` — web search. Free tier is 1,000 credits/month, no card required (https://tavily.com) |
| Backend env | `TAVILY_SEARCH_DEPTH` (`basic` = 1 credit, `advanced` = 2 credits, default advanced), `TAVILY_COUNTRY` (default `philippines`; blank disables the boost) — the recall-versus-budget trade, configurable per deployment |
| Backend env | `AI_TEMPERATURE`, `AI_TOP_P`, `AI_MAX_TOKENS` — generation controls |
| Backend env | `AI_REASONING_ENABLED`, `AI_REASONING_MAX_TOKENS`, `AI_REASONING_EFFORT` — reasoning-model controls, mapped to OpenRouter's `reasoning` parameter. `AI_REASONING_ENABLED=false` turns reasoning off outright and is the cleanest option; blank sends nothing |
| Backend env | `AI_MAX_CONCURRENT`, `AI_MAX_QUEUE_DEPTH` — concurrency limits |
| Backend env | `CLIENT_SECRET_KEY` — shared secret for extension auth; leave empty to disable (dev mode) |
| Theme persistence | `chrome.storage.local` stores `theme`, `textSize`, `fabEnabled` |
| Startup order | Backend → Extension |
| Dev workflow | `npm run dev` for extension; `uvicorn --reload` for backend |
| Build output | `.output/` directory (gitignored) contains production extension |

---

### NFR-11: Test Isolation & External Service Safety

| Attribute | Value |
|-----------|-------|
| **ID** | NFR-11 |
| **Category** | Testing & Network Safety |

**Requirements:**

| Requirement | Description |
|-------------|-------------|
| Offline default suite | `python -m pytest tests/ -q` uses deterministic fakes and mocks; it makes no live OpenRouter/LLM, Tavily, DNS, or other external API calls. Two layers enforce this: an autouse fixture swaps every AI and search boundary for a fake, and a session-scoped guard raises on any non-loopback DNS resolution. |
| Service-boundary isolation | Tests mock external clients before invoking endpoints, including the AI provider, Tavily, and email/DNS services. |
| Auth and route coverage | Tests that assert authentication, routing, parsing, or SSE format also mock AI and search dependencies. |
| Explicit live-provider opt-in | Live-provider tests use a separate command or environment flag and never run in the default suite. |
| Quota protection | Local verification must not spend provider credits or external-service quotas. |

---

## 5. Data Models

### ScanResult

```typescript
interface ScanResult {
  riskLevel: 'low' | 'moderate' | 'high' | 'critical' | null;
  riskLabel: string;              // "Low Risk", "Moderate Risk", "High Risk", "Critical Risk"
  riskScored: boolean;            // false only for history predating the posting stage
  riskScore: number | null;       // 0-100, from the two-stage blend
  unverifiedEmployer?: boolean;   // no name + no red flags: "Unverified", not 0 / Low Risk
  scanningTarget: string;
  redFlags: RedFlag[];
  flagsCritical: boolean;
  isJobPosting: boolean;
  companyName?: string | null;    // the employer the reader would work for
  jobSummary?: string;            // what the role is
  postingAnalysis?: string;       // the verdict on the posting
  emailVerifications?: EmailCheck[];
  scoreBreakdown?: ScoreBreakdown;
  verificationResult?: VerificationResult;
  verificationLoading?: boolean;
  verificationError?: boolean;
}
```

### VerificationResult

```typescript
interface VerificationResult {
  items: VerificationItem[];
  evidence?: VerificationEvidence[];   // results a reader can open
  report: string;
  recommendation: string;
  searchOk?: boolean;                  // false = the categories are unknown, not clear
  searchError?: string;
}

interface VerificationEvidence {
  title: string;
  url: string;
  snippet: string;
}
```

### VerificationItem

```typescript
interface VerificationItem {
  label: string;             // "Company Existence" | "Official Registration" | "Reputation"
  status: 'green' | 'yellow' | 'red';
  explanation: string;       // the `finding`: the fact that decided the status
  source_title?: string;     // copied from the search results
  source_url?: string;       // copied from the search results, never constructed
}
```

### RedFlag

```typescript
interface RedFlag {
  id: string;
  title: string;
  description: string;
  icon: IconName;
  severity?: 'low' | 'mid' | 'high';
}
```

### ResumeData

```typescript
interface ResumeData {
  skills: string[];
  experience_years: number;
  job_titles: string[];
  industries: string[];
  summary: string;
}
```

### JobMatchItem

```typescript
interface JobMatchItem {
  jobId: string;
  score: number;           // 0-100
  label: string;           // "High/Medium/Low Compatibility"
  skillGaps: string[];
  matchedSkills: string[];
  reasoning?: string;
  experienceFit?: string;
  industryFit?: string;
  recommendedActions?: string[];
}
```

### ScannedJob

```typescript
interface ScannedJob {
  id: string;
  title: string;
  summary: string;
  timestamp: string;
  scanResult: ScanResult;
}
```

---

## 6. API Reference

All API endpoints (except `GET /health`) require the `X-Trabahero-Client-Key` header. The extension generates a unique key per instance, stores it in `chrome.storage.local`, and sends it with every request. The backend validates this against the `CLIENT_SECRET_KEY` environment variable. If `CLIENT_SECRET_KEY` is empty, auth is disabled (development mode). Requests without a valid key receive `401 Unauthorized`.

### POST /api/scan

Scans job posting images for scam indicators.

**Request:**
```json
{
  "images_base64": ["<base64-encoded-png>", ...],
  "language": "english"
}
```

**Response:** SSE stream with progress events and final result.

### POST /api/scan-text

Scans job posting text for scam indicators.

**Request:**
```json
{
  "text": "Job posting text content...",
  "language": "english"
}
```

**Response:** SSE stream with progress events and final result.

### POST /api/analyze-resume

Parses a resume file into structured data.

**Request:**
```json
{
  "file_base64": "<base64-encoded-file>",
  "file_type": "pdf"
}
```

**Response:** SSE stream with progress events and `ResumeData` result.

### POST /api/match-resume

Matches a resume against scanned job postings.

**Request:**
```json
{
  "resume": {
    "skills": ["JavaScript", "React"],
    "experience_years": 3,
    "job_titles": ["Frontend Developer"],
    "industries": ["Information Technology"],
    "summary": "Experienced frontend developer..."
  },
  "jobs": [
    { "id": "job-1", "title": "Web Developer", "summary": "..." }
  ]
}
```

**Response:** SSE stream with progress events and match results.

### POST /api/verify

Looks up a named employer and reports the three verification categories.

**Request:**
```json
{
  "company_name": "Jollibee Foods Corporation",
  "job_summary": "The role is a crew member at Jollibee...",
  "red_flags": [{ "flag": "...", "reasoning": "...", "severity": "high" }]
}
```

**Response:** SSE stream. The final `result` event carries `items`, `evidence`, `report`, `recommendation`, `riskScore`, `riskLevel`, `scoreBreakdown`, `search_ok`, `search_error`, and `search_count`.

Only the search results are sent to the model. The job summary and the posting's red flags are deliberately excluded: the model is asked what the search shows about a *company*, and handing it a posting red flag invites it to answer about the posting instead.

### POST /api/analyze-offer

Assesses an offer that names no employer, so there is nothing to look up. One AI call, no search.

**Request:**
```json
{
  "text": "Offer text content...",
  "company_name": "",
  "language": "english"
}
```

**Response:** SSE stream carrying `kind`, `verdict`, `what_it_asks`, `what_it_offers`, `what_to_check`, and `is_offer`.

---

## 7. Traceability Matrix

| Requirement | Component(s) | Status |
|-------------|-------------|--------|
| FR-01 | TopAppBar, SideNav, Footer, App.tsx | Implemented |
| FR-02 | content.tsx, PickerButton, capture.ts | Implemented |
| FR-03 | content.tsx, PickerButton, capture.ts | Implemented |
| FR-04 | content.tsx | Implemented |
| FR-05 | ScamScanView, api.ts, scan.py | Implemented |
| FR-06 | api.ts, scan.py | Implemented |
| FR-07 | lm_client.py, services/scanner/, SYSTEM_PROMPT.md | Implemented |
| FR-08 | scan.py, RiskGauge.tsx | Implemented |
| FR-09 | RedFlagsList, RedFlagCard | Implemented |
| FR-10 | search.py, verification_flow.py, verification_prompt.py | Implemented — Tavily, one query, ok/results independent |
| FR-11 | search.py, verification_prompt.py, VerificationCard | Implemented — Official Registration (SEC/DTI/PEZA/BOI/LGU) |
| FR-12 | email_verifier.py, ScamScanView | Implemented |
| FR-13 | verification_flow.py, verification_prompt.py, VerificationSection | Implemented — findings + clickable sources, grey neutral state |
| FR-14 | ResumeUploader, ResumePreview, api.ts, scan.py | Implemented |
| FR-15 | ResumeMatchView, JobMatchList, api.ts, scan.py | Implemented |
| FR-16 | ResumeMatchView, App.tsx | Implemented |
| FR-17 | ResumeMatchView | Implemented |
| FR-18 | App.tsx, TopAppBar, tailwind.css | Implemented |
| FR-19 | App.tsx, TopAppBar, tailwind.css | Implemented |
| FR-20 | Toast.tsx, content.tsx | Implemented |
| FR-21 | ConfirmDialog.tsx | Implemented |
| FR-22 | ScamScanView, capture.ts | Implemented |
| FR-23 | ScamScanView | Implemented |
| FR-24 | api.ts, scan.py | Implemented |
| FR-25 | scan.py | Implemented |
| FR-26 | ai_limiter.py | Implemented |
| FR-27 | rate_limit.py | Implemented |
| FR-28 | InvalidContentError.tsx, scan.py | Implemented |
| FR-29 | ResumeMatchView, App.tsx | Implemented |
| FR-30 | entrypoints/popup/ | Implemented |
| FR-31 | CompanyNameNeeded, OfferAnalysisCard, RiskGauge, riskDisplay.ts | Implemented — missing name is a missing input, not a red flag |
| FR-32 | ScamScanView, riskDisplay, riskAccent, useFlipReorder, ScanActions | Implemented — high/critical leads with the evidence |
| NFR-01 | All components, imageUtils.ts | Implemented |
| NFR-02 | api.ts, ai_limiter.py, scan.py | Implemented |
| NFR-03 | wxt.config.ts, config.py, core/auth.py, api.ts | Implemented |
| NFR-04 | TopAppBar, tailwind.css, Toast | Implemented |
| NFR-05 | wxt.config.ts, package.json, requirements.txt | Implemented |
| NFR-06 | Project structure, services/scanner, TypeScript, Tailwind | Implemented |
| NFR-07 | ai_limiter.py, rate_limit.py (_get_client_ip) | Implemented |
| NFR-08 | No auth, no persistence, local AI option | Implemented |
| NFR-09 | scan.py (language param), system prompts | Implemented |
| NFR-10 | .env files, config.py, App.tsx, api.ts | Implemented |
| NFR-11 | Test suite, service boundaries, provider configuration | Implemented — Default pytest runs offline; live providers require explicit opt-in |

---

*Document generated from codebase analysis. All requirements reflect the current implemented state of Trabahero v0.5.0.*

*Notes on this revision (0.4.0 → 0.5.0): a settled high or critical score now promotes the evidence above the prose and tints the panel chrome (FR-32); the verification recommendation is addressed to a job seeker rather than assigning a registry lookup; the scan prompt's severity list no longer offers a missing employer as an example of a low-severity flag, which had been scoring nameless postings at 4; and a scanned job's stored result is replaced when verification lands, so a history entry no longer disagrees with the panel about the same posting.*

*Earlier revision (0.3.0 → 0.4.0): web search moved from DuckDuckGo scraping to the Tavily API; the SEC-only registration check was widened to "Official Registration"; the AI-provided `VERDICT_PERCENTAGE` score was replaced by the two-stage posting/verification blend; a missing employer name became a distinct state rather than a red flag; search relevance was fixed by the `country` boost and a suffix strip rather than by category tokens; the credit knobs became environment values; and the temporary search debug surface (`/api/debug/search`, `SearchRawPanel`, `SearchOutcome.raw_response`) was removed once the ranking fix was confirmed by a real run.*


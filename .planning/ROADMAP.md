# ROADMAP: Traba-Hero Frontend

## Phase 1: Foundation & WXT Setup
Setup the web extension foundation and configure resources.

**Requirements:**
- WXT-01 (Setup WXT project with Tailwind CSS support)
- WXT-02 (Load custom fonts and Material symbols)

**Deliverables:**
- Working WXT extension shell that builds successfully
- Configured `tailwind.config.js` with Stitch design system tokens
- Global styles loading Inter and Hanken Grotesk fonts

---

## Phase 2: Scam Scan Sidebar UI
Implement the visual scam scanning side panel screen matching the Stitch design.

**Requirements:**
- SCAN-01 (Top App Bar matching design)
- SCAN-02 (Navigation sidebar tabs)
- SCAN-03 (Security Status Banner)
- SCAN-04 (circular SVG Risk Gauge)
- SCAN-05 (Red Flags list)
- SCAN-06 (Re-scan active page button with rotation animation)

**Deliverables:**
- Isolated shadow DOM container for the extension sidebar
- Complete Scam Scan sidebar panel UI matching design.html mockup
- Responsive interactive elements (hover states, click animations)

---

## Phase 3: FastAPI Backend
Scratch-built modular FastAPI backend with OpenRouter AI integration.

**Requirements:**
- BACK-01 (FastAPI app factory — not monolithic main.py)
- BACK-02 (POST /api/scan endpoint with image → AI → verdict flow)
- BACK-03 (Job post prefilter before full AI analysis)
- BACK-04 (Typed request/response schemas with Pydantic)
- BACK-05 (Structured JSON verdict: verdict_percentage, red_flags, analysis, recommended_steps)
- BACK-06 (.env config for API keys)

**Deliverables:**
- Modular `backend/app/` structure (config, routers/, services/, models/)
- OpenRouter integration via `openai` SDK
- `requirements.txt`, `.env.example`, `.gitignore`

**Files:** `backend/` (all ~15 files)

---

## Phase 4: Resume Match Sidebar UI
Implement the resume matching side panel screen and sidebar tab navigation.

**Requirements:**
- MATCH-01 (Active Resume card)
- MATCH-02 (Match Score gauge and progress bar)
- MATCH-03 (Skill Gaps layout)
- MATCH-04 (Top Match Keywords list)
- MATCH-05 (Apply with Match button)
- SCAN-02 (Active sidebar navigation between scan and match views)

**Deliverables:**
- Resume Match sidebar panel UI matching design.html mockup
- Seamless tab navigation in sidebar to switch views

---

## Phase 5: API Integration & End-to-End Verification
Connect UI actions to backend services and run verification checks.

**Requirements:**
- INT-01 (Connect Scan UI trigger to backend API) — ✅ DONE
- INT-02 (Connect Resume Match UI to backend API) — pending

**Deliverables:**
- Fully integrated Chrome extension sidebars communicating with FastAPI backend
- Final verification of mock scan responses and visual states

**Plans:** 3 plans in 3 waves

**Wave 1** *(foundation)*
- [x] 05-01 — API Client module with scanScreenshot() and matchResume()
- Note: Scan integration done; ResumeMatch still needs wiring

**Wave 2** *(scan integration)*
- [x] 05-02 — Wire ScamScanView to real `POST /api/scan`

**Wave 3** *(match integration)*
- [ ] 05-03 — Wire ResumeMatchView to real backend API

**Cross-cutting constraints:**
- API error handling must never crash the UI
- Existing demo data serves as fallback when API is unavailable
- All plans must pass `tsc --noEmit`

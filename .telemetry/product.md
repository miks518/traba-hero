# Product: Trabahero

**Last updated:** 2026-10-31
**Method:** codebase scan + conversation

## Product Identity

- **One-liner:** A job seeker screenshots a job posting or recruiter chat and gets a
  defensible assessment — including whether the named employer actually exists —
  before they send money, documents, or personal information to it.
- **Category:** B2C privacy/security tool (AI-assisted consumer protection)
- **Product type:** B2C — no accounts, no organizations, no tenancy of any kind.
  Entity-level tracking reduces to anonymous events; there is nothing to identify.
- **Collaboration:** single-player

Context note that no other product of this shape has: the product is *privacy
tooling under the Philippine Data Privacy Act (RA 10173)*. Its consent notice
promises in-memory processing and no kept copies of personal content. That promise
is enforced by tests, not prose (`backend/tests/test_resume_content_not_logged.py`),
and the standing constraint is: **the notice's claims move before the code does.**
Telemetry on this product must not smuggle in a retention practice the notice denies.

## Business Model

- **Monetization:** free — thesis product (v0.5.0), no paid surface
- **Pricing tiers:** none
- **Billing integration:** none detected
- Cost sensitivity exists but is operational, not commercial: the OpenRouter key is
  shared and provider credits are treated as test resources. Token/credit usage is
  an analytics signal worth collecting for that reason alone.

## Tech Stack

- **Primary language:** TypeScript (extension) / Python (backend)
- **Framework:** React 19 + WXT (Chrome MV3 side panel extension); FastAPI proxy backend
- **Database:** none — the backend is stateless and retains nothing; the only
  persistence is `chrome.storage.local` on the client (scan history capped at 20,
  manual profile, consent flag, theme, text size)
- **Background jobs:** none
- **HTTP client patterns:** `fetch` (extension → backend), OpenAI-compatible
  streaming client (`lm_client.py` → OpenRouter), Tavily REST (search)
- **Module organization:** WXT entrypoints (`entrypoints/background`,
  `entrypoints/content`, `entrypoints/sidepanel` with `views/`, `components/`,
  `lib/`, `hooks/`); backend is `app/routers` + `app/services/scanner` +
  `app/services` with test-tree enforcements per concern

## Value Mapping

### Primary Value Action

**Scan → assessment.** The reader captures a posting, the scan extracts its claims,
and the verify stage checks the named employer against the open web before a
code-owned level ("Nothing found against it" / "Caution" / "Contradicted") is
issued in the side panel. **If this drops to zero, the product has failed.**
Confirmed with the user 2026-10-31.

### Core Features (directly deliver value)

1. **Scam Scan (`ScamScanView`, `/api/scan`)** — screenshot → anomaly finding →
   streaming result. The entry point for the primary value action.
2. **Employer verification (`/api/verify`)** — web retrieval against the extracted
   employer name; produces the code-owned final assessment. Without it the scan
   returns a posting-stage reading that is not the verdict.
3. **Offer analysis (`/api/analyze-offer`)** — post-only path for offers naming no
   employer; keeps nameless pitches out of the "never verified" dead end.

### Supporting Features (enable core actions)

1. **Resume Match (`ResumeMatchView`, `/api/analyze-resume`, `/api/match-resume`)**
   — ranks verified jobs against the reader's skills; consent-gated on upload.
2. **Element picker + screenshot capture (`content.tsx`)** — the capture affordance
   every scan runs through.
3. **Scan history (`lib/scanHistory.ts`)** — last 20 scans, client-only.
4. **Offline banner + health probe (`useBackendHealth`)** — reachability as a
   first-class UX state; probe cadence 4s.
5. **Manual skills profile (`SkillsProfileForm`)** — privacy-symmetric alternative
   to resume upload; persists by design where the upload does not.

## Entity Model

### Users

- **ID format:** none. There is no auth, no account, no user concept anywhere in
  the system. The only identifiers are client-side scan-entry IDs
  (UUID-format, `scanHistory.ts`-managed) used to key history entries — client-only,
  never sent to the backend.
- **Roles:** none
- **Multi-account:** not applicable

### Accounts

- None. Confirmed with the user 2026-10-31: telemetry must be **strictly anonymous**
  — no user ID, no device ID, no install ID. One bucket, no "whose".

## Group Hierarchy

None. B2C, single-player, no tenancy. There is no `group()` equivalent in this plan,
ever — the design phase must not import the B2B two-entity model's vocabulary.

| Group Type | Parent | Where Actions Happen |
|------------|--------|---------------------|
| — | — | events happen at the product level only |

**Default event level:** product (anonymous)
**Admin actions at:** operator-side server logs, out of the panel's reach

## Current State

- **Existing tracking:** none installed. Zero analytics SDKs (`package.json`
  carries React and nothing else), no tracking calls anywhere in the extension or
  backend, no database, no destination.
- **What exists instead is diagnostic logging, and it already encodes the privacy
  split this product would track under.** `resume_flow.py` / `match_flow.py` log
  token and character counts only — content logging is enforced out by tests.
  `scan_flow.py` / `offer_flow.py` log raw model output on purpose (posting content
  is third-party material under assessment), with a wider zero-retention audit
  still open (`docs/decisions/resume-input-paths.md`).
- **Documentation:** yes, unusually strong — `docs/architecture.md`,
  `docs/decisions/*` decision records, scoring docs.
- **Known issues:** slots blocked on "no database, no destination" — the
  *"Was this accurate?"* feedback control and the *report-the-posting* control are
  deliberately absent (`architecture.md` § report panel). Telemetry is what would
  un-block them, not what they can stand on today.

## Integration Targets

| Destination | Purpose | Priority |
|-------------|---------|----------|
| **First-party backend** (counters only) | All event ingestion; aggregate stats stay operator-side. Confirmed as the destination decision 2026-10-31 | Active choice |
| Third-party analytics SDK (Segment/Amplitude/Mixpanel/PostHog/etc.) | Rejected — creates a new external data flow the consent notice does not cover, imports identity vocabulary this product refuses | None |
| Backend structured logs (existing `trabahero` logger) | Where AI/search/system diagnostics already land; counts and shapes, never resume content | Existing, extends this plan |

### Destination constraints (design-changing)

1. **No identity anywhere.** No user/device/install ID in any event. Any funnel or
   session math must work identity-free or be dropped.
2. **No content properties.** Quotes, text excerpts, URLs, employer names, images
   may never ride an event. The safe set is counts, shapes, durations, closed-set
   codes, status words, and failure class names.
3. **Ingestion lives on the backend**, reached by the same transport the panel
   already trusts — a new SDK in the extension bundle would also hit MV3
   remote-script restrictions.
4. **Consent text moves first.** If analytics expands beyond what the existing RA
   10173 notice covers, the notice changes before the wiring does.

## Codebase Observations

- **Feature areas inferred:** Scam Scan (capture → scan → verify → report panel),
  Offer Analysis (post-only fallback), Resume Match (upload/manual profile → match
  → filter categories), plus shell-level concerns (health, offline, history).
- **Entity model inferred:** there isn't one — the only structured "entities" are
  scan results (`ScannedJob`: posting + assessment + verification outcome) living
  client-side. Events will therefore name *flows and stages*, not objects.
- **Rate limiting is the only quasi-identity in the system** (`rate_limit.py`
  keyed on socket peer) — diagnostics-only, transient, and out of scope for events.

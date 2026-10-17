# Architecture

Trabahero is a job-scam detection browser extension for Filipino job seekers. It uses AI
(OpenRouter) to analyse job postings for fraud signals.

**Two tiers:**

- **Extension** (repo root): React 19 + TypeScript + Tailwind, built with WXT
- **Backend** (`backend/`): FastAPI Python proxy — calls OpenRouter

Decision records explaining *why* any of this is shaped this way live in
`docs/decisions/`.

---

## Extension

| Path | Role |
|---|---|
| `entrypoints/background.ts` | Opens the sidepanel on toolbar click |
| `entrypoints/content.tsx` | Element picker overlay for screenshot capture |
| `entrypoints/sidepanel/` | Main React app (views, components, types) |
| `entrypoints/sidepanel/lib/api.ts` | HTTP client → backend URL; `pingHealth()` is the `GET /health` reachability probe |
| `entrypoints/sidepanel/hooks/useBackendHealth.ts` | Reachability polling |
| `entrypoints/sidepanel/lib/imageUtils.ts` | Screenshot compression |
| `entrypoints/sidepanel/lib/scanHistory.ts` | Stored scan history and its migrations |
| `entrypoints/sidepanel/lib/riskDisplay.ts` | `isUnverifiedEmployer()` and `shouldElevateEvidence()` — the two pure decisions the scan panel's layout turns on |
| `entrypoints/sidepanel/lib/riskAccent.ts` | Token-based risk colour for chrome |
| `entrypoints/sidepanel/lib/useFlipReorder.ts` | FLIP animation for reordered blocks |
| `entrypoints/sidepanel/views/ScamScanView.tsx` | Job scanning with progress streaming; owns the evidence-promotion layout |
| `entrypoints/sidepanel/views/ResumeMatchView.tsx` | Resume analysis + job matching |
| `entrypoints/sidepanel/components/scan/` | Result cards — see below |
| `entrypoints/sidepanel/components/shell/OfflineBanner.tsx` | "Server Unreachable" strip with a Retry button |

### Screenshot compression

JPEG 0.8, max 1280px on the long edge.

**The cap is a token-budget knob as much as a bandwidth one:** vision cost scales with
pixel area, and the configured model is a reasoning model, so visual input is also what
it deliberates over. Raise it only if dense small print starts scanning badly.

### Scan history

- `migrateScannedJobs()` clears risk scores stored before the posting stage produced a
  real score, **so invented numbers are never displayed as findings.**
- `updateScannedJob()` replaces a stored entry's whole `scanResult` once a later stage
  produces one.
- The `redFlags` → `anomalies` field migration is deliberate — see
  `docs/decisions/anomaly-terminology.md`.

### The report panel

`components/report/` replaces the score-and-gauge panel. Architecture:
`docs/superpowers/specs/2026-10-17-report-panel-architecture.md` §1 (slot stack) and
§7 (migration map). Visual source: `jobposts/stitch/01-do-not-proceed.html`.

| Component | Slot | Notes |
|---|---|---|
| `ReportPanel.tsx` | — | The slot stack, and the promotion restatement below |
| `JobMeta.tsx` | 1–2 | Scan time, role, employer. **No provenance line** — see below |
| `VerdictBlock.tsx` | 3 | Tone container + **authored** headline. Replaces `RiskGauge` |
| `ActionBlock.tsx` | 4 | Two authored instruction lines. The share chips and report control are absent |
| `AnomalyCards.tsx` | 5 | One card per finding. **No code pill, no quote block** — see below |
| `WhatWeChecked.tsx` | 7 | **Asserts checks ran.** Heading derived from state — see below |
| `FullDetails.tsx` | 8 | **Shows what retrieval returned.** Split from §7 for the reason below |
| `ReportFooter.tsx` | 10 | Disclaimer, ruleset version. No scan id — no field carries one |
| `verdictCopy.ts` | 3, 4 | Every authored string. **Nothing here may be model-written** |

`ScamScanView.tsx` is now a composition of this panel plus the capture
affordances. The scan lifecycle lives in `hooks/useScanSession.ts`; the wire
mapping in `lib/mapApiResponse.ts`.

#### Why §7 and §8 are two components

**They answer different questions and carry opposite honesty requirements.** §7
asserts that checks were performed, so a line there that cannot be backed by a
real check is a false claim about coverage wearing the honest hat. §8 shows what
retrieval returned, which is safe to show whether or not it amounts to anything.
Collapsing them back into one component means choosing which rule to obey.

#### `WhatWeChecked` heading rule — unchanged, and it still binds

**The heading is derived from state, never constant.** "What we checked" is
reachable only when checks exist. A lookup still running, one that could not
complete, and one that ran and found nothing each get their own heading.

**A section titled "What we checked" over an empty list asserts checks were
performed when none were.**

Three groups, not two: **Verified**, **Contradicted**, **Could not verify**. A
contradicted claim is not a failed check — it is the check *succeeding* and
finding the opposite of what the posting stated. Folding `red` into either
column loses the single most important thing verification can produce.

`shouldShowCheck` still applies: a `yellow` Reputation is hidden, because it could
only restate an absence and put the word *scam* beside a named employer to do it.

#### Promotion is restated, not kept

The old scheme moved a **pair of sibling groups** — evidence up, prose down — so
the evidence rose above the posting analysis. The new stack is a **single fixed
order** with the verdict and instructions already at the top, so there is nothing
above them to promote.

**Promotion now means the neutral context drops below the findings.** On a settled
high or critical level, `[data-group="context"]` lands under
`[data-group="findings"]`; otherwise it leads. A reader who has just been told not
to send money does not need the coverage count in their first viewport.

Both groups stay mounted across a level change so nothing is torn down.

#### What is absent, and why

Every one of these is a slot the panel cannot yet support. Each is **absent, not
empty** — an empty container asserts something was found or withheld.

| Absent | Why |
|---|---|
| Provenance line ("posted 2 days ago on a job board") | The extension screenshots a region of a page and does not know where the posting came from |
| One-line verdict reason | No short field on the wire. `VerificationResult.report` is multi-sentence and must not be reused here |
| Anomaly `code` pill | The taxonomy is a draft with nothing implemented — `2026-10-17-anomaly-code-set.md` |
| Quote block per anomaly | The most load-bearing gap. Needs a verbatim `quote` **bound** to the posting; a paraphrase cannot be rendered as a quotation |
| "Do not share" chips | Keyed to the code families above. Generic chips would be identical for every posting |
| Report control | Nothing to report the post *to*, for the same reason as the provenance line |
| Coverage count | Its denominator must be a constant the backend owns, or it drifts with whatever the panel renders |
| "Was this accurate?" | No database, no destination for the answer. A dead control reads as a working feature |

#### `riskAccent`

Token-based risk colour for chrome — headers, borders, button. **Never returns a hex or
hsl literal; body prose deliberately has no entry.** Still applied to the primary
capture action, and only while a high or critical level is settled.

---

## Backend

| Path | Role |
|---|---|
| `backend/app/routers/scan.py` | Compatibility facade for all API endpoints + SSE streaming helpers; `/api/verify` includes raw AI response logging |
| `backend/app/services/scanner/` | Modular prompts, SSE, scan, resume, match, parsing, risk, and verification workflows |
| `backend/app/services/lm_client.py` | OpenAI-compatible client (OpenRouter) |
| `backend/app/services/search.py` | Tavily web search — see `docs/decisions/search-retrieval.md` |
| `backend/app/services/scanner/verification_prompt.py` | Loads `VERIFY_PROMPT.md`, owns the response schema and search-context formatters |
| `backend/app/services/scanner/verification_parser.py` | Fallback labeled-text parser |
| `backend/app/services/scanner/offer_prompt.py`, `offer_parser.py`, `offer_flow.py` | Post-only analysis for offers naming no employer; its own endpoint and parser so it cannot break the scan or verify paths |
| `backend/app/services/scanner/risk_calculator.py` | Two-stage scoring — see `docs/scoring.md` |
| `backend/app/config.py` | Settings via pydantic-settings, loads from `backend/.env` |
| `backend/app/rate_limit.py` | Rate limiting — see `docs/decisions/security-boundaries.md` |
| `backend/app/ai_limiter.py` | Concurrency control (semaphore + queue depth) |

### Settings parsing

A blank `AI_REASONING_ENABLED` reads as unset rather than raising: `.env.example` ships
that key blank and tells the reader to leave it blank, which a bare `bool | None` cannot
parse, so a fresh copy used to crash at import.

**Only blank is coerced** — `maybe` still raises, because silently treating nonsense as
unset would leave reasoning at the provider default while the operator believed they had
set it.

`test_env_example.py` parses the shipped example and asserts every model field appears in
it, since nothing else in the repo executes that file.

### Empty responses

`chat_stream_pieces` logs and raises `EmptyModelResponse` when a stream yields no content,
because a mid-stream provider error frame (rate limits included) arrives inside a
successful 200 and is otherwise indistinguishable from an empty answer.

`_create_completion` sends OpenRouter's `reasoning` parameter and falls back once if the
provider rejects it — see `docs/decisions/reasoning-models.md` and
`docs/decisions/parser-resilience.md`.

---

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/scan` | POST | Scan job posting image (SSE stream) |
| `/api/scan-text` | POST | Scan job posting text (SSE stream) |
| `/api/analyze-resume` | POST | Parse resume into structured data (SSE stream) |
| `/api/match-resume` | POST | Match resume against job postings (SSE stream) |
| `/api/verify` | POST | External verification via Tavily + AI (SSE stream) |
| `/api/analyze-offer` | POST | Post-only analysis for offers naming no employer (SSE stream) |
| `/health` | GET | Reachability probe; no client key required, rate limited to 30/minute |

All endpoints return `text/event-stream` with progress events (`percent`, `stage`) and a
final `result` event.

`/api/scan` and `/api/scan-text` assess **offers of work or income**, not just formatted
job adverts. Chat messages, forwarded paragraphs, and recruitment pitches are in scope;
`VALID: false` means the content offers no work or income at all.

### Verification flow

After a successful scan, the backend adds `verification_context` to the scan response
**only if a company name was extracted.** The name comes from the scan's own
`COMPANY NAME:` field, preferred over the `extract_company_name()` regex fallback.

If no company name is found, `verification_context` is absent and the frontend never
calls `/api/verify`; it calls `POST /api/analyze-offer` instead, which assesses the offer
on its own terms and returns a verdict. **Either path produces a score; the employer check
only ever adds to one.**

`/api/verify` logs the raw AI response and parsed items at INFO/WARNING level for
debugging.

---

## System prompts

| Prompt | Used by | Loaded by |
|---|---|---|
| `SYSTEM_PROMPT.md` | Job scan (scan, scan-text) | `load_system_prompt()` in `prompts.py` |
| `VERIFY_PROMPT.md` + `VERIFY_RESPONSE_SCHEMA` | External verification (`/api/verify`) | `load_verify_prompt()` in `scanner/verification_prompt.py` |
| `RESUME_PROMPT.md` | Resume analysis | `load_resume_prompt()` in `prompts.py` |
| `MATCH_PROMPT.md` | Resume-job matching | `load_match_prompt()` in `prompts.py` |

All four prompt files are in `backend/` root, resolved via
`Path(__file__).resolve().parents[3]`.

Verification design — categories, schema, and why the file is the source of truth — is in
`docs/decisions/verification-design.md`.

---

## Structured output

`/api/verify` and `/api/analyze-offer` use OpenRouter's `response_format` with a JSON
Schema instead of a labeled text format. The custom text format existed because the native
model web search broke on curly braces; searches now run in the backend and the model only
reads the results, so structured output is safe.

- `chat()` takes an optional `response_format`. `_structured_output_body(schema, name)`
  builds the `json_schema` envelope with `strict: true` and
  `provider.require_parameters: true`. **That provider flag matters for a `:free`
  model**, which can route to an endpoint that does not support structured outputs and
  answer with prose instead.
- A strict schema must list every property in `required` and set
  `additionalProperties: false`, or the provider rejects the request.
- If the provider rejects `reasoning` or `response_format`, `_create_completion` drops
  that parameter, logs the rejection, and never sends it again. A 429 or an unrelated 400
  propagates. The one-time `[lm] Generation config in use:` line reports
  `structured_output` and `dropped_params`.
- **The JSON schema constrains the shape only, never the wording.** Every rule about what
  may be claimed still lives in the prompt prose.
- `/api/scan`, `/api/scan-text`, `/api/analyze-resume`, and `/api/match-resume` still use
  labeled text. They stream, and the scan path relies on `_VALID_LINE_RE` finding
  `VALID: false` mid-stream to stop early; JSON would have to be buffered whole, giving
  that up.

---

## Environment variables

**Extension** (root `.env`):

| Variable | Meaning |
|---|---|
| `WXT_API_BASE` | Backend URL |

**Backend** (`backend/.env`):

| Variable | Meaning |
|---|---|
| `AI_API_KEY` | OpenRouter API key |
| `AI_API_URL` | AI provider URL |
| `MODEL_NAME` | Model ID |
| `AI_MODEL_SCAN`, `AI_MODEL_VERIFY` | Optional per-endpoint model overrides |
| `AI_TEMPERATURE`, `AI_TOP_P`, `AI_MAX_TOKENS` | Generation controls |
| `AI_MAX_TOKENS_SCAN`, `AI_MAX_TOKENS_VERIFY` | Per-endpoint token overrides |
| `AI_REASONING_ENABLED`, `AI_REASONING_MAX_TOKENS`, `AI_REASONING_EFFORT` | Reasoning-model controls |
| `AI_MAX_CONCURRENT`, `AI_MAX_QUEUE_DEPTH` | Concurrency limits |
| `TAVILY_API_KEY` | Tavily search key; free tier is 1,000 credits/month, no card |
| `TAVILY_MAX_RESULTS` | Results requested per verification (default 4) |
| `TAVILY_SEARCH_DEPTH` | `basic` \| `advanced`, default `basic` |
| `TAVILY_COUNTRY` | Default `philippines`; blank disables the boost |
| `TAVILY_EXCLUDE_DOMAINS` | Domains to drop from the result set; defaults to `wikipedia.org` |
| `TRUSTED_PROXIES` | Proxies permitted to supply `X-Forwarded-For`; blank trusts nobody |
| `CORS_ALLOWED_ORIGINS` | Extension origins permitted; blank installs no CORS middleware |

### Per-endpoint model overrides

Blank by default, falling back to `MODEL_NAME`.

The scan wants prose in a labelled format; `/api/verify` and `/api/analyze-offer` want a
JSON object matching a schema, and only some models have an endpoint OpenRouter can route
that to.

`Settings.resolve_model()` treats blank and an unrecognised endpoint name as unset,
**because an empty model ID is itself a 404.** This is an optimisation, not the fix for a
model that cannot do structured output — see the 404 fallback in
`docs/decisions/parser-resilience.md`.

### Token controls

**`AI_MAX_TOKENS` was ignored by four of the five endpoints** until `resolve_max_tokens()`
replaced the hardcoded literals at the call sites; they were all set to the same value as
the default, which is what hid it.

`AI_MAX_TOKENS_SCAN` / `AI_MAX_TOKENS_VERIFY` override it per endpoint (the offer call
follows verify — both request schema-enforced JSON), and anything that is not a positive
integer reads as unset, **so a typo costs answer length rather than becoming a provider
rejection.**

### `TAVILY_MAX_RESULTS`

Free in credits — cost is per *request* — but every snippet is prompt text for a model
sharing `AI_MAX_TOKENS` with its own reasoning, **so raise it only if `AI_MAX_TOKENS` is
raised with it.**

---

## Panel behaviour

### Verification guardrails

- If no company name is extracted, `verification_context` is absent from the scan
  response.
- The frontend renders `CompanyNameNeeded` instead of the verification section when
  `isValidJob && !companyName`.
- **A missing employer is a missing input, not a finding.** It is deliberately not an
  anomaly: it contradicted the "never flag the absence of something" rule in the same
  prompt list, and it added risk-score weight for an input that was lacked rather than for
  something wrong with the posting. The panel asks the reader for the name instead.
- `CompanyNameNeeded` is styled with a **dashed** border where every result container uses
  a solid one, **so a missing input cannot be misread as a finding.** It states what was
  and was not checked, and says explicitly that it is not a warning about the posting — a
  fact about the output rather than a claim about how common nameless posts are.
- **Scans are always screenshots** (`ScamScanView` calls `/api/scan`; `scanTextStream` is
  exported but has no caller), so this state is never about a missing image. It is about
  the captured region not containing a logo, letterhead or sender name.
- There is **no text input** for the company name. A typed name would flow straight into
  the verification prompt, which produces a verdict naming a real company; guidance only,
  by decision.

### Unverified employer

**The risk gauge shows "Unverified" instead of "0 / Low Risk"** for a nameless posting
with no anomalies.

The posting stage scores 0 when a posting raises no indicators, and "Low Risk" would claim
the posting was cleared when the employer was never checked at all.

`isUnverifiedEmployer()` in `sidepanel/lib/riskDisplay.ts` derives this from
`isJobPosting && !companyName && anomalyCount === 0`; the gauge renders the same empty-ring
shape as an unscored result, **so no figure is displayed that was not measured.**

An anomaly is real evidence about the posting, so it is scored on severity instead, and a
named employer is verified normally.

**The unverified ring is the neutral `outline` grey, not amber** — amber is the
`moderate` level, and borrowing it would read as a mid risk score rather than an unchecked
one.

### Ring animation - deleted

There is none. `.ring-pulse`, the `ring-breathe` keyframes and the per-ring
`--ring-glow-color` all went with the gauge that used them, so the property had
no setter and its two uses fell back to `transparent`. The
`prefers-reduced-motion` clause that disabled the animation went with them too:
no other animation in the stylesheet needs it, as the loading bar and the spinners
are inline Tailwind utilities and each carries its own.
### Evidence promotion

**Restated, not kept.** The old scheme moved a pair of sibling groups so the
evidence rose above the posting analysis. The new stack is a **single fixed
order** with the verdict and the instructions already at the top, so there is
nothing above them to promote.

```
(old) Normal:        Gauge -> Posting Analysis -> Job Summary -> [shots] -> [Anomalies - Offer - Evidence]
(old) High/Critical: Gauge -> [Anomalies - Offer - Evidence] -> Posting Analysis -> Job Summary -> [shots]

(new) Always:    Job meta -> Verdict -> What to do now -> Findings -> Context -> Footer
(new) Elevated:  the same, with Context moved below Findings
```

- **What promotion means now is the neutral context dropping *below* the
  findings.** A reader who has just been told not to send money does not need
  the coverage count in their first viewport.
- **`shouldElevateEvidence()` waits for the level to settle.** The scan returns a
  level from the posting alone and verification can move it, so a posting can
  read "high" and settle at "moderate". Promoting on the intermediate value
  would move the evidence out from under the reader and put it back a moment
  later. `verificationLoading` and `offerAnalysisLoading` both gate it. **A failed
  verification still promotes**, because the posting stage's findings are real
  regardless of whether the employer lookup ran.
- **Both groups stay mounted; `order` on the flex parent decides which leads.**
  Unmounting to reorder would give FLIP nothing to animate and would reset a
  collapsed disclosure on every level change.
  **`display: contents` is the trap here:** it looks like the tidier way to drop a
  wrapper, but it generates no box and `order` has no effect on a box that does
  not exist.
- **`order` reorders every sibling, not just the pair.** An element with no order
  value sorts at `0`, so the groups on `order-1`/`order-2` pushed the
  `sticky bottom-0` action bar above the results. It carries `order-3` and the
  capture preview `order-4`. **`order-last` is not the fix** - a later sibling
  swaps with it.
- **`useFlipReorder` animates the move, both directions.** A fade cannot express
  a reorder: the content dissolves and reappears elsewhere, which reads as a
  glitch.
- **Colour is chrome, not prose.** `riskAccent()` tints the primary capture
  button, and only while a high or critical level is settled. **Body prose has no
  entry on purpose**: long blocks of red or amber on a light surface are the
  hardest thing on the panel to read, and this is where someone reads a verdict
  carefully enough to act on it. The accent is temporary by construction - it
  rides on the displayed result, which `resetAll()` already clears when a new
  element is picked.
- **The score is gone.** The retired 0-100 index and the gauge ring that drew it
  are deleted, along with the ring's `ring-breathe` keyframes and the
  `--ring-glow-color` property they read. What replaced them is a short authored
  instruction in `verdictCopy.ts`, looked up by level, so it cannot drift between
  runs and keeps the libel guardrail in code. See
  `docs/decisions/report-panel-redesign.md`.
### Filter categories (`ResumeMatchView`)

| Filter | Icon | Condition |
|---|---|---|
| All | `work` | Always shown |
| Verified | `verified` (green) | `riskLevel === 'low'` AND `isJobPosting` |
| Unverified | `info` (neutral) | `riskLevel === null` — excluded from matching |
| Moderate | `warning` (amber) | `riskLevel === 'moderate'` |
| High/Critical | `shield_person` (red) | `riskLevel === 'high'` OR `riskLevel === 'critical'` |

**High/Critical jobs are excluded from resume matching.**

**Every level but `low` is excluded, and each per-job row has to say so.** The exclusion
itself is `verifiedJobs` — `isVerifiedJob` is `low` only, and that collection is what gets
matched.

The bug was in the *label*: the per-row status branch tested `isSuspiciousJob` (which means
**moderate**) and then `riskLevel === null`, so `high` and `critical` fell through to the
final `else` and were told *"No high-severity indicators found. Included in resume
matching."* **The one branch that must never be reassuring was the one the most dangerous
job took.**

`isSuspiciousJob`/`suspiciousJobs` are now `isModerateJob`/`moderateJobs`, because the old
name reads like it covers the risky levels and invites the same omission. The
`JobFilterCategory` data key is still `'suspicious'` — it is a stored union value, not a
predicate.

`ResumeMatchView.riskMessage.test.tsx` asserts the message for all four levels plus
unscored, so the `else` cannot swallow a level again.

---

## Offline mode

- `useBackendHealth()` is the single source of truth for reachability and is mounted once
  in `App.tsx`; views receive `isOnline` as a prop (default `true`).
- Poll cadence is 4s (~15 requests/min) to stay under the backend's `30/minute` limit on
  `GET /health`; probes are skipped while `document.hidden` and never overlap.
- `isOnline` starts `true` and flips false **only after 2 consecutive failed probes** —
  never surface a false offline banner from one slow response.
- The first successful probe restores online state, so the banner clears itself on
  recovery; the Retry button only forces an immediate check.
- Offline disables network actions only (Scan, Match, resume upload). Element picking,
  cropping, and scan history stay usable because they are local-only.
- In-flight scans are **not** aborted when the backend drops; they keep their existing
  240s/300s timeouts.

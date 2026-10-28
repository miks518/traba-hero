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
| `AssessmentBlock.tsx` | 3 | Tone container + **authored** headline. Replaces `RiskGauge` |
| `ActionBlock.tsx` | 4 | Two authored instruction lines. The share chips and report control are absent |
| `AnomalyCards.tsx` | 5 | One card per finding: code pill, quote well, and the evidence assessment strip. **Checking / Stale / Contradicted / Unconfirmed** — see below |
| `WhatWeChecked.tsx` | 7 | **Asserts checks ran.** Heading derived from state — see below. **Labels only** |
| `FullDetails.tsx` | 8 | **Shows what retrieval returned,** including each check's `explanation`. Split from §7 for the reason below |
| `ReportFooter.tsx` | 10 | Disclaimer, ruleset version. No scan id — no field carries one |
| `assessmentCopy.ts` | 3, 4, 8 | Every authored string. **Nothing here may be model-written** |
| `checkPresentation.ts` | 7, 8 | The three groups and the per-status icon. **Shared, because both slots render the same checks** |

`ScamScanView.tsx` is now a composition of this panel plus the capture
affordances. The scan lifecycle lives in `hooks/useScanSession.ts`; the wire
mapping in `lib/mapApiResponse.ts`.

`ReportSkeleton.tsx` is the initial-scan placeholder, not a report slot: it
mirrors the order and proportions above with grey `animate-pulse` blocks and
yields to the real panel as soon as the scan lands. It never uses a assessment
colour and never draws the unbuilt controls. Verification uses the per-card
confirming box, not a second skeleton.

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

#### Why §7 shows labels and §8 shows the sentences

**`VerificationItem.explanation` is rendered in §8 and nowhere else.** Every check
carries the model's account of what decided its status. Until 2026-10-18 that field
was parsed, bound to a retrieved URL, weighed by `risk_calculator`, serialised onto
the wire and typed on the client — and never displayed. §7 drew the label alone, so a
`red` Channel Match rendered as the two words "Channel Match" in a red bucket with no
sentence on screen explaining what contradicted what.

The split is §7's, not §8's: §7 asserts that checks ran, and a paragraph of
model-written prose under a heading that asserts coverage is a different claim at a
different weight. §8 shows what retrieval returned, which is where a sentence
belongs.

**§8 repeats the three groups so the two slots correlate.** A label above has to land
on its sentence below. Both components therefore call `groupBy` and
`statusPresentation` from `checkPresentation.ts` rather than restating them — a second
copy would let a status read green above and be filed under "Could not verify" below,
which is worse than showing no sentence at all.

**§8 runs `shouldShowCheck` too, and that is load-bearing, not tidiness.** Before this,
the only surface for per-check model prose was one label, so the guardrail had a
bounded exposure. Now that the sentences render, §8 is the surface where a model's
words about a named employer actually appear, and the filter that keeps the *scam* /
*fraud* restatement off the panel has to cover it. It is imported, not reimplemented:
two policies is one too many. Items with a blank explanation are dropped as well — a
label over an empty paragraph is a placeholder.

**§8 no longer hides itself when there is nothing but a sentence.** Its early return
was keyed on `evidence` and `report` only. A `red` whose citation
`_bind_to_retrieved` stripped arrives with no URL and no evidence entry, so that
condition would have withdrawn the disclosure holding the only explanation of the
contradiction. Explanations are now a third reason to render.

**§8 wears the banner's tone.** `ReportPanel` resolves `(verifying ? VERIFYING :
assessmentFor(level)).tone` once and passes it down, so the panel reads as one object
rather than a banner with a foreign card under it. `tactile-disclosure` shares the
assessment surface rules with `tactile-assessment` and adds the press state the banner must
not have — a banner is a measurement and does not move; a disclosure is operable and
does. See `docs/decisions/design-system.md`.

**Everything inside §8 is a container, and each check group is tinted by its status.**
The checks, the report prose and the sources each sit in a card, inside one flat parent
(`BODY_CLASS`). Within the checks, each of the three groups is its own `tactile-card`
filled with that status's chip tint — `status-card-verified` / `-critical` / `-caution` —
so the three read apart by shape and colour before a word is read. Bare text separated
only by `gap-4` made the blocks read as one run, so a reader could not tell a *finding*
from a *summary* from a *source*, and could not see a contradiction as a colour at all.

Four rules, each with a failure it prevents:

- **The tints reuse the chip `--bg` tokens** rather than introducing a second palette.
  Those values already exist as pale tints chosen to sit under saturated text, so a card
  and a chip can share one and cannot drift apart.
- **The chip inside a tinted card drops its own fill** (`chip-cutout`) and keeps its
  saturated text. A chip-coloured chip on a chip-coloured card is invisible, and the
  symptom — a tint that "doesn't work" — points at the wrong thing.
- **A container that holds containers is not itself a card.** `BODY_CLASS` and
  `WRAPPER_CLASS` carry a fill and a border and no `tactile-card`; the shadows belong to
  the leaves inside them. Stacking extrusions spends the elevation cue on nothing, and
  the shadow is only worth anything while it means something.
- **One neutral step for the non-status blocks.** The five `surface-container` steps are
  a depth scale, not a palette; stepping between them would encode a difference that
  does not exist between a summary and a source list.

The sources block also gained a **Sources** heading. The list previously ran straight
into the block above it with nothing marking where it began.

#### Promotion is restated, not kept

The old scheme moved a **pair of sibling groups** — evidence up, prose down — so
the evidence rose above the posting analysis. The new stack is a **single fixed
order** with the assessment and instructions already at the top, so there is nothing
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
| "Do not share" chips | Keyed to the code families, and the chips have to name what *this* posting asks for. Generic ones would be identical for every posting |
| Report control | Nothing to report the post *to*, for the same reason as the provenance line |
| Coverage count | Its denominator must be a constant the backend owns, or it drifts with whatever the panel renders |
| "Was this accurate?" | No database, no destination for the answer. A dead control reads as a working feature |
| Highlighted span inside a quotation | The wire carries the quotation but not which phrase inside it decided the finding. Highlighting the whole quote would be decoration pretending to be an analysis |

#### Three slots that came back

These were absent until the backend grew the fields. Each returns with a
degradation that matters more than its happy path.

| Slot | Field | Degradation |
|---|---|---|
| One-line assessment reason | `verificationResult.assessmentReason` | Absent leaves a banner carrying only its authored headline, which is complete on its own. Suppressed entirely while the lookup is running, so the banner's wording and what sits under it cannot go out of step |
| Anomaly `code` pill | `anomalies[].code` | Absent is **not** `OTHER`. `OTHER` is the escape valve and is shown, because its frequency is the drift signal the taxonomy exists to produce; absent means a scan predating the field |
| Quote block per anomaly | `anomalies[].quote` | Absent degrades the card to its explanation. An empty quotation block would read as "the posting said nothing here", which is a claim about the posting rather than about our screening |

The code is model-emitted from the closed set in
`backend/app/services/anomaly_codes.py` — same shape as `EXPECTED_CATEGORIES`
being derived from `VERIFY_CLAIM_CATEGORIES`, so there is one home for the
vocabulary. A wrong model-picked code is visible as an `OTHER` spike; a wrong
backend mapping would be invisible.

**The quote screening is weaker than the citation binding on the verification
side, deliberately.** The extension scans an *image*, so a span cannot be located
in the posting and only its wording can be checked (`quote_is_clean`). On the text
path it is located as well. Screening a quote leaves the finding intact and the
card renders its explanation, which is the honest degradation; a fabricated quote
is never rendered.

#### The anomaly evidence assessment

`Anomaly.assessment` is optional, and absence is a real state rather than a
`stale`. One of four card states is derived in the client:

- **`Checking`** — the verify request is in flight. Neutral chip, no severity
  colour, and a confirming box with `role="status"` and `aria-busy="true"` under
  the quote. Driven by `result.verificationLoading`, never the panel's sticky
  `verifying` flag.
- **`Stale`** — grey chip and `status-card-stale` strip. A source about this
  employer accounted for the finding and it no longer stands.
- **Contradicted** — red `status-card-critical` strip; the chip keeps the scan's
  severity. A source states something different from the posting.
- **`Unconfirmed`** — amber chip and `status-card-caution` strip. No employer,
  a failed lookup, a missing assessment, or results that did not settle it.

`stale` and `red` are shown only with a bound retrieved URL. The parser demotes
an unbacked one to `yellow`, and the card repeats the rule as a last guard
against a saved or hand-edited response. `AnomalyCards` never drops a finding:
the omitted cards from the 20-finding request cap get their own amber note, and
`anomalyAssessmentRun` separates "the check ran and missed this one" from "this
reading predates the check". The heading stays **Anomalies detected** and counts
the cards shown.

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
| `backend/app/services/scanner/channel_match.py` | Channel Match facts, free-provider detection, lookalike detection, and the code-owned severity |
| `backend/app/services/scanner/assessment.py` | The code-owned final level: posting findings + refutation score, with the strong-channel floor |
| `backend/app/services/scanner/offer_prompt.py`, `offer_parser.py`, `offer_flow.py` | Post-only analysis for offers naming no employer; its own endpoint and parser so it cannot break the scan or verify paths |
| `backend/app/services/scanner/risk_calculator.py` | Weights and two-stage arithmetic behind `assessment.py` — see `docs/scoring.md` |
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

A request that went out with thinking disabled and came back with nothing is retried once
with thinking enabled, in both `chat` and `chat_stream_pieces`; a retry that produces
content memorizes the model in `_thinking_required_models` so later requests skip the
doomed attempt. See `docs/decisions/reasoning-models.md`.

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
on its own terms and returns a assessment. **Both paths produce a level, but they are not
the same kind of level, and the difference is deliberate.** The verify path's level is
computed in `assessment.py` from the posting's findings and the retrieved evidence. The
offer path's level is the model's own reading, because that path has no employer to look
up, no anomalies to price, and no retrieval to contradict anything — the prompt says so
in as many words. It is a separate design, not an oversight, and it carries the same
risk the verify path used to carry: a model that prices a category instead of reading
the whole offer. `docs/decisions/scoring-model.md` records why the verify path moved
into code; the offer path has not been revisited.

On the verify path, a source that accounts for a finding removes that finding from the
posting score, a source that contradicts one adds to the refutation score, and an
unresolved finding never lowers it. The final number is computed in `assessment.py`; the
verify model does not return `risk_level` or `risk_score`.

The verify prompt carries the scan's findings as a numbered block, plus a 4,000-character
excerpt of `job_summary` as context. It returns `anomaly_assessments`, one per finding.
`stale` and `red` require a retrieved URL; an unbacked assessment is demoted to `yellow`.
The five status-bearing category checks stay evidence-only: the findings are labelled as
the posting's claims and may not make a category green or red. Channel Match is not one of
those status-bearing checks; the model reports its facts in a `channel_match` object and
`channel_match.py` assigns the status. The labeled-text fallback returns no assessments,
so every card is amber, and its missing `channel_match` facts leave the category yellow.

`/api/verify` logs the raw AI response and parsed items at INFO/WARNING level for
debugging, and warns when a finding came back without an assessment.

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

**What `_build_verify_prompt` sends** is five blocks, in order: the employer name, the
gating instruction, the posting's own stated claims (`attributes`), a bounded
`job_summary` excerpt, and the findings a first reading of the posting already produced
(`anomalies`) — then the search results. The findings carry the scan's taxonomy code and
quote, and they are labelled as untrusted posting claims rather than facts
about the employer; the model returns one `anomaly_assessments` entry per numbered
finding. The findings never decide one of the five category statuses - the categories are
tested against the results alone. What the model may and may not say about a finding is
in `docs/decisions/verification-design.md`, and what the code does with the answer is in
`docs/decisions/report-panel-redesign.md`.

The scan prompt's `CONTACT_METHOD` has to hold *every* channel the posting directs
applicants to, not one — one typed line each (`email | address@host`), which
`lm_client.py` accumulates rather than overwriting. It is the slot that opens
`Channel Match`, and a channel the posting never wrote down is a channel nothing can
test. `CLAIMED_TYPE` is the same observation's other half: whether the poster presents
itself as a government office is a different fact from the name it prints. Both are in
`docs/decisions/scan-channel-enumeration.md`, which also holds the separator contract
with the search planner. The rules that compare those channels against the employer's
own are in `docs/decisions/channel-match-severity.md`.

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
| `TAVILY_MAX_RESULTS` | Results requested per query (default 3) |
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
raised with it.** Three per query across up to six queries is the shipped shape; the
merged list is capped at `MERGED_RESULTS_CAP` (12) regardless.

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
  the verification prompt, which produces a assessment naming a real company; guidance only,
  by decision.
- **The anomaly cards are present before verification and never hidden.** While the
  lookup runs they show `Checking` with no severity; a no-employer or failed lookup shows
  amber `Unconfirmed` and no spinner. `stale` and `red` always carry a bound source.
- **The initial-scan loader is `ReportSkeleton`**, which mirrors the report with grey
  pulsing blocks. It is not used for verification, and it does not draw the unbuilt
  controls.

### Unverified employer

**The risk gauge shows "Unverified" instead of "0 / Low Risk"** for a nameless posting
with no anomalies.

The posting stage scores 0 when a posting raises no indicators, and "Low Risk" would claim
the posting was cleared when the employer was never checked at all.

`isUnverifiedEmployer()` in `sidepanel/lib/riskDisplay.ts` derives this from
`isJobPosting && !companyName && anomalyCount === 0`; the gauge renders the same empty-ring
shape as an unscored result, **so no figure is displayed that was not measured.**

An anomaly is real evidence about the posting, and a named employer is verified normally.
The scan carries no severity for anything — see `docs/decisions/scan-severity-removal.md`.

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
order** with the assessment and the instructions already at the top, so there is
nothing above them to promote.

```
(old) Normal:        Gauge -> Posting Analysis -> Job Summary -> [shots] -> [Anomalies - Offer - Evidence]
(old) High/Critical: Gauge -> [Anomalies - Offer - Evidence] -> Posting Analysis -> Job Summary -> [shots]

(new) Always:    Job meta -> Assessment -> What to do now -> Findings -> Context -> Footer
(new) Elevated:  the same, with Context moved below Findings
```

- **What promotion means now is the neutral context dropping *below* the
  findings.** A reader who has just been told not to send money does not need
  the coverage count in their first viewport.
- **`shouldElevateEvidence()` waits for the level to settle.** The scan carries no
  level; the verify response returns the code-owned one from the posting's
  findings plus the evidence, so a posting can read "high" on its findings and
  settle at "moderate" after a stale finding is accounted for. Promoting on the
  intermediate value would move the evidence out from under the reader and put it
  back a moment later. `verificationLoading` and `offerAnalysisLoading` both gate
  it. **A failed verification still promotes**, because the posting stage's
  findings are real regardless of whether the employer lookup ran.
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
  hardest thing on the panel to read, and this is where someone reads a assessment
  carefully enough to act on it. The accent is temporary by construction - it
  rides on the displayed result, which `resetAll()` already clears when a new
  element is picked.
- **The gauge is gone.** The 0-100 gauge ring that drew the index is deleted,
  along with the ring's `ring-breathe` keyframes and the `--ring-glow-color`
  property they read. The number still exists in the backend for the level bands,
  resume matching and `score_breakdown`, but the panel renders a short authored
  instruction from `assessmentCopy.ts`, looked up by level, so it cannot drift between
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

# Unfinished Work

Running list of what was left undone, why, and how to verify it. Newest task first.

**Start here in a new session.** The developer has manually confirmed the scan
pipeline works end to end with the tightened prompts, the two-stage score, and
`AI_MAX_TOKENS=2048` + `AI_REASONING_EFFORT=low`. What is still open is the
formal output-quality pass below, the outstanding tests, and the deferred
roadmap tasks.

**Do not call the AI provider.** The key is shared and its 24-hour limit blocks
the developer's own testing. Every check in this document is written to run
offline; if something appears to need a live call, it belongs in the checklist
for the developer to run instead.

---

## Task 2.3 — Defamation-Safe AI Output

Code is integrated, the offline gates pass, and the developer has confirmed the
live path works. What remains is the formal output-quality pass below and the
outstanding tests.

### A verdict always exists now

Gating the verdict on the employer check was the wrong model: the product
analyses **offers**, and an employer name is only a secondary input. Scanning is
now also wider than formatted job adverts — chat messages, forwarded paragraphs,
and "earn by doing X" pitches are in scope, with `VALID: false` reserved for
content that offers no work or income at all.

- **Two-stage score.** `_posting_risk_from_flags` counts the indicators the scan
  reported (high 40, mid 12, low 4, capped at 100) and always returns a number.
  `_calculate_risk_score_from_verify` adds the employer check, and
  `_combine_scores` blends them 60/40. A stage that did not run is absent, not
  zero: an unlookable posting keeps its own score instead of being penalised.
- **`POST /api/analyze-offer`** (SSE, 5/min) is the no-employer path. One AI call,
  no search. It returns `KIND` / `VERDICT` / `WHAT IT ASKS` / `WHAT IT OFFERS` /
  `WHAT TO CHECK`, parsed by a new `offer_parser.py`. Rendered by
  `OfferAnalysisCard`.
- It runs **only** when no employer was found. When one was found the existing
  scan + verify data is combined instead, so the common path costs no extra call.
- Unparseable analysis degrades to a generic failsafe, never an error. The score
  never depends on this pass, so a failure costs the explanation, not the verdict.
- `InvalidContentError` is now "Nothing To Assess" and names the content it
  accepts, so a rejected chat message reads as a scope note rather than a bug.

Verified offline: 20 scoring cases and 10 extraction cases, all correct. Both
scratch scripts were deleted; the cases should become permanent tests.

### Earlier fixes in this task

Applied after hands-on testing surfaced them. All offline, all verified by the
existing suites plus a throwaway extraction script that was removed afterwards.

- **`risk_calculator.py` no longer scores absence.** When every verification item
  came back `yellow` — meaning the search confirmed nothing either way — the old
  weighting summed to 49 and reported "Moderate Risk". That is a number derived
  from what we failed to find, presented as a measurement. It now returns
  `(None, None)` so the panel shows "Not scored". Same reason an empty item list
  scores nothing.
- **`extract_company_name` over-captured.** Its character class also matches
  sentence punctuation, so "Acme Corp. We are hiring for a cook" produced the
  company name **"Acme Corp. We are hiring"**. Verification then searched for
  garbage, found nothing, and produced the all-yellow score above — the two bugs
  fed each other. Candidates are now cut at the first clause boundary, stripped
  of parentheticals and of the trailing verb in "X is hiring".
- **All candidates are evaluated, not just the first.** "We are looking for
  staff. Jollibee is hiring servers" matched from "We", and that rejected capture
  hid the real employer behind it. Matches are zero-width so overlapping
  candidates are no longer skipped. Verified against 10 sample strings, including
  three that must still return nothing.
- **`"company"` added to `INVALID_COMPANY_NAMES`.** A bare "Company" was passing
  validation once overlapping candidates were evaluated.
- **Logo instruction added to the scan prompt.** When a posting names no employer
  in its text, the model is now told to check for a logo, wordmark, letterhead, or
  sender name in the image before concluding there is none.
- **Post-only flow in the panel.** With no employer named, the gauge explains that
  there was nothing to look up, the posting analysis sits under it, and the
  verification card tells the user to pick the part of the page carrying the
  employer's name if there is one. No score, no accusation.

### Still not done

| Item | Where | Why |
|---|---|---|
| Prompt-contract tests | new `backend/tests/test_prompt_contracts.py` | Asserts all four prompts contain the observational rules and none of the banned patterns. Cheap and fully offline. |
| `risk_calculator` unit tests | `backend/tests/` | The new all-yellow → `(None, None)` rule deserves a test of its own. Pure function. |
| `extract_company_name` regression tests | `backend/tests/test_search.py` | The 10 sample strings I checked were ad hoc and are now lost. They should be permanent. |
| Scan-mapping tests | extract `mapApiResponse` out of `ScamScanView.tsx` | Module-private today, so "no synthesised score" cannot be asserted. |
| History-migration test | `migrateScannedJobs` in `lib/scanHistory.ts` | Extracted and exported for exactly this. |
| UI copy review | `VerificationSection`, `VerificationCard`, `ResumeMatchView` | Reworded from code, not from reading the rendered panel. |

### Live output-quality pass — the developer runs this

The developer has confirmed the pipeline works: scans complete, the employer
name is extracted from the `COMPANY NAME` field, verification runs, and a score
appears. What has **not** been done is the systematic check below, which
validates that the tightened prompts produce the *right* output rather than
merely some output. It needs live provider calls, so it is the developer's to
run — it is roughly ten requests.

Note the prompt was hand-shortened by the developer mid-task. The "do not flag
on their own" list was reduced to a single Gmail line, so missing office
addresses, generic job titles, and "no experience needed" are no longer
explicitly excluded. Watch for false positives there.

| # | Posting | Expected red flags | Expected verification | Expected gauge |
|---|---|---|---|---|
| 1 | Obvious fee scam ("pay a 500 peso processing fee to start") | Exactly one `high`: names the fee request. No claim about the employer. | Reputation `red` only if a result actually describes a report; `yellow` otherwise | Score from posting + employer |
| 2 | Legitimate posting using a Gmail address | **Zero** flags. Gmail is explicitly not a flag. | Green where results support it | Score from posting + employer |
| 3 | Real posting that names no employer | Exactly one `low`: "Company name not stated" | `/api/analyze-offer` runs instead; verdict from the offer itself | Score from the posting alone |
| 3b | Same posting, but the name is only in the logo | Employer name pulled from the logo, no company-name flag | Verification runs normally | Score from posting + employer |
| 4 | A restaurant menu or an article | `VALID: false` and nothing else | n/a | n/a |
| 5 | Deliberately ambiguous posting with a vague employer | At most a `mid`, or zero | Yellow-heavy | Score from posting + employer |
| 6 | A chat message: "Earn 5k/day, pay 500 fee to register" | `VALID: true` plus the fee flag | `/api/analyze-offer`; verdict must name the requested payment | Score from the posting alone |
| 7 | A forwarded recruitment paragraph naming no employer | `VALID: true` | `/api/analyze-offer` | Score from the posting alone |

Also confirm:

- Row 6 must **not** return `VALID: false`. A chat message offering work is in
  scope; that was the original point of widening the gate.
- `KIND` on row 6 should read something like "Chat message" or "Earnings scheme".
- A posting with a real employer and a working search does **not** return an
  all-yellow result. If it does, the extracted name is still dirty — check the
  server log for `company_name='…'`.
- `/api/analyze-offer` output parses. If the card shows the failsafe text, the
  parser missed the labels.
- No red-flag reasoning contains *likely, appears, suggests, probably, seemingly, may be, might be, could indicate, often, typically, we think*.
- No red-flag reasoning contains *always, never, definitely, guaranteed, 100%*.
- Nothing anywhere states or implies that a named company is a scam, fraud, or criminal.
- No verification `DETAIL` claims a website or registry was checked when it was not in the provided results.
- `REPORT` and `RECOMMENDATION` both survive parsing. `/api/verify` is capped at
  `max_tokens=2048` and `/api/analyze-offer` at 1536; if either comes back empty,
  the model truncated.

### Known risks

- **Recall may have dropped.** Fewer hedged flags is the intent, but "less
  ambiguity" and "fewer findings" trade against each other. The table above is
  the only way to find out. If obvious scams in rows 1 and 6 are now missed, the
  severity table in `SYSTEM_PROMPT.md` is too narrow.
- **A new endpoint is barely exercised.** `/api/analyze-offer` was written
  against a stubbed search and a hand-written model response. Its parser is
  deliberately small and has a failsafe, but the shape of real model output is
  an assumption. Rows 3, 6, and 7 above are the test.
- **The 60/40 blend is a judgement call**, not a measurement. It is documented in
  `AGENTS.md` and the breakdown travels with the response, so it can be retuned
  once real data exists.
- **Widening `VALID` means more content is analysed**, including borderline text
  that merely mentions earning. Rows 4 and 6 bracket that; watch for content in
  between being scored when it should not be.
- **Banned-word rules are weaker in Tagalog.** `_language_instruction` asks for
  Tagalog output, and the rules are written as constraints rather than a word
  list for that reason. English word lists will not catch a Tagalog hedge.
- **`_parse_custom` is fragile about section order.** `END FLAGS` resets the
  parser's `matched_any` flag, so it only works because the prompt puts
  `JOB SUMMARY` after it. The prompt now states the order explicitly, but a
  model that reorders sections will produce an unreadable-response error. Worth
  a parser fix, left alone here to avoid changing the wire contract.
- **Old history is unrecoverable.** Migrated jobs are cleared to "Not scored"
  and cannot be re-scored without a new scan. There is no backfill path.

---

## Task 2.1 — Data Privacy Consent Modal

Not started. Resume upload currently goes straight to `/api/analyze-resume`
with a confirm dialog but no NPC consent gate. See `CRITICAL.md`.

## Task 2.2 — Backend In-Memory Processing & Zero-Retention

Not started. Relevant to the work above: `scan_flow.py` and `verification_flow.py`
both log AI output at INFO, including job summaries and company names. That is
posting data, not applicant PII, but it is not zero-retention either.

## Task 3.2 — Resilient SEC Philippines Verification

Not started. Note that `backend/app/services/sec_api.py` referenced in
`CRITICAL.md` and `AGENTS.md` does not exist; no SEC call path is present in the
code. The task as written has no code to harden.

## Task 4.1 — Misclassification Reporting

Not started.

---

## Housekeeping found along the way

### Verification output is now JSON

The labeled-text format is gone from the primary path. `/api/verify` and
`/api/analyze-offer` now request `response_format` with a JSON Schema, because
the original reason for the custom format — the native model web search breaking
on curly braces — no longer applies: searches run in the backend and the model
only reads the results.

Key implementation points:

- `provider.require_parameters: true` is set on every structured request. Without
  it a `:free` model can route to an endpoint that does not support structured
  outputs and return prose instead of JSON.
- Strict schemas list every property in `required` and set
  `additionalProperties: false`, including nested array items.
- The guardrail prose is unchanged. A schema constrains shape, not wording, so
  every rule about what may be claimed still has to be said in the prompt.
- **Both text parsers are kept as fallbacks**, not deleted. `_read_verify_output`
  prefers JSON and falls back to the block-wise labeled-text parser if the
  response is not JSON; the offer flow does the same. So a provider that ignores
  structured outputs still produces a result rather than an error.
- `_create_completion` now drops `reasoning` and `structured` independently when
  a provider rejects either, and records both in the one-time
  `[lm] Generation config in use:` line as `structured_output` and
  `dropped_params`.

**Not yet exercised against the live model.** If `:free` endpoints for this model
do not support structured outputs, the rejection fallback will fire and the flow
will quietly use the text parser — which is why the config line matters. Grep for
it after the first run.

**Still not converted:** `/api/scan`, `/api/scan-text`, `/api/analyze-resume`, and
`/api/match-resume` still use labeled text. They stream, and the scan path relies
on `_VALID_LINE_RE` finding `VALID: false` mid-stream to stop early and save
tokens. Switching them to JSON would require buffering the whole response,
giving that up. Worth doing only if the text-parser brittleness bites there too.

### Resolved: the web search was rebuilt on Tavily

The DuckDuckGo module produced results for the wrong query. A search for
`Cleanfuel Philippines company` returned YouTube TV Help pages; `Vikings`
returned Knowunity; `Caishen` returned Wikipedia articles about the Chinese god
of wealth and Philippine senate impeachment news. Every response was
**successful** � HTTP 200, results present, no throttling flag � so nothing in
the code or the logs indicated a fault. Two intermediate diagnoses (a "/" in a
joined company name, and a throttling window) were both wrong.

Four defects compounded:

1. **Category headings asserted facts retrieval never established.** A result
   found by a `"<company> scam fraud complaint"` query was printed under a
   `[SCAM REPORTS]` heading. A regulator's complaint form appeared there as if
   it were a scam report. This was the most serious of the four.
2. **Snippets were silently dropped** by reading the library's `body` key where
   the normalised result used `snippet` (twice, in two different formatters). The
   model was shown titles only and correctly reported that no result mentioned SEC
   registration.
3. **Empty results were indistinguishable from failures** � `[]` for both a
   rate-limited query and a company with no footprint, so a retrieval failure
   read as a clean company.
4. **Engine selection was a coin flip.** The `ddgs` library picks an engine at
   random when none is named; most engines returned nothing from this machine, so
   an unpinned call frequently hit an engine serving a stale cached page.

`app/services/search.py` replaces the 620-line module. `SearchOutcome.ok` and
`.results` are independent fields, so a caller cannot read "retrieval failed" as
"nothing found". One query (`"{company} Philippines"`) replaces four, with no
category headings � the model sorts results into the three categories itself. The
scan no longer searches at all, so `/api/verify` is the only consumer of online
evidence. `ai_tools.py` and `chat_with_tools` were dead tool-calling code and are
gone.

**Not yet validated end to end.** Tavily needs a real run to confirm the SEC card
turns green with a registration number in its detail, and the Search debug tab
should be used to check the raw provider response is on-topic.

### Under investigation: only one verification card rendered

**Status: no longer reproducing; the cause was never confirmed.** This section
is kept so the log lines it names are the ones to check if it returns.

Reported as: the panel showed only **Company Existence** even though the log
showed values for the other categories. The frontend was ruled out — it maps
`result.items` with no filter — and the parser passed every well-formed shape
tested, so the cause was a deviation in the model's actual output. The parser
was made block-wise and a partial parse now logs
`[verify] Parsed N of 3 expected categories; missing: ...`, so if it returns,
that line plus `[verify] Raw AI response` will identify it. The search
rebuild may also have removed the trigger: retrieval no longer stamps results
with category headings.

### Remaining levers on reasoning volume


The model is a native reasoning model and the developer is rate-limited on other
free multimodal options, so switching models is not available. Scans complete at
`AI_MAX_TOKENS=2048` + `AI_REASONING_EFFORT=low`, so this is optimisation, not a
blocker. The remaining levers are all input size, and none of them can be
verified without a live call:

- **Reasoning can now be switched off outright.** `AI_REASONING_ENABLED=false`
  sends `{"reasoning": {"enabled": false}}`, which is the documented OpenRouter
  way to turn thinking off rather than fund it. It overrides the other two
  controls, because a provider returns 400 for a disabled reasoning combined
  with a high effort level. Not yet tried against the live model — the
  `AI_REASONING_ENABLED` tri-state (`None` unset, `True` force on, `False` off)
  and the override are verified offline. If it is rejected, the existing
  fallback logs `[lm] Provider rejected the reasoning parameter` and the app
  continues on `effort: low`, which is the setting already confirmed working.
  Note `exclude: true` is not the same thing — it only hides reasoning from the
  response while still paying for it.
- **Image dimensions — done.** `MAX_DIMENSION` lowered 1920px → 1280px, so one
  image is 44% of the pixels and a 4-image scan goes from ~8.3M to ~3.7M pixels.
  If dense small print starts scanning badly, raise it and expect reasoning cost
  to rise with it.
- **Screenshot count — not done.** `MAX_SCREENSHOTS` is 4, so a full scan can
  still send four images. Halving it to 2 is the largest remaining lever on
  deliberation, at the cost of requiring two scans for a long posting. The
  developer chose to leave it.
- **Temperature — not done.** `AI_TEMPERATURE` is 0.2. For structured extraction
  0 is the conventional choice and is free, but it will not shorten reasoning
  much and was not selected.
- **Unverified assumption.** Lowering pixel count reduces *vision* cost
  measurably; that it also reduces *reasoning length* is unproven here. Treat any
  improvement as unconfirmed until the developer measures it.

### Resolved: the reasoning model exhausted the token budget

This cost most of a session. **Resolved — the developer confirmed scans complete
at `AI_MAX_TOKENS=2048` with `AI_REASONING_EFFORT=low` and
`AI_REASONING_MAX_TOKENS=0`.** Recorded so it is not re-diagnosed.

- **Symptom.** `[lm] Stream produced no content ... finish_reason=length` with a
  reasoning-only character count. The model spent the whole budget thinking and
  was cut off before answering, so the parser saw an empty string.
- **The prompt was only half the problem.** `OUTPUT_RULES` and `SCAN_FIELD_RULES`
  (3,541 chars) were sent twice — once in the system prompt, once in the user
  message via `SCAN_OUTPUT_FORMAT` — making the request 9,236 chars of which
  ~3.9k was duplication. `SCAN_OUTPUT_FORMAT` is now the bare skeleton, 5,367
  chars total, no information lost. Shortening `SYSTEM_PROMPT.md` by hand did
  **not** fix it, because the failure was budget exhaustion, not input size.
- **What actually fixed it** was `AI_REASONING_EFFORT=low`, which reduces
  deliberation at the source. `AI_REASONING_MAX_TOKENS` only truncates it and a
  truncated reasoning phase can make a provider re-attempt, so set one or the
  other, not both.
- **Lowering `AI_MAX_TOKENS` guarantees the failure.** 2048 cannot hold a long
  think plus an answer. Keep the cap above the reasoning budget.
- **Two instrumentation bugs made the diagnosis harder than it needed to be.**
  The reasoning counter summed `reasoning` and `reasoning_content` on every
  chunk, so a provider mirroring the same text into both fields counted every
  character twice — a failure reported 16949 chars where the model had emitted
  8681. The counter now counts an identical pair once and reports per-field
  totals. Separately, an early probe of mine failed for the wrong reason and a
  second gap let a `ValueError` reach production; the lesson recorded in
  `AGENTS.md` is to exercise the consumer of a function, not just the function.
- **The diagnostics are the durable win.** `EmptyModelResponse` names which of
  the three causes occurred, and `[lm] Generation config in use:` logs the config
  actually in force once per process. Grep for that line when anything fails.

  `AI_MAX_TOKENS=4096` in `backend/.env`; the developer has since confirmed
  2048 works with `AI_REASONING_EFFORT=low`.
- **Deliberation can now be capped separately from the answer.**  `AI_REASONING_MAX_TOKENS` and `AI_REASONING_EFFORT` map to OpenRouter's
  normalized `reasoning` parameter, sent via `extra_body` on both the streaming
  and non-streaming paths. Both default to off, so nothing is sent until they
  are set in `backend/.env`. `AI_REASONING_EFFORT=low` is the setting the
  developer validated live.
- **A provider that rejects the parameter degrades instead of breaking.** A 400
  that names the parameter triggers one retry without it, sets a process-level
  flag so it is never sent again, and logs a warning. A 429, 500, or an
  unrelated 400 propagates untouched. Verified offline across all of those.
- **`chat()` now also reports an empty response.** The reasoning-only failure was
  previously only detected on the streaming path; `chat()` returned `""` to the
  verification and offer-analysis flows, which then fell into their parse
  failsafes with no explanation. It now raises `EmptyModelResponse` naming the
  model and the reasoning character count. The `max_tokens` on those two
  non-streaming calls was also very tight for a reasoning model — 512 for
  `/api/analyze-offer` and 1536 for `/api/verify` — now 1536 and 2048.
- **`[verify] ValueError: not enough values to unpack (expected 3, got 2)`.**
  `format_verification_context` iterated `_VERIFY_QUERIES` with
  `for k, _, _ in ...` while its entries are 2-tuples, so every verify request
  that reached that function raised and fell into the generic handler, which
  reported a verification failure instead of a crash. It slipped through because
  the earlier probe only counted searches and never called the formatter that
  consumes their output. Fixed, and the path is now covered end to end with a
  stubbed search: populated results, zero results, and a placeholder company
  name.
- **`is_valid_company_name("Not stated")` returned True.** The value the model is
  now instructed to emit when a posting names no employer was not in the
  rejection set, so a direct `POST /api/verify` with that value would have
  searched for the literal string. The `NOT_STATED_MARKERS` check now lives in
  `is_valid_company_name` itself, so every caller rejects those values rather
  than only the scan path. The probe above found this one.
- **The employer name was being guessed by regex over prose.** The scan asked the
  model to work the name into a natural-language summary and then tried to
  fish a company name out of that sentence, which is how verification ended up
  searching for an unrelated phrase and returning all-yellow. The scan now
  outputs a dedicated `COMPANY NAME:` field, parsed by `_parse_custom` and used
  ahead of the regex (which stays as a fallback for older output).
  `clean_company_name()` rejects "Not stated" and the other placeholders the
  model writes when it has nothing, and drops a leading article so "The company"
  is judged on the word after it.
- **Verification asked about six things using eight searches.** Two categories
  were redundant — the endpoint cannot run without a company name, and "Online
  Presence" restated "Company Existence" — and "Scam Reports" plus "Social
  Reputation" were the two most prone to invention. Now three categories
  (Company Existence 40, SEC Registration 25, Reputation 35, summing to 100)
  behind four searches. The prompt forbids inventing another category. Separately,
  `search_company()` is now memoised per company name, because a single text scan
  called it twice and paid for eight searches twice.
- **Empty AI responses were unloggable (`[scan-image] tokens=0, chars=0`).** The
  streaming client read only `delta.content` and did `if not chunk.choices:
  continue`, so three different failures all became "empty string" and surfaced
  as a misleading "unreadable response":
  1. a mid-stream provider error frame — OpenRouter reports upstream failures,
     including rate limits on the routed provider, as a data frame inside an
     otherwise successful 200 stream, so no HTTP error is ever raised;
  2. a model refusal, which arrives in `delta.refusal` and was never read;
  3. reasoning-only output, which goes to a provider-specific `reasoning` field
     the SDK does not declare.

  `chat_stream_pieces` now collects all three, logs the model,
  `finish_reason`, and the counts, and raises `EmptyModelResponse` with the
  reason. The scan, resume, and match flows handle it separately from their
  generic handler, so the log line and the user-facing message are both
  accurate instead of saying the AI returned garbage. Verified offline against
  real SDK chunk objects built with `.construct()` for all four cases plus the
  healthy path. The probe script was deleted; it should become a permanent
  test.

  This was **not** caused by the prompt work. Zero tokens means no text came
  back to parse, and a bad prompt yields wrong text rather than no text. The
  likely trigger is the configured model,
  `dots-studio/dots-3-note-preview:free` — a free route with no availability
  guarantee, on a key that had already hit a 24-hour limit. Worth confirming the
  chosen model accepts image input as well; a non-vision model given
  `image_url` content can return empty on every request.
- **DEFENSE-CH1-3-QA.md** still claims a local Gemma 4 LLM at `localhost:1234`
  and a "fine-tuned XLM-RoBERTa classifier" that does not exist in the codebase.
  It needs rewriting, not word-swapping.
- **`lmstudio.md`** is a 200-line LM Studio changelog with no inbound references.
  Probably delete.
- **`GET /health` is rate limited to 30/min per IP** and the extension now polls
  it every 4s (15/min). Fine for one user, but a shared NAT address with two or
  more open panels will 429. Raise the limit or back off to 6s if seen.

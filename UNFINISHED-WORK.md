# Unfinished Work

Running list of what was left undone, why, and how to verify it. Newest task first.

---

## Task 2.3 — Defamation-Safe AI Output

Code is integrated and the offline gates pass. What remains is verification that
could not be done without a working AI provider quota.

### Not done on purpose

These were skipped deliberately. They are worth doing, just not blindly.

| Item | Where | Why it was skipped |
|---|---|---|
| Prompt-contract tests | new `backend/tests/test_prompt_contracts.py` | Asserts all four prompts contain the observational rules and none of the banned patterns. Cheap and fully offline — the highest-value remaining test. |
| `risk_calculator` unit tests | `backend/tests/` | Yellow contributes half weight, red only when present, level boundaries at 30/50/75. Pure function, no provider needed. |
| Scan-mapping tests | extract `mapApiResponse` out of `ScamScanView.tsx` | It is currently a module-private function, so the "no synthesised score" rule cannot be asserted. Extracting it to `lib/` makes it testable. |
| History-migration test | `migrateScannedJobs` in `entrypoints/sidepanel/lib/scanHistory.ts` | Already extracted and exported specifically so this is easy to add. |
| UI copy review | `VerificationSection`, `VerificationCard`, `ResumeMatchView` | Rewording was done from the code, not from reading the rendered panel. Some strings may read awkwardly in context. |

### Live output-quality pass — requires AI quota

The provider daily limit was exhausted when this work landed, so **no scan was
ever run against the new prompts.** Everything below is unverified assumption.

Run this when quota resets. For each posting, check the four columns:

| # | Posting | Expected red flags | Expected verification | Expected gauge |
|---|---|---|---|---|
| 1 | Obvious fee scam ("pay a 500 peso processing fee to start") | Exactly one `high`: names the fee request. No claim about the employer. | Scam Reports `red` only if a result actually describes a report; `yellow` otherwise | Score from verification only |
| 2 | Legitimate posting using a Gmail address | **Zero** flags. Gmail is explicitly not a flag. | Green where results support it | Score from verification only |
| 3 | Real posting that names no employer | Exactly one `low`: "Company name not stated" | Yellow (skipped), **no risk score** | "Not scored" |
| 4 | A restaurant menu or an article | `VALID: false` and nothing else | n/a | n/a |
| 5 | Deliberately ambiguous posting with a vague employer | At most a `mid`, or zero | Yellow-heavy | Score from verification only |

Also confirm:

- No red-flag reasoning contains *likely, appears, suggests, probably, seemingly, may be, might be, could indicate, often, typically, we think*.
- No red-flag reasoning contains *always, never, definitely, guaranteed, 100%*.
- Nothing anywhere states or implies that a named company is a scam, fraud, or criminal.
- No verification `DETAIL` claims a website or registry was checked when it was not in the provided results.
- `REPORT` and `RECOMMENDATION` both survive parsing — the prompt grew, and
  `/api/verify` is capped at `max_tokens=1536`. If either is empty, the model
  truncated and that cap needs raising again.

### Known risks

- **Recall may have dropped.** Fewer hedged flags is the intent, but "less
  ambiguity" and "fewer findings" trade against each other. The table above is
  the only way to find out. If obvious scams in row 1 are now missed, the
  severity table in `SYSTEM_PROMPT.md` is too narrow.
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

- **`DEFENSE-CH1-3-QA.md`** still claims a local Gemma 4 LLM at `localhost:1234`
  and a "fine-tuned XLM-RoBERTa classifier" that does not exist in the codebase.
  It needs rewriting, not word-swapping.
- **`lmstudio.md`** is a 200-line LM Studio changelog with no inbound references.
  Probably delete.
- **`GET /health` is rate limited to 30/min per IP** and the extension now polls
  it every 4s (15/min). Fine for one user, but a shared NAT address with two or
  more open panels will 429. Raise the limit or back off to 6s if seen.

# Decision record — the scan no longer emits severity

Date: 2026-10-27
Supersedes: the severity ladder in `SYSTEM_PROMPT.md`, `prompts.py`, the parser, and the
wire; the last consumer of the scan's severity as a *decision input* was already gone
before this change — this removes the output nobody was reading.

---

## The rule

The scan's `ANOMALY` line is `label | reasoning`. There is no third slot. The model is
never asked to price a finding — no `high`/`mid`/`low`, no weight, no priority.

## Why

The ladder's only real job, at the end, was a sort key, and even that had eroded:

- **The score it fed is gone.** `scan_result.py` emits `risk_score=None, risk_level=None,
  score_breakdown={}`, and `/api/analyze-offer` dropped the model's `risk_level` and
  `risk_score` too. The verify assessment is `assessment.py`'s decision grid — request
  class × establishment state — and `code_assessment` states outright that the findings
  and their assessments *are not inputs to the decision*.
- **The panel no longer renders it.** After the report-panel redesign, a card's chip is
  derived from the evidence (`stale`, `contradicted`, `unknown`) — the scan's severity is
  explicitly *not* the answer (`AnomalyCards.tsx`).
- **What remained was two mechanical uses and one relic:**
  1. the over-cap selection for the verify request (which findings get checked when
     there are more than `MAX_VERIFY_ANOMALIES`),
  2. a `[severity]` tag in the findings block the verify model reads,
  3. `flagsCritical` on `ScanResult` — produced, typed, round-tripped in tests, and read
     by nothing.

Keeping a model-owned number for a sort key is the exact "the model prices a category
instead of the posting" shape `channel_match.py` and the assessment grid exist to remove.
The taxonomy the finding already carries is a better sort key, and it is code-owned.

## What replaced each use

| Old use | Replacement |
|---|---|
| Over-cap ranking (highest severity first) | The finding's taxonomy `code`, ranked in `useScanSession.ts`: demands for money or account access (`FEE_*`, `PURCHASE_REQUIRED`, `DEPOSIT_REQUIRED`, `PAYMENT_FORWARDING`, `ACCOUNT_CREDENTIALS`) rank above identity exposure (`DOCUMENTS_VIA_THIRD_PARTY`, `IMPERSONATES_AUTHORITY`) and labour schemes (`TASK_FOR_EARNING`), which rank above the ordinary packet (`APPLICATION_DOCUMENTS`) and `OTHER`. The ranking reuses the scan prompt's own selection rule — "what the posting asks the reader to give up" — as code. |
| `[severity]` in the verify findings block | Dropped. The finding's `code` and `quote` still ride along. |
| `flagsCritical` / `SEVERITY_ICONS` | `flagsCritical` deleted outright (no consumer). Card icons derive from the taxonomy `code`: demand codes render the warning icon, everything else the info icon. |

`VerifyAnomaly` (the verify request) lost its `severity` field with it, and
`lm_client.py` lost `_infer_severity`, `_normalize_severity`, `_SEVERITIES`, and the
`_HIGH_SEVERITY_KEYWORDS` list.

## What is deliberately kept

- **Legacy three-part lines still parse.** Recorded scans from before the change carry
  `label | reasoning | severity`; the parser reads the reasoning and ignores the rest,
  the same way `RED FLAG:` stays accepted alongside `ANOMALY:`.
- **`channel_match.py` still assigns a severity.** That is a different severity — a
  code-owned Channel Match rule outcome, not a model judgement — and it is untouched.
  See `docs/decisions/channel-match-severity.md`.
- **Task-for-earning keeps its place in the prompt.** It was added as a *pattern with a
  concrete element*, not as a severity example; its tests (`TestTaskForEarningIsReportable`)
  now assert the element without any ladder.

## The guards

- `test_the_prompt_asks_for_no_severity` — the word `severity` must be absent from **both**
  prompt copies (`SYSTEM_PROMPT.md` and `FALLBACK_SYSTEM_PROMPT`).
- `test_the_anomaly_line_has_two_slots` — `label | reasoning`, no third slot, both copies.
- `test_the_parsed_anomaly_carries_no_severity` — the parser emits no severity key.
- The three severity guardrails in `GUARDRAILS` ("do not stretch the severity ladder",
  "paid tasks, orders, or referrals", "rarely correct") were removed with the ladder they
  guarded; the remaining entries are unchanged, so the two copies can still not drift.

## What this does not claim

- That findings are all equal. They are not — but their ordering is now stated where the
  system can enforce it (the code ranking above), not priced by a model into a field
  nothing read.
- That the ANOMALY CODES list is a severity scale. It never was; it is a taxonomy of what
  the posting asks the reader to give up.

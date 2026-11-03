# The labour-code red

Date: 2026-11-04
Owner files: `backend/app/services/scanner/assessment.py`,
`assessment_copy.py`, `offer_flow.py`

---

## The failure

A task-to-earn DM — "follow any 1 store, send me the screenshots, get a reward" —
scanned twice and read **Caution** both times, with an `TASK_FOR_EARNING` card on
screen and the pick-again button red.

The button was correct and the chip was not, and they were disagreeing for a
reason worth recording: `riskAccent.ELEVATING_RULES` paints
`prohibited_at_unestablished_employer` with the error accent. So a yellow that
already means "a prohibited ask, nobody established" was being shown as urgent
in chrome while the banner said "Caution".

The deeper problem was that **the code had already decided this is red, in one
place only.** `offer_flow` patched `code_assessment`'s return value after the
fact. Consequences, all measured:

- `/api/verify` never got the rule, so the same finding was yellow there.
- The breakdown was internally inconsistent: `assessment: red` beside
  `establishment: unknown` and no field saying why.
- `test_every_path_to_red_needs_the_contradiction` iterated
  `_decide(request_class, state)` with no codes, so it **could not see the rule
  that reads them**, and passed while the product violated its own invariant.

## The decision

**The rule is a cell in `_decide`, and it is consulted from `code_assessment`.**

```python
if request_class == "prohibited":
    if state == "unknown" and _LABOUR_CODES & codes:
        return "red", "task_for_earning_at_unestablished_employer"
```

`_LABOUR_CODES` is `{"TASK_FOR_EARNING"}` — the codes where the reader sells
their labour and is paid at the poster's discretion. `codes` comes from
`_codes_of(anomalies)`, read off either an `Anomaly` or a replayed dict.

### `unknown` only, and why

| establishment | TASK_FOR_EARNING | why |
|---|---|---|
| `contradicted` | **red** | already red by the main rule |
| `unknown` | **red** | nobody is established as responsible for the payment |
| `supported` | yellow | an independent record names the employer; the reader can go and look at it |
| `confirmed` | yellow | the posting's channel is the employer's own; per-referral or per-shift pay is an ordinary business model |

**A confirmed employer paying per referral is not a scam**, and a red there would
be the product asserting something it cannot support. The rule fires only where
there is no one to weigh the finding against.

## This red is not a contradiction, and the template has to know

The assessment vocabulary says `red` means *"a source states something different
from what the posting states."* This red has **no source**. It is red for the
same underlying reason the invariant cares about — the posting cannot supply
evidence about itself, and nothing establishes who would pay — but it is not an
impersonation.

`assessment_copy.statement()`'s red branch said:

> "The communication is not from the employer it names. This is a contradicted
> impersonation."

**That sentence is false for a DM that names no employer.** Rendering it would be
a libel exposure of a new shape: an accusation of impersonation against nobody,
which reads to the reader as an accusation against whoever they assume is behind
it. So `statement()` takes `rule`, and the labour rule gets its own sentence:

> "The posting asks for nothing the rules prohibit. It offers pay per task, order
> or referral, and nothing in the record establishes who would pay it."

The clause "nothing in the record establishes who would pay it" is the fact that
made it red, stated as a fact. A red with no rule — a stored scan, a caller that
predates the field — keeps the contradiction wording, which is right for every
red it can carry.

## What this does not fix

**A task-for-earn scam that borrows a real company's name still reads yellow.**
If the lookup confirms an existence, the establishment is `supported` and the
rule does not fire. That is the identity gap already recorded in `AGENTS.md`
contradiction #7, and pricing it here would mean treating "a company exists" as
"the poster is not that company" — which is the inference the whole channel
comparison exists to avoid.

**`OTHER` still prices `unclassified`.** A task-for-earn posting whose finding the
model codes `OTHER` — the live run produced one — cannot reach this rule. That is
the taxonomy-coverage question in `docs/decisions/assessment-vocabulary.md`, and
it is the next lever, not this one.

## Tests

- `test_code_assessment.py::TestOnlyAContradictionStops::
  test_every_path_to_red_needs_the_contradiction` — rewritten. It now passes no
  codes nowhere and asserts the **one named exception** rather than loosening the
  property. The old version could not reach the code it guarded.
- `test_the_named_red_is_reachable_only_by_that_one_rule` — red at
  `prohibited/unknown`, yellow at `confirmed` and `supported`, and yellow for a
  fee at the same cell.
- `test_assessment_copy.py` — the labour red does not contain "impersonat" or
  "not from the employer"; a red with no rule keeps the contradiction wording.
- Mutation-checked: firing at any state, firing for any code, and never firing
  are each caught.

## Live

The screenshot that started this, end to end through `/api/scan` then
`/api/analyze-offer`:

```
assessment: red
rule:       task_for_earning_at_unestablished_employer
exposure:   prohibited
establishment: unknown
codes:      [OTHER, TASK_FOR_EARNING]
```

Before the change the same scan read Caution with the button red.

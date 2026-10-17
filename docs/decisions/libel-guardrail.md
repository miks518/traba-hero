# Decision record — the prompt rules (libel guardrail)

These are not stylistic preferences. They keep the product from asserting things it
cannot support, which is the legal exposure for the project.

---

## Standing rules

- **Observational only.** Every statement must trace to the input. Unknowns are
  declared, never inferred. All four prompts carry an `OUTPUT RULES` block saying so.
- **Never accuse.** No prompt may describe a named company or person as a scam, fraud,
  or criminal — only what a posting asks for or what a search result states.
- **No hedging, no absolutes.** Banned inference words (likely, appears, suggests,
  probably…) and banned absolutes (always, never, definitely, 100%).
- **Absence is never `red`.** In verification, `red` requires a provided search result
  that actually contradicts a claim the posting made, and the `finding` must name that
  source. "Not found" is `yellow`, which `risk_calculator.py` weights at zero.

---

## A prompt may contradict itself, and the severity list is where it hides

`SYSTEM_PROMPT.md` once offered "low: something like a missing employer name" as an
example while a later bullet banned flagging a missing employer. The model followed the
example, and low severity scores 4 in `risk_calculator`.

**A long prompt drifts, so any rule stated in a *list of examples* must be restated as
an explicit prohibition at the point of use.**

`test_severity_list_never_offers_a_missing_name_as_an_example` parses the severity block
by indentation and inspects only the text after each severity's colon, so a line may
name the phrase in order to forbid it but not offer it as an example.

---

## A prohibition containing a hedge is half a permission, and the model takes the half it needs

The same failure had a second shape. The 2026-10-12 fix for "the model flagged a Gmail
address" added *"Do not flag any of these **on their own**: a free email domain (Gmail,
Yahoo), a missing office address…"* — and that carve-out is the only statement in the
prompt that *permits* flagging one of them.

Two absolute rules followed it ("Do NOT report … Gmail addresses", "A generic or
personal email is not an anomaly"), and a model reading a posting with a free address
plus some other oddity could still resolve the contradiction permissively. It did; the
same flag was reported again on 2026-10-14.

**The hedge is the defect, so grep for the phrase rather than reasoning about the
rule** — `test_the_ordinary_things_rule_carries_no_carve_out` asserts
`"on their own" not in` both prompt copies.

**A `GUARDRAILS` entry cannot catch this shape:** every entry asserts a phrase is
*present*, and this defect is a phrase being *absent*. Two consequences worth keeping:

- A guardrail list is a **floor, not a ceiling**.
- A ban that admits exceptions must have those exceptions **named and closed** ("There
  is no combination of these that makes one of them a finding") or the model will find
  them.

`prompts.py` had drifted too — it carried only the hedged form and neither absolute
rule — which is the failure `test_a_guardrail_cannot_be_dropped_from_one_copy_alone`
exists to catch, and which it did the moment the new phrase was added to `GUARDRAILS`.

---

## A prohibition with no matching permission is a dead end

This is how a task-scam DM scored low risk.

The severity ladder is anchored on the *employer demanding something* — money, goods, a
deposit, a purchase. A "do this task and then earn a reward" DM asks for no payment, so
nothing matched, and the only things marking it as not-a-job were the absences the
prompt forbids flagging. **The model had a prohibition and no permission**, which is why
it regressed across models rather than being a weak-model problem.

**`task-for-earning` is now a named pattern with a concrete element** — discrete tasks,
orders, or referrals completed for payment rather than a role with duties — plus a
`mid` severity example, because `mid` previously carried exactly one example and
anything else fell back to `low` (which scores 4).

**The fix is a positive anchor, not an enumeration of flaggable things**, which would be
a whitelist wearing different clothes: the next scam shape would be invisible to it.

Two guards are load-bearing alongside it:

- **The element must be text the posting *contains*** (the unit of work), never the
  reader's ignorance of a role, or the absence-flag bug returns.
- **Work-followed-by-payment must be stated as the ordinary order**, because "do the
  task, then get paid" reads as the reverse of work-before-money and most jobs are paid
  that way. Without that sentence, every job posting becomes flaggable.

`TestTaskForEarningIsFlaggable` checks all three against **both** prompt copies.

---

## Field rules live in the prompt file, not in Python

**The scan prompt's field rules live in `SYSTEM_PROMPT.md` only.**
`SCAN_OUTPUT_FORMAT` is the bare format skeleton. They were once duplicated into the
user message, which is wasted context and gives a reasoning model more to deliberate
over.

`OUTPUT_RULES` and `SCAN_FIELD_RULES` in `prompts.py` now build only
`FALLBACK_SYSTEM_PROMPT`, so the two copies can still drift. **Nothing enforces that
yet** — see `UNFINISHED-WORK.md`.

---

## The employer name is stated, not inferred

The scan outputs a dedicated `EMPLOYER NAME:` field, and `scan_flow` prefers it over
the regex fallback. Asking the model to state the name in prose and then regexing a
sentence out of the summary is what produced unrelated search keywords.

`clean_company_name()` rejects "Not stated" and other placeholders, and drops a leading
article so "The company" is judged on the word after it.

---

## The recommendation is addressed to a job seeker, not an auditor

The field rule must name its reader. Without that, the model — steeped in the prompt's
own SEC/DTI/PEZA vocabulary — hands the reader a registry lookup: "Confirm the
registration number on the SEC site" is technically actionable and practically useless,
because nobody applying for a job queries a government portal.

The rule says to build on what the results showed and give one step from an ordinary
hiring exchange, and forbids naming a registry, a government website, or a permit
check.

**`RETRIEVAL_FAILED` needs the same treatment:** it is read as an instruction, so it
tells the reader to hold off on money or personal details rather than to "confirm the
employer through an official channel".

---

## `POSTING ANALYSIS` word ban

`POSTING ANALYSIS` must not contain "scam", "legitimate", "suspicious", "genuine",
"fraudulent" or "honest".

**The ban appears in the field rule itself, not only in the prompt preamble**, because a
long prompt drifts and the field rule is what the model weights when writing the
verdict. It also gives the allowed phrasing — describe what the posting asks for, not
what it is.

A verdict naming a post a scam is the libel exposure the whole prompt rule set exists
to prevent.

---

## Both structured prompts state the output format in prose as well as in the schema

`VERIFY_SYSTEM_PROMPT` and `ANALYZE_OFFER_SYSTEM_PROMPT` each carry an
`OUTPUT FORMAT:` line naming their keys, because a model with no schema-capable
endpoint drops the schema (see the 404 fallback in `lm_client.py`) and the prompt is
then the only thing specifying the shape.

Without that line the model writes prose, `_parse_json` finds nothing, and the panel
renders empty cards with no Sources, no report and no recommendation —
**silently, because the request itself succeeded.**

Their "plain sentences only" rules are scoped to the values for that reason.
`test_verify_unschemaed.py` covers the schema-less path.

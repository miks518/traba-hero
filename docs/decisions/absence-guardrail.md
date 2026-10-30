# The absence guardrail

## The failure it was written against

A live scan reported a clean posting as Caution. The anomaly card read
"Pay Information not provided, the posting states no pay amount or
period", it carried no anomaly code, and the assessment summary said
"This post asks you to apply though an Apply now button and does not
request money" — a benign sentence above a yellow chip.

The chain, four links, each deliberate in isolation:

1. **The scan prompt forbids flagging an absence** — "Never flag the
   absence of something", and "If the posting states no salary, do not
   flag salary. Only flag a salary amount that is stated and does not
   fit the role." `test_scan_prompt_file.py::test_prompt_says_absent_salary_is_not_an_anomaly`
   pins both. But that enforcement was prompt-only, and the model
   ignored it. A better model does not close this door: nothing in the
   pipeline checked the label against the rule.
2. **The finding carried no CODE line.** `normalise_code` returns `""`
   for an absent code — deliberately, because absent and OTHER are
   different claims (`anomaly_codes.py`).
3. **`_class_for`'s catch-all prices `""` as `unclassified`**
   (`request_class.py`). That is also deliberate: an unknown code is a
   labelling miss, and clearing a posting because the model mistyped
   would lose a real request silently.
4. **The grid prices `unclassified` yellow** (`assessment.py`), with
   rule `unclassified_request`.

So one hallucinated finding rode a conservative rule into a Caution
verdict. The mismatch the reader sees — benign summary, yellow chip —
is structural: the summary is model-written from what it decided it
saw, while the colour is code-owned from the request class. When a
drifted finding silently changes the class, the sentence stays benign
while the chip turns.

## The decision

The guardrail sits at **`scan_result._anomalies`** — the last gate
before the wire. It drops a finding whose **label** names silence
instead of something the posting contains. Every consumer reads
downstream of `_anomalies` — the verify path's request class, the offer
path, the panel — so one gate covers every channel, and the request
class stays `ordinary` for a posting the model reported nothing real
about.

The trigger list lives in `scan_result.py` as `_ABSENCE_PHRASES`
("not provided", "not stated", "does not mention", "no pay amount",
"omitted", …). Two boundaries, both deliberate:

- **The label only, never the reasoning.** A reasoning that paraphrases
  absence ("the link's destination is not shown") belongs to a real
  finding; the label is the elevator statement, so it is the one field
  whose absence-shape is decisive. A mixed finding — a real element
  "not provided" in a reasoning — therefore survives, and its label is
  what carries it.
- **A narrow list, each drop logged.** A wrongful drop is invisible to
  the reader (the finding vanishes entirely — this was chosen over
  "visible but unpriced", so the reader never sees a card the system
  itself treats as meaningless), so precision beats recall. Every drop
  logs at warning level with the label and a reasoning prefix, so a
  model drift to a phrasing the list misses shows up in the server log
  rather than as a silent widening of the door.

## What was deliberately not changed

- **The `unclassified → yellow` pricing stays.** It exists so a real
  finding that merely got a bad code cannot clear a posting. This bug
  is one shape of finding that should never exist, not a mispricing.
- **The `""`/OTHER catch-all in `_class_for` stays** for the same
  reason. Anything that survives the guardrail prices, as before.
- **No prompt change.** The prompt already forbids it — twice. Adding a
  third restatement would have no mechanism behind it; the guardrail is
  the mechanism.

## Tests

`backend/tests/test_absence_guardrail.py`: the reported finding
vanishes; the request class stays ordinary; the drop does not require
an absent code (OTHER drops too); a real finding survives whole;
absence phrasing in the reasoning only is kept; a mixed list keeps the
real and drops the hallucinated.

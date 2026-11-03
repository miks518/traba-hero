# The ordinary-channel guardrail

Date: 2026-11-04
Owner file: `backend/app/services/scanner/scan_result.py`

---

## The failure

Field report: the same job posting scanned three times, three times yellow. The
employer's existence was confirmed, Similar Offers came back unknown, and
Channel Match was unknown on a free email. The finding was *"Applies via a
personal Gmail address"* or *"informal application through direct message"* —
and its code was `OTHER`.

**The Gmail address was not the cause, and the trace confirmed it.** A free-email
Channel Match gives `establishment = supported`; with a confirmed existence and
an ordinary request class the grid returns **green**. Nothing about the channel
moved the colour.

`OTHER` did. `request_class._class_for`'s catch-all returns `unclassified` for
every code the taxonomy does not name, and the grid prices `unclassified` yellow
in all four establishment states. One escape-coded finding is enough to turn a
clean posting into Caution.

**The prompt already forbids this finding**, three times, with a test
(`test_the_ordinary_things_rule_carries_no_carve_out`) keeping the "on their own"
carve-out from returning. The model reaches for `OTHER` anyway — which is the
same lesson `docs/decisions/absence-guardrail.md` records: a prompt rule with no
mechanism behind it is a rule the model can drift past.

## The decision

**No new code.** `app/services/anomaly_codes.py` admits a code only with a
confirmed claim and citation behind it, and the honest answer here is that
*there is no finding* — not that there is a differently-named one. Adding
`FREE_EMAIL_DOMAIN` would have made the taxonomy carry a category the product
has three prompt rules saying does not exist.

The drop sits in `scan_result._anomalies`, beside the absence guardrail and the
money guard, for the same reason those do: every consumer reads downstream of it,
so one gate covers the request class, the verify path's findings block, and the
panel.

### The scope is the escape codes, and that is load-bearing

```python
_ESCAPE_CODES = frozenset({"OTHER", ""})

def _is_ordinary_channel_flagged(label, reasoning, code):
    if code not in _ESCAPE_CODES:
        return False
```

**A correctly-coded finding is the taxonomy working, and this gate is only about
a labelling miss.** `APPLICATION_DOCUMENTS` already exists for the ordinary
packet and is priced `ordinary`; `DOCUMENTS_VIA_THIRD_PARTY` is about *where*
documents go and `_documents_class` decides it on the free-provider list. Widening
the scope past the escape codes would swallow those, which a mutation test
catches.

### The text is the label **and** the reasoning

Unlike the absence guardrail, which reads the label only. The model writes this
finding with the channel named in either field — *"Requires an informal
application"* says nothing on its face, and only the reasoning under it names the
Gmail account. A label-only read missed that case, and the mutation check found
it: removing the reasoning from the searched text passed every test until a
reasoning-only fixture was added.

### What it does not touch

- **A contradiction is never dropped.** This gate sees a finding before any
  status exists, so it cannot remove evidence — it only stops an escape-coded
  labelling miss from becoming one.
- **The card is not shown.** The drop is silent to the reader, logged at warning
  like the absence guardrail. `docs/decisions/absence-guardrail.md` records why
  that direction was chosen over "shown but unpriced": the reader never sees a
  card the system itself treats as meaningless.
- **`CONTACT_METHOD` still records the channel.** That is the slot that says
  where to apply, and it is where a Gmail address belongs.

## The cost

A Gmail address is *sometimes* worth mentioning — an employer's own domain
beside a free-mail address is the case Channel Match exists for. That case is
**not** this one: it is a Channel Match comparison against a retrieved result,
not an anomaly about application channels, and it is untouched.

What is lost is the ability to show *"the posting asks you to apply by personal
email"* as a card. The prompt's three rules say that card should not exist, and
`CONTACT_METHOD` carries the fact to the verification's claims block, where it is
compared against the employer's own channels and can produce a real finding.

## Tests

`backend/tests/test_ordinary_channel_guardrail.py` — seven ordinary-channel drops,
five correctly-coded survivors, the scope contract, an end-to-end request class,
and a mixed list. Mutation-checked: the guard never firing, the scope widening
past the escape codes, the text reading the label only, and the phrase list being
emptied are each caught.

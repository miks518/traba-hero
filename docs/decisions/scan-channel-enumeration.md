# The scan's channel enumeration

Date: 2026-10-21
Status: in force
Supersedes: nothing. There was no record of the singular slot.
Diagnosis: `docs/superpowers/specs/2026-10-18-verification-comparison-design.md`,
`docs/superpowers/specs/2026-10-21-port-verification-comparison-design.md`

## What this record owns

**The producer side.** What the scan writes, and why. The *consumer* side — the rules
that turn those facts into a status, the `escalation` string, and the strong-channel
floor — is in `docs/decisions/channel-match-severity.md`. The two are one subject seen
from two ends, and they live in two records so neither has to repeat the other.

## What the scan writes

```
CONTACT_METHOD: email | hrmo6@ched.gov.ph
CONTACT_METHOD: email | recruitment.ched@outlook.com
CONTACT_METHOD: form   | bit.ly/ChedRegionForm
```

One **typed** line per channel. The type is free signal: nothing has to be split on a
separator to recover it, and it is the thing that tells a domain from a messenger
handle before any of them is compared.

`CLAIMED_TYPE` is the other half of the same observation:

```
CLAIMED_TYPE: government | private company | recruitment agency | individual | unclear
```

"It says CHED" and "it presents itself as a government office" are two different facts
about one poster, and only the second says what to compare a fee against.

`JOB_TITLE` is a third, written the same way, and it exists for the search planner
rather than for the channel rules: `<role> <employer>` is the only form of the question
"is this role listed on the employer's own site".

## Why the slot was singular, and what that cost

`CONTACT_METHOD` held one value. A posting that named two ways to apply kept only the
last one.

The case that made it matter: the CHED flyer offered `hrmo6@ched.gov.ph` and
`recruitment.ched@outlook.com` side by side. Matching on the first satisfied the rule
while the second — the one the posting actually applies through — went untested. A rule
satisfied by the channel that looks legitimate is satisfied by nothing.

**The dropped channel could not arrive by another route.** The scan prompt forbids
flagging a free email domain as an anomaly, correctly, since a Gmail address is
ordinary in a Philippine posting. So `recruitment.ched@outlook.com` was not an anomaly,
and therefore was not in the findings block either. It existed in the scan's output only
if written into `CONTACT_METHOD`, which could hold one.

So the channel the whole design turns on had nowhere to live, and the fix would have
been undemonstrable on the case that motivated it.

**This had already been identified two days earlier and not built.**
`docs/superpowers/specs/2026-10-16-evidence-hierarchy-design.md:193-197` says the scan
must write any URL, email address, phone number or account the posting directs
applicants to into `CONTACT_METHOD`, and calls it *"the highest-value single change in
the document."*

## Why a repeat accumulates rather than overwrites

A plain `attributes[key] = value` keeps only the last line. That is the original bug
wearing a different hat: the value the test needs is the one that gets thrown away.

So `CONTACT_METHOD` is a **repeatable** key, and the parser joins repeats with `"; "`.
It is deliberately the only one. Accumulating every attribute would merge two `LOCATION`
lines into one unparseable value, which is a worse failure than the last-one-wins the
prompt already discourages by telling the model to omit the line rather than repeat it.

`lm_client._REPEATABLE_ATTRIBUTE_KEYS` is the single place that says which keys
accumulate.

## The separator contract

**The scan's writer and the planner's reader must agree exactly.**

| End | Contract |
|---|---|
| `lm_client._ATTRIBUTE_JOIN` | joins repeats with `"; "` |
| `search_planner.classify_signals` | splits `CONTACT_METHOD` on `";"`, then each piece on `"\|"` |

If either side changes, channels silently vanish: a posting with two channels is
parsed as one, no rule fires, and **nothing errors**. There is no exception to catch it
and no log line to find it by. Both ends have a test, and the two tests have to change
together.

A channel value that itself contains a `;` or a `|` becomes a phantom channel with a
wrong domain. The type prefix is what makes the `|` unambiguous for well-formed
output; a model that writes a bare value containing one of those characters produces
something the planner reads as two channels.

## What `CLAIMED_TYPE` does, and does not, do

**It opens no category.** `expected_categories` is unchanged by `CLAIMED_TYPE`:
categories open on the claims the posting states, and with `Official Registration`
retired none of them is opened by a claimed type.

**It reaches two readers, and the second one matters.**

1. **The search planner**, as a signal about the scan's own fields. It decides
   which follow-up questions are worth a credit. It sets no status.
2. **The verify model**, because the claims block quotes *every* attribute, and
   `CLAIMED_TYPE: government` appears in it verbatim. The model is then asked
   for `government_claim` — "true only when the posting presents the employer
   itself as a government agency" — and `channel_match.py`'s government rule
   escalates a government claim with a non-`.gov.ph` channel to **red**.

So the field is a prompt-level input to a red Channel Match card, reached
through the model rather than through the planner. That is a legitimate
design — it is the posting's own claim about itself, which is exactly the kind
of fact the guardrail allows — but it is a stronger effect than "a signal for
the planner", and the difference between the two paths is worth being explicit
about:

- The planner's use of it decides **which questions to ask**. It cannot make a
  card red.
- The model's use of it decides **what the facts say**. The card is still
  the code's, and the government rule still needs the official side to be a
  retrieved result — an unbacked government claim is demoted to yellow by
  `_bind_to_retrieved`, exactly like every other red.

The value is read leniently, because the prompt's format line is a list of
options and a model that copies it produces the whole list: the first option
is the answer, so "government | private company | …" is read as "government".

## The consumer side, and where the rules live

`docs/decisions/channel-match-severity.md` owns:

- `channel_match.py`'s seven rules and the `escalation` string each fires
- the free-provider list, the lookalike comparison, and the combination rule
- the binding of `channel_match.source_url` against the retrieved set
- the strong-channel floor in `assessment.py`

This record does not restate them. The two meet at one place: the scan writes the
channels, and `channel_match.py` compares them.

## The open question: identity

**The results show whether an employer with this name exists. They do not tell you
whether the person who posted this is that employer.**

This is open on `main`, and `channel_match.py` says so itself:

> It does not prove identity. A matching domain is a retrieved fact, not a guarantee
> that the poster is the company.

A scam that borrows a real employer's name and asks for nothing unusual is caught by
neither `channel_match.py` nor the independent-finding rule, because both compare the
posting's channels against the employer's own channels and find them equal.

The branch `feat/verification-comparison` answered this with a model-written
`name_comparison` — `same` / `differs` / `unclear` — and a `results_entity` field
naming the organisation the results describe. That is a model-owned assessment, which is
precisely the shape `channel_match.py` exists to remove: a model that can be satisfied
by a rule without performing the comparison. It was not ported.

**If this is solved, it must be solved code-side** — a fact the model reports and code
prices, the way `printed_channels` and `government_claim` are facts now. It is
recorded in `AGENTS.md`'s contradictions list as needing a decision.

## What the prompt copies are

Three, and they are separate strings that have drifted before:

1. `backend/SYSTEM_PROMPT.md` — what ships
2. `prompts.SCAN_FORMAT_BLOCK` — the output shape
3. `prompts.SCAN_FIELD_RULES` — the field rules

`backend/tests/test_scan_prompt_file.py` asserts all three, in both directions: the
typed form is present, and the old singular phrasing is gone. The absence assertion is
half the test — a prompt carrying both "the channel it directs applicants to" and
"every channel" says two things, and the model resolves the contradiction the way it
happens to on the day.

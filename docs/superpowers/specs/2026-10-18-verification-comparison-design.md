# The verification stage must compare the posting against the results, not the name against the results

Date: 2026-10-18
Status: design approved, Part 1 unbuilt
Reverses: `verification_prompt.py:_build_verify_prompt` — "the posting's anomalies
used to be sent as well, and both are actively harmful here"

> **Partly superseded, 2026-10-21.** `main` moved the same ground in the opposite
> direction: the model emits facts and the code assigns the verdict
> (`channel_match.py`, `verdict.py`), and the findings reach the verifier as
> `anomaly_assessments` rather than as a severity-free claims block. The decision
> record this design names — `docs/decisions/verification-findings.md` — was **not
> created**; it is superseded by `docs/decisions/scan-channel-enumeration.md` and
> `docs/decisions/channel-match-severity.md`. The channel-enumeration half (Part 1b)
> was built and ported. See
> `docs/superpowers/specs/2026-10-21-port-verification-comparison-design.md`.

## Intent and why

Trabahero's scan of a fake CHED recruitment flyer produced a panel that read as a
real employer. Brave Search, given the same image, produced six correct findings in
one pass. The gap is not model capability — it is that the pipeline never asks the
one question that would have caught it.

**The question is: is this posting from the employer the results describe?** The
pipeline instead asks: *does an employer with this name exist?* For a scam that
borrows a real name, the second question has the answer "yes" — it is the same real
employer — and the first is never asked.

This design closes that gap. The findings the scan already produced reach the
verification stage, and three rules stop a clean employer record from standing in
for an answer about the poster.

## The defect, in four links

### Link 1 — the scan finds the problem and the verifier never sees it

The scan reads the poster's mandatory fee, its identity-document request, and its
`outlook.com` application address. Those become anomalies with severities. The
verify request carries them — the extension sends `anomalies: data.anomalies`
(`useScanSession.ts:398`), and `VerifyRequest.anomalies` accepts them
(`schemas.py:270`, bounded to 20 entries of 2,000 characters).

**`verification_prompt.py:_build_verify_prompt` never reads `req.anomalies`.** The
data crosses the wire, is parsed, is bounded, and is dropped on the floor. The
prompt's own docstring records the removal as deliberate:

> *"The job summary and the posting's anomalies used to be sent as well, and both
> are actively harmful here: the model is asked to report what the search shows, and
> handing it 'Asks applicants to pay a processing fee' invites it to answer about
> the posting instead of the employer."*

That reasoning was sound for the goal it had — report what the search shows. It is
wrong for the goal this design has, because the posting's own asks are not a
distraction from the comparison; **they are the thing being compared.**

### Link 2 — the search confirms the wrong thing

The scan takes the employer name from the poster's wordmark, which reads
"COMMISSION FOR HIGHER LEARNING" — a misspelling of the real body's name. The
search goes out for a body that does not exist. Where the name happens to be right
it is worse: the search finds the real Commission on Higher Education, and every
category comes back green, because it *is* the real body.

### Link 3 — the prompt tells the model to forgive it

`VERIFY_PROMPT.md`, on `risk_level`:

> *"A fee demanded by a business a reader can find, at an address that matches, is
> different from the same fee demanded by a name that appears nowhere."*

This is the instruction doing the laundering. It is also wrong in a specific way:
**finding the employer says nothing about whether the poster is the employer.** A
scammer using a real name produces exactly the first case, and the prompt has no
way to tell the first case from the second.

The second half of the sentence fails the same way. "At an address that matches" —
but the poster offers *two* addresses, `hrmo6@ched.gov.ph` and
`recruitment.ched@outlook.com`. One matching channel was enough to satisfy the
rule.

### Link 4 — the level is overwritten wholesale

`useScanSession.ts:226`:

```ts
riskLevel: nextLevel as ScanResult['riskLevel'],
```

The verify response's level **replaces** the scan's. Not a maximum, not a blend.
Whatever the scan concluded about the fee is discarded the moment a real employer
shows up.

### The inconsistency this exposes

`risk_calculator.py:_combine_scores` already settled this question for the score,
in a docstring that could be quoted at a panel:

> *"Asymmetric: evidence may only **raise**. What the retrieval establishes is that
> a claim is contradicted, not that a posting is safe. **A clean employer record
> must not be able to pull a maxed posting down** to a number the reader would read
> as tolerable."*

That asymmetry was never applied to the **level** — and the level is the only one of
the two the panel shows. The 0–100 score was retired; `riskLevel` is the verdict,
the banner, the headline, and the elevation test. The rule the codebase believes and
enforces on a number nobody sees is not enforced on the number everybody does.

## Goals

- The verification stage sees what the scan found, as facts rather than as a
  severity rating.
- A clean employer record cannot make a money or identity ask look ordinary.
- A posting that names several channels is tested on every channel it names.
- The rule that "evidence may only raise" governs the level, not only the score.

## Non-goals

- **Not a new anomaly taxonomy.** No new rule codes, no `ANOMALY_CODES` changes.
  The findings the scan already produces are enough for the CHED case.
- **Not a change to what the scan detects.** Part 3 below proposes one, separately.
- **Not a rewrite of the verification stage.** The six categories, the gating, the
  citation binding, and the libel guardrail are untouched.

## Anti-goals

- **The verifier must not become a second opinion on the posting.** It still
  reports on the employer. The findings are context, not categories.
- **The verifier must not rubber-stamp the scan's severities.** Hence: facts, not
  ratings. A verifier that echoes the scan's severity cannot correct it.
- **Nothing may be asserted that the results do not support.** The existing rule
  stands, and the new rules must not become a licence to conclude from a name.

## The design

### Part 1 — the findings reach the verifier

**`verification_prompt.py:_build_verify_prompt`** gains a block, alongside the
existing "claims under test" block. Facts only: `flag` and `reasoning`. **The
severity is deliberately not sent.**

The reason severity is withheld: the verifier's job is to be a second opinion. Given
"high: asks applicants to pay a processing fee", a model under instruction to read
the ask against the evidence will tend to adopt the rating rather than derive one.
Given the fact alone, it must judge for itself — which is what lets it correct a
false-positive severity, and what lets it *raise* one the scan under-weighted.
The scan's judgement is the thing under examination; its observations are the input.

The block text, in the prompt:

> WHAT A FIRST READING OF THE POSTING FOUND (context, not a verdict):
> \- *Asks applicants to pay a processing fee*: The posting asks for money up front.
>
> These are observations about the posting, made before anything was searched. They
> are not findings about the employer, and they carry no severity rating here: a
> first reading can be wrong, and one of them can be an overreaction to something
> ordinary. What they give you is what the posting asks for and which channels it
> names — use them to judge the offer and the channels, and to decide what the
> results are being read against. Do not report them as a check, and do not write a
> finding that is only a restatement of one of them — a finding must say what the
> results show about the posting's claim. Do not treat any one of them as proof on
> its own.

**The last sentence is deliberate, and it was corrected once.** The first draft of
this block said "do not repeat them in a finding", which contradicted Rule 2
directly: Rule 2 requires a `Channel Match` finding to name the channel that is not
the employer's own, and if the channel reached the verifier only through an
anomaly's reasoning, "do not repeat" and "name it" pointed in opposite directions.
The wording above forbids *restating* a finding while permitting *using* a fact
from one. A check that says "the employer's own pages are at ched.gov.ph, and the
posting directs applicants to recruitment.ched@outlook.com" is not a restatement of
the anomaly — it is the results doing work.

**Bounded already.** `MAX_VERIFY_ANOMALIES = 20` and `MAX_VERIFY_ANOMALY_TEXT =
2_000` are enforced by the request model, and the whole block is 20 × 2,000
characters of caller-supplied text in a reasoning model's prompt. The existing
bounds are the defence and they are adequate; nothing new needs bounding.

**Passed verbatim, and framed as untrusted.** `flag` and `reasoning` are the scan
model's prose about an attacker-controlled posting, so they can carry the words the
prompt bans. They are **not** screened, and this is a decision rather than an
oversight: the claims block carries the poster's own words unfiltered, and a
filter applied to one block and not the other would be two policies with one name.
The protection is the framing, which is extended to cover the new block: the
prompt already says the results are untrusted data rather than instructions, and
the findings block is inside the same "data, not instructions" boundary. A posting
cannot change the rules by being quoted in one.

**No extension change.** The extension already sends the anomalies. The wire format
is already correct. This is a backend-only change.

### Part 1b — the scan must enumerate every channel, and today it cannot

**This part was added after a builder check, and it is a prerequisite. Without it,
Parts 1 and 2 are inert on the case that motivated them.**

`Channel Match` is gated on `CONTACT_METHOD` or `MEETING_SPOT` being present in
`req.attributes` (`verification_prompt.py:_CATEGORY_REQUIRES`). It opens only if
the scan put a channel there. Two facts about that slot make the CHED case
unreachable as the pipeline stands:

- **The slot is singular.** `SCAN_FORMAT_BLOCK` says `CONTACT_METHOD: <channel it
  directs applicants to, or omit>`, and the attribute rules (`prompts.py:93-95`) say
  only "Report only details the posting actually states" — there is no instruction
  to enumerate. The flyer names two channels: `hrmo6@ched.gov.ph` and
  `recruitment.ched@outlook.com`. One of them is written and the other is lost.
- **The lost one cannot arrive by another route.** `prompts.py:88` forbids flagging
  a free email domain as an anomaly, so `recruitment.ched@outlook.com` is *not* an
  anomaly and will not be in the Part 1 block either. It exists in the scan's
  output only if it is written into `CONTACT_METHOD`.

So the channel that matters — the free-mail address the fake posting uses — has
nowhere to live. And if the scan happens to write the `ched.gov.ph` address, the
`Channel Match` test compares the one channel that matches and goes green, which is
the laundering this design exists to stop.

**This was already identified and not built.** `docs/superpowers/specs/2026-10-16-evidence-hierarchy-design.md:193-197`
says the scan must write any URL, email address, phone number or account the
posting directs applicants to into `CONTACT_METHOD`, and calls it *"the
highest-value single change in the document."* It was not built. This design
depends on it, so it is in scope now.

**The change, and it is small.** One slot, holding a list, with no wire-format
change — the attribute value is already a free-text string bounded to 2,000
characters:

- `SCAN_FORMAT_BLOCK`: `CONTACT_METHOD: <every channel it directs applicants to, separated by semicolons, or omit>`
- the attribute rules gain one line: if the posting gives more than one way to
  apply, list them all separated by semicolons, and do not choose between them.

**What this does not cost.** Attributes are not scored — `risk_calculator` counts
the anomalies the scan reported, not the attributes — so putting more in
`CONTACT_METHOD` changes no score and no severity. It changes what the verifier is
able to test, which is the whole point.

**What it does not fix.** It does not fix the employer name (Part 3), and it does
not make `Channel Match` red by itself. It makes the channel *available to be
tested*; Rule 2 is what does the testing. The 2026-10-16 design says the same
thing: *"Both halves are required. The first without the second gets a category
that is requested and then answered wrongly, which is worse than never asking."*

### Part 2 — three rules, in `VERIFY_PROMPT.md` and its Python fallback

The `.md` file is the source of truth and the Python copy is the fallback. Both
change, together, or they drift — which has happened here before.

**Rule 1 — identity. A new OUTPUT RULE.**

> The results tell you whether an employer with this name exists. They do not tell
> you whether the person who posted this is that employer. A posting can name a
> real company and still come from someone else entirely, so a matching name, a
> matching logo or a matching domain is a claim to test, not a fact about the
> poster. The only things that speak to who is actually asking are the channel the
> posting directs applicants to, the address it gives, and the contact details it
> carries.

This is the deepest correction and it belongs at the top, because it governs every
category, not just `Channel Match`.

**Rule 2 — every channel. An addition to `Channel Match`.**

> A posting may name more than one way to apply. Test every channel it names, not
> only the one that looks most legitimate. If the results show the employer using a
> different channel than one the posting names, that is a contradiction and the
> status is red — even when another channel the posting names does match the
> employer's own. A posting that offers the employer's real address alongside one
> the employer does not use is exactly the pattern this category exists to catch,
> and matching on one channel does not excuse the other.

**Rule 3 — the level. A replacement inside the `risk_level` field.**

Replace:

> A fee demanded by a business a reader can find, at an address that matches, is
> different from the same fee demanded by a name that appears nowhere.

With:

> Finding the employer does not make the ask ordinary. A real employer that asks
> for a fee is still asking for a fee, and evidence that the name is real says
> nothing about whether the poster is that employer. Weigh the ask together with
> the channel it is made through: a fee asked through the employer's own address is
> ordinary, and the same fee asked through an address or account the employer does
> not use is not — whatever else the results confirm about the employer.

The good parts of the original survive: weigh the ask against who is asking, read
the categories together, do not let the loudest single finding decide. Only the
sentence that laundered is replaced.

### Part 3 — the scan's internal contradiction (separate, later)

Link 2 above is a scan defect: the employer name was read off a stylised wordmark
and never reconciled against the seal and the domain in the same image. Brave
caught it as *"Wrong agency name."* Nothing in the pipeline compares our own
extracted fields to each other, and no part of Parts 1–2 creates that comparison.

The proposal, for a later session: the scan reports a contradiction between the
name a poster writes and the domain or seal it displays, as an ordinary anomaly,
which then flows to the verifier through Part 1 and to the panel as a finding. This
needs a rule in `SYSTEM_PROMPT.md` and a taxonomy decision, and it is prompt work
that cannot be verified offline — so it is not bundled with Parts 1–2, which can.

### The level floor — deliberately deferred, and revisited after the live test

`_combine_scores` already implements "evidence may only raise" for the score. The
level has no equivalent, and `useScanSession.ts:226` overwrites unconditionally.

**This design does not change that**, because the user chose to hand the findings to
the verifier rather than to floor the level, on the better argument: a floor only
helps when the scan caught the problem, while a second reading also covers the case
where it did not.

**But it should be looked at again once Part 1 has been run live.** If the verifier,
now holding the findings, still returns a lower level than the scan on a posting
with a money or identity ask, then the prompt rules are not sufficient and the
structural floor is the remaining fix. Recorded here so the next session reads it
as a known open question rather than a new discovery.

## Constraints

- **The default test suite must be fully offline.** No live provider calls.
- **Both prompt copies change together.** `VERIFY_PROMPT.md` is the source of
  truth; `verification_prompt.py:_FALLBACK_VERIFY_PROMPT` is the fallback and
  drifts if only one changes.
- **The findings block must not become a category.** The six categories are a
  closed set and the request's gating list still decides which are reported.
- **`shouldShowCheck` still applies to everything the verifier says.** The findings
  block puts model prose about a named employer into the prompt; the panel's libel
  filter already covers the verifier's output and is unchanged by this.
- **The scan prompt has two copies too.** `SYSTEM_PROMPT.md` and
  `prompts.py:SCAN_FORMAT_BLOCK` / `SCAN_FIELD_RULES` hold the same rules, and the
  Part 1b change touches both.

## Where the record lives

- **The new decision record is `docs/decisions/verification-findings.md`**, and
  `AGENTS.md`'s documentation map gains a row for it. There is no existing record
  of the anomalies' exclusion to supersede — `docs/decisions/verification-design.md`
  never mentions them — so the re-admission needs its own record, and the map is
  stale without the row.
- **The three rules live in the decision record, not in `docs/architecture.md`.**
  `architecture.md` has no section describing the verify prompt's contents today;
  it names the file and the loader. It gains a pointer to the record, and the
  record holds the rules and the reasons. One fact, one place.
- **`docs/architecture.md`'s component map** still needs the new behaviour described
  in the "what the verify prompt contains" sense — one paragraph, pointing at the
  record rather than restating it.

## Verification

### Offline, and complete

| Check | Where |
|---|---|
| The findings block appears in the prompt, with the flag and the reasoning | new `backend/tests/test_verify.py` case on `_build_verify_prompt` |
| A request with no anomalies produces no block at all | same |
| The severity never appears in the prompt | same — the point of the decision |
| The claims block still carries no anomaly field | rewrite of `test_verify.py:197` — its intent survives, in modified form |
| The three rules are in `VERIFY_PROMPT.md` | new `backend/tests/test_prompt_contracts.py` |
| The three rules are in the Python fallback too | same — the two copies must agree |
| The banned hedge and accusation words are still absent from both | same |
| The six categories and the gating are unchanged | same |
| `CONTACT_METHOD` is described as holding every channel, in both scan prompt copies | same |

**Two existing tests assert the opposite of this design and are rewritten in
place, not deleted:**

- `test_verify.py:91` `test_excludes_job_summary_and_anomalies` — becomes
  "excludes the job summary, includes the findings". `job_summary` stays excluded;
  the anomaly marker moves from *must not appear* to *must appear*.
- `test_verify.py:197` `test_the_anomaly_exclusion_is_not_a_door_attributes_walk_back_through`
  — its concern is real and survives: the **claims block** must carry the posting's
  words and none of the model's characterisations. It becomes an assertion that
  the claims block is clean while the findings block is present, which is the
  stronger version of what it was checking.

`test_prompt_contracts.py` should reuse the parametrized both-copies fixture
already in `backend/tests/test_claim_prompt.py:26-30` rather than invent a second.

### Live, and the developer's to run

**A scan cannot reach the state this design is testing.** The scan's employer name
is "Commision on High Learning" (Part 3), so the search goes out for a body that
does not exist, and the panel has no field for the reader to correct it
(`docs/architecture.md:426-429`). A live scan therefore cannot demonstrate this
design on the CHED case.

**The live test is a hand-written `POST /api/verify`.** The body is a fixture:
`company_name` set to the real body's name, `attributes` carrying both channels as
Part 1b would have written them, and `anomalies` carrying the fee and the
identity-document findings. The request bypasses the scan, so it tests Parts 1 and
2 — the verifier's blindness and its rules — without needing Part 3.

The fixture and the exact command belong in
`backend/scripts/ched_verify_probe.json` and the decision record, not in the spec,
because they are an artifact rather than a design decision.

**Do not run this without the developer's permission.** The key is shared and its
limit blocks their own testing for 24 hours.

## What's left to the builder

1. `verification_prompt.py`: `_stated_findings`, the findings block, and the
   rewritten `_build_verify_prompt` docstring — which must record *why* the
   anomalies are back, so the next reader does not remove them again.
2. `VERIFY_PROMPT.md` and `_FALLBACK_VERIFY_PROMPT`: the three rules, together.
3. `prompts.py` (`SCAN_FORMAT_BLOCK`, `SCAN_FIELD_RULES`) and `SYSTEM_PROMPT.md`:
   Part 1b, the channel enumeration, in both copies.
4. The offline tests above, and the two rewrites.
5. `docs/decisions/verification-findings.md` — the new record — plus the
   `AGENTS.md` map row and the `docs/architecture.md` pointer.
6. `backend/scripts/ched_verify_probe.json` — the live fixture and command.
7. `UNFINISHED-WORK.md` — the CHED entry moves from "open" to "Parts 1, 1b and 2
   built, live verification outstanding", and Part 3 and the level floor are
   recorded as still open.

## The builder check, and what it changed

A fresh reviewer was asked what it would still need answered before it could plan
this. It raised five. Four were decisions and are now made: the block text's
"do not repeat them in a finding" was corrected so it no longer contradicts Rule 2
(Part 1); the findings are passed verbatim with the untrusted-data framing
extended, because the claims block is unfiltered too and two filters with one name
is worse than one (Part 1); the live test is a hand-written `POST /api/verify`
rather than a scan, because the scan's name cannot reach the state under test
(Verification); and the decision record is a new file with an `AGENTS.md` map row
(Where the record lives).

**The fifth was not a decision. It was a hole in this design.** The reviewer asked
whether `Channel Match` opens on the CHED flyer at all, and the answer was that it
cannot, because the scan has nowhere to put a second channel and a free-mail
address is forbidden from being an anomaly. That became Part 1b, and it is a
prerequisite: without it the CHED case never reaches the rules this design
changes, and the design would have shipped a fix that could not have been
demonstrated on the case that motivated it.

## What this design does not claim

It does not claim the CHED case is solved. It removes the two mechanisms that made
the verdict wrong — the verifier's blindness to the findings, and the prompt rule
that told it to forgive — and it does so in a way that can be tested offline. Whether
that is enough is one live scan away, and until that scan runs, this is a change
with a plausible mechanism rather than a demonstrated fix.

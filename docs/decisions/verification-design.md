# Decision record — verification design

Owner files: `backend/VERIFY_PROMPT.md`,
`backend/app/services/scanner/verification_prompt.py`,
`verification_parser.py`, `verification_flow.py`,
`channel_match.py`, `assessment.py`.

---

## The prompt file is the source of truth, and the module keeps a full fallback copy

`VERIFY_PROMPT.md` is what the backend loads; the in-module copy is a fallback.

The prose used to be a constant in `verification_prompt.py`, which meant editing a prompt
meant editing Python. It moved because this is the longest prompt and its rules are the
libel guardrail, so it needs to be readable and diffable in a text file.

`_FALLBACK_VERIFY_PROMPT` is kept **complete rather than reduced to a role line**: a
deployment shipping without the file must not verify against a stub.

**The two can drift** — that is the known risk. `test_verify_prompt_file.py` asserts they
currently agree, re-asserts the guardrails against the file the backend loads, and checks
the loader follows the file rather than the constant.

`VERIFY_SYSTEM_PROMPT = load_verify_prompt()` is evaluated at import, so **editing the
file needs a restart**, exactly as with the other three prompts.

---

## Exactly five claim categories

**Company Existence**, **Location / Branch**,
**Channel Match**, **Reputation**, **Similar Offers**.

- The first three were the old category list.
- `Location / Branch`, `Channel Match` and `Similar Offers` test *claims the posting made*
  rather than facts about a company name, **because a check that a real employer always
  passes cannot tell an impersonator from an employer.**
- "Company Name" and "Online Presence" were removed earlier as redundant — the scan
  already establishes whether a name was present, and the endpoint cannot run at all
  without one.
- "Scam Reports" + "Social Reputation" were merged into Reputation.
- **"Official Registration" was retired on 2026-10-27**, and it is the one removal that
  was not a rename or a merge. It was the only category whose evidence the search never
  sought: the `registration certificate` query went when the budget was three credits,
  the category was gated on the posting asserting `REGISTERED_AS`, and the check then
  ran against a result set no query had aimed at registration — so "not confirmed" was
  the honest answer *by construction*, not a finding. A small employer's SEC filing is
  often unindexed, and a business is not required to be registered to hire honestly,
  so unconfirmed carried no information either way. The impersonation shape the
  category was thought to serve — a fake "CHED" — is caught by `CLAIMED_TYPE=government`
  plus Channel Match's government-domain rule, not by a registration lookup. Company
  Existence carries the identity question. `REGISTERED_AS` survives as a scan attribute
  (the posting's own claim, quoted back in the verification's claims block); only the
  check category is gone. A stored result carrying the old label still parses and
  renders — the parser accepts any label — but no new response can produce one.

**Forbidding a sixth is load-bearing:** the score is a fixed weight table, so an
invented category has no weight and silently vanishes.

### Channel Match is reported as facts, not a status

Four categories carry a status in `checks`. Channel Match does not. The model
returns a top-level `channel_match` object with `printed_channels`,
`official_channels`, `government_claim`, `finding`, `source_title` and
`source_url`, and `channel_match.py` assigns the status:

- A free-provider email is **yellow**, informational. It is ordinary in
  Philippine job postings, whether or not the results name an official channel.
- A government claim with a printed domain outside `.gov.ph`, or a printed domain
  that imitates the official one, is **red**.
- A non-matching domain plus an independent finding (a fee, a credential request,
  documents sent to a third party) is **red**. The combination is the pattern.
- A different domain with no independent finding is **yellow**. "The results do
  not confirm this channel" is not "the results contradict this channel."
- A matching channel is **green**.

The official side is dropped when its `source_url` was not retrieved. A model can
copy the official domain from the posting and call it the employer's; without a
retrieved result behind it, the comparison has no anchor and the status must not
become red.

The full rule set and the two regressions it was written for are in
`docs/decisions/channel-match-severity.md`.

---

## Anomalies are assessed against the same evidence, and do not touch the status-bearing checks

The verify stage receives the scan's findings as a numbered block, plus a bounded
excerpt of `job_summary` (4,000 characters) as context. It returns
`anomaly_assessments`, one entry per finding, with `index`, `status`, `finding`,
`source_title` and `source_url`.

- The status set is `stale | yellow | red`. **`green` is deliberately absent**:
  a retired finding is grey (`Stale`), not a green pass. The five status-bearing
  category checks keep `green | yellow | red`; Channel Match is code-assigned from
  facts and is not one of them.
- `stale` — a retrieved result **about this employer** accounts for the finding's
  stated explanation, so the finding no longer stands. A general page about the
  practice is not enough, and a result that confirms only *some* fee without
  accounting for the stated purpose is not stale either: the purpose is the
  claim under test.
- `red` — a retrieved result about this employer states something different from
  what the posting states.
- `yellow` — the default. The results did not settle it, the only support is a
  general page, or there was nothing to check. "Nothing was found" is yellow,
  never red.
- A `stale` or `red` is shown only with the retrieved URL it relies on. An
  unbound URL is dropped, and an unbacked `stale`/`red` is demoted to `yellow`.
  Unknown statuses, blank findings, duplicate indices and indices outside
  `1..len(anomalies)` are dropped rather than renumbered.

**The findings block is not a second source of evidence for the five categories.**
It is labelled as the posting's claims, and the prompt forbids a finding from
making a category green or red. A fee demand must not push `Reputation` red, and
a finding the results account for must not push `Similar Offers` green. Without
that rule, passing the findings into the same prompt would reopen the failure the
original exclusion was written to prevent.

A `stale` assessment removes that specific finding from the code's posting score
in `assessment.py`. The model does not write a lower level; the exclusion is the
mechanism. `yellow` and `red` assessments do not change the posting score.

The labeled-text fallback has no `anomaly_assessments` section, so it returns an
empty list and every card renders amber. Its missing `assessment_reason` is the same
declared degradation. The final level is still computed in code; the fallback
does not remove it.

The client derives the final chip from the assessment rather than accepting a
second severity from the model: `stale → Stale` (grey), `red → the scan's
severity`, `yellow → Unconfirmed` (amber), in flight → `Checking` (neutral).
`Checking` asserts no severity. More than 20 findings are capped before the
request, highest severity first; the omitted cards remain with an amber note.
See `docs/superpowers/specs/2026-10-20-anomaly-evidence-assessment-design.md`.

---

## The final level is code-owned

The verify model used to return `risk_level` and `risk_score`. It no longer
does, and the flow ignores them if an old provider still sends them. The level
comes from `assessment.py`:

- `_posting_risk_from_flags` prices the posting's findings.
- `_refutation_score_from_verify` prices the retrieved contradictions.
- `_combine_scores` keeps the additive asymmetry: verification can raise the
  posting's score but cannot lower it.
- A strong Channel Match red gets a floor of `high` (51). It does not reach
  `critical` on its own; the combined score still has to pass 75.

The reason is recorded in `docs/decisions/scoring-model.md`: the model owning the
level let one weak Channel Match observation become "Do not proceed." The model
still writes `report`, `recommendation`, `assessment_reason` and
`anomaly_assessments`; it does not write the number.

A failed search still returns `riskLevel: null` and `riskScore: null`. A readable
response with no usable check does the same. Undefined is not `low`.

---

## Registration is not the same as the SEC — and then retired

The category was `SEC Registration` until a test showed a company holding a DTI/PEZA/BOI/LGU
registration being reported as inconclusive.

It became `Official Registration`, and the prompt named SEC, DTI, PEZA, BOI, a local
government unit business permit and government portal listings as equally valid.

**Scoring "no SEC number" against a company that has a DTI registration is a false
negative that made the card useless rather than merely cautious.**

**The category was retired on 2026-10-27** — see "Exactly five claim categories" above
for the reasoning. `verification_parser._LEGACY_LABELS` still maps the legacy
`SEC Registration` label forward, and the parser accepts any label, so a stored result
carrying either old name still parses and renders.

---

## Each check returns the fact and its source, not a 20-word summary

The old `detail` cap discarded almost everything retrieval found: roughly 3,000
characters of results became three details of at most 20 words.

The schema now carries:

- `finding` — the one fact that decided the status, **uncapped**
- `source_title` and `source_url` — **copied exactly from the provided results, never
  constructed**
- a top-level `evidence` list the panel renders as clickable sources

**This is the only channel by which online evidence reaches the user, so a fabricated
URL here is a fabricated citation.** Binding it in code is recorded in
`docs/decisions/security-boundaries.md`.

---

## The text parser is the fallback, not the primary path

`verification_parser.py` splits the response into per-`VERIFY` blocks and extracts
`STATUS` and `DETAIL` from each independently, rather than matching the whole shape in
one regex — a single missing `END VERIFY` used to make one match span two blocks and
swallow a category.

It is now the **fallback** parser, used only when the provider does not honour structured
output.

---

## A partial parse is never silent

`verification_flow` logs
`[verify] Parsed N of 6 expected categories; missing: ...`.

It also logs `[verify] Parsed N of M anomaly assessments; missing indices: ...`
when the model omits a finding. A missing assessment is not filled in; the card
renders its own amber "no assessment recorded" note.

The retired labels — `risk_calculator`'s weight table knew the six canonical labels
plus the legacy `SEC Registration` — are history: the parser accepts any label, so a
stored result carrying one parses and renders. **Any other legacy label such as "Scam
Reports" parses and renders but carries no assessment weight, because an unweighted
label is silence rather than a default.**

---

## Status labels are named on the axis they are judged on

`green` / `yellow` / `red` render as **Supported** / **Not established** /
**Contradicted**.

The anomaly assessment vocabulary is separate. `stale` / `yellow` / `red` render
as **Stale** (grey) / **Unconfirmed** (amber) / **Contradicted** (red, with the
scan's severity chip). `green` is deliberately absent there, because a finding
the evidence accounts for is retired rather than praised.

`yellow` is amber in the card and that is deliberate — see
`docs/architecture.md` for the full rendering rule and its scope limit.

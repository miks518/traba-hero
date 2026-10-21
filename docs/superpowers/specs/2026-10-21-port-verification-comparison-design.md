# Porting the Verification Comparison Branch

**Date:** 2026-10-21
**Status:** Design Approved
**Supersedes:** Nothing. Adds to `2026-10-18-verification-comparison-design.md` and
`docs/decisions/channel-match-severity.md`.
**Branch:** `feat/verification-comparison` (13 commits, tip `492f862`)

---

## 1. The problem

`feat/verification-comparison` was started on 2026-10-18 to answer one question: *can
the verification stage weigh what the posting asks against what the search shows, so
that a scam borrowing a real employer's name is not laundered by that employer's clean
record?*

While it was open, `main` moved the same ground in a different direction. The verify
model now emits **facts** and the **code** assigns the verdict: `channel_match.py` turns
`printed_channels` / `official_channels` / `government_claim` into a status and an
`escalation`, and `verdict.py` computes the level and the score. The branch's design
does the opposite — the model owns the level (`_read_risk_level`, `_read_risk_score`),
owns the identity comparison (`results_entity`, `name_comparison`), and owns the
corroboration of the scan's findings (`findingCorroborations`).

Two of those are now the same fact in two places, and one of them (`anomaly_assessments`)
already ships on `main` in the code-owned form the branch's `findingCorroborations` was
reaching for.

So the branch cannot be merged: its `verification_flow.py` would revert
`docs/decisions/channel-match-severity.md`, and its
`docs/decisions/verification-findings.md` would put a second "in force" record on a
subject `main` already has one for.

**But the branch is not empty.** Two of its commits hold work `main` has no equivalent
of, and one of them is the input `main`'s `channel_match.py` was built to consume and
cannot currently be fed.

## 2. What is in the branch, and what each part is worth

Thirteen commits, stacked:

```
492f862  Prune UNFINISHED-WORK.md, and correct the contradictions it caused
8f71e25  Adaptive verification search, behind VERIFY_SEARCH_MODE=fixed
29fcf66  fix(panel): nothing is shown as a finding until the search has spoken
50c5931  feat: a finding is shown only once the search has confirmed it
e3a9639  feat(verify): make the identity comparison a structured step
2b34784  feat(scan): one typed line per channel, and the claimed type
0a05bbd  test: pin the decisions a reviewer found were unpinned
70eb6b0  docs: the CHED entry moves to built, with the live test outstanding
ac918e0  docs: record the verification findings decision, and pin the live probe
900038f  feat(scan): enumerate every channel a posting directs applicants to
6d8aac4  feat(verify): stop a clean employer record from discounting what the posting asks
8454366  feat(verify): give the verification stage the scan's findings
```

| Commit | Worth | Verdict |
|---|---|---|
| `2b34784` | The scan writes **one typed line per channel** and the type it claims. `CONTACT_METHOD` becomes repeatable, `CLAIMED_TYPE` is added. | **Port** |
| `8f71e25` | `search_planner.py`: entity resolution, planned follow-up queries, result labelling, `VERIFY_SEARCH_MODE`. | **Port** |
| `8454366`, `50c5931`, `29fcf66` | The scan's findings reach the verifier, and nothing is shown as a finding until the search has confirmed it. | **Already on `main`** as `anomaly_assessments` + `verdict.py`, code-owned. Do not port. |
| `6d8aac4`, `900038f` | The findings reach the verifier; the scan enumerates every channel. | Split: the channel half is in `2b34784` (port), the findings half is `8454366` (skip). |
| `e3a9639` | The identity comparison as a structured step: `results_entity`, `name_comparison`. | **Do not port as model-owned fields.** The question stays open — see §5. |
| `ac918e0`, `0a05bbd`, `70eb6b0` | The decision record, the tests that pin it, the live probe. | Rewrite, do not copy — see §4. |
| `492f862` | Prunes `UNFINISHED-WORK.md`. | **Do not port.** `main` deprecated that file and replaced it with the contradictions list in `AGENTS.md`. |

## 3. The dependency that fixes the order

`8f71e25` **hard-depends** on `2b34784`, and the dependency is in the data, not just in
the history:

- `search_planner.classify_signals()` reads `attrs["CONTACT_METHOD"]` and splits it on
  `;` and `|`.
- `search_planner.classify_signals()` reads `attrs["CLAIMED_TYPE"]` and
  `attrs["JOB_TITLE"]`.
- `lm_client._REPEATABLE_ATTRIBUTE_KEYS` joins repeats with `"; "`.

**The scan's writer and the planner's reader must agree on the separator exactly.** If
they drift, the channels silently vanish — a posting with two channels is parsed as
one, and no rule fires, and nothing errors.

This is also why the cherry-pick order matters mechanically. `8f71e25`'s diff was
computed against a base that already had `2b34784`. Cherry-picking it first produces
**seven** conflicts; cherry-picking in branch order produces **two**, one of which is
`UNFINISHED-WORK.md` and the other a single import block.

## 4. The decision record is rewritten, not copied

`docs/decisions/verification-findings.md` (242 lines on the branch) cannot be ported
as-is, because it documents a design `main` has replaced:

- It states the findings reach the verifier "as facts and **not** as severities".
  **False on `main`** — `_findings_block` sends `[{severity}] {flag}`.
- It states the three prompt rules (identity, every channel, the level) are in force.
  **False on `main`** — the level is computed in `verdict.py` and the channel status in
  `channel_match.py`.
- It points at `name_comparison` and `results_entity`, which are not being ported.

`main` already has `docs/decisions/channel-match-severity.md`, which owns the
consumer-side rules. The *producer*-side facts — what the scan writes, and why the
singular slot was the bug — have no home. So:

- **New:** `docs/decisions/scan-channel-enumeration.md` owns the repeatable
  `CONTACT_METHOD`, `CLAIMED_TYPE`, `JOB_TITLE`, and the separator contract with the
  planner. It states the facts and points at `channel-match-severity.md` for what the
  code does with them.
- **Deleted:** the branch's `verification-findings.md` is not ported. Its surviving
  reasoning is folded into the new record and into the contradictions list.

## 5. The identity question stays open, and is recorded as open

The branch's rule 1 — *the results tell you whether an employer with this name exists;
they do not tell you whether the person who posted this is that employer* — is a real
gap, and `main` does not close it. `channel_match.py` says so itself:

> It does not prove identity. A matching domain is a retrieved fact, not a guarantee
> that the poster is the company.

`main` handles the impersonation case through *independent findings* (a fee finding
next to a matching channel) rather than through an identity comparison. That is a
different mechanism, and it is weaker: a scam that borrows a real employer's name and
asks for nothing unusual is not caught by either.

The branch's answer was to make the model emit `name_comparison: same | differs |
unclear`. That is a model-owned verdict, and `main`'s direction is facts-not-status:
`channel_match.py` is precisely the case of a model-written conclusion that was moved
into code.

**Decision:** the identity question is recorded in `AGENTS.md`'s contradictions list as
open, with the note that if it is solved it must be solved code-side. It is not ported
now. Nothing is lost by leaving it open; a wrong model-owned field is worse than a
recorded gap.

## 6. The wire

Two additions to the verify result event:

- **`rounds`** — what each query was for and what it returned. It replaces nothing;
  `queries_issued`, `model_queries`, `search_count` and `queries_failed` all stay.
- **`rounds: []`** is added to the **no-company early return** as well, so both result
  events carry the same keys. The branch's version omits it there, which means a client
  reading `rounds` has to handle its absence on exactly the response that most
  obviously searched nothing.

`rounds` is backend-only for now — the frontend does not read it, and
`entrypoints/sidepanel/types/index.ts` does not declare it. This is tracked in
`AGENTS.md`'s contradictions list, the same way `escalation` is.

## 7. What ships off

`VERIFY_SEARCH_MODE` defaults to `fixed`, and it stays there.

- `fixed` is `main`'s behaviour exactly: the employer-name query plus up to two the
  scan model proposed, all fired before anything is known.
- `adaptive` is Round 0 (classify the scan's own fields), Round 1 (the anchor query,
  unchanged), then a planner that chooses up to two follow-ups from what Round 1
  returned.

The branch's own commit says it plainly: *"Shipped OFF. Nothing here has been shown to
improve a verdict, and the fixtures that would decide it have not been run."* That
stays true after the port. The flag exists so the question can be answered later with
one line of change.

Two invariants make "off" mean off, and both are asserted by tests:

1. **The flag off must not alter the call, not merely the queries.** `fixed` mode calls
   `runtime.get_search()(query)` with one argument. The scoped form
   `runtime.get_search()(query, include_domains=[...])` is only ever reached with a
   scope.
2. **`format_results` is byte-identical when its two new optional parameters are
   omitted.** The two parameters are `entity_name: str = ""` and `labels: dict | None = None`.

## 8. Scope of a scoped follow-up

`search()` gains `include_domains: list | None = None` as a third parameter, after
`max_results`. It is sent with `include_domains_mode: "prefer"`, **never** the provider
default `restrict`.

- `restrict` confines results to the listed domains, which would discard exactly the
  JobStreet, Indeed PH and PESO pages the `country` boost exists to surface. There is
  no configured `INCLUDE_DOMAINS` and there is not going to be one.
- `prefer` boosts the listed domains and still searches the rest of the web. It is the
  same kind of lever as `country`, and the two coexist.

**A scope is only ever a domain that came back from an earlier search.** A domain the
posting supplied is never scoped to: that would search precisely the thing under
suspicion.

## 9. What is not ported

- The `.planning/` directory (16 files) — scaffolding, not product.
- `SCORING-SOURCES.md` — deleted on `main`; its §8 was the only record of the
  conflicting account of the posting-severity weights, and AGENTS.md records that it
  can no longer be checked.
- `UNFINISHED-WORK.md` — deprecated on `main`, replaced by the contradictions list.
- `jobposts/Job Post Scan Report*.html` — output dumps, already removed on `main`.
- `package-lock.json` churn — not needed; no dependency changes.

## 10. The end state

The branch is deleted. `feat/verification-comparison` has contributed two commits'
worth of code and one new decision record; the rest of it is retired by being
superseded.

Nothing is pushed. `main` is a local branch, and the commits are local until the
developer says otherwise.

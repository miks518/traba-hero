# Porting the Verification Comparison Branch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the two commits of `feat/verification-comparison` that `main` has no
equivalent of — the scan writing every channel, and the adaptive search planner — on
top of `main`'s code-owned verdict, without reverting it.

**Architecture:** Cherry-pick `2b34784` then `8f71e25` onto `main` in branch order,
resolving six small conflicts. `2b34784` makes `CONTACT_METHOD` a repeatable typed
attribute and adds `CLAIMED_TYPE`; `8f71e25` adds `search_planner.py`, a
`VERIFY_SEARCH_MODE` setting defaulting to `fixed`, and a two-round query issuer in
`verification_flow.py`. The model-owned verdict, identity fields and corroboration
fields the branch also carried are **not** ported — `main`'s `verdict.py`,
`channel_match.py` and `anomaly_assessments` own those, and the identity question is
recorded in `AGENTS.md`'s contradictions list instead.

**Tech Stack:** Python 3, FastAPI, Pydantic v2, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-21-port-verification-comparison-design.md`

**Branch:** work lands on `main` directly, matching the repo's recent history. **Nothing
is pushed** — `AGENTS.md` authorises committing and withholds pushing.

## Global Constraints

- The default test suite stays **fully offline**. Never call OpenRouter, Tavily, or any
  other external API — not in a probe, not in a smoke test. `backend/tests/conftest.py`
  enforces this; do not weaken the fixture.
- **`VERIFY_SEARCH_MODE` defaults to `fixed`** and ships off. Nothing in this plan
  changes what a verification does until someone sets the flag.
- **The flag off must not alter the call, not merely the queries.** In `fixed` mode the
  search is `runtime.get_search()(query)` — one argument. The scoped form
  `runtime.get_search()(query, include_domains=[...])` is reachable only with a scope.
- **`format_results` gains two optional parameters** — `entity_name: str = ""` and
  `labels: dict | None = None` — and is **byte-identical to `main`'s output when both
  are omitted**.
- **The model does not emit the level or the score.** `verdict.py` computes them. Do not
  reintroduce `_read_risk_level` / `_read_risk_score` into `verification_flow.py`, and do
  not add `risk_level` / `risk_score` to the verify schema.
- **`include_domains` is sent with `include_domains_mode: "prefer"`, never `restrict`.**
  There is no configured `INCLUDE_DOMAINS` and there will not be one.
- **A scope is only ever a domain that came back from an earlier search.** A domain the
  posting supplied is never scoped to.
- **`CONTACT_METHOD` is the only repeatable attribute key.** It accumulates with
  `"; "`. Every other key stays last-one-wins.
- **All three prompt copies are asserted in one test:** `backend/SYSTEM_PROMPT.md`,
  `prompts.SCAN_FORMAT_BLOCK`, `prompts.SCAN_FIELD_RULES`. They have drifted before.
- **A red test in this repo is a finding, not a condition.** If the suite fails, find
  out why before fixing it.
- **One logical change per commit**, with a body that carries the reason.
  `git commit`, never `git commit --amend` on a commit the developer wrote.
- **Committing is authorised. Pushing is not.**

## Review Focus

- **Separator drift.** The scan joins repeated `CONTACT_METHOD` lines with `"; "`; the
  planner splits on `";"` and `"|"`. If either side changes, channels silently vanish,
  no rule fires, and nothing errors. A posting with two channels is parsed as one.
- **Two channels, one of them free-mail.** The CHED shape: the employer's own
  `.gov.ph` address beside a free-mail one. The scan must write both, `printed_channels`
  must carry both, and the government rule must fire on the free-mail one.
- **A channel value that itself contains `;` or `|`.** `classify_signals` splits on both,
  so such a value becomes a phantom channel with a wrong domain.
- **`VERIFY_SEARCH_MODE` set to a typo** (`adapative`, `ADAPTIVE `, blank). It must
  degrade to `fixed` — not raise, and not spend adaptive credits.
- **Round 1 fails.** No follow-up is planned, `queries_failed` is 1, and the panel sees
  partial coverage rather than a clean success.
- **A posting with channels but no employer name.** The no-company early return must
  still carry `anomaly_assessments: []` and `rounds: []`, and the frontend must not
  throw on a missing key.

---

### Task 1: The scan writes every channel, and the type it claims

**Files:**
- Modify: `backend/app/services/lm_client.py`
- Modify: `backend/app/services/scanner/prompts.py`
- Modify: `backend/SYSTEM_PROMPT.md`
- Test: `backend/tests/test_anomaly_parsing.py`
- Test: `backend/tests/test_scan_prompt_file.py`

**Interfaces:**
- Produces: `lm_client._REPEATABLE_ATTRIBUTE_KEYS = frozenset({"CONTACT_METHOD"})`
- Produces: `lm_client._ATTRIBUTE_JOIN = "; "`
- Produces: `lm_client._ATTRIBUTE_KEYWORDS` gains `"JOB_TITLE"` and `"CLAIMED_TYPE"`
- Produces: `lm_client._SECTION_RE` matches `JOB[_\s]*TITLE` and `CLAIMED[_\s]*TYPE`
- Produces: `prompts.SCAN_FORMAT_BLOCK` and `prompts.SCAN_FIELD_RULES` carry the typed
  one-line-per-channel `CONTACT_METHOD` and the `CLAIMED_TYPE` line
- Consumes: nothing. This is the first task.

- [ ] **Step 1: Cherry-pick `2b34784` without committing**

```bash
git cherry-pick --no-commit 2b34784
```

Expected: six conflicts, and `git status` shows `UU` on `UNFINISHED-WORK.md`,
`backend/SYSTEM_PROMPT.md`, `backend/app/services/scanner/prompts.py`,
`backend/tests/test_scan_prompt_file.py`, `docs/architecture.md`, and
`docs/decisions/verification-findings.md`.

- [ ] **Step 2: Resolve `UNFINISHED-WORK.md` by keeping `main`'s**

```bash
git checkout --ours UNFINISHED-WORK.md && git add UNFINISHED-WORK.md
```

`main` deprecated this file and replaced it with the contradictions list in `AGENTS.md`.
The branch's edits to it are dropped.

- [ ] **Step 3: Resolve `backend/SYSTEM_PROMPT.md` by taking the branch's**

```bash
git checkout --theirs backend/SYSTEM_PROMPT.md && git add backend/SYSTEM_PROMPT.md
```

`main`'s copy is byte-identical to the merge base — `6c387cf` added 32 lines and
`ce6a1b3` removed the same 32 — so taking the branch's loses nothing.

- [ ] **Step 4: Resolve `backend/app/services/scanner/prompts.py` by taking the branch's**

```bash
git checkout --theirs backend/app/services/scanner/prompts.py && git add backend/app/services/scanner/prompts.py
```

`main` did not touch this file since the merge base. The only conflict is the
`CONTACT_METHOD` format line, and the branch's is the one being ported.

- [ ] **Step 5: Resolve `backend/tests/test_scan_prompt_file.py` by taking the branch's**

```bash
git checkout --theirs backend/tests/test_scan_prompt_file.py && git add backend/tests/test_scan_prompt_file.py
```

The conflict is a pure append of two new test functions; `main` added nothing there.

- [ ] **Step 6: Take the branch's `docs/architecture.md`**

```bash
git checkout --theirs docs/architecture.md && git add docs/architecture.md
```

The two paragraphs the branch adds are rewritten in Task 2, once the decision record
they point at exists.

- [ ] **Step 7: Drop the branch's decision record**

```bash
git rm --cached docs/decisions/verification-findings.md && rm docs/decisions/verification-findings.md
```

`main` has `docs/decisions/channel-match-severity.md` for the consumer side, and the
branch's record documents a design `main` replaced. A replacement is written in Task 2.
The file is **not** ported in any part.

- [ ] **Step 8: Read the ported parser change**

`backend/app/services/lm_client.py` must now contain, and the file must not contain
anything that contradicts it:

```python
_REPEATABLE_ATTRIBUTE_KEYS = frozenset({"CONTACT_METHOD"})
_ATTRIBUTE_JOIN = "; "
```

and inside `_parse_custom`, the attribute write is:

```python
if kw in _REPEATABLE_ATTRIBUTE_KEYS and kw in attributes:
    attributes[kw] = f"{attributes[kw]}{_ATTRIBUTE_JOIN}{rest}"
else:
    attributes[kw] = rest
```

- [ ] **Step 9: Run the parser and prompt tests**

```bash
cd backend && python -m pytest tests/test_anomaly_parsing.py tests/test_scan_prompt_file.py -q
```

Expected: PASS. `TestRepeatableAttributeKeys` and
`test_contact_method_is_a_typed_line_and_claimed_type_exists` are the two that must
exist and pass.

- [ ] **Step 10: Run the whole backend suite**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: PASS, and **more** tests than `main`'s 763 + 1 skipped. If a count went down,
a test was lost — find it before committing.

- [ ] **Step 11: Commit**

```bash
git add -A && git commit -m "feat(scan): one typed line per channel, and the claimed type" -m "The scan writes CONTACT_METHOD as one typed line per channel, and
CLAIMED_TYPE says whether the poster presents itself as a government
office, a private company, a recruitment agency, an individual, or
unclear.

The slot was singular, so a posting naming two ways to apply kept only
the last one, and the channel that mattered could not arrive by any
other route: a free email domain is forbidden from being an anomaly, so
recruitment.ched@outlook.com was not in the findings block either.
It existed only if written into CONTACT_METHOD, which could hold one.

The type is free signal, nothing has to be split on a separator, and a
repeat accumulates rather than overwrites - a plain attributes[key] =
value keeps only the last line, which is the original bug wearing a
different hat. CONTACT_METHOD is the only repeatable key: accumulating
every attribute would merge two LOCATION lines into one unparseable
value.

Ported from feat/verification-comparison (2b34784)."
```

- [ ] **Step 12: Verify the tree is clean**

```bash
git status --short && git ls-files | grep -E "verification-findings|UNFINISHED-WORK" 
```

Expected: `git status --short` is empty. The `grep` must return
`UNFINISHED-WORK.md` only — `docs/decisions/verification-findings.md` must not be
tracked.

---

### Task 2: The decision record for what the scan writes

**Files:**
- Create: `docs/decisions/scan-channel-enumeration.md`
- Modify: `docs/architecture.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: the `CONTACT_METHOD` / `CLAIMED_TYPE` / `JOB_TITLE` facts from Task 1
- Produces: `docs/decisions/scan-channel-enumeration.md`, referenced by `AGENTS.md`'s
  doc map and by `docs/architecture.md`
- Produces: an `AGENTS.md` contradictions entry (number 7) recording the open identity
  question

- [ ] **Step 1: Write `docs/decisions/scan-channel-enumeration.md`**

The record owns the **producer** side. It must state:

- What the scan writes: `CONTACT_METHOD` as one typed line per channel
  (`email | hrmo6@ched.gov.ph`), `CLAIMED_TYPE`
  (`government | private company | recruitment agency | individual | unclear`), and
  `JOB_TITLE`.
- Why the slot was singular and what that cost, in the CHED case: one channel was
  written and the other lost, and the lost one could not arrive by another route
  because a free email domain is forbidden from being an anomaly.
- The separator contract with the planner: the scan joins with `"; "`, the planner
  splits on `";"` and `"|"`. **The two must change together.**
- That `CLAIMED_TYPE` opens no category. `expected_categories` is unchanged;
  `CLAIMED_TYPE` reaches the planner as a signal.
- That the **consumer** side is `docs/decisions/channel-match-severity.md` — the rules,
  the `escalation` string, and the strong-channel floor live there, not here. This
  record states only what the scan writes and why.
- The open identity question, stated as open: the results show whether an employer
  with this name exists, not whether the poster is that employer.
  `channel_match.py` says it does not prove identity. If it is solved, it must be
  solved code-side, as a fact the model reports and code prices — not as a
  model-written verdict.

The record must **not** claim any of the following, because none of them is true on
`main`:

- that the findings reach the verifier "as facts and not as severities"
  (`_findings_block` sends `[{severity}] {flag}`)
- that the model owns the level or the score (`verdict.py` computes them)
- that `name_comparison` or `results_entity` exist
- that `findingCorroborations` exists (`anomaly_assessments` is main's equivalent)

- [ ] **Step 2: Fix the `docs/architecture.md` paragraph the branch added**

The branch's first added paragraph claims the findings go in "as facts and **not** as
severities". That is false on `main` — `_findings_block` sends
`[{severity}] {flag}`. Rewrite the paragraph to say what `main` actually sends, and
point at `docs/decisions/scan-channel-enumeration.md` instead of
`docs/decisions/verification-findings.md`.

The second added paragraph (the one about `CONTACT_METHOD` holding every channel, and
`CLAIMED_TYPE` being the other half) is accurate. Keep it and repoint its decision
record reference.

- [ ] **Step 3: Add the `AGENTS.md` doc map row**

Insert into the documentation map table, next to the `verification-design.md` row:

```
| `docs/decisions/scan-channel-enumeration.md` | What the scan writes: repeatable `CONTACT_METHOD`, `CLAIMED_TYPE`, the separator contract with the planner |
```

- [ ] **Step 4: Add the identity question to `AGENTS.md`'s contradictions list**

Append as item 7, after the `escalation` entry:

```
7. **The identity question is open.** The results show whether an employer with this
   name exists, not whether the person who posted this is that employer. A scam that
   borrows a real employer's name and asks for nothing unusual is caught by neither
   `channel_match.py` nor the independent-finding rule, because both compare the
   posting's channels against the employer's own channels and find them equal. The
   branch solved it with a model-written `name_comparison`; that is a model-owned
   verdict, which is the shape `channel_match.py` exists to remove. **Needs a
   decision**, and if it is decided it must be decided code-side.
```

- [ ] **Step 5: Check no document points at a file that does not exist**

```bash
git grep -n "verification-findings" -- "*.md"
```

Expected: no output, or only a line that explicitly says the file was retired.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "docs: the scan's channel enumeration gets a record, and the identity question is listed as open" -m "The branch's verification-findings.md documented a design main has
replaced - a model-owned level, model-owned identity fields, and a
model-owned corroboration list. Copying it would put a second 'in force'
record on a subject main already has one for.

The new record owns the producer side only: what the scan writes, why the
singular slot was the bug, and the separator contract with the planner.
The consumer side stays in channel-match-severity.md.

The identity question is not solved and is recorded as unsolved, with the
note that solving it code-side is the requirement."
```

---

### Task 3: The adaptive search planner

**Files:**
- Create: `backend/app/services/scanner/search_planner.py`
- Create: `backend/tests/test_search_planner.py`
- Create: `backend/tests/test_adaptive_search.py`
- Create: `backend/scripts/mutation_check.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/app/services/search.py`
- Modify: `backend/app/services/scanner/verification_prompt.py`
- Modify: `backend/app/services/lm_client.py`
- Modify: `backend/tests/test_multi_query.py`
- Modify: `backend/tests/test_anomaly_parsing.py`
- Modify: `backend/tests/test_scan_prompt_file.py`

**Interfaces:**
- Produces: `search_planner.MAX_FOLLOWUPS = 2`
- Produces: `search_planner.Signals` — frozen dataclass, fields `printed_name`,
  `can_search`, `claimed_government`, `channels`, `main_domain`, `domains_disagree`,
  `has_location`, `location`, `registration_claim`, `has_registration_claim`,
  `job_title`
- Produces: `search_planner.Entity` — frozen dataclass, fields `name`, `domain`,
  `names_differ`, `shares_identifier`
- Produces: `search_planner.PlannedQuery` — frozen dataclass, fields `purpose`,
  `text`, `include_domains: tuple = ()`, method `as_wire() -> dict`
- Produces: `search_planner.LabelledResult` — frozen dataclass, fields `url`, `query`,
  `describes_entity`
- Produces: `search_planner.classify_signals(company_name: str, attributes: dict) -> Signals`
- Produces: `search_planner.resolve_entity(signals: Signals, results: list) -> Entity`
- Produces: `search_planner.plan_followups(signals: Signals, entity: Entity, round1_ok: bool, model_queries: list | None = None) -> list[PlannedQuery]`
- Produces: `search_planner.label_results(results: list, entity: Entity, query_of: dict) -> dict`
- Produces: `search_planner.search_query_is_safe(query: str) -> bool`
- Produces: `search_planner.entity_domain_of(domain: str) -> str`
- Produces: `search.registrable_domain(raw: str) -> str`
- Produces: `search.search(query: str, max_results: int | None = None, include_domains: list | None = None) -> SearchOutcome`
- Produces: `Settings.verify_search_mode: str = "fixed"` and
  `Settings.resolve_search_mode() -> str`
- Produces: `verification_prompt.format_results(results, company, ok, error="", entity_name="", labels=None) -> str`
- Consumes: Task 1's `CONTACT_METHOD` / `CLAIMED_TYPE` format — `classify_signals`
  splits `attrs["CONTACT_METHOD"]` on `";"` and `"|"`, and reads `attrs["CLAIMED_TYPE"]`
  and `attrs["JOB_TITLE"]`

- [ ] **Step 1: Cherry-pick `8f71e25` without committing**

```bash
git cherry-pick --no-commit 8f71e25
```

Expected: **two** conflicts only — `UNFINISHED-WORK.md` and
`backend/app/services/scanner/verification_flow.py`. If there are more, the cherry-pick
was not applied on top of Task 1's commit; stop and rebase onto `main` first.

- [ ] **Step 2: Resolve `UNFINISHED-WORK.md` by keeping `main`'s**

```bash
git checkout --ours UNFINISHED-WORK.md && git add UNFINISHED-WORK.md
```

- [ ] **Step 3: Resolve `backend/app/services/scanner/verification_flow.py`**

The conflict is **one hunk, the import block**. Keep `main`'s imports and add the
planner's — the resulting block is exactly:

```python
from .channel_match import (
    apply_channel_rules,
    assess_channel_match,
    has_channel_content,
    read_channel_facts,
    with_official_only_if_retrieved,
)
from .dependencies import runtime
from .search_planner import classify_signals, label_results, plan_followups, resolve_entity
from .verdict import code_verdict
from .verification_parser import VerificationParseError
from .verification_prompt import clean_verdict_reason, expected_categories
```

**Do not** take the branch's side of this hunk. The branch's side imports
`_Identity`, `_read_corroborations`, `_read_name_comparison`, `_read_results_entity`
and `keep_sent_corroborations` — the model-owned identity and corroboration fields
that are **not** being ported. Those functions do not exist on `main`, and importing
them breaks the module.

The rest of `verification_flow.py` merges cleanly: `_search`, `_issue`, `_query_rows`,
the round-based issuing and the `rounds` wiring. Task 4 completes and verifies it.

- [ ] **Step 4: Confirm the planner's public surface**

`backend/app/services/scanner/search_planner.py` must export, exactly:

```python
MAX_FOLLOWUPS = 2
def entity_domain_of(domain: str) -> str
def search_query_is_safe(query: str) -> bool
def classify_signals(company_name: str, attributes: dict) -> Signals
def resolve_entity(signals: Signals, results: list) -> Entity
def plan_followups(signals, entity, round1_ok, model_queries=None) -> list
def label_results(results: list, entity: Entity, query_of: dict) -> dict
```

with the four frozen dataclasses `Signals`, `Entity`, `PlannedQuery`, `LabelledResult`.

- [ ] **Step 5: Confirm the config and the setting**

`backend/app/config.py` must contain:

```python
_VALID_SEARCH_MODES = frozenset({"fixed", "adaptive"})
```

```python
verify_search_mode: str = "fixed"
```

```python
def resolve_search_mode(self) -> str:
    value = (self.verify_search_mode or "").strip().lower()
    return value if value in _VALID_SEARCH_MODES else "fixed"
```

The default is `fixed`. An unrecognised value degrades to `fixed` — a typo costs the
new behaviour, not the endpoint.

- [ ] **Step 6: Confirm `search()`'s scope parameter**

`backend/app/services/search.py` must have the signature

```python
def search(query: str, max_results: int | None = None, include_domains: list | None = None) -> SearchOutcome:
```

with `include_domains` **last**, so `search(query)` and `search(query, None)` are
unchanged for every existing caller. The request body must send
`body["include_domains_mode"] = "prefer"` whenever a scope is present, and must never
send `restrict`.

- [ ] **Step 7: Confirm `format_results` is additive and byte-identical when unused**

`backend/app/services/scanner/verification_prompt.py`:

```python
def format_results(
    results: list,
    company: str,
    ok: bool,
    error: str = "",
    entity_name: str = "",
    labels: dict | None = None,
) -> str:
```

`test_multi_query.py` already asserts that omitting the two new arguments produces
output identical to `main`'s. That assertion is the reason the flag-off claim is
checkable, and it must pass.

- [ ] **Step 8: Run the planner's tests**

```bash
cd backend && python -m pytest tests/test_search_planner.py tests/test_adaptive_search.py tests/test_multi_query.py -q
```

Expected: PASS.

- [ ] **Step 9: Run the whole backend suite**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: PASS, and the count is **higher** than Task 1's. `main`'s 763 + 1 skipped is
the floor; the prototype reached 847 + 1 skipped.

- [ ] **Step 10: Run the mutation check**

```bash
cd backend && python scripts/mutation_check.py
```

Expected: every mutation is caught. A surviving mutation is a finding, not a condition
— `docs/gotchas.md` records the two that survived the first pass and what the fix was
(a property test over a matrix, or a fixture that fires more rows than the bound
permits — not a stronger assertion on the same one case).

- [ ] **Step 11: Commit**

```bash
git add -A && git commit -m "feat(search): an adaptive verification search, behind VERIFY_SEARCH_MODE=fixed" -m "Round 0 classifies the scan's own fields, Round 1 spends the
employer-name query unchanged, and a planner chooses up to two
follow-ups from what Round 1 actually returned. Same 3-credit ceiling,
typical cost 1.

Shipped OFF. Nothing here has been shown to improve a verdict, and the
fixtures that would decide it have not been run.

Adding queries does not remove noise. Every merged result now carries
the query that found it and whether it describes the organisation the
results describe, so a page about the wrong body reads as wrong-entity
rather than as absence. Nothing is dropped - dropping evidence is how the
entity heuristic goes wrong in the first place.

include_domains is not a narrow exception. Tavily's include_domains_mode
'prefer' boosts rather than filters, so a scoped follow-up is the same
kind of lever as country, and it is sent with 'prefer' and never
'restrict'. A scope is only ever a domain a previous search returned,
never one the poster supplied.

Ported from feat/verification-comparison (8f71e25)."
```

---

### Task 4: The flow issues the rounds

**Files:**
- Modify: `backend/app/services/scanner/verification_flow.py`
- Test: `backend/tests/test_adaptive_search.py`
- Test: `backend/tests/test_verify.py`

**Interfaces:**
- Consumes: Task 3's `classify_signals`, `resolve_entity`, `plan_followups`,
  `label_results`, and `Settings.resolve_search_mode()`
- Consumes: Task 3's `format_results(results, company, ok, error, entity_name, labels)`
- Produces: `verification_flow._search(query: str, scope) -> object`
- Produces: `verification_flow._issue(queries: list) -> tuple[list, list, list, list]`
- Produces: `verification_flow._query_rows(texts: list) -> list`
- Produces: `"rounds": list[dict]` on **both** verify result events

- [ ] **Step 1: Read the merged flow and check the fixed path**

In `verification_event_stream`, the anchor query is issued first, unscoped:

```python
for query in company_queries:
    yield runtime.get_sse({"type": "search", "query": query, "round": 1})
first_collected, first_failures, first_raw, first_per_query = await _issue(
    _query_rows(company_queries)
)
```

`_search` must call `runtime.get_search()(query)` with **one argument** when `scope` is
falsy. A collaborator substituted by a test is entitled to see the call unchanged.

- [ ] **Step 2: Check the adaptive path**

When `settings.resolve_search_mode() == "adaptive"`, the flow must:

1. call `classify_signals(company, getattr(req, "attributes", None) or {})`
2. call `resolve_entity(signals, [r for batch in first_collected for r in batch])`
3. call `plan_followups(signals, entity, round1_ok=not first_failures, model_queries=model_queries)`
4. issue the planned queries with their scopes
5. call `label_results(everything, entity, query_of)` and pass `entity_name` and
   `labels` to `format_results`

When the mode is `fixed`, the model-proposed queries are issued unscoped, with no round
between them, and `entity_name` stays `""` and `labels` stays `None`.

- [ ] **Step 3: Add `rounds` to the no-company early return**

The early return currently emits `"anomaly_assessments": []` and `"scheme_queries": []`
but no `rounds`. Add:

```python
"rounds": [],
```

so both result events carry the same keys. A client reading `rounds` must not have to
handle its absence on exactly the response that most obviously searched nothing.

- [ ] **Step 4: Write the failing test for the shape**

In `backend/tests/test_adaptive_search.py`, add a test that posts a verify request with
no company name and asserts the result event carries `rounds == []` and
`anomaly_assessments == []`.

```python
def test_the_no_company_result_carries_the_same_keys():
    ...
    assert data["rounds"] == []
    assert data["anomaly_assessments"] == []
```

- [ ] **Step 5: Run it to verify it fails**

```bash
cd backend && python -m pytest tests/test_adaptive_search.py -q -k no_company
```

Expected: FAIL — `KeyError: 'rounds'` or an assertion failure on the missing key.

- [ ] **Step 6: Implement Step 3's change**

Add `"rounds": []` to the no-company result payload.

- [ ] **Step 7: Run it to verify it passes**

```bash
cd backend && python -m pytest tests/test_adaptive_search.py -q -k no_company
```

Expected: PASS.

- [ ] **Step 8: Fix the stale comment about query families**

`verification_flow.py` says *"Two query families, one flat result set, one model call"*
and *"Two of them because one cannot serve every category"*. `build_queries()` returns
**one** query — `f"{name} company or employer"` — so the second query never existed.
Rewrite the comment to describe one anchor query plus the model-proposed ones, and
state the credit ceiling: one anchor plus up to `MAX_SEARCH_QUERIES = 2`, so three
credits at `basic` depth.

- [ ] **Step 9: Run the whole backend suite**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add -A && git commit -m "fix(verify): the no-company result carries the same keys as the other one" -m "The rounds key is on the wire so a reader can tell a deliberate
silence from a question nobody thought to ask. Leaving it off the
no-company path would mean a client reading it has to handle its
absence on exactly the response that most obviously searched nothing.

Also corrects a comment that claimed build_queries issues two queries. It
issues one; the second never existed. The ceiling is one anchor plus up
to two model-proposed, so three credits at basic depth."
```

---

### Task 5: The search record, the spec, and the repo map

**Files:**
- Modify: `docs/decisions/search-retrieval.md`
- Modify: `docs/gotchas.md`
- Modify: `AGENTS.md`
- Create: `docs/superpowers/specs/2026-10-18-adaptive-verification-search.md`

**Interfaces:**
- Consumes: Task 3's planner and Task 4's flow
- Produces: `docs/decisions/search-retrieval.md` owns the adaptive search; the
  `AGENTS.md` doc map points at it
- Produces: an `AGENTS.md` contradictions entry (number 8) for the backend-only
  `rounds` field

- [ ] **Step 1: Port `docs/decisions/search-retrieval.md`**

The cherry-pick in Task 3 already brought this file's changes. Read them and confirm
they describe the shipped behaviour: the two modes, the credit ceiling, the
`prefer`-not-`restrict` rule, and that a scope is only ever a domain from an earlier
search. If any sentence describes a model-owned verdict, it does not belong here.

- [ ] **Step 2: Port `docs/gotchas.md`**

The cherry-pick brought the mutation-check note. Read it against the current
`docs/gotchas.md` — the note about a surviving mutation being a fixture-limited test
is about `backend/scripts/mutation_check.py`, which now exists. Keep it.

- [ ] **Step 3: Port the adaptive spec**

`docs/superpowers/specs/2026-10-18-adaptive-verification-search.md` came in with the
cherry-pick. It is the design the planner implements, and it is worth keeping as the
spec the code answers to. Confirm its "shipped off" statement still matches the code.

- [ ] **Step 4: Add the `AGENTS.md` command line**

In the Commands block, under the backend commands:

```
python scripts/mutation_check.py   # breaks each search control, asserts a test catches it
```

- [ ] **Step 5: Add the `AGENTS.md` contradictions entry for `rounds`**

Append as item 8:

```
8. **`rounds` reaches the wire and nothing reads it.** The verify result carries what
   each query was for and what it returned, so a reader can tell a deliberate silence
   from a question nobody thought to ask. The frontend does not declare it. It is
   backend-only for now, and the day the panel explains what was looked up and why,
   this is the field it should read.
```

- [ ] **Step 6: Check the doc map is complete and accurate**

`AGENTS.md`'s documentation map must have exactly one row per fact. Confirm:

- `docs/decisions/search-retrieval.md` — row present, and its "Holds" text now mentions
  the adaptive mode and the two modes' difference.
- `docs/decisions/scan-channel-enumeration.md` — row present from Task 2.
- `docs/decisions/channel-match-severity.md` — row present and **not** duplicated.
- No row points at `docs/decisions/verification-findings.md`.

- [ ] **Step 7: Check the whole repo for a dangling reference**

```bash
git grep -n "verification-findings\|2026-10-18-adaptive-verification-search" -- "*.md"
```

Expected: every hit is a link to a file that exists.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "docs: the adaptive search gets a record, and the repo map points at it" -m "search-retrieval.md now describes the two modes, the credit ceiling, and
that a scope is only ever a domain from an earlier search. The adaptive
spec travels with the code it specifies.

rounds is backend-only for now, so it is listed in the contradictions
rather than left as an unread field with no home."
```

---

### Task 6: Retire the branch

**Files:**
- No file changes. This task is a branch deletion and a verification.

**Interfaces:**
- Consumes: Tasks 1-5, all landed on `main`
- Produces: `feat/verification-comparison` deleted

- [ ] **Step 1: Confirm the port is complete against the branch**

```bash
git log --oneline main ^feat/verification-comparison
git diff --stat main feat/verification-comparison
```

Expected: the diff shows **only** what was deliberately not ported — the model-owned
identity and corroboration code, `docs/decisions/verification-findings.md`, the
`.planning/` directory, the `UNFINISHED-WORK.md` and `SCORING-SOURCES.md` churn, the
`jobposts/*.html` dumps, and the branch's panel work. Read the diff before deleting.

- [ ] **Step 2: Confirm the tests and the extension build**

```bash
cd backend && python -m pytest tests/ -q
cd .. && npm run compile && npm test -- --run
```

Expected: backend PASS; `npm run compile` clean; frontend tests PASS. The port touches
no frontend file, so the frontend suite is a regression check, not a deliverable.

- [ ] **Step 3: Confirm the tree is clean and nothing was pushed**

```bash
git status --short
git log --oneline origin/main..main
```

Expected: `git status --short` is empty. The second command lists the port's commits
and **none of them is pushed** — `origin/main` has not moved.

- [ ] **Step 4: Delete the branch**

```bash
git branch -d feat/verification-comparison
```

Use `-d`, not `-D`. Git will refuse if the branch is not merged into `main` — and
**that refusal is the finding**: it means something from the branch is not on `main`
yet, and Step 1's diff must be read again to find out what.

- [ ] **Step 5: Remove the prototype worktree**

```bash
git worktree remove "C:\Users\Guest2\AppData\Local\Temp\opencode\cp-test"
```

If it refuses, the worktree has uncommitted changes; read them first, then
`git worktree remove --force` only if they are the resolved prototype and nothing
else.

- [ ] **Step 6: Report**

Report to the developer:

- the commits landed on `main`, and that nothing was pushed
- the test count before and after
- the two things deliberately not ported, and where each now lives
- the open identity question, and that it is recorded in `AGENTS.md`'s contradictions
  list rather than solved
- that `VERIFY_SEARCH_MODE` ships at `fixed`, and what flipping it to `adaptive` would
  change

---

## Self-Review

**1. Spec coverage.** Every section of the spec maps to a task: §2 (what is in the
branch) → Tasks 1 and 3, with the "not ported" list → Task 6 Step 1; §3 (the
dependency that fixes the order) → Task 1 Step 1 and Task 3 Step 1; §4 (the record is
rewritten) → Task 2; §5 (the identity question stays open) → Task 2 Step 4; §6 (the
wire) → Task 4 Steps 3-7; §7 (what ships off) → Task 3 Steps 5 and 7, and the Global
Constraints; §8 (the scope) → Task 3 Step 6; §9 (what is not ported) → Task 6 Step 1;
§10 (the end state) → Task 6.

**2. Step scan.** Every step names one action with a checkable result. Task 1 Steps
2-7 are each a single `git checkout` or `git rm`. Task 3 Steps 4-7 name the exact
signatures and constants to confirm, not bodies to write. No step says "handle edge
cases" or "add appropriate tests".

**3. Type consistency.** `plan_followups(signals, entity, round1_ok, model_queries=None)`
is used in Task 3's Interfaces and Task 4's Step 2 with the same argument names and
order. `label_results(results, entity, query_of)` is consistent in both. `rounds` is
produced in Task 4 Step 3 and consumed in Task 5 Step 5 — the same key. `Signals`,
`Entity`, `PlannedQuery`, `LabelledResult` field lists appear once, in Task 3's
Interfaces, and are not restated with different field sets.

**4. Review Focus.** Each of the six lines has a test:

- separator drift → Task 1 Step 9 (`TestRepeatableAttributeKeys`) and Task 3 Step 8
  (`test_search_planner.py` splits the joined value)
- two channels, one free-mail → Task 1 Step 9, and `test_adaptive_search.py`
- a channel value containing `;` or `|` → Task 3 Step 8
- `VERIFY_SEARCH_MODE` typo → Task 3 Step 8 (`test_search_planner.py` covers
  `resolve_search_mode`)
- Round 1 failure → Task 3 Step 8
- channels but no employer → Task 4 Steps 4-7, written as an explicit failing test

**5. Proportion.** The plan is six tasks of 6-12 steps. The code it describes is
2,912 inserted lines. The plan does not reproduce the planner, the parser change, or
the test bodies — it names the signatures, the constants, the conflicts, and the
commands. The one place a body appears is the import block in Task 3 Step 3, because
that block is the conflict and choosing the wrong side of it breaks the module in a
way a prose instruction would not prevent.

# Adaptive verification search

Date: 2026-10-18
Status: design approved, not built
Source: `jobposts/2026-10-18-adaptive-verification-search.md` (proposal, untracked)
Builds on: `docs/decisions/verification-findings.md`, `docs/decisions/search-retrieval.md`

## Amendments to the proposal

Three changes, each forced by the live run recorded in `UNFINISHED-WORK.md`. The
proposal's reasoning is kept; only these three are different.

### 1. Row 1 fires on `names_differ` alone

The proposal required `names_differ AND shares_identifier`, where
`shares_identifier` is *"the posting's LOCATION appears in a result that describes
the entity."*

**That trigger does not fire on the case the proposal was written for.** The live
run's Round 1 results for the CHED flyer were:

- `Higher Learning Commission` (a US accreditor)
- `WPU-STUDENT-HANDBOOK.pdf`
- `Productivity in Higher Education`

No Iloilo, no CHED, no Magsaysay Village. So `shares_identifier` is false, row 1
never fires, no domain query is issued, and the verifier receives the same results
it already had. The whole planner would run and the verdict would not move.

The proposal's own fixture (§7 test 1, "address shared") assumes the one thing
that is false precisely when the design is needed: the failure mode is that Round 1
found nothing relevant, so there is nothing to share an address with.

The ceiling is already 3 and the typical cost is 1, so a second credit whenever the
name does not match is affordable. And it is the impersonation question exactly:
**does this domain belong to the organisation the results describe?**

`shares_identifier` is kept — as an *additional* row, not a precondition. It earns a
narrower, more specific follow-up when the address does appear.

### 2. Results are labelled against `entity`, not just against their query

The resolver computes `entity` and then merges every result anyway, so US
accreditors stay in the list and the model reports *"none of these channels appear
in any search result"* — which is the observed bug, stated verbatim. Adding queries
does not remove noise.

Every merged result therefore carries whether it **describes `entity`**. Not
dropped — dropping evidence is how the entity heuristic goes wrong, and a result
that turns out to matter cannot be recovered once discarded — but labelled, so the
model can discount a page about the wrong body instead of reading its silence as
absence.

### 3. Model-proposed queries become filler, not a retirement

The proposal retires them. Retiring them outright removes the only path for a
question the decision table did not anticipate — and one table row is missing
already: **`Similar Offers` has no entry**, while `SYSTEM_PROMPT.md` deliberately
spends a query on it (*"the same work posted elsewhere… this is the only way to
find other postings of the same offer"*). Retiring without a row makes that
category structurally unanswerable.

So: planner rows first, model queries as **filler only when the planner leaves
slots empty**. The proposal's own transitional suggestion, promoted to the default.

### 4. `include_domains` is not an exception — `prefer` is not a filter

Checked against Tavily's `POST /search` reference rather than assumed, and the
proposal's framing was wrong.

The proposal treated a scoped follow-up as a **narrow exception** to the standing
rule that `include_domains` stays unset, and the design doc for that rule
(`docs/decisions/search-retrieval.md`) records why the rule exists: `include_domains`
restricts results to the listed domains, which would discard precisely the JobStreet,
Indeed PH and PESO pages the `country` boost exists to surface.

Tavily's `include_domains` defaults to `include_domains_mode: "restrict"` — that
filter. It also accepts `"prefer"`, which **boosts** the listed domains and still
searches the rest of the web. That is the same kind of lever as `country`, so both
sit on one request and neither excludes anything.

So it is not an exception at all. Two changes follow:

- **`search()` gained `include_domains`, always sent as `prefer`.** There is still no
  configured `INCLUDE_DOMAINS` and still no global scope; the rule that
  `docs/decisions/search-retrieval.md` states stands unchanged. Only the adaptive
  planner passes one, and only ever a domain **a previous search returned** — which is
  what distinguishes it from the whitelist the original rule was defending against. The
  system learned the domain; nobody predicted it.
- **The validation is stricter than for `exclude_domains`.** `_normalise_domain` cuts
  `ched.gov.ph/careers` down to `ched.gov.ph`, which is right for an exclusion and wrong
  for a scope: silently widening a scope is the wrong direction to fail. Scoped values
  are validated before they are reduced, so a path or a wildcard is **dropped** and the
  query runs unscoped.

### Still open from the proposal

- **Test 9, the franchise case.** A franchisee running its own domain triggers
  `names_differ`, so this planner will spend a credit on it. Decided behaviour is
  still owed; recording the behaviour is not enough.
- **`include_domains` with the country boost.** Unverified against Tavily's docs.
  Checked before build.

## Problem

Verification fires a fixed set of queries once, before anything is known: one on the
employer name, plus up to two the scan model proposed from the posting alone.

Two things follow.

**The follow-up that matters depends on what the first search returned, and a fixed
set cannot react.** When results describe an organisation whose name differs from
the printed name, the useful next questions are different ones — what exists for
the poster's own domain, is this job on the organisation's own site. Today those
are never asked.

**Credits are spent without a stated purpose.** Model-proposed queries can duplicate
the anchor query or ask about details that decide nothing.

Observed, on the CHED flyer: the anchor query is literally
`"Commission for High Learning company or employer"`, and every entity-level check
comes back yellow because the results describe US accreditors.

## Goals

- Same credit ceiling as today (3 per verification). Typical cost falls to 1.
- Query planning is **code, not a model**, so it is deterministic and testable
  offline.
- Every planned query has one stated purpose.
- The "no conclusion words in a query" rule is enforced in code, not only in prompt
  text.

## Non-goals

- Domain age, certificate history, direct page fetching. Round 0 leaves hooks.
- **Changing the verdict logic.** This changes what evidence is gathered. The
  resolver picks questions; the verify prompt makes the call and nothing else does.

## Design

```
Round 0  free      classify facts from the scan, no network
Round 1  1 credit  anchor query on the printed employer name (unchanged)
Resolve  free      derive entity name and domain from Round 1 results, no network
Round 2  0-2       follow-up queries chosen by a decision table, in parallel
Merge    free      dedupe, label each result with its query and whether it describes entity
One AI call        verify prompt
```

### Round 0 — signals (deterministic, free)

From the scan fields:

- `printed_name`, normalised (case, spacing, punctuation, legal suffix removed)
- `claimed_government` — true when `CLAIMED_TYPE` is `government`
- for each channel: a `domain_class` of `free_email`, `job_board`, `social`,
  `gov_ph`, or `other`
- `domains_disagree` — more than one non-free domain, or a `gov_ph` domain beside
  a non-`gov_ph` one
- `deadline_passed`, `has_registration_claim`, `has_location`
- `job_title` — **new scan field**, see Dependencies

### Round 1 (1 credit)

Unchanged: `"<company> company or employer"`, verbatim name, country boost,
configured depth and exclude list. A nameless posting still runs no search.

### Resolve (deterministic, free)

From Round 1's results:

- `name` — the organisation the top results use, taken from result titles
- `domain` — registrable domain of the best-ranked result not on an aggregator
  denylist (job boards, social platforms, news, directories). For a government
  claim, prefer a `.gov.ph` domain
- `names_differ` — token overlap between the normalised printed name and
  `entity.name` below a threshold
- `shares_identifier` — the posting's `LOCATION` appears in a result describing
  the entity

**These choose queries. They never set a status.** Every value is a heuristic for
spending a credit, and the verify prompt remains the only thing that decides
anything.

### Round 2 — the decision table (0 to 2 credits, first matching rows in order)

| # | Trigger | Query | Purpose |
|---|---|---|---|
| 1 | `names_differ` | the poster's main non-free channel domain, verbatim | Does anything exist for the poster's own domain, and does it belong to the entity the results describe |
| 2 | `names_differ` and `shares_identifier` and `entity.domain` known | `<job_title> <entity.name>` with `include_domains=[entity.domain]` | Is this job on the entity's own site, and with which contact details |
| 3 | Round 1 `ok` with no results | `<printed name> <location>`, or `REGISTERED_AS` verbatim if present | Find a footprint another way |
| 4 | Round 1 returned several unrelated entities | `<printed name> <location>` | Disambiguate |
| 5 | `has_registration_claim`, not yet covered | `<registration verbatim> <printed name>` | Test the claim itself |
| 6 | none of the above, and a slot is free, and `search_queries` were sent | each model query, verbatim | Questions the planner did not anticipate |
| 7 | none of the above | none | Save credits |

Rows run in order and stop at the cap. **Row 1 is the one the live run needs** and
is deliberately first.

### Merge and labelling

Flat list, deduped on canonical URL. Each result carries:

- the literal query text that retrieved it
- **whether it describes `entity`** — a boolean, and nothing else

No category headings, no purposes, no annotations about what a result is. The
planner knows the purpose; the model needs to know whether a page is about the
organisation being verified. A result returned for a query is not evidence that the
entity is the one named.

### Model-proposed queries

Filler for row 6. Used only when the planner leaves slots empty, so a credit is
never spent on a duplicate of the anchor query when the planner had better uses.

## Cost

| Case | Credits |
|---|---|
| No trigger | 1 |
| `names_differ` only | 2 |
| `names_differ` + entity domain | 3 |
| Ceiling | 3 |

`advanced` depth doubles each request as it does today.

## Failure semantics

- `SearchOutcome.ok` and `.results` stay independent. `ok=True` with no results is
  a trigger for a follow-up; `ok=False` is a stop.
- **If Round 1 fails, no follow-ups are planned and `search_ok: false` is reported.**
  Credits are never spent against a provider that just failed.
- A Round 2 failure reports `search_partial` with pair-style errors.
- A `rounds` list goes on the response: purpose, query text, `ok`, result count.
  This replaces `model_queries`, which is currently emitted and read by nobody.

## Safety

- Queries are built only from extracted fields. Control characters stripped, each
  query length capped.
- **Banned-term check in code** — `scam`, `fraud`, `fraudulent`, `fake`,
  `suspicious`, `legitimate`. A query that fails is dropped. This moves the rule
  from prompt text to a control. Word-bounded, not substring: `Scamander Foods` is a
  company, and a substring check would drop a legitimate query about it.
- `include_domains` is set only on a Round 2 query, only to one validated
  registrable domain **taken from results, never from posting text**, and always in
  `prefer` mode so it boosts rather than filters. See amendment 4.
- Result text stays untrusted data.

## Rollout

1. `VERIFY_SEARCH_MODE=fixed|adaptive`, default **`fixed`**.
2. Flag off reproduces today's behaviour exactly — asserted by test.
3. Run the fixtures in both modes against saved model outputs. Compare verdicts and
   credits.
4. Switch the default only when adaptive is at least as good on every fixture and
   within the ceiling.
5. Record three decisions: adaptive search under a 3-credit ceiling, the scoped
   `include_domains` exception, and model queries as filler.

## Dependencies

- The scan fields in `SYSTEM_PROMPT.proposed.md`: `CLAIMED_TYPE` (landed),
  repeated typed `CONTACT_METHOD` (landed), `LOCATION` (exists), `REGISTERED_AS`
  (exists).
- **`JOB_TITLE` — does not exist yet.** Row 2 needs the position as printed. Without
  it the row falls back to `<entity.name> hiring` and its purpose is weaker.

## Tests

All offline. The planner and resolver are pure functions of the scan facts and
Round 1's results.

1. CHED flyer: government claim, names differ, **no shared address**. Expect the
   row-1 domain query. *This is the regression guard — it is the case the live run
   produced and the proposal's own fixture got wrong.*
2. CHED flyer with the address also present in results: row 1 and row 2.
3. Small private employer, Gmail, no trigger. Expect no follow-up, 1 credit.
4. Round 1 `ok=False`. Expect no follow-ups, `search_ok: false`.
5. Round 1 `ok=True`, no results. Expect the row-3 follow-up.
6. Nameless posting. Expect no search.
7. Banned word in a planned query. Expect it dropped.
8. Property: anchor plus follow-ups never exceed 3.
9. `include_domains` appears only on a Round 2 query and only with a domain taken
   from results.
10. Franchise with its own domain: record the decided behaviour.
11. Flag off reproduces today's query set exactly.
12. Every merged result carries its query text and its `describes_entity` flag.
13. Mutation-check each in both directions. Use function `side_effect` mocks,
    never a plain list.

## Risks

- The entity-domain heuristic can pick an aggregator. Contained: a wrong domain
  produces a wrong scoped query, not a wrong verdict.
- Sequential rounds add one round trip of latency. **Round 2 runs in parallel.**
- **Nothing here is shown to improve accuracy yet.** The fixtures decide, and the
  live run has not been repeated with this design.
- Row 1 fires on `names_differ`, which a franchise or a branch with its own domain
  produces. That is a real false-positive cost and it is accepted, because the
  ceiling is already 3 and typical cost is 1.

## Decisions taken

| Decision | Default | Why |
|---|---|---|
| Retire model-proposed queries | **No — filler only** | A planner table cannot anticipate every question, and `Similar Offers` has no row |
| Scoped `include_domains` on follow-ups | Yes, sent as `prefer` | Not an exception — `prefer` boosts, and the domain came from a previous search rather than from prediction |
| Credit ceiling | Keep 3 | Typical cost 1 |
| Row 1 trigger | `names_differ` alone | The address is absent precisely when it is needed |
| Keep the channel-domain query | Yes | It is the only query that tests the poster's own domain |

---

## Built

Status as of the first commit of this work.

| Piece | Where | Tests |
|---|---|---|
| Round 0 signals | `search_planner.classify_signals` | `test_search_planner.py::TestSignals` |
| Resolve | `search_planner.resolve_entity` | `TestResolve` |
| Decision table | `search_planner._planner_rows` | `TestPlanner` |
| Ceiling, banned terms, sanitising | `search_planner.plan_followups` | `TestPlanner`, `TestSafety` |
| Labelling | `search_planner.label_results` | `TestLabelling` |
| The flag | `config.Settings.resolve_search_mode` | `test_adaptive_search.py::TestTheFlag` |
| Rounds and the branch | `verification_flow._issue` | `TestFixedModeIsUnchanged`, `TestAdaptiveMode`, `TestRoundsOnTheWire` |
| The scope | `search.search`, `search._scoped_domains` | `test_multi_query.py::TestTheDomainScopeIsAPreferenceNotAFilter` |
| `JOB_TITLE`, row 2's subject | `SYSTEM_PROMPT.md`, `prompts.py`, `lm_client` | `test_scan_prompt_file.py`, `test_anomaly_parsing.py` |
| `rounds` on the wire | `verification_flow` | `TestRoundsOnTheWire` |

**`rounds` is not read by the panel.** It is telemetry alongside `queries_issued` and
`search_count`, and it is the record of what each credit was spent on — but nothing
renders it, so the "what was looked up" surface is still the one the panel shows.
Wiring it up is frontend work and its wording is the developer's to write.

**`VERIFY_SEARCH_MODE` ships as `fixed`.** Nothing here has been shown to improve a
verdict. `docs/architecture.md` and `backend/scripts/ched_verify_probe.json` have not
been run against this design.
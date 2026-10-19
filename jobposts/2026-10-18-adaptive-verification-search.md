# Adaptive verification search

**Status:** proposal, not implemented.
**Written without sight of** `search.py` and `verification_flow.py`. Function names below are suggestions. Facts about credits, `MAX_SEARCH_QUERIES`, the country boost and the `include_domains` policy are taken from AGENTS.md and have not been re-verified.
**Depends on:** the scan fields in `SYSTEM_PROMPT.proposed.md` (`CLAIMED_TYPE`, repeated `CONTACT_METHOD`, `LOCATION`, `REGISTERED_AS`) plus one addition: `JOB_TITLE: <position as printed>`. Without those, the planner falls back to the current `extract_company_name()` path and only the anchor query runs.

## 1. Problem

Verification fires a fixed set of queries once, before anything is known: one on the employer name, plus up to two the scan model proposed from the posting alone. Two things follow.

1. **The follow-up that matters depends on what the first search returned, and a fixed set cannot react.** When results describe an organisation whose name differs from the printed name, the useful next questions are different ones (what is the poster's own domain, is the job on the organisation's own site). Today those are never asked.
2. **Credits are spent without a stated purpose.** Model-proposed queries can duplicate the anchor query or ask about details that decide nothing.

Observed outcome: the test poster (a real agency's name altered, real address and a real `.gov.ph` address copied, two fake channels added) returns results about the real agency, and every entity-level check goes green.

## 2. Goals and non-goals

Goals
- Same credit ceiling as today (3 per verification). Typical cost falls to 1.
- Query planning is code, not a model, so it is deterministic and testable offline.
- Every planned query has one stated purpose.
- The "no conclusion words in a query" rule is enforced in code, not only in prompt text.

Non-goals
- Domain age, certificate history and direct page fetching. Round 0 leaves hooks for them (section 8).
- Changing the verdict logic. This proposal changes what evidence is gathered.

## 3. Design

```
Round 0  free      classify facts from the scan, no network
Round 1  1 credit  anchor query on the printed employer name (unchanged)
Resolve  free      derive entity name and domain from Round 1 results, no network
Round 2  0-2       follow-up queries chosen by a decision table
Merge    free      dedupe, flat list, each result labelled with its query text
One AI call        verify prompt
```

### Round 0 (deterministic, free)
From the scan fields, compute and store as `signals`:
- the printed name, normalised (case, spacing, punctuation, legal suffix removed);
- `claimed_government` (true when `CLAIMED_TYPE` is government);
- for each channel, a domain class: `free_email`, `job_board`, `social`, `gov_ph`, `other`;
- `domains_disagree`: more than one non-free domain, or a `gov_ph` domain beside a non-`gov_ph` one;
- `deadline_passed`, `has_registration_claim`, `has_location`.

### Round 1 (1 credit)
Unchanged: `"<company> company or employer"`, verbatim name, country boost, configured depth and exclude list. A nameless posting still runs no search.

### Resolve (deterministic, free)
From Round 1 results compute `entity`:
- `name`: the organisation name the top results use, taken from result titles;
- `domain`: the registrable domain of the best-ranked result that is not on an aggregator denylist (job boards, social platforms, news, directories). For a government claim, prefer a `.gov.ph` domain;
- `names_differ`: token overlap between the normalised printed name and `entity.name` below a threshold;
- `shares_identifier`: the posting's `LOCATION` appears in a result that describes the entity.

These are heuristics for choosing queries only. They never set a status. The verify prompt makes the call and the rules module acts on its output.

### Round 2 (0 to 2 credits, first matching rows, in priority order)

| Trigger | Follow-up query | Purpose |
|---|---|---|
| `names_differ` and `shares_identifier` | the posting's main non-free channel domain, in quotes, verbatim | What exists for the poster's own domain, and whether it appears beside the entity |
| same trigger and `entity.domain` known | `<JOB_TITLE> <entity.name>`, with `include_domains=[entity.domain]` | Is this job on the entity's own site, and with which contact details |
| Round 1 `ok` with no results | `<printed name> <LOCATION>` verbatim, or `REGISTERED_AS` verbatim if present | Find a footprint another way |
| Round 1 returned several unrelated entities | `<printed name> <LOCATION>` verbatim | Disambiguate |
| `has_registration_claim`, not yet covered | `<REGISTERED_AS verbatim> <printed name>` | Test the claim itself |
| none of the above | none | Save credits |

Cap: `MAX_FOLLOWUPS = 2`, enforced inside the planner and again in `verification_flow`, as the existing cap is.

What each follow-up can and cannot show
- The listing query can only produce evidence when a real posting exists on the entity's site. It catches edited copies of real postings, which is the test case. It tells us little about a job invented at a real agency. Absence stays yellow.
- The channel-domain query may return nothing useful. Keep it only if the fixtures show it adds evidence.

### Model-proposed queries
Retire them. They are written from the posting alone, cannot react to results, and cost credits the planner can spend with a purpose. If you want a transition, keep them behind the flag and use them only when the planner leaves slots empty.

### Merge and labelling
Keep the flat list and the dedupe. Label each result with the literal query text that retrieved it, nothing more. Do not add category headings or purposes to the prompt: the planner knows the purpose, the model only needs to know a result came back for that query. A result returned for a query is not evidence the entity is the one named.

## 4. Cost

| Case | Credits (basic depth) |
|---|---|
| No trigger | 1 |
| One trigger | 2 |
| Names differ and entity domain known | 3 |
| Ceiling | 3 |

Average cost is 1 plus the fraction of scans that trigger times 1 or 2. Measure the trigger rate on the fixtures before quoting a number. `advanced` depth doubles each request as it does today.

## 5. Failure semantics

- Keep `SearchOutcome.ok` and `.results` independent. `ok=True` with no results is a trigger for a follow-up. `ok=False` is a stop.
- If Round 1 fails, plan no follow-ups and report `search_ok: false`. Do not spend credits against a provider that just failed.
- If a Round 2 query fails, report `search_partial` with the existing wording and pair-style errors (query, reason).
- Record a `rounds` list on the response: purpose, query text, `ok`, result count. This replaces the unused `scheme_queries` idea and shows the reader what was searched.

## 6. Safety

- Queries are built only from extracted fields. Strip control characters and cap each query at a fixed length.
- Run a banned-term check on every planned query (`scam`, `fraud`, `fraudulent`, `fake`, `suspicious`, `legitimate`) and drop a query that fails. This moves the rule from prompt text into code.
- `include_domains` is set only on a Round 2 query, only to one validated registrable domain taken from results, never from posting text. This is a narrow exception to the current policy that it stays unset. The policy exists so discovery is not restricted to a whitelist. A scoped check of one known domain is a different use and should be recorded as a decision.
- Result text stays untrusted data, as today.

## 7. Tests (all offline)

The planner and resolver are pure functions of the scan facts and Round 1 results.

1. Test poster: government claim, names differ, address shared. Expect two Round 2 queries and total credits of 3.
2. Small private employer with a Gmail address and no trigger. Expect no follow-up and 1 credit.
3. Round 1 `ok=False`. Expect no follow-ups and `search_ok: false`.
4. Round 1 `ok=True`, no results. Expect the alternate-anchor follow-up.
5. Nameless posting. Expect no search.
6. Banned word in a planned query. Expect the query dropped.
7. Property test: for any input, planned queries plus the anchor never exceed 3.
8. `include_domains` appears only on a Round 2 query and only with a validated domain.
9. Franchise or branch that legitimately runs its own domain: record the behaviour, because it may trigger the names-differ row.
10. Flag off (`fixed`) reproduces today's behaviour exactly.

Mutation-check each in both directions, per the repo convention. Use function `side_effect` mocks, never a plain list.

## 8. Rollout

1. Land the current search-error fix first. Do not combine it with this.
2. Add `VERIFY_SEARCH_MODE=fixed|adaptive`, default `fixed`.
3. Run the fixtures in both modes against saved model outputs. Compare verdicts and credits.
4. Switch the default only when adaptive is at least as good on every fixture and within the ceiling.
5. Record three decisions: adaptive search under a 3-credit ceiling, the scoped `include_domains` exception, and retiring model-proposed queries.

Future Round 0 hooks (separate proposals): domain age from RDAP or certificate transparency logs; a direct sandboxed fetch of the poster's domain.

## 9. Risks

- The entity-domain heuristic can pick an aggregator or news domain. Contained: a wrong domain produces a wrong scoped query, not a wrong verdict. Keep the denylist small and tested.
- Sequential rounds add one round trip of latency. Run the Round 2 queries in parallel and report rounds in the progress stream.
- Nothing here is shown to improve accuracy yet. The fixtures decide.
- The Tavily behaviour of `include_domains` combined with the country boost should be checked against its documentation.

## 10. Decisions needed

| Decision | Recommended default |
|---|---|
| Retire model-proposed queries | Yes |
| Allow scoped `include_domains` on follow-ups | Yes, recorded as an exception |
| Credit ceiling | Keep 3 |
| Keep the channel-domain query | Only if fixtures show it adds evidence |

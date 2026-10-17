# Decision record — search and retrieval

Owner file: `backend/app/services/search.py`. Every warning below is a deliberate
decision. Nothing here is dormant behaviour waiting to be cleaned up.

---

## One query per verification

`build_queries()` issues **exactly one** query per verification:
`"<company> company or employer"`.

The `or employer` reads as a boolean, so a business writing itself either way is
matched. **The employer name is used verbatim — no part of it is rewritten.**

The query used to be paired with `registration certificate` and
`reviews complaints`. Both are gone: a general company query returns the employer's
own pages, a PESO listing and a job board post in one result set, where two targeted
queries starved each other.

**The traded cost is real.** `Official Registration` and `Reputation` now depend on
that one query surfacing the right page rather than asking for it by name.

### Credit cost: 1 to 3 per verification, not 2 to 5

One query is the employer's own; the rest are the scan model's, capped at
`MAX_SEARCH_QUERIES = 2`. The cap is enforced **in `verification_flow.py` as well as
in the parser** — a client that is not this extension can post a longer list, and a
malformed request is not a reason to spend six credits silently.

### `build_scheme_queries()`, `CHECKABLE_ATTRIBUTES`, `_with_country` and `_squeeze` are deleted, not dormant

The queries are model-authored now, so anything that rebuilt them from `attributes`
would be a second and stale source. `TestTheSchemeQueryBuilderIsDeleted` in
`test_multi_query.py` is the tombstone. **A function left in the module is a trap for
the next reader.**

### The corporate-suffix strip is gone, and it was wrong

A trailing Corporation/Corp/Inc/Co/LLC used to be removed on the reasoning that a
generic legal form dilutes a rare name. For a Philippine employer that is backwards:
an SEC filing, a city PESO listing and the employer's own legal pages are all titled
with the *legal* name, so stripping it left the distinctive part competing against a
brand, its franchisees, and unrelated products sharing the word.

Searching `"Jollibee Foods"` is a worse lookup than `"Jollibee Foods Corporation"`.

`_strip_corporate_suffix` and `build_query` are **deleted rather than left dormant**,
since a stripper left in the module is a trap for the next reader.
`TestQueryBuildingMovedOut` in `test_search.py` is the tombstone; `test_multi_query.py`
owns the query tests.

---

## No query names a conclusion — and that rule is enforced by prompt text alone

`scam`, `fraud`, `fraudulent`, `fake`, `suspicious` and `legitimate` stay out, because
a query carrying one returns pages chosen for containing that word, which then read as
corroboration of an accusation the query already made up.

**Both scan prompts state the rule and no code enforces it.** This is a deliberate
decision, not an oversight: `_QUERY_PLACEHOLDERS` survives because a model answering
`QUERY: none` is answering the *format* rather than proposing a search, which is a
parsing question rather than a judgment about query content.

**The exposure is a model reading a job posting and writing `Tanika scam`** — the
prompt is the only thing standing between that and the provider.

---

## No query carries `Philippines`, so `TAVILY_COUNTRY` is load-bearing

`country` on the request already biases ranking toward Philippine results, so appending
the suffix spent characters without adding reach. `country` is a *boost*, not a filter,
which is also why dropping the suffix does not lose the job boards and PESO listings
the query targets.

**Blank the setting and nothing anchors these queries to the Philippines at all** — an
invisible failure, because the search still succeeds. `test_multi_query.py` asserts
both halves: the query text carries no country, and the request body carries the boost.

---

## Category coverage, and what each check gave up

**Company Existence shares the one employer query.** It was the original single query,
and a general company query ranks the employer's own site and job boards first, which
proves existence. Existence is now read off that one query's results alongside whatever
the model proposed.

**The traded cost is recorded in `test_multi_query.py`:** an employer with no
footprint the query surfaces reports `yellow` on existence, which is the smallest
employers — the ones this product exists for.

**`Official Registration` and `Reputation` no longer have a query of their own.** They
used to, and were deliberately narrowed and merged as the query set grew. Both now
depend on one query and at most two model proposals surfacing the right page, rather
than on a query naming the document it wanted. This is the cost of dropping to three
credits per verification.

---

## Result assembly

**Results merge into one flat list for one AI call**, so the cost is one to three
requests, not three model calls.

`merge_results()` dedupes on canonical URL — `_canonical_url()` drops the scheme,
`www.`, query and trailing slash — keeping the higher-scoring copy, sorts by score,
and caps at `TAVILY_MAX_RESULTS * 2`.

Dedupe is not tidiness: the employer's own site appears in more than one result set,
and every result is prompt text competing for a budget shared with the model's
reasoning.

**No category heading is applied to the merged list.** Stamping one query's results
with a REGISTRATION heading is exactly the bug `format_results` was written to
prevent.

**`search_partial` is the state one search never had.** With one query, either it
worked or it did not. With several, one can fail while the others succeed: the
findings are real but some categories were checked by a thinner search than the
others.

- `ok` is true (there *is* usable data)
- `search_partial` is true
- `WhatWeChecked` says "{queriesFailed} of {queriesIssued} searches failed, so some
  checks were made against a thinner set of results than the others. This is not a
  finding about the employer…"

  (Named `EvidenceSummary` until 2026-10-18, when the report panel split that
  component across two slots — `WhatWeChecked` carries the check half and owns this
  copy. See `docs/architecture.md` § The report panel.)

Reporting plain `ok: true` would overstate coverage; reporting a total failure would
discard a search that worked. **Every query failing is still the `search_ok: false`
state.**

Failures are collected as `(query, error)` pairs, not queries — `search_error` carries
the *reason*, and putting the query there once reported "Acme Philippines" to the user
in place of "TAVILY_API_KEY is not configured".

The wire also carries `scheme_queries` (which of the issued queries came from the
posting's claims rather than from the employer), reported separately from
`queries_issued` because the two families answer different questions.

---

## `SearchOutcome.ok` and `.results` are independent, and that is the whole point

`ok=False` with no results means the search failed. `ok=True` with no results means the
company has no online footprint. The previous module returned `[]` for both, so a
throttled query was indistinguishable from a clean company and the model reported
"nothing found" when the truth was "we could not look".

**Never collapse these two states.**

**A missing `TAVILY_API_KEY` is a failure, not an empty success**, so a broken
deployment cannot look like a clean employer.

---

## No retries, no fallback provider, no caching, no engine rotation

The old DuckDuckGo module was 620 lines of policy layered on scraping, and the failures
were the policy's fault rather than the provider's. One call, one outcome, reported
honestly.

---

## No category headings in the prompt

The old `format_verification_context()` stamped each result with the category whose
query had found it, which asserted something retrieval never established — a
regulator's complaint form under a `[SCAM REPORTS]` heading read as a scam report.

`format_results()` emits a flat list with URLs and the model judges each result. This
is also why the query carries no `SEC`/`scam`/`hiring` tokens: asking for that text
biases retrieval toward it and manufactures the appearance of evidence the prompt then
has to be careful not to trust.

---

## Relevance is a ranking problem, so it is fixed with ranking

A small Philippine employer's SEC filing, city PESO listing and JobStreet page are
well covered by a browser search from the Philippines but only thinly by Tavily's own
crawl index. A niche name therefore falls through to whatever that index holds
strongly — a London VC firm, or an unrelated product with a similar word.

`search()` therefore sends `country="philippines"` and `search_depth="advanced"`.

- **`country` is a boost.** `include_domains` is a **filter** and must stay unset,
  since restricting the result set to named domains would discard exactly the job
  boards and PESO pages the boost exists to surface. The job here is to fact-check a
  company, and the sites that fact-check it are the ones a whitelist cannot name in
  advance.
- Tavily does offer `include_domains_mode: "prefer"`, which searches the listed
  domains *and* the rest of the web. **It is not used**, because it still requires
  naming domains up front, and the boost exists precisely so a deployment need not
  predict which sites will mention a small Philippine employer.
- Advanced depth costs 2 credits against basic's 1, halving the 1,000/month free
  budget. **That is the deliberate trade for a niche lookup.**
- **`include_answer` is never set.** A synthesised answer is retrieval's opinion, not
  evidence, and the prompt requires source URLs copied from the results.

---

## Credit knobs are env values, not constants

`TAVILY_SEARCH_DEPTH` (`basic` | `advanced`, default `basic`) and `TAVILY_COUNTRY`
(default `philippines`, blank disables the boost) live in `backend/.env`, because the
recall-versus-budget trade is a deployment decision and should not require a code
change.

- An unrecognised depth **logs an error and falls back to advanced** rather than being
  sent. The provider would reject it, and a rejected search is reported to the user as
  a company that cannot be looked up, so **a typo in a cost setting must never become
  a verdict.**
- A blank country is dropped from the request rather than sent as `""`.
- **Credits are per *request*.** A verification issues the single employer query plus
  at most two the scan model proposed, so `basic` costs 1–3 credits and `advanced`
  2–6 — which is not what the knob's own name suggests, and is why `basic` remains the
  default.
- **Credits are per request, not per result, so every other recall lever is free.**
  `max_results`, `chunks_per_source`, `country`, `exclude_domains` and
  `include_domains_mode` all change what comes back at the same 1-or-2 credit cost.
  Only `search_depth` moves the price, and only a second `POST /search` adds another
  charge — the API takes a single `query` per request, so "several queries" means
  several requests. The documented sub-query pattern would have tripled the monthly
  verification count on a 1,000-credit budget, and it is the wrong shape for this
  product: the query is deliberately unadorned so no category bias is introduced, and
  three queries' worth of chunks would crowd out a reasoning model already sharing
  `AI_MAX_TOKENS` with its own answer.

---

## `TAVILY_EXCLUDE_DOMAINS`

`exclude_domains` is a **different lever** from `include_domains`, and the difference
is the entire reason it is allowed. `include_domains` restricts the result set to a
whitelist and would discard the very pages the country boost exists to surface.
`exclude_domains` *removes named pages* from an otherwise unfiltered set, so a domain
is dropped by name rather than everything outside it.

**The default list is `wikipedia.org` and nothing else, and that is an evidence rule
rather than a noise rule.** A crowd-edited entry is unattributed and often wrong about
a company, and the panel is required to state facts about a named employer with a
source behind each one; a citation nobody can trace back to whoever asserted it is not
defensible.

Every other entry is a deployment decision, made when a domain has actually been seen
displacing a real source — SEO farms and scrapers that hijack a company name are the
usual case, and each one removed is a result the verification prompt no longer gets to
judge.

`test_the_default_list_keeps_the_sources_the_boost_targets` exists because the obvious
overcorrection (excluding the job boards and PESO sites) would spend the recall the
boost buys on getting rid of it.

### Parsing

`_parse_domains()` takes a comma- or whitespace-separated value and normalises each
entry to a bare host. `_normalise_domain()` strips a scheme, a `www.`, and any path or
query, because Tavily matches on the host — `https://www.Example.com/jobs` as a filter
would silently exclude nothing while still looking configured, **which is worse than
an error.**

- A leading `*.` is preserved, since flattening it would widen what gets dropped.
- Entries without a dot are discarded, so a stray word in a `.env` cannot become a
  domain Tavily rejects — **the same typo-becomes-a-verdict failure the depth
  fallback exists to prevent.**
- A blank value is dropped from the request rather than sent as `[]`.

---

## A recruiter is not the employer

The scan's employer field is `EMPLOYER NAME:` and the rules require the company the
reader would work for, with a staffing agency named only when the posting is for the
agency's own staff.

A joined name reaches `clean_company_name()` as
`Vikings / Silvergreen Manpower Services Corporation`, and a search engine tokenises
the slash into neither entity, so it is split and the last part is looked up.

The parser accepts `COMPANY NAME` as well **so scans recorded before the rename still
parse.**

---

## Result text is untrusted input

A search snippet is whatever a page said, and it can read like an instruction or
assert a green status. `VERIFY_PROMPT.md`'s `OUTPUT RULES` say so explicitly and
require a result to concern the same entity as the company being verified — a
common-word name returns a mixed bag.

`format_results()` labels the block as data and strips `===` from result text so a
page cannot forge the block terminator and append its own findings.

**Do not remove any of the three.**

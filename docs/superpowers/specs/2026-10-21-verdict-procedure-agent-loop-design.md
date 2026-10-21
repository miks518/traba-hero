# Design — the verdict procedure, and the agentic loop that feeds it

Date: 2026-10-21
Status: draft for review (rev. 2, after builder check)
Supersedes: `docs/scoring.md`, `docs/decisions/scoring-model.md`,
`docs/decisions/verification-design.md` (the category-status section),
the token-budget section of `docs/decisions/reasoning-models.md`,
`docs/superpowers/specs/2026-10-18-adaptive-verification-search.md`

Owner files: `backend/app/services/scanner/verdict.py`,
`risk_calculator.py` (to be retired), `channel_match.py`,
`verification_flow.py`, `scan_flow.py`, `prompts.py`,
`verification_prompt.py`, `search.py`, `backend/app/services/lm_client.py`,
`backend/app/services/scanner/dependencies.py`,
`backend/app/models/schemas.py`, `backend/app/config.py`,
`entrypoints/sidepanel/**`.

**Reader's note on the marked decisions.** Items marked **[CALL]** are the
author's calls — settled here, changeable by the reviewer without opening a
new discussion. Items marked **[OPEN]** are the ones only the reviewer can
settle, and they are collected in §12.

---

## 1. The intent

Three defects, one cause.

**The number is indefensible.** The verdict is computed as
`POSTING_SEVERITY_WEIGHTS` (40/12/4) plus `REFUTATION_WEIGHTS` (25/13/7/4/2/2),
summed, then banded into `low | moderate | high | critical`. A panelist asks
"where did you get that number?" and there is no answer, because there is
nothing in 37 that describes a posting. The weights price a *category*; the
posting is not a category. A Saaty matrix does not fix this — AHP needs a
fixed, commensurable variable set, and an unstructured job posting does not
have one. **The number comes out.**

**The context is lost in the relay.** The scan model reads the flyer and emits
fixed slots; the verify model never sees the flyer and reasons over a lossy,
model-chosen compression of it. So the fact that decided the verdict is often
not in the room when the verdict is written. In the Fake CHED fixture the
one-line reason names the fee ("It asks for a fee before it will accept an
application"), because the fee is what survived the compression — the
impersonation, which is the fact that matters, was never handed over. (The
verdict *headline* for `critical` is the fixed string "Do not proceed"; the
fee appears in the separate one-line reason slot. Both are rewritten here.)

**The false caution.** `channel_match.py` rule 4 makes a free-provider email
plus any independent finding a **red** Channel Match worth 25 points. A posting
with one ordinary finding and a Gmail address lands at 37 = `moderate` =
"Proceed with caution". The scan prompt says a free email is not an anomaly;
the scoring says it is worth 25 points. Every clean posting is amber.

This design replaces the sum with a **decision procedure**, and replaces the
relay with **one agent that holds the posting for the whole proceeding**.

The product's purpose is unchanged and is what the design is built around: it
is a risk assessment whose job is spotting a fake or fraudulent job post. It
does not prove fraud, and it does not certify legitimacy. The reader decides
whether to apply.

---

## 2. The roles

The design is a courtroom with separated roles. The separation is where the
defects above come from, and each role has a hard limit on what it can see.

| Role | Who | Sees | Produces | Cannot |
|---|---|---|---|---|
| **Exhibit** | the posting | itself | channels, demands, what it claims to be | — |
| **Prosecutor** | the agent, first turn | **the posting only** | findings: what the posting asks for, what it claims to be | consult the web before the record is open |
| **Witness** | the agent, later turns | the retrieved record | facts about the employer's own record, each with a source | decide what the facts mean |
| **Defense** | the employer's own pages, fetched | the employer's site, listings, registry pages | "this employer publishes this role" | — |
| **Clerk** | `verdict.py` | facts + rules | the verdict label, the exposure, the establishment state, the authored statement | write prose, or judge anything not on the record |
| **Judge** | the reader | the verdict, the record, the options | whether to apply | — |

Two rules fall out and are load-bearing:

1. **The agent never decides.** It reports what an exhibit says. The code
   decides what that means. This is the rule in
   `docs/decisions/libel-guardrail.md` — every statement traces to the input —
   and it is what `channel_match.py` and `verdict.py` already do for the
   channel comparison. It is extended, not replaced.
2. **The prosecutor and the witness are the same model, in the same session,
   separated by time and by tools** — not by two different prompts. The scan
   model is already walled off from the internet (`NO_ONLINE_ACCESS` in
   `prompts.py`). The agent keeps that wall for its first turn and lifts it
   only once the charges are on the record.

**[CALL] Where a model-produced fact crosses into a decision, the code makes
the check.** The agent proposes *which page to fetch* and *what that page
appears to show*; the code checks the fetched text for the thing at issue
(the role title, the fee amount, the employer's own domain). A model boolean
never establishes anything on its own. Without this the `confirmed` state —
the strongest one, and the reason the fetch tool exists — would rest on a
model assertion, which is the same shape as the defect this design exists to
fix, one level up.

---

## 3. The verdict procedure

### 3.1 Exposure — what the posting asks the reader to give up

Derived from the anomaly code. `app/services/anomaly_codes.py` documents the
codes in families by what the reader gives up, but **the family grouping
exists only in that module's comments** — `ANOMALY_CODES` is a flat tuple with
no family mapping in code. A code→exposure table has to be written:

| Family | Codes | Exposure |
|---|---|---|
| M | `FEE_MANDATORY`, `FEE_CONDITIONAL`, `PURCHASE_REQUIRED`, `DEPOSIT_REQUIRED`, `PAYMENT_FORWARDING` | `money` |
| I | `CREDENTIALS_BEFORE_INTERVIEW`, `DOCUMENTS_VIA_THIRD_PARTY` | `documents` |
| C | `TASK_FOR_EARNING` | `labour` |
| — | `OTHER`, and any finding whose code is absent | `none` |

`IMPERSONATES_AUTHORITY` sits in Family I in that module, but **is not an
exposure**. It is a claim about *who is asking*, and it is read as an
establishment signal (§3.3). It contributes no exposure of its own: a posting
that only impersonates and asks for nothing has exposure `none`. The family
comment in `anomaly_codes.py` gets a note saying so.

**[CALL] A posting can have more than one exposure** — a fee *and* identity
papers. The grid is indexed by the **highest** exposure, in the order
`documents > money > labour > none`, because identity papers are the least
reversible thing a reader can hand over. The statement lists *all* of the
exposures; the grid uses the worst one. A compound-exposure row set would
multiply the authored statements for a case the reader experiences as "it
wants several things, the worst being my documents". **[OPEN 1]** if the
reviewer wants compounds, the grid grows and the statement table grows with
it.

### 3.2 Establishment — what the record says about who is asking

Two questions about the employer's own record, asked separately:

- **(i) Was the employer found?** Does anything on the record identify the
  entity the posting names?
- **(ii) Does their record show *this posting*?** The role, and the terms if
  the posting asks for something.

| State | Meaning |
|---|---|
| `confirmed` | (i) and (ii). Their own record shows this posting — the role, and the terms as advertised — with a source. |
| `supported` | (i) but not (ii). The employer was found and nothing contradicts them; the posting itself was not found in their record. |
| `unknown` | not (i). Nothing was found either way. Grey. Nothing is asserted. |
| `contradicted` | a retrieved source shows the posting's claims are false, in a way that bears on *who is asking*. |

The words are `confirmed` / `supported` / `unknown`, not `corroborated`:
`corroborated` is not a word a reader of this panel parses at a glance, and
"corroborate" carries a legal connotation that does not fit.

**`supported` is the state that catches the case nothing else catches.** A
scam that borrows a real employer's name and asks for nothing unusual is
caught by neither `channel_match.py` nor the independent-finding rule, because
both compare the posting's channels against the employer's own channels and
find them equal. What catches it is (ii) failing: the employer's own site
does not list this role. That is `AGENTS.md` contradiction #7, and this is
where it gets closed.

### 3.3 Establishment is a rule over facts, never a model verdict

The agent reports facts about the employer's record. The code turns them into
the state. Each fact carries the URL it came from:

```
employer_domain          the domain the employer's own pages use      (+ url)
employer_pages           the pages retrieved that describe the employer (+ url each)
employer_lists_role      the excerpt of their page showing this role   (+ url)
employer_states_terms    the excerpt of their page showing the request (+ url)
posting_channels         every channel the posting directs applicants to (verbatim)
government_claim         the posting presents itself as a government agency
```

The code decides:

1. `contradicted` when a **material** contradiction is on the record:
   - the posting claims to be entity X, and X's own domain (retrieved) differs
     from the domain the posting uses — the impersonation shape, and the
     existing `channel_match.py` rules 1 and 2 (`government`, `lookalike`);
   - or the posting states a registration or permit that a retrieved registry
     contradicts.
   Materiality is **identity-level only**. A wrong phone number beside a
   matching domain is not a contradiction of who is asking; it is `supported`
   with the mismatch recorded.
2. `confirmed` when (i) and (ii) hold. **(ii) is checked by code against the
   fetched text** — the fetched page must contain the role title (or the fee
   amount), case-insensitively — not by the model's boolean. A model-proposed
   excerpt that does not contain the thing does not establish it.
3. `supported` when (i) holds and nothing contradicts.
4. `unknown` otherwise.

**`unknown` is never punished on its own.** It is the state of a small
employer with no web footprint, which is the ordinary case for the people this
product exists for. It is punished only in combination with an exposure, and
the reasoning is stated in §3.4: the exposure is certain either way, and that
is what makes it a caution rather than a green light. *Reconciliation with the
standing rule:* "absence is never red" is not violated — `unknown` produces no
red, no charge, and no accusation; it is a fact, and the fact that a small
employer cannot be looked up is not a finding about them.

A finding the employer's own record accounts for is **retired** — the existing
`stale` rule, unchanged in meaning, and re-expressed in the new vocabulary
(§7.2).

### 3.4 The grid

Authored. Hand-written. Not computed, and not a function of any number.

| Exposure | `confirmed` | `supported` | `unknown` | `contradicted` |
|---|---|---|---|---|
| `none` | CLEAR | CLEAR | CLEAR | **STOP** |
| `money` | CLEAR | NOTE | CAUTION | **STOP** |
| `documents` | CLEAR | CAUTION | CAUTION | **STOP** |
| `labour` | CLEAR | NOTE | CAUTION | **STOP** |

The reasoning behind each choice, because the grid is a set of judgements and
not a derivation:

- **Exposure `none` + `contradicted` is STOP.** The posting is not from the
  employer it names, which is the product's whole purpose, and nothing is
  asked of the reader. The reader still loses their time and leaves a trail.
- **Exposure `none` is CLEAR at every other establishment.** Nothing is asked
  that cannot be walked away from. A free email address is a **fact in the
  record**, not a finding and not a charge. This is the false-caution fix.
- **Exposure + `unknown` is at least CAUTION.** The reader has a certain
  exposure — the money leaves their pocket either way, and whether the
  employer is real does not change that — and the counterparty is
  unestablished. That combination is what a caution is for.
- **Exposure + `supported` is softer than + `unknown`**, because the employer
  exists and nothing contradicts them. It is a NOTE, except for documents,
  where an unestablished channel for identity papers is one step worse than
  money.
- **Exposure + `confirmed` is CLEAR**, because nothing is hidden: the employer's
  own site publishes the role and the terms, so the reader can see what they
  are agreeing to before they send anything.

**[OPEN 1] The grid cells the reviewer must settle**, because they are the
arguable ones and they decide how often the panel says what:

- `documents` + `unknown` — CAUTION or STOP? For STOP: identity papers are
  irreversible. For CAUTION: most small Philippine employers are `unknown`,
  and STOP on every one of them would cry wolf.
- `money` + `confirmed` — CLEAR or NOTE? For CLEAR: a fee the employer's own
  site publishes is a published term, not a hidden one. For NOTE: the reader
  may still decide against it, and saying CLEAR says the reader's decision
  has been made for them.
- `money` + `supported` — NOTE or CAUTION? For NOTE: the fee has a stated
  reason and the employer is real. For CAUTION: their site does not mention
  the fee, and that is a question the reader should have answered before
  they pay it.

### 3.5 A fee with a reason, and a fee without one

A fee the posting explains (medical, uniform, a training kit) and a fee it
does not are not the same. The scan model reports the reason as a **fact**,
verbatim, and never judges it:

```
FEE_REASON: <the reason the posting gives, or omit>
```

**[CALL] The reason does not change the verdict.** Only exposure and
establishment do. What it changes is how the record says it: a fee with a
stated reason is reported as "they ask for ₱1,500 for medical clearance", and
a fee without one as "they ask for ₱1,500 and give no reason". Whether a
reasonless fee should be worse is a fifth row in the grid, and it is not
added here. **[OPEN 1]** if the reviewer wants it, it is decided in §3.4.

---

## 4. The agentic loop

### 4.1 Why the loop

The scan→verify relay exists because two models were cheaper than one. The
cost was the compression, and the compression is where the context died. One
agent that holds the posting for the whole proceeding has no relay and so no
hop where context can be lost.

The loop is **not** "let the model be clever". It is one job: **establish
whether the employer is `confirmed`, `supported`, or `contradicted`.** That is
the fact the verdict needs and the fact the current pipeline cannot produce,
because a model reading four search snippets cannot know whether the employer's
own site lists this role.

### 4.2 The shape

```
Turn 0   system: the agent's role, the tool definitions, the output format
         user:   the posting (image, or text where a caller supplies it)
                 + the task
         agent:  charges — the findings, the attributes, what it claims to be
                 and, if it already has enough, the final answer.
                 Otherwise: tool calls.

Turn n   harness runs the requested tools, appends the results, and re-sends
         the posting together with the transcript so far.

         The posting is re-sent on every turn. That is the whole fix: there
         is no hop where the context can be dropped.

Final    the agent emits the structured payload (§6).
```

**The posting is re-sent every turn, and it is never summarised on the way.**
The relay does not exist any more.

**[CALL] The protocol is a text protocol, not native tool calling.**
`lm_client.chat()` returns `completion.choices[0].message.content` and nothing
else; it has no `tools=` parameter, no multi-turn support, and it raises
`EmptyModelResponse` when the content is empty. `scan_flow.py` even strips
`<|tool_call|>` text as a hack. Native tool calling is also not guaranteed
across OpenRouter routes, and the repo's precedent for a missing capability is
to fall back rather than fail (`_create_completion` drops a rejected
parameter; there is a 404 fallback for the structured-output endpoint). So:
the agent's tool calls are a **labeled text block** with its own parser and
its own injection guardrail — the `===` problem, one level up, closed the way
`format_results()` closes it today. The existing
`verification_parser.py` labeled-text fallback is the model for the parser.
If a route does support native tool calls, that is an optimisation to add
later, not a dependency.

### 4.3 The tools

Two tools, both code-owned, both metered.

**`search(query)`** — the existing `search()` in `app/services/search.py`.
Unchanged. One credit per request at `basic` depth. The query-safety filter
(`search_planner.search_query_is_safe`) becomes unconditional: a query
carrying a conclusion word — scam, fraud, fraudulent, fake, suspicious,
legitimate — is refused before it is issued, in every mode.

**[CALL] This amends a recorded decision.** `docs/decisions/search-retrieval.md`
states, at length, that "in the shipped default, both scan prompts state the
rule and no code enforces it", and that the code control exists only in the
`adaptive` mode that ships off. The design's direction is the better one, so
that record is amended rather than left to contradict the code, and
`lm_client.py`'s comment (which repeats the "in `fixed` mode the prompt
sentence is the only control" statement three times) is corrected with it.

**[CALL] A refused query does not count against the search budget**, because it
spends no credit, and the agent is told the query was refused so it can choose
another.

**[CALL] One search is reserved for the employer's own record.** The agent
chooses the rest. The reserved one is the code-built anchor — `"<company>
company or employer"` — because `confirmed` and `supported` both need the
employer's own pages, and an agent that spends all three searches on
discriminating queries about the posting could come back with nothing about
the employer. The agent gets two.

**`fetch(url)`** — new. Retrieves a page and returns its text.

- Only `http` and `https`. Only URLs whose host came from a **search result**,
  **and** whose registrable domain is not one the posting itself supplied.
  These are two different rules and both are needed: the Fake CHED case is
  exactly a domain (`chred-region6.org`, `outlook.com`) that a search for
  "CHED Regional Office VI" would surface, so "came from a search result"
  alone would admit the very thing under suspicion. The reason is the one
  `search_planner` already gives for scoped follow-ups: fetching the thing
  under suspicion is the one source that can never report that it found
  nothing.
  (`search.registrable_domain()` returns `""` for bare suffixes such as
  `gov.ph`, so the reduction needs the care `entity_domain_of` documents.)
- No cookies, no authentication, no JavaScript execution.
- **SSRF guard**: resolve the host and refuse loopback, link-local, private and
  reserved ranges; re-check on every redirect hop. A search result is
  untrusted input and can point anywhere.
- Byte cap and time cap. The text is truncated with an explicit marker so the
  model knows it is seeing a fragment.
- The result is **untrusted input** and is labelled as such in the prompt, the
  same way `format_results()` labels search results today, and the `===`
  terminator trick is closed the same way.
- The fetched text never reaches the wire as a claim. It becomes a fact with
  a source URL, and the source URL must be in the retrieved set, exactly as
  `_bind_to_retrieved` does for search results today.

### 4.4 The limits (the procedural limits)

Every one of these is an env value, in the same style as the existing knobs in
`app/config.py`:

| Knob | Default | Meaning |
|---|---|---|
| `AGENT_MAX_TURNS` | 4 | model round trips per scan |
| `AGENT_MAX_SEARCHES` | 3 | Tavily requests per scan (the current ceiling) |
| `AGENT_MAX_FETCHES` | 4 | page fetches per scan |
| `AGENT_MAX_FETCH_BYTES` | 200000 | bytes per fetched page |

`AGENT_MAX_SEARCHES` stays at 3, because Tavily's free tier is 1,000 credits
per **month** and that is the binding constraint in the whole system — against
the provider's 1,000 requests per **day**, roughly thirty times tighter. The
loop must not raise the credit ceiling; it must spend the same credits on
better questions. A loop that asks the *discriminating* question (the exact
domain string, the exact permit number, the exact role title with the
employer's name) buys more per credit than the current generic probes.

The other three limits are new and are the reason the agent cannot run away.

### 4.5 What the agent may and may not assert

- It may report what a page says, with the page's URL.
- It may report what the posting says, with a verbatim quote.
- It may not state a verdict, a level, or a conclusion about the employer.
- **It may not use its own memory as a source.** A claim it believes from
  training is not on the record and cannot be bound to a retrieved URL, so it
  carries no weight. Memory shapes *what to search for*; retrieval is what
  establishes a fact. A model that "knows" CHED's domain is `ched.gov.ph`
  still has to fetch it, and if it cannot, the establishment state is
  `unknown`, not `confirmed`.

---

## 5. The wire

The verdict vocabulary replaces the level vocabulary. `low | moderate | high |
critical` becomes:

```
clear | note | caution | stop
```

Plus the state that already exists and is not a verdict: **no verdict** (grey)
— the posting named no employer, or the answer could not be read.

The number and its machinery leave the wire entirely:

| Removed | Replaced by |
|---|---|
| `riskScore`, `riskScored` | `verdict` (the label) |
| `scoreBreakdown` | `verdictBreakdown` — the exposure, the establishment state, the rule that fired, and the record |
| `riskLevel` (wire key and `VerificationResult` field) | `verdict` |

`verdictBreakdown` is not a score. It is the clerk's record of how the verdict
was reached:

```json
{
  "verdict": "caution",
  "exposure": "money",
  "exposures": [
    {"code": "FEE_MANDATORY", "label": "Asks applicants to pay a fee",
     "amount": "1,500", "reason": "medical clearance", "quote": "..."}
  ],
  "establishment": {"state": "unknown", "reason": "no page describing the employer was retrieved"},
  "rule": "exposure+money|establishment+unknown",
  "record": [ {"claim": "...", "source_title": "...", "source_url": "..."} ]
}
```

The `rule` field names the cell of the grid that fired. It is the thing that
makes the verdict auditable without a number: it says which fact decided it.

**[OPEN 3] The endpoint shape.** The agent has to replace both stages — the
scan and the verify — or the relay survives. That is a protocol change with
real consequences: `useScanSession.startVerification` fires the verify only
after the scan returns, `verificationLoading`, `CompanyNameNeeded`,
`ScanResponse`, and the offer path all move. The three shapes are:

- **(a)** `/api/scan` becomes the agent endpoint and `/api/verify` is deleted.
  The extension makes one call. The scan is image-only in practice today
  (`architecture.md`: "Scans are always screenshots"; `scanTextStream` is
  exported but has no caller), so the agent's first turn is a vision turn.
- **(b)** A new `/api/assess` endpoint replaces both, and `/api/scan` and
  `/api/verify` are deleted. Same product behaviour, a name that says what it
  is.
- **(c)** `/api/verify` becomes the agent endpoint and is fed the scan's
  parsed output — which reinstates the relay the design exists to remove.

The author's preference is **(b)**: the endpoint name should say what it does,
and a new name makes the deletion of the old pair a deliberate act rather than
a silent overwrite. **(a)** is smaller and equally honest.

---

## 6. The agent's output

The agent's final answer is structured, not prose, and the code reads it:

```json
{
  "valid": true,
  "findings": [
    {"label": "...", "reasoning": "...", "code": "FEE_MANDATORY",
     "quote": "...", "fee_reason": "medical clearance"}
  ],
  "attributes": {"company": "...", "job_title": "...", "location": "...",
                 "claimed_type": "...", "channels": [{"type":"email","value":"..."}],
                 "pay": "...", "registered_as": "..."},
  "employer_record": {
    "domain": {"value": "knollridges.com.ph", "source_url": "https://knollridges.com.ph"},
    "pages": [{"title": "...", "url": "...", "snippet": "..."}],
    "lists_role": {"excerpt": "...", "source_url": "..."},
    "states_terms": {"excerpt": "...", "source_url": "..."}
  },
  "record": [ {"claim": "...", "source_title": "...", "source_url": "..."} ]
}
```

Every fact about the employer's record carries the URL it came from —
including the domain, which carries no URL in an earlier draft of this
document and would therefore be unbound and unusable under §4.5's rule.

Everything the agent says about the employer's record is a **fact with a
source**, and every source URL is checked against the retrieved set before it
is used. An unbound fact is dropped, and an unbound fact that would have
established something leaves the state at `unknown`. This is
`_bind_to_retrieved`, extended to the facts the loop produces.

---

## 7. The panel

### 7.1 The verdict, the statement, the options

Three slots, and they are different in kind:

1. **The verdict** — the label, in a chip: CLEAR / NOTE / CAUTION / STOP.
2. **The statement** — one sentence naming what was found, in the reader's
   terms.
3. **The options** — what the reader can do about it.

**"Do not proceed" is the ace card.** It is the verdict headline for `stop`
only, and `stop` requires `contradicted` — hard evidence, like the Commission
on Higher Learning not being CHED. It is not said for a caution. A product
that says it for everything says it for nothing.

For the other verdicts the statement is evidentiary, because the reader is the
judge:

| Verdict | Statement shape |
|---|---|
| CLEAR | "This posting does not ask you for money, documents, or work before you start." |
| NOTE | "They ask for ₱500 for medical clearance. Their site lists this role, but not that fee." |
| CAUTION | "They ask you to pay ₱1,500 before you start, and we could not find a record of this agency." |
| STOP | "This posting is not from the employer it names." |

The options block is authored per verdict family and offers the reader's
choices — ask for something in writing, meet at an address they give you, do
not send money or documents before you have spoken to someone — in the shape
`VERIFY_PROMPT.md` already describes for the recommendation. It does not decide
for the reader; it tells them what the stakes are and what they can do.

**[CALL] The statement is rendered by the backend**, from an authored template
module, with the structured facts substituted. `verdictCopy.ts`'s rule is that
every word is authored in code and looked up — and a template with the amount
and the fee reason substituted is still authored, because the substituted
values are structured facts off the record (`amount` from the posting's own
`PAY` attribute, `reason` from `FEE_REASON`), not model prose. Rendering it
on the backend keeps the substitution next to the binding that guarantees the
facts came from the record, and it keeps the frontend from having to trust a
number it did not compute. `verdictCopy.ts` keeps the verdict→label mapping
and the options block. The backend module is `backend/app/services/scanner/verdict_copy.py`.

The model's own `verdict_reason` field — the current one-line reason, which is
where the CHED fee sentence comes from — **is retired**. It is a model-written
headline, and the whole point of the statement is that it is not.

### 7.2 The status vocabulary collapses to the four states

Today the panel carries two incompatible status systems: green/yellow/red for
the six claim categories (`VerificationItem[]`, rendered by
`WhatWeChecked.tsx` and `FullDetails.tsx`) and stale/yellow/red for the
findings (`anomaly_assessments`, rendered by `AnomalyCards.tsx`).

**[CALL] Both collapse onto `confirmed` / `supported` / `unknown` /
`contradicted`**, applied per category and per finding, with the source
attached. The six claim categories survive as **the grouping of the record** —
they are the questions the record answers, and `WhatWeChecked` keeps its
structure — but their green/yellow/red statuses go, because a model-written
status beside a code-owned establishment state would be two verdicts in one
panel, and they will disagree.

`stale` survives in meaning and is renamed for the new vocabulary: a finding
the employer's own record accounts for is **retired** — it is not shown as a
finding, and it does not count toward the exposure. `verdict.py`'s
`_without_stale` keeps its rule and changes its input: it consumes the
agent's per-finding status rather than a separate assessment list.

**[OPEN 2] The panel's information architecture.** §7.2 says the categories
survive as the grouping of the record and their statuses go. The alternative
is to rebuild the panel around the record and the establishment state, with
the categories dissolved. The first is a smaller change; the second is a
cleaner panel and a bigger one. The author's preference is the first, because
it preserves `WhatWeChecked` and `FullDetails` — the parts of the panel that
earn their place — and because the categories are a good way to organise a
record.

### 7.3 Naming

The product's output is a **verdict**, not an assessment. An assessment is
advisory; a verdict is the finding the reader acts on. `docs/architecture.md`,
`Documentation.md`, the panel copy, and the identifiers that carry the word
get renamed.

**[CALL] The rename is complete, not cosmetic.** `ScanRiskLevel`, `riskLevel`,
`riskLabel`, `riskDisplay.ts`, `riskAccent.ts`, `riskLevelLabel`,
`mapApiResponse.riskScored`, `isUnverifiedEmployer`, the `risk_score` /
`risk_level` wire keys, and the history keys all move to the verdict
vocabulary. The user said "verdict, rather assessment" and a thesis reads
better when the code says what the product says. It is mechanical churn and it
is contained.

**[CALL] Stored history is migrated, not re-derived.** Old scans carry a level
and no exposure and no establishment, so a new verdict cannot be computed from
them. `scanHistory.ts` gets a migration that maps the old level onto the old
label and renders it with a note that it was recorded under the previous
procedure. A stored scan is never silently re-labelled as a new verdict.

### 7.4 What the panel must not say

- It must not say the employer is safe, legitimate, real, or genuine. The
  verdict is about the posting, not about the employer's character. `unknown`
  is not a soft yes.
- It must not accuse. No "scam", "fake", "fraudulent", "suspicious" beside a
  named employer. `contradicted` is a comparison between the posting and a
  retrieved source, and the panel says so in those terms.
- It must not show a number. There is no number.

---

## 8. What dies

| Removed | Note |
|---|---|
| `risk_calculator.py` | the weights, the bands, `_combine_scores`, `_level_for`. The whole file. It is **live** today — resurrected on 2026-10-21 as the arithmetic behind `verdict.py`, and recorded as live in `AGENTS.md` contradiction #3 — so its removal is a second reversal, and both `AGENTS.md` and `docs/decisions/scoring-model.md` get a line saying so and why. |
| `docs/scoring.md` | the bands, the AHP derivations, the anchor, the sensitivity analysis. Superseded by `docs/decisions/verdict-procedure.md`. |
| `docs/decisions/scoring-model.md` | superseded. |
| `backend/scripts/derive_refutation_weights.py` | deleted, with a tombstone test. |
| `POSTING_SEVERITY_WEIGHTS`, `REFUTATION_WEIGHTS`, `MAX_REFUTATION_SCORE` | with the file. |
| `riskScore`, `riskScored`, `scoreBreakdown` on the wire | replaced by `verdict` and `verdictBreakdown`. |
| `entrypoints/sidepanel/lib/scoreBreakdown.ts` | deleted, with a tombstone test. |
| "40% Risk" in `ResumeMatchView.tsx` | shows the verdict label instead. |
| `RISK_LEVELS` | replaced by the verdict vocabulary. |
| the model's `severity` field | display only. The code carries the meaning. The exposure axis and the grid replace the 40/12/4 ladder. |
| `offer_prompt.py`'s model-owned `risk_level` | the offer path gets the same procedure. It has no employer, so establishment is `unknown` by construction and exposure carries the whole verdict. This closes contradiction #5 in `AGENTS.md`. |
| `verification_prompt.py`'s `verdict_reason` | retired (§7.1). |
| `VerificationItem.status` (green/yellow/red) | retired in favour of the four states (§7.2). |

**`docs/scoring.md` is deleted, not rewritten.** The AHP work is not wrong; it
answers a question this product no longer asks. The thesis claim changes from
"a weighted score over indicators" to "an auditable decision procedure over
observed facts, with the burden of proof on the charge" — which is a stronger
claim to defend in front of a panelist, because every step of it can be
questioned and answered.

---

## 9. Phasing

Four commits, each one runnable and each one tested.

**Commit 1 — the clerk.** The two-axis procedure, the verdict vocabulary, the
grid, the authored statements and options. The **existing** pipeline feeds it:
the scan model still extracts, the verify model still reports what it reports
today.

**[CALL] The provisional establishment mapping for commits 1–3.** `confirmed`
is not reachable before commit 4, because nothing today fetches the employer's
own pages. So, for commits 1–3:

| Today's output | Establishment |
|---|---|
| a red Channel Match with escalation `government` or `lookalike` | `contradicted` |
| a red Channel Match with any other escalation | `contradicted` only if the mismatch is identity-level (the employer's own domain was retrieved and differs); otherwise `supported` |
| a green Company Existence or Official Registration | `supported` |
| anything else, including a yellow check | `unknown` |

This is enough to fix the CHED headline in commit 1, because the CHED case is
the `government` rule and that rule already exists in code today. A red
`Reputation` does **not** become `contradicted` — reputation is not a claim
about who is asking — so the panel does not become STOP-heavy.

**Commit 2 — the wire and the panel.** `riskScore`/`scoreBreakdown` removed,
the panel reads the new vocabulary, the status vocabulary collapses (§7.2),
the copy is rewritten, the resume-match list shows the verdict instead of a
percentage, and the history migration lands (§7.3).

**Commit 3 — the agentic loop.** `scan_flow.py` and `verification_flow.py` are
replaced by one agent session with the `search` and `fetch` tools, the posting
re-sent every turn, the limits in §4.4 enforced, the text protocol in §4.2
parsed. The procedure from commit 1 is unchanged and becomes the reader of the
agent's facts.

**Commit 4 — the establishment rules.** The `confirmed` / `supported` /
`unknown` / `contradicted` decision moves fully into code over the agent's
reported facts, the code-side check on the fetched text lands, and the
fake-site-with-a-real-name case (the identity question that `AGENTS.md`
contradiction #7 records as open) gets its own fixture.

Commit 3 without commit 4 leaves establishment mostly `unknown`, because
nothing fetches the employer's pages. Commit 4 before commit 3 has nothing to
read. The order is forced.

**The branch is `feat/verdict-procedure`, off `main`.** If the corpus shows a
regression, the branch is deleted and `main` is untouched. `main` stays
runnable in every commit above.

---

## 10. Tests

- The **offline suite stays offline.** `backend/tests/conftest.py`'s autouse
  fixture must fake the new fetch tool at the module boundary, and the
  session-scoped DNS guard must cover it. A fetch that escapes the fake is a
  test failure, not a surprise on a bill.
- `test_code_verdict.py` — rewritten against the grid. Every cell, and the
  materiality rule for contradictions.
- `test_channel_match_regressions.py` — the two permanent fixtures, with
  updated expectations: **Knollridges is CLEAR** (a free email is a fact, not a
  charge), **Fake CHED is STOP** with establishment `contradicted` and the
  impersonation in the statement, not the fee. The fixture's method — reading
  the headline out of the copy module rather than restating it — is kept.
- `test_risk_model.py` — deleted, with a tombstone. It recomputes the AHP
  weights.
- `backend/scripts/mutation_check.py` — re-pointed at the new rules: break the
  materiality rule, break the grid, break the binding, and assert a test
  catches each.
- `verdictCopy.test.ts` — the verdict → headline contract, restated for the
  new vocabulary, plus: **no verdict below `stop` tells the reader to stop.**
- A new fixture: a **real employer whose site does not list the role** and
  whose posting asks for nothing. That is the case contradiction #7 says is
  uncaught today, and it is the case the loop exists to catch.

**[OPEN 4] The corpus.** The acceptance criterion needs three things the design
does not yet have: a corpus (today `jobposts/` holds three images and one PDF
plus the stitch mockups), a "before" verdict per posting, and an ordering
across two vocabularies so that "worse" is checkable.

**[CALL] The ordering**, for the criterion to be checkable at all:

```
old:    low     <  moderate  <  high    <  critical
new:    note/clear <  caution   <  stop   <  stop
```

`low → clear` and `low → note` are the same position; `moderate → caution` is
a rename, not a worsening; `high` and `critical` both become `stop`. So
"**no posting may end up with a worse verdict than today**" means: a posting
that was `low` or `moderate` must not become `stop`, and a posting that was
`high` or `critical` must not become `clear` or `note`.

**[OPEN 4] the live question.** Producing the "before" column needs the live
model and live Tavily, and `AGENTS.md` forbids running anything that calls the
provider without explicit permission — including throwaway probe scripts,
because the key is shared. So the corpus run is either run live with the
reviewer's explicit go-ahead, or computed offline from fixtures. The author's
preference is offline first (the two permanent fixtures plus new ones), and
live only once the reviewer says so.

---

## 11. Non-goals

- **Proving fraud.** The product reports what was found. It does not conclude
  that anyone committed a crime, and it does not conclude that anyone is
  legitimate.
- **Profiling the employer.** No reputation score, no employer ranking, no
  history. The panel is about one posting.
- **Replacing the reader's judgement.** The verdict is the finding the reader
  acts on. The decision to apply is theirs.
- **A general-purpose agent.** The agent has two tools and one job. It is not a
  browser and it does not plan a research agenda.

---

## 12. Open questions

1. **The grid cells** — §3.4: `documents` + `unknown` (CAUTION or STOP),
   `money` + `confirmed` (CLEAR or NOTE), `money` + `supported` (NOTE or
   CAUTION); and §3.1: whether a posting with several exposures gets one
   verdict from the worst exposure (the author's call) or a compound row.
2. **The panel's information architecture** — §7.2: do the six claim
   categories survive as the grouping of the record with their statuses
   retired (the author's preference), or is the panel rebuilt around the
   record and the establishment state?
3. **The endpoint shape** — §5: `/api/scan` becomes the agent (a), a new
   `/api/assess` replaces both (b, the author's preference), or `/api/verify`
   is fed the scan's output (c, which reinstates the relay).
4. **The corpus run** — §10: live with the reviewer's explicit permission, or
   offline from fixtures.

Two further questions were raised by the builder check and are settled here as
the author's calls rather than left open: the fee reason does not change the
verdict (§3.5), and the statement is authored per cell with the specific fact
substituted (§7.1).

---

## 13. Files

**Backend — new**

- `backend/app/services/scanner/verdict.py` — rewritten. The procedure, the
  grid, the establishment rules.
- `backend/app/services/scanner/verdict_copy.py` — the authored statements and
  options, with the structured facts substituted.
- `backend/app/services/scanner/establishment.py` — new. The rules that turn
  the agent's reported facts into the four states.
- `backend/app/services/scanner/agent.py` — new. The loop, the tools, the
  limits, the transcript, the text-protocol parser.
- `backend/app/services/fetch.py` — new. The `fetch` tool, the SSRF guard, the
  untrusted-content framing.

**Backend — changed**

- `backend/app/services/scanner/prompts.py` — the scan prompt becomes the
  agent's first-turn prompt: charges, then tools. The `NO_ONLINE_ACCESS` wall
  applies to turn 0 only. `SCAN_FORMAT_BLOCK` gains the `FEE_REASON` slot.
- `backend/SYSTEM_PROMPT.md` — the source of truth the scan prompt's field
  rules live in; it gains `FEE_REASON` too, and the two copies must not drift.
- `backend/app/services/scanner/verification_prompt.py`,
  `backend/VERIFY_PROMPT.md` — the agent's output format and the facts schema.
  `verdict_reason` leaves the schema.
- `backend/app/services/scanner/verification_flow.py`,
  `scan_flow.py` — replaced by the loop.
- `backend/app/services/scanner/scan_result.py` — the scan response shape.
- `backend/app/services/scanner/channel_match.py` — the rules become the
  materiality rules for `contradicted`. The free-email rules stay, and now
  carry no weight.
- `backend/app/services/scanner/offer_flow.py`, `offer_prompt.py` — the offer
  path uses the same procedure.
- `backend/app/services/scanner/risk_calculator.py` — deleted.
- `backend/app/services/scanner/search_planner.py` — the query-safety filter
  becomes unconditional.
- `backend/app/services/lm_client.py` — multi-turn support, the tool-call text
  protocol, the "in `fixed` mode the prompt sentence is the only control"
  comment corrected three times.
- `backend/app/services/scanner/dependencies.py` — the runtime seam every flow
  resolves its collaborators through; the new modules join it.
- `backend/app/services/scanner/__init__.py` and
  `backend/tests/test_scanner_package.py` — the package's symbol list is
  pinned, `risk_calculator` is in it.
- `backend/app/routers/scan.py` — the endpoint shape (§5).
- `backend/app/models/schemas.py` — the verdict vocabulary, the new request
  and response shapes, `FEE_REASON` on `Anomaly`.
- `backend/app/config.py` — the four agent limits.
- `backend/app/services/anomaly_codes.py` — the family comment gains the
  exposure note and the `IMPERSONATES_AUTHORITY` note.

**Frontend**

- `entrypoints/sidepanel/components/report/verdictCopy.ts` — the verdict
  vocabulary, the options. Still authored, still looked up.
- `entrypoints/sidepanel/components/report/ActionBlock.tsx` — reads the
  options, not a directive.
- `entrypoints/sidepanel/components/report/VerdictBlock.tsx` — the chip and
  the statement.
- `entrypoints/sidepanel/components/report/WhatWeChecked.tsx`,
  `FullDetails.tsx`, `AnomalyCards.tsx`,
  `checkPresentation.ts` — the status vocabulary collapse (§7.2).
- `entrypoints/sidepanel/types/index.ts`, `lib/api.ts`,
  `lib/mapApiResponse.ts` — the wire.
- `entrypoints/sidepanel/lib/scoreBreakdown.ts` — deleted.
- `entrypoints/sidepanel/lib/riskDisplay.ts`, `riskAccent.ts` — renamed.
- `entrypoints/sidepanel/lib/scanHistory.ts` — the migration (§7.3).
- `entrypoints/sidepanel/views/ResumeMatchView.tsx` — the verdict instead of
  a percentage, and the filter categories (§14).

**Docs**

- `docs/decisions/verdict-procedure.md` — new decision record. The two axes,
  the grid, the materiality rule, the burden of proof, and why the score is
  gone.
- `docs/scoring.md`, `docs/decisions/scoring-model.md` — deleted.
- `docs/decisions/verification-design.md` — amended: the six categories
  survive as the record's grouping; their status vocabulary does not.
- `docs/decisions/search-retrieval.md` — amended: the conclusion-word filter
  becomes a code control in every mode, not only in `adaptive`.
- `docs/decisions/libel-guardrail.md` — amended: the burden of proof, and the
  rule that memory is not a source.
- `docs/architecture.md`, `Documentation.md`, `AGENTS.md` — updated;
  contradictions #3 and #5 closed, #6 and #8 given their new homes
  (`establishment.reason` and the agent transcript), #7 addressed by commit 4.
- `docs/gotchas.md` — the new traps.

---

## 14. Still to place

**The resume-match filter.** `ResumeMatchView.tsx` excludes `high` and
`critical` and includes only `low` (`isVerifiedJob`), and `JobFilterCategory`
is a stored union of `'verified' | 'suspicious' | 'risky' | 'low' |
'moderate' | 'high' | 'critical'`. The design replaces the percentage on the
list, but the exclusion rule is the behaviourally significant part and the new
vocabulary does not map onto it by inspection.

**[CALL]** `clear` and `note` are included in the match list, `caution` and
`stop` are excluded, and `JobFilterCategory` becomes
`'clear' | 'note' | 'caution' | 'stop'`. The old categories are migrated on
read: `low → clear`, `moderate → caution`, `high → stop`, `critical → stop`,
with the same note the history migration uses (§7.3). If the reviewer wants
`note` excluded as well — a reader who has seen a NOTE posting may not want to
see that employer again — that is a one-line change to the same call.

# Design — the assessment procedure, and the agentic loop that feeds it

Date: 2026-10-21
Status: draft for review (rev. 3, after the research and the reviewer's
answers on 2026-10-21)
Research: `docs/research/2026-10-21-assessment-grid-research.md`
Supersedes: `docs/scoring.md`, `docs/decisions/scoring-model.md`,
`docs/decisions/verification-design.md` (the category-status section),
the token-budget section of `docs/decisions/reasoning-models.md`,
`docs/superpowers/specs/2026-10-18-adaptive-verification-search.md`

Owner files: `backend/app/services/scanner/assessment.py`,
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

**The number is indefensible.** The assessment is computed as
`POSTING_SEVERITY_WEIGHTS` (40/12/4) plus `REFUTATION_WEIGHTS` (25/13/7/4/2/2),
summed, then banded into `low | moderate | high | critical`. A panelist asks
"where did you get that number?" and there is no answer, because there is
nothing in 37 that describes a posting. The weights price a *category*; the
posting is not a category. A Saaty matrix does not fix this — AHP needs a
fixed, commensurable variable set, and an unstructured job posting does not
have one. **The number comes out.**

**The context is lost in the relay.** The scan model reads the flyer and emits
fixed slots; the verify model never sees the flyer and reasons over a lossy,
model-chosen compression of it. So the fact that decided the assessment is often
not in the room when the assessment is written. In the Fake CHED fixture the
one-line reason names the fee ("It asks for a fee before it will accept an
application"), because the fee is what survived the compression — the
impersonation, which is the fact that matters, was never handed over. (The
assessment *headline* for `critical` is the fixed string "Do not proceed"; the
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
| **Clerk** | `assessment.py` | facts + rules | the assessment label, the exposure, the establishment state, the authored statement | write prose, or judge anything not on the record |
| **Judge** | the reader | the assessment, the record, the options | whether to apply | — |

Two rules fall out and are load-bearing:

1. **The agent never decides.** It reports what an exhibit says. The code
   decides what that means. This is the rule in
   `docs/decisions/libel-guardrail.md` — every statement traces to the input —
   and it is what `channel_match.py` and `assessment.py` already do for the
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

## 3. The assessment procedure

### 3.1 The class of the request — what shape is it?

**This section was rewritten on 2026-10-21 after the research.** The first
draft indexed the grid by *exposure* (money / documents / labour / none). The
research found that the exposure is the wrong axis: the Philippine rules
attach to the **shape** of a request, not to the category of what it takes.
A fee to the employer for a uniform is ordinary; a fee to an agency before a
contract is prohibited; a fee to a personal account is prohibited. All three
are "money".

The research note is `docs/research/2026-10-21-assessment-grid-research.md`. It
carries the citations (DMW, DOLE, POEA, NTC, CICC, DOLE Department Order
No. 141-14, DMW-DC-01-2023, TESDA Circular 023-2020, RA 10173 §11(d), NPC
Advisory Opinion 2019-034, and Axelsson's base-rate result) and the derivation.

So the primary axis is the **class of the request**, decided from facts on the
face of the posting:

| Class | Test | Weight |
|---|---|---|
| **ordinary** | a shape the rules permit and Philippine hiring does routinely: a free email address, an application through a messenger, the ordinary applicant packet (résumé, 2×2 photo, transcript, NBI clearance, medical results), a uniform or medical cost charged by the employer, no experience needed, no formal process | no charge |
| **cannot be classified** | the shape is real but the facts that decide it are not stated — a fee whose recipient is not stated, a meeting place that is not named | a question |
| **prohibited** | a shape the rules forbid: a fee charged by a recruitment agency before a contract (DOLE DO 141-14 §35; DMW §56, §59), a fee paid to a personal account or remittance centre (POEA Advisory 62), account credentials before hiring (RA 10173 §11(d) — not excessive for the purpose), documents routed through a third party, impersonation, payment pass-through, task-for-earning | a charge |

**Three taxonomy changes follow from the research**, and they are not optional
— the classes cannot be decided without them:

1. **`CREDENTIALS_BEFORE_INTERVIEW` splits.** The code currently covers
   "identification, bank details or passwords". Those are not alike here:
   asking for the ordinary applicant packet is ordinary Philippine practice
   (PESO checklists; the pre-employment packets employers publish), and asking
   for bank details, an e-wallet number, an OTP or a password before hiring is
   the mechanism by which an applicant becomes a mule account. The code becomes
   `APPLICATION_DOCUMENTS` (ordinary) and `ACCOUNT_CREDENTIALS` (prohibited).
2. **Two facts are extracted that were not.** `FEE_RECIPIENT`
   (`employer | agency | third party | individual account | not stated`) and
   `FEE_TIMING` (`before hiring | at hiring | after a contract | not stated`).
   These two decide the money class, and they are facts, not judgements.
   `FEE_REASON` — the reason the posting gives — is extracted as a third fact
   and appears in the statement; it does not decide the class.
3. **`MEETING_SPOT` gains a nature.** "A named place" is not enough. The rule
   the research found is about whether the transaction happens at the
   employer's registered premises: DMW-CAR calls meetings, interviews and
   payments in malls, restaurants, private homes or chat platforms "clear
   signs of illegal activity" where an agency is involved.
4. **`DOCUMENTS_VIA_THIRD_PARTY` stops covering free email.** The corpus
   measured the model using this code for "the posting uses a Gmail address"
   — the code means "through a domain or account that is **not the employer's
   own**", and a free-provider address is not a *third party*, it is the
   absence of a domain. A free address belongs to the ordinary class; the
   code is for documents routed through somebody else's named account.
5. **`OTHER` stops being a severity carrier.** The corpus measured `OTHER` at
   `mid` on four legitimate postings, for "grocery bags for walk-ins", "be
   there at 7am", and a gender preference. `OTHER` is the escape valve for a
   finding whose shape is not in the set; it cannot also be a charge, because
   the charge is defined by the shape. `OTHER` becomes a *finding* with no
   class, and the assessment follows the class of everything else in the posting.
   If everything in the posting is `OTHER`, the posting's class is *cannot be
   classified* and the assessment is a question.

`IMPERSONATES_AUTHORITY` is not a class of request at all. It is a claim
about *who is asking*, and it is read as an establishment signal (§3.3); it
contributes no request class of its own. The family comment in
`anomaly_codes.py` gets a note saying so.

**[CALL] A posting can carry more than one request.** The grid is indexed by
the **worst** class present, in the order `prohibited > cannot be classified >
ordinary`, because a prohibited shape is a charge whatever else is in the
posting. The statement lists all of them.

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

### 3.3 Establishment is a rule over facts, never a model assessment

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
   with the mismatch recorded. The corpus measured what the opposite rule
   costs: a 600-store franchise's posting naming one branch produced a **red**
   `Location / Branch` card, because the company's own page listed a different
   venue.

   **[CALL] The government case survives the citation binding.** This is a
   defect the corpus measured, not a refinement. `assess_channel_match`
   returns `red`/`government`/`strong` for the Fake CHED facts — the posting
   made the claim and the posting supplied the domain, so the rule needs no
   retrieved source, as its own comment says. `_bind_to_retrieved` then
   demotes it to `yellow` because the cited `https://ched.gov.ph` was not in
   the retrieved set, and the strong-channel floor never applies. The
   impersonation was detected, written out on the card in plain words ("That
   is outside the .gov.ph domain"), and scored **zero**; the assessment rested
   entirely on the two fees. The binding's rule is right for a claim about an
   employer's identity and wrong for a claim the posting makes about itself,
   so the government branch is exempted from it. The reproduction is in
   `docs/research/2026-10-21-corpus-baseline.md` §5 and §10.
2. `confirmed` when (i) and (ii) hold. **(ii) is checked by code against the
   fetched text** — the fetched page must contain the role title (or the fee
   amount), case-insensitively — not by the model's boolean. A model-proposed
   excerpt that does not contain the thing does not establish it.
3. `supported` when (i) holds and nothing contradicts.
4. `unknown` otherwise.

**`unknown` is never punished on its own.** It is the state of a small
employer with no web footprint, which is the ordinary case for the people this
product exists for. In the research-backed grid it never, by itself, produces
anything above a question. *Reconciliation with the standing rule:* "absence is
never red" is not violated — `unknown` produces no red, no charge, and no
accusation; it is a fact, and the fact that a small employer cannot be looked
up is not a finding about them. The base-rate constraint is the reason it is
not punished: a rule that fires on "the employer has no website" fires on
ordinary life, and a panel that cries wolf teaches its reader to ignore it
(Axelsson 2000).

A finding the employer's own record accounts for is **retired** — the existing
`stale` rule, unchanged in meaning, and re-expressed in the new vocabulary
(§7.2).

### 3.4 The grid

Authored. Hand-written. Not computed, and not a function of any number.

| Exposure | `confirmed` | `supported` | `unknown` | `contradicted` |
|---|---|---|---|---|
| `none` | CLEAR | CLEAR | CLEAR | **STOP** |
| Class of the request | `confirmed` | `supported` | `unknown` | `contradicted` |
|---|---|---|---|---|
| ordinary only | CLEAR | CLEAR | CLEAR | **STOP** |
| cannot be classified | NOTE | NOTE | NOTE | **STOP** |
| prohibited | NOTE | CAUTION | CAUTION | **STOP** |

**The cells are settled by the research, not by taste.** The derivation and
the citations are in `docs/research/2026-10-21-assessment-grid-research.md` §6;
the reasoning is:

- **`contradicted` is the only path to STOP, and it requires a retrieved
  official source.** This is the reviewer's "ace card" rule — "Do not
  proceed" is said only on hard evidence — and it is what the base-rate
  constraint demands: the strongest output needs the hardest evidence.
- **A prohibited shape with a `confirmed` counterparty softens to NOTE**,
  because the reader can go and see the thing on the employer's own site and
  judge it themselves.
- **`unknown` never, on its own, produces anything above a question.** NTC
  lists "companies that cannot be found online" as a red flag, and the panel
  reports it — as a fact in the record, not as an alarm. The base-rate
  argument is decisive here: a large minority of legitimate Philippine
  employers are small and have no website, so a rule that fires on that fires
  on ordinary life. Axelsson's result is the reason: a low posterior detection
  rate "would quickly teach the [user] to safely ignore all alarms".
- **CAUTION is reserved for the prohibited class alone.** That is what keeps
  it from becoming common, and it is the whole fix for the false-caution
  flood: the old system produced cautions out of a free email and an ordinary
  finding, because it had no rule for what is ordinary.

The four worked examples, from the research note:

| Posting | Class | Establishment | Assessment |
|---|---|---|---|
| Real employer, Gmail address, no demands | ordinary | supported | CLEAR |
| Employer charges ₱500 for a uniform, stated | ordinary | unknown | CLEAR |
| Agency asks ₱1,500 before hiring, paid to a personal account | prohibited | unknown | CAUTION |
| Fake CHED — claims to be CHED Region VI, gives `chred-region6.org`, asks for fees | prohibited **and** contradicted | contradicted | **STOP** |

The last row is the one the reviewer asked about: the impersonation wins,
because `contradicted` is the only path to STOP and it is the fact the reader
needs. The fees are in the record and are not in the headline.

**[OPEN 1] is closed.** The three cells the reviewer would not sign off on
are decided by published rules and by the base-rate constraint, and the
reasoning is written down rather than asserted.

### 3.5 A CLEAR assessment is a statement about the posting, not about the employer

A CLEAR assessment never says the employer is safe, and it never says the posting
asks for nothing if it does. A posting that asks for a ₱500 uniform is CLEAR
and its statement says so: "They ask for ₱500 for a uniform, and nothing else
before you start." The statement is a statement about the posting, and every
word of it has to be true of the posting.

This is why the statement is rendered from the record (§7.1) rather than
written per cell as a fixed sentence. A fixed CLEAR sentence would be false
for the uniform-fee posting, and a false statement on the panel is the one
thing the libel guardrail cannot tolerate.

---

## 4. The agentic loop

### 4.1 Why the loop

The scan→verify relay exists because two models were cheaper than one. The
cost was the compression, and the compression is where the context died. One
agent that holds the posting for the whole proceeding has no relay and so no
hop where context can be lost.

The loop is **not** "let the model be clever". It is one job: **establish
whether the employer is `confirmed`, `supported`, or `contradicted`.** That is
the fact the assessment needs and the fact the current pipeline cannot produce,
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
- It may not state a assessment, a level, or a conclusion about the employer.
- **It may not use its own memory as a source.** A claim it believes from
  training is not on the record and cannot be bound to a retrieved URL, so it
  carries no weight. Memory shapes *what to search for*; retrieval is what
  establishes a fact. A model that "knows" CHED's domain is `ched.gov.ph`
  still has to fetch it, and if it cannot, the establishment state is
  `unknown`, not `confirmed`.

---

## 5. The wire

The assessment vocabulary replaces the level vocabulary. `low | moderate | high |
critical` becomes:

```
clear | note | caution | stop
```

Plus the state that already exists and is not a assessment: **no assessment** (grey)
— the posting named no employer, or the answer could not be read.

The number and its machinery leave the wire entirely:

| Removed | Replaced by |
|---|---|
| `riskScore`, `riskScored` | `assessment` (the label) |
| `scoreBreakdown` | `assessmentBreakdown` — the exposure, the establishment state, the rule that fired, and the record |
| `riskLevel` (wire key and `VerificationResult` field) | `assessment` |

`assessmentBreakdown` is not a score. It is the clerk's record of how the assessment
was reached:

```json
{
  "assessment": "caution",
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
makes the assessment auditable without a number: it says which fact decided it.

**[SETTLED 2026-10-21] The endpoint shape is (b): a new `/api/assess`
replaces both, and `/api/scan` and `/api/verify` are deleted.** The three
shapes that were on the table:

- **(a)** `/api/scan` becomes the agent endpoint and `/api/verify` is deleted.
  The extension makes one call. The scan is image-only in practice today
  (`architecture.md`: "Scans are always screenshots"; `scanTextStream` is
  exported but has no caller), so the agent's first turn is a vision turn.
- **(b)** A new `/api/assess` endpoint replaces both, and `/api/scan` and
  `/api/verify` are deleted. Same product behaviour, a name that says what it
  is.
- **(c)** `/api/verify` becomes the agent endpoint and is fed the scan's
  parsed output — which reinstates the relay the design exists to remove.

**The reviewer chose (b)**: the endpoint name should say what it does, and a
new name makes the deletion of the old pair a deliberate act rather than a
silent overwrite. `(a)` was smaller and equally honest, and remains a one-line
change to the same decision if the reviewer changes their mind.

Consequences that travel with the choice: `useScanSession.startVerification`
fires the verify only after the scan returns, so the two-phase loading state
collapses into one; `verificationLoading`, `CompanyNameNeeded`,
`ScanResponse`, the offer path and `verification_context` all move; and the
extension makes one call instead of two.

---

## 6. The agent's output

The agent's final answer is structured, not prose, and the code reads it:

```json
{
  "valid": true,
  "findings": [
    {"label": "...", "reasoning": "...", "code": "FEE_MANDATORY",
     "quote": "...", "fee_reason": "medical clearance",
     "fee_recipient": "employer", "fee_timing": "before hiring"}
  ],
  "attributes": {"company": "...", "job_title": "...", "location": "...",
                 "claimed_type": "...", "channels": [{"type":"email","value":"..."}],
                 "pay": "...", "registered_as": "...",
                 "meeting_spot": {"value": "...", "nature": "employer premises | elsewhere | not stated"}},
  "employer_record": {
    "domain": {"value": "knollridges.com.ph", "source_url": "https://knollridges.com.ph"},
    "pages": [{"title": "...", "url": "...", "snippet": "..."}],
    "lists_role": {"excerpt": "...", "source_url": "..."},
    "states_terms": {"excerpt": "...", "source_url": "..."}
  },
  "record": [ {"claim": "...", "source_title": "...", "source_url": "..."} ]
}
```

The `fee_recipient`, `fee_timing` and `meeting_spot.nature` fields are the
three facts the research added (§3.1). They are the difference between a fee
that is ordinary and a fee that is prohibited, and they are extracted as
facts — the code decides what they mean.

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

### 7.1 The assessment, the statement, the options

Three slots, and they are different in kind:

1. **The assessment** — the label, in a chip: CLEAR / NOTE / CAUTION / STOP.
2. **The statement** — one sentence naming what was found, in the reader's
   terms.
3. **The options** — what the reader can do about it.

**"Do not proceed" is the ace card.** It is the assessment headline for `stop`
only, and `stop` requires `contradicted` — hard evidence, like the Commission
on Higher Learning not being CHED. It is not said for a caution. A product
that says it for everything says it for nothing.

For the other assessments the statement is evidentiary, because the reader is the
judge. Every statement has **two parts** — what the posting asks for, and what
the record showed — because a statement that says only the second is not
actionable and one that says only the first is not evidence:

| Assessment | Statement shape |
|---|---|
| CLEAR | "They ask for ₱500 for a uniform, and nothing else before you start." |
| NOTE | "They ask for ₱1,500 and do not say who it is paid to. Their site lists this role, but not that fee." |
| CAUTION | "They ask you to pay ₱1,500 to a personal account before you start, and we could not find a record of this agency." |
| STOP | "This posting is not from the employer it names." |

The first part is rendered from the finding's structured facts (the amount, the
fee's recipient, the reason if stated, what kind of documents). The second is
rendered from the establishment state. Neither is written by the model.

The options block is authored per assessment family and offers the reader's
choices — ask for something in writing, meet at an address they give you, do
not send money or documents before you have spoken to someone — in the shape
`VERIFY_PROMPT.md` already describes for the recommendation. It does not decide
for the reader; it tells them what the stakes are and what they can do.

**[CALL] The statement is rendered by the backend**, from an authored template
module, with the structured facts substituted. `assessmentCopy.ts`'s rule is that
every word is authored in code and looked up — and a template with the amount
and the fee reason substituted is still authored, because the substituted
values are structured facts off the record (`amount` from the posting's own
`PAY` attribute, `reason` from `FEE_REASON`), not model prose. Rendering it
on the backend keeps the substitution next to the binding that guarantees the
facts came from the record, and it keeps the frontend from having to trust a
number it did not compute. `assessmentCopy.ts` keeps the assessment→label mapping
and the options block. The backend module is `backend/app/services/scanner/assessment_copy.py`.

The model's own `assessment_reason` field — the current one-line reason, which is
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
status beside a code-owned establishment state would be two assessments in one
panel, and they will disagree.

`stale` survives in meaning and is renamed for the new vocabulary: a finding
the employer's own record accounts for is **retired** — it is not shown as a
finding, and it does not count toward the exposure. `assessment.py`'s
`_without_stale` keeps its rule and changes its input: it consumes the
agent's per-finding status rather than a separate assessment list.

**[SETTLED 2026-10-21] The panel's information architecture is the first
option: the six claim categories survive as the grouping of the record, and
their green/yellow/red statuses retire onto the four states.** The reviewer
took the author's preference.

### 7.3 Naming

The product's output is a **assessment**, not an assessment. An assessment is
advisory; a assessment is the finding the reader acts on. `docs/architecture.md`,
`Documentation.md`, the panel copy, and the identifiers that carry the word
get renamed.

**[CALL] The rename is complete, not cosmetic.** `ScanRiskLevel`, `riskLevel`,
`riskLabel`, `riskDisplay.ts`, `riskAccent.ts`, `riskLevelLabel`,
`mapApiResponse.riskScored`, `isUnverifiedEmployer`, the `risk_score` /
`risk_level` wire keys, and the history keys all move to the assessment
vocabulary. The user said "assessment, rather assessment" and a thesis reads
better when the code says what the product says. It is mechanical churn and it
is contained.

**[CALL] Stored history is migrated, not re-derived.** Old scans carry a level
and no exposure and no establishment, so a new assessment cannot be computed from
them. `scanHistory.ts` gets a migration that maps the old level onto the old
label and renders it with a note that it was recorded under the previous
procedure. A stored scan is never silently re-labelled as a new assessment.

### 7.4 What the panel must not say

- It must not say the employer is safe, legitimate, real, or genuine. The
  assessment is about the posting, not about the employer's character. `unknown`
  is not a soft yes.
- It must not accuse. No "scam", "fake", "fraudulent", "suspicious" beside a
  named employer. `contradicted` is a comparison between the posting and a
  retrieved source, and the panel says so in those terms.
- It must not show a number. There is no number.

---

## 8. What dies

| Removed | Note |
|---|---|
| `risk_calculator.py` | the weights, the bands, `_combine_scores`, `_level_for`. The whole file. It is **live** today — resurrected on 2026-10-21 as the arithmetic behind `assessment.py`, and recorded as live in `AGENTS.md` contradiction #3 — so its removal is a second reversal, and both `AGENTS.md` and `docs/decisions/scoring-model.md` get a line saying so and why. |
| `docs/scoring.md` | the bands, the AHP derivations, the anchor, the sensitivity analysis. Superseded by `docs/decisions/assessment-procedure.md`. |
| `docs/decisions/scoring-model.md` | superseded. |
| `backend/scripts/derive_refutation_weights.py` | deleted, with a tombstone test. |
| `POSTING_SEVERITY_WEIGHTS`, `REFUTATION_WEIGHTS`, `MAX_REFUTATION_SCORE` | with the file. |
| `riskScore`, `riskScored`, `scoreBreakdown` on the wire | replaced by `assessment` and `assessmentBreakdown`. |
| `entrypoints/sidepanel/lib/scoreBreakdown.ts` | deleted, with a tombstone test. |
| "40% Risk" in `ResumeMatchView.tsx` | shows the assessment label instead. |
| `RISK_LEVELS` | replaced by the assessment vocabulary. |
| the model's `severity` field | display only. The code carries the meaning. The exposure axis and the grid replace the 40/12/4 ladder. |
| `offer_prompt.py`'s model-owned `risk_level` | the offer path gets the same procedure. It has no employer, so establishment is `unknown` by construction and exposure carries the whole assessment. This closes contradiction #5 in `AGENTS.md`. |
| `verification_prompt.py`'s `assessment_reason` | retired (§7.1). |
| `VerificationItem.status` (green/yellow/red) | retired in favour of the four states (§7.2). |
| `CREDENTIALS_BEFORE_INTERVIEW` | **split** into `APPLICATION_DOCUMENTS` (ordinary) and `ACCOUNT_CREDENTIALS` (prohibited). §3.1, and the research note §4. |
| `FEE_REASON`, `FEE_RECIPIENT`, `FEE_TIMING` | new extracted facts, on the finding and in the attributes (§3.1). |

**`docs/scoring.md` is deleted, not rewritten.** The AHP work is not wrong; it
answers a question this product no longer asks. The thesis claim changes from
"a weighted score over indicators" to "an auditable decision procedure over
observed facts, with the burden of proof on the charge" — which is a stronger
claim to defend in front of a panelist, because every step of it can be
questioned and answered.

---

## 9. Phasing

Four commits, each one runnable and each one tested.

**Commit 1 — the clerk.** The two-axis procedure, the assessment vocabulary, the
grid, the authored statements and options. The **existing** pipeline feeds it:
the scan model still extracts, the verify model still reports what it reports
today.

The taxonomy changes from the research (§3.1) land here too, because the grid
cannot be implemented without them: `CREDENTIALS_BEFORE_INTERVIEW` splits,
`DOCUMENTS_VIA_THIRD_PARTY` stops covering free email, `OTHER` stops carrying
a severity, and `FEE_REASON` / `FEE_RECIPIENT` / `FEE_TIMING` and
`meeting_spot.nature` are extracted. That is a prompt change and a parser
change, and it is the part of commit 1 that needs the corpus to validate — a
misclassified fee recipient is a misclassified charge, and a misclassified
charge on a legitimate posting is exactly the cry-wolf failure the grid exists
to prevent.

**The citation-binding demotion is fixed in this commit too, and it is the
first thing in it.** The corpus measured a 2-in-10 false-positive rate on
legitimate postings and an unscored impersonation on the flagship forgery
(`docs/research/2026-10-21-corpus-baseline.md`). Both are one-line changes in
the code that stands behind them — a split and an exemption — and both are
worth having even if the rest of the design is abandoned. The regression
fixture for the demotion is the Fake CHED facts **without** a retrieved
`ched.gov.ph`, which is the case the existing fixture cannot reach because it
supplies that URL by hand.

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
the copy is rewritten, the resume-match list shows the assessment instead of a
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

**The branch is `feat/assessment-procedure`, off `main`.** If the corpus shows a
regression, the branch is deleted and `main` is untouched. `main` stays
runnable in every commit above.

---

## 10. Tests

- The **offline suite stays offline.** `backend/tests/conftest.py`'s autouse
  fixture must fake the new fetch tool at the module boundary, and the
  session-scoped DNS guard must cover it. A fetch that escapes the fake is a
  test failure, not a surprise on a bill.
- `test_code_assessment.py` — rewritten against the grid. Every cell, and the
  materiality rule for contradictions.
- `test_channel_match_regressions.py` — the two permanent fixtures, with
  updated expectations: **Knollridges is CLEAR** (a free email is a fact, not a
  charge), **Fake CHED is STOP** with establishment `contradicted` and the
  impersonation in the statement, not the fee. The fixture's method — reading
  the headline out of the copy module rather than restating it — is kept.
- **A third fixture, and it is the one the existing two cannot reach:** the
  Fake CHED facts **without** a retrieved `https://ched.gov.ph`. The existing
  fixture mocks the search to return that URL, so the citation binds and the
  red survives — the flagship case passes because the test hands the system the
  evidence the pipeline failed to find. The corpus baseline §5 shows the live
  pipeline demotes the same facts to yellow and scores the impersonation zero.
  The regression asserts that the government branch survives the citation
  binding.
- **A corpus regression.** The eleven legitimate postings in `jobposts/` and
  the assessments in `docs/research/2026-10-21-corpus-baseline.md` §3 are the
  acceptance baseline: no legitimate posting may reach `stop` or `caution`,
  and every assessment change is explained by a named rule. The baseline is a
  document, not a test — the postings are images and the assessments came from
  live runs — so the regression is over *fixtures* transcribed from the
  corpus, with the corpus itself re-measured by hand when the procedure
  changes.
- `test_risk_model.py` — deleted, with a tombstone. It recomputes the AHP
  weights.
- `backend/scripts/mutation_check.py` — re-pointed at the new rules: break the
  materiality rule, break the grid, break the binding, and assert a test
  catches each.
- `assessmentCopy.test.ts` — the assessment → headline contract, restated for the
  new vocabulary, plus: **no assessment below `stop` tells the reader to stop.**
- A new fixture: a **real employer whose site does not list the role** and
  whose posting asks for nothing. That is the case contradiction #7 says is
  uncaught today, and it is the case the loop exists to catch.

**[OPEN 1] the corpus.** The acceptance criterion needs three things the design
does not yet have: a corpus (today `jobposts/` holds two job postings — the
Fake CHED flyer and one screenshot — and one PDF that is a reference document
rather than a posting), a "before" assessment per posting, and an ordering
across two vocabularies so that "worse" is checkable.

**[CALL] The ordering**, for the criterion to be checkable at all:

```
old:    low     <  moderate  <  high    <  critical
new:    note/clear <  caution   <  stop   <  stop
```

`low → clear` and `low → note` are the same position; `moderate → caution` is
a rename, not a worsening; `high` and `critical` both become `stop`. So
"**no posting may end up with a worse assessment than today**" means: a posting
that was `low` or `moderate` must not become `stop`, and a posting that was
`high` or `critical` must not become `clear` or `note`.

**[CALL] the live run is permitted.** The reviewer granted permission on
2026-10-21 for live provider calls, up to about twenty runs today, so the
"before" column can be produced against the running system rather than
guessed. Two things follow from the grant and are conditions on it:

- The Tavily budget is spent by these runs. A verification costs one to three
  credits and the free tier is 1,000 per month, so twenty runs cost at most
  sixty credits. The runs are also the only thing that will produce a
  false-positive *rate*, and the rate is what §3.4's soft edges are argued
  from.
- **The corpus is the binding constraint, not the budget.** A rate measured on
  two postings is not a rate. The corpus needs mostly *legitimate* postings —
  real small employers, Gmail addresses, ordinary notices, a uniform fee, an
  ordinary applicant packet — because the thing being measured is the false
  positive, and the false positive only appears on legitimate postings. The
  reviewer offered to add postings to `jobposts/`; that is the next task, and
  it is worth more than the twenty runs.

---

## 11. Non-goals

- **Proving fraud.** The product reports what was found. It does not conclude
  that anyone committed a crime, and it does not conclude that anyone is
  legitimate.
- **Profiling the employer.** No reputation score, no employer ranking, no
  history. The panel is about one posting.
- **Replacing the reader's judgement.** The assessment is the finding the reader
  acts on. The decision to apply is theirs.
- **A general-purpose agent.** The agent has two tools and one job. It is not a
  browser and it does not plan a research agenda.

---

## 12. Open questions

**Two of the four are closed.** The grid cells (§3.4) are settled by the
research and by the base-rate constraint — see
`docs/research/2026-10-21-assessment-grid-research.md` — and the panel's
information architecture (§7.2) and the endpoint shape (§5) were settled by
the reviewer on 2026-10-21. What remains:

1. **The controlled-pair corpus** (§10). The "before" column is measured —
   `docs/research/2026-10-21-corpus-baseline.md` — and it found a 2-in-10
   false-positive rate on legitimate postings and an impersonation that is
   detected and then scored zero. What the corpus cannot do is measure the
   true-positive side: **no legitimate posting in it asks for money**, so the
   prohibited class has exactly one member. The pairs in the baseline §8 are
   the way to fix that, and they are the reviewer's own method — the Fake CHED
   flyer is an edited real posting, and controlled editing makes the ground
   truth true by construction. The pairs that matter are A/B (the same fee,
   two shapes) and C/D (the same document family, two classes).
2. **Copy at the class boundaries** (§7.1). A fee paid to a licensed agency at
   exactly the statutory one-month cap, after a signed contract, is lawful
   (DMW §56). Whether the panel says so or simply has nothing to say is a
   copy question rather than a rule question, and it belongs with whoever
   writes the final words.
3. **A caution the reader can act on.** The research says the CAUTION class is
   reserved for the prohibited shapes, which are rare by construction. That
   makes the CAUTION assessment meaningful — and it also means the *options*
   block for a CAUTION has to carry the weight: what exactly is the reader
   supposed to do about "a fee to a personal account before you start"? The
   options are authored (§7.1), and this is a design question for them.

Questions raised by the builder check and settled here as the author's calls:
the fee reason does not change the assessment (§3.5), the statement is authored
per cell with the specific facts substituted (§7.1), and the wire's
`VerificationResult` type is a frontend type while the wire key is
`riskLevel` inside the SSE payload (§5).

---

## 13. Files

**Backend — new**

- `backend/app/services/scanner/assessment.py` — rewritten. The procedure, the
  grid, the establishment rules.
- `backend/app/services/scanner/assessment_copy.py` — the authored statements and
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
  `assessment_reason` leaves the schema.
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
- `backend/app/models/schemas.py` — the assessment vocabulary, the new request
  and response shapes, `FEE_REASON` on `Anomaly`.
- `backend/app/config.py` — the four agent limits.
- `backend/app/services/anomaly_codes.py` — the family comment gains the
  exposure note and the `IMPERSONATES_AUTHORITY` note.

**Frontend**

- `entrypoints/sidepanel/components/report/assessmentCopy.ts` — the assessment
  vocabulary, the options. Still authored, still looked up.
- `entrypoints/sidepanel/components/report/ActionBlock.tsx` — reads the
  options, not a directive.
- `entrypoints/sidepanel/components/report/AssessmentBlock.tsx` — the chip and
  the statement.
- `entrypoints/sidepanel/components/report/WhatWeChecked.tsx`,
  `FullDetails.tsx`, `AnomalyCards.tsx`,
  `checkPresentation.ts` — the status vocabulary collapse (§7.2).
- `entrypoints/sidepanel/types/index.ts`, `lib/api.ts`,
  `lib/mapApiResponse.ts` — the wire.
- `entrypoints/sidepanel/lib/scoreBreakdown.ts` — deleted.
- `entrypoints/sidepanel/lib/riskDisplay.ts`, `riskAccent.ts` — renamed.
- `entrypoints/sidepanel/lib/scanHistory.ts` — the migration (§7.3).
- `entrypoints/sidepanel/views/ResumeMatchView.tsx` — the assessment instead of
  a percentage, and the filter categories (§14).

**Docs**

- `docs/research/2026-10-21-assessment-grid-research.md` — the research behind
  §3.1 and §3.4: the Philippine red-flag taxonomy, the legal tests, the
  base-rate argument, and the citations.
- `docs/research/2026-10-21-corpus-baseline.md` — the measured "before"
  column for the thirteen postings in `jobposts/`, the false-positive rate,
  the unscored Fake CHED impersonation and its reproduction, and the
  controlled-pair corpus the true-positive side needs.
- `docs/decisions/assessment-procedure.md` — new decision record. The two axes,
  the grid, the materiality rule, the burden of proof, and why the score is
  gone.
- `docs/scoring.md`, `docs/decisions/scoring-model.md` — deleted.
- `docs/decisions/verification-design.md` — amended: the six categories
  survive as the record's grouping; their status vocabulary does not.
- `docs/decisions/search-retrieval.md` — amended: the conclusion-word filter
  becomes a code control in every mode, not only in `adaptive`.
- `docs/decisions/libel-guardrail.md` — amended: the burden of proof, and the
  rule that memory is not a source.
- `docs/superpowers/specs/2026-10-17-anomaly-code-set.md` — amended: the
  split of `CREDENTIALS_BEFORE_INTERVIEW`, and the §7 note that the fee
  question is now closed by the research rather than left open.
- `docs/architecture.md`, `Documentation.md`, `AGENTS.md` — updated;
  contradictions #3 and #5 closed, #6 and #8 given their new homes
  (`establishment.reason` and the agent transcript), #7 addressed by commit 4.
  `AGENTS.md`'s documentation map gains a row for `docs/research/`.
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

# Anomaly Code Set — draft

**Date:** 2026-10-17
**Status:** draft for review. Nothing here is implemented.
**Replaces:** the `high`/`mid`/`low` severity ladder in `SYSTEM_PROMPT.md` §2.
**Grounding:** 4 anomaly labels emitted across 3 real postings (`scan_cache.json`),
the current prompt's own closure rules, and the session's literature findings.
See **Limits** at the end — the evidence base is small and this says so.

---

## 1. What this is for

The 0–100 score is retired. What replaces it must do two jobs at once:

1. **Be comparable across runs**, so Phase 6.2 can measure verdict stability and
   Phase 6.5 can act as a regression gate.
2. **Be legible to a job seeker**, so Phase 7.1 can lead with reasons a reader
   can act on.

A free-text phrase fails (1). A bare number fails (2). The resolution is two layers:
an **authored, closed code set** that the machine and the test set compare, and
**one short sentence** generated from it that the reader sees.

The wording of every phrase is *authored, not generated*, so it cannot drift
between runs. This is `oldPlan.md` §1.2 — "each red flag with an ID, a definition,
and a weight" — with the weight removed and the definition kept. The ID turns out
to be the part that matters: it is what the gold set gets labeled with.

---

## 2. The finding that shaped this

From `scan_cache.json`, the Philippine Air Force posting produced exactly one
anomaly:

> **Claims non-government domain is official portal** — severity `low`
> *"directs applicants to `paf-recruitment-portal.ph`, calling it the 'official
> online portal' for submitting documents, but it is a commercial domain"*

A portal impersonating a government agency, **collecting identity documents**,
scored **4 points**, because `SYSTEM_PROMPT.md:51` reserves `high` for money or a
scam mechanic and `mid` for task-for-earning. There is no rung for authority
impersonation.

This is a **false negative constructed by the ladder**, and it is more consequential
than the original complaint about unusual Facebook posts. It is also why those
posts feel odd: the findings that *do* fire are mostly form-based and land on
`low`, while a genuinely serious finding has nowhere to go.

Second observation, same file. The CHED posting emitted two `high` anomalies:

> Asks for an application processing fee — ₱1,500, **mandatory**
> Asks for a seminar registration fee — ₱800, **refundable**

Identical severity, materially different asks. A mandatory non-refundable fee and a
fee returned on completing a seminar are different requests to the reader.

Third observation: `SYSTEM_PROMPT.md:53` says *"low: Rarely correct. If you are
weighing a low, weigh reporting nothing instead."* The Air Force model emitted a
`low` anyway. So the rung is being used for something the ladder does not describe.

---

## 3. Organisation: by what the reader gives up

Organising by scam *type* produces a taxonomy that needs a new entry for every new
scheme. Organising by **what the posting asks the reader to part with** produces a
small, stable set, and it is the harm axis the plan already commits to — `§6.3`
weights false negatives above false positives because a missed scam costs the
reader far more.

### Family M — money

The reader loses funds.

| ID | Phrase | Definition |
|---|---|---|
| `FEE_MANDATORY` | Asks for a fee before starting work | A fee the applicant must pay to be considered or to start, stated as non-refundable. |
| `FEE_CONDITIONAL` | Asks for a fee returned on a later condition | A fee refunded on some later event — completing a seminar, passing, being hired. The refund is stated or clearly implied. |
| `PURCHASE_REQUIRED` | Asks you to buy something to start | Equipment, a uniform, materials, or a kit bought before work begins. |
| `DEPOSIT_REQUIRED` | Asks for a deposit to hold the role | A deposit or security bond to reserve a position. |
| `PAYMENT_FORWARDING` | Asks you to handle other people's money | Receive, pass on, withdraw, or bank money on someone else's behalf. |

### Family I — identity

The reader loses accounts or personal data. **This is the family the ladder had no
rung for.**

| ID | Phrase | Definition |
|---|---|---|
| `CREDENTIALS_BEFORE_INTERVIEW` | Asks for your ID or bank details before an interview | Government ID, bank details, passwords, or similar, requested before any interview or offer. |
| `DOCUMENTS_VIA_THIRD_PARTY` | Asks you to send documents to a third-party address | Identity or personal documents submitted through a domain, address, or account that is not the employer's own. |
| `IMPERSONATES_AUTHORITY` | Presents itself as an organisation it is not | Claims to be a government agency, the armed forces, or a named company, through a channel or domain it does not control. |

### Family C — labour sold as the product

| ID | Phrase | Definition |
|---|---|---|
| `TASK_FOR_EARNING` | Pays per task rather than for a role | Discrete tasks, orders, or referrals completed for payment, rather than a role with duties. The unit of work is the task or the earning event. |

*Work followed by payment is the ordinary order and is not a finding. The unit of
work is what separates this — a task, not a role.*

### Family E — the employer's substance

Emitted by **verification**, not the scan. The scan cannot see these; only a lookup
can. Listed here so the gold set has one vocabulary across both stages.

| ID | Phrase | Stage | Definition |
|---|---|---|---|
| `EMPLOYER_UNTRACEABLE` | No trace of this employer online | verify | The named employer produced no footprint from the general lookup. |
| `CLAIM_CONTRADICTED` | A retrieved source contradicts this posting | verify | A result contradicts a specific claim the posting made. Maps to the existing `Contradicted` status. |

### Family O — escape valve

| ID | Phrase | Definition |
|---|---|---|
| `OTHER` | (the model's own words) | Anything the closed set does not cover. **Free text is mandatory.** |

`OTHER` is not a dumping ground — it is a **drift detector**. The frequency with
which the model reaches for it is the measurable form of `oldPlan.md` §8.2
("add new scam patterns monthly"), which is currently unbuilt. A rising `OTHER`
rate means the set needs a new member, and it is the only signal that would tell you.

---

## 4. What is deliberately NOT a code

Equally a part of the design. From `SYSTEM_PROMPT.md:42`, restated here so the table
is self-contained:

- A free or personal email domain (Gmail, Yahoo, Outlook)
- A missing office address, salary, employer name, contract, or application process
- A generic job title, or "no experience needed"
- An informal or Messenger-based application
- A stated pay figure that is simply low for the role
- Ungrammatical, informal, or non-native writing
- **A posting that does not look like a job board advertisement**

That last one is the direct answer to the observation that drove this draft. Most
Philippine recruitment happens on Facebook, where posts are informal and miss
fields a job board would require. A post being unlike a job board ad carries almost
no information about whether it is safe — and wiring it to severity made the noise
drive the number. There is no code for it, and adding one would be the error.

**Absence is never a code.** Nothing is missing that the posting fails to ask for.
Only demands count.

---

## 5. Two rules that must not be collapsed

**The set labels; it does not gate.** Detection stays governed by the general
behavioural test, unchanged:

> Would a job seeker do something differently after reading this?

The code set exists so the gold set can be labeled and so the test suite can compare
things exactly. It is a **taxonomy, not a whitelist**. A model that finds something
real but uncoded emits `OTHER` plus free text — it does not suppress it. Making the
set a gate would recreate the enumeration trap already documented for
`task-for-earning`, where a positive anchor beat a list of flaggable things
precisely because a whitelist makes the next scam shape invisible.

**No per-instance severity.** The scan emits codes only. Family membership is a
coarse qualitative prior; the **level is emitted by verification**, which is the only
stage that knows *who* is asking.

This is not a preference. The Air Force case is the argument for it: a commercial
portal collecting identity documents while calling itself the official Air Force
portal scored 4 because the ladder priced *the category of the ask* and could not see
whether the asker was real. Fee severity has the same shape — ₱1,500 from a
traceable government agency and ₱1,500 from a name that appears nowhere are different
situations, and only the lookup can tell them apart.

Per-instance severity is also a **variance source**: it is model-judged, so it moves
between runs on identical input. Removing it removes one input to the Phase 6.2
instability the plan exists to measure.

*This is not a re-introduction of the retired weights.* A family ordering is a
qualitative prior handed to a model that reasons over it. The retired thing was a
numeric weight **summed into a score** — arithmetic aggregation, which is what
required a commensurable variable set the data never had.

---

## 6. What this buys the test set

| Plan phase | With a score | With codes |
|---|---|---|
| §6.2 stability | did the number repeat? | Jaccard on code sets, **and which code moved** |
| §1.4 agreement | did two humans pick the same number? | Cohen's κ **per code** |
| §6.3 false negatives | one aggregate FN rate | FN rate **per code** |
| §8.3 drift | the number moved | which code started or stopped firing |
| §8.2 new patterns | not measurable | `OTHER` frequency |

The single highest-value question for the gold set, stated so it can be falsified:

> **Does the count of codes in Family I predict the level, holding constant
> whether any Family M code is present?**

If it does, identity risk is being under-weighted — which the Air Force posting
suggests it was. If it does not, the level is already reading identity risk
correctly and the ladder was only mislabelling it.

---

## 7. Limits of this draft

Stated plainly, because a taxonomy built mostly from one idea is worth less than one
built from data.

- **Four emitted labels exist.** Two postings, and one of them is the subject of a
  known open question (whether a government agency may charge an application fee at
  all). That is nowhere near enough to derive a taxonomy from.
- **Of the 12 codes, 4 are grounded in observed output** (`FEE_MANDATORY`,
  `FEE_CONDITIONAL`, `DOCUMENTS_VIA_THIRD_PARTY`, `IMPERSONATES_AUTHORITY`) and 1 in
  the prompt's explicit `mid` rung (`TASK_FOR_EARNING`). The rest are **proposals**,
  grounded in the session's literature (the Nadé et al. corporate-identity-theft
  typology; the Australian NASC Job Scam Fusion Cell's risk-indicator guide; DMW/POEA
  licensing) but **not observed in this project's output**.
- **The largest family is the least evidenced.** Family I has one observation and is
  the family that changes behaviour most. That is a reason to prioritise it in the
  gold set, not a reason to be confident about it.
- **The registry-list problem is untouched.** `Official Registration` remains
  jurisdiction-locked to Philippine registries and asks an unanswerable question for
  the Australian employer in the Yeppoon test posting. A code set does not fix that;
  it is a separate prompt change.
- **The refundable-fee question is unresolved.** `FEE_CONDITIONAL` exists to make the
  difference legible, not to decide whether a refundable seminar fee is a finding. The
  panelist's position — that a fee alone is not a valid flag — is still open, and this
  draft deliberately does not close it.

## 8. Open decisions this draft does not make

1. **Does the scan emit a level before verification finishes?** If it does not, the
   panel has no verdict between scan-complete and verify-complete. That is more
   honest — you cannot judge danger before knowing who is asking — but it is a visible
   change and the copy has to cover it.
2. **Are Family I codes `high` by default?** Proposed: no severity field at all, per
   §5. If the panel wants a coarse band shown before verification resolves, the family
   letter is the obvious candidate.
3. **Is `IMPERSONATES_AUTHORITY` a scan code or a verification finding?** It is
   proposed as a scan code because the posting contains it, but confirm.
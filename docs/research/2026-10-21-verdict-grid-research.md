# Research — what a job post should have to do before the panel raises its voice

Date: 2026-10-21
Supports: `docs/superpowers/specs/2026-10-21-verdict-procedure-agent-loop-design.md` §3
Question asked: the verdict grid's cells were proposed from intuition. The
reviewer declined to sign off on them and asked for evidence. This is that
evidence, and it changed the design.

---

## 1. What was asked

Three questions, because the grid's cells depend on them and they cannot be
settled by taste:

1. **Which exposures are the real scam patterns?** The grid's `money`,
   `documents` and `labour` rows have to correspond to what actually happens to
   Filipino job seekers, or the panel is grading the wrong thing.
2. **What is the legal test?** A rule that can be checked against published
   rules does not need a base rate to be defensible. A rule that is only a
   statistical judgement needs one, and the base rate is against it.
3. **How much false-alarm rate can this afford?** The answer sets how soft the
   soft edges of the grid are, and it is the difference between a panel that
   is trusted and a panel that is ignored.

---

## 2. Finding 1 — there is an authoritative Philippine red-flag taxonomy, and it is consistent

DMW, DOLE, POEA, NTC and CICC all publish job-scam advisories, and they
agree with each other closely enough to use as the reference set.

| # | Red flag | Source |
|---|---|---|
| 1 | Advance payment or "reservation fee" before a contract is signed | DMW-CAR (Bucang, 2026-05-15): "Legitimate agencies do not collect fees before a contract is signed and official employment documents are issued." POEA Advisory 62: advertisements "ask for reservation fees and/or personal information". |
| 2 | Unregistered agency, no approved job order, not in the official registry | DOLE: recruitment by a non-licencee "shall be deemed illegal and punishable by a fine or imprisonment" (Art. 38, Labor Code as amended; RA 10022). DMW-CAR: "If the agency is not listed in the official registry … it is illegal." |
| 3 | Fake or misspelled domain, phishing lookalike | NTC (Maningding, 2025-04-24): "phishing sites often look like real ones but may have misspelled names or unusual web addresses." POEA: "the use of fake emails and websites". |
| 4 | Contact only through messaging or social media | DMW (Cacdac, 2026-02-09): recruiters who "communicate only through Telegram, Facebook, or other social media platforms are clear indicators of scams". |
| 5 | Transaction outside the agency's registered office | DMW-CAR: meetings, interviews, contracts or payments "done in malls, restaurants, coffee shops, private homes, or online chat platforms instead of inside the agency's registered office address are clear signs of illegal activity". |
| 6 | Employer cannot be found online | NTC: "companies that cannot be found online" is a red flag; also "businesses not listed with the SEC or the Department of Trade and Industry". |
| 7 | Pay or promise far above the market rate | DMW-CAR: "the most common bait used by scammers". |
| 8 | Offer that requires no résumé or biodata | NTC: "job offers that don't require a resume or biodata". |
| 9 | Request for sensitive personal information | POEA: "providing sensitive personal information … may be used in criminal activities". |
| 10 | Work on a tourist visa, no work permit | DMW-CAR; POEA. |

**Consequence for the design.** The grid cannot be organised around what a
posting *asks for* in the abstract. It has to be organised around **what shape
the request is**, because the published rules attach to shapes: a fee *before
a contract* (1), a fee *charged by an agency* (2), a transaction *outside an
office* (5), documents *through a third party* (3). The repo already extracts
the attributes most of this needs — `CLAIMED_TYPE` (agency vs employer),
`MEETING_SPOT`, `CONTACT_METHOD`, `PAY` — and it is missing the two that
decide the money case: **who the fee is paid to** and **when**.

---

## 3. Finding 2 — the legal test for a fee depends on the recipient and the timing, not on whether a reason is given

This is the finding that matters most, because it is the one that settles the
question the reviewer could not answer from intuition, and it settles it
without a base rate.

### Local employment

**DOLE Department Order No. 141-14**, *Rules and Regulations Governing
Recruitment and Placement for Local Employment*, Article on Fees and Charges
(§35): "**No fees whatsoever shall be collected neither deducted from the
salaries or wages of the workers.**" The service fee is the agency's to charge
to the **employer** ("An agency may only charge the service fee to the
employers based on the contract of service"), not to the worker.

So: **a recruitment agency charging a job seeker a placement fee for local
work is prohibited by rule.** That is not a statistical judgement and it does
not need a base rate.

### Overseas employment

**DMW rules (DMW-DC-01-2023)**, §56: a placement fee may be charged against
the OFW, capped at one month of basic salary, and "the worker shall pay the
placement fee to the licensed recruitment agency **only after signing the
DMW-approved contract**." §59: "**No other fees** in whatever amount, form,
manner or purpose shall be charged against the Overseas Filipino Worker."

So: a placement fee is lawful *only* if it is the prescribed one, *only* up to
one month of salary, and *only* after a signed contract. Every other fee
charged to the worker — a seminar fee, a "processing fee", a "uniform fee"
levied by the recruiter — is prohibited.

### What is lawful, and routinely happens

- **Training and assessment fees.** TESDA's Schedule of Cost
  (Circular 023-2020 and successors) publishes training cost, assessment fee
  and insurance fee per qualification. These are regulated, published, and
  paid to TESDA, with official receipts.
- **Uniform and pre-employment medical.** Standard Philippine pre-employment
  requirements: 2×2 and 1×1 photos, transcript of records, certificates, NBI
  clearance, chest X-ray, CBC, urinalysis, drug test. PESO client checklists
  (e.g. Bataan Provincial Public Employment Service Office, Alamada PESO)
  carry these as the ordinary job-seeker requirements, and job posts routinely
  ask for them ("SEND RESUME, 2X2 PICTURE, TRANSCRIPT OF RECORDS,
  CERTIFICATIONS, NBI CLEARANCE AND PASSPORT").
- **A placement fee charged by the employer** rather than by an agency is not
  governed by DO 141-14 §35, which governs recruitment and placement by
  licensed agencies.

### Consequence for the design — the grid's money row was wrong

The proposed cell was "a fee with a stated reason vs a fee without one". The
reason is the wrong axis. The right axes are **the recipient** and **the
timing**:

| Fee is paid… | Rule |
|---|---|
| to a recruitment agency, before a contract is signed | **prohibited** (local: DOLE DO 141-14 §35; overseas: DMW §56, §59) |
| to a personal account, GCash, remittance centre | **prohibited** (POEA Advisory 62 names remittance centres, GCash, 7/11 and PayPal explicitly) |
| to the employer, for uniform, medical or a training kit, and stated | ordinary practice |
| to TESDA, against a published assessment fee, with a receipt | lawful and regulated |
| recipient or timing not stated | **cannot be classified** |

So the money exposure needs two new facts from the posting, and they are
facts, not judgements:

```
FEE_RECIPIENT: <employer | agency | third party | individual account | not stated>
FEE_TIMING:   <before hiring | at hiring | after a contract | not stated>
```

This also settles the open question from
`docs/superpowers/specs/2026-10-17-anomaly-code-set.md` §7 — "the panelist's
position — that a fee alone is not a valid flag — is still open". The fee alone
is not a valid flag because a fee alone says nothing: a fee to the employer for
a uniform is ordinary, and a fee to an agency before a contract is prohibited.
The rule is not about the fee. It is about the shape.

---

## 4. Finding 3 — asking for documents is ordinary here; asking for *accounts* is not

`CREDENTIALS_BEFORE_INTERVIEW` currently reads "identification, bank details
or passwords requested before any interview or offer". That conflates two
things that are not alike in the Philippines.

**Ordinary, and the expected practice:**

- Résumé, 2×2 photo, transcript of records, certificates, NBI clearance,
  passport — the standard applicant packet (PESO checklists; the pre-employment
  checklists published by PH employers).
- Medical results for fitness to work.
- Government IDs (SSS, PhilHealth, Pag-IBIG, TIN) at onboarding.
- Bank details at onboarding: NPC Advisory Opinion 2019-034 on consent for
  employment purposes lists "facilitate processing of ATM payroll" among the
  legitimate employment purposes for which personal data is processed.

**Not ordinary, and never needed at the application stage:**

- Bank account or e-wallet number, one-time password, password, or remote
  access to an account. No employer needs any of these to consider an
  application. This is the mechanism by which an applicant's identity is
  turned into an account, a loan, a mule account or a card — the "may be used
  in criminal activities" that POEA warns about.

**Consequence for the design — the code splits.** `CREDENTIALS_BEFORE_INTERVIEW`
becomes two codes:

- `APPLICATION_DOCUMENTS` — the ordinary applicant packet. **Not an exposure.**
  It is a fact, like a free email address.
- `ACCOUNT_CREDENTIALS` — bank details, e-wallet, OTP, password, or account
  access, requested before hiring. **An exposure**, and one with no lawful
  reading.

And the Data Privacy Act supplies the test that separates them: RA 10173
§11(d) requires that personal information be "adequate and **not excessive** in
relation to the purposes for which they are collected and processed".
Collecting an applicant's bank credentials for an application is excessive for
that purpose; collecting a 2×2 photo is not.

`DOCUMENTS_VIA_THIRD_PARTY` — documents routed through a domain or account the
employer does not control — stays as it is. It has no lawful reading under
any of the above, and it is the CHED case's real charge.

---

## 5. Finding 4 — the base rate is the governing constraint on the soft edges

**The prevalence.** Job fraud is a low-prevalence event against a large
background of legitimate postings. The order of magnitude, from the agencies'
own numbers: DMW reports **146,871 illegal-recruitment posts removed from
Facebook and 57,557 from TikTok between 2020 and 2026** (Cacdac, 2026-05-25),
which is roughly 30,000 a year across both platforms; CICC logged **10,004
online scam complaints in 2024** (all categories) for a combined ₱198 million
in losses. Set against a Philippine job-posting population in the hundreds of
thousands a week, fraudulent postings are a low single-digit percentage at
most. No source gives a clean denominator, and this note does not claim one.

**Why that governs.** Axelsson, *The Base-Rate Fallacy and its Implications for
the Difficulty of Intrusion Detection* (ACM CCS '99; ACM TISSEC 3(3), 2000),
is the standard citation: where the base rate is low, "the false alarm rate is
the limiting factor for the performance of the system", and a low posterior
detection rate "would quickly teach the [user] to safely ignore all alarms,
even though their absolute numbers would theoretically have allowed complete
investigation of all alarms". The same result is the false-positive paradox:
when a disease is rare, the benefit of catching a few cases "is outweighed by
the medical, financial and psychological harm caused by a flurry of false
positives", which is why rare diseases are not mass-screened.

This is the precise failure the reviewer reported: a panel that says "Proceed
with caution" about a posting with nothing wrong does not lose one reader, it
teaches every reader that the caution does not mean anything.

**What it rules out.** The finding must be *classifiable*, not merely
present. A rule that fires on "the employer has no website" fires on a large
minority of legitimate Philippine employers, because a large minority of
Philippine employers are small and have no website. It also fires, on the
government's own list, in a form the reader cannot act on.

**What it permits.** A rule that fires on a *shape the rules forbid* — a fee
to an agency before a contract, account credentials before hiring, documents
through a third party, impersonation — fires rarely, and when it fires it is
right, because the shape itself is the finding.

**Consequence for the design.** The grid's primary axis is not "what does the
posting ask for". It is **which class the request falls into**, where the
classes are defined by the published rules and the classes are decided from
facts on the face of the posting:

| Class | Test | Verdict weight |
|---|---|---|
| **ordinary** | a shape the Philippine rules permit and PH hiring does routinely: free email, messenger application, biodata and 2×2 photos, medical and uniform costs charged by the employer, no experience needed, no formal process | no charge |
| **cannot be classified** | the shape is real but the facts that decide it are not stated — a fee whose recipient is not stated, a meeting place that is not named | a question |
| **prohibited** | a shape the rules forbid: a fee charged by an agency before a contract, a fee to a personal account, account credentials before hiring, documents through a third party, impersonation | a charge |

And the establishment axis becomes a **modulator**, not a co-equal axis:

- `contradicted` is the only path to STOP, and it requires a retrieved
  official source. This is the reviewer's "ace card" rule and it is what
  Axelsson's false-alarm constraint demands: the strongest output needs the
  hardest evidence.
- A prohibited charge whose counterparty is `confirmed` softens to a question,
  because the reader can see the thing on the employer's own site and judge
  it.
- `unknown` never, on its own, produces anything above a question. NTC lists
  "cannot be found online" as a red flag, and it is reported — as a fact in the
  record — but the panel is not the police, and the base rate says alarming on
  every small employer is the failure mode, not the safeguard.

---

## 6. The resulting grid

| Class of the request | `confirmed` | `supported` | `unknown` | `contradicted` |
|---|---|---|---|---|
| ordinary only | CLEAR | CLEAR | CLEAR | **STOP** |
| cannot be classified | NOTE | NOTE | NOTE | **STOP** |
| prohibited | NOTE | CAUTION | CAUTION | **STOP** |

Reading the three rows:

- **CLEAR** means "nothing in this posting is a shape that would put your money
  or documents at risk". It does **not** mean the employer is safe, and the
  statement must not claim it is: a CLEAR verdict on a posting that asks for a
  ₱500 uniform fee has to say that the fee is for a uniform, because the
  statement is a statement about the posting.
- **NOTE** means "here is a question you can settle in a minute". A fee whose
  recipient the posting does not say; an employer whose own pages do not list
  the role; a prohibited shape whose counterparty's own site publishes it.
- **CAUTION** means "a rule-forbidden shape, and you cannot dismiss it". It is
  reserved for the prohibited class alone, which is why it stops being common.
- **STOP** means "this posting is not from the employer it names" — the ace
  card, and the only output that requires hard evidence.

The three worked examples:

| Posting | Class | Establishment | Verdict | Statement |
|---|---|---|---|---|
| Real employer, Gmail address, no demands | ordinary | supported | CLEAR | "This posting asks you for nothing before you start." |
| Employer charges ₱500 for a uniform, stated | ordinary | unknown | CLEAR | "They ask for ₱500 for a uniform, and nothing else before you start." |
| Agency asks for a ₱1,500 fee before hiring, paid to a personal account | prohibited | unknown | CAUTION | "They ask you to pay ₱1,500 to a personal account before you start, and we could not find a record of this agency." |
| Fake CHED: claims to be CHED Region VI, gives `chred-region6.org`, asks for fees | prohibited **and** contradicted | contradicted | **STOP** | "This posting is not from the employer it names." |

Note the last row: the impersonation wins, because `contradicted` is the only
path to STOP and it is the fact the reader needs. The fees are in the record
and are not in the headline.

---

## 7. What the research changed in the design

1. **The grid's rows are the request class, not the exposure.** Exposure
   becomes an attribute of the class, not a row of the table.
2. **The taxonomy splits.** `CREDENTIALS_BEFORE_INTERVIEW` →
   `APPLICATION_DOCUMENTS` (ordinary) and `ACCOUNT_CREDENTIALS` (prohibited).
3. **Two new facts are extracted.** `FEE_RECIPIENT` and `FEE_TIMING`, and
   `FEE_REASON` as the reason if stated.
4. **`MEETING_SPOT` gains a nature.** "A named place" is not enough; the rule
   is about whether the transaction happens at the employer's registered
   premises.
5. **The establishment axis is a modulator.** `contradicted` is the only path
   to STOP, and `unknown` alone never rises above a question.
6. **The statement is about the posting, not about the employer.** A CLEAR
   verdict never says the employer is safe.

## 8. What the research did not settle

- **No clean base rate.** Every prevalence number available is a complaint
  count or a takedown count, and none has a denominator of postings seen. The
  argument in §5 is an order-of-magnitude argument and it is labelled as one.
- **Which shapes are common in the corpus.** The repo's own evidence is thin:
  `docs/superpowers/specs/2026-10-17-anomaly-code-set.md` §7 records four of
  twelve codes grounded in observed output and one observation for the family
  that changes behaviour most. The corpus is the thing to fix, and the corpus
  run is the next task.
- **Overseas placement fees at the one-month cap.** A fee at exactly the
  statutory cap, paid after a signed contract, is lawful. Whether the panel
  should say so, or simply have nothing to say, is a copy question rather
  than a rule question.

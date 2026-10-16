# Evidence hierarchy and verification triage — design

**Date:** 2026-10-16
**Status:** draft for review. Nothing here is built.
**Supersedes:** nothing. Adds to `2026-10-14-deployment-fences-design.md`.

---

## Intent

The verification stage answers six questions for every scan that names an
employer. It answers them the same way every time, in a fixed order, spending
the same budget regardless of what the posting actually claimed. Two failures
follow from that, both observed live:

1. **The model spends its own search budget duplicating the employer lookup.**
   A scan of a Yeppoon posting proposed `"Community Solutions Yeppoon"
   registered business Australia` and `"6A/18 Anzac Parade, Yeppoon" business
   registration or ABN lookup`. `build_queries` already runs
   `"<company> company or employer"` and returns the employer's own pages, its
   listings and its job posts. Two of three Tavily credits bought a second copy
   of pages the first search had already returned. On a 1,000-credit monthly
   tier that is roughly a third of the verifications the budget could buy.

2. **The most informative check never gets asked.** A posting claiming to be
   Philippine Airforce recruitment linked to a domain that is not the Airforce's.
   The scan flagged it accurately. Verification searched "Philippine Airforce",
   found the real Philippine Airforce, and reported Company Existence: green.
   Both statements were true; together they describe a phishing page.
   `Channel Match` is the category built to catch exactly this, and it was never
   requested — `verification_prompt.py:_CATEGORY_REQUIRES` gates it on the scan
   having reported a channel, and the scan put the channel in the anomaly prose
   where it was scored rather than in the attribute slot where it was testable.

The fix is not a better prompt. It is a **priority order over evidence, plus a
triage rule**, and a set of categories widened to match where these offers
actually appear.

## The organising principle

> **A check is worth most when it could have come out the other way.**

"The Philippine Airforce exists" is true and carries no information — that check
could not fail. "The link in this posting is not `paf.mil.ph`" is true and
carries everything — it could have failed. Existence checks on famous employers
are the pockets swept at a crime scene. A mismatch is the knife: it is
informative because someone put it there.

This is also why the hierarchy is defensible in a way a list of "important
things" is not. It is a claim about **discriminating power**, and discriminating
power is a property of the check, not of the employer.

## Scope

**In scope:** unstructured, unfiltered offers seen on Facebook groups and pages,
Telegram channels, and messaging apps — the ones with no employer verification,
no editorial review, and no corporate ATS behind them. These are where the
research below is densest and where this product's users actually are.

**Out of scope:** structured job boards (their own fraud filtering is the
relevant layer, and they have it); anything requiring the tool to dereference a
link; and the overseas-trafficking-to-scam-hub category, which is a different
crime with a different response and which no screenshot of a post can establish.

**Framing.** The earlier ambition was "the ultimate fact checker". That is
dropped. It is not defensible from a few seconds of searching, and asserting
conclusions is precisely what this system's prompt rules exist to prevent. The
defensible claim is narrower and better:

> The tool does not assert that a website is fraudulent. It reports that the
> link in a posting is not the link the named employer uses, and shows the
> sources. Both facts come from the posting and from public search results, and
> the finding is their disagreement — which a reader can check in one click.

## Evidence hierarchy

Ordering is a **judgement informed by the sources below, not a finding of them**.
It is to be derived by the existing Saaty/AHP method
(`backend/scripts/derive_refutation_weights.py`) with the consistency ratio
reported, so the reasoning is explicit and reproducible rather than asserted.

| Rank | Check | Why here |
|---|---|---|
| 1 | **Channel Match** | The only check that can detect impersonation. A real employer passes every existence, registration and branch check; a fake one borrows a real employer and fails only here. |
| 2 | **Company Existence** | Informative in proportion to how unremarkable the employer's existence would be. Trivial for a famous name, load-bearing for "Acme Roofing". |
| 3 | **Official Registration** | Corroborating. Now DMW/POEA-aware (below). |
| 4 | **Location / Branch** | Corroborating. |
| 5 | **Reputation, Similar Offers** | Supporting. Rarely decisive; see the documented disagreement below. |

## Categories to add

The six current categories are about the *employer*. Two gaps are about the
*post*, and both are documented patterns in the sources.

### 1. Unreadable pointer — a new state, not a category

Some posts contain a QR code or a bare link and little else. The scan model
**cannot decode a QR code** — it sees a pattern, not a URL. And that is precisely
why attackers use one:

> "Embedding phishing URLs into QR codes makes it more difficult for traditional
> scanning engines to extract the actual URL" — Unit 42, *Evolution of
> Sophisticated Phishing Tactics: The QR Code Phenomenon*, Apr 2025

> "We observed that 85% of those who scanned a QR code subsequently visited the
> associated URL" — Vidas et al., *QRishing*, USENIX Security 2013

**This is a bug in the current system, and a serious one.** `SYSTEM_PROMPT.md`
says set `VALID: false` only when there is no offer of work or income "in the
content at all." A QR code is not content. A QR-only post therefore reads as
`VALID: false` → `InvalidContentError` → the panel tells the reader **this is not
a job posting**, when the truth is *this is a job posting we cannot read*.

Those are different, and conflating them is the same class of error as
collapsing "searched and found nothing" into "never searched".

Required: a distinct outcome. Something like `UNREADABLE` — the panel reports
that the posting directs the reader somewhere this tool cannot follow, states
what surrounds it, and says plainly that it has assessed nothing. It must not
render a score, a colour, or a level, because nothing was measured.

**Mechanism, so a builder does not have to choose one.** `VALID` currently
carries two values and drives whether the scan endpoint proceeds at all
(`InvalidContentError` on `false`). `UNREADABLE` is a **third value**, not a new
field:

- `VALID: false` means *this is not an offer of work*. The reader is told so and
  nothing else follows.
- `VALID: unreadable` means *this directs the reader somewhere we cannot follow*.
  The scan still completes, reports no employer, and the panel renders the
  pointer state.

`unreadable` is chosen **only** when the content contains a QR code, a barcode,
or a link with no surrounding offer text, and nothing readable about the work
itself. A post with two sentences of role description *and* a QR code is not
unreadable — the sentences are the posting and the QR code is a `CONTACT_METHOD`
claim, which is the impersonation case, not this one.

This state precedes `analyze-offer`. A QR-only post names no employer and offers
nothing assessable, so it should never reach the offer path, which would
otherwise analyse a link as though it were an offer.

### 2. Channel patterns to name inside `Channel Match`

The category is correctly defined but under-specified. The sources name three
specific patterns it should recognise, all of them **channel migration** — the
post sits on a legitimate surface and the instruction leaves it:

| Pattern | Source |
|---|---|
| Moved to a messaging app. *"We never make first contact through it"* — aTalent's stated practice, for a legitimate recruiter. FTC's Telegram alert describes the opposite as the scam shape. | FTC Consumer Advice, Jul 2023; aTalent/National Cyber Security Centre |
| Off-platform form or shortened link. Posts *"redirect users to a Google Form through a shortened url"*; the form requested *"name, phone number, identification number, date of birth, location, nationality and level of education."* | CfA iLAB *Inauthentic Facebook Profiles*, Kenya |
| Install-then-join. A real posting on a real platform, then *"directing candidates to join the call via a video conferencing application… downloaded from the website."* | GTIG UNC6229; 'GrassCall'/'VibeCall' |

And the rule the FTC states in one sentence, which is the whole category:

> "Visit the official website for the organization or company you're applying
> for. **Don't use the site the caller gives you. Find the real site yourself.**"

## Triage

The hierarchy is both a **ranking** and a **checklist**, and it governs a work
queue under a credit budget.

- Take checks in rank order.
- Skip a check that is **not applicable** — `_CATEGORY_REQUIRES` already gates on
  whether the posting made the claim at all.
- Skip a check whose answer is **already in hand**, meaning either of:
  - the scan supplied the value as an attribute (a stated `LOCATION` needs no
    search to know what was claimed), or
  - the employer lookup's own results already carry the answer, in which case
    asking again is the duplication this document exists to stop.
- Spend the remaining credit cap in rank order. **When more checks are applicable
  than the cap allows, the rank order is what selects them** — that is the whole
  mechanism, and it is what makes the hierarchy load-bearing rather than
  decorative. With `MAX_SEARCH_QUERIES = 2` and all six applicable, checks 1 and
  2 are the two that run, and 3–6 are answered from the merged results the first
  search returned.
- **Record what was checked and came back empty**, as its own state. Not a card,
  not a sentence: *"Checked whether the link is the employer's own — the results
  did not show one."* An unrecorded negative is indistinguishable from never
  having looked, and that collapse is the single failure this system has spent
  the most effort preventing.

Note the consequence, which is a real cost and not an oversight: a low-ranked
check that is applicable but unfunded now reports *checked against what the
employer lookup returned* rather than getting its own query. That is weaker
evidence than it was, and the panel must not present it as though a dedicated
search settled it.

## Prompt changes implied

1. The scan must write any URL, email address, phone number, or account the
   posting directs applicants to into `CONTACT_METHOD` — the slot that opens
   `Channel Match`. Today it writes that observation into anomaly prose, where it
   is scored but never tested. *This is the highest-value single change in the
   document.*
2. `VERIFY_PROMPT.md` must say that when the posting names one channel and the
   results show another, that is a **contradiction** — `red` — not a confirmation
   that the employer has a website.
3. The verify prompt should be given the ranked checklist and told to work it in
   order.

Both halves are required. The first without the second gets a category that is
requested and then answered wrongly, which is worse than never asking.

## Registry correction

`VERIFY_PROMPT.md` names SEC, DTI, PEZA, BOI, an LGU business permit, and
government portal listings. It omits **DMW licensing**, which for a Filipino
applicant is arguably the registration that matters, and which is publicly
checkable:

> "illegal postings misuse the names, addresses, and logos of legitimate and
> DMW-licensed recruitment agencies" — DMW, via PNA

DMW also supplies a rule sharper than "asks for money", and it is about the
*channel of payment*:

> "A job offer which require early payment of fees through electronic transfer
> is a solid indication of a scam." — DMW / POEA

Small, self-contained, and independent of everything else here.

## Documented disagreements with the project's existing rules

Recorded because a panel will find them, and because a rule contradicted by a
citation is defensible while one contradicted silently is not.

**Processing fees.** `SYSTEM_PROMPT.md` offers *"Asks applicants to pay a
processing fee"* as the worked `high`-severity example, and defines high as
"asks the applicant for money, goods, or a deposit". The Australian National
Anti-Scam Centre lists what upfront fees are actually demanded for — *"training
or qualification required for the role; visas…; essential equipment…; police
check or other pre-employment checks; mandatory uniform"* — and the FTC states
that government job information is free and *"Never respond to an ad that
promises jobs with the federal government."* A panelist has already said this is
not a valid flag on its own.

The project's own reason for keeping it is that it is the clearest advance-fee
signal there is. The research's reason for qualifying it is that impersonation,
not the fee, is the constant across every scam type — *"Upfront fee job scams
typically involve an element of impersonation."*

**Unresolved — and this part is blocked, not merely open. Do not build it until
it is decided.** The project's own reason for keeping the rule is that a fee is
the clearest advance-fee signal there is. The research's reason for qualifying it
is that impersonation, not the fee, is the constant across every scam type —
*"Upfront fee job scams typically involve an element of impersonation."*
Resolving it means choosing between "the fee is the finding" and "the
unverifiability is the finding," and that is a judgement about the product's
posture, not an implementation detail. It needs the panel's actual objection in
hand.

**"No experience needed".** The Finnish National Cyber Security Centre lists this
among recruitment-scam indicators. `SYSTEM_PROMPT.md` explicitly forbids flagging
it, because it is ordinary in Philippine job postings and reporting it buries
real findings. The project's rule is a deliberate localisation and should be kept
— but it is now a *judgement with a counter-source*, and the commit history
should say so.

## Testing

This project's convention is that a test must fail when the production code is
deliberately broken, **in both directions**, and a test that still passes under
a mutation was testing nothing. Every change below inherits that.

| Change | The test that must fail under mutation |
|---|---|
| `CONTACT_METHOD` written for any stated channel | Feed a scan output containing a link but no `CONTACT_METHOD`; the category must not open. Mutating the prompt to drop the rule fails the guardrail assertion in both prompt copies. |
| `Channel Match` reads a mismatched domain as `red` | Assert on the request built for a posting whose domain differs from the results'. Mutating `red` to `yellow` fails it. |
| `UNREADABLE` | Assert a QR-only post yields `unreadable` and not `false`. **The overcorrection matters more here:** a post with readable role text plus a QR code must stay assessable, or the new state swallows normal postings. |
| Rank order selects the funded checks | With all six applicable and a cap of 2, assert checks 1 and 2 ran and 3 did not. Mutating the sort to insertion order fails it. |
| DMW added to the registry list | Assert the phrase is in the file **and** the fallback copy — `test_verify_prompt_file.py` already enforces the two agree, so this is one line. |

Nothing here is testable against a live provider. Every assertion is against
prompt text, request construction, or parse output, so the suite stays offline.

## Explicitly rejected

**Fetching the link to inspect its certificate.** Rejected on evidence:

| Finding | Source |
|---|---|
| *"generally impossible to differentiate between benign sites and phishing sites based on the content of their certificates alone"* (10k phishing vs 40k benign certs) | *Certified Phishing*, USENIX SOUPS 2019 |
| **20% of the top 1,000 popular SSL sites** triggered a browser false warning; **62%** of 297,574 SSL-enabled sites would | *Alice in Warningland*, USENIX Sec 2013 |
| Chrome's SSL warning clickthrough rate **70.2%** | same |

"Not secure" fires on most legitimate sites. On small Philippine employers it
would fire on most. It is a prevalence signal, not a fraud signal, and chasing it
would manufacture precisely the false positives this product exists to avoid —
while turning the backend into a fetcher of attacker-controlled hosts.

**A numeric risk score.** See the separate decision; the number was a visual
motif (a tachometer) and the rules were fitted to it afterwards.

## Sources

Government and regulator first, then peer-reviewed.

**Philippines — most on-point for this product's audience**

- DMW (via PNA), *"DMW cautions against overseas job scams on social media"*
- DOLE (via PNA), *"DOLE cautions public vs. phishing attempts"*; *"DOLE warns
  public vs. fake emergency job hiring"*
- POEA (DMW), *"Beware of job offers which require early payment of fees"*
- SEC (via ABS-CBN), *"SEC warns vs 'tasking and recharging' job offer scams"*
- Bureau of Immigration, *"Telegram and Facebook used by syndicates to lure
  trafficking victims to work for scam hubs"*, Apr 2025 — 125 cases intercepted
  in 2024

**International government / regulator**

- National Anti-Scam Centre (Australia), *Job Scam Fusion Cell Final Report*,
  May 2025 — published risk-indicator guide
- FTC, *Job Scams*; *"Job offer through Telegram Messenger? Not so fast"*
- Scamwatch (Australia), *Jobs and employment scams*
- Action Fraud (UK), *Recruitment scams*

**Peer-reviewed**

- Vidros et al., *Automatic Detection of Online Recruitment Frauds*, Future
  Internet 2017 — **EMSCAD dataset**, 17,014 legitimate / 866 fraudulent
- Nadé, Adebayo & Nanda, *A machine learning approach to detecting fraudulent job
  types*, AI & Society 2022 — the **corporate identity theft** category
- Employment scams crime script and scoping review, 2026
- Vidas et al., *QRishing*, USENIX Security 2013
- Unit 42 (Palo Alto), *Evolution of Sophisticated Phishing Tactics: The QR Code
  Phenomenon*, Apr 2025
- *Certified Phishing*, USENIX SOUPS 2019
- Akhawe & Felt, *Alice in Warningland*, USENIX Sec 2013

**Field investigations**

- CfA iLAB, *Inauthentic Facebook Profiles used to share Fake Job
  opportunities* (Kenya) — 33 pages, 184,532 followers, impersonating real chains
- Google Cloud GTIG, *Vietnamese Actors Using Fake Job Posting Campaigns*, 2025

## Open questions for the panel

1. **Is a processing fee a finding at all?** Largest unresolved item here, and
   the prompt change is blocked on it.
2. **Does the derivation belong in an appendix?** If the ordering is defended,
   the Saaty matrix and its sources should be readable by someone who does not
   have the repository. Right now they live in a commit message and a script.
3. **Who reviews the `UNREADABLE` wording?** It is specified here as behaviour,
   not as copy, and copy is what a reader of the panel will actually see.

## Sequencing

Four interlocking changes. They do not all have to ship together, and two of them
are worth shipping first because they are independently valuable and cheap:

1. **`CONTACT_METHOD` plumbing.** Independent of everything else. Fixes the
   Airforce case on its own. Prompt rule plus a guardrail test in both copies.
2. **DMW/POEA registry line.** One sentence, one test. Independent.
3. **`Channel Match` sharpened** so a mismatched domain reads as `red`. Depends
   on nothing, but is inert until 1 ships — the category is not requested yet.
4. **`UNREADABLE` state.** Independent of 1–3, and the only one that changes the
   `VALID` contract. Ships separately because it touches `InvalidContentError`
   and the offer path, and a regression there hides a posting rather than
   misdescribing one.

The triage work — rank order, already-in-hand skipping, the recorded negative —
depends on 1 landing first, because until the scan populates `CONTACT_METHOD`
there is nothing for the ranking to prioritise.

Score removal is **not** in this document. It was decided in conversation and is
not yet written down; it needs its own spec, because it changes the wire format,
the gauge, the accent colours, and the resume-matching filter in one go.

# Corpus baseline — what the current system says about 13 real postings

Date: 2026-10-21
Runs against: `main` at `451d7b4`
Produces: the "before" column the verdict procedure is measured against
Related: `docs/superpowers/specs/2026-10-21-verdict-procedure-agent-loop-design.md`,
`docs/research/2026-10-21-verdict-grid-research.md`

---

## 1. Method

Every job posting in `jobposts/` was run through the current pipeline —
`/api/scan` then `/api/verify` — and the result recorded. Live provider calls;
the reviewer granted permission on 2026-10-21 for about twenty runs. Thirteen
postings were run, which is 13 scan calls and 11 verify calls, and a Tavily
budget of roughly 20–30 credits against the monthly free tier.

**One caveat that matters for the thesis: the configured model is
`dots-studio/dots-3-note-preview:free`.** Everything below is a measurement of
*this* model inside *this* pipeline. The verdict procedure is code-owned, so
its output should be far less model-dependent than what is measured here — but
the false-positive rate quoted in §4 is a rate for this model, and it should be
quoted as such.

The ground truth is not inferred. Each posting was read by hand and labelled
before the run.

## 2. The corpus

Thirteen postings. **Eleven are legitimate**, two name no employer, and one is
a forgery. **Not one legitimate posting asks the reader for money** — which is
the corpus's most important property and its biggest limitation (§8).

| File | Employer | Channel | Asks for money | Asks for documents | Truth |
|---|---|---|---|---|---|
| `randomjob.png` | Excell Workforce Solutions Corp. (agency) | Gmail | no | no | legit |
| `randomjob2.png` | Abenson Company | Gmail (globalventure) | no | SSS, PhilHealth, Pag-IBIG, NBI, Mayor's + Health Card | legit |
| `randomjob3.png` | Cafe France | Gmail (worldclass) | no | no | legit |
| `minuteburger.png` | Minute Burger | **own domain** + Facebook | no | SSS, Pag-IBIG, PhilHealth | legit |
| `transformativeemployer.jpg` | Transformative Solutions Gen Services | phone + TikTok | no | PSA, SSS, PhilHealth, Pag-IBIG, NBI, diploma, medical | legit |
| `sutherland.jpg` | Sutherland Clark | walk-in / PM me | no | no | legit |
| `tanika.jpg` | Tanika Philippines Corp. | PM me, terminal meeting point + free shuttle | no | résumé/biodata | legit |
| `crabsncrack.jpg` | Crabs N Crack | none visible | no | no | legit |
| `acabar.jfif` | Acabar Marketing International | Gmail **+ own domain** | no | no | legit |
| `knollridges.jpg` | Knollridges Consultancy | Gmail | no | no | legit |
| `nocompanynamecallcenter.jpg` | none | PM me | no (offers free accommodation) | no | no employer |
| `nocompanynamewarehouse.jpg` | none | message me | no | no | no employer |
| `fakeched.png` | "Commission for Higher Learning" | `ched.gov.ph` **and** `chred-region6.org` + Outlook | **P1,500 + P800** | no | **fraud** |

`Screenshot 2026-10-18 013313.png` is a screenshot of another system's analysis
of the CHED flyer, not a posting, and is not in the corpus. So is the
contractors PDF, which is a reference document.

## 3. The "before" column

| File | Truth | Level | Score | Codes the scan emitted |
|---|---|---|---|---|
| randomjob.png | legit | low | 29 | `DOCUMENTS_VIA_THIRD_PARTY` |
| randomjob2.png | legit | **moderate** | 37 | `CREDENTIALS_BEFORE_INTERVIEW` |
| randomjob3.png | legit | low | 4 | `OTHER` |
| minuteburger.png | legit | low | 4 | — |
| transformativeemployer.jpg | legit | **moderate** | 37 | `CREDENTIALS_BEFORE_INTERVIEW` |
| sutherland.jpg | legit | low | 12 | `OTHER` |
| tanika.jpg | legit | low | 12 | `OTHER` |
| crabsncrack.jpg | legit | low | 12 | `OTHER` |
| acabar.jfif | legit | low | 4 | `OTHER` |
| knollridges.jpg | legit | low | 4 | `OTHER` |
| nocompanynamecallcenter.jpg | no employer | — | — | `OTHER` (offer path) |
| nocompanynamewarehouse.jpg | no employer | — | — | — (offer path) |
| fakeched.png | fraud | critical | 80 | `FEE_MANDATORY` ×2 |

## 4. Finding 1 — the false-positive rate is 2 in 10, and the cause is exactly what the research predicted

Two of the ten legitimate postings that named an employer came back
**moderate**. Both were pushed there by the same pair of mechanisms.

**`randomjob2.png` (Abenson, a real appliance retailer):**

```
CREDENTIALS_BEFORE_INTERVIEW  (mid)   12 points
Channel Match: free_email_with_findings (red)  25 points
                                          --------
                                            37  ->  moderate
```

The finding's own quote: *"With complete mandatory requirements such as SSS,
PHILHEALTH, Pag-IBIG, and latest NBI."* The Channel Match explanation: *"The
posting directs applicants to the email address recruitment09.globalventure@gmail.com,
while the search results show that the official Abenson website is abenson.com."*

**`transformativeemployer.jpg` (Transformative Solutions):** the same pair,
same score, 37. Its quote: *"REQUIREMENTS: PSA Birth Certificate, SSS,
Philhealth, Pag-ibig, NBI Clearance, Diploma, Medical."*

Two things are wrong, and the research says both:

1. **The document request is the ordinary applicant packet.** PESO checklists,
   TESDA and the employers' own published pre-employment packets all ask for
   this. The research note §4 says so, and the corpus confirms it: these two
   postings are the two that ask for the most documents, and they are both
   legitimate.
2. **A free email is worth 25 points.** `channel_match.py` rule 4 turns "a
   free-provider address" plus "any independent finding" into a red card worth
   a quarter of the scale. The scan prompt says a free email is not an
   anomaly; the scoring says it is worth 25.

Neither posting was a borderline case. Both are ordinary, both are real
employers, and both are now told "Proceed with caution".

## 5. Finding 2 — the Fake CHED impersonation is detected, written out in plain words, and then scored **zero**

This is the finding the whole exercise was aimed at, and it is worse than a
missing detection: the detection happens and is discarded.

The live run's verdict breakdown for `fakeched.png`:

```
posting_score      80     (two FEE_MANDATORY findings, 40 + 40)
verification_score None   (the employer check refuted nothing)
channel_escalation  ''     (no strong channel rule fired)
channel_floor      false  (the strong-channel floor was not applied)
risk_level     critical
verdict_reason  "The posting asks for a mandatory processing fee and a registration fee."
```

And the Channel Match card the reader is shown — **amber**, with escalation
`government`:

> The posting presents the employer as a government office and gives
> "recruitment.chred@outlook.com", "chred-region6.org" and
> "info@chred-region6.org" as a contact. **That is outside the .gov.ph domain.**

The card states the impersonation in plain words and is then treated as an
observation worth nothing.

### The mechanism

`assess_channel_match` is called with the facts the model reported and it
returns the right answer:

```
assess_channel_match  ->  status=red  escalation=government  strong=True
```

The government rule (`channel_match.py:203`) fires exactly as its own comment
says it should — *"it needs no retrieved source to see: the posting made the
claim and the posting supplied the domain."*

Then `_bind_to_retrieved` demotes it. Its rule: an item with no bound
`source_url` that is `red` becomes `yellow`, because an unbacked red is a
claim nobody could confirm. The Channel Match item's citation was
`https://ched.gov.ph`, and it was **not in the retrieved set** — so the
demotion applies. The escalation string survives (`government`), which is why
the card still carries the word, and `verdict.py`'s `_strong_channel_rule`
requires `status == "red"`, so the strong-channel floor never applies either.

Reproduced offline, both worlds, no provider calls:

```python
# A) ched.gov.ph WAS retrieved  (what the fixture supplies)
red | escalation=government | url=https://ched.gov.ph
-> level=critical score=100 channel_escalation='government' verification_score=25

# B) ched.gov.ph was NOT retrieved  (what the live pipeline actually got)
red | escalation=government | url=''
   after _bind_to_retrieved: yellow | escalation=government
-> level=critical score= 80 channel_escalation='' verification_score=None
```

### Why the pipeline cannot retrieve it

Because the **scan took the forgery's misspelling at face value**. The flyer
says *"Commision on Higher Learning"*; the scan's `COMPANY` slot became
*"Commission for Higher Learning - Regional Office VI"*, so the employer lookup
searched for an agency that does not exist, found nothing, and returned pages
that do not include `ched.gov.ph`.

**So the context loss and the unscored impersonation are the same defect.** The
flyer carries both `ched.gov.ph` and `chred-region6.org` in the same image,
along with a misspelled agency name and a placeholder phone number. Every one
of those facts is visible in the image. The pipeline threw the image away
after slot-filling, and the slot it kept was the forger's own lie.

### Why the test suite does not catch it

`backend/tests/test_channel_match_regressions.py` mocks the search to return
`https://ched.gov.ph`, so the citation binds, the red survives, and Fake CHED
is critical. **The fixture supplies by hand the one retrieved URL the real
pipeline cannot obtain.** The flagship case passes because the test supplies
the evidence the system failed to find.

## 6. Finding 3 — two more taxonomy conflations, both visible in the corpus

**`DOCUMENTS_VIA_THIRD_PARTY` is being used for free email.** On
`randomjob.png` the finding's label was *"Uses a free email domain for
recruitment"*, the code was `DOCUMENTS_VIA_THIRD_PARTY`, and the quote was
the Gmail address. The code means "documents sent through a domain or account
that is **not the employer's own**" — but a free-provider address is not a
*third party*, it is the absence of a domain. The two need separating, and the
research's ordinary/prohibited split puts a free email in the ordinary class.

**`OTHER` at `mid` severity is a false-finding machine.** Four legitimate
postings got a mid-severity finding for something entirely ordinary:

| Posting | Finding | Severity |
|---|---|---|
| `sutherland.jpg` | "Offers grocery bags as an incentive for walk-in applicants on specific days" | mid |
| `tanika.jpg` | "In-person recruitment event with mandatory early arrival and specific physical location" | mid |
| `crabsncrack.jpg` | "Gender preference in hiring" | mid |
| `acabar.jfif` | "Gender-restricted hiring (Male only)" | low |

"Grocery bags for walk-ins" and "be there at 7am" are how mass hiring in the
Philippines is done; a gender preference is a hiring decision, not a scam
signal. Any of these four would have reached **moderate** had the posting
carried a free email address as well — `sutherland` and `tanika` were saved
from that only because they use Messenger and no address at all.

## 7. Finding 4 — two more defects the corpus surfaced

**A false red card.** `minuteburger.png` produced a **red** `Location / Branch`
card: *"The posting names a San Fernando, Pampanga branch at a local market,
but the company's own Facebook page lists a different venue at Robinsons
Starmills Pampanga."* Minute Burger has 600+ stores. A franchise listing one
venue does not contradict a posting that names another. The verdict reason the
reader gets is *"The posting directs applicants to a meeting spot that does not
match the venue listed on the company's official Facebook page"* — a warning
about a 600-store chain, on a legitimate posting, from a card worth 4 points.

**A misattributed employer.** `randomjob3.png` is a Cafe France flyer for a
branch inside Mega Caltex. The scan's `COMPANY` slot became **"Mega Caltex in
Metro Manila"** — a shopping mall, not the employer. Every subsequent stage
checked the wrong entity, and the verdict reason says the posting's email
"is not confirmed as belonging to Mega Caltex". The verify model *noticed* —
its report says the same address is used for Cafe France — and could not act
on it, because the employer was fixed in an earlier slot.

## 8. What the corpus cannot measure, and how to fix that

**No legitimate posting in the corpus asks for money, so the corpus measures the
false-positive side well and the true-positive side not at all.** There is
exactly one member of the prohibited class: Fake CHED. A grid whose whole
point is to tell an ordinary fee from a prohibited one cannot be validated on
one example.

The reviewer's own observation is the answer: *the Fake CHED flyer is an edited
version of a real CHED posting.* That is the method — **controlled editing**,
where the ground truth is true by construction because the difference between
the pair is the element under test. The pairs to build, each one differing from
a legitimate posting by exactly one element:

| Pair | Base | Edit | Expected class |
|---|---|---|---|
| A | `randomjob.png` (Excell, an agency) | add "Application fee ₱500. Send to our HR via GCash 09xx." | **prohibited** — fee to an individual account before hiring |
| B | `randomjob.png` | instead: "Processing fee ₱500 for the company ID and uniform, payable in cash at our office during the interview." | **ordinary** — a fee to the employer, at hiring, with a reason |
| C | `randomjob2.png` (Abenson) | add "Please send your bank account number and e-wallet details with your biodata." | **prohibited** — account credentials before hiring |
| D | `randomjob2.png` as it stands | SSS, PhilHealth, Pag-IBIG, NBI, Mayor's + Health Card | **ordinary** — the applicant packet |
| E | `minuteburger.png` | change `www.minuteburger.com` to `www.minuteburger-careers.com` | **contradicted** — lookalike domain |
| F | `randomjob3.png` | change the header to "CITY OF CEBU — JOBSITE", keep the Gmail address | **contradicted** — government claim on a non-government channel |
| G | `sutherland.jpg` | make the role "Facebook liker — ₱50 per 100 likes" | **prohibited** — task-for-earning |

Pairs **A/B** and **C/D** are the important ones: each is a pair whose two
halves differ by the fee's *shape* and by the *kind* of document, and they are
what the whole taxonomy split rests on. If the new grid cannot separate A from
B, or C from D, it has failed regardless of what it does with Fake CHED.

The edits are synthetic and the corpus says so. For real adversarial cases,
the government advisories publish example flyers (the DMW, POEA and NTC
advisories link to images of the postings they warn about), and those are
worth collecting as a separate, clearly-labelled set.

## 9. What this changes in the design

1. **§3.1's taxonomy split is confirmed by measurement, not only by reading.**
   `CREDENTIALS_BEFORE_INTERVIEW` produced two of the two false positives,
   and `DOCUMENTS_VIA_THIRD_PARTY` produced a third false finding on a free
   email. Both are fixed by the split the research already requires.
2. **A free-provider address is never a third party.** It goes in the ordinary
   class, and rule 4 of `channel_match.py` — the 25 points — goes with it.
3. **`Location / Branch` red must not be a contradiction.** The new
   materiality rule is identity-level only, so the franchise false red cannot
   happen. §3.3 already says this; the corpus shows why it matters.
4. **The Fake CHED demotion is a bug, not a design.** The government rule
   says it needs no retrieved source, and the general binding rule discards it
   anyway. Commit 1 must fix it, and it must be fixed *before* the agentic
   loop, because otherwise the loop's better facts are thrown away the same
   way.
5. **The employer slot must be reconciled against the image.** The scan took
   the forger's misspelling and the mall's name. One agent holding the flyer
   can see that the wordmark says "Commision" and that the flyer carries both
   `ched.gov.ph` and `chred-region6.org`; a fixed slot cannot.
6. **The corpus needs the controlled pairs** before the design can claim it
   works. §8.

## 10. Reproduction

The run is a script over `/api/scan` and `/api/verify` with a 13-second pause
between calls to stay under the endpoints' 5-per-minute limit, and it writes
one JSON record per posting. The defect in §5 is reproducible with no provider
calls at all:

```python
from app.services.scanner.verification_flow import _read_channel_item, _bind_to_retrieved
from app.services.scanner.verdict import code_verdict

cm = {
  "printed_channels": ["hrm06@ched.gov.ph", "recruitment.chred@outlook.com",
                       "chred-region6.org", "(033) 987-6543", "info@chred-region6.org"],
  "official_channels": ["ched.gov.ph"],
  "government_claim": True,
  "source_title": "CHED Regional Office VI",
  "source_url": "https://ched.gov.ph",
}
anoms = [{"flag": "processing fee", "severity": "high", "code": "FEE_MANDATORY"},
         {"flag": "seminar fee", "severity": "high", "code": "FEE_MANDATORY"}]

item = _read_channel_item({"channel_match": cm}, frozenset({"https://www.facebook.com/chedregion6"}))
bound, _ = _bind_to_retrieved([item], [], frozenset({"https://www.facebook.com/chedregion6"}))
print(bound[0].status, bound[0].escalation)      # yellow government
print(code_verdict(anoms, bound, [])[:2])        # (80, 'critical')
```

`assess_channel_match` on the same facts returns `red`/`government`/`strong`
before the binding runs. The demotion is the whole defect.

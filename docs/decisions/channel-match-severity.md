# Decision record — Channel Match severity

Owner files: `backend/app/services/scanner/channel_match.py`,
`backend/VERIFY_PROMPT.md`,
`backend/app/services/scanner/verification_prompt.py`,
`verification_flow.py`, `verdict.py`.

---

## The failure this replaces

The verify model used to decide the Channel Match status and the overall level in
the same response. The prompt told it that *any* channel different from the one in
the results was a contradiction, so the two decisions reinforced each other.

Two postings show the two directions of the error.

**Knollridges.** A real employer's posting used
`yvonne.knollridges@gmail.com`; the company's own site was
`knollridges.com.ph`. The model reported the difference as a red Channel Match,
then emitted `risk_level: critical`, and the panel said "Do not proceed" from one
weak observation. A free email address is ordinary in Philippine job postings,
including ones written by employers with a real office and a real website.

**Fake CHED.** A poster used the real CHED Regional Office VI seal and
`ched.gov.ph`, but sent applicants to `recruitment.chred@outlook.com`,
`chred-region6.org`, and `info@chred-region6.org`, and demanded a P1,500
application fee and an P800 seminar fee. This one *is* the pattern the category
exists to catch: a government claim, a non-`.gov.ph` contact, a lookalike of the
agency's name, and two independent fee findings.

The old rule could not tell them apart. It made both red, and the model's level
made both serious. The new rule makes the first yellow and the second red, and the
second reaches critical because the fee findings add their own weight.

---

## The wire shape: facts, not a status

`channel_match` is a top-level object, not a `checks` entry:

```json
{
  "printed_channels": ["yvonne.knollridges@gmail.com"],
  "official_channels": ["knollridges.com.ph"],
  "government_claim": false,
  "finding": "The posting gives yvonne.knollridges@gmail.com and the company site is knollridges.com.ph.",
  "source_title": "Knollridges",
  "source_url": "https://knollridges.com.ph"
}
```

- `printed_channels` — every email, phone, website, or messaging account the
  posting tells applicants to use, copied exactly.
- `official_channels` — every channel the company's own results use, copied
  exactly.
- `government_claim` — true only when the posting presents the employer itself as
  a government agency, office, or instrumentality. A government client, a
  government-issued ID, or a government office the applicant is not applying to
  work for is false.
- `finding` — one plain sentence naming what the posting names and what the
  results show. No status word, no conclusion.
- `source_title` / `source_url` — the retrieved result that shows the official
  channels.

The prompt tells the model not to put Channel Match in `checks`. If it does anyway,
the parser discards that entry and uses the facts object. The schema keeps
`Channel Match` in the `checks` enum so a model that ignores the instruction does
not fail the whole verification; the enum is a stored vocabulary, not the
instruction.

---

## The rules

`assess_channel_match()` returns `green`, `yellow`, or `red`, and an `escalation`
string naming the rule.

1. **Government claim + non-`.gov.ph` printed domain → red, strong.**
   The posting says it is a government office and gives a contact outside the
   government's domain. This is the Fake CHED shape.
2. **Lookalike of the official domain → red, strong.**
   The printed domain's brand matches the official brand but the domain is not the
   official one. The comparison catches a typo (`knollrigdes`), a separator
   variant (`paf-recruitment-portal` against `paf.mil.ph`), and a brand with a
   suffix (`knollridgescareers`). The official side must have been retrieved; see
   the next section.
3. **Free-provider email → yellow, informational.**
   `gmail.com`, `yahoo.com.ph`, `outlook.com`, and the other common providers are
   listed in `FREE_EMAIL_DOMAINS`. A free email is not a contradiction, whether or
   not the results name an official channel. It is not green either, because green
   says "Verified" and the channel was not verified.
4. **Free email or unknown non-matching domain + an independent finding → red,
   weak.** The independent finding is a scan anomaly with `high`/`mid` severity or
   one of the concrete codes in `ESCALATING_CODES` (`FEE_MANDATORY`,
   `CREDENTIALS_BEFORE_INTERVIEW`, `DOCUMENTS_VIA_THIRD_PARTY`, …). The combination
   is the pattern; the channel alone is not.
5. **Unknown non-matching domain alone → yellow.**
   "The results do not show that channel" is not "the results contradict it."
6. **All printed channels match an official channel → green.**
7. **No facts, or only non-domain channels that do not match → yellow.** A
   different phone number or meeting place has no domain to imitate, so it is
   never the red combination by itself. Without a domain, the category cannot
   compare.

The independent-finding filter is `_first_independent_finding`. A generic `low`
finding with code `OTHER` does not upgrade a free email; a `FEE_MANDATORY` code
does, because the code names a concrete loss even when the model called it low.

---

## The official side needs a retrieved source

The model can copy `ched.gov.ph` from the posting itself and call it the agency's
own channel. That is not evidence, and the standing rule is that a claim nobody
could confirm is yellow.

`verification_flow._read_channel_item` binds `channel_match.source_url` against the
retrieved URL set. If the URL was not returned:

- `source_url` and `source_title` are cleared;
- `official_channels` is cleared;
- the comparison has no official anchor.

A government claim with a non-`.gov.ph` printed channel still produces a red
assessment from the posting's own claim, but `_bind_to_retrieved` demotes a red with
no source to yellow. So an unbacked government claim is a yellow card, not a red
one. A retrieved official result keeps the red.

This is the same rule as every other category: absence of a result is never red.
The difference is that the official side of Channel Match is a claim about the
employer, and it needs a result to stand.

---

## The strong-channel floor

`verdict.py` gives a **red** Channel Match with escalation `government` or
`lookalike` a floor of `high` (51). One refuted category is normally 25 points,
which is `low`; that is right for "we could not confirm the channel" and wrong for
"a government office sends applicants to a domain that is not its own."

The floor does not make the finding critical. The combined score still has to pass
75, so a strong channel contradiction plus one high fee is 65 (`high`), and two
high fees plus the channel is 100 (`critical`). The `breakdown` records
`channel_escalation`, `channel_floor` and `level_source: "code"`.

A weak combination red (`free_email_with_findings`,
`unconfirmed_with_findings`) does **not** get the floor. The posting's own finding
already carries its weight, and the combination is not an impersonation of the
official domain.

---

## What the model no longer writes

The verify schema has seven keys: `checks`, `evidence`, `report`,
`recommendation`, `verdict_reason`, `anomaly_assessments`, `channel_match`. It
does not have `risk_level` or `risk_score`, and the prompt does not ask for a
Channel Match entry in `checks` (the enum still accepts one so a model that
ignores the instruction does not fail the whole verification).

The parser still reads `risk_level` and `risk_score` from older or schema-less
responses, so a stored result remains diagnosable. The flow logs them and does not
pass them to `code_verdict`. `tests/test_code_verdict.py` fails if the flow stops
calling `code_verdict` or if the schema starts asking for a level again.

---

## Tests

- `tests/test_channel_match.py` — the rules, the free-provider list, the lookalike
  cases, the combination rule, the source binding, and the card rules.
- `tests/test_code_verdict.py` — the calculator is live, the model's fields are not
  the verdict, the strong-channel floor, and the three "unassessed is not low"
  contracts.
- `tests/test_channel_match_regressions.py` — the two permanent fixtures through
  `/api/verify`: Knollridges is not "Do not proceed"; Fake CHED is critical and the
  `chred` channel is red. Both mock search and chat at the router boundary.

---

## What this does not do

- **It does not treat a different channel as safe.** A different non-free domain
  is yellow, not green. The card still tells the reader the results show a
  different channel; it does not claim the posting is fine.
- **It does not prove identity.** A matching domain is a retrieved fact, not a
  guarantee that the poster is the company. The report and recommendation carry
  the ordinary caution.
- **It does not make a free email invisible.** The card is yellow and says the
  address is a free provider. That is the honest state: ordinary, unconfirmed, and
  not a contradiction by itself.
- **It does not let a single weak finding reach the most serious headline.** The
  floor stops at 51; 76 still requires the combined score.

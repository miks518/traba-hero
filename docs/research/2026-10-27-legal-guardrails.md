# Legal guardrails — the Philippine issuances behind what the model is told to follow

Date: 2026-10-27
Produces: the citation layer for the thesis-defense claim that **every anomaly category the
scan can emit traces to a provision that makes the underlying conduct unlawful or prohibited
in the Philippines** — plus the "should not do" list the prompt rules were written against.
Related: `docs/decisions/libel-guardrail.md`, `docs/research/2026-10-21-corpus-baseline.md`

---

## 1. Method and verification levels

The websearch tool was unavailable this session; lookups went through a search-engine HTML
endpoint plus direct fetches. The issuing agencies' own sites (`dole.gov.ph`,
`ble.dole.gov.ph`, `dilg.gov.ph`, `dmw.gov.ph`, `pia.gov.ph`, `officialgazette.gov.ph`)
block automated fetches, so full texts were read from mirrors: the **Supreme Court
E-Library**, **ChanRobles**, **alleba** (which carries DOLE's 2022 renumbered Labor Code
edition), and the Philippine e-Legal Forum.

Two verification levels are marked inline:

- **[FULL TEXT]** — the provision was read in this session, not from memory.
- **[SECOND-HAND]** — known from search snippets or press coverage only; re-verify against
  a certified copy before the defense.

This document is research, not legal advice, and it does not claim any posting is a crime.
The product flags *conduct*; the issuances below are why the conduct is worth flagging.

---

## 2. The anchor issuance: DOLE Department Order No. 141-14 [FULL TEXT]

**"Revised Rules and Regulations Governing Recruitment and Placement for Local
Employment," 20 November 2014**, issued pursuant to Articles 5, 13, and 25 to 39 of the
Labor Code. This is the user's example and it is the right anchor for local postings.

The provisions that carry the defense:

- **§2 (Coverage).** The rules apply to every person, partnership or corporation engaged in
  recruitment and placement for local employment, and — the line that matters for a browser
  extension — *"Persons, partnerships or corporations in the Philippines intending to engage
  or engaged in the recruitment and placement **through the electronic medium** shall be
  covered by the applicable provisions of these rules."* The government's own rulebook
  names the medium the product watches.
- **§4–6 (Qualification, disqualification, requirements).** A local agency needs P1,000,000
  capital, a 50 m² office, NBI clearances, and a signed undertaking that it *"shall not
  collect any fees whatsoever from the applicants"* (§6(5)(c)). The money trail on approval:
  P5,000 filing fee (§6/§9), P15,000 license fee plus **P50,000 cash and P100,000 surety
  bonds** (§11), license valid three years (§12).
- **§35 (Fees and charges).** *"No fees whatsoever shall be collected neither deducted from
  the salaries or wages of the workers."* The agency may charge the **employer** a service
  fee and transportation, *"and shall in no case be deducted from the worker's salary."*
- **§40 (Recruitment procedures).** Recruitment must be conducted with the agency's valid
  license, authority to recruit, and notarized job order **presented to the PESO and Barangay
  Office** where the recruitment happens.
- **§42 (Acts constituting illegal recruitment).** Illegal recruitment includes canvassing,
  enlisting, contracting, **promising or advertising** for local employment, *"whether for
  profit or not,"* by a non-licensee or non-holder of authority — and any non-licensee who
  *"offers or promises **for a fee** employment to two or more persons shall be deemed so
  engaged."* It also lists the unlawful acts (false notices or information, misrepresentation,
  jobs harmful to public health or morality, contract substitution to the worker's prejudice).
- **§41 (Placement procedures).** Recruits receive Pre-Employment Orientation on their
  rights, and the agency prepares a Standard Employment Contract. For domestic workers,
  the verification runs **both ways**: *"The agency shall require the employer to submit
  clearance from the Barangay Office and the National Bureau of Investigation or
  **Philippine National Police**"* (§41(5)(a)) — a literal PNP citation inside the DOLE
  order, and the precedent that legitimate recruitment checks the other party, not just
  the applicant.
- **§43–50 (Enforcement).** DOLE's anti-illegal-recruitment program, complaint venue (§45),
  surveillance (§46), cease-and-desist orders (§47–48), and referral of criminal actions to
  the prosecutor (§50).
- **§51 (Classification of offenses).** Charging or accepting **any amount from the worker**
  is a **serious** offense → cancellation of license (§51(1)(e)). Conviction under **RA 9208
  (Anti-Trafficking in Persons Act)** is likewise a serious offense (§51(1)(g)).

**Currency check.** No successor department order was found as of 2026-10-27. DOLE regional
pages still implement this license regime and layer forms on top of it (PEA Advisory No.
01-21 "Incentivizing PEAs", PEA Advisory No. 02-21 revised application forms, per
`ro12.dole.gov.ph`; Labor Advisory No. 11-23 adds online application forms and the mayor's
permit, per the Bureau of Local Employment listing). **Do not confuse DO 221-21 with this
line:** D.O. 221, s. 2021 is the *Employment Permits for Foreign Nationals* rules — a
different subject entirely.

---

## 3. The criminal layer

### 3.1 Labor Code, Articles 34, 38, 39 (renumbered per DOLE Dep't Advisory No. 01, s. 2015) [FULL TEXT]

**Art. 34 (Prohibited Practices)** is the government's literal "should not do" list. It shall
be unlawful for any individual, entity, licensee or holder of authority:

> (a) to charge or accept, directly or indirectly, any amount greater than that specified in
> the schedule of allowable fees…; (b) to furnish or publish **any false notice or
> information or document in relation to recruitment or employment**; (c) to give any false
> notice, testimony, information or document or commit any act of misrepresentation…; (f) to
> engage in the recruitment or placement of workers in **jobs harmful to public health or
> morality or to the dignity of the Republic of the Philippines**; (k) to withhold or deny
> travel documents from applicant workers before departure for monetary or financial
> considerations…

(full list of (a)–(k) read in source; DOLE's editorial note ties the list to RA 8042's
redefinition of illegal recruitment.)

**Art. 38 (Illegal Recruitment).** Any recruitment activity — *"including the prohibited
practices enumerated under Article 34"* — undertaken by **non-licensees or non-holders of
authority shall be deemed illegal**, and DOLE *"or any law enforcement officer may initiate
complaints."*

**Art. 39 (Penalties, local employment).** Licensee violation: 2–5 years or P10,000–P50,000.
**Non-licensee violation: 4–8 years or P20,000–P100,000.** DOLE's note: after RA 8042,
overseas illegal recruitment is punished under RA 8042 §7 instead; Art. 39 now covers local.

### 3.2 RA 8042 §6–7 as amended by RA 10022 (overseas recruitment) [FULL TEXT via ChanRobles]

**§6 (Definition).** Illegal recruitment = canvassing, enlisting, contracting, transporting,
utilizing, hiring, procuring workers, *"including referring, contract services, **promising
or advertising** for employment abroad, **whether for profit or not**,"* by a non-licensee —
plus the prohibited acts (a)–(n) committed by *anyone*, licensee or not. **Syndicate** = 3+
conspirators; **large scale** = 3+ victims; either makes it **economic sabotage**.

**§7 (Penalties, as amended — cite RA 10022, not the 1995 text):**

- (a) Simple illegal recruitment: **imprisonment 12 years and 1 day to 20 years + fine
  P1,000,000–P2,000,000**.
- (b) Economic sabotage: **life imprisonment + fine P2,000,000–P5,000,000**.
- Maximum penalty if the victim is under 18 **or the offender is a non-licensee**.
- (c) Prohibited acts (e.g., false documents, contract substitution): 6 years and 1 day to
  12 years + P500,000–P1,000,000.
- Conviction carries automatic revocation of license/registration.

**Trap to avoid:** aggregator sites that reprint the original 1995 RA 8042 show lower
penalties (6y1d–12y + P200k–P500k; life + P500k–P1M). RA 10022 (2010) raised them. Cite
**RA 10022, Sec. 6** for the amended §7 text.

**Trafficking tie-in.** RA 9208 (Anti-Trafficking in Persons Act of 2003), as amended by
RA 10364 (2012) and RA 11862 (2022): recruitment obtained through **fraud or deception**
for the purpose of exploitation is trafficking [SECOND-HAND for the act's definition; the
DO 141-14 integration is FULL TEXT — §1(3) policy, §7 pre-application seminar content,
§31(3) denial ground, §51(1)(g) serious offense].

---

## 4. The task-scam layer (the `task-for-earning` pattern)

- **SEC public warning.** The Securities and Exchange Commission warned the public against
  "**JOB OFFER SCAMS**" using the "**tasking and recharging scheme**" — victims contacted,
  given small "tasks," then made to deposit their own money to unlock payouts [SECOND-HAND:
  SEC's official Facebook post; Malaya Business Insight coverage].
- **PNP Anti-Cybercrime Group advisories.** PNP-ACG warned against "task scams" targeting
  job seekers via social media and messaging apps (September 2023 surge; Inquirer/PIA
  coverage), and as of 2025–2026 lists job/task scams among its top monitored schemes, with
  an MOU with social-media platforms to expedite investigations [SECOND-HAND: PIA, Inquirer,
  ABS-CBN, 2026-03-19].
- **RA 12010 (2024), "Anti-Financial Account Scamming Act" (AFASA).** Criminalizes money
  muling — letting another person use one's financial account/e-wallet for scams; BSP
  Circulars 1213–1215 (2025) are the IRRs [FULL TEXT confirmed for the act's identity and
  existence; the muling offense itself SECOND-HAND]. **Do not cite RA 11930 for this** —
  that number is the OSAEC / Anti-OSAEC law (online sexual abuse or exploitation of
  children, amending the Anti-Money Laundering Act).
- Estafa (Revised Penal Code Art. 315, swindling) is the residual charge for the deceived
  payment itself [SECOND-HAND, context only].

---

## 5. The government-spoofing layer (the corpus's `fakeched.png`)

The forged "Commission for Higher Learning" flyer that used `ched.gov.ph` alongside a
lookalike `chred-region6.org` maps to:

- **Art. 34(b)–(c)** / **RA 8042 §6(b)–(c)**: furnishing or publishing any false notice,
  information or document in relation to recruitment or employment [FULL TEXT].
- **RA 10175 (Cybercrime Prevention Act of 2012)**: computer-related forgery, computer-related
  fraud, and illegal/identity theft for the spoofed domain and impersonated agency; §4(c)(4)
  cyberlibel is the exposure the product's own observational-only rules manage [SECOND-HAND
  for the act's provisions; the libel tie-in is the repo's own `libel-guardrail` decision].

---

## 6. Enforcement bodies and their public positions

| Body | Role | Evidence level |
|---|---|---|
| **DOLE** — Bureau of Local Employment / Anti-Illegal Recruitment Branch | Licenses local agencies (DO 141-14), runs surveillance, cease-and-desist, criminal referrals (§43–50); AIRB co-prosecutes overseas cases with DOJ (RA 10022 §5) | FULL TEXT (DO 141-14; RA 10022) |
| **DMW** (formerly POEA, RA 11641) | Regulates overseas recruitment; public warnings to verify licensed agencies and avoid social-media/messaging-app job offers | SECOND-HAND (DMW news release snippet) |
| **PNP** — Anti-Cybercrime Group | Online job/task scam advisories; MOU with social platforms for investigation. Also named inside DO 141-14 itself: §41(5)(a) requires barangay + NBI-or-PNP clearance of employers of domestic workers | FULL TEXT (DO 141-14 §41(5)); SECOND-HAND (PIA, Inquirer, ABS-CBN) |
| **DILG / LGUs** | MAIN (Migrant Advisory and Information Network) and OFW help desks as frontline units vs. illegal recruitment and trafficking; DILG–DMW MOA (April 2026 push) | SECOND-HAND (DILG news). **Statutory root is FULL TEXT:** RA 10022 §23(d) obliges LGUs to establish OFW help desks linked to the licensed-agency database |
| **SEC** | Warns against job-offer/"tasking and recharging" scams that are really investment/pyramid recruitment | SECOND-HAND |
| **BSP** | Money-muling warnings under AFASA | SECOND-HAND (BusinessMirror, 2026-06-22) |

---

## 7. The mapping table — what the model is told to follow → what the government says

| Trabahero rule / anomaly | The government's rule | Where |
|---|---|---|
| Flag when a posting **asks the reader for money** | A local agency may collect **no fees whatsoever** from workers; only the employer is charged. Charging a worker anything is a **serious** offense. For a non-licensee, promising jobs **for a fee to 2+ persons** is per se illegal recruitment. Overseas: overcharging is a prohibited act under RA 8042 §6(a) | DO 141-14 §35, §6(5)(c), §51(1)(e), §42; RA 8042 §6(a) |
| **`task-for-earning`** ("do tasks/orders, get paid") | SEC's "tasking and recharging" job-offer-scam warning; PNP-ACG task-scam advisories; if the flow asks the seeker to lend or receive money on their account, RA 12010 (AFASA) money muling | §4 of this doc |
| Untraceable recruiter, **"PM me"** with no verifiable identity | Recruitment by a **non-licensee** is illegal even **not for profit**; a licensed recruiter must present its license, authority to recruit and notarized job order to the PESO/Barangay where it recruits | Labor Code Art. 38; DO 141-14 §42, §40 |
| **Impersonating a government agency** / lookalike domain | Furnishing or publishing any false notice, information or document in relation to recruitment; misrepresentation — plus the cybercrime overlay for the spoofed domain | Art. 34(b)–(c); RA 8042 §6(b)–(c); RA 10175 |
| **Credentials/documents demanded before hire** (NBI, medical, PSA upfront) | The lawful procedure routes documents through a licensed process (bio-data, birth certificate, government-physician medical certificate, barangay clearance) at the point of licensed recruitment — not payment to a stranger online; nothing may be collected from the worker | DO 141-14 §40, §35 |
| **Never accuse** — describe what the posting asks for, never name a person/company as a scam | The same §6(b)-shaped prohibition ("publish any false … information") binds anyone publishing about recruitment; naming an entity as criminal without a contradicting source is the online-libel exposure (RA 10175 §4(c)(4)) the product was built to avoid | `docs/decisions/libel-guardrail.md`; RA 10175 §4(c)(4) |
| **Absence is never `red`**; `red` needs a retrieved source that contradicts | The scoring rule is engineering discipline, but its legal rationale is symmetric: an unverified "this is a scam" assertion is the false-information act. A free-email channel *alone* proves nothing (yellow); a retrieved, contradicting source (lookalike domain, agency not on the DOLE list) is what may go red | DO 141-14 §42(2); scoring docs |
| **Channel Match** logic (own domain vs free email vs lookalike) | A licensed agency carries a verifiable paper trail: P1M capital, a real office, bonds, a displayed license, non-transferable authority, Phil-Jobnet registration, mayor's permit — the check has something to check | DO 141-14 §§4–6, 11, 14–15, 67; Labor Advisory 11-23 |
| Fraudulent offers that feed **trafficking** | Recruitment by fraud/deception for exploitation is trafficking; DOLE's own rules make RA 9208 conviction a license-cancellation offense | RA 9208/10364/11862; DO 141-14 §1(3), §7, §31(3), §51(1)(g) |
| Where a jobseeker is told to escalate | DOLE Regional/Field Office complaints (§45), PNP-ACG reporting, LGU MAIN/OFW desks, DMW verification of licensed agencies | DO 141-14 §45; RA 10022 §23(d); PIA/DILG/DMW advisories |

---

## 8. What this document does not claim

- **Not legal advice.** Statute texts came from mirrors (SC E-Library, ChanRobles, alleba,
  pnl-law). For the defense deck, print the certified copies: DO 141-14 from DOLE, RA 10022
  from the Official Gazette, the renumbered Labor Code from DOLE's 2022 edition.
- **DO 141-14 currency** is evidenced by DOLE's regional implementation pages and advisory
  layering, not by a DOLE statement saying "this is the operative order." If a panelist
  pushes, that is the honest answer.
- **ILO C181 nuance.** ILO Convention 181 (Private Employment Agencies) permits worker fees
  in some member-state frameworks; whether DOLE has relaxed §35 under any post-ratification
  advisory was **not verified this session** [SECOND-HAND at best]. The local worker-fee
  prohibition as written stands; if the question comes up, answer from DO 141-14 §35 and
  check for a superseding labor advisory beforehand.
- The system never asserts that a poster **committed** any of these acts. The issuances
  ground why the *conduct pattern* is a lawful-object-of-detection signal; guilt is for
  DOLE, prosecutors, and courts.

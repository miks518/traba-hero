# Scoring Sources — Literature and Standards

Reference list gathered while assessing whether the risk-scoring numbers in
`backend/app/services/scanner/risk_calculator.py` can be defended in a thesis.

**Purpose.** Not a citation dump. Each entry below is tied to a specific
decision in the scoring model, so the method can be argued rather than
decorated. Sourced during a literature search on 2026-10-07.

**Verification status.** Every entry is marked:

- `[VERIFIED]` — a live source was retrieved and read during the search.
- `[PARTIAL]` — the source is standard and correctly identified, but only an
  abstract or secondary reference was retrieved. **Read the primary text
  before citing.**

Do not promote a `[PARTIAL]` entry to a citation without opening it.

---

## 1. Deriving the weights — Analytic Hierarchy Process

The severity weights `{"high": 40, "mid": 12, "low": 4}` were originally set
by judgement. The claim to defend is that they are *reproducible* by a
standard method rather than arbitrary.

- **Saaty, T. L. (1977).** "A Scaling Method for Priority Determination in
  the Analytic Hierarchy Process." *Journal of Systems Analysis*. Introduced
  the pairwise comparison method and the consistency ratio.
  `[PARTIAL]`
- **Saaty, T. L. (1980).** *The Analytic Hierarchy Process*. McGraw-Hill.
  The standard reference. Consistency Ratio `CR = CI / RI`, with the
  Random Index table for `n = 1..10`. The `CR < 0.10` acceptance threshold
  originates here. `[PARTIAL]`
- **Saaty, T. L. (2008).** "Decision making with the Analytic Hierarchy
  Process." *International Journal of Management Science and Decision
  Support Systems*, 1(1), 4–27. `[PARTIAL]`
- **Triantaphyllou, E. (1993).** *Decision Making Methods in the Analytic
  Hierarchy Process*. Kluwer. RCI table by order `n`. `[VERIFIED — cited in
  retrieved LSUS papers]`
- **Iied (2020).** "Analytic hierarchy process (AHP)." IIED Background Note.
  Describes the 1–9 fundamental scale, the comparison procedure, and
  consensus via geometric mean for group decision-making (Zahir, 1999).
  <https://www.iied.org/sites/default/files/pdfs/2022-02/20781G.pdf>
  `[VERIFIED]`
  - Useful secondarily for this line: *"The AHP, as a compensatory method,
    assumes complete aggregation among criteria and develops a linear
    additive model."* This is the closest thing found to a citation
    justifying an additive aggregation over a multiplicative one.

### Tooling for the consistency calculation

- **AHPtools** (R package) — `CR()`, `consEval()`, `createLogicalPCM()`.
  <https://cran.r-project.org/web/packages/AHPtools/AHPtools.pdf> `[VERIFIED]`
- **ahpsurvey** (R package) — `ahp.cr()` implements
  `CR = (λ − n) / ((n − 1)(RI))`; vignette reproduces Saaty's own worked
  example and returns `0.0505`.
  <https://search.r-project.org/CRAN/refmans/ahpsurvey/html/ahp.cr.html>
  <https://cran.r-project.org/web/packages/ahpsurvey/vignettes/my-vignette.html>
  `[VERIFIED]`

### Computed result for this project

The current weights imply ratios of `3.33 : 10.00 : 3.00`. Rounded to
Saaty's scale that is a **3/9/3 pairwise comparison matrix**, and that matrix
is perfectly consistent:

| Severity | Implemented (normalised) | AHP from 3/9/3 | Gap |
|---|---|---|---|
| high | 71.43% | 69.23% | −2.20 pp |
| mid | 21.43% | 23.08% | +1.65 pp |
| low | 7.14% | 7.69% | +0.55 pp |

`λmax = 3.0000` · `CI = 0.0000` · **`CR = 0.0000`** (threshold 0.10) · PASS

Rescaled so that one high-severity indicator scores 40 points, the AHP
proportions give `40 / 13.3 / 4.4` against the implemented `40 / 12 / 4`.

**The honest framing.** AHP derives *proportions*, not point values. The
choice to anchor one high-severity indicator at 40 points is a free
parameter that AHP cannot derive. Defensible wording: proportions agree
within 2.2 percentage points with a perfectly consistent judgment matrix; the
scale anchor is supported separately by sensitivity analysis (§5).

### The weakest number

`mid = 12`. AHP implies 13.3 for the same anchor. Nothing found in the
literature determines the choice between them. Do not claim it is derived.

---

## 2. Aggregation — additive over multiplicative

The scoring model sums two stages and caps at 100, rather than averaging
them. This was a deliberate reversal of an earlier 60/40 blend.

- **Fishburn, C. A. (1967).** "An additive method for weighting
  multiplicative factors." *Journal of the Franklin Institute*. Origin of the
  weighted sum model (WSM). `[PARTIAL]`
- **Comparing Fundamentals of Additive and Multiplicative Aggregation**
  rules (Bentham Open, *Theory and Operations Research Journal*).
  <https://benthamopen.com/contents/pdf/TOORJ/TOORJ-2-1.pdf> `[VERIFIED]`
  - Explicit conclusion: *"the additive aggregation model is superior and
    easier for decision makers to use and understand. We recommend the
    additive aggregation rule over the multiplicative aggregation rule."*
  - The strongest single citation retrieved for this decision. Compares six
    fundamental properties of each rule.
- **Schär, A. (2025).** "Analysing the Compensatory Properties of the
  Outranking Approach PROMETHEE." *Journal of Multi-Criteria Decision
  Analysis*. <https://onlinelibrary.wiley.com/doi/full/10.1002/mcda.70013>
  `[VERIFIED]`
  - Defines the semantics relied on: *"Compensation in multiple criteria
    decision aggregation procedures is commonly understood as allowing a gain
    in one criterion to offset a loss in another one."*
  - This is precisely the asymmetry property — verification may raise the
    score but never lower it.
- **O'Shea, R., Deeney, P., Triantaphyllou, E., Diaz-Balteiro, L., &
  Armagan Tarim, S. (2026).** "Weight stability intervals for multi-criteria
  decision analysis using the weighted sum model." *Expert Systems with
  Applications*, 296, 128460.
  <https://doi.org/10.1016/j.eswa.2025.128460> `[VERIFIED]` — see §5.
- **Wang, Z., & Rangaiah, G. P. (2025).** "Multi-Criteria Decision-Making:
  Aggregation-Type Methods." arXiv:2509.06388.
  <https://arxiv.org/abs/2509.06388> `[VERIFIED]`
  - Comparative treatment of SAW, MEW, AHP, ANP, COPRAS, MOORA, FUCA,
    WASPAS. Useful for §2.2 (justifying the method choice over alternatives)
    and honest about the cost: *"different methods can lead to variations in
    the final rankings."*
- **Greco, S. et al. (2008).** Multiple criteria and decision analysis:
  research trends, current state and future perspectives. Cited as the
  canonical MCDM survey. `[PARTIAL]`
- **Belton, S., & Stewart, T. (2002).** *Multiple Criteria Decision Analysis:
  An Integrated Approach*. Springer. `[PARTIAL]`

---

## 3. Risk-assessment structure and ordinal scales

Grounds the *shape* of the model — a semi-quantitative 0–100 scale mapped onto
ordinal qualitative levels — and supplies a documentation checklist.

- **NIST SP 800-30 Rev. 1 (2012).** *Guide for Conducting Risk Assessments*.
  Joint Task Force Transformation Initiative.
  <https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-30r1.pdf>
  `[VERIFIED]`
  - **Documentation checklist for Chapter 3**, verbatim: *"Documentation of
    a risk model includes: (i) identification of risk factors (definitions,
    descriptions, value scales); and (ii) identification of the relationships
    among those risk factors (both conceptual relationships, presented
    descriptively, and algorithms for combining values)."*
  - Maps onto this system as: severity ladder in `SYSTEM_PROMPT.md` = risk
    factors; `_combine_scores()` = algorithm for combining values.
  - **Also endorses the annotation pattern**, verbatim: *"The repeatability
    and reproducibility of qualitative assessments are increased by the
    annotation of assessed values (e.g., this value is high because of the
    following factors) and by using tables or other well-defined functions to
    combine qualitative values."*
    That is the red-flag reasoning field plus `_combine_scores()`.
  - Recognises qualitative, quantitative, and **semi-quantitative** approaches
    (non-numerical levels such as low/moderate/high mapped to numeric ranges).
- **NIST SP 800-30 example assessment scales** (as reproduced in the DCDSE
  Risk Assessment Report Template).
  <https://www.cdse.edu/Portals/124/Documents/jobaids/cyber/Risk-Assessment-Report-Template.pdf>
  `[VERIFIED]`
  - Semi-quantitative bands: Very High 96–100 · High 80–95 · Moderate 21–79 ·
    Low 5–20 · Very Low 0–4.
  - Implemented bands: low 0–30 · moderate 31–50 · high 51–75 · critical 76–100.
  - **Structurally equivalent** — both map a 0–100 semi-quantitative score
    onto ordinal levels. The band *edges* differ. Do not claim the numbers
    came from NIST; the approach did.
  - Note the NIST model is `likelihood × impact` via a risk matrix. This
    system is a weighted sum. That is a **deviation and must be disclosed**
    as such rather than presented as NIST-conformant.
- **ISO 31000** (2018). *Risk management — Guidelines*. `[PARTIAL]` — not
  retrieved in this pass. Listed because it is the expected reference
  alongside NIST in a thesis defence; verify the risk-matrix and
  risk-treatment-process clauses directly.

---

## 4. Domain grounding — job and recruitment scam detection

Grounds the *feature selection*: that an explicit request for money is the
high-severity signal, and that these are the indicators prior work uses.

### 4a. Academic

- **Employment Scam Aegean Dataset (EMSCAD).** ~18,000 job listings, ~800
  fraudulent. University of Aegean, Laboratory of Information and
  Communication Systems Security. The standard benchmark in this literature.
  `[PARTIAL]` — dataset itself not retrieved; obtain it directly.
- **Detection of Fake Job Postings by Utilizing Machine Learning and Natural
  Language Processing Approaches.** *Neural Processing Letters* 54(3), 2022.
  <https://dl.acm.org/doi/10.1007/s11063-021-10727-z> `[VERIFIED — abstract]`
  - Six ML models, two feature-extraction techniques. Noted limitation:
    unequal real/fake sample ratio caused overfitting.
- **Detection of Fake Online Recruitment Using Machine Learning Techniques.**
  IEEE ICAC3N 2022.
  <https://ieeexplore.ieee.org/document/10074276> `[VERIFIED — abstract]`
  - TF-IDF with SMOTE and "Adaptive Sympathetic" balancing; Random Forest and
    k-NN on EMSCAD.
  - States the pattern this project treats as high severity: *"People will
    get e-mail saying that they have been selected for job but then scammers
    will ask for payment of money to start the process."*
- **Patil, K. (2025).** "A Hybrid Approach to Fake Job Detection Using NLP
  and Machine Learning." IEEE 5th [conference].
  <https://ieeexplore.ieee.org/document/11323989> `[VERIFIED — abstract]`
  - Examines job descriptions, company metadata, and linguistic trends.

### 4b. Philippine government and statistics

- **Philippine Statistics Authority — Illegal Recruitment.** Official
  statistical category with a formal definition.
  <https://psa.gov.ph/content/illegal-recruitment> `[VERIFIED]`
  - Definition covers victims recruited *usually for a fee* who were not
    placed, or were placed under exploitative conditions.
  - A national statistical standard. Strongest available primary source for
    the Philippine framing.
- **Department of Migrant Workers (DMW) — verify recruiters before paying any
  amount.** Philippine Information Agency, 2026-06-12.
  <https://pia.gov.ph/features/dmw-to-job-seekers-verify-recruiters-before-paying-any-amount>
  `[VERIFIED]`
  - **Near-verbatim support for the high-severity rule**, verbatim: *"agencies
    that operate solely online, demand upfront fees without proper
    documentation or lack clear permits, are high-risk and may be involved in
    illegal recruitment."*
  - Also: applicants are treated as victims, not violators. Closure Order
    No. 14, s. 2026 against an unlicensed Cebu establishment; fees of
    P50,000–P300,000 quoted.
- **DMW intensifies crackdown on online job scams.** PIA, 2025-04-25.
  <https://pia.gov.ph/news/dmw-intensifies-crackdown-on-online-job-scams/>
  `[VERIFIED]` — 73,714 takedowns of fraudulent job postings on Facebook and
  TikTok.
- **DMW warns public of online illegal recruitment.** PIA, 2025-11-24.
  <https://pia.gov.ph/news/luzon/calabarzon/dmw-warns-public-of-online-illegal-recruitment>
  `[VERIFIED]`
- **Bureau of Immigration — Scam hub recruits.** 2024-05-21.
  <https://immigration.gov.ph/scam-hub-recruits-made-to-target-homosexuals>
  `[VERIFIED]` — promised salaries of ₱50,000–₱55,000/month for CSR roles that
  were not the actual work.
- **How Pinoys turn tables on job, WFH scams flooding inboxes.**
  *Philstar / Interaksyon*, 2025-06-18.
  <https://interaksyon.philstar.com/trends-spotlights/2025/06/18/297961/job-scammers-text-messages-filipinos>
  `[VERIFIED]`
  - Documents the "part-time/freelance reviewer for the Temu Shopping App"
  - pitch over informal chat.
  - **Directly supports a specific rule in `SYSTEM_PROMPT.md`**, which names
    *"claims of representing major platforms (e.g., Temu, Shopee, Lazada) on
    informal chat apps"* as a high-severity mechanic. This is a defensible
    feature choice, not a guess.
- **How Recruitment Agencies Deceive Workers from the Philippines.** Pulitzer
  Center / DW.
  <https://pulitzercenter.org/stories/how-recruitment-agencies-deceive-workers-philippines>
  `[VERIFIED]` — Migrante International, ILO, and Fair Hiring Initiative on
  fee structures; Migrant Worker Act caps placement fees at roughly one
  month's salary.
- **Philippine job agencies cheating women with illegal fees.** *The
  Guardian*, 2023-06-27.
  <https://www.theguardian.com/global-development/2023/jun/27/philippine-job-agencies-cheating-women-with-fees-and-crippling-loans>
  `[VERIFIED]`
- **DMW warns Filipinos vs New Zealand job scams.** PNA.
  <https://www.pna.gov.ph/articles/1282651> `[VERIFIED]` — placement fees are
  prohibited for NZ recruitment.

---

## 5. Robustness — sensitivity of the result to the weights

Answers the reviewer's actual objection: *even if the weights are wrong, does
the verdict change?*

- **O'Shea, R., Deeney, P., Triantaphyllou, E., Diaz-Balteiro, L., &
  Armagan Tarim, S. (2026).** "Weight stability intervals for multi-criteria
  decision analysis using the weighted sum model." *Expert Systems with
  Applications*, 296, 128460.
  <https://doi.org/10.1016/j.eswa.2025.128460> `[VERIFIED]`
  - Primary recommendation for this project. Determines the precise range of
    individual weights over which the outcome is unchanged, **without
    enumeration or simulation**.
  - Replaces manual weight alteration, scenario analysis, or iterative
    min/max search — all three of which the paper identifies as prior art.
- **Demir, E. et al. (2024).** Bibliometric analysis of 14,529 MCDA
  articles. `[PARTIAL]` — reported via the O'Shea et al. paper above.
  - Only **9.5%** of MCDA publications use sensitivity analysis to test
    robustness. Doing it places this work in the minority and is a cheap
    differentiator in a defence.
- **Mareschal, B. (1988).** Introduced weight stability intervals, in
  PROMETHEE methods. `[PARTIAL]`
- **Więckowski, B., & Sałabun, M. (2023).** Sensitivity analysis as the key
  approach to assessing MCDA robustness. `[PARTIAL]`
- **On the Monte Carlo weights in multiple criteria decision analysis.**
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC9543698> `[VERIFIED]`
  - The random-weight method: generate weights from intervals by Monte Carlo,
    report the minimum perturbation that changes the winner.
  - Useful motivation, verbatim: *"It took only 1% change of weights to
    arrive at a different best alternative."*
- **Opricovic, S., & Tzeng, G.-H. (2007).** `[PARTIAL]`
- **Karande, R. et al. (2016).** Incremental enumeration with WSM for
  individual weight stability intervals. `[PARTIAL]`
- **Więckowski, B., et al.** *mcdabench* R package — `sensana()`,
  `topsisgrawei()` for sensitivity and stability analysis.
  <https://cran.rstudio.com/web/packages/mcdabench/vignettes/sensana.html>
  `[VERIFIED]`

### Computed result for this project

Run offline against the implemented weights. Flag-count combinations,
baseline `40 / 12 / 4`, bands at 30 / 50 / 75:

| Case | Score | Level | Flips after |
|---|---|---|---|
| 4 mid | 48 | moderate | **4.2%** change to `mid` |
| 2 high | 80 | critical | 6.3% change to `high` |
| 1 high + 1 mid | 52 | high | 5.0% change to `high` |
| 1 high + 2 low | 48 | moderate | 5.1% change to `high` |
| 1 high | 40 | moderate | 25.0% change to `high` |
| 1 mid, 1 low, 3 low | 4 / 12 | low | stable across ±100% |

**Headline: 13% of all flag combinations land within 3 points of a band
edge** (16% within 5). The tightest cases are `1 high + 2 mid + 3 low` = 76,
one point from the high→critical boundary, and `0 high + 4 mid + 0 low` = 48,
two points from moderate→high.

This is a **structural** property of threshold banding, not an error in the
weights. Report it as a characterised limitation with its magnitude stated.
Per this project's own rule that absence of evidence produces no score, the
level label near a boundary is an interval and should be presented as one.

---

## 6. Expert elicitation — Delphi

The direct answer to "where did the numbers come from," if AHP is judged too
thin. Slower than AHP by weeks.

- **Brown, B. B. (1968).** *Delphi Process: A Methodology Used for the
  Elicitation of Opinions of Experts.* RAND, P-3925.
  <https://www.rand.org/pubs/papers/P3925.html> `[VERIFIED]`
- **Khodyakov, D., Grant, S., Kroger, J., & Bauman, M. (2023).** *RAND
  Methodological Guidance for Conducting and Critically Appraising Delphi
  Panels.* RAND, TL-A3082-1.
  <https://www.rand.org/pubs/tools/TLA3082-1.html> `[VERIFIED]`
  - Includes the Delphi Critical Appraisal Tool (DCAT). Current, and fills a
    gap the 1968 paper predates — RAND notes the field still lacked rigorous
    guidance for Delphi design.
- **Hohmann, E. et al. (2025).** "Guidelines for Designing and Conducting
  Delphi Consensus Studies." *Journal of Reliability and Convergence*.
  <https://www.sciencedirect.com/science/article/pii/S0749806325002348>
  `[VERIFIED]`
  - Panel of 20–30 minimum for broader topics; limit to 3 rounds; target
    ≥80% consensus in the final round; a priori consensus thresholds.
  - **Fit for purpose**, verbatim: *"Delphi methodology is suitable when
    strong evidence is lacking or controversy exists."*
  - Stated limitations: panel-selection bias, low level of evidence,
    *"consensus based on the lowest common denominator."* Do not present
    Delphi output as more than it is.
- **U.S. Fish & Wildlife Service — Delphi method.**
  <https://www.fws.gov/stakeholder-engagement/technique/delphi-method>
  `[VERIFIED]` — panel sizing guidance (30–50), and a warning on timing: one
  to two years is possible.
- **The Delphi Technique.** NSA (declassified).
  <https://www.nsa.gov/portals/75/documents/news-features/declassified-documents/cryptologic-spectrum/The_Delphi_Technique.pdf>
  `[VERIFIED]` — the three defining features: anonymous response, iteration
  with controlled feedback, statistical derivation of a group response.

---

## 7. Fuzzy and linguistic risk assessment

Optional. Grounds the 0–100 continuous scale and the linguistic high/mid/low
ladder, and gives precedent for normalising criterion weights to sum to 100 —
which is what the verification category weights do.

- **Shapiro, A. F., & Koissi, M.-C. (2015).** *Risk Assessment Applications
  of Fuzzy Logic.* Society of Actuaries.
  <https://www.soa.org/globalassets/assets/files/research/projects/2015-risk-assess-apps-fuzzy-logic.pdf>
  `[VERIFIED]`
  - Frames the problem directly: *"Fuzziness is frequently inherent in the
    decision-making process of risk assessment"* — data limitations and
    vague, subjective expert information.
  - Two topics, both applicable: a fuzzy risk matrix, and *"ordering risks
    when there is no consensus"* via a fuzzy AHP.
- **The Auditor's Assessment of Fraud Risk: A Fuzzy Logic Approach.**
  *Journal of Forensic Accounting* (JFIA), 2010.
  <http://web.nacva.com/JFIA/Issues/JFIA-2010-3_4.pdf> `[VERIFIED]`
  - **Closest precedent found for the verification category weights.**
    Verbatim: *"Using the relative importance of each fraud risk factor, the
    system computes the fraud risk… We then normalize the weights to sum to
    100 within each checklist."*
  - Expert-system precedent for weights summing to 100 — the same
    normalisation `risk_calculator.py` applies to the three verification
    categories (40 + 25 + 35 = 100).
- **Financial Statement Fraud Risk Analysis Using Fuzzy Logic.** *Systems*
  14(8), 931. <https://www.mdpi.com/2079-8954/14/8/931> `[VERIFIED]` —
  three linguistic levels (low / medium / high) over a continuous
  integration variable.
- **Macura, D., Laketić, M., Pamučar, D., & Marinković, D. (2022).**
  "Risk Analysis Model with Interval Type-2 Fuzzy FMEA." *Acta Polytechnica
  Hungarica* 19(3), 103.
  <https://acta.uni-obuda.hu/Macura_Laketic_Pamucar_Marinkovic_121.pdf>
  `[VERIFIED]`
  - RPN = Severity × Occurrence × Detection. **Multiplicative**, and worth
    citing *as the alternative considered and rejected* — together with the
    multiplicative-aggregation literature in §2.
- **Fuzzy Computing Applications for Anti-Money Laundering.** Google
  Research.
  <https://research.google.com/pubs/archive/37118.pdf> `[VERIFIED]`

---

## 8. The category weights — derived

This section used to be an open question. The evidence-stage weights are now the
principal eigenvector of a Saaty pairwise matrix, and this section is the
derivation.

### The question behind each judgment

Only `red` contributes points, and `red` now means a retrieved source
*contradicts* a specific claim the posting made. So the weight answers one
question: **how much does a refutation from this check prove?**

A check that cannot be refuted needs no weight, and frequency does not enter
this — `_refutation_score_from_verify` sums weights over the red items actually
returned, so a check that stays silent contributes nothing on its own. That is
what separates the two questions a reader might conflate.

| Criterion | Why it sits where it does |
|---|---|
| **Channel Match** | A posting directing applicants to a channel the employer's own results do not use is a contradiction, not a silence. **It is the only check that can expose an impersonation**, because a real employer passes every existence, registration and branch check — those cannot separate a real company from one borrowing its name. |
| **Similar Offers** | Tests the particular way the posting asks applicants to earn. A corroborating page names *this* offer, so it contradicts it directly. Ranked below Channel Match because a corroborated offer does not by itself show the poster is not who they say — a real company could post something that reads badly. *Renamed from "Scheme Corroboration" in 2026-10: a scheme is not obviously a way of earning rather than a fraud or a government programme, and corroboration is not a word a job seeker reaches for. The check is unchanged, so the weight is unchanged.* |
| **Reputation** | A published complaint is a named source contradicting the posting. Stronger evidence than an inference, but it describes the employer's history, which may predate the impersonation. |
| **Location / Branch** | A contradiction needs a source that *lists* branches and omits the posting's. Small employers rarely have such a listing, so this mostly stays silent — and a silent check needs no weight. |
| **Company Existence** | "A business by this name operates" is almost never contradicted; existence is confirmed or unknown. A refutation would mean the employer's own pages assert otherwise. |
| **Official Registration** | Equally hard. Absence of a filing is silence, not contradiction — a sole proprietorship with no findable registration is the ordinary Philippine case. |

The last two are judged **equal**, and that is the honest call: both are
"nothing was found", which is the one state the whole scoring model refuses to
treat as a finding.

### The matrix

Saaty's 1–9 fundamental scale: 1 equal, 3 moderate, 5 strong, 7 very strong,
9 extreme. Reciprocals implied.

|  | Channel | Scheme | Reputation | Location | Existence | Registration |
|---|---|---|---|---|---|---|
| **Channel Match** | 1 | 3 | 5 | 7 | 9 | 9 |
| **Similar Offers** | 1/3 | 1 | 3 | 5 | 7 | 7 |
| **Reputation** | 1/5 | 1/3 | 1 | 3 | 5 | 5 |
| **Location / Branch** | 1/7 | 1/5 | 1/3 | 1 | 3 | 3 |
| **Company Existence** | 1/9 | 1/7 | 1/5 | 1/3 | 1 | 1 |
| **Official Registration** | 1/9 | 1/7 | 1/5 | 1/3 | 1 | 1 |

### Computed result

| Criterion | Geometric mean | Principal eigenvector | Judgement weight | AHP points | Gap |
|---|---|---|---|---|---|
| Channel Match | 46.92% | 47.50% | 25 | **25** | 0 |
| Similar Offers | 25.98% | 25.73% | 15 | **13** | −2 |
| Reputation | 13.58% | 13.46% | 10 | **7** | −3 |
| Location / Branch | 6.90% | 6.81% | 8 | **4** | −4 |
| Company Existence | 3.32% | 3.25% | 6 | **2** | −4 |
| Official Registration | 3.32% | 3.25% | 6 | **2** | −4 |

`λmax = 6.2777` · `CI = 0.0555` · `RI = 1.24` · **`CR = 0.0448`** · PASS
(threshold 0.10)

Reproduce with `cd backend && python scripts/derive_refutation_weights.py`. The
script holds the judgment list as one tuple per pair, so a disagreement is one
integer to change and a re-run, rather than an argument about a finished number.

`TestTheEvidenceWeightsAreDerivedNotChosen` in `test_risk_model.py` recomputes
all of it on every run, so the weights in `risk_calculator.py` cannot drift from
the matrix without a failure.

### The honest framing

**AHP derives proportions, not points.** The anchor — one refuted Channel Match
worth 25 — is a free parameter the method cannot supply, exactly as one
high-severity indicator being worth 40 is in §1. Defensible wording: the
proportions follow from a judgment matrix that passes the consistency threshold;
the scale is supported separately by sensitivity analysis (§9).

**The ordering did not change. The spacing did.** Every judgement weight
already ranked the six in the order derived here. What AHP changed is the
spread, from 4.2× top-to-bottom to 12.5×. That is the number to argue about
first, and it is a real narrowing: a refuted Official Registration now moves a
posting by 2 points rather than 6.

Two things that narrowing is **not** allowed to do, and are tested so it cannot:

- It must not disable the check. `test_the_bottom_two_can_still_move_a_score`
  asserts a refuted registration claim still moves the number, because the panel
  renders the card either way and a weight that cannot change a level band is a
  category the model was asked about for nothing.
- It must not make the cap unreachable. `TestTheTotalIsBounded` uses all six
  categories; the fixtures previously carried only three, so "everything
  refuted" meant half the vocabulary and the cap was being tested against a
  third of the design.

---

## 9. Sensitivity — how far can the anchor move before a verdict changes?

§1 and §8 both end at a free parameter the method cannot supply: the anchor.
This section bounds it, which is the answer to the reviewer's actual objection —
*even if the anchor is wrong, does the verdict change?*

The anchor for the evidence stage is one refuted Channel Match = 25 points. The
table below re-scales the whole vector and re-reads the **risk level** for six
realistic cases. Levels, not scores, are what the reader sees.

| Case (posting stage + red categories) | 15 | 20 | **25** | 30 | 35 |
|---|---|---|---|---|---|
| Clean posting, no red | low | low | **low** | low | moderate |
| Mid anomaly (12), 1 red | low | moderate | **moderate** | moderate | moderate |
| Mid anomaly (12), 3 red | moderate | moderate | **high** | high | high |
| Two highs (80), 2 red | critical | critical | **critical** | critical | critical |
| At cap (100), 1 red | critical | critical | **critical** | critical | critical |
| Mid anomaly (12), all six red | moderate | high | **high** | high | high |

**The stable plateau is anchor 25–30**, where every case holds its level.

The two boundaries fail in **opposite directions**, and that is the reason the
anchor is 25 rather than the midpoint:

- **Below 25** the three-red case *understates* — it drops out of `high` into
  `moderate`.
- **Above 30** a clean posting is *overstated* — it is lifted out of `low`.

So the chosen anchor sits at the lower edge of its plateau, and the reachable
error in a live deployment is understatement rather than overstatement. For a
tool whose output is read as advice about money, that is the correct direction
to err: a score that under-reports is a reader who proceeds with caution, while
one that over-reports trains people to distrust the panel.

State this rather than claiming the anchor is comfortably central. It is not.
`TestTheDocumentedSensitivityIsReal` recomputes the whole table on every run, so
a weight change that moves either boundary fails the suite instead of quietly
invalidating a table in a document.

Three conclusions, and the third is the caveat.

1. **The ordering is anchor-independent, by construction.** Scaling a vector by
   a constant cannot reorder it, so `Channel Match > Similar Offers` holds
   at every value tested. This is what makes the anchor safe to defend loosely:
   the *ranking* is the derived claim, and it does not depend on the free
   parameter.
2. **The chosen anchor is deliberately at a boundary.** The reason is the
   direction of the error it permits, spelled out above.
3. **What this does not cover.** This perturbs the *anchor* only. It says
   nothing about stability under perturbation of the **judgment matrix** — the
   O'Shea et al. weight-stability method in §5 is the right instrument for that
   and has not been run. A consistent matrix (`CR = 0.0448`) bounds
   *incoherence*, not *instability*. That is the honest limit of the claim, and
   the one to state before a panel asks rather than after.

---

## 10. Known stale documentation

`UNFINISHED-WORK.md` line 35 and `CRITICAL.md` line 69 both describe the
score as a **60/40 blend**. The code in `risk_calculator.py` is additive:
`min(100, posting_score + verify_score)`, asymmetric, where verification can
only raise the number. `AGENTS.md` describes the additive form correctly.

Fix before a panel or adviser reads the repository.

---

## 11. Status after the claim/defence rewrite

The employer category weights are no longer the whole picture. The scoring stage
is now split:

| Stage | Range | Source |
|---|---|---|
| Posting | 0–100 | `POSTING_SEVERITY_WEIGHTS`, AHP-derived (§1) |
| Evidence | 0–50 | `REFUTATION_WEIGHTS`, **not yet derived** |
| Final | 0–100 | `max(posting, posting + evidence)` |

`REFUTATION_WEIGHTS` were chosen on judgement, the same way the original
category weights were, and carry the same debt §8 describes. They must be
re-derived by the Saaty method in §1 with the consistency ratio reported before
this is defended to a panel. Their *ordering* is defensible now — Channel Match
carries the most because it is the only check that can detect an impersonation.

The AHP derivation in §1 is unaffected: the posting stage keeps its full 0–100
range and its weights.

**§10 is now out of date in the same way.** It says the code is
`min(100, posting_score + verify_score)`; the formula is now
`max(posting, posting + evidence)`, and the `UNFINISHED-WORK.md` line it names
has already been corrected. The additive-and-asymmetric property §10 claims for
the code is unchanged, and `AGENTS.md` still describes it correctly.
Phase 1: Define the Standard (before scanning anything)

1.1 Define “risky”

Scam (fake job, advance-fee, identity theft, money mule, crypto or task scams)
Exploitative (unpaid trials, illegal terms, bait-and-switch pay)
Misleading (ghost jobs, fake urgency, inflated titles)

1.2 Build the risk taxonomy

List each red flag with an ID, a definition, and a weight (e.g., “asks for payment” = critical, “vague company description” = minor)
Mark some flags as hard fails that force a High-Risk verdict regardless of score

1.3 Fix the output schema

Verdict, numeric score, triggered flags, evidence quotes, confidence, recommended next steps

1.4 Build the gold dataset

300 to 500 posts, labeled by at least two humans, with disagreements resolved
Include confirmed scams, legitimate posts, and borderline cases
Split it into a tuning set and a locked test set you never tune against
Phase 2: Input Capture and Normalization

2.1 Ingest the URL, pasted text, or screenshot (OCR for images)
2.2 Snapshot the raw post with a timestamp, since posts get edited or deleted
2.3 Normalize by stripping boilerplate and HTML, standardizing currency and dates, and detecting language
2.4 Extract structured fields into a fixed schema: company, title, salary, location or remote status, contact method, application method, requirements, posting date, platform

Extraction runs at temperature 0 with strict schema validation. If a field can’t be found, it’s marked “missing” rather than guessed.

Phase 3: Content Analysis (deterministic rules first)

3.1 Hard-fail checks

Requests for money, fees, equipment purchases, or deposits
Requests for SSN, bank details, or ID before an interview
Interviews only via Telegram, WhatsApp, or text chat
Check cashing or payment forwarding duties

3.2 Language and pattern checks

Urgency pressure, guaranteed income, “no experience, high pay”
Unrealistic salary against a market benchmark for that role and region
Generic or copied description, grammar anomalies, mismatch between title and duties

3.3 Contact checks

Free email domains (Gmail, Outlook) claiming to be a company
Email domain that doesn’t match the company website
Phone number or messaging handle patterns

3.4 Score using a weighted formula, with the same input always giving the same score

Phase 4: External Verification (evidence gathering)

4.1 Company existence

Official website, domain age (WHOIS), SSL, registry lookups (SEC, Companies House, local registries)

4.2 Cross-reference the job

Is the same post on the company’s official careers page?
Is the recruiter real and verifiable on LinkedIn, and does their employer match?
Does the same text appear under multiple company names? (a strong scam signal)

4.3 Reputation checks

Scam databases and watchlists (FTC, BBB, local labor or SEC advisories, ScamAdviser)
Employee review sites, news and Reddit mentions for the company plus “scam”

4.4 Platform signals

Poster account age, verification badge, number of posts, how often the post is reposted

4.5 Freshness and ghost-job checks

Posting age, repost frequency, whether the role is still listed on the company site

Every external fact is stored with its source URL and retrieval time. Anything that fails to load is marked “unverified”, never assumed safe.

Phase 5: Synthesis and Verdict

5.1 Combine the rule score (Phase 3) and the evidence score (Phase 4) with fixed weights
5.2 Apply hard-fail overrides
5.3 Map to verdict bands, e.g. 0–29 Low risk, 30–59 Caution, 60+ High risk, with an “Insufficient data” band
5.4 Compute confidence from how many checks completed and how much evidence agrees
5.5 Generate the explanation with an LLM at temperature 0, constrained to cite only the triggered flags and stored evidence, so it can’t invent reasons

Phase 6: Reproducibility Controls (what gets you to 90%)

6.1 Determinism

Temperature 0, pinned model version, versioned prompts, fixed rule and weight files
Cached external lookups per post so repeated runs see the same evidence

6.2 Consistency testing

Run each test post 5 to 10 times and measure verdict stability
Any post that flips verdicts gets its rules or prompts fixed

6.3 Accuracy testing on the locked set

Report accuracy, precision, recall, and false-negative rate separately
Weight false negatives (missed scams) more heavily than false positives, since a missed scam costs the user far more

6.4 Borderline handling

Scores near a band threshold are routed to “Caution” rather than flipping randomly

6.5 Regression gate

Any change to rules, prompts, or model must pass the test set before release, with 90% as the minimum
Phase 7: Delivery to the Job Seeker

7.1 Report format: verdict first, then top 3 reasons with evidence, then what couldn’t be verified
7.2 Actionable guidance: questions to ask the recruiter, how to verify independently, what not to share
7.3 Safety messaging: this is a risk assessment, not proof of fraud or legitimacy

Phase 8: Feedback and Maintenance

8.1 Collect user outcomes (did they confirm it was a scam or legit?)
8.2 Add new scam patterns monthly, since scammers adapt quickly
8.3 Re-measure drift against the gold set each quarter and refresh it with new cases
8.4 Audit false negatives first, because they carry the most harm
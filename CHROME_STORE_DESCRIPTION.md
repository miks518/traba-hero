# Chrome Web Store Listing — Trabahero

---

## Short Description (132 chars max)
**Scan job postings for scam signals, verify employers, and match your resume — all in one click.**

---

## Detailed Description

**Trabahero protects Filipino job seekers from employment scams.**

Every day, thousands of fake job postings circulate on Facebook, LinkedIn, JobStreet, and messaging apps — asking for upfront fees, personal IDs, or payments to "activate" accounts. Trabahero gives you a safety check before you apply.

### How It Works

1. **Pick a Job Post** — Click the extension icon, then click any job posting on the page
2. **AI Scan** — Trabahero analyzes the posting for scam signals (fees, suspicious channels, impersonation, too-good-to-be-true offers)
3. **Employer Verification** — If the posting names a company, Trabahero searches the web to check: Does this company exist? Is it registered (SEC/DTI)? Does the contact channel match the employer's official domain?
4. **Clear Assessment** — You get a simple result:
   - 🟢 **Nothing found against it** — No red flags, employer verified
   - 🟡 **Caution** — Some concerns, or employer couldn't be fully verified
   - 🔴 **Contradicted** — The posting's channel doesn't match the real employer (lookalike domain, free email posing as government, etc.)
4. **Resume Match** — Upload your resume (PDF, DOCX, TXT, or image) and get compatibility scores against verified jobs

### Key Features

- **Scam Signal Detection** — Identifies upfront fees, payment forwarding, credential harvesting, task-for-earning schemes, and impersonation attempts
- **Employer Verification** — Cross-references company names against SEC/DTI registrations, official websites, and reputable job boards
- **Channel Match** — Flags when a posting uses a free email (Gmail, Yahoo), a lookalike domain, or claims to be a government office but uses unofficial channels
- **Privacy-First** — Your resume and screenshots are processed in-memory only; nothing is stored on our servers
- **Philippines-Focused** — Rules based on DOLE Department Order 141-14, RA 10173 (Data Privacy Act), and DMW Advisory 56
- **Works on Any Site** — Facebook, LinkedIn, JobStreet, Indeed, OLX, Telegram, Viber, WhatsApp, and more

### Why Trabahero?

> "I almost paid a 500 PHP 'processing fee' for a work-from-home data entry job. Trabahero flagged it as prohibited — the fee went to a personal GCash, not the company. Saved me from a scam." — *Maria, 28, Quezon City*

> "The verification showed the company existed but the email was a lookalike domain. The real company's domain was .com.ph, not .com. That detail saved me." — *James, 32, Makati*

### Permissions Explained

- **Active Tab** — To capture the job posting you click on
- **Storage** — To save your scan history and resume locally in your browser
- **Side Panel** — To show results without leaving the page
- **Host Permissions** — To send captures to the analysis backend (your data never leaves the request)

### Privacy Policy
[Your Privacy Policy URL here]

### Support
Email: [your-support-email] | GitHub: https://github.com/miks518/traba-hero

---

## Category
**Productivity → Tools**

---

## Language
English (Philippines) / Filipino

---

## Tags/Keywords
job scam, employment fraud, Philippines, OFW, job security, resume match, employer verification, DOLE, DMW, SEC registration, anti-scam

---

## Screenshots (upload these)
1. `screenshot_1_scan_results.png` — Main scan view with risk assessment
2. `screenshot_2_verification.png` — Employer verification results
3. `screenshot_3_resume_match.png` — Resume-to-job matching

---

## Promo Tile (440×280)
Upload `promo_tile_440x280.png`

---

## Marquee (1400×560) — Optional
Upload `marquee_1400x560.png`

---

## Privacy Policy URL
**Required** — Add your hosted privacy policy URL here (GitHub Pages, your site, etc.)

---

## Support Email
Add your support email for user inquiries

---

## Developer Notes for Reviewers

- Extension uses a FastAPI backend (separate deployment) for AI analysis via OpenRouter
- Backend CORS is locked to this extension's ID: `hdmdhiojgdoomcjfhbkidbhkifmokkop`
- No user accounts, no tracking, no analytics
- All AI prompts enforce libel guardrails (no accusations, only observable findings)
- Resume data never leaves the request lifecycle; zero retention
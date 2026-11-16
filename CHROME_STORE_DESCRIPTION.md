# Chrome Web Store Listing — Traba-Hero

---

## Short Description (132 chars max)
**Scan job postings for scam signals, verify employers, and match your resume — all in one click.**

---

## Detailed Description

**Traba-Hero protects Filipino job seekers from employment scams.**

Every day, thousands of fake job postings circulate on Facebook, LinkedIn, JobStreet, and messaging apps — asking for upfront fees, personal IDs, or payments to "activate" accounts. Traba-Hero gives you a safety check before you apply.

### How It Works

1. **Pick a job post** — Open the side panel and select the posting you want checked.
2. **Scan** — Traba-Hero reads the posting you selected and looks for scam signals: upfront fees, payment forwarding, credential requests, task-for-earning schemes, and impersonation.
3. **Employer check** — If the post names a company, Traba-Hero searches the web for that company's official presence: whether it appears in official sources, and whether the contact channel in the post matches the employer's real domain.
4. **Plain-language result** — 🟢 **Nothing found against it** · 🟡 **Caution** · 🔴 **Contradicted**
5. **Resume match** — Upload a resume (PDF, DOCX, TXT, or image) and compare it against postings you have scanned.

### Key Features

- **Scam signal detection** — upfront fees, payment forwarding, credential harvesting, task-for-earning schemes, impersonation
- **Employer check with sources** — links to what the search actually returned, so you can read it yourself
- **Channel match** — flags free email addresses (Gmail, Yahoo), lookalike domains, and government claims made through unofficial channels
- **Privacy-first** — your resume and screenshots are processed in memory; nothing is stored on our servers
- **Philippines-focused** — rules based on DOLE Department Order 141-14, RA 10173 (Data Privacy Act), and DMW Advisory 56
- **Works on any site** — Facebook, LinkedIn, JobStreet, Indeed, OLX, Telegram, Viber, WhatsApp web, and more

### What It Does Not Do

It does not contact employers, apply on your behalf, or guarantee that a posting is safe. It shows the evidence it found and lets you decide.

### Permissions Explained

- **Storage** — saves your settings and scan history in your browser
- **Side Panel** — shows results next to the posting without navigating away
- **Active Tab** — grants access only when you start a scan from the toolbar
- **Host Permissions** — lets you select a region on any page and send that capture to the analysis backend

### Privacy Policy

https://traba-hero.online/#privacy

### Support

support@traba-hero.online | GitHub: https://github.com/miks518/traba-hero

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
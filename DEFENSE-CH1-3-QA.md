# Trabahero — Defense Q&A Guide (Actual System)

## What Trabahero ACTUALLY Is

A **Chrome browser extension** + **FastAPI backend** + **local LLM (Gemma 4)** that:
1. Captures screenshots of job postings (text or image-based)
2. Sends screenshots to a local LLM for visual analysis + classification
3. Classifies postings as **scam / suspicious / legitimate** with explanation
4. Analyzes resumes and matches them against scanned jobs
5. Provides company verification (web search, SEC registry) for text-based scans
6. Runs entirely locally — no data sent to external APIs

---

## What the Paper Describes vs What's Implemented

| Paper Describes | Actually Implemented |
|---|---|
| Fine-tuned XLM-RoBERTa classifier | Gemma 4 via LM Studio (general-purpose LLM) |
| Tesseract.js OCR | No OCR library — LLM reads the screenshot directly |
| SHAP token-level explanations | LLM-generated natural language explanations |
| ISMOTE for class imbalance | Not implemented (no training pipeline) |
| POS tagging + dependency parsing for resume clarity | LLM-based resume extraction (skills, experience, titles) |
| Multi-layered pipeline (OCR → NLP → SHAP → conditional LLM) | Single LLM pass handles everything |
| Company info returned to frontend | Company data used as context for LLM only, not returned |
| Taglish language support | English/Tagalog only (via prompt instruction) |

---

## Defense Questions & Answers (Honest)

### Q1: "What problem does this solve?"

**Answer:** Filipino job seekers face online recruitment fraud — 20% of SEEK's fraud cases target Filipinos (2025). Many scam postings on Facebook appear as **image-based graphics/flyers** where the DOM only has metadata like "Photo" — no extractable text. NLP-only tools can't read these. Trabahero captures a screenshot and sends it to an LLM that can **visually read the image**, classify it, and explain why it's a scam.

---

### Q2: "Why a browser extension?"

**Answer:**
1. **Proximity** — users see scam posts while browsing; the extension analyzes right there
2. **Screenshot access** — Chrome's `tabs.captureVisibleTab` API lets us capture any visible page, including image-based Facebook posts
3. **Privacy** — data stays local; no external API calls

---

### Q3: "How does the detection work technically?"

**Answer:** The system has three components:

1. **Chrome Extension (Frontend)** — React/TypeScript in a sidepanel. User clicks the toolbar icon, the sidepanel opens. User can:
   - Pick an element on the page (element picker)
   - Manually crop a region
   - Paste text directly

2. **FastAPI Backend** — Receives screenshots (base64) or text. For text scans, it also runs DuckDuckGo web searches and SEC registry lookups to gather context. Sends everything to the LLM.

3. **LM Studio (Local LLM)** — Gemma 4 model running locally at `localhost:1234`. The system prompt instructs it to classify the job posting and return structured JSON with: validity, scam score (0-100), red flags with severity, analysis, and job summary.

---

### Q4: "Why use Gemma 4 instead of a trained classifier?"

**Answer:** Gemma 4 is a general-purpose LLM that can:
- **Visually read screenshots** (multimodal) — no separate OCR needed
- **Classify text** as scam/legitimate/suspicious
- **Explain reasoning** in natural language
- **Extract structured data** (company name, salary, requirements)
- **Work in Tagalog** via prompt instructions

This eliminates the need for a separate OCR library, a trained classifier, and an explainability layer. One model handles the entire pipeline.

---

### Q5: "How does the system handle image-based posts?"

**Answer:** When a user captures a screenshot of a Facebook job post (which may be an image/flyer with embedded text):
1. The extension captures the visible tab area using `chrome.tabs.captureVisibleTab`
2. The user can crop to the relevant region
3. The screenshot (base64 data URL) is sent to the backend
4. The backend sends it to Gemma 4 as a multimodal input
5. Gemma 4 **visually reads the image** — it performs OCR internally as part of its analysis
6. Returns classification + explanation

No separate OCR library (like Tesseract.js) is needed because Gemma 4 handles image understanding natively.

---

### Q6: "What about the multilingual aspect?"

**Answer:** The system supports **English and Tagalog**. When the user selects Tagalog in the UI, the backend appends a language instruction to the prompt telling the LLM to respond in Tagalog. The LLM's multilingual capability depends on which model is loaded in LM Studio. Gemma 4 has training data that includes Tagalog content.

*Taglish (code-switched) is not explicitly supported as a separate option, but the LLM can handle mixed-language input naturally.*

---

### Q7: "How does resume matching work?"

**Answer:** Two-step process:
1. **Resume Analysis** — User uploads a resume (PDF, TXT, DOCX, or image). The backend extracts text (using pypdf for PDFs, or sends images to the LLM). The LLM extracts: skills, years of experience, job titles, industries, and a summary.
2. **Job Matching** — The extracted resume data is compared against previously scanned job summaries. The LLM scores compatibility (0-100) and returns: matched skills, skill gaps, experience fit, industry fit, and recommended actions.

*Note: The paper describes POS tagging and dependency parsing for resume clarity feedback. The current implementation uses the LLM instead, which provides richer analysis but without the formal NLP pipeline.*

---

### Q8: "How does the company verification work?"

**Answer:** For **text-based scans only** (not screenshots):
1. The backend extracts a company name from the job text using regex
2. Runs **DuckDuckGo web searches** for: legitimacy, SEC registration, scam reports, LinkedIn presence
3. Queries the **Philippine SEC registry API** (`sec.gov.ph`) to check if the company is registered
4. These search results are prepended to the LLM prompt as context

The search results help the LLM make more informed decisions, but are **not returned directly to the frontend** — only the final classification is shown.

*SEC API requires a $10 API key. If not configured, the system skips it gracefully.*

---

### Q9: "How are risk levels determined?"

**Answer:** The backend returns a `verdict_percentage` (0-100 scam score). The frontend applies thresholds:
- **Score ≥ 70** → "High Risk" (scam)
- **Score 40-69** → "Medium Risk" (suspicious)
- **Score < 40** → "Low Risk" (legitimate)

The high-risk threshold also **locks** the resume upload feature — if a scanned job is classified as scam, the user can't upload a resume for it (to avoid applying to scams).

---

### Q10: "What about privacy?"

**Answer:**
- Screenshots and text are sent **only to localhost:8000** (local backend)
- No data is sent to external APIs or cloud services
- LM Studio runs locally — the LLM never leaves the user's machine
- No data is stored or persisted
- Compliant with RA 10173 (Data Privacy Act of 2012)

---

### Q11: "What are the limitations?"

**Answer:**
1. **Local setup required** — Backend server + LM Studio must be running locally
2. **No cloud deployment** — The system runs entirely on the user's machine
3. **No custom-trained model** — Uses Gemma 4 (general-purpose), not a model trained specifically on Philippine job scam data
4. **LLM-dependent accuracy** — Classification quality depends on the loaded model's capabilities
5. **Image scans skip web search** — Company verification only works for text-based scans
6. **Taglish not explicitly supported** — Only English/Tagalog language options

---

### Q12: "Why not use a commercial API like OpenAI or Google Vision?"

**Answer:** Three reasons:
1. **Cost** — No API fees; the model runs locally
2. **Privacy** — No data leaves the user's machine
3. **Offline capability** — Works without internet (after initial model download)

---

### Q13: "Can this work on mobile?"

**Answer:** Not currently. The Chrome extension API (`tabs.captureVisibleTab`) is desktop-only. Mobile would require a native app or a different architecture.

---

### Q14: "How accurate is the system?"

**Answer:** The system correctly identifies obvious scam patterns (upfront fees, urgency tactics, unrealistic salaries, "no experience needed" + high pay) and legitimate postings. Edge cases with ambiguous language are flagged as suspicious for human review. Accuracy depends on the loaded model — Gemma 4 e4b (6.33GB) runs at ~5.5 tokens/second on local hardware.

---

## Key Metrics to Memorize

| Metric | Value |
|---|---|
| Unemployed Filipinos | 1.96 million |
| Cybercrime complaints (2024) | 10,004 |
| AI adoption surge in PH recruiting | 26% → 53% (2024-2025) |
| SEEK fraud targeting Filipinos | 20% of all fraud schemes |
| Model used | Gemma 4 e4b (6.33GB) |
| Processing speed | ~5.5 tok/s |
| Risk thresholds | High ≥70, Medium 40-69, Low <40 |

---

## Suggested Defense Flow (15 min)

1. **Problem** (2 min) — ORF stats, image-based scam gap, ATS disadvantage
2. **Architecture** (3 min) — Extension + Backend + Local LLM diagram
3. **Demo** (5 min) — Live: screenshot a scam post, show classification + red flags
4. **Resume matching** (2 min) — Upload resume, match against scanned jobs
5. **Results & limitations** (2 min) — What works, what's future work
6. **Conclusion** (1 min) — Contribution: browser-based tool for image-based scam detection

# Anomaly Evidence Assessment and Verification Integration

**Date:** 2026-10-19  
**Status:** Design Approved  
**Supersedes:** None. Extends `2026-10-18-verification-comparison-design.md` and `2026-10-17-report-panel-architecture.md`.

---

## 1. Intent and Problem Statement

When Trabahero performs an initial scan of a job post, anomalies (such as "Mandatory Fee", "Contact via Telegram", or "Requests ID Documents") are detected from the posting's text alone.

Under the current architecture:
1. **Premature / Uncontextualized Findings:** Anomalies are rendered immediately upon scan completion as red or yellow warnings. But in legitimate contexts, certain anomalies have valid justifications (e.g. an upfront fee may be a standard, legitimate medical examination fee charged by an accredited clinic, or an application address might match the company's verified domain). Conversely, an anomalous fee may be completely unstated or contradicted by official employer policies (e.g. "We never collect recruitment fees").
2. **Disconnected Verification:** `/api/verify` receives `VerifyRequest.anomalies`, but does not assess each anomaly against retrieved web search evidence.
3. **Missing Feedback on Evidence Support:** The user is left wondering whether an anomaly was actually verified, refuted, or left unconfirmed because no company could be searched.

### The Desired Behavior

- **Initial Scan & Display:** Anomalies detected during scan remain attached to the scan result, but their presentation reflects their assessment against verification evidence.
- **Evidence-Based Verdicts per Anomaly:**
  1. **Confirmed by Context / Evidence (Green Strip):** Evidence accounts for the posting's claim (e.g., fee is confirmed as an official medical exam or authorized clinic fee, supported by a retrieved source URL and title).
  2. **Contradicted by Evidence (Red Strip):** Evidence contradicts the posting or confirms illegitimate collection (e.g., employer policy states "Does not collect any recruitment/placement fees", or the posting's claims are refuted by official advisories).
  3. **Unconfirmed / No Employer to Search (Amber / Yellow Strip):** If no company or employer is named, or if search retrieval fails/yields no assessment, the anomaly card displays a clear yellow notice:
     > *"This was not confirmed as there's no company or employer to search for but shown to help users notice the anomaly."*
- **Decoupled Visual Hierarchy:**
  - **Severity Chips (`Critical` [red], `Serious` [amber], `Minor` [green]):** Remain strictly tied to the anomaly's intrinsic severity (`high`, `mid`, `low`).
  - **Evidence Strip:** Reflects the verification outcome (`confirmed`, `contradicted`, `unconfirmed`).

---

## 2. Architecture & Data Flow

```
[Job Posting Image / Text]
           │
           ▼
     /api/scan-text or /api/scan
           │
           ├─ Emits ScanResult:
           │    - anomalies: list[Anomaly] (title, description, severity, code, quote)
           │    - company_name
           │    - attributes & search_queries
           │
           ▼
[Sidepanel Extension Client]
           │
           │ Sends VerifyRequest(company_name, job_summary, anomalies, attributes, search_queries)
           ▼
     /api/verify (SSE Stream)
           │
           ├─ 1. Web Search (Tavily): Company reputation + anomaly/scheme queries
           ├─ 2. LLM Verification Call:
           │       - Verifies employer existence & claims
           │       - Evaluates EACH anomaly in req.anomalies against search evidence
           │       - Produces per-anomaly assessment:
           │           * status: 'confirmed' | 'contradicted' | 'unconfirmed'
           │           * explanation: concise finding
           │           * source_title & source_url (bound to retrieved URLs)
           │
           ▼
     SSE "result" Event with updated anomalies:
       anomalies: [
         {
           id, title, description, severity, code, quote,
           assessment: {
             status: 'confirmed' | 'contradicted' | 'unconfirmed',
             explanation: string,
             source_title?: string,
             source_url?: string
           }
         }
       ]
           │
           ▼
[Sidepanel AnomalyCards]
   Renders cards with:
     - Header: Severity Chip (Critical / Serious / Minor) + Code Pill
     - Body: Title + Description
     - Quote Well: "From the post" (verbatim quote)
     - Evidence Strip:
         * Green: Confirmed with evidence + clickable source
         * Red: Contradicted by evidence + clickable source
         * Amber: Unconfirmed notice (no employer / unverified)
```

---

## 3. Wire Format & Schema Changes

### 3.1 Backend: `backend/app/models/schemas.py`

#### Update `VerifyAnomaly` (Input to `/api/verify`)
Expand `VerifyAnomaly` so the model receives the posting's verbatim quotes and codes:
```python
class VerifyAnomaly(BaseModel):
    flag: str = Field(..., max_length=MAX_VERIFY_ANOMALY_TEXT)
    reasoning: str = Field(default="", max_length=MAX_VERIFY_ANOMALY_TEXT)
    severity: str = Field(default="", max_length=50)
    query_ref: str = Field(default="", max_length=MAX_VERIFY_QUERY_CHARS)
    code: str = Field(default="", max_length=50)
    quote: str = Field(default="", max_length=MAX_VERIFY_ANOMALY_TEXT)
```

#### New `AnomalyAssessment` Schema
```python
class AnomalyAssessment(BaseModel):
    status: Literal["confirmed", "contradicted", "unconfirmed"]
    explanation: str = Field(default="", max_length=500)
    source_title: str | None = None
    source_url: str | None = None
```

#### Update `Anomaly` (Emitted by backend & stored in history)
```python
class Anomaly(BaseModel):
    id: str = ""
    flag: str
    reasoning: str
    severity: str
    query_ref: str = ""
    code: str = ""
    quote: str = ""
    assessment: AnomalyAssessment | None = None
```

#### Update `/api/verify` SSE Result Payload
In `verification_flow.py`, the `"result"` event includes `anomalies`:
```python
{
    "type": "result",
    "data": {
        "items": [...],
        "evidence": [...],
        "anomalies": [anomaly.model_dump() for anomaly in assessed_anomalies],
        "report": report,
        "recommendation": recommendation,
        "riskScore": risk_score,
        "riskLevel": risk_level,
        "verdictReason": verdict_reason,
        ...
    }
}
```

### 3.2 Frontend Types: `entrypoints/sidepanel/types/index.ts`

```typescript
export type AnomalyEvidenceStatus = 'confirmed' | 'contradicted' | 'unconfirmed';

export interface AnomalyAssessment {
  status: AnomalyEvidenceStatus;
  explanation: string;
  source_title?: string;
  source_url?: string;
}

export interface Anomaly {
  id: string;
  title: string;
  description: string;
  icon: IconName;
  severity?: 'low' | 'mid' | 'high';
  code?: string;
  quote?: string;
  assessment?: AnomalyAssessment;
}

export interface VerificationResult {
  items: VerificationItem[];
  evidence?: VerificationEvidence[];
  anomalies?: Anomaly[];
  report: string;
  recommendation: string;
  verdictReason?: string;
  riskScore?: number;
  riskLevel?: ScanRiskLevel;
  noCompanyName?: boolean;
  searchOk?: boolean;
  ...
}
```

---

## 4. Verification Prompt & Model Evaluation

### 4.1 System Prompt & Structured Output (`VERIFY_PROMPT.md`)

The verification model is instructed to evaluate each anomaly in `ANOMALIES TO ASSESS`:

```markdown
## Anomaly Evidence Assessment Rules

For each anomaly provided in the input, evaluate whether the search results support, explain, or contradict the finding:

1. **confirmed (Green)**: The search results account for or legitimate the claim in context (e.g. the employer explicitly lists the medical fee as a required clinic fee, or official channels confirm the process).
2. **contradicted (Red)**: The search results directly contradict the claim (e.g. the employer explicitly states "We do not charge any recruitment or placement fees", or the poster's payment demand is fraudulent).
3. **unconfirmed (Yellow/Amber)**: The search results do not contain sufficient evidence to evaluate the anomaly, or no official information exists.

Every `source_url` MUST strictly match a URL from the retrieved search results. Do not fabricate URLs.
```

### 4.2 Handling No-Company-Name Path

When `no_company_name` is true (or company validation fails):
- `/api/verify` short-circuits early.
- It maps all incoming `req.anomalies` to `Anomaly` objects with:
  ```python
  assessment = AnomalyAssessment(
      status="unconfirmed",
      explanation="This was not confirmed as there's no company or employer to search for but shown to help users notice the anomaly."
  )
  ```

---

## 5. UI Presentation in `AnomalyCards.tsx`

### 5.1 Card Structure
Each card in `AnomalyCards` displays:
1. **Header Row:**
   - Severity Chip (e.g., `Critical` in red, `Serious` in amber, `Minor` in green).
   - Rule Code Pill (e.g., `FEE_MANDATORY`).
2. **Body:**
   - Heading (`anomaly.title`)
   - Description (`anomaly.description`)
3. **Quotation Well:**
   - *"From the post"* quote (when present).
4. **Evidence Strip (Bottom Banner):**
   - **Confirmed (`status === 'confirmed'`):**
     - Background: `bg-green-500/10 border-green-500/30 text-green-700 dark:text-green-300`
     - Icon: `check_circle`
     - Text: Explanation + clickable link `[source_title](source_url)`
   - **Contradicted (`status === 'contradicted'`):**
     - Background: `bg-red-500/10 border-red-500/30 text-red-700 dark:text-red-300`
     - Icon: `warning` / `gpp_bad`
     - Text: Explanation + clickable link `[source_title](source_url)`
   - **Unconfirmed (`status === 'unconfirmed'`):**
     - Background: `bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-300`
     - Icon: `info` / `gpp_maybe`
     - Text: *"This was not confirmed as there's no company or employer to search for but shown to help users notice the anomaly."* (or model-provided unconfirmed explanation).

### 5.2 Verification In-Flight State
While verification is loading (`verificationLoading === true`), anomaly cards can show an amber / neutral pending indicator:
- *"Verifying against employer evidence..."* with a subtle shimmer/spinner.

---

## 6. Testing & Offline Verification Plan

In accordance with `AGENTS.md` test safety rules:
1. **Zero live provider calls during testing.** All tests must use mocked responses.
2. **Backend Unit Tests (`backend/tests/test_verify.py`):**
   - Test no-company path sets `status="unconfirmed"` with the exact disclaimer text.
   - Test structured response parsing binds `source_url` only to retrieved URLs and discards hallucinated URLs.
   - Test serialization/deserialization of `AnomalyAssessment`.
3. **Frontend Component Tests (`AnomalyCards.test.tsx`):**
   - Render card with `assessment: confirmed` -> verifies green strip and source link.
   - Render card with `assessment: contradicted` -> verifies red strip and source link.
   - Render card with `assessment: unconfirmed` -> verifies yellow disclaimer text.
   - Render card without assessment (initial scan state) -> verifies clean card without broken strips.

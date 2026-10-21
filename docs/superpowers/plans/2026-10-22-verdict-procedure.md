# The Verdict Procedure and the Agent Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the weighted risk score with an auditable two-axis decision procedure, and replace the scan→verify relay with one agent that holds the posting for the whole proceeding.

**Architecture:** Four parts on one branch, each independently shippable. **Part 1** fixes the classification layer — the anomaly taxonomy, the request facts, the classifier, the free-email combination rule, and the citation binding that currently discards the Fake CHED impersonation. **Part 2** replaces the score with the verdict grid and rewrites the wire and the panel. **Part 3** replaces the two-stage pipeline with one agent session holding a `search` and a `fetch` tool. **Part 4** decides establishment — `confirmed` / `supported` / `unknown` / `contradicted` — from the employer's own record.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, pytest, Tavily search, OpenRouter (chat + vision). TypeScript 5, React 19, WXT, Vitest, Tailwind.

**Spec:** `docs/superpowers/specs/2026-10-21-verdict-procedure-agent-loop-design.md`
**Research:** `docs/research/2026-10-21-verdict-grid-research.md` (the rules behind the grid), `docs/research/2026-10-21-corpus-baseline.md` (the measured "before" column and the two defects Part 1 fixes)

---

## Global Constraints

These hold for every task in this plan. A task's requirements implicitly include this section.

- **The default suite must be fully offline.** Never make live OpenRouter or Tavily calls from a test. `backend/tests/conftest.py` installs an autouse `_offline_ai_and_search` fixture and a session-scoped `_block_external_dns` guard. A new external entry point (the `fetch` tool) must be faked at the module boundary and covered by the DNS guard.
- **Use `class_settings(monkeypatch)` from `backend/tests/conftest.py`** for any test asserting a shipped default. A test that constructs `Settings()` directly reads the real `backend/.env` and prints the live `AI_API_KEY` on failure.
- **Never commit a secret.** `backend/.env` and the root `.env` are ignored; `.env.example` carries placeholders only.
- **Nothing in `verdictCopy.ts` or the new `verdict_copy.py` may be written by a model.** Every word the panel says is authored in code and looked up.
- **A red test in this repo is a finding, not a condition.** If a test you wrote fails for a reason the spec does not explain, stop and record the finding before fixing it.
- **Never let the product assert what it cannot support.** Every statement traces to the input; unknowns are declared, never inferred. The absence of a result is never red.
- **One logical change per commit.** The message says what changed and why; the body carries the reason. Scratch files (`debug*.py`, `probe*.py`, `.bak`, output dumps) are deleted, not committed.
- **Run before every commit:** `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q` and `npm test -- --run` from the repo root, plus `npm run compile` for the extension. If the suite has failures, they are pre-existing or new — say which, in the commit message.
- **Committing is authorised. Pushing is not.**
- **The corpus in `jobposts/` is the reviewer's local machine and is never committed.** Read it; do not add it to `.gitignore` either.
- **WXT globals** (`defineBackground`, `defineContentScript`) are auto-imported — do not import them. **Chrome APIs** use `// @ts-ignore` for `chrome.sidePanel` and `chrome.storage`.
- **Tailwind colours are CSS variables** (`var(--color-*)`) in `assets/tailwind.css`. Use semantic tokens, not raw hex. **Fonts:** `font-headline` (Hanken Grotesk), `font-body`/`font-label` (Inter). **Hard shadows:** `tactile-card` for containers, `tactile-btn-accent` for buttons; they are not interchangeable.
- **Logging:** every AI stream function uses an `[endpoint]` prefix (`[scan-text]`, `[analyze-resume]`, `[match-resume]`). The new agent endpoint uses `[assess]`.

---

## Review Focus

Five input classes the spec implies that a task's tests must pin. Each is added to the task that owns the code, in that task's own step style.

1. **A legitimate posting that asks for the ordinary applicant packet** (résumé, 2×2, transcript, SSS, PhilHealth, Pag-IBIG, NBI, medical) through a free email. Expected: no charge, and the verdict is never `caution` or `stop`. The corpus measured this as the product's worst false positive — `docs/research/2026-10-21-corpus-baseline.md` §4. Pinned by Task 3 and Task 4.
2. **A government office whose posting gives a non-`.gov.ph` contact, where the official page was never retrieved.** Expected: the impersonation is red and strong, because the posting made the claim and supplied the domain. Pinned by Task 6 — the case the existing fixture cannot reach.
3. **A fee whose recipient and timing the posting does not state.** Expected: the class is `unclassified`, not `prohibited` and not `ordinary`, so the verdict is a question and never a charge. Pinned by Task 3.
4. **A posting that names no employer.** Expected: no verdict (grey), the employer prompt, and no charge from the posting's own text. Pinned by Task 7 and Task 12.
5. **A model answer that cites a URL the search never returned.** Expected: the citation is dropped and the claim it carried is demoted — except for the government branch, which needs no retrieved source. Pinned by Task 6.

---

# Part 1 — The classification layer

*Nothing in the verdict changes in this part. The inputs do. Every task here is worth having on its own: Part 1 alone drops the measured false-positive rate and restores the Fake CHED impersonation.*

### Task 1: Split the document codes

**Files:**
- Modify: `backend/app/services/anomaly_codes.py` (`ANOMALY_CODES`, the family comments)
- Modify: `backend/app/services/scanner/prompts.py` (`SCAN_FIELD_RULES`, the ANOMALY CODES list)
- Modify: `backend/SYSTEM_PROMPT.md` (the ANOMALY CODES list — the two copies must not drift)
- Modify: `backend/app/models/schemas.py` (`Anomaly`)
- Test: `backend/tests/test_anomaly_codes.py`, `backend/tests/test_verify_prompt_file.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ANOMALY_CODES` gains `APPLICATION_DOCUMENTS` and `ACCOUNT_CREDENTIALS`, loses `CREDENTIALS_BEFORE_INTERVIEW`. `Anomaly.fee_reason: str = ""`.

- [ ] **Step 1: Write the failing test** in `backend/tests/test_anomaly_codes.py`:

```python
def test_the_document_codes_are_split():
    """The ordinary applicant packet is not the same finding as account credentials."""
    assert "APPLICATION_DOCUMENTS" in ANOMALY_CODES
    assert "ACCOUNT_CREDENTIALS" in ANOMALY_CODES
    assert "CREDENTIALS_BEFORE_INTERVIEW" not in ANOMALY_CODES
```

and, in `backend/tests/test_verify_prompt_file.py`, a test asserting both prompts state `APPLICATION_DOCUMENTS` and `ACCOUNT_CREDENTIALS` and no longer state `CREDENTIALS_BEFORE_INTERVIEW`. Follow the house style of the existing "every code is stated in the prompt" test in that file.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_anomaly_codes.py tests/test_verify_prompt_file.py -q`
Expected: FAIL — `AssertionError: assert 'APPLICATION_DOCUMENTS' in ANOMALY_CODES`.

- [ ] **Step 3: Implement the taxonomy change**

In `backend/app/services/anomaly_codes.py`, replace `"CREDENTIALS_BEFORE_INTERVIEW"` with `"APPLICATION_DOCUMENTS"` and `"ACCOUNT_CREDENTIALS"` in the tuple, and rewrite the family comments: Family I is now *the reader loses documents or accounts*, with `APPLICATION_DOCUMENTS` marked **not an exposure** (the ordinary applicant packet — résumé, 2×2 photo, transcript, certificates, NBI clearance, medical results — is ordinary Philippine hiring practice) and `ACCOUNT_CREDENTIALS` marked **the exposure** (bank account, e-wallet number, one-time password, password, or account access requested before hiring).

In `backend/app/services/scanner/prompts.py` (`SCAN_FIELD_RULES`) and `backend/SYSTEM_PROMPT.md`, write the two entries in the same wording, and add the rule that a free-provider address is **not** a third party for `DOCUMENTS_VIA_THIRD_PARTY`. The two prompt copies must state the same set of codes; `test_verify_prompt_file.py` already asserts the codes are present in both.

- [ ] **Step 4: Add the `fee_reason` field** to `Anomaly` in `backend/app/models/schemas.py`:

```python
    # The reason the posting gives for a fee, verbatim. A fact, never a
    # judgement: "medical clearance" is what the posting says.
    fee_reason: str = ""
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_anomaly_codes.py tests/test_verify_prompt_file.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/anomaly_codes.py backend/app/services/scanner/prompts.py backend/SYSTEM_PROMPT.md backend/app/models/schemas.py backend/tests/test_anomaly_codes.py backend/tests/test_verify_prompt_file.py
git commit -m "feat: split the document codes into an ordinary packet and account credentials

CREDENTIALS_BEFORE_INTERVIEW covered two things that are not alike in the
Philippines. Asking for the applicant packet - resume, 2x2, transcript, NBI
clearance, medical results - is ordinary hiring practice and is what PESO
checklists and the employers' own pre-employment packets ask for. Asking for
a bank account, an e-wallet number, an OTP or a password before hiring has no
lawful reading: no employer needs them to consider an application, and it is
the mechanism by which an applicant becomes a mule account.

The corpus measured the cost of the conflation: of the ten legitimate
postings, the two that asked for the most documents are the two the panel
called 'Proceed with caution'. RA 10173 s11(d) draws the line - personal
information must not be excessive in relation to the purpose."
```

### Task 2: Extract the request facts

**Files:**
- Modify: `backend/app/services/scanner/prompts.py` (`SCAN_FORMAT_BLOCK`, `SCAN_FIELD_RULES`)
- Modify: `backend/SYSTEM_PROMPT.md`
- Modify: `backend/app/services/lm_client.py` (`_SECTION_RE`, `_parse_custom`)
- Modify: `backend/app/models/schemas.py` (`Anomaly.fee_reason` exists from Task 1; `AttributeKey`/`AttributeValue`)
- Test: `backend/tests/test_anomaly_codes.py`

**Interfaces:**
- Consumes: Task 1's `Anomaly.fee_reason`.
- Produces: three new attribute keys — `FEE_RECIPIENT`, `FEE_TIMING`, `MEETING_PLACE_KIND` — and one new anomaly-section line, `FEE_REASON`. `Anomaly.fee_recipient: str = ""`, `Anomaly.fee_timing: str = ""`, and `Anomaly.meeting_place_kind: str = ""` are carried on the wire.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_anomaly_codes.py`, following the house style of `test_a_code_line_attaches_to_the_anomaly_above_it`:

```python
def test_a_fee_reason_line_attaches_to_the_anomaly_above_it():
    raw = ("ANOMALY: Asks applicants to pay a processing fee | The posting asks for a fee | high\n"
           "CODE: FEE_MANDATORY\n"
           "FEE_REASON: medical clearance\n"
           "END ANOMALIES\n")
    result = _parse_custom(raw)
    assert result["anomalies"][0]["fee_reason"] == "medical clearance"


def test_the_fee_facts_parse_as_attributes():
    raw = ("ATTRIBUTES:\n"
           "FEE_RECIPIENT: agency\n"
           "FEE_TIMING: before hiring\n"
           "MEETING_PLACE_KIND: elsewhere\n"
           "END ATTRIBUTES\n")
    result = _parse_custom(raw)
    assert result["attributes"]["FEE_RECIPIENT"] == "agency"
    assert result["attributes"]["FEE_TIMING"] == "before hiring"
    assert result["attributes"]["MEETING_PLACE_KIND"] == "elsewhere"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_anomaly_codes.py -q`
Expected: FAIL — the keys are not in `_SECTION_RE`.

- [ ] **Step 3: Implement the extraction**

Add to `SCAN_FORMAT_BLOCK` in `backend/app/services/scanner/prompts.py` (and the same lines in `backend/SYSTEM_PROMPT.md`):

```
FEE_REASON: <the reason the posting gives for the fee, or omit>
```
inside the ANOMALY section, after `QUOTE:`, and

```
FEE_RECIPIENT: <employer | agency | third party | individual account | omit>
FEE_TIMING: <before hiring | at hiring | after a contract | omit>
MEETING_PLACE_KIND: <employer premises | elsewhere | omit>
```
inside the ATTRIBUTES section.

In `backend/app/services/lm_client.py`, add the three attribute keywords to `_SECTION_RE` and to the attribute-key set beside it, and handle `FEE_REASON` in `_parse_custom` **inside the anomaly section only**, exactly as `CODE` and `QUOTE` are handled — they are ordinary English words, so an ungated line would swallow unrelated text. See `docs/decisions/parser-resilience.md` for the gating rule.

In `backend/app/models/schemas.py`, add `fee_recipient`, `fee_timing` and `meeting_place_kind` to `Anomaly` with `""` defaults, and add the three keys to `AttributeKey`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_anomaly_codes.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner/prompts.py backend/SYSTEM_PROMPT.md backend/app/services/lm_client.py backend/app/models/schemas.py backend/tests/test_anomaly_codes.py
git commit -m "feat: extract the fee's recipient and timing, and the meeting place's nature

The rules the research found attach to the shape of a request, and the shape
was not in the scan. DOLE DO 141-14 s35 forbids a recruitment agency from
charging a job seeker a placement fee for local work; DMW s56 allows exactly
one fee overseas, payable only after a signed contract. A fee to the employer
for a uniform is ordinary. Telling those apart needs who the fee is paid to
and when - both facts on the face of the posting, neither of them a judgement.

MEETING_PLACE_KIND exists for the same reason: DMW-CAR treats a transaction
in a mall or a private home instead of the registered office as a sign of
illegal activity, and that is a fact about the place, not about the poster."
```

### Task 3: Write the classifier

**Files:**
- Create: `backend/app/services/scanner/request_class.py`
- Modify: `backend/app/services/scanner/__init__.py` (export it)
- Modify: `backend/tests/test_scanner_package.py` (the package's symbol list is pinned there)
- Test: `backend/tests/test_request_class.py` (new)

**Interfaces:**
- Consumes: Task 1's codes and Task 2's facts.
- Produces:

```python
REQUEST_CLASSES = ("ordinary", "unclassified", "prohibited")

@dataclass(frozen=True)
class RequestFact:
    code: str
    quote: str = ""
    fee_recipient: str = ""
    fee_timing: str = ""

def classify_request(facts: Sequence[RequestFact], *, claimed_type: str = "") -> str
```

`claimed_type` is the scan's `CLAIMED_TYPE` attribute: `"recruitment agency"`, `"private company"`, `"government"`, `"individual"`, `"unclear"`, or `""`.

- [ ] **Step 1: Write the failing test file** `backend/tests/test_request_class.py` with one test per rule, each named for the rule it pins:

```python
def test_a_free_email_with_an_ordinary_packet_is_ordinary():
    facts = [RequestFact(code="APPLICATION_DOCUMENTS", quote="2x2 picture, NBI clearance")]
    assert classify_request(facts) == "ordinary"


def test_account_credentials_before_hiring_are_prohibited():
    facts = [RequestFact(code="ACCOUNT_CREDENTIALS")]
    assert classify_request(facts) == "prohibited"


def test_a_fee_to_an_agency_before_hiring_is_prohibited():
    facts = [RequestFact(code="FEE_MANDATORY", fee_recipient="agency", fee_timing="before hiring")]
    assert classify_request(facts, claimed_type="recruitment agency") == "prohibited"


def test_a_fee_to_the_employer_for_a_uniform_is_ordinary():
    facts = [RequestFact(code="FEE_MANDATORY", fee_recipient="employer", fee_timing="before hiring",
                         quote="uniform")]
    assert classify_request(facts) == "ordinary"


def test_a_fee_to_an_individual_account_is_prohibited():
    facts = [RequestFact(code="FEE_MANDATORY", fee_recipient="individual account")]
    assert classify_request(facts) == "prohibited"


def test_a_fee_with_no_stated_recipient_cannot_be_classified():
    facts = [RequestFact(code="FEE_MANDATORY")]
    assert classify_request(facts) == "unclassified"


def test_a_fee_to_an_agency_after_a_signed_contract_is_ordinary():
    facts = [RequestFact(code="FEE_MANDATORY", fee_recipient="agency", fee_timing="after a contract")]
    assert classify_request(facts, claimed_type="recruitment agency") == "ordinary"


def test_documents_via_a_free_provider_are_ordinary():
    facts = [RequestFact(code="DOCUMENTS_VIA_THIRD_PARTY", quote="recruitment4@gmail.com")]
    assert classify_request(facts) == "ordinary"


def test_documents_via_a_named_domain_are_prohibited():
    facts = [RequestFact(code="DOCUMENTS_VIA_THIRD_PARTY", quote="send to forms.hiredocs.net")]
    assert classify_request(facts) == "prohibited"


def test_task_for_earning_is_prohibited():
    assert classify_request([RequestFact(code="TASK_FOR_EARNING")]) == "prohibited"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_request_class.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.scanner.request_class'`.

- [ ] **Step 3: Implement `request_class.py`**

The rules, each carrying the citation that justifies it in a comment:

- `ACCOUNT_CREDENTIALS`, `PAYMENT_FORWARDING`, `TASK_FOR_EARNING` → **prohibited**. (RA 10173 §11(d) — not excessive for the purpose; the first two are the money-mule and task-for-earning mechanics.)
- `FEE_MANDATORY`, `FEE_CONDITIONAL`, `PURCHASE_REQUIRED`, `DEPOSIT_REQUIRED` → decided by the fee's recipient and timing:
  - recipient `individual account` or `third party` → **prohibited** (POEA Advisory 62 names remittance centres, GCash, 7/11 and PayPal);
  - recipient `employer` → **ordinary** (a uniform or medical cost charged by the employer is ordinary practice, and DO 141-14 §35 governs agencies, not employers);
  - recipient `agency` → **prohibited** unless the timing is `after a contract` (DOLE DO 141-14 §35 for local work: no fee may be collected from the worker; DMW §56 and §59 for overseas: the prescribed placement fee, after a signed contract, and nothing else);
  - recipient not stated → **unclassified**.
- `DOCUMENTS_VIA_THIRD_PARTY` → **ordinary** when every domain named in the finding's quote is a free-provider domain (reuse `channel_match._is_free_email`); otherwise **prohibited**. The corpus measured the model using this code for "the posting uses a Gmail address", and a free-provider address is not a third party — it is the absence of a domain.
- `IMPERSONATES_AUTHORITY` → no class of its own. It is an establishment signal and Part 4 reads it.
- `OTHER` → **unclassified**. The escape valve is a real finding whose shape the taxonomy does not name, so it cannot be a charge, and it is not ordinary either.
- Anything else, including `APPLICATION_DOCUMENTS` → **ordinary**.

The function returns the **worst** class present, in the order `prohibited > unclassified > ordinary`. A posting with no findings at all is `ordinary`.

- [ ] **Step 4: Export it from the package** — add `request_class` to `backend/app/services/scanner/__init__.py`'s `__all__` and to `PACKAGE_EXPORTS` in `backend/tests/test_scanner_package.py`, which pins the list.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv\Scripts\python.exe -m pytest tests/test_request_class.py tests/test_scanner_package.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/scanner/request_class.py backend/app/services/scanner/__init__.py backend/tests/test_scanner_package.py backend/tests/test_request_class.py
git commit -m "feat: classify what a posting asks for as ordinary, unclassified or prohibited

The rules the research found attach to the shape of a request. A fee to the
employer for a uniform is ordinary. A fee to an agency before a contract is
prohibited by DOLE DO 141-14 s35. A fee to a personal account is prohibited by
POEA Advisory 62. Asking for the applicant packet is ordinary. Asking for
account credentials before hiring has no lawful reading under RA 10173
s11(d). A fee whose recipient the posting does not state cannot be classified
at all, and is a question rather than a charge.

The classifier is a pure function over facts on the face of the posting, so
the model never decides whether a request is a scam."
```

### Task 4: Put the class on the wire

**Files:**
- Modify: `backend/app/services/scanner/scan_result.py` (`_build_scan_response`)
- Modify: `backend/app/services/scanner/verification_flow.py` (the result event)
- Modify: `backend/app/models/schemas.py` (`ScanResponse`, `VerificationResult`)
- Modify: `entrypoints/sidepanel/types/index.ts` (`ScanResult`, `VerificationResult`)
- Modify: `entrypoints/sidepanel/lib/api.ts`, `entrypoints/sidepanel/lib/mapApiResponse.ts`
- Test: `backend/tests/test_request_class.py` (a wire assertion), `entrypoints/sidepanel/lib/api.test.ts` if it exists

**Interfaces:**
- Consumes: `classify_request` and `RequestFact` from Task 3.
- Produces: `ScanResponse.request_class: str = ""` and `VerificationResult.request_class: str = ""`, both carrying one of `REQUEST_CLASSES`. The frontend type `ScanResult.requestClass?: string`.

- [ ] **Step 1: Write the failing test** — a scan of a fake posting body with a fee and no stated recipient yields `request_class == "unclassified"` on the response, and the verify response carries the same field. Assert on the schema, not on the wire format, so the test is not a transcript of the parser.

- [ ] **Step 2: Run the test to verify it fails** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_request_class.py -q`. Expected: FAIL — no `request_class` attribute.

- [ ] **Step 3: Implement** — in `_build_scan_response`, build the `RequestFact` list from the anomalies (`code`, `quote`, `fee_recipient`, `fee_timing`) and the attributes (`CLAIMED_TYPE`), call `classify_request`, and set `request_class`. In `verification_flow.py`'s result event, add `"request_class": request_class` alongside `riskLevel`. Add the field to both schemas with `""` defaults and to the frontend types and both mapping functions (`api.ts` and `mapApiResponse.ts` read different shapes; both need it).

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q` and `npm test -- --run`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner/scan_result.py backend/app/services/scanner/verification_flow.py backend/app/models/schemas.py entrypoints/sidepanel/types/index.ts entrypoints/sidepanel/lib/api.ts entrypoints/sidepanel/lib/mapApiResponse.ts backend/tests/test_request_class.py
git commit -m "feat: carry the request class on the wire

The verdict needs it and the panel will show it. Nothing reads it yet: the
score still decides the level, and the score does not know what a request
class is. Part 2 does."
```

### Task 5: The free-email combination rule needs a prohibited request

**Files:**
- Modify: `backend/app/services/scanner/channel_match.py` (`apply_channel_rules`, `_first_independent_finding`)
- Modify: `backend/app/services/scanner/verification_flow.py` (the call site)
- Test: `backend/tests/test_channel_match.py`

**Interfaces:**
- Consumes: the request class, from Task 4.
- Produces: `apply_channel_rules(items, request_class: str, expected: set[str]) -> list[VerificationItem]` — the `anomalies` parameter is **replaced**, not added to.

- [ ] **Step 1: Write the failing test** in `backend/tests/test_channel_match.py`:

```python
def test_a_free_email_with_an_ordinary_request_stays_yellow():
    items = [VerificationItem(label="Channel Match", status="yellow", explanation="x",
                               escalation="free_email")]
    out = apply_channel_rules(items, "ordinary", {"Channel Match"})
    assert out[0].status == "yellow"
    assert out[0].escalation == "free_email"


def test_a_free_email_with_a_prohibited_request_becomes_red():
    items = [VerificationItem(label="Channel Match", status="yellow", explanation="x",
                               escalation="free_email")]
    out = apply_channel_rules(items, "prohibited", {"Channel Match"})
    assert out[0].status == "red"
    assert out[0].escalation == "free_email_with_findings"
```

- [ ] **Step 2: Run the test to verify it fails** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_channel_match.py -q`. Expected: FAIL — the free email is escalated regardless of what was asked.

- [ ] **Step 3: Implement** — replace the `anomalies` parameter with `request_class: str`. The combination now fires only when `request_class == "prohibited"`, and the explanation's trailing sentence names the request rather than the finding. `_first_independent_finding` is deleted with a tombstone test in the same file, in the house style of the existing tombstones: the test asserts the name is absent and says why.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_channel_match.py tests/test_channel_match_regressions.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner/channel_match.py backend/app/services/scanner/verification_flow.py backend/tests/test_channel_match.py
git commit -m "fix: a free email only combines with a prohibited request

Rule 4 made a free-provider address plus ANY independent finding a red card
worth 25 points. The scan prompt says a free email is not an anomaly, and the
corpus confirmed it: of ten legitimate postings, the two that asked for the
most documents were pushed to 'Proceed with caution' by exactly this rule
(25 + 12 = 37). A Gmail address is ordinary in Philippine hiring.

The combination now needs a request the rules prohibit, which is rare by
construction, so the red it produces means something."
```

### Task 6: Exempt the government branch from the citation binding

**Files:**
- Modify: `backend/app/services/scanner/verification_flow.py` (`_bind_to_retrieved`)
- Modify: `backend/app/services/scanner/channel_match.py` (a named constant for the escalations that need no source)
- Test: `backend/tests/test_channel_match_regressions.py` (a third fixture)

**Interfaces:**
- Consumes: nothing new.
- Produces: `channel_match.SOURCE_INDEPENDENT_ESCALATIONS = frozenset({"government"})` — the escalations that are a claim the *posting* makes about itself, and therefore need no retrieved source.

- [ ] **Step 1: Write the failing test** in `backend/tests/test_channel_match_regressions.py`, beside the existing Fake CHED fixture, using the facts the corpus recorded — printed channels `hrm06@ched.gov.ph`, `recruitment.chred@outlook.com`, `chred-region6.org`, `(033) 987-6543`, `info@chred-region6.org`; `government_claim: True`; and **no** retrieved `https://ched.gov.ph`:

```python
def test_the_government_red_survives_the_citation_binding():
    """The posting made the claim and supplied the domain. No retrieval is needed."""
    item = _read_channel_item(payload, frozenset({"https://www.facebook.com/chedregion6"}))
    bound, _ = _bind_to_retrieved([item], [], frozenset({"https://www.facebook.com/chedregion6"}))
    assert bound[0].status == "red"
    assert bound[0].escalation == "government"
```

and a second test asserting `code_verdict` on that item returns `critical` with `channel_escalation == "government"` and `verification_score` **not** `None`.

- [ ] **Step 2: Run the test to verify it fails** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_channel_match_regressions.py -q`. Expected: FAIL — `assert 'yellow' == 'red'`.

- [ ] **Step 3: Implement** — in `_bind_to_retrieved`, skip the red→yellow demotion when the item's `escalation` is in `SOURCE_INDEPENDENT_ESCALATIONS`. The rule's own comment in `channel_match.py` already says the government branch "needs no retrieved source to see: the posting made the claim and the posting supplied the domain". The binding's rule is right for a claim about an employer's identity and wrong for a claim the posting makes about itself.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner/verification_flow.py backend/app/services/scanner/channel_match.py backend/tests/test_channel_match_regressions.py
git commit -m "fix: stop the citation binding from discarding the government contradiction

The corpus found the flagship case failing in the product and passing in the
test. assess_channel_match returns red/government/strong for the Fake CHED
facts, and _bind_to_retrieved then demoted it to yellow because the cited
ched.gov.ph was not in the retrieved set - so the strong-channel floor never
applied, the verification stage refuted nothing, and the critical came
entirely from the two fees. The card even said 'That is outside the .gov.ph
domain' while being worth zero.

The citation was missing because the scan took the forgery's misspelling at
face value, so the employer lookup searched for an agency that does not
exist. The existing fixture missed all of it by mocking the search to return
ched.gov.ph by hand - the one piece of evidence the live pipeline cannot find.

The government branch is a claim the posting makes about itself, so it needs
no retrieved source. The new fixture is the case the old one could not reach."
```

### Task 7: `OTHER` stops carrying a severity

**Files:**
- Modify: `backend/app/services/scanner/risk_calculator.py` (`_posting_risk_from_flags`)
- Modify: `backend/app/services/scanner/prompts.py` and `backend/SYSTEM_PROMPT.md` (the `OTHER` rule)
- Test: `backend/tests/test_risk_model.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: a finding whose code is `OTHER` contributes the `low` weight (4 points) whatever severity the model gave it.

**Note on the file this test lives in.** `risk_calculator.py` and `test_risk_model.py` are deleted in Task 8, one task later. This task is still worth doing on its own: between the two tasks the product is the old score-based one, and the corpus measured `OTHER` findings at 12 points each on four legitimate postings. The durable half is the prompt rule, which survives into Part 2 and beyond.

- [ ] **Step 1: Write the failing test** in `backend/tests/test_risk_model.py`:

```python
def test_an_other_finding_contributes_the_low_weight_whatever_its_severity():
    flags = [Anomaly(flag="Offers grocery bags to walk-ins", reasoning="x", severity="mid", code="OTHER")]
    score, _level, _breakdown = _posting_risk_from_flags(flags)
    assert score == 4
```

- [ ] **Step 2: Run the test to verify it fails** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_risk_model.py -q`. Expected: FAIL — `assert 12 == 4`.

- [ ] **Step 3: Implement** — in `_posting_risk_from_flags`, treat a finding whose `code` is `OTHER` as `low` before counting. In both prompts, write the rule: `OTHER` is for a finding whose shape is not in the list, and it is not for a benefit, an event, a hiring condition, a preference, or anything else a reader would not act on differently.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner/risk_calculator.py backend/app/services/scanner/prompts.py backend/SYSTEM_PROMPT.md backend/tests/test_risk_model.py
git commit -m "fix: OTHER no longer carries the model's severity

The corpus measured four legitimate postings with a mid-severity OTHER
finding: grocery bags for walk-ins, an in-person hiring event, and two
gender preferences. Each was worth 12 points, and any of them would have
reached moderate had the posting also carried a free email.

OTHER is the escape valve for a finding whose shape the taxonomy does not
name. It cannot also be a charge, because the charge is defined by the shape.
It contributes the low weight, and in Part 2 it makes the posting's class
'unclassified' - a question, not a charge."
```

**Part 1 done.** Run `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q` and `npm test -- --run`, then re-measure the corpus (§Task 23 describes the script) and check that the two false positives are gone and that Fake CHED is still `critical` with `channel_escalation == "government"`.

---

# Part 2 — The clerk

### Task 8: `verdict.py` decides, and it decides without a number

**Files:**
- Modify: `backend/app/services/scanner/verdict.py`
- Create: `backend/app/services/scanner/establishment.py` (the `Establishment` dataclass and the provisional mapping; Task 21 fills in the real decision)
- Modify: `backend/app/services/scanner/verification_flow.py` and `offer_flow.py` (the two call sites of `code_verdict`)
- Delete: `backend/app/services/scanner/risk_calculator.py` (with the tombstone in `backend/tests/test_scanner_package.py`)
- Test: `backend/tests/test_code_verdict.py`

**Interfaces:**
- Consumes: the request class (Task 4) and the establishment state.
- Produces:

```python
# establishment.py
VERDICTS = ("clear", "note", "caution", "stop")

@dataclass(frozen=True)
class Establishment:
    state: str            # confirmed | supported | unknown | contradicted
    reason: str = ""

# verdict.py
def code_verdict(
    anomalies: list,
    items: list[VerificationItem],
    assessments: list = (),
    *,
    request_class: str = "ordinary",
    establishment: Establishment | None = None,
) -> tuple[str, dict]
```

The breakdown it returns is the record of how the verdict was reached — `verdict`, `exposure`, `establishment`, `rule`, `record` — and carries **no number**.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_code_verdict.py`, one per cell of the grid and one per rule that decides it:

```python
def test_an_ordinary_request_at_an_unknown_employer_is_clear():
    verdict, breakdown = code_verdict([], [], request_class="ordinary",
                                       establishment=Establishment("unknown"))
    assert verdict == "clear"


def test_a_prohibited_request_at_an_unknown_employer_is_caution():
    verdict, _ = code_verdict([], [], request_class="prohibited",
                              establishment=Establishment("unknown"))
    assert verdict == "caution"


def test_a_prohibited_request_at_a_confirmed_employer_is_a_note():
    verdict, _ = code_verdict([], [], request_class="prohibited",
                              establishment=Establishment("confirmed"))
    assert verdict == "note"


def test_an_unclassified_request_is_a_note():
    verdict, _ = code_verdict([], [], request_class="unclassified",
                              establishment=Establishment("supported"))
    assert verdict == "note"


def test_a_contradicted_employer_stops_whatever_the_request():
    verdict, breakdown = code_verdict([], [], request_class="ordinary",
                                      establishment=Establishment("contradicted"))
    assert verdict == "stop"
    assert breakdown["establishment"]["state"] == "contradicted"
```

and a test asserting `code_verdict` returns a breakdown with **no** key whose name contains "score" and no value that is a number representing risk.

- [ ] **Step 2: Run the tests to verify they fail** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_code_verdict.py -q`. Expected: FAIL — the signature does not exist.

- [ ] **Step 3: Implement** — rewrite `verdict.py` around the grid from the spec §3.4:

| Class of the request | `confirmed` | `supported` | `unknown` | `contradicted` |
|---|---|---|---|---|
| ordinary only | clear | clear | clear | **stop** |
| cannot be classified | note | note | note | **stop** |
| prohibited | note | caution | caution | **stop** |

`contradicted` is the only path to `stop`. `unknown` never rises above a note on its own. `prohibited` + `confirmed` softens to a note because the reader can go and see the thing on the employer's own site.

**Provisional establishment in this part.** Part 4 decides establishment properly. Until then, `establishment.py` derives the state from today's channel escalation: `government` or `lookalike` → `contradicted`; a `match` escalation → `confirmed`; a green `Company Existence` → `supported`; anything else → `unknown`. A red `Reputation` is **not** a contradiction — reputation is not a claim about who is asking.

**Update the two call sites.** `verification_flow.py` and `offer_flow.py` both call `code_verdict` and both expect the old `(score, level, breakdown)` triple. They now take `(verdict, breakdown)`, and the level they put on the wire is the verdict string. Nothing else in either file changes.

- [ ] **Step 4: Delete `risk_calculator.py`** and add the tombstone to `backend/tests/test_scanner_package.py`, in the house style of the existing tombstones: assert the name is absent from the package and that the module file is gone, and say why in the test's docstring. Update `backend/tests/test_risk_model.py` — it recomputes the AHP weights and has no reason to exist — by deleting it and replacing it with a tombstone that asserts `app.services.scanner.risk_calculator` cannot be imported.

- [ ] **Step 5: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q`. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/scanner/verdict.py backend/app/services/scanner/__init__.py backend/tests/test_code_verdict.py backend/tests/test_scanner_package.py backend/tests/test_risk_model.py
git commit -m "feat: the verdict is a decision procedure, not a sum

The score was a sum of weights over categories, and nothing in 37 describes a
posting. A panelist asking where the number came from gets no answer, and
the Saaty derivation does not help: AHP needs a fixed commensurable variable
set and a job post is not one.

The verdict is now a class of request against an establishment, decided by an
authored grid. STOP requires a contradiction, which is the only path to the
strongest output and the only one that needs hard evidence. 'contradicted' is
the only path to stop; 'unknown' never rises above a note on its own; a
prohibited request at a confirmed employer softens to a note because the
reader can go and see it for themselves.

risk_calculator.py is deleted with a tombstone. docs/scoring.md and
scripts/derive_refutation_weights.py go with it in Task 10."
```

### Task 9: The authored statements and options

**Files:**
- Create: `backend/app/services/scanner/verdict_copy.py`
- Test: `backend/tests/test_verdict_copy.py` (new)

**Interfaces:**
- Consumes: the verdict, the request class, the establishment, and the structured facts (the amount, the fee's recipient and reason, what kind of documents).
- Produces:

```python
def statement(verdict: str, *, request_class: str, establishment: Establishment,
              facts: StatementFacts) -> str
def options(verdict: str) -> tuple[str, ...]
```

`StatementFacts` is a frozen dataclass with `amount: str = ""`, `fee_recipient: str = ""`, `fee_reason: str = ""`, `documents: str = ""`, `role: str = ""`.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_verdict_copy.py`:

```python
def test_a_clear_statement_names_what_the_posting_does_ask():
    text = statement("clear", request_class="ordinary",
                     establishment=Establishment("unknown"),
                     facts=StatementFacts(amount="500", fee_reason="a uniform"))
    assert "500" in text
    assert "uniform" in text
    assert "safe" not in text
    assert "legitimate" not in text


def test_a_clear_statement_never_says_the_employer_is_safe():
    text = statement("clear", request_class="ordinary", establishment=Establishment("unknown"),
                     facts=StatementFacts())
    assert "safe" not in text and "legitimate" not in text and "genuine" not in text


def test_a_stop_statement_names_the_impersonation():
    text = statement("stop", request_class="prohibited",
                     establishment=Establishment("contradicted"), facts=StatementFacts())
    assert "not from the employer it names" in text
```

- [ ] **Step 2: Run the tests to verify they fail** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_verdict_copy.py -q`. Expected: FAIL — no module.

- [ ] **Step 3: Implement** — the statements are templates with the structured facts substituted. The rules:

  - Every statement has **two parts**: what the posting asks for, and what the record showed. The first comes from the facts, the second from the establishment.
  - A `clear` statement **must not say the posting asks for nothing** when it asks for something. A posting that asks for a ₱500 uniform is clear and says so.
  - No statement contains an accusation and no statement contains a hedge — no "likely", "appears", "suggests", "may", "might", "could". The same word ban `clean_verdict_reason` applies, because the same reader-facing risk applies.
  - The `options` are per verdict family and offer the reader's choices rather than orders. `clear` gets one; `stop` gets "do not send money or documents"; `caution` gets the specific thing to settle first.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_verdict_copy.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner/verdict_copy.py backend/tests/test_verdict_copy.py
git commit -m "feat: authored statements and options for each verdict

Every word is in code and looked up, like the panel's own copy. The statement
is rendered from structured facts off the record - the amount, the fee's
recipient and reason, what kind of documents - so the panel never puts model
prose in front of the reader.

The rule that catches me: a clear statement must not say the posting asks for
nothing when it asks for something. A posting that asks for a 500 peso
uniform is clear, and the sentence has to say so, because a false statement
on the panel is the one thing the libel guardrail cannot tolerate."
```

### Task 10: The wire loses the score

**Files:**
- Modify: `backend/app/models/schemas.py` (`ScanResponse`, `VerificationResult`)
- Modify: `backend/app/services/scanner/verification_flow.py` (the result event)
- Modify: `backend/app/services/scanner/scan_result.py`
- Modify: `entrypoints/sidepanel/types/index.ts`, `entrypoints/sidepanel/lib/api.ts`, `entrypoints/sidepanel/lib/mapApiResponse.ts`
- Delete: `entrypoints/sidepanel/lib/scoreBreakdown.ts` (with a tombstone)
- Delete: `backend/scripts/derive_refutation_weights.py` (with a tombstone in `backend/tests/`)
- Delete: `docs/scoring.md`, `docs/decisions/scoring-model.md`
- Test: `backend/tests/test_code_verdict.py`, `entrypoints/sidepanel/lib/api.test.ts` if it exists

**Interfaces:**
- Consumes: Task 8's `code_verdict` and Task 9's `statement`.
- Produces: `VerificationResult.verdict: str = ""` and `VerificationResult.verdict_breakdown: dict = {}` replace `riskLevel` / `riskScore` / `scoreBreakdown`. `ScanResponse.verdict: str = ""` and `ScanResponse.verdict_breakdown: dict = {}` replace `risk_level` / `risk_score` / `score_breakdown`.

- [ ] **Step 1: Write the failing test** — a verify response carries `verdict` and `verdict_breakdown`, and the payload carries **no** key named `riskLevel`, `riskScore` or `scoreBreakdown`. Assert on the keys of the result dict, not on their values.

- [ ] **Step 2: Run the test to verify it fails** — `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q`. Expected: FAIL — the old keys are present.

- [ ] **Step 3: Implement** — rename the fields on both schemas and in the result event; delete `scoreBreakdown.ts` and `derive_refutation_weights.py` with tombstones in the house style; delete `docs/scoring.md` and `docs/decisions/scoring-model.md`. Update `backend/app/models/schemas.py`'s `RISK_LEVELS` to `VERDICTS = ("clear", "note", "caution", "stop")` and every place that imports it — `verification_flow.py`, `offer_flow.py`, `offer_prompt.py`.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/schemas.py backend/app/services/scanner/verification_flow.py backend/app/services/scanner/scan_result.py entrypoints/sidepanel/types/index.ts entrypoints/sidepanel/lib/api.ts entrypoints/sidepanel/lib/mapApiResponse.ts backend/scripts/derive_refutation_weights.py docs/scoring.md docs/decisions/scoring-model.md
git commit -m "feat: the wire loses the score

riskScore, riskScored and scoreBreakdown are gone, and with them the
remaining home for the retired number: the resume-match list still rendered
'40% Risk' next to every job. verdict and verdictBreakdown replace them, and
the breakdown is a record of how the verdict was reached - the class of the
request, the establishment, the rule that fired, and the sources - not a
magnitude.

docs/scoring.md and the Saaty derivation go with the number. The work was
not wrong; it answered a question this product no longer asks."
```

### Task 11: The panel reads the new vocabulary

**Files:**
- Modify: `entrypoints/sidepanel/components/report/verdictCopy.ts`
- Modify: `entrypoints/sidepanel/components/report/ActionBlock.tsx`
- Modify: `entrypoints/sidepanel/components/report/VerdictBlock.tsx`
- Modify: `entrypoints/sidepanel/components/report/ReportPanel.tsx`
- Modify: `entrypoints/sidepanel/types/index.ts` (`ScanRiskLevel` → `Verdict`)
- Test: `entrypoints/sidepanel/components/report/verdictCopy.test.ts`

**Interfaces:**
- Consumes: `verdict` and `verdictBreakdown` from the wire (Task 10) and the backend's statement (Task 9).
- Produces: `verdictFor(verdict: Verdict | null): VerdictCopy`, `actionsFor(verdict: Verdict | null): ActionLines`, and `VerdictBlock` rendering the label as a chip and the statement beneath it.

- [ ] **Step 1: Write the failing test** in `verdictCopy.test.ts`, following the house style of the existing level→headline contract test:

```ts
it('never tells the reader to stop below stop', () => {
  for (const verdict of ['clear', 'note', 'caution'] as const) {
    expect(verdictFor(verdict).headline).not.toMatch(/do not proceed/i);
  }
});
```

and a test that `actionsFor('stop')` offers the reader's options without the word "proceed", and that `actionsFor('clear')` does not carry an alarm.

- [ ] **Step 2: Run the test to verify it fails** — `npm test -- --run`. Expected: FAIL — the vocabulary is the old one.

- [ ] **Step 3: Implement** — the label vocabulary becomes `clear | note | caution | stop` with tones `verified | caution | critical | unknown`. **"Do not proceed" is the ace card**: it is the headline for `stop` only, and `stop` requires a contradiction. Every other verdict's statement comes from the backend's authored statement. The action block offers the reader's options rather than orders.

- [ ] **Step 4: Run the tests to verify they pass** — `npm test -- --run` and `npm run compile`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add entrypoints/sidepanel/components/report/ entrypoints/sidepanel/types/index.ts
git commit -m "feat: the panel reads the verdict vocabulary

'Do not proceed' is the ace card: it is said only for stop, and stop
requires a contradiction. Every other verdict states what was found and what
the record showed, and the action block offers the reader's options instead
of ordering them - the reader is the judge."
```

### Task 12: One status vocabulary, and the missing-employer state

**Files:**
- Modify: `entrypoints/sidepanel/components/report/WhatWeChecked.tsx`
- Modify: `entrypoints/sidepanel/components/report/FullDetails.tsx`
- Modify: `entrypoints/sidepanel/components/report/AnomalyCards.tsx`
- Modify: `entrypoints/sidepanel/components/report/checkPresentation.ts`
- Modify: `backend/app/services/scanner/verification_flow.py` (the status the model writes is no longer a status)
- Test: `entrypoints/sidepanel/components/report/AnomalyCards.test.tsx`, `backend/tests/test_code_verdict.py`

**Interfaces:**
- Consumes: the four establishment states.
- Produces: the six claim categories keep their **grouping** and lose their green/yellow/red statuses; the per-item state becomes `confirmed | supported | unknown | contradicted`, and the retired-by-the-record state keeps the name `stale`.

- [ ] **Step 1: Write the failing test** — a check with no state other than the four renders as one of the four; a check whose state is `contradicted` renders with the critical treatment; and a posting that names no employer renders the grey "no verdict on this one" with the employer prompt, **not** a verdict.

- [ ] **Step 2: Run the test to verify it fails** — `npm test -- --run`. Expected: FAIL.

- [ ] **Step 3: Implement** — collapse both status vocabularies onto the four states. A model-written status beside a code-owned establishment state is two verdicts in one panel and they will disagree, so the model's per-category status stops being a status: the category becomes a **fact with its source**, and the state comes from the code.

- [ ] **Step 4: Run the tests to verify they pass** — `npm test -- --run` and `npm run compile`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add entrypoints/sidepanel/components/report/ backend/app/services/scanner/verification_flow.py
git commit -m "refactor: one status vocabulary

The panel carried two incompatible status systems - green/yellow/red for the
six claim categories and stale/yellow/red for the findings - and a
model-written one beside a code-owned one is two verdicts in one panel. They
will disagree, and the corpus caught one: a red Location/Branch card on a
600-store franchise, because the company's own page listed a different venue.

The categories survive as the grouping of the record. Their statuses retire
onto the four establishment states."
```

### Task 13: History and the resume-match list

**Files:**
- Modify: `entrypoints/sidepanel/lib/scanHistory.ts` (`migrateScannedJobs`)
- Modify: `entrypoints/sidepanel/views/ResumeMatchView.tsx`
- Modify: `entrypoints/sidepanel/types/index.ts` (`JobFilterCategory`)
- Test: `entrypoints/sidepanel/views/ScamScanView.restore.test.tsx`, `entrypoints/sidepanel/views/ResumeMatchView.riskMessage.test.tsx`

**Interfaces:**
- Consumes: the new vocabulary.
- Produces: `migrateScannedJobs` maps a stored `low` → `clear`, `moderate` → `caution`, `high` → `stop`, `critical` → `stop`, and marks the entry as recorded under the previous procedure. `JobFilterCategory` becomes `'clear' | 'note' | 'caution' | 'stop'`.

- [ ] **Step 1: Write the failing test** — a stored scan with `riskLevel: "moderate"` restores as `verdict: "caution"` with `verdictRecordedUnder: "previous-procedure"`, and restores **without** inventing a request class or an establishment. A stored scan is never silently re-labelled as a new verdict.

- [ ] **Step 2: Run the test to verify it fails** — `npm test -- --run`. Expected: FAIL.

- [ ] **Step 3: Implement** — the migration, the `JobFilterCategory` union, the list's filter (include `clear` and `note`, exclude `caution` and `stop`), and the removal of the "40% Risk" render in favour of the verdict label.

- [ ] **Step 4: Run the tests to verify they pass** — `npm test -- --run` and `npm run compile`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add entrypoints/sidepanel/lib/scanHistory.ts entrypoints/sidepanel/views/ResumeMatchView.tsx entrypoints/sidepanel/types/index.ts entrypoints/sidepanel/views/
git commit -m "feat: migrate stored history, and show the verdict instead of a percentage

A stored scan carries a level and no request class and no establishment, so a
new verdict cannot be computed from it. It restores as the old label with a
note that it was recorded under the previous procedure. It is never silently
re-labelled as a verdict the system did not reach."
```

**Part 2 done.** The score is gone from the wire, the code and the panel. Re-measure the corpus: every legitimate posting must now be `clear` or `note`, and Fake CHED must be `stop` with the impersonation in the statement.

---

# Part 3 — The agent loop

### Task 14: `fetch.py`

**Files:**
- Create: `backend/app/services/fetch.py`
- Test: `backend/tests/test_fetch.py` (new)

**Interfaces:**
- Consumes: a URL.
- Produces:

```python
@dataclass(frozen=True)
class FetchedPage:
    url: str
    text: str
    truncated: bool

async def fetch_page(url: str, *, max_bytes: int) -> FetchedPage
```

Raises `FetchRefused` for a scheme that is not http/https, a host that resolves to a loopback, link-local, private or reserved address, a redirect to one, or a body over the cap.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_fetch.py`:

```python
async def test_a_private_address_is_refused():
    with pytest.raises(FetchRefused):
        await fetch_page("http://127.0.0.1/admin", max_bytes=1000)


async def test_a_file_scheme_is_refused():
    with pytest.raises(FetchRefused):
        await fetch_page("file:///etc/passwd", max_bytes=1000)


async def test_a_page_over_the_cap_is_truncated():
    page = await fetch_page("https://example.com/", max_bytes=10)
    assert page.truncated is True
```

- [ ] **Step 2: Run the tests to verify they fail** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_fetch.py -q`. Expected: FAIL — no module.

- [ ] **Step 3: Implement** — httpx with `follow_redirects=False` and a manual redirect loop of at most 3 hops, each hop re-checking the resolved address. Resolve the host with `socket.getaddrinfo` and refuse any address in `127.0.0.0/8`, `10/8`, `172.16/12`, `192.168/16`, `169.254/16`, `::1`, `fc00::/7`, or `0.0.0.0/8`. Strip the HTML to text, cap the bytes, and mark the result truncated. The result is **untrusted input** and the framing that says so belongs to the agent's prompt (Task 16).

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_fetch.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/fetch.py backend/tests/test_fetch.py
git commit -m "feat: a fetch tool that refuses to touch anything private

The employer's own pages are the fact the verdict needs and the current
pipeline cannot get: the model only ever sees Tavily snippets, so it can
never know whether the employer's site lists this role.

A search result is untrusted input and can point anywhere, so the tool
resolves the host and refuses loopback, link-local, private and reserved
addresses, re-checking on every redirect hop."
```

### Task 15: Multi-turn chat and the text protocol

**Files:**
- Modify: `backend/app/services/lm_client.py` (a `messages` parameter and a `chat_turn` entry point)
- Create: `backend/app/services/scanner/agent_protocol.py` (the tool-call parser)
- Test: `backend/tests/test_agent_protocol.py` (new), `backend/tests/test_lm_client.py` if it exists

**Interfaces:**
- Consumes: nothing.
- Produces:

```python
# agent_protocol.py
@dataclass(frozen=True)
class ToolCall:
    name: str      # "search" | "fetch"
    argument: str

def parse_tool_calls(text: str) -> tuple[ToolCall, ...]
def is_final_answer(text: str) -> bool
```

and in `lm_client.py`:

```python
async def chat_turn(messages: list[dict], *, endpoint: str = "assess") -> str
```

which accepts a message list and returns the assistant's text.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_agent_protocol.py`:

```python
def test_a_search_call_parses():
    assert parse_tool_calls("TOOL: search\nARGUMENT: knollridges company or employer") == (
        ToolCall("search", "knollridges company or employer"),)


def test_text_that_merely_mentions_search_is_not_a_call():
    assert parse_tool_calls("I would search for the employer now.") == ()


def test_a_conclusion_word_in_an_argument_is_refused():
    # The query is refused before it is issued, so the parser must drop it.
    assert parse_tool_calls("TOOL: search\nARGUMENT: acme scam") == ()
```

- [ ] **Step 2: Run the tests to verify they fail** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_agent_protocol.py -q`. Expected: FAIL — no module.

- [ ] **Step 3: Implement** — the protocol is a labeled text block, not native tool calling: `lm_client.chat()` has no `tools=` parameter, no multi-turn support, and raises `EmptyModelResponse` on empty content, and native tool calls are not guaranteed across OpenRouter routes. The parser follows the house style of `verification_parser.py`'s labeled-text fallback. The conclusion-word filter is `search_planner.search_query_is_safe`; it drops the call and the agent is told.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_agent_protocol.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/lm_client.py backend/app/services/scanner/agent_protocol.py backend/tests/test_agent_protocol.py
git commit -m "feat: a text tool-call protocol and multi-turn chat

Native tool calling is not available on this client and is not guaranteed
across OpenRouter routes, so the protocol is labeled text and the parser is
the house style: a labeled-text fallback like verification_parser's.

The conclusion-word filter drops a query carrying scam or fraud or fake
before it is issued, in every mode. The prompt sentence is not the control."
```

### Task 16: `agent.py`

**Files:**
- Create: `backend/app/services/scanner/agent.py`
- Modify: `backend/app/config.py` (the four limits)
- Modify: `backend/app/services/scanner/dependencies.py` (the runtime seam every flow resolves collaborators through)
- Test: `backend/tests/test_agent.py` (new)

**Interfaces:**
- Consumes: `chat_turn`, `search`, `fetch_page`, `parse_tool_calls`.
- Produces:

```python
async def run_agent(
    posting: list[dict],
    *,
    system_prompt: str,
    tools: AgentTools,
    limits: AgentLimits,
) -> AgentResult
```

`AgentLimits` is a frozen dataclass with `max_turns: int = 4`, `max_searches: int = 3`, `max_fetches: int = 4`, `max_fetch_bytes: int = 200000`. `AgentResult` carries `text: str`, `turns: int`, `searches: int`, `fetches: int`, `tool_log: list[dict]`.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_agent.py`:

```python
async def test_the_posting_is_re_sent_on_every_turn():
    # The relay is the defect. The same posting must be in every request.
    ...

async def test_the_search_budget_is_three():
    ...

async def test_a_refused_query_does_not_spend_a_credit():
    ...

async def test_the_loop_stops_at_the_turn_limit():
    ...
```

- [ ] **Step 2: Run the tests to verify they fail** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_agent.py -q`. Expected: FAIL — no module.

- [ ] **Step 3: Implement** — the loop: build the messages, call `chat_turn`, parse the tool calls, run the tools, append the results, and re-send **the posting together with the whole transcript** on every turn. The posting is never summarised on the way. The first turn's system prompt carries `NO_ONLINE_ACCESS`; later turns carry the tool definitions and the untrusted-input warning.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_agent.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner/agent.py backend/app/config.py backend/app/services/scanner/dependencies.py backend/tests/test_agent.py
git commit -m "feat: one agent that holds the posting for the whole proceeding

The scan->verify relay exists because two models were cheaper than one, and
the cost was the compression. The corpus showed what it costs: the scan took
the forgery's misspelled agency name at face value, so the employer lookup
searched for an agency that does not exist, so the one rule written for that
case fired and was discarded, so the verdict rested on the fees.

The posting is re-sent on every turn and never summarised on the way. There
is no hop where the context can be dropped."
```

### Task 17: The query filter is unconditional, and one search is reserved

**Files:**
- Modify: `backend/app/services/scanner/search_planner.py` (`search_query_is_safe` is applied in every mode)
- Modify: `backend/app/services/scanner/agent.py` (the reserved anchor query)
- Modify: `docs/decisions/search-retrieval.md` (the record that says the prompt sentence is the only control in the shipped default)
- Test: `backend/tests/test_multi_query.py`

**Interfaces:**
- Consumes: `search_query_is_safe` from `search_planner.py`.
- Produces: the agent's first search is always the code-built anchor — `"<company> company or employer"` — and the agent chooses the rest.

- [ ] **Step 1: Write the failing test** — a query carrying a conclusion word is refused in `fixed` mode as well as `adaptive`, and a refused query does not count against `AGENT_MAX_SEARCHES` and the agent is told so it can choose another.

- [ ] **Step 2: Run the test to verify it fails** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_multi_query.py -q`. Expected: FAIL — the filter is `adaptive`-only.

- [ ] **Step 3: Implement** and amend `docs/decisions/search-retrieval.md`, which states at length that in the shipped default the prompt sentence is the only control and that the code control exists only in the `adaptive` mode that ships off. The record is amended rather than left to contradict the code. Correct `lm_client.py`'s comment, which repeats the same statement three times.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner/search_planner.py backend/app/services/scanner/agent.py docs/decisions/search-retrieval.md backend/tests/test_multi_query.py
git commit -m "fix: the conclusion-word filter is a control in every mode

The record says the prompt sentence is the only control in the shipped
default, and that the code control exists only in the adaptive mode that
ships off. A prompt sentence is not a control: the exposure is a model
reading a job posting and writing 'Tanika scam'."

```

### Task 18: `/api/assess` replaces `/api/scan` and `/api/verify`

**Files:**
- Modify: `backend/app/routers/scan.py` (the new endpoint; the two old ones are deleted)
- Modify: `backend/app/main.py` if it routes by path
- Modify: `backend/app/services/scanner/scan_flow.py` and `verification_flow.py` (deleted or reduced to the agent's helpers)
- Modify: `backend/tests/test_scanner_package.py` (the pinned symbol list)
- Test: `backend/tests/test_assess_endpoint.py` (new)

**Interfaces:**
- Consumes: `run_agent` (Task 16).
- Produces: `POST /api/assess` with the same SSE shape as today — `progress` events and a final `result` event — carrying `valid`, `anomalies`, `attributes`, `request_class`, `verdict`, `verdict_breakdown`, `items`, `record`, `search_ok`, `search_count`, `establishment`.

- [ ] **Step 1: Write the failing test** — posting an image to `/api/assess` returns a result event with a `verdict` and no `riskLevel`, and `/api/scan` and `/api/verify` return 404.

- [ ] **Step 2: Run the test to verify it fails** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_assess_endpoint.py -q`. Expected: FAIL — the endpoint does not exist.

- [ ] **Step 3: Implement** — the endpoint runs the agent with the image, streams progress, and returns the result. Delete `/api/scan` and `/api/verify` and their flows, with tombstones in `test_scanner_package.py`. Keep the offer path (`/api/analyze-offer`) — it is a separate endpoint for postings that name no employer — and give it the same procedure in Task 21.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/scan.py backend/app/main.py backend/app/services/scanner/scan_flow.py backend/app/services/scanner/verification_flow.py backend/tests/
git commit -m "feat: one endpoint, /api/assess

The extension made one call to /api/scan and a second to /api/verify after
the first returned. That is the relay. The agent endpoint makes one call and
holds the posting for the whole proceeding.

The endpoint is named rather than overwriting /api/scan, so the deletion of
the old pair is a deliberate act."
```

### Task 19: The extension makes one call

**Files:**
- Modify: `entrypoints/sidepanel/lib/api.ts`
- Modify: `entrypoints/sidepanel/hooks/useScanSession.ts`
- Modify: `entrypoints/sidepanel/views/ScamScanView.tsx`
- Test: `entrypoints/sidepanel/views/ScamScanView.restore.test.tsx`

**Interfaces:**
- Consumes: the `/api/assess` stream.
- Produces: `scanAndAssess(imagesBase64: string[]): AsyncGenerator<...>` replacing the scan-then-verify pair. `verificationLoading` becomes one loading state.

- [ ] **Step 1: Write the failing test** — one request is made for a scan, and the result carries the verdict.

- [ ] **Step 2: Run the test to verify it fails** — `npm test -- --run`. Expected: FAIL.

- [ ] **Step 3: Implement** — the hook stops firing a second request; the two-phase loading collapses into one.

- [ ] **Step 4: Run the tests to verify they pass** — `npm test -- --run` and `npm run compile`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add entrypoints/sidepanel/lib/api.ts entrypoints/sidepanel/hooks/useScanSession.ts entrypoints/sidepanel/views/ScamScanView.tsx
git commit -m "feat: the extension makes one call

The scan-then-verify pair was the relay from the extension's side too."
```

---

# Part 4 — Establishment

### Task 20: The employer-record facts the agent reports

**Files:**
- Modify: `backend/app/services/scanner/prompts.py` and `backend/SYSTEM_PROMPT.md` (the agent's output format)
- Modify: `backend/app/models/schemas.py` (`EmployerRecord`)
- Modify: `backend/app/services/scanner/agent.py` (the final answer's shape)
- Test: `backend/tests/test_agent.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `EmployerRecord` with `domain: str = ""`, `domain_source_url: str = ""`, `pages: list[dict] = []`, `lists_role: str = ""` (an excerpt), `lists_role_source_url: str = ""`, `states_terms: str = ""`, `states_terms_source_url: str = ""`.

- [ ] **Step 1: Write the failing test** — the agent's final answer parses into an `EmployerRecord`, and every field that carries a fact about the employer's record carries a source URL.

- [ ] **Step 2: Run the test to verify it fails** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_agent.py -q`. Expected: FAIL.

- [ ] **Step 3: Implement** — the agent reports facts, never a state. The prompt says so in the same words as the libel guardrail.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_agent.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner/prompts.py backend/SYSTEM_PROMPT.md backend/app/models/schemas.py backend/app/services/scanner/agent.py backend/tests/test_agent.py
git commit -m "feat: the agent reports facts about the employer's record

Facts, never a state. The code decides what they mean, which is the rule the
whole design rests on: a model-produced boolean that establishes the
strongest state would be the same shape as the defect the design exists to
fix, one level up."
```

### Task 21: `establishment.py` decides

**Files:**
- Modify: `backend/app/services/scanner/establishment.py` (the provisional mapping from Task 8 becomes the real decision)
- Modify: `backend/app/services/scanner/verdict.py` (the call site)
- Modify: `backend/app/services/scanner/offer_flow.py` and `offer_prompt.py` (the offer path gets the same procedure)
- Test: `backend/tests/test_establishment.py` (new)

**Interfaces:**
- Consumes: `EmployerRecord` (Task 20), the posting's channels, the `government_claim` attribute.
- Produces:

```python
def decide_establishment(
    record: EmployerRecord,
    *,
    posting_channels: Sequence[str],
    government_claim: bool,
    retrieved: frozenset[str],
) -> Establishment
```

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_establishment.py`:

```python
def test_an_employer_with_their_own_channel_is_confirmed():
    est = decide_establishment(record, posting_channels=["recruitment@acme.com.ph"],
                                government_claim=False, retrieved=frozenset({"https://acme.com.ph"}))
    assert est.state == "confirmed"


def test_an_employer_found_but_without_this_posting_is_supported():
    est = decide_establishment(record, posting_channels=["hr@gmail.com"],
                                government_claim=False, retrieved=frozenset({"https://acme.com.ph"}))
    assert est.state == "supported"


def test_nothing_found_is_unknown():
    assert decide_establishment(EmployerRecord(), posting_channels=["hr@gmail.com"],
                                government_claim=False, retrieved=frozenset()).state == "unknown"


def test_a_government_claim_on_a_non_government_channel_is_contradicted():
    est = decide_establishment(record, posting_channels=["recruitment.chred@outlook.com"],
                                government_claim=True, retrieved=frozenset())
    assert est.state == "contradicted"
```

and a test that an unbound source URL leaves the state at `unknown` rather than `confirmed`.

- [ ] **Step 2: Run the tests to verify they fail** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_establishment.py -q`. Expected: FAIL — no module.

- [ ] **Step 3: Implement** — the four states, with the materiality rule: a contradiction is **identity-level only**. A wrong phone number beside a matching domain is `supported` with the mismatch recorded, not `contradicted`. The government claim plus a non-`.gov.ph` printed channel is `contradicted` and needs no retrieved source.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/ -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner/establishment.py backend/app/services/scanner/verdict.py backend/app/services/scanner/offer_flow.py backend/app/services/scanner/offer_prompt.py backend/tests/test_establishment.py
git commit -m "feat: establishment is decided over the employer's own record

Four states: confirmed, supported, unknown, contradicted. Confirmed means
their record shows this posting; supported means the employer was found and
nothing contradicts them; unknown means nothing was found either way, and it
is never punished on its own; contradicted means a retrieved source shows
the posting's claims are false, in a way that bears on who is asking.

The offer path gets the same procedure. It has no employer, so its
establishment is unknown by construction and the request class carries the
verdict - which closes the last model-owned level in the product."
```

### Task 22: `confirmed` is checked in code, against the fetched text

**Files:**
- Modify: `backend/app/services/scanner/establishment.py`
- Modify: `backend/app/services/fetch.py` (expose the fetched text for the check)
- Test: `backend/tests/test_establishment.py`

**Interfaces:**
- Consumes: the fetched page's text and the role title.
- Produces: `page_shows_role(page_text: str, role_title: str) -> bool` — a case-insensitive containment check on the fetched text, with whitespace collapsed. The model's excerpt is **not** the check.

- [ ] **Step 1: Write the failing test** — a fetched page that does not contain the role title does not confirm, even when the model says it does; a fetched page that contains it does.

- [ ] **Step 2: Run the test to verify it fails** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_establishment.py -q`. Expected: FAIL.

- [ ] **Step 3: Implement** — the check runs against the fetched text. A model-proposed excerpt that does not contain the thing does not establish it.

- [ ] **Step 4: Run the tests to verify they pass** — `cd backend && .venv\Scripts\python.exe -m pytest tests/test_establishment.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner/establishment.py backend/app/services/fetch.py backend/tests/test_establishment.py
git commit -m "fix: confirmed is checked against the fetched text, not the model's word

The strongest state was resting on a model boolean, which is the same shape
as the defect this whole change exists to fix, one level up. The code checks
that the fetched page contains the role title. If it does not, the state is
not confirmed."
```

### Task 23: Re-measure the corpus

**Files:**
- Create: `backend/scripts/corpus_run.py` (the runner; it is a script, and it is **not** committed if the reviewer's corpus is local — the script is, the images are not)
- Modify: `docs/research/2026-10-21-corpus-baseline.md` (a second "after" section)
- Test: none — this is a measurement, not a test

**Interfaces:**
- Consumes: the running backend and the reviewer's `jobposts/`.
- Produces: a JSON record per posting, the same shape as the baseline's, and a before/after table.

- [ ] **Step 1: Write the runner** — the same script the baseline used: for each image, `POST /api/assess`, parse the SSE result, write one JSON record. A 13-second pause between calls keeps the endpoints under their 5-per-minute limit. It must not be run without the reviewer's explicit permission, because it calls the provider.

- [ ] **Step 2: Run it** and record the results in `docs/research/2026-10-21-corpus-baseline.md` as an "after" section: every legitimate posting's verdict, and Fake CHED's.

- [ ] **Step 3: Check the acceptance criteria** — no legitimate posting reaches `caution` or `stop`; Fake CHED is `stop` with the impersonation in the statement and not the fee; every changed verdict is explained by a named rule. Any that is not is a finding, and the finding is recorded before it is fixed.

- [ ] **Step 4: Commit** the runner and the updated baseline:

```bash
git add backend/scripts/corpus_run.py docs/research/2026-10-21-corpus-baseline.md
git commit -m "docs: the corpus after the verdict procedure

The before column is in the same file. The corpus is the reviewer's local
machine and is not committed."
```

### Task 24: The controlled pairs, and the docs

**Files:**
- Create: `docs/decisions/verdict-procedure.md` (the decision record: the two axes, the grid, the materiality rule, the burden of proof, and why the score is gone)
- Modify: `AGENTS.md` (the contradictions list: #3 and #5 closed, #6 and #8 given their homes, #7 closed)
- Modify: `docs/architecture.md`, `Documentation.md`
- Modify: `docs/decisions/verification-design.md` (the categories survive as the record's grouping)
- Modify: `docs/decisions/libel-guardrail.md` (the burden of proof, and that memory is not a source)
- Modify: `docs/superpowers/specs/2026-10-17-anomaly-code-set.md` (the split, and the fee question now closed by the research)
- Modify: `docs/gotchas.md` (the new traps)

**Interfaces:**
- Consumes: everything above.
- Produces: the record of the decision, and a repository whose documentation map matches the code.

- [ ] **Step 1: Write the decision record** `docs/decisions/verdict-procedure.md` — the house style is the existing records: what the failure was, what replaced it, the rules with their citations, what each one costs, and what the decision does not do.

- [ ] **Step 2: Update the contradictions list** in `AGENTS.md`: #3 (the calculator is live again) is now resolved the other way, with the reason; #5 (the offer path's model-owned level) is closed; #6 (`escalation`) and #8 (`rounds`) are given their new homes (`establishment.reason` and the agent transcript); #7 (the identity question) is closed by Tasks 21 and 22.

- [ ] **Step 3: Update the rest of the documentation** listed above, so that every fact is stated in exactly one place.

- [ ] **Step 4: Run the whole suite and commit**

```bash
cd backend && .venv\Scripts\python.exe -m pytest tests/ -q && cd .. && npm test -- --run && npm run compile
git add AGENTS.md docs/
git commit -m "docs: the verdict procedure, and the records it supersedes"
```

---

## Self-review

**Spec coverage.** Every section of the spec maps to a task: §3.1 the taxonomy and the facts → Tasks 1–3; §3.2–§3.3 the establishment → Tasks 20–22; §3.4 the grid → Task 8; §3.5 the statement → Task 9; §4 the loop → Tasks 14–19; §5 the wire → Task 10 and Task 18; §6 the agent's output → Tasks 16 and 20; §7 the panel → Tasks 9, 11, 12, 13; §8 what dies → Tasks 8 and 10; §9 the phasing → the four parts; §10 the tests → every task's Step 1, plus Task 23; §12 the open questions → Task 23's acceptance criteria, and the copy questions for the reviewer.

**Gaps found and closed during review.** The spec's §12 open question on the corpus is answered by Task 23 and the pairs in the baseline §8; the spec's `POSTING_SEVERITY_WEIGHTS` removal is in Task 8; the spec's mention of `docs/decisions/scoring-model.md` is in Task 10; the offer path's model-owned level is closed in Task 21.

**Type consistency.** `classify_request` returns a `REQUEST_CLASSES` member; `code_verdict` takes `request_class: str` and an `Establishment`; `Establishment` is defined in Task 8 and imported by Tasks 9, 21 and 22; `StatementFacts` is defined in Task 9 and consumed there only; `EmployerRecord` is defined in Task 20 and consumed by Task 21. `apply_channel_rules` changes signature in Task 5 and its call site is in Task 5.

**Review Focus coverage.** Item 1 is pinned by Task 3's `test_a_free_email_with_an_ordinary_packet_is_ordinary` and Task 5's `test_a_free_email_with_an_ordinary_request_stays_yellow`. Item 2 by Task 6. Item 3 by Task 3's `test_a_fee_with_no_stated_recipient_cannot_be_classified`. Item 4 by Task 7 and Task 12. Item 5 by Task 6 and Task 21's unbound-source test.

**Proportion.** The plan is longer than the spec because the spec is a design and the plan has a test cycle per task; the code blocks are test bodies and signatures, not implementations.

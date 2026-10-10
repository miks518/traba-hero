# Dynamic Anomaly Verification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed employer-name verification queries with dynamic queries built from the posting's own claims, and make the verification stage score only *refutations* — never absence.

**Architecture:** The existing scan call additionally emits posting attributes and up to 3 search queries; no new LLM call. Retrieval runs company queries plus those attribute queries into one merged result set. One verification call returns per-claim statuses where `green` = confirmed, `red` = a source contradicts the claim, `yellow` = nothing learned. `risk_calculator` gains a refutation stage capped at 50 points, combined with a floor so no search result can lower the posting's own score.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest (offline suite), httpx. Frontend React 19 + TypeScript + WXT + Vitest.

**Spec:** `docs/superpowers/specs/2026-10-10-dynamic-anomaly-verification-design.md`

## Global Constraints

- **Never call the AI provider or Tavily.** The key is shared; hitting the 24-hour limit blocks the developer's own testing for a day. Every test runs against the offline fixture in `backend/tests/conftest.py`. No `pytest.mark.skip`, no live smoke tests.
- **No placeholders, no "similar to Task N".** Every step carries its own code.
- **Deterministic scoring only.** The LLM never computes a number. `risk_calculator.py` owns every calculation.
- **Absence is never `red`.** A claim nobody could confirm is `yellow`. Points require a retrieved source that *contradicts* the claim.
- **Confirmed claims add exactly 0.** Verification withholds trust; it never grants it.
- **Query terms come from posting content, never from model-written anomaly labels.** A `high`-severity label is a characterisation; using it as a query term reintroduces the conclusion-in-query bias `search.py` bans.
- **The employer name is used verbatim.** No corporate-suffix strip, no rewrite, anywhere.
- **No verdict words from any model output.** Banned: scam, legitimate, suspicious, genuine, fraudulent, honest. Also banned in `finding`: verified, safe, authorized.
- **Legacy paths stay.** `RED FLAG` remains an accepted parse keyword; `EMPLOYER NAME` remains accepted alongside `COMPANY NAME`. Do not remove either.
- **Preserve `SearchOutcome.ok`/`.results` independence** and the `search_partial` state. Every task touching retrieval must keep both.

## Review Focus

Five input classes the spec implies but no single task's tests obviously cover. Each gets a test in the task that owns the code, listed here so they are not lost.

1. **A posting with no employer and no location.** Must produce zero attribute queries, zero credits spent, and still show its anomalies. A naive "one query per attribute" implementation spends credits here.
2. **A posting whose only anomaly is `low`.** Must produce no queries — a formatting note is never corroborated, so `QUERY_REF` is absent and it can never be double-counted.
3. **A provider that drops `response_format`.** The request succeeds, the text parser runs, and if *that* fails the panel must say so rather than rendering empty cards. This fails **silently** today.
4. **A `red` whose source is generic.** "Task-for-earning schemes are usually scams" refutes nothing about this posting and must be `yellow`.
5. **An anomaly with `QUERY_REF` pointing at a query that failed.** Corroboration must not be credited from a search that never returned.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/models/schemas.py` | `Anomaly` gains `query_ref`; new `PostingAttributes`; `ScanResponse` gains `attributes`, `search_queries`; `VerificationItem` gains `source_query` |
| `backend/app/services/scanner/prompts.py` | `SCAN_FORMAT_BLOCK` emits attributes + queries; `QUERY_REF` line; query-selection rules |
| `backend/SYSTEM_PROMPT.md` | Same, in the file the backend loads |
| `backend/app/services/lm_client.py` | `_SECTION_RE` gains the new keywords; `_parse_custom` reads them; placeholder filter extended |
| `backend/app/services/scanner/scan_result.py` | `_attributes()`, `_search_queries()` factories |
| `backend/app/services/search.py` | `build_queries()` gains `build_scheme_queries()`; `CHECKABLE_ATTRIBUTES` |
| `backend/app/services/scanner/verification_prompt.py` | `VERIFY_RESPONSE_SCHEMA` gains the claim categories; prompt rewritten around confirmed/refuted/unverified |
| `backend/app/services/scanner/verification_parser.py` | Text fallback for the new shape; distinguishes "parsed nothing" from "could not parse" |
| `backend/app/services/scanner/verification_flow.py` | Runs scheme queries; reports `scheme_queries`; raises the loud parse failure |
| `backend/app/services/scanner/risk_calculator.py` | `_refutation_score_from_verify()`; `_combine_scores()` gains the floor |
| `entrypoints/sidepanel/types/index.ts` | `PostingAttributes`, `VerificationItem.queryRef` |
| `entrypoints/sidepanel/components/scan/VerificationSection.tsx` | → "Evidence Summary"; heading derived from state |
| `entrypoints/sidepanel/components/scan/AnomaliesList.tsx` | Renders as Evidence Summary's first child |

---

### Task 1: Scan emits posting attributes and search queries

Extends the existing scan call. No new LLM call.

**Files:**
- Modify: `backend/SYSTEM_PROMPT.md` (Output Format block, section 2)
- Modify: `backend/app/services/scanner/prompts.py:32-41` (`SCAN_FORMAT_BLOCK`), `:52-60` (field rules)
- Modify: `backend/app/services/lm_client.py:253-261` (`_SECTION_RE`), `:308-374` (`_parse_custom`)
- Modify: `backend/app/models/schemas.py:16-31` (`ScanResponse`), `:10-27` (`Anomaly`)
- Test: `backend/tests/test_anomaly_parsing.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ScanResponse.attributes: dict`, `ScanResponse.search_queries: list[str]`, `Anomaly.query_ref: str`. `_parse_custom` result gains keys `"attributes"` (dict) and `"search_queries"` (list[str]).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_anomaly_parsing.py`:

```python
class TestPostingAttributes:
    """The scan must report what the posting claims, not only who it names.

    This is what makes dynamic retrieval possible: a query can only be built
    from a detail the posting actually states, so the detail has to be stated.
    """

    def test_attributes_parse(self):
        raw = (
            "VALID: true\n"
            "ATTRIBUTES:\n"
            "COMPANY: Tanika\n"
            "LOCATION: Maingate Terminal\n"
            "CONTACT_METHOD: personal Gmail\n"
            "MEETING_SPOT: Maingate Terminal\n"
            "PAY: 26,000 monthly\n"
            "END ATTRIBUTES\n"
            "EMPLOYER NAME: Tanika\n"
        )
        result = _parse_custom(raw)
        assert result is not None
        assert result["attributes"]["LOCATION"] == "Maingate Terminal"
        assert result["attributes"]["CONTACT_METHOD"] == "personal Gmail"

    def test_a_missing_attribute_is_not_emitted(self):
        """A missing detail must not become an empty string.

        An empty LOCATION would otherwise read as "the posting stated no
        location", which is a different claim from "the posting said nothing
        about location" — and it would generate a query that cannot succeed.
        """
        raw = "VALID: true\nATTRIBUTES:\nCOMPANY: Tanika\nEND ATTRIBUTES\n"
        result = _parse_custom(raw)
        assert "LOCATION" not in result["attributes"]
        assert "Not stated" not in result["attributes"].values()

    def test_end_attributes_does_not_reset_the_parser(self):
        raw = "VALID: true\nATTRIBUTES:\nCOMPANY: Tanika\nEND ATTRIBUTES\nEMPLOYER NAME: Tanika\n"
        result = _parse_custom(raw)
        assert result["company_name"] == "Tanika"

    def test_search_queries_parse_in_order(self):
        raw = (
            "VALID: true\n"
            "SEARCH QUERIES:\n"
            "QUERY: Tanika Maingate Terminal recruitment\n"
            "QUERY: Tanika hiring schedule\n"
            "END SEARCH QUERIES\n"
        )
        result = _parse_custom(raw)
        assert result["search_queries"] == [
            "Tanika Maingate Terminal recruitment",
            "Tanika hiring schedule",
        ]

    def test_no_queries_section_yields_an_empty_list_not_a_missing_key(self):
        result = _parse_custom("VALID: true\nEMPLOYER NAME: Acme\n")
        assert result["search_queries"] == []

    def test_a_placeholder_query_is_dropped(self):
        raw = "VALID: true\nSEARCH QUERIES:\nQUERY: none\nQUERY: N/A\nQUERY: Acme branch\nEND SEARCH QUERIES\n"
        result = _parse_custom(raw)
        assert result["search_queries"] == ["Acme branch"]

    def test_query_ref_attaches_to_the_preceding_anomaly(self):
        """Without this, corroboration is not computable.

        The scoring stage must know which search a finding came from, or it
        cannot tell "confirms something already counted" from "reveals
        something new" — and the double-count returns silently.
        """
        raw = (
            "VALID: true\n"
            "ANOMALY: Asks applicants to pay a fee | The post asks for a fee | high\n"
            "QUERY_REF: Acme processing fee Philippines\n"
            "ANOMALY: Generic job title | Title says 'worker' | low\n"
        )
        result = _parse_custom(raw)
        first, second = result["anomalies"]
        assert first["query_ref"] == "Acme processing fee Philippines"
        assert second["query_ref"] == ""

    def test_query_ref_after_the_last_anomaly_does_not_crash(self):
        raw = "VALID: true\nANOMALY: A fee | r | high\nQUERY_REF: orphan query\n"
        result = _parse_custom(raw)
        assert result["anomalies"][0]["query_ref"] == "orphan query"

    def test_the_cap_is_three_queries(self):
        raw = (
            "VALID: true\nSEARCH QUERIES:\n"
            "QUERY: one Philippines\nQUERY: two Philippines\n"
            "QUERY: three Philippines\nQUERY: four Philippines\n"
            "QUERY: five Philippines\nEND SEARCH QUERIES\n"
        )
        result = _parse_custom(raw)
        assert len(result["search_queries"]) == 3
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_anomaly_parsing.py -q`

Expected: FAIL — `KeyError: 'attributes'` and `KeyError: 'search_queries'`.

- [ ] **Step 3: Extend `_SECTION_RE`**

In `backend/app/services/lm_client.py`, replace `_SECTION_RE` and its comment:

```python
_SECTION_RE = re.compile(
    r"^\s*(?P<kw>VALID|ANOMALY|ANOMALIES|RED\s*FLAG|ATTRIBUTES|END\s*ATTRIBUTES|COMPANY|LOCATION|CONTACT\s*METHOD|MEETING\s*SPOT|PAY|QUERY_REF|SEARCH\s*QUERIES|END\s*SEARCH\s*QUERIES|COMPANY\s*NAME|EMPLOYER\s*NAME|POSTING\s*ANALYSIS|JOB\s*SUMMARY|END\s*(?:FLAGS|ANOMALIES|JOB\s*SUMMARY|POSTING\s*ANALYSIS))\s*:?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)

# Sections whose body runs until their END marker. END ATTRIBUTES and
# END SEARCH QUERIES are deliberately NOT in this set: they are bare terminators,
# and treating a terminator as a section end resets the parser's matched_any flag,
# which makes a valid scan parse as nothing at all.
_SECTION_END_KW = ("END JOB SUMMARY", "END POSTING ANALYSIS")

# Attributes whose presence the search can actually check against a public
# record. PAY and ROLE are absent deliberately: a salary figure or a job title is
# not corroborated or refuted by a web search, so querying one spends a credit
# and learns nothing.
CHECKABLE_ATTRIBUTES = ("LOCATION", "CONTACT_METHOD", "MEETING_SPOT")

# A placeholder the model emits to mean "nothing found". A surviving placeholder
# becomes a query, and a query for "none" is a credit spent to learn nothing.
_QUERY_PLACEHOLDERS = {"none", "n/a", "na", "nothing", "none found", "no query", "-"}

MAX_SEARCH_QUERIES = 3
```

- [ ] **Step 4: Extend `_parse_custom`**

In `backend/app/services/lm_client.py`, add these state variables after `flags: list[dict] = []` in `_parse_custom`:

```python
    attributes: dict[str, str] = {}
    search_queries: list[str] = []
    in_queries = False
    last_anomaly: dict | None = None
```

Replace the `END JOB SUMMARY`-handling block so the new terminators are skipped without resetting the parser — locate `if kw in _SECTION_END_KW:` and replace that whole `for line in raw.splitlines():` body with:

```python
    for line in raw.splitlines():
        m = _SECTION_RE.match(line)
        if not m:
            if section:
                buf.append(line)
            continue
        kw = " ".join(m.group("kw").split()).upper()
        rest = m.group("rest").strip()

        if kw == "END ATTRIBUTES":
            in_queries = False
            close_section()
            continue
        if kw == "END SEARCH QUERIES":
            in_queries = False
            close_section()
            continue
        if kw in _SECTION_END_KW:
            close_section()
            continue

        close_section()
        matched_any = True

        if kw == "VALID":
            val = rest.lower()
            result["valid"] = val in ("true", "yes", "1", "legitimate", "valid")
        elif kw in ("ANOMALY", "ANOMALIES", "RED FLAG"):
            parts = [p.strip() for p in re.split(r"\s*\|\s*", rest) if p.strip()]
            if not parts:
                continue
            flag_title = parts[0]
            flag_lower = flag_title.lower()
            # Placeholders the model emits to mean "nothing found". Both the
            # anomaly and the legacy red-flag spellings are listed because a
            # model asked for one may answer with either, and a placeholder that
            # survives becomes a finding about nothing.
            if flag_lower in {
                "none", "no red flags", "no red flags detected", "n/a", "na",
                "no significant red flags", "none detected", "no flags", "no flags detected",
                "no anomalies", "no anomalies detected", "no significant anomalies",
                "no anomaly", "legitimate", "no issues found", "nil",
            } or (
                flag_lower.startswith("no red flag")
                or flag_lower.startswith("no significant")
                or flag_lower.startswith("no anomal")
            ):
                continue

            reasoning = parts[1] if len(parts) >= 3 else ""
            severity = parts[2] if len(parts) >= 3 else ""
            if len(parts) == 2:
                if parts[1].lower() in _SEVERITIES:
                    severity = parts[1]
                else:
                    reasoning = parts[1]
            if severity:
                final_severity = _normalize_severity(severity)
            else:
                final_severity = _infer_severity(flag_title, reasoning)
            last_anomaly = {
                "flag": flag_title,
                "reasoning": reasoning,
                "severity": final_severity,
                "query_ref": "",
            }
            flags.append(last_anomaly)
        elif kw == "QUERY_REF":
            # Which search this finding relates to. Optional: an anomaly judged
            # not worth a query has none, and therefore no corroboration path —
            # which is correct, since a low-severity note is never corroborated.
            if last_anomaly is not None:
                last_anomaly["query_ref"] = rest
        elif kw == "SEARCH QUERIES":
            in_queries = True
            if rest.lower() not in _QUERY_PLACEHOLDERS:
                search_queries.append(rest)
        elif kw == "QUERY":
            if in_queries and rest and rest.lower() not in _QUERY_PLACEHOLDERS:
                if len(search_queries) < MAX_SEARCH_QUERIES:
                    search_queries.append(rest)
        elif kw in ("COMPANY", "LOCATION", "CONTACT_METHOD", "MEETING_SPOT", "PAY"):
            # A detail the posting did not state is omitted entirely rather than
            # stored empty. An empty LOCATION would read as "the posting stated
            # no location", which is a different claim, and would generate a
            # query that cannot succeed.
            if rest and rest.lower() != "not stated":
                attributes[kw] = rest
        elif kw in ("COMPANY NAME", "EMPLOYER NAME"):
            # The employer name is what the verification step searches on, so the
            # model states it directly instead of leaving a downstream regex to
            # fish it out of the prose summary. EMPLOYER NAME is the current
            # label; COMPANY NAME is still accepted so scans recorded before the
            # rename still parse.
            result["company_name"] = rest.strip()
        elif kw == "POSTING ANALYSIS":
            # Assessment of the posting's structure, kept separate from the job
            # summary so the panel can show the verdict and the role separately.
            section = kw.lower().replace(" ", "_")
            if rest:
                buf.append(rest)
        elif kw == "JOB SUMMARY":
            section = kw.lower().replace(" ", "_")
            if rest:
                buf.append(rest)
        else:
            matched_any = False
    close_section()
    result["anomalies"] = flags
    result["attributes"] = attributes
    result["search_queries"] = search_queries[:MAX_SEARCH_QUERIES]
    return result if matched_any or flags else None
```

- [ ] **Step 5: Add the schema fields**

In `backend/app/models/schemas.py`, add `query_ref` to `Anomaly` and the two fields to `ScanResponse`:

```python
class Anomaly(BaseModel):
    """One thing about a posting that differs from the ordinary case."""

    flag: str
    reasoning: str
    severity: str
    # The search this finding relates to, when one was issued for it. Carried so
    # the scoring stage can tell "confirms something already counted" from
    # "reveals something new" — without it the double-count returns silently.
    query_ref: str = ""


class ScanResponse(BaseModel):
    valid: bool
    anomalies: list[Anomaly] = []
    # What the posting states about itself, in its own words. Only present keys
    # were stated; an absent key means the posting said nothing, which is a
    # different claim from stating nothing and is never scored.
    attributes: dict[str, str] = {}
    # Up to three queries built from those attributes. Empty when the posting
    # stated nothing checkable.
    search_queries: list[str] = []
    job_summary: str = ""
    posting_analysis: str = ""
    error: str | None = None
    company_name: str | None = None
    sec_registration: list[dict] = []
    external_verification: dict = {}
    risk_score: int = 0
    risk_level: str = "low"
    score_breakdown: dict = {}
```

- [ ] **Step 6: Wire them through `_anomalies` and `_build_scan_response`**

In `backend/app/services/scanner/scan_result.py`, replace `_anomalies`:

```python
def _anomalies(flags: list) -> list[Anomaly]:
    out: list[Anomaly] = []
    if not isinstance(flags, list):
        return out
    for f in flags:
        if isinstance(f, str):
            f = {"flag": f}
        if not isinstance(f, dict):
            continue
        name = str(f.get("flag") or "").strip()
        if not name:
            continue
        reasoning = str(f.get("reasoning") or "").strip()
        severity = str(f.get("severity") or "").strip().lower()
        out.append(Anomaly(
            flag=name,
            reasoning=reasoning,
            severity=severity or "mid",
            query_ref=str(f.get("query_ref") or "").strip(),
        ))
    return out
```

And in `_build_scan_response`, add the two arguments:

```python
    return ScanResponse(
        valid=result.get("valid", False),
        anomalies=flags,
        attributes=result.get("attributes", {}),
        search_queries=result.get("search_queries", []),
        job_summary=result.get("job_summary", ""),
        posting_analysis=result.get("posting_analysis", ""),
        company_name=company_name if company_name_validator(company_name) else None,
        error=result.get("error"),
        risk_score=score,
        risk_level=level,
        score_breakdown=breakdown,
    )
```

- [ ] **Step 7: Update both prompt copies**

In `backend/SYSTEM_PROMPT.md`, replace the Output Format block:

```
VALID: <true or false>
ANOMALY: <label> | <reasoning> | <severity>
END ANOMALIES
ATTRIBUTES:
COMPANY: <exact employer name, or omit>
LOCATION: <city or region the post names, or omit>
CONTACT_METHOD: <channel it directs applicants to, or omit>
MEETING_SPOT: <named place, or omit>
PAY: <amount and period as stated, or omit>
END ATTRIBUTES
SEARCH QUERIES:
QUERY: <one search line, repeatable, at most three>
END SEARCH QUERIES
EMPLOYER NAME: <exact employer name, or "Not stated">
POSTING ANALYSIS:
<2-3 neutral, factual sentences analyzing the offer based on anomalies found, ending with a recommended action.>
END POSTING ANALYSIS
JOB SUMMARY:
<2-3 factual sentences describing what is being offered, required duties, pay, and contact info.>
END JOB SUMMARY
```

Add a new numbered section after section 2 in the same file:

```
6. ATTRIBUTES AND SEARCH QUERIES
- Report only details the posting actually states. If it names no location, omit the LOCATION line entirely rather than writing "none" or "Not stated".
- PAY and CONTACT_METHOD may be reported but generate no search query. Only LOCATION, CONTACT_METHOD and MEETING_SPOT are checkable online.
- Write at most three QUERY lines, and only for details the posting states. A posting with no location produces no location query.
- Build queries from the words the posting uses. "Tanika Maingate Terminal recruitment" is right; "Tanika scam recruitment" is not — never name a conclusion in a query.
- Put a QUERY_REF line after an ANOMALY line when you issued a query for it. Omit QUERY_REF for a low-severity anomaly; it will never be corroborated.
```

In `backend/app/services/scanner/prompts.py`, mirror the same block into `SCAN_FORMAT_BLOCK` and append the same rules to `SCAN_FIELD_RULES` as a new `- ATTRIBUTES AND SEARCH QUERIES:` group. The file copy and `SYSTEM_PROMPT.md` must agree — `test_verify_prompt_file.py` asserts the two do.

- [ ] **Step 8: Run the tests**

Run: `python -m pytest tests/test_anomaly_parsing.py tests/test_offline_suite.py tests/test_scanner_package.py -q`

Expected: PASS.

- [ ] **Step 9: Mutation-check both directions**

Break `MAX_SEARCH_QUERIES` to `0` and confirm `test_the_cap_is_three_queries` fails. Restore. Then break the `last_anomaly is not None` guard so every `QUERY_REF` attaches to the first anomaly, and confirm `test_query_ref_attaches_to_the_preceding_anomaly` fails. Restore. Then invert the missing-attribute check to store empty strings, and confirm `test_a_missing_attribute_is_not_emitted` fails. Restore.

Report each mutation and its result; do not claim the tests pass without running them.

- [ ] **Step 10: Commit**

```bash
git add backend/SYSTEM_PROMPT.md backend/app/models/schemas.py \
  backend/app/services/lm_client.py backend/app/services/scanner/prompts.py \
  backend/app/services/scanner/scan_result.py backend/tests/test_anomaly_parsing.py
git commit -m "feat(scan): report posting attributes and search queries"
```

---

### Task 2: Dynamic scheme queries from checkable attributes

**Files:**
- Modify: `backend/app/services/search.py` (add `build_scheme_queries` after `build_queries`)
- Test: `backend/tests/test_multi_query.py`

**Interfaces:**
- Consumes: `result["search_queries"]` and `result["attributes"]` from Task 1.
- Produces: `build_scheme_queries(attributes: dict, company: str) -> list[str]`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_multi_query.py`:

```python
class TestSchemeQueries:
    """Queries come from what the posting states, never from its labels.

    A model's `high` label is a characterisation; using it as a query term puts
    the accusation inside the query, and a query carrying a conclusion makes its
    own results look like corroboration. Only checkable attributes qualify, and
    only when the posting actually stated them.
    """

    def test_no_attributes_means_no_queries(self):
        assert build_scheme_queries({}, "Acme") == []

    def test_a_location_the_posting_stated_produces_a_query(self):
        queries = build_scheme_queries(
            {"LOCATION": "Maingate Terminal"}, "Tanika"
        )
        assert queries == ["Tanika Maingate Terminal recruitment"]

    def test_pay_and_role_are_never_queried(self):
        # A salary figure is not corroborated or refuted by a web search, so a
        # query for one spends a credit and learns nothing.
        queries = build_scheme_queries(
            {"PAY": "26,000 monthly", "ROLE": "crew"}, "Tanika"
        )
        assert queries == []

    def test_a_missing_location_produces_nothing(self):
        # The case a naive "one query per attribute" implementation gets wrong:
        # it spends a credit searching for something the posting never said.
        queries = build_scheme_queries({"CONTACT_METHOD": "personal Gmail"}, "Tanika")
        assert all("location" not in q.lower() for q in queries)

    def test_a_placeholder_attribute_is_not_queried(self):
        queries = build_scheme_queries(
            {"LOCATION": "Not stated"}, "Tanika"
        )
        assert queries == []

    def test_the_cap_is_three(self):
        queries = build_scheme_queries(
            {
                "LOCATION": "Pampanga",
                "CONTACT_METHOD": "personal Gmail",
                "MEETING_SPOT": "Waltermart Mabalacat",
            },
            "Tanika",
        )
        assert len(queries) <= 3

    def test_the_company_name_is_used_verbatim(self):
        # No suffix strip: a filing and a store locator are titled with the legal
        # name, and stripping it searches a different company than the one named.
        queries = build_scheme_queries({"LOCATION": "Quezon City"}, "Jollibee Foods Corporation")
        assert "Jollibee Foods Corporation" in queries[0]

    def test_no_query_carries_a_conclusion(self):
        banned = ("scam", "fraud", "fake", "illegal", "criminal")
        queries = build_scheme_queries(
            {"LOCATION": "Pampanga", "MEETING_SPOT": "bus terminal"},
            "Tanika",
        )
        for q in queries:
            for word in banned:
                assert word not in q.lower()
```

Add the import at the top of the file:

```python
from app.services.search import build_queries, build_scheme_queries
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_multi_query.py -q -k SchemeQueries`

Expected: FAIL — `ImportError: cannot import name 'build_scheme_queries'`.

- [ ] **Step 3: Implement**

Add after `build_queries` in `backend/app/services/search.py`:

```python
# Attributes whose presence a web search can actually check. PAY and ROLE are
# absent deliberately: a salary figure and a job title are not corroborated or
# refuted by a search, so querying one spends a credit and learns nothing.
CHECKABLE_ATTRIBUTES = ("LOCATION", "CONTACT_METHOD", "MEETING_SPOT")

_PLACEHOLDER_VALUES = {"", "none", "n/a", "na", "not stated", "not mentioned", "unknown", "-"}


def build_scheme_queries(attributes: dict, company: str) -> list[str]:
    """Queries built from what the posting states about itself.

    The employer queries in `build_queries` can only find pages that name the
    employer, so they find nothing when a scam impersonates a real company: a
    page posting "Now Hiring at Jollibee" is invisible to a search for Jollibee's
    reputation, because Jollibee's reputation is clean. These queries target the
    posting's own claims instead, which are searchable whether or not the
    employer is.

    Three rules make this safe rather than an accusation generator:

      * **Only stated details.** A posting that names no location produces no
        location query. A missing input is a missing input — it does not earn a
        credit, and a search for something the posting never mentioned cannot
        succeed.
      * **Only checkable attributes.** See `CHECKABLE_ATTRIBUTES`.
      * **No conclusions in the query.** The terms are the poster's words. A
        query naming `scam` or `fraud` returns pages that appear to corroborate
        the accusation it already embedded, which is the same failure that made
        these queries static in the first place.

    Capped at 3: credits are the scarce resource and they should buy recall,
    not verbosity. A detailed posting must not cost more to check than a sparse
    one.
    """
    name = (company or "").strip()
    if not name:
        return []

    queries: list[str] = []
    for attribute in CHECKABLE_ATTRIBUTES:
        if len(queries) >= 3:
            break
        value = str(attributes.get(attribute) or "").strip()
        if not value or value.lower() in _PLACEHOLDER_VALUES:
            continue
        detail = _squeeze(value)
        if not detail:
            continue
        query = _with_country(f"{name} {detail}")
        # Dedupe: two attributes often state the same place ("Waltermart Mabalacat"
        # as both LOCATION and MEETING_SPOT), and the same query twice buys
        # nothing.
        if query not in queries:
            queries.append(query)
    return queries[:3]


def _squeeze(value: str) -> str:
    """Reduce an attribute value to the searchable part of it.

    Strips the sentence the poster wrote around the detail. A LOCATION of
    "our Robinsons Starmills branch in Cabatuan" becomes "Robinsons Starmills
    branch Cabatuan" — the connector words are the poster's prose and dilute
    the query without adding a term the search index will use.
    """
    text = re.sub(r"[,;]", " ", value)
    text = re.sub(r"\b(our|the|a|an|nearest|located at|based in)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    # "branch" and "location" describe the posting, not the place. Keeping them
    # crowds the query toward generic pages about branches in general.
    text = re.sub(r"\b(branch|location|office|address|site|meet(?:ing)? (?:point|spot|place)?)\b",
                  " ", text, flags=re.IGNORECASE)
    return text.strip(" .-")
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_multi_query.py -q`

Expected: PASS.

- [ ] **Step 5: Mutation-check**

Set `CHECKABLE_ATTRIBUTES` to include `"PAY"` and confirm `test_pay_and_role_are_never_queried` fails. Restore. Then remove the `value.lower() in _PLACEHOLDER_VALUES` guard and confirm `test_a_placeholder_attribute_is_not_queried` fails. Restore.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/search.py backend/tests/test_multi_query.py
git commit -m "feat(search): build scheme queries from checkable attributes"
```

---

### Task 3: Verification prompt and schema — confirmed / refuted / unverified

**Files:**
- Modify: `backend/VERIFY_PROMPT.md`
- Modify: `backend/app/services/scanner/verification_prompt.py` (`VERIFY_RESPONSE_SCHEMA`, `_FALLBACK_VERIFY_PROMPT`)
- Test: `backend/tests/test_verify_prompt_file.py` is already failing on `HEAD` — **do not** count it. Create `backend/tests/test_claim_prompt.py`.

**Interfaces:**
- Consumes: nothing.
- Produces: `VERIFY_CLAIM_CATEGORIES: tuple[str, ...]`, and `VERIFY_RESPONSE_SCHEMA["properties"]["checks"]["items"]["properties"]["category"]["enum"]` extended to the six claim categories.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_claim_prompt.py`:

```python
"""`red` must mean a source contradicts a claim, not that nothing was found.

This is the rule that keeps small Philippine employers from being scored as
suspicious. A sole proprietorship with no website, no listing and no reviews is
the ordinary case, and it is the population this product exists for. If silence
scored, the most common real employer would be the most penalised one.

The two states are distinguished in the prompt prose the backend actually loads,
so this reads `VERIFY_PROMPT.md` and the in-module fallback rather than a
constant.
"""

from pathlib import Path

import pytest

from app.services.scanner.verification_prompt import (
    VERIFY_CLAIM_CATEGORIES,
    VERIFY_SYSTEM_PROMPT,
    _FALLBACK_VERIFY_PROMPT,
)

PROMPT = Path(__file__).resolve().parents[1] / "VERIFY_PROMPT.md"


@pytest.fixture(params=["file", "fallback"], ids=["VERIFY_PROMPT.md", "fallback"])
def prompt(request):
    if request.param == "file":
        return PROMPT.read_text(encoding="utf-8").lower()
    return _FALLBACK_VERIFY_PROMPT.lower()


def test_red_requires_a_contradiction(prompt):
    assert "contradict" in prompt, (
        "red must be defined as a source contradicting a claim — otherwise "
        "'nothing found' and 'contradicted' are the same state"
    )


def test_silence_is_not_red(prompt):
    assert any(
        phrase in prompt
        for phrase in (
            "never red",
            "not red",
            "yellow, not red",
            "nothing found is yellow",
        )
    ), "the prompt must state explicitly that an unconfirmed claim is yellow"


def test_green_confirms_and_adds_nothing(prompt):
    assert any(
        phrase in prompt
        for phrase in ("confirm", "supports the claim", "backs up")
    ), "green must mean a retrieved source supports the claim"


def test_no_verdict_words_in_the_output_rules(prompt):
    for word in ("legitimate", "fraudulent", "genuine"):
        assert f"never use {word}" in prompt or f"do not use {word}" in prompt or \
            f"never write {word}" in prompt, (
            f"the output rules must still ban {word} — this is the libel guardrail"
        )


def test_finding_must_not_name_a_status(prompt):
    for word in ("verified", "safe", "authorized"):
        assert word in prompt, (
            f"the prompt must forbid {word} in a finding — a status adjective is "
            "a conclusion, and the reader draws conclusions from a source they can open"
        )


def test_every_claim_category_is_documented():
    assert "channel" in VERIFY_CLAIM_CATEGORIES[0].lower() or any(
        "channel" in c.lower() for c in VERIFY_CLAIM_CATEGORIES
    ), "the impersonation check must be a category or it cannot be scored"
    assert any("location" in c.lower() or "branch" in c.lower()
               for c in VERIFY_CLAIM_CATEGORIES)


def test_scheme_corroboration_requires_the_same_scheme():
    body = (PROMPT.read_text(encoding="utf-8") + _FALLBACK_VERIFY_PROMPT).lower()
    assert "same scheme" in body or "this specific scheme" in body, (
        "a page about task-for-earning schemes generally establishes nothing "
        "about this posting and must not redden a category"
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_claim_prompt.py -q`

Expected: FAIL — `ImportError: cannot import name 'VERIFY_CLAIM_CATEGORIES'`.

- [ ] **Step 3: Add the category tuple and extend the schema**

In `backend/app/services/scanner/verification_prompt.py`, immediately after `PROMPT_PATH`, add:

```python
# The claims a posting makes that a web search can test. Each is a question about
# the relationship between one claim and the retrieved evidence, not a general
# question about the employer.
#
# `Location / Branch` and `Channel Match` test the posting's own claims rather
# than the employer's existence. Channel Match is the only check that can detect
# impersonation: a real employer passes every existence, registration and branch
# check, so those checks structurally cannot distinguish a real company from a
# scammer borrowing its name.
VERIFY_CLAIM_CATEGORIES = (
    "Company Existence",
    "Official Registration",
    "Location / Branch",
    "Channel Match",
    "Reputation",
    "Scheme Corroboration",
)
```

Replace the `checks` items `category` enum in `VERIFY_RESPONSE_SCHEMA`:

```python
                    "category": {
                        "type": "string",
                        "enum": list(VERIFY_CLAIM_CATEGORIES),
                    },
```

- [ ] **Step 4: Rewrite the status rules in both prompt copies**

In `backend/VERIFY_PROMPT.md`, replace the STATUS RULES block with:

```
STATUS RULES for each check. A check tests one claim this posting made:
- green: a retrieved result CONFIRMS the claim. The result must be about the same company, and for Scheme Corroboration the same scheme. Confirmed adds nothing to the score — it means the claim is supported, not that the posting is safe.
- yellow: the results neither confirm nor contradict the claim. THIS IS THE DEFAULT. When you did not find something, use yellow.
- red: a retrieved result CONTRADICTS the claim. Name the contradicting result in the finding and give its source. Examples of a contradiction: a source locates the company's branches and the posting's location is not among them; a source shows the company's own domain and the posting directs applicants to an unrelated one; a source describes this specific scheme as fraudulent.

Never red because nothing was found. A claim nobody could confirm is yellow, not red. "We found no registration" is yellow. "A source states this company is not registered anywhere" is red.

A result must concern the same entity as the company being verified, and for Scheme Corroboration the same scheme. A page describing task-for-earning schemes in general establishes nothing about this posting — that is yellow, not red.
```

Mirror the same text into `_FALLBACK_VERIFY_PROMPT` in `verification_prompt.py`, and extend its category list from three categories to the six.

- [ ] **Step 5: Extend the FIELD RULES in both copies**

Add to each:

```
- finding: the one specific fact that decided the status, in one plain sentence, naming what the source states. Never write "verified", "safe", "authorized", or "legitimate" — a status adjective is a conclusion, and the reader draws conclusions from a source they can open. "Robinsons Starmills lists this address on its store locator" is a fact. "The branch is verified" is not.
- When the status is green or red, source_title and source_url must be copied exactly from the results. Never construct or guess a URL.
```

- [ ] **Step 6: Run to verify it passes**

Run: `python -m pytest tests/test_claim_prompt.py tests/test_verify.py -q`

Expected: PASS. `test_verify.py` will need its category fixtures updated — it asserts on the old three categories.

- [ ] **Step 7: Mutation-check**

Remove the word "contradict" from the file copy and confirm `test_red_requires_a_contradiction` fails for the `file` param only. Restore.

- [ ] **Step 8: Commit**

```bash
git add backend/VERIFY_PROMPT.md \
  backend/app/services/scanner/verification_prompt.py \
  backend/tests/test_claim_prompt.py backend/tests/test_verify.py
git commit -m "feat(verify): define red as a source contradicting a claim"
```

---

### Task 4: Text fallback for the new shape, and a loud parse failure

This is the hole that fails **silently**. A provider that drops `response_format` answers in prose, the parser returns nothing, the request has already succeeded, and the panel shows empty cards with no error.

**Files:**
- Modify: `backend/app/services/scanner/verification_parser.py`
- Modify: `backend/app/services/scanner/verification_flow.py:15-62` (`_read_verify_output`), `:200-212` (failsafe)
- Test: `backend/tests/test_verify_fallback.py` (new)

**Interfaces:**
- Consumes: `VERIFY_CLAIM_CATEGORIES` from Task 3.
- Produces: `_parse_verification_result(text) -> list[VerificationItem]` extended for `FINDING:`/`SOURCE:`; `_parse_verify_section(text, name)` gains `"FINDING"`; new `VerificationParseError` raised by `_read_verify_output` when both parsers fail on non-empty text.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_verify_fallback.py`:

```python
"""The schema-less path must parse, or fail loudly.

A provider that drops `response_format` answers in prose and the request still
succeeds. If the text parser returns nothing quietly, the panel renders empty
cards with no error anywhere — the failure mode this whole file exists to stop.

The distinction that matters: "parsed the response and it contained no checks"
is a legitimate empty result; "could not read this response at all" is a
failure worth reporting. Only the second raises.
"""

import pytest

from app.services.scanner.verification_parser import (
    VerificationParseError,
    _parse_verification_result,
    _parse_verify_section,
)

BLOCK = (
    "VERIFY: Company Existence\n"
    "STATUS: green\n"
    "DETAIL: Acme lists this address on its own site.\n"
    "SOURCE: Acme Contact | https://acme.example/contact\n"
    "END VERIFY\n"
    "VERIFY: Channel Match\n"
    "STATUS: red\n"
    "DETAIL: Acme's own domain is acme.example; the post directs applicants to a Gmail address.\n"
    "SOURCE: Acme Contact | https://acme.example/contact\n"
    "END VERIFY\n"
)


def test_the_documented_block_shape_parses():
    items = _parse_verification_result(BLOCK)
    assert [i.label for i in items] == ["Company Existence", "Channel Match"]
    assert items[0].status == "green"
    assert items[1].status == "red"


def test_finding_is_accepted_as_well_as_detail():
    """The new shape names the field FINDING; the old one named it DETAIL.

    A parser that only knows DETAIL returns an item with an empty explanation,
    which renders as a card with a status and no explanation — looking like a
    finding that says nothing.
    """
    text = "VERIFY: Reputation\nSTATUS: yellow\nFINDING: No adverse record in the results.\nEND VERIFY\n"
    items = _parse_verification_result(text)
    assert items[0].explanation == "No adverse record in the results."


def test_source_is_captured():
    text = (
        "VERIFY: Reputation\nSTATUS: red\nDETAIL: A DMW advisory names this scheme.\n"
        "SOURCE: DMW Advisory | https://dmw.gov.ph/advisory\nEND VERIFY\n"
    )
    items = _parse_verification_result(text)
    assert items[0].source_title == "DMW Advisory"
    assert items[0].source_url == "https://dmw.gov.ph/advisory"


def test_a_missing_end_marker_does_not_swallow_the_next_block():
    """The bug this parser was rewritten for.

    One combined regex loses a whole category whenever the model deviates
    slightly. A missing END VERIFY made the next match span two blocks.
    """
    text = (
        "VERIFY: Company Existence\nSTATUS: green\nDETAIL: Has a site.\n"
        "VERIFY: Reputation\nSTATUS: red\nDETAIL: A complaint was published.\n"
    )
    labels = [i.label for i in _parse_verification_result(text)]
    assert "Company Existence" in labels
    assert "Reputation" in labels


def test_unparseable_prose_raises_rather_than_returning_empty():
    # The silent failure. Without this raise the panel shows nothing and
    # nothing in the log says why.
    with pytest.raises(VerificationParseError):
        _parse_verification_result("The company appears to be legitimate based on my analysis.")


def test_empty_text_raises_too():
    with pytest.raises(VerificationParseError):
        _parse_verification_result("")


def test_a_response_with_no_checks_is_not_an_error():
    """A well-formed response that simply reported nothing parses to empty.

    That is a legitimate result — the verification flow renders its own notice
    — and must not be confused with an unreadable one.
    """
    assert _parse_verification_result("REPORT: Nothing found.\nEND REPORT\n") == []


def test_report_and_recommendation_still_parse():
    text = BLOCK + "REPORT: Two checks found something.\nEND REPORT\n"
    assert _parse_verify_section(text, "REPORT") == "Two checks found something."
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_verify_fallback.py -q`

Expected: FAIL — `ImportError: cannot import name 'VerificationParseError'`.

- [ ] **Step 3: Extend the parser**

In `backend/app/services/scanner/verification_parser.py`, replace the regex block and add the exception:

```python
_BLOCK_SPLIT_RE = re.compile(r"^\s*VERIFY\s*:", re.IGNORECASE | re.MULTILINE)
_STATUS_RE = re.compile(r"\bSTATUS\s*:\s*\**\s*(green|yellow|red)\b", re.IGNORECASE)
# FINDING is the new field name; DETAIL is the legacy one. Both are accepted so a
# provider that answers in prose either way still yields an explanation — a card
# with a status and no explanation reads as a finding that says nothing.
_DETAIL_RE = re.compile(
    r"\b(?:DETAIL|FINDING)\s*:\s*(.*?)(?=\s*SOURCE\s*:|\s*END\s*VERIFY|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_SOURCE_RE = re.compile(
    r"\bSOURCE\s*:\s*(.*?)\|\s*(https?://\S+)(?=\s*END\s*VERIFY|\Z)",
    re.IGNORECASE | re.DOTALL,
)
# The label runs from just after VERIFY: up to whichever field comes first.
_LABEL_END_RE = re.compile(
    r"\b(?:STATUS|DETAIL|FINDING|SOURCE)\s*:|\bEND\s*VERIFY", re.IGNORECASE
)


class VerificationParseError(RuntimeError):
    """The response could not be read at all.

    Distinct from a well-formed response that reported no checks. The first is a
    failure worth reporting; the second is a legitimate empty result that the
    verification flow renders with its own notice.
    """
```

Replace `_parse_verification_result` with:

```python
def _parse_verification_result(text: str) -> list[VerificationItem]:
    """Parse the labeled verification output into structured items.

    Raises `VerificationParseError` when the text contains no VERIFY block at
    all. Returning an empty list for unparseable text is what let a failed
    verification render as a panel with nothing on it and no error.
    """
    if not text or not text.strip():
        raise VerificationParseError("empty response")

    items: list[VerificationItem] = []
    for block in _blocks(text):
        body = block.split(":", 1)[1] if ":" in block else block

        end_match = re.search(
            r"\bSTATUS\s*:|\bDETAIL\s*:|\bFINDING\s*:", body, re.IGNORECASE
        )
        label_source = body[: end_match.start()] if end_match else body
        label_end = _LABEL_END_RE.search(label_source)
        if label_end:
            label_source = label_source[: label_end.start()]
        label = " ".join(label_source.split()).strip(" -*\t")
        if not label:
            continue

        status_match = _STATUS_RE.search(block)
        if not status_match:
            continue

        detail_match = _DETAIL_RE.search(block)
        explanation = " ".join(detail_match.group(1).split()).strip() if detail_match else ""

        source_title = ""
        source_url = ""
        source_match = _SOURCE_RE.search(block)
        if source_match:
            source_title = " ".join(source_match.group(1).split()).strip()
            source_url = source_match.group(2).strip()

        items.append(VerificationItem(
            label=label,
            status=status_match.group(1).strip().lower(),
            explanation=explanation,
            source_title=source_title,
            source_url=source_url,
        ))

    if not _blocks(text):
        raise VerificationParseError("no VERIFY block in the response")
    return items
```

- [ ] **Step 4: Make `_read_verify_output` loud**

In `backend/app/services/scanner/verification_flow.py`, change the import and replace the tail of `_read_verify_output`:

```python
from .verification_parser import (
    EXPECTED_CATEGORIES,
    VerificationParseError,
)
```

and replace the final three lines of the function with:

```python
    log.warning("[verify] Response was not JSON; falling back to the labeled-text parser.")
    try:
        items = runtime.get_parse_verification_result()(text)
    except VerificationParseError as exc:
        # The request succeeded and the response could not be read. Returning an
        # empty list here would render three empty cards with no error anywhere,
        # so the failure is reported instead.
        log.error("[verify] Response was neither JSON nor readable labeled text: %s. raw=%s",
                  exc, text[:400])
        raise VerificationParseError(str(exc)) from exc
    report = runtime.get_parse_verify_section()(text, "REPORT")
    recommendation = runtime.get_parse_verify_section()(text, "RECOMMENDATION")
    return items, report, recommendation, False, []
```

- [ ] **Step 5: Make the flow surface it**

In `backend/app/services/scanner/verification_flow.py`, replace the `if not items:` failsafe block with:

```python
        if not items:
            # Either the parsers read a well-formed response that reported
            # nothing, or the response was unreadable. The second must reach the
            # reader rather than rendering as a panel with nothing on it.
            unreadable = isinstance(used_json, str) and "no VERIFY block" in used_json
            log.warning("[verify] Failsafe triggered (unreadable=%s). Raw: %s", unreadable, final_text[:300])
            items = [
                VerificationItem(
                    label="Company Existence",
                    status="yellow",
                    explanation=(
                        "The verification response could not be read, so nothing about this "
                        "employer was established."
                        if unreadable
                        else f"No structured findings could be read from the search results for '{company}'."
                    ),
                )
            ]
            if not report:
                report = (
                    "The verification response could not be read, so no risk score was "
                    "calculated from it."
                    if unreadable
                    else f"Structured findings could not be parsed from the search results for '{company}', so no risk score was calculated."
                )
            if not recommendation:
                recommendation = "Confirm the employer independently before submitting personal details."
```

Add `search_ok=False` is not needed here; the flow already reports `search_ok`.

- [ ] **Step 6: Run to verify it passes**

Run: `python -m pytest tests/test_verify_fallback.py tests/test_verify.py tests/test_verify_unschemaed.py -q`

Expected: PASS.

- [ ] **Step 7: Mutation-check**

Revert `_parse_verification_result` to return `[]` instead of raising, and confirm `test_unparseable_prose_raises_rather_than_returning_empty` and `test_empty_text_raises_too` both fail. Restore. Then remove `FINDING` from `_DETAIL_RE` and confirm `test_finding_is_accepted_as_well_as_detail` fails. Restore.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/scanner/verification_parser.py \
  backend/app/services/scanner/verification_flow.py \
  backend/tests/test_verify_fallback.py
git commit -m "fix(verify): parse the text fallback shape and fail loudly"
```

---

### Task 5: The flow runs scheme queries

**Files:**
- Modify: `backend/app/services/scanner/verification_flow.py:112-165` (query loop), `:234-260` (result event)
- Modify: `backend/app/services/scanner/dependencies.py` (add `get_build_scheme_queries`)
- Modify: `backend/app/services/scanner/__init__.py` (export it)
- Modify: `backend/app/routers/scan.py:93` (runtime wiring)
- Test: `backend/tests/test_verify.py`

**Interfaces:**
- Consumes: `build_scheme_queries(attributes, company)` from Task 2; `req.attributes` from `VerifyRequest`.
- Produces: `VerifyRequest.attributes: dict`; result event gains `scheme_queries: list[str]`.

- [ ] **Step 1: Add the schema field**

In `backend/app/models/schemas.py`:

```python
class VerifyRequest(BaseModel):
    company_name: str = ""
    job_summary: str = ""
    anomalies: list[Anomaly] = []
    # What the scan extracted about the posting. Only stated details are present.
    # Used to build scheme queries; an absent key produces no query, never a
    # query for something the posting never said.
    attributes: dict[str, str] = {}
```

- [ ] **Step 2: Write the failing tests**

Append to `backend/tests/test_verify.py`:

```python
class TestSchemeQueriesAreIssued:
    """Retrieval must target what the posting claims, not only the employer."""

    async def test_a_stated_location_produces_a_scheme_query(self, client):
        with patch(_search_ok), patch(_chat_corroboration()):
            resp = await client.post("/api/verify", json={
                "company_name": "Tanika",
                "attributes": {"LOCATION": "Maingate Terminal"},
            }, headers=HEADERS)

        assert resp.status_code == 200
        assert "Maingate Terminal" in resp.text
        assert '"scheme_queries": ["Tanika Maingate Terminal' in resp.text.replace("'", '"')

    async def test_no_attributes_issues_no_scheme_query(self, client):
        with patch(_search_ok), patch(_chat_corroboration()):
            resp = await client.post("/api/verify", json={
                "company_name": "Tanika",
            }, headers=HEADERS)

        assert '"scheme_queries": []' in resp.text.replace("'", '"')

    async def test_a_missing_location_spends_no_credit(self, client):
        """The case a naive implementation gets wrong: searching for what the
        posting never mentioned spends a credit and cannot succeed."""
        issued: list[str] = []
        with patch(_search_ok_recording(issued)), patch(_chat_corroboration()):
            await client.post("/api/verify", json={
                "company_name": "Tanika",
                "attributes": {"CONTACT_METHOD": "personal Gmail"},
            }, headers=HEADERS)

        assert not any("location" in q.lower() for q in issued)

    async def test_a_scheme_query_failure_is_partial_not_total(self, client):
        """One scheme query failing must not discard the others."""
        issued: list[str] = []

        def fail_on_scheme(query: str):
            return SearchOutcome(ok="Maingate" not in query, error="boom")

        with patch(_search_by_query(fail_on_scheme)), patch(_chat_corroboration()):
            resp = await client.post("/api/verify", json={
                "company_name": "Tanika",
                "attributes": {"LOCATION": "Maingate Terminal"},
            }, headers=HEADERS)

        assert resp.status_code == 200
        assert '"search_partial": true' in resp.text.replace("'", '"')
```

The helpers `patch`ed above follow the file's existing `_patch_search` pattern — read the top of `backend/tests/test_verify.py` and add `_search_ok`, `_chat_corroboration`, `_search_ok_recording`, and `_search_by_query` matching the conventions already used there.

- [ ] **Step 3: Run to verify it fails**

Run: `python -m pytest tests/test_verify.py -q -k SchemeQueries`

Expected: FAIL — no `scheme_queries` in the response.

- [ ] **Step 4: Wire the dependency**

In `backend/app/services/scanner/dependencies.py`, change the import:

```python
from app.services.search import build_queries, build_scheme_queries, clean_company_name, extract_company_name, is_valid_company_name, merge_results, search
```

and add beside `get_build_queries`:

```python
    get_build_scheme_queries = staticmethod(lambda: build_scheme_queries)
```

Export `build_scheme_queries` from `backend/app/services/scanner/__init__.py` and import it in `backend/app/routers/scan.py`, then add `runtime.get_build_scheme_queries = lambda: build_scheme_queries`.

- [ ] **Step 5: Run the scheme queries**

In `backend/app/services/scanner/verification_flow.py`, replace the query-building lines (currently `queries = runtime.get_build_queries()(company)`) with:

```python
        # Two query families. The company queries find what is published about
        # the employer; the scheme queries find what is published about the
        # posting's own claims, which is the only way to catch an impersonation
        # of a real company. Both merge into one flat result set for one model
        # call, so the cost is one AI call and up to five provider requests.
        company_queries = runtime.get_build_queries()(company)
        scheme_queries = runtime.get_build_scheme_queries()(
            getattr(req, "attributes", None) or {}, company
        )
        queries = company_queries + scheme_queries
```

Leave the existing loop, merge and `ok`/`partial` logic unchanged — it already handles a mixed list, which is the point of the design.

- [ ] **Step 6: Report the scheme queries**

In the result event, add after `"queries_issued"`:

```python
            "scheme_queries": scheme_queries,
```

- [ ] **Step 7: Run to verify it passes**

Run: `python -m pytest tests/test_verify.py tests/test_multi_query.py -q`

Expected: PASS.

- [ ] **Step 8: Mutation-check**

Make `build_scheme_queries` return `[(name + " location")]` unconditionally and confirm `test_no_attributes_issues_no_scheme_query` and `test_a_missing_location_spends_no_credit` both fail. Restore.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/schemas.py backend/app/services/scanner/verification_flow.py \
  backend/app/services/scanner/dependencies.py backend/app/services/scanner/__init__.py \
  backend/app/routers/scan.py backend/tests/test_verify.py
git commit -m "feat(verify): run scheme queries built from the posting's claims"
```

---

### Task 6: Refutation scoring with a floor

The scoring stage. Deterministic — the LLM never sees this.

**Files:**
- Modify: `backend/app/services/scanner/risk_calculator.py`
- Test: `backend/tests/test_risk_model.py`

**Interfaces:**
- Consumes: `VerificationItem` list with the six claim categories.
- Produces: `_refutation_score_from_verify(items) -> int | None`; `_combine_scores(posting_score, refutation_score)`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_risk_model.py`:

```python
class TestRefutationScoring:
    """Points require a source that contradicts a claim.

    The three-state model: confirmed adds nothing, a contradiction adds, and
    nothing learned adds nothing. Silence scoring points would penalise a sole
    proprietorship with no web presence — the ordinary case in the Philippines
    and the population this product exists for.
    """

    def test_a_confirmed_claim_adds_nothing(self):
        items = [VerificationItem(label="Company Existence", status="green", explanation="")]
        assert _refutation_score_from_verify(items) is None

    def test_an_unverified_claim_adds_nothing(self):
        items = [VerificationItem(label="Company Existence", status="yellow", explanation="")]
        assert _refutation_score_from_verify(items) is None

    def test_a_refuted_channel_adds_points(self):
        """Channel Match is the impersonation check and carries the most weight."""
        items = [VerificationItem(label="Channel Match", status="red", explanation="")]
        assert _refutation_score_from_verify(items) == REFUTATION_WEIGHTS["Channel Match"]

    def test_a_refuted_location_carries_less_than_a_channel(self):
        weights = REFUTATION_WEIGHTS
        assert weights["Channel Match"] > weights["Location / Branch"]

    def test_all_yellow_is_absent_not_zero(self):
        """(None, None) is not (0, 0). It tells the caller nothing was learned,
        which a zero score would report as a measurement of zero risk."""
        items = [
            VerificationItem(label="Company Existence", status="yellow", explanation=""),
            VerificationItem(label="Channel Match", status="yellow", explanation=""),
        ]
        assert _refutation_score_from_verify(items) is None

    def test_an_empty_list_is_absent(self):
        assert _refutation_score_from_verify([]) is None

    def test_the_stage_is_capped_at_fifty(self):
        items = [
            VerificationItem(label="Channel Match", status="red", explanation=""),
            VerificationItem(label="Location / Branch", status="red", explanation=""),
            VerificationItem(label="Reputation", status="red", explanation=""),
            VerificationItem(label="Scheme Corroboration", status="red", explanation=""),
            VerificationItem(label="Company Existence", status="red", explanation=""),
        ]
        score = _refutation_score_from_verify(items)
        assert score is not None and score <= MAX_REFUTATION_SCORE

    def test_a_legacy_category_label_still_scores(self):
        """Results stored before the rename used 'SEC Registration'. Without the
        mapping a stored verification silently rescores from 25 to the default."""
        items = [VerificationItem(label="SEC Registration", status="red", explanation="")]
        assert _refutation_score_from_verify(items) is not None


class TestCombineScoresHasAFloor:
    """A search result may add to the posting's score. It may never lower it.

    The 60/40 blend was deleted because averaging let corroborating evidence
    outvote the artifact the reader asked about, and because 'we found nothing'
    could pull a maxed posting down. A plain 50/50 mean would reintroduce both:
    three high-severity anomalies plus an unlookable employer would score 50,
    reporting the most dangerous input this product receives as moderate.
    """

    def test_evidence_can_raise(self):
        assert _combine_scores(20, 30) == (50, "moderate")

    def test_evidence_cannot_lower_a_maxed_posting(self):
        score, level = _combine_scores(100, 0)
        assert score == 100
        assert level == "critical"

    def test_a_clean_employer_cannot_lower_a_finding_posting(self):
        assert _combine_scores(40, 0) == (40, "moderate")

    def test_an_absent_stage_leaves_the_posting_alone(self):
        assert _combine_scores(40, None) == (40, "moderate")

    def test_a_posting_with_no_findings_scores_only_from_refutation(self):
        assert _combine_scores(0, 30) == (30, "low")

    def test_both_absent_is_absent(self):
        assert _combine_scores(None, None) == (None, None)
```

Update the imports at the top of the file:

```python
from app.services.scanner.risk_calculator import (
    MAX_REFUTATION_SCORE,
    POSTING_SEVERITY_WEIGHTS,
    REFUTATION_WEIGHTS,
    _combine_scores,
    _posting_risk_from_flags,
    _refutation_score_from_verify,
)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_risk_model.py -q`

Expected: FAIL — `ImportError: cannot import name 'MAX_REFUTATION_SCORE'`.

- [ ] **Step 3: Add the weights and the function**

In `backend/app/services/scanner/risk_calculator.py`, after `POSTING_SEVERITY_WEIGHTS`, add:

```python
# Evidence stage. A claim the retrieval CONTRADICTS costs points; a claim it
# confirms, and a claim it learned nothing about, both cost nothing.
#
# The weights are the one thing in this file not yet derived. `SCORING-SOURCES.md`
# §8 found the employer category weights nearly flat (40/25/35 is a 1.6x spread,
# barely distinguishable from equal importance on Saaty's scale), and these were
# chosen on the same judgement rather than by the pairwise method in
# `SCORING-SOURCES.md` §1. They MUST be re-derived before this ships to a panel,
# with the consistency ratio reported. The ordering is defensible now:
# Channel Match is the only check that can detect an impersonation, because a
# real employer passes every existence, registration and branch check.
REFUTATION_WEIGHTS = {
    "Channel Match": 25,
    "Scheme Corroboration": 15,
    "Reputation": 10,
    "Location / Branch": 8,
    "Company Existence": 6,
    "Official Registration": 6,
}

# The evidence stage may add up to half the scale. See `_combine_scores`.
MAX_REFUTATION_SCORE = 50
```

Then add:

```python
def _refutation_score_from_verify(items: list[VerificationItem]) -> int | None:
    """Points for claims the retrieval contradicted. Returns None if nothing was refuted.

    Only `red` carries weight, and `red` now means a retrieved result contradicts
    a specific claim the posting made — not merely that a result stated
    something negative.

    `green` is zero because a confirmed claim means the claim is supported, not
    that the posting is safe: verification withholds trust, it never grants it.

    `yellow` is zero for the same reason `SearchOutcome.ok` and `.results` are
    independent. A claim nobody could confirm has not been refuted, and a sole
    proprietorship with no web presence is the ordinary case in the Philippines.
    Scoring silence would penalise the smallest employers — the ones this product
    exists for — for having no website.

    Returns None rather than 0 when nothing was refuted, so the caller can tell
    "nothing was learned" from "a measurement of zero risk".
    """
    if not items:
        return None

    penalty = 0
    for item in items:
        if item.status != "red":
            continue
        label = item.label.strip()
        # Legacy label from before the rename; without the mapping a stored
        # verification would rescore from its weight to the default of 0.
        weight = REFUTATION_WEIGHTS.get(label) or REFUTATION_WEIGHTS.get(
            {"SEC Registration": "Official Registration"}.get(label, ""), 0
        )
        penalty += weight

    if penalty <= 0:
        return None
    return min(MAX_REFUTATION_SCORE, penalty)
```

- [ ] **Step 4: Give `_combine_scores` a floor**

Replace `_combine_scores` with:

```python
def _combine_scores(
    posting_score: int | None,
    refutation_score: int | None,
) -> tuple[int, str] | tuple[None, None]:
    """Add the refutation penalty to the posting score, with a floor.

    Asymmetric: evidence may only **raise**. What the retrieval establishes is
    that a claim is contradicted, not that a posting is safe. A clean employer
    record must not be able to pull a maxed posting down to a number the reader
    would read as tolerable.

    The `max` is what makes a balanced split possible without reintroducing the
    blend that was deleted. A plain 50/50 mean would report three high-severity
    anomalies plus an unlookable employer as 50 — "moderate" — because half of
    nothing is nothing. The floor keeps the posting's own full range intact and
    gives evidence a guaranteed share of the ceiling above it.

    A missing stage is absent, not zero: a posting that could not be looked up is
    not penalised for the failed lookup.
    """
    if posting_score is None:
        if refutation_score is None:
            return None, None
        return refutation_score, _level_for(refutation_score)
    if refutation_score is None:
        return posting_score, _level_for(posting_score)
    total = min(100, max(posting_score, posting_score + refutation_score))
    return total, _level_for(total)
```

- [ ] **Step 5: Point the flow at the new function**

In `backend/app/services/scanner/verification_flow.py`, replace both occurrences of `runtime.get_calculate_risk()(items)` with `runtime.get_refutation_score()(items)`, and change the log line `verify_score=` to `refutation_score=`.

In `backend/app/services/scanner/dependencies.py`, replace `get_calculate_risk` with:

```python
    get_refutation_score = staticmethod(lambda: _refutation_score_from_verify)
```

and import `_refutation_score_from_verify` from `.risk_calculator`. Keep `_calculate_risk_score_from_verify` exported — `test_scanner_package.py` asserts the symbol list, and removing it is a separate decision.

- [ ] **Step 6: Run to verify it passes**

Run: `python -m pytest tests/test_risk_model.py tests/test_verify.py -q`

Expected: PASS.

- [ ] **Step 7: Mutation-check both directions**

Replace `max(posting_score, posting_score + refutation_score)` with `(posting_score + refutation_score) // 2` and confirm `test_evidence_cannot_lower_a_maxed_posting` fails. Restore. Then set `MAX_REFUTATION_SCORE = 200` and confirm `test_the_stage_is_capped_at_fifty` fails. Restore. Then give `yellow` a weight of 5 and confirm `test_an_unverified_claim_adds_nothing` fails. Restore.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/scanner/risk_calculator.py \
  backend/app/services/scanner/verification_flow.py \
  backend/app/services/scanner/dependencies.py backend/tests/test_risk_model.py
git commit -m "feat(risk): score refutations only, with a floor on the posting stage"
```

---

### Task 7: Evidence Summary on the panel

**Files:**
- Modify: `entrypoints/sidepanel/types/index.ts`
- Modify: `entrypoints/sidepanel/components/scan/VerificationSection.tsx`
- Modify: `entrypoints/sidepanel/components/scan/AnomaliesList.tsx` (render as child)
- Modify: `entrypoints/sidepanel/views/ScamScanView.tsx:556,570`
- Test: `entrypoints/sidepanel/components/scan/EvidenceSummary.test.tsx` (new)

**Interfaces:**
- Consumes: `anomalies` on `ScanResult`; `searchOk`/`searchPartial`/`searchError` on `VerificationResult`.
- Produces: `EvidenceSummary` component; the heading is derived from state.

- [ ] **Step 1: Write the failing tests**

Create `entrypoints/sidepanel/components/scan/EvidenceSummary.test.tsx`:

```tsx
/**
 * The heading names what happened, and only calls something "evidence" when
 * there is some.
 *
 * A section titled "Evidence Summary" over an empty list asserts that evidence
 * was summarised. It was not. The reader must be able to tell three states
 * apart: something was found, the search ran and found nothing, and the search
 * could not run — the last two of which are both "no evidence" and must not be
 * dressed as findings.
 *
 * `happy-dom` performs no flex layout and zeroes every `getBoundingClientRect()`,
 * so these assert rendered text, not position or size.
 */

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { EvidenceSummary } from './EvidenceSummary';

afterEach(() => cleanup());

const base = {
  items: [
    { label: 'Company Existence', status: 'green' as const, explanation: 'Has a site.' },
  ],
  searchOk: true,
  report: '',
  recommendation: '',
};

describe('the heading is derived from state', () => {
  it('calls it Evidence Summary when something was found', () => {
    render(<EvidenceSummary result={base} />);
    expect(screen.getByText('Evidence Summary')).not.toBeNull();
  });

  it('does not call an empty result evidence', () => {
    render(<EvidenceSummary result={{ ...base, items: [] }} />);
    expect(screen.queryByText('Evidence Summary')).toBeNull();
    expect(screen.getByText(/found nothing/i)).not.toBeNull();
  });

  it('says the search could not run, separately from finding nothing', () => {
    // The distinction SearchOutcome.ok exists to preserve. Collapsing them
    // would report a deployment problem as a clean employer.
    render(<EvidenceSummary result={{ ...base, searchOk: false, searchError: 'TAVILY_API_KEY is not configured' }} />);
    expect(screen.getByText(/could not run/i)).not.toBeNull();
    expect(screen.queryByText(/found nothing/i)).toBeNull();
  });

  it('names a partial search rather than implying full coverage', () => {
    render(
      <EvidenceSummary
        result={{ ...base, searchPartial: true, queriesFailed: 1, queriesIssued: 3 }}
      />
    );
    expect(screen.getByText(/1 of 3 searches failed/i)).not.toBeNull();
  });
});

describe('nothing found must not read as a warning', () => {
  it('does not tell the reader to confirm the employer', () => {
    // An absent footprint is ordinary for a small Philippine employer, and
    // `build_queries` records this as the traded cost. Telling the reader to go
    // confirm attaches a warning to a non-event.
    render(<EvidenceSummary result={{ ...base, items: [] }} />);
    expect(screen.queryByText(/confirm the employer independently/i)).toBeNull();
  });
});

describe('anomalies lead the summary', () => {
  it('renders them above the search findings', () => {
    const anomalies = [
      { id: 'a1', title: 'Asks for a fee', description: 'The post asks for money.', icon: 'warning' as const, severity: 'high' as const },
    ];
    const { container } = render(<EvidenceSummary result={base} anomalies={anomalies} />);

    const text = container.textContent ?? '';
    expect(text.indexOf('Asks for a fee')).toBeGreaterThan(-1);
    expect(text.indexOf('Asks for a fee')).toBeLessThan(text.indexOf('Has a site.'));
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run entrypoints/sidepanel/components/scan/EvidenceSummary.test.tsx`

Expected: FAIL — module not found.

- [ ] **Step 3: Add the types**

In `entrypoints/sidepanel/types/index.ts`, add to `VerificationItem` if absent:

```ts
  /** The search that surfaced this check, when one was issued for it. */
  source_query?: string;
```

- [ ] **Step 4: Create `EvidenceSummary.tsx`**

Create `entrypoints/sidepanel/components/scan/EvidenceSummary.tsx`:

```tsx
import React from 'react';
import { Icon } from '../common';
import { VerificationCard } from './VerificationCard';
import { AnomaliesList } from './AnomaliesList';
import type { Accent } from '../../lib/riskAccent';
import type { Anomaly, VerificationResult } from '../../types';

interface EvidenceSummaryProps {
  result?: VerificationResult;
  loading?: boolean;
  error?: boolean;
  currentQuery?: string;
  anomalies?: Anomaly[];
  critical?: boolean;
  accent?: Accent;
}

/**
 * What the search found, with sources. Renamed from "External Verification":
 * that named the mechanism (external, meaning the web) and implied an actor
 * reaching a verdict. This section reports, and the reader draws the line.
 *
 * The heading is derived from state. A section titled "Evidence Summary" over
 * an empty list asserts that evidence was summarised when none was, so the
 * three outcomes each get their own heading:
 *
 *   something found  -> "Evidence Summary"
 *   ran, found none  -> not evidence; says what was searched
 *   could not run    -> not evidence; says the search did not complete
 *
 * The last two are both "no evidence" and are deliberately kept apart, because
 * `SearchOutcome.ok` and `.results` are independent and the panel must not undo
 * that by collapsing them into one "nothing found" state.
 */
export function EvidenceSummary({
  result,
  loading,
  error,
  currentQuery,
  anomalies = [],
  critical = false,
  accent,
}: EvidenceSummaryProps) {
  const hasItems = Boolean(result && result.items && result.items.length > 0);
  const unreadable = result?.searchOk === false;
  const partial = Boolean(result?.searchPartial);

  const heading = hasItems ? 'Evidence Summary' : null;
  const surface = accent?.surface ?? 'bg-surface-container-low';
  const border = accent?.border ? `${accent.border} border` : '';
  const text = accent?.text ?? 'text-secondary';

  return (
    <div className={`flex flex-col gap-3 p-4 rounded-xl ${surface} ${border}`}>
      <div className="flex items-center gap-2">
        <Icon name="search" className={text} />
        {heading ? (
          <h3 className={`text-label-md font-bold ${accent?.text ?? 'text-on-surface'}`}>
            {heading}
          </h3>
        ) : null}
        {loading && (
          <span className="ml-auto flex items-center gap-1.5 text-label-sm text-on-surface-variant">
            <span className="w-2 h-2 rounded-full bg-secondary animate-ping" />
            Searching…
          </span>
        )}
      </div>

      {/* Anomalies lead the summary: they are what the evidence is about. They
          render here in the found state and stay a sibling otherwise, because a
          posting with no employer and no search still has them and they must not
          disappear behind a heading that says nothing was found. */}
      {hasItems && <AnomaliesList anomalies={anomalies} critical={critical} />}

      {unreadable && (
        <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-error-container/10 border border-error/40">
          <div className="flex items-center gap-2">
            <Icon name="warning" className="text-error" />
            <span className="font-label-md font-bold text-on-surface">Search could not run</span>
          </div>
          <p className="text-body-sm text-on-surface-variant leading-relaxed">
            The web search did not run, so nothing about this employer is known.
            This is not a finding about them. What the posting itself says still
            stands.
          </p>
          {result?.searchError && (
            <span className="text-label-sm text-on-surface-variant/80 break-words">
              {result.searchError}
            </span>
          )}
        </div>
      )}

      {partial && (
        <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-amber-500/10 border border-amber-500/40">
          <div className="flex items-center gap-2">
            <Icon name="warning" className="text-amber-500" />
            <span className="font-label-md font-bold text-on-surface">Partial search coverage</span>
          </div>
          <p className="text-body-sm text-on-surface-variant leading-relaxed">
            {result?.queriesFailed && result?.queriesIssued
              ? `${result.queriesFailed} of ${result.queriesIssued} searches failed, `
              : 'One of the searches failed, '}
            so some checks below were made against a thinner set of results than
            the others. This is not a finding about the employer, and an
            unconfirmed claim may simply not have been covered.
          </p>
        </div>
      )}

      {hasItems && (
        <div className="flex flex-col gap-2">
          {result!.items.map((item, i) => (
            <VerificationCard key={i} item={item} />
          ))}
        </div>
      )}

      {!loading && !hasItems && !unreadable && !partial && !error && (
        <div className="flex flex-col gap-2 p-3 rounded-lg bg-surface-container border border-outline-variant/20">
          <div className="flex items-center gap-2">
            <Icon name="info" className="text-on-surface-variant" />
            <span className="font-label-md font-medium text-on-surface">
              Searched, found nothing
            </span>
          </div>
          {/* Deliberately not a warning and deliberately not advice. An absent
              online footprint is ordinary for a small employer, and telling the
              reader to go and confirm attaches an alarm to a non-event. */}
          <p className="text-body-sm text-on-surface-variant leading-relaxed">
            The search completed and returned no results for this employer. That
            is common for small businesses and is not itself a problem.
          </p>
        </div>
      )}

      {result?.report && (
        <div className="mt-1 pt-3 border-t border-outline-variant/20">
          <h4 className="text-label-md font-bold text-on-surface mb-1">What the search found</h4>
          <p className="text-body-sm text-on-surface-variant leading-relaxed">{result.report}</p>
        </div>
      )}

      {result?.evidence && result.evidence.length > 0 && (
        <details className="rounded-lg border border-outline-variant/20 bg-surface-container">
          <summary className="flex items-center gap-2 px-3 py-2 cursor-pointer">
            <Icon name="search" className="text-secondary" />
            <span className="text-label-sm font-bold text-on-surface">
              Sources ({result.evidence.length})
            </span>
            <span className="ml-auto text-label-sm text-on-surface-variant">tap to open</span>
          </summary>
          <ul className="flex flex-col gap-2 px-3 pb-3">
            {result.evidence.map((e, i) => (
              <li key={i} className="flex flex-col gap-0.5">
                <a
                  href={e.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-body-sm text-secondary hover:underline break-words"
                >
                  {e.title || e.url}
                </a>
                {e.snippet && (
                  <span className="text-label-sm text-on-surface-variant/80 leading-relaxed">
                    {e.snippet}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}

      {result?.recommendation && (
        <div className="rounded-lg bg-secondary-container/10 p-3">
          <h4 className="text-label-md font-bold text-secondary mb-1">What to do</h4>
          <p className="text-body-sm text-on-surface leading-relaxed">
            {result.recommendation}
          </p>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 py-2 text-body-sm text-on-surface-variant">
          <Icon name="info" className="text-secondary" />
          <span>The search could not be completed. What the posting itself says still stands.</span>
        </div>
      )}
    </div>
  );
}

export default EvidenceSummary;
```

- [ ] **Step 5: Wire it into the view**

In `entrypoints/sidepanel/views/ScamScanView.tsx`, change the import and the two render sites:

```tsx
import { RiskGauge, AnomaliesList, EvidenceSummary, ScanActions, ... } from '../components/scan';
```

Move `AnomaliesList` **inside** the `hasItems` path by passing it as a prop, and render:

```tsx
            {/* Anomalies lead the summary when the search found something, and
                stay a sibling when it did not — a posting with no employer still
                has them and must not lose them behind an empty heading. */}
            {hasFindings ? null : (
              <AnomaliesList anomalies={scanResult.anomalies} critical={scanResult.flagsCritical} />
            )}

            {needsCompanyName ? (
              <CompanyNameNeeded />
            ) : (
              <EvidenceSummary
                result={scanResult.verificationResult}
                loading={scanResult.verificationLoading}
                error={scanResult.verificationError}
                currentQuery={currentSearchQuery}
                anomalies={scanResult.anomalies}
                critical={scanResult.flagsCritical}
                accent={elevate ? accent : undefined}
              />
            )}
```

where `const hasFindings = Boolean(scanResult.verificationResult?.items?.length);` is declared beside `needsCompanyName`.

Export `EvidenceSummary` from `entrypoints/sidepanel/components/scan/index.ts` and keep `AnomaliesList` exported too.

Delete `VerificationSection.tsx` and its partial test, or leave the file exporting a re-export of `EvidenceSummary` if a reviewer prefers the rename to be visible in git history. **Prefer the git-visible rename**: `git mv` the file, then edit.

- [ ] **Step 6: Run to verify it passes**

Run: `npm run compile && npm test`

Expected: both clean.

- [ ] **Step 7: Mutation-check**

Set `const heading = hasItems ? 'Evidence Summary' : null;` to `'Evidence Summary'` unconditionally and confirm `test_does_not_call_an_empty_result_evidence` fails. Restore. Then change the "found nothing" body to include "confirm the employer independently" and confirm `test_does_not_tell_the_reader_to_confirm_the_employer` fails. Restore.

- [ ] **Step 8: Commit**

```bash
git add entrypoints/sidepanel/components/scan/ entrypoints/sidepanel/views/ScamScanView.tsx \
  entrypoints/sidepanel/types/index.ts
git commit -m "feat(scan): rename the verification section to Evidence Summary"
```

---

### Task 8: Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `SCORING-SOURCES.md` §8
- Modify: `docs/superpowers/specs/2026-10-10-dynamic-anomaly-verification-design.md` (mark built)

- [ ] **Step 1: Update AGENTS.md**

Add to the Key Architecture list:

```
- `backend/app/services/search.py` — **also owns `build_scheme_queries()`.** Given the posting's `attributes`, it returns up to 3 queries built from `LOCATION`, `CONTACT_METHOD` and `MEETING_SPOT` only. Three rules make it safe: only *stated* details (a missing input never earns a credit), only *checkable* attributes (`PAY` and `ROLE` are excluded — a salary figure is not corroborated by a search), and **no conclusions in the query** (terms are the poster's words, because a model-written anomaly label is a characterisation and would put the accusation inside the query).
- `backend/app/services/scanner/risk_calculator.py` — **evidence stage is `_refutation_score_from_verify()` and only `red` scores.** `red` means a retrieved source *contradicts a specific claim the posting made*; `green` (confirmed) and `yellow` (nothing learned) both contribute **zero**. Returns `None`, not `0`, when nothing was refuted. `_combine_scores` applies a **floor**: `max(posting, posting + refutation)`. A plain 50/50 mean was rejected because it would report three high-severity anomalies plus an unlookable employer as "moderate".
- `backend/app/services/scanner/verification_parser.py` — **raises `VerificationParseError` when the response contains no VERIFY block.** Returning `[]` for unparseable text let a failed verification render as a panel with nothing on it and no error anywhere. "Parsed and reported nothing" is a legitimate empty result and still returns `[]`.
- `backend/app/services/lm_client.py` — `_SECTION_RE` also matches `ATTRIBUTES`, `COMPANY`, `LOCATION`, `CONTACT_METHOD`, `MEETING_SPOT`, `PAY`, `QUERY_REF`, `SEARCH QUERIES`, `QUERY`. `END ATTRIBUTES` and `END SEARCH QUERIES` are bare terminators and are **deliberately not** in `_SECTION_END_KW` — treating a terminator as a section end resets `matched_any` and makes a valid scan parse as nothing.
```

Add to Gotchas:

```
- **A claim nobody could confirm is `yellow`, not `red`.** Absence of evidence is not evidence of absence, and it is the rule that keeps small employers from being scored as suspicious. A sole proprietorship with no website, no listing and no reviews is the ordinary case in the Philippines and is the population this product exists for — `build_queries` records this as the traded cost. Points require a retrieved source that **contradicts** the claim. A *channel mismatch* is the exception worth noticing: it is a contradiction, not a silence, because the employer's own domain exists and the posting directs applicants elsewhere. It is also the only check that can detect an impersonation, since a real employer passes every existence, registration and branch check.
- **One search query per credit, and credits are per request.** Adding scheme queries takes a verification from 2 requests to as many as 5. The cap is 3 and the queries are only issued for details the posting actually states, so a sparse posting still costs 2.
```

- [ ] **Step 2: Update SCORING-SOURCES.md §8**

Append:

```
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
```

- [ ] **Step 3: Mark the spec built**

Change the spec's status line to:

```
**Status:** Stages 1–4 implemented. Open items 6–9 remain. See
`docs/superpowers/plans/2026-10-10-dynamic-anomaly-verification.md`.
```

- [ ] **Step 4: Run every gate**

Run: `cd backend && python -m pytest tests/ -q` then `npm run compile && npm test`

Expected: **the 11 pre-existing failures in `test_scan_prompt_file.py` will still be there.** They fail identically on `HEAD` with the prompt files stashed and are unrelated to this work. Report the real number alongside that known set — do not claim the suite is green.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md SCORING-SOURCES.md \
  docs/superpowers/specs/2026-10-10-dynamic-anomaly-verification-design.md
git commit -m "docs: claim/defence verification and the refutation stage"
```

---

## Review Focus test placement

Each line from the header's Review Focus, and where its test lives:

| # | Input | Task | Test |
|---|---|---|---|
| 1 | No employer, no location | 2 | `test_a_missing_location_produces_nothing`, `test_a_missing_location_spends_no_credit` |
| 2 | Only a `low` anomaly | 1 | `test_query_ref_attaches_to_the_preceding_anomaly` (asserts the second anomaly's ref is `""`) |
| 3 | Provider drops `response_format` | 4 | `test_unparseable_prose_raises_rather_than_returning_empty` |
| 4 | `red` from a generic page | 3 | `test_every_claim_category_is_documented` + the same-scheme rule in the prompt |
| 5 | `QUERY_REF` to a failed query | 6 | `test_a_scheme_query_failure_is_partial_not_total` — partial, so no corroboration is credited |

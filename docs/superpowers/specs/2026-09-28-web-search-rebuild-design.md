# Web Search Rebuild — Design

**Date:** 2026-09-28
**Status:** awaiting review
**Supersedes:** `backend/app/services/ddg_search.py`

## Problem

The DuckDuckGo-based search produced results for the wrong query. Searches for
`Cleanfuel Philippines company` returned YouTube TV Help pages; `Vikings`
returned Knowunity; `Caishen` returned Wikipedia articles about the Chinese god
of wealth and Philippine senate impeachment news. The responses were successful
— HTTP 200, three or five results, no throttling flag — so nothing in the code
or the logs indicated a fault.

Four separate defects compounded over the day:

1. **Category headings asserted facts the retrieval never established.** A result
   found by a `"<company> scam fraud complaint"` query was presented under a
   `[SCAM REPORTS]` heading. A generic results page such as a regulator's
   complaint form appeared there as if it were a scam report.
2. **Snippets were silently dropped** by reading the library's `body` key where
   the normalised result used `snippet`. The model was shown titles only, and
   correctly reported that no result mentioned SEC registration.
3. **Empty results were indistinguishable from failures.** `ddg_search()`
   returned `[]` for both a rate-limited query and a company with no online
   presence, so a retrieval failure read as a clean company.
4. **Engine selection was a coin flip.** The `ddgs` library picks an engine at
   random when none is named. Most engines returned nothing from this machine;
   an unpinned call frequently hit an engine serving a stale cached page.

Each fix was individually reasonable. Together they produced a system where
success and failure looked identical, which is why diagnosis took a day and why
two intermediate diagnoses were wrong.

## Goals

- A search result is either evidence or it is unknown. Never a silent `[]`.
- One provider, one query, no per-request policy to get wrong.
- Online evidence enters the product at exactly one place.
- The debug surface reports the provider's raw response.

## Non-goals

- Multi-provider fallback, engine rotation, retry policy, or response caching.
- Searching during the scan. The scan reports on the posting; verification
  reports on the company.
- Changing the three verification categories, the risk scoring, or any prompt
  guardrail.

## Approach

Tavily as the search provider. It is built for LLM grounding, returns clean
JSON, requires no scraping or engine selection, and its free tier (1,000
searches/month, no card required) comfortably covers development. DuckDuckGo
scraping stays available in the git history.

### Module

`backend/app/services/search.py` replaces `ddg_search.py`. Approximately 80
lines against the previous 620.

```python
@dataclass
class SearchOutcome:
    results: list[SearchResult]   # empty on failure AND on no results
    ok: bool                      # the call succeeded
    error: str                    # "" unless it failed
    latency: float
```

A caller cannot conflate failure with absence: `ok` and `results` are
independent. `ok=False` with empty results means retrieval failed;
`ok=True` with empty results means the search genuinely found nothing.

`SearchResult` is `title`, `url`, `snippet`, `score` — Tavily's shape, normalised
once at the boundary.

### Query

One query per verification: `"{employer} Philippines"`.

No category suffixes. No formatter. The model receives a plain list of results
with their URLs and decides what each one is. This removes the mechanism that
produced the most serious defect: a heading cannot misrepresent a result when
no heading is imposed.

### Scan path

`/api/scan-text` no longer performs a search and no longer injects results into
the scan prompt. The scan reports only what the posting states: red flags,
employer name, posting analysis, job summary. The `web_search` field is removed
from `ScanResponse` — it was mapped in the frontend and never rendered.

This makes `/api/verify` the only place online evidence is used, which is where
the existing guardrail prose already lives and already instructs the model to
report only what the provided results state.

### Failure reporting

An unsuccessful search produces an explicit `NOTE ON RETRIEVAL` block in the
verification prompt, instructing the model to report every category as `yellow`
and to state that the search returned no results — without implying the company
lacks the records.

`verify_score` is `None` in that case, so `risk_calculator._combine_scores`
omits the verification stage entirely rather than scoring an absence. This is
existing behaviour and stays.

### Cost

One query per verification, against four today. Removing search from the scan
removes eight more per text scan. The rebuild is cheaper than the system it
replaces.

## Deletions

| Removed | Notes |
|---|---|
| `app/services/ddg_search.py` | entire file |
| `app/services/ai_tools.py` | `VERIFY_TOOLS`, `execute_tool`; nothing called them |
| `chat_with_tools` in `app/services/lm_client.py` | only consumer of `execute_tool` |
| `search_job_posting`, `search_job_posting_data` | scan-path search |
| `verify_company`, `search_company`, `search_company_for_verification` | verification-path search |
| `format_search_context`, `format_verification_context` | category formatters |
| `web_search` on `ScanResponse` | mapped, never rendered |
| `search_log` on the verify result | cosmetic query list, hardcoded before the search ran |
| 7 `ddg_*` settings | `ddg_max_concurrent`, `ddg_min_interval`, `ddg_max_per_verify`, `ddg_search_attempts`, `ddg_search_backoff`, `ddg_search_backoff_max`, `ddg_backend` |
| `SEARCH_CODE_VERSION` | new module logs its own startup line |
| `runtime.get_verify_company`, `get_extract_company`, `get_clean_company_name`, `get_company_name_is_valid` search bindings | rebound to the new module |

## Retained

`is_valid_company_name`, `clean_company_name`, and `extract_company_name` move
into `search.py`. They are pure string logic with no provider dependency, and
the scan depends on all three. `INVALID_COMPANY_NAMES`, `NOT_STATED_MARKERS`,
`_clean_company_candidate`, and the `EMPLOYER NAME` joined-name splitting come
across unchanged.

`/api/debug/search` and the Search debug tab stay, repointed at Tavily.
`SearchRawPanel` and the `debug_prompt` field stay: showing the exact prompt
handed to the model is how a bad retrieval gets diagnosed, which is the failure
this rebuild exists to prevent. It loses only the `searchLog` query list, since
the one query is now stated in the prompt itself.

## Debug surface

`POST /api/debug/search` takes `{query, max_results}` and streams:

1. `meta` — provider, key configured, model, max_results
2. `result` — one per result, in provider order
3. `raw` — the provider's complete response body, verbatim
4. `outcome` — `ok`, `error`, `latency`, `count`, `credits_used`
5. `done`

The raw response is included so a bad SERP is visible rather than inferred, and
`credits_used` makes the free tier's consumption observable.

## Files

| File | Change |
|---|---|
| `app/services/search.py` | new — provider call, outcome type, name helpers |
| `app/services/ddg_search.py` | deleted |
| `app/services/ai_tools.py` | deleted |
| `app/services/lm_client.py` | drop `chat_with_tools` |
| `app/config.py` | drop 7 `ddg_*`; keep `TAVILY_API_KEY`; add `tavily_max_results` |
| `app/routers/scan.py` | drop scan-path search and `web_search`; repoint debug endpoint and `runtime` bindings |
| `app/services/scanner/dependencies.py` | rebind to `search.py` |
| `app/services/scanner/scan_flow.py` | no change expected; `web_search` removal verified |
| `app/services/scanner/verification_flow.py` | call the new search; keep `debug_prompt` |
| `app/services/scanner/verification_prompt.py` | add the retrieval-failure block |
| `app/models/schemas.py` | drop `web_search`, `search_log`, `SearchDebugRequest` gains `max_results` |
| `entrypoints/sidepanel/lib/api.ts` | drop `searchLog`; `debugSearchStream` reads Tavily events |
| `entrypoints/sidepanel/types/index.ts` | drop `webSearch`, `searchLog` |
| `entrypoints/sidepanel/views/ScamScanView.tsx` | drop `webSearch` mapping |
| `entrypoints/sidepanel/components/scan/SearchRawPanel.tsx` | drop the `searchLog` query list |
| `backend/tests/test_ddg_search.py` | replace with `test_search.py` |
| `backend/tests/test_ai_tools.py` | deleted with its subject |
| `AGENTS.md`, `UNFINISHED-WORK.md`, `CRITICAL.md` | rewrite the search sections |

## Error handling

| Condition | Behaviour |
|---|---|
| No `TAVILY_API_KEY` | `ok=False`, `error="TAVILY_API_KEY is not configured"`, logged at ERROR once per call |
| HTTP error, timeout, or malformed body | `ok=False`, `error` names the cause, logged `[search] [error]` |
| HTTP 200, zero results | `ok=True`, `results=[]` — a finding, not a failure |
| Verification receives `ok=False` | `NOTE ON RETRIEVAL` block, all categories `yellow`, `verify_score=None` |

No retries. A retry policy on top of a provider that returns clean JSON would
recreate the ambiguity this rebuild exists to remove.

## Testing

The suite stays fully offline. Tavily is mocked at the HTTP boundary in
`conftest.py`, alongside the existing AI and DNS guards.

- `ok=True` with results returns the normalised shape, URLs and snippets intact
- `ok=False` on HTTP error sets `error` and leaves `results` empty
- `ok=True` with an empty body is **not** a failure
- a missing API key is a failure, not an empty success
- `NOTE ON RETRIEVAL` appears when retrieval failed and is absent when it
  genuinely found nothing
- `is_valid_company_name`, `clean_company_name`, `extract_company_name` keep
  their existing cases
- no test performs a network call

`npm test`, `npm run compile`, `npm run build`, and `python -m pytest` all pass.

## Manual verification

`/api/verify` on a posting naming a real Philippine employer, expecting a
`green` on Company Existence and an `SEC Registration` detail carrying a
registration number or a `yellow` stating the results mentioned none.

Tavily is a dependency with a credential. If the key is absent the panel must
say the search was unavailable, not present it as a clean company.

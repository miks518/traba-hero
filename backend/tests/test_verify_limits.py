"""Everything a caller sends to /api/verify is caller-supplied and was uncapped.

This is the only endpoint that spends from two budgets at once — Tavily *and*
OpenRouter. Every one of these fields reaches the provider: `company_name`
becomes a search query, and `job_summary`, `anomalies` and `attributes` are
quoted into the verification prompt as the claims its categories test.

`anomalies` was the worst of them. `list[Anomaly]` had no cap on the count and
no cap on `flag`, `reasoning` or `query_ref`, so a caller who could not afford
many jobs or images could send one verification carrying thousands of anomalies
with pages of text each, and have all of it tokenised into a reasoning call.
The same shape as the resume list, and bounded the same way.

`attributes` had the same problem in a dictionary: unbounded keys and unbounded
values, both fed to the model.

The `search_queries` count was already capped at two in `verification_flow`, and
that cap is enforced there rather than on the schema — which is correct, because
a client that is not this extension can post a longer list and the backend is
the last place it can be refused. What was missing is a cap on the *length* of
each query, which reaches Tavily verbatim.
"""

import re
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.schemas import (
    VerifyRequest,
    MAX_VERIFY_COMPANY_NAME,
    MAX_VERIFY_JOB_SUMMARY,
    MAX_VERIFY_ANOMALIES,
    MAX_VERIFY_ANOMALY_TEXT,
    MAX_VERIFY_ATTRIBUTES,
    MAX_VERIFY_ATTRIBUTE_KEY,
    MAX_VERIFY_ATTRIBUTE_VALUE,
    MAX_VERIFY_QUERY_CHARS,
)

transport = ASGITransport(app=app)
HEADERS = {"X-Trabahero-Client-Key": "test-secret-key"}

BODY = {"company_name": "Acme Trading", "job_summary": "Sales associate wanted"}


async def post_verify(payload: dict):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/verify", json=payload, headers=HEADERS)


def anomaly(**over) -> dict:
    return {
        "flag": "Asks for a processing fee",
        "reasoning": "The post asks for money up front.",
        "severity": "high",
        **over,
    }


# ── The anomaly list: the one that mattered ───────────────────────────────────

@pytest.mark.asyncio
async def test_two_thousand_anomalies_is_refused():
    payload = {**BODY, "anomalies": [anomaly() for _ in range(2000)]}

    resp = await post_verify(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_one_anomaly_past_the_cap_is_refused():
    payload = {**BODY, "anomalies": [anomaly() for _ in range(MAX_VERIFY_ANOMALIES + 1)]}

    resp = await post_verify(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_exactly_the_cap_of_anomalies_is_accepted():
    payload = {**BODY, "anomalies": [anomaly() for _ in range(MAX_VERIFY_ANOMALIES)]}

    resp = await post_verify(payload)

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_one_anomaly_with_pages_of_reasoning_is_refused():
    """The count cap does not bound an item. Twenty anomalies of 50KB is the
    same token cost as one enormous one, so bounding only the list leaves the
    cheaper door — which is the mistake the image cap made on its first attempt."""
    payload = {
        **BODY,
        "anomalies": [anomaly(reasoning="A" * (MAX_VERIFY_ANOMALY_TEXT + 1))],
    }

    resp = await post_verify(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_an_oversized_anomaly_flag_is_refused():
    payload = {**BODY, "anomalies": [anomaly(flag="A" * (MAX_VERIFY_ANOMALY_TEXT + 1))]}

    resp = await post_verify(payload)

    assert resp.status_code == 422


# ── The claims dictionary ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_too_many_attributes_is_refused():
    payload = {**BODY, "attributes": {f"K{i}": "v" for i in range(MAX_VERIFY_ATTRIBUTES + 1)}}

    resp = await post_verify(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_an_oversized_attribute_value_is_refused():
    payload = {**BODY, "attributes": {"LOCATION": "A" * (MAX_VERIFY_ATTRIBUTE_VALUE + 1)}}

    resp = await post_verify(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_an_oversized_attribute_key_is_refused():
    payload = {**BODY, "attributes": {"A" * (MAX_VERIFY_ATTRIBUTE_KEY + 1): "v"}}

    resp = await post_verify(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_exactly_the_cap_of_attributes_is_accepted():
    payload = {**BODY, "attributes": {f"K{i}": "v" for i in range(MAX_VERIFY_ATTRIBUTES)}}

    resp = await post_verify(payload)

    assert resp.status_code == 200


# ── The strings that become a query and the prompt ────────────────────────────

@pytest.mark.asyncio
async def test_an_oversized_company_name_is_refused():
    """This one is quoted into the search query, so it also reaches Tavily."""
    resp = await post_verify({**BODY, "company_name": "A" * (MAX_VERIFY_COMPANY_NAME + 1)})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_an_oversized_job_summary_is_refused():
    resp = await post_verify({**BODY, "job_summary": "A" * (MAX_VERIFY_JOB_SUMMARY + 1)})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_an_oversized_search_query_is_refused():
    """The count is already capped at two server-side; the length was not, and
    each query goes to Tavily verbatim."""
    resp = await post_verify({**BODY, "search_queries": ["A" * (MAX_VERIFY_QUERY_CHARS + 1)]})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_a_normal_verification_is_accepted():
    resp = await post_verify(
        {
            **BODY,
            "anomalies": [anomaly()],
            "attributes": {"LOCATION": "Davao", "CONTACT_METHOD": "Messenger"},
            "search_queries": ["Acme Trading branches Davao"],
        }
    )

    assert resp.status_code == 200


# ── Without a server ──────────────────────────────────────────────────────────

def test_the_schema_rejects_the_attempt_directly():
    with pytest.raises(ValueError):
        VerifyRequest(**BODY, anomalies=[anomaly()] * (MAX_VERIFY_ANOMALIES + 1))

    assert len(VerifyRequest(**BODY, anomalies=[anomaly()] * MAX_VERIFY_ANOMALIES).anomalies) == (
        MAX_VERIFY_ANOMALIES
    )


def test_the_query_count_is_capped_in_the_flow_and_not_on_the_schema():
    """Only the length is bounded here, and that asymmetry is the design.

    The count is capped at `MAX_SEARCH_QUERIES` inside `verification_flow`,
    which is the layer that can refuse a caller who is not this extension. A
    count cap on the schema would turn an over-long list into a 422 and make
    that truncation unreachable — leaving the real defence untested, which is
    worse than having two of them.

    `test_verify.py::TestTheQueryBudget` covers the flow-side cap; this asserts
    the schema has deliberately stayed out of it.
    """
    from app.models.schemas import VerifyRequest

    field = VerifyRequest.model_fields["search_queries"]
    bounds = [m.max_length for m in field.metadata if hasattr(m, "max_length")]

    assert not bounds, (
        "search_queries gained a schema-level count cap; the count belongs to "
        "verification_flow"
    )


def test_the_job_summary_bound_matches_the_text_endpoints():
    """`/api/scan-text` and `/api/analyze-offer` already accept 50,000
    characters. A verification fed from the same posting must accept the same
    text, or a posting that scans fine fails to verify — and it would fail
    after the reader has already paid for the scan.

    Read from the schema rather than restated, so the two drifting apart fails
    here instead of in production.
    """
    from app.models.schemas import ScanTextRequest

    bound = ScanTextRequest.model_fields["text"]
    assert bound.metadata[-1].max_length == MAX_VERIFY_JOB_SUMMARY
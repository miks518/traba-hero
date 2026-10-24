"""The verify stage's verdict on each posting finding.

The findings are the scan's own claims, so the verify model is asked to assess
them against the same retrieved results it uses for the six category checks.
These tests cover the boundary that matters: an assessment is only shown with a
source that was actually retrieved, and a missing or unusable assessment is
never turned into a `stale`.
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch

from app.main import app
from app.services.scanner.verification_flow import _read_verify_output

transport = ASGITransport(app=app)

RETRIEVED = "https://employer.example/careers"


def _payload(assessments, checks=None):
    return json.dumps({
        "checks": checks if checks is not None else [],
        "evidence": [],
        "report": "r",
        "recommendation": "x",
        "risk_level": "moderate",
        "risk_score": 40,
        "verdict_reason": "",
        "anomaly_assessments": assessments,
    })


def _read(assessments, count=3, allowed=(RETRIEVED,), checks=None):
    return _read_verify_output(
        _payload(assessments, checks=checks),
        allowed_urls=frozenset(allowed),
        anomaly_count=count,
    )


def _assess(index=1, status="stale", finding="The careers page states the exam fee is paid before deployment.", url=RETRIEVED, title="Careers"):
    return {
        "index": index,
        "status": status,
        "finding": finding,
        "source_title": title,
        "source_url": url,
    }


def test_a_stale_assessment_with_a_retrieved_source_survives():
    *_, assessments = _read([_assess()])

    assert len(assessments) == 1
    assert assessments[0].index == 1
    assert assessments[0].status == "stale"
    assert assessments[0].source_url == RETRIEVED
    assert assessments[0].source_title == "Careers"


def test_a_stale_without_a_source_is_demoted_to_unknown():
    """Absence is never evidence in the reader's favour.

    `stale` retires a finding. An unbacked one would retire it on nothing, which
    is the same failure an unbacked `red` has, in the opposite direction.
    """
    *_, assessments = _read([_assess(url="")])

    assert assessments[0].status == "unknown"
    assert assessments[0].source_url == ""
    assert assessments[0].source_title == ""


def test_a_source_outside_the_retrieved_set_is_dropped_and_demotes():
    *_, assessments = _read([_assess(url="https://attacker.example/never-retrieved")])

    assert assessments[0].status == "unknown"
    assert assessments[0].source_url == ""
    assert assessments[0].source_title == ""


def test_a_contradicted_without_a_source_is_demoted_to_unknown():
    *_, assessments = _read([_assess(status="red", url="")])

    assert assessments[0].status == "unknown"


def test_an_out_of_range_index_is_dropped_not_renumbered():
    *_, assessments = _read([_assess(index=4)], count=3)

    assert assessments == []


def test_a_fractional_index_is_dropped_not_truncated():
    """`int(1.5)` is 1, which would attach the verdict to the wrong finding."""
    *_, assessments = _read([_assess(index=1.5)])

    assert assessments == []


def test_a_numeric_string_index_is_accepted():
    """The labeled-text path has no schema, and a quoted index is still an index."""
    *_, assessments = _read([_assess(index="2")])

    assert assessments[0].index == 2


def test_a_duplicate_index_keeps_the_first():
    first = _assess(index=1, status="stale")
    second = _assess(index=1, status="red", url="")
    *_, assessments = _read([first, second])

    assert len(assessments) == 1
    assert assessments[0].status == "stale"


def test_an_unknown_status_is_dropped():
    *_, assessments = _read([_assess(status="green")])

    assert assessments == []


def test_an_assessment_with_no_sentence_is_dropped():
    """The strip is the sentence and, for stale/red, the source.

    An entry with no sentence would render a label over an empty space, which is
    worse than the card's own "no verdict recorded" note.
    """
    *_, assessments = _read([_assess(finding="   ")])

    assert assessments == []


def test_a_missing_key_returns_no_assessments():
    payload = json.dumps({
        "checks": [], "evidence": [], "report": "r", "recommendation": "x",
    })
    *_, assessments = _read_verify_output(payload, anomaly_count=2)

    assert assessments == []


def test_the_text_fallback_returns_no_assessments():
    text = (
        "VERIFY: Company Existence\n"
        "STATUS: yellow\n"
        "DETAIL: The results do not mention this company.\n"
        "END VERIFY\n"
    )
    *_, assessments = _read_verify_output(text, anomaly_count=2)

    assert assessments == []


def test_assessments_are_returned_in_index_order():
    *_, assessments = _read([
        _assess(index=3, finding="third"),
        _assess(index=1, finding="first"),
        _assess(index=2, finding="second"),
    ])

    assert [a.index for a in assessments] == [1, 2, 3]


@pytest.mark.asyncio
async def test_the_verify_result_event_carries_the_assessments():
    """The field reaches the wire on the normal path, not only the parser.

    This is the leg that a parser-only test would miss: the parser could return
    assessments while the SSE event forgot to serialize them, and the panel
    would show every card as amber with no error anywhere.
    """
    from app.services.search import SearchOutcome, SearchResult

    answer = _payload([
        {
            "index": 1,
            "status": "stale",
            "finding": "The careers page states the exam fee is paid before deployment.",
            "source_title": "Acme",
            "source_url": "https://example.invalid/acme",
        }
    ])
    found = SearchOutcome(
        results=[SearchResult("Acme", "https://example.invalid/acme", "s", 0.9)],
        ok=True,
    )
    with (
        patch("app.routers.scan.chat", return_value=answer),
        patch("app.routers.scan.search", return_value=found),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/verify", json={
                "company_name": "Acme Corporation",
                "job_summary": "Software Engineer at Acme Corporation",
                "anomalies": [{
                    "flag": "Asks applicants to pay a processing fee",
                    "reasoning": "The post asks for money before work.",
                    "severity": "high",
                }],
            })

    assert resp.status_code == 200
    result_line = next(
        line for line in resp.text.splitlines()
        if line.startswith("data: ") and '"type": "result"' in line
    )
    event = json.loads(result_line[len("data: "):])
    assessments = event["data"]["anomaly_assessments"]

    assert len(assessments) == 1
    assert assessments[0]["index"] == 1
    assert assessments[0]["status"] == "stale"

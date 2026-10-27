"""The wire loses the score.

`riskScore`, `riskLevel`, `scoreBreakdown` are gone. `assessment` and
`assessmentBreakdown` replace them. The breakdown is a record of how the assessment
was reached - the class of the request, the establishment, the rule that fired,
and the sources - not a magnitude.
"""

import json
import pytest
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.search import SearchOutcome, SearchResult


transport = ASGITransport(app=app)


async def _verify(payload: dict, request: dict, results: list[SearchResult]):
    with (
        patch("app.routers.scan.search", return_value=SearchOutcome(results=results, ok=True)),
        patch("app.routers.scan.chat", return_value=json.dumps(payload)),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/verify", json=request)
    assert resp.status_code == 200
    events = []
    for line in resp.text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    results = [event for event in events if event.get("type") == "result"]
    assert results, resp.text
    return results[-1]["data"]


def _knollridges_payload() -> dict:
    return {
        "checks": [
            {
                "category": "Company Existence",
                "status": "green",
                "finding": "Knollridges is a recruitment firm with an office in Makati.",
                "source_title": "Knollridges",
                "source_url": "https://knollridges.com.ph",
            },
            {
                "category": "Reputation",
                "status": "yellow",
                "finding": "The results do not mention this category.",
                "source_title": "",
                "source_url": "",
            },
        ],
        "evidence": [
            {
                "title": "Knollridges",
                "url": "https://knollridges.com.ph",
                "snippet": "Knollridges is a recruitment firm.",
            }
        ],
        "report": "The results show a recruitment firm with its own site.",
        "recommendation": "Ask the recruiter to confirm the email address in writing.",
        "assessment_reason": "It gives an email address the company's own site does not show.",
        "anomaly_assessments": [],
        "channel_match": {
            "printed_channels": ["yvonne.knollridges@gmail.com"],
            "official_channels": ["knollridges.com.ph"],
            "government_claim": False,
            "finding": "The posting gives yvonne.knollridges@gmail.com and the company site is knollridges.com.ph.",
            "source_title": "Knollridges",
            "source_url": "https://knollridges.com.ph",
        },
    }


def _knollridges_request() -> dict:
    return {
        "company_name": "Knollridges Inc.",
        "job_summary": "Send your resume to yvonne.knollridges@gmail.com.",
        "attributes": {
            "CONTACT_METHOD": "Email yvonne.knollridges@gmail.com",
        },
        "anomalies": [],
    }


@pytest.mark.asyncio
async def test_the_verify_wire_carries_assessment_not_score():
    """The result event carries `assessment` and `assessmentBreakdown`, not
    `riskLevel`, `riskScore`, or `scoreBreakdown`."""
    data = await _verify(
        _knollridges_payload(),
        _knollridges_request(),
        [
            SearchResult(
                "Knollridges",
                "https://knollridges.com.ph",
                "Knollridges is a recruitment firm.",
                0.9,
            )
        ],
    )

    # The new keys
    assert "assessment" in data, "wire must carry assessment"
    assert "assessmentBreakdown" in data, "wire must carry assessmentBreakdown"

    # The old keys are gone
    assert "riskLevel" not in data, f"old key riskLevel still present: {data.get('riskLevel')}"
    assert "riskScore" not in data, f"old key riskScore still present: {data.get('riskScore')}"
    assert "scoreBreakdown" not in data, f"old key scoreBreakdown still present: {data.get('scoreBreakdown')}"

    # The assessment is a string from the grid
    assert data["assessment"] in ("clear", "note", "caution", "stop")

    # The breakdown is a dict with the decision record
    breakdown = data["assessmentBreakdown"]
    assert isinstance(breakdown, dict)
    assert "assessment" in breakdown
    assert "exposure" in breakdown
    assert "establishment" in breakdown
    assert "rule" in breakdown
    assert "record" in breakdown
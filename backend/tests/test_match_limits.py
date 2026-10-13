"""The match payload is the second unbounded surface, and it is not a small one.

`MatchRequest.jobs` had no cap. Every job in the list becomes one match result,
so the cost of the call grows with the number of jobs and with how long each one
is — and the request is a single model call, not one call per job.

The extension sends `verifiedJobs`, which is capped at `MAX_SCAN_HISTORY`, so
the server was accepting arbitrarily more work than any real client could ask
for. That is the same shape of gap as the image list: the frontend is careful,
the API is not, and only one of those is on your bill.

The resume half matters too. `ResumeData.skills` and friends were unbounded lists
of unbounded strings, so a caller who could not afford many jobs could send one
job and an enormous resume instead.

Rejected, never truncated, for the same reason as the image cap: dropping the
101st skill and returning 100 silently would hand back a match computed from a
resume the caller never sent.
"""

import re
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.schemas import (
    MAX_JOBS_PER_MATCH,
    MAX_MATCH_JOB_SUMMARY,
    MAX_MATCH_JOB_TITLE,
    MAX_MATCH_JOB_ID,
    MAX_RESUME_SUMMARY,
    MAX_RESUME_LIST_ITEMS,
    MAX_RESUME_ITEM_CHARS,
    MatchRequest,
)

transport = ASGITransport(app=app)
HEADERS = {"X-Trabahero-Client-Key": "test-secret-key"}

RESUME = {
    "skills": ["Python"],
    "experience_years": 2,
    "job_titles": ["Developer"],
    "industries": ["IT"],
    "summary": "A summary.",
}


def job(i: int = 0, **over) -> dict:
    return {"id": f"job-{i}", "title": "Sales associate", "summary": "A role.", **over}


async def post_match(payload: dict):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/match-resume", json=payload, headers=HEADERS)


# ── The job list ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_thousand_jobs_is_refused():
    payload = {"resume": RESUME, "jobs": [job(i) for i in range(1000)]}

    resp = await post_match(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_one_job_past_the_cap_is_refused():
    payload = {"resume": RESUME, "jobs": [job(i) for i in range(MAX_JOBS_PER_MATCH + 1)]}

    resp = await post_match(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_exactly_the_cap_is_accepted():
    """The other side of the same boundary. Without it a cap of zero passes
    every test above."""
    payload = {"resume": RESUME, "jobs": [job(i) for i in range(MAX_JOBS_PER_MATCH)]}

    resp = await post_match(payload)

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_one_oversized_job_summary_is_refused():
    """Bounded count, unbounded item. Twenty 200KB jobs are the same token cost
    as one enormous one, so the count cap alone does not bound the call."""
    payload = {"resume": RESUME, "jobs": [job(summary="A" * (MAX_MATCH_JOB_SUMMARY + 1))]}

    resp = await post_match(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_an_oversized_job_title_is_refused():
    payload = {"resume": RESUME, "jobs": [job(title="A" * (MAX_MATCH_JOB_TITLE + 1))]}

    resp = await post_match(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_an_oversized_job_id_is_refused():
    payload = {"resume": RESUME, "jobs": [job(id="A" * (MAX_MATCH_JOB_ID + 1))]}

    resp = await post_match(payload)

    assert resp.status_code == 422


# ── The resume half ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_an_oversized_resume_summary_is_refused():
    """One job and a megabyte of resume is the cheap way around the job cap."""
    payload = {
        "resume": {**RESUME, "summary": "A" * (MAX_RESUME_SUMMARY + 1)},
        "jobs": [job()],
    }

    resp = await post_match(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_a_resume_with_too_many_skills_is_refused():
    payload = {
        "resume": {**RESUME, "skills": ["x"] * (MAX_RESUME_LIST_ITEMS + 1)},
        "jobs": [job()],
    }

    resp = await post_match(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_a_single_enormous_skill_is_refused():
    """The list cap does not bound an item, which is the mistake the image cap
    made the first time."""
    payload = {
        "resume": {**RESUME, "skills": ["x" * (MAX_RESUME_ITEM_CHARS + 1)]},
        "jobs": [job()],
    }

    resp = await post_match(payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_a_normal_resume_and_job_are_accepted():
    resp = await post_match({"resume": RESUME, "jobs": [job()]})

    assert resp.status_code == 200


# ── Without a server ──────────────────────────────────────────────────────────

def test_the_schema_rejects_the_attempt_directly():
    with pytest.raises(ValueError):
        MatchRequest(resume=RESUME, jobs=[job(i) for i in range(MAX_JOBS_PER_MATCH + 1)])

    assert len(
        MatchRequest(resume=RESUME, jobs=[job(i) for i in range(MAX_JOBS_PER_MATCH)]).jobs
    ) == MAX_JOBS_PER_MATCH


def test_the_job_cap_matches_the_history_the_client_can_hold():
    """You can only match jobs you have scanned, so the two limits are the same
    number by construction. Read out of the extension rather than restated, so
    raising the history cap without raising this one does not break matching.
    """
    frontend = Path(__file__).resolve().parents[2] / (
        "entrypoints/sidepanel/lib/scanHistory.ts"
    )
    match = re.search(
        r"export const MAX_SCAN_HISTORY\s*=\s*(\d+)", frontend.read_text(encoding="utf-8")
    )

    assert match, "MAX_SCAN_HISTORY not found in scanHistory.ts"
    assert int(match.group(1)) == MAX_JOBS_PER_MATCH
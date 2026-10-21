"""The two Channel Match regressions, pinned end to end through /api/verify.

These are the fixtures that motivated moving the severity out of the model:

* **Knollridges** — a real employer whose posting used
  `yvonne.knollridges@gmail.com` while its own site was `knollridges.com.ph`.
  The model reported the difference and its own `risk_level` as critical, and the
  wire carried "Do not proceed". The corrected outcome is a yellow informational
  Channel Match card and a level that comes from the posting's findings.
* **Fake CHED** — a poster using the real CHED Regional Office VI seal and
  `ched.gov.ph`, but sending applicants to `recruitment.chred@outlook.com`,
  `chred-region6.org`, and `info@chred-region6.org`, with mandatory fees. The
  government claim plus a non-.gov.ph channel is red; the two high fee findings
  make the final level critical.

Every test here mocks `app.routers.scan.search` and `app.routers.scan.chat`. No
test in this file reaches a provider.
"""

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.lm_client import _parse_custom
from app.services.search import SearchOutcome, SearchResult


transport = ASGITransport(app=app)

VERDICT_COPY = (
    Path(__file__).resolve().parents[2]
    / "entrypoints"
    / "sidepanel"
    / "components"
    / "report"
    / "verdictCopy.ts"
)


def _headline_for(level: str | None) -> str:
    """The headline the panel renders for a level, read from the real file.

    **The two halves of the verdict are a contract, and this is the seam.** The
    backend decides the level; `verdictCopy.ts` decides the words; the reader
    sees the words. A test that asserts only the level pins one half, and the
    other half can be edited into saying "Do not proceed" for a level the
    backend chose carefully - which is exactly the bug these fixtures exist to
    prevent, and exactly what happened before the level moved into code.

    So the assertion reads the frontend's own table rather than restating the
    expected string. If the mapping changes, this fails and says so, instead of
    the two sides drifting apart quietly.
    """
    if not level:
        return "No verdict on this one"
    source = VERDICT_COPY.read_text(encoding="utf-8")
    match = re.search(
        rf"\b{re.escape(level)}:\s*\{{\s*headline:\s*'([^']+)'", source
    )
    assert match, f"verdictCopy.ts has no headline for level {level!r}"
    return match.group(1)


def _result(resp) -> dict:
    events = []
    for line in resp.text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    results = [event for event in events if event.get("type") == "result"]
    assert results, resp.text
    return results[-1]["data"]


def _items_by_label(data: dict) -> dict[str, dict]:
    return {item["label"]: item for item in data["items"]}


async def _verify(payload: dict, request: dict, results: list[SearchResult]):
    with (
        patch(
            "app.routers.scan.search",
            return_value=SearchOutcome(results=results, ok=True),
        ),
        patch("app.routers.scan.chat", return_value=json.dumps(payload)),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/verify", json=request)
    assert resp.status_code == 200
    return _result(resp)


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
        "verdict_reason": "It gives an email address the company's own site does not show.",
        "anomaly_assessments": [],
        "channel_match": {
            "printed_channels": ["yvonne.knollridges@gmail.com"],
            "official_channels": ["knollridges.com.ph"],
            "government_claim": False,
            "finding": (
                "The posting gives yvonne.knollridges@gmail.com and the company "
                "site is knollridges.com.ph."
            ),
            "source_title": "Knollridges",
            "source_url": "https://knollridges.com.ph",
        },
        # Deliberately the old model-owned verdict. It must not reach the wire.
        "risk_level": "critical",
        "risk_score": 95,
    }


def _fake_ched_payload() -> dict:
    # The source poster is
    # jobposts/849453314_1725304345239568_5019491814499416862_n.png. This payload
    # is the model's read of it, kept offline so the regression never spends a
    # provider call or a search credit.
    return {
        "checks": [
            {
                "category": "Company Existence",
                "status": "green",
                "finding": "CHED Regional Office VI is a government office in Iloilo City.",
                "source_title": "CHED Regional Office VI",
                "source_url": "https://ched.gov.ph",
            },
            {
                "category": "Official Registration",
                "status": "green",
                "finding": "The results show the office on the CHED official site.",
                "source_title": "CHED Regional Office VI",
                "source_url": "https://ched.gov.ph",
            },
            {
                "category": "Location / Branch",
                "status": "yellow",
                "finding": "The results do not mention this category.",
                "source_title": "",
                "source_url": "",
            },
            {
                # The model is told not to send this. If it does, the facts
                # object wins and this entry is discarded.
                "category": "Channel Match",
                "status": "green",
                "finding": "The posting uses the official channel.",
                "source_title": "CHED Regional Office VI",
                "source_url": "https://ched.gov.ph",
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
                "title": "CHED Regional Office VI",
                "url": "https://ched.gov.ph",
                "snippet": "Official site of the Commission on Higher Education.",
            }
        ],
        "report": "The results show the government office the posting names.",
        "recommendation": "Confirm the application process with the office directly.",
        "verdict_reason": "It asks for a fee before it will accept an application.",
        "anomaly_assessments": [],
        "channel_match": {
            "printed_channels": [
                "recruitment.chred@outlook.com",
                "chred-region6.org",
                "info@chred-region6.org",
                "hrmo6@ched.gov.ph",
            ],
            "official_channels": ["ched.gov.ph"],
            "government_claim": True,
            "finding": (
                "The posting gives recruitment.chred@outlook.com and the agency "
                "site is ched.gov.ph."
            ),
            "source_title": "CHED Regional Office VI",
            "source_url": "https://ched.gov.ph",
        },
        # The model's own verdict is the opposite of the facts. It must not reach
        # the wire.
        "risk_level": "low",
        "risk_score": 0,
    }


def _fake_ched_request() -> dict:
    return {
        "company_name": "CHED Regional Office VI",
        "job_summary": "Apply by emailing recruitment.chred@outlook.com.",
        "attributes": {
            "CONTACT_METHOD": "Email recruitment.chred@outlook.com",
            "REGISTERED_AS": "CHED Regional Office VI",
            "LOCATION": "Iloilo City",
        },
        "anomalies": [
            {
                "flag": "Mandatory application fee",
                "reasoning": "The poster says a P1,500 application fee is required.",
                "severity": "high",
                "code": "FEE_MANDATORY",
            },
            {
                "flag": "Mandatory seminar fee",
                "reasoning": "The poster says an P800 seminar fee is required.",
                "severity": "high",
                "code": "FEE_MANDATORY",
            },
        ],
    }


def _two_channel_payload() -> dict:
    """The model's answer when the posting named two channels.

    The model is told to report the facts, and it reports both channels it
    was given. The status it would have written is not in here: the card is
    the code's.
    """
    return {
        "checks": [
            {
                "category": "Company Existence",
                "status": "green",
                "finding": "CHED Regional Office VI is a government office in Iloilo City.",
                "source_title": "CHED Regional Office VI",
                "source_url": "https://ched.gov.ph",
            },
            {
                "category": "Official Registration",
                "status": "green",
                "finding": "The results show the office on the CHED official site.",
                "source_title": "CHED Regional Office VI",
                "source_url": "https://ched.gov.ph",
            },
        ],
        "evidence": [
            {
                "title": "CHED Regional Office VI",
                "url": "https://ched.gov.ph",
                "snippet": "Official site of the Commission on Higher Education.",
            }
        ],
        "report": "The results show the government office the posting names.",
        "recommendation": "Confirm the application process with the office directly.",
        "verdict_reason": "It asks you to apply through a free-mail address.",
        "anomaly_assessments": [],
        "channel_match": {
            "printed_channels": [
                "hrmo6@ched.gov.ph",
                "recruitment.ched@outlook.com",
            ],
            "official_channels": ["ched.gov.ph"],
            "government_claim": True,
            "finding": (
                "The posting gives hrmo6@ched.gov.ph and "
                "recruitment.ched@outlook.com; the agency site is ched.gov.ph."
            ),
            "source_title": "CHED Regional Office VI",
            "source_url": "https://ched.gov.ph",
        },
    }


def _two_channel_request() -> dict:
    """The scan's own output, carried through to the verify request.

    The attributes are **parsed from a scan output**, not written by hand. A
    scan that could only hold one channel would parse this to a single
    channel, and the request would carry one — so the test fails on the
    pre-port parser, which is the point: the capability being pinned is the
    scan's, and the prompt assertion below is where it shows up.
    """
    raw = (
        "VALID: true\n"
        "ATTRIBUTES:\n"
        "CONTACT_METHOD: email | hrmo6@ched.gov.ph\n"
        "CONTACT_METHOD: email | recruitment.ched@outlook.com\n"
        "CLAIMED_TYPE: government\n"
        "REGISTERED_AS: CHED Regional Office VI\n"
        "LOCATION: Iloilo City\n"
        "END ATTRIBUTES\n"
        "EMPLOYER NAME: Commission on Higher Education\n"
    )
    attributes = _parse_custom(raw)["attributes"]
    return {
        "company_name": "CHED Regional Office VI",
        "job_summary": "Apply by emailing recruitment.ched@outlook.com.",
        "attributes": attributes,
        "anomalies": [
            {
                "flag": "Mandatory application fee",
                "reasoning": "The poster says a P1,500 application fee is required.",
                "severity": "high",
                "code": "FEE_MANDATORY",
            }
        ],
    }


@pytest.mark.asyncio
async def test_knollridges_does_not_become_do_not_proceed():
    data = await _verify(
        _knollridges_payload(),
        {
            "company_name": "Knollridges Inc.",
            "job_summary": "Send your resume to yvonne.knollridges@gmail.com.",
            "attributes": {
                "CONTACT_METHOD": "Email yvonne.knollridges@gmail.com",
            },
            "anomalies": [],
        },
        [
            SearchResult(
                "Knollridges",
                "https://knollridges.com.ph",
                "Knollridges is a recruitment firm.",
                0.9,
            )
        ],
    )

    channel = _items_by_label(data)["Channel Match"]

    assert channel["status"] == "yellow"
    assert channel["escalation"] == "free_email"
    assert "ordinary in Philippine job postings" in channel["explanation"]
    assert "not a contradiction by itself" in channel["explanation"]
    assert "recruitment.chred" not in channel["explanation"]

    # The model tried to say critical/95. The code says low/0.
    assert data["riskLevel"] == "low"
    assert data["riskScore"] == 0

    # The reader-visible half. The panel renders `verdictCopy.ts`'s headline for
    # the level, and `low` is the only level that means "Proceed, with a quick
    # check". Asserting the level alone leaves the outcome unpinned: the
    # mapping could be edited to say "Do not proceed" for `low` and every test
    # in this file would still pass, with this exact bug back in the panel.
    # The mapping itself is pinned in
    # `entrypoints/sidepanel/components/report/verdictCopy.test.ts`.
    assert _headline_for(data["riskLevel"]) == "Proceed, with a quick check"


@pytest.mark.asyncio
async def test_fake_ched_stays_critical_and_the_chred_domain_is_red():
    data = await _verify(
        _fake_ched_payload(),
        _fake_ched_request(),
        [
            SearchResult(
                "CHED Regional Office VI",
                "https://ched.gov.ph",
                "Official site of the Commission on Higher Education.",
                0.9,
            )
        ],
    )

    items = _items_by_label(data)
    channel = items["Channel Match"]

    # The model's Channel Match check said green; the facts said government,
    # outlook, and a lookalike. The code's card wins.
    assert channel["status"] == "red"
    assert channel["escalation"] == "government"
    assert channel["source_url"] == "https://ched.gov.ph"
    assert "recruitment.chred@outlook.com" in channel["explanation"]
    assert "chred-region6.org" in channel["explanation"]
    assert "ched.gov.ph" in channel["explanation"]

    # Two high fee findings (80) plus one refuted Channel Match (25), capped at
    # 100. The model tried to say low/0.
    assert data["riskLevel"] == "critical"
    assert data["riskScore"] == 100

    # The reader-visible half. `critical` is the one level whose headline is the
    # flat stop, and it needs a combined score above 75 - which is what two
    # high fee findings plus a refuted government channel reaches. The mapping
    # is pinned in
    # `entrypoints/sidepanel/components/report/verdictCopy.test.ts`.
    assert _headline_for(data["riskLevel"]) == "Do not proceed"


@pytest.mark.asyncio
async def test_a_posting_with_two_channels_tests_both():
    """The CHED shape, offline: the employer's own address beside a free-mail one.

    The flyer offered `hrmo6@ched.gov.ph` and `recruitment.ched@outlook.com`
    side by side. With one slot, the model was handed one channel and the
    other went untested — and a rule satisfied by the channel that looks
    legitimate is satisfied by nothing.

    Two things have to hold. The **prompt** must carry both channels, or the
    model cannot report the second one. And the **code** must still read the
    free-mail channel as a contradiction while the `.gov.ph` one is the
    employer's own — a matching channel is not an amnesty for the one beside
    it.
    """
    prompt_holder: dict = {}

    def _capture(messages, **kwargs):
        prompt_holder["prompt"] = "\n".join(m["content"] for m in messages)
        return json.dumps(_two_channel_payload())

    with (
        patch(
            "app.routers.scan.search",
            return_value=SearchOutcome(
                results=[
                    SearchResult(
                        "CHED Regional Office VI",
                        "https://ched.gov.ph",
                        "Official site of the Commission on Higher Education.",
                        0.9,
                    )
                ],
                ok=True,
            ),
        ),
        patch("app.routers.scan.chat", side_effect=_capture),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/verify", json=_two_channel_request())

    assert resp.status_code == 200
    data = _result(resp)

    # The prompt carried both channels. A one-slot request cannot produce
    # this string, so this is the port's actual new capability.
    prompt = prompt_holder["prompt"]
    assert "hrmo6@ched.gov.ph" in prompt, prompt[-600:]
    assert "recruitment.ched@outlook.com" in prompt, prompt[-600:]

    # And the posting's own claim that it is a government office reached the
    # model, so `government_claim` is answerable from the posting's words
    # rather than from the model's own reading. It opens no category.
    assert "CLAIMED_TYPE" in prompt, prompt[-600:]

    # And the code still read the free-mail one as a contradiction, while
    # the `.gov.ph` one is the employer's own channel.
    channel = _items_by_label(data)["Channel Match"]
    assert channel["status"] == "red", channel
    assert channel["escalation"] == "government", channel
    assert "recruitment.ched@outlook.com" in channel["explanation"]


@pytest.mark.asyncio
async def test_a_fee_plus_a_free_email_is_high_but_not_do_not_proceed():
    """The combination rule escalates the card, not the headline past `high`.

    One high fee (40) plus the refuted Channel Match (25) is 65: "Do not proceed
    without checking first", not "Do not proceed". That distinction is the reason
    the strong-channel floor exists separately and needs 76 for critical.
    """
    payload = _knollridges_payload()
    payload["channel_match"]["official_channels"] = []
    payload["channel_match"]["source_url"] = ""
    payload["channel_match"]["source_title"] = ""
    payload["anomaly_assessments"] = [
        {
            "index": 1,
            "status": "yellow",
            "finding": "The results do not mention this category.",
            "source_title": "",
            "source_url": "",
        }
    ]

    data = await _verify(
        payload,
        {
            "company_name": "Knollridges Inc.",
            "job_summary": "Send your resume to yvonne.knollridges@gmail.com.",
            "attributes": {
                "CONTACT_METHOD": "Email yvonne.knollridges@gmail.com",
            },
            "anomalies": [
                {
                    "flag": "Mandatory application fee",
                    "reasoning": "The poster asks for a fee.",
                    "severity": "high",
                    "code": "FEE_MANDATORY",
                }
            ],
        },
        [
            SearchResult(
                "Knollridges",
                "https://knollridges.com.ph",
                "Knollridges is a recruitment firm.",
                0.9,
            )
        ],
    )

    channel = _items_by_label(data)["Channel Match"]

    assert channel["status"] == "red"
    assert channel["escalation"] == "free_email_with_findings"
    assert data["riskLevel"] == "high"
    assert data["riskScore"] == 65


@pytest.mark.asyncio
async def test_a_stale_fee_does_not_escalate_a_free_email():
    """The combination rule reads active findings, not stale ones.

    A fee the employer's own page states is accounted for: the stale card renders
    and the 40 points leave the posting score. It must also stop being the
    independent finding that turns a free email into a red combination, or the
    same retired finding would keep 25 points on the channel side.
    """
    payload = _knollridges_payload()
    payload["channel_match"]["official_channels"] = []
    payload["channel_match"]["source_url"] = ""
    payload["channel_match"]["source_title"] = ""
    payload["anomaly_assessments"] = [
        {
            "index": 1,
            "status": "stale",
            "finding": "The employer's own careers page states the exam fee.",
            "source_title": "Knollridges",
            "source_url": "https://knollridges.com.ph",
        }
    ]

    data = await _verify(
        payload,
        {
            "company_name": "Knollridges Inc.",
            "job_summary": "Send your resume to yvonne.knollridges@gmail.com.",
            "attributes": {
                "CONTACT_METHOD": "Email yvonne.knollridges@gmail.com",
            },
            "anomalies": [
                {
                    "flag": "Mandatory application fee",
                    "reasoning": "The poster asks for a fee.",
                    "severity": "high",
                    "code": "FEE_MANDATORY",
                }
            ],
        },
        [
            SearchResult(
                "Knollridges",
                "https://knollridges.com.ph",
                "Knollridges is a recruitment firm.",
                0.9,
            )
        ],
    )

    channel = _items_by_label(data)["Channel Match"]

    assert channel["status"] == "yellow"
    assert channel["escalation"] == "free_email"
    assert data["riskLevel"] == "low"
    assert data["riskScore"] == 0
    assert data["scoreBreakdown"]["stale_excluded"] == 1


@pytest.mark.asyncio
async def test_an_unretrieved_official_channel_cannot_keep_a_red_card():
    """The official side is a claim about the employer, and it needs a result.

    A model can copy `ched.gov.ph` from the posting itself and cite a URL the
    search never returned. The citation is dropped, the official side is dropped,
    and the government claim becomes a yellow card rather than a red one.
    """
    payload = _fake_ched_payload()
    payload["channel_match"] = {
        "printed_channels": ["recruitment@example.com"],
        "official_channels": ["ched.gov.ph"],
        "government_claim": True,
        "finding": "The posting gives recruitment@example.com.",
        "source_title": "Not retrieved",
        "source_url": "https://not-in-the-results.example/apply",
    }

    data = await _verify(
        payload,
        {
            "company_name": "CHED Regional Office VI",
            "job_summary": "Email recruitment@example.com.",
            "attributes": {"CONTACT_METHOD": "Email recruitment@example.com"},
            "anomalies": [
                {
                    "flag": "Vague employer",
                    "reasoning": "The office name is not on the site.",
                    "severity": "mid",
                }
            ],
        },
        [
            SearchResult(
                "CHED Regional Office VI",
                "https://ched.gov.ph",
                "Official site of the Commission on Higher Education.",
                0.9,
            )
        ],
    )

    channel = _items_by_label(data)["Channel Match"]

    assert channel["status"] == "yellow"
    assert channel["source_url"] == ""
    # The explanation may still say the posting claims to be a government office;
    # it must not assert the unretrieved official domain.
    assert "ched.gov.ph" not in channel["explanation"]
    assert data["riskLevel"] == "low"

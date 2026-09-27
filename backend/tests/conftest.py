import os
import socket
import pytest
from unittest.mock import patch

# Set test env before importing the app
os.environ["CLIENT_SECRET_KEY"] = "test-secret-key"

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services import ddg_search, lm_client

# Captured at import time, before any patching, so tests can assert that a
# boundary is swapped for something other than the real implementation.
REAL_AI_STREAM = lm_client.chat_stream_pieces
REAL_AI_CHAT = lm_client.chat
REAL_VERIFY_COMPANY = ddg_search.verify_company
REAL_SEARCH_JOB_POSTING = ddg_search.search_job_posting


# ── Offline enforcement ────────────────────────────────────────────────────
#
# AGENTS.md: the default suite must make no live OpenRouter/DuckDuckGo/SEC/DNS
# calls. Two layers enforce it:
#   1. `_offline_ai_and_search` swaps every AI/search entry point for a
#      deterministic fake, so endpoint tests never reach a provider.
#   2. `_block_external_dns` refuses to resolve any non-loopback host, so an
#      unmocked call fails loudly instead of spending credits or quota.

FAKE_COMPANY_NAME = "Acme Corporation"
# The trailing "(" is deliberate: extract_company_name's character class stops
# there, so the captured company name is exactly "Acme Corporation".
FAKE_JOB_SUMMARY = f"Software Engineer at {FAKE_COMPANY_NAME} (offline test fixture)."
FAKE_REPORT = "OFFLINE FAKE REPORT"
FAKE_RECOMMENDATION = "OFFLINE FAKE RECOMMENDATION"

# Only these labels survive _parse_custom; any other keyword resets its
# matched_any flag and makes the parser return None. The summary contains
# "at Acme Corporation" so extract_company_name finds it and the scan response
# carries a verification_context, exercising that guardrail offline.
FAKE_SCAN_RESPONSE = (
    "VALID: true\n"
    "RED FLAG: Application fee requested | Candidates are asked to pay a processing fee before being considered | high\n"
    "JOB SUMMARY:\n"
    f"{FAKE_JOB_SUMMARY}\n"
    "END JOB SUMMARY\n"
)

FAKE_RESUME_RESPONSE = (
    "SKILLS: Python, SQL\n"
    "EXPERIENCE_YEARS: 2\n"
    "JOB_TITLES: Developer\n"
    "INDUSTRIES: IT\n"
    "SUMMARY:\nOFFLINE FAKE RESUME\nEND SUMMARY\n"
)

FAKE_MATCH_RESPONSE = (
    "JOB_ID: 1\n"
    "SCORE: 80\n"
    "LABEL: Strong match\n"
    "SKILL_GAPS: Kubernetes\n"
    "MATCHED_SKILLS: Python\n"
    "REASONING: OFFLINE FAKE REASONING\n"
    "EXPERIENCE_FIT: Good\n"
    "INDUSTRY_FIT: Good\n"
    "RECOMMENDED_ACTIONS: Apply\n"
    "END JOB\n"
)

FAKE_VERIFY_RESPONSE = (
    "VERIFY: Company Name STATUS: green DETAIL: OFFLINE FAKE DETAIL END VERIFY\n"
    f"REPORT: {FAKE_REPORT} END REPORT\n"
    f"RECOMMENDATION: {FAKE_RECOMMENDATION} END RECOMMENDATION\n"
)


class _FakeDDGS:
    """Stand-in for the ddgs DDGS context manager.

    A bare MagicMock is iterable-but-empty, so every search looked like a total
    retrieval failure. That made search paths report 'throttled' and, because
    retries back off in real time, added ~27s to the suite. Returning library-
    shaped rows keeps the offline tests on the success path and fast, while
    individual tests still patch `_ddg_once` to exercise the failure paths.
    """

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def text(self, query, max_results=5, **kwargs):
        return [
            {
                "title": f"OFFLINE FAKE RESULT for {query}",
                "href": "https://example.invalid/",
                "body": "OFFLINE FAKE SNIPPET. No network was used.",
            }
        ]


class ExternalNetworkBlocked(RuntimeError):
    """Raised when a test tries to resolve a non-loopback host."""


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", ""}
_real_getaddrinfo = socket.getaddrinfo


def _is_loopback(host) -> bool:
    text = host.decode() if isinstance(host, bytes) else host
    if not isinstance(text, str):
        return True
    return text.split("%")[0] in _LOOPBACK_HOSTS


@pytest.fixture(autouse=True, scope="session")
def _block_external_dns():
    """Fail fast on any attempt to reach a host outside the machine."""
    def guarded_getaddrinfo(host, *args, **kwargs):
        if not _is_loopback(host):
            raise ExternalNetworkBlocked(
                f"Live network access to {host!r} is blocked in tests. "
                "Mock the AI/search boundary instead of calling a real provider."
            )
        return _real_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = guarded_getaddrinfo
    yield
    socket.getaddrinfo = _real_getaddrinfo


@pytest.fixture(autouse=True)
def _offline_ai_and_search():
    """Replace AI, search, and DNS boundaries with deterministic fakes.

    Patches `app.routers.scan` because every flow resolves these lazily:
    `runtime.get_chat_stream`, `get_chat`, `get_verify_company`, etc. are
    lambdas that read the router module's globals at call time. Per-test
    `patch(...)` calls still win, since they are applied after this fixture.

    Also patches `app.services.lm_client` so a direct call to `chat_json`,
    `chat_resume`, `chat_match`, or `chat_custom` — which reach the provider
    through lm_client's own `chat` global — cannot escape the fake.
    """
    async def fake_stream(messages, max_tokens=None, temperature=None, top_p=None):
        for piece in (FAKE_SCAN_RESPONSE, FAKE_RESUME_RESPONSE, FAKE_MATCH_RESPONSE):
            yield piece

    async def fake_chat(messages, max_tokens=None, temperature=None, top_p=None, **kwargs):
        return FAKE_VERIFY_RESPONSE

    with (
        patch("app.routers.scan.chat_stream_pieces", fake_stream),
        patch("app.routers.scan.chat", fake_chat),
        patch("app.services.lm_client.chat_stream_pieces", fake_stream),
        patch("app.services.lm_client.chat", fake_chat),
        patch("app.routers.scan.search_job_posting", return_value=""),
        patch("app.routers.scan.search_job_posting_data", return_value={"company_name": None, "results": {}}),
        patch("app.routers.scan.verify_company", return_value=""),
        patch("app.routers.scan.verify_emails_in_text", return_value=[]),
        patch("app.services.ddg_search.DDGS", _FakeDDGS),
    ):
        yield


@pytest.fixture(autouse=True)
def _set_test_secret():
    """Ensure the auth module uses the test secret key."""
    import app.core.auth as auth_mod
    auth_mod.EXPECTED_KEY = "test-secret-key"
    yield
    auth_mod.EXPECTED_KEY = ""


@pytest.fixture
def scan_payload():
    """Minimal valid body for POST /api/scan."""
    return {"images_base64": ["dGVzdA=="], "language": "english"}


@pytest.fixture
def text_payload():
    """Minimal valid body for POST /api/scan-text."""
    return {"text": "Software Engineer at Acme Corp, salary 50k monthly"}


@pytest.fixture
def resume_payload():
    """Minimal valid body for POST /api/analyze-resume."""
    return {"file_base64": "dGVzdA==", "file_type": "txt"}


@pytest.fixture
def match_payload():
    """Minimal valid body for POST /api/match-resume."""
    return {
        "resume": {
            "skills": ["Python"],
            "experience_years": 2,
            "job_titles": ["Developer"],
            "industries": ["IT"],
            "summary": "Test",
        },
        "jobs": [{"id": "1", "title": "Dev", "summary": "Test job"}],
    }

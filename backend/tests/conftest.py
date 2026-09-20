import os
import pytest
from unittest.mock import patch

# Set test env before importing the app
os.environ["CLIENT_SECRET_KEY"] = "test-secret-key"

from httpx import AsyncClient, ASGITransport
from app.main import app


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

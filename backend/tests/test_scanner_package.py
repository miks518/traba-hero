import asyncio
import importlib
import importlib.util
import inspect
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import Request

from app.models.schemas import (
    JobForMatch,
    MatchRequest,
    ResumeAnalysisRequest,
    ResumeData,
    ScanRequest,
    VerifyRequest,
)


MODULE_NAMES = (
    "prompts",
    "dependencies",
    "sse",
    "scan_result",
    "scan_flow",
    "resume_flow",
    "match_flow",
    "verification_prompt",
    "verification_parser",
    "risk_calculator",
    "verification_flow",
)

PACKAGE_EXPORTS = (
    "FALLBACK_SYSTEM_PROMPT",
    "SCAN_OUTPUT_FORMAT",
    "IMAGE_SCAN_INSTRUCTION",
    "TEXT_SCAN_INSTRUCTION",
    "RESUME_INSTRUCTION",
    "MATCH_INSTRUCTION",
    "VERIFY_SYSTEM_PROMPT",
    "load_system_prompt",
    "load_resume_prompt",
    "load_match_prompt",
    "_red_flags",
    "_language_instruction",
    "_scan_response",
    "_sse",
    "_VALID_LINE_RE",
    "_scan_event_stream",
    "_extract_resume_text",
    "_resume_event_stream",
    "_match_event_stream",
    "_calculate_risk_score_from_verify",
    "_build_verify_prompt",
    "_parse_verification_result",
    "_parse_verify_section",
)

PURE_REEXPORTS = (
    "FALLBACK_SYSTEM_PROMPT",
    "SCAN_OUTPUT_FORMAT",
    "IMAGE_SCAN_INSTRUCTION",
    "TEXT_SCAN_INSTRUCTION",
    "RESUME_INSTRUCTION",
    "MATCH_INSTRUCTION",
    "VERIFY_SYSTEM_PROMPT",
    "load_system_prompt",
    "load_resume_prompt",
    "load_match_prompt",
    "_red_flags",
    "_language_instruction",
    "_sse",
    "_VALID_LINE_RE",
    "_calculate_risk_score_from_verify",
    "_build_verify_prompt",
    "_parse_verification_result",
    "_parse_verify_section",
)

class _FakeLimiter:
    def __init__(self):
        self.acquired = 0
        self.released = 0

    async def acquire(self):
        self.acquired += 1

    def release(self):
        self.released += 1


def _blocking_provider(state):
    async def stream(messages, max_tokens=None, temperature=None, top_p=None):
        try:
            yield "VALID: true\n"
            await asyncio.Event().wait()
        finally:
            state["closed"] = True

    return stream


EXPECTED_ENDPOINT_PARAMETERS = {
    "scan": ("req", "request", "_auth"),
    "scan_text": ("req", "request", "_auth"),
    "analyze_resume_endpoint": ("req", "request", "_auth"),
    "match_resume_endpoint": ("req", "request", "_auth"),
    "verify_job": ("req", "request", "_auth"),
}

EXPECTED_SIGNATURES = {
    "load_system_prompt": "() -> str",
    "load_resume_prompt": "() -> str",
    "load_match_prompt": "() -> str",
    "_extract_resume_text": "(file_base64: str, file_type: str) -> str",
    "_calculate_risk_score_from_verify": "(items: list[app.models.schemas.VerificationItem]) -> tuple[int | None, str | None]",
    "_build_verify_prompt": "(req: app.models.schemas.VerifyRequest, search_context: str = '') -> str",
    "_parse_verification_result": "(text: str) -> list[app.models.schemas.VerificationItem]",
    "_parse_verify_section": "(text: str, name: str) -> str",
    "_red_flags": "(flags: list) -> list[app.models.schemas.RedFlag]",
    "_language_instruction": "(language: str) -> str",
    "_scan_response": "(result: dict, company_name: str = '') -> app.models.schemas.ScanResponse",
    "_sse": "(data: dict) -> str",
    "_scan_event_stream": "(messages: list, max_tokens: int | None = None, company_data: dict | None = None, original_text: str = '', endpoint: str = 'scan') -> str",
    "_resume_event_stream": "(messages: list, max_tokens: int | None = None, endpoint: str = 'resume') -> str",
    "_match_event_stream": "(messages: list, max_tokens: int | None = None, endpoint: str = 'match') -> str",
}


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_scanner_support_module_exists(module_name):
    module_path = f"app.services.scanner.{module_name}"
    try:
        module_spec = importlib.util.find_spec(module_path)
    except ModuleNotFoundError:
        module_spec = None
    assert module_spec is not None


def test_scanner_package_exports_expected_api():
    scanner = importlib.import_module("app.services.scanner")
    assert set(PACKAGE_EXPORTS) <= set(scanner.__all__)
    assert all(hasattr(scanner, name) for name in PACKAGE_EXPORTS)


@pytest.mark.parametrize("name", PURE_REEXPORTS)
def test_scan_facade_reexports_package_symbols(name):
    scanner = importlib.import_module("app.services.scanner")
    scan_router = importlib.import_module("app.routers.scan")
    assert getattr(scan_router, name) is getattr(scanner, name)


@pytest.mark.parametrize("name", ("_scan_event_stream", "_resume_event_stream", "_match_event_stream"))
def test_scan_facade_uses_package_stream_functions_directly(name):
    scanner = importlib.import_module("app.services.scanner")
    scan_router = importlib.import_module("app.routers.scan")
    assert getattr(scan_router, name) is getattr(scanner, name)


@pytest.mark.parametrize("name, expected", EXPECTED_SIGNATURES.items())
def test_scan_facade_signatures_are_unchanged(name, expected):
    scan_router = importlib.import_module("app.routers.scan")
    assert str(inspect.signature(getattr(scan_router, name))) == expected


@pytest.mark.parametrize("name, expected", EXPECTED_ENDPOINT_PARAMETERS.items())
def test_scan_endpoint_parameter_names_are_unchanged(name, expected):
    scan_router = importlib.import_module("app.routers.scan")
    signature = inspect.signature(getattr(scan_router, name))
    assert tuple(signature.parameters) == expected
    assert signature.return_annotation is inspect.Signature.empty


def test_package_scan_response_signature_remains_unchanged():
    scanner = importlib.import_module("app.services.scanner")
    assert str(inspect.signature(scanner._scan_response)) == "(result: dict, company_name: str = '') -> app.models.schemas.ScanResponse"


def test_scanner_prompt_loaders_resolve_backend_prompt_files():
    scanner = importlib.import_module("app.services.scanner")
    backend_root = Path(__file__).resolve().parents[1]
    expected_prompts = {
        "load_system_prompt": "SYSTEM_PROMPT.md",
        "load_resume_prompt": "RESUME_PROMPT.md",
        "load_match_prompt": "MATCH_PROMPT.md",
    }
    for loader_name, prompt_name in expected_prompts.items():
        expected = (backend_root / prompt_name).read_text(encoding="utf-8").strip()
        assert getattr(scanner, loader_name)() == expected


def test_scanner_risk_calculator_preserves_weighted_score():
    scanner = importlib.import_module("app.services.scanner")
    items = [
        scanner.VerificationItem(label="Company Existence", status="red", explanation="Not found"),
        scanner.VerificationItem(label="SEC Registration", status="yellow", explanation="Unclear"),
    ]
    # Company Existence red = 40, SEC Registration yellow = 25 // 2 = 12, of 100.
    assert scanner._calculate_risk_score_from_verify(items) == (52, "high")


def test_scanner_sse_encoder_preserves_wire_format():
    scanner = importlib.import_module("app.services.scanner")
    assert scanner._sse({"type": "progress"}) == 'data: {"type": "progress"}\n\n'


@pytest.mark.parametrize("name", ("base64", "io", "re", "zipfile", "Path", "HTTPException", "_time"))
def test_scan_facade_preserves_legacy_module_bindings(name):
    scan_router = importlib.import_module("app.routers.scan")
    assert hasattr(scan_router, name)


@pytest.mark.asyncio
async def test_scan_facade_closes_provider_stream_before_returning():
    scan_router = importlib.import_module("app.routers.scan")
    provider_closed = False

    async def fake_stream(messages, max_tokens=None, temperature=None, top_p=None):
        nonlocal provider_closed
        try:
            yield "VALID: true\n"
            await asyncio.Event().wait()
        finally:
            provider_closed = True

    with patch("app.routers.scan.chat_stream_pieces", fake_stream):
        stream = scan_router._scan_event_stream([], endpoint="cleanup-test")
        assert "Preparing request" in await anext(stream)
        assert "Sent to AI" in await anext(stream)
        await stream.aclose()

    assert provider_closed is True


@pytest.mark.asyncio
async def test_scan_facade_resolves_chat_dependency_at_use_time():
    scan_router = importlib.import_module("app.routers.scan")
    original_called = False
    replacement_called = False

    async def original_stream(messages, max_tokens=None, temperature=None, top_p=None):
        nonlocal original_called
        original_called = True
        yield "VALID: true\n"

    async def replacement_stream(messages, max_tokens=None, temperature=None, top_p=None):
        nonlocal replacement_called
        replacement_called = True
        yield "VALID: true\n"

    with patch("app.routers.scan.chat_stream_pieces", original_stream):
        stream = scan_router._scan_event_stream([], endpoint="patch-timing-test")
        assert "Preparing request" in await anext(stream)
        with patch("app.routers.scan.chat_stream_pieces", replacement_stream):
            assert "Sent to AI" in await anext(stream)
        await stream.aclose()

    assert replacement_called is True
    assert original_called is False


@pytest.mark.asyncio
async def test_verify_facade_releases_limiter_before_closing_returns():
    scan_router = importlib.import_module("app.routers.scan")

    class FakeLimiter:
        def __init__(self):
            self.acquired = 0
            self.released = 0

        async def acquire(self):
            self.acquired += 1

        def release(self):
            self.released += 1

    limiter = FakeLimiter()
    with patch("app.routers.scan.ai_limiter", limiter):
        verify_endpoint = scan_router.verify_job.__wrapped__
        response = await verify_endpoint(VerifyRequest(), Request({"type": "http"}))
        stream = response.body_iterator
        assert "Preparing verification" in await anext(stream)
        await stream.aclose()

    assert limiter.acquired == 1
    assert limiter.released == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint_name", "stream_name", "request_factory"),
    (
        ("scan", "_scan_event_stream", lambda: ScanRequest(images_base64=["dGVzdA=="])),
        ("analyze_resume_endpoint", "_resume_event_stream", lambda: ResumeAnalysisRequest(file_base64="dGVzdA==", file_type="txt")),
        ("match_resume_endpoint", "_match_event_stream", lambda: MatchRequest(resume=ResumeData(skills=["Python"]), jobs=[JobForMatch(id="1", title="Developer")])),
    ),
)
async def test_endpoint_releases_limiter_when_stream_construction_fails(endpoint_name, stream_name, request_factory):
    scan_router = importlib.import_module("app.routers.scan")
    limiter = _FakeLimiter()
    with patch("app.routers.scan.ai_limiter", limiter), \
         patch(f"app.routers.scan.{stream_name}", side_effect=RuntimeError("stream construction failed")):
        endpoint = getattr(scan_router, endpoint_name).__wrapped__
        response = await endpoint(request_factory(), Request({"type": "http"}))
        with pytest.raises(RuntimeError, match="stream construction failed"):
            await anext(response.body_iterator)

    assert limiter.acquired == 1
    assert limiter.released == 1


@pytest.mark.asyncio
async def test_scan_endpoint_closes_inner_stream_before_aclose_returns():
    scan_router = importlib.import_module("app.routers.scan")
    state = {"closed": False}
    limiter = _FakeLimiter()

    with patch("app.routers.scan.chat_stream_pieces", _blocking_provider(state)), \
         patch("app.routers.scan.ai_limiter", limiter):
        endpoint = scan_router.scan.__wrapped__
        response = await endpoint(ScanRequest(images_base64=["dGVzdA=="]), Request({"type": "http"}))
        stream = response.body_iterator
        assert "Preparing request" in await anext(stream)
        assert "Sent to AI" in await anext(stream)
        await stream.aclose()

    assert state["closed"] is True
    assert limiter.released == 1


@pytest.mark.asyncio
async def test_resume_endpoint_closes_inner_stream_before_aclose_returns():
    scan_router = importlib.import_module("app.routers.scan")
    state = {"closed": False}
    limiter = _FakeLimiter()

    with patch("app.routers.scan.chat_stream_pieces", _blocking_provider(state)), \
         patch("app.routers.scan.ai_limiter", limiter):
        endpoint = scan_router.analyze_resume_endpoint.__wrapped__
        response = await endpoint(ResumeAnalysisRequest(file_base64="dGVzdA==", file_type="txt"), Request({"type": "http"}))
        stream = response.body_iterator
        assert "Preparing request" in await anext(stream)
        assert "Sent to AI" in await anext(stream)
        await stream.aclose()

    assert state["closed"] is True
    assert limiter.released == 1


@pytest.mark.asyncio
async def test_match_endpoint_closes_inner_stream_before_aclose_returns():
    scan_router = importlib.import_module("app.routers.scan")
    state = {"closed": False}
    limiter = _FakeLimiter()
    request = MatchRequest(
        resume=ResumeData(skills=["Python"]),
        jobs=[JobForMatch(id="1", title="Developer", summary="Build software")],
    )

    with patch("app.routers.scan.chat_stream_pieces", _blocking_provider(state)), \
         patch("app.routers.scan.ai_limiter", limiter):
        endpoint = scan_router.match_resume_endpoint.__wrapped__
        response = await endpoint(request, Request({"type": "http"}))
        stream = response.body_iterator
        assert "Preparing request" in await anext(stream)
        assert "Sent to AI" in await anext(stream)
        await stream.aclose()

    assert state["closed"] is True
    assert limiter.released == 1


def test_scan_response_uses_facade_patched_company_validator():
    scan_router = importlib.import_module("app.routers.scan")
    with patch("app.routers.scan.is_valid_company_name", return_value=False):
        response = scan_router._scan_response({"valid": True}, "ACME")
    assert response.company_name is None

"""Tests for suppressing the /health access log (Task 3.1)."""
import logging

from app.main import DropHealthAccessLogs


def _access_record(*args):
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s HTTP/%s" %s',
        args=args,
        exc_info=None,
    )


def test_health_access_record_is_dropped():
    record = _access_record("127.0.0.1:5000", "GET", "/health", "1.1", 200)
    assert DropHealthAccessLogs().filter(record) is False


def test_health_access_record_with_query_string_is_dropped():
    record = _access_record("127.0.0.1:5000", "GET", "/health?verbose=1", "1.1", 200)
    assert DropHealthAccessLogs().filter(record) is False


def test_scan_access_record_is_kept():
    record = _access_record("127.0.0.1:5000", "POST", "/api/scan", "1.1", 200)
    assert DropHealthAccessLogs().filter(record) is True


def test_similar_path_is_kept():
    record = _access_record("127.0.0.1:5000", "GET", "/healthz", "1.1", 200)
    assert DropHealthAccessLogs().filter(record) is True


def test_unrelated_record_without_tuple_args_is_kept():
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Uvicorn running on port 8000",
        args=(),
        exc_info=None,
    )
    assert DropHealthAccessLogs().filter(record) is True


def test_filter_is_installed_on_uvicorn_access_logger():
    filters = logging.getLogger("uvicorn.access").filters
    assert any(isinstance(f, DropHealthAccessLogs) for f in filters)

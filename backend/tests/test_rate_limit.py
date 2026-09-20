"""Tests for reverse-proxy safe rate limiting (Task 1.3)."""
import pytest
from unittest.mock import MagicMock
from app.rate_limit import _get_client_ip


def _make_request(headers: dict = None, client_host: str = "127.0.0.1"):
    """Create a mock Starlette Request with given headers and client IP."""
    request = MagicMock()
    # Starlette headers are case-insensitive; use lowercase to match code
    request.headers = {k.lower(): v for k, v in (headers or {}).items()}
    request.client.host = client_host
    return request


def test_no_proxy_headers_returns_client_host():
    request = _make_request(client_host="192.168.1.1")
    assert _get_client_ip(request) == "192.168.1.1"


def test_x_forwarded_for_single_ip():
    request = _make_request(headers={"X-Forwarded-For": "203.0.113.50"})
    assert _get_client_ip(request) == "203.0.113.50"


def test_x_forwarded_for_multiple_ips():
    request = _make_request(headers={"X-Forwarded-For": "203.0.113.50, 70.41.3.18, 150.172.238.178"})
    assert _get_client_ip(request) == "203.0.113.50"


def test_x_real_ip():
    request = _make_request(headers={"X-Real-IP": "198.51.100.22"})
    assert _get_client_ip(request) == "198.51.100.22"


def test_x_forwarded_for_takes_priority_over_x_real_ip():
    request = _make_request(headers={
        "X-Forwarded-For": "203.0.113.50",
        "X-Real-IP": "198.51.100.22",
    })
    assert _get_client_ip(request) == "203.0.113.50"


def test_x_forwarded_for_with_whitespace():
    request = _make_request(headers={"X-Forwarded-For": "  203.0.113.50  , 70.41.3.18"})
    assert _get_client_ip(request) == "203.0.113.50"

from starlette.datastructures import Headers
from starlette.requests import Request

from app.core.geofence import get_client_ip, is_ip_allowed


def _make_request(headers=None, client_host=None):
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": client_host,
    }
    if headers:
        scope["headers"] = [
            (key.lower().encode("latin-1"), value.encode("latin-1"))
            for key, value in headers.items()
        ]
    return Request(scope)


def test_get_client_ip_prefers_first_forwarded_ip():
    request = _make_request({"x-forwarded-for": "203.0.113.7, 10.0.0.5"})
    assert get_client_ip(request) == "203.0.113.7"


def test_get_client_ip_handles_ipv6_brackets():
    request = _make_request({"x-forwarded-for": "[2001:db8::1], 10.0.0.5"})
    assert get_client_ip(request) == "2001:db8::1"


def test_is_ip_allowed_rejects_invalid_inputs():
    assert is_ip_allowed(None, "127.0.0.0/8") is False
    assert is_ip_allowed("not-an-ip", "127.0.0.0/8") is False
    assert is_ip_allowed("127.0.0.1", "") is False


def test_is_ip_allowed_matches_allowed_networks():
    assert is_ip_allowed("127.0.0.1", "127.0.0.0/8,::1/128") is True
    assert is_ip_allowed("::1", "127.0.0.0/8,::1/128") is True
    assert is_ip_allowed("8.8.8.8", "127.0.0.0/8,::1/128") is False

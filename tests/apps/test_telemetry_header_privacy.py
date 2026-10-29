"""验证平台凭证不会通过请求遥测进入 Span。"""

import json
from unittest.mock import MagicMock

import pytest

from agentkit.apps.agent_server_app.telemetry import telemetry as server_telemetry
from agentkit.apps.simple_app.telemetry import telemetry as simple_telemetry
from agentkit.apps.telemetry_headers import telemetry_request_headers


@pytest.mark.parametrize(
    "name",
    [
        "Authorization", "Cookie", "X-Api-Key", "X-Faas-Access-Key-Id",
        "X-Faas-Secret-Access-Key", "X-Faas-Session-Token", "X-Session-Id",
        "X-Ve-TIP-Token", "X-Future-Credential", "Baggage", "Tracestate",
    ],
)
@pytest.mark.parametrize("entry", ["server", "simple"])
def test_request_telemetry_drops_credentials_even_without_middleware(name, entry):
    span = MagicMock()
    headers = {name: "synthetic-secret-do-not-export", "content-type": "application/json"}
    if entry == "server":
        server_telemetry.trace_agent_server("POST /invoke", span, headers, "")
    else:
        simple_telemetry.trace_agent(lambda: None, span, {}, headers)
    attributes = {
        call.kwargs["key"]: call.kwargs["value"]
        for call in span.set_attribute.call_args_list
    }
    assert json.loads(attributes["gen_ai.request.headers"]) == {
        "content-type": "application/json"
    }
    assert "synthetic-secret-do-not-export" not in json.dumps(attributes)
    assert headers[name] == "synthetic-secret-do-not-export"


def test_allowlisted_correlation_and_media_type_survive_without_mutating_headers():
    headers = {
        "Traceparent": "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
        "Content-Type": "application/json; private_parameter=synthetic-secret",
        "X-Request-Id": "request-123",
        "X-Faas-Request-Id": "faas-request-123",
        "unknown": "synthetic-secret",
    }
    before = dict(headers)
    assert telemetry_request_headers(headers) == {
        "traceparent": headers["Traceparent"],
        "content-type": "application/json",
        "x-request-id": "request-123",
        "x-faas-request-id": "faas-request-123",
    }
    assert headers == before


@pytest.mark.parametrize(
    "headers",
    [
        {"content-type": "application/json\r\nAuthorization: secret"},
        {"traceparent": "invalid-secret"},
        {"x-request-id": "a" * 129},
        {"x-faas-request-id": "request?token=secret"},
        {"content-type": None},
    ],
)
def test_invalid_or_unbounded_header_values_are_not_exported(headers):
    assert telemetry_request_headers(headers) == {}

# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit guards for ``AgentkitTelemetryHTTPMiddleware``.

The middleware is a pure ASGI callable: it wraps another ASGI app, opens a
telemetry span for HTTP requests, strips sensitive headers before handing them
to the telemetry singleton, and closes the span exactly once when the response
body finishes (or when the wrapped app raises). These tests drive ``__call__``
directly with hand-rolled ``scope``/``receive``/``send`` coroutines and spy on
the module-level ``telemetry`` singleton, so no real OTEL exporter, socket, or
uvicorn server is involved.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from agentkit.apps.agent_server_app import middleware as middleware_mod
from agentkit.apps.agent_server_app.middleware import AgentkitTelemetryHTTPMiddleware


@pytest.fixture
def fake_telemetry(monkeypatch):
    """Replace the module-level telemetry singleton with a MagicMock.

    ``tracer.start_span`` must return a usable span object because the real
    middleware feeds it into ``trace.set_span_in_context``; a MagicMock span is
    accepted there without touching a real exporter.
    """

    fake = MagicMock(name="telemetry")
    monkeypatch.setattr(middleware_mod, "telemetry", fake)
    return fake


async def _noop_receive():  # pragma: no cover - never awaited in these tests
    return {"type": "http.request", "body": b"", "more_body": False}


def _make_send_recorder():
    """Return (send_coro, sent_messages) capturing everything sent downstream."""

    sent = []

    async def _send(message):
        sent.append(message)

    return _send, sent


def test_non_http_scope_is_passed_through_without_touching_telemetry(fake_telemetry):
    seen = {}

    async def _app(scope, receive, send):
        seen["scope"] = scope
        seen["receive"] = receive
        seen["send"] = send
        return "app-return-value"

    mw = AgentkitTelemetryHTTPMiddleware(_app)
    scope = {"type": "lifespan"}
    send, _sent = _make_send_recorder()

    result = asyncio.run(mw(scope, _noop_receive, send))

    # The wrapped app is called with the exact same objects, unchanged.
    assert seen["scope"] is scope
    assert seen["receive"] is _noop_receive
    assert seen["send"] is send
    assert result == "app-return-value"

    # No telemetry interaction at all for non-http scopes.
    assert fake_telemetry.mock_calls == []


def test_http_scope_starts_span_and_calls_trace_agent_server(fake_telemetry):
    async def _app(scope, receive, send):
        return None

    mw = AgentkitTelemetryHTTPMiddleware(_app)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/hello",
        "headers": [(b"content-type", b"application/json")],
    }
    send, _sent = _make_send_recorder()

    asyncio.run(mw(scope, _noop_receive, send))

    fake_telemetry.tracer.start_span.assert_called_once_with(name="agent_server_request")
    fake_telemetry.trace_agent_server.assert_called_once()
    kwargs = fake_telemetry.trace_agent_server.call_args.kwargs
    assert kwargs["func_name"] == "GET /hello"
    assert kwargs["text"] == ""
    assert kwargs["span"] is fake_telemetry.tracer.start_span.return_value
    assert kwargs["headers"] == {"content-type": "application/json"}


def test_sensitive_headers_are_excluded_before_reaching_telemetry(fake_telemetry):
    async def _app(scope, receive, send):
        return None

    mw = AgentkitTelemetryHTTPMiddleware(_app)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/chat",
        "headers": [
            (b"authorization", b"Bearer secret-token"),
            (b"token", b"another-secret"),
            (b"x-security-token", b"sts-session-token"),
            (b"cookie", b"session=abc"),
            (b"x-api-key", b"key-123"),
            (b"content-type", b"text/plain"),
        ],
    }
    send, _sent = _make_send_recorder()

    asyncio.run(mw(scope, _noop_receive, send))

    kwargs = fake_telemetry.trace_agent_server.call_args.kwargs
    headers = kwargs["headers"]
    assert "authorization" not in headers
    assert "token" not in headers
    assert "x-security-token" not in headers
    assert "cookie" not in headers
    assert "x-api-key" not in headers
    # The non-sensitive header survives with its decoded value.
    assert headers == {"content-type": "text/plain"}


def test_header_exclusion_is_case_insensitive(fake_telemetry):
    async def _app(scope, receive, send):
        return None

    mw = AgentkitTelemetryHTTPMiddleware(_app)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (b"Authorization", b"Bearer x"),
            (b"TOKEN", b"y"),
            (b"X-Custom", b"keep"),
        ],
    }
    send, _sent = _make_send_recorder()

    asyncio.run(mw(scope, _noop_receive, send))

    headers = fake_telemetry.trace_agent_server.call_args.kwargs["headers"]
    # Keys are preserved verbatim; only the lowercased comparison decides exclusion.
    assert "Authorization" not in headers
    assert "TOKEN" not in headers
    assert headers == {"X-Custom": "keep"}


def test_finish_is_called_only_on_final_body_message_not_on_response_start(fake_telemetry):
    async def _app(scope, receive, send):
        # A realistic send sequence: start, then a final body chunk.
        await send({"type": "http.response.start", "status": 200, "headers": []})
        # After the start message, finish must NOT yet have been called.
        assert fake_telemetry.trace_agent_server_finish.call_count == 0
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    mw = AgentkitTelemetryHTTPMiddleware(_app)
    scope = {"type": "http", "method": "GET", "path": "/done", "headers": []}
    send, sent = _make_send_recorder()

    asyncio.run(mw(scope, _noop_receive, send))

    # Exactly one finish, triggered by the final body message.
    fake_telemetry.trace_agent_server_finish.assert_called_once_with(
        path="/done", func_result="", exception=None
    )
    # Both messages were forwarded downstream in order.
    assert [m["type"] for m in sent] == [
        "http.response.start",
        "http.response.body",
    ]


def test_finish_is_not_called_while_more_body_is_true(fake_telemetry):
    async def _app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"chunk", "more_body": True})

    mw = AgentkitTelemetryHTTPMiddleware(_app)
    scope = {"type": "http", "method": "GET", "path": "/stream", "headers": []}
    send, sent = _make_send_recorder()

    asyncio.run(mw(scope, _noop_receive, send))

    # more_body=True means the response is not finished, so no finish call.
    assert fake_telemetry.trace_agent_server_finish.call_count == 0
    # The chunk is still forwarded downstream.
    assert [m["type"] for m in sent] == [
        "http.response.start",
        "http.response.body",
    ]


def test_body_message_without_more_body_key_defaults_to_finished(fake_telemetry):
    async def _app(scope, receive, send):
        # Omitting "more_body" entirely: the middleware defaults it to False,
        # so the response is treated as finished.
        await send({"type": "http.response.body", "body": b"ok"})

    mw = AgentkitTelemetryHTTPMiddleware(_app)
    scope = {"type": "http", "method": "GET", "path": "/nofield", "headers": []}
    send, _sent = _make_send_recorder()

    asyncio.run(mw(scope, _noop_receive, send))

    fake_telemetry.trace_agent_server_finish.assert_called_once_with(
        path="/nofield", func_result="", exception=None
    )


def test_wrapped_app_exception_records_finish_with_exception_and_reraises(fake_telemetry):
    boom = RuntimeError("downstream failure")

    async def _app(scope, receive, send):
        raise boom

    mw = AgentkitTelemetryHTTPMiddleware(_app)
    scope = {"type": "http", "method": "GET", "path": "/boom", "headers": []}
    send, _sent = _make_send_recorder()

    with pytest.raises(RuntimeError, match="downstream failure") as exc_info:
        asyncio.run(mw(scope, _noop_receive, send))

    # The very same exception instance is re-raised.
    assert exc_info.value is boom
    # finish is called once, on the error path, carrying the exception.
    fake_telemetry.trace_agent_server_finish.assert_called_once_with(
        path="/boom", func_result="", exception=boom
    )


def test_context_is_detached_in_finally_even_on_success(monkeypatch, fake_telemetry):
    # Spy on context attach/detach to prove the finally block runs and pairs up.
    attached_token = object()
    detached = []

    monkeypatch.setattr(
        middleware_mod.context_api, "attach", lambda ctx: attached_token
    )
    monkeypatch.setattr(
        middleware_mod.context_api, "detach", lambda token: detached.append(token)
    )

    async def _app(scope, receive, send):
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    mw = AgentkitTelemetryHTTPMiddleware(_app)
    scope = {"type": "http", "method": "GET", "path": "/ok", "headers": []}
    send, _sent = _make_send_recorder()

    asyncio.run(mw(scope, _noop_receive, send))

    assert detached == [attached_token]


def test_context_is_detached_in_finally_even_on_exception(monkeypatch, fake_telemetry):
    attached_token = object()
    detached = []

    monkeypatch.setattr(
        middleware_mod.context_api, "attach", lambda ctx: attached_token
    )
    monkeypatch.setattr(
        middleware_mod.context_api, "detach", lambda token: detached.append(token)
    )

    async def _app(scope, receive, send):
        raise ValueError("nope")

    mw = AgentkitTelemetryHTTPMiddleware(_app)
    scope = {"type": "http", "method": "GET", "path": "/err", "headers": []}
    send, _sent = _make_send_recorder()

    with pytest.raises(ValueError, match="nope"):
        asyncio.run(mw(scope, _noop_receive, send))

    # detach still ran despite the exception (finally block), no crash.
    assert detached == [attached_token]

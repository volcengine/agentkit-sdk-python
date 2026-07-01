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

"""Unit tests for the simple_app request handlers.

Covers the pure helpers (`_build_error_content`, `_convert_to_sse`,
`_format_ping_status`), the entrypoint-dispatch logic of
`InvokeHandler._process_invoke`, the full HTTP response matrix of
`InvokeHandler.handle` (driven through a Starlette TestClient), and the
in-memory bookkeeping of `AsyncTaskHandler`.

The telemetry singleton attached to the ``handle`` path binds real OTEL
tracer/meter objects, so tests that exercise ``handle`` swap the module-level
``telemetry`` for a hand-rolled fake. This keeps the tests deterministic and
free of any real exporter, while still driving the async handlers synchronously
via the TestClient / ``asyncio.run``.
"""

from __future__ import annotations

import asyncio

import pytest
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.testclient import TestClient

import agentkit.apps.simple_app.simple_app_handlers as handlers_mod
from agentkit.apps.simple_app.simple_app import AgentkitSimpleApp
from agentkit.apps.simple_app.simple_app_handlers import (
    AsyncTaskHandler,
    InvalidJSONPayloadError,
    InvokeHandler,
    PingHandler,
    _build_error_content,
)


# ---------------------------------------------------------------------------
# Hand-rolled fakes
# ---------------------------------------------------------------------------


class _FakeSpanContext:
    def __init__(self) -> None:
        self.trace_id = 0
        self.span_id = 0


class _FakeSpan:
    def __init__(self) -> None:
        self.attributes: dict = {}
        self.ended = False
        self.status = None
        self.recorded_exceptions: list = []
        self.events: list = []

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def is_recording(self):
        return True

    def get_span_context(self):
        return _FakeSpanContext()

    def set_status(self, status):
        self.status = status

    def record_exception(self, exc):
        self.recorded_exceptions.append(exc)

    def add_event(self, *args, **kwargs):
        self.events.append((args, kwargs))

    def end(self):
        self.ended = True


class _FakeTracer:
    def __init__(self) -> None:
        self.spans: list = []

    def start_span(self, name=None, **kwargs):
        span = _FakeSpan()
        self.spans.append(span)
        return span


class _FakeTelemetry:
    """Records calls instead of touching real OTEL exporters."""

    def __init__(self) -> None:
        self.tracer = _FakeTracer()
        self.trace_agent_calls: list = []
        self.finish_calls: list = []

    def trace_agent(self, func, span, payload, headers):
        self.trace_agent_calls.append((func, span, payload, headers))

    def trace_agent_finish(self, func_result, exception):
        self.finish_calls.append((func_result, exception))


class _FakeHeaders:
    """Minimal mapping stand-in that survives dict(...) conversion."""

    def __init__(self, data: dict) -> None:
        self._data = dict(data)

    def keys(self):
        return self._data.keys()

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def get(self, key, default=None):
        return self._data.get(key, default)


class _FakeRequest:
    """Async request stand-in for exercising `_process_invoke` directly."""

    def __init__(self, payload=None, headers=None, raise_json=False) -> None:
        self._payload = {} if payload is None else payload
        self.headers = _FakeHeaders(headers or {})
        self._raise_json = raise_json

    async def json(self):
        if self._raise_json:
            import json as _json

            # Trigger the real JSONDecodeError path taken by Request.json().
            _json.loads("not json")
        return self._payload


@pytest.fixture(autouse=True)
def _spy_telemetry(monkeypatch):
    """Swap the module-level telemetry singleton for a fake on every test."""
    fake = _FakeTelemetry()
    monkeypatch.setattr(handlers_mod, "telemetry", fake)
    return fake


# ---------------------------------------------------------------------------
# _build_error_content
# ---------------------------------------------------------------------------


def test_build_error_content_returns_nested_error_dict_shape():
    assert _build_error_content(message="boom", error_type="BadRequest") == {
        "error": {"message": "boom", "type": "BadRequest"}
    }


# ---------------------------------------------------------------------------
# Instantiability with no args
# ---------------------------------------------------------------------------


def test_all_handlers_are_instantiable_with_no_arguments():
    assert InvokeHandler().func is None
    assert PingHandler().func is None
    async_handler = AsyncTaskHandler()
    assert async_handler.func is None
    assert async_handler._active_tasks == {}


# ---------------------------------------------------------------------------
# InvokeHandler._process_invoke dispatch
# ---------------------------------------------------------------------------


def test_process_invoke_zero_param_entrypoint_is_called_with_no_args():
    handler = InvokeHandler()

    def entrypoint():
        return {"called": "no-args"}

    handler.func = entrypoint
    request = _FakeRequest(payload={"ignored": True}, headers={"h": "v"})
    payload, headers, result = asyncio.run(handler._process_invoke(request))

    assert payload == {"ignored": True}
    assert headers == {"h": "v"}
    assert result == {"called": "no-args"}


def test_process_invoke_single_param_named_request_receives_the_request():
    handler = InvokeHandler()

    def entrypoint(Request):  # case-insensitive match on "request"
        return {"is_request": Request is captured["req"]}

    captured: dict = {}
    handler.func = entrypoint
    request = _FakeRequest(payload={"a": 1})
    captured["req"] = request
    _, _, result = asyncio.run(handler._process_invoke(request))

    assert result == {"is_request": True}


def test_process_invoke_single_param_other_name_receives_the_payload_dict():
    handler = InvokeHandler()

    def entrypoint(payload):
        return {"echo": payload}

    handler.func = entrypoint
    request = _FakeRequest(payload={"x": 42})
    _, _, result = asyncio.run(handler._process_invoke(request))

    assert result == {"echo": {"x": 42}}


def test_process_invoke_two_param_entrypoint_receives_payload_and_headers():
    handler = InvokeHandler()

    def entrypoint(payload, headers):
        return {"payload": payload, "headers": headers}

    handler.func = entrypoint
    request = _FakeRequest(payload={"k": "v"}, headers={"user_id": "u1"})
    _, _, result = asyncio.run(handler._process_invoke(request))

    assert result == {"payload": {"k": "v"}, "headers": {"user_id": "u1"}}


def test_process_invoke_supports_async_coroutine_entrypoint():
    handler = InvokeHandler()

    async def entrypoint(payload):
        return {"async_echo": payload}

    handler.func = entrypoint
    request = _FakeRequest(payload={"n": 7})
    _, _, result = asyncio.run(handler._process_invoke(request))

    assert result == {"async_echo": {"n": 7}}


def test_process_invoke_malformed_json_body_raises_invalid_json_payload_error():
    handler = InvokeHandler()

    def entrypoint(payload):
        return payload

    handler.func = entrypoint
    request = _FakeRequest(raise_json=True)

    with pytest.raises(InvalidJSONPayloadError):
        asyncio.run(handler._process_invoke(request))


def test_process_invoke_without_registered_func_returns_placeholder_message():
    handler = InvokeHandler()
    request = _FakeRequest(payload={"any": "thing"})
    payload, headers, result = asyncio.run(handler._process_invoke(request))

    assert payload == {}
    assert headers == {}
    assert result == {"message": "Invoke handler function is not set."}


# ---------------------------------------------------------------------------
# InvokeHandler._convert_to_sse
# ---------------------------------------------------------------------------


def test_convert_to_sse_passes_string_through_unserialized():
    handler = InvokeHandler()
    assert handler._convert_to_sse("hello") == b"data: hello\n\n"


def test_convert_to_sse_json_serializes_non_string_objects():
    handler = InvokeHandler()
    assert handler._convert_to_sse({"a": 1}) == b'data: {"a": 1}\n\n'


# ---------------------------------------------------------------------------
# InvokeHandler.handle response matrix (via TestClient)
# ---------------------------------------------------------------------------


def _make_client() -> tuple[AgentkitSimpleApp, TestClient]:
    app = AgentkitSimpleApp()
    return app, TestClient(app)


def test_handle_without_registered_entrypoint_returns_404():
    app, client = _make_client()
    resp = client.post("/invoke", json={"anything": True})

    assert resp.status_code == 404
    assert resp.json() == {
        "error": {
            "message": (
                "Entrypoint function is not set. Please register a function "
                "with @app.entrypoint."
            ),
            "type": "NotFound",
        }
    }


def test_handle_entrypoint_returning_plain_dict_yields_json_200():
    app, client = _make_client()

    @app.entrypoint
    def entrypoint(payload):
        return {"got": payload}

    resp = client.post("/invoke", json={"q": "hi"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"got": {"q": "hi"}}


def test_handle_malformed_json_request_body_returns_400():
    app, client = _make_client()

    @app.entrypoint
    def entrypoint(payload):
        return payload

    resp = client.post(
        "/invoke",
        content=b"this-is-not-json",
        headers={"content-type": "application/json"},
    )

    assert resp.status_code == 400
    assert resp.json() == {
        "error": {
            "message": (
                "Invalid JSON payload. Please provide a valid JSON object in "
                "the request body."
            ),
            "type": "BadRequest",
        }
    }


def test_handle_http_exception_below_500_passes_detail_through():
    app, client = _make_client()

    @app.entrypoint
    def entrypoint(payload):
        raise HTTPException(status_code=403, detail="forbidden zone")

    resp = client.post("/invoke", json={})

    assert resp.status_code == 403
    assert resp.json() == {
        "error": {"message": "forbidden zone", "type": "HTTPException"}
    }


def test_handle_http_exception_at_or_above_500_masks_detail_with_generic_message():
    app, client = _make_client()

    @app.entrypoint
    def entrypoint(payload):
        raise HTTPException(status_code=503, detail="leaky internal secret")

    resp = client.post("/invoke", json={})

    assert resp.status_code == 503
    body = resp.json()
    assert body["error"]["type"] == "HTTPException"
    assert "leaky internal secret" not in body["error"]["message"]
    assert "user-defined entrypoint function" in body["error"]["message"]


def test_handle_generic_exception_returns_500_with_exception_type_name():
    app, client = _make_client()

    class _CustomBoom(Exception):
        ...

    @app.entrypoint
    def entrypoint(payload):
        raise _CustomBoom("kaboom")

    resp = client.post("/invoke", json={})

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["type"] == "_CustomBoom"
    assert "user-defined entrypoint function" in body["error"]["message"]


def test_handle_sync_generator_entrypoint_streams_sse():
    app, client = _make_client()

    @app.entrypoint
    def entrypoint(payload):
        yield "chunk-1"
        yield {"chunk": 2}

    resp = client.post("/invoke", json={})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.text == 'data: chunk-1\n\ndata: {"chunk": 2}\n\n'


def test_handle_async_generator_entrypoint_streams_sse():
    app, client = _make_client()

    @app.entrypoint
    async def entrypoint(payload):
        yield "async-1"
        yield {"async": 2}

    resp = client.post("/invoke", json={})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.text == 'data: async-1\n\ndata: {"async": 2}\n\n'


# ---------------------------------------------------------------------------
# AsyncTaskHandler in-memory bookkeeping
# ---------------------------------------------------------------------------


def test_async_task_handler_add_then_complete_known_task_returns_true():
    handler = AsyncTaskHandler()
    task_id = handler.add_async_task("file_processing", {"file": "data.csv"})

    assert task_id in handler._active_tasks
    info = handler.get_async_task_info()
    assert info["active_count"] == 1
    assert info["running_jobs"][0]["name"] == "file_processing"

    assert handler.complete_async_task(task_id) is True
    assert handler._active_tasks == {}
    assert handler.get_async_task_info()["active_count"] == 0


def test_async_task_handler_complete_unknown_task_returns_false():
    handler = AsyncTaskHandler()
    assert handler.complete_async_task(1234567890) is False


def test_async_task_handler_tracks_multiple_independent_tasks():
    handler = AsyncTaskHandler()
    first = handler.add_async_task("a")
    second = handler.add_async_task("b")

    assert first != second
    assert handler.get_async_task_info()["active_count"] == 2

    assert handler.complete_async_task(first) is True
    assert handler.get_async_task_info()["active_count"] == 1
    # Completing the same id twice: second attempt no longer found.
    assert handler.complete_async_task(first) is False
    assert handler.complete_async_task(second) is True


# ---------------------------------------------------------------------------
# PingHandler._format_ping_status
# ---------------------------------------------------------------------------


def test_format_ping_status_wraps_string_result_in_status_dict():
    handler = PingHandler()
    assert handler._format_ping_status("healthy") == {"status": "healthy"}


def test_format_ping_status_returns_dict_result_unchanged():
    handler = PingHandler()
    payload = {"status": "ok", "extra": 1}
    assert handler._format_ping_status(payload) == payload


def test_format_ping_status_on_non_str_non_dict_returns_error_dict_when_func_is_none():
    # After the fix (None-safe func name via getattr): with no registered func
    # the else branch no longer raises AttributeError -- it returns the intended
    # error dict for an unexpected (non str/dict) result type.
    handler = PingHandler()
    assert handler.func is None
    assert handler._format_ping_status(12345) == {
        "status": "error",
        "message": "Invalid response type.",
    }


def test_format_ping_status_on_non_str_non_dict_returns_error_dict_when_func_present():
    # With a registered func the __name__ lookup succeeds, so the intended
    # error dict is returned for an unexpected (non str/dict) result type.
    handler = PingHandler()

    def ping():
        return "ok"

    handler.func = ping
    assert handler._format_ping_status(12345) == {
        "status": "error",
        "message": "Invalid response type.",
    }


# ---------------------------------------------------------------------------
# AsyncTaskHandler.handle signature deviation
# ---------------------------------------------------------------------------


def test_async_task_handler_handle_accepts_optional_request_argument():
    # After the fix: handle conforms to the BaseHandler.handle(self, request)
    # contract via an optional request param, so it works both as a no-arg call
    # and as a Starlette route endpoint (which passes a request). Both return an
    # empty Response.
    handler = AsyncTaskHandler()

    resp = asyncio.run(handler.handle())
    assert isinstance(resp, Response)

    resp2 = asyncio.run(handler.handle(object()))
    assert isinstance(resp2, Response)

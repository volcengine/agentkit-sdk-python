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

"""Offline unit guards for the per-app telemetry helpers.

These pin the observable behaviour of the ``Telemetry`` helpers that live in
each ``agentkit.apps.*.telemetry`` module:

* ``simple_app.telemetry`` -- the ``dont_throw`` decorator, ``trace_agent``,
  ``trace_agent_finish`` (latency recording + exception handling), and
  ``handle_exception``.
* ``agent_server_app.telemetry`` -- ``trace_agent_server_finish`` error_type
  formatting and the ``_INVOKE_PATH`` gate on latency recording.
* ``mcp_app.telemetry`` -- ``trace_tool`` attribute wiring.
* ``a2a_app.telemetry`` -- ``handle_exception`` and ``trace_a2a_agent``.

Everything is driven with hand-rolled fakes (no OTEL SDK exporters, no real
histograms). The trace_* methods are called directly; the ``dont_throw``
assertions exercise the decorator in isolation.
"""

from __future__ import annotations

import json

import pytest

import agentkit.apps.simple_app.telemetry as simple_tel
import agentkit.apps.agent_server_app.telemetry as server_tel
import agentkit.apps.mcp_app.telemetry as mcp_tel
import agentkit.apps.a2a_app.telemetry as a2a_tel
import agentkit.apps.utils as apps_utils


# ---------------------------------------------------------------------------
# Hand-rolled fakes
# ---------------------------------------------------------------------------


class _FakeSpanContext:
    def __init__(self, trace_id: int = 1, span_id: int = 2) -> None:
        self.trace_id = trace_id
        self.span_id = span_id


class _FakeSpan:
    """Minimal stand-in for an OTEL Span.

    ``set_attribute`` records into ``.attributes``; the various lifecycle
    hooks record into flat lists so tests can assert on them.
    """

    def __init__(self, recording: bool = True, start_time: int = 0) -> None:
        self.attributes: dict = {}
        self._recording = recording
        self._context = _FakeSpanContext()
        self.statuses: list = []
        self.recorded_exceptions: list = []
        self.events: list = []
        self.ended = False
        # start_time is read via hasattr(span, "start_time") to gate latency
        # recording; keep it a real attribute so the branch executes.
        self.start_time = start_time

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value

    def is_recording(self) -> bool:
        return self._recording

    def get_span_context(self) -> _FakeSpanContext:
        return self._context

    def set_status(self, status) -> None:
        self.statuses.append(status)

    def record_exception(self, exception) -> None:
        self.recorded_exceptions.append(exception)

    def add_event(self, name, attributes=None) -> None:
        self.events.append((name, attributes))

    def end(self) -> None:
        self.ended = True


class _FakeHistogram:
    """Records every .record(value, attributes) call."""

    def __init__(self) -> None:
        self.records: list = []

    def record(self, value, attributes=None) -> None:
        self.records.append((value, attributes))


def _make_func(name: str = "my_agent"):
    def f():  # pragma: no cover - only __name__ is read
        return None

    f.__name__ = name
    return f


def _unwrap_dont_throw(wrapper):
    """Recover the original function wrapped by ``dont_throw``.

    The ``dont_throw`` decorator does not use ``functools.wraps``, so there is
    no ``__wrapped__``; the original callable lives in the wrapper's closure
    under the ``func`` free variable. Reaching for it lets us invoke the
    traced logic directly, bypassing the exception-swallowing wrapper so any
    error surfaces in the test.
    """
    idx = wrapper.__code__.co_freevars.index("func")
    return wrapper.__closure__[idx].cell_contents


# The undecorated trace_agent (invoked directly, per the test brief).
_simple_trace_agent = _unwrap_dont_throw(simple_tel.Telemetry.trace_agent)


# ===========================================================================
# simple_app.telemetry
# ===========================================================================


def test_dont_throw_swallows_exception_and_returns_none_without_propagating():
    @simple_tel.dont_throw
    def boom():
        raise RuntimeError("kaboom")

    # The wrapper must not propagate; it returns None on failure.
    assert boom() is None


def test_dont_throw_returns_wrapped_value_when_function_succeeds():
    @simple_tel.dont_throw
    def ok(a, b):
        return a + b

    assert ok(2, 3) == 5


def test_simple_trace_agent_sets_core_span_attributes():
    span = _FakeSpan()
    func = _make_func("handle_run")
    payload = {"prompt": "hi"}
    headers = {"content-type": "application/json"}

    # Call the underlying function directly, bypassing dont_throw, so any
    # error surfaces instead of being swallowed.
    _simple_trace_agent(simple_tel.telemetry, func, span, payload, headers)

    attrs = span.attributes
    assert attrs["gen_ai.system"] == "agentkit"
    assert attrs["gen_ai.func_name"] == "handle_run"
    assert attrs["gen_ai.span.kind"] == "workflow"
    assert attrs["gen_ai.operation.name"] == "invoke_agent"
    assert attrs["gen_ai.operation.type"] == "agent"
    assert attrs["gen_ai.request.headers"] == json.dumps(headers, ensure_ascii=False)
    assert attrs["gen_ai.input"] == json.dumps(payload, ensure_ascii=False)


def test_simple_trace_agent_redacts_credentials_and_caps_span_payloads():
    span = _FakeSpan()
    func = _make_func("handle_run")
    # Deliberately NOT in any real credential format (GitHub push protection
    # scans test fixtures too); the field rule redacts by key name.
    secret = "fake-credential-1234567890abcdef1234"
    payload = {"prompt": "hi", "api_key": secret, "filler": "x" * 8192}
    headers = {"content-type": "application/json"}

    _simple_trace_agent(simple_tel.telemetry, func, span, payload, headers)

    recorded = span.attributes["gen_ai.input"]
    assert secret not in recorded
    assert "***" in recorded
    # Oversized payloads are capped so spans cannot ship unbounded data.
    assert recorded.endswith("...[truncated]")
    assert len(recorded) == apps_utils.SPAN_ATTR_VALUE_MAX_LEN + len(
        "...[truncated]"
    )


def test_simple_trace_agent_sets_session_and_user_ids_only_when_in_headers():
    span_with = _FakeSpan()
    _simple_trace_agent(
        simple_tel.telemetry,
        _make_func(),
        span_with,
        {},
        {"session_id": "sess-1", "user_id": "user-1"},
    )
    assert span_with.attributes["gen_ai.session.id"] == "sess-1"
    assert span_with.attributes["gen_ai.user.id"] == "user-1"

    span_without = _FakeSpan()
    _simple_trace_agent(simple_tel.telemetry, _make_func(), span_without, {}, {})
    assert "gen_ai.session.id" not in span_without.attributes
    assert "gen_ai.user.id" not in span_without.attributes


def test_simple_trace_agent_finish_sets_output_and_records_latency(monkeypatch):
    fake_hist = _FakeHistogram()
    span = _FakeSpan(recording=True, start_time=0)

    monkeypatch.setattr(simple_tel.telemetry, "latency_histogram", fake_hist)
    monkeypatch.setattr(simple_tel.trace, "get_current_span", lambda: span)

    simple_tel.telemetry.trace_agent_finish("the-output", None)

    assert span.attributes["gen_ai.output"] == "the-output"
    assert span.ended is True
    # No exception -> exactly one latency record with the base attributes only.
    assert len(fake_hist.records) == 1
    _duration, attributes = fake_hist.records[0]
    assert attributes["gen_ai_operation_name"] == "invoke_agent"
    assert attributes["gen_ai_operation_type"] == "agent"
    assert "error_type" not in attributes


def test_simple_trace_agent_finish_on_exception_sets_error_type_and_handles(
    monkeypatch,
):
    fake_hist = _FakeHistogram()
    span = _FakeSpan(recording=True, start_time=0)
    monkeypatch.setattr(simple_tel.telemetry, "latency_histogram", fake_hist)
    monkeypatch.setattr(simple_tel.trace, "get_current_span", lambda: span)

    exc = ValueError("bad input")
    simple_tel.telemetry.trace_agent_finish("out", exc)

    # handle_exception must have run: ERROR status set + exception recorded.
    assert span.recorded_exceptions == [exc]
    assert len(span.statuses) == 1
    assert span.statuses[0].status_code == simple_tel.trace.StatusCode.ERROR
    # error_type carried into the latency attributes.
    _duration, attributes = fake_hist.records[0]
    assert attributes["error_type"] == "ValueError"


def test_simple_trace_agent_finish_is_noop_when_span_not_recording(monkeypatch):
    fake_hist = _FakeHistogram()
    span = _FakeSpan(recording=False, start_time=0)
    monkeypatch.setattr(simple_tel.telemetry, "latency_histogram", fake_hist)
    monkeypatch.setattr(simple_tel.trace, "get_current_span", lambda: span)

    simple_tel.telemetry.trace_agent_finish("out", None)

    assert "gen_ai.output" not in span.attributes
    assert span.ended is False
    assert fake_hist.records == []


def test_simple_handle_exception_sets_error_status_and_records_exception():
    span = _FakeSpan()
    exc = KeyError("missing")

    simple_tel.Telemetry.handle_exception(span, exc)

    assert span.recorded_exceptions == [exc]
    assert len(span.statuses) == 1
    status = span.statuses[0]
    assert status.status_code == simple_tel.trace.StatusCode.ERROR
    assert "KeyError" in status.description


# ===========================================================================
# agent_server_app.telemetry
# ===========================================================================


class _StatusCodeExc(Exception):
    """Exception carrying a truthy status_code attribute."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def test_server_trace_agent_server_finish_error_type_includes_status_code(monkeypatch):
    fake_hist = _FakeHistogram()
    span = _FakeSpan(recording=True, start_time=0)
    monkeypatch.setattr(server_tel.telemetry, "latency_histogram", fake_hist)
    monkeypatch.setattr(server_tel.trace, "get_current_span", lambda: span)

    exc = _StatusCodeExc("nope", 503)
    server_tel.telemetry.trace_agent_server_finish("/run", "result", exc)

    assert len(fake_hist.records) == 1
    _duration, attributes = fake_hist.records[0]
    assert attributes["error_type"] == "_StatusCodeExc_503"
    # handle_exception still ran.
    assert span.recorded_exceptions == [exc]


def test_server_trace_agent_server_finish_error_type_is_plain_class_without_status(
    monkeypatch,
):
    fake_hist = _FakeHistogram()
    span = _FakeSpan(recording=True, start_time=0)
    monkeypatch.setattr(server_tel.telemetry, "latency_histogram", fake_hist)
    monkeypatch.setattr(server_tel.trace, "get_current_span", lambda: span)

    exc = ValueError("plain")
    server_tel.telemetry.trace_agent_server_finish("/invoke", "result", exc)

    _duration, attributes = fake_hist.records[0]
    assert attributes["error_type"] == "ValueError"


def test_server_latency_recorded_only_for_invoke_paths(monkeypatch):
    # Matching path -> record fires.
    for path in ("/run_sse", "/run", "/invoke"):
        fake_hist = _FakeHistogram()
        span = _FakeSpan(recording=True, start_time=0)
        monkeypatch.setattr(server_tel.telemetry, "latency_histogram", fake_hist)
        monkeypatch.setattr(server_tel.trace, "get_current_span", lambda: span)

        server_tel.telemetry.trace_agent_server_finish(path, "result", None)

        assert len(fake_hist.records) == 1, f"expected a record for path {path}"
        assert span.ended is True


def test_server_latency_not_recorded_for_non_invoke_path(monkeypatch):
    fake_hist = _FakeHistogram()
    span = _FakeSpan(recording=True, start_time=0)
    monkeypatch.setattr(server_tel.telemetry, "latency_histogram", fake_hist)
    monkeypatch.setattr(server_tel.trace, "get_current_span", lambda: span)

    server_tel.telemetry.trace_agent_server_finish("/healthz", "result", None)

    # Path is not in _INVOKE_PATH -> no latency recorded, but span still ends.
    assert fake_hist.records == []
    assert span.ended is True


def test_server_status_code_falsy_falls_back_to_plain_class_name(monkeypatch):
    # status_code present but falsy (0) -> getattr(..., None) is falsy -> plain name.
    fake_hist = _FakeHistogram()
    span = _FakeSpan(recording=True, start_time=0)
    monkeypatch.setattr(server_tel.telemetry, "latency_histogram", fake_hist)
    monkeypatch.setattr(server_tel.trace, "get_current_span", lambda: span)

    exc = _StatusCodeExc("zero", 0)
    server_tel.telemetry.trace_agent_server_finish("/run", "result", exc)

    _duration, attributes = fake_hist.records[0]
    assert attributes["error_type"] == "_StatusCodeExc"


# ===========================================================================
# mcp_app.telemetry
# ===========================================================================


def test_mcp_trace_tool_sets_operation_type_and_io_attributes():
    span = _FakeSpan(recording=True, start_time=0)
    fake_hist = _FakeHistogram()
    mcp_tel.telemetry.latency_histogram = fake_hist  # reset below in fixture

    func = _make_func("multiply")
    args = {"a": 2, "b": 3}
    result = {"value": 6}

    mcp_tel.telemetry.trace_tool(
        func, span, args, result, operation_type="my_op", exception=None
    )

    attrs = span.attributes
    assert attrs["gen_ai.operation.type"] == "my_op"
    assert attrs["gen_ai.system"] == "agentkit"
    assert attrs["gen_ai.func_name"] == "multiply"
    assert attrs["gen_ai.span.kind"] == "tool"
    assert attrs["gen_ai.operation.name"] == "tool"
    assert attrs["gen_ai.input"] == json.dumps(args, ensure_ascii=False)
    assert attrs["gen_ai.output"] == json.dumps(result, ensure_ascii=False)
    # latency recorded once with base attributes (no exception).
    assert len(fake_hist.records) == 1
    _duration, attributes = fake_hist.records[0]
    assert attributes["gen_ai_operation_type"] == "my_op"
    assert "error_type" not in attributes


@pytest.fixture(autouse=True)
def _restore_mcp_histogram():
    # test_mcp_trace_tool_* replaces the module singleton's histogram; restore.
    original = mcp_tel.telemetry.latency_histogram
    yield
    mcp_tel.telemetry.latency_histogram = original


def test_mcp_trace_tool_records_error_type_on_exception(monkeypatch):
    span = _FakeSpan(recording=True, start_time=0)
    fake_hist = _FakeHistogram()
    monkeypatch.setattr(mcp_tel.telemetry, "latency_histogram", fake_hist)

    exc = RuntimeError("tool failed")
    mcp_tel.telemetry.trace_tool(
        _make_func("t"),
        span,
        {"x": 1},
        None,
        operation_type="op",
        exception=exc,
    )

    assert span.recorded_exceptions == [exc]
    _duration, attributes = fake_hist.records[0]
    assert attributes["error_type"] == "RuntimeError"


# ===========================================================================
# a2a_app.telemetry
# ===========================================================================


def test_a2a_handle_exception_sets_error_status_and_records_exception():
    span = _FakeSpan()
    exc = ValueError("a2a boom")

    a2a_tel.Telemetry.handle_exception(span, exc)

    assert span.recorded_exceptions == [exc]
    assert len(span.statuses) == 1
    status = span.statuses[0]
    assert status.status_code == a2a_tel.trace.StatusCode.ERROR
    assert "ValueError" in status.description


class _FakePart:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeMessage:
    def __init__(self, parts) -> None:
        self.parts = parts


class _FakeRequestContext:
    """RequestContext-like object satisfying trace_a2a_agent + _get_user_id.

    ``_get_user_id`` reads ``call_context`` (None here -> fall back path) and
    ``context_id``; ``trace_a2a_agent`` reads ``context_id`` and
    ``message.parts``.
    """

    def __init__(self, context_id: str, parts) -> None:
        self.context_id = context_id
        self.message = _FakeMessage(parts)
        self.call_context = None


def test_a2a_trace_a2a_agent_sets_attributes_and_derives_user_from_context_id():
    span = _FakeSpan(recording=True, start_time=0)
    fake_hist = _FakeHistogram()
    a2a_tel.telemetry.latency_histogram = fake_hist  # restored by fixture below

    request = _FakeRequestContext("ctx-42", [_FakePart("hello")])

    a2a_tel.telemetry.trace_a2a_agent(
        _make_func("a2a_handler"), span, request, result=None, exception=None
    )

    attrs = span.attributes
    assert attrs["gen_ai.system"] == "agentkit"
    assert attrs["gen_ai.func_name"] == "a2a_handler"
    assert attrs["gen_ai.span.kind"] == "a2a_agent"
    assert attrs["gen_ai.operation.type"] == "a2a_agent"
    assert attrs["gen_ai.session.id"] == "ctx-42"
    # _get_user_id falls back to A2A_USER_<context_id> when no call_context user.
    assert attrs["gen_ai.user.id"] == "A2A_USER_ctx-42"
    assert attrs["gen_ai.input"] == apps_utils.safe_serialize_to_json_string(
        request.message.parts
    )
    assert len(fake_hist.records) == 1


@pytest.fixture(autouse=True)
def _restore_a2a_histogram():
    original = a2a_tel.telemetry.latency_histogram
    yield
    a2a_tel.telemetry.latency_histogram = original


def test_a2a_trace_a2a_agent_records_error_type_on_exception(monkeypatch):
    span = _FakeSpan(recording=True, start_time=0)
    fake_hist = _FakeHistogram()
    monkeypatch.setattr(a2a_tel.telemetry, "latency_histogram", fake_hist)

    request = _FakeRequestContext("ctx-1", [_FakePart("hi")])
    exc = RuntimeError("a2a failed")

    a2a_tel.telemetry.trace_a2a_agent(
        _make_func(), span, request, result=None, exception=exc
    )

    assert span.recorded_exceptions == [exc]
    _duration, attributes = fake_hist.records[0]
    assert attributes["error_type"] == "RuntimeError"

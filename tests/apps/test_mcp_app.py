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

"""Offline unit guards for ``agentkit.apps.mcp_app.mcp_app.AgentkitMCPApp``.

These tests exercise the decorator/registration surface of the MCP app without
ever calling ``run()`` (which would bind a socket via uvicorn). We spy on the
``FastMCP`` server's ``tool`` method to capture the wrapper that gets registered,
and we replace the module-level ``telemetry`` singleton with a hand-rolled fake
so we can assert how ``trace_tool`` is invoked (operation type, argument shape)
for both the sync and the coroutine code paths.
"""

from __future__ import annotations

import asyncio

import pytest

from agentkit.apps.mcp_app import mcp_app as mcp_app_module
from agentkit.apps.mcp_app.mcp_app import AgentkitMCPApp


# ---------------------------------------------------------------------------
# Hand-rolled fakes
# ---------------------------------------------------------------------------


class _FakeSpan:
    """Minimal span honouring the ``start_as_current_span`` context manager."""

    def __init__(self) -> None:
        self.attributes: dict = {}
        self.ended = False

    def set_attribute(self, key=None, value=None, **_kw) -> None:
        self.attributes[key] = value

    def is_recording(self) -> bool:
        return True

    def get_span_context(self):
        return object()

    def set_status(self, *_a, **_kw) -> None:
        pass

    def record_exception(self, *_a, **_kw) -> None:
        pass

    def add_event(self, *_a, **_kw) -> None:
        pass

    def end(self, *_a, **_kw) -> None:
        self.ended = True


class _FakeSpanCM:
    """Context manager returned by ``tracer.start_as_current_span``."""

    def __init__(self, span: _FakeSpan) -> None:
        self._span = span

    def __enter__(self) -> _FakeSpan:
        return self._span

    def __exit__(self, *exc) -> bool:
        return False


class _FakeTracer:
    def __init__(self) -> None:
        self.span = _FakeSpan()

    def start_as_current_span(self, name=None, **_kw) -> _FakeSpanCM:
        return _FakeSpanCM(self.span)


class _FakeTelemetry:
    """Spy standing in for the module-level ``telemetry`` singleton."""

    def __init__(self) -> None:
        self.tracer = _FakeTracer()
        self.calls: list[dict] = []

    def trace_tool(
        self,
        func=None,
        span=None,
        args=None,
        func_result=None,
        operation_type=None,
        exception=None,
    ) -> None:
        self.calls.append(
            {
                "func": func,
                "span": span,
                "args": args,
                "func_result": func_result,
                "operation_type": operation_type,
                "exception": exception,
            }
        )


class _FakeMCPServer:
    """Captures every callable registered via ``.tool``."""

    def __init__(self) -> None:
        self.registered: list = []

    def tool(self, func):
        self.registered.append(func)
        return func


# ---------------------------------------------------------------------------
# Fixtures (local to this file)
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_telemetry(monkeypatch) -> _FakeTelemetry:
    fake = _FakeTelemetry()
    monkeypatch.setattr(mcp_app_module, "telemetry", fake)
    return fake


@pytest.fixture
def app(monkeypatch, fake_telemetry) -> AgentkitMCPApp:
    """An app whose real ``FastMCP`` server is swapped for a capturing fake.

    We build the app first (letting the ctor construct the real FastMCP, which
    performs no I/O) and then replace ``_mcp_server`` so registrations are
    captured without hitting the actual server.
    """
    instance = AgentkitMCPApp()
    instance._mcp_server = _FakeMCPServer()
    return instance


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_constructor_builds_a_fastmcp_server_without_binding_sockets():
    from fastmcp import FastMCP

    instance = AgentkitMCPApp()

    assert isinstance(instance._mcp_server, FastMCP)


# ---------------------------------------------------------------------------
# tool() decorator
# ---------------------------------------------------------------------------


def test_tool_decorator_returns_the_same_func_object_for_sync_func(app):
    def my_sync_tool(x):
        return x + 1

    returned = app.tool(my_sync_tool)

    assert returned is my_sync_tool


def test_tool_decorator_returns_the_same_func_object_for_async_func(app):
    async def my_async_tool(x):
        return x + 1

    returned = app.tool(my_async_tool)

    assert returned is my_async_tool


def test_tool_decorator_registers_a_wrapper_not_the_original_sync_func(app):
    def my_sync_tool(x):
        return x + 1

    app.tool(my_sync_tool)

    assert len(app._mcp_server.registered) == 1
    registered = app._mcp_server.registered[0]
    # A wraps() wrapper preserves __name__ but is a distinct object.
    assert registered is not my_sync_tool
    assert registered.__name__ == "my_sync_tool"


def test_tool_decorator_registers_a_wrapper_not_the_original_async_func(app):
    async def my_async_tool(x):
        return x + 1

    app.tool(my_async_tool)

    assert len(app._mcp_server.registered) == 1
    registered = app._mcp_server.registered[0]
    assert registered is not my_async_tool
    assert registered.__name__ == "my_async_tool"


def test_invoking_sync_tool_wrapper_returns_result_and_traces_as_mcp_tool(
    app, fake_telemetry
):
    def my_sync_tool(x):
        return x * 10

    app.tool(my_sync_tool)
    wrapper = app._mcp_server.registered[0]

    result = wrapper(5)

    assert result == 50
    assert len(fake_telemetry.calls) == 1
    call = fake_telemetry.calls[0]
    assert call["func"] is my_sync_tool
    assert call["operation_type"] == "mcp_tool"
    assert call["func_result"] == 50
    assert call["exception"] is None
    # The sync branch forwards the positional args tuple.
    assert call["args"] == (5,)
    assert call["span"] is fake_telemetry.tracer.span


def test_invoking_async_tool_wrapper_returns_result_and_traces_as_mcp_tool(
    app, fake_telemetry
):
    async def my_async_tool(x):
        return x * 10

    app.tool(my_async_tool)
    wrapper = app._mcp_server.registered[0]

    result = asyncio.run(wrapper(5))

    assert result == 50
    assert len(fake_telemetry.calls) == 1
    call = fake_telemetry.calls[0]
    assert call["func"] is my_async_tool
    assert call["operation_type"] == "mcp_tool"
    assert call["func_result"] == 50
    assert call["exception"] is None
    assert call["args"] == (5,)


def test_invoking_sync_tool_wrapper_reraises_original_error_and_still_traces(
    app, fake_telemetry
):
    boom = ValueError("kaboom")

    def failing_tool():
        raise boom

    app.tool(failing_tool)
    wrapper = app._mcp_server.registered[0]

    # After the fix (result initialized before the try): the wrapper re-raises
    # the ORIGINAL exception instead of an UnboundLocalError from the finally,
    # and telemetry.trace_tool is still invoked once with func_result=None and
    # the captured exception.
    with pytest.raises(ValueError) as excinfo:
        wrapper()
    assert excinfo.value is boom

    assert len(fake_telemetry.calls) == 1
    call = fake_telemetry.calls[0]
    assert call["func_result"] is None
    assert call["exception"] is boom
    assert call["operation_type"] == "mcp_tool"


def test_invoking_async_tool_wrapper_reraises_original_error_and_still_traces(
    app, fake_telemetry
):
    boom = ValueError("kaboom")

    async def failing_tool():
        raise boom

    app.tool(failing_tool)
    wrapper = app._mcp_server.registered[0]

    # After the fix: the async wrapper re-raises the original ValueError (not an
    # UnboundLocalError from the finally) and still records one trace_tool call.
    with pytest.raises(ValueError) as excinfo:
        asyncio.run(wrapper())
    assert excinfo.value is boom

    assert len(fake_telemetry.calls) == 1
    call = fake_telemetry.calls[0]
    assert call["func_result"] is None
    assert call["exception"] is boom
    assert call["operation_type"] == "mcp_tool"


# ---------------------------------------------------------------------------
# agent_as_a_tool()
# ---------------------------------------------------------------------------


def test_agent_as_a_tool_returns_the_same_func_object_for_sync_func(app):
    def my_agent(x):
        return x

    returned = app.agent_as_a_tool(my_agent)

    assert returned is my_agent


def test_agent_as_a_tool_returns_the_same_func_object_for_async_func(app):
    async def my_agent(x):
        return x

    returned = app.agent_as_a_tool(my_agent)

    assert returned is my_agent


def test_agent_as_a_tool_registers_a_wrapper_not_the_original_sync_func(app):
    def my_agent(x):
        return x

    app.agent_as_a_tool(my_agent)

    assert len(app._mcp_server.registered) == 1
    assert app._mcp_server.registered[0] is not my_agent
    assert app._mcp_server.registered[0].__name__ == "my_agent"


def test_invoking_sync_agent_tool_wrapper_traces_as_agent_mcp_tool_with_positional_args(
    app, fake_telemetry
):
    def my_agent(a, b):
        return a + b

    app.agent_as_a_tool(my_agent)
    wrapper = app._mcp_server.registered[0]

    result = wrapper(2, 3)

    assert result == 5
    assert len(fake_telemetry.calls) == 1
    call = fake_telemetry.calls[0]
    assert call["operation_type"] == "agent_mcp_tool"
    assert call["func"] is my_agent
    assert call["func_result"] == 5
    # Sync branch (source :135) forwards the positional args tuple to
    # trace_tool's third positional parameter.
    assert call["args"] == (2, 3)


def test_invoking_async_agent_tool_wrapper_traces_as_agent_mcp_tool_with_args_as_keyword(
    app, fake_telemetry
):
    async def my_agent(a, b):
        return a + b

    app.agent_as_a_tool(my_agent)
    wrapper = app._mcp_server.registered[0]

    result = asyncio.run(wrapper(2, 3))

    assert result == 5
    assert len(fake_telemetry.calls) == 1
    call = fake_telemetry.calls[0]
    assert call["operation_type"] == "agent_mcp_tool"
    assert call["func"] is my_agent
    assert call["func_result"] == 5
    # NOTE: the async branch (source :112) passes ``args=args`` as a keyword,
    # while the sync branch (source :135) passes it positionally. Because
    # Telemetry.trace_tool declares ``args`` as its third parameter, both bind
    # to the same slot -- the observable payload is identical: the positional
    # args tuple. This pins that current behavior.
    assert call["args"] == (2, 3)


def test_invoking_async_agent_tool_wrapper_reraises_original_error_and_still_traces(
    app, fake_telemetry
):
    boom = RuntimeError("agent boom")

    async def failing_agent():
        raise boom

    app.agent_as_a_tool(failing_agent)
    wrapper = app._mcp_server.registered[0]

    # After the fix: the agent wrapper re-raises the original RuntimeError (not
    # an UnboundLocalError from the finally) and still records one trace_tool
    # call tagged agent_mcp_tool.
    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(wrapper())
    assert excinfo.value is boom

    assert len(fake_telemetry.calls) == 1
    call = fake_telemetry.calls[0]
    assert call["func_result"] is None
    assert call["exception"] is boom
    assert call["operation_type"] == "agent_mcp_tool"


# ---------------------------------------------------------------------------
# add_env_detect_tool()
# ---------------------------------------------------------------------------


def test_add_env_detect_tool_registers_a_single_get_env_callable(app):
    app.add_env_detect_tool()

    assert len(app._mcp_server.registered) == 1
    get_env = app._mcp_server.registered[0]
    assert get_env.__name__ == "get_env"


def test_env_detect_tool_reports_agentkit_when_iam_role_trn_is_set(app, monkeypatch):
    app.add_env_detect_tool()
    get_env = app._mcp_server.registered[0]

    monkeypatch.setenv("RUNTIME_IAM_ROLE_TRN", "trn:some:role")

    assert get_env() == {"env": "agentkit"}


def test_env_detect_tool_reports_veadk_when_iam_role_trn_is_absent(app, monkeypatch):
    app.add_env_detect_tool()
    get_env = app._mcp_server.registered[0]

    monkeypatch.delenv("RUNTIME_IAM_ROLE_TRN", raising=False)

    assert get_env() == {"env": "veadk"}


def test_env_detect_tool_reports_veadk_when_iam_role_trn_is_empty_string(
    app, monkeypatch
):
    app.add_env_detect_tool()
    get_env = app._mcp_server.registered[0]

    # An empty string is falsy, so is_agentkit_runtime() returns False.
    monkeypatch.setenv("RUNTIME_IAM_ROLE_TRN", "")

    assert get_env() == {"env": "veadk"}

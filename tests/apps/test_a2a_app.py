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

"""Offline unit guards for ``AgentkitA2aApp``.

These tests exercise the decorator guards (``agent_executor`` / ``task_store`` /
``ping``), the pure ``_format_ping_status`` helper, the async ``ping_endpoint``
handler (driven via ``asyncio.run``), and the ``/env`` runtime-detection route
(driven via ``starlette.testclient.TestClient``) -- all without building the
real A2A server or ever calling ``run()`` (which binds sockets via uvicorn).
"""

from __future__ import annotations

import asyncio
import json

import pytest
from a2a.server.agent_execution import AgentExecutor
from a2a.server.tasks.task_store import TaskStore
from starlette.applications import Starlette
from starlette.testclient import TestClient

from agentkit.apps.a2a_app.a2a_app import AgentkitA2aApp


# ---------------------------------------------------------------------------
# Minimal concrete a2a subclasses used as decorator targets.
# a2a's AgentExecutor requires execute/cancel; TaskStore requires get/save/delete.
# ---------------------------------------------------------------------------


class _FakeAgentExecutor(AgentExecutor):
    async def execute(self, context, event_queue):  # pragma: no cover - never invoked
        return None

    async def cancel(self, context, event_queue):  # pragma: no cover - never invoked
        return None


class _FakeTaskStore(TaskStore):
    async def get(self, task_id):  # pragma: no cover - never invoked
        return None

    async def save(self, task):  # pragma: no cover - never invoked
        return None

    async def delete(self, task_id):  # pragma: no cover - never invoked
        return None


class _NotAnExecutor:
    """A plain class that is deliberately NOT a subclass of AgentExecutor."""


class _NotATaskStore:
    """A plain class that is deliberately NOT a subclass of TaskStore."""


class _DummyRequest:
    """Placeholder request object; ping_endpoint never reads the request."""


# ---------------------------------------------------------------------------
# _format_ping_status (pure)
# ---------------------------------------------------------------------------


def test_format_ping_status_wraps_string_result_under_status_key():
    app = AgentkitA2aApp()
    assert app._format_ping_status("ok") == {"status": "ok"}


def test_format_ping_status_wraps_dict_result_under_status_key():
    app = AgentkitA2aApp()
    payload = {"healthy": True, "detail": "fine"}
    assert app._format_ping_status(payload) == {"status": payload}


def test_format_ping_status_returns_error_dict_for_non_str_non_dict_result():
    app = AgentkitA2aApp()
    assert app._format_ping_status(12345) == {
        "status": "error",
        "message": "Invalid response type.",
    }


def test_format_ping_status_treats_bool_as_invalid_response_type():
    # NOTE: bool is not str/dict, so it falls through to the error branch.
    app = AgentkitA2aApp()
    assert app._format_ping_status(True) == {
        "status": "error",
        "message": "Invalid response type.",
    }


# ---------------------------------------------------------------------------
# ping() decorator guard
# ---------------------------------------------------------------------------


def test_ping_decorator_rejects_function_with_parameters():
    app = AgentkitA2aApp()

    def health(request):
        return "ok"

    with pytest.raises(AssertionError):
        app.ping(health)
    assert app._ping_func is None


def test_ping_decorator_registers_zero_argument_function_and_returns_it():
    app = AgentkitA2aApp()

    def health():
        return "ok"

    returned = app.ping(health)
    assert returned is health
    assert app._ping_func is health


# ---------------------------------------------------------------------------
# ping_endpoint (async, driven via asyncio.run)
# ---------------------------------------------------------------------------


def test_ping_endpoint_returns_404_when_no_ping_func_registered():
    app = AgentkitA2aApp()
    response = asyncio.run(app.ping_endpoint(_DummyRequest()))
    assert response.status_code == 404


def test_ping_endpoint_wraps_sync_ping_func_result_under_status():
    app = AgentkitA2aApp()
    app._ping_func = lambda: "alive"

    response = asyncio.run(app.ping_endpoint(_DummyRequest()))

    assert response.status_code == 200
    assert json.loads(bytes(response.body)) == {"status": "alive"}


def test_ping_endpoint_awaits_coroutine_ping_func_result():
    app = AgentkitA2aApp()

    async def health():
        return {"db": "up"}

    app._ping_func = health

    response = asyncio.run(app.ping_endpoint(_DummyRequest()))

    assert response.status_code == 200
    assert json.loads(bytes(response.body)) == {"status": {"db": "up"}}


def test_ping_endpoint_returns_500_error_payload_when_ping_func_raises():
    app = AgentkitA2aApp()

    def boom():
        raise ValueError("kaboom")

    app._ping_func = boom

    response = asyncio.run(app.ping_endpoint(_DummyRequest()))

    assert response.status_code == 500
    assert json.loads(bytes(response.body)) == {
        "status": "error",
        "message": "kaboom",
    }


def test_ping_endpoint_returns_error_payload_when_ping_func_returns_invalid_type():
    app = AgentkitA2aApp()
    app._ping_func = lambda: 42

    response = asyncio.run(app.ping_endpoint(_DummyRequest()))

    assert response.status_code == 200
    assert json.loads(bytes(response.body)) == {
        "status": "error",
        "message": "Invalid response type.",
    }


# ---------------------------------------------------------------------------
# agent_executor() decorator guard
# ---------------------------------------------------------------------------


def test_agent_executor_rejects_class_not_subclassing_a2a_agent_executor():
    app = AgentkitA2aApp()

    with pytest.raises(TypeError):
        app.agent_executor()(_NotAnExecutor)
    assert app._agent_executor is None


def test_agent_executor_binds_valid_executor_and_returns_the_class():
    app = AgentkitA2aApp()

    class _MyExecutor(_FakeAgentExecutor):
        pass

    returned = app.agent_executor()(_MyExecutor)

    assert returned is _MyExecutor
    assert isinstance(app._agent_executor, _MyExecutor)


def test_agent_executor_raises_runtime_error_when_binding_a_second_executor():
    app = AgentkitA2aApp()

    class _First(_FakeAgentExecutor):
        pass

    class _Second(_FakeAgentExecutor):
        pass

    app.agent_executor()(_First)
    with pytest.raises(RuntimeError):
        app.agent_executor()(_Second)


# ---------------------------------------------------------------------------
# task_store() decorator guard
# ---------------------------------------------------------------------------


def test_task_store_rejects_class_not_subclassing_a2a_task_store():
    app = AgentkitA2aApp()

    with pytest.raises(TypeError):
        app.task_store()(_NotATaskStore)
    assert app._task_store is None


def test_task_store_binds_valid_store_and_returns_the_class():
    app = AgentkitA2aApp()

    class _MyStore(_FakeTaskStore):
        pass

    returned = app.task_store()(_MyStore)

    assert returned is _MyStore
    assert isinstance(app._task_store, _MyStore)


def test_task_store_raises_runtime_error_when_binding_a_second_store():
    app = AgentkitA2aApp()

    class _First(_FakeTaskStore):
        pass

    class _Second(_FakeTaskStore):
        pass

    app.task_store()(_First)
    with pytest.raises(RuntimeError):
        app.task_store()(_Second)


# ---------------------------------------------------------------------------
# add_env_detect_route() -> GET /env
# ---------------------------------------------------------------------------


def test_env_route_reports_agentkit_when_runtime_iam_role_trn_is_set(monkeypatch):
    monkeypatch.setenv("RUNTIME_IAM_ROLE_TRN", "x")

    bare_app = Starlette()
    AgentkitA2aApp().add_env_detect_route(bare_app)

    with TestClient(bare_app) as client:
        response = client.get("/env")

    assert response.status_code == 200
    assert response.json() == {"env": "agentkit"}


def test_env_route_reports_veadk_when_runtime_iam_role_trn_is_absent(monkeypatch):
    monkeypatch.delenv("RUNTIME_IAM_ROLE_TRN", raising=False)

    bare_app = Starlette()
    AgentkitA2aApp().add_env_detect_route(bare_app)

    with TestClient(bare_app) as client:
        response = client.get("/env")

    assert response.status_code == 200
    assert response.json() == {"env": "veadk"}


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [False, True])
async def test_execute_preserves_protocol_task_and_original_error(monkeypatch, failed):
    from a2a.server.agent_execution.context import RequestContext
    from a2a.server.events.event_queue import EventQueue
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from agentkit.apps.a2a_app.a2a_app import _wrap_agent_executor_execute_func
    from agentkit.apps.a2a_app.telemetry import telemetry

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "tracer", provider.get_tracer("test.a2a"))
    failure = ValueError("original executor failure")
    observed = []
    monkeypatch.setattr(
        telemetry, "trace_a2a_agent",
        lambda func, span, context, result, exception: observed.append((result, exception)),
    )

    async def execute(self, context, event_queue):
        if failed:
            raise failure
        return "result"

    wrapped = _wrap_agent_executor_execute_func(execute)
    try:
        if failed:
            with pytest.raises(ValueError) as caught:
                await wrapped(object(), RequestContext(task_id="protocol-task"), EventQueue())
            assert caught.value is failure
            assert observed == [(None, failure)]
        else:
            assert await wrapped(object(), RequestContext(task_id="protocol-task"), EventQueue()) == "result"
            assert observed == [("result", None)]
        span = exporter.get_finished_spans()[0]
        assert span.attributes["agentkit.task.id"] == "protocol-task"
        assert not any(event.name == "task.completed" for event in span.events)
    finally:
        provider.shutdown()

import json
from types import SimpleNamespace

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from starlette.applications import Starlette
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from agentkit.apps.agent_server_app.telemetry import telemetry
from agentkit.apps.langgraph_server_app.diagnostics import (
    LangGraphTelemetryMiddleware,
    trace_execution,
)
from agentkit.apps.langgraph_server_app.langgraph_server_app import AgentkitRunRequest


@pytest.fixture
def traces(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test.langgraph.diagnostics")
    monkeypatch.setattr(telemetry, "tracer", tracer)
    yield exporter
    provider.shutdown()


@pytest.mark.parametrize("failed", [False, True])
def test_stream_http_parent_run_correlation_and_error_without_body(traces, failed):
    class Probe:
        @trace_execution
        async def stream(self, req):
            yield {"content": "private output"}
            if failed:
                raise RuntimeError("private failure")
            yield {"content": "private final"}

    async def route(request):
        req = AgentkitRunRequest.model_validate(await request.json())

        async def stream():
            try:
                async for event in Probe().stream(req):
                    yield json.dumps(event).encode()
            except RuntimeError:
                yield b"error"

        return StreamingResponse(stream())

    app = Starlette(routes=[Route("/run_sse", route, methods=["POST"])])
    app.add_middleware(LangGraphTelemetryMiddleware)
    parent_trace = "a" * 32
    parent_span = "b" * 16
    with TestClient(app) as client:
        response = client.post(
            "/run_sse",
            headers={"traceparent": f"00-{parent_trace}-{parent_span}-01"},
            json={
                "app_name": "probe",
                "user_id": "test",
                "session_id": "session-1",
                "agentkitDiagnosticRunId": "run-1",
                "new_message": "private prompt",
            },
        )
    assert response.status_code == 200
    spans = traces.get_finished_spans()
    root = next(s for s in spans if s.name == "agent_server_request")
    execution = next(s for s in spans if s.name == "runtime.agent.execute")
    assert root.context.trace_id == int(parent_trace, 16)
    assert root.parent.span_id == int(parent_span, 16)
    assert execution.parent.span_id == root.context.span_id
    assert (
        execution.start_time >= root.start_time and execution.end_time <= root.end_time
    )
    assert (
        root.attributes["agentkit.run.id"]
        == execution.attributes["agentkit.run.id"]
        == "run-1"
    )
    assert root.attributes["gen_ai.session.id"] == "session-1"
    names = {e.name for e in root.events}
    assert "agent.execution.first_event" in names
    assert ("agent.execution.finished" in names) is not failed
    assert (root.status.status_code is trace.StatusCode.ERROR) is failed
    assert (execution.status.status_code is trace.StatusCode.ERROR) is failed
    assert all("private" not in s.to_json() for s in spans)


def test_native_route_does_not_duplicate_langgraph_tracing(traces):
    async def native(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/threads", native, methods=["POST"])])
    app.add_middleware(LangGraphTelemetryMiddleware)
    with TestClient(app) as client:
        assert client.post("/threads").status_code == 200
    assert not traces.get_finished_spans()


@pytest.mark.asyncio
async def test_cancel_closes_inner_stream_and_ends_execution(traces):
    closed = []

    class Probe:
        @trace_execution
        async def stream(self, req):
            try:
                yield {}
                yield {}
            finally:
                closed.append(True)

    req = SimpleNamespace(session_id="session-1", agentkit_diagnostic_run_id=None)
    with telemetry.tracer.start_as_current_span("request"):
        events = Probe().stream(req)
        await anext(events)
        await events.aclose()
    assert closed == [True]
    execution = next(
        s for s in traces.get_finished_spans() if s.name == "runtime.agent.execute"
    )
    assert execution.end_time is not None


def test_adapter_installs_once_and_correlates_real_protocol_routes(
    traces, monkeypatch, tmp_path
):
    from tests.apps.test_langgraph_server_app import (
        _FakeClient,
        _install_fake_langgraph,
        _write_config,
    )
    from agentkit.apps.langgraph_server_app.langgraph_server_app import (
        AgentkitLangGraphServerApp,
    )

    app = _install_fake_langgraph(monkeypatch, _FakeClient())
    config = _write_config(tmp_path)
    AgentkitLangGraphServerApp(config_path=config)
    AgentkitLangGraphServerApp(config_path=config)
    assert sum(m.cls is LangGraphTelemetryMiddleware for m in app.user_middleware) == 1
    with TestClient(app) as client:
        response = client.post(
            "/run_sse",
            json={
                "appName": "lead_agent",
                "userId": "test",
                "sessionId": "session-1",
                "agentkitDiagnosticRunId": "run-sse-1",
                "newMessage": "hello",
            },
        )
        assert response.status_code == 200 and "final answer" in response.text
        response = client.post(
            "/invoke",
            json={"prompt": "hello", "agentkitDiagnosticRunId": "run-invoke-1"},
        )
        assert response.status_code == 200
    roots = [s for s in traces.get_finished_spans() if s.name == "agent_server_request"]
    assert {s.attributes["agentkit.run.id"] for s in roots} == {
        "run-sse-1",
        "run-invoke-1",
    }


def test_diagnostic_identifier_rejects_unbounded_or_invalid_values():
    from pydantic import ValidationError

    for value in ["x" * 65, "not a run id", "\r\n"]:
        with pytest.raises(ValidationError):
            AgentkitRunRequest(
                app_name="a", user_id="u", session_id="s", agentkitDiagnosticRunId=value
            )

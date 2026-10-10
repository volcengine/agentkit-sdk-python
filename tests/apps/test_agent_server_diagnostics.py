import asyncio

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agentkit.apps.agent_server_app.diagnostics import mark_execution_event, phase
from agentkit.apps.agent_server_app.middleware import AgentkitTelemetryHTTPMiddleware
from agentkit.apps.agent_server_app.telemetry import telemetry


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "tracer", provider.get_tracer("test.runtime"))
    yield exporter
    provider.shutdown()


def test_upstream_trace_and_phase_parent_are_preserved(spans):
    observed = []

    async def app(scope, receive, send):
        with phase("runtime.session.get"):
            observed.append(trace.get_current_span().get_span_context().trace_id)
        mark_execution_event("agent.execution.finished", trace.get_current_span())
        await send({"type": "http.response.start", "status": 200})
        await send({"type": "http.response.body", "body": b"data: ok\n\n"})

    async def send(message):
        # 发送仍在 HTTP Span 内，不能把网络发送耗时归为 Agent 执行。
        assert trace.get_current_span().is_recording()

    upstream_trace = "12345678901234567890123456789012"
    upstream_span = "1234567890123456"
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/run_sse",
        "headers": [
            (b"traceparent", f"00-{upstream_trace}-{upstream_span}-01".encode())
        ],
    }
    asyncio.run(AgentkitTelemetryHTTPMiddleware(app)(scope, None, send))
    child, request = spans.get_finished_spans()
    assert request.context.trace_id == int(upstream_trace, 16) == observed[0]
    assert request.parent.span_id == int(upstream_span, 16)
    assert child.parent.span_id == request.context.span_id
    assert request.kind is trace.SpanKind.SERVER
    assert request.attributes["http.response.status_code"] == 200
    assert [event.name for event in request.events] == [
        "agent.execution.finished",
        "http.response.first_body",
    ]


def test_phase_error_keeps_type_without_sensitive_message(spans):
    with pytest.raises(ValueError):
        with phase("runtime.session.get"):
            raise ValueError("credential-bearing backend message")
    span = spans.get_finished_spans()[0]
    assert span.status.status_code is trace.StatusCode.ERROR
    assert span.attributes == {"error.type": "ValueError"}
    assert not span.events


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", [False, True])
async def test_real_runner_events_stay_on_request_span(spans, failed):
    from google.adk.agents import BaseAgent
    from google.adk.events import Event
    from google.genai import types
    import httpx

    from agentkit.apps.agent_server_app.agent_server_app import AgentkitAgentServerApp

    class ProbeAgent(BaseAgent):
        async def _run_async_impl(self, ctx):
            # 保留跨 yield 的子 Span，覆盖真实 Runner 中上下文尚未退出的情况。
            with telemetry.tracer.start_as_current_span("probe.agent"):
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(role="model", parts=[types.Part(text="ok")]),
                )
                if failed:
                    raise ValueError("test execution failed")

    server = AgentkitAgentServerApp(agent=ProbeAgent(name="diagnostic_probe"))
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/apps/diagnostic_probe/users/test_user/sessions/test_session", json={}
        )
        assert response.status_code == 200
        spans.clear()
        response = await client.post(
            "/run_sse",
            json={
                "appName": "diagnostic_probe",
                "userId": "test_user",
                "sessionId": "test_session",
                "newMessage": {"role": "user", "parts": [{"text": "test"}]},
                "streaming": True,
                "agentkitDiagnosticRunId": "diagnostic-123",
            },
            headers={
                "traceparent": "00-12345678901234567890123456789012-1234567890123456-01"
            },
        )
    assert response.status_code == 200
    exported = spans.get_finished_spans()
    request = next(span for span in exported if span.name == "agent_server_request")
    child = next(span for span in exported if span.name == "probe.agent")
    events = [event.name for event in request.events]
    assert "agent.execution.first_event" in events
    assert "http.response.first_body" in events
    assert "http.response.incomplete" not in events
    assert not any(event.name.startswith("agent.execution.") for event in child.events)
    assert request.attributes["agentkit.run.id"] == "diagnostic-123"
    assert request.attributes["gen_ai.session.id"] == "test_session"
    assert request.parent.span_id == int("1234567890123456", 16)
    assert request.end_time >= child.end_time
    if failed:
        assert "agent.execution.failed" in events
        assert "agent.execution.finished" not in events
        assert request.status.status_code is trace.StatusCode.ERROR
        assert request.attributes["error.type"] == "ValueError"
    else:
        assert "agent.execution.finished" in events
        assert "agent.execution.failed" not in events


def test_cancelled_request_is_closed(spans):
    async def app(scope, receive, send):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            AgentkitTelemetryHTTPMiddleware(app)(
                {"type": "http", "method": "POST", "path": "/run_sse", "headers": []},
                None,
                None,
            )
        )
    request = spans.get_finished_spans()[0]
    assert [event.name for event in request.events] == ["http.response.incomplete"]

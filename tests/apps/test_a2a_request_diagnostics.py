"""核对 A2A 诊断元数据不改变请求、任务或鉴权信息。"""

import json

import pytest
from a2a.server.agent_execution import AgentExecutor
from a2a.types import AgentCapabilities, AgentCard
from a2a.utils.message import new_agent_text_message
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from starlette.testclient import TestClient

from agentkit.apps.a2a_app.a2a_app import AgentkitA2aApp
from agentkit.apps.a2a_app.request_diagnostics import observe_a2a_request
from agentkit.apps.agent_server_app.telemetry import telemetry


@pytest.fixture
def exported_spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "tracer", provider.get_tracer("test.a2a.request"))
    yield exporter, provider
    provider.shutdown()


def rpc_payload(run_id="run-a2a-1", method="message/send"):
    return {
        "jsonrpc": "2.0",
        "id": "request-1",
        "method": method,
        "params": {
            "message": {
                "kind": "message",
                "messageId": "message-1",
                "role": "user",
                "parts": [{"kind": "text", "text": "synthetic"}],
            },
            "metadata": {
                "agentkitDiagnosticRunId": run_id,
                "authorization": "not-exported",
            },
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["valid", "stream", "invalid-id", "query", "oversized", "invalid-json"]
)
async def test_fragmented_body_is_forwarded_unchanged_and_only_execution_run_is_recorded(
    exported_spans, case
):
    exporter, provider = exported_spans
    payload = rpc_payload()
    if case == "stream":
        payload["method"] = "message/stream"
    elif case == "invalid-id":
        payload["params"]["metadata"]["agentkitDiagnosticRunId"] = {
            "untrusted": "value"
        }
    elif case == "query":
        payload["method"] = "tasks/get"
    elif case == "oversized":
        payload["params"]["message"]["parts"][0]["text"] = "x" * 70000
    body = b"{" if case == "invalid-json" else json.dumps(payload).encode()
    messages = [
        {"type": "http.request", "body": body[:7], "more_body": True},
        {"type": "http.request", "body": body[7:], "more_body": False},
    ]
    expected = [dict(message) for message in messages]
    calls = []

    async def receive():
        calls.append(1)
        return messages[len(calls) - 1]

    with provider.get_tracer("parent").start_as_current_span("request") as span:
        observed = observe_a2a_request({"method": "POST", "path": "/"}, receive, span)
        assert [await observed(), await observed()] == expected
    assert len(calls) == 2
    attributes = exporter.get_finished_spans()[0].attributes
    assert attributes == (
        {"agentkit.run.id": "run-a2a-1"} if case in ("valid", "stream") else {}
    )
    assert "not-exported" not in str(attributes)


def test_standalone_a2a_protocol_response_and_trace_parent_are_preserved(
    exported_spans, monkeypatch
):
    exporter, _ = exported_spans
    app = AgentkitA2aApp()

    @app.agent_executor()
    class SyntheticExecutor(AgentExecutor):
        async def execute(self, context, event_queue):
            assert context.metadata["agentkitDiagnosticRunId"] == "run-a2a-1"
            await event_queue.enqueue_event(
                new_agent_text_message("a2a-ok", context_id=context.context_id)
            )

        async def cancel(self, context, event_queue):
            raise NotImplementedError

    captured = {}
    monkeypatch.setattr(
        "agentkit.apps.a2a_app.a2a_app.uvicorn.run",
        lambda app, **kwargs: captured.update(app=app),
    )
    app.run(
        AgentCard(
            name="synthetic",
            description="test",
            url="http://testserver/",
            version="1",
            capabilities=AgentCapabilities(),
            default_input_modes=["text"],
            default_output_modes=["text"],
            skills=[],
        ),
        host="127.0.0.1",
    )
    trace_id = "12345678901234567890123456789012"
    parent_id = "1234567890123456"
    with TestClient(captured["app"]) as client:
        response = client.post(
            "/",
            json=rpc_payload(),
            headers={
                "traceparent": f"00-{trace_id}-{parent_id}-01",
                "Authorization": "Bearer synthetic-secret",
            },
        )
    assert response.status_code == 200
    assert response.json()["result"]["parts"][0]["text"] == "a2a-ok"
    roots = [
        span
        for span in exporter.get_finished_spans()
        if span.name == "agent_server_request"
    ]
    assert len(roots) == 1
    root = roots[0]
    assert root.attributes["agentkit.run.id"] == "run-a2a-1"
    assert root.context.trace_id == int(trace_id, 16)
    assert root.parent.span_id == int(parent_id, 16)
    assert "synthetic-secret" not in str(root.attributes)
    assert "not-exported" not in str(root.attributes)

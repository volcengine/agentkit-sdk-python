import json

import httpx
import pytest
from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.genai import types
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agentkit.apps.agent_server_app.agent_server_app import AgentkitAgentServerApp
from agentkit.apps.agent_server_app.telemetry import telemetry


@pytest.fixture
def invoke_probe(monkeypatch):
    received = []
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "tracer", provider.get_tracer("test.invoke"))

    class ProbeAgent(BaseAgent):
        async def _run_async_impl(self, ctx):
            received.append(ctx.user_content.parts[0].text)
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(role="model", parts=[types.Part(text="ok")]),
            )

    server = AgentkitAgentServerApp(agent=ProbeAgent(name="invoke_probe"))
    yield server, exporter, received
    provider.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,expected,run_id",
    [
        (
            {"prompt": "hello", "agentkitDiagnosticRunId": "api-run-123"},
            "hello",
            "api-run-123",
        ),
        (
            {"question": "hello", "agentkitDiagnosticRunId": "api-run-456"},
            json.dumps({"question": "hello"}),
            "api-run-456",
        ),
        ({"question": "hello"}, json.dumps({"question": "hello"}), None),
    ],
)
async def test_invoke_run_is_exported_without_changing_agent_input(
    invoke_probe, payload, expected, run_id
):
    server, exporter, received = invoke_probe
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/invoke", json=payload, headers={"session_id": "invoke-session"}
        )
    assert response.status_code == 200
    assert received == [expected]
    request = next(
        s for s in exporter.get_finished_spans() if s.name == "agent_server_request"
    )
    assert request.attributes.get("agentkit.run.id") == run_id
    assert request.attributes["gen_ai.session.id"] == "invoke-session"
    assert "agent.execution.finished" in [e.name for e in request.events]
    assert "agentkitDiagnosticRunId" not in received[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "run_id", ["secret/bad", "a" * 65, 42, {"unexpected": "value"}]
)
async def test_invalid_invoke_run_rejects_before_agent_and_does_not_echo_value(
    invoke_probe, run_id
):
    server, exporter, received = invoke_probe
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/invoke", json={"prompt": "hello", "agentkitDiagnosticRunId": run_id}
        )
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid diagnostic Run ID"}
    assert received == []
    spans = exporter.get_finished_spans()
    assert not any(s.name.startswith("runtime.session.") for s in spans)
    request = next(s for s in spans if s.name == "agent_server_request")
    assert "agentkit.run.id" not in request.attributes
    assert "agent.execution.failed" in [e.name for e in request.events]

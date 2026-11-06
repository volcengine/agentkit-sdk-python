import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from google.adk.agents import BaseAgent
from google.adk.events import Event
from google.genai import types
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import BaseModel

from agentkit.apps.agent_server_app.agent_server_app import (
    AgentkitAgentServerApp,
    DiagnosticRunAgentRequest,
)
from agentkit.apps.agent_server_app.non_streaming_diagnostics import (
    install_non_streaming_diagnostics,
)
from agentkit.apps.agent_server_app.middleware import AgentkitTelemetryHTTPMiddleware
from agentkit.apps.agent_server_app.telemetry import telemetry
from starlette.responses import Response


@pytest.fixture
def non_streaming_probe(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "tracer", provider.get_tracer("test.native.run"))
    received = []

    class ProbeAgent(BaseAgent):
        async def _run_async_impl(self, ctx):
            received.append(ctx.user_content.parts[0].text)
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(role="model", parts=[types.Part(text="ok")]),
            )

    server = AgentkitAgentServerApp(agent=ProbeAgent(name="native_run_probe"))
    yield server, exporter, received
    provider.shutdown()


@pytest.mark.asyncio
async def test_real_native_run_preserves_response_and_exports_round(
    non_streaming_probe,
):
    server, exporter, received = non_streaming_probe
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/apps/native_run_probe/users/test_user/sessions/test_session", json={}
        )
        assert created.status_code == 200
        exporter.clear()
        response = await client.post(
            "/run",
            json={
                "appName": "native_run_probe",
                "userId": "test_user",
                "sessionId": "test_session",
                "newMessage": {"role": "user", "parts": [{"text": "hello"}]},
                "agentkitDiagnosticRunId": "native-run-123",
            },
        )
    assert response.status_code == 200
    assert received == ["hello"]
    assert response.json()[0]["content"]["parts"] == [{"text": "ok"}]
    request = next(
        s for s in exporter.get_finished_spans() if s.name == "agent_server_request"
    )
    assert request.attributes["agentkit.run.id"] == "native-run-123"
    assert request.attributes["gen_ai.session.id"] == "test_session"
    assert "agent.execution.finished" in [e.name for e in request.events]
    assert request.attributes["http.response.status_code"] == 200


@pytest.mark.asyncio
async def test_missing_session_keeps_native_404_without_success(non_streaming_probe):
    server, exporter, received = non_streaming_probe
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=server.app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/run",
            json={
                "appName": "native_run_probe",
                "userId": "user",
                "sessionId": "missing",
                "agentkitDiagnosticRunId": "missing-run",
                "newMessage": {"role": "user", "parts": [{"text": "hello"}]},
            },
        )
    assert response.status_code == 404
    assert received == []
    request = next(
        s for s in exporter.get_finished_spans() if s.name == "agent_server_request"
    )
    assert "agent.execution.finished" not in [e.name for e in request.events]
    assert "agent.execution.failed" in [e.name for e in request.events]


@pytest.mark.asyncio
async def test_native_route_dependencies_and_response_filter_are_preserved():
    app = FastAPI()
    calls = []

    class NativeResponse(BaseModel):
        result: str
        unused: str | None = None

    async def authorize(request: Request):
        if request.headers.get("x-test-allowed") != "yes":
            raise HTTPException(status_code=403)

    @app.post(
        "/run", dependencies=[Depends(authorize)], response_model_exclude_none=True
    )
    async def native(
        req: DiagnosticRunAgentRequest, request: Request
    ) -> NativeResponse:
        calls.append((req.invocation_id, request.headers.get("x-test-allowed")))
        return {"result": "ok", "unused": None}

    async def prepare(req, request):
        pass

    assert install_non_streaming_diagnostics(app, DiagnosticRunAgentRequest, prepare)
    payload = {
        "appName": "app",
        "userId": "user",
        "sessionId": "session",
        "invocationId": "resume-framework-id",
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        denied = await client.post("/run", json=payload)
        assert denied.status_code == 403
        assert calls == []
        response = await client.post(
            "/run", json=payload, headers={"x-test-allowed": "yes"}
        )
    assert response.json() == {"result": "ok"}
    assert calls == [("resume-framework-id", "yes")]


@pytest.mark.asyncio
@pytest.mark.parametrize("request_aware", [False, True])
async def test_native_disconnect_response_is_preserved_without_success(
    non_streaming_probe, request_aware
):
    _, exporter, _ = non_streaming_probe
    app = FastAPI()

    async def old_native(req: DiagnosticRunAgentRequest):
        return Response(status_code=499)

    async def new_native(req: DiagnosticRunAgentRequest, request: Request):
        assert request.url.path == "/run"
        return Response(status_code=499)

    async def prepare(req, request):
        pass

    app.add_api_route(
        "/run", new_native if request_aware else old_native, methods=["POST"]
    )
    app.add_middleware(AgentkitTelemetryHTTPMiddleware)
    assert install_non_streaming_diagnostics(app, DiagnosticRunAgentRequest, prepare)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/run",
            json={"appName": "app", "userId": "user", "sessionId": "session"},
        )
    assert response.status_code == 499
    request = next(
        s for s in exporter.get_finished_spans() if s.name == "agent_server_request"
    )
    assert "agent.execution.finished" not in [e.name for e in request.events]
    assert "agent.execution.failed" in [e.name for e in request.events]

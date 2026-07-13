import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from google.genai import types

from agentkit.frameworks._common import UnsupportedFrameworkAgentError
from agentkit.frameworks import agentcore as agentcore_module
from agentkit.frameworks.agentcore import (
    AGENTCORE_SESSION_HEADER,
    AGENTCORE_WORKLOAD_ACCESS_TOKEN_HEADER,
    BedrockAgentCoreAgentkitBridge,
    attach_bedrock_agentcore_compat_routes,
)


def _ctx(text: str = "hi", session_id: str | None = "session-1"):
    session = (
        SimpleNamespace(id=session_id, app_name="app", user_id="user")
        if session_id
        else None
    )
    return SimpleNamespace(
        invocation_id="invocation-1",
        branch=None,
        user_content=types.UserContent(parts=[types.Part(text=text)]),
        session=session,
    )


def _event_text(event) -> str:
    if event.content is None:
        return ""
    return "".join(part.text or "" for part in event.content.parts)


def _collect_events(bridge: BedrockAgentCoreAgentkitBridge, ctx=None):
    async def run():
        events = []
        async for event in bridge._run_async_impl(ctx or _ctx()):
            events.append({"partial": event.partial, "text": _event_text(event)})
        return events

    return asyncio.run(run())


class AgentCoreLikeApp:
    def __init__(self, handler):
        self.handlers = {"main": handler}
        self._last_status_update_time = 42

    def get_current_ping_status(self):
        return SimpleNamespace(value="Healthy")


def _request(app: FastAPI, method: str, path: str, **kwargs) -> httpx.Response:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(run())


def _sse_payloads(response: httpx.Response):
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_bridge_adapts_agentcore_async_generator_entrypoint():
    async def invoke(payload, context=None):
        assert payload == {"prompt": "hi"}
        assert context.session_id == "session-1"
        yield {"type": "response.created", "runId": "run-1"}
        yield {"type": "response.thinking", "text": "hidden"}
        yield {"type": "response.output_text.delta", "delta": "he"}
        yield {"type": "response.output_text.delta", "delta": "llo"}
        yield {"type": "response.completed"}

    events = _collect_events(
        BedrockAgentCoreAgentkitBridge(AgentCoreLikeApp(invoke), name="agentcore")
    )

    assert events == [
        {"partial": True, "text": "he"},
        {"partial": True, "text": "llo"},
        {"partial": False, "text": "hello"},
    ]


def test_bridge_preserves_json_payload_when_adk_text_is_json():
    seen = {}

    async def invoke(payload, context=None):
        seen["payload"] = payload
        seen["session_id"] = context.session_id
        return {"answer": payload["prompt"], "roles": payload["role_codes"]}

    ctx = _ctx(json.dumps({"prompt": "hi", "role_codes": ["rm"]}))

    events = _collect_events(
        BedrockAgentCoreAgentkitBridge(AgentCoreLikeApp(invoke), name="agentcore"),
        ctx,
    )

    assert seen == {
        "payload": {"prompt": "hi", "role_codes": ["rm"]},
        "session_id": "session-1",
    }
    assert events[-1] == {"partial": False, "text": "hi"}


def test_bridge_accepts_callable_entrypoint_without_app_object():
    def invoke(payload):
        return {"answer": payload["prompt"]}

    events = _collect_events(BedrockAgentCoreAgentkitBridge(invoke))

    assert events == [{"partial": False, "text": "hi"}]


def test_bridge_handles_plain_text_invalid_json_and_sync_generator():
    def invoke(payload, context=None):
        assert payload == {"prompt": "{bad json"}
        assert context.session_id is None
        yield Response(b"he")
        yield b"ll"
        yield "o"
        yield {"type": "response.failed", "message": "!"}
        yield {"nested": {"value": 1}}
        yield 2

    events = _collect_events(
        BedrockAgentCoreAgentkitBridge(AgentCoreLikeApp(invoke), name="agentcore"),
        _ctx("{bad json", None),
    )

    assert events == [
        {"partial": True, "text": "he"},
        {"partial": True, "text": "ll"},
        {"partial": True, "text": "o"},
        {"partial": True, "text": "!"},
        {"partial": True, "text": '{"nested": {"value": 1}}'},
        {"partial": True, "text": "2"},
        {"partial": False, "text": 'hello!{"nested": {"value": 1}}2'},
    ]


def test_bridge_rejects_objects_without_agentcore_entrypoint():
    with pytest.raises(UnsupportedFrameworkAgentError, match="Bedrock AgentCore"):
        BedrockAgentCoreAgentkitBridge(object())


def test_real_bedrock_agentcore_app_is_supported_when_package_is_available():
    runtime = pytest.importorskip("bedrock_agentcore.runtime")
    app = runtime.BedrockAgentCoreApp()

    @app.entrypoint
    async def invoke(payload, context=None):
        yield {
            "type": "response.output_text.delta",
            "delta": f"{context.session_id}:{payload['prompt']}",
        }

    events = _collect_events(BedrockAgentCoreAgentkitBridge(app), _ctx("hi", "s-real"))

    assert events == [
        {"partial": True, "text": "s-real:hi"},
        {"partial": False, "text": "s-real:hi"},
    ]


def test_agentcore_compat_invocations_preserves_payload_context_and_sse():
    async def invoke(payload, context=None):
        assert payload == {"prompt": "hi", "login_token": "token-1"}
        assert context.session_id == "session-http"
        yield {"type": "response.output_text.delta", "delta": payload["login_token"]}
        yield {"custom": "event"}

    app = FastAPI()
    root = FastAPI()
    app.mount("/", root)
    attach_bedrock_agentcore_compat_routes(app, AgentCoreLikeApp(invoke))

    response = _request(
        app,
        "POST",
        "/invocations",
        headers={AGENTCORE_SESSION_HEADER: "session-http"},
        json={"prompt": "hi", "login_token": "token-1"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert _sse_payloads(response) == [
        {"type": "response.output_text.delta", "delta": "token-1"},
        {"custom": "event"},
    ]


def test_agentcore_compat_invocations_returns_json_for_non_streaming_result():
    async def invoke(payload):
        return {"answer": payload["prompt"]}

    app = FastAPI()
    attach_bedrock_agentcore_compat_routes(app, AgentCoreLikeApp(invoke))

    response = _request(app, "POST", "/invocations", json={"prompt": "hi"})

    assert response.status_code == 200
    assert response.json() == {"answer": "hi"}


def test_agentcore_compat_invocations_preserves_response_results():
    async def invoke(payload):
        return JSONResponse({"answer": payload["prompt"]}, status_code=202)

    app = FastAPI()
    attach_bedrock_agentcore_compat_routes(app, AgentCoreLikeApp(invoke))

    response = _request(app, "POST", "/invocations", json={"prompt": "hi"})

    assert response.status_code == 202
    assert response.json() == {"answer": "hi"}


def test_agentcore_compat_invocations_rejects_invalid_json():
    app = FastAPI()
    attach_bedrock_agentcore_compat_routes(
        app,
        AgentCoreLikeApp(lambda payload: payload),
    )

    response = _request(
        app,
        "POST",
        "/invocations",
        content="{bad",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Request body must be valid JSON."}


def test_agentcore_compat_invocations_returns_task_action_response():
    class TaskActionApp(AgentCoreLikeApp):
        def _handle_task_action(self, payload):
            return JSONResponse({"task": payload["taskAction"]})

    app = FastAPI()
    attach_bedrock_agentcore_compat_routes(
        app,
        TaskActionApp(lambda payload: {"answer": "not reached"}),
    )

    response = _request(
        app,
        "POST",
        "/invocations",
        json={"taskAction": "cancel"},
    )

    assert response.status_code == 200
    assert response.json() == {"task": "cancel"}


def test_agentcore_compat_invocations_uses_source_context_builder():
    seen = {}

    class ContextApp(AgentCoreLikeApp):
        def _build_request_context(self, request):
            return SimpleNamespace(session_id="built-session", request=request)

    async def invoke(payload, context=None):
        seen["session_id"] = context.session_id
        seen["request_path"] = context.request.url.path
        return {"answer": payload["prompt"]}

    app = FastAPI()
    attach_bedrock_agentcore_compat_routes(app, ContextApp(invoke))

    response = _request(app, "POST", "/invocations", json={"prompt": "hi"})

    assert response.status_code == 200
    assert response.json() == {"answer": "hi"}
    assert seen == {"session_id": "built-session", "request_path": "/invocations"}


def test_agentcore_compat_invocations_exposes_stream_errors_as_sse():
    async def invoke(payload, context=None):
        async def stream():
            yield {"delta": "before"}
            raise RuntimeError("boom")

        return stream()

    app = FastAPI()
    attach_bedrock_agentcore_compat_routes(app, AgentCoreLikeApp(invoke))

    response = _request(app, "POST", "/invocations", json={"prompt": "hi"})

    assert response.status_code == 200
    assert _sse_payloads(response) == [
        {"delta": "before"},
        {
            "error": "boom",
            "error_type": "RuntimeError",
            "message": "An error occurred during streaming",
        },
    ]


def test_agentcore_compat_prefix_and_fallback_ping():
    app = FastAPI()
    attach_bedrock_agentcore_compat_routes(
        app,
        AgentCoreLikeApp(lambda payload: payload),
        prefix="/agentcore/",
    )

    response = _request(app, "GET", "/agentcore/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "Healthy", "time_of_last_update": 42}

    class NoStatusApp:
        handlers = {"main": lambda payload: payload}

    fallback = FastAPI()
    attach_bedrock_agentcore_compat_routes(fallback, NoStatusApp(), prefix="/")

    fallback_response = _request(fallback, "GET", "/ping")

    assert fallback_response.status_code == 200
    assert fallback_response.json() == {"status": "Healthy"}


def test_agentcore_compat_rejects_relative_prefix():
    with pytest.raises(ValueError, match="prefix"):
        attach_bedrock_agentcore_compat_routes(
            FastAPI(),
            AgentCoreLikeApp(lambda payload: payload),
            prefix="agentcore",
        )


def test_agentcore_compat_ping_uses_source_status():
    app = FastAPI()
    attach_bedrock_agentcore_compat_routes(app, AgentCoreLikeApp(lambda payload: payload))

    response = _request(app, "GET", "/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "Healthy", "time_of_last_update": 42}


def test_agentcore_private_edge_helpers(monkeypatch):
    assert agentcore_module._takes_context(42) is False

    context_module = pytest.importorskip("bedrock_agentcore.runtime.context")
    monkeypatch.setattr(
        context_module,
        "RequestContext",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("bad context")),
    )

    context = agentcore_module._context_object(
        request_id="request-1",
        session_id="session-1",
        headers={AGENTCORE_WORKLOAD_ACCESS_TOKEN_HEADER: "workload-token"},
    )

    assert context.session_id == "session-1"
    assert context.request_headers[AGENTCORE_WORKLOAD_ACCESS_TOKEN_HEADER] == "workload-token"

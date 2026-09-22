from __future__ import annotations

from pydantic import PrivateAttr
from starlette.testclient import TestClient

from google.adk.agents.base_agent import BaseAgent
from google.adk.apps.app import App
from google.adk.events import Event
from google.genai import types

from agentkit.apps import AgentkitAgentServerApp
from agentkit.plugins.llm_shield import (
    LLM_SHIELD_BLOCK_MESSAGE,
    LLMShieldPlugin,
)


class _RecordingAgent(BaseAgent):
    _calls: int = PrivateAttr(default=0)

    @property
    def calls(self) -> int:
        return self._calls

    async def _run_async_impl(self, ctx):
        self._calls += 1
        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            content=types.Content(
                role="model", parts=[types.Part(text="unsafe model output")]
            ),
            partial=False,
        )


def _server(monkeypatch, *, block_role: str):
    plugin = LLMShieldPlugin(app_id="app-test", region="cn-beijing")
    calls = []

    async def moderate(text, *, role):
        calls.append((text, role))
        return LLM_SHIELD_BLOCK_MESSAGE if role == block_role else None

    monkeypatch.setattr(plugin, "moderate_text", moderate)
    agent = _RecordingAgent(name="shield_agent")
    runtime_app = App(name="shield_app", root_agent=agent, plugins=[plugin])
    return AgentkitAgentServerApp(app=runtime_app), agent, calls


def _run_payload(prompt: str, *, streaming: bool) -> dict:
    return {
        "appName": "shield_app",
        "userId": "shield-user",
        "sessionId": "shield-session",
        "newMessage": {"role": "user", "parts": [{"text": prompt}]},
        "streaming": streaming,
    }


def _create_session(client: TestClient) -> None:
    response = client.post(
        "/apps/shield_app/users/shield-user/sessions/shield-session", json={}
    )
    assert response.status_code == 200


def test_run_sse_blocks_input_before_agent_execution(monkeypatch):
    server, agent, calls = _server(monkeypatch, block_role="user")

    with TestClient(server.app) as client:
        _create_session(client)
        response = client.post(
            "/run_sse", json=_run_payload("unsafe input", streaming=True)
        )

    assert response.status_code == 200
    assert LLM_SHIELD_BLOCK_MESSAGE in response.text
    assert agent.calls == 0
    assert calls == [("unsafe input", "user")]


def test_run_replaces_unsafe_output_before_response(monkeypatch):
    server, agent, calls = _server(monkeypatch, block_role="assistant")

    with TestClient(server.app) as client:
        _create_session(client)
        response = client.post("/run", json=_run_payload("safe input", streaming=False))
        session = client.get(
            "/apps/shield_app/users/shield-user/sessions/shield-session"
        )

    assert response.status_code == 200
    assert session.status_code == 200
    assert LLM_SHIELD_BLOCK_MESSAGE in response.text
    assert "unsafe model output" not in response.text
    assert LLM_SHIELD_BLOCK_MESSAGE in session.text
    assert "unsafe model output" not in session.text
    assert agent.calls == 1
    assert calls == [
        ("safe input", "user"),
        ("unsafe model output", "assistant"),
    ]


def test_invoke_uses_the_same_app_plugin(monkeypatch):
    server, agent, calls = _server(monkeypatch, block_role="assistant")

    with TestClient(server.app) as client:
        response = client.post(
            "/invoke",
            json={"prompt": "safe input"},
            headers={"user_id": "shield-user", "session_id": "shield-invoke"},
        )

    assert response.status_code == 200
    assert LLM_SHIELD_BLOCK_MESSAGE in response.text
    assert "unsafe model output" not in response.text
    assert agent.calls == 1
    assert calls == [
        ("safe input", "user"),
        ("unsafe model output", "assistant"),
    ]


def test_a2a_uses_the_same_app_plugin(monkeypatch):
    server, agent, calls = _server(monkeypatch, block_role="user")

    with TestClient(server.app) as client:
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": "request-1",
                "method": "message/send",
                "params": {
                    "message": {
                        "kind": "message",
                        "messageId": "message-1",
                        "role": "user",
                        "parts": [{"kind": "text", "text": "unsafe input"}],
                    },
                    "configuration": {"blocking": True},
                },
            },
        )

    assert response.status_code == 200
    assert LLM_SHIELD_BLOCK_MESSAGE in response.text
    assert agent.calls == 0
    assert calls == [("unsafe input", "user")]

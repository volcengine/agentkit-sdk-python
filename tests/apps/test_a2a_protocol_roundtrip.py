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

"""Offline protocol-level round-trip tests for ``AgentkitA2aApp``.

Unlike ``test_a2a_app.py`` (which unit-tests decorator guards and never builds
the real server), these tests exercise the FULL production build path of
``AgentkitA2aApp.run()``: the real ``A2AStarletteApplication`` is assembled with
a ``DefaultRequestHandler`` + ``InMemoryTaskStore`` and ``.build()`` into a real
Starlette app. Only the final ``uvicorn.run`` socket bind is stubbed out; the
captured ASGI app is then driven in-process via ``starlette.testclient.TestClient``
(no network).

Contract assertions are anchored on the OFFICIAL ``a2a.types`` pydantic models
(``AgentCard.model_validate`` / ``SendMessageResponse.model_validate``), so a
wire-format regression in a2a-sdk (field renames, alias changes, envelope
shape) fails these tests even if agentkit's own code is untouched. Assertions
about agentkit-specific behavior (extra routes, fixed reply text) are kept
separate from the schema-validation assertions.

Covered protocol surface (a2a-sdk 0.3.7):
  * Agent card discovery: GET /.well-known/agent-card.json (canonical) and the
    deprecated /.well-known/agent.json alias, both validated against AgentCard.
  * JSON-RPC 2.0 ``message/send``: request serialized from a real
    ``SendMessageRequest`` (by_alias camelCase wire format), response parsed
    into ``SendMessageResponse`` -> ``SendMessageSuccessResponse`` -> Message.
"""

from __future__ import annotations

import uuid

import pytest
from a2a.server.agent_execution import AgentExecutor
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Message,
    MessageSendParams,
    Part,
    Role,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    TextPart,
)
from a2a.utils import new_agent_text_message
from starlette.applications import Starlette
from starlette.testclient import TestClient

from agentkit.apps.a2a_app import a2a_app as a2a_app_module
from agentkit.apps.a2a_app.a2a_app import AgentkitA2aApp

AGENT_CARD_PATH = "/.well-known/agent-card.json"
DEPRECATED_AGENT_CARD_PATH = "/.well-known/agent.json"
RPC_PATH = "/"

FIXED_REPLY_TEXT = "fixed-reply-from-stub-executor"


class _RecordingUvicorn:
    """Stands in for the ``uvicorn`` module inside ``a2a_app``; captures the
    built Starlette app instead of binding a socket."""

    def __init__(self) -> None:
        self.app: Starlette | None = None
        self.kwargs: dict | None = None

    def run(self, app, **kwargs) -> None:
        self.app = app
        self.kwargs = kwargs


def _minimal_agent_card() -> AgentCard:
    """The smallest AgentCard that satisfies a2a.types' required fields."""
    return AgentCard(
        name="stub-agent",
        description="Protocol round-trip test agent",
        url="http://testserver/",
        version="0.0.1",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id="echo",
                name="Echo",
                description="Returns a fixed reply.",
                tags=["test"],
            )
        ],
    )


@pytest.fixture
def built_app(monkeypatch) -> Starlette:
    """Runs the real AgentkitA2aApp.run() build path and returns the Starlette
    app that would have been served by uvicorn.

    A fresh executor class is defined per invocation because the
    ``agent_executor`` decorator mutates ``cls.execute`` in place (a shared
    class would get double-wrapped across tests).
    """
    recorder = _RecordingUvicorn()
    monkeypatch.setattr(a2a_app_module, "uvicorn", recorder)

    app = AgentkitA2aApp()

    @app.agent_executor()
    class _FixedReplyExecutor(AgentExecutor):
        async def execute(self, context, event_queue):
            # A Message event is terminal for message/send: the handler
            # returns it as the JSON-RPC result.
            await event_queue.enqueue_event(
                new_agent_text_message(
                    FIXED_REPLY_TEXT,
                    context_id=context.context_id,
                    task_id=context.task_id,
                )
            )

        async def cancel(self, context, event_queue):  # pragma: no cover
            raise NotImplementedError

    app.run(_minimal_agent_card(), host="127.0.0.1", port=0)

    assert recorder.app is not None, "run() never reached uvicorn.run"
    return recorder.app


# ---------------------------------------------------------------------------
# Agent card discovery (GET well-known path) -- schema contract
# ---------------------------------------------------------------------------


def test_agent_card_endpoint_returns_schema_valid_agent_card(built_app):
    with TestClient(built_app) as client:
        response = client.get(AGENT_CARD_PATH)

    assert response.status_code == 200
    # Contract assertion: the served card must round-trip through the official
    # a2a.types model (camelCase wire aliases included).
    card = AgentCard.model_validate(response.json())
    assert card.name == "stub-agent"
    assert card.version == "0.0.1"
    assert [skill.id for skill in card.skills] == ["echo"]


def test_deprecated_agent_json_path_serves_the_same_schema_valid_card(built_app):
    # a2a-sdk 0.3.7 still serves the pre-rename path for backward compat.
    with TestClient(built_app) as client:
        response = client.get(DEPRECATED_AGENT_CARD_PATH)

    assert response.status_code == 200
    card = AgentCard.model_validate(response.json())
    assert card.name == "stub-agent"


# ---------------------------------------------------------------------------
# JSON-RPC message/send round trip -- schema contract
# ---------------------------------------------------------------------------


def _send_message_payload(text: str) -> dict:
    """Build a message/send request through the official request model so the
    outgoing wire format is also produced (and thus checked) by a2a.types."""
    request = SendMessageRequest(
        id=str(uuid.uuid4()),
        params=MessageSendParams(
            message=Message(
                message_id=str(uuid.uuid4()),
                role=Role.user,
                parts=[Part(root=TextPart(text=text))],
            )
        ),
    )
    return request.model_dump(mode="json", by_alias=True, exclude_none=True)


def test_message_send_roundtrip_returns_schema_valid_success_response(built_app):
    payload = _send_message_payload("hello over the real protocol stack")

    with TestClient(built_app) as client:
        response = client.post(RPC_PATH, json=payload)

    assert response.status_code == 200

    # Contract assertions: parse with the official union response model.
    parsed = SendMessageResponse.model_validate(response.json())
    assert isinstance(parsed.root, SendMessageSuccessResponse)
    assert parsed.root.jsonrpc == "2.0"
    assert parsed.root.id == payload["id"]

    result = parsed.root.result
    assert isinstance(result, Message)
    assert result.role == Role.agent

    # Behavior assertion (agentkit + stub executor): the fixed reply text made
    # it through executor -> event queue -> request handler -> JSON-RPC result.
    text_parts = [
        part.root.text for part in result.parts if isinstance(part.root, TextPart)
    ]
    assert text_parts == [FIXED_REPLY_TEXT]


# ---------------------------------------------------------------------------
# agentkit-specific routes registered by run() on top of the protocol app
# ---------------------------------------------------------------------------


def test_run_build_path_registers_agentkit_extra_routes_alongside_protocol_routes(
    built_app,
):
    # These are implementation details of AgentkitA2aApp.run(), asserted
    # separately from the protocol contract above.
    route_paths = {route.path for route in built_app.routes}
    assert RPC_PATH in route_paths
    assert AGENT_CARD_PATH in route_paths
    assert "/ping" in route_paths
    assert "/env" in route_paths

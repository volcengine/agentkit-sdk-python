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

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
from google.adk.agents.base_agent import BaseAgent
from starlette.testclient import TestClient
from veadk.memory.short_term_memory import ShortTermMemory

from agentkit.apps.agent_server_app.agent_server_app import (
    AgentkitAgentServerApp,
    _run_a2a_app_lifespan,
)


def test_run_a2a_app_lifespan_uses_lifespan_context_without_on_startup():
    events: list[str] = []

    @asynccontextmanager
    async def lifespan_context(app):
        events.append(f"enter:{app.name}")
        yield
        events.append(f"exit:{app.name}")

    app = SimpleNamespace(
        name="a2a-app",
        router=SimpleNamespace(lifespan_context=lifespan_context),
    )

    async def exercise():
        async with _run_a2a_app_lifespan(app):
            events.append("inside")

    asyncio.run(exercise())

    assert events == ["enter:a2a-app", "inside", "exit:a2a-app"]


def test_run_a2a_app_lifespan_falls_back_to_legacy_startup_shutdown_handlers():
    events: list[str] = []

    def sync_startup():
        events.append("sync-startup")

    async def async_startup():
        events.append("async-startup")

    async def async_shutdown():
        events.append("async-shutdown")

    app = SimpleNamespace(
        router=SimpleNamespace(
            on_startup=[sync_startup, async_startup],
            on_shutdown=[async_shutdown],
        ),
    )

    async def exercise():
        async with _run_a2a_app_lifespan(app):
            events.append("inside")

    asyncio.run(exercise())

    assert events == [
        "sync-startup",
        "async-startup",
        "inside",
        "async-shutdown",
    ]


def test_run_a2a_app_lifespan_raises_clear_error_when_app_has_no_router():
    async def exercise():
        async with _run_a2a_app_lifespan(SimpleNamespace()):
            pass

    with pytest.raises(RuntimeError, match="A2A server app has no router"):
        asyncio.run(exercise())


def test_agent_server_app_startup_initializes_mounted_a2a_agent_card_route():
    root_agent = BaseAgent(
        name="agent_server_a2a_test_agent",
        description="Agent used to verify mounted A2A startup.",
    )
    server = AgentkitAgentServerApp(
        agent=root_agent,
        short_term_memory=ShortTermMemory(backend="local"),
    )

    with TestClient(server.app) as client:
        assert client.get("/list-apps").json() == ["agent_server_a2a_test_agent"]
        response = client.get(AGENT_CARD_WELL_KNOWN_PATH)

    assert response.status_code == 200
    assert response.json()["name"] == "agent_server_a2a_test_agent"

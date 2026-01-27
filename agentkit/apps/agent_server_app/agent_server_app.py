# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

import json
import logging
from contextlib import asynccontextmanager
from typing import Any
from typing_extensions import override

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.apps.app import App
from google.adk.artifacts.in_memory_artifact_service import (
    InMemoryArtifactService,
)
from google.adk.auth.credential_service.in_memory_credential_service import (
    InMemoryCredentialService,
)
from google.adk.cli.adk_web_server import AdkWebServer
from google.adk.cli.utils.base_agent_loader import BaseAgentLoader
from google.adk.evaluation.local_eval_set_results_manager import (
    LocalEvalSetResultsManager,
)
from google.adk.evaluation.local_eval_sets_manager import LocalEvalSetsManager
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.sessions.base_session_service import BaseSessionService
from google.adk.utils.context_utils import Aclosing
from google.genai import types
from opentelemetry import trace
from veadk import Agent
from veadk.runner import Runner
from veadk.memory.short_term_memory import ShortTermMemory

from agentkit.apps.agent_server_app.middleware import (
    AgentkitTelemetryHTTPMiddleware,
)
from agentkit.apps.agent_server_app.telemetry import telemetry
from agentkit.apps.base_app import BaseAgentkitApp

logger = logging.getLogger(__name__)


class AgentKitAgentLoader(BaseAgentLoader):
    def __init__(self, agent_or_app: BaseAgent | App) -> None:
        super().__init__()

        self.agent_or_app = agent_or_app
        if isinstance(agent_or_app, App):
            self.root_agent = agent_or_app.root_agent
            self.app_name = agent_or_app.name or self.root_agent.name
        else:
            self.root_agent = agent_or_app
            self.app_name = agent_or_app.name

    @override
    def load_agent(self, agent_name: str) -> BaseAgent | App:
        if agent_name != self.app_name:
            raise ValueError(
                f"Unknown agent '{agent_name}'. Expected '{self.app_name}'."
            )
        return self.agent_or_app

    @override
    def list_agents(self) -> list[str]:
        return [self.app_name]

    @override
    def list_agents_detailed(self) -> list[dict[str, Any]]:
        name = self.app_name
        description = getattr(self.root_agent, "description", "") or ""
        return [
            {
                "name": name,
                "root_agent_name": self.root_agent.name,
                "description": description,
                "language": "python",
            }
        ]


class AgentkitAgentServerApp(BaseAgentkitApp):
    def __init__(
        self,
        agent: BaseAgent | App | None = None,
        short_term_memory: BaseSessionService | ShortTermMemory | None = None,
        *,
        app: App | None = None,
    ) -> None:
        super().__init__()

        if short_term_memory is None:
            raise TypeError("short_term_memory is required.")

        if app is not None and agent is not None:
            raise TypeError("Only one of 'agent' or 'app' can be provided.")

        entry = app if app is not None else agent
        if entry is None:
            raise TypeError("Either 'agent' or 'app' must be provided.")

        root_agent = entry.root_agent if isinstance(entry, App) else entry

        _artifact_service = InMemoryArtifactService()
        _credential_service = InMemoryCredentialService()

        _eval_sets_manager = LocalEvalSetsManager(agents_dir=".")
        _eval_set_results_manager = LocalEvalSetResultsManager(agents_dir=".")

        self.server = AdkWebServer(
            agent_loader=AgentKitAgentLoader(entry),
            session_service=short_term_memory
            if isinstance(short_term_memory, BaseSessionService)
            else short_term_memory.session_service,
            memory_service=root_agent.long_term_memory
            if isinstance(root_agent, Agent) and root_agent.long_term_memory
            else InMemoryMemoryService(),
            artifact_service=_artifact_service,
            credential_service=_credential_service,
            eval_sets_manager=_eval_sets_manager,
            eval_set_results_manager=_eval_set_results_manager,
            agents_dir=".",
        )

        runner = Runner(agent=root_agent)
        _a2a_server_app = to_a2a(agent=root_agent, runner=runner)

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # trigger A2A server app startup
            logger.info("Triggering A2A server app startup within API server...")
            for handler in _a2a_server_app.router.on_startup:
                await handler()
            yield

        self.app = self.server.get_fast_api_app(lifespan=lifespan)

        # Attach ASGI middleware for unified telemetry across all routes
        self.app.add_middleware(AgentkitTelemetryHTTPMiddleware)

        async def _invoke_compat(request: Request):
            # Use current request span from middleware for telemetry
            span = trace.get_current_span()

            # Extract headers (fallback keys supported)
            headers = request.headers
            telemetry_headers = {
                k: v
                for k, v in dict(headers).items()
                if k.lower() not in {"authorization", "token"}
            }
            user_id = headers.get("user_id") or "agentkit_user"
            session_id = headers.get("session_id") or ""

            # Determine app_name from loader
            app_names = self.server.agent_loader.list_agents()
            if not app_names:
                raise HTTPException(status_code=404, detail="No agents configured")
            app_name = app_names[0]

            # Parse payload and convert to ADK Content
            try:
                payload = await request.json()
            except Exception:
                payload = None

            text = payload.get("prompt") if isinstance(payload, dict) else None
            if text is None:
                if payload is not None:
                    try:
                        text = json.dumps(payload, ensure_ascii=False)
                    except Exception:
                        text = ""
                else:
                    try:
                        body_bytes = await request.body()
                        text = body_bytes.decode("utf-8")
                    except Exception:
                        text = ""
            content = types.UserContent(parts=[types.Part(text=text or "")])

            # trace request attributes on current span
            telemetry.trace_agent_server(
                func_name="_invoke_compat",
                span=span,
                headers=telemetry_headers,
                text=text or "",
            )

            # Ensure session exists
            session = await self.server.session_service.get_session(
                app_name=app_name, user_id=user_id, session_id=session_id
            )
            if not session:
                await self.server.session_service.create_session(
                    app_name=app_name, user_id=user_id, session_id=session_id
                )

            async def event_generator():
                try:
                    runner = await self.server.get_runner_async(app_name)
                    async with Aclosing(
                        runner.run_async(
                            user_id=user_id,
                            session_id=session_id,
                            new_message=content,
                            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
                        )
                    ) as agen:
                        async for event in agen:
                            yield (
                                "data: "
                                + event.model_dump_json(
                                    exclude_none=True, by_alias=True
                                )
                                + "\n\n"
                            )
                    # finish span on successful end of stream handled by middleware
                    pass
                except Exception as e:
                    yield f'data: {{"error": "{str(e)}"}}\n\n'
                    telemetry.trace_agent_server_finish(
                        path="/invoke", func_result="", exception=e
                    )

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        # Compatibility route for AgentKit CLI invoke
        self.app.add_api_route("/invoke", _invoke_compat, methods=["POST"])

        # Mount A2A server app last to avoid shadowing API routes like `/invoke`.
        self.app.mount("/", _a2a_server_app)

    def run(self, host: str, port: int = 8000) -> None:
        """Run the app with Uvicorn server."""
        uvicorn.run(self.app, host=host, port=port)

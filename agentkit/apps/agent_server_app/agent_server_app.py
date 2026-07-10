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

import inspect
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

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
from google.adk.cli.adk_web_server import AdkWebServer, RunAgentRequest
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
from typing_extensions import override
from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.runner import Runner

from agentkit.apps.agent_server_app.middleware import (
    AgentkitTelemetryHTTPMiddleware,
)
from agentkit.apps.agent_server_app.origin import (
    add_cors_compat_middleware,
    adk_supports_regex_origins,
    resolve_agentkit_allow_origins,
    split_allow_origins,
    supports_get_fast_api_kwarg,
)
from agentkit.apps.agent_server_app.telemetry import telemetry
from agentkit.apps.base_app import BaseAgentkitApp

logger = logging.getLogger(__name__)


async def _call_lifecycle_handler(handler: Any) -> None:
    result = handler()
    if inspect.isawaitable(result):
        await result


@asynccontextmanager
async def _run_a2a_app_lifespan(a2a_app: Any) -> AsyncIterator[None]:
    router = getattr(a2a_app, "router", None)
    if router is None:
        raise RuntimeError("A2A server app has no router; cannot initialize lifecycle.")

    lifespan_context = getattr(router, "lifespan_context", None)
    if lifespan_context is not None:
        async with lifespan_context(a2a_app):
            yield
        return

    startup_handlers = tuple(getattr(router, "on_startup", ()) or ())
    shutdown_handlers = tuple(getattr(router, "on_shutdown", ()) or ())
    for handler in startup_handlers:
        await _call_lifecycle_handler(handler)
    try:
        yield
    finally:
        for handler in shutdown_handlers:
            await _call_lifecycle_handler(handler)


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
        allow_origins: list[str] | None = None,
        allow_origin_regex: str | list[str] | None = None,
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

        runner = Runner(
            agent=root_agent,
            short_term_memory=short_term_memory
            if isinstance(short_term_memory, ShortTermMemory)
            else None,
        )
        _a2a_server_app = to_a2a(agent=root_agent, runner=runner)

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # trigger A2A server app startup
            logger.info(
                "Triggering A2A server app lifespan within API server..."
            )
            async with _run_a2a_app_lifespan(_a2a_server_app):
                yield

        resolved_allow_origins = resolve_agentkit_allow_origins(
            allow_origins=allow_origins,
            allow_origin_regex=allow_origin_regex,
        )
        get_fast_api_app = self.server.get_fast_api_app
        get_fast_api_app_kwargs: dict[str, Any] = {"lifespan": lifespan}
        supports_allow_origins = supports_get_fast_api_kwarg(
            get_fast_api_app, "allow_origins"
        )
        supports_regex_origins = adk_supports_regex_origins()
        needs_cors_compat_middleware = False

        if supports_allow_origins:
            if supports_regex_origins:
                get_fast_api_app_kwargs["allow_origins"] = (
                    resolved_allow_origins or None
                )
            else:
                literal_origins, combined_regex = split_allow_origins(
                    resolved_allow_origins
                )
                get_fast_api_app_kwargs["allow_origins"] = literal_origins or None
                needs_cors_compat_middleware = combined_regex is not None
        else:
            needs_cors_compat_middleware = bool(resolved_allow_origins)

        self.app = get_fast_api_app(**get_fast_api_app_kwargs)

        if needs_cors_compat_middleware:
            add_cors_compat_middleware(self.app, resolved_allow_origins)

        @self.app.post("/run_sse")
        async def run_agent_sse(req: RunAgentRequest) -> StreamingResponse:
            logger.info("Overriding run_agent_sse endpoint...")
            # SSE endpoint
            session = await self.server.session_service.get_session(
                app_name=req.app_name,
                user_id=req.user_id,
                session_id=req.session_id,
            )
            if not session:
                e = HTTPException(status_code=404, detail="Session not found")
                telemetry.trace_agent_server_finish(
                    path="/run_sse", func_result="", exception=e
                )
                raise e

            # Convert the events to properly formatted SSE
            async def event_generator():
                try:
                    stream_mode = (
                        StreamingMode.SSE if req.streaming else StreamingMode.NONE
                    )
                    runner = await self.server.get_runner_async(req.app_name)
                    async with Aclosing(
                        runner.run_async(
                            user_id=req.user_id,
                            session_id=req.session_id,
                            new_message=req.new_message,
                            state_delta=req.state_delta,
                            run_config=RunConfig(streaming_mode=stream_mode),
                            invocation_id=req.invocation_id,
                        )
                    ) as agen:
                        async for event in agen:
                            # ADK Web renders artifacts from `actions.artifactDelta`
                            # during part processing *and* during action processing
                            # 1) the original event with `artifactDelta` cleared (content)
                            # 2) a content-less "action-only" event carrying `artifactDelta`
                            events_to_stream = [event]
                            if (
                                event.actions.artifact_delta
                                and event.content
                                and event.content.parts
                            ):
                                content_event = event.model_copy(deep=True)
                                content_event.actions.artifact_delta = {}
                                artifact_event = event.model_copy(deep=True)
                                artifact_event.content = None
                                events_to_stream = [
                                    content_event,
                                    artifact_event,
                                ]
                            for event_to_stream in events_to_stream:
                                sse_event = event_to_stream.model_dump_json(
                                    exclude_none=True,
                                    by_alias=True,
                                )
                                logger.debug(
                                    "Generated event in agent run streaming: %s",
                                    sse_event,
                                )
                                yield f"data: {sse_event}\n\n"
                except Exception as e:
                    logger.exception("Error in event_generator: %s", e)
                    telemetry.trace_agent_server_finish(
                        path="/run_sse", func_result="", exception=e
                    )
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                # Returns a streaming response with the proper media type for SSE

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
            )

        # Move the custom /run_sse route to the beginning of the routes list for priority matching (without deleting the ADK default route)
        routes = self.app.router.routes
        for i, r in enumerate(routes):
            if (
                getattr(r, "path", None) == "/run_sse"
                and "POST" in getattr(r, "methods", set())
                and getattr(r, "endpoint", None) == run_agent_sse
            ):
                routes.insert(0, routes.pop(i))
                break

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
            # trace request attributes on current span
            telemetry.trace_agent_server(
                func_name="_invoke_compat",
                span=span,
                headers=telemetry_headers,
                text="",
            )

            user_id = headers.get("user_id") or "agentkit_user"
            session_id = headers.get("session_id") or ""

            # Determine app_name from loader
            app_names = self.server.agent_loader.list_agents()
            if not app_names:
                exception = HTTPException(
                    status_code=404, detail="No agents configured"
                )
                telemetry.trace_agent_server_finish(
                    path="/invoke", func_result="", exception=exception
                )
                raise exception
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
                            run_config=RunConfig(
                                streaming_mode=StreamingMode.SSE
                            ),
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
                    telemetry.trace_agent_server_finish(
                        path="/invoke", func_result="", exception=e
                    )
                    yield f'data: {{"error": "{str(e)}"}}\n\n'

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

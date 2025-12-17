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

from typing import Callable

from opentelemetry import trace
from opentelemetry import context as context_api

from agentkit.apps.agent_server_app.telemetry import telemetry

_EXCLUDED_HEADERS = {"authorization", "token"}


class AgentkitTelemetryHTTPMiddleware:
    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope, receive, send):
        print(f"test: {scope}")
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        method = scope.get("method", "")
        path = scope.get("path", "")
        headers_list = scope.get("headers", [])
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in headers_list}
        span = telemetry.tracer.start_span(name="agent_server_request")
        ctx = trace.set_span_in_context(span)
        context_api.attach(ctx)
        headers = {
            k: v for k, v in headers.items() if k.lower() not in _EXCLUDED_HEADERS
        }

        # Currently unable to retrieve user_id and session_id from headers; keep logic for future use
        user_id = headers.get("user_id")
        session_id = headers.get("session_id")
        headers["user_id"] = user_id
        headers["session_id"] = session_id
        telemetry.trace_agent_server(
            func_name=f"{method} {path}",
            span=span,
            headers=headers,
            text="",  # do not consume body in middleware
        )

        async def send_wrapper(message):
            try:
                if message.get("type") == "http.response.body":
                    more_body = message.get("more_body", False)
                    if not more_body:
                        telemetry.trace_agent_server_finish(
                            path=path, func_result="", exception=None
                        )
                elif message.get("type") == "http.response.start":
                    # could record status code if needed
                    pass
            finally:
                await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            telemetry.trace_agent_server_finish(path=path, func_result="", exception=e)
            raise

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

from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from agentkit.apps.agent_server_app.telemetry import telemetry
from agentkit.apps.auth.inbound import redact_inbound_auth_headers


class AgentkitTelemetryHTTPMiddleware:
    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        method = scope.get("method", "")
        path = scope.get("path", "")
        headers_list = scope.get("headers", [])
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in headers_list}
        # 仅提取标准 Trace 上下文，不把上游 baggage 当作可信租户或任务属性。
        parent = TraceContextTextMapPropagator().extract(
            {key.lower(): value for key, value in headers.items()}
        )
        span = telemetry.tracer.start_span(
            name="agent_server_request", context=parent, kind=trace.SpanKind.SERVER
        )
        ctx = trace.set_span_in_context(span)
        token = context_api.attach(ctx)
        headers = redact_inbound_auth_headers(headers)

        # Currently unable to retrieve user_id and session_id from headers; keep logic for future use
        user_id = headers.get("user_id")
        session_id = headers.get("session_id")
        if user_id:
            headers["user_id"] = user_id
        if session_id:
            headers["session_id"] = session_id
        telemetry.trace_agent_server(
            func_name=f"{method} {path}",
            span=span,
            headers=headers,
            text="",  # do not consume body in middleware
        )

        first_body = True

        async def send_wrapper(message):
            nonlocal first_body
            # HTTP Span 包含实际发送；后端执行结束由执行事件单独标记。
            await send(message)
            if message.get("type") == "http.response.start":
                span.set_attribute("http.response.status_code", message["status"])
            elif message.get("type") == "http.response.body":
                if first_body and message.get("body"):
                    first_body = False
                    span.add_event("http.response.first_body")
                if not message.get("more_body", False):
                    telemetry.trace_agent_server_finish(
                        path=path, func_result="", exception=None
                    )

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            telemetry.trace_agent_server_finish(path=path, func_result="", exception=e)
            raise
        finally:
            # 断开或取消可能没有最终 body；仍需结束请求 Span，避免留下悬挂记录。
            if span.is_recording():
                span.add_event("http.response.incomplete")
                span.end()
            context_api.detach(token)

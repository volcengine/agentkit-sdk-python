"""LangGraph 协议适配层的计时，复用 Runtime 的 OTel 上报通道。"""

from contextlib import aclosing
from functools import wraps

from opentelemetry import trace

from agentkit.apps.agent_server_app.diagnostics import mark_execution_error, phase
from agentkit.apps.agent_server_app.middleware import AgentkitTelemetryHTTPMiddleware


class LangGraphTelemetryMiddleware(AgentkitTelemetryHTTPMiddleware):
    async def __call__(self, scope, receive, send):
        # 只覆盖 AgentKit 适配入口；原生 LangGraph 路由沿用自己的观测，避免重复采集。
        if scope.get("method") == "POST" and scope.get("path") in {
            "/run",
            "/run_sse",
            "/invoke",
        }:
            return await super().__call__(scope, receive, send)
        return await self.app(scope, receive, send)


def trace_execution(func):
    @wraps(func)
    async def wrapped(self, req):
        request_span = trace.get_current_span()
        attributes = {
            "gen_ai.session.id": req.session_id,
            "agentkit.framework.type": "langgraph",
        }
        if req.agentkit_diagnostic_run_id:
            attributes["agentkit.run.id"] = req.agentkit_diagnostic_run_id
        request_span.set_attributes(attributes)
        with phase("runtime.agent.execute") as span:
            span.set_attributes(attributes)
            first = True
            try:
                # 消费方取消时关闭底层流，不留下继续执行的生成器或悬挂 Span。
                async with aclosing(func(self, req)) as events:
                    async for event in events:
                        if first:
                            first = False
                            request_span.add_event("agent.execution.first_event")
                        yield event
            except BaseException as error:
                mark_execution_error(error, request_span)
                raise
            else:
                # 这里只表示本次适配流结束，不代表业务 Task 或人工等待已经完成。
                request_span.add_event("agent.execution.finished")

    return wrapped

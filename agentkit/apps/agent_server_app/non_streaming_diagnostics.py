"""为 ADK 原生非流式入口补关联，执行和断连处理仍由 ADK 负责。"""

import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException, Request
from fastapi.routing import APIRoute
from opentelemetry import trace
from starlette.responses import Response

from agentkit.apps.agent_server_app.diagnostics import (
    mark_execution_error,
    mark_execution_event,
)
from agentkit.apps.agent_server_app.inbound_auth_adapter import save_inbound_auth

logger = logging.getLogger(__name__)


def make_non_streaming_prepare(server_app):
    async def prepare(req, request):
        identity_context = server_app._request_identity_context()
        if identity_context is not None:
            # 与 SSE 路径一致：用户主体来自验证后的身份，不能由正文切换会话归属。
            req.user_id = identity_context.user_sub
        if getattr(server_app, "_enable_auth_enabled", False):
            app_name = req.app_name or getattr(
                server_app.server, "default_app_name", None
            )
            if not app_name:
                # 原生 ADK 会按自己的契约返回 400；不让凭据保存先改变这个错误边界。
                return
            await save_inbound_auth(
                request=request,
                app_name=app_name,
                user_id=req.user_id,
                credential_service=server_app.server.credential_service,
            )

    return prepare


def install_non_streaming_diagnostics(
    app,
    request_model,
    prepare_request: Callable[[Any, Request], Awaitable[None]],
) -> bool:
    for index, route in enumerate(app.router.routes):
        if (
            not isinstance(route, APIRoute)
            or route.path != "/run"
            or "POST" not in route.methods
        ):
            continue
        native = route.endpoint
        parameters = inspect.signature(native).parameters
        # ADK 的旧版只接收 req，新版还接收 Request 来监测断连；未知签名不能猜调用方式。
        if set(parameters) not in ({"req"}, {"req", "request"}):
            logger.warning(
                "Native ADK /run diagnostics unavailable: unsupported signature"
            )
            return False

        async def run_agent(req, request: Request):
            span = trace.get_current_span()
            if req.agentkit_diagnostic_run_id is not None:
                span.set_attribute("agentkit.run.id", req.agentkit_diagnostic_run_id)
            try:
                await prepare_request(req, request)
                kwargs = {"req": req}
                if "request" in parameters:
                    kwargs["request"] = request
                result = await native(**kwargs)
                # 新版 ADK 在断连时返回 499 Response；不能把这种返回标为执行成功。
                if isinstance(result, Response) and result.status_code >= 400:
                    mark_execution_error(HTTPException(result.status_code), span)
                else:
                    span.set_attribute("gen_ai.session.id", req.session_id)
                    mark_execution_event("agent.execution.finished", span)
                return result
            except BaseException as error:
                mark_execution_error(error, span)
                raise

        # 显式替换请求类型，使 FastAPI 在调用执行器前验证诊断字段；不读取或重放原始正文。
        run_agent.__annotations__["req"] = request_model
        preserved = (
            "response_model",
            "status_code",
            "tags",
            "dependencies",
            "summary",
            "description",
            "response_description",
            "responses",
            "deprecated",
            "name",
            "methods",
            "operation_id",
            "response_model_include",
            "response_model_exclude",
            "response_model_by_alias",
            "response_model_exclude_unset",
            "response_model_exclude_defaults",
            "response_model_exclude_none",
            "include_in_schema",
            "response_class",
            "callbacks",
            "openapi_extra",
            "generate_unique_id_function",
        )
        # 保留原路由的鉴权依赖、响应过滤、文档信息与位置，仅扩展入站模型和观测边界。
        app.router.routes[index] = APIRoute(
            route.path, run_agent, **{key: getattr(route, key) for key in preserved}
        )
        app.openapi_schema = None
        return True
    return False

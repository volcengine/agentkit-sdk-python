"""Runtime 阶段计时，复用现有 OTel tracer 与上报通道。"""

from contextlib import contextmanager
import os
import re
from typing import Any

from opentelemetry import trace

from agentkit.apps.agent_server_app.telemetry import telemetry

DIAGNOSTIC_RUN_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


def split_invoke_diagnostics(payload: Any) -> tuple[Any, str | None]:
    if not isinstance(payload, dict):
        return payload, None
    # 诊断元数据不属于用户输入；复制后移除，保留旧版无 prompt 的 JSON 输入语义。
    content = dict(payload)
    run_id = content.pop("agentkitDiagnosticRunId", None)
    if run_id is not None and (
        not isinstance(run_id, str)
        or re.fullmatch(DIAGNOSTIC_RUN_ID_PATTERN, run_id) is None
    ):
        raise ValueError("invalid diagnostic Run ID")
    return content, run_id


@contextmanager
def phase(name: str):
    # 不记录请求正文或凭据；阶段 Span 只描述真实调用边界。
    with telemetry.tracer.start_as_current_span(
        name, record_exception=False, set_status_on_exception=False
    ) as span:
        try:
            yield span
        except BaseException as error:
            span.set_attribute("error.type", type(error).__name__)
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            raise


def mark_execution_event(name: str, span: trace.Span) -> None:
    span.add_event(name)


def mark_execution_error(error: BaseException, span: trace.Span) -> None:
    # 请求 Span 由中间件在发送完成后结束；执行失败只记录类型，避免泄露异常正文。
    span.set_attribute("error.type", type(error).__name__)
    code = getattr(error, "status_code", None)
    if code:
        span.set_attribute("agentkit.error.status_code", code)
    span.set_status(trace.Status(trace.StatusCode.ERROR))
    span.add_event("agent.execution.failed")


def runtime_attributes() -> dict[str, str]:
    # 部署平台注入 agentkit/<Runtime ID>；只保留资源标识，不读取请求头。
    # 该字段用于关联执行来源，不代替服务端的账号归属与写权限校验。
    identity = os.getenv("MODEL_AGENT_CLIENT_REQ_ID", "")
    if not identity.startswith("agentkit/"):
        return {}
    runtime_id = identity[len("agentkit/") :]
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", runtime_id):
        return {}
    return {"agentkit.runtime.id": runtime_id}

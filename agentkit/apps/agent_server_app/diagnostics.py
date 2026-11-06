"""Runtime 阶段计时，复用现有 OTel tracer 与上报通道。"""

from contextlib import contextmanager
import os
import re
from typing import Any

from opentelemetry import trace

from agentkit.apps.agent_server_app.runtime_config import runtime_config_attributes
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


def runtime_attributes() -> dict[str, str | int]:
    # 部署平台注入 agentkit/<Runtime ID>；只保留资源标识，不读取请求头。
    # 该字段用于关联执行来源，不代替服务端的账号归属与写权限校验。
    identity = os.getenv("MODEL_AGENT_CLIENT_REQ_ID", "")
    if not identity.startswith("agentkit/"):
        return {}
    runtime_id = identity[len("agentkit/") :]
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", runtime_id):
        return {}
    attributes: dict[str, str | int] = {"agentkit.runtime.id": runtime_id}
    attributes.update(runtime_config_attributes())
    # 同一 Revision 可出现在不同物理函数中；保留平台函数标识以便核对历史快照。
    # 它是资源关联字段，不是业务版本，也不接受浏览器自报的函数身份。
    function_id = os.getenv("_FAAS_FUNC_ID", "")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", function_id):
        attributes["agentkit.runtime.function.id"] = function_id
    # 记录平台在本进程中注入的 Revision，避免查询时用当前配置回填历史执行。
    # 它不是业务版本、版本类型或授权依据，也不接受请求头提供的版本。
    revision = os.getenv("_FAAS_REVISION_NUMBER", "")
    if re.fullmatch(r"(?:0|[1-9][0-9]{0,9})", revision) and int(revision) <= 2147483647:
        attributes["faas.version"] = revision
    return attributes

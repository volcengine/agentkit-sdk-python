"""Runtime 阶段计时，复用现有 OTel tracer 与上报通道。"""

from contextlib import contextmanager

from opentelemetry import trace

from agentkit.apps.agent_server_app.telemetry import telemetry


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
    span.set_status(trace.Status(trace.StatusCode.ERROR))
    span.add_event("agent.execution.failed")

"""将工具执行关联到本次 MCP 请求，避免复用会话上下文造成串链。"""

import re

from mcp.server.lowlevel.server import request_ctx
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


# W3C Trace Context 的成员语法；先过滤，避免解析器将无效原文写进警告日志。
_STATE_MEMBER = re.compile(
    r"([a-z][_0-9a-z*/\-]{0,255}|[a-z0-9][_0-9a-z*/\-]{0,240}@[a-z][_0-9a-z*/\-]{0,13})"
    r"=([\x20-\x2b\x2d-\x3c\x3e-\x7e]{0,255}[\x21-\x2b\x2d-\x3c\x3e-\x7e])[ \t]*"
)


def _valid_tracestate(value):
    if not isinstance(value, str) or len(value) > 512:
        return False
    members = [part for part in re.split(r"[ \t]*,[ \t]*", value) if part]
    matches = [_STATE_MEMBER.fullmatch(part) for part in members]
    if len(matches) > 32 or not all(matches):
        return False
    keys = [match.group(1) for match in matches]
    return len(keys) == len(set(keys))


def tool_span_options():
    try:
        meta = request_ctx.get().meta
    except LookupError:
        return {}
    if meta is None:
        return {}
    get = meta.get if isinstance(meta, dict) else lambda key: getattr(meta, key, None)
    traceparent = get("traceparent")
    if not isinstance(traceparent, str) or len(traceparent) > 512:
        return {}
    carrier = {"traceparent": traceparent}
    tracestate = get("tracestate")
    if _valid_tracestate(tracestate):
        carrier["tracestate"] = tracestate
    # 只提取 W3C 追踪字段；不把请求中的 baggage 或其它元数据复制到观测上下文。
    parent_context = TraceContextTextMapPropagator().extract(carrier, context=Context())
    parent = trace.get_current_span(parent_context).get_span_context()
    if not parent.is_valid:
        return {}
    current = trace.get_current_span().get_span_context()
    links = []
    if current.is_valid and (current.trace_id, current.span_id) != (
        parent.trace_id,
        parent.span_id,
    ):
        # 会话任务可能保留旧 HTTP 上下文；本次调用作父级，传输处理另用 Link 保留。
        links.append(trace.Link(current, {"agentkit.link.relationship": "transport"}))
    return {"context": parent_context, "links": links}

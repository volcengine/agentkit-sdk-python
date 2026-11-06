"""同一 MCP 会话的工具调用应分别关联各自的调用 Span。"""

import asyncio

import pytest
from fastmcp import Client
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agentkit.apps.mcp_app import mcp_app


@pytest.mark.parametrize("registration", ["tool", "agent_as_a_tool"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_reused_mcp_session_uses_each_call_context(
    monkeypatch, registration, asynchronous
):
    monkeypatch.setenv("OBSERVABILITY_OPENTELEMETRY_TRACE_CONTENT", "false")
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test.mcp.request")
    monkeypatch.setattr(mcp_app.telemetry, "tracer", tracer)

    def sync_handler():
        sc = trace.get_current_span().get_span_context()
        return {
            "trace_id": format(sc.trace_id, "032x"),
            "span_id": format(sc.span_id, "016x"),
        }

    async def async_handler():
        return sync_handler()

    handler = async_handler if asynchronous else sync_handler
    app = mcp_app.AgentkitMCPApp()
    getattr(app, registration)(handler)
    expected = []
    replies = []
    wire_parents = []
    from mcp import ClientSession
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    original_call = ClientSession.call_tool

    async def observe_call(self, *args, **kwargs):
        # FastMCP 可另建客户端 Span；以实际协议元数据为准，不假定它等于外层 Span。
        context = TraceContextTextMapPropagator().extract(kwargs.get("meta") or {})
        wire_parents.append(trace.get_current_span(context).get_span_context())
        return await original_call(self, *args, **kwargs)

    monkeypatch.setattr(ClientSession, "call_tool", observe_call)

    async def run():
        # 连接任务继承传输上下文；后续调用须使用各自请求的追踪标识。
        with tracer.start_as_current_span("transport") as transport:
            transport_context = transport.get_span_context()
            async with Client(app._mcp_server) as client:
                for _ in range(2):
                    with tracer.start_as_current_span(
                        "caller", context=trace.Context()
                    ) as caller:
                        sc = caller.get_span_context()
                        expected.append(sc)
                        replies.append(await client.call_tool(handler.__name__, {}))
            return transport_context

    try:
        transport = asyncio.run(run())
        tool_spans = [
            span
            for span in exporter.get_finished_spans()
            if span.name in ["tool", "agent_as_a_tool"]
        ]
        assert len(tool_spans) == 2
        assert len({context.trace_id for context in expected}) == 2
        assert len(wire_parents) == 2
        for expected_context, wire_parent, reply, span in zip(
            expected, wire_parents, replies, tool_spans
        ):
            assert reply.data["trace_id"] == format(expected_context.trace_id, "032x")
            assert wire_parent.trace_id == expected_context.trace_id
            assert span.parent.span_id == wire_parent.span_id
            assert span.context.trace_id == expected_context.trace_id
            assert len(span.links) == 1
            assert span.links[0].context.trace_id == transport.trace_id
            assert "gen_ai.input" not in span.attributes
            assert "gen_ai.output" not in span.attributes
    finally:
        provider.shutdown()


@pytest.mark.parametrize(
    "meta",
    [
        None,
        {},
        {"traceparent": None},
        {"traceparent": 7},
        {"traceparent": "invalid"},
        {"traceparent": "x" * 513},
        {"traceparent": "00-" + "0" * 32 + "-" + "1" * 16 + "-01"},
    ],
)
def test_missing_or_invalid_request_trace_keeps_original_parent(meta):
    from types import SimpleNamespace
    from mcp.server.lowlevel.server import request_ctx
    from agentkit.apps.mcp_app.request_diagnostics import tool_span_options

    token = request_ctx.set(SimpleNamespace(meta=meta))
    try:
        assert tool_span_options() == {}
    finally:
        request_ctx.reset(token)


def test_request_trace_only_extracts_whitelisted_fields(caplog):
    from types import SimpleNamespace
    from mcp.server.lowlevel.server import request_ctx
    from agentkit.apps.mcp_app.request_diagnostics import tool_span_options

    token = request_ctx.set(
        SimpleNamespace(
            meta={
                "traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-01",
                "tracestate": "synthetic-private-invalid-state",
                "baggage": "synthetic-private-baggage",
            }
        )
    )
    try:
        options = tool_span_options()
        parent = trace.get_current_span(options["context"]).get_span_context()
        assert parent.trace_id == int("1" * 32, 16)
        assert parent.span_id == int("2" * 16, 16)
        assert options["context"].get("baggage") is None
        assert "synthetic-private-invalid-state" not in caplog.text
        assert "synthetic-private-baggage" not in caplog.text
    finally:
        request_ctx.reset(token)


@pytest.mark.parametrize("tracestate", ["vendor=value", "a@tenant=opaque, other=value"])
def test_valid_request_tracestate_is_preserved(tracestate):
    from types import SimpleNamespace
    from mcp.server.lowlevel.server import request_ctx
    from agentkit.apps.mcp_app.request_diagnostics import tool_span_options

    token = request_ctx.set(
        SimpleNamespace(
            meta={
                "traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-00",
                "tracestate": tracestate,
            }
        )
    )
    try:
        parent = trace.get_current_span(
            tool_span_options()["context"]
        ).get_span_context()
        assert parent.trace_flags == 0
        assert parent.trace_state.to_header() == tracestate.replace(", ", ",")
        assert parent.is_remote
    finally:
        request_ctx.reset(token)


def test_outside_mcp_request_keeps_original_parent():
    from agentkit.apps.mcp_app.request_diagnostics import tool_span_options

    assert tool_span_options() == {}

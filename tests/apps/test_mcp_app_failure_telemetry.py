"""真实 FastMCP 注册与执行链路应保留失败原因和耗时。"""

import asyncio
from types import SimpleNamespace

import pytest
from fastmcp.exceptions import ToolError
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agentkit.apps.mcp_app import mcp_app


@pytest.mark.parametrize("registration", ["tool", "agent_as_a_tool"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_real_mcp_failure_retains_original_error_and_latency(
    monkeypatch, registration, asynchronous
):
    monkeypatch.setenv("OBSERVABILITY_OPENTELEMETRY_TRACE_CONTENT", "false")
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(
        mcp_app.telemetry, "tracer", provider.get_tracer("test.mcp.failure")
    )
    records = []
    monkeypatch.setattr(
        mcp_app.telemetry,
        "latency_histogram",
        SimpleNamespace(record=lambda *args: records.append(args)),
    )
    boom = ValueError("synthetic execution failure")

    def sync_handler():
        raise boom

    async def async_handler():
        raise boom

    handler = async_handler if asynchronous else sync_handler
    app = mcp_app.AgentkitMCPApp()
    getattr(app, registration)(handler)
    try:
        # 走真实注册和调用管线，避免仅调用遥测函数漏掉包装层的异常覆盖。
        with pytest.raises(ToolError) as caught:
            asyncio.run(app._mcp_server.call_tool(handler.__name__, {}))
        causes = []
        error = caught.value
        while error is not None:
            causes.append(error)
            error = error.__cause__
        assert any(error is boom for error in causes)
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.status.status_code == trace.StatusCode.ERROR
        assert span.attributes["gen_ai.operation.type"] == (
            "mcp_tool" if registration == "tool" else "agent_mcp_tool"
        )
        assert "gen_ai.input" not in span.attributes
        assert "gen_ai.output" not in span.attributes
        errors = [
            event for event in span.events
            if event.attributes.get("exception.type") == "ValueError"
        ]
        # 一次失败只记录一个异常事件，不能把自动和手动重复记录误当成重试。
        assert len(errors) == 1
        assert len(records) == 1
        duration, attributes = records[0]
        assert duration >= 0
        assert attributes["error_type"] == "ValueError"
    finally:
        provider.shutdown()

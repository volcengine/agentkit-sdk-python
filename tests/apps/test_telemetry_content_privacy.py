"""关闭正常输入输出正文采集时，协议执行与耗时记录仍然保留。"""

from types import SimpleNamespace

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import agentkit.apps.a2a_app.telemetry as a2a
import agentkit.apps.mcp_app.telemetry as mcp
import agentkit.apps.simple_app.telemetry as simple


def synthetic_handler():
    return None


@pytest.mark.parametrize("app_type", ["simple", "mcp", "a2a"])
@pytest.mark.parametrize(
    ("setting", "expected_content"),
    [
        ("false", False),
        ("FaLsE", False),
        ("invalid", False),
        ("true", True),
        (None, True),
    ],
)
def test_content_flag_preserves_operation_and_latency(
    monkeypatch, app_type, setting, expected_content
):
    if setting is None:
        monkeypatch.delenv("OBSERVABILITY_OPENTELEMETRY_TRACE_CONTENT", raising=False)
    else:
        monkeypatch.setenv("OBSERVABILITY_OPENTELEMETRY_TRACE_CONTENT", setting)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    module = {"simple": simple, "mcp": mcp, "a2a": a2a}[app_type]
    records = []
    monkeypatch.setattr(
        module.telemetry,
        "latency_histogram",
        SimpleNamespace(record=lambda *args: records.append(args)),
    )
    span = provider.get_tracer("test.content.privacy").start_span("execution")
    marker = "synthetic-private-body"
    try:
        with trace.use_span(span, end_on_exit=False):
            if app_type == "simple":
                module.telemetry.trace_agent(
                    synthetic_handler, span, {"prompt": marker}, {}
                )
                module.telemetry.trace_agent_finish(marker, None)
            elif app_type == "mcp":
                module.telemetry.trace_tool(
                    synthetic_handler, span, {"argument": marker}, marker, "tool", None
                )
                span.end()
            else:
                request = SimpleNamespace(
                    context_id="synthetic-context",
                    call_context=None,
                    message=SimpleNamespace(parts=[{"text": marker}]),
                )
                module.telemetry.trace_a2a_agent(
                    synthetic_handler, span, request, None, None
                )
                span.end()
        finished = exporter.get_finished_spans()
        assert len(finished) == 1
        attributes = finished[0].attributes
        assert (
            attributes["gen_ai.operation.type"]
            == {"simple": "agent", "mcp": "tool", "a2a": "a2a_agent"}[app_type]
        )
        assert len(records) == 1
        assert ("gen_ai.input" in attributes) == expected_content
        if app_type != "a2a":
            assert ("gen_ai.output" in attributes) == expected_content
        if not expected_content:
            assert marker not in str(attributes)
    finally:
        provider.shutdown()

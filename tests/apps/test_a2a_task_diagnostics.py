import pytest
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import Task, TaskStatus, TaskState
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from agentkit.apps.a2a_app.task_diagnostics import observe_task_store


@pytest.mark.asyncio
async def test_saved_protocol_state_and_parent_without_replacing_store(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test.tasks")
    monkeypatch.setattr(trace, "get_tracer", lambda *args, **kwargs: tracer)
    delegate = InMemoryTaskStore()
    store = observe_task_store(delegate)
    task = Task(id="task-1", context_id="context-1", status=TaskStatus(state=TaskState.input_required))
    try:
        with tracer.start_as_current_span("request") as parent:
            await store.save(task)
        child = exporter.get_finished_spans()[0]
        assert child.parent.span_id == parent.get_span_context().span_id
        assert child.attributes == {"agentkit.task.id": "task-1", "gen_ai.session.id": "context-1"}
        assert child.events[0].attributes["agentkit.task.state"] == "input-required"
        assert await store.get("task-1") == await delegate.get("task-1")
        await store.delete("task-1")
        assert await delegate.get("task-1") is None
        assert observe_task_store(store) is store
    finally:
        provider.shutdown()


@pytest.mark.asyncio
async def test_failed_save_keeps_error_without_saved_state_or_sensitive_message(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "get_tracer", lambda *args, **kwargs: provider.get_tracer("test.tasks"))
    failure = RuntimeError("sensitive store failure")
    class BrokenStore(InMemoryTaskStore):
        async def save(self, task, context=None):
            raise failure
    task = Task(id="task-1", context_id="context-1", status=TaskStatus(state=TaskState.completed))
    try:
        with pytest.raises(RuntimeError) as caught:
            await observe_task_store(BrokenStore()).save(task)
        assert caught.value is failure
        span = exporter.get_finished_spans()[0]
        assert span.status.status_code is trace.StatusCode.ERROR
        assert span.attributes["error.type"] == "RuntimeError"
        assert not span.events
        assert "sensitive" not in span.to_json()
    finally:
        provider.shutdown()


def test_standard_harness_a2a_emits_real_saved_task_state(monkeypatch):
    from google.adk.agents import BaseAgent
    from google.adk.events import Event
    from google.genai import types
    from starlette.testclient import TestClient
    from agentkit.apps.agent_server_app.agent_server_app import AgentkitAgentServerApp

    class Probe(BaseAgent):
        async def _run_async_impl(self, ctx):
            yield Event(author=self.name, invocation_id=ctx.invocation_id,
                        content=types.Content(role="model", parts=[types.Part(text="ok")]))

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "get_tracer", lambda *args, **kwargs: provider.get_tracer("test.tasks"))
    try:
        server = AgentkitAgentServerApp(agent=Probe(name="a2a_task_probe"))
        with TestClient(server.app) as client:
            response = client.post("/", json={"jsonrpc": "2.0", "id": "request-1",
                "method": "message/send", "params": {"message": {"kind": "message",
                "messageId": "message-1", "role": "user", "parts": [{"kind": "text", "text": "probe"}]},
                "configuration": {"blocking": True}}})
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["kind"] == "task"
        saved = [s for s in exporter.get_finished_spans() if s.name == "a2a.task.save"]
        assert saved
        assert all(s.attributes["agentkit.task.id"] == result["id"] for s in saved)
        assert any(e.attributes["agentkit.task.state"] == "completed" for s in saved for e in s.events)
    finally:
        provider.shutdown()

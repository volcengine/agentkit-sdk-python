import asyncio
from types import SimpleNamespace

import pytest
from google.genai import types

pytest.importorskip("langchain_core.messages")

from agentkit.frameworks._common import UnsupportedFrameworkAgentError
from agentkit.frameworks.langgraph import LANGGRAPH_PENDING_INTERRUPT_STATE_KEY, LangGraphAgentkitBridge


def _ctx(
    text: str = "hi",
    session_id: str | None = None,
    state: dict | None = None,
    app_name: str | None = None,
    user_id: str | None = None,
):
    session = None
    if session_id:
        session = SimpleNamespace(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            state=state if state is not None else {},
        )
    return SimpleNamespace(
        invocation_id="invocation",
        branch=None,
        user_content=types.UserContent(parts=[types.Part(text=text)]),
        session=session,
    )


def _event_text(event) -> str:
    if event.content is None:
        return ""
    return "".join(part.text or "" for part in event.content.parts)


def _collect_events(bridge: LangGraphAgentkitBridge, ctx=None):
    async def run():
        events = []
        async for event in bridge._run_async_impl(ctx or _ctx()):
            actions = getattr(event, "actions", None)
            events.append(
                {
                    "partial": event.partial,
                    "text": _event_text(event),
                    "error_code": getattr(event, "error_code", None),
                    "interrupted": getattr(event, "interrupted", None),
                    "metadata": getattr(event, "custom_metadata", None),
                    "state_delta": dict(actions.state_delta) if actions and actions.state_delta else {},
                }
            )
        return events

    return asyncio.run(run())


def _visible(events):
    return [{"partial": event["partial"], "text": event["text"]} for event in events]


def test_default_stream_uses_final_updates_without_partial_tokens():
    class FakeGraph:
        async def astream(self, payload, stream_mode=None):
            assert stream_mode == "updates"
            yield ("updates", {"classify": {"route": "handoff"}})
            yield ("updates", {"finalize": {"final": "final answer"}})

    events = _collect_events(
        LangGraphAgentkitBridge(FakeGraph(), name="lg_updates"),
    )

    assert _visible(events) == [{"partial": False, "text": "final answer"}]


def test_default_message_stream_does_not_leak_internal_llm_tokens():
    class FakeGraph:
        async def astream(self, payload, stream_mode=None):
            assert stream_mode == "updates"
            yield ("messages", (SimpleNamespace(content="internal llm token"), {}))
            yield ("updates", {"answer": {"answer": "LG_PROD_OK\nfinal graph answer"}})

    events = _collect_events(
        LangGraphAgentkitBridge(FakeGraph(), name="lg_final_update"),
    )

    assert _visible(events) == [{"partial": False, "text": "LG_PROD_OK\nfinal graph answer"}]


def test_stream_nodes_emit_matching_message_chunks_as_deltas():
    class CumulativeGraph:
        async def astream(self, payload, stream_mode=None, version=None):
            del payload
            assert stream_mode == ["messages", "updates"]
            assert version == "v2"
            yield ("messages", (SimpleNamespace(content="ignore"), {"langgraph_node": "classify"}))
            yield ("messages", (SimpleNamespace(content="a"), {"langgraph_node": "final_answer"}))
            yield ("messages", (SimpleNamespace(content="ab"), {"langgraph_node": "final_answer"}))

    events = _collect_events(
        LangGraphAgentkitBridge(
            CumulativeGraph(),
            name="lg_cumulative",
            stream_nodes=("final_answer",),
        ),
    )

    assert _visible(events) == [
        {"partial": True, "text": "a"},
        {"partial": True, "text": "b"},
        {"partial": False, "text": "ab"},
    ]


def test_stream_nodes_emit_native_langgraph_token_deltas():
    class DeltaGraph:
        async def astream(self, payload, stream_mode=None, version=None):
            del payload
            assert stream_mode == ["messages", "updates"]
            assert version == "v2"
            yield (
                "messages",
                (SimpleNamespace(content="hel"), {"langgraph_node": "chatbot"}),
            )
            yield (
                "messages",
                (SimpleNamespace(content="lo"), {"langgraph_node": "chatbot"}),
            )
            yield (
                "messages",
                (SimpleNamespace(content=""), {"langgraph_node": "chatbot"}),
            )

    events = _collect_events(
        LangGraphAgentkitBridge(
            DeltaGraph(),
            name="lg_delta",
            stream_nodes=("chatbot",),
        ),
    )

    assert _visible(events) == [
        {"partial": True, "text": "hel"},
        {"partial": True, "text": "lo"},
        {"partial": False, "text": "hello"},
    ]


def test_stream_nodes_ignore_message_chunks_without_matching_metadata():
    class MetadataGraph:
        async def astream(self, payload, stream_mode=None, version=None):
            del payload, version
            assert stream_mode == ["messages", "updates"]
            yield ("messages", (SimpleNamespace(content="no metadata"), {}))
            yield ("messages", (SimpleNamespace(content="wrong node"), {"langgraph_node": "classify"}))
            yield ("updates", {"finalize": {"final": "safe final"}})

    events = _collect_events(
        LangGraphAgentkitBridge(
            MetadataGraph(),
            name="lg_filtered",
            stream_nodes=("final_answer",),
        ),
    )

    assert _visible(events) == [{"partial": False, "text": "safe final"}]


def test_update_stream_is_used_when_graph_emits_no_messages():
    class UpdateOnlyGraph:
        async def astream(self, payload, stream_mode=None):
            assert stream_mode == "updates"
            yield ("updates", {"result": {"answer": "fallback answer"}})

    events = _collect_events(
        LangGraphAgentkitBridge(UpdateOnlyGraph(), name="lg_updates"),
    )

    assert _visible(events) == [{"partial": False, "text": "fallback answer"}]


def test_v2_stream_parts_are_supported():
    class V2Graph:
        async def astream(self, payload, stream_mode=None, version=None):
            assert stream_mode == "updates"
            assert version == "v2"
            yield {
                "type": "updates",
                "data": {"classify": {"route": "self_serve"}},
            }
            yield {
                "type": "updates",
                "data": {"finalize": {"final": "v2 answer"}},
            }

    events = _collect_events(
        LangGraphAgentkitBridge(V2Graph(), name="lg_v2"),
    )

    assert _visible(events) == [{"partial": False, "text": "v2 answer"}]


def test_raw_state_updates_do_not_leak_intermediate_fields():
    class RawUpdateGraph:
        async def astream(self, payload, stream_mode=None, version=None):
            assert stream_mode == "updates"
            assert version == "v2"
            yield {
                "classify_intent": {
                    "intent": "general",
                    "needs_compliance": False,
                    "audience_hint": "",
                }
            }
            yield {"finalize": {"final": "hello", "messages": [SimpleNamespace(content="hello")]}}

    events = _collect_events(
        LangGraphAgentkitBridge(RawUpdateGraph(), name="lg_raw_updates"),
    )

    assert _visible(events) == [{"partial": False, "text": "hello"}]


def test_raw_internal_state_update_without_output_fields_emits_nothing():
    class InternalOnlyGraph:
        async def astream(self, payload, stream_mode=None, version=None):
            del payload, stream_mode, version
            yield {
                "classify_intent": {
                    "intent": "general",
                    "needs_compliance": False,
                    "audience_hint": "",
                }
            }

    events = _collect_events(
        LangGraphAgentkitBridge(InternalOnlyGraph(), name="lg_internal_only"),
    )

    assert _visible(events) == []


def test_internal_content_field_does_not_leak_as_output():
    class InternalContentGraph:
        async def astream(self, payload, stream_mode=None, version=None):
            del payload, stream_mode, version
            yield {"retrieve": {"content": "internal document text"}}
            yield {"finalize": {"final": "public answer"}}

    events = _collect_events(
        LangGraphAgentkitBridge(InternalContentGraph(), name="lg_internal_content"),
    )

    assert _visible(events) == [{"partial": False, "text": "public answer"}]


def test_raw_state_update_with_messages_reducer_outputs_latest_message():
    class RawMessagesGraph:
        async def astream(self, payload, stream_mode=None, version=None):
            del payload, stream_mode, version
            yield {"agent": {"messages": [SimpleNamespace(content="latest answer")]}}

    events = _collect_events(
        LangGraphAgentkitBridge(RawMessagesGraph(), name="lg_raw_messages"),
    )

    assert _visible(events) == [{"partial": False, "text": "latest answer"}]


def test_update_stream_supports_final_output_field():
    class FinalFieldGraph:
        async def astream(self, payload, stream_mode=None, version=None):
            del payload, stream_mode, version
            yield ("updates", {"finalize": {"final": "final field answer"}})

    events = _collect_events(
        LangGraphAgentkitBridge(FinalFieldGraph(), name="lg_final_field"),
    )

    assert _visible(events) == [{"partial": False, "text": "final field answer"}]


def test_raw_langgraph_interrupt_update_is_exposed_as_explicit_event():
    class RawInterruptingGraph:
        async def astream(self, payload, config=None, stream_mode=None, version=None):
            del payload, config, stream_mode, version
            yield {
                "__interrupt__": (
                    SimpleNamespace(id="interrupt-raw", value={"prompt": "continue?"}),
                )
            }

    events = _collect_events(
        LangGraphAgentkitBridge(RawInterruptingGraph(), name="lg_raw_interrupt"),
    )

    assert events == [
        {
            "partial": None,
            "text": "",
            "error_code": "LANGGRAPH_INTERRUPT",
            "interrupted": True,
            "metadata": {
                "langgraph_interrupt": [
                    {"id": "interrupt-raw", "value": {"prompt": "continue?"}},
                ]
            },
            "state_delta": {},
        }
    ]


def test_custom_input_key_supports_non_message_workflow_state():
    class WorkflowGraph:
        async def astream(self, payload, stream_mode=None, version=None):
            assert payload == {"question": "hi"}
            assert stream_mode == "updates"
            assert version == "v2"
            yield {
                "type": "updates",
                "data": {"answer": f"workflow:{payload['question']}"},
            }

    events = _collect_events(
        LangGraphAgentkitBridge(
            WorkflowGraph(),
            name="lg_workflow",
            input_key="question",
        ),
    )

    assert _visible(events) == [{"partial": False, "text": "workflow:hi"}]


def test_session_id_is_passed_as_langgraph_thread_id_for_update_streaming():
    class ThreadAwareGraph:
        async def astream(self, payload, config=None, stream_mode=None, version=None):
            assert payload == {"question": "hi"}
            assert config == {"configurable": {"thread_id": "session-123"}}
            assert stream_mode == "updates"
            assert version == "v2"
            yield {"type": "updates", "data": {"answer": config["configurable"]["thread_id"]}}

    events = _collect_events(
        LangGraphAgentkitBridge(
            ThreadAwareGraph(),
            name="lg_thread",
            input_key="question",
        ),
        _ctx(session_id="session-123"),
    )

    assert _visible(events) == [{"partial": False, "text": "session-123"}]


def test_session_id_is_passed_as_langgraph_thread_id_for_invoke_fallback():
    class ThreadAwareGraph:
        async def ainvoke(self, payload, config=None):
            assert payload == {"question": "hi"}
            assert config == {"configurable": {"thread_id": "session-456"}}
            return {"answer": config["configurable"]["thread_id"]}

    events = _collect_events(
        LangGraphAgentkitBridge(
            ThreadAwareGraph(),
            name="lg_thread_invoke",
            input_key="question",
        ),
        _ctx(session_id="session-456"),
    )

    assert _visible(events) == [{"partial": False, "text": "session-456"}]


def test_langgraph_interrupt_update_is_exposed_as_explicit_event():
    class InterruptingGraph:
        async def astream(self, payload, config=None, stream_mode=None, version=None):
            del payload, config, stream_mode, version
            yield {
                "type": "updates",
                "data": {
                    "__interrupt__": (
                        SimpleNamespace(id="interrupt-1", value={"prompt": "approve?"}),
                    )
                },
            }

    events = _collect_events(
        LangGraphAgentkitBridge(InterruptingGraph(), name="lg_interrupt"),
    )

    assert events == [
        {
            "partial": None,
            "text": "",
            "error_code": "LANGGRAPH_INTERRUPT",
            "interrupted": True,
            "metadata": {
                "langgraph_interrupt": [
                    {"id": "interrupt-1", "value": {"prompt": "approve?"}},
                ]
            },
            "state_delta": {},
        }
    ]


def test_langgraph_interrupt_is_recorded_in_agentkit_session_state():
    class InterruptingGraph:
        async def astream(self, payload, config=None, stream_mode=None, version=None):
            del payload, stream_mode, version
            yield {
                "type": "updates",
                "data": {
                    "__interrupt__": (
                        SimpleNamespace(id="interrupt-1", value={"prompt": "approve?"}),
                    )
                },
            }

    events = _collect_events(
        LangGraphAgentkitBridge(InterruptingGraph(), name="lg_interrupt"),
        _ctx(session_id="session-1"),
    )

    assert events == [
        {
            "partial": None,
            "text": "",
            "error_code": "LANGGRAPH_INTERRUPT",
            "interrupted": True,
            "metadata": {
                "langgraph_interrupt": [
                    {"id": "interrupt-1", "value": {"prompt": "approve?"}},
                ]
            },
            "state_delta": {
                LANGGRAPH_PENDING_INTERRUPT_STATE_KEY: {
                    "agent": "lg_interrupt",
                    "thread_id": "session-1",
                    "interrupts": [
                        {"id": "interrupt-1", "value": {"prompt": "approve?"}},
                    ],
                }
            },
        }
    ]


def test_pending_interrupt_resumes_with_text_input_and_clears_state():
    from langgraph.types import Command

    class ResumableGraph:
        async def astream(self, payload, config=None, stream_mode=None, version=None):
            assert isinstance(payload, Command)
            assert payload.resume == "approved"
            assert config == {"configurable": {"thread_id": "session-1"}}
            assert stream_mode == "updates"
            assert version == "v2"
            yield {"type": "updates", "data": {"answer": f"resumed:{payload.resume}"}}

    state = {
        LANGGRAPH_PENDING_INTERRUPT_STATE_KEY: {
            "agent": "lg_resume",
            "thread_id": "session-1",
            "interrupts": [{"id": "interrupt-1", "value": {"prompt": "approve?"}}],
        }
    }

    events = _collect_events(
        LangGraphAgentkitBridge(ResumableGraph(), name="lg_resume"),
        _ctx("approved", session_id="session-1", state=state),
    )

    assert _visible(events) == [{"partial": False, "text": "resumed:approved"}]
    assert events[-1]["state_delta"] == {LANGGRAPH_PENDING_INTERRUPT_STATE_KEY: None}


def test_pending_interrupt_resumes_with_json_input():
    from langgraph.types import Command

    class ResumableGraph:
        async def astream(self, payload, config=None, stream_mode=None, version=None):
            del config, stream_mode, version
            assert isinstance(payload, Command)
            assert payload.resume == {"decision": "yes"}
            yield {"type": "updates", "data": {"answer": payload.resume["decision"]}}

    state = {
        LANGGRAPH_PENDING_INTERRUPT_STATE_KEY: {
            "agent": "lg_json_resume",
            "thread_id": "session-1",
            "interrupts": [{"id": "interrupt-1", "value": {"prompt": "approve?"}}],
        }
    }

    events = _collect_events(
        LangGraphAgentkitBridge(ResumableGraph(), name="lg_json_resume"),
        _ctx('{"decision":"yes"}', session_id="session-1", state=state),
    )

    assert _visible(events) == [{"partial": False, "text": "yes"}]
    assert events[-1]["state_delta"] == {LANGGRAPH_PENDING_INTERRUPT_STATE_KEY: None}


def test_real_interrupt_resume_from_compiled_graph_is_supported():
    from typing import TypedDict

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt

    class State(TypedDict, total=False):
        question: str
        answer: str

    def ask(state: State):
        resume = interrupt({"prompt": f"approve {state['question']}?"})
        return {"answer": f"approved:{resume['decision']}:{state['question']}"}

    builder = StateGraph(State)
    builder.add_node("ask", ask)
    builder.add_edge(START, "ask")
    builder.add_edge("ask", END)
    graph = builder.compile(checkpointer=InMemorySaver())

    class SyncOnlyGraph:
        def stream(self, payload, **kwargs):
            yield from graph.stream(payload, **kwargs)

    bridge = LangGraphAgentkitBridge(SyncOnlyGraph(), name="lg_real_hitl", input_key="question")
    session_state: dict = {}

    first = _collect_events(bridge, _ctx("deploy", session_id="thread-1", state=session_state))
    assert first[0]["error_code"] == "LANGGRAPH_INTERRUPT"
    assert first[0]["state_delta"][LANGGRAPH_PENDING_INTERRUPT_STATE_KEY]["thread_id"] == "thread-1"
    session_state.update(first[0]["state_delta"])

    second = _collect_events(
        bridge,
        _ctx('{"decision":"yes"}', session_id="thread-1", state=session_state),
    )

    assert _visible(second) == [{"partial": False, "text": "approved:yes:deploy"}]
    assert second[-1]["state_delta"] == {LANGGRAPH_PENDING_INTERRUPT_STATE_KEY: None}


def test_real_checkpointer_history_is_scoped_by_app_user_and_session():
    from typing import Annotated, TypedDict

    from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.graph.message import add_messages

    class State(TypedDict):
        messages: Annotated[list[AnyMessage], add_messages]
        answer: str

    def write_answer(state: State):
        human_messages = [
            message.content
            for message in state["messages"]
            if isinstance(message, HumanMessage)
        ]
        answer = "|".join(human_messages)
        return {"messages": [AIMessage(content=answer)], "answer": answer}

    builder = StateGraph(State)
    builder.add_node("write_answer", write_answer)
    builder.add_edge(START, "write_answer")
    builder.add_edge("write_answer", END)
    graph = builder.compile(checkpointer=InMemorySaver())

    class SyncOnlyGraph:
        def stream(self, payload, **kwargs):
            yield from graph.stream(payload, **kwargs)

    bridge = LangGraphAgentkitBridge(SyncOnlyGraph(), name="lg_scoped_history")

    user_one = _collect_events(
        bridge,
        _ctx(
            "USER_ONE_MARKER",
            session_id="shared-session",
            app_name="app",
            user_id="user-one",
        ),
    )
    user_two = _collect_events(
        bridge,
        _ctx(
            "USER_TWO_MARKER",
            session_id="shared-session",
            app_name="app",
            user_id="user-two",
        ),
    )
    user_one_again = _collect_events(
        bridge,
        _ctx(
            "USER_ONE_SECOND",
            session_id="shared-session",
            app_name="app",
            user_id="user-one",
        ),
    )

    assert _visible(user_one)[-1] == {"partial": False, "text": "USER_ONE_MARKER"}
    assert _visible(user_two)[-1] == {"partial": False, "text": "USER_TWO_MARKER"}
    assert _visible(user_one_again)[-1] == {
        "partial": False,
        "text": "USER_ONE_MARKER|USER_ONE_SECOND",
    }


def test_real_command_updates_from_compiled_graph_are_supported():
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command

    class State(TypedDict):
        question: str
        answer: str

    def route(state: State):
        return Command(goto="write_answer", update={"answer": f"command:{state['question']}"})

    def write_answer(state: State):
        return {"answer": f"{state['answer']}:done"}

    builder = StateGraph(State)
    builder.add_node("route", route)
    builder.add_node("write_answer", write_answer)
    builder.add_edge(START, "route")
    builder.add_edge("write_answer", END)
    graph = builder.compile()

    class SyncOnlyGraph:
        def stream(self, payload, **kwargs):
            yield from graph.stream(payload, **kwargs)

    events = _collect_events(
        LangGraphAgentkitBridge(
            SyncOnlyGraph(),
            name="lg_command",
            input_key="question",
        ),
    )

    assert _visible(events) == [{"partial": False, "text": "command:hi:done"}]


def test_ainvoke_is_used_when_streaming_is_not_available():
    class AsyncGraph:
        async def ainvoke(self, payload):
            assert "messages" in payload
            return {"messages": [SimpleNamespace(content="async graph answer")]}

    events = _collect_events(
        LangGraphAgentkitBridge(AsyncGraph(), name="lg_async"),
    )

    assert _visible(events) == [{"partial": False, "text": "async graph answer"}]


def test_sync_invoke_is_used_when_streaming_is_not_available():
    class SyncGraph:
        def invoke(self, payload):
            assert "messages" in payload
            return {"answer": "sync graph answer"}

    events = _collect_events(
        LangGraphAgentkitBridge(SyncGraph(), name="lg_sync"),
    )

    assert _visible(events) == [{"partial": False, "text": "sync graph answer"}]


def test_sync_stream_is_used_when_async_streaming_is_not_available():
    class SyncStreamGraph:
        def stream(self, payload, stream_mode=None, version=None):
            assert "messages" in payload
            assert stream_mode == "updates"
            assert version == "v2"
            yield {"type": "updates", "data": {"answer": "sync graph"}}

    events = _collect_events(
        LangGraphAgentkitBridge(SyncStreamGraph(), name="lg_sync_stream"),
    )

    assert _visible(events) == [{"partial": False, "text": "sync graph"}]


def test_stream_mode_fallback_only_handles_call_signature_errors():
    class LegacyGraph:
        async def astream(self, payload):
            yield SimpleNamespace(content="legacy stream")

    events = _collect_events(
        LangGraphAgentkitBridge(LegacyGraph(), name="lg_legacy"),
    )

    assert _visible(events) == [{"partial": False, "text": "legacy stream"}]


def test_stream_runtime_type_errors_are_not_retried_as_legacy_signature():
    class BrokenGraph:
        async def astream(self, payload, stream_mode=None):
            del payload, stream_mode
            raise TypeError("node execution failed")
            yield None

    bridge = LangGraphAgentkitBridge(BrokenGraph(), name="lg_broken")

    with pytest.raises(TypeError, match="node execution failed"):
        _collect_events(bridge)


def test_unsupported_entry_raises_actionable_error():
    bridge = LangGraphAgentkitBridge(object(), name="lg_bad")

    with pytest.raises(UnsupportedFrameworkAgentError, match="compiled graph-like"):
        _collect_events(bridge)

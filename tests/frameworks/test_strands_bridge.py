import asyncio
import json
from types import SimpleNamespace

import pydantic.root_model  # noqa: F401
import pytest
from google.genai import types

from agentkit.frameworks.strands import (
    STRANDS_PENDING_INTERRUPT_STATE_KEY,
    StrandsAgentkitBridge,
    _invoke_factory,
    _restore_snapshot,
    _result_to_text,
    _stream_text_from_event,
)


def _ctx(
    text: str = "hi",
    session_id: str | None = None,
    state: dict | None = None,
    app_name: str | None = "app",
    user_id: str | None = "user",
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
        invocation_id=f"invocation-{session_id or 'none'}",
        branch=None,
        user_content=types.UserContent(parts=[types.Part(text=text)]),
        session=session,
    )


def _event_text(event) -> str:
    if event.content is None:
        return ""
    return "".join(part.text or "" for part in event.content.parts)


def _collect_events(bridge: StrandsAgentkitBridge, ctx=None):
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
                    "state_delta": dict(actions.state_delta)
                    if actions and actions.state_delta
                    else {},
                }
            )
        return events

    return asyncio.run(run())


def _visible(events):
    return [{"partial": event["partial"], "text": event["text"]} for event in events]


def _agent_result(text: str, *, stop_reason: str = "end_turn", interrupts=None):
    return SimpleNamespace(
        stop_reason=stop_reason,
        message={"role": "assistant", "content": [{"text": text}]},
        structured_output=None,
        interrupts=interrupts,
    )


def test_stream_async_data_events_are_forwarded_as_deltas():
    class StreamingAgent:
        async def stream_async(
            self, prompt, invocation_state=None, idempotency_token=None
        ):
            assert prompt == "hi"
            assert invocation_state["agentkit"]["session_id"] is None
            assert idempotency_token == "invocation-none"
            yield {"data": "he"}
            yield {"data": "llo"}
            yield {"current_tool_use": {"name": "internal"}}
            yield {"result": _agent_result("hello")}

    events = _collect_events(StrandsAgentkitBridge(StreamingAgent(), name="strands"))

    assert _visible(events) == [
        {"partial": True, "text": "he"},
        {"partial": True, "text": "llo"},
        {"partial": False, "text": "hello"},
    ]


def test_stream_event_variants_are_filtered_to_user_visible_text():
    class MixedStreamAgent:
        async def stream_async(self, prompt, invocation_state=None):
            del prompt, invocation_state
            yield object()
            yield {"event": {"data": "nested"}}
            yield {"event": {"metadata": "ignored"}}
            yield {"result": _agent_result("nested")}

    events = _collect_events(StrandsAgentkitBridge(MixedStreamAgent(), name="strands"))

    assert _visible(events) == [
        {"partial": True, "text": "nested"},
        {"partial": False, "text": "nested"},
    ]


def test_multiagent_node_stream_events_are_forwarded_but_lifecycle_events_are_ignored():
    writer_result = _agent_result("final multiagent answer")
    multiagent_result = SimpleNamespace(
        results={"writer": SimpleNamespace(result=writer_result)},
        execution_order=[SimpleNamespace(node_id="writer")],
    )

    class GraphLikeAgent:
        async def stream_async(self, prompt, invocation_state=None):
            del prompt, invocation_state
            yield {"type": "multiagent_node_start", "node_id": "research"}
            yield {
                "type": "multiagent_node_stream",
                "node_id": "writer",
                "event": {"data": "draft"},
            }
            yield {"type": "multiagent_handoff", "from_node_ids": ["research"]}
            yield {"type": "multiagent_result", "result": multiagent_result}

    events = _collect_events(
        StrandsAgentkitBridge(GraphLikeAgent(), name="strands_graph")
    )

    assert _visible(events) == [
        {"partial": True, "text": "draft"},
        {"partial": False, "text": "final multiagent answer"},
    ]


def test_multiagent_result_uses_node_history_and_falls_back_to_last_result():
    history_result = SimpleNamespace(
        results={
            "draft": SimpleNamespace(result=_agent_result("draft")),
            "review": SimpleNamespace(result=_agent_result("reviewed")),
        },
        execution_order=[],
        node_history=[
            SimpleNamespace(node_id="draft"),
            SimpleNamespace(node_id="review"),
        ],
    )
    fallback_result = SimpleNamespace(
        results={
            "first": SimpleNamespace(result=_agent_result("first")),
            "last": SimpleNamespace(result=_agent_result("last")),
        },
        execution_order=[],
        node_history=[],
    )
    empty_result = SimpleNamespace(results={})

    class MultiResultAgent:
        def __init__(self):
            self.turn = 0

        async def stream_async(self, prompt, invocation_state=None):
            del prompt, invocation_state
            self.turn += 1
            if self.turn == 1:
                yield {"result": history_result}
            elif self.turn == 2:
                yield {"result": fallback_result}
            else:
                yield {"result": empty_result}

    agent = MultiResultAgent()
    bridge = StrandsAgentkitBridge(agent, name="strands_multi")

    first = _collect_events(bridge, _ctx("one"))
    second = _collect_events(bridge, _ctx("two"))
    third = _collect_events(bridge, _ctx("three"))

    assert _visible(first) == [{"partial": False, "text": "reviewed"}]
    assert _visible(second) == [{"partial": False, "text": "last"}]
    assert _visible(third)[0]["text"].startswith("namespace(results={})")


def test_factory_entry_is_scoped_by_agentkit_session():
    created = []

    class StatefulAgent:
        def __init__(self, context_id):
            self.context_id = context_id
            self.turns = 0

        async def stream_async(self, prompt, invocation_state=None):
            del invocation_state
            self.turns += 1
            yield {"result": _agent_result(f"{self.context_id}:{prompt}:{self.turns}")}

    def build_agent(context_id):
        created.append(context_id)
        return StatefulAgent(context_id)

    bridge = StrandsAgentkitBridge(
        build_agent, name="strands_factory", agent_factory=True
    )

    first_a = _collect_events(bridge, _ctx("one", session_id="a"))
    first_b = _collect_events(bridge, _ctx("one", session_id="b"))
    second_a = _collect_events(bridge, _ctx("two", session_id="a"))

    assert _visible(first_a)[-1]["text"].endswith(":one:1")
    assert _visible(first_b)[-1]["text"].endswith(":one:1")
    assert _visible(second_a)[-1]["text"].endswith(":two:2")
    assert len(created) == 2


def test_factory_rejects_uninspectable_and_async_factories():
    class BadSignatureFactory:
        @property
        def __signature__(self):
            raise ValueError("no signature")

        def __call__(self):
            return object()

    async def async_factory():
        return object()

    with pytest.raises(TypeError, match="no inspectable signature"):
        _invoke_factory(BadSignatureFactory(), None)

    with pytest.raises(TypeError, match="returned an awaitable"):
        _invoke_factory(async_factory, None)


def test_keyword_only_context_id_factory_is_supported():
    class ContextAgent:
        async def stream_async(self, prompt, invocation_state=None):
            del invocation_state
            yield {"result": _agent_result(f"{self.context_id}:{prompt}")}

    def build_agent(*, context_id):
        agent = ContextAgent()
        agent.context_id = context_id
        return agent

    bridge = StrandsAgentkitBridge(
        build_agent, name="keyword_factory", agent_factory=True
    )

    events = _collect_events(bridge, _ctx("hello", session_id="s"))

    assert _visible(events)[-1]["text"].endswith(":hello")


def test_optional_context_id_factory_receives_session_context():
    contexts = []

    class ContextAgent:
        async def stream_async(self, prompt, invocation_state=None):
            del invocation_state
            yield {"result": _agent_result(prompt)}

    def build_agent(context_id=None):
        contexts.append(context_id)
        return ContextAgent()

    bridge = StrandsAgentkitBridge(
        build_agent, name="optional_factory", agent_factory=True
    )

    _collect_events(bridge, _ctx("hello", session_id="s"))

    assert contexts == ["app\0user\0s"]


def test_factory_entry_without_session_is_cleaned_up_after_invocation():
    cleaned = []

    class TemporaryAgent:
        async def stream_async(self, prompt, invocation_state=None):
            del invocation_state
            yield {"result": _agent_result(prompt)}

        def cleanup(self):
            cleaned.append("done")

    bridge = StrandsAgentkitBridge(
        lambda: TemporaryAgent(),
        name="temporary_factory",
        agent_factory=True,
    )

    events = _collect_events(bridge, _ctx("hello"))

    assert _visible(events) == [{"partial": False, "text": "hello"}]
    assert cleaned == ["done"]


def test_callable_with_uninspectable_signature_receives_agentkit_kwargs():
    class BadSignatureCallable:
        @property
        def __signature__(self):
            raise ValueError("no signature")

        def __call__(self, prompt, **kwargs):
            return {
                "text": (
                    f"{prompt}:"
                    f"{kwargs['invocation_state']['agentkit']['invocation_id']}:"
                    f"{kwargs['idempotency_token']}"
                )
            }

    events = _collect_events(StrandsAgentkitBridge(BadSignatureCallable()))

    assert _visible(events) == [
        {"partial": False, "text": "hi:invocation-none:invocation-none"}
    ]


def test_factory_cache_evicts_old_session_agents_with_cleanup():
    cleaned = []

    class CachedAgent:
        def __init__(self, context_id):
            self.context_id = context_id

        async def stream_async(self, prompt, invocation_state=None):
            del prompt, invocation_state
            yield {"result": _agent_result(self.context_id)}

        def cleanup(self):
            cleaned.append(self.context_id)

    bridge = StrandsAgentkitBridge(
        lambda context_id: CachedAgent(context_id),
        name="evicting_factory",
        agent_factory=True,
        max_session_agents=1,
    )

    _collect_events(bridge, _ctx("one", session_id="one"))
    _collect_events(bridge, _ctx("two", session_id="two"))

    assert cleaned == ["app\0user\0one"]


def test_singleton_entry_uses_snapshots_to_isolate_sessions():
    class SnapshotAgent:
        def __init__(self):
            self.turns = 0

        def take_snapshot(self, preset=None):
            assert preset == "session"
            return {"turns": self.turns}

        def load_snapshot(self, snapshot):
            self.turns = snapshot["turns"]

        async def stream_async(self, prompt, invocation_state=None):
            del invocation_state
            self.turns += 1
            yield {"result": _agent_result(f"{prompt}:{self.turns}")}

    agent = SnapshotAgent()
    bridge = StrandsAgentkitBridge(agent, name="strands_singleton")

    first_a = _collect_events(bridge, _ctx("one", session_id="a"))
    first_b = _collect_events(bridge, _ctx("one", session_id="b"))
    second_a = _collect_events(bridge, _ctx("two", session_id="a"))

    assert _visible(first_a) == [{"partial": False, "text": "one:1"}]
    assert _visible(first_b) == [{"partial": False, "text": "one:1"}]
    assert _visible(second_a) == [{"partial": False, "text": "two:2"}]
    assert agent.turns == 0


def test_singleton_orchestrator_snapshot_protocol_is_supported():
    class Orchestrator:
        def __init__(self):
            self.state = {"turns": 0}

        def serialize_state(self):
            return self.state

        def deserialize_state(self, state):
            self.state = state

        async def stream_async(self, prompt, invocation_state=None):
            del invocation_state
            self.state["turns"] += 1
            yield {"result": _agent_result(f"{prompt}:{self.state['turns']}")}

    orchestrator = Orchestrator()
    bridge = StrandsAgentkitBridge(orchestrator, name="strands_orchestrator")

    first = _collect_events(bridge, _ctx("one", session_id="s"))
    second = _collect_events(bridge, _ctx("two", session_id="s"))

    assert _visible(first) == [{"partial": False, "text": "one:1"}]
    assert _visible(second) == [{"partial": False, "text": "two:2"}]
    assert orchestrator.state == {"turns": 0}


def test_snapshot_cache_evicts_old_session_snapshots():
    class SnapshotAgent:
        def __init__(self):
            self.turns = 0

        def take_snapshot(self, preset=None):
            del preset
            return {"turns": self.turns}

        def load_snapshot(self, snapshot):
            self.turns = snapshot["turns"]

        async def stream_async(self, prompt, invocation_state=None):
            del invocation_state
            self.turns += 1
            yield {"result": _agent_result(f"{prompt}:{self.turns}")}

    bridge = StrandsAgentkitBridge(
        SnapshotAgent(),
        name="small_snapshot_cache",
        max_session_agents=1,
    )

    _collect_events(bridge, _ctx("one", session_id="one"))
    _collect_events(bridge, _ctx("two", session_id="two"))
    repeated_one = _collect_events(bridge, _ctx("again", session_id="one"))

    assert _visible(repeated_one) == [{"partial": False, "text": "again:1"}]


def test_interrupt_result_is_recorded_and_next_input_resumes_with_response_blocks():
    class Interrupt:
        id = "interrupt-1"
        name = "approval"
        reason = {"tool": "delete"}

        def to_dict(self):
            return {"id": self.id, "name": self.name, "reason": self.reason}

    class InterruptAgent:
        def __init__(self):
            self.prompts = []

        async def stream_async(self, prompt, invocation_state=None):
            del invocation_state
            self.prompts.append(prompt)
            if len(self.prompts) == 1:
                yield {
                    "result": _agent_result(
                        "",
                        stop_reason="interrupt",
                        interrupts=[Interrupt()],
                    )
                }
            else:
                yield {"result": _agent_result("resumed")}

    agent = InterruptAgent()
    bridge = StrandsAgentkitBridge(
        lambda: agent, name="strands_hitl", agent_factory=True
    )

    state = {}
    interrupted = _collect_events(bridge, _ctx("delete", session_id="s", state=state))
    state.update(interrupted[0]["state_delta"])
    resumed = _collect_events(bridge, _ctx("yes", session_id="s", state=state))

    assert interrupted[0]["error_code"] == "STRANDS_INTERRUPT"
    assert interrupted[0]["metadata"] == {
        "strands_interrupt": [
            {"id": "interrupt-1", "name": "approval", "reason": {"tool": "delete"}}
        ]
    }
    assert (
        state[STRANDS_PENDING_INTERRUPT_STATE_KEY]["interrupts"][0]["id"]
        == "interrupt-1"
    )
    assert agent.prompts[1] == [
        {
            "interruptResponse": {
                "interruptId": "interrupt-1",
                "response": "yes",
            }
        }
    ]
    assert resumed[-1]["state_delta"] == {STRANDS_PENDING_INTERRUPT_STATE_KEY: None}
    assert _visible(resumed) == [{"partial": False, "text": "resumed"}]


def test_interrupt_payload_falls_back_when_to_dict_is_not_a_dict():
    class Interrupt:
        id = "interrupt-2"
        name = "approval"
        reason = "confirm"

        def to_dict(self):
            return "not-a-dict"

    class InterruptAgent:
        async def stream_async(self, prompt, invocation_state=None):
            del prompt, invocation_state
            yield {
                "result": _agent_result(
                    "",
                    stop_reason="interrupt",
                    interrupts=[Interrupt()],
                )
            }

    events = _collect_events(StrandsAgentkitBridge(InterruptAgent(), name="hitl"))

    assert events[0]["metadata"] == {
        "strands_interrupt": [
            {"id": "interrupt-2", "name": "approval", "reason": "confirm"}
        ]
    }
    assert events[0]["state_delta"] == {}


def test_empty_interrupt_result_uses_empty_payload():
    class InterruptAgent:
        async def stream_async(self, prompt, invocation_state=None):
            del prompt, invocation_state
            yield {"result": _agent_result("", stop_reason="interrupt", interrupts=[])}

    events = _collect_events(
        StrandsAgentkitBridge(InterruptAgent(), name="hitl"),
        _ctx("approve", session_id="s"),
    )

    assert events[0]["metadata"] == {"strands_interrupt": []}
    assert events[0]["state_delta"] == {
        STRANDS_PENDING_INTERRUPT_STATE_KEY: {"agent": "hitl", "interrupts": []}
    }


def test_explicit_interrupt_response_json_is_passed_through():
    class InterruptAgent:
        def __init__(self):
            self.prompt = None

        async def stream_async(self, prompt, invocation_state=None):
            del invocation_state
            self.prompt = prompt
            yield {"result": _agent_result("resumed")}

    state = {
        STRANDS_PENDING_INTERRUPT_STATE_KEY: {
            "agent": "strands_hitl",
            "interrupts": [{"id": "interrupt-1"}],
        }
    }
    agent = InterruptAgent()
    bridge = StrandsAgentkitBridge(
        lambda: agent, name="strands_hitl", agent_factory=True
    )
    payload = '{"interruptResponse":{"interruptId":"interrupt-1","response":"ok"}}'

    events = _collect_events(bridge, _ctx(payload, session_id="s", state=state))

    assert agent.prompt == [
        {"interruptResponse": {"interruptId": "interrupt-1", "response": "ok"}}
    ]
    assert events[-1]["state_delta"] == {STRANDS_PENDING_INTERRUPT_STATE_KEY: None}


def test_interrupt_resume_accepts_response_lists_and_ignores_unusable_pending_state():
    class CaptureAgent:
        def __init__(self):
            self.prompts = []

        async def stream_async(self, prompt, invocation_state=None):
            del invocation_state
            self.prompts.append(prompt)
            yield {"result": _agent_result("ok")}

    agent = CaptureAgent()
    bridge = StrandsAgentkitBridge(
        lambda: agent, name="resume_agent", agent_factory=True
    )

    pending = {
        STRANDS_PENDING_INTERRUPT_STATE_KEY: {
            "agent": "resume_agent",
            "interrupts": [{"id": "a"}, {"name": "missing"}, "bad"],
        }
    }
    _collect_events(
        bridge,
        _ctx(
            '[{"interruptResponse":{"interruptId":"a","response":"ok"}}]',
            session_id="s",
            state=pending,
        ),
    )
    _collect_events(
        bridge,
        _ctx(
            '{"interruptResponses":[{"interruptResponse":{"interruptId":"b","response":"ok"}}]}',
            session_id="s",
            state=pending,
        ),
    )
    ignored_pending = {
        STRANDS_PENDING_INTERRUPT_STATE_KEY: {
            "agent": "other",
            "interrupts": [{"id": "c"}],
        }
    }
    _collect_events(bridge, _ctx("{not-json", session_id="s", state=ignored_pending))
    no_interrupts = {
        STRANDS_PENDING_INTERRUPT_STATE_KEY: {
            "agent": "resume_agent",
            "interrupts": "bad",
        }
    }
    _collect_events(bridge, _ctx("plain", session_id="s", state=no_interrupts))

    assert agent.prompts[0] == [
        {"interruptResponse": {"interruptId": "a", "response": "ok"}}
    ]
    assert agent.prompts[1] == [
        {"interruptResponse": {"interruptId": "b", "response": "ok"}}
    ]
    assert agent.prompts[2] == "{not-json"
    assert agent.prompts[3] == "plain"


def test_pending_interrupt_without_text_clears_state():
    class EmptyAgent:
        async def stream_async(self, prompt, invocation_state=None):
            del prompt, invocation_state
            yield {"metadata": "ignored"}

    state = {
        STRANDS_PENDING_INTERRUPT_STATE_KEY: {
            "agent": "empty_agent",
            "interrupts": [{"id": "interrupt-1"}],
        }
    }

    events = _collect_events(
        StrandsAgentkitBridge(EmptyAgent(), name="empty_agent"),
        _ctx("ok", session_id="s", state=state),
    )

    assert events == [
        {
            "partial": None,
            "text": "",
            "error_code": None,
            "interrupted": None,
            "metadata": None,
            "state_delta": {STRANDS_PENDING_INTERRUPT_STATE_KEY: None},
        }
    ]


def test_invoke_async_fallback_is_supported():
    class InvokeOnlyAgent:
        async def invoke_async(self, prompt, invocation_state=None):
            assert invocation_state["agentkit"]["invocation_id"] == "invocation-none"
            return _agent_result(f"invoke:{prompt}")

    events = _collect_events(
        StrandsAgentkitBridge(InvokeOnlyAgent(), name="strands_invoke")
    )

    assert _visible(events) == [{"partial": False, "text": "invoke:hi"}]


def test_result_text_variants_cover_messages_exceptions_and_plain_values():
    class MessageObject:
        content = [{"text": "message-object"}]

    assert _result_to_text(None) == ""
    assert _result_to_text(SimpleNamespace(message=MessageObject())) == "message-object"
    assert _result_to_text(RuntimeError("boom")) == "boom"
    assert _result_to_text({"answer": []}) == '{"answer": []}'
    assert _result_to_text(42) == "42"


def test_final_message_filters_reasoning_and_tool_blocks():
    result = SimpleNamespace(
        message={
            "role": "assistant",
            "content": [
                {"reasoningContent": {"reasoningText": {"text": "internal"}}},
                {"toolUse": {"name": "calculator"}},
                {"text": "visible"},
            ],
        },
        structured_output=None,
        interrupts=[],
    )

    assert _result_to_text(result) == "visible"
    assert (
        _result_to_text(
            {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"reasoningContent": {"reasoningText": {"text": "internal"}}},
                        {"toolUse": {"name": "calculator"}},
                        {"text": "visible-dict"},
                    ],
                }
            }
        )
        == "visible-dict"
    )
    assert _result_to_text({"content": [{"toolUse": {"name": "calculator"}}]}) == ""


def test_model_output_fallbacks_cover_json_and_plain_string():
    class JsonStructured:
        def model_dump_json(self):
            return '{"ok":true}'

    class BrokenStructured:
        def model_dump_json(self):
            raise RuntimeError("json failed")

        def model_dump(self):
            raise RuntimeError("dump failed")

        def __str__(self):
            return "plain-structured"

    json_events = _collect_events(
        StrandsAgentkitBridge(
            type(
                "JsonStructuredAgent",
                (),
                {
                    "stream_async": lambda self, prompt, invocation_state=None: (
                        _async_result(JsonStructured())
                    )
                },
            )()
        )
    )
    broken_events = _collect_events(
        StrandsAgentkitBridge(
            type(
                "BrokenStructuredAgent",
                (),
                {
                    "stream_async": lambda self, prompt, invocation_state=None: (
                        _async_result(BrokenStructured())
                    )
                },
            )()
        )
    )

    assert _visible(json_events) == [{"partial": False, "text": '{"ok":true}'}]
    assert _visible(broken_events) == [{"partial": False, "text": "plain-structured"}]


async def _async_result(structured_output):
    yield {
        "result": SimpleNamespace(
            stop_reason="end_turn",
            message=None,
            structured_output=structured_output,
            interrupts=[],
        )
    }


def test_callable_fallback_and_dict_result_are_supported():
    class CallableAgent:
        def __call__(self, prompt, invocation_state=None):
            assert invocation_state["agentkit"]["invocation_id"] == "invocation-none"
            return {"answer": [{"text": f"call:{prompt}"}]}

    events = _collect_events(
        StrandsAgentkitBridge(CallableAgent(), name="callable_agent")
    )

    assert _visible(events) == [{"partial": False, "text": "call:hi"}]


def test_unsupported_entry_raises_clear_error():
    bridge = StrandsAgentkitBridge(object(), name="unsupported_strands")

    with pytest.raises(Exception, match="Strands entry must expose"):
        _collect_events(bridge)


def test_invalid_factory_configuration_is_rejected():
    with pytest.raises(TypeError, match="agent_factory=True"):
        StrandsAgentkitBridge(object(), agent_factory=True)

    with pytest.raises(ValueError, match="max_session_agents"):
        StrandsAgentkitBridge(
            lambda: object(), agent_factory=True, max_session_agents=0
        )


def test_factory_with_extra_required_arguments_is_rejected():
    def build_agent(context_id, tenant):
        del context_id, tenant
        return object()

    bridge = StrandsAgentkitBridge(build_agent, agent_factory=True)

    with pytest.raises(TypeError, match="required arguments: context_id, tenant"):
        _collect_events(bridge, _ctx("hello", session_id="s"))


def test_structured_output_is_returned_as_json_text():
    class Structured:
        def model_dump(self):
            return {"intent": "general"}

    class StructuredAgent:
        async def stream_async(self, prompt, invocation_state=None):
            del prompt, invocation_state
            yield {
                "result": SimpleNamespace(
                    stop_reason="end_turn",
                    message={"role": "assistant", "content": []},
                    structured_output=Structured(),
                    interrupts=[],
                )
            }

    events = _collect_events(StrandsAgentkitBridge(StructuredAgent()))

    assert _visible(events)[0]["partial"] is False
    assert json.loads(_visible(events)[0]["text"]) == {"intent": "general"}


def test_internal_helpers_handle_empty_snapshot_and_non_dict_stream_event():
    _restore_snapshot(object(), None)
    assert _stream_text_from_event(object()) == ""


def test_real_strands_agent_streams_through_bridge_when_package_is_available():
    strands = pytest.importorskip("strands")
    pytest.importorskip("strands.models")

    from strands.models import Model

    class LocalModel(Model):
        def update_config(self, **model_config):
            self.model_config = model_config

        def get_config(self):
            return {}

        async def structured_output(
            self, output_model, prompt, system_prompt=None, **kwargs
        ):
            yield {"output": output_model()}

        async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
            user_text = messages[-1]["content"][0]["text"]
            yield {"messageStart": {"role": "assistant"}}
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": f"real:{user_text}"}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            yield {
                "metadata": {
                    "usage": {
                        "inputTokens": 1,
                        "outputTokens": 1,
                        "totalTokens": 2,
                    },
                    "metrics": {"latencyMs": 0},
                }
            }

    agent = strands.Agent(model=LocalModel(), callback_handler=None)
    events = _collect_events(StrandsAgentkitBridge(agent, name="real_strands"))

    assert _visible(events) == [
        {"partial": True, "text": "real:hi"},
        {"partial": False, "text": "real:hi"},
    ]

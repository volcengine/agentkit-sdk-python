import asyncio
from types import SimpleNamespace
import pytest

pytest.importorskip("langchain.agents")
from google.adk.apps import App
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.tools import tool
from langchain.agents import create_agent
from langgraph.prebuilt import create_react_agent
from agentkit.frameworks import LangChainAgentkitBridge, LangGraphAgentkitBridge
from agentkit.plugins import LLMShieldPlugin
from agentkit.plugins.agentsentry_v3 import MISSING_PLAN


class Model(BaseChatModel):
    plan: str

    @property
    def _llm_type(self):
        return "fixture"

    def bind_tools(self, *args, **kwargs):
        return self

    def _generate(self, messages, **kwargs):
        if isinstance(messages[-1], ToolMessage):
            message = AIMessage(content="done")
        else:
            message = AIMessage(
                content=[
                    {"type": "text", "text": "prefix"},
                    {"type": "text", "text": self.plan},
                ]
                if self.plan
                else "",
                tool_calls=[
                    {
                        "id": "call1",
                        "name": "record",
                        "args": {"action": "test"},
                        "type": "tool_call",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(self, messages, **kwargs):
        return self._generate(messages, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("framework", ["langchain", "langgraph"])
@pytest.mark.parametrize("plan,expected", [("safe", 1), ("risk", 0), ("", 0)])
async def test_original_agent(framework, plan, expected, monkeypatch):
    for k, v in {
        "URL": "http://sentry/OpenTOP/V3/Lumen/Moderate",
        "ACCOUNT_ID": "account",
        "INSTANCE_ID": "instance",
        "AK": "ak",
        "SK": "sk",
    }.items():
        monkeypatch.setenv("AGENTSENTRY_" + k, v)
    executed = []
    seen = []

    @tool
    def record(action: str) -> str:
        """Record locally."""
        executed.append(action)
        return "ok"

    model = Model(plan=plan)
    original = (
        create_agent(model, [record])
        if framework == "langchain"
        else create_react_agent(model, [record])
    )
    bridge = (
        LangChainAgentkitBridge(original, name="test", input_key="messages")
        if framework == "langchain"
        else LangGraphAgentkitBridge(original, name="test", stream_nodes=("agent",))
    )
    shield = LLMShieldPlugin.from_env()

    def moderate(text, **kwargs):
        seen.append((text, kwargs))
        return "blocked-risk" if "risk" in text else None

    shield._sentry_v3.moderate = moderate
    sessions = InMemorySessionService()
    await sessions.create_session(app_name="test", user_id="u", session_id="s")
    runner = Runner(
        app=App(name="test", root_agent=bridge, plugins=[shield]),
        session_service=sessions,
    )
    events = [
        e
        async for e in runner.run_async(
            user_id="u",
            session_id="s",
            new_message=types.Content(role="user", parts=[types.Part(text="hello")]),
        )
    ]
    assert len(executed) == expected
    if not expected:
        reason = "blocked-risk" if plan == "risk" else MISSING_PLAN
        notice_delta = f"\n\n{reason}"
        earlier_deltas = [
            event for event in events[:-1]
            if event.partial and event.content.parts[0].text != notice_delta
        ]
        if plan:
            assert earlier_deltas
        if earlier_deltas:
            assert events[-2].partial
            assert events[-2].content.parts[0].text == notice_delta
            assert events[-2].id != events[-1].id
        else:
            assert all(not event.partial for event in events)
        terminal = events[-1]
        assert not terminal.partial
        assert terminal.is_final_response()
        payload = terminal.model_dump(by_alias=True, exclude_none=True)
        assert "errorCode" not in payload
        assert "errorMessage" not in payload
        assert payload["content"]["parts"][0]["text"] == reason

        history = await sessions.get_session(app_name="test", user_id="u", session_id="s")
        assert history.events[-1].id == terminal.id
        assert history.events[-1].content.parts[0].text == reason
        assert history.events[-1].error_code is None
    else:
        assert all(event.error_code is None for event in events)
    if plan:
        assert any(
            t == "prefix\n" + plan and k["hook_name"] == "before_tool_call"
            for t, k in seen
        )
    assert seen[0][1]["hook_name"] == "before_dispatch"


def test_guard_state_is_per_invocation_and_rejects_wrong_arguments():
    from agentkit.frameworks._agentsentry import _make_guard, AgentSentryBlocked
    from langchain_core.outputs import LLMResult

    observed = []
    plugin = SimpleNamespace(
        _sentry_v3=SimpleNamespace(moderate=lambda *a, **kw: observed.append(kw))
    )
    context = SimpleNamespace(
        session=SimpleNamespace(id="session"), invocation_id="run"
    )
    first = _make_guard(plugin, context)
    second = _make_guard(plugin, context)
    message = AIMessage(
        content="safe plan",
        tool_calls=[
            {
                "id": "x",
                "name": "record",
                "args": {"action": "safe"},
                "type": "tool_call",
            }
        ],
    )
    first.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]))
    with pytest.raises(AgentSentryBlocked):
        second.on_tool_start({"name": "record"}, '{"action":"safe"}')
    first.on_tool_start({"name": "record"}, '{"action":"safe"}')
    assert len(observed) == 1
    assert observed[0]["tool_calls"][0]["Function"]["Name"] == "record"
    with pytest.raises(AgentSentryBlocked):
        first.on_tool_start({"name": "record"}, '{"action":"changed"}')
    assert len(observed) == 1

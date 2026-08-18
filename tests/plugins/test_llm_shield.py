from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
import requests
from google.adk.events import Event
from google.genai import types

from agentkit.platform.configuration import Credentials
from agentkit.plugins.llm_shield import (
    LLM_SHIELD_BLOCK_MESSAGE,
    LLM_SHIELD_UNAVAILABLE_MESSAGE,
    LLMShieldPlugin,
)


class _Response:
    def __init__(self, payload=None, *, status_code: int = 200, json_error=None):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


def _decision(value: int) -> dict:
    return {
        "Result": {
            "Decision": {"DecisionType": value},
            "RiskInfo": {"Risks": [{"Category": 104}]},
        }
    }


@pytest.fixture(autouse=True)
def _clean_llm_shield_env(monkeypatch):
    for name in (
        "ENABLE_LLM_SHIELD",
        "TOOL_LLM_SHIELD_APP_ID",
        "TOOL_LLM_SHIELD_REGION",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("value", [None, "", "0", "false", "FALSE", "no", "off"])
def test_from_env_returns_none_when_disabled(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("ENABLE_LLM_SHIELD", value)

    assert LLMShieldPlugin.from_env() is None


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_from_env_enables_with_app_id_only(monkeypatch, value):
    monkeypatch.setenv("ENABLE_LLM_SHIELD", value)
    monkeypatch.setenv("TOOL_LLM_SHIELD_APP_ID", "app-test")

    plugin = LLMShieldPlugin.from_env()

    assert plugin is not None
    assert plugin.app_id == "app-test"
    assert plugin.region == "cn-beijing"


def test_from_env_rejects_missing_app_id(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_SHIELD", "true")

    with pytest.raises(ValueError, match="TOOL_LLM_SHIELD_APP_ID"):
        LLMShieldPlugin.from_env()


def test_from_env_rejects_invalid_boolean(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_SHIELD", "sometimes")

    with pytest.raises(ValueError, match="ENABLE_LLM_SHIELD"):
        LLMShieldPlugin.from_env()


def test_from_env_uses_explicit_shield_region(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM_SHIELD", "true")
    monkeypatch.setenv("TOOL_LLM_SHIELD_APP_ID", "app-test")
    monkeypatch.setenv("TOOL_LLM_SHIELD_REGION", "cn-shanghai")

    plugin = LLMShieldPlugin.from_env()

    assert plugin is not None
    assert plugin.region == "cn-shanghai"


def test_moderate_text_signs_with_agentkit_credentials(monkeypatch):
    calls = []

    class _Configuration:
        def __init__(self, *, region):
            assert region == "cn-beijing"

        def get_service_credentials(self, service_key):
            assert service_key == "llm_shield"
            return Credentials("ak", "sk", "token", source="test")

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return _Response(_decision(1))

    monkeypatch.setattr("agentkit.plugins.llm_shield.VolcConfiguration", _Configuration)
    monkeypatch.setattr("agentkit.plugins.llm_shield.requests.post", fake_post)
    plugin = LLMShieldPlugin(app_id="app-test", region="cn-beijing", timeout=7)

    assert asyncio.run(plugin.moderate_text("safe text", role="user")) is None
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url.endswith("/v2/moderate")
    assert kwargs["timeout"] == 7
    assert kwargs["params"] == {"Action": "Moderate", "Version": "2025-08-31"}
    assert "Authorization" in kwargs["headers"]
    assert kwargs["headers"]["X-Security-Token"] == "token"
    assert "x-api-key" not in kwargs["headers"]
    assert json.loads(kwargs["data"])["Scene"] == "app-test"


def test_moderate_text_returns_stable_block_message(monkeypatch):
    monkeypatch.setattr(
        "agentkit.plugins.llm_shield.requests.post",
        lambda *args, **kwargs: _Response(_decision(2)),
    )
    plugin = LLMShieldPlugin(app_id="app-test", region="cn-beijing")
    monkeypatch.setattr(plugin, "_request_headers", lambda body: {})

    result = asyncio.run(plugin.moderate_text("unsafe", role="assistant"))

    assert result == LLM_SHIELD_BLOCK_MESSAGE


@pytest.mark.parametrize(
    "response_or_error",
    [
        _Response({}, status_code=503),
        _Response(json_error=json.JSONDecodeError("bad", "{", 0)),
        _Response({"Result": {"Decision": {"DecisionType": 99}}}),
        requests.Timeout("timeout"),
    ],
)
def test_moderate_text_fails_closed_without_logging_content(
    monkeypatch, caplog, response_or_error
):
    def fake_post(*args, **kwargs):
        if isinstance(response_or_error, Exception):
            raise response_or_error
        return response_or_error

    monkeypatch.setattr("agentkit.plugins.llm_shield.requests.post", fake_post)
    plugin = LLMShieldPlugin(app_id="app-test", region="cn-beijing")
    monkeypatch.setattr(plugin, "_request_headers", lambda body: {})

    result = asyncio.run(plugin.moderate_text("sensitive-body-marker", role="user"))

    assert result == LLM_SHIELD_UNAVAILABLE_MESSAGE
    assert "sensitive-body-marker" not in caplog.text


def test_before_run_blocks_agent_execution_content(monkeypatch):
    plugin = LLMShieldPlugin(app_id="app-test", region="cn-beijing")

    async def moderate(text, *, role):
        assert text == "unsafe input"
        assert role == "user"
        return LLM_SHIELD_BLOCK_MESSAGE

    monkeypatch.setattr(plugin, "moderate_text", moderate)
    context = SimpleNamespace(
        invocation_id="inv-1",
        agent_states={},
        user_content=types.Content(
            role="user", parts=[types.Part(text="unsafe input")]
        ),
    )

    result = asyncio.run(plugin.before_run_callback(invocation_context=context))

    assert result.parts[0].text == LLM_SHIELD_BLOCK_MESSAGE


def test_before_tool_blocks_unsafe_arguments(monkeypatch):
    plugin = LLMShieldPlugin(app_id="app-test", region="cn-beijing")
    calls = []

    async def moderate(text, *, role):
        calls.append((text, role))
        return LLM_SHIELD_BLOCK_MESSAGE

    monkeypatch.setattr(plugin, "moderate_text", moderate)

    result = asyncio.run(
        plugin.before_tool_callback(
            tool=object(),
            tool_args={"query": "unsafe tool input", "limit": 2},
            tool_context=object(),
        )
    )

    assert result == {"result": LLM_SHIELD_BLOCK_MESSAGE}
    assert calls == [('{"query":"unsafe tool input","limit":2}', "user")]


def test_after_tool_replaces_unsafe_result(monkeypatch):
    plugin = LLMShieldPlugin(app_id="app-test", region="cn-beijing")
    calls = []

    async def moderate(text, *, role):
        calls.append((text, role))
        return LLM_SHIELD_BLOCK_MESSAGE

    monkeypatch.setattr(plugin, "moderate_text", moderate)

    result = asyncio.run(
        plugin.after_tool_callback(
            tool=object(),
            tool_args={"query": "safe"},
            tool_context=object(),
            result={"answer": "unsafe tool output"},
        )
    )

    assert result == {"result": LLM_SHIELD_BLOCK_MESSAGE}
    assert calls == [('{"answer":"unsafe tool output"}', "assistant")]


def test_tool_payload_serialization_failure_fails_closed(monkeypatch, caplog):
    plugin = LLMShieldPlugin(app_id="app-test", region="cn-beijing")
    recursive: dict = {}
    recursive["self"] = recursive

    async def should_not_run(*args, **kwargs):
        raise AssertionError("unserializable tool payload must fail closed locally")

    monkeypatch.setattr(plugin, "moderate_text", should_not_run)

    result = asyncio.run(
        plugin.before_tool_callback(
            tool=object(), tool_args=recursive, tool_context=object()
        )
    )

    assert result == {"result": LLM_SHIELD_UNAVAILABLE_MESSAGE}
    assert "could not serialize" in caplog.text


def test_on_event_buffers_partial_text_and_moderates_complete_output(monkeypatch):
    plugin = LLMShieldPlugin(app_id="app-test", region="cn-beijing")
    moderated = []

    async def moderate(text, *, role):
        moderated.append((text, role))
        return None

    monkeypatch.setattr(plugin, "moderate_text", moderate)
    context = SimpleNamespace(invocation_id="inv-1", agent_states={})
    partial = Event(
        invocation_id="inv-1",
        author="agent",
        partial=True,
        content=types.Content(role="model", parts=[types.Part(text="hel")]),
    )
    final = Event(
        invocation_id="inv-1",
        author="agent",
        partial=False,
        content=types.Content(role="model", parts=[types.Part(text="hello")]),
    )

    hidden = asyncio.run(
        plugin.on_event_callback(invocation_context=context, event=partial)
    )
    visible = asyncio.run(
        plugin.on_event_callback(invocation_context=context, event=final)
    )

    assert hidden.content.parts[0].text == ""
    assert visible.content.parts[0].text == "hello"
    assert moderated == [("hello", "assistant")]


def test_on_event_replaces_unsafe_output_and_cleans_invocation(monkeypatch):
    plugin = LLMShieldPlugin(app_id="app-test", region="cn-beijing")

    async def moderate(text, *, role):
        return LLM_SHIELD_BLOCK_MESSAGE

    monkeypatch.setattr(plugin, "moderate_text", moderate)
    context = SimpleNamespace(invocation_id="inv-1", agent_states={})
    event = Event(
        invocation_id="inv-1",
        author="agent",
        partial=False,
        content=types.Content(role="model", parts=[types.Part(text="unsafe output")]),
    )

    replaced = asyncio.run(
        plugin.on_event_callback(invocation_context=context, event=event)
    )
    asyncio.run(plugin.after_run_callback(invocation_context=context))

    assert replaced.content.parts[0].text == LLM_SHIELD_BLOCK_MESSAGE
    assert context.agent_states == {}


def test_output_buffers_are_isolated_by_invocation(monkeypatch):
    plugin = LLMShieldPlugin(app_id="app-test", region="cn-beijing")
    moderated = []

    async def moderate(text, *, role):
        moderated.append((text, role))
        return None

    monkeypatch.setattr(plugin, "moderate_text", moderate)
    contexts = {
        invocation_id: SimpleNamespace(invocation_id=invocation_id, agent_states={})
        for invocation_id in ("inv-1", "inv-2")
    }
    for invocation_id, text in (("inv-1", "one"), ("inv-2", "two")):
        asyncio.run(
            plugin.on_event_callback(
                invocation_context=contexts[invocation_id],
                event=Event(
                    invocation_id=invocation_id,
                    author="agent",
                    partial=True,
                    content=types.Content(role="model", parts=[types.Part(text=text)]),
                ),
            )
        )
    for invocation_id in ("inv-2", "inv-1"):
        asyncio.run(
            plugin.on_event_callback(
                invocation_context=contexts[invocation_id],
                event=Event(
                    invocation_id=invocation_id,
                    author="agent",
                    partial=False,
                    content=types.Content(role="model", parts=[types.Part(text="")]),
                ),
            )
        )

    assert moderated == [("two", "assistant"), ("one", "assistant")]


def test_output_buffer_limit_fails_closed(monkeypatch):
    plugin = LLMShieldPlugin(
        app_id="app-test",
        region="cn-beijing",
        max_output_bytes=3,
    )

    async def should_not_run(*args, **kwargs):
        raise AssertionError("overflowed output must fail closed locally")

    monkeypatch.setattr(plugin, "moderate_text", should_not_run)
    context = SimpleNamespace(invocation_id="inv-overflow", agent_states={})
    asyncio.run(
        plugin.on_event_callback(
            invocation_context=context,
            event=Event(
                invocation_id="inv-overflow",
                author="agent",
                partial=True,
                content=types.Content(role="model", parts=[types.Part(text="four")]),
            ),
        )
    )
    final = asyncio.run(
        plugin.on_event_callback(
            invocation_context=context,
            event=Event(
                invocation_id="inv-overflow",
                author="agent",
                partial=False,
                content=types.Content(role="model", parts=[types.Part(text="four")]),
            ),
        )
    )

    assert final.content.parts[0].text == LLM_SHIELD_UNAVAILABLE_MESSAGE

"""Strands Agents adapter for AgentKit apps."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import AsyncGenerator, AsyncIterator, Callable
import copy
from dataclasses import dataclass
import inspect
import json
from typing import Any

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types
from pydantic import PrivateAttr

from agentkit.frameworks._common import (
    UnsupportedFrameworkAgentError,
    adk_event,
    content_to_text,
    json_text,
    maybe_await,
    user_text,
)


STRANDS_PENDING_INTERRUPT_STATE_KEY = "agentkit:strands:pending_interrupt"


@dataclass
class _AgentEntry:
    agent: Any
    lock: asyncio.Lock


def _method_kwargs(method: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return kwargs

    parameters = signature.parameters
    accepts_kwargs = any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters.values()
    )
    return {
        key: value
        for key, value in kwargs.items()
        if accepts_kwargs or key in parameters
    }


def _session_key(ctx: InvocationContext) -> str | None:
    session = getattr(ctx, "session", None)
    session_id = getattr(session, "id", None)
    if not session_id:
        return None
    app_name = getattr(session, "app_name", None) or ""
    user_id = getattr(session, "user_id", None) or ""
    return "\0".join((str(app_name), str(user_id), str(session_id)))


def _agentkit_invocation_state(ctx: InvocationContext) -> dict[str, Any]:
    session = getattr(ctx, "session", None)
    return {
        "agentkit": {
            "invocation_id": getattr(ctx, "invocation_id", None),
            "app_name": getattr(session, "app_name", None),
            "user_id": getattr(session, "user_id", None),
            "session_id": getattr(session, "id", None),
        }
    }


def _callable_signature(func: Callable[..., Any]) -> inspect.Signature:
    try:
        return inspect.signature(func)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            "Strands agent factory has no inspectable signature. Expose a "
            "zero-argument factory or a factory accepting context_id."
        ) from exc


def _callable_required_params(func: Callable[..., Any]) -> list[inspect.Parameter]:
    signature = _callable_signature(func)
    return [
        param
        for name, param in signature.parameters.items()
        if param.default is inspect.Parameter.empty
        and param.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
    ]


def _factory_context_call(
    factory: Callable[..., Any],
    parameter: inspect.Parameter,
    context_id: str | None,
) -> Any:
    if parameter.kind == inspect.Parameter.KEYWORD_ONLY:
        return factory(context_id=context_id)
    return factory(context_id)


def _invoke_factory(factory: Callable[..., Any], context_id: str | None) -> Any:
    signature = _callable_signature(factory)
    required_params = _callable_required_params(factory)
    if not required_params:
        context_param = signature.parameters.get("context_id")
        if context_param is not None:
            result = _factory_context_call(factory, context_param, context_id)
        else:
            result = factory()
    elif len(required_params) == 1:
        result = _factory_context_call(factory, required_params[0], context_id)
    else:
        formatted = ", ".join(param.name for param in required_params)
        raise TypeError(
            "Strands agent factory must be zero-argument or accept a single "
            f"context_id argument; required arguments: {formatted}."
        )

    if inspect.isawaitable(result):
        close = getattr(result, "close", None)
        if callable(close):
            close()
        raise TypeError(
            "Strands agent factory returned an awaitable object. Generated "
            "AgentKit apps require a synchronous factory."
        )
    return result


def _supports_agent_snapshot(agent: Any) -> bool:
    return callable(getattr(agent, "take_snapshot", None)) and callable(
        getattr(agent, "load_snapshot", None)
    )


def _supports_orchestrator_snapshot(agent: Any) -> bool:
    return callable(getattr(agent, "serialize_state", None)) and callable(
        getattr(agent, "deserialize_state", None)
    )


def _capture_snapshot(agent: Any) -> Any | None:
    if _supports_agent_snapshot(agent):
        return agent.take_snapshot(preset="session")
    if _supports_orchestrator_snapshot(agent):
        return copy.deepcopy(agent.serialize_state())
    return None


def _restore_snapshot(agent: Any, snapshot: Any | None) -> None:
    if snapshot is None:
        return
    snapshot_copy = copy.deepcopy(snapshot)
    if _supports_agent_snapshot(agent):
        agent.load_snapshot(snapshot_copy)
        return
    if _supports_orchestrator_snapshot(agent):
        agent.deserialize_state(snapshot_copy)


def _interrupt_to_dict(interrupt: Any) -> dict[str, Any]:
    to_dict = getattr(interrupt, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if isinstance(value, dict):
            return value
    return {
        "id": getattr(interrupt, "id", None),
        "name": getattr(interrupt, "name", None),
        "reason": getattr(interrupt, "reason", None),
    }


def _interrupts_payload(result: Any) -> list[dict[str, Any]]:
    interrupts = getattr(result, "interrupts", None)
    if not interrupts:
        return []
    return [_interrupt_to_dict(interrupt) for interrupt in interrupts]


def _pending_interrupt(ctx: InvocationContext, agent_name: str) -> Any | None:
    session = getattr(ctx, "session", None)
    state = getattr(session, "state", None)
    if not isinstance(state, dict):
        return None
    pending = state.get(STRANDS_PENDING_INTERRUPT_STATE_KEY)
    if not pending:
        return None
    if isinstance(pending, dict) and pending.get("agent") not in {None, agent_name}:
        return None
    return pending


def _parse_json_if_possible(value: str) -> Any:
    stripped = value.strip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _resume_prompt(text_input: str, pending: Any) -> Any:
    parsed = _parse_json_if_possible(text_input)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        if "interruptResponse" in parsed:
            return [parsed]
        if "interruptResponses" in parsed and isinstance(
            parsed["interruptResponses"], list
        ):
            return parsed["interruptResponses"]

    interrupts = pending.get("interrupts") if isinstance(pending, dict) else None
    if not isinstance(interrupts, list):
        return text_input

    responses = []
    for interrupt in interrupts:
        if not isinstance(interrupt, dict):
            continue
        interrupt_id = interrupt.get("id")
        if not interrupt_id:
            continue
        responses.append(
            {
                "interruptResponse": {
                    "interruptId": interrupt_id,
                    "response": text_input,
                }
            }
        )
    return responses or text_input


def _content_blocks_to_text(content: Any) -> str:
    if not isinstance(content, list):
        return content_to_text(content)

    chunks = []
    for block in content:
        if isinstance(block, dict):
            if "text" in block:
                chunks.append(content_to_text(block["text"]))
            continue
        chunks.append(content_to_text(block))
    return "".join(chunks)


def _message_to_text(message: Any) -> str:
    if not message:
        return ""
    if isinstance(message, dict):
        return _content_blocks_to_text(message.get("content"))
    content = getattr(message, "content", None)
    return _content_blocks_to_text(content)


def _model_to_text(value: Any) -> str:
    model_dump_json = getattr(value, "model_dump_json", None)
    if callable(model_dump_json):
        try:
            return str(model_dump_json())
        except Exception:
            pass
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return json_text(model_dump())
        except Exception:
            pass
    return str(value)


def _node_result_text(node_result: Any) -> str:
    result = getattr(node_result, "result", node_result)
    return _result_to_text(result)


def _multiagent_result_to_text(result: Any) -> str:
    results = getattr(result, "results", None)
    if not isinstance(results, dict) or not results:
        return str(result)

    execution_order = getattr(result, "execution_order", None)
    if execution_order:
        for node in reversed(execution_order):
            node_id = getattr(node, "node_id", node)
            if node_id in results:
                text = _node_result_text(results[node_id])
                if text:
                    return text

    node_history = getattr(result, "node_history", None)
    if node_history:
        for node in reversed(node_history):
            node_id = getattr(node, "node_id", node)
            if node_id in results:
                text = _node_result_text(results[node_id])
                if text:
                    return text

    for node_result in reversed(list(results.values())):
        text = _node_result_text(node_result)
        if text:
            return text
    return ""


def _result_to_text(result: Any) -> str:
    if result is None:
        return ""
    structured_output = getattr(result, "structured_output", None)
    if structured_output is not None:
        return _model_to_text(structured_output)
    message_text = _message_to_text(getattr(result, "message", None))
    if message_text:
        return message_text
    if isinstance(result, Exception):
        return str(result)
    if isinstance(getattr(result, "results", None), dict):
        return _multiagent_result_to_text(result)
    if isinstance(result, dict):
        for key in ("message", "content", "result", "output", "answer", "text"):
            if key in result:
                if key == "message":
                    text = _message_to_text(result[key])
                elif key == "content":
                    text = _content_blocks_to_text(result[key])
                else:
                    text = content_to_text(result[key])
                if text:
                    return text
        if "message" in result or "content" in result:
            return ""
        return json_text(result)
    return str(result)


def _stream_text_from_event(event: Any) -> str:
    if not isinstance(event, dict):
        return ""

    event_type = event.get("type")
    if event_type == "multiagent_node_stream":
        return _stream_text_from_event(event.get("event"))

    if "data" in event:
        return content_to_text(event["data"])

    nested_event = event.get("event")
    if isinstance(nested_event, dict) and "data" in nested_event:
        return content_to_text(nested_event["data"])

    return ""


def _result_from_event(event: Any) -> Any | None:
    if isinstance(event, dict) and "result" in event:
        return event["result"]
    return None


def _is_interrupt_result(result: Any) -> bool:
    return getattr(result, "stop_reason", None) == "interrupt" or bool(
        getattr(result, "interrupts", None)
    )


class StrandsAgentkitBridge(BaseAgent):
    """Adapt a Strands Agent, A2AAgent, Graph, or Swarm to AgentKit's ADK runtime."""

    _source: Any = PrivateAttr()
    _agent_factory: bool = PrivateAttr(default=False)
    _max_session_agents: int = PrivateAttr(default=1000)
    _session_agents: OrderedDict[str, _AgentEntry] = PrivateAttr(
        default_factory=OrderedDict
    )
    _session_snapshots: OrderedDict[str, Any] = PrivateAttr(default_factory=OrderedDict)
    _context_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    _singleton_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    _template_snapshot: Any = PrivateAttr(default=None)

    def __init__(
        self,
        source: Any,
        *,
        name: str = "strands_agent",
        description: str = "Strands agent adapted for AgentKit runtime",
        agent_factory: bool = False,
        max_session_agents: int = 1000,
    ) -> None:
        super().__init__(name=name, description=description)
        if max_session_agents < 1:
            raise ValueError("max_session_agents must be >= 1")
        if agent_factory and not callable(source):
            raise TypeError("agent_factory=True requires a callable source.")
        self._source = source
        self._agent_factory = agent_factory
        self._max_session_agents = max_session_agents
        if not agent_factory:
            self._template_snapshot = _capture_snapshot(source)

    def _evict_cached_agents(self) -> None:
        while len(self._session_agents) > self._max_session_agents:
            _, entry = self._session_agents.popitem(last=False)
            cleanup = getattr(entry.agent, "cleanup", None)
            if callable(cleanup):
                cleanup()

    def _evict_snapshots(self) -> None:
        while len(self._session_snapshots) > self._max_session_agents:
            self._session_snapshots.popitem(last=False)

    async def _factory_entry(self, ctx: InvocationContext) -> _AgentEntry:
        key = _session_key(ctx)
        if key is None:
            return _AgentEntry(
                agent=_invoke_factory(self._source, None),
                lock=asyncio.Lock(),
            )

        async with self._context_lock:
            entry = self._session_agents.get(key)
            if entry is None:
                entry = _AgentEntry(
                    agent=_invoke_factory(self._source, key),
                    lock=asyncio.Lock(),
                )
                self._session_agents[key] = entry
                self._evict_cached_agents()
            else:
                self._session_agents.move_to_end(key)
            return entry

    async def _stream_source(
        self,
        agent: Any,
        prompt: Any,
        ctx: InvocationContext,
    ) -> AsyncIterator[Any]:
        kwargs = {
            "invocation_state": _agentkit_invocation_state(ctx),
            "idempotency_token": getattr(ctx, "invocation_id", None),
        }

        stream_async = getattr(agent, "stream_async", None)
        if callable(stream_async):
            async for event in stream_async(
                prompt, **_method_kwargs(stream_async, kwargs)
            ):
                yield event
            return

        result = await self._call_once(agent, prompt, ctx)
        yield {"result": result}

    async def _call_once(self, agent: Any, prompt: Any, ctx: InvocationContext) -> Any:
        kwargs = {
            "invocation_state": _agentkit_invocation_state(ctx),
            "idempotency_token": getattr(ctx, "invocation_id", None),
        }
        invoke_async = getattr(agent, "invoke_async", None)
        if callable(invoke_async):
            return await invoke_async(prompt, **_method_kwargs(invoke_async, kwargs))

        if callable(agent):
            return await maybe_await(agent(prompt, **_method_kwargs(agent, kwargs)))

        raise UnsupportedFrameworkAgentError(
            "Strands entry must expose stream_async, invoke_async, or be callable. "
            "Supported entries include Agent, A2AAgent, Graph, Swarm, and compatible wrappers."
        )

    async def _run_with_factory(
        self,
        ctx: InvocationContext,
        prompt: Any,
    ) -> AsyncIterator[Any]:
        entry = await self._factory_entry(ctx)
        async with entry.lock:
            try:
                async for event in self._stream_source(entry.agent, prompt, ctx):
                    yield event
            finally:
                if _session_key(ctx) is None:
                    cleanup = getattr(entry.agent, "cleanup", None)
                    if callable(cleanup):
                        cleanup()

    async def _run_with_singleton(
        self,
        ctx: InvocationContext,
        prompt: Any,
    ) -> AsyncIterator[Any]:
        key = _session_key(ctx)
        async with self._singleton_lock:
            if self._template_snapshot is not None:
                snapshot = (
                    self._session_snapshots.get(key, self._template_snapshot)
                    if key is not None
                    else self._template_snapshot
                )
                _restore_snapshot(self._source, snapshot)

            try:
                async for event in self._stream_source(self._source, prompt, ctx):
                    yield event
            finally:
                if self._template_snapshot is not None:
                    if key is not None:
                        self._session_snapshots[key] = _capture_snapshot(self._source)
                        self._session_snapshots.move_to_end(key)
                        self._evict_snapshots()
                    _restore_snapshot(self._source, self._template_snapshot)

    def _final_event(
        self,
        ctx: InvocationContext,
        text: str,
        *,
        clear_pending_interrupt: bool,
    ) -> Event:
        event_kwargs: dict[str, Any] = {}
        if clear_pending_interrupt:
            event_kwargs["actions"] = EventActions(
                state_delta={STRANDS_PENDING_INTERRUPT_STATE_KEY: None}
            )
        return Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            partial=False,
            content=types.Content(role="model", parts=[types.Part(text=text)]),
            **event_kwargs,
        )

    def _clear_pending_interrupt_event(self, ctx: InvocationContext) -> Event:
        return Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            actions=EventActions(
                state_delta={STRANDS_PENDING_INTERRUPT_STATE_KEY: None}
            ),
        )

    def _interrupt_event(self, ctx: InvocationContext, result: Any) -> Event:
        payload = _interrupts_payload(result)
        state_delta = {}
        if _session_key(ctx) is not None:
            state_delta[STRANDS_PENDING_INTERRUPT_STATE_KEY] = {
                "agent": self.name,
                "interrupts": payload,
            }
        event_kwargs: dict[str, Any] = {}
        if state_delta:
            event_kwargs["actions"] = EventActions(state_delta=state_delta)
        return Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            interrupted=True,
            error_code="STRANDS_INTERRUPT",
            error_message="Strands execution interrupted and requires resume input.",
            custom_metadata={"strands_interrupt": payload},
            **event_kwargs,
        )

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        pending = _pending_interrupt(ctx, self.name)
        prompt = _resume_prompt(user_text(ctx), pending) if pending else user_text(ctx)
        accumulated_text = ""
        final_text = ""

        stream = (
            self._run_with_factory(ctx, prompt)
            if self._agent_factory
            else self._run_with_singleton(ctx, prompt)
        )

        async for item in stream:
            result = _result_from_event(item)
            if result is not None:
                if _is_interrupt_result(result):
                    yield self._interrupt_event(ctx, result)
                    return
                text = _result_to_text(result)
                if text:
                    final_text = text
                continue

            text = _stream_text_from_event(item)
            if text:
                accumulated_text += text
                yield adk_event(ctx, self.name, text, partial=True)

        text = final_text or accumulated_text
        if text:
            yield self._final_event(
                ctx,
                text,
                clear_pending_interrupt=pending is not None,
            )
        elif pending is not None:
            yield self._clear_pending_interrupt_event(ctx)

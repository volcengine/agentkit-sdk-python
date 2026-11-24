"""Invocation-scoped AgentSentry callbacks for migrated LC/LG agents.

No global monkeypatches: only standard LangChain model/tool callbacks are covered.
Direct Python side effects inside graph nodes are outside this boundary.
"""

from contextvars import ContextVar
from functools import wraps
import json
import threading

from agentkit.frameworks._common import adk_event

_active_guard = ContextVar("agentkit_agentsentry_guard", default=None)


class AgentSentryBlocked(RuntimeError):
    """Stop framework execution before a protected tool runs."""


def _text(content):
    if isinstance(content, str):
        return content
    return "\n".join(
        item if isinstance(item, str) else item.get("text", "")
        for item in (content or [])
        if isinstance(item, str)
        or isinstance(item, dict)
        and item.get("type") == "text"
        and isinstance(item.get("text"), str)
    )


def _key(name, args):
    return name, json.dumps(
        args, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def _make_guard(plugin, ctx):
    # Optional framework dependency is loaded only for the private V3 path.
    from langchain_core.callbacks import BaseCallbackHandler
    from agentkit.plugins.agentsentry_v3 import MISSING_CALL, MISSING_PLAN

    class Guard(BaseCallbackHandler):
        raise_error = True

        def __init__(self):
            self.plans = {}
            self.blocked = None
            self.lock = threading.RLock()
            self.session = {"SessionID": ctx.session.id, "RunID": ctx.invocation_id}

        def remember(self, message, completed=()):
            with self.lock:
                plan = _text(message.content)
                for call in getattr(message, "tool_calls", ()) or ():
                    if call.get("id") in completed:
                        continue
                    key = _key(call["name"], call["args"])
                    self.plans.setdefault(key, []).append((plan, call))

        def on_llm_end(self, response, **kwargs):
            for generations in response.generations:
                for generation in generations:
                    message = getattr(generation, "message", None)
                    if message is not None:
                        self.remember(message)

        def on_tool_start(self, serialized, input_str, *, inputs=None, **kwargs):
            with self.lock:
                if self.blocked:
                    raise AgentSentryBlocked(self.blocked)
                try:
                    args = inputs if isinstance(inputs, dict) else json.loads(input_str)
                    matches = self.plans.pop(_key(serialized.get("name"), args), [])
                except (ValueError, TypeError, AttributeError):
                    matches = []
                # Ambiguous or missing model/tool correlation must not allow execution.
                if len(matches) != 1:
                    self.blocked = MISSING_CALL
                elif not matches[0][0].strip():
                    self.blocked = MISSING_PLAN
                else:
                    plan, call = matches[0]
                    self.blocked = plugin._sentry_v3.moderate(
                        plan,
                        role="assistant",
                        hook_name="before_tool_call",
                        session_info=self.session,
                        tool_calls=[
                            {
                                "ID": call.get("id", ""),
                                "Type": "function",
                                "Function": {
                                    "Name": call["name"],
                                    "Arguments": json.dumps(args, ensure_ascii=False),
                                },
                            }
                        ],
                    )
                if self.blocked:
                    raise AgentSentryBlocked(self.blocked)

        def on_chat_model_start(self, *args, **kwargs):
            if self.blocked:
                raise AgentSentryBlocked(self.blocked)

        def on_llm_start(self, *args, **kwargs):
            if self.blocked:
                raise AgentSentryBlocked(self.blocked)

    return Guard()


def guarded_config(config=None):
    guard = _active_guard.get()
    if guard is None:
        return config
    merged = dict(config or {})
    callbacks = merged.get("callbacks")
    if callbacks is None or isinstance(callbacks, list):
        merged["callbacks"] = [*(callbacks or []), guard]
    else:
        callbacks = callbacks.copy()
        callbacks.add_handler(guard, inherit=True)
        merged["callbacks"] = callbacks
    return merged


def protect_migrated_tools(method):
    """Use the V3 plugin already attached to ADK App; public paths are unchanged."""

    @wraps(method)
    async def wrapped(self, ctx):
        plugins = getattr(getattr(ctx, "plugin_manager", None), "plugins", ())
        plugin = next((p for p in plugins if getattr(p, "_sentry_v3", None)), None)
        if plugin is None:
            async for event in method(self, ctx):
                yield event
            return
        guard = _make_guard(plugin, ctx)
        events = method(self, ctx)
        streamed_text = False
        try:
            while True:
                token = _active_guard.set(guard)
                try:
                    event = await anext(events)
                except StopAsyncIteration:
                    break
                except AgentSentryBlocked:
                    if not guard.blocked:
                        raise
                    break
                finally:
                    _active_guard.reset(token)
                if guard.blocked:
                    break
                streamed_text = streamed_text or getattr(event, "partial", False) is True
                yield event
            if guard.blocked:
                if streamed_text:
                    # Live clients may drop complete text after an earlier delta.
                    yield adk_event(ctx, self.name, f"\n\n{guard.blocked}", partial=True)
                yield adk_event(ctx, self.name, guard.blocked, partial=False)
        finally:
            token = _active_guard.set(guard)
            try:
                await events.aclose()
            finally:
                _active_guard.reset(token)

    return wrapped


async def restore_pending_tools(graph, config):
    """Rebuild pending calls from this graph/thread's checkpoint on resume."""
    guard = _active_guard.get()
    if guard is None:
        return
    from agentkit.plugins.agentsentry_v3 import MISSING_CALL

    try:
        snapshot = await graph.aget_state(config)
        messages = snapshot.values.get("messages", [])
        completed = set()
        for message in reversed(messages):
            if getattr(message, "type", None) == "tool":
                completed.add(message.tool_call_id)
            elif getattr(message, "type", None) == "ai":
                guard.remember(message, completed)
                return
    except (AttributeError, TypeError, ValueError):
        pass
    guard.blocked = MISSING_CALL
    raise AgentSentryBlocked(guard.blocked)

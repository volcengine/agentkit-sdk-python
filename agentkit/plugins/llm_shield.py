"""LLM Shield integration for AgentKit migration runtimes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

import requests
from google.adk.events import Event
from google.adk.plugins import BasePlugin
from google.genai import types
from volcengine.Credentials import Credentials as SigningCredentials
from volcengine.auth.SignerV4 import SignerV4
from volcengine.base.Request import Request as SigningRequest

from agentkit.platform.configuration import VolcConfiguration
from agentkit.utils.http_defaults import http_timeout

logger = logging.getLogger(__name__)

LLM_SHIELD_BLOCK_MESSAGE = (
    "Your request has been blocked by the security policy. "
    "Please modify it and try again."
)
LLM_SHIELD_UNAVAILABLE_MESSAGE = (
    "The security service is unavailable. Please try again later."
)

_ACTION = "Moderate"
_API_VERSION = "2025-08-31"
_DEFAULT_REGION = "cn-beijing"
_SERVICE = "llmshield"
_PATH = "/v2/moderate"
_INVOCATION_STATE_KEY = "__agentkit_llm_shield__"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"", "0", "false", "no", "off"})


class _Decision(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ERROR = "error"


@dataclass(frozen=True)
class _ModerationResult:
    decision: _Decision


class LLMShieldPlugin(BasePlugin):
    """Moderate AgentKit text boundaries with Volcengine LLM Shield.

    New applications opt in explicitly through :meth:`from_env`. Existing
    AgentKit applications are unchanged until they construct this plugin.
    """

    unavailable_message = LLM_SHIELD_UNAVAILABLE_MESSAGE

    def __init__(
        self,
        *,
        app_id: str,
        region: str = _DEFAULT_REGION,
        timeout: float | None = None,
        base_url: str | None = None,
        max_output_bytes: int = 256 * 1024,
    ) -> None:
        super().__init__(name="LLMShieldPlugin")
        if not app_id.strip():
            raise ValueError("LLM Shield app_id must not be empty")
        if not region.strip():
            raise ValueError("LLM Shield region must not be empty")
        if max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be greater than zero")

        self.app_id = app_id.strip()
        self.region = region.strip()
        self.timeout = timeout if timeout is not None else http_timeout()
        self.base_url = (
            base_url or f"https://{self.region}.sdk.access.llm-shield.omini-shield.com"
        ).rstrip("/")
        self.max_output_bytes = max_output_bytes
        self._configuration = VolcConfiguration(region=self.region)

    @classmethod
    def from_env(cls) -> LLMShieldPlugin | None:
        """Build the plugin from the migration runtime environment.

        Disabled and empty values return ``None`` without resolving credentials
        or constructing a client. Enabled configurations require only an App
        ID; request authentication uses AgentKit's AK/SK, STS, or Runtime IAM
        credential chain.
        """

        raw_enabled = os.getenv("ENABLE_LLM_SHIELD", "").strip().lower()
        if raw_enabled in _FALSE_VALUES:
            return None
        if raw_enabled not in _TRUE_VALUES:
            raise ValueError(
                "ENABLE_LLM_SHIELD must be one of 1/true/yes/on or 0/false/no/off"
            )

        app_id = os.getenv("TOOL_LLM_SHIELD_APP_ID", "").strip()
        if not app_id:
            raise ValueError(
                "TOOL_LLM_SHIELD_APP_ID is required when ENABLE_LLM_SHIELD=true"
            )

        region = os.getenv("TOOL_LLM_SHIELD_REGION", "").strip()
        region = region or _DEFAULT_REGION

        return cls(
            app_id=app_id,
            region=region,
        )

    async def moderate_text(
        self, text: str, *, role: Literal["user", "assistant"]
    ) -> str | None:
        """Return replacement text when content must not pass unchanged."""

        if not text:
            return None
        if role not in {"user", "assistant"}:
            raise ValueError("LLM Shield role must be 'user' or 'assistant'")
        if role == "assistant" and len(text.encode("utf-8")) > self.max_output_bytes:
            logger.warning("LLM Shield output exceeded the moderation size limit")
            return LLM_SHIELD_UNAVAILABLE_MESSAGE
        result = await asyncio.to_thread(self._moderate_sync, text, role)
        if result.decision is _Decision.ALLOW:
            return None
        if result.decision is _Decision.BLOCK:
            return LLM_SHIELD_BLOCK_MESSAGE
        return LLM_SHIELD_UNAVAILABLE_MESSAGE

    def _moderate_sync(
        self, text: str, role: Literal["user", "assistant"]
    ) -> _ModerationResult:
        body = json.dumps(
            {
                "Message": {
                    "Role": role,
                    "Content": text,
                    "ContentType": 1,
                },
                "Scene": self.app_id,
            },
            ensure_ascii=False,
        )
        try:
            headers = self._request_headers(body)
            response = requests.post(
                f"{self.base_url}{_PATH}",
                headers=headers,
                params={"Action": _ACTION, "Version": _API_VERSION},
                data=body,
                timeout=self.timeout,
            )
        except requests.Timeout:
            logger.warning("LLM Shield moderation request timed out")
            return _ModerationResult(_Decision.ERROR)
        except requests.RequestException:
            logger.warning("LLM Shield moderation network request failed")
            return _ModerationResult(_Decision.ERROR)
        except Exception:
            logger.warning("LLM Shield moderation authentication failed")
            return _ModerationResult(_Decision.ERROR)

        if response.status_code != 200:
            logger.warning(
                "LLM Shield moderation returned HTTP %s", response.status_code
            )
            return _ModerationResult(_Decision.ERROR)
        try:
            payload = response.json()
        except ValueError:
            logger.warning("LLM Shield moderation returned invalid JSON")
            return _ModerationResult(_Decision.ERROR)

        if not isinstance(payload, dict):
            logger.warning("LLM Shield moderation returned an invalid response")
            return _ModerationResult(_Decision.ERROR)
        result = payload.get("Result")
        decision = result.get("Decision") if isinstance(result, dict) else None
        decision_type = (
            decision.get("DecisionType") if isinstance(decision, dict) else None
        )
        try:
            normalized_decision = int(decision_type)
        except (TypeError, ValueError):
            normalized_decision = None
        if normalized_decision == 1:
            return _ModerationResult(_Decision.ALLOW)
        if normalized_decision == 2:
            return _ModerationResult(_Decision.BLOCK)
        logger.warning("LLM Shield moderation returned an unknown decision")
        return _ModerationResult(_Decision.ERROR)

    def _request_headers(self, body: str) -> dict[str, str]:
        credentials = self._configuration.get_service_credentials("llm_shield")
        host = self.base_url.split("://", 1)[-1].split("/", 1)[0]
        request = SigningRequest()
        request.set_schema("https")
        request.set_method("POST")
        request.set_host(host)
        request.set_path(_PATH)
        request.set_headers({"Content-Type": "application/json", "Host": host})
        request.set_query({"Action": _ACTION, "Version": _API_VERSION})
        request.set_body(body)
        SignerV4.sign(
            request,
            SigningCredentials(
                credentials.access_key,
                credentials.secret_key,
                _SERVICE,
                self.region,
                credentials.session_token or "",
            ),
        )
        request.headers.update({"X-Top-Service": _SERVICE, "X-Top-Region": self.region})
        return dict(request.headers)

    async def before_run_callback(self, *, invocation_context) -> types.Content | None:
        text = _content_text(getattr(invocation_context, "user_content", None))
        replacement = await self.moderate_text(text, role="user")
        if replacement is None:
            return None
        _invocation_state(invocation_context)["terminal"] = True
        return _model_content(replacement)

    async def before_tool_callback(
        self,
        *,
        tool: Any,
        tool_args: dict[str, Any],
        tool_context: Any,
    ) -> dict[str, Any] | None:
        del tool, tool_context
        text = _tool_payload_text(tool_args)
        if text is None:
            return {"result": LLM_SHIELD_UNAVAILABLE_MESSAGE}
        replacement = await self.moderate_text(text, role="user")
        return {"result": replacement} if replacement is not None else None

    async def after_tool_callback(
        self,
        *,
        tool: Any,
        tool_args: dict[str, Any],
        tool_context: Any,
        result: dict[str, Any],
    ) -> dict[str, Any] | None:
        del tool, tool_args, tool_context
        text = _tool_payload_text(result)
        if text is None:
            return {"result": LLM_SHIELD_UNAVAILABLE_MESSAGE}
        replacement = await self.moderate_text(text, role="assistant")
        return {"result": replacement} if replacement is not None else None

    async def on_event_callback(
        self, *, invocation_context, event: Event
    ) -> Event | None:
        state = _invocation_state(invocation_context)
        if state.get("terminal"):
            return event
        if getattr(event, "author", None) == "user":
            return event
        content = getattr(event, "content", None)
        if getattr(content, "role", None) == "user":
            return event
        text = _content_text(content)
        if getattr(event, "partial", None) is True:
            if text:
                buffered = _merge_stream_text(str(state.get("output", "")), text)
                if len(buffered.encode("utf-8")) > self.max_output_bytes:
                    state.pop("output", None)
                    state["overflowed"] = True
                else:
                    state["output"] = buffered
            return _replace_event_text(event, "") if text else event

        buffered = str(state.pop("output", ""))
        if state.pop("overflowed", False):
            return _replace_event_text(event, LLM_SHIELD_UNAVAILABLE_MESSAGE)
        final_text = _final_stream_text(buffered, text)
        if not final_text:
            return event
        replacement = await self.moderate_text(final_text, role="assistant")
        return _replace_event_text(event, replacement or final_text)

    async def after_run_callback(self, *, invocation_context) -> None:
        agent_states = getattr(invocation_context, "agent_states", None)
        if isinstance(agent_states, dict):
            agent_states.pop(_INVOCATION_STATE_KEY, None)


def _invocation_state(invocation_context: Any) -> dict[str, Any]:
    """Return state owned by this plugin for one ADK invocation."""

    agent_states = getattr(invocation_context, "agent_states", None)
    if not isinstance(agent_states, dict):
        agent_states = {}
        setattr(invocation_context, "agent_states", agent_states)
    state = agent_states.get(_INVOCATION_STATE_KEY)
    if not isinstance(state, dict):
        state = {}
        agent_states[_INVOCATION_STATE_KEY] = state
    return state


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    parts = getattr(content, "parts", None) or []
    texts = [str(part.text) for part in parts if getattr(part, "text", None)]
    return "\n".join(texts)


def _model_content(text: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part(text=text)])


def _tool_payload_text(value: Any) -> str | None:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
    except (TypeError, ValueError, RecursionError):
        logger.warning("LLM Shield could not serialize a tool payload")
        return None


def _merge_stream_text(buffered: str, text: str) -> str:
    if not buffered:
        return text
    if text.startswith(buffered):
        return text
    if buffered.endswith(text):
        return buffered
    return buffered + text


def _final_stream_text(buffered: str, final_text: str) -> str:
    if not final_text:
        return buffered
    if final_text.startswith(buffered) or buffered.endswith(final_text):
        return final_text if len(final_text) >= len(buffered) else buffered
    return final_text


def _replace_event_text(event: Event, text: str) -> Event:
    updated = event.model_copy(deep=True)
    content = getattr(updated, "content", None)
    if content is None:
        updated.content = _model_content(text)
        return updated

    replaced = False
    parts = []
    for part in content.parts or []:
        if getattr(part, "text", None) is not None:
            parts.append(part.model_copy(update={"text": text if not replaced else ""}))
            replaced = True
        else:
            parts.append(part)
    if not replaced:
        parts.insert(0, types.Part(text=text))
    updated.content = content.model_copy(update={"parts": parts})
    return updated

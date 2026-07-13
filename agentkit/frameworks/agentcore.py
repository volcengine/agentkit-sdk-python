"""Bedrock AgentCore Runtime adapters for AgentKit apps."""

from __future__ import annotations

import inspect
import json
from collections.abc import AsyncGenerator, Iterable
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from agentkit.frameworks._common import (
    UnsupportedFrameworkAgentError,
    adk_event,
    content_to_text,
    json_text,
    user_text,
)
from agentkit.frameworks.model_replacement import (
    ARK_DEFAULT_BASE_URL,
    apply_agentkit_model_replacement,
)


AGENTCORE_SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"
AGENTCORE_REQUEST_ID_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Request-Id"
AGENTCORE_WORKLOAD_ACCESS_TOKEN_HEADER = "WorkloadAccessToken"
AGENTCORE_AUTHORIZATION_HEADER = "Authorization"


class _AgentCoreEntry:
    def __init__(self, source: Any) -> None:
        self.source = source
        self.handler = _entrypoint_handler(source)

    async def invoke(self, payload: Any, context: Any) -> Any:
        args = (
            (payload, context)
            if _takes_context(self.handler)
            else (payload,)
        )
        result = self.handler(*args)
        if inspect.isawaitable(result):
            result = await result
        return result


def _entrypoint_handler(source: Any) -> Any:
    handlers = getattr(source, "handlers", None)
    if isinstance(handlers, dict) and callable(handlers.get("main")):
        return handlers["main"]
    if callable(source):
        return source
    raise UnsupportedFrameworkAgentError(
        "Bedrock AgentCore entry must be a BedrockAgentCoreApp with an "
        "@app.entrypoint handler, or a callable entrypoint function."
    )


def _takes_context(handler: Any) -> bool:
    try:
        params = list(inspect.signature(handler).parameters.values())
    except (TypeError, ValueError):
        return False
    if len(params) < 2:
        return False
    return params[1].name == "context"


def _parse_json_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _payload_from_adk_text(text: str) -> Any:
    parsed = _parse_json_text(text)
    if parsed is not None:
        return parsed
    return {"prompt": text}


def _session_id(ctx: InvocationContext) -> str | None:
    session = getattr(ctx, "session", None)
    value = getattr(session, "id", None)
    return str(value) if value else None


def _request_headers(
    *,
    request_id: str | None,
    session_id: str | None,
    source_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    headers = dict(source_headers or {})
    if request_id and not _has_header(headers, AGENTCORE_REQUEST_ID_HEADER):
        headers.setdefault(AGENTCORE_REQUEST_ID_HEADER, request_id)
    if session_id and not _has_header(headers, AGENTCORE_SESSION_HEADER):
        headers.setdefault(AGENTCORE_SESSION_HEADER, session_id)
    return headers


def _has_header(headers: dict[str, str], name: str) -> bool:
    wanted = name.lower()
    return any(key.lower() == wanted for key in headers)


def _get_header(headers: dict[str, str], name: str) -> str | None:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def _set_agentcore_context(
    *,
    request_id: str | None,
    session_id: str | None,
    headers: dict[str, str],
) -> None:
    try:
        from bedrock_agentcore.runtime.context import BedrockAgentCoreContext
    except Exception:
        return

    BedrockAgentCoreContext.set_request_context(request_id or str(uuid4()), session_id)
    if headers:
        BedrockAgentCoreContext.set_request_headers(headers)
    workload_token = _get_header(headers, AGENTCORE_WORKLOAD_ACCESS_TOKEN_HEADER)
    if workload_token:
        BedrockAgentCoreContext.set_workload_access_token(workload_token)


def _context_object(
    *,
    request_id: str | None,
    session_id: str | None,
    headers: dict[str, str],
    request: Request | None = None,
) -> Any:
    _set_agentcore_context(
        request_id=request_id,
        session_id=session_id,
        headers=headers,
    )
    try:
        from bedrock_agentcore.runtime.context import RequestContext

        return RequestContext(
            session_id=session_id,
            request_headers=headers or None,
            request=request,
        )
    except Exception:
        return SimpleNamespace(
            session_id=session_id,
            request_headers=headers or None,
            request=request,
        )


def _context_from_adk(ctx: InvocationContext) -> Any:
    session_id = _session_id(ctx)
    request_id = getattr(ctx, "invocation_id", None)
    headers = _request_headers(request_id=request_id, session_id=session_id)
    return _context_object(
        request_id=request_id,
        session_id=session_id,
        headers=headers,
    )


def _context_from_request(source: Any, request: Request) -> Any:
    build_context = getattr(source, "_build_request_context", None)
    if callable(build_context):
        return build_context(request)

    headers = dict(request.headers)
    session_id = request.headers.get(AGENTCORE_SESSION_HEADER)
    request_id = request.headers.get(AGENTCORE_REQUEST_ID_HEADER) or str(uuid4())
    return _context_object(
        request_id=request_id,
        session_id=session_id,
        headers=_request_headers(
            request_id=request_id,
            session_id=session_id,
            source_headers=headers,
        ),
        request=request,
    )


def _is_stream(value: Any) -> bool:
    return inspect.isasyncgen(value) or inspect.isgenerator(value)


def _response_text(response: Response) -> str:
    body = getattr(response, "body", b"")
    if isinstance(body, bytes):
        return body.decode("utf-8", errors="replace")
    return content_to_text(body)


def _agentcore_chunk_text(value: Any) -> str:
    if isinstance(value, Response):
        return _response_text(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        event_type = value.get("type")
        if event_type == "response.output_text.delta":
            return content_to_text(value.get("delta"))
        if event_type == "response.thinking":
            return ""
        if event_type == "response.failed":
            return content_to_text(value.get("message") or value.get("reason"))
        if isinstance(event_type, str) and event_type.startswith("response."):
            return ""
        for key in ("delta", "text", "content", "output", "answer", "message", "result"):
            if key in value:
                text = content_to_text(value[key])
                if text:
                    return text
        return json_text(value)
    return content_to_text(value)


async def _iterate_stream(value: Any) -> AsyncGenerator[Any, None]:
    if inspect.isasyncgen(value):
        async for item in value:
            yield item
        return
    if inspect.isgenerator(value):
        for item in value:
            yield item
        return
    yield value


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)


def _sse_bytes(value: Any) -> bytes:
    return f"data: {_safe_json(value)}\n\n".encode("utf-8")


async def _async_sse_stream(value: Any) -> AsyncGenerator[bytes, None]:
    try:
        async for item in _iterate_stream(value):
            yield _sse_bytes(item)
    except Exception as exc:
        yield _sse_bytes(
            {
                "error": str(exc),
                "error_type": type(exc).__name__,
                "message": "An error occurred during streaming",
            }
        )


def _json_response(value: Any) -> Response:
    if isinstance(value, Response):
        return value
    return Response(_safe_json(value), media_type="application/json")


class BedrockAgentCoreAgentkitBridge(BaseAgent):
    """Adapt a Bedrock AgentCore entrypoint to AgentKit's ADK runtime."""

    def __init__(
        self,
        source: Any,
        *,
        name: str = "bedrock_agentcore_agent",
        description: str = "Bedrock AgentCore entrypoint adapted for AgentKit runtime",
    ) -> None:
        super().__init__(name=name, description=description)
        self._entry = _AgentCoreEntry(source)

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        payload = _payload_from_adk_text(user_text(ctx))
        context = _context_from_adk(ctx)
        result = await self._entry.invoke(payload, context)
        accumulated = ""

        if _is_stream(result):
            async for item in _iterate_stream(result):
                text = _agentcore_chunk_text(item)
                if text:
                    accumulated += text
                    yield adk_event(ctx, self.name, text, partial=True)
        else:
            accumulated = _agentcore_chunk_text(result)

        if accumulated:
            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                branch=ctx.branch,
                partial=False,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=accumulated)],
                ),
            )


def _normalize_prefix(prefix: str) -> str:
    if prefix == "/":
        return ""
    if prefix and not prefix.startswith("/"):
        raise ValueError("AgentCore compatibility prefix must start with '/'.")
    return prefix.rstrip("/")


def _path(prefix: str, path: str) -> str:
    return f"{prefix}{path}" if prefix else path


def _promote_routes(app: FastAPI, paths: Iterable[str]) -> None:
    target_paths = set(paths)
    routes = app.router.routes
    promoted = []
    remaining = []
    for route in routes:
        if getattr(route, "path", None) in target_paths:
            promoted.append(route)
        else:
            remaining.append(route)

    insert_at = len(remaining)
    for index, route in enumerate(remaining):
        if getattr(route, "path", None) in {"", "/"}:
            insert_at = index
            break
    routes[:] = remaining[:insert_at] + promoted + remaining[insert_at:]


def attach_bedrock_agentcore_compat_routes(
    app: FastAPI,
    source: Any,
    *,
    prefix: str = "",
) -> None:
    """Attach Bedrock AgentCore-compatible /invocations and /ping routes."""

    normalized_prefix = _normalize_prefix(prefix)
    entry = _AgentCoreEntry(source)
    invocations_path = _path(normalized_prefix, "/invocations")
    ping_path = _path(normalized_prefix, "/ping")

    @app.post(invocations_path)
    async def _agentcore_invocations(request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="Request body must be valid JSON.",
            ) from exc

        task_response = None
        if isinstance(payload, dict):
            handle_task_action = getattr(source, "_handle_task_action", None)
            if callable(handle_task_action):
                task_response = handle_task_action(payload)
        if task_response is not None:
            return task_response

        context = _context_from_request(source, request)
        result = await entry.invoke(payload, context)
        if _is_stream(result):
            return StreamingResponse(
                _async_sse_stream(result),
                media_type="text/event-stream",
            )
        return _json_response(result)

    @app.get(ping_path)
    async def _agentcore_ping():
        get_status = getattr(source, "get_current_ping_status", None)
        if callable(get_status):
            status = get_status()
            return JSONResponse(
                {
                    "status": getattr(status, "value", status),
                    "time_of_last_update": int(
                        getattr(source, "_last_status_update_time", 0)
                    ),
                }
            )
        return JSONResponse({"status": "Healthy"})

    _promote_routes(app, [invocations_path, ping_path])

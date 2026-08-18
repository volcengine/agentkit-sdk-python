"""AgentKit protocol routes for LangGraph Server applications."""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import NAMESPACE_URL, uuid4, uuid5

import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from starlette.responses import Response
from starlette.routing import Mount
from typing_extensions import override

from agentkit.apps.base_app import BaseAgentkitApp

if TYPE_CHECKING:
    from agentkit.plugins.llm_shield import LLMShieldPlugin

logger = logging.getLogger(__name__)

_OUTPUT_FIELD_KEYS = ("answer", "output", "final", "response", "text", "messages")
_THREAD_ID_NAMESPACE = "agentkit:langgraph-server"


class AgentkitRunRequest(BaseModel):
    """Minimal AgentKit run request model for LangGraph Server mode."""

    model_config = ConfigDict(populate_by_name=True)

    app_name: str = Field(validation_alias=AliasChoices("appName", "app_name"))
    user_id: str = Field(validation_alias=AliasChoices("userId", "user_id"))
    session_id: str = Field(validation_alias=AliasChoices("sessionId", "session_id"))
    new_message: Any | None = Field(
        default=None,
        validation_alias=AliasChoices("newMessage", "new_message"),
    )
    streaming: bool | None = None
    state_delta: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("stateDelta", "state_delta"),
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"LangGraph config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"LangGraph config file is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError("LangGraph config must be a JSON object.")
    return data


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        from dotenv.main import DotEnv
    except ImportError:
        logger.warning("python-dotenv is not installed; skipping %s.", path)
        return {}
    values = DotEnv(dotenv_path=path).dict() or {}
    return {key: value for key, value in values.items() if value is not None}


def _set_env_json(name: str, value: Any) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = json.dumps(value)


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _content_value_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        for key in ("text", "content", "output", "answer"):
            if key in content:
                text = _content_value_to_text(content[key])
                if text:
                    return text
        return _json_text(content)
    if isinstance(content, list):
        return "".join(_content_value_to_text(item) for item in content)
    text = getattr(content, "text", None)
    if isinstance(text, str):
        return text
    return str(content)


def _chunk_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    content = getattr(value, "content", None)
    if content is not None:
        return _content_value_to_text(content)
    text = getattr(value, "text", None)
    if isinstance(text, str):
        return text
    if isinstance(value, dict):
        for key in ("output", "answer", "text", "content"):
            if key in value:
                text = _chunk_to_text(value[key])
                if text:
                    return text
        messages = value.get("messages")
        if isinstance(messages, (list, tuple)) and messages:
            return _chunk_to_text(messages[-1])
        for nested in value.values():
            text = _chunk_to_text(nested)
            if text:
                return text
        return _json_text(value)
    if isinstance(value, (list, tuple)):
        for item in reversed(value):
            text = _chunk_to_text(item)
            if text:
                return text
        return ""
    return str(value)


def _chunk_delta(accumulated: str, text: str) -> str:
    if not accumulated:
        return text
    if text.startswith(accumulated):
        return text[len(accumulated) :]
    return text


def _normalize_import_path(config_dir: Path, value: Any) -> Any:
    if not isinstance(value, str) or ":" not in value:
        return value
    path_or_module, variable = value.rsplit(":", 1)
    if not path_or_module or os.path.isabs(path_or_module):
        return value
    if "/" not in path_or_module and not path_or_module.endswith(".py"):
        return value
    return f"{(config_dir / path_or_module).resolve()}:{variable}"


def _normalize_path_config(config_dir: Path, value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    normalized = dict(value)
    if "path" in normalized:
        normalized["path"] = _normalize_import_path(config_dir, normalized["path"])
    if "app" in normalized:
        normalized["app"] = _normalize_import_path(config_dir, normalized["app"])
    return normalized


def _normalize_config_paths(config_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(config)
    graphs = config.get("graphs")
    if isinstance(graphs, dict):
        normalized_graphs: dict[str, Any] = {}
        for graph_id, graph_config in graphs.items():
            if isinstance(graph_config, str):
                normalized_graphs[graph_id] = _normalize_import_path(config_dir, graph_config)
            elif isinstance(graph_config, dict):
                normalized_graphs[graph_id] = _normalize_path_config(config_dir, graph_config)
            else:
                normalized_graphs[graph_id] = graph_config
        normalized["graphs"] = normalized_graphs
    for key in ("auth", "checkpointer", "http"):
        normalized[key] = _normalize_path_config(config_dir, config.get(key))
    return normalized


def _graph_source(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("path"), str):
        return value["path"]
    return None


def _materialize_lazy_graph_exports(graphs: Any) -> None:
    if not isinstance(graphs, dict):
        return
    for graph_config in graphs.values():
        source = _graph_source(graph_config)
        if not source or ":" not in source:
            continue
        module_name, variable = source.rsplit(":", 1)
        if "/" in module_name or module_name.endswith(".py"):
            continue
        try:
            module = importlib.import_module(module_name)
        except Exception:
            # This helper only makes lazy module exports visible to LangGraph's
            # loader. Import errors still belong to the official loader path.
            continue
        if variable in module.__dict__:
            continue
        try:
            module.__dict__[variable] = getattr(module, variable)
        except Exception:
            continue


def _extend_python_path(config_dir: Path, config: dict[str, Any]) -> None:
    candidates = [config_dir]
    dependencies = config.get("dependencies")
    if isinstance(dependencies, list):
        for dependency in dependencies:
            if not isinstance(dependency, str):
                continue
            dependency_path = (config_dir / dependency).resolve()
            if dependency_path.is_dir():
                candidates.append(dependency_path)
    for candidate in reversed(candidates):
        value = str(candidate)
        if value not in sys.path:
            sys.path.insert(0, value)


def _prepare_langgraph_environment(
    config_path: Path,
    config: dict[str, Any],
    *,
    allow_blocking: bool | None = None,
) -> None:
    config_dir = config_path.parent
    env_config = config.get("env")
    if isinstance(env_config, str):
        env_path = (config_dir / env_config).resolve()
        for key, value in _load_dotenv(env_path).items():
            os.environ.setdefault(key, value)
    elif isinstance(env_config, dict):
        for key, value in env_config.items():
            if isinstance(key, str) and value is not None:
                os.environ.setdefault(key, str(value))

    os.environ["LANGSERVE_GRAPHS"] = json.dumps(config.get("graphs", {}))
    _set_env_json("LANGGRAPH_AUTH", config.get("auth"))
    _set_env_json("LANGGRAPH_HTTP", config.get("http"))
    _set_env_json("LANGGRAPH_STORE", config.get("store"))
    _set_env_json("LANGGRAPH_UI", config.get("ui"))
    _set_env_json("LANGGRAPH_WEBHOOKS", config.get("webhooks"))
    _set_env_json("LANGGRAPH_UI_CONFIG", config.get("ui_config"))
    _set_env_json("LANGGRAPH_CHECKPOINTER", config.get("checkpointer"))
    os.environ.setdefault("DATABASE_URI", ":memory:")
    os.environ.setdefault("REDIS_URI", "fake")
    os.environ.setdefault("MIGRATIONS_PATH", "__inmem")
    os.environ.setdefault("N_JOBS_PER_WORKER", "1")
    os.environ.setdefault("LANGSMITH_LANGGRAPH_API_VARIANT", "local_dev")
    os.environ.setdefault("LANGGRAPH_RUNTIME_EDITION", "inmem")
    os.environ.setdefault("LANGGRAPH_API_URL", os.environ.get("AGENTKIT_BASE_URL", "http://localhost:8000"))
    os.environ.setdefault("LANGGRAPH_DISABLE_FILE_PERSISTENCE", "false")
    if allow_blocking is None:
        os.environ.setdefault("LANGGRAPH_ALLOW_BLOCKING", "false")
    else:
        os.environ["LANGGRAPH_ALLOW_BLOCKING"] = str(allow_blocking).lower()
    os.environ.setdefault("ALLOW_PRIVATE_NETWORK", "true")


def _resolve_graph_id(config: dict[str, Any], graph_id: str | None) -> str:
    graphs = config.get("graphs")
    if not isinstance(graphs, dict) or not graphs:
        raise ValueError("LangGraph config must define at least one graph.")
    if graph_id:
        if graph_id not in graphs:
            raise ValueError(f"Graph id {graph_id!r} was not found in langgraph.json.")
        return graph_id
    if len(graphs) > 1:
        choices = ", ".join(str(key) for key in graphs)
        raise ValueError(f"Multiple LangGraph graphs found; specify graph_id. Available: {choices}.")
    return next(iter(graphs))


def _content_text(content: Any | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        parts = content.get("parts") or []
        if not parts and isinstance(content.get("text"), str):
            return content["text"]
        if not parts and isinstance(content.get("content"), str):
            return content["content"]
    else:
        parts = getattr(content, "parts", None) or []
    texts: list[str] = []
    for part in parts:
        text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
        if text:
            texts.append(str(text))
    return "\n".join(texts)


def _input_payload(text: str, input_key: str | None) -> dict[str, Any]:
    if input_key:
        return {input_key: text}
    return {"messages": [{"role": "user", "content": text}]}


def _update_output_text(data: Any) -> str:
    if not isinstance(data, dict):
        return _chunk_to_text(data)
    for key in _OUTPUT_FIELD_KEYS:
        if key in data:
            text = _stream_message_text(data[key]) if key == "messages" else _chunk_to_text(data[key])
            if text:
                return text
    latest = ""
    for value in data.values():
        if not isinstance(value, dict):
            continue
        for key in _OUTPUT_FIELD_KEYS:
            if key in value:
                text = _stream_message_text(value[key]) if key == "messages" else _chunk_to_text(value[key])
                if text:
                    latest = text
    return latest


def _stream_chunk(chunk: Any) -> tuple[str, Any]:
    if isinstance(chunk, dict):
        return str(chunk.get("type") or chunk.get("event") or ""), chunk.get("data")
    event = getattr(chunk, "event", "")
    data = getattr(chunk, "data", None)
    return str(event or ""), data


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except Exception:
        return str(value)


def _interrupt_payload(data: Any) -> Any | None:
    if not isinstance(data, dict):
        return None
    if "__interrupt__" in data:
        interrupts = data.get("__interrupt__")
        if not isinstance(interrupts, (list, tuple)) or not interrupts:
            return _jsonable(interrupts)
        values: list[dict[str, Any]] = []
        for interrupt in interrupts:
            values.append(
                {
                    "id": getattr(interrupt, "id", None),
                    "value": _jsonable(getattr(interrupt, "value", interrupt)),
                }
            )
        return values
    for value in data.values():
        interrupt = _interrupt_payload(value)
        if interrupt is not None:
            return interrupt
    return None


def _message_type(value: Any) -> str:
    if isinstance(value, dict):
        raw = value.get("type") or value.get("role") or ""
    else:
        raw = getattr(value, "type", None) or getattr(value, "role", None) or value.__class__.__name__
    return str(raw).lower()


def _is_ai_message(value: Any) -> bool:
    message_type = _message_type(value)
    return message_type in {"ai", "assistant", "model", "aimessage", "aimessagechunk"}


def _is_empty_message_content(value: Any) -> bool:
    if isinstance(value, dict):
        content = value.get("content")
        has_text = isinstance(value.get("text"), str) and bool(value.get("text"))
    else:
        content = getattr(value, "content", None)
        has_text = isinstance(getattr(value, "text", None), str) and bool(getattr(value, "text", None))
    return not has_text and (content is None or content == "" or content == {} or content == [])


def _message_candidates(data: Any) -> list[Any]:
    if isinstance(data, dict):
        messages = data.get("messages")
        if isinstance(messages, (list, tuple)):
            return list(messages)
        return [data]
    if isinstance(data, (list, tuple)):
        return list(data)
    return [data]


def _stream_message_text(data: Any) -> str:
    latest = ""
    for candidate in _message_candidates(data):
        if _is_ai_message(candidate) and not _is_empty_message_content(candidate):
            text = _chunk_to_text(candidate)
            if text:
                latest = text
    return latest


def _agentkit_text_event(agent_name: str, text: str, *, partial: bool) -> dict[str, Any]:
    return {
        "invocationId": f"agentkit-langgraph-{uuid4()}",
        "author": agent_name,
        "partial": partial,
        "content": {"role": "model", "parts": [{"text": text}]},
    }


def _interrupt_event(agent_name: str, interrupt: Any) -> dict[str, Any]:
    return {
        "invocationId": f"agentkit-langgraph-{uuid4()}",
        "author": agent_name,
        "interrupted": True,
        "errorCode": "LANGGRAPH_INTERRUPT",
        "errorMessage": "LangGraph execution interrupted and requires resume input.",
        "customMetadata": {"langgraph_interrupt": interrupt},
    }


def _event_json(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, separators=(",", ":"))


def _agentkit_thread_id(app_name: str, user_id: str, session_id: str) -> str:
    raw = f"{_THREAD_ID_NAMESPACE}:{app_name}:{user_id}:{session_id}"
    return str(uuid5(NAMESPACE_URL, raw))


def _session_body(app_name: str, user_id: str, session_id: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": session_id,
        "appName": app_name,
        "userId": user_id,
        "state": state or {},
        "events": [],
    }


async def _json_body_or_empty(request: Request) -> dict[str, Any]:
    body = await request.body()
    if not body:
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


class AgentkitLangGraphServerApp(BaseAgentkitApp):
    """Run a LangGraph Server app and expose AgentKit-compatible routes.

    LangGraph remains the execution runtime. AgentKit routes translate requests
    into LangGraph threads/runs so persistence, interrupts, runtime context, and
    graph factories keep their original LangGraph Server semantics.
    """

    def __init__(
        self,
        *,
        config_path: str | Path = "langgraph.json",
        graph_id: str | None = None,
        input_key: str | None = None,
        allow_blocking: bool | None = None,
        llm_shield: LLMShieldPlugin | None = None,
    ) -> None:
        super().__init__()
        self.config_path = Path(config_path).resolve()
        raw_config = _load_json(self.config_path)
        self.config = _normalize_config_paths(self.config_path.parent, raw_config)
        self.graph_id = _resolve_graph_id(self.config, graph_id)
        self.input_key = input_key
        self.llm_shield = llm_shield
        _extend_python_path(self.config_path.parent, self.config)
        _prepare_langgraph_environment(self.config_path, self.config, allow_blocking=allow_blocking)
        _materialize_lazy_graph_exports(self.config.get("graphs"))
        try:
            server_module = importlib.import_module("langgraph_api.server")
            from langgraph_sdk import get_client
        except ImportError as exc:
            raise ImportError(
                "LangGraph server mode requires langgraph-api and langgraph-sdk. "
                "Install langgraph-cli[inmem] or use the requirements generated by agentkit migrate."
            ) from exc
        self.app = server_module.app
        self._client = get_client(url=None, api_key=None)
        self._attach_agentkit_routes()

    def _run_kwargs(self, req: AgentkitRunRequest) -> dict[str, Any]:
        app_name = req.app_name or self.graph_id
        thread_id = _agentkit_thread_id(app_name, req.user_id, req.session_id)
        text = _content_text(req.new_message)
        configurable = {
            "thread_id": thread_id,
            "user_id": req.user_id,
            "agentkit_session_id": req.session_id,
            "agentkit_thread_id": thread_id,
        }
        if req.state_delta:
            configurable.update(req.state_delta)
        return {
            "thread_id": thread_id,
            "assistant_id": self.graph_id,
            "input": _input_payload(text, self.input_key),
            "config": {"configurable": configurable},
            "metadata": {
                "agentkit_user_id": req.user_id,
                "agentkit_session_id": req.session_id,
                "agentkit_app_name": req.app_name or self.graph_id,
            },
            "if_not_exists": "create",
        }

    async def _ensure_thread(self, app_name: str, user_id: str, session_id: str, state: dict[str, Any] | None = None) -> None:
        thread_id = _agentkit_thread_id(app_name, user_id, session_id)
        metadata = {
            "agentkit_app_name": app_name,
            "agentkit_user_id": user_id,
            "agentkit_session_id": session_id,
            **(state or {}),
        }
        await self._client.threads.create(
            thread_id=thread_id,
            if_exists="do_nothing",
            graph_id=self.graph_id,
            metadata=metadata,
        )

    async def _stream_events(self, req: AgentkitRunRequest):
        input_text = _content_text(req.new_message)
        if self.llm_shield is not None:
            replacement = await self.llm_shield.moderate_text(input_text, role="user")
            if replacement is not None:
                yield _agentkit_text_event(self.graph_id, replacement, partial=False)
                return
        await self._ensure_thread(req.app_name or self.graph_id, req.user_id, req.session_id)
        accumulated_text = ""
        final_text = ""
        try:
            async for chunk in self._client.runs.stream(
                **self._run_kwargs(req),
                stream_mode=["messages", "updates", "values"],
                version="v2",
            ):
                mode, data = _stream_chunk(chunk)
                if mode == "messages" or mode.startswith("messages/"):
                    text = _stream_message_text(data)
                    delta = _chunk_delta(accumulated_text, text)
                    if delta:
                        buffered_text = accumulated_text + delta
                        if (
                            self.llm_shield is not None
                            and len(buffered_text.encode("utf-8")) > self.llm_shield.max_output_bytes
                        ):
                            yield _agentkit_text_event(
                                self.graph_id,
                                self.llm_shield.unavailable_message,
                                partial=False,
                            )
                            return
                        accumulated_text = buffered_text
                        if self.llm_shield is None:
                            yield _agentkit_text_event(self.graph_id, delta, partial=True)
                    if text:
                        final_text = text
                    continue
                if mode in {"updates", "values"}:
                    interrupt = _interrupt_payload(data)
                    if interrupt is not None:
                        yield _interrupt_event(self.graph_id, interrupt)
                        return
                    text = _update_output_text(data)
                    if text:
                        if (
                            self.llm_shield is not None
                            and len(text.encode("utf-8")) > self.llm_shield.max_output_bytes
                        ):
                            yield _agentkit_text_event(
                                self.graph_id,
                                self.llm_shield.unavailable_message,
                                partial=False,
                            )
                            return
                        final_text = text
        except Exception as exc:
            if self.llm_shield is None:
                raise
            logger.warning(
                "LangGraph Server stream failed while LLM Shield was enabled (%s)",
                type(exc).__name__,
            )
            yield _agentkit_text_event(
                self.graph_id,
                self.llm_shield.unavailable_message,
                partial=False,
            )
            return
        final_text = final_text or accumulated_text
        if final_text:
            if self.llm_shield is not None:
                replacement = await self.llm_shield.moderate_text(final_text, role="assistant")
                final_text = replacement or final_text
            yield _agentkit_text_event(self.graph_id, final_text, partial=False)

    def _attach_agentkit_routes(self) -> None:
        async def health(request: Request) -> JSONResponse:
            del request
            return JSONResponse({"status": "ok"})

        async def list_apps(request: Request) -> JSONResponse:
            detailed = request.query_params.get("detailed") == "true"
            if detailed:
                return JSONResponse(
                    {
                        "apps": [
                            {
                                "name": self.graph_id,
                                "root_agent_name": self.graph_id,
                                "description": "LangGraph Server app exposed through AgentKit routes",
                                "language": "python",
                            }
                        ]
                    }
                )
            return JSONResponse([self.graph_id])

        async def get_session(request: Request) -> JSONResponse:
            session_id = request.path_params["session_id"]
            app_name = request.path_params["app_name"]
            user_id = request.path_params["user_id"]
            thread_id = _agentkit_thread_id(app_name, user_id, session_id)
            response = await self._client.threads.get(thread_id)
            metadata = response.get("metadata", {}) if isinstance(response, dict) else {}
            return JSONResponse(_session_body(app_name, user_id, session_id, metadata))

        async def list_sessions(request: Request) -> JSONResponse:
            app_name = request.path_params["app_name"]
            user_id = request.path_params["user_id"]
            response = await self._client.threads.search(
                metadata={"agentkit_app_name": app_name, "agentkit_user_id": user_id},
                limit=100,
            )
            sessions = [
                _session_body(
                    app_name,
                    user_id,
                    item.get("metadata", {}).get("agentkit_session_id", item.get("thread_id", "")),
                    item.get("metadata", {}),
                )
                for item in response
                if isinstance(item, dict) and item.get("thread_id")
            ]
            return JSONResponse(sessions)

        async def create_session(request: Request) -> JSONResponse:
            app_name = request.path_params["app_name"]
            user_id = request.path_params["user_id"]
            payload = await _json_body_or_empty(request)
            session_id = str(payload.get("sessionId") or payload.get("session_id") or uuid4())
            state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
            await self._ensure_thread(app_name, user_id, session_id, state)
            return JSONResponse(_session_body(app_name, user_id, session_id, state))

        async def create_session_with_id(request: Request) -> JSONResponse:
            app_name = request.path_params["app_name"]
            user_id = request.path_params["user_id"]
            session_id = request.path_params["session_id"]
            payload = await _json_body_or_empty(request)
            state = payload
            await self._ensure_thread(app_name, user_id, session_id, state)
            return JSONResponse(_session_body(app_name, user_id, session_id, state))

        async def delete_session(request: Request) -> Response:
            thread_id = _agentkit_thread_id(
                request.path_params["app_name"],
                request.path_params["user_id"],
                request.path_params["session_id"],
            )
            await self._client.threads.delete(thread_id)
            return Response(status_code=204)

        async def update_session(request: Request) -> JSONResponse:
            app_name = request.path_params["app_name"]
            user_id = request.path_params["user_id"]
            session_id = request.path_params["session_id"]
            payload = await _json_body_or_empty(request)
            state_delta = payload.get("stateDelta") or payload.get("state_delta")
            state = state_delta if isinstance(state_delta, dict) else {}
            thread_id = _agentkit_thread_id(app_name, user_id, session_id)
            await self._client.threads.update(thread_id, metadata=state)
            return JSONResponse(_session_body(app_name, user_id, session_id, state))

        async def run_agent(request: Request) -> JSONResponse:
            req = AgentkitRunRequest.model_validate(await request.json())
            events = [event async for event in self._stream_events(req)]
            return JSONResponse(events)

        def stream_response(req: AgentkitRunRequest) -> StreamingResponse:
            async def event_generator():
                try:
                    async for event in self._stream_events(req):
                        yield f"data: {_event_json(event)}\n\n"
                except Exception as exc:
                    logger.exception("Error in LangGraph Server AgentKit stream: %s", exc)
                    yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        async def run_agent_sse(request: Request) -> StreamingResponse:
            req = AgentkitRunRequest.model_validate(await request.json())
            return stream_response(req)

        async def invoke_compat(request: Request) -> StreamingResponse:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            prompt = payload.get("prompt") if isinstance(payload, dict) else None
            if prompt is None:
                prompt = json.dumps(payload, ensure_ascii=False) if payload else ""
            user_id = request.headers.get("user_id") or "agentkit_user"
            session_id = request.headers.get("session_id") or str(uuid4())
            req = AgentkitRunRequest(
                app_name=self.graph_id,
                user_id=user_id,
                session_id=session_id,
                new_message={"role": "user", "parts": [{"text": str(prompt)}]},
                streaming=True,
            )
            return stream_response(req)

        routes = [
            ("/health", health, ["GET"]),
            ("/list-apps", list_apps, ["GET"]),
            ("/apps/{app_name}/users/{user_id}/sessions/{session_id}", get_session, ["GET"]),
            ("/apps/{app_name}/users/{user_id}/sessions", list_sessions, ["GET"]),
            ("/apps/{app_name}/users/{user_id}/sessions", create_session, ["POST"]),
            ("/apps/{app_name}/users/{user_id}/sessions/{session_id}", create_session_with_id, ["POST"]),
            ("/apps/{app_name}/users/{user_id}/sessions/{session_id}", delete_session, ["DELETE"]),
            ("/apps/{app_name}/users/{user_id}/sessions/{session_id}", update_session, ["PATCH"]),
            ("/run", run_agent, ["POST"]),
            ("/run_sse", run_agent_sse, ["POST"]),
            ("/invoke", invoke_compat, ["POST"]),
        ]
        existing = {
            (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", ()) or ())))
            for route in getattr(self.app, "routes", [])
        }
        for path, endpoint, methods in routes:
            key = (path, tuple(sorted(methods)))
            if key not in existing:
                self.app.add_route(path, endpoint, methods=methods)
                route = self.app.routes.pop()
                insert_at = next(
                    (
                        index
                        for index, existing_route in enumerate(self.app.routes)
                        if isinstance(existing_route, Mount)
                        and getattr(existing_route, "path", None) == ""
                    ),
                    len(self.app.routes),
                )
                self.app.routes.insert(insert_at, route)

    @override
    def run(self, host: str | None = None, port: int = 8000) -> None:
        uvicorn.run(self.app, host=host or "0.0.0.0", port=port)

from __future__ import annotations

import os
import subprocess
import sys
import types as py_types
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import types
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.testclient import TestClient

from agentkit.apps.langgraph_server_app.langgraph_server_app import (
    AgentkitLangGraphServerApp,
    _agentkit_thread_id,
    _chunk_delta,
    _chunk_to_text,
    _content_value_to_text,
    _content_text,
    _input_payload,
    _interrupt_payload,
    _json_text,
    _load_dotenv,
    _load_json,
    _message_candidates,
    _materialize_lazy_graph_exports,
    _normalize_config_paths,
    _normalize_import_path,
    _resolve_graph_id,
    _stream_chunk,
    _stream_message_text,
    _update_output_text,
)
from agentkit.plugins.llm_shield import (
    LLM_SHIELD_BLOCK_MESSAGE,
    LLM_SHIELD_UNAVAILABLE_MESSAGE,
)


class _FakeThreads:
    def __init__(self):
        self.created = []
        self.updated = []
        self.deleted = []
        self.got = []

    async def create(self, **kwargs):
        self.created.append(kwargs)
        return {"thread_id": kwargs["thread_id"], "metadata": kwargs.get("metadata", {})}

    async def get(self, thread_id):
        self.got.append(thread_id)
        return {"thread_id": thread_id, "metadata": {"existing": True}}

    async def search(self, **kwargs):
        return [
            {
                "thread_id": "session-1",
                "metadata": {
                    **kwargs["metadata"],
                    "agentkit_session_id": "session-1",
                },
            }
        ]

    async def update(self, thread_id, **kwargs):
        self.updated.append((thread_id, kwargs))
        return {"thread_id": thread_id, "metadata": kwargs.get("metadata", {})}

    async def delete(self, thread_id):
        self.deleted.append(thread_id)


class _FakeRuns:
    def __init__(self):
        self.calls = []

    async def stream(self, **kwargs):
        self.calls.append(kwargs)
        yield {"type": "messages", "data": [{"type": "ai", "content": "hel"}]}
        yield {"type": "messages", "data": [{"type": "ai", "content": "hello"}]}
        yield {"type": "values", "data": {"messages": [{"type": "ai", "content": "final answer"}]}}


class _ServerStyleRuns:
    def __init__(self):
        self.calls = []

    async def stream(self, **kwargs):
        self.calls.append(kwargs)
        yield {"type": "messages/metadata", "data": {"run": {"metadata": {"node": "model"}}}}
        yield {"type": "messages/complete", "data": [{"type": "human", "content": "hello"}]}
        yield {"type": "messages/partial", "data": [{"type": "ai", "content": {}}]}
        yield {"type": "messages/partial", "data": [{"type": "ai", "content": "Hel"}]}
        yield {"type": "messages/partial", "data": [{"type": "ai", "content": "Hello"}]}
        yield {"type": "messages/partial", "data": [{"type": "ai", "content": "Hello"}]}


class _HumanOnlyValuesRuns:
    def __init__(self):
        self.calls = []

    async def stream(self, **kwargs):
        self.calls.append(kwargs)
        yield {"type": "values", "data": {"messages": [{"type": "human", "content": "hello"}]}}


class _InterruptRuns:
    def __init__(self):
        self.calls = []

    async def stream(self, **kwargs):
        self.calls.append(kwargs)
        yield {
            "type": "updates",
            "data": {
                "review": {
                    "__interrupt__": [
                        {
                            "value": {
                                "question": "Approve deployment?",
                                "options": ["yes", "no"],
                            }
                        }
                    ]
                }
            },
        }


class _FailingRuns:
    async def stream(self, **kwargs):
        del kwargs
        raise RuntimeError("stream boom")
        yield


class _OversizedRuns:
    async def stream(self, **kwargs):
        del kwargs
        yield {"type": "messages", "data": [{"type": "ai", "content": "four"}]}


class _FakeClient:
    def __init__(self):
        self.threads = _FakeThreads()
        self.runs = _FakeRuns()


class _FakeShield:
    unavailable_message = LLM_SHIELD_UNAVAILABLE_MESSAGE

    def __init__(
        self,
        *,
        blocked_role: str | None = None,
        unavailable=False,
        max_output_bytes: int = 256 * 1024,
    ):
        self.blocked_role = blocked_role
        self.unavailable = unavailable
        self.max_output_bytes = max_output_bytes
        self.calls = []

    async def moderate_text(self, text: str, *, role: str):
        self.calls.append((text, role))
        if self.unavailable:
            return LLM_SHIELD_UNAVAILABLE_MESSAGE
        if role == self.blocked_role:
            return LLM_SHIELD_BLOCK_MESSAGE
        return None


def _install_fake_langgraph(monkeypatch, fake_client: _FakeClient):
    async def ok(request):
        del request
        return JSONResponse({"ok": True})

    async def native_threads(request):
        del request
        return JSONResponse({"native": "threads"})

    native_app = Starlette(routes=[Route("/threads", native_threads, methods=["POST"])])
    app = Starlette(routes=[Route("/ok", ok, methods=["GET"]), Mount("", app=native_app)])
    server_module = py_types.ModuleType("langgraph_api.server")
    server_module.app = app
    package_module = py_types.ModuleType("langgraph_api")
    package_module.server = server_module
    sdk_module = py_types.ModuleType("langgraph_sdk")
    sdk_module.get_client = lambda url=None, api_key=None: fake_client
    monkeypatch.setitem(sys.modules, "langgraph_api", package_module)
    monkeypatch.setitem(sys.modules, "langgraph_api.server", server_module)
    monkeypatch.setitem(sys.modules, "langgraph_sdk", sdk_module)
    return app


def _write_config(tmp_path: Path, body: str | None = None) -> Path:
    config = tmp_path / "langgraph.json"
    config.write_text(
        body
        or '{"graphs": {"lead_agent": "pkg.agent:make_graph"}, "env": {"FROM_CONFIG": "yes"}}',
        encoding="utf-8",
    )
    return config


def test_config_loader_reports_missing_invalid_and_non_object_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="LangGraph config file not found"):
        _load_json(tmp_path / "missing.json")

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        _load_json(invalid)

    non_object = tmp_path / "array.json"
    non_object.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        _load_json(non_object)


def test_langgraph_server_module_import_does_not_require_google_adk():
    script = (
        "import sys;"
        "sys.modules['google.adk'] = None;"
        "import agentkit.apps.langgraph_server_app.langgraph_server_app"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_helper_functions_cover_path_and_payload_boundaries(tmp_path):
    assert _load_dotenv(tmp_path / "missing.env") == {}
    assert _normalize_import_path(tmp_path, 123) == 123
    assert _normalize_import_path(tmp_path, "pkg.graph:graph") == "pkg.graph:graph"
    assert _normalize_import_path(tmp_path, "/abs/graph.py:graph") == "/abs/graph.py:graph"
    assert _normalize_import_path(tmp_path, "./graph.py:graph") == f"{tmp_path / 'graph.py'}:graph"
    normalized = _normalize_config_paths(
        tmp_path,
        {
            "graphs": {
                "dict_graph": {"path": "./dict_graph.py:graph", "description": "demo"},
                "bad_graph": 1,
            }
        },
    )
    assert normalized["graphs"]["dict_graph"]["path"] == f"{tmp_path / 'dict_graph.py'}:graph"
    assert normalized["graphs"]["bad_graph"] == 1
    assert _resolve_graph_id({"graphs": {"one": "pkg:graph"}}, None) == "one"
    assert _resolve_graph_id({"graphs": {"one": "pkg:graph"}}, "one") == "one"
    with pytest.raises(ValueError, match="at least one graph"):
        _resolve_graph_id({"graphs": {}}, None)
    with pytest.raises(ValueError, match="was not found"):
        _resolve_graph_id({"graphs": {"one": "pkg:graph"}}, "two")
    assert _content_text(None) == ""
    assert _content_text("plain input") == "plain input"
    assert _content_text({"text": "dict text"}) == "dict text"
    assert _content_text({"content": "dict content"}) == "dict content"
    assert (
        _content_text(SimpleNamespace(parts=[SimpleNamespace(text="object part")]))
        == "object part"
    )
    assert _input_payload("hello", "question") == {"question": "hello"}
    assert _update_output_text("plain") == "plain"
    assert _update_output_text({"node": {"answer": "nested"}}) == "nested"
    assert _stream_chunk(SimpleNamespace(event="values", data={"answer": "ok"})) == (
        "values",
        {"answer": "ok"},
    )


def test_text_extraction_helpers_cover_supported_chunk_shapes():
    circular: list = []
    circular.append(circular)

    assert _json_text(circular) == "[[...]]"
    assert _content_value_to_text(None) == ""
    assert _content_value_to_text("plain") == "plain"
    assert _content_value_to_text({"content": {"text": "nested"}}) == "nested"
    assert _content_value_to_text({"unknown": "value"}) == '{"unknown": "value"}'
    assert _content_value_to_text(["a", {"text": "b"}]) == "ab"
    assert _content_value_to_text(SimpleNamespace(text="object text")) == "object text"
    assert _content_value_to_text(123) == "123"

    assert _chunk_to_text(None) == ""
    assert _chunk_to_text("chunk") == "chunk"
    assert _chunk_to_text(SimpleNamespace(content={"answer": "from content"})) == "from content"
    assert _chunk_to_text(SimpleNamespace(text="from text")) == "from text"
    assert _chunk_to_text({"messages": [{"content": "first"}, {"content": "last"}]}) == "last"
    assert _chunk_to_text({"outer": {"answer": "nested answer"}}) == "nested answer"
    assert _chunk_to_text({"empty": ""}) == '{"empty": ""}'
    assert _chunk_to_text([None, {"answer": "list answer"}]) == "list answer"
    assert _chunk_to_text([None, ""]) == ""
    assert _chunk_to_text(42) == "42"

    assert _chunk_delta("", "hello") == "hello"
    assert _chunk_delta("hel", "hello") == "lo"
    assert _chunk_delta("hello", "token") == "token"

    assert _interrupt_payload("not dict") is None
    assert _interrupt_payload({"__interrupt__": []}) == []
    assert _interrupt_payload(
        {"__interrupt__": [SimpleNamespace(id="circular", value=circular)]}
    ) == [
        {"id": "circular", "value": "[[...]]"}
    ]
    assert _message_candidates({"messages": ("a", "b")}) == ["a", "b"]
    assert _message_candidates(("a", "b")) == ["a", "b"]
    assert _message_candidates("one") == ["one"]
    assert (
        _stream_message_text([SimpleNamespace(type="ai", content="object ai")])
        == "object ai"
    )


def test_materialize_lazy_graph_exports_supports_module_getattr(monkeypatch):
    module = py_types.ModuleType("lazy_graph_module")

    def __getattr__(name):
        if name == "make_graph":
            return "graph-factory"
        raise AttributeError(name)

    module.__getattr__ = __getattr__
    monkeypatch.setitem(sys.modules, "lazy_graph_module", module)

    _materialize_lazy_graph_exports({"lead": "lazy_graph_module:make_graph"})

    assert module.__dict__["make_graph"] == "graph-factory"


def test_materialize_lazy_graph_exports_ignores_file_paths_and_missing_attrs(monkeypatch):
    module = py_types.ModuleType("empty_graph_module")
    module.existing_graph = object()
    monkeypatch.setitem(sys.modules, "empty_graph_module", module)

    _materialize_lazy_graph_exports("not-a-dict")
    _materialize_lazy_graph_exports(
        {
            "file": "./graph.py:make_graph",
            "no_colon": "empty_graph_module",
            "already_present": "empty_graph_module:existing_graph",
            "dict_without_path": {"description": "demo"},
            "missing": {"path": "empty_graph_module:missing_graph"},
            "missing_module": "missing_graph_module:make_graph",
        }
    )

    assert "missing_graph" not in module.__dict__


def test_dotenv_loader_skips_existing_env_file_when_dotenv_is_missing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FROM_DOTENV=loaded\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "dotenv.main", None)

    assert _load_dotenv(env_file) == {}


def test_langgraph_server_app_prepares_env_and_mounts_agentkit_routes(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    config = _write_config(tmp_path)

    server = AgentkitLangGraphServerApp(config_path=config)

    paths = {getattr(route, "path", "") for route in server.app.routes}
    assert "/run" in paths
    assert "/run_sse" in paths
    assert "/invoke" in paths
    assert "/apps/{app_name}/users/{user_id}/sessions/{session_id}" in paths
    assert server.graph_id == "lead_agent"


def test_langgraph_server_app_can_enable_official_blocking_override(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    monkeypatch.delenv("LANGGRAPH_ALLOW_BLOCKING", raising=False)

    AgentkitLangGraphServerApp(config_path=_write_config(tmp_path), allow_blocking=True)

    assert os.environ["LANGGRAPH_ALLOW_BLOCKING"] == "true"


def test_langgraph_server_app_preserves_existing_blocking_env_by_default(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    monkeypatch.setenv("LANGGRAPH_ALLOW_BLOCKING", "true")

    AgentkitLangGraphServerApp(config_path=_write_config(tmp_path))

    assert os.environ["LANGGRAPH_ALLOW_BLOCKING"] == "true"


def test_langgraph_server_app_loads_env_file_and_python_path(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    (tmp_path / "deps").mkdir()
    (tmp_path / ".env").write_text("FROM_DOTENV=loaded\nEMPTY=\n", encoding="utf-8")
    config = _write_config(
        tmp_path,
        '{"dependencies": ["deps", 1], "graphs": {"lead_agent": "pkg.agent:make_graph"}, "env": ".env"}',
    )
    monkeypatch.delenv("FROM_DOTENV", raising=False)

    AgentkitLangGraphServerApp(config_path=config)

    assert os.environ["FROM_DOTENV"] == "loaded"
    assert str(tmp_path / "deps") in sys.path


def test_langgraph_server_app_normalizes_relative_config_paths(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    (tmp_path / "pkg").mkdir()
    config = _write_config(
        tmp_path,
        '{"dependencies": ["."], "graphs": {"lead_agent": "./pkg/graph.py:graph"}, '
        '"auth": {"path": "./auth.py:auth"}, '
        '"http": {"app": "./api.py:app"}, '
        '"checkpointer": {"path": "./checkpointer.py:make_checkpointer"}}',
    )

    server = AgentkitLangGraphServerApp(config_path=config)

    assert server.config["graphs"]["lead_agent"] == f"{tmp_path / 'pkg' / 'graph.py'}:graph"
    assert server.config["auth"]["path"] == f"{tmp_path / 'auth.py'}:auth"
    assert server.config["http"]["app"] == f"{tmp_path / 'api.py'}:app"
    assert server.config["checkpointer"]["path"] == f"{tmp_path / 'checkpointer.py'}:make_checkpointer"


def test_langgraph_server_app_preserves_native_langgraph_routes(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    server = AgentkitLangGraphServerApp(config_path=_write_config(tmp_path))
    client = TestClient(server.app)

    assert client.get("/ok").json() == {"ok": True}
    assert client.post("/threads").json() == {"native": "threads"}
    assert client.get("/list-apps").json() == ["lead_agent"]


def test_langgraph_server_app_requires_graph_id_for_multi_graph_configs(tmp_path, monkeypatch):
    _install_fake_langgraph(monkeypatch, _FakeClient())
    config = _write_config(
        tmp_path,
        '{"graphs": {"lead": "pkg:lead", "worker": "pkg:worker"}}',
    )

    try:
        AgentkitLangGraphServerApp(config_path=config)
    except ValueError as exc:
        assert "Multiple LangGraph graphs found" in str(exc)
    else:
        raise AssertionError("expected multi-graph config to require graph_id")


def test_langgraph_server_app_reports_missing_server_dependencies(tmp_path, monkeypatch):
    config = _write_config(tmp_path)

    def fail_import(name):
        if name == "langgraph_api.server":
            raise ImportError("missing server")
        return __import__(name)

    monkeypatch.setattr(
        "agentkit.apps.langgraph_server_app.langgraph_server_app.importlib.import_module",
        fail_import,
    )

    with pytest.raises(ImportError, match="requires langgraph-api and langgraph-sdk"):
        AgentkitLangGraphServerApp(config_path=config)


def test_run_sse_maps_agentkit_request_to_langgraph_thread_and_stream(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    server = AgentkitLangGraphServerApp(config_path=_write_config(tmp_path))
    client = TestClient(server.app)
    message = types.UserContent(parts=[types.Part(text="hello")])

    response = client.post(
        "/run_sse",
        json={
            "appName": "lead_agent",
            "userId": "user-1",
            "sessionId": "session-1",
            "newMessage": message.model_dump(exclude_none=True, by_alias=True),
            "streaming": True,
            "stateDelta": {"tenant": "demo"},
        },
    )

    assert response.status_code == 200
    assert "hel" in response.text
    assert "lo" in response.text
    assert "final answer" in response.text
    expected_thread_id = _agentkit_thread_id("lead_agent", "user-1", "session-1")
    assert fake_client.threads.created[0]["thread_id"] == expected_thread_id
    assert fake_client.threads.created[0]["metadata"]["agentkit_session_id"] == "session-1"
    run_kwargs = fake_client.runs.calls[0]
    assert run_kwargs["assistant_id"] == "lead_agent"
    assert run_kwargs["thread_id"] == expected_thread_id
    assert run_kwargs["input"] == {"messages": [{"role": "user", "content": "hello"}]}
    assert run_kwargs["config"]["configurable"]["user_id"] == "user-1"
    assert run_kwargs["config"]["configurable"]["agentkit_session_id"] == "session-1"
    assert run_kwargs["config"]["configurable"]["tenant"] == "demo"
    assert "context" not in run_kwargs
    assert run_kwargs["if_not_exists"] == "create"


def test_llm_shield_blocks_langgraph_input_before_thread_or_run(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    shield = _FakeShield(blocked_role="user")
    server = AgentkitLangGraphServerApp(
        config_path=_write_config(tmp_path), llm_shield=shield
    )
    client = TestClient(server.app)

    response = client.post(
        "/run_sse",
        json={
            "appName": "lead_agent",
            "userId": "user-1",
            "sessionId": "session-1",
            "newMessage": {"role": "user", "parts": [{"text": "unsafe"}]},
            "streaming": True,
        },
    )

    assert response.status_code == 200
    assert LLM_SHIELD_BLOCK_MESSAGE in response.text
    assert fake_client.threads.created == []
    assert fake_client.runs.calls == []
    assert shield.calls == [("unsafe", "user")]


def test_llm_shield_buffers_and_blocks_langgraph_output(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    shield = _FakeShield(blocked_role="assistant")
    server = AgentkitLangGraphServerApp(
        config_path=_write_config(tmp_path), llm_shield=shield
    )
    client = TestClient(server.app)

    response = client.post(
        "/run_sse",
        json={
            "appName": "lead_agent",
            "userId": "user-1",
            "sessionId": "session-1",
            "newMessage": {"role": "user", "parts": [{"text": "hello"}]},
            "streaming": True,
        },
    )

    assert response.status_code == 200
    assert LLM_SHIELD_BLOCK_MESSAGE in response.text
    assert '"text":"hel"' not in response.text
    assert '"text":"lo"' not in response.text
    assert "final answer" not in response.text
    assert shield.calls == [("hello", "user"), ("final answer", "assistant")]


def test_llm_shield_fails_closed_when_service_is_unavailable(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    shield = _FakeShield(unavailable=True)
    server = AgentkitLangGraphServerApp(
        config_path=_write_config(tmp_path), llm_shield=shield
    )
    client = TestClient(server.app)

    response = client.post(
        "/invoke",
        json={"prompt": "hello"},
        headers={"user_id": "user-1", "session_id": "session-1"},
    )

    assert response.status_code == 200
    assert LLM_SHIELD_UNAVAILABLE_MESSAGE in response.text
    assert fake_client.runs.calls == []


def test_llm_shield_fails_closed_before_buffering_oversized_langgraph_output(
    tmp_path, monkeypatch
):
    fake_client = _FakeClient()
    fake_client.runs = _OversizedRuns()
    _install_fake_langgraph(monkeypatch, fake_client)
    shield = _FakeShield(max_output_bytes=3)
    server = AgentkitLangGraphServerApp(
        config_path=_write_config(tmp_path), llm_shield=shield
    )
    client = TestClient(server.app)

    response = client.post(
        "/run_sse",
        json={
            "appName": "lead_agent",
            "userId": "user-1",
            "sessionId": "session-1",
            "newMessage": {"role": "user", "parts": [{"text": "ok"}]},
            "streaming": True,
        },
    )

    assert response.status_code == 200
    assert LLM_SHIELD_UNAVAILABLE_MESSAGE in response.text
    assert "four" not in response.text
    assert shield.calls == [("ok", "user")]


def test_llm_shield_hides_langgraph_stream_errors(tmp_path, monkeypatch, caplog):
    fake_client = _FakeClient()
    fake_client.runs = _FailingRuns()
    _install_fake_langgraph(monkeypatch, fake_client)
    shield = _FakeShield()
    server = AgentkitLangGraphServerApp(
        config_path=_write_config(tmp_path), llm_shield=shield
    )
    client = TestClient(server.app)

    response = client.post(
        "/run_sse",
        json={
            "appName": "lead_agent",
            "userId": "user-1",
            "sessionId": "session-1",
            "newMessage": {"role": "user", "parts": [{"text": "ok"}]},
            "streaming": True,
        },
    )

    assert response.status_code == 200
    assert LLM_SHIELD_UNAVAILABLE_MESSAGE in response.text
    assert "stream boom" not in response.text
    assert "stream boom" not in caplog.text


def test_run_sse_streams_langgraph_server_messages_partial_without_echoing_user(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    fake_client.runs = _ServerStyleRuns()
    _install_fake_langgraph(monkeypatch, fake_client)
    server = AgentkitLangGraphServerApp(config_path=_write_config(tmp_path))
    client = TestClient(server.app)
    message = types.UserContent(parts=[types.Part(text="hello")])

    response = client.post(
        "/run_sse",
        json={
            "appName": "lead_agent",
            "userId": "user-1",
            "sessionId": "session-1",
            "newMessage": message.model_dump(exclude_none=True, by_alias=True),
            "streaming": True,
        },
    )

    assert response.status_code == 200
    assert '"text":"Hel"' in response.text
    assert '"text":"lo"' in response.text
    assert '"text":"Hello"' in response.text
    assert '"text":"{}"' not in response.text
    assert response.text.count('"text":"hello"') == 0


def test_run_sse_does_not_echo_human_only_values(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    fake_client.runs = _HumanOnlyValuesRuns()
    _install_fake_langgraph(monkeypatch, fake_client)
    server = AgentkitLangGraphServerApp(config_path=_write_config(tmp_path))
    client = TestClient(server.app)
    message = types.UserContent(parts=[types.Part(text="hello")])

    response = client.post(
        "/run_sse",
        json={
            "appName": "lead_agent",
            "userId": "user-1",
            "sessionId": "session-1",
            "newMessage": message.model_dump(exclude_none=True, by_alias=True),
            "streaming": True,
        },
    )

    assert response.status_code == 200
    assert '"text":"hello"' not in response.text


def test_run_sse_exposes_nested_langgraph_interrupt(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    fake_client.runs = _InterruptRuns()
    _install_fake_langgraph(monkeypatch, fake_client)
    server = AgentkitLangGraphServerApp(config_path=_write_config(tmp_path))
    client = TestClient(server.app)
    message = types.UserContent(parts=[types.Part(text="deploy")])

    response = client.post(
        "/run_sse",
        json={
            "appName": "lead_agent",
            "userId": "user-1",
            "sessionId": "session-1",
            "newMessage": message.model_dump(exclude_none=True, by_alias=True),
            "streaming": True,
        },
    )

    assert response.status_code == 200
    assert '"interrupted":true' in response.text
    assert '"errorCode":"LANGGRAPH_INTERRUPT"' in response.text
    assert "Approve deployment?" in response.text
    assert '"text":"deploy"' not in response.text


def test_run_and_invoke_routes_use_langgraph_server_stream(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    server = AgentkitLangGraphServerApp(config_path=_write_config(tmp_path), input_key="question")
    client = TestClient(server.app)
    message = types.UserContent(parts=[types.Part(text="hello")])

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    detailed = client.get("/list-apps?detailed=true")
    assert detailed.status_code == 200
    assert detailed.json()["apps"][0]["name"] == "lead_agent"

    session = client.get("/apps/lead_agent/users/user-1/sessions/session-1")
    assert session.status_code == 200
    assert session.json()["state"] == {"existing": True}
    assert fake_client.threads.got == [_agentkit_thread_id("lead_agent", "user-1", "session-1")]

    run = client.post(
        "/run",
        json={
            "appName": "lead_agent",
            "userId": "user-1",
            "sessionId": "session-1",
            "newMessage": message.model_dump(exclude_none=True, by_alias=True),
            "streaming": False,
        },
    )
    assert run.status_code == 200
    assert "final answer" in run.text
    assert fake_client.runs.calls[-1]["input"] == {"question": "hello"}

    invoke = client.post(
        "/invoke",
        json={"prompt": "from invoke"},
        headers={"user_id": "invoke-user", "session_id": "invoke-session"},
    )
    assert invoke.status_code == 200
    assert "final answer" in invoke.text
    assert fake_client.runs.calls[-1]["config"]["configurable"]["user_id"] == "invoke-user"

    invoke_without_prompt = client.post("/invoke", json={"question": "from payload"})
    assert invoke_without_prompt.status_code == 200
    assert fake_client.runs.calls[-1]["input"] == {
        "question": '{"question": "from payload"}'
    }

    invalid_invoke = client.post(
        "/invoke",
        data="{",
        headers={"Content-Type": "application/json"},
    )
    assert invalid_invoke.status_code == 200
    assert fake_client.runs.calls[-1]["input"] == {"question": ""}


def test_run_sse_returns_error_event_when_langgraph_stream_fails(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    fake_client.runs = _FailingRuns()
    _install_fake_langgraph(monkeypatch, fake_client)
    server = AgentkitLangGraphServerApp(config_path=_write_config(tmp_path))
    client = TestClient(server.app)
    message = types.UserContent(parts=[types.Part(text="hello")])

    response = client.post(
        "/run_sse",
        json={
            "appName": "lead_agent",
            "userId": "user-1",
            "sessionId": "session-1",
            "newMessage": message.model_dump(exclude_none=True, by_alias=True),
            "streaming": True,
        },
    )

    assert response.status_code == 200
    assert "stream boom" in response.text


def test_session_create_tolerates_empty_and_invalid_json_bodies(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    server = AgentkitLangGraphServerApp(config_path=_write_config(tmp_path))
    client = TestClient(server.app)

    empty = client.post("/apps/lead_agent/users/user-1/sessions")
    assert empty.status_code == 200

    invalid = client.post(
        "/apps/lead_agent/users/user-1/sessions/session-invalid",
        data="{",
        headers={"Content-Type": "application/json"},
    )
    assert invalid.status_code == 200
    assert invalid.json()["id"] == "session-invalid"


def test_session_routes_map_to_langgraph_threads(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    server = AgentkitLangGraphServerApp(config_path=_write_config(tmp_path))
    client = TestClient(server.app)

    created = client.post(
        "/apps/lead_agent/users/user-1/sessions",
        json={"sessionId": "session-2", "state": {"topic": "demo"}},
    )
    assert created.status_code == 200
    assert created.json()["id"] == "session-2"
    expected_thread_id = _agentkit_thread_id("lead_agent", "user-1", "session-2")
    assert fake_client.threads.created[0]["thread_id"] == expected_thread_id
    assert fake_client.threads.created[0]["metadata"]["topic"] == "demo"

    listed = client.get("/apps/lead_agent/users/user-1/sessions")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == "session-1"

    updated = client.patch(
        "/apps/lead_agent/users/user-1/sessions/session-2",
        json={"stateDelta": {"step": "next"}},
    )
    assert updated.status_code == 200
    assert fake_client.threads.updated == [(expected_thread_id, {"metadata": {"step": "next"}})]

    deleted = client.delete("/apps/lead_agent/users/user-1/sessions/session-2")
    assert deleted.status_code == 204
    assert fake_client.threads.deleted == [expected_thread_id]


def test_agentkit_sessions_are_scoped_by_app_user_and_session(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    server = AgentkitLangGraphServerApp(config_path=_write_config(tmp_path))
    client = TestClient(server.app)

    for user_id in ("user-1", "user-2"):
        response = client.post(
            f"/apps/lead_agent/users/{user_id}/sessions/shared-session",
            json={},
        )
        assert response.status_code == 200

    thread_ids = [call["thread_id"] for call in fake_client.threads.created]
    assert thread_ids == [
        _agentkit_thread_id("lead_agent", "user-1", "shared-session"),
        _agentkit_thread_id("lead_agent", "user-2", "shared-session"),
    ]
    assert thread_ids[0] != thread_ids[1]


def test_run_delegates_to_uvicorn(tmp_path, monkeypatch):
    fake_client = _FakeClient()
    _install_fake_langgraph(monkeypatch, fake_client)
    server = AgentkitLangGraphServerApp(config_path=_write_config(tmp_path))
    calls = []

    def fake_run(app, host=None, port=None):
        calls.append({"app": app, "host": host, "port": port})

    monkeypatch.setattr(
        "agentkit.apps.langgraph_server_app.langgraph_server_app.uvicorn.run",
        fake_run,
    )

    server.run(port=9000)

    assert calls == [{"app": server.app, "host": "0.0.0.0", "port": 9000}]

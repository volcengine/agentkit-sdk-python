# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Offline behaviour guards for the ``/invoke`` compatibility serving path.

Target: ``AgentkitAgentServerApp.__init__``'s ``_invoke_compat`` closure
(``agentkit/apps/agent_server_app/agent_server_app.py``). The endpoint is the
AgentKit-CLI-compatible request-serving transport and is otherwise 0% covered.

``_invoke_compat`` is a *closure* defined inside ``__init__`` -- there is no
class-level method to bind, and constructing the app normally builds heavy ADK
objects (AdkWebServer, to_a2a, a full FastAPI app). So we rebuild the *real*
function object from its compiled code object -- the closure captures exactly
one free variable (``self``) -- and rebind it against a hand-rolled fake
``self``. This runs the genuine bytecode of ``_invoke_compat`` (real branch
logic, real module globals: ``trace``, ``telemetry``, ``HTTPException``,
``json``, ``types``, ``RunConfig``, ``StreamingMode``, ``Aclosing``,
``StreamingResponse``) with a controllable collaborator surface -- no sockets,
no ADK runtime, no network.

The fakes match the real collaborator surface the closure reaches for:
``self.server.agent_loader.list_agents()``, the async
``self.server.session_service.get_session/create_session(...)``, and the async
``self.server.get_runner_async(app_name)`` yielding a runner whose
``run_async(...)`` returns an async generator of events.
"""

from __future__ import annotations

import asyncio
import json
import types as pytypes

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from google.adk.agents.run_config import StreamingMode
from google.genai import types as genai_types

import agentkit.apps.agent_server_app.agent_server_app as mod


# ---------------------------------------------------------------------------
# Extract the real _invoke_compat code object from __init__ and rebuild it.
# ---------------------------------------------------------------------------


def _find_code(code, name):
    for const in code.co_consts:
        if isinstance(const, pytypes.CodeType):
            if const.co_name == name:
                return const
            found = _find_code(const, name)
            if found is not None:
                return found
    return None


_INVOKE_COMPAT_CODE = _find_code(
    mod.AgentkitAgentServerApp.__init__.__code__, "_invoke_compat"
)
assert _INVOKE_COMPAT_CODE is not None, "could not locate _invoke_compat code object"
# Guard the seam assumption: the closure captures exactly `self`. If a future
# refactor adds free variables, this test's rebind would silently drift.
assert _INVOKE_COMPAT_CODE.co_freevars == ("self",), (
    f"unexpected freevars: {_INVOKE_COMPAT_CODE.co_freevars}"
)


def _make_cell(value):
    # Build a closure cell holding `value`.
    return (lambda: value).__closure__[0]


def _bind_invoke_compat(fake_self):
    """Rebuild the real ``_invoke_compat`` bound to ``fake_self``.

    Uses the module's real ``__dict__`` as globals so every name the closure
    references resolves to the production symbol.
    """
    return pytypes.FunctionType(
        _INVOKE_COMPAT_CODE,
        mod.__dict__,
        "_invoke_compat",
        None,
        (_make_cell(fake_self),),
    )


# ---------------------------------------------------------------------------
# Hand-rolled fakes matching the real collaborator surface.
# ---------------------------------------------------------------------------


class _FakeHeaders:
    """Mapping-like stand-in for starlette Headers.

    ``_invoke_compat`` reaches for ``dict(headers)`` (needs keys/__getitem__)
    and ``headers.get(...)``.
    """

    def __init__(self, data: dict) -> None:
        self._d = dict(data)

    def keys(self):
        return self._d.keys()

    def __getitem__(self, key):
        return self._d[key]

    def get(self, key, default=None):
        return self._d.get(key, default)


class _FakeRequest:
    """Minimal starlette Request substitute for the invoke path.

    ``json_payload`` is returned by the async ``json()``; when
    ``raise_on_json`` is set, ``json()`` raises to drive the fallback branch.
    ``body_bytes`` backs the async ``body()`` fallback.
    """

    def __init__(
        self,
        headers: dict | None = None,
        json_payload=None,
        raise_on_json: bool = False,
        body_bytes: bytes = b"",
    ) -> None:
        self.headers = _FakeHeaders(headers or {})
        self._json_payload = json_payload
        self._raise_on_json = raise_on_json
        self._body_bytes = body_bytes
        self.json_calls = 0
        self.body_calls = 0

    async def json(self):
        self.json_calls += 1
        if self._raise_on_json:
            raise ValueError("not json")
        return self._json_payload

    async def body(self):
        self.body_calls += 1
        return self._body_bytes


class _FakeEvent:
    """Event stand-in with the real ``model_dump_json`` signature."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.dump_kwargs = None

    def model_dump_json(self, exclude_none=False, by_alias=False):
        self.dump_kwargs = {"exclude_none": exclude_none, "by_alias": by_alias}
        return json.dumps(self._payload)


class _FakeRunner:
    """Records the run_async kwargs and yields the configured events.

    ``run_async`` returns a *real* async generator so ``Aclosing`` can call
    ``aclose()`` on it, exactly as the production code expects.
    """

    def __init__(self, events, raise_exc: Exception | None = None) -> None:
        self._events = events
        self._raise_exc = raise_exc
        self.run_async_calls: list[dict] = []

    def run_async(self, **kwargs):
        self.run_async_calls.append(kwargs)
        events = self._events
        raise_exc = self._raise_exc

        async def _agen():
            if raise_exc is not None:
                raise raise_exc
            for ev in events:
                yield ev

        return _agen()


class _FakeSessionService:
    """Async session service.

    ``existing_session`` (any truthy sentinel) is returned by ``get_session``;
    when it is falsy, the closure must call ``create_session``. All calls are
    recorded with their kwargs.
    """

    def __init__(self, existing_session=None) -> None:
        self._existing = existing_session
        self.get_calls: list[dict] = []
        self.create_calls: list[dict] = []

    async def get_session(self, **kwargs):
        self.get_calls.append(kwargs)
        return self._existing

    async def create_session(self, **kwargs):
        self.create_calls.append(kwargs)
        return object()


class _FakeAgentLoader:
    def __init__(self, agents) -> None:
        self._agents = list(agents)
        self.list_calls = 0

    def list_agents(self):
        self.list_calls += 1
        return list(self._agents)


class _FakeServer:
    def __init__(self, agent_loader, session_service, runner) -> None:
        self.agent_loader = agent_loader
        self.session_service = session_service
        self._runner = runner
        self.get_runner_calls: list = []

    async def get_runner_async(self, app_name):
        self.get_runner_calls.append(app_name)
        return self._runner


class _FakeSelf:
    """The ``self`` the closure captures: only ``server`` is ever touched."""

    def __init__(self, server) -> None:
        self.server = server


# Records of telemetry calls so tests can assert wiring without touching a
# real OTEL span (whose set_attribute/end side-effects we don't want here).
_TELEMETRY_CALLS: dict = {"server": [], "finish": []}


class _FakeSpan:
    def __init__(self) -> None:
        self.recording = True

    def is_recording(self):
        return self.recording


@pytest.fixture(autouse=True)
def _isolate_telemetry_and_span(monkeypatch):
    """Neutralise telemetry side-effects and record its calls.

    ``_invoke_compat`` calls ``trace.get_current_span()`` then
    ``telemetry.trace_agent_server(...)`` at entry, and
    ``telemetry.trace_agent_server_finish(...)`` on the 404 branch and inside
    the streaming generator's error path. We patch the module singleton's
    bound methods to no-op recorders and pin the current span so nothing
    touches a live tracer.
    """
    _TELEMETRY_CALLS["server"].clear()
    _TELEMETRY_CALLS["finish"].clear()

    def _fake_trace_agent_server(*, func_name, span, headers, text):
        _TELEMETRY_CALLS["server"].append(
            {"func_name": func_name, "headers": headers, "text": text}
        )

    def _fake_trace_finish(*, path, func_result, exception):
        _TELEMETRY_CALLS["finish"].append(
            {"path": path, "func_result": func_result, "exception": exception}
        )

    monkeypatch.setattr(
        mod.telemetry, "trace_agent_server", _fake_trace_agent_server
    )
    monkeypatch.setattr(
        mod.telemetry, "trace_agent_server_finish", _fake_trace_finish
    )
    monkeypatch.setattr(mod.trace, "get_current_span", lambda: _FakeSpan())
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build(
    *,
    agents=("my_app",),
    existing_session=None,
    events=None,
    run_exc: Exception | None = None,
):
    runner = _FakeRunner(events if events is not None else [], raise_exc=run_exc)
    session_service = _FakeSessionService(existing_session=existing_session)
    agent_loader = _FakeAgentLoader(agents)
    server = _FakeServer(agent_loader, session_service, runner)
    fake_self = _FakeSelf(server)
    invoke = _bind_invoke_compat(fake_self)
    return invoke, fake_self, server, session_service, runner


async def _drain(response: StreamingResponse) -> list[str]:
    return [chunk async for chunk in response.body_iterator]


# ===========================================================================
# 404 branch: no agents configured
# ===========================================================================


def test_invoke_raises_404_when_no_agents_configured():
    invoke, _self, server, session_service, _runner = _build(agents=())
    request = _FakeRequest(json_payload={"prompt": "hi"})

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(invoke(request))

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "No agents configured"
    # The loader was consulted, but nothing downstream ran.
    assert server.agent_loader.list_calls == 1
    assert session_service.get_calls == []
    assert session_service.create_calls == []


def test_invoke_404_reports_finish_telemetry_for_invoke_path_with_the_exception():
    invoke, _self, _server, _ss, _runner = _build(agents=())
    request = _FakeRequest(json_payload={"prompt": "hi"})

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(invoke(request))

    # The 404 branch traces a finish event on the /invoke path carrying the
    # raised HTTPException before re-raising.
    assert len(_TELEMETRY_CALLS["finish"]) == 1
    finish = _TELEMETRY_CALLS["finish"][0]
    assert finish["path"] == "/invoke"
    assert finish["exception"] is excinfo.value


# ===========================================================================
# Entry telemetry + header redaction
# ===========================================================================


def test_invoke_entry_traces_request_with_authorization_and_token_redacted():
    invoke, _self, _server, _ss, _runner = _build(
        agents=("my_app",), existing_session=object()
    )
    request = _FakeRequest(
        headers={
            "Authorization": "Bearer secret",
            "Token": "abc",
            "user_id": "u1",
            "content-type": "application/json",
        },
        json_payload={"prompt": "hi"},
    )

    asyncio.run(invoke(request))

    assert len(_TELEMETRY_CALLS["server"]) == 1
    entry = _TELEMETRY_CALLS["server"][0]
    assert entry["func_name"] == "_invoke_compat"
    # Authorization/token (case-insensitively) are stripped from telemetry.
    assert "Authorization" not in entry["headers"]
    assert "Token" not in entry["headers"]
    assert entry["headers"]["user_id"] == "u1"
    assert entry["headers"]["content-type"] == "application/json"


# ===========================================================================
# user_id / session_id header handling
# ===========================================================================


def test_invoke_defaults_user_id_and_empty_session_when_headers_absent():
    invoke, _self, _server, session_service, _runner = _build(
        agents=("my_app",), existing_session=None
    )
    request = _FakeRequest(headers={}, json_payload={"prompt": "hi"})

    asyncio.run(invoke(request))

    # get_session is called with the defaulted identity before the stream.
    assert session_service.get_calls == [
        {
            "app_name": "my_app",
            "user_id": "agentkit_user",
            "session_id": "",
        }
    ]


def test_invoke_uses_user_and_session_id_from_headers():
    invoke, _self, _server, session_service, _runner = _build(
        agents=("my_app",), existing_session=object()
    )
    request = _FakeRequest(
        headers={"user_id": "alice", "session_id": "sess-9"},
        json_payload={"prompt": "hi"},
    )

    asyncio.run(invoke(request))

    assert session_service.get_calls == [
        {"app_name": "my_app", "user_id": "alice", "session_id": "sess-9"}
    ]


# ===========================================================================
# app_name selection: first agent from the loader
# ===========================================================================


def test_invoke_selects_first_agent_as_app_name():
    invoke, _self, server, session_service, runner = _build(
        agents=("first_app", "second_app"), existing_session=object()
    )
    request = _FakeRequest(json_payload={"prompt": "hi"})

    response = asyncio.run(invoke(request))
    asyncio.run(_drain(response))

    assert session_service.get_calls[0]["app_name"] == "first_app"
    assert server.get_runner_calls == ["first_app"]
    assert runner.run_async_calls[0]["session_id"] == ""


# ===========================================================================
# Prompt extraction branches
# ===========================================================================


def test_invoke_uses_prompt_field_verbatim_as_content_text():
    invoke, _self, _server, _ss, runner = _build(
        agents=("my_app",), existing_session=object()
    )
    request = _FakeRequest(json_payload={"prompt": "hello world", "other": 1})

    response = asyncio.run(invoke(request))
    asyncio.run(_drain(response))

    content = runner.run_async_calls[0]["new_message"]
    assert isinstance(content, genai_types.UserContent)
    assert content.parts[0].text == "hello world"


def test_invoke_falls_back_to_json_dumps_of_dict_payload_without_prompt():
    invoke, _self, _server, _ss, runner = _build(
        agents=("my_app",), existing_session=object()
    )
    payload = {"foo": "bar", "n": 2}
    request = _FakeRequest(json_payload=payload)

    response = asyncio.run(invoke(request))
    asyncio.run(_drain(response))

    content = runner.run_async_calls[0]["new_message"]
    # No "prompt" key -> the whole dict is json.dumps'd (ensure_ascii=False).
    assert content.parts[0].text == json.dumps(payload, ensure_ascii=False)


def test_invoke_json_dumps_fallback_preserves_non_ascii():
    invoke, _self, _server, _ss, runner = _build(
        agents=("my_app",), existing_session=object()
    )
    payload = {"msg": "你好"}
    request = _FakeRequest(json_payload=payload)

    response = asyncio.run(invoke(request))
    asyncio.run(_drain(response))

    content = runner.run_async_calls[0]["new_message"]
    # ensure_ascii=False keeps the raw characters rather than \uXXXX escapes.
    assert content.parts[0].text == json.dumps(payload, ensure_ascii=False)
    assert "你好" in content.parts[0].text


def test_invoke_reads_raw_body_when_json_parsing_fails():
    invoke, _self, _server, _ss, runner = _build(
        agents=("my_app",), existing_session=object()
    )
    request = _FakeRequest(raise_on_json=True, body_bytes=b"raw text body")

    response = asyncio.run(invoke(request))
    asyncio.run(_drain(response))

    # json() raised -> payload is None -> not a dict -> raw body decoded.
    assert request.json_calls == 1
    assert request.body_calls == 1
    content = runner.run_async_calls[0]["new_message"]
    assert content.parts[0].text == "raw text body"


def test_invoke_non_dict_json_payload_is_json_dumped_not_read_from_body():
    # json() succeeds but returns a list (not a dict): text is None, and since
    # payload is not None the raw-body branch is skipped -- json.dumps(payload)
    # runs instead. Pin that: a list payload is serialised, NOT the raw body.
    invoke, _self, _server, _ss, runner = _build(
        agents=("my_app",), existing_session=object()
    )
    payload = ["a", "b"]
    request = _FakeRequest(json_payload=payload, body_bytes=b"unused")

    response = asyncio.run(invoke(request))
    asyncio.run(_drain(response))

    # payload is not None -> json.dumps(payload) path (body() NOT read).
    assert request.body_calls == 0
    content = runner.run_async_calls[0]["new_message"]
    assert content.parts[0].text == json.dumps(payload, ensure_ascii=False)


# ===========================================================================
# Session creation branch
# ===========================================================================


def test_invoke_creates_session_when_missing():
    invoke, _self, _server, session_service, _runner = _build(
        agents=("my_app",), existing_session=None
    )
    request = _FakeRequest(
        headers={"user_id": "u2", "session_id": "s2"},
        json_payload={"prompt": "hi"},
    )

    asyncio.run(invoke(request))

    # get_session returned falsy -> create_session invoked with same identity.
    assert session_service.create_calls == [
        {"app_name": "my_app", "user_id": "u2", "session_id": "s2"}
    ]


def test_invoke_does_not_create_session_when_it_already_exists():
    invoke, _self, _server, session_service, _runner = _build(
        agents=("my_app",), existing_session=object()
    )
    request = _FakeRequest(json_payload={"prompt": "hi"})

    asyncio.run(invoke(request))

    assert session_service.get_calls != []
    assert session_service.create_calls == []


# ===========================================================================
# StreamingResponse shape + SSE headers
# ===========================================================================


def test_invoke_returns_sse_streaming_response_with_cache_headers():
    invoke, _self, _server, _ss, _runner = _build(
        agents=("my_app",), existing_session=object()
    )
    request = _FakeRequest(json_payload={"prompt": "hi"})

    response = asyncio.run(invoke(request))

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers.get("Cache-Control") == "no-cache"
    assert response.headers.get("Connection") == "keep-alive"
    assert response.headers.get("X-Accel-Buffering") == "no"


# ===========================================================================
# Event streaming body: happy path
# ===========================================================================


def test_invoke_stream_emits_sse_data_frames_per_event():
    ev1 = _FakeEvent({"id": 1, "text": "a"})
    ev2 = _FakeEvent({"id": 2, "text": "b"})
    invoke, _self, server, _ss, runner = _build(
        agents=("my_app",), existing_session=object(), events=[ev1, ev2]
    )
    request = _FakeRequest(json_payload={"prompt": "hi"})

    response = asyncio.run(invoke(request))
    chunks = asyncio.run(_drain(response))

    # The runner is fetched lazily inside the generator, only on drain.
    assert server.get_runner_calls == ["my_app"]
    assert chunks == [
        "data: " + json.dumps({"id": 1, "text": "a"}) + "\n\n",
        "data: " + json.dumps({"id": 2, "text": "b"}) + "\n\n",
    ]
    # Each event is dumped with the ADK-web serialization flags.
    assert ev1.dump_kwargs == {"exclude_none": True, "by_alias": True}
    assert ev2.dump_kwargs == {"exclude_none": True, "by_alias": True}


def test_invoke_stream_runs_agent_with_sse_run_config_and_identity():
    ev = _FakeEvent({"ok": True})
    invoke, _self, _server, _ss, runner = _build(
        agents=("my_app",), existing_session=object(), events=[ev]
    )
    request = _FakeRequest(
        headers={"user_id": "bob", "session_id": "sid-5"},
        json_payload={"prompt": "yo"},
    )

    response = asyncio.run(invoke(request))
    asyncio.run(_drain(response))

    call = runner.run_async_calls[0]
    assert call["user_id"] == "bob"
    assert call["session_id"] == "sid-5"
    assert isinstance(call["new_message"], genai_types.UserContent)
    assert call["new_message"].parts[0].text == "yo"
    assert call["run_config"].streaming_mode == StreamingMode.SSE


def test_invoke_stream_is_lazy_no_runner_fetch_before_drain():
    ev = _FakeEvent({"ok": True})
    invoke, _self, server, _ss, runner = _build(
        agents=("my_app",), existing_session=object(), events=[ev]
    )
    request = _FakeRequest(json_payload={"prompt": "hi"})

    asyncio.run(invoke(request))  # build the response but do NOT drain

    # get_runner_async / run_async live inside the body generator; without
    # draining they must not have run.
    assert server.get_runner_calls == []
    assert runner.run_async_calls == []


# ===========================================================================
# Event streaming body: error path inside the generator
# ===========================================================================


def test_invoke_stream_emits_error_frame_when_runner_raises():
    boom = RuntimeError("runner exploded")
    invoke, _self, _server, _ss, _runner = _build(
        agents=("my_app",), existing_session=object(), run_exc=boom
    )
    request = _FakeRequest(json_payload={"prompt": "hi"})

    response = asyncio.run(invoke(request))
    chunks = asyncio.run(_drain(response))

    # The generator catches the exception and yields a single error SSE frame
    # carrying only the exception type — never the exception message, which
    # may leak internal paths/backend detail (parity with /run_sse).
    assert len(chunks) == 1
    assert chunks[0].startswith("data: ") and chunks[0].endswith("\n\n")
    frame = json.loads(chunks[0][len("data: ") :])
    assert frame["error_type"] == "RuntimeError"
    assert "runner exploded" not in chunks[0]


def test_invoke_stream_error_path_traces_finish_with_the_exception():
    boom = RuntimeError("kaboom")
    invoke, _self, _server, _ss, _runner = _build(
        agents=("my_app",), existing_session=object(), run_exc=boom
    )
    request = _FakeRequest(json_payload={"prompt": "hi"})

    response = asyncio.run(invoke(request))
    asyncio.run(_drain(response))

    # The except branch traces a finish event for /invoke carrying the error.
    assert len(_TELEMETRY_CALLS["finish"]) == 1
    finish = _TELEMETRY_CALLS["finish"][0]
    assert finish["path"] == "/invoke"
    assert finish["exception"] is boom

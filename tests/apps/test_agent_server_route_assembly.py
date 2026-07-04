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

"""Offline route-table assembly guards for ``AgentkitAgentServerApp``.

Target: ``AgentkitAgentServerApp.__init__``
(``agentkit/apps/agent_server_app/agent_server_app.py``). The constructor
assembles the serving surface on the FastAPI app returned by ADK's
``AdkWebServer.get_fast_api_app``: it registers the custom ``POST /run_sse``
override and moves it to the *front* of the route table for priority matching
(without deleting the ADK default route), attaches
``AgentkitTelemetryHTTPMiddleware``, adds the ``POST /invoke`` compatibility
route, and finally mounts the A2A server app at ``/`` -- deliberately last so
the catch-all mount cannot shadow API routes.

None of this was previously covered by a test that assembles a *real* FastAPI
app and inspects ``router.routes``; a duplicated ``POST /run_sse``
registration (dead code, since removed) shipped unnoticed because of that
gap. These tests close it.

Seam: ``get_fast_api_app`` is a *bound method* of the ``AdkWebServer``
instance created inside ``__init__`` (there is no module-level symbol to
patch), so we monkeypatch the module's ``AdkWebServer`` reference with a
subclass that keeps the real (trivial, assignment-only) constructor and
overrides only ``get_fast_api_app`` to return a plain ``fastapi.FastAPI``.
``__init__`` then runs its full assembly logic against that real app -- real
route objects, real middleware stack -- with no ADK server, no sockets, no
network. The two heavy collaborators that cannot be built offline from a
plain ``BaseAgent`` are stubbed at module level: ``Runner`` (veadk; reaches
for ``agent.short_term_memory``) and ``to_a2a`` (builds a full A2A app); the
stubbed A2A app is a real ``starlette`` application so the ``mount()`` and
lifespan surfaces stay genuine.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute
from google.adk.agents.base_agent import BaseAgent
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from starlette.applications import Starlette
from starlette.routing import Mount

import agentkit.apps.agent_server_app.agent_server_app as mod
from agentkit.apps.agent_server_app.middleware import (
    AgentkitTelemetryHTTPMiddleware,
)

# Env vars read by resolve_agentkit_allow_origins(); cleared per-assembly so
# CORS resolution is deterministic regardless of the host environment.
_ORIGIN_ENV_VARS = (
    "AGENTKIT_ALLOW_ORIGINS",
    "ADK_ALLOW_ORIGINS",
    "AGENTKIT_ALLOW_ORIGIN_REGEX",
    "ADK_ALLOW_ORIGIN_REGEX",
    "AGENTKIT_DISABLE_DEFAULT_ALLOW_ORIGINS",
)


# ---------------------------------------------------------------------------
# Assembly helper: run the real __init__ against a real FastAPI base app.
# ---------------------------------------------------------------------------


def _assemble(monkeypatch, *, with_adk_default_run_sse: bool = False):
    """Construct ``AgentkitAgentServerApp`` on a real FastAPI base app.

    ``with_adk_default_run_sse`` simulates the ADK default ``POST /run_sse``
    route already being present on the app returned by ``get_fast_api_app``,
    which is what the priority-move logic exists for in production.

    Returns ``(server_app, records)`` where ``records`` captures the base
    app, the stubbed A2A app instance, and the veadk Runner kwargs.
    """
    for name in _ORIGIN_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    records: dict = {"base_app": None, "a2a_app": None, "runner_kwargs": None}

    class _StubAdkWebServer(mod.AdkWebServer):
        """Real AdkWebServer wiring, minus the ADK FastAPI factory."""

        def get_fast_api_app(self, lifespan=None, allow_origins=None, **kwargs):
            del allow_origins, kwargs
            base_app = FastAPI(lifespan=lifespan)
            if with_adk_default_run_sse:
                # Stand-in for the route the real ADK factory registers.
                async def _adk_default_run_sse():
                    return {"source": "adk-default"}

                base_app.post("/run_sse")(_adk_default_run_sse)
            records["base_app"] = base_app
            return base_app

    class _StubRunner:
        """veadk Runner stand-in: record kwargs, build nothing."""

        def __init__(self, agent=None, short_term_memory=None, **kwargs):
            records["runner_kwargs"] = {
                "agent": agent,
                "short_term_memory": short_term_memory,
                **kwargs,
            }

    def _stub_to_a2a(agent=None, runner=None, **kwargs):
        del agent, runner, kwargs
        # A real starlette app: mountable ASGI callable with a genuine
        # ``router.on_startup`` for the lifespan hook in __init__.
        records["a2a_app"] = Starlette()
        return records["a2a_app"]

    monkeypatch.setattr(mod, "AdkWebServer", _StubAdkWebServer)
    monkeypatch.setattr(mod, "Runner", _StubRunner)
    monkeypatch.setattr(mod, "to_a2a", _stub_to_a2a)

    server_app = mod.AgentkitAgentServerApp(
        agent=BaseAgent(name="route_assembly_agent"),
        short_term_memory=InMemorySessionService(),
    )
    return server_app, records


def _post_routes(app, path):
    return [
        r
        for r in app.router.routes
        if getattr(r, "path", None) == path
        and "POST" in getattr(r, "methods", set())
    ]


def _endpoint_name(route):
    return getattr(getattr(route, "endpoint", None), "__name__", None)


# ===========================================================================
# POST /run_sse: exactly one custom registration, at the front of the table
# ===========================================================================


def test_run_sse_registered_exactly_once(monkeypatch):
    # Regression guard for the removed dead code that registered the custom
    # POST /run_sse override twice. On a plain base app the route table must
    # contain exactly one POST /run_sse: the custom override.
    server_app, _records = _assemble(monkeypatch)

    run_sse_routes = _post_routes(server_app.app, "/run_sse")

    assert len(run_sse_routes) == 1
    assert _endpoint_name(run_sse_routes[0]) == "run_agent_sse"


def test_run_sse_is_the_first_route_for_priority_matching(monkeypatch):
    # __init__ pops the custom route and insert(0)s it so it wins matching
    # over anything else (FastAPI puts /openapi.json, /docs, ... first by
    # default). Assert it really landed at index 0.
    server_app, _records = _assemble(monkeypatch)

    routes = server_app.app.router.routes

    first = routes[0]
    assert isinstance(first, APIRoute)
    assert first.path == "/run_sse"
    assert "POST" in first.methods
    assert _endpoint_name(first) == "run_agent_sse"
    # And it is the only POST /run_sse anywhere else in the table.
    assert _post_routes(server_app.app, "/run_sse") == [first]


def test_run_sse_priority_move_keeps_adk_default_route(monkeypatch):
    # When the base app already carries the ADK default POST /run_sse (the
    # production case), the custom override must be moved ahead of it while
    # the default stays in the table -- moved, not deleted, and no duplicate
    # of the custom endpoint.
    server_app, _records = _assemble(monkeypatch, with_adk_default_run_sse=True)

    run_sse_routes = _post_routes(server_app.app, "/run_sse")
    names = [_endpoint_name(r) for r in run_sse_routes]

    assert names == ["run_agent_sse", "_adk_default_run_sse"]
    assert server_app.app.router.routes[0] is run_sse_routes[0]


# ===========================================================================
# POST /invoke: present and not shadowed by the A2A root mount
# ===========================================================================


def test_invoke_route_registered_exactly_once(monkeypatch):
    server_app, _records = _assemble(monkeypatch)

    invoke_routes = _post_routes(server_app.app, "/invoke")

    assert len(invoke_routes) == 1
    assert _endpoint_name(invoke_routes[0]) == "_invoke_compat"


def test_root_mount_is_last_and_does_not_shadow_invoke(monkeypatch):
    # The A2A app is mounted at "/" (a catch-all): if it preceded /invoke in
    # the route table it would swallow the request. __init__ mounts it last
    # on purpose; pin both the relative order and the mounted app identity.
    server_app, records = _assemble(monkeypatch)

    routes = server_app.app.router.routes
    mounts = [r for r in routes if isinstance(r, Mount)]

    assert len(mounts) == 1
    mount = mounts[0]
    assert mount.app is records["a2a_app"]

    [invoke_route] = _post_routes(server_app.app, "/invoke")
    assert routes.index(invoke_route) < routes.index(mount)
    # Nothing is registered after the catch-all mount.
    assert routes[-1] is mount


# ===========================================================================
# Middleware: unified telemetry attached at the app level
# ===========================================================================


def test_telemetry_http_middleware_is_attached(monkeypatch):
    server_app, _records = _assemble(monkeypatch)

    middleware_classes = [m.cls for m in server_app.app.user_middleware]

    assert AgentkitTelemetryHTTPMiddleware in middleware_classes

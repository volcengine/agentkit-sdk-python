"""兼容会话路由须保留原生 Thread 不存在的语义。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.testclient import TestClient

from agentkit.apps.langgraph_server_app.langgraph_server_app import (
    AgentkitLangGraphServerApp,
    _agentkit_thread_id,
)


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
@pytest.mark.parametrize("upstream_status", [404, 403, 500])
@pytest.mark.parametrize("app_factory", [Starlette, FastAPI])
def test_missing_session_preserves_not_found_without_exposing_upstream(
    method, upstream_status, app_factory
):
    request = httpx.Request("GET", "http://private.invalid/threads/private")
    response = httpx.Response(
        upstream_status, request=request, text="synthetic-private-upstream-body"
    )
    error = httpx.HTTPStatusError(
        "synthetic-private-upstream-error", request=request, response=response
    )
    threads = SimpleNamespace(
        get=AsyncMock(side_effect=error),
        update=AsyncMock(side_effect=error),
        delete=AsyncMock(side_effect=error),
    )
    # 本用例只验证 SDK 的 ASGI 边界；原生 Server 的真实异常另由集成回归核对。
    server = object.__new__(AgentkitLangGraphServerApp)
    server.app = app_factory()
    server.graph_id = "validation"
    server._client = SimpleNamespace(threads=threads)
    server._attach_agentkit_routes()
    client = TestClient(server.app, raise_server_exceptions=False)

    response = client.request(
        method,
        "/apps/validation/users/test-user/sessions/missing",
        **({"json": {"stateDelta": {"step": "next"}}} if method == "PATCH" else {}),
    )

    assert response.status_code == (404 if upstream_status == 404 else 500)
    if upstream_status == 404:
        if app_factory is FastAPI:
            assert response.json() == {"detail": "Session not found"}
        else:
            assert response.text == "Session not found"
    assert "synthetic-private" not in response.text
    assert "private.invalid" not in response.text
    operation = {"GET": "get", "PATCH": "update", "DELETE": "delete"}[method]
    called = getattr(threads, operation)
    assert called.await_count == 1
    assert called.await_args.args == (
        _agentkit_thread_id("validation", "test-user", "missing"),
    )

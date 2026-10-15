from __future__ import annotations

import asyncio
import time

from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
from google.adk.agents.base_agent import BaseAgent
from starlette.testclient import TestClient

from agentkit.apps.agent_server_app.agent_server_app import AgentkitAgentServerApp
from agentkit.identity import (
    IdentityAuthenticationError,
    IdentityRuntimeConfig,
    RuntimeIdentity,
    VerifiedUserIdentity,
    current_identity,
)


class _Verifier:
    def verify(self, compact):
        if compact != "valid.jwt.value":
            raise IdentityAuthenticationError("invalid")
        now = int(time.time())
        return VerifiedUserIdentity(
            subject="alice",
            issuer="https://issuer.example.com",
            audiences=("agentkit-client",),
            client_id="agentkit-client",
            expires_at=now + 300,
            issued_at=now,
            claims={"sub": "alice"},
        )


class _RecordingRunner:
    def __init__(self, calls):
        self.calls = calls

    def run_async(self, **kwargs):
        async def events():
            identity = current_identity()
            self.calls.append(
                {
                    "user_id": kwargs["user_id"],
                    "identity_sub": identity.user_sub,
                }
            )
            if False:
                yield None

        return events()


def _runtime_identity():
    return RuntimeIdentity(
        IdentityRuntimeConfig(
            runtime_id="runtime-1",
            discovery_url="https://issuer.example.com",
            expected_user_issuer="https://issuer.example.com",
            allowed_clients=("agentkit-client",),
            targets={},
        ),
        verifier=_Verifier(),
    )


def _server_with_recording_runner(*, enable_auth=False):
    server = AgentkitAgentServerApp(
        agent=BaseAgent(name="identity_integration_agent"),
        identity=_runtime_identity(),
        enable_auth=enable_auth,
    )
    calls = []
    runner = _RecordingRunner(calls)

    async def get_runner_async(app_name):
        return runner

    server.server.get_runner_async = get_runner_async
    return server, calls


def test_real_app_rejects_missing_invalid_and_unbound_requests():
    server, _ = _server_with_recording_runner()
    with TestClient(server.app) as client:
        assert client.post("/invoke", json={"prompt": "hello"}).status_code == 401
        assert (
            client.post(
                "/invoke",
                headers={"Authorization": "Bearer invalid.jwt.value"},
                json={"prompt": "hello"},
            ).status_code
            == 401
        )
        headers = {"Authorization": "Bearer valid.jwt.value"}
        assert client.get("/future-admin-route", headers=headers).status_code == 403
        assert (
            client.get(AGENT_CARD_WELL_KNOWN_PATH, headers=headers).status_code == 403
        )


def test_invoke_uses_verified_subject_for_session_and_stream_lifetime():
    server, calls = _server_with_recording_runner()
    with TestClient(server.app) as client:
        response = client.post(
            "/invoke",
            headers={
                "Authorization": "Bearer valid.jwt.value",
                "user_id": "mallory",
                "session_id": "invoke-session",
            },
            json={"prompt": "hello"},
        )
    assert response.status_code == 200
    assert calls == [{"user_id": "alice", "identity_sub": "alice"}]
    session = asyncio.run(
        server.server.session_service.get_session(
            app_name="identity_integration_agent",
            user_id="alice",
            session_id="invoke-session",
        )
    )
    assert session is not None


def test_run_sse_uses_verified_subject_for_existing_session():
    server, calls = _server_with_recording_runner()
    asyncio.run(
        server.server.session_service.create_session(
            app_name="identity_integration_agent",
            user_id="alice",
            session_id="sse-session",
        )
    )
    with TestClient(server.app) as client:
        response = client.post(
            "/run_sse",
            headers={"Authorization": "Bearer valid.jwt.value"},
            json={
                "appName": "identity_integration_agent",
                "userId": "mallory",
                "sessionId": "sse-session",
                "newMessage": {"role": "user", "parts": [{"text": "hello"}]},
                "streaming": True,
            },
        )
    assert response.status_code == 200
    assert calls == [{"user_id": "alice", "identity_sub": "alice"}]


def test_run_sse_inbound_auth_uses_body_user_id_without_identity():
    server = AgentkitAgentServerApp(
        agent=BaseAgent(name="run_sse_inbound_auth_agent"),
        enable_auth=True,
    )
    asyncio.run(
        server.server.session_service.create_session(
            app_name="run_sse_inbound_auth_agent",
            user_id="body-user",
            session_id="sse-session",
        )
    )

    class _Runner:
        def run_async(self, **kwargs):
            async def events():
                if False:
                    yield None

            return events()

    async def get_runner_async(app_name):
        return _Runner()

    server.server.get_runner_async = get_runner_async

    with TestClient(server.app) as client:
        response = client.post(
            "/run_sse",
            headers={
                "user_id": "header-user",
                "X-Ve-TIP-Token": "tip-secret",
            },
            json={
                "appName": "run_sse_inbound_auth_agent",
                "userId": "body-user",
                "sessionId": "sse-session",
                "newMessage": {"role": "user", "parts": [{"text": "hello"}]},
                "streaming": True,
            },
        )

    assert response.status_code == 200
    credential = asyncio.run(
        server.server.credential_service.get_credential(
            app_name="run_sse_inbound_auth_agent",
            user_id="body-user",
            credential_key="ve_tip_token",
        )
    )
    assert credential.api_key == "tip-secret"
    header_credential = asyncio.run(
        server.server.credential_service.get_credential(
            app_name="run_sse_inbound_auth_agent",
            user_id="header-user",
            credential_key="ve_tip_token",
        )
    )
    assert header_credential is None


def test_run_sse_inbound_auth_uses_verified_subject_for_credentials():
    server, calls = _server_with_recording_runner(enable_auth=True)
    asyncio.run(
        server.server.session_service.create_session(
            app_name="identity_integration_agent",
            user_id="alice",
            session_id="sse-session",
        )
    )
    with TestClient(server.app) as client:
        response = client.post(
            "/run_sse",
            headers={
                "Authorization": "Bearer valid.jwt.value",
                "X-Ve-TIP-Token": "tip-secret",
            },
            json={
                "appName": "identity_integration_agent",
                "userId": "mallory",
                "sessionId": "sse-session",
                "newMessage": {"role": "user", "parts": [{"text": "hello"}]},
                "streaming": True,
            },
        )

    assert response.status_code == 200
    assert calls == [{"user_id": "alice", "identity_sub": "alice"}]
    credential = asyncio.run(
        server.server.credential_service.get_credential(
            app_name="identity_integration_agent",
            user_id="alice",
            credential_key="ve_tip_token",
        )
    )
    assert credential.api_key == "tip-secret"
    auth_credential = asyncio.run(
        server.server.credential_service.get_credential(
            app_name="identity_integration_agent",
            user_id="alice",
            credential_key="inbound_auth",
        )
    )
    assert auth_credential.http.scheme == "bearer"
    assert auth_credential.http.credentials.token == "valid.jwt.value"
    mallory_credential = asyncio.run(
        server.server.credential_service.get_credential(
            app_name="identity_integration_agent",
            user_id="mallory",
            credential_key="ve_tip_token",
        )
    )
    assert mallory_credential is None


def test_invoke_inbound_auth_captures_authorization_before_identity_scrub():
    server, calls = _server_with_recording_runner(enable_auth=True)
    with TestClient(server.app) as client:
        response = client.post(
            "/invoke",
            headers={
                "Authorization": "Bearer valid.jwt.value",
                "user_id": "mallory",
                "session_id": "invoke-session",
            },
            json={"prompt": "hello"},
        )

    assert response.status_code == 200
    assert calls == [{"user_id": "alice", "identity_sub": "alice"}]
    credential = asyncio.run(
        server.server.credential_service.get_credential(
            app_name="identity_integration_agent",
            user_id="alice",
            credential_key="inbound_auth",
        )
    )
    assert credential.http.scheme == "bearer"
    assert credential.http.credentials.token == "valid.jwt.value"
    mallory_credential = asyncio.run(
        server.server.credential_service.get_credential(
            app_name="identity_integration_agent",
            user_id="mallory",
            credential_key="inbound_auth",
        )
    )
    assert mallory_credential is None


def test_identity_none_preserves_the_existing_unauthenticated_app_surface():
    server = AgentkitAgentServerApp(agent=BaseAgent(name="legacy_agent"))
    with TestClient(server.app) as client:
        assert client.get("/list-apps").json() == ["legacy_agent"]
        assert client.get(AGENT_CARD_WELL_KNOWN_PATH).status_code == 200


def test_identity_mode_never_falls_back_to_caller_user_without_bound_context():
    server, _ = _server_with_recording_runner()
    server.app.user_middleware = [
        middleware
        for middleware in server.app.user_middleware
        if middleware.cls.__name__ != "AgentIdentityMiddleware"
    ]
    server.app.middleware_stack = None

    with TestClient(server.app, raise_server_exceptions=False) as client:
        response = client.post(
            "/invoke",
            headers={"user_id": "mallory", "session_id": "unbound-session"},
            json={"prompt": "hello"},
        )

    assert response.status_code == 500
    session = asyncio.run(
        server.server.session_service.get_session(
            app_name="identity_integration_agent",
            user_id="mallory",
            session_id="unbound-session",
        )
    )
    assert session is None


def test_identity_mode_does_not_return_or_log_arbitrary_agent_errors(caplog):
    secret = "Bearer tip.jwt.must-not-leak"
    server, _ = _server_with_recording_runner()

    class _FailingRunner:
        def run_async(self, **kwargs):
            async def events():
                raise RuntimeError(secret)
                yield None

            return events()

    async def get_runner_async(app_name):
        return _FailingRunner()

    server.server.get_runner_async = get_runner_async
    with TestClient(server.app) as client:
        response = client.post(
            "/invoke",
            headers={"Authorization": "Bearer valid.jwt.value"},
            json={"prompt": "hello"},
        )
    assert response.status_code == 200
    assert secret not in response.text
    assert "agent execution failed" in response.text
    assert secret not in caplog.text


def test_native_run_diagnostics_keeps_identity_v1_route_denied():
    server, calls = _server_with_recording_runner()
    with TestClient(server.app) as client:
        response = client.post(
            "/run",
            headers={"Authorization": "Bearer valid.jwt.value"},
            json={
                "appName": "identity_integration_agent",
                "userId": "mallory",
                "sessionId": "run-session",
                "agentkitDiagnosticRunId": "identity-run",
                "newMessage": {"role": "user", "parts": [{"text": "hello"}]},
            },
        )
    # Identity V1 未授权原生 /run；补观测不能扩大其允许访问的路由范围。
    assert response.status_code == 403
    assert calls == []

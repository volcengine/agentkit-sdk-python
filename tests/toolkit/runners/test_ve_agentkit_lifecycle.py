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

from __future__ import annotations

import pytest

import agentkit.sdk.runtime.types as runtime_types
from agentkit.toolkit.config import CommonConfig
from agentkit.toolkit.errors import ErrorCode
from agentkit.toolkit.runners.ve_agentkit import (
    VeAgentkitRuntimeRunner,
    VeAgentkitRunnerConfig,
    RUNTIME_STATUS_READY,
    RUNTIME_STATUS_ERROR,
    RUNTIME_STATUS_UNRELEASED,
    ARTIFACT_TYPE_DOCKER_IMAGE,
    AUTH_TYPE_KEY_AUTH,
    AUTH_TYPE_CUSTOM_JWT,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _make_runtime(
    *,
    runtime_id="r-1",
    status=RUNTIME_STATUS_READY,
    artifact_type=ARTIFACT_TYPE_DOCKER_IMAGE,
    artifact_url="reg/img:tag",
    name="rt-name",
    api_key=None,
    public_endpoint="https://public.example/",
    failed_log_file_url=None,
):
    """Build a real GetRuntimeResponse pydantic object matching the API shape."""
    authorizer = None
    if api_key is not None:
        authorizer = runtime_types.AuthorizerConfigurationForGetRuntime(
            KeyAuth=runtime_types.KeyAuthForGetRuntime(ApiKey=api_key)
        )
    net = []
    if public_endpoint is not None:
        net.append(
            runtime_types.NetworkConfigurationsForGetRuntime(
                NetworkType="public", Endpoint=public_endpoint
            )
        )
    return runtime_types.GetRuntimeResponse(
        RuntimeId=runtime_id,
        Status=status,
        ArtifactType=artifact_type,
        ArtifactUrl=artifact_url,
        Name=name,
        AuthorizerConfiguration=authorizer,
        NetworkConfigurations=net,
        FailedLogFileUrl=failed_log_file_url,
    )


class _FakeRuntimeClient:
    """Records calls; get_runtime returns a scripted sequence of statuses.

    ``get_runtime_responses`` is a list of runtime objects (or exceptions) served
    one-per-call; the last element is repeated once exhausted so polling loops
    that call more times than scripted keep seeing the terminal state.
    """

    def __init__(
        self,
        *,
        create_response=None,
        get_runtime_responses=None,
        get_runtime_exc=None,
    ):
        self._create_response = create_response
        self._get_seq = list(get_runtime_responses or [])
        self._get_runtime_exc = get_runtime_exc
        self.create_calls = []
        self.get_calls = []
        self.update_calls = []
        self.release_calls = []
        self.delete_calls = []

    def create_runtime(self, req):
        self.create_calls.append(req)
        return self._create_response

    def get_runtime(self, req):
        self.get_calls.append(req)
        if self._get_runtime_exc is not None:
            raise self._get_runtime_exc
        if not self._get_seq:
            raise AssertionError("get_runtime called with no scripted responses")
        if len(self._get_seq) == 1:
            return self._get_seq[0]
        return self._get_seq.pop(0)

    def update_runtime(self, req):
        self.update_calls.append(req)
        return runtime_types.UpdateRuntimeResponse(RuntimeId=req.runtime_id)

    def release_runtime(self, req):
        self.release_calls.append(req)
        return runtime_types.ReleaseRuntimeResponse(RuntimeId=req.runtime_id)

    def delete_runtime(self, req):
        self.delete_calls.append(req)
        return runtime_types.DeleteRuntimeResponse(RuntimeId=req.runtime_id)


class _RecordingReporter:
    """Reporter double that records confirm() prompts and show_logs() calls."""

    def __init__(self, confirm_return=False):
        self.confirm_return = confirm_return
        self.confirm_calls = []
        self.show_logs_calls = []
        self.long_task_descriptions = []

    def info(self, message, **kwargs):
        pass

    def success(self, message, **kwargs):
        pass

    def warning(self, message, **kwargs):
        pass

    def error(self, message, **kwargs):
        pass

    def progress(self, message, current, total=100, **kwargs):
        pass

    def confirm(self, message, default=False, **kwargs):
        self.confirm_calls.append((message, default))
        return self.confirm_return

    def show_logs(self, title, lines, max_lines=100):
        self.show_logs_calls.append((title, list(lines), max_lines))

    class _Task:
        def update(self, description=None, completed=None):
            pass

    from contextlib import contextmanager as _cm

    @_cm
    def long_task(self, description, total=100):
        self.long_task_descriptions.append(description)
        yield _RecordingReporter._Task()


class _FakeResponse:
    def __init__(self, content=b"log line 1\nlog line 2\n"):
        self.content = content

    def raise_for_status(self):
        pass


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    """Neutralise all real waiting inside the ve_agentkit module."""
    import agentkit.toolkit.runners.ve_agentkit as mod

    monkeypatch.setattr(mod.time, "sleep", lambda *a, **k: None)
    # deterministic client token so request construction is reproducible
    monkeypatch.setattr(mod, "generate_client_token", lambda: "tok-fixed")


def _make_config(**overrides):
    cfg = VeAgentkitRunnerConfig(
        common_config=CommonConfig(),
        runtime_name="my-runtime",
        runtime_role_name="role-x",
        image_url="reg/img:tag",
        region="cn-beijing",
        runtime_auth_type=AUTH_TYPE_KEY_AUTH,
        runtime_apikey_name="apikey-name-x",
        min_instance=2,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _install_client(monkeypatch, runner, client):
    monkeypatch.setattr(runner, "_get_runtime_client", lambda region="": client)


def _freeze_time(monkeypatch, values):
    """Make ve_agentkit's time.time() return the given sequence, then hold last."""
    import agentkit.toolkit.runners.ve_agentkit as mod

    seq = list(values)

    def _time():
        if len(seq) == 1:
            return seq[0]
        return seq.pop(0)

    monkeypatch.setattr(mod.time, "time", _time)


# ---------------------------------------------------------------------------
# _create_new_runtime
# ---------------------------------------------------------------------------


def test_create_new_runtime_happy_path_builds_request_and_returns_ready_metadata(
    monkeypatch,
):
    runner = VeAgentkitRuntimeRunner()
    ready = _make_runtime(
        runtime_id="rt-new", status=RUNTIME_STATUS_READY, api_key="secret-key"
    )
    client = _FakeRuntimeClient(
        create_response=runtime_types.CreateRuntimeResponse(RuntimeId="rt-new"),
        get_runtime_responses=[ready],
    )
    _install_client(monkeypatch, runner, client)

    cfg = _make_config(runtime_envs={"FOO": "bar"})
    result = runner._create_new_runtime(cfg)

    # Behaviour: a CreateRuntimeRequest was actually submitted with the mapped fields.
    assert len(client.create_calls) == 1
    req = client.create_calls[0]
    assert isinstance(req, runtime_types.CreateRuntimeRequest)
    assert req.name == "my-runtime"
    assert req.artifact_type == ARTIFACT_TYPE_DOCKER_IMAGE
    assert req.artifact_url == "reg/img:tag"
    assert req.role_name == "role-x"
    assert req.min_instance == 2
    assert req.client_token == "tok-fixed"
    assert req.apmplus_enable is True
    # env mapping into EnvsItemForCreateRuntime
    assert [(e.key, e.value) for e in req.envs] == [("FOO", "bar")]
    # key_auth branch built a key_auth authorizer (not custom jwt)
    assert req.authorizer_configuration.key_auth is not None
    assert req.authorizer_configuration.custom_jwt_authorizer is None

    # Runtime id is captured from create response and returned.
    assert cfg.runtime_id == "rt-new"

    # Success DeployResult with endpoint + metadata mapping.
    assert result.success is True
    assert result.error_code is None
    assert result.service_id == "rt-new"
    assert result.endpoint_url == "https://public.example/"
    assert result.metadata["runtime_id"] == "rt-new"
    assert result.metadata["runtime_auth_type"] == AUTH_TYPE_KEY_AUTH
    assert result.metadata["message"] == "Runtime created successfully"
    # key_auth mode pulls the api key off the ready runtime.
    assert cfg.runtime_apikey == "secret-key"
    assert result.metadata["runtime_apikey"] == "secret-key"


def test_create_new_runtime_custom_jwt_does_not_fetch_api_key(monkeypatch):
    runner = VeAgentkitRuntimeRunner()
    ready = _make_runtime(runtime_id="rt-jwt", api_key="should-not-be-read")
    client = _FakeRuntimeClient(
        create_response=runtime_types.CreateRuntimeResponse(RuntimeId="rt-jwt"),
        get_runtime_responses=[ready],
    )
    _install_client(monkeypatch, runner, client)

    cfg = _make_config(
        runtime_auth_type=AUTH_TYPE_CUSTOM_JWT,
        runtime_jwt_discovery_url="https://issuer/.well-known",
        runtime_jwt_allowed_clients=["client-a"],
    )
    result = runner._create_new_runtime(cfg)

    req = client.create_calls[0]
    assert req.authorizer_configuration.custom_jwt_authorizer is not None
    assert (
        req.authorizer_configuration.custom_jwt_authorizer.discovery_url
        == "https://issuer/.well-known"
    )
    assert result.success is True
    # custom_jwt path leaves runtime_apikey untouched (stays default empty string)
    assert cfg.runtime_apikey == ""


def test_create_new_runtime_init_failure_downloads_logs_and_cleans_up_when_confirmed(
    monkeypatch, tmp_path
):
    reporter = _RecordingReporter(confirm_return=True)
    runner = VeAgentkitRuntimeRunner(reporter=reporter)

    errored = _make_runtime(
        runtime_id="rt-bad",
        status=RUNTIME_STATUS_ERROR,
        failed_log_file_url="https://logs.example/failed.log",
    )
    client = _FakeRuntimeClient(
        create_response=runtime_types.CreateRuntimeResponse(RuntimeId="rt-bad"),
        get_runtime_responses=[errored],
    )
    _install_client(monkeypatch, runner, client)

    # Redirect log-file writes into tmp_path and capture the download call.
    monkeypatch.chdir(tmp_path)
    import agentkit.toolkit.runners.ve_agentkit as mod

    get_calls = []

    def _fake_get(url, timeout=None):
        get_calls.append((url, timeout))
        return _FakeResponse()

    monkeypatch.setattr(mod.requests, "get", _fake_get)

    cfg = _make_config()
    result = runner._create_new_runtime(cfg)

    # Init failure -> RUNTIME_NOT_READY with the runtime id preserved.
    assert result.success is False
    assert result.error_code == ErrorCode.RUNTIME_NOT_READY
    assert result.service_id == "rt-bad"

    # Failure-log download was attempted against the failed_log_file_url.
    assert get_calls == [("https://logs.example/failed.log", 30)]
    assert reporter.show_logs_calls  # logs were shown
    # A cleanup confirmation was requested, defaulting to False.
    assert reporter.confirm_calls and reporter.confirm_calls[0][1] is False
    # Confirmed -> delete_runtime called with the failed runtime id.
    assert len(client.delete_calls) == 1
    assert client.delete_calls[0].runtime_id == "rt-bad"


def test_create_new_runtime_init_failure_skips_cleanup_when_declined(monkeypatch):
    reporter = _RecordingReporter(confirm_return=False)
    runner = VeAgentkitRuntimeRunner(reporter=reporter)

    # No failed_log_file_url -> download is short-circuited (no requests.get needed).
    errored = _make_runtime(
        runtime_id="rt-bad2",
        status=RUNTIME_STATUS_ERROR,
        failed_log_file_url=None,
    )
    client = _FakeRuntimeClient(
        create_response=runtime_types.CreateRuntimeResponse(RuntimeId="rt-bad2"),
        get_runtime_responses=[errored],
    )
    _install_client(monkeypatch, runner, client)

    cfg = _make_config()
    result = runner._create_new_runtime(cfg)

    assert result.success is False
    assert result.error_code == ErrorCode.RUNTIME_NOT_READY
    # Declined cleanup -> no delete call.
    assert client.delete_calls == []
    # No log url -> show_logs never invoked.
    assert reporter.show_logs_calls == []


def test_create_new_runtime_exception_maps_to_runtime_create_failed(monkeypatch):
    runner = VeAgentkitRuntimeRunner()

    class _BoomClient(_FakeRuntimeClient):
        def create_runtime(self, req):
            raise RuntimeError("boom from create")

    client = _BoomClient()
    _install_client(monkeypatch, runner, client)

    cfg = _make_config()
    result = runner._create_new_runtime(cfg)

    assert result.success is False
    assert result.error_code == ErrorCode.RUNTIME_CREATE_FAILED
    assert "boom from create" in result.error


# ---------------------------------------------------------------------------
# _wait_for_runtime_status / _wait_for_runtime_status_multiple
# ---------------------------------------------------------------------------


def test_wait_for_status_returns_success_when_target_reached(monkeypatch):
    runner = VeAgentkitRuntimeRunner()
    ready = _make_runtime(status=RUNTIME_STATUS_READY)
    client = _FakeRuntimeClient(get_runtime_responses=[ready])
    _install_client(monkeypatch, runner, client)

    ok, runtime, err = runner._wait_for_runtime_status(
        runtime_id="r-1",
        target_status=RUNTIME_STATUS_READY,
        task_description="waiting",
        timeout=600,
    )

    assert ok is True
    assert err is None
    assert runtime is ready
    # Only one poll needed since first status already matched.
    assert len(client.get_calls) == 1
    assert client.get_calls[0].runtime_id == "r-1"


def test_wait_for_status_polls_until_target_reached(monkeypatch):
    runner = VeAgentkitRuntimeRunner()
    creating = _make_runtime(status="Creating")
    ready = _make_runtime(status=RUNTIME_STATUS_READY)
    client = _FakeRuntimeClient(get_runtime_responses=[creating, creating, ready])
    _install_client(monkeypatch, runner, client)
    # keep elapsed small so timeout never trips
    _freeze_time(monkeypatch, [1000.0, 1001.0, 1002.0, 1003.0, 1004.0, 1005.0])

    ok, runtime, err = runner._wait_for_runtime_status(
        runtime_id="r-1",
        target_status=RUNTIME_STATUS_READY,
        task_description="waiting",
        timeout=600,
    )

    assert ok is True
    assert runtime.status == RUNTIME_STATUS_READY
    assert len(client.get_calls) == 3


def test_wait_for_status_error_status_returns_failure(monkeypatch):
    runner = VeAgentkitRuntimeRunner()
    errored = _make_runtime(status=RUNTIME_STATUS_ERROR)
    client = _FakeRuntimeClient(get_runtime_responses=[errored])
    _install_client(monkeypatch, runner, client)

    ok, runtime, err = runner._wait_for_runtime_status(
        runtime_id="r-1",
        target_status=RUNTIME_STATUS_READY,
        task_description="waiting",
        timeout=600,
        error_message="Initialization failed",
    )

    assert ok is False
    assert runtime is errored
    assert "Runtime status is Error" in err
    assert "Initialization failed" in err


def test_wait_for_status_timeout_returns_timeout_message(monkeypatch):
    runner = VeAgentkitRuntimeRunner()
    creating = _make_runtime(status="Creating")
    client = _FakeRuntimeClient(get_runtime_responses=[creating])
    _install_client(monkeypatch, runner, client)
    # start_time=0; first elapsed read = 999 (> timeout 10) -> timeout branch.
    _freeze_time(monkeypatch, [0.0, 999.0])

    ok, runtime, err = runner._wait_for_runtime_status(
        runtime_id="r-1",
        target_status=RUNTIME_STATUS_READY,
        task_description="waiting",
        timeout=10,
        error_message="Initialization failed",
    )

    assert ok is False
    assert runtime is creating
    assert "timeout after 10s" in err
    # Non-terminal status: it polled once then timed out (no sleep loop since patched).
    assert len(client.get_calls) == 1


def test_wait_for_status_multiple_accepts_any_target(monkeypatch):
    runner = VeAgentkitRuntimeRunner()
    unreleased = _make_runtime(status=RUNTIME_STATUS_UNRELEASED)
    client = _FakeRuntimeClient(get_runtime_responses=[unreleased])
    _install_client(monkeypatch, runner, client)

    ok, runtime, err = runner._wait_for_runtime_status_multiple(
        runtime_id="r-1",
        target_statuses=[RUNTIME_STATUS_UNRELEASED, RUNTIME_STATUS_READY],
        task_description="waiting",
        timeout=600,
    )

    assert ok is True
    assert runtime.status == RUNTIME_STATUS_UNRELEASED


# ---------------------------------------------------------------------------
# _update_existing_runtime
# ---------------------------------------------------------------------------


def test_update_existing_runtime_not_found_returns_resource_not_found(monkeypatch):
    runner = VeAgentkitRuntimeRunner()
    client = _FakeRuntimeClient(
        get_runtime_exc=RuntimeError("InvalidAgentKitRuntime.NotFound: gone")
    )
    _install_client(monkeypatch, runner, client)

    cfg = _make_config(runtime_id="r-missing")
    result = runner._update_existing_runtime(cfg)

    assert result.success is False
    assert result.error_code == ErrorCode.RESOURCE_NOT_FOUND
    assert result.service_id == "r-missing"
    # No update was attempted.
    assert client.update_calls == []


def test_update_existing_runtime_wrong_artifact_type_returns_config_invalid(monkeypatch):
    runner = VeAgentkitRuntimeRunner()
    # artifact_type is not the docker image type -> CONFIG_INVALID guard.
    existing = _make_runtime(runtime_id="r-code", artifact_type="code")
    client = _FakeRuntimeClient(get_runtime_responses=[existing])
    _install_client(monkeypatch, runner, client)

    cfg = _make_config(runtime_id="r-code")
    result = runner._update_existing_runtime(cfg)

    assert result.success is False
    assert result.error_code == ErrorCode.CONFIG_INVALID
    assert "code" in result.error
    assert client.update_calls == []


def test_update_existing_runtime_other_get_error_maps_to_deploy_failed(monkeypatch):
    runner = VeAgentkitRuntimeRunner()
    # A non-NotFound error is re-raised and caught by the outer handler.
    client = _FakeRuntimeClient(get_runtime_exc=RuntimeError("network exploded"))
    _install_client(monkeypatch, runner, client)

    cfg = _make_config(runtime_id="r-x")
    result = runner._update_existing_runtime(cfg)

    assert result.success is False
    assert result.error_code == ErrorCode.DEPLOY_FAILED
    assert "network exploded" in result.error


def test_update_existing_runtime_direct_to_ready_submits_update_and_skips_release(
    monkeypatch,
):
    runner = VeAgentkitRuntimeRunner()
    existing = _make_runtime(runtime_id="r-up", status=RUNTIME_STATUS_READY, name="orig-name")
    # get_runtime is called: once for the initial fetch, then by the wait loop.
    ready_after_update = _make_runtime(
        runtime_id="r-up", status=RUNTIME_STATUS_READY, api_key="k-updated"
    )
    client = _FakeRuntimeClient(
        get_runtime_responses=[existing, ready_after_update]
    )
    _install_client(monkeypatch, runner, client)

    cfg = _make_config(
        runtime_id="r-up",
        runtime_envs={"A": "1"},
        runtime_bindings={"memory_id": "mem-1", "knowledge_id": ""},
    )
    result = runner._update_existing_runtime(cfg)

    # An update request was submitted with mapped fields.
    assert len(client.update_calls) == 1
    ureq = client.update_calls[0]
    assert isinstance(ureq, runtime_types.UpdateRuntimeRequest)
    assert ureq.runtime_id == "r-up"
    assert ureq.artifact_url == "reg/img:tag"
    assert ureq.memory_id == "mem-1"
    # empty-string binding -> explicit clear ("")
    assert ureq.knowledge_id == ""
    # binding key absent -> None (not sent)
    assert ureq.tool_id is None
    # After the fix: UpdateRuntimeRequest now defines a client_token field
    # (matching CreateRuntimeRequest), so the idempotency token supplied by
    # _update_existing_runtime is retained instead of being silently dropped.
    assert isinstance(ureq.client_token, str) and ureq.client_token

    # Reached Ready directly -> no release step.
    assert client.release_calls == []

    assert result.success is True
    assert result.error_code is None
    assert result.service_id == "r-up"
    assert result.endpoint_url == "https://public.example/"
    # metadata prefers the fetched runtime's name over config's runtime_name.
    assert result.metadata["runtime_name"] == "orig-name"
    assert result.metadata["message"] == "Runtime update completed"
    # key_auth mode pulls apikey from the updated runtime.
    assert cfg.runtime_apikey == "k-updated"


def test_update_existing_runtime_unreleased_triggers_release_then_ready(monkeypatch):
    runner = VeAgentkitRuntimeRunner()
    existing = _make_runtime(runtime_id="r-rel", status=RUNTIME_STATUS_READY)
    unreleased = _make_runtime(runtime_id="r-rel", status=RUNTIME_STATUS_UNRELEASED)
    released_ready = _make_runtime(runtime_id="r-rel", status=RUNTIME_STATUS_READY)
    # 1: initial get, 2: post-update wait (UnReleased), 3: post-release wait (Ready)
    client = _FakeRuntimeClient(
        get_runtime_responses=[existing, unreleased, released_ready]
    )
    _install_client(monkeypatch, runner, client)

    cfg = _make_config(runtime_id="r-rel")
    result = runner._update_existing_runtime(cfg)

    # Phase 2 release path exercised.
    assert len(client.release_calls) == 1
    assert client.release_calls[0].runtime_id == "r-rel"
    assert result.success is True
    assert result.error_code is None


def test_update_existing_runtime_update_wait_error_returns_deploy_failed(monkeypatch):
    reporter = _RecordingReporter()
    runner = VeAgentkitRuntimeRunner(reporter=reporter)
    existing = _make_runtime(runtime_id="r-fail", status=RUNTIME_STATUS_READY)
    errored = _make_runtime(
        runtime_id="r-fail",
        status=RUNTIME_STATUS_ERROR,
        failed_log_file_url=None,
    )
    client = _FakeRuntimeClient(get_runtime_responses=[existing, errored])
    _install_client(monkeypatch, runner, client)

    cfg = _make_config(runtime_id="r-fail")
    result = runner._update_existing_runtime(cfg)

    assert result.success is False
    assert result.error_code == ErrorCode.DEPLOY_FAILED
    assert result.service_id == "r-fail"
    # Update was submitted, but no release happened after the failed wait.
    assert len(client.update_calls) == 1
    assert client.release_calls == []


def test_update_existing_runtime_release_wait_failure_returns_deploy_failed(monkeypatch):
    runner = VeAgentkitRuntimeRunner()
    existing = _make_runtime(runtime_id="r-rf", status=RUNTIME_STATUS_READY)
    unreleased = _make_runtime(runtime_id="r-rf", status=RUNTIME_STATUS_UNRELEASED)
    # Release phase wait ends in Error -> phase-2 failure path.
    release_error = _make_runtime(
        runtime_id="r-rf", status=RUNTIME_STATUS_ERROR, failed_log_file_url=None
    )
    client = _FakeRuntimeClient(
        get_runtime_responses=[existing, unreleased, release_error]
    )
    _install_client(monkeypatch, runner, client)

    cfg = _make_config(runtime_id="r-rf")
    result = runner._update_existing_runtime(cfg)

    # Release was attempted, but the subsequent wait failed.
    assert len(client.release_calls) == 1
    assert result.success is False
    assert result.error_code == ErrorCode.DEPLOY_FAILED
    assert result.service_id == "r-rf"


def test_update_existing_runtime_warns_and_ignores_network_and_clears_none_binding(
    monkeypatch,
):
    reporter = _RecordingReporter()
    runner = VeAgentkitRuntimeRunner(reporter=reporter)
    existing = _make_runtime(runtime_id="r-net", status=RUNTIME_STATUS_READY)
    ready = _make_runtime(runtime_id="r-net", status=RUNTIME_STATUS_READY)
    client = _FakeRuntimeClient(get_runtime_responses=[existing, ready])
    _install_client(monkeypatch, runner, client)

    cfg = _make_config(
        runtime_id="r-net",
        runtime_network={"mode": "public"},
        # None value -> explicit clear ("")
        runtime_bindings={"tool_id": None},
    )
    result = runner._update_existing_runtime(cfg)

    assert result.success is True
    ureq = client.update_calls[0]
    # None binding -> explicit clear ("")
    assert ureq.tool_id == ""
    # runtime_network is ignored on update (network only applies to create),
    # so no NetworkConfiguration is sent as part of the update request.
    assert not hasattr(ureq, "network_configuration") or ureq.network_configuration is None

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

import importlib
import os
from types import SimpleNamespace

import pytest


@pytest.fixture
def harness_deploy_spy(monkeypatch):
    deploy_module = importlib.import_module("agentkit.toolkit.harness.deploy")
    lifecycle_module = importlib.import_module("agentkit.toolkit.sdk.lifecycle")
    runtime_client_module = importlib.import_module("agentkit.sdk.runtime.client")
    config_utils = importlib.import_module("agentkit.toolkit.config.utils")

    captured = {}

    class FakeRuntimeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        def create_runtime(self, request):
            raise AssertionError("create_runtime should be handled by the fake launch")

    def fake_launch(**kwargs):
        captured["config_dict"] = kwargs["config_dict"]
        captured["excluded_env"] = set(config_utils.COMPAT_ENV_EXCLUDE)
        provider = kwargs["config_dict"]["common"]["cloud_provider"]
        provider_prefix = "BYTEPLUS" if provider == "byteplus" else "VOLCENGINE"
        captured["deploy_env"] = {
            key: os.getenv(key)
            for key in (
                "VOLC_ACCESSKEY",
                "VOLC_SECRETKEY",
                "VOLC_SESSIONTOKEN",
                f"{provider_prefix}_ACCESS_KEY",
                f"{provider_prefix}_SECRET_KEY",
                f"{provider_prefix}_SESSION_TOKEN",
            )
        }
        return SimpleNamespace(success=False)

    monkeypatch.setattr(
        runtime_client_module, "AgentkitRuntimeClient", FakeRuntimeClient
    )
    monkeypatch.setattr(deploy_module, "_find_runtimes_by_name", lambda *_args: [])
    monkeypatch.setattr(lifecycle_module, "launch", fake_launch)
    return deploy_module, captured


@pytest.mark.parametrize(
    (
        "provider",
        "access_key_name",
        "secret_key_name",
        "session_token_name",
        "region_name",
        "region",
    ),
    [
        (
            "volcengine",
            "VOLCENGINE_ACCESS_KEY",
            "VOLCENGINE_SECRET_KEY",
            "VOLCENGINE_SESSION_TOKEN",
            "VOLCENGINE_REGION",
            "cn-beijing",
        ),
        (
            "byteplus",
            "BYTEPLUS_ACCESS_KEY",
            "BYTEPLUS_SECRET_KEY",
            "BYTEPLUS_SESSION_TOKEN",
            "BYTEPLUS_REGION",
            "ap-southeast-1",
        ),
    ],
)
def test_deploy_harness_resolves_provider_credentials_and_region(
    tmp_path,
    monkeypatch,
    harness_deploy_spy,
    provider,
    access_key_name,
    secret_key_name,
    session_token_name,
    region_name,
    region,
):
    deploy_module, captured = harness_deploy_spy
    (tmp_path / "demo.harness.json").write_text("{}")

    for key in (
        "VOLCENGINE_ACCESS_KEY",
        "VOLCENGINE_SECRET_KEY",
        "VOLCENGINE_SESSION_TOKEN",
        "VOLCENGINE_REGION",
        "VOLC_ACCESSKEY",
        "VOLC_SECRETKEY",
        "VOLC_SESSIONTOKEN",
        "BYTEPLUS_ACCESS_KEY",
        "BYTEPLUS_SECRET_KEY",
        "BYTEPLUS_SESSION_TOKEN",
        "BYTEPLUS_REGION",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("CLOUD_PROVIDER", provider)
    monkeypatch.setenv(access_key_name, "test-ak")
    monkeypatch.setenv(secret_key_name, "test-sk")
    monkeypatch.setenv(session_token_name, "test-token")
    monkeypatch.setenv(region_name, region)

    deploy_module.deploy_harness("demo", tmp_path)

    assert captured["client_kwargs"] == {
        "access_key": "test-ak",
        "secret_key": "test-sk",
        "region": region,
        "session_token": "test-token",
    }
    assert captured["config_dict"]["common"]["cloud_provider"] == provider
    assert captured["config_dict"]["launch_types"]["cloud"]["region"] == region
    assert captured["excluded_env"] >= {
        access_key_name,
        secret_key_name,
        session_token_name,
    }
    assert captured["deploy_env"] == {
        "VOLC_ACCESSKEY": "test-ak",
        "VOLC_SECRETKEY": "test-sk",
        "VOLC_SESSIONTOKEN": "test-token",
        access_key_name: "test-ak",
        secret_key_name: "test-sk",
        session_token_name: "test-token",
    }
    assert os.getenv("VOLC_ACCESSKEY") is None
    assert os.getenv("VOLC_SECRETKEY") is None
    assert os.getenv("VOLC_SESSIONTOKEN") is None


def test_deploy_harness_maps_explicit_credentials_for_byteplus(
    tmp_path, monkeypatch, harness_deploy_spy
):
    deploy_module, captured = harness_deploy_spy
    (tmp_path / "demo.harness.json").write_text("{}")

    monkeypatch.setenv("CLOUD_PROVIDER", "byteplus")
    monkeypatch.setenv("BYTEPLUS_REGION", "ap-southeast-1")
    for key in (
        "VOLCENGINE_ACCESS_KEY",
        "VOLCENGINE_SECRET_KEY",
        "VOLCENGINE_SESSION_TOKEN",
        "VOLC_ACCESSKEY",
        "VOLC_SECRETKEY",
        "VOLC_SESSIONTOKEN",
        "BYTEPLUS_ACCESS_KEY",
        "BYTEPLUS_SECRET_KEY",
        "BYTEPLUS_SESSION_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)

    deploy_module.deploy_harness(
        "demo", tmp_path, access_key="explicit-ak", secret_key="explicit-sk"
    )

    assert captured["client_kwargs"]["access_key"] == "explicit-ak"
    assert captured["client_kwargs"]["secret_key"] == "explicit-sk"
    assert captured["config_dict"]["common"]["cloud_provider"] == "byteplus"
    assert captured["deploy_env"]["BYTEPLUS_ACCESS_KEY"] == "explicit-ak"
    assert captured["deploy_env"]["BYTEPLUS_SECRET_KEY"] == "explicit-sk"

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

import pytest
from fastapi import FastAPI

from agentkit.apps.agent_server_app.origin import (
    DEFAULT_AGENTKIT_ALLOW_ORIGINS,
    add_cors_compat_middleware,
    resolve_agentkit_allow_origins,
    split_allow_origins,
    supports_get_fast_api_kwarg,
)


def test_resolve_allow_origins_defaults_to_wildcard(monkeypatch):
    monkeypatch.delenv("AGENTKIT_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("ADK_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("AGENTKIT_DISABLE_DEFAULT_ALLOW_ORIGINS", raising=False)

    assert (
        resolve_agentkit_allow_origins(allow_origins=None)
        == DEFAULT_AGENTKIT_ALLOW_ORIGINS
        == ["*"]
    )


def test_resolve_allow_origins_can_disable_default(monkeypatch):
    monkeypatch.delenv("AGENTKIT_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("ADK_ALLOW_ORIGINS", raising=False)
    monkeypatch.setenv("AGENTKIT_DISABLE_DEFAULT_ALLOW_ORIGINS", "true")

    assert resolve_agentkit_allow_origins(allow_origins=None) == []


def test_resolve_allow_origins_explicit_empty_disables_default(monkeypatch):
    monkeypatch.setenv("AGENTKIT_ALLOW_ORIGINS", "*")

    assert resolve_agentkit_allow_origins(allow_origins=[]) == []


def test_resolve_allow_origins_env_overrides_default(monkeypatch):
    monkeypatch.setenv(
        "AGENTKIT_ALLOW_ORIGINS",
        "https://console.example.com, regex:https://.*\\.example\\.com",
    )

    assert resolve_agentkit_allow_origins(allow_origins=None) == [
        "https://console.example.com",
        "regex:https://.*\\.example\\.com",
    ]


def test_resolve_allow_origin_regex_env_overrides_default(monkeypatch):
    monkeypatch.delenv("AGENTKIT_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("ADK_ALLOW_ORIGINS", raising=False)
    monkeypatch.setenv("AGENTKIT_ALLOW_ORIGIN_REGEX", "https://.*\\.example\\.com")

    assert resolve_agentkit_allow_origins(allow_origins=None) == [
        "regex:https://.*\\.example\\.com",
    ]


def test_resolve_allow_origin_regex_adds_regex_prefix(monkeypatch):
    monkeypatch.delenv("AGENTKIT_ALLOW_ORIGINS", raising=False)
    monkeypatch.delenv("ADK_ALLOW_ORIGINS", raising=False)

    assert resolve_agentkit_allow_origins(
        allow_origins=["https://console.example.com"],
        allow_origin_regex="https://.*\\.example\\.com",
    ) == [
        "https://console.example.com",
        "regex:https://.*\\.example\\.com",
    ]


def test_resolve_allow_origins_converts_glob_to_regex():
    assert resolve_agentkit_allow_origins(
        allow_origins=["https://*.example.com"]
    ) == ["regex:https://.*\\.example\\.com"]


def test_resolve_allow_origins_rejects_invalid_regex():
    with pytest.raises(ValueError, match="Invalid allow origin regex"):
        resolve_agentkit_allow_origins(
            allow_origins=[],
            allow_origin_regex="https://[",
        )


def test_split_allow_origins():
    literals, regex = split_allow_origins(
        [
            "*",
            "https://console.example.com",
            "regex:https://.*\\.example\\.com",
            "regex:https://.*\\.example.org",
        ]
    )

    assert literals == ["*", "https://console.example.com"]
    assert regex == "https://.*\\.example\\.com|https://.*\\.example.org"


def test_supports_get_fast_api_kwarg():
    def without_allow_origins(lifespan=None):
        del lifespan

    def with_allow_origins(lifespan=None, allow_origins=None):
        del lifespan, allow_origins

    def with_kwargs(**kwargs):
        del kwargs

    assert not supports_get_fast_api_kwarg(without_allow_origins, "allow_origins")
    assert supports_get_fast_api_kwarg(with_allow_origins, "allow_origins")
    assert supports_get_fast_api_kwarg(with_kwargs, "allow_origins")


def test_add_cors_compat_middleware_splits_literal_and_regex():
    app = FastAPI()

    add_cors_compat_middleware(
        app,
        [
            "*",
            "regex:https://.*\\.example\\.com",
        ],
    )

    [middleware] = app.user_middleware
    options = getattr(middleware, "options", None) or getattr(middleware, "kwargs", {})
    assert middleware.cls.__name__ == "CORSMiddleware"
    assert options["allow_origins"] == ["*"]
    assert options["allow_origin_regex"] == "https://.*\\.example\\.com"
    assert options["allow_methods"] == ["*"]
    assert options["allow_headers"] == ["*"]


def _cors_options(app: FastAPI) -> dict:
    [middleware] = app.user_middleware
    return getattr(middleware, "options", None) or getattr(middleware, "kwargs", {})


def test_add_cors_compat_middleware_disables_credentials_for_wildcard():
    # A wildcard origin must not be paired with allow_credentials=True, or any
    # site could make credentialed cross-origin calls.
    app = FastAPI()
    add_cors_compat_middleware(app, ["*"])
    assert _cors_options(app)["allow_credentials"] is False


def test_add_cors_compat_middleware_keeps_credentials_for_explicit_allowlist():
    app = FastAPI()
    add_cors_compat_middleware(
        app,
        ["https://console.volcengine.com", "regex:https://.*\\.volcengine\\.com"],
    )
    assert _cors_options(app)["allow_credentials"] is True

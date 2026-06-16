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

"""Tests for ``agentkit invoke harness`` (and the bare-message fallback)."""

import json

from typer.testing import CliRunner

from agentkit.toolkit.cli.cli import app
from agentkit.toolkit.cli import cli_invoke

runner = CliRunner()


def _write_registry(directory, mapping):
    """Write the ``harness.json`` registry that ``deploy --harness`` produces."""
    (directory / "harness.json").write_text(json.dumps(mapping))


def _run_harness(args):
    return runner.invoke(app, ["invoke", "harness", *args])


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def _patch_post(monkeypatch, captured, *, payload=None, status_code=200):
    payload = payload or {"harness_name": "first", "overwrite": False, "output": "ok"}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeResponse(payload, status_code)

    monkeypatch.setattr("requests.post", fake_post)


# --- pure helper: HarnessOverrides shape ------------------------------------


def test_build_harness_overrides_matches_harness_overrides_model():
    overrides = cli_invoke.build_harness_overrides(
        system_prompt="be terse",
        model_name="m1",
        tools="web_search,web_fetch",
        skills="s1",
        runtime="codex",
    )
    # model_name (not model.name); tools/skills as comma-separated STRINGS.
    assert overrides == {
        "system_prompt": "be terse",
        "model_name": "m1",
        "tools": "web_search,web_fetch",
        "skills": "s1",
        "runtime": "codex",
    }


def test_build_harness_overrides_empty_when_unset():
    assert cli_invoke.build_harness_overrides(None, None, None, None, None) == {}


# --- fast-fail: unknown harness ---------------------------------------------


def test_unknown_harness_fails(tmp_path):
    _write_registry(tmp_path, {"other": {"url": "https://x", "key": "k"}})
    result = _run_harness(["first", "hi", "--directory", str(tmp_path)])
    assert result.exit_code == 1
    assert "not found in registry" in result.output


def test_no_registry_fails(tmp_path):
    result = _run_harness(["first", "hi", "--directory", str(tmp_path)])
    assert result.exit_code == 1
    assert "not found in registry" in result.output


# --- happy path: builds InvokeHarnessRequest and POSTs /harness/invoke ------


def test_harness_invoke_posts_correct_request(tmp_path, monkeypatch):
    _write_registry(
        tmp_path,
        {"first": {"url": "https://x", "key": "ak", "runtime_id": "r-1"}},
    )
    captured = {}
    _patch_post(monkeypatch, captured, payload={
        "harness_name": "first",
        "overwrite": True,
        "output": "PINEAPPLE",
    })

    result = _run_harness(
        [
            "first",
            "What should you reply?",
            "--directory",
            str(tmp_path),
            "--system-prompt",
            "Reply PINEAPPLE.",
            "--max-llm-calls",
            "7",
        ]
    )

    assert result.exit_code == 0, result.output
    assert "PINEAPPLE" in result.output
    # Endpoint + auth.
    assert captured["url"] == "https://x/harness/invoke"
    assert captured["headers"]["Authorization"] == "Bearer ak"
    # InvokeHarnessRequest shape.
    body = captured["json"]
    assert body["prompt"] == "What should you reply?"
    assert body["harness_name"] == "first"
    assert body["run_agent_request"]["user_id"] == "agentkit_user"
    assert body["run_agent_request"]["max_llm_calls"] == 7
    # Partial overrides only (model_fields_set semantics).
    assert body["harness"] == {"system_prompt": "Reply PINEAPPLE."}


def test_harness_invoke_no_overrides_omits_harness_key(tmp_path, monkeypatch):
    _write_registry(tmp_path, {"first": {"url": "https://x", "key": "ak"}})
    captured = {}
    _patch_post(monkeypatch, captured)

    result = _run_harness(["first", "hi", "--directory", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "harness" not in captured["json"]
    assert "max_llm_calls" not in captured["json"]["run_agent_request"]


def test_harness_error_field_is_surfaced(tmp_path, monkeypatch):
    _write_registry(tmp_path, {"first": {"url": "https://x", "key": "ak"}})
    captured = {}
    _patch_post(
        monkeypatch,
        captured,
        payload={
            "harness_name": "first",
            "overwrite": True,
            "output": "",
            "error": "Tool 'bogus' is not a supported built-in tool. Available: web_search",
        },
    )

    result = _run_harness(
        ["first", "hi", "--directory", str(tmp_path), "--tools", "bogus"]
    )
    assert result.exit_code == 1
    assert "Harness error" in result.output
    assert "not a supported built-in tool" in result.output


def test_harness_invoke_http_error_fails(tmp_path, monkeypatch):
    _write_registry(tmp_path, {"first": {"url": "https://x", "key": "ak"}})
    captured = {}
    _patch_post(monkeypatch, captured, payload={"detail": "boom"}, status_code=500)

    result = _run_harness(["first", "hi", "--directory", str(tmp_path)])
    assert result.exit_code == 1
    assert "HTTP 500" in result.output


def test_apikey_overrides_registry_key(tmp_path, monkeypatch):
    _write_registry(tmp_path, {"first": {"url": "https://x", "key": "registrykey"}})
    captured = {}
    _patch_post(monkeypatch, captured)

    result = _run_harness(
        ["first", "hi", "--directory", str(tmp_path), "--apikey", "jwt-token"]
    )
    assert result.exit_code == 0, result.output
    assert captured["headers"]["Authorization"] == "Bearer jwt-token"


# --- bare-message fallback still routes to `run` ----------------------------


def test_bare_message_falls_back_to_run(monkeypatch):
    captured = {}

    class _FakeResult:
        success = True
        error = None
        error_code = None
        is_streaming = False
        response = {"text": "ok"}

    class _FakeExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def execute(self, **kwargs):
            captured.update(kwargs)
            return _FakeResult()

    monkeypatch.setattr(
        "agentkit.toolkit.executors.InvokeExecutor", _FakeExecutor, raising=True
    )

    class _FakeCommon:
        agent_type = ""

    class _FakeConfig:
        def get_common_config(self):
            return _FakeCommon()

    monkeypatch.setattr(cli_invoke, "get_config", lambda config_path: _FakeConfig())

    result = runner.invoke(app, ["invoke", "hello"])

    assert result.exit_code == 0, result.output
    # Non-direct `run` path uses the yaml config_file and passes no config_dict.
    assert captured.get("config_dict") is None
    assert captured["config_file"] is not None
    assert captured["payload"] == {"prompt": "hello"}

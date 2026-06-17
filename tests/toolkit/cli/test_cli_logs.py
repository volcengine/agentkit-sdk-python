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

"""Tests for ``agentkit logs --harness <name>``."""

from types import SimpleNamespace

from typer.testing import CliRunner

from agentkit.platform.configuration import Credentials
from agentkit.toolkit.cli.cli import app
from agentkit.toolkit.harness.deploy import HARNESS_TAG_KEY, HARNESS_TAG_VALUE

runner = CliRunner()


def _tag(key, value):
    return SimpleNamespace(key=key, value=value)


def _runtime(name, runtime_id, *, harness):
    tags = [_tag(HARNESS_TAG_KEY, HARNESS_TAG_VALUE)] if harness else []
    return SimpleNamespace(name=name, runtime_id=runtime_id, tags=tags)


class _FakeClient:
    """Stand-in for AgentkitRuntimeClient returning a fixed runtime page."""

    runtimes: list = []

    def __init__(self, *args, **kwargs):
        pass

    def list_runtimes(self, request):
        return SimpleNamespace(agent_kit_runtimes=self.runtimes, next_token=None)


def _patch_common(monkeypatch, runtimes):
    _FakeClient.runtimes = runtimes
    monkeypatch.setattr(
        "agentkit.sdk.runtime.client.AgentkitRuntimeClient", _FakeClient
    )
    monkeypatch.setattr(
        "agentkit.platform.resolve_credentials",
        lambda *a, **k: Credentials(access_key="ak", secret_key="sk", source="test"),
    )


def test_logs_non_harness_app_is_rejected(monkeypatch):
    _patch_common(
        monkeypatch,
        [_runtime("drawing_assistant-1joart6y", "r-draw", harness=False)],
    )
    result = runner.invoke(
        app, ["logs", "--harness", "drawing_assistant-1joart6y", "--region", "cn-beijing"]
    )
    assert result.exit_code == 1
    assert "非 Harness 应用，无法查询日志" in result.stdout


def test_logs_runtime_not_found(monkeypatch):
    _patch_common(monkeypatch, [])
    result = runner.invoke(
        app, ["logs", "--harness", "missing", "--region", "cn-beijing"]
    )
    assert result.exit_code == 1
    assert "未找到" in result.stdout


def test_logs_harness_success_builds_default_query(monkeypatch):
    _patch_common(
        monkeypatch, [_runtime("my-harness", "r-abc", harness=True)]
    )

    captured = {}

    def fake_topic(**kwargs):
        return "topic-123"

    def fake_search(**kwargs):
        captured.update(kwargs)
        return {
            "Logs": [
                {"__time__": "1781683297505", "__content__": "hello from harness"}
            ]
        }

    monkeypatch.setattr(
        "agentkit.toolkit.volcengine.apmplus_logs.get_log_topic_id", fake_topic
    )
    monkeypatch.setattr(
        "agentkit.toolkit.volcengine.apmplus_logs.search_logs", fake_search
    )

    result = runner.invoke(
        app, ["logs", "--harness", "my-harness", "--region", "cn-beijing"]
    )
    assert result.exit_code == 0, result.stdout
    # Default query is built from runtime_id + name.
    assert captured["query"] == "service:r-abc.my-harness"
    assert captured["topic_id"] == "topic-123"
    assert "hello from harness" in result.stdout


def test_logs_query_override(monkeypatch):
    _patch_common(monkeypatch, [_runtime("my-harness", "r-abc", harness=True)])

    captured = {}

    monkeypatch.setattr(
        "agentkit.toolkit.volcengine.apmplus_logs.get_log_topic_id",
        lambda **k: "t",
    )

    def fake_search(**kwargs):
        captured.update(kwargs)
        return {"Logs": []}

    monkeypatch.setattr(
        "agentkit.toolkit.volcengine.apmplus_logs.search_logs", fake_search
    )

    result = runner.invoke(
        app,
        ["logs", "--harness", "my-harness", "--query", "error", "--region", "cn-beijing"],
    )
    assert result.exit_code == 0, result.stdout
    assert captured["query"] == "error"
    assert "未查询到日志" in result.stdout


def test_parse_since_durations():
    from agentkit.toolkit.cli.cli_logs import _parse_since

    assert _parse_since("30m") == 30 * 60_000
    assert _parse_since("1h") == 3_600_000
    assert _parse_since("2d") == 2 * 86_400_000
    assert _parse_since("1h30m") == 3_600_000 + 30 * 60_000


def test_parse_since_invalid():
    import pytest

    from agentkit.toolkit.cli.cli_logs import _parse_since

    with pytest.raises(ValueError):
        _parse_since("yesterday")


def test_logs_since_sets_window(monkeypatch):
    _patch_common(monkeypatch, [_runtime("my-harness", "r-abc", harness=True)])

    captured = {}
    monkeypatch.setattr(
        "agentkit.toolkit.volcengine.apmplus_logs.get_log_topic_id", lambda **k: "t"
    )

    def fake_search(**kwargs):
        captured.update(kwargs)
        return {"Logs": []}

    monkeypatch.setattr(
        "agentkit.toolkit.volcengine.apmplus_logs.search_logs", fake_search
    )

    result = runner.invoke(
        app, ["logs", "--harness", "my-harness", "--since", "1h", "--region", "cn-beijing"]
    )
    assert result.exit_code == 0, result.stdout
    # Window spans exactly the requested duration.
    assert captured["end_time_ms"] - captured["start_time_ms"] == 3_600_000


def test_logs_since_conflicts_with_start(monkeypatch):
    _patch_common(monkeypatch, [_runtime("my-harness", "r-abc", harness=True)])
    result = runner.invoke(
        app,
        [
            "logs", "--harness", "my-harness",
            "--since", "1h", "--start", "1", "--region", "cn-beijing",
        ],
    )
    assert result.exit_code == 1
    assert "--since 与 --start 不能同时使用" in result.stdout


def test_logs_output_writes_file(monkeypatch, tmp_path):
    _patch_common(monkeypatch, [_runtime("my-harness", "r-abc", harness=True)])
    monkeypatch.setattr(
        "agentkit.toolkit.volcengine.apmplus_logs.get_log_topic_id", lambda **k: "t"
    )
    monkeypatch.setattr(
        "agentkit.toolkit.volcengine.apmplus_logs.search_logs",
        lambda **k: {
            "Logs": [
                {"__time__": "1781683297505", "log_level": "INFO", "message": "line one"}
            ]
        },
    )

    out = tmp_path / "logs" / "my-harness.log"
    result = runner.invoke(
        app,
        ["logs", "--harness", "my-harness", "--output", str(out), "--region", "cn-beijing"],
    )
    assert result.exit_code == 0, result.stdout
    assert out.is_file()
    content = out.read_text(encoding="utf-8")
    assert "line one" in content
    assert "INFO" in content
    # (path may be line-wrapped by rich in captured output, so just check the verb)
    assert "已写入" in result.stdout

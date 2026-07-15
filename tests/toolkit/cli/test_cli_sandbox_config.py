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

import yaml
from typer.testing import CliRunner

runner = CliRunner()


def test_sandbox_config_set_initializes_defaults_and_redacts(tmp_path, monkeypatch):
    from agentkit.toolkit.cli.cli import app

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        ["sandbox", "config", "--set", "model-api-key=sk-test-secret"],
    )

    assert result.exit_code == 0
    config_path = tmp_path / ".agentkit" / "sandbox.yaml"
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["model"]["api_key"] == "sk-test-secret"
    assert payload["tool"]["type"] == "CodeEnv"
    assert payload["tool"]["cpu"] == 4
    assert payload["session"]["ttl"] == 28800
    assert payload["session"]["workspace"] == "/home/gem"

    list_result = runner.invoke(app, ["sandbox", "config", "--list"])

    assert list_result.exit_code == 0
    assert "sk-test-secret" not in list_result.output
    assert "api_key:" in list_result.output
    assert "/home/gem" in list_result.output


def test_sandbox_config_help_has_no_subcommands():
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, ["sandbox", "config", "--help"])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "COMMAND [ARGS]" not in result.output
    assert "Commands" not in result.output
    assert "--set" in result.output
    assert "--unset" in result.output
    assert "--list" in result.output


def test_sandbox_config_rejects_removed_subcommands(tmp_path, monkeypatch):
    from agentkit.toolkit.cli.cli import app

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        ["sandbox", "config", "set", "model-name", "glm-5.2"],
    )

    assert result.exit_code != 0
    assert "unexpected extra arguments" in result.output


def test_sandbox_config_set_option_accepts_repeated_key_values(tmp_path, monkeypatch):
    from agentkit.toolkit.cli.cli import app

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "config",
            "--set",
            "model-name=glm-5.2",
            "--set",
            "ttl=200",
            "--set",
            "model-api-key=sk-test-secret",
        ],
    )

    assert result.exit_code == 0
    assert "Set model-name: glm-5.2" in result.output
    assert "Set ttl: 200" in result.output
    assert "Set model-api-key: <redacted>" in result.output
    assert "sk-test-secret" not in result.output
    payload = yaml.safe_load(
        (tmp_path / ".agentkit" / "sandbox.yaml").read_text(encoding="utf-8")
    )
    assert payload["model"]["name"] == "glm-5.2"
    assert payload["model"]["api_key"] == "sk-test-secret"
    assert payload["session"]["ttl"] == 200


def test_sandbox_config_unset_option_accepts_repeated_keys(tmp_path, monkeypatch):
    from agentkit.toolkit.cli.cli import app

    monkeypatch.chdir(tmp_path)
    assert (
        runner.invoke(
            app,
            [
                "sandbox",
                "config",
                "--set",
                "tool-id=tool-123",
                "--set",
                "session-id=session-123",
            ],
        ).exit_code
        == 0
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "config",
            "--unset",
            "tool-id",
            "--unset",
            "session-id",
        ],
    )

    assert result.exit_code == 0
    assert "Unset tool-id" in result.output
    assert "Unset session-id" in result.output
    payload = yaml.safe_load(
        (tmp_path / ".agentkit" / "sandbox.yaml").read_text(encoding="utf-8")
    )
    assert "id" not in payload.get("tool", {})
    assert "id" not in payload.get("session", {})


def test_sandbox_config_list_option_prints_effective_config(tmp_path, monkeypatch):
    from agentkit.toolkit.cli.cli import app

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "config",
            "--set",
            "model-name=glm-5.2",
            "--list",
        ],
    )

    assert result.exit_code == 0
    assert "Wrote" in result.output
    assert "model:" in result.output
    assert "name: glm-5.2" in result.output
    assert "workspace: /home/gem" in result.output


def test_sandbox_config_list_option_does_not_create_config(tmp_path, monkeypatch):
    from agentkit.toolkit.cli.cli import app

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["sandbox", "config", "--list"])

    assert result.exit_code == 0
    assert "version: 1" in result.output
    assert "workspace: /home/gem" in result.output
    assert not (tmp_path / ".agentkit" / "sandbox.yaml").exists()


def test_sandbox_config_set_option_rejects_non_key_value(tmp_path, monkeypatch):
    from agentkit.toolkit.cli.cli import app

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["sandbox", "config", "--set", "model-name"])

    assert result.exit_code != 0
    assert "KEY=VALUE" in result.output


def test_sandbox_config_unset_option_removes_value(tmp_path, monkeypatch):
    from agentkit.toolkit.cli.cli import app

    monkeypatch.chdir(tmp_path)
    assert (
        runner.invoke(
            app,
            ["sandbox", "config", "--set", "tool-id=tool-123"],
        ).exit_code
        == 0
    )

    result = runner.invoke(app, ["sandbox", "config", "--unset", "tool-id"])

    assert result.exit_code == 0
    payload = yaml.safe_load(
        (tmp_path / ".agentkit" / "sandbox.yaml").read_text(encoding="utf-8")
    )
    assert "id" not in payload["tool"]


def test_sandbox_config_accepts_underscore_aliases(tmp_path, monkeypatch):
    from agentkit.toolkit.cli.cli import app

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        ["sandbox", "config", "--set", "network_subnet_ids=subnet-a,subnet-b"],
    )

    assert result.exit_code == 0
    payload = yaml.safe_load(
        (tmp_path / ".agentkit" / "sandbox.yaml").read_text(encoding="utf-8")
    )
    assert payload["network"]["subnet_ids"] == ["subnet-a", "subnet-b"]


def test_sandbox_config_rejects_invalid_ttl(tmp_path, monkeypatch):
    from agentkit.toolkit.cli.cli import app

    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["sandbox", "config", "--set", "ttl=0"])

    assert result.exit_code != 0
    assert "greater than 0" in result.output


def test_sandbox_config_list_prefers_file_over_env(tmp_path, monkeypatch):
    from agentkit.toolkit.cli.cli import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODEL_API_KEY", "env-secret")
    monkeypatch.setenv("AGENTKIT_SANDBOX_TOOL_ID", "tool-from-env")
    monkeypatch.setenv("AGENTKIT_SANDBOX_TTL", "100")
    monkeypatch.setenv("AGENTKIT_SANDBOX_REGION", "region-from-env")

    assert (
        runner.invoke(
            app,
            [
                "sandbox",
                "config",
                "--set",
                "model-api-key=file-secret",
                "--set",
                "tool-id=tool-from-file",
                "--set",
                "ttl=200",
                "--set",
                "region=region-from-file",
            ],
        ).exit_code
        == 0
    )

    result = runner.invoke(app, ["sandbox", "config", "--list"])

    assert result.exit_code == 0
    assert "env-secret" not in result.output
    assert "tool-from-env" not in result.output
    assert "tool-from-file" in result.output
    assert "region-from-file" in result.output
    assert "region-from-env" not in result.output
    assert "ttl: 200" in result.output
    assert "ttl: 100" not in result.output


def test_sandbox_ttl_prefers_config_over_env(tmp_path, monkeypatch):
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENTKIT_SANDBOX_TTL", "100")
    config_dir = tmp_path / ".agentkit"
    config_dir.mkdir()
    (config_dir / "sandbox.yaml").write_text(
        "session:\n  ttl: 200\n",
        encoding="utf-8",
    )

    assert session_create._resolve_ttl(None) == 200
    assert session_create._resolve_ttl(300) == 300


def test_sandbox_tool_id_prefers_config_over_env(tmp_path, monkeypatch):
    import agentkit.toolkit.cli.sandbox.session_create as session_create

    captured = {}

    def fake_resolve_sandbox_tool_id(**kwargs):
        captured.update(kwargs)
        return "tool-from-resolver"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENTKIT_SANDBOX_TOOL_ID", "tool-from-env")
    config_dir = tmp_path / ".agentkit"
    config_dir.mkdir()
    (config_dir / "sandbox.yaml").write_text(
        "tool:\n  id: tool-from-file\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(session_create, "AgentkitToolsClient", lambda: object())
    monkeypatch.setattr(
        session_create,
        "resolve_sandbox_tool_id",
        fake_resolve_sandbox_tool_id,
    )
    monkeypatch.setattr(
        session_create,
        "_create_session",
        lambda *_args, **_kwargs: {
            "session_id": "session-1",
            "tool_id": "tool-from-resolver",
            "instance_id": "instance-1",
            "endpoint": "https://sandbox.example.com",
        },
    )

    session_create.ensure_sandbox_session()

    assert captured["tool_id"] == "tool-from-file"
    assert "default_tool_id" not in captured


def test_sandbox_region_prefers_config_over_env(tmp_path, monkeypatch):
    import agentkit.toolkit.cli.sandbox.cli_create as cli_create

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENTKIT_SANDBOX_REGION", "region-from-env")
    config_dir = tmp_path / ".agentkit"
    config_dir.mkdir()
    (config_dir / "sandbox.yaml").write_text(
        "tool:\n  region: region-from-file\n",
        encoding="utf-8",
    )

    assert cli_create._resolve_region("AGENTKIT_SANDBOX_REGION", "agentkit") == (
        "region-from-file"
    )

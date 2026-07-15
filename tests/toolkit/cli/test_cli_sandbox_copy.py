from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def _session():
    return {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "instance-1",
        "endpoint": "https://sandbox.example.com",
    }


def test_exec_copy_can_repeat_and_defaults_relative_destination_to_home(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    first = tmp_path / "config.yaml"
    second = tmp_path / "project"
    first.write_text("answer: 42\n", encoding="utf-8")
    second.mkdir()
    monkeypatch.setattr(
        cli_exec,
        "ensure_sandbox_session_with_status",
        lambda **_kwargs: (_session(), False),
    )
    monkeypatch.setattr(cli_exec, "get_tool_websearch_config", lambda **_kwargs: None)
    copied = []
    monkeypatch.setattr(
        cli_exec,
        "_upload_scp_source",
        lambda session, *, source, destination: copied.append(
            (session, source, destination)
        ),
    )
    monkeypatch.setattr(cli_exec, "_connect_terminal", lambda *_args, **_kwargs: None)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "exec",
            "-s",
            "user-1",
            "--copy",
            str(first),
            "sandbox:/tmp/config.yaml",
            "--copy",
            str(second),
            "workspace/project",
        ],
    )

    assert result.exit_code == 0
    assert copied == [
        (_session(), first, "/tmp/config.yaml"),
        (_session(), second, "/home/gem/workspace/project"),
    ]


def test_shell_copy_runs_before_command(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_shell as cli_shell

    source = tmp_path / "input.txt"
    source.write_text("input", encoding="utf-8")
    monkeypatch.setattr(
        cli_shell, "ensure_sandbox_session", lambda **_kwargs: _session()
    )
    events = []
    monkeypatch.setattr(
        cli_shell,
        "_upload_scp_source",
        lambda session, *, source, destination: events.append(
            ("copy", source, destination)
        ),
    )
    monkeypatch.setattr(cli_shell, "apply_git_config_to_session", lambda *_args: None)

    class Response:
        text = ""

        def json(self):
            events.append(("command",))
            return {"success": True, "data": {"session_id": "shell-1"}}

    monkeypatch.setattr(
        cli_shell.requests, "post", lambda *_args, **_kwargs: Response()
    )
    result = runner.invoke(
        app,
        [
            "sandbox",
            "shell",
            "-s",
            "user-1",
            "--copy",
            str(source),
            "/tmp/input.txt",
            "--command",
            "cat /tmp/input.txt",
        ],
    )

    assert result.exit_code == 0
    assert events == [("copy", source, "/tmp/input.txt"), ("command",)]
    assert json.loads(result.output)["data"]["shell_id"] == "shell-1"


def test_copy_rejects_missing_destination_before_session_resolution(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    source = tmp_path / "input.txt"
    source.write_text("input", encoding="utf-8")
    called = {"ensure": False}
    monkeypatch.setattr(
        cli_exec,
        "ensure_sandbox_session_with_status",
        lambda **_kwargs: called.update(ensure=True),
    )
    result = runner.invoke(
        app,
        ["sandbox", "exec", "--copy", str(source)],
    )

    assert result.exit_code == 1
    assert "--copy requires SOURCE and DESTINATION" in result.output
    assert called["ensure"] is False


def test_copy_rejects_sandbox_source(monkeypatch) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_exec as cli_exec

    called = {"ensure": False}
    monkeypatch.setattr(
        cli_exec,
        "ensure_sandbox_session_with_status",
        lambda **_kwargs: called.update(ensure=True),
    )
    result = runner.invoke(
        app,
        ["sandbox", "exec", "--copy", "sandbox:/tmp/in", "/tmp/out"],
    )

    assert result.exit_code == 1
    assert "--copy only supports local-to-sandbox transfers" in result.output
    assert called["ensure"] is False


def test_copy_rejects_unexpected_positional_argument() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, ["sandbox", "exec", "orphan"])
    assert result.exit_code == 1
    assert "Unexpected argument: orphan" in result.output


def test_exec_and_shell_remove_legacy_copy_options() -> None:
    from agentkit.toolkit.cli.cli import app

    for command in ("exec", "shell"):
        result = runner.invoke(app, ["sandbox", command, "--help"])
        assert result.exit_code == 0
        assert "--copy" in result.output
        assert "--src-dir" not in result.output
        assert "--dst-dir" not in result.output
        assert "--workspace" not in result.output

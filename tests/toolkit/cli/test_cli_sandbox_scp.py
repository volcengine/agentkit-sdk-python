from __future__ import annotations

import io
import json
import os
from pathlib import Path
import tarfile

import pytest
from typer.testing import CliRunner


runner = CliRunner()


class _FakeResponse:
    def __init__(self, *, status_code=200, payload=None, text="", content=b""):
        self.status_code = status_code
        self._payload = {"success": True} if payload is None else payload
        self.text = text
        self._content = content

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def iter_content(self, chunk_size=1024 * 1024):
        del chunk_size
        yield self._content


def _patch_session(monkeypatch, tmp_path, cli_file):
    import agentkit.toolkit.cli.sandbox.sandbox_client as sandbox_client

    session = {
        "session_id": "user-1",
        "tool_id": "tool-1",
        "instance_id": "instance-1",
        "endpoint": "https://sandbox.example.com/base?token=abc",
    }
    store_path = tmp_path / "sessions.json"
    store_path.write_text(json.dumps({"user-1": session}), encoding="utf-8")
    monkeypatch.setattr(sandbox_client, "_get_session_store_path", lambda: store_path)
    monkeypatch.setattr(cli_file, "AgentkitToolsClient", lambda: object())
    monkeypatch.setattr(
        cli_file,
        "sync_remote_sessions",
        lambda **_kwargs: "tool-1",
    )
    return session


def _tar_bytes(entries: dict[str, bytes], dirs: list[str] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for directory in dirs or []:
            info = tarfile.TarInfo(directory.rstrip("/") + "/")
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
        for name, content in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def _tar_bytes_with_member(member: tarfile.TarInfo, content: bytes = b"") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        file_obj = io.BytesIO(content) if member.isfile() else None
        tar.addfile(member, file_obj)
    return buffer.getvalue()


def _tar_names(file_obj) -> list[str]:
    with tarfile.open(fileobj=io.BytesIO(file_obj.read()), mode="r") as tar:
        return sorted(member.name for member in tar.getmembers())


def test_scp_command_replaces_file_command_group() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, ["sandbox", "scp", "--help"])
    assert result.exit_code == 0
    assert "SOURCE" in result.output
    assert "DESTINATION" in result.output
    assert "--session-id" in result.output
    assert "--sid" in result.output
    assert "-s" in result.output

    result = runner.invoke(app, ["sandbox", "file", "--help"])
    assert result.exit_code != 0
    assert "No such command" in result.output


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("sandbox:/tmp/project", "/tmp/project"),
        ("sandbox:/tmp/../project", "/project"),
        ("sandbox:project/config.yaml", "/home/gem/project/config.yaml"),
        ("sandbox:./project", "/home/gem/project"),
        ("sandbox:project/../config.yaml", "/home/gem/config.yaml"),
    ],
)
def test_resolve_sandbox_operand_normalizes_absolute_and_relative_paths(
    value,
    expected,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    assert cli_file._resolve_sandbox_operand(value) == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("sandbox:", "must not be empty"),
        ("sandbox:../../etc", "must stay inside /home/gem"),
        ("sandbox:bad\x00path", "must not contain NUL bytes"),
        ("/tmp/plain", "must start with sandbox:"),
    ],
)
def test_resolve_sandbox_operand_rejects_invalid_paths(value, message) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    with pytest.raises(cli_file.typer.Exit):
        cli_file._resolve_sandbox_operand(value)


def test_resolve_scp_operands_detects_direction() -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    assert cli_file._resolve_scp_operands("local.txt", "sandbox:tmp/out.txt") == (
        "upload",
        Path("local.txt"),
        "/home/gem/tmp/out.txt",
    )
    assert cli_file._resolve_scp_operands("sandbox:/tmp/out.txt", "local.txt") == (
        "download",
        "/tmp/out.txt",
        Path("local.txt"),
    )


@pytest.mark.parametrize(
    ("source", "destination"),
    [
        ("one", "two"),
        ("sandbox:/one", "sandbox:/two"),
    ],
)
def test_resolve_scp_operands_requires_exactly_one_sandbox_path(
    source,
    destination,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    with pytest.raises(cli_file.typer.Exit):
        cli_file._resolve_scp_operands(source, destination)


def test_scp_upload_file_uses_archive_and_remote_copy(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    _patch_session(monkeypatch, tmp_path, cli_file)
    source = tmp_path / "config.yaml"
    source.write_text("answer: 42\n", encoding="utf-8")
    captured = {}

    def fake_post(url, **kwargs):
        if url.endswith("/v1/file/upload?token=abc"):
            captured["archive_names"] = _tar_names(kwargs["files"]["file"][1])
            captured["remote_archive"] = kwargs["data"]["path"]
            return _FakeResponse()
        captured["shell_command"] = kwargs["json"]["command"]
        return _FakeResponse(
            payload={"success": True, "data": {"status": "completed", "exit_code": 0}}
        )

    monkeypatch.setattr(cli_file.requests, "post", fake_post)

    result = runner.invoke(
        app,
        [
            "sandbox",
            "scp",
            "-s",
            "user-1",
            str(source),
            "sandbox:/tmp/copied.yaml",
        ],
    )

    assert result.exit_code == 0
    assert captured["archive_names"] == ["config.yaml"]
    assert captured["remote_archive"].startswith("/tmp/agentkit-upload-")
    assert "cp -R --" in captured["shell_command"]
    assert "/config.yaml /tmp/copied.yaml" in captured["shell_command"]
    assert "trap" in captured["shell_command"]
    output = json.loads(result.output)
    assert output["direction"] == "upload"
    assert output["remote_path"] == "/tmp/copied.yaml"


def test_scp_upload_directory_is_recursive_and_resolves_relative_remote_path(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    _patch_session(monkeypatch, tmp_path, cli_file)
    source = tmp_path / "project"
    (source / "nested").mkdir(parents=True)
    (source / "nested" / "app.py").write_text("print(42)\n", encoding="utf-8")
    captured = {}

    def fake_post(url, **kwargs):
        if "/v1/file/upload" in url:
            captured["archive_names"] = _tar_names(kwargs["files"]["file"][1])
            return _FakeResponse()
        captured["shell_command"] = kwargs["json"]["command"]
        return _FakeResponse(payload={"success": True, "data": {"exit_code": 0}})

    monkeypatch.setattr(cli_file.requests, "post", fake_post)
    result = runner.invoke(
        app,
        ["sandbox", "scp", "-s", "user-1", str(source), "sandbox:workspace"],
    )

    assert result.exit_code == 0
    assert captured["archive_names"] == [
        "project",
        "project/nested",
        "project/nested/app.py",
    ]
    assert "/project /home/gem/workspace" in captured["shell_command"]


def test_scp_upload_rejects_missing_local_source(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    _patch_session(monkeypatch, tmp_path, cli_file)
    result = runner.invoke(
        app,
        ["sandbox", "scp", "-s", "user-1", "missing", "sandbox:/tmp/out"],
    )
    assert result.exit_code == 1
    assert "Source path not found" in result.output


def test_validate_scp_local_source_rejects_special_file_and_root_name(
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    with pytest.raises(cli_file.typer.Exit):
        cli_file._validate_scp_local_source(fifo)
    with pytest.raises(cli_file.typer.Exit):
        cli_file._validate_scp_local_source(Path("/"))


def test_scp_download_file_overwrites_like_linux_scp(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    _patch_session(monkeypatch, tmp_path, cli_file)
    destination = tmp_path / "result.txt"
    destination.write_text("old", encoding="utf-8")
    archive = _tar_bytes({"source.txt": b"new"})
    commands = []

    def fake_post(_url, **kwargs):
        command = kwargs["json"]["command"]
        commands.append(command)
        if "printf 'file'" in command:
            return _FakeResponse(
                payload={"success": True, "data": {"exit_code": 0, "output": "file"}}
            )
        return _FakeResponse(payload={"success": True, "data": {"exit_code": 0}})

    monkeypatch.setattr(cli_file.requests, "post", fake_post)
    monkeypatch.setattr(
        cli_file.requests,
        "get",
        lambda *_args, **_kwargs: _FakeResponse(content=archive),
    )

    result = runner.invoke(
        app,
        [
            "sandbox",
            "scp",
            "-s",
            "user-1",
            "sandbox:/tmp/source.txt",
            str(destination),
        ],
    )

    assert result.exit_code == 0
    assert destination.read_text(encoding="utf-8") == "new"
    assert "tar -cf" in commands[1]
    assert "-C /tmp source.txt" in commands[1]
    assert commands[-1].startswith("rm -f /tmp/agentkit-download-")
    output = json.loads(result.output)
    assert output["direction"] == "download"
    assert output["local_path"] == str(destination)


def test_scp_download_file_into_existing_directory_uses_source_name(
    monkeypatch,
    tmp_path,
) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    _patch_session(monkeypatch, tmp_path, cli_file)
    destination = tmp_path / "downloads"
    destination.mkdir()
    archive = _tar_bytes({"source.txt": b"content"})

    def fake_post(_url, **kwargs):
        command = kwargs["json"]["command"]
        output = "file" if "printf 'file'" in command else ""
        return _FakeResponse(
            payload={"success": True, "data": {"exit_code": 0, "output": output}}
        )

    monkeypatch.setattr(cli_file.requests, "post", fake_post)
    monkeypatch.setattr(
        cli_file.requests,
        "get",
        lambda *_args, **_kwargs: _FakeResponse(content=archive),
    )
    result = runner.invoke(
        app,
        [
            "sandbox",
            "scp",
            "-s",
            "user-1",
            "sandbox:/tmp/source.txt",
            str(destination),
        ],
    )

    assert result.exit_code == 0
    assert (destination / "source.txt").read_bytes() == b"content"


def test_scp_download_directory_merges_and_overwrites(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    _patch_session(monkeypatch, tmp_path, cli_file)
    destination = tmp_path / "destination"
    existing = destination / "project"
    existing.mkdir(parents=True)
    (existing / "same.txt").write_text("old", encoding="utf-8")
    archive = _tar_bytes(
        {"project/same.txt": b"new", "project/new.txt": b"added"},
        dirs=["project"],
    )

    def fake_post(_url, **kwargs):
        command = kwargs["json"]["command"]
        output = "directory" if "printf 'directory'" in command else ""
        return _FakeResponse(
            payload={"success": True, "data": {"exit_code": 0, "output": output}}
        )

    monkeypatch.setattr(cli_file.requests, "post", fake_post)
    monkeypatch.setattr(
        cli_file.requests,
        "get",
        lambda *_args, **_kwargs: _FakeResponse(content=archive),
    )
    result = runner.invoke(
        app,
        [
            "sandbox",
            "scp",
            "-s",
            "user-1",
            "sandbox:/tmp/project",
            str(destination),
        ],
    )

    assert result.exit_code == 0
    assert (existing / "same.txt").read_text(encoding="utf-8") == "new"
    assert (existing / "new.txt").read_text(encoding="utf-8") == "added"


def test_scp_download_rejects_file_directory_collision(monkeypatch, tmp_path) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    source = tmp_path / "stage" / "item"
    source.parent.mkdir()
    source.write_text("file", encoding="utf-8")
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "item").mkdir()

    with pytest.raises(cli_file.typer.Exit):
        cli_file._copy_downloaded_source(source, destination)


def test_remote_source_type_rejects_unknown_output(monkeypatch) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    monkeypatch.setattr(
        cli_file,
        "_exec_shell_command",
        lambda *_args, **_kwargs: {"data": {"output": "mystery"}},
    )
    with pytest.raises(cli_file.typer.Exit):
        cli_file._remote_source_type({"endpoint": "https://example.com"}, "/tmp/x")


def test_remote_source_type_reports_missing_source(monkeypatch, capsys) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    monkeypatch.setattr(
        cli_file,
        "_exec_shell_command",
        lambda *_args, **_kwargs: {"data": {"output": "missing"}},
    )

    with pytest.raises(cli_file.typer.Exit):
        cli_file._remote_source_type({"endpoint": "https://example.com"}, "/tmp/x")

    assert "Source path not found: /tmp/x" in capsys.readouterr().err


def test_remote_archive_command_handles_root_source() -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    assert cli_file._build_remote_scp_archive_command(
        archive_path="/tmp/archive.tar",
        source="/",
    ).startswith("tar -cf /tmp/archive.tar -C / .;")


def test_shell_output_returns_empty_for_unexpected_payload() -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    assert cli_file._shell_output({"data": "not-a-dict"}) == ""


def test_scp_requires_session_id() -> None:
    from agentkit.toolkit.cli.cli import app

    result = runner.invoke(app, ["sandbox", "scp", "one", "sandbox:/tmp/one"])
    assert result.exit_code != 0
    assert "--session-id" in result.output


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"detail": ["plain detail"]}, "plain detail"),
        ({"detail": "detail text"}, "detail text"),
        ({"message": "message text"}, "message text"),
        (
            {"ResponseMetadata": {"Error": {"Message": "metadata text"}}},
            "metadata text",
        ),
    ],
)
def test_format_response_error_extracts_api_messages(payload, expected) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    message = cli_file._format_response_error(
        _FakeResponse(status_code=400, payload=payload),
        "file upload",
    )

    assert expected in message


def test_format_response_error_extracts_validation_detail() -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    message = cli_file._format_response_error(
        _FakeResponse(
            status_code=422,
            payload={"detail": [{"loc": ["body", "path"], "msg": "invalid path"}]},
        ),
        "file upload",
    )

    assert "body.path: invalid path" in message


def test_json_response_rejects_invalid_or_failed_payloads() -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    with pytest.raises(cli_file.typer.Exit):
        cli_file._json_response(
            _FakeResponse(
                status_code=503,
                payload={"message": "temporarily unavailable"},
            ),
            "file upload",
        )
    with pytest.raises(cli_file.typer.Exit):
        cli_file._json_response(
            _FakeResponse(payload=ValueError("bad"), text="<html>"),
            "file upload",
        )
    with pytest.raises(cli_file.typer.Exit):
        cli_file._json_response(_FakeResponse(payload=[]), "file upload")
    with pytest.raises(cli_file.typer.Exit):
        cli_file._json_response(
            _FakeResponse(payload={"success": False, "message": "denied"}),
            "file upload",
        )


def test_exec_shell_command_reports_running_and_failed_commands(monkeypatch) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    responses = [
        _FakeResponse(payload={"success": True, "data": "done"}),
        _FakeResponse(
            payload={
                "success": True,
                "data": {"status": "running", "output": "still running"},
            }
        ),
        _FakeResponse(
            payload={
                "success": True,
                "data": {"status": "completed", "exit_code": 2, "output": "failed"},
            }
        ),
    ]

    monkeypatch.setattr(
        cli_file.requests, "post", lambda *_args, **_kwargs: responses.pop(0)
    )
    session = {"endpoint": "https://sandbox.example.com"}

    assert cli_file._exec_shell_command(session, "true")["data"] == "done"
    with pytest.raises(cli_file.typer.Exit):
        cli_file._exec_shell_command(session, "sleep 10")
    with pytest.raises(cli_file.typer.Exit):
        cli_file._exec_shell_command(session, "false")


@pytest.mark.parametrize(
    "member_name",
    ["/abs/path.txt", "../escape.txt", "nested/../../escape.txt"],
)
def test_extract_archive_rejects_unsafe_member_paths(tmp_path, member_name) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    member = tarfile.TarInfo(member_name)
    member.size = 4
    archive = tmp_path / "unsafe.tar"
    archive.write_bytes(_tar_bytes_with_member(member, b"data"))

    with pytest.raises(cli_file.typer.Exit):
        cli_file._extract_archive(archive, download_dir=tmp_path, overwrite=True)


@pytest.mark.parametrize("link_type", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_extract_archive_rejects_links_and_invalid_archive(
    tmp_path,
    link_type,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    link = tarfile.TarInfo("link")
    link.type = link_type
    link.linkname = "../target"
    archive = tmp_path / "link.tar"
    archive.write_bytes(_tar_bytes_with_member(link))

    with pytest.raises(cli_file.typer.Exit):
        cli_file._extract_archive(archive, download_dir=tmp_path, overwrite=True)

    invalid = tmp_path / "invalid.tar"
    invalid.write_text("not a tar", encoding="utf-8")
    with pytest.raises(cli_file.typer.Exit):
        cli_file._extract_archive(invalid, download_dir=tmp_path, overwrite=True)


def test_extract_archive_rejects_special_member_types(tmp_path) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    fifo = tarfile.TarInfo("pipe")
    fifo.type = tarfile.FIFOTYPE
    archive = tmp_path / "fifo.tar"
    archive.write_bytes(_tar_bytes_with_member(fifo))

    with pytest.raises(cli_file.typer.Exit):
        cli_file._extract_archive(archive, download_dir=tmp_path, overwrite=True)


def test_extract_archive_skips_current_directory_and_streams_file(tmp_path) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    archive = tmp_path / "download.tar"
    archive.write_bytes(_tar_bytes({"./": b"", "nested/file.txt": b"content"}))
    destination = tmp_path / "out"
    destination.mkdir()

    cli_file._extract_archive(archive, download_dir=destination, overwrite=True)

    assert (destination / "nested" / "file.txt").read_bytes() == b"content"


def test_extract_archive_can_reject_existing_file_when_overwrite_disabled(
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    archive = tmp_path / "download.tar"
    archive.write_bytes(_tar_bytes({"same.txt": b"new"}))
    destination = tmp_path / "out"
    destination.mkdir()
    (destination / "same.txt").write_text("old", encoding="utf-8")

    with pytest.raises(cli_file.typer.Exit):
        cli_file._extract_archive(archive, download_dir=destination, overwrite=False)


def test_copy_downloaded_source_rejects_parent_type_and_missing_source(
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    source_file = tmp_path / "source.txt"
    source_file.write_text("source", encoding="utf-8")
    with pytest.raises(cli_file.typer.Exit):
        cli_file._copy_downloaded_source(source_file, tmp_path / "missing" / "out.txt")

    existing_file = tmp_path / "target"
    existing_file.write_text("target", encoding="utf-8")
    source_dir = tmp_path / "source-dir"
    source_dir.mkdir()
    with pytest.raises(cli_file.typer.Exit):
        cli_file._copy_downloaded_source(source_dir, existing_file)

    with pytest.raises(cli_file.typer.Exit):
        cli_file._copy_downloaded_source(tmp_path / "missing-source", tmp_path / "out")


def test_scp_command_defensive_operand_type_checks(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    _patch_session(monkeypatch, tmp_path, cli_file)
    monkeypatch.setattr(
        cli_file,
        "_resolve_scp_operands",
        lambda *_args: ("upload", "/not-a-path", "/tmp/out"),
    )
    result = runner.invoke(
        app,
        ["sandbox", "scp", "-s", "user-1", "local", "sandbox:/tmp/out"],
    )
    assert result.exit_code == 1
    assert "Invalid resolved upload operands" in result.output

    monkeypatch.setattr(
        cli_file,
        "_resolve_scp_operands",
        lambda *_args: ("download", "/tmp/in", "/not-a-path"),
    )
    result = runner.invoke(
        app,
        ["sandbox", "scp", "-s", "user-1", "sandbox:/tmp/in", "local"],
    )
    assert result.exit_code == 1
    assert "Invalid resolved download operands" in result.output


def test_upload_scp_source_cleans_remote_archive_on_shell_error(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    source = tmp_path / "input.txt"
    source.write_text("content", encoding="utf-8")
    events = []
    monkeypatch.setattr(
        cli_file,
        "_upload_remote_file",
        lambda *_args, **_kwargs: events.append("uploaded"),
    )
    monkeypatch.setattr(
        cli_file,
        "_exec_shell_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("copy failed")),
    )
    monkeypatch.setattr(
        cli_file,
        "_cleanup_remote_file",
        lambda *_args, **_kwargs: events.append("cleaned"),
    )

    with pytest.raises(RuntimeError):
        cli_file._upload_scp_source(
            {"endpoint": "https://sandbox.example.com"},
            source=source,
            destination="/tmp/input.txt",
        )

    assert events == ["uploaded", "cleaned"]


def test_upload_scp_source_cleans_remote_archive_on_ambiguous_upload_error(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    source = tmp_path / "input.txt"
    source.write_text("content", encoding="utf-8")
    events = []
    local_archives = []
    monkeypatch.setattr(
        cli_file,
        "_new_remote_archive_path",
        lambda _prefix: "/tmp/agentkit-upload-fixed.tar",
    )

    def fail_upload(*_args, **kwargs):
        local_archives.append(kwargs["local_path"])
        raise cli_file.requests.ConnectionError("connection reset")

    monkeypatch.setattr(
        cli_file,
        "_upload_remote_file",
        fail_upload,
    )
    monkeypatch.setattr(
        cli_file,
        "_cleanup_remote_file",
        lambda _session, remote_path: events.append(remote_path),
    )

    with pytest.raises(cli_file.requests.ConnectionError):
        cli_file._upload_scp_source(
            {"endpoint": "https://sandbox.example.com"},
            source=source,
            destination="/tmp/input.txt",
        )

    assert events == ["/tmp/agentkit-upload-fixed.tar"]
    assert len(local_archives) == 1
    assert not local_archives[0].exists()


def test_download_scp_source_cleans_archive_when_archive_command_fails(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    events = []
    monkeypatch.setattr(cli_file, "_remote_source_type", lambda *_args: "file")
    monkeypatch.setattr(
        cli_file,
        "_new_remote_archive_path",
        lambda _prefix: "/tmp/agentkit-download-fixed.tar",
    )
    monkeypatch.setattr(
        cli_file,
        "_exec_shell_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("tar failed")),
    )
    monkeypatch.setattr(
        cli_file,
        "_cleanup_remote_file",
        lambda _session, remote_path: events.append(remote_path),
    )

    with pytest.raises(RuntimeError, match="tar failed"):
        cli_file._download_scp_source(
            {"endpoint": "https://sandbox.example.com"},
            source="/tmp/input.txt",
            destination=tmp_path / "output.txt",
        )

    assert events == ["/tmp/agentkit-download-fixed.tar"]


def test_download_scp_source_cleans_archive_when_download_fails(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    events = []
    monkeypatch.setattr(cli_file, "_remote_source_type", lambda *_args: "file")
    monkeypatch.setattr(
        cli_file,
        "_new_remote_archive_path",
        lambda _prefix: "/tmp/agentkit-download-fixed.tar",
    )
    monkeypatch.setattr(
        cli_file,
        "_exec_shell_command",
        lambda *_args, **_kwargs: {"success": True, "data": {"exit_code": 0}},
    )
    monkeypatch.setattr(
        cli_file,
        "_download_remote_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            cli_file.requests.ConnectionError("download interrupted")
        ),
    )
    monkeypatch.setattr(
        cli_file,
        "_cleanup_remote_file",
        lambda _session, remote_path: events.append(remote_path),
    )

    with pytest.raises(cli_file.requests.ConnectionError, match="download interrupted"):
        cli_file._download_scp_source(
            {"endpoint": "https://sandbox.example.com"},
            source="/tmp/input.txt",
            destination=tmp_path / "output.txt",
        )

    assert events == ["/tmp/agentkit-download-fixed.tar"]


def test_cleanup_remote_file_warns_without_raising(monkeypatch, capsys) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    monkeypatch.setattr(
        cli_file,
        "_exec_shell_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    cli_file._cleanup_remote_file(
        {"endpoint": "https://sandbox.example.com"},
        "/tmp/archive.tar",
    )

    assert "Warning: failed to remove remote temporary file" in capsys.readouterr().err


def test_scp_reports_transport_error_without_traceback(monkeypatch, tmp_path) -> None:
    from agentkit.toolkit.cli.cli import app
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    _patch_session(monkeypatch, tmp_path, cli_file)
    source = tmp_path / "input.txt"
    source.write_text("content", encoding="utf-8")
    monkeypatch.setattr(
        cli_file,
        "_upload_scp_source",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            cli_file.requests.ConnectionError("network unavailable")
        ),
    )

    result = runner.invoke(
        app,
        ["sandbox", "scp", "-s", "user-1", str(source), "sandbox:/tmp/out"],
    )

    assert result.exit_code == 1
    assert "network unavailable" in result.output
    assert "Traceback" not in result.output


def test_create_sources_upload_archive_removes_temp_file_on_tar_error(
    monkeypatch,
    tmp_path,
) -> None:
    import agentkit.toolkit.cli.sandbox.cli_file as cli_file

    source = tmp_path / "input.txt"
    source.write_text("content", encoding="utf-8")

    monkeypatch.setattr(
        cli_file.tarfile,
        "open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(tarfile.TarError("boom")),
    )

    with pytest.raises(tarfile.TarError):
        cli_file._create_sources_upload_archive([source])

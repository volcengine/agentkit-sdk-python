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

"""File transfer commands for sandbox CLI."""

from __future__ import annotations

import os
from pathlib import Path
import posixpath
import shlex
import shutil
import tarfile
import tempfile
from typing import Optional
import uuid

import requests
import typer

from agentkit.toolkit.cli.sandbox.agentkit_client import AgentkitToolsClient
from agentkit.toolkit.cli.sandbox.session_create import SANDBOX_TOOL_ID_ENV
from agentkit.toolkit.cli.sandbox.session_sync import sync_remote_sessions
from agentkit.toolkit.cli.sandbox.tool_resolve import SandboxToolType
from agentkit.toolkit.cli.sandbox.sandbox_client import (
    SANDBOX_EXEC_TIMEOUT_SECONDS,
    SANDBOX_FILE_DOWNLOAD_ROUTE,
    SANDBOX_FILE_UPLOAD_ROUTE,
    build_exec_url,
    build_file_url,
    echo_json,
    error,
    get_session_result,
)

SANDBOX_FILE_TIMEOUT_SECONDS = 300
SANDBOX_REMOTE_TMP_DIR = "/tmp"
SANDBOX_OPERAND_PREFIX = "sandbox:"
DEFAULT_SANDBOX_PATH_ROOT = "/home/gem"


def _is_path_inside(path: str, root: str) -> bool:
    normalized_root = root.rstrip("/") or "/"
    if normalized_root == "/":
        return path.startswith("/")
    return path == normalized_root or path.startswith(f"{normalized_root}/")


def _resolve_sandbox_operand(value: str) -> str:
    if not value.startswith(SANDBOX_OPERAND_PREFIX):
        error(f"Sandbox path must start with {SANDBOX_OPERAND_PREFIX}")

    raw = value[len(SANDBOX_OPERAND_PREFIX) :].strip()
    if not raw:
        error("Sandbox path must not be empty")
    if "\x00" in raw:
        error("Sandbox path must not contain NUL bytes")

    if raw.startswith("/"):
        return posixpath.normpath(raw)

    resolved = posixpath.normpath(posixpath.join(DEFAULT_SANDBOX_PATH_ROOT, raw))
    if not _is_path_inside(resolved, DEFAULT_SANDBOX_PATH_ROOT):
        error(f"Relative sandbox path must stay inside {DEFAULT_SANDBOX_PATH_ROOT}")
    return resolved


def _resolve_scp_operands(
    source: str,
    destination: str,
) -> tuple[str, Path | str, Path | str]:
    source_is_sandbox = source.startswith(SANDBOX_OPERAND_PREFIX)
    destination_is_sandbox = destination.startswith(SANDBOX_OPERAND_PREFIX)
    if source_is_sandbox == destination_is_sandbox:
        error(
            "Exactly one of SOURCE and DESTINATION must start with "
            f"{SANDBOX_OPERAND_PREFIX}"
        )

    if source_is_sandbox:
        return "download", _resolve_sandbox_operand(source), Path(destination)
    return "upload", Path(source), _resolve_sandbox_operand(destination)


def _new_remote_archive_path(prefix: str) -> str:
    return f"{SANDBOX_REMOTE_TMP_DIR}/{prefix}-{uuid.uuid4().hex}.tar"


def _format_response_error(response: requests.Response, action: str) -> str:
    message = response.text.strip()
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, list):
            messages = []
            for item in detail:
                if isinstance(item, dict):
                    loc = ".".join(str(part) for part in item.get("loc", []))
                    msg = item.get("msg")
                    messages.append(f"{loc}: {msg}" if loc and msg else str(item))
                else:
                    messages.append(str(item))
            message = "; ".join(messages)
        elif isinstance(detail, str):
            message = detail
        elif isinstance(payload.get("message"), str):
            message = str(payload["message"])

        metadata = payload.get("ResponseMetadata")
        if isinstance(metadata, dict):
            api_error = metadata.get("Error")
            if isinstance(api_error, dict) and api_error.get("Message"):
                message = str(api_error["Message"])

    return f"Sandbox {action} failed ({response.status_code}): {message}"


def _json_response(response: requests.Response, action: str) -> dict[str, object]:
    if response.status_code >= 400:
        error(_format_response_error(response, action))

    try:
        payload = response.json()
    except ValueError:
        error(f"Invalid sandbox {action} response: {response.text}")

    if not isinstance(payload, dict):
        error(f"Invalid sandbox {action} response: expected JSON object")
    if payload.get("success") is False:
        message = payload.get("message")
        error(str(message or f"Sandbox {action} failed"))
    return payload


def _resolve_existing_session(
    *,
    session_id: str,
    tool_id: Optional[str],
    tool_type: SandboxToolType,
) -> dict[str, object]:
    client = AgentkitToolsClient()
    resolved_tool_id = sync_remote_sessions(
        session_id=session_id,
        tool_id=tool_id,
        tool_type=tool_type,
        client=client,
        env_var_name=SANDBOX_TOOL_ID_ENV,
    )
    result = get_session_result(session_id)
    if resolved_tool_id and result.get("tool_id") != resolved_tool_id:
        error(f"Sandbox session not found: {session_id}")
    return result


def _shell_error(message: str, *, quiet_errors: bool) -> None:
    if quiet_errors:
        raise RuntimeError(message)
    error(message)


def _exec_shell_command(
    session: dict[str, object],
    command: str,
    *,
    shell_id: str = "",
    exec_dir: str = "",
    quiet_errors: bool = False,
) -> dict[str, object]:
    response = requests.post(
        build_exec_url(session.get("endpoint")),
        json={"id": shell_id, "exec_dir": exec_dir, "command": command},
        timeout=SANDBOX_EXEC_TIMEOUT_SECONDS,
    )
    payload = _json_response(response, "shell exec")
    data = payload.get("data")
    if not isinstance(data, dict):
        return payload

    status = data.get("status")
    if status and status != "completed":
        output = data.get("output")
        message = output if isinstance(output, str) and output.strip() else payload
        _shell_error(
            f"Sandbox shell command did not complete: {message}",
            quiet_errors=quiet_errors,
        )
    if data.get("exit_code") not in (None, 0):
        output = data.get("output")
        message = output if isinstance(output, str) and output.strip() else payload
        _shell_error(
            f"Sandbox shell command failed: {message}",
            quiet_errors=quiet_errors,
        )
    return payload


def _cleanup_remote_file(session: dict[str, object], remote_path: str) -> None:
    try:
        _exec_shell_command(
            session,
            f"rm -f {shlex.quote(remote_path)}",
            quiet_errors=True,
        )
    except Exception as exc:
        typer.echo(
            f"Warning: failed to remove remote temporary file {remote_path}: {exc}",
            err=True,
        )


def _upload_remote_file(
    session: dict[str, object],
    *,
    local_path: Path,
    remote_path: str,
) -> dict[str, object]:
    url = build_file_url(session.get("endpoint"), SANDBOX_FILE_UPLOAD_ROUTE)
    with local_path.open("rb") as file_obj:
        response = requests.post(
            url,
            data={"path": remote_path},
            files={"file": (local_path.name, file_obj, "application/x-tar")},
            timeout=SANDBOX_FILE_TIMEOUT_SECONDS,
        )
    return _json_response(response, "file upload")


def _download_remote_file(
    session: dict[str, object],
    *,
    remote_path: str,
    local_path: Path,
) -> None:
    response = requests.get(
        build_file_url(session.get("endpoint"), SANDBOX_FILE_DOWNLOAD_ROUTE),
        params={"path": remote_path, "change_policy": "abort"},
        stream=True,
        timeout=SANDBOX_FILE_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        error(_format_response_error(response, "file download"))

    with local_path.open("wb") as file_obj:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                file_obj.write(chunk)


def _archive_source_name(source: Path) -> str:
    return source.name or source.resolve().name


def _add_source_to_archive(tar: tarfile.TarFile, source: Path) -> None:
    source_name = _archive_source_name(source)
    if source.is_dir():
        tar.add(source, arcname=source_name, recursive=False)
        for path in sorted(source.rglob("*")):
            relative_path = path.relative_to(source).as_posix()
            tar.add(
                path,
                arcname=posixpath.join(source_name, relative_path),
                recursive=False,
            )
        return
    tar.add(source, arcname=source_name, recursive=False)


def _create_sources_upload_archive(sources: list[Path]) -> Path:
    fd, name = tempfile.mkstemp(prefix="agentkit-sandbox-upload-", suffix=".tar")
    os.close(fd)
    archive_path = Path(name)
    try:
        with tarfile.open(archive_path, "w") as tar:
            for source in sources:
                _add_source_to_archive(tar, source)
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise
    return archive_path


def _validate_scp_local_source(source: Path) -> Path:
    if not source.exists():
        error(f"Source path not found: {source}")
    if not source.is_file() and not source.is_dir():
        error(f"Source path is not a file or directory: {source}")
    if not _archive_source_name(source):
        error(f"Source path must have a file or directory name: {source}")
    return source


def _build_remote_scp_upload_command(
    *,
    archive_path: str,
    source_name: str,
    destination: str,
) -> str:
    stage_dir = f"{archive_path}.d"
    cleanup = f"rm -rf {shlex.quote(stage_dir)}; rm -f {shlex.quote(archive_path)}"
    staged_source = posixpath.join(stage_dir, source_name)
    return (
        f"trap {shlex.quote(cleanup)} EXIT; "
        f"mkdir -p {shlex.quote(stage_dir)} && "
        f"tar -xf {shlex.quote(archive_path)} -C {shlex.quote(stage_dir)} && "
        f"cp -R -- {shlex.quote(staged_source)} {shlex.quote(destination)}"
    )


def _upload_scp_source(
    session: dict[str, object],
    *,
    source: Path,
    destination: str,
) -> None:
    resolved_source = _validate_scp_local_source(source)
    archive_path = _create_sources_upload_archive([resolved_source])
    remote_archive_path = _new_remote_archive_path("agentkit-upload")
    try:
        _upload_remote_file(
            session,
            local_path=archive_path,
            remote_path=remote_archive_path,
        )
        _exec_shell_command(
            session,
            _build_remote_scp_upload_command(
                archive_path=remote_archive_path,
                source_name=_archive_source_name(resolved_source),
                destination=destination,
            ),
        )
    except Exception:
        # Upload failures are ambiguous: the remote API may have persisted the
        # archive before the client observed a transport error.
        _cleanup_remote_file(session, remote_archive_path)
        raise
    finally:
        archive_path.unlink(missing_ok=True)


def _safe_members(
    tar: tarfile.TarFile,
    *,
    download_dir: Path,
    overwrite: bool,
) -> list[tarfile.TarInfo]:
    download_root = download_dir.resolve()
    members = tar.getmembers()
    for member in members:
        name = member.name
        normalized = posixpath.normpath(name)
        if posixpath.isabs(name) or normalized == ".." or normalized.startswith("../"):
            error(f"Unsafe archive member path: {name}")
        if member.issym() or member.islnk():
            error(f"Archive member links are not supported: {name}")
        if not member.isdir() and not member.isfile():
            error(f"Unsupported archive member type: {name}")
        if normalized in {"", "."}:
            continue

        target_path = (download_dir / normalized).resolve()
        try:
            target_path.relative_to(download_root)
        except ValueError:
            error(f"Unsafe archive member path: {name}")
        if target_path.exists() and member.isfile() and not overwrite:
            error(f"Download target already exists: {target_path}")
    return members


def _extract_archive(
    archive_path: Path,
    *,
    download_dir: Path,
    overwrite: bool,
) -> None:
    try:
        with tarfile.open(archive_path, "r") as tar:
            for member in _safe_members(
                tar,
                download_dir=download_dir,
                overwrite=overwrite,
            ):
                normalized = posixpath.normpath(member.name)
                if normalized in {"", "."}:
                    continue

                target_path = download_dir / normalized
                if member.isdir():
                    target_path.mkdir(parents=True, exist_ok=True)
                    continue
                if member.isfile():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    source = tar.extractfile(member)
                    if source is None:
                        error(f"Invalid archive member: {member.name}")
                    with source, target_path.open("wb") as target:
                        shutil.copyfileobj(source, target, length=1024 * 1024)
    except tarfile.TarError as exc:
        error(f"Invalid sandbox download archive: {exc}")


def _shell_output(payload: dict[str, object]) -> str:
    data = payload.get("data")
    if not isinstance(data, dict):
        return ""
    output = data.get("output")
    return output.strip() if isinstance(output, str) else ""


def _remote_source_type(session: dict[str, object], source: str) -> str:
    quoted_source = shlex.quote(source)
    payload = _exec_shell_command(
        session,
        "if test -f {source}; then printf 'file'; "
        "elif test -d {source}; then printf 'directory'; "
        "else printf 'missing'; fi".format(
            source=quoted_source,
        ),
    )
    source_type = _shell_output(payload)
    if source_type == "missing":
        error(f"Source path not found: {source}")
    if source_type not in {"file", "directory"}:
        error(f"Unable to determine sandbox source type: {source}")
    return source_type


def _remote_source_name(source: str) -> str | None:
    return posixpath.basename(source.rstrip("/")) or None


def _build_remote_scp_archive_command(
    *,
    archive_path: str,
    source: str,
) -> str:
    quoted_archive = shlex.quote(archive_path)
    source_name = _remote_source_name(source)
    if source_name is None:
        tar_command = f"tar -cf {quoted_archive} -C / ."
    else:
        source_dir = posixpath.dirname(source) or "/"
        tar_command = (
            f"tar -cf {quoted_archive} -C {shlex.quote(source_dir)} "
            f"{shlex.quote(source_name)}"
        )
    return (
        f"{tar_command}; status=$?; "
        f"[ $status -eq 0 ] || rm -f {quoted_archive}; [ $status -eq 0 ]"
    )


def _copy_downloaded_source(
    source: Path,
    destination: Path,
    *,
    source_name: str | None = None,
) -> Path:
    name = source.name if source_name is None else source_name
    target = destination / name if destination.is_dir() and name else destination
    if not target.parent.is_dir():
        error(f"Destination parent directory not found: {target.parent}")

    if source.is_dir():
        if target.exists() and not target.is_dir():
            error(f"Cannot overwrite file with directory: {target}")
        shutil.copytree(source, target, dirs_exist_ok=True, copy_function=shutil.copy2)
        return target

    if not source.is_file():
        error(f"Downloaded source is not a file or directory: {source}")
    if target.exists() and target.is_dir():
        error(f"Cannot overwrite directory with file: {target}")
    shutil.copy2(source, target)
    return target


def _download_scp_source(
    session: dict[str, object],
    *,
    source: str,
    destination: Path,
) -> Path:
    _remote_source_type(session, source)
    source_name = _remote_source_name(source)
    remote_archive_path = _new_remote_archive_path("agentkit-download")
    try:
        _exec_shell_command(
            session,
            _build_remote_scp_archive_command(
                archive_path=remote_archive_path,
                source=source,
            ),
        )
        with tempfile.TemporaryDirectory(prefix="agentkit-sandbox-download-") as name:
            temp_dir = Path(name)
            archive_path = temp_dir / "download.tar"
            stage_dir = temp_dir / "stage"
            stage_dir.mkdir()
            _download_remote_file(
                session,
                remote_path=remote_archive_path,
                local_path=archive_path,
            )
            _extract_archive(archive_path, download_dir=stage_dir, overwrite=True)
            staged_source = stage_dir / source_name if source_name else stage_dir
            return _copy_downloaded_source(
                staged_source,
                destination,
                source_name=source_name or "",
            )
    finally:
        _cleanup_remote_file(session, remote_archive_path)


def scp_command(
    source: str = typer.Argument(..., metavar="SOURCE"),
    destination: str = typer.Argument(..., metavar="DESTINATION"),
    session_id: str = typer.Option(
        ...,
        "--session-id",
        "--sid",
        "-s",
        help="Sandbox session ID used for the transfer.",
    ),
    tool_id: Optional[str] = typer.Option(
        None,
        "--tool-id",
        help=f"Sandbox tool ID. Defaults to {SANDBOX_TOOL_ID_ENV}.",
    ),
    tool_type: SandboxToolType = typer.Option(
        SandboxToolType.CODE_ENV,
        "--tool-type",
        help="Sandbox tool type to resolve when --tool-id is omitted.",
    ),
) -> None:
    """Copy one file or directory between local storage and a sandbox session."""
    try:
        direction, local_operand, sandbox_operand = _resolve_scp_operands(
            source,
            destination,
        )
        session = _resolve_existing_session(
            session_id=session_id,
            tool_id=tool_id,
            tool_type=tool_type,
        )
        if direction == "upload":
            local_path = local_operand
            remote_path = sandbox_operand
            if not isinstance(local_path, Path) or not isinstance(remote_path, str):
                raise RuntimeError("Invalid resolved upload operands")
            _upload_scp_source(
                session,
                source=local_path,
                destination=remote_path,
            )
            result_local_path = local_path
        else:
            remote_path = local_operand
            local_path = sandbox_operand
            if not isinstance(remote_path, str) or not isinstance(local_path, Path):
                raise RuntimeError("Invalid resolved download operands")
            result_local_path = _download_scp_source(
                session,
                source=remote_path,
                destination=local_path,
            )
    except typer.Exit:
        raise
    except requests.RequestException as exc:
        error(str(exc))
    except Exception as exc:
        error(str(exc))

    echo_json(
        {
            "direction": direction,
            "session_id": session_id,
            "local_path": str(result_local_path),
            "remote_path": remote_path,
        }
    )

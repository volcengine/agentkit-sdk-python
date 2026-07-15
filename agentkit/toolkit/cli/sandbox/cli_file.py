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
from agentkit.toolkit.cli.sandbox.config_store import (
    SandboxConfigError,
    config_default_str,
    configured_sandbox_config,
    param_was_provided,
)
from agentkit.toolkit.cli.sandbox.session_create import SANDBOX_TOOL_ID_ENV
from agentkit.toolkit.cli.sandbox.session_sync import sync_remote_sessions
from agentkit.toolkit.cli.sandbox.tool_resolve import SandboxToolType
from agentkit.toolkit.cli.sandbox.sandbox_client import (
    SANDBOX_EXEC_TIMEOUT_SECONDS,
    SANDBOX_FILE_DOWNLOAD_ROUTE,
    SANDBOX_FILE_LIST_ROUTE,
    SANDBOX_FILE_UPLOAD_ROUTE,
    build_exec_url,
    build_file_url,
    echo_json,
    error,
    get_session_result,
)

SANDBOX_FILE_TIMEOUT_SECONDS = 300
SANDBOX_REMOTE_TMP_DIR = "/tmp"
SANDBOX_FILE_SORT_KEYS = {"name", "size", "modified", "type"}


file_command = typer.Typer(
    name="file",
    help="Upload, download, and list files in sandbox sessions.",
    no_args_is_help=True,
)


def _normalize_workspace(workspace: Optional[str]) -> str | None:
    resolved = (workspace or "").strip()
    if not resolved:
        return None
    return _normalize_absolute_sandbox_path(resolved, "--workspace")


def _normalize_absolute_sandbox_path(path: str, option_name: str) -> str:
    if "\x00" in path:
        error(f"{option_name} must not contain NUL bytes")
    if not path.startswith("/"):
        error(f"{option_name} must be an absolute sandbox path")
    return posixpath.normpath(path)


def _is_path_inside(path: str, root: str) -> bool:
    normalized_root = root.rstrip("/") or "/"
    if normalized_root == "/":
        return path.startswith("/")
    return path == normalized_root or path.startswith(f"{normalized_root}/")


def _resolve_sandbox_path(
    value: Optional[str],
    *,
    workspace: str | None,
    option_name: str,
    default_without_workspace: str | None = None,
) -> str:
    raw = (value or "").strip()
    if not raw:
        if workspace:
            return workspace
        if default_without_workspace:
            return default_without_workspace
        error(f"{option_name} is required")

    if raw.startswith("/"):
        resolved = _normalize_absolute_sandbox_path(raw, option_name)
    else:
        if not workspace:
            error(f"{option_name} must be absolute when --workspace is omitted")
        resolved = _normalize_absolute_sandbox_path(
            posixpath.join(workspace, raw),
            option_name,
        )

    if workspace and not _is_path_inside(resolved, workspace):
        error(f"{option_name} must be inside --workspace")
    return resolved


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
    tool_name: Optional[str],
    tool_type: SandboxToolType,
) -> dict[str, object]:
    client = AgentkitToolsClient()
    resolved_tool_id = sync_remote_sessions(
        session_id=session_id,
        tool_id=tool_id,
        tool_name=tool_name,
        tool_type=tool_type,
        client=client,
        env_var_name=SANDBOX_TOOL_ID_ENV,
    )
    if not resolved_tool_id:
        error(f"Sandbox session not found: {session_id}")
    result = get_session_result(resolved_tool_id, session_id)
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


def _list_remote_path(
    session: dict[str, object],
    *,
    path: str,
    recursive: bool,
    show_hidden: bool,
    max_depth: Optional[int],
    include_size: bool,
    include_permissions: bool,
    sort_by: str,
    sort_desc: bool,
) -> dict[str, object]:
    response = requests.post(
        build_file_url(session.get("endpoint"), SANDBOX_FILE_LIST_ROUTE),
        json={
            "path": path,
            "recursive": recursive,
            "show_hidden": show_hidden,
            "max_depth": max_depth,
            "include_size": include_size,
            "include_permissions": include_permissions,
            "sort_by": sort_by,
            "sort_desc": sort_desc,
        },
        timeout=SANDBOX_FILE_TIMEOUT_SECONDS,
    )
    return _json_response(response, "file list")


def _paths_or_empty(paths: Optional[list[Path]]) -> list[Path]:
    return list(paths or [])


def _strings_or_empty(values: Optional[list[str]]) -> list[str]:
    return list(values or [])


def _validate_upload_inputs(
    upload_dir: Optional[list[Path]],
    upload_files: Optional[list[Path]],
) -> tuple[Path | None, list[Path]]:
    dirs = _paths_or_empty(upload_dir)
    files = _paths_or_empty(upload_files)
    if dirs and files:
        error("Use either --src-dir or FILE..., not both")
    if not dirs and not files:
        error("Provide --src-dir or one or more FILE arguments")
    if len(dirs) > 1:
        error("--src-dir accepts one directory")

    if dirs:
        directory = dirs[0]
        if not directory.exists():
            error(f"Source directory not found: {directory}")
        if not directory.is_dir():
            error(f"Source path is not a directory: {directory}")
        return directory, []

    seen_names: set[str] = set()
    resolved_files = []
    for file_path in files:
        if not file_path.exists():
            error(f"Source file not found: {file_path}")
        if not file_path.is_file():
            error(f"Source path is not a file: {file_path}")
        if file_path.name in seen_names:
            error(f"Duplicate source file name: {file_path.name}")
        seen_names.add(file_path.name)
        resolved_files.append(file_path)
    return None, resolved_files


def _add_directory_contents(tar: tarfile.TarFile, directory: Path) -> None:
    for path in sorted(directory.rglob("*")):
        tar.add(
            path,
            arcname=path.relative_to(directory).as_posix(),
            recursive=False,
        )


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


def _create_upload_archive(
    *,
    upload_dir: Path | None,
    upload_files: list[Path],
) -> Path:
    fd, name = tempfile.mkstemp(prefix="agentkit-sandbox-upload-", suffix=".tar")
    os.close(fd)
    archive_path = Path(name)
    try:
        with tarfile.open(archive_path, "w") as tar:
            if upload_dir:
                _add_directory_contents(tar, upload_dir)
            else:
                for file_path in upload_files:
                    tar.add(file_path, arcname=file_path.name, recursive=False)
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise
    return archive_path


def _build_remote_extract_command(
    *,
    archive_path: str,
    dst_dir: str,
) -> str:
    quoted_archive = shlex.quote(archive_path)
    quoted_dst = shlex.quote(dst_dir)
    return (
        f"mkdir -p {quoted_dst} && tar -xf {quoted_archive} -C {quoted_dst}; "
        f"status=$?; rm -f {quoted_archive}; [ $status -eq 0 ]"
    )


def _validate_download_inputs(
    sandbox_dir: Optional[str],
    sandbox_files: Optional[list[str]],
    *,
    workspace: str | None,
) -> tuple[str, list[str]]:
    files = _strings_or_empty(sandbox_files)
    has_dir = bool((sandbox_dir or "").strip())
    if has_dir and files:
        error("Use either --src-dir or FILE..., not both")
    if not has_dir and not files:
        error("Provide --src-dir or one or more FILE arguments")

    if has_dir:
        return (
            "directory",
            [
                _resolve_sandbox_path(
                    sandbox_dir,
                    workspace=workspace,
                    option_name="--src-dir",
                )
            ],
        )

    resolved_files = [
        _resolve_sandbox_path(
            file_path,
            workspace=workspace,
            option_name="FILE",
        )
        for file_path in files
    ]
    seen_names: set[str] = set()
    for file_path in resolved_files:
        name = posixpath.basename(file_path)
        if not name:
            error(f"Invalid FILE path: {file_path}")
        if name in seen_names:
            error(f"Duplicate source file name: {name}")
        seen_names.add(name)
    return "files", resolved_files


def _build_remote_archive_command(
    *,
    archive_path: str,
    source_mode: str,
    sources: list[str],
) -> str:
    quoted_archive = shlex.quote(archive_path)
    if source_mode == "directory":
        quoted_source = shlex.quote(sources[0])
        return (
            f"tar -cf {quoted_archive} -C {quoted_source} .; "
            f"status=$?; [ $status -eq 0 ] || rm -f {quoted_archive}; "
            f"[ $status -eq 0 ]"
        )

    command = f"tar -cf {quoted_archive}"
    for source in sources:
        directory = posixpath.dirname(source) or "/"
        name = posixpath.basename(source)
        command += f" -C {shlex.quote(directory)} {shlex.quote(name)}"
    return (
        f"{command}; "
        f"status=$?; [ $status -eq 0 ] || rm -f {quoted_archive}; "
        f"[ $status -eq 0 ]"
    )


def _build_remote_source_validation_command(
    *,
    source_mode: str,
    sources: list[str],
) -> str:
    commands = []
    for source in sources:
        quoted_source = shlex.quote(source)
        if source_mode == "directory":
            commands.append(
                f"if ! test -e {quoted_source}; then "
                f"echo {shlex.quote(f'Source directory not found: {source}')}; "
                f"false; elif ! test -d {quoted_source}; then "
                f"echo {shlex.quote(f'Source path is not a directory: {source}')}; "
                "false; else true; fi"
            )
        else:
            commands.append(
                f"if ! test -e {quoted_source}; then "
                f"echo {shlex.quote(f'Source file not found: {source}')}; "
                f"false; elif ! test -f {quoted_source}; then "
                f"echo {shlex.quote(f'Source path is not a file: {source}')}; "
                "false; else true; fi"
            )
    return " && ".join(commands)


def _validate_local_download_dir(download_dir: Path) -> Path:
    if download_dir.exists() and not download_dir.is_dir():
        error(f"Download path is not a directory: {download_dir}")
    download_dir.mkdir(parents=True, exist_ok=True)
    return download_dir


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


def file_upload_command(
    ctx: typer.Context,
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        "--sid",
        "-s",
        help="Sandbox session ID to upload into.",
    ),
    workspace: Optional[str] = typer.Option(
        None,
        "--workspace",
        help=(
            "Optional sandbox workspace root. Relative --dst-dir values are "
            "resolved inside this directory."
        ),
    ),
    upload_dir: Optional[list[Path]] = typer.Option(
        None,
        "--src-dir",
        help=(
            "Local directory whose contents are uploaded. May be used once. "
            "Use FILE... for single or multiple files."
        ),
    ),
    files: Optional[list[Path]] = typer.Argument(
        None,
        metavar="FILE...",
        help="Local files to upload.",
    ),
    dst_dir: Optional[str] = typer.Option(
        None,
        "--dst-dir",
        help=(
            "Sandbox destination directory. Relative paths require --workspace. "
            "The directory is created when it does not exist."
        ),
    ),
    tool_id: Optional[str] = typer.Option(
        None,
        "--tool-id",
        help=f"Sandbox tool ID. Defaults to {SANDBOX_TOOL_ID_ENV}.",
    ),
    tool_name: Optional[str] = typer.Option(
        None,
        "--tool-name",
        help="Sandbox tool name. Resolved with ListTools(Name=...).",
    ),
    tool_type: SandboxToolType = typer.Option(
        SandboxToolType.CODE_ENV,
        "--tool-type",
        help="Sandbox tool type to resolve when tool id/name is omitted.",
    ),
) -> None:
    """Upload a local directory or one or more files into a sandbox session."""
    try:
        config_defaults = configured_sandbox_config()
        if not param_was_provided(ctx, "session_id"):
            session_id = (
                config_default_str("session-id", data=config_defaults) or session_id
            )
        if not param_was_provided(ctx, "workspace"):
            workspace = (
                config_default_str("workspace", data=config_defaults) or workspace
            )
        if not param_was_provided(ctx, "dst_dir"):
            dst_dir = config_default_str("dst-dir", data=config_defaults) or dst_dir
        if not param_was_provided(ctx, "tool_id") and not param_was_provided(
            ctx, "tool_name"
        ):
            tool_id = config_default_str("tool-id", data=config_defaults) or tool_id
        if not param_was_provided(ctx, "tool_type"):
            configured_tool_type = config_default_str(
                "tool-type",
                data=config_defaults,
            )
            if configured_tool_type:
                tool_type = SandboxToolType(configured_tool_type)
        if not session_id:
            error("--session-id is required")
        resolved_workspace = _normalize_workspace(workspace)
        resolved_dst_dir = _resolve_sandbox_path(
            dst_dir,
            workspace=resolved_workspace,
            option_name="--dst-dir",
        )
        resolved_upload_dir, resolved_upload_files = _validate_upload_inputs(
            upload_dir,
            files,
        )
        session = _resolve_existing_session(
            session_id=session_id,
            tool_id=tool_id,
            tool_name=tool_name,
            tool_type=tool_type,
        )
        archive_path = _create_upload_archive(
            upload_dir=resolved_upload_dir,
            upload_files=resolved_upload_files,
        )
        remote_archive_path = _new_remote_archive_path("agentkit-upload")
        try:
            _upload_remote_file(
                session,
                local_path=archive_path,
                remote_path=remote_archive_path,
            )
            _exec_shell_command(
                session,
                _build_remote_extract_command(
                    archive_path=remote_archive_path,
                    dst_dir=resolved_dst_dir,
                ),
            )
        finally:
            archive_path.unlink(missing_ok=True)
    except typer.Exit:
        raise
    except (SandboxConfigError, ValueError) as exc:
        error(str(exc))
    except requests.RequestException as exc:
        error(str(exc))
    except Exception as exc:
        error(str(exc))

    sources: list[str]
    if resolved_upload_dir:
        sources = [str(resolved_upload_dir)]
    else:
        sources = [str(file_path) for file_path in resolved_upload_files]
    echo_json(
        {
            "session_id": session_id,
            "workspace": resolved_workspace,
            "dst_dir": resolved_dst_dir,
            "sources": sources,
        }
    )


def file_download_command(
    ctx: typer.Context,
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        "--sid",
        "-s",
        help="Sandbox session ID to download from.",
    ),
    workspace: Optional[str] = typer.Option(
        None,
        "--workspace",
        help=(
            "Optional sandbox workspace root. Relative --src-dir and FILE "
            "values are resolved inside this directory."
        ),
    ),
    sandbox_dir: Optional[str] = typer.Option(
        None,
        "--src-dir",
        help="Sandbox directory whose contents are downloaded.",
    ),
    files: Optional[list[str]] = typer.Argument(
        None,
        metavar="FILE...",
        help="Sandbox files to download.",
    ),
    dst_dir: Path = typer.Option(
        ...,
        "--dst-dir",
        help="Local directory where downloaded contents are extracted.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing local files while extracting the download archive.",
    ),
    tool_id: Optional[str] = typer.Option(
        None,
        "--tool-id",
        help=f"Sandbox tool ID. Defaults to {SANDBOX_TOOL_ID_ENV}.",
    ),
    tool_name: Optional[str] = typer.Option(
        None,
        "--tool-name",
        help="Sandbox tool name. Resolved with ListTools(Name=...).",
    ),
    tool_type: SandboxToolType = typer.Option(
        SandboxToolType.CODE_ENV,
        "--tool-type",
        help="Sandbox tool type to resolve when tool id/name is omitted.",
    ),
) -> None:
    """Download a sandbox directory or one or more files."""
    local_archive_path: Path | None = None
    try:
        config_defaults = configured_sandbox_config()
        if not param_was_provided(ctx, "session_id"):
            session_id = (
                config_default_str("session-id", data=config_defaults) or session_id
            )
        if not param_was_provided(ctx, "workspace"):
            workspace = (
                config_default_str("workspace", data=config_defaults) or workspace
            )
        if not param_was_provided(ctx, "tool_id") and not param_was_provided(
            ctx, "tool_name"
        ):
            tool_id = config_default_str("tool-id", data=config_defaults) or tool_id
        if not param_was_provided(ctx, "tool_type"):
            configured_tool_type = config_default_str(
                "tool-type",
                data=config_defaults,
            )
            if configured_tool_type:
                tool_type = SandboxToolType(configured_tool_type)
        if not session_id:
            error("--session-id is required")
        resolved_workspace = _normalize_workspace(workspace)
        source_mode, sources = _validate_download_inputs(
            sandbox_dir,
            files,
            workspace=resolved_workspace,
        )
        resolved_download_dir = _validate_local_download_dir(dst_dir)
        session = _resolve_existing_session(
            session_id=session_id,
            tool_id=tool_id,
            tool_name=tool_name,
            tool_type=tool_type,
        )
        _exec_shell_command(
            session,
            _build_remote_source_validation_command(
                source_mode=source_mode,
                sources=sources,
            ),
        )
        remote_archive_path = _new_remote_archive_path("agentkit-download")
        _exec_shell_command(
            session,
            _build_remote_archive_command(
                archive_path=remote_archive_path,
                source_mode=source_mode,
                sources=sources,
            ),
        )

        fd, name = tempfile.mkstemp(
            prefix="agentkit-sandbox-download-",
            suffix=".tar",
        )
        os.close(fd)
        local_archive_path = Path(name)
        try:
            _download_remote_file(
                session,
                remote_path=remote_archive_path,
                local_path=local_archive_path,
            )
            _extract_archive(
                local_archive_path,
                download_dir=resolved_download_dir,
                overwrite=overwrite,
            )
        finally:
            _cleanup_remote_file(session, remote_archive_path)
    except typer.Exit:
        raise
    except (SandboxConfigError, ValueError) as exc:
        error(str(exc))
    except requests.RequestException as exc:
        error(str(exc))
    except Exception as exc:
        error(str(exc))
    finally:
        if local_archive_path:
            local_archive_path.unlink(missing_ok=True)

    echo_json(
        {
            "session_id": session_id,
            "workspace": resolved_workspace,
            "dst_dir": str(resolved_download_dir),
            "sources": sources,
        }
    )


def file_list_command(
    ctx: typer.Context,
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        "--sid",
        "-s",
        help="Sandbox session ID to list files from.",
    ),
    workspace: Optional[str] = typer.Option(
        None,
        "--workspace",
        help=(
            "Optional sandbox workspace root. Relative PATH values are "
            "resolved inside it."
        ),
    ),
    path: str = typer.Argument(
        ...,
        metavar="PATH",
        help="Sandbox path to list. Relative paths require --workspace.",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive/--no-recursive",
        help="List files recursively.",
    ),
    show_hidden: bool = typer.Option(
        False,
        "--show-hidden/--hide-hidden",
        help="Include hidden files.",
    ),
    max_depth: Optional[int] = typer.Option(
        None,
        "--max-depth",
        help="Maximum recursive listing depth.",
    ),
    include_size: bool = typer.Option(
        True,
        "--include-size/--no-include-size",
        help="Include file size metadata.",
    ),
    include_permissions: bool = typer.Option(
        False,
        "--include-permissions",
        help="Include file permission metadata.",
    ),
    sort_by: str = typer.Option(
        "name",
        "--sort-by",
        help="Sort key: name, size, modified, or type.",
    ),
    sort_desc: bool = typer.Option(
        False,
        "--sort-desc",
        help="Sort in descending order.",
    ),
    tool_id: Optional[str] = typer.Option(
        None,
        "--tool-id",
        help=f"Sandbox tool ID. Defaults to {SANDBOX_TOOL_ID_ENV}.",
    ),
    tool_name: Optional[str] = typer.Option(
        None,
        "--tool-name",
        help="Sandbox tool name. Resolved with ListTools(Name=...).",
    ),
    tool_type: SandboxToolType = typer.Option(
        SandboxToolType.CODE_ENV,
        "--tool-type",
        help="Sandbox tool type to resolve when tool id/name is omitted.",
    ),
) -> None:
    """List files and directories in a sandbox workspace or path."""
    try:
        config_defaults = configured_sandbox_config()
        if not param_was_provided(ctx, "session_id"):
            session_id = (
                config_default_str("session-id", data=config_defaults) or session_id
            )
        if not param_was_provided(ctx, "workspace"):
            workspace = (
                config_default_str("workspace", data=config_defaults) or workspace
            )
        if not param_was_provided(ctx, "tool_id") and not param_was_provided(
            ctx, "tool_name"
        ):
            tool_id = config_default_str("tool-id", data=config_defaults) or tool_id
        if not param_was_provided(ctx, "tool_type"):
            configured_tool_type = config_default_str(
                "tool-type",
                data=config_defaults,
            )
            if configured_tool_type:
                tool_type = SandboxToolType(configured_tool_type)
        if not session_id:
            error("--session-id is required")
        if max_depth is not None and max_depth < 0:
            error("--max-depth must be greater than or equal to 0")
        if sort_by not in SANDBOX_FILE_SORT_KEYS:
            error("--sort-by must be one of: name, size, modified, type")

        resolved_workspace = _normalize_workspace(workspace)
        resolved_sandbox_dir = _resolve_sandbox_path(
            path,
            workspace=resolved_workspace,
            option_name="PATH",
        )
        session = _resolve_existing_session(
            session_id=session_id,
            tool_id=tool_id,
            tool_name=tool_name,
            tool_type=tool_type,
        )
        result = _list_remote_path(
            session,
            path=resolved_sandbox_dir,
            recursive=recursive,
            show_hidden=show_hidden,
            max_depth=max_depth,
            include_size=include_size,
            include_permissions=include_permissions,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )
    except typer.Exit:
        raise
    except (SandboxConfigError, ValueError) as exc:
        error(str(exc))
    except requests.RequestException as exc:
        error(str(exc))
    except Exception as exc:
        error(str(exc))

    echo_json(result)


file_command.command(name="upload")(file_upload_command)
file_command.command(name="download")(file_download_command)
file_command.command(name="list")(file_list_command)

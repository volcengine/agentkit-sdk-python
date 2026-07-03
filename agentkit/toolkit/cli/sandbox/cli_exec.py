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

"""Interactive exec command for sandbox CLI."""

from __future__ import annotations

import json
import os
import select
import shlex
import shutil
import signal
import sys
import termios
import threading
import tty
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import typer

from agentkit.toolkit.cli.sandbox.agentkit_client import AgentkitToolsClient
from agentkit.toolkit.cli.sandbox.cli_file import (
    _build_remote_extract_command,
    _create_sources_upload_archive,
    _exec_shell_command,
    _new_remote_archive_path,
    _normalize_workspace,
    _resolve_sandbox_path,
    _upload_remote_file,
)
from agentkit.toolkit.cli.sandbox.session_create import (
    SANDBOX_TOOL_ID_ENV,
    build_model_envs,
    ensure_sandbox_session,
)
from agentkit.toolkit.cli.sandbox.git_config import apply_git_config_to_session
from agentkit.toolkit.cli.sandbox.model_config import normalize_model_base_url
from agentkit.toolkit.cli.sandbox.tos_config import DEFAULT_SANDBOX_WORKSPACE
from agentkit.toolkit.cli.sandbox.tool_resolve import (
    SandboxToolType,
    find_tool_model_provider,
    get_remote_tool_model_provider,
    get_tool_websearch_config,
)
from agentkit.toolkit.cli.sandbox.sandbox_client import (
    add_session_terminal_shell_id,
    build_terminal_ws_url,
    error,
    find_session_result,
    remove_session_terminal_shell_id,
)

DETACH_SEQUENCE = b"\x1d"
DETACH_HINT = "Ctrl-]"
LOCAL_EXIT_COMMANDS = {"exit", "exit()"}
EXEC_MODE_TMUX = "tmux"


def _terminal_size() -> dict[str, int]:
    size = shutil.get_terminal_size(fallback=(120, 40))
    return {"cols": size.columns, "rows": size.lines}


@contextmanager
def _raw_terminal_mode() -> Iterator[None]:
    if not sys.stdin.isatty():
        yield
        return

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _send_json(ws, payload: dict[str, object]) -> None:
    ws.send(json.dumps(payload, ensure_ascii=False))


def _send_resize(ws) -> None:
    _send_json(ws, {"type": "resize", "data": _terminal_size()})


def _stream_stdin(ws, stop_event: threading.Event) -> None:
    fd = sys.stdin.fileno()
    line_buffer = b""
    while not stop_event.is_set():
        readable, _, _ = select.select([fd], [], [], 0.1)
        if not readable:
            continue

        data = os.read(fd, 4096)
        if not data:
            break

        if DETACH_SEQUENCE in data:
            before_detach = data.split(DETACH_SEQUENCE, 1)[0]
            if before_detach:
                _send_json(
                    ws,
                    {
                        "type": "input",
                        "data": before_detach.decode("utf-8", errors="ignore"),
                    },
                )
            stop_event.set()
            ws.close()
            break

        normalized_data = data.replace(b"\r", b"\n")
        line_buffer += normalized_data
        has_newline = b"\n" in normalized_data
        line_parts = line_buffer.split(b"\n")
        complete_lines = line_parts[:-1]
        line_buffer = line_parts[-1]
        if has_newline and any(_is_local_exit_line(line) for line in complete_lines):
            stop_event.set()
            ws.close()
            break

        _send_json(
            ws,
            {
                "type": "input",
                "data": data.decode("utf-8", errors="ignore"),
            },
        )


def _is_local_exit_line(line: bytes) -> bool:
    text = line.decode("utf-8", errors="ignore").strip()
    if text in LOCAL_EXIT_COMMANDS:
        return True
    return any(text.endswith(f" {command}") for command in LOCAL_EXIT_COMMANDS)


def _write_output(data: object) -> None:
    if data is None:
        return
    sys.stdout.write(str(data))
    sys.stdout.flush()


def _connect_terminal(
    ws_url: str,
    initial_command: Optional[str],
    on_shell_id=None,
) -> None:
    try:
        import websocket
    except ImportError:
        error(
            "websocket-client is required. Install with: pip install websocket-client"
        )

    stop_event = threading.Event()
    initial_command_sent = {"value": False}
    websocket_app = None

    def send_initial_command(ws) -> None:
        if initial_command_sent["value"] or not initial_command:
            return
        initial_command_sent["value"] = True
        _send_json(ws, {"type": "input", "data": f"{initial_command}\n"})

    def on_open(ws) -> None:
        _send_resize(ws)
        thread = threading.Thread(
            target=_stream_stdin,
            args=(ws, stop_event),
            daemon=True,
        )
        thread.start()

    def on_message(ws, message: str) -> None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            _write_output(message)
            return

        message_type = payload.get("type")
        if message_type == "session_id":
            shell_id = payload.get("data")
            if isinstance(shell_id, str) and on_shell_id:
                on_shell_id(shell_id)
            return
        if message_type == "output":
            _write_output(payload.get("data"))
            return
        if message_type == "ready":
            send_initial_command(ws)
            return
        if message_type == "ping":
            timestamp = payload.get("timestamp", payload.get("data"))
            _send_json(ws, {"type": "pong", "data": {"timestamp": timestamp}})
            return
        if message_type == "error":
            _write_output(f"\r\n{payload.get('data')}\r\n")

    def on_close(_ws, _status_code, _message) -> None:
        stop_event.set()

    def on_error(_ws, exc: Exception) -> None:
        stop_event.set()
        error(str(exc))

    def on_resize(_signum, _frame) -> None:
        if websocket_app and websocket_app.sock and websocket_app.sock.connected:
            _send_resize(websocket_app)

    websocket_app = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error,
    )

    sigwinch = getattr(signal, "SIGWINCH", None)
    previous_sigwinch = signal.getsignal(sigwinch) if sigwinch else None
    if sigwinch:
        signal.signal(sigwinch, on_resize)
    try:
        typer.echo(
            f"Press {DETACH_HINT} or type exit/exit() to detach.",
            err=True,
        )
        with _raw_terminal_mode():
            websocket_app.run_forever()
    except KeyboardInterrupt:
        websocket_app.close()
    finally:
        stop_event.set()
        if sigwinch:
            signal.signal(sigwinch, previous_sigwinch)


def _resolve_exec_dst_dir(
    *,
    workspace: Optional[str],
    dst_dir: Optional[str],
) -> str:
    resolved_workspace = _normalize_workspace(workspace) or DEFAULT_SANDBOX_WORKSPACE
    raw_dst_dir = (dst_dir or "").strip()
    if not raw_dst_dir:
        return resolved_workspace
    if raw_dst_dir.startswith("/"):
        error("--dst-dir must be relative to --workspace")
    return _resolve_sandbox_path(
        raw_dst_dir,
        workspace=resolved_workspace,
        option_name="--dst-dir",
    )


def _resolve_exec_upload_sources(src_dirs: list[Path]) -> list[Path]:
    resolved_sources = []
    seen_names: set[str] = set()
    for src_dir in src_dirs:
        if not src_dir.exists():
            error(f"Source path not found: {src_dir}")
        if not src_dir.is_dir() and not src_dir.is_file():
            error(f"Source path is not a file or directory: {src_dir}")
        if src_dir.name in seen_names:
            error(f"Duplicate source name: {src_dir.name}")
        seen_names.add(src_dir.name)
        resolved_sources.append(src_dir)
    return resolved_sources


def _collect_exec_upload_sources(
    ctx: typer.Context,
    src_dir: Optional[Path],
) -> list[Path]:
    src_dirs = [Path(value) for value in ctx.args]
    if src_dirs and not src_dir:
        error("Additional source paths require --src-dir")
    if src_dir:
        src_dirs.insert(0, src_dir)
    return src_dirs


def _upload_source_before_exec(
    session: dict[str, object],
    *,
    workspace: Optional[str],
    src_dirs: list[Path],
    dst_dir: Optional[str],
) -> str:
    resolved_dst_dir = _resolve_exec_dst_dir(
        workspace=workspace,
        dst_dir=dst_dir,
    )
    resolved_sources = _resolve_exec_upload_sources(src_dirs)
    archive_path = _create_sources_upload_archive(resolved_sources)
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
    return resolved_dst_dir


def _resolve_exec_model_tool_id(
    *,
    session_id: Optional[str],
    tool_id: Optional[str],
    model_name: Optional[str],
) -> str | None:
    if not (model_name or "").strip():
        return None
    resolved_tool_id = (tool_id or "").strip()
    if not resolved_tool_id and session_id:
        existing = find_session_result(session_id)
        if existing:
            existing_tool_id = existing.get("tool_id")
            if isinstance(existing_tool_id, str):
                resolved_tool_id = existing_tool_id.strip()

    return resolved_tool_id or None


def _resolve_exec_model_provider(
    *,
    session_id: Optional[str],
    tool_id: Optional[str],
    tool_type: SandboxToolType,
    model_name: Optional[str],
    model_provider: Optional[str],
) -> str | None:
    if model_provider or not (model_name or "").strip():
        return model_provider

    resolved_tool_id = _resolve_exec_model_tool_id(
        session_id=session_id,
        tool_id=tool_id,
        model_name=model_name,
    )
    if not resolved_tool_id:
        return find_tool_model_provider(
            tool_id=None,
            tool_type=tool_type,
        )
    cached_model_provider = find_tool_model_provider(
        tool_id=resolved_tool_id,
        tool_type=tool_type,
    )
    if cached_model_provider:
        return cached_model_provider

    if not (tool_id or "").strip():
        return None

    try:
        return get_remote_tool_model_provider(
            AgentkitToolsClient(),
            resolved_tool_id,
            tool_type=tool_type,
        )
    except Exception:
        return None


def _normalize_exec_mode(mode: Optional[str]) -> Optional[str]:
    resolved = (mode or "").strip()
    if not resolved:
        return None
    if resolved != EXEC_MODE_TMUX:
        error("--mode must be empty or tmux")
    return resolved


def _build_initial_command(
    *,
    command: Optional[str],
    mode: Optional[str],
    session_id: str,
) -> Optional[str]:
    if mode != EXEC_MODE_TMUX:
        return command

    tmux_session_id = shlex.quote(session_id)
    tmux_command = (
        f"tmux has-session -t {tmux_session_id} 2>/dev/null "
        f"&& tmux a -t {tmux_session_id} "
        f"|| tmux new -s {tmux_session_id}"
    )
    if command:
        tmux_command = f"{tmux_command} {command}"
    return tmux_command


def exec_command(
    ctx: typer.Context,
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        "--sid",
        "-s",
        help=(
            "Sandbox session ID. Defaults to a generated UUID and creates "
            "a sandbox session when needed."
        ),
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
    command: Optional[str] = typer.Option(
        None,
        "--command",
        help=(
            "Initial command to run after the exec session is ready. "
            "Omit this option to connect without an initial command."
        ),
    ),
    mode: Optional[str] = typer.Option(
        None,
        "--mode",
        help=(
            "Exec command mode. Omit or pass an empty value for the default "
            "behavior; use 'tmux' to attach to or create a tmux session."
        ),
    ),
    workspace: str = typer.Option(
        DEFAULT_SANDBOX_WORKSPACE,
        "--workspace",
        help=(
            "Sandbox workspace root. Relative --dst-dir values are "
            "resolved inside this directory."
        ),
    ),
    src_dir: Optional[Path] = typer.Option(
        None,
        "--src-dir",
        help=("Local file or directory to upload before opening the exec session."),
    ),
    dst_dir: Optional[str] = typer.Option(
        None,
        "--dst-dir",
        help=(
            "Relative sandbox destination directory for --src-dir. Defaults "
            "to --workspace."
        ),
    ),
    git_config: Optional[str] = typer.Option(
        None,
        "--git-config",
        help=(
            "Git identity source. Use 'local' to read local git config, or "
            "provide an INI/TOML/JSON file path with user.name and user.email."
        ),
    ),
    model_name: Optional[str] = typer.Option(
        None,
        "--model-name",
        help=(
            "Model name to inject into OPENCODE_MODEL, CODEX_MODEL, "
            "and ANTHROPIC_MODEL when creating a sandbox session."
        ),
    ),
    model_api_key: Optional[str] = typer.Option(
        None,
        "--model-api-key",
        help=(
            "Model API key to inject into OPENCODE_API_KEY, CODEX_API_KEY, "
            "and ANTHROPIC_AUTH_TOKEN when creating a sandbox session."
        ),
    ),
    model_provider: Optional[str] = typer.Option(
        None,
        "--model-provider",
        help=(
            "Model provider to use for base URLs, defaults, and model catalog "
            "when creating a sandbox session."
        ),
    ),
    model_base_url: Optional[str] = typer.Option(
        None,
        "--model-base-url",
        help=(
            "Custom model base URL to inject into OPENCODE_BASE_URL, "
            "CODEX_BASE_URL, MODEL_BASE_URL, and ANTHROPIC_BASE_URL "
            "when creating a sandbox session."
        ),
    ),
    disable_websearch_apikey: bool = typer.Option(
        False,
        "--disable-websearch-apikey",
        help=(
            "Disable WEB_SEARCH_API_KEY for this session. "
            "Omit this option to keep the default enabled behavior."
        ),
    ),
) -> None:
    """Open a streaming sandbox exec session. Press Ctrl-] or type exit/exit()."""
    exec_mode = _normalize_exec_mode(mode)
    try:
        resolved_model_provider = _resolve_exec_model_provider(
            session_id=session_id,
            tool_id=tool_id,
            tool_type=tool_type,
            model_name=model_name,
            model_provider=model_provider,
        )
        explicit_model_provider = bool((model_provider or "").strip())
        resolved_model_base_url = normalize_model_base_url(model_base_url)

        resolved_tool_id = (tool_id or "").strip()
        ws_config = get_tool_websearch_config(
            tool_id=resolved_tool_id or None,
            tool_type=tool_type,
        )
        has_role = bool(ws_config and ws_config.get("has_role"))

        disable_websearch = disable_websearch_apikey
        if disable_websearch_apikey and has_role:
            disable_websearch = False
            typer.echo(
                "警告：当前工具使用 IAM Role 模式，--disable-websearch-apikey 不会生效（WebSearch 权限由角色策略控制）。",
                err=True,
            )

        session = ensure_sandbox_session(
            session_id=session_id,
            tool_id=tool_id,
            tool_type=tool_type.value,
            envs=build_model_envs(
                model_name=model_name,
                model_api_key=model_api_key,
                model_provider=resolved_model_provider,
                model_base_url=resolved_model_base_url,
                model_provider_was_provided=explicit_model_provider,
                model_base_url_was_provided=bool(
                    normalize_model_base_url(model_base_url)
                ),
                include_codex_config=tool_type == SandboxToolType.CODE_ENV,
                disable_websearch_apikey=disable_websearch,
            ),
        )
    except typer.Exit:
        raise
    except Exception as exc:
        error(str(exc))

    session_id = session.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        error("Sandbox session missing session_id")

    try:
        src_dirs = _collect_exec_upload_sources(ctx, src_dir)
        if src_dirs:
            _upload_source_before_exec(
                session,
                workspace=workspace,
                src_dirs=src_dirs,
                dst_dir=dst_dir,
            )
    except typer.Exit:
        raise
    except Exception as exc:
        error(str(exc))

    cleanup_shell_ids: list[str] = []
    cleanup_shell_ids_lock = threading.Lock()

    def remember_cleanup_shell_id(remote_shell_id: str) -> None:
        with cleanup_shell_ids_lock:
            if remote_shell_id not in cleanup_shell_ids:
                cleanup_shell_ids.append(remote_shell_id)

    try:
        apply_git_config_to_session(
            session,
            git_config,
        )
    except typer.Exit:
        raise
    except Exception as exc:
        error(str(exc))

    ws_url = build_terminal_ws_url(session.get("endpoint"))
    initial_command = _build_initial_command(
        command=command,
        mode=exec_mode,
        session_id=session_id,
    )

    def on_shell_id(remote_shell_id: str) -> None:
        add_session_terminal_shell_id(session_id, remote_shell_id)
        remember_cleanup_shell_id(remote_shell_id)
        typer.echo(f"Shell ID: {remote_shell_id}", err=True)

    try:
        _connect_terminal(
            ws_url,
            initial_command=initial_command,
            on_shell_id=on_shell_id,
        )
    finally:
        with cleanup_shell_ids_lock:
            shell_ids_to_cleanup = list(cleanup_shell_ids)
        for cleanup_shell_id in shell_ids_to_cleanup:
            remove_session_terminal_shell_id(session_id, cleanup_shell_id)

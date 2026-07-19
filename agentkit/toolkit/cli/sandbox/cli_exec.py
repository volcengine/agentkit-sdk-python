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
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import requests
import typer

from agentkit.toolkit.cli.sandbox.agentkit_client import AgentkitToolsClient
from agentkit.toolkit.cli.sandbox.config_store import (
    SandboxConfigError,
    config_default_if_unprovided,
    config_tool_identifier_defaults_if_unprovided,
    configured_sandbox_config,
    param_was_provided,
)
from agentkit.toolkit.cli.sandbox.cli_scp import (
    SANDBOX_OPERAND_PREFIX,
    _resolve_sandbox_operand,
    _upload_scp_source,
    _validate_scp_local_source,
)
from agentkit.toolkit.cli.sandbox.session_create import (
    SANDBOX_TOOL_ID_ENV,
    build_model_envs,
    ensure_sandbox_session_with_status,
)
from agentkit.toolkit.cli.sandbox.git_config import apply_git_config_to_session
from agentkit.toolkit.cli.sandbox.model_config import (
    build_codex_hot_update_command,
    build_codex_hot_update_env,
    normalize_model_base_url,
    validate_model_provider_base_url,
)
from agentkit.utils.http_defaults import ws_ping_interval, ws_ping_timeout
from agentkit.toolkit.cli.sandbox.tool_resolve import (
    SandboxToolType,
    find_tool_model_provider,
    get_remote_tool_model_provider,
    get_tool_websearch_config,
    resolve_existing_sandbox_tool_id,
)
from agentkit.toolkit.cli.sandbox.sandbox_client import (
    add_session_terminal_shell_id,
    build_bash_exec_url,
    build_terminal_ws_url,
    error,
    remove_session_terminal_shell_id,
)

DETACH_SEQUENCE = b"\x1d"
DETACH_HINT = "Ctrl-]"
LOCAL_EXIT_COMMANDS = {"exit", "exit()"}
EXEC_MODE_TMUX = "tmux"
CODEX_HOT_UPDATE_TIMEOUT_SECONDS = 300
CODEX_HOT_UPDATE_REQUEST_TIMEOUT = 30
CODEX_HOT_UPDATE_REQUEST_HARD_TIMEOUT = 90
IS_WINDOWS = os.name == "nt"


def _terminal_size() -> dict[str, int]:
    size = shutil.get_terminal_size(fallback=(120, 40))
    return {"cols": size.columns, "rows": size.lines}


def _codex_hot_update_requested(
    *,
    model_api_key_was_provided: bool,
    model_name_was_provided: bool,
    model_base_url_was_provided: bool,
) -> bool:
    return (
        model_api_key_was_provided
        or model_name_was_provided
        or model_base_url_was_provided
    )


def _handle_hot_update_response(payload: object) -> None:
    if not isinstance(payload, dict):
        return

    data = payload.get("data")
    if not isinstance(data, dict):
        return

    status = data.get("status")
    if status and status != "completed":
        output = data.get("output")
        message = output if isinstance(output, str) and output.strip() else payload
        error(f"Codex hot update did not complete: {message}")

    exit_code = data.get("exit_code")
    if exit_code not in (None, 0):
        output = data.get("output")
        message = output if isinstance(output, str) and output.strip() else payload
        error(f"Codex hot update failed: {message}")


def _hot_update_codex_config(
    session: dict[str, object],
    *,
    model_name: Optional[str],
    model_api_key: Optional[str],
    model_provider: Optional[str],
    model_base_url: Optional[str],
    model_api_key_was_provided: bool,
    model_name_was_provided: bool,
    model_base_url_was_provided: bool,
) -> None:
    env = build_codex_hot_update_env(
        model_name=model_name,
        model_api_key=model_api_key,
        model_provider=model_provider,
        model_base_url=model_base_url,
        model_api_key_was_provided=model_api_key_was_provided,
        model_name_was_provided=model_name_was_provided,
        model_base_url_was_provided=model_base_url_was_provided,
    )
    body = {
        "timeout": CODEX_HOT_UPDATE_REQUEST_TIMEOUT,
        "hard_timeout": CODEX_HOT_UPDATE_REQUEST_HARD_TIMEOUT,
        "env": env,
        "command": build_codex_hot_update_command(),
    }

    try:
        response = requests.post(
            build_bash_exec_url(session.get("endpoint")),
            json=body,
            timeout=CODEX_HOT_UPDATE_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        error(str(exc))

    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int) and status_code >= 400:
        error(f"Codex hot update failed: {getattr(response, 'text', '')}")

    try:
        payload = response.json()
    except ValueError:
        error(f"Invalid Codex hot update response: {response.text}")

    _handle_hot_update_response(payload)


@contextmanager
def _raw_terminal_mode() -> Iterator[None]:
    if IS_WINDOWS or not sys.stdin.isatty():
        yield
        return

    try:
        import termios
        import tty
    except ImportError:  # pragma: no cover - POSIX-only modules are unavailable.
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


def _process_stdin_data(
    ws,
    stop_event: threading.Event,
    line_buffer: bytes,
    data: bytes,
) -> bytes:
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
        return b""

    normalized_data = data.replace(b"\r", b"\n")
    line_buffer += normalized_data
    has_newline = b"\n" in normalized_data
    line_parts = line_buffer.split(b"\n")
    complete_lines = line_parts[:-1]
    line_buffer = line_parts[-1]
    if has_newline and any(_is_local_exit_line(line) for line in complete_lines):
        stop_event.set()
        ws.close()
        return b""

    _send_json(
        ws,
        {
            "type": "input",
            "data": data.decode("utf-8", errors="ignore"),
        },
    )
    return line_buffer


def _stream_windows_stdin(ws, stop_event: threading.Event) -> None:
    try:
        import msvcrt
    except ImportError:
        error("Windows console input requires the msvcrt standard library module")

    line_buffer = b""
    while not stop_event.is_set():
        if not msvcrt.kbhit():
            stop_event.wait(0.1)
            continue

        char = msvcrt.getwch()
        data = _windows_console_char_to_bytes(char, msvcrt)
        if not data:
            continue
        line_buffer = _process_stdin_data(ws, stop_event, line_buffer, data)


def _windows_console_char_to_bytes(char: str, msvcrt) -> bytes:
    if char in ("\x00", "\xe0"):
        key = msvcrt.getwch()
        return {
            "H": b"\x1b[A",  # Up
            "P": b"\x1b[B",  # Down
            "K": b"\x1b[D",  # Left
            "M": b"\x1b[C",  # Right
            "G": b"\x1b[H",  # Home
            "O": b"\x1b[F",  # End
            "S": b"\x1b[3~",  # Delete
        }.get(key, b"")
    return char.encode("utf-8", errors="ignore")


def _stream_stdin(ws, stop_event: threading.Event) -> None:
    if IS_WINDOWS:
        _stream_windows_stdin(ws, stop_event)
        return

    fd = sys.stdin.fileno()
    line_buffer = b""
    while not stop_event.is_set():
        readable, _, _ = select.select([fd], [], [], 0.1)
        if not readable:
            continue

        data = os.read(fd, 4096)
        if not data:
            break

        line_buffer = _process_stdin_data(ws, stop_event, line_buffer, data)


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
            # Keepalive: without ping_interval/ping_timeout a silently dead
            # server leaves run_forever() blocked indefinitely with no way out
            # but Ctrl-C. Pings detect the dead peer and unblock the session.
            websocket_app.run_forever(
                ping_interval=ws_ping_interval(),
                ping_timeout=ws_ping_timeout(),
            )
    except KeyboardInterrupt:
        websocket_app.close()
    finally:
        stop_event.set()
        if sigwinch:
            signal.signal(sigwinch, previous_sigwinch)


def _collect_copy_specs(
    ctx: typer.Context,
    copy_sources: Optional[list[str]],
) -> list[tuple[Path, str]]:
    sources = list(copy_sources or [])
    destinations = list(ctx.args)
    if not sources:
        if destinations:
            error(f"Unexpected argument: {destinations[0]}")
        return []
    if len(sources) != len(destinations):
        error("--copy requires SOURCE and DESTINATION and may be repeated")

    result = []
    for source, destination in zip(sources, destinations):
        if source.startswith(SANDBOX_OPERAND_PREFIX):
            error("--copy only supports local-to-sandbox transfers")
        local_source = _validate_scp_local_source(Path(source))
        sandbox_destination = destination
        if not sandbox_destination.startswith(SANDBOX_OPERAND_PREFIX):
            sandbox_destination = f"{SANDBOX_OPERAND_PREFIX}{sandbox_destination}"
        result.append((local_source, _resolve_sandbox_operand(sandbox_destination)))
    return result


def _upload_copy_specs(
    session: dict[str, object],
    specs: list[tuple[Path, str]],
) -> None:
    for source, destination in specs:
        _upload_scp_source(
            session,
            source=source,
            destination=destination,
        )


def _resolve_exec_model_tool_id(
    *,
    session_id: Optional[str],
    tool_id: Optional[str],
    model_name: Optional[str],
) -> str | None:
    del session_id
    if not (model_name or "").strip():
        return None
    resolved_tool_id = (tool_id or "").strip()
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
    copy: Optional[list[str]] = typer.Option(
        None,
        "--copy",
        metavar="SOURCE DESTINATION",
        help=(
            "Copy a local file or directory into the sandbox before exec. "
            "May be repeated; sandbox: is optional for DESTINATION."
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
    try:
        config_defaults = configured_sandbox_config()
        session_id = config_default_if_unprovided(
            ctx, "session_id", "session-id", session_id, data=config_defaults
        )
        tool_id, tool_name = config_tool_identifier_defaults_if_unprovided(
            ctx, tool_id=tool_id, tool_name=tool_name, data=config_defaults
        )
        tool_type = config_default_if_unprovided(
            ctx,
            "tool_type",
            "tool-type",
            tool_type,
            data=config_defaults,
            transform=SandboxToolType,
        )
        git_config = config_default_if_unprovided(
            ctx, "git_config", "git-config", git_config, data=config_defaults
        )
        model_name = config_default_if_unprovided(
            ctx, "model_name", "model-name", model_name, data=config_defaults
        )
        model_api_key = config_default_if_unprovided(
            ctx,
            "model_api_key",
            "model-api-key",
            model_api_key,
            data=config_defaults,
        )
        model_provider = config_default_if_unprovided(
            ctx,
            "model_provider",
            "model-provider",
            model_provider,
            data=config_defaults,
        )
        model_base_url = config_default_if_unprovided(
            ctx,
            "model_base_url",
            "model-base-url",
            model_base_url,
            data=config_defaults,
        )
        if tool_name:
            tool_id = resolve_existing_sandbox_tool_id(
                tool_id=tool_id,
                tool_name=tool_name,
                tool_type=tool_type,
                client=AgentkitToolsClient(),
                env_var_name=SANDBOX_TOOL_ID_ENV,
            )
            tool_name = None
        exec_mode = _normalize_exec_mode(mode)
        copy_specs = _collect_copy_specs(ctx, copy)
        model_api_key_was_provided = param_was_provided(ctx, "model_api_key")
        model_name_was_provided = param_was_provided(ctx, "model_name")
        model_provider_was_provided = param_was_provided(ctx, "model_provider")
        model_base_url_was_provided = param_was_provided(ctx, "model_base_url")
        resolved_model_base_url = normalize_model_base_url(model_base_url)
        validate_model_provider_base_url(
            model_provider=model_provider,
            model_base_url=resolved_model_base_url,
            model_provider_was_provided=model_provider_was_provided,
            model_base_url_was_provided=model_base_url_was_provided,
        )
        resolved_model_provider = _resolve_exec_model_provider(
            session_id=session_id,
            tool_id=tool_id,
            tool_type=tool_type,
            model_name=model_name,
            model_provider=model_provider,
        )

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

        session, is_new_session = ensure_sandbox_session_with_status(
            session_id=session_id,
            tool_id=tool_id,
            tool_name=tool_name,
            tool_type=tool_type.value,
            envs=build_model_envs(
                model_name=model_name,
                model_api_key=model_api_key,
                model_provider=resolved_model_provider,
                model_base_url=resolved_model_base_url,
                model_provider_was_provided=model_provider_was_provided,
                model_base_url_was_provided=model_base_url_was_provided,
                include_codex_config=tool_type == SandboxToolType.CODE_ENV,
                disable_websearch_apikey=disable_websearch,
            ),
        )
        if (
            not is_new_session
            and tool_type == SandboxToolType.CODE_ENV
            and _codex_hot_update_requested(
                model_api_key_was_provided=model_api_key_was_provided,
                model_name_was_provided=model_name_was_provided,
                model_base_url_was_provided=model_base_url_was_provided,
            )
        ):
            _hot_update_codex_config(
                session,
                model_name=model_name,
                model_api_key=model_api_key,
                model_provider=resolved_model_provider,
                model_base_url=resolved_model_base_url,
                model_api_key_was_provided=model_api_key_was_provided,
                model_name_was_provided=model_name_was_provided,
                model_base_url_was_provided=model_base_url_was_provided,
            )
    except typer.Exit:
        raise
    except (SandboxConfigError, ValueError) as exc:
        error(str(exc))
    except Exception as exc:
        error(str(exc))

    session_id = session.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        error("Sandbox session missing session_id")

    try:
        _upload_copy_specs(session, copy_specs)
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
        tool_id = session.get("tool_id")
        if not isinstance(tool_id, str) or not tool_id.strip():
            error("Sandbox session missing tool_id")
        add_session_terminal_shell_id(tool_id.strip(), session_id, remote_shell_id)
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
            tool_id = session.get("tool_id")
            if not isinstance(tool_id, str) or not tool_id.strip():
                error("Sandbox session missing tool_id")
            remove_session_terminal_shell_id(
                tool_id.strip(),
                session_id,
                cleanup_shell_id,
            )

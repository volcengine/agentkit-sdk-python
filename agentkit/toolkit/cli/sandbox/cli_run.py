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

"""Run multiple sandbox exec sessions in a local terminal layout."""

from __future__ import annotations

from pathlib import Path
import json
import platform
import shutil
import shlex
import subprocess
import tempfile
from typing import Any
import uuid

import typer
import yaml

from agentkit.toolkit.cli.sandbox.sandbox_client import error

DEFAULT_RUN_CONFIG = "agentkit-sandbox-run.yaml"

_EXEC_CONFIG_KEYS = ("exec", "execs", "tabs", "commands")
_IGNORED_ENTRY_KEYS = {"name", "title"}
_ENTRY_CWD_KEYS = ("cwd", "workdir")
_RAW_ARG_KEYS = ("args", "argv")
_COPY_KEYS = ("copy", "copies")

_OPTION_FIELDS = {
    "session_id": "--session-id",
    "sid": "--session-id",
    "tool_id": "--tool-id",
    "tool_type": "--tool-type",
    "command": "--command",
    "mode": "--mode",
    "shell_id": "--shell-id",
    "git_config": "--git-config",
    "model_name": "--model-name",
    "model_api_key": "--model-api-key",
    "model_provider": "--model-provider",
    "model_base_url": "--model-base-url",
}


def _load_run_config(path: Path) -> Any:
    if not path.exists():
        error(f"Sandbox run config not found: {path}")
    if not path.is_file():
        error(f"Sandbox run config is not a file: {path}")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        error(f"Invalid sandbox run config YAML: {exc}")
    except OSError as exc:
        error(f"Cannot read sandbox run config {path}: {exc}")


def _extract_exec_entries(config: Any) -> list[dict[str, Any]]:
    if isinstance(config, list):
        raw_entries = config
    elif isinstance(config, dict):
        raw_entries = None
        for key in _EXEC_CONFIG_KEYS:
            value = config.get(key)
            if value is not None:
                raw_entries = value
                break
        if raw_entries is None:
            error(
                "Sandbox run config must contain one of: "
                f"{', '.join(_EXEC_CONFIG_KEYS)}"
            )
    else:
        error("Sandbox run config must be a YAML mapping or list")

    if not isinstance(raw_entries, list):
        error("Sandbox run exec entries must be a YAML list")
    if not raw_entries:
        error("Sandbox run config does not contain any exec entries")

    entries: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(raw_entries, start=1):
        if not isinstance(raw_entry, dict):
            error(f"Exec entry #{index} must be a YAML mapping")
        entries.append(raw_entry)
    return entries


def _string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, int, float)):
        return [str(value)]
    if isinstance(value, list):
        items: list[str] = []
        for index, item in enumerate(value, start=1):
            if not isinstance(item, (str, int, float)):
                error(f"{field_name}[{index}] must be a string")
            items.append(str(item))
        return items
    error(f"{field_name} must be a string or list")


def _append_option(args: list[str], option_name: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        error(f"{option_name} does not accept a boolean value")
    if isinstance(value, list):
        if len(value) != 1:
            error(f"{option_name} must be a single value")
        value = value[0]
    args.extend([option_name, str(value)])


def _entry_cwd(entry: dict[str, Any]) -> Path:
    for key in _ENTRY_CWD_KEYS:
        value = entry.get(key)
        if value is not None:
            return Path(str(value)).expanduser().resolve()
    return Path.cwd()


def _copy_pairs(value: Any, field_name: str) -> list[tuple[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        error(f"{field_name} must be a source/destination pair or list of pairs")
    if len(value) == 2 and all(isinstance(item, (str, int, float)) for item in value):
        value = [value]

    pairs = []
    for index, pair in enumerate(value, start=1):
        if not isinstance(pair, list) or len(pair) != 2:
            error(f"{field_name}[{index}] must contain SOURCE and DESTINATION")
        source, destination = pair
        if not isinstance(source, (str, int, float)) or not isinstance(
            destination, (str, int, float)
        ):
            error(f"{field_name}[{index}] values must be strings")
        pairs.append((str(source), str(destination)))
    return pairs


def _build_exec_args(entry: dict[str, Any], *, entry_index: int) -> list[str]:
    args = ["agentkit", "sandbox", "exec"]

    raw_args_value = None
    for key in _RAW_ARG_KEYS:
        if key in entry:
            raw_args_value = entry[key]
            break
    if raw_args_value is not None:
        args.extend(_string_list(raw_args_value, f"exec[{entry_index}].args"))
        return args

    consumed_keys = (
        set(_OPTION_FIELDS)
        | set(_COPY_KEYS)
        | set(_ENTRY_CWD_KEYS)
        | _IGNORED_ENTRY_KEYS
    )
    unknown_keys = sorted(key for key in entry if key not in consumed_keys)
    if unknown_keys:
        error(f"Unknown key(s) in exec entry #{entry_index}: {', '.join(unknown_keys)}")

    for field_name, option_name in _OPTION_FIELDS.items():
        if field_name == "command":
            continue
        _append_option(args, option_name, entry.get(field_name))

    for copy_key in _COPY_KEYS:
        if copy_key not in entry:
            continue
        for source, destination in _copy_pairs(
            entry[copy_key],
            f"exec[{entry_index}].{copy_key}",
        ):
            args.extend(["--copy", source, destination])
        break

    _append_option(args, "--command", entry.get("command"))

    return args


def _build_terminal_commands(entries: list[dict[str, Any]]) -> list[str]:
    commands = []
    for index, entry in enumerate(entries, start=1):
        argv = _build_exec_args(entry, entry_index=index)
        cwd = _entry_cwd(entry)
        commands.append(f"cd {shlex.quote(str(cwd))} && {shlex.join(argv)}")
    return commands


def _applescript_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _write_executable_script(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o700)


def _build_pane_script(command: str) -> str:
    return "\n".join(
        [
            "#!/bin/zsh",
            "set -o pipefail",
            command,
            "exit_status=$?",
            "echo",
            'echo "[agentkit sandbox run] pane exited with status ${exit_status}."',
            'echo "[agentkit sandbox run] Press Enter to close this pane."',
            "read -r _ </dev/tty || true",
            'exit "${exit_status}"',
            "",
        ]
    )


def _build_tmux_grid_script(
    commands: list[str],
    *,
    tmux_path: str = "tmux",
    session_name: str,
    scripts_dir: Path,
) -> str:
    pane_scripts = [
        scripts_dir / f"pane-{index}.zsh" for index in range(1, len(commands) + 1)
    ]
    for command, pane_script in zip(commands, pane_scripts):
        _write_executable_script(pane_script, _build_pane_script(command))

    quoted_tmux = shlex.quote(tmux_path)
    quoted_session = shlex.quote(session_name)
    first_pane = shlex.quote(shlex.join(["/bin/zsh", str(pane_scripts[0])]))
    lines = [
        "#!/bin/zsh",
        "set -e",
        "pause_on_error() {",
        "  exit_status=$?",
        '  if [ "${exit_status}" -ne 0 ]; then',
        "    echo",
        '    echo "[agentkit sandbox run] launcher failed with status ${exit_status}."',
        '    echo "[agentkit sandbox run] Press Enter to close this window."',
        "    read -r _ </dev/tty || true",
        "  fi",
        "}",
        "trap pause_on_error EXIT",
        f"TMUX_BIN={quoted_tmux}",
        f"SESSION_NAME={quoted_session}",
        f'"${{TMUX_BIN}}" new-session -d -s "${{SESSION_NAME}}" {first_pane}',
    ]
    for pane_script in pane_scripts[1:]:
        pane_command = shlex.quote(shlex.join(["/bin/zsh", str(pane_script)]))
        lines.append(
            f'"${{TMUX_BIN}}" split-window -t "${{SESSION_NAME}}" {pane_command}'
        )
    lines.extend(
        [
            '"${TMUX_BIN}" select-layout -t "${SESSION_NAME}" tiled',
            '"${TMUX_BIN}" attach-session -t "${SESSION_NAME}"',
            "",
        ]
    )
    return "\n".join(lines)


def _write_tmux_grid_launcher(
    commands: list[str],
    *,
    tmux_path: str = "tmux",
) -> Path:
    session_name = f"agentkit-sandbox-{uuid.uuid4().hex[:8]}"
    scripts_dir = Path(tempfile.mkdtemp(prefix="agentkit-sandbox-run-"))
    launcher = scripts_dir / "run.zsh"
    _write_executable_script(
        launcher,
        _build_tmux_grid_script(
            commands,
            tmux_path=tmux_path,
            session_name=session_name,
            scripts_dir=scripts_dir,
        ),
    )
    return launcher


def _build_macos_terminal_script(
    launcher: Path,
) -> str:
    launch_command = shlex.join(["/bin/zsh", str(launcher)])
    lines = [
        'tell application "Terminal"',
        "  activate",
        f"  do script {_applescript_string(launch_command)}",
        "end tell",
    ]
    return "\n".join(lines)


def _open_macos_terminal_tabs(commands: list[str]) -> None:
    tmux_path = shutil.which("tmux")
    if not tmux_path:
        error("tmux is required to arrange sandbox exec sessions in a 2x2 layout")
    launcher = _write_tmux_grid_launcher(commands, tmux_path=tmux_path)
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                _build_macos_terminal_script(launcher),
            ],
            check=True,
        )
    except FileNotFoundError:
        error("osascript is required to open terminal tabs on macOS")
    except subprocess.CalledProcessError as exc:
        error(f"Failed to open terminal tabs: {exc}")


def _open_terminal_tabs(commands: list[str]) -> None:
    if platform.system() != "Darwin":
        error("Opening terminal tabs is currently supported on macOS Terminal only")
    _open_macos_terminal_tabs(commands)


def _run_single_command_inline(command: str) -> None:
    try:
        subprocess.run(["/bin/sh", "-c", command], check=True)
    except FileNotFoundError:
        error("/bin/sh is required to run sandbox exec commands inline")
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(exc.returncode) from exc


def run_command(
    config: Path = typer.Option(
        DEFAULT_RUN_CONFIG,
        "--config",
        "-f",
        help="YAML file containing sandbox exec entries.",
    ),
    terminal: int = typer.Option(
        1,
        "--terminal",
        min=1,
        help="Number of sandbox exec panes to open.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the exec commands without opening terminal tabs.",
    ),
) -> None:
    """Open a local terminal layout and run sandbox exec commands from YAML."""
    entries = _extract_exec_entries(_load_run_config(config))[:terminal]
    if len(entries) < terminal:
        error(
            f"Sandbox run config contains {len(entries)} exec entries, "
            f"but --terminal requested {terminal}"
        )

    commands = _build_terminal_commands(entries)
    if dry_run:
        for command in commands:
            typer.echo(command)
        return

    if platform.system() != "Darwin" and len(commands) == 1:
        _run_single_command_inline(commands[0])
        return

    _open_terminal_tabs(commands)

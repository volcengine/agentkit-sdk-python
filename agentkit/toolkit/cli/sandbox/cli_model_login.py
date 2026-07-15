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

"""`agentkit sandbox codex-login`: inject a local model subscription into a sandbox.

Reads the OAuth login codex/claude wrote locally ($CODEX_HOME/auth.json,
~/.claude/.credentials.json) and writes the token to the same path in the sandbox session.
Only the OAuth token is injected; an API key in the same file is stripped. Codex sessions use
the codex_login provider, which authenticates from the injected OAuth token.
"""

from __future__ import annotations

import json
import re
from typing import Optional

import typer

from agentkit.toolkit.cli.sandbox.cli_file import _exec_shell_command
from agentkit.toolkit.cli.sandbox.model_config import (
    CODEX_LOGIN_MODEL_PROVIDER_ID,
    MODEL_API_KEY_ENV_KEYS,
)
from agentkit.toolkit.cli.sandbox.session_create import (
    SANDBOX_TOOL_ID_ENV,
    build_model_envs,
    ensure_sandbox_session,
)
from agentkit.toolkit.cli.sandbox.tool_resolve import SandboxToolType
from agentkit.toolkit.cli.sandbox.sandbox_client import error


def _shell_output(payload: dict) -> str:
    data = payload.get("data")
    if isinstance(data, dict):
        out = data.get("output")
        if isinstance(out, str):
            return out
    return ""


def _redact_inject(cmd: str) -> str:
    """Redact the base64 token blob in an injection command (for --dry-run display)."""
    return re.sub(
        r"printf %s '([A-Za-z0-9+/=]+)'",
        lambda m: f"printf %s '<base64 {len(m.group(1))} bytes - redacted>'",
        cmd,
    )


def _codex_login_session_envs(tool_type: SandboxToolType):
    envs = build_model_envs(
        model_provider=CODEX_LOGIN_MODEL_PROVIDER_ID,
        model_provider_was_provided=True,
        include_codex_config=tool_type == SandboxToolType.CODE_ENV,
    )
    if not envs:
        return envs
    return [
        env for env in envs if getattr(env, "key", None) not in MODEL_API_KEY_ENV_KEYS
    ]


def codex_login_command(
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        "--sid",
        "-s",
        help=(
            "Sandbox session to inject into. Defaults to a new session; reuse the printed id "
            "with `agentkit sandbox exec --sid <id>`."
        ),
    ),
    provider: str = typer.Option(
        "codex",
        "--provider",
        "-p",
        help="Subscription to bring in: codex (ChatGPT) or claude (Claude Code).",
    ),
    auth_file: Optional[str] = typer.Option(
        None,
        "--auth-file",
        help=(
            "Use a specific local credential file (codex auth.json / claude .credentials.json) "
            "instead of running the local SSO."
        ),
    ),
    codex_home: Optional[str] = typer.Option(
        None,
        "--codex-home",
        help="Local codex home (default $CODEX_HOME or ~/.codex).",
    ),
    login: bool = typer.Option(
        True,
        "--login/--no-login",
        help="If no local credential exists, trigger `codex login` (browser SSO) once.",
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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve the local credential and print what would be injected (token redacted); no session.",
    ),
) -> None:
    """Inject your ChatGPT/Codex or Claude Code subscription token into a sandbox session.

    Only the OAuth token is injected; an API key in the same file is not. Codex sessions use the
    codex_login provider, which authenticates from the injected OAuth token.
    """
    from agentkit.auth import model_login as ml

    provider = (provider or "codex").lower()
    if provider not in ml.PROVIDERS:
        error(f"unknown provider: {provider} (supported: {', '.join(ml.PROVIDERS)})")

    # 1) resolve the LOCAL native credential (runs the provider's local SSO if needed)
    try:
        if provider == "codex":
            src, data = ml.resolve_local_codex_auth(
                codex_home=codex_home, auth_file=auth_file, allow_login=login
            )
            summary = ml.codex_auth_summary(data)
            build_cmd = ml.build_codex_injection_command(
                auth_data=data
            )  # sanitizes: OAuth only
            marker = ml.CODEX_INJECT_MARKER
        else:  # claude
            data = ml.read_claude_creds(creds_file=auth_file)
            src = ml.claude_creds_path(auth_file)
            summary = ml.claude_creds_summary(data)
            build_cmd = ml.build_claude_injection_command(
                creds_data=data
            )  # sanitizes: OAuth only
            marker = ml.CLAUDE_INJECT_MARKER
    except ml.ModelLoginError as exc:
        error(str(exc))

    typer.secho(f"\nLocal credential: {src}", fg=typer.colors.CYAN, err=True)
    typer.echo(json.dumps(summary, indent=2, ensure_ascii=False))
    if summary.get("has_local_api_key"):
        typer.secho(
            "  note: a local API key was found and is not injected, only the OAuth login.",
            fg=typer.colors.YELLOW,
            err=True,
        )
    if summary.get("id_token_expired") and not summary.get("has_refresh_token"):
        typer.secho(
            "  warning: token expired and has no refresh_token; re-run `codex login` locally first.",
            fg=typer.colors.YELLOW,
            err=True,
        )

    if dry_run:
        typer.secho(
            "\n(dry-run) would inject (OAuth token only, redacted):",
            fg=typer.colors.CYAN,
            err=True,
        )
        typer.secho(_redact_inject(build_cmd), err=True)
        raise typer.Exit(0)

    # 2) ensure the sandbox session, then inject over its shell-exec endpoint
    try:
        session = ensure_sandbox_session(
            session_id=session_id,
            tool_id=tool_id,
            tool_name=tool_name,
            tool_type=tool_type.value,
            envs=(
                _codex_login_session_envs(tool_type) if provider == "codex" else None
            ),
        )
    except typer.Exit:
        raise
    except Exception as exc:  # noqa: BLE001
        error(str(exc))

    sid = session.get("session_id")
    if not isinstance(sid, str) or not sid:
        error("sandbox session missing session_id")

    out = _shell_output(_exec_shell_command(session, build_cmd))
    if marker not in out:
        error(
            f"injection did not confirm (marker missing). sandbox output: {out[:200]}"
        )
    where = out.split(marker, 1)[1].strip() or "<sandbox>"

    typer.secho(
        f"\ninjected your {summary.get('provider', provider)} subscription into {where}",
        fg=typer.colors.GREEN,
        bold=True,
        err=True,
    )
    typer.secho(f"  session: {sid}", fg=typer.colors.CYAN, err=True)
    if provider == "codex":
        typer.secho(
            f'  run: agentkit sandbox exec --sid {sid} --command "codex"',
            fg=typer.colors.CYAN,
            err=True,
        )
        typer.secho(
            "  (session uses model_provider=codex_login with OAuth auth)",
            fg=typer.colors.BRIGHT_BLACK,
            err=True,
        )
    typer.secho(
        "  note: the token is refreshed by codex/claude in the sandbox; re-inject if the session is recreated.",
        fg=typer.colors.BRIGHT_BLACK,
        err=True,
    )
    typer.echo(
        json.dumps(
            {"injected": True, "provider": provider, "session_id": sid, "path": where},
            ensure_ascii=False,
        )
    )

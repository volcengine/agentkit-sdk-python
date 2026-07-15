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

"""Sandbox command group for AgentKit CLI."""

from __future__ import annotations

import typer

from agentkit.toolkit.cli.sandbox.cli_build import build_command
from agentkit.toolkit.cli.sandbox.cli_create import create_command
from agentkit.toolkit.cli.sandbox.cli_delete import delete_command
from agentkit.toolkit.cli.sandbox.cli_exec import exec_command
from agentkit.toolkit.cli.sandbox.cli_file import file_command
from agentkit.toolkit.cli.sandbox.cli_get import get_command
from agentkit.toolkit.cli.sandbox.cli_invoke import invoke_command
from agentkit.toolkit.cli.sandbox.cli_init_dockerfile import init_dockerfile_command
from agentkit.toolkit.cli.sandbox.cli_model_login import codex_login_command
from agentkit.toolkit.cli.sandbox.cli_mount import mount_command
from agentkit.toolkit.cli.sandbox.cli_run import run_command
from agentkit.toolkit.cli.sandbox.cli_shell import shell_command
from agentkit.toolkit.cli.sandbox.cli_web import web_command

sandbox_app = typer.Typer(
    name="sandbox",
    help="Manage AgentKit sandbox tools and sessions.",
    no_args_is_help=True,
)

sandbox_app.command(name="build")(build_command)
sandbox_app.command(name="init-dockerfile")(init_dockerfile_command)
sandbox_app.command(
    name="create",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)(create_command)
sandbox_app.command(name="delete")(delete_command)
sandbox_app.command(name="get")(get_command)
sandbox_app.command(name="mount")(mount_command)
sandbox_app.command(
    name="exec",
    context_settings={"allow_extra_args": True},
)(exec_command)
sandbox_app.command(
    name="invoke",
    context_settings={"allow_extra_args": True},
)(invoke_command)
sandbox_app.command(name="run")(run_command)
sandbox_app.command(
    name="shell",
    context_settings={"allow_extra_args": True},
)(shell_command)
sandbox_app.command(name="web")(web_command)
sandbox_app.command(name="codex-login")(codex_login_command)
sandbox_app.command(name="model-login")(codex_login_command)  # provider-agnostic alias
sandbox_app.add_typer(file_command, name="file")

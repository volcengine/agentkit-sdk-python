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

"""Build custom sandbox images."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()
DEFAULT_SANDBOX_REPO_NAME = "agentkit-custom-sandbox-image"


def build_command(
    dockerfile: str = typer.Option(
        "Dockerfile",
        "--dockerfile",
        help="Dockerfile path relative to the project directory",
    ),
    repo: str = typer.Option(
        DEFAULT_SANDBOX_REPO_NAME,
        "--image-name",
        "--repo",
        help="Container Registry image name, mapped to CR repository name",
    ),
    tag: str = typer.Option(
        "{{timestamp}}",
        "--tag",
        help="Container image tag",
    ),
    namespace: str = typer.Option(
        "agentkit",
        "--namespace",
        help="Container Registry namespace",
    ),
    project_dir: Optional[Path] = typer.Option(
        None,
        "--project-dir",
        help="Project directory to package as Docker build context",
    ),
):
    """Build a custom sandbox image in cloud Code Pipeline."""
    from agentkit.toolkit.builders.ve_sandbox_pipeline import (
        VeSandboxCPCRBuilder,
        VeSandboxCPCRBuilderConfig,
    )
    from agentkit.toolkit.cli.console_reporter import ConsoleReporter

    build_dir = project_dir or Path.cwd()
    console.print(f"[cyan]Building sandbox image from {build_dir}[/cyan]")

    reporter = ConsoleReporter()
    builder = VeSandboxCPCRBuilder(project_dir=build_dir, reporter=reporter)
    config = VeSandboxCPCRBuilderConfig(
        dockerfile=dockerfile,
        cr_repo_name=repo,
        cr_namespace_name=namespace,
        image_tag=tag,
    )

    result = builder.build(config)
    if result.success:
        image_name = result.image.full_name if result.image else config.image_url
        console.print("[green]✅ Sandbox image build completed successfully![/green]")
        if image_name:
            console.print(f"[green]📦 Image: {image_name}[/green]")
    else:
        console.print(f"[red]❌ Sandbox image build failed: {result.error}[/red]")
        raise typer.Exit(1)

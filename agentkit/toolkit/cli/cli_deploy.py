# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

"""AgentKit CLI - Deploy command implementation."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

# Note: Avoid importing heavy packages at the top to keep CLI startup fast

console = Console()


def deploy_command(
    config_file: Path = typer.Option("agentkit.yaml", help="Configuration file"),
    harness: Optional[str] = typer.Option(
        None,
        "--harness",
        help="Deploy a harness spec <name>.harness.json (cloud build+deploy) "
        "from the current directory instead of agentkit.yaml.",
    ),
    region: Optional[str] = typer.Option(
        None, "--region", help="AgentKit region (harness deploy)."
    ),
    volcengine_access_key: Optional[str] = typer.Option(
        None, "--volcengine-access-key", help="Volcengine access key (harness deploy)."
    ),
    volcengine_secret_key: Optional[str] = typer.Option(
        None, "--volcengine-secret-key", help="Volcengine secret key (harness deploy)."
    ),
    discovery_url: Optional[str] = typer.Option(
        None,
        "--discovery-url",
        help="OIDC discovery URL; enables OAuth2/JWT auth (harness deploy).",
    ),
    allowed_id: Optional[str] = typer.Option(
        None,
        "--allowed-id",
        help="Comma-separated allowed client IDs for OAuth2/JWT auth (harness deploy).",
    ),
):
    """Deploy the Agent to target environment."""
    from agentkit.toolkit.executors import DeployExecutor
    from agentkit.toolkit.cli.console_reporter import ConsoleReporter
    from agentkit.toolkit.context import ExecutionContext

    if harness is not None:
        _deploy_harness(
            name=harness,
            region=region,
            access_key=volcengine_access_key,
            secret_key=volcengine_secret_key,
            discovery_url=discovery_url,
            allowed_id=allowed_id,
        )
        return

    console.print(f"[green]Deploying with {config_file}[/green]")

    # Set execution context - CLI uses ConsoleReporter (with colored output and progress)
    reporter = ConsoleReporter()
    ExecutionContext.set_reporter(reporter)

    executor = DeployExecutor(reporter=reporter)
    result = executor.execute(config_file=str(config_file))

    # Format output
    if result.success:
        console.print("[green]✅ Deployment successful[/green]")
        if result.endpoint_url:
            console.print(f"[green]Endpoint: {result.endpoint_url}[/green]")
        if result.container_id:
            console.print(f"[green]Container ID: {result.container_id}[/green]")
        if result.service_id:
            console.print(f"[green]Service ID: {result.service_id}[/green]")
    else:
        console.print(f"[red]❌ Deployment failed: {result.error}[/red]")
        # deploy_logs may not exist, use getattr for safe access
        deploy_logs = getattr(result, "deploy_logs", None) or result.metadata.get(
            "deploy_logs", []
        )
        if deploy_logs:
            for log in deploy_logs:
                if log.strip():
                    console.print(f"[red]{log}[/red]")
        raise typer.Exit(1)


def _deploy_harness(
    name: str,
    region,
    access_key,
    secret_key,
    discovery_url,
    allowed_id,
):
    """Deploy a harness spec <name>.harness.json from the current directory."""
    from agentkit.toolkit.sdk import deploy_harness
    from agentkit.toolkit.cli.console_reporter import ConsoleReporter
    from agentkit.toolkit.context import ExecutionContext

    console.print(f"[green]Deploying harness '{name}' from current directory[/green]")

    reporter = ConsoleReporter()
    ExecutionContext.set_reporter(reporter)

    # Surface fast-fail input/validation errors (missing spec, missing creds,
    # name collision) as a clean CLI error + exit code, not a raw traceback.
    try:
        result = deploy_harness(
            name=name,
            region=region,
            access_key=access_key,
            secret_key=secret_key,
            discovery_url=discovery_url,
            allowed_id=allowed_id,
            reporter=reporter,
        )
    except (ValueError, FileNotFoundError, NotADirectoryError) as exc:
        console.print(f"[red]❌ Harness deploy failed: {exc}[/red]")
        raise typer.Exit(1)

    if not result.success:
        console.print(f"[red]❌ Harness deploy failed: {result.error}[/red]")
        raise typer.Exit(1)

    deploy_result = result.deploy_result
    meta = deploy_result.metadata if (deploy_result and deploy_result.metadata) else {}
    endpoint = deploy_result.endpoint_url if deploy_result else None

    console.print("[green]✅ Harness runtime deployed[/green]")
    console.print(f"[green]Name: {name}[/green]")
    if meta.get("runtime_id"):
        console.print(f"[green]Runtime id: {meta['runtime_id']}[/green]")
    console.print(f"[green]Endpoint: {endpoint or '(see AgentKit console)'}[/green]")
    if meta.get("runtime_apikey"):
        console.print(f"[green]API key: {meta['runtime_apikey']}[/green]")
    if endpoint:
        console.print(
            f"[green]Recorded in {(Path.cwd() / 'harness.json')}[/green]"
        )

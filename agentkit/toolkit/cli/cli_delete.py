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

"""AgentKit CLI - ``delete`` commands.

``agentkit delete credential <name>`` removes an inbound auth config. The
config is addressed by ``InboundAuthConfigId``, so the name is first resolved
to its id via ``ListInboundAuthConfigs``.
"""

from typing import Optional

import typer
from rich.console import Console

console = Console()

delete_app = typer.Typer(
    name="delete",
    help="Delete AgentKit resources.",
    add_completion=False,
)


@delete_app.command("credential")
def delete_credential_command(
    name: str = typer.Argument(..., help="Credential name to delete."),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
):
    """Delete a credential (inbound auth config) by name."""
    from agentkit.toolkit.cli.utils import PaginationHelper
    from agentkit.sdk.identity.client import AgentkitIdentityClient
    from agentkit.sdk.identity import types as it

    client = AgentkitIdentityClient(region=(region or "").strip())

    def build_request(next_token_val):
        return it.ListInboundAuthConfigsRequest(
            max_results=50,
            next_token=next_token_val,
        )

    configs, _, _ = PaginationHelper.fetch_all_pages(
        request_func=client.list_inbound_auth_configs,
        request_builder=build_request,
        max_results=50,
        next_token=None,
        fetch_all=True,
        max_batches=None,
        sleep_ms=0,
    )

    matches = [c for c in configs if c.config_name == name]
    if not matches:
        console.print(f"[red]Error: credential '{name}' not found.[/red]")
        raise typer.Exit(1)

    for config in matches:
        config_id = config.inbound_auth_config_id
        if not config_id:
            continue
        client.delete_inbound_auth_config(
            it.DeleteInboundAuthConfigRequest(inbound_auth_config_id=config_id)
        )

    console.print(f"[green]✓ Deleted credential '{name}'[/green]")


@delete_app.command("harness")
def delete_harness_command(
    name: str = typer.Option(..., "--name", help="Harness runtime name to delete."),
    region: Optional[str] = typer.Option(
        None,
        "--region",
        help=(
            "Region override for this command (e.g. cn-beijing, cn-shanghai). "
            "Defaults to VOLCENGINE_AGENTKIT_REGION/VOLCENGINE_REGION/global config."
        ),
    ),
    timeout: int = typer.Option(
        300, "--timeout", help="Max seconds to wait for the async deletion to finish."
    ),
):
    """Delete a harness runtime by name.

    Resolves ``--name`` to a runtime and only deletes it when it carries the
    deploy-time harness tag (``agentkit:agenttype=harness``):

    * not found            -> reports it and exits non-zero;
    * exists, not a harness -> warns and refuses to delete (exits non-zero);
    * exists and a harness  -> deletes it, then polls until the deletion (which
      is asynchronous) actually completes.
    """
    import time

    from agentkit.toolkit.cli.utils import PaginationHelper
    from agentkit.sdk.runtime.client import AgentkitRuntimeClient
    from agentkit.sdk.runtime import types as rt
    from agentkit.toolkit.harness.deploy import HARNESS_TAG_KEY, HARNESS_TAG_VALUE

    client = AgentkitRuntimeClient(region=(region or "").strip())

    def build_request(next_token_val):
        return rt.ListRuntimesRequest(max_results=50, next_token=next_token_val)

    runtimes, _, _ = PaginationHelper.fetch_all_pages(
        request_func=client.list_runtimes,
        request_builder=build_request,
        max_results=50,
        next_token=None,
        fetch_all=True,
        max_batches=None,
        sleep_ms=0,
    )

    matches = [r for r in runtimes if r.name == name]
    if not matches:
        console.print(f"[yellow]Harness '{name}' not found.[/yellow]")
        raise typer.Exit(1)

    def _is_harness(runtime) -> bool:
        return any(
            tag.key == HARNESS_TAG_KEY and tag.value == HARNESS_TAG_VALUE
            for tag in (runtime.tags or [])
        )

    harness_matches = [r for r in matches if _is_harness(r)]
    if not harness_matches:
        console.print(
            f"[red]✗ '{name}' exists but is not a harness runtime "
            f"(missing {HARNESS_TAG_KEY}={HARNESS_TAG_VALUE} tag). "
            "Refusing to delete.[/red]"
        )
        raise typer.Exit(1)

    for runtime in harness_matches:
        runtime_id = runtime.runtime_id
        console.print(
            f"[cyan]Deleting harness '{name}' (runtime_id: {runtime_id})...[/cyan]"
        )
        client.delete_runtime(rt.DeleteRuntimeRequest(runtime_id=runtime_id))

        # Deletion is asynchronous: poll get_runtime until it reports the runtime
        # is gone (the API raises InvalidAgentKitRuntime.NotFound once removed).
        deadline = time.monotonic() + timeout
        with console.status(
            f"[cyan]Waiting for '{name}' deletion...[/cyan]", spinner="dots"
        ):
            while True:
                try:
                    current = client.get_runtime(
                        rt.GetRuntimeRequest(runtime_id=runtime_id)
                    )
                except Exception as exc:
                    if "InvalidAgentKitRuntime.NotFound" in str(exc):
                        break
                    raise
                if time.monotonic() > deadline:
                    console.print(
                        f"[red]✗ Timed out after {timeout}s waiting for '{name}' "
                        f"deletion (last status: {current.status}).[/red]"
                    )
                    raise typer.Exit(1)
                time.sleep(3)

        console.print(
            f"[green]✓ Deleted harness '{name}' (runtime_id: {runtime_id})[/green]"
        )

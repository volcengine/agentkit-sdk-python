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

"""AgentKit CLI - ``logs`` command.

Query a deployed harness runtime's logs from APMPlus / TLS. The ``--harness``
value names a runtime; it must carry the harness tag stamped at deploy time
(``agentkit:agenttype=harness``) — otherwise it is a regular agent app whose logs
this command cannot query.
"""

import datetime
import re
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()

_DURATION_UNITS_MS = {"s": 1000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}
_DURATION_RE = re.compile(r"(\d+)([smhd])")


def _parse_since(since: str) -> int:
    """Parse a relative duration like ``1h`` / ``30m`` / ``1h30m`` / ``2d`` to ms.

    Raises:
        ValueError: when the string has no recognizable ``<number><unit>`` token.
    """
    matches = _DURATION_RE.findall(since.strip().lower())
    if not matches or "".join(n + u for n, u in matches) != since.strip().lower():
        raise ValueError(
            f"无法解析 --since '{since}'，请使用形如 1h / 30m / 2d / 1h30m 的格式。"
        )
    return sum(int(n) * _DURATION_UNITS_MS[u] for n, u in matches)


def _format_timestamp(ts) -> str:
    """Format a millisecond epoch timestamp to local time; pass through on failure."""
    try:
        return datetime.datetime.fromtimestamp(int(ts) / 1000).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (ValueError, TypeError, OSError):
        return str(ts)


def _render_line(entry: dict) -> str:
    """Render one log entry as a plain ``<time> [level] <message>`` line."""
    ts = _format_timestamp(entry.get("__time__", ""))
    # AgentKit runtime logs carry the line in `message`; fall back to the generic
    # TLS `__content__` field for other topics.
    content = entry.get("message") or entry.get("__content__") or ""
    level = entry.get("log_level")
    return f"{ts} {level} {content}" if level else f"{ts} {content}"


def _find_runtime(client, target: str):
    """Return the runtime whose name (or RuntimeId) equals ``target``, or None."""
    from agentkit.sdk.runtime import types as rt

    next_token = None
    while True:
        resp = client.list_runtimes(
            rt.ListRuntimesRequest(max_results=50, next_token=next_token)
        )
        for runtime in resp.agent_kit_runtimes or []:
            if runtime.name == target or runtime.runtime_id == target:
                return runtime
        next_token = resp.next_token
        if not next_token:
            return None


def logs_command(
    harness: str = typer.Option(
        ...,
        "--harness",
        help="Harness runtime name (or RuntimeId) to query logs for.",
    ),
    region: Optional[str] = typer.Option(
        None, "--region", help="Region override (default: cn-beijing / global config)."
    ),
    query: Optional[str] = typer.Option(
        None,
        "--query",
        help="Override the TLS query. Default: service:<runtime_id>.<name>.",
    ),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Relative window from now, e.g. 1h / 30m / 2d / 1h30m. Conflicts with --start.",
    ),
    start_time: Optional[int] = typer.Option(
        None, "--start", help="Query start time (epoch ms). Default: 15 minutes ago."
    ),
    end_time: Optional[int] = typer.Option(
        None, "--end", help="Query end time (epoch ms). Default: now."
    ),
    limit: int = typer.Option(
        200, "--limit", help="Max log entries to return (default: 200)."
    ),
    sort: str = typer.Option(
        "desc", "--sort", help="Order by time: desc (newest first) or asc."
    ),
    tls_endpoint: Optional[str] = typer.Option(
        None, "--tls-endpoint", help="TLS host override (default: tls-<region>.volces.com)."
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write logs to this file (parent dirs created) instead of stdout.",
    ),
    raw: bool = typer.Option(False, "--raw", help="Print the raw SearchLogs JSON."),
) -> None:
    """Query a deployed harness runtime's logs (APMPlus / TLS).

    Examples:
        agentkit logs --harness research-agent
        agentkit logs --harness my-harness --limit 50 --sort asc
        agentkit logs --harness research-agent --since 1h --output ./logs/research-agent.log
    """
    import json as _json

    if since is not None and start_time is not None:
        console.print("[red]❌ --since 与 --start 不能同时使用。[/red]")
        raise typer.Exit(1)

    from agentkit.platform import VolcConfiguration, resolve_credentials
    from agentkit.sdk.runtime.client import AgentkitRuntimeClient
    from agentkit.toolkit.harness.deploy import HARNESS_TAG_KEY, HARNESS_TAG_VALUE
    from agentkit.toolkit.volcengine import apmplus_logs

    cfg = VolcConfiguration(region=region or None)
    resolved_region = cfg.region
    try:
        creds = resolve_credentials("agentkit", platform_config=cfg)
    except ValueError as exc:
        console.print(f"[red]❌ {exc}[/red]")
        raise typer.Exit(1)

    # Resolve the runtime and confirm it is a harness before doing anything else.
    client = AgentkitRuntimeClient(region=resolved_region)
    with console.status("[cyan]Resolving runtime...[/cyan]", spinner="dots"):
        runtime = _find_runtime(client, harness)

    if runtime is None:
        console.print(
            f"[red]❌ 未找到名为 '{harness}' 的运行时（region: {resolved_region}）。[/red]"
        )
        raise typer.Exit(1)

    is_harness = any(
        tag.key == HARNESS_TAG_KEY and tag.value == HARNESS_TAG_VALUE
        for tag in (runtime.tags or [])
    )
    if not is_harness:
        console.print("[red]❌ 非 Harness 应用，无法查询日志[/red]")
        raise typer.Exit(1)

    runtime_id = runtime.runtime_id or ""
    runtime_name = runtime.name or harness
    final_query = query or f"service:{runtime_id}.{runtime_name}"

    now_ms = int(time.time() * 1000)
    end_ms = end_time if end_time is not None else now_ms
    if since is not None:
        try:
            start_ms = end_ms - _parse_since(since)
        except ValueError as exc:
            console.print(f"[red]❌ {exc}[/red]")
            raise typer.Exit(1)
    elif start_time is not None:
        start_ms = start_time
    else:
        start_ms = end_ms - 15 * 60 * 1000

    try:
        with console.status("[cyan]Fetching log topic...[/cyan]", spinner="dots"):
            topic_id = apmplus_logs.get_log_topic_id(
                access_key=creds.access_key,
                secret_key=creds.secret_key,
                region=resolved_region,
                session_token=creds.session_token,
            )
        with console.status("[cyan]Searching logs...[/cyan]", spinner="dots"):
            response = apmplus_logs.search_logs(
                access_key=creds.access_key,
                secret_key=creds.secret_key,
                region=resolved_region,
                topic_id=topic_id,
                query=final_query,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
                limit=limit,
                sort=sort,
                session_token=creds.session_token,
                tls_host=tls_endpoint,
            )
    except ValueError as exc:
        console.print(f"[red]❌ 查询日志失败: {exc}[/red]")
        raise typer.Exit(1)

    entries = apmplus_logs.flatten_logs(response)

    # Build the text payload once (raw JSON or rendered lines), then either write
    # it to --output or print it to the console.
    if raw:
        payload = _json.dumps(response, ensure_ascii=False, indent=2)
    else:
        payload = "\n".join(_render_line(entry) for entry in entries)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + ("\n" if payload else ""), encoding="utf-8")
        console.print(
            f"[green]✅ 命中 {len(entries)} 条日志，已写入 {output}[/green]"
        )
        return

    if raw:
        console.print(payload)
        return

    console.print(f"[blue]Query: {final_query}[/blue]")
    if not entries:
        console.print("[yellow]未查询到日志。[/yellow]")
        return

    console.print(f"[green]✅ 命中 {len(entries)} 条日志[/green]")
    for entry in entries:
        ts = _format_timestamp(entry.get("__time__", ""))
        content = entry.get("message") or entry.get("__content__") or ""
        level = entry.get("log_level")
        prefix = f"[magenta]{ts}[/magenta]"
        if level:
            prefix += f" [yellow]{level}[/yellow]"
        console.print(f"{prefix} {content}")

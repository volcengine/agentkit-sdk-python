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

"""AgentKit CLI - Invoke command implementation."""

from pathlib import Path
from typing import Optional, Any
import json
import typer
from rich.console import Console
import random
import uuid
from agentkit.toolkit.config import get_config
import logging

# Note: Avoid importing heavy packages at the top to keep CLI startup fast
logger = logging.getLogger(__name__)
console = Console()


def build_standard_payload(message: Optional[str], payload: Optional[str]) -> dict:
    if message:
        return {"prompt": message}
    else:
        try:
            parsed = json.loads(payload) if isinstance(payload, str) else payload
            console.print(f"[blue]Using custom payload: {parsed}[/blue]")
            return parsed
        except json.JSONDecodeError as e:
            console.print(f"[red]Error: Invalid JSON payload: {e}[/red]")
            raise typer.Exit(1)


def build_a2a_payload(
    message: Optional[str], payload: Optional[str], headers: dict
) -> dict:
    parsed = None
    if payload:
        try:
            parsed = json.loads(payload) if isinstance(payload, str) else payload
        except json.JSONDecodeError:
            parsed = None

    if isinstance(parsed, dict) and parsed.get("jsonrpc"):
        console.print("[blue]Using provided JSON-RPC payload for A2A[/blue]")
        return parsed

    if message:
        text = message
    elif parsed is not None:
        text = json.dumps(parsed, ensure_ascii=False)
    else:
        text = payload if payload else ""

    a2a = {
        "jsonrpc": "2.0",
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "parts": [{"kind": "text", "text": text}],
            },
            "metadata": headers,
        },
        "id": random.randint(1, 999999),
    }
    return a2a


def invoke_command(
    config_file: Path = typer.Option("agentkit.yaml", help="Configuration file"),
    message: str = typer.Argument(None, help="Simple message to send to agent"),
    payload: str = typer.Option(
        None, "--payload", "-p", help="JSON payload to send (advanced option)"
    ),
    headers: str = typer.Option(
        None, "--headers", "-h", help="JSON headers for request (advanced option)"
    ),
    apikey: str = typer.Option(
        None, "--apikey", "-ak", help="API key for authentication"
    ),
) -> Any:
    """Send a test request to deployed Agent.

    Examples:
        # Simple message
        agentkit invoke "What is the weather today?"

        # Custom payload
        agentkit invoke --payload '{"prompt": "What is the weather in Hangzhou?"}'

        # With custom headers
        agentkit invoke --payload '{"prompt": "What is the weather in Hangzhou?"}' --headers '{"user_id": "test123"}'
    """
    from agentkit.toolkit.executors import InvokeExecutor
    from agentkit.toolkit.cli.console_reporter import ConsoleReporter

    console.print("[cyan]Invoking agent...[/cyan]")

    # Validate parameters: message and payload cannot be provided simultaneously
    if message and payload:
        console.print(
            "[red]Error: Cannot specify both message and payload. Use either message or --payload.[/red]"
        )
        raise typer.Exit(1)

    # Validate parameters: must provide either message or payload
    if not message and not payload:
        console.print(
            "[red]Error: Must provide either a message or --payload option.[/red]"
        )
        raise typer.Exit(1)

    config = get_config(config_path=config_file)
    common_config = config.get_common_config()

    # Process headers
    final_headers = {
        "user_id": "agentkit_user",
        "session_id": "agentkit_sample_session",
    }
    if headers:
        try:
            final_headers = json.loads(headers) if isinstance(headers, str) else headers
            console.print(f"[blue]Using custom headers: {final_headers}[/blue]")
        except json.JSONDecodeError as e:
            console.print(f"[red]Error: Invalid JSON headers: {e}[/red]")
            raise typer.Exit(1)
    else:
        console.print(f"[blue]Using default headers: {final_headers}[/blue]")

    final_payload = build_standard_payload(message, payload)
    agent_type = getattr(common_config, "agent_type", "") or getattr(
        common_config, "template_type", ""
    )
    is_a2a = isinstance(agent_type, str) and "a2a" in agent_type.lower()

    # If it's an A2A Agent, reconstruct payload using A2A constructor
    if is_a2a:
        console.print(
            "[cyan]Detected A2A agent type - constructing A2A JSON-RPC envelope[/cyan]"
        )
        final_payload = build_a2a_payload(message, payload, final_headers)

    # Set execution context - CLI uses ConsoleReporter (with colored output and progress)
    from agentkit.toolkit.context import ExecutionContext

    reporter = ConsoleReporter()
    ExecutionContext.set_reporter(reporter)

    executor = InvokeExecutor(reporter=reporter)
    result = executor.execute(
        payload=final_payload,
        config_file=str(config_file),
        headers=final_headers,
        stream=None,  # Automatically determined by Runner
    )

    if not result.success:
        console.print(f"[red]❌ Invocation failed: {result.error}[/red]")
        raise typer.Exit(1)

    console.print("[green]✅ Invocation successful[/green]")

    # Get response
    response = result.response

    # Handle streaming response (generator)
    if result.is_streaming:
        console.print("[cyan]📡 Streaming response detected...[/cyan]\n")
        result_list = []
        complete_text = []

        for event in result.stream():
            result_list.append(event)

            # If it's a string starting with "data: ", try to parse (fallback handling)
            if isinstance(event, str):
                if event.strip().startswith("data: "):
                    try:
                        json_str = event.strip()[6:].strip()  # Remove "data: " prefix
                        event = json.loads(json_str)
                    except json.JSONDecodeError:
                        # Parsing failed, skip this event
                        continue
                else:
                    # Not SSE format string, skip
                    continue

            # Handle A2A JSON-RPC
            if isinstance(event, dict) and event.get("jsonrpc") and "result" in event:
                event = event["result"]

            if isinstance(event, dict):
                parts = []
                if isinstance(event.get("parts"), list):
                    parts = event.get("parts", [])
                elif isinstance(event.get("message"), dict):
                    parts = event["message"].get("parts", [])
                elif isinstance(event.get("content"), dict):
                    parts = event["content"].get("parts", [])
                elif isinstance(event.get("status"), dict):
                    role = event["status"].get("message", {}).get("role")
                    if role == "agent":
                        parts = event["status"].get("message", {}).get("parts", [])
                if not event.get("partial", True):
                    logger.info("Partial event: %s", event)  # Log partial events
                    continue

                if parts:
                    for p in parts:
                        text = None
                        if isinstance(p, dict) and "text" in p:
                            text = p["text"]
                        elif isinstance(p, str):
                            text = p
                        if text:
                            complete_text.append(text)
                            # Incremental print (keep no newline)
                            console.print(text, end="", style="green")

                # Display error information in event (if any)
                if "error" in event:
                    console.print(f"\n[red]Error: {event['error']}[/red]")

                # Handle status updates (e.g., final flag or completed status)
                if event.get("final") is True:
                    break

                status = event.get("status")
                if isinstance(status, dict) and status.get("state") == "completed":
                    console.print("\n[cyan]Status indicates completed[/cyan]")
                    break

        # Display complete response (commented out for now)
        # if complete_text:
        #     console.print("\n\n[cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/cyan]")
        #     console.print(f"[cyan]📝 Complete response:[/cyan] {''.join(complete_text)}")
        console.print("")  # Line break

        return str(result_list)

    # Handle non-streaming response
    console.print("[cyan]📝 Response:[/cyan]")
    if isinstance(response, dict):
        console.print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        console.print(response)

    return str(response)

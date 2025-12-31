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
import time
import random
import uuid
from agentkit.toolkit.config import get_config
import logging

# Note: Avoid importing heavy packages at the top to keep CLI startup fast
logger = logging.getLogger(__name__)
console = Console()


def _extract_text_chunks_from_langchain_event(event: dict) -> list[str]:
    """Extract incremental text chunks from LangChain message_to_dict-style events.

    Expected shape (example):
        {"type": "AIMessageChunk", "data": {"content": "今天", ...}}
    """
    if not isinstance(event, dict):
        return []

    event_type = event.get("type")
    data = event.get("data")
    if not isinstance(event_type, str) or not isinstance(data, dict):
        return []

    # Most common streaming types: AIMessageChunk / HumanMessageChunk / ToolMessageChunk
    if not (
        event_type.endswith("MessageChunk")
        or event_type in {"AIMessage", "HumanMessage", "ToolMessage"}
    ):
        return []

    content = data.get("content")
    if content is None:
        return []

    # content can be a string, or a multimodal list like:
    #   [{"type":"text","text":"..."}, ...]
    if isinstance(content, str):
        return [content] if content else []
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str) and item:
                chunks.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text:
                    chunks.append(text)
        return chunks

    return []


def _extract_reasoning_chunks_from_langchain_event(event: dict) -> list[str]:
    """Extract incremental reasoning chunks from LangChain events.

    LangChain emit reasoning in:
        event['data']['additional_kwargs']['reasoning_content']
    while leaving event['data']['content'] empty.
    """
    if not isinstance(event, dict):
        return []

    event_type = event.get("type")
    data = event.get("data")
    if not isinstance(event_type, str) or not isinstance(data, dict):
        return []

    if not (
        event_type.endswith("MessageChunk")
        or event_type in {"AIMessage", "HumanMessage", "ToolMessage"}
    ):
        return []

    additional_kwargs = data.get("additional_kwargs")
    if not isinstance(additional_kwargs, dict):
        return []

    reasoning = additional_kwargs.get("reasoning_content")
    if isinstance(reasoning, str):
        return [reasoning] if reasoning else []
    return []


def _extract_text_chunks_from_adk_event(event: dict) -> list[str]:
    """Extract incremental text chunks from Google ADK/AgentKit streaming events."""
    if not isinstance(event, dict):
        return []

    parts: list[Any] = []
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

    if not isinstance(parts, list) or not parts:
        return []

    chunks: list[str] = []
    for part in parts:
        text: Optional[str] = None
        if isinstance(part, dict) and "text" in part:
            val = part.get("text")
            text = val if isinstance(val, str) else None
        elif isinstance(part, str):
            text = part
        if text:
            chunks.append(text)
    return chunks


def _normalize_stream_event(event: Any) -> Optional[dict]:
    """Normalize an event yielded by InvokeResult.stream() to a dict.

    - Runner normally yields dict (already JSON-decoded).
    - CLI keeps a fallback path for raw SSE strings ("data: {...}").
    """
    if isinstance(event, dict):
        return event
    if isinstance(event, str):
        s = event.strip()
        if not s.startswith("data: "):
            return None
        json_str = s[6:].strip()
        if not json_str:
            return None
        try:
            parsed = json.loads(json_str)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


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
    show_reasoning: bool = typer.Option(
        False,
        "--show-reasoning",
        help="Print LangChain reasoning_content (if present) during streaming",
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Print raw streaming events (and raw JSON response) for debugging",
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
    default_headers = {
        "user_id": "agentkit_user",
        "session_id": "agentkit_sample_session",
    }
    final_headers = default_headers.copy()

    if headers:
        try:
            custom_headers = (
                json.loads(headers) if isinstance(headers, str) else headers
            )
        except json.JSONDecodeError as e:
            console.print(f"[red]Error: Invalid JSON headers: {e}[/red]")
            raise typer.Exit(1)
        if not isinstance(custom_headers, dict):
            console.print(
                '[red]Error: --headers must be a JSON object (e.g. \'{"user_id": "u1"}\').[/red]'
            )
            raise typer.Exit(1)
        final_headers.update(custom_headers)
        console.print(f"[blue]Using merged headers: {final_headers}[/blue]")
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

    if apikey:
        final_headers["Authorization"] = f"Bearer {apikey}"

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
        if raw:
            console.print(
                "[yellow]Raw mode enabled: printing raw stream events[/yellow]\n"
            )
        result_list = []
        complete_text = []
        printed_reasoning_header = False
        printed_answer_header = False
        printed_hidden_reasoning_hint = False
        printed_heartbeat = False
        last_heartbeat_ts = time.monotonic()

        for event in result.stream():
            result_list.append(event)

            if raw:
                # Print the event as received (before normalization), to help debugging.
                if isinstance(event, dict):
                    console.print(json.dumps(event, ensure_ascii=False))
                elif isinstance(event, str):
                    console.print(event.rstrip("\n"))
                else:
                    console.print(repr(event))

            normalized = _normalize_stream_event(event)
            if normalized is None:
                continue

            # Handle A2A JSON-RPC wrapper (unwrap to the underlying result payload)
            if normalized.get("jsonrpc") and "result" in normalized:
                result_payload = normalized.get("result")
                normalized = result_payload if isinstance(result_payload, dict) else {}

            # Keep existing partial-event behavior for ADK style streams.
            # (LangChain message events typically don't carry this field.)
            if not normalized.get("partial", True):
                logger.info("Partial event: %s", normalized)
                continue

            # In raw mode, we still keep termination/error handling, but skip
            # extracted text printing to avoid mixing structured debug output.
            if not raw:
                # LangChain: reasoning_content
                reasoning_chunks = _extract_reasoning_chunks_from_langchain_event(
                    normalized
                )
                if reasoning_chunks:
                    if show_reasoning:
                        if not printed_reasoning_header:
                            console.print("[cyan]🧠 Reasoning:[/cyan]")
                            printed_reasoning_header = True
                        for text in reasoning_chunks:
                            console.print(text, end="", style="yellow")
                    else:
                        # Default behavior: do not print reasoning, but keep the CLI responsive
                        # with a one-time hint and a periodic heartbeat.
                        if not printed_hidden_reasoning_hint:
                            console.print(
                                "[cyan]🤔 Model is thinking... (use --show-reasoning to view)[/cyan]"
                            )
                            printed_hidden_reasoning_hint = True
                        now = time.monotonic()
                        if now - last_heartbeat_ts >= 1.5:
                            console.print(".", end="", style="cyan")
                            printed_heartbeat = True
                            last_heartbeat_ts = now

                # Extract and print incremental answer text chunks
                text_chunks: list[str] = []
                text_chunks.extend(
                    _extract_text_chunks_from_langchain_event(normalized)
                )
                if not text_chunks:
                    text_chunks.extend(_extract_text_chunks_from_adk_event(normalized))

                if text_chunks:
                    # If we printed a hidden reasoning hint / heartbeat dots, separate answer on a new line.
                    if printed_hidden_reasoning_hint or printed_heartbeat:
                        console.print("")
                        printed_hidden_reasoning_hint = False
                        printed_heartbeat = False
                    if printed_reasoning_header and not printed_answer_header:
                        console.print("\n[cyan]📝 Answer:[/cyan]")
                        printed_answer_header = True
                    for text in text_chunks:
                        complete_text.append(text)
                        console.print(text, end="", style="green")

            # Display error information in event (if any)
            if "error" in normalized:
                console.print(f"\n[red]Error: {normalized['error']}[/red]")

            # Handle status updates (e.g., final flag or completed status)
            if normalized.get("final") is True:
                break

            status = normalized.get("status")
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
        if raw:
            console.print(json.dumps(response, ensure_ascii=False))
        else:
            console.print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        console.print(response)

    return str(response)

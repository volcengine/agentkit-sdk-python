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

"""A2A JSON-RPC helpers for sandbox CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sys
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit
import uuid

import requests

DEFAULT_A2A_PATH = "/a2a"
DEFAULT_A2A_TIMEOUT_SECONDS = 1200
DEFAULT_A2A_HISTORY_LENGTH = 20
DEFAULT_A2A_POLL_INTERVAL_SECONDS = 2.0
DEFAULT_READY_RETRIES = 12
DEFAULT_READY_RETRY_DELAY = 5.0
RETRYABLE_A2A_STATUS_CODES = {502, 503, 504}
TERMINAL_STATES = {
    "completed",
    "failed",
    "canceled",
    "rejected",
    "input-required",
    "auth-required",
}


class A2AApiError(RuntimeError):
    """Raised when a sandbox A2A request fails."""

    def __init__(
        self,
        operation: str,
        message: str,
        *,
        status_code: int | None = None,
        response_text: str | None = None,
        response_json: Any = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.status_code = status_code
        self.response_text = response_text
        self.response_json = response_json


@dataclass(frozen=True)
class A2ATaskStart:
    task: dict[str, Any]
    task_id: str
    context_id: str | None


def send_message_nonblocking(
    *,
    endpoint: object,
    prompt: str,
    a2a_path: str = DEFAULT_A2A_PATH,
    context_id: str | None = None,
    request_metadata: dict[str, str] | None = None,
    history_length: int | None = DEFAULT_A2A_HISTORY_LENGTH,
    timeout: int = 60,
    readiness_retries: int = DEFAULT_READY_RETRIES,
    readiness_retry_delay: float = DEFAULT_READY_RETRY_DELAY,
) -> A2ATaskStart:
    message: dict[str, Any] = {
        "kind": "message",
        "messageId": str(uuid.uuid4()),
        "role": "user",
        "parts": [{"kind": "text", "text": prompt}],
    }
    if context_id:
        message["contextId"] = context_id

    configuration: dict[str, Any] = {"blocking": False}
    if history_length is not None:
        configuration["historyLength"] = history_length

    params: dict[str, Any] = {
        "message": message,
        "configuration": configuration,
    }
    if request_metadata:
        params["metadata"] = request_metadata

    response = _post_jsonrpc(
        endpoint=endpoint,
        a2a_path=a2a_path,
        payload={
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": params,
        },
        timeout=timeout,
        operation="A2ASendMessage",
        readiness_retries=readiness_retries,
        readiness_retry_delay=readiness_retry_delay,
    )
    task = _jsonrpc_result_task("A2ASendMessage", response)
    task_id = _task_id(task)
    if not task_id:
        raise A2AApiError(
            "A2ASendMessage",
            "response task does not contain id",
            response_json=response,
        )
    return A2ATaskStart(
        task=task,
        task_id=task_id,
        context_id=task_context_id(task),
    )


def get_task(
    *,
    endpoint: object,
    task_id: str,
    a2a_path: str = DEFAULT_A2A_PATH,
    history_length: int | None = DEFAULT_A2A_HISTORY_LENGTH,
    timeout: int = 60,
    readiness_retries: int = DEFAULT_READY_RETRIES,
    readiness_retry_delay: float = DEFAULT_READY_RETRY_DELAY,
) -> dict[str, Any]:
    params: dict[str, Any] = {"id": task_id}
    if history_length is not None:
        params["historyLength"] = history_length

    response = _post_jsonrpc(
        endpoint=endpoint,
        a2a_path=a2a_path,
        payload={
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/get",
            "params": params,
        },
        timeout=timeout,
        operation="A2AGetTask",
        readiness_retries=readiness_retries,
        readiness_retry_delay=readiness_retry_delay,
    )
    return _jsonrpc_result_task("A2AGetTask", response)


def poll_task_until_terminal(
    *,
    endpoint: object,
    task_id: str,
    a2a_path: str = DEFAULT_A2A_PATH,
    history_length: int | None = DEFAULT_A2A_HISTORY_LENGTH,
    timeout: int = DEFAULT_A2A_TIMEOUT_SECONDS,
    interval: float = DEFAULT_A2A_POLL_INTERVAL_SECONDS,
    print_events: bool = False,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    latest_task = get_task(
        endpoint=endpoint,
        task_id=task_id,
        a2a_path=a2a_path,
        history_length=history_length,
        timeout=min(60, timeout),
    )
    while task_state(latest_task) not in TERMINAL_STATES:
        if print_events:
            print(json.dumps(latest_task, ensure_ascii=False), file=sys.stderr)
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out while waiting for A2A task {task_id}")
        time.sleep(interval)
        latest_task = get_task(
            endpoint=endpoint,
            task_id=task_id,
            a2a_path=a2a_path,
            history_length=history_length,
            timeout=min(60, timeout),
        )
    if print_events:
        print(json.dumps(latest_task, ensure_ascii=False), file=sys.stderr)
    return latest_task


def task_result_parts(task: dict[str, Any] | None) -> list[dict[str, str]]:
    if not task:
        return []
    for source in (
        _artifact_parts(task),
        _message_parts(_get_nested(task, ("status", "message"))),
        _history_agent_parts(task),
    ):
        parts = _text_parts(source)
        if parts:
            return parts
    return []


def task_result_text(task: dict[str, Any] | None) -> str:
    return "\n".join(part["text"] for part in task_result_parts(task))


def task_state(task: dict[str, Any] | None) -> str | None:
    value = _get_nested(task, ("status", "state"))
    return value if isinstance(value, str) else None


def task_context_id(task: dict[str, Any] | None) -> str | None:
    if not isinstance(task, dict):
        return None
    value = task.get("contextId") or task.get("context_id")
    return value if isinstance(value, str) and value else None


def build_a2a_url(endpoint: object, a2a_path: str = DEFAULT_A2A_PATH) -> str:
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise A2AApiError("A2ARequest", "Sandbox session endpoint is missing")

    parts = urlsplit(endpoint.strip())
    base_path = parts.path.rstrip("/")
    if not a2a_path or a2a_path == "/":
        resolved_path = f"{base_path}/" if base_path else "/"
    else:
        suffix = "/" + a2a_path.strip("/")
        resolved_path = f"{base_path}{suffix}" if base_path else suffix
    return urlunsplit(
        (parts.scheme, parts.netloc, resolved_path, parts.query, parts.fragment)
    )


def _post_jsonrpc(
    *,
    endpoint: object,
    a2a_path: str,
    payload: dict[str, Any],
    timeout: int,
    operation: str,
    readiness_retries: int,
    readiness_retry_delay: float,
) -> dict[str, Any]:
    url = build_a2a_url(endpoint, a2a_path)
    response: requests.Response | None = None
    for attempt in range(readiness_retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            if attempt >= readiness_retries:
                raise A2AApiError(operation, str(exc)) from exc
            time.sleep(readiness_retry_delay)
            continue

        if not _is_retryable_a2a_response(response) or attempt >= readiness_retries:
            break
        time.sleep(readiness_retry_delay)

    if response is None:
        raise A2AApiError(operation, "request was not sent")

    body = response.text
    if response.status_code < 200 or response.status_code >= 300:
        raise A2AApiError(
            operation,
            _failure_hint(response.status_code, body),
            status_code=response.status_code,
            response_text=body,
        )

    try:
        parsed = response.json()
    except ValueError as exc:
        raise A2AApiError(
            operation,
            "response is not valid JSON",
            status_code=response.status_code,
            response_text=body,
        ) from exc
    if not isinstance(parsed, dict):
        raise A2AApiError(
            operation,
            "response JSON is not an object",
            status_code=response.status_code,
            response_json={"response": parsed},
        )
    if parsed.get("error") is not None:
        raise A2AApiError(
            operation,
            "A2A JSON-RPC returned error",
            status_code=response.status_code,
            response_json=parsed,
        )
    return parsed


def _is_retryable_a2a_response(response: requests.Response) -> bool:
    if response.status_code in RETRYABLE_A2A_STATUS_CODES:
        return True
    if response.status_code != 500:
        return False

    body = response.text.lower()
    return "function_proxy_error" in body and "connection refused" in body


def _jsonrpc_result_task(operation: str, response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    if not isinstance(result, dict):
        raise A2AApiError(
            operation,
            "response does not contain result task",
            response_json=response,
        )
    if result.get("kind") != "task" and "status" not in result:
        raise A2AApiError(
            operation,
            "response result is not an A2A task",
            response_json=response,
        )
    return result


def _task_id(task: dict[str, Any] | None) -> str | None:
    if not isinstance(task, dict):
        return None
    value = task.get("id")
    return value if isinstance(value, str) and value else None


def _artifact_parts(task: dict[str, Any]) -> list[Any]:
    artifacts = task.get("artifacts")
    if not isinstance(artifacts, list):
        return []
    parts: list[Any] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        artifact_parts = artifact.get("parts")
        if isinstance(artifact_parts, list):
            parts.extend(artifact_parts)
    return parts


def _message_parts(message: Any) -> list[Any]:
    if not isinstance(message, dict):
        return []
    parts = message.get("parts")
    return parts if isinstance(parts, list) else []


def _history_agent_parts(task: dict[str, Any]) -> list[Any]:
    history = task.get("history")
    if not isinstance(history, list):
        return []
    parts: list[Any] = []
    for message in reversed(history):
        if not isinstance(message, dict) or message.get("role") != "agent":
            continue
        message_parts = message.get("parts")
        if isinstance(message_parts, list):
            text_parts = _text_parts(message_parts)
            if text_parts:
                parts.extend(message_parts)
                break
    return parts


def _text_parts(parts: list[Any]) -> list[dict[str, str]]:
    return [
        {"text": part["text"]}
        for part in parts
        if isinstance(part, dict)
        and part.get("kind") == "text"
        and isinstance(part.get("text"), str)
        and part["text"]
    ]


def _get_nested(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _failure_hint(status_code: int, body: str) -> str:
    lower_body = body.lower()
    if status_code in (404, 410) or "expired" in lower_body or "deleted" in lower_body:
        return "Sandbox session or A2A task may have expired or been deleted"
    if status_code in (401, 403):
        return "Sandbox access credentials may have expired or become invalid"
    return "A2A request returned non-2xx status"

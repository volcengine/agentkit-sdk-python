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

"""Single source of truth for HTTP timeout/retry defaults.

Defaults and their controlling environment variables live here so the
HTTP/credential/SDK paths share one consistent, env-tunable configuration.
``AGENTKIT_HTTP_RETRIES=0`` disables retries.
"""

import os

ENV_HTTP_TIMEOUT = "AGENTKIT_HTTP_TIMEOUT"
ENV_HTTP_RETRIES = "AGENTKIT_HTTP_RETRIES"
ENV_STREAM_TIMEOUT = "AGENTKIT_STREAM_TIMEOUT"
ENV_POLL_TIMEOUT = "AGENTKIT_POLL_TIMEOUT"
ENV_WS_PING_INTERVAL = "AGENTKIT_WS_PING_INTERVAL"
ENV_WS_PING_TIMEOUT = "AGENTKIT_WS_PING_TIMEOUT"

DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_HTTP_RETRIES = 2
DEFAULT_STREAM_TIMEOUT = 300.0
# Upper bound for status-polling loops (resource create/status waits) so a
# stuck backend can never hang the CLI forever. 30 min covers slow provisioning.
DEFAULT_POLL_TIMEOUT = 1800.0
# WebSocket keepalive: send a ping every interval and drop the connection if no
# pong arrives within the timeout, so a silently dead server can't wedge the
# interactive session indefinitely.
DEFAULT_WS_PING_INTERVAL = 20.0
DEFAULT_WS_PING_TIMEOUT = 10.0


def http_timeout() -> float:
    """Return the per-request HTTP timeout in seconds (clamped to >= 1.0)."""
    try:
        return max(1.0, float(os.getenv(ENV_HTTP_TIMEOUT, "30")))
    except ValueError:
        return DEFAULT_HTTP_TIMEOUT


def http_retries() -> int:
    """Return the number of HTTP retries (clamped to >= 0; 0 disables retries)."""
    try:
        return max(0, int(os.getenv(ENV_HTTP_RETRIES, "2")))
    except ValueError:
        return DEFAULT_HTTP_RETRIES


def stream_timeout() -> float:
    """Return the streaming-response timeout in seconds (clamped to >= 1.0)."""
    try:
        return max(1.0, float(os.getenv(ENV_STREAM_TIMEOUT, "300")))
    except ValueError:
        return DEFAULT_STREAM_TIMEOUT


def poll_timeout() -> float:
    """Return the upper bound in seconds for status-polling loops (>= 1.0)."""
    try:
        return max(1.0, float(os.getenv(ENV_POLL_TIMEOUT, "1800")))
    except ValueError:
        return DEFAULT_POLL_TIMEOUT


def ws_ping_interval() -> float:
    """Return the WebSocket keepalive ping interval in seconds (>= 1.0)."""
    try:
        return max(1.0, float(os.getenv(ENV_WS_PING_INTERVAL, "20")))
    except ValueError:
        return DEFAULT_WS_PING_INTERVAL


def ws_ping_timeout() -> float:
    """Return the WebSocket pong-wait timeout in seconds (>= 1.0).

    Clamped to strictly less than the ping interval, as required by
    ``websocket-client``'s ``run_forever``.
    """
    try:
        value = max(1.0, float(os.getenv(ENV_WS_PING_TIMEOUT, "10")))
    except ValueError:
        value = DEFAULT_WS_PING_TIMEOUT
    interval = ws_ping_interval()
    if value >= interval:
        value = max(1.0, interval - 1.0)
    return value

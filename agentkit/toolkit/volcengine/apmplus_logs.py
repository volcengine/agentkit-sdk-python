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

"""Query a harness runtime's logs from APMPlus / TLS (VE-sign auth).

Two steps:

1. ``GetLogModuleConfig`` (APMPlus OpenAPI, Action style) — signed with
   Volcengine SigV4 via :func:`agentkit.auth._sigv4.sign_headers` — returns the
   TLS log topic id that AgentKit runtime logs are written to.
2. ``SearchLogs`` (TLS native API) — issued via the official ``volcengine.tls``
   SDK, which handles TLS's own SigV4 variant — searches that topic.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from agentkit.auth._sigv4 import sign_headers

logger = logging.getLogger("agentkit." + __name__)

# APMPlus OpenAPI: returns the runtime log module config (incl. the TLS topic).
_APMPLUS_SERVICE = "apmplus_server"
_APMPLUS_ACTION = "GetLogModuleConfig"
_APMPLUS_VERSION = "2024-07-30"

_TIMEOUT = 30


def _apmplus_host(region: str) -> str:
    return f"apmplus-server.{region}.volcengineapi.com"


def _tls_host(region: str) -> str:
    return f"tls-{region}.volces.com"


def get_log_topic_id(
    *,
    access_key: str,
    secret_key: str,
    region: str,
    session_token: Optional[str] = None,
    scheme: str = "https",
) -> str:
    """Resolve the TLS log topic id via APMPlus ``GetLogModuleConfig``.

    The action takes no request parameters; it returns the account/region log
    module config, whose ``LogTopicId`` is the TLS topic AgentKit runtimes log to.

    Raises:
        ValueError: on a non-200 response or when ``LogTopicId`` is absent.
    """
    host = _apmplus_host(region)
    query = {"Action": _APMPLUS_ACTION, "Version": _APMPLUS_VERSION}
    body = b"{}"
    headers = sign_headers(
        "POST",
        host,
        query,
        body,
        access_key=access_key,
        secret_key=secret_key,
        service=_APMPLUS_SERVICE,
        region=region,
        session_token=session_token,
    )
    resp = requests.post(
        f"{scheme}://{host}/", params=query, data=body, headers=headers, timeout=_TIMEOUT
    )
    if resp.status_code != 200:
        raise ValueError(
            f"GetLogModuleConfig failed (HTTP {resp.status_code}): {resp.text}"
        )

    data = resp.json()
    # APMPlus returns {"data": {"LogTopicId": ...}, ...}; the OpenAPI gateway may
    # additionally wrap it under "Result". Accept either shape.
    container = data.get("Result", data) if isinstance(data, dict) else {}
    module = container.get("data", {}) if isinstance(container, dict) else {}
    topic_id = module.get("LogTopicId") if isinstance(module, dict) else None
    if not topic_id:
        raise ValueError(f"GetLogModuleConfig returned no LogTopicId: {data}")
    return str(topic_id)


def search_logs(
    *,
    access_key: str,
    secret_key: str,
    region: str,
    topic_id: str,
    query: str,
    start_time_ms: int,
    end_time_ms: int,
    limit: int = 20,
    sort: str = "desc",
    session_token: Optional[str] = None,
    scheme: str = "https",
    tls_host: Optional[str] = None,
) -> Dict[str, Any]:
    """Search a TLS topic via the native ``SearchLogs`` API (api-version 0.3.0).

    Uses the official ``volcengine.tls`` SDK, which applies the TLS-specific
    request signing (service ``TLS``, ``Content-MD5`` / ``x-tls-apiversion``
    headers). Returns a normalized ``{ResultStatus, Count, Logs, ...}`` dict.

    Raises:
        ValueError: when the TLS API rejects the request.
    """
    from volcengine.tls.TLSService import TLSService
    from volcengine.tls.tls_requests import SearchLogsRequest
    from volcengine.tls.tls_exception import TLSException

    endpoint = tls_host or _tls_host(region)
    # Only pass a session token when present: the SDK treats its absence (default)
    # as "no token", and signing an empty token would be rejected.
    token_kwargs = {"security_token": session_token} if session_token else {}
    service = TLSService(
        endpoint=f"{scheme}://{endpoint}",
        access_key_id=access_key,
        access_key_secret=secret_key,
        region=region,
        timeout=_TIMEOUT,
        **token_kwargs,
    )
    request = SearchLogsRequest(
        topic_id=topic_id,
        query=query,
        start_time=start_time_ms,
        end_time=end_time_ms,
        limit=limit,
        sort=sort,
    )
    try:
        result = service.search_logs_v2(request).get_search_result()
    except TLSException as exc:
        raise ValueError(f"SearchLogs failed: {exc}") from exc

    if result is None:
        raise ValueError("SearchLogs returned no result")

    return {
        "ResultStatus": result.result_status,
        "Count": result.count,
        "Limit": result.limit,
        "ListOver": result.list_over,
        "Analysis": result.analysis,
        "Context": result.context,
        "Logs": result.logs or [],
    }


def flatten_logs(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten the ``Logs`` field of a SearchLogs response to a list of dicts.

    ``Logs`` is normally a list of JSON maps; for some context queries it is a
    list of single-element lists. Both shapes are flattened to dict entries.
    """
    logs = response.get("Logs") if isinstance(response, dict) else None
    if not isinstance(logs, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in logs:
        if isinstance(item, dict):
            out.append(item)
        elif isinstance(item, list):
            out.extend(x for x in item if isinstance(x, dict))
    return out

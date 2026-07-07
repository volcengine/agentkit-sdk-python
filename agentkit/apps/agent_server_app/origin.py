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

import inspect
import logging
import os
import re
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

_REGEX_PREFIX = "regex:"

DEFAULT_AGENTKIT_ALLOW_ORIGINS = ["*"]

STRICT_AGENTKIT_HOSTED_ORIGINS = [
    "https://console.volcengine.com",
    "https://console.byteplus.com",
    "regex:https://.*\\.volcengine\\.com",
    "regex:https://.*\\.volceapi\\.com",
    "regex:https://.*\\.byteplus\\.com",
    "regex:https://.*\\.byteplusapi\\.com",
]


def resolve_agentkit_allow_origins(
    *,
    allow_origins: list[str] | None,
    allow_origin_regex: str | list[str] | None = None,
) -> list[str]:
    """Resolve AgentKit CORS origins with SDK defaults and env overrides."""

    env_origins = _get_env_list("AGENTKIT_ALLOW_ORIGINS", "ADK_ALLOW_ORIGINS")
    env_regexes = _get_env_list(
        "AGENTKIT_ALLOW_ORIGIN_REGEX",
        "ADK_ALLOW_ORIGIN_REGEX",
    )
    if allow_origins is not None:
        origins = list(allow_origins)
    elif env_origins is not None or env_regexes is not None:
        origins = env_origins or []
    elif _truthy_env("AGENTKIT_DISABLE_DEFAULT_ALLOW_ORIGINS"):
        origins = []
    else:
        origins = list(DEFAULT_AGENTKIT_ALLOW_ORIGINS)

    if allow_origin_regex is None:
        regexes = env_regexes or []
    else:
        regexes = _as_list(allow_origin_regex)

    resolved = [_normalize_origin(origin) for origin in origins]
    resolved.extend(_normalize_regex(pattern) for pattern in regexes)

    deduped = _dedupe(resolved)
    _validate_regex_origins(deduped)
    return deduped


def split_allow_origins(allow_origins: list[str]) -> tuple[list[str], str | None]:
    """Split ADK-style origins into literal origins and a combined regex."""

    literal_origins: list[str] = []
    regex_patterns: list[str] = []
    for origin in allow_origins:
        if origin.startswith(_REGEX_PREFIX):
            pattern = origin[len(_REGEX_PREFIX) :]
            if pattern:
                regex_patterns.append(pattern)
        else:
            literal_origins.append(origin)

    return literal_origins, "|".join(regex_patterns) if regex_patterns else None


def supports_get_fast_api_kwarg(func: Callable[..., Any], kwarg_name: str) -> bool:
    """Return whether a callable accepts a given keyword argument."""

    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return True

    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            return True
    return kwarg_name in signature.parameters


def adk_supports_regex_origins() -> bool:
    """Return whether installed ADK understands `regex:` allow_origins entries."""

    try:
        from google.adk.cli import adk_web_server

        return hasattr(adk_web_server, "_parse_cors_origins")
    except Exception:
        return False


def add_cors_compat_middleware(app: FastAPI, allow_origins: list[str]) -> None:
    """Add CORS middleware for ADK versions that cannot parse regex origins."""

    literal_origins, allow_origin_regex = split_allow_origins(allow_origins)
    # A wildcard origin combined with allow_credentials=True is unsafe: Starlette
    # then echoes the caller's Origin back with Access-Control-Allow-Credentials,
    # which lets *any* site make credentialed cross-origin calls. Only enable
    # credentials when the origin set is an explicit allowlist.
    allow_credentials = "*" not in literal_origins
    if not allow_credentials:
        logger.warning(
            "CORS allow_origins includes '*'; disabling allow_credentials. Set "
            "AGENTKIT_ALLOW_ORIGINS (or allow_origins=) to an explicit allowlist "
            "to permit credentialed cross-origin requests."
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=literal_origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _normalize_origin(origin: str) -> str:
    origin = origin.strip()
    if not origin or origin == "*" or origin.startswith(_REGEX_PREFIX):
        return origin
    if "*" in origin:
        return _normalize_regex(_glob_to_regex(origin))
    return origin


def _normalize_regex(pattern: str) -> str:
    pattern = pattern.strip()
    if not pattern:
        return pattern
    if pattern.startswith(_REGEX_PREFIX):
        return pattern
    return f"{_REGEX_PREFIX}{pattern}"


def _glob_to_regex(origin: str) -> str:
    return re.escape(origin).replace("\\*", ".*")


def _validate_regex_origins(origins: list[str]) -> None:
    for origin in origins:
        if not origin.startswith(_REGEX_PREFIX):
            continue
        pattern = origin[len(_REGEX_PREFIX) :]
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid allow origin regex '{pattern}': {e}") from e


def _get_env_list(*names: str) -> list[str] | None:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        return [item.strip() for item in value.split(",") if item.strip()]
    return None


def _truthy_env(name: str) -> bool:
    value = os.getenv(name, "")
    return value.lower() in {"1", "true", "yes", "on"}


def _as_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped

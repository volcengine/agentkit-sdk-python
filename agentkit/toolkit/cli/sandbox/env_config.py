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

"""Environment variable profiles for sandbox tool and session creation."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Optional

from agentkit.sdk.tools import types as tools_types
from agentkit.toolkit.cli.sandbox.model_config import (
    ANTHROPIC_BASE_URL_ENV_KEYS,
    CODE_ENV_CODEX_HOME,
    CODE_ENV_HOME,
    CODEX_CONFIG_TOML_ENV,
    CODEX_MODEL_CATALOG_JSON_ENV,
    MODEL_API_KEY_ENV,
    MODEL_API_KEY_ENV_KEYS,
    MODEL_BASE_URL_ENV_KEYS,
    MODEL_NAME_ENV_KEYS,
    MODEL_PROVIDER_ENV,
    ModelProviderType,
    build_codex_config_toml,
    build_codex_model_catalog_json,
    infer_model_provider_from_base_url,
    normalize_model_base_url,
    normalize_model_provider,
    normalize_optional_model_provider,
    resolve_model_base_urls,
    resolve_model_name,
    should_emit_codex_model_catalog,
    should_emit_codex_model_config,
    validate_model_provider_base_url,
)

DEFAULT_CREATE_TOOL_TYPE = "CodeEnv"
PRIVATE_TOOL_TYPE = "Private"
PRIVATE_TOOL_COMMAND = "/opt/gem/run.sh"
PRIVATE_TOOL_PORT = 8080
PRIVATE_TOOL_VARS = (
    (
        "PATH",
        "/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:"
        "/usr/sbin:/usr/bin:/sbin:/bin",
    ),
    ("DEBIAN_FRONTEND", "noninteractive"),
    ("USER", "gem"),
    ("USER_UID", "1000"),
    ("USER_GID", "1000"),
    ("DISPLAY", ":99.0"),
    ("DISPLAY_WIDTH", "1280"),
    ("DISPLAY_HEIGHT", "1024"),
    ("DISPLAY_DEPTH", "24"),
    ("XDG_RUNTIME_DIR", "/tmp/runtime-gem"),
    ("BROWSER_EXECUTABLE_PATH", "/usr/local/bin/browser"),
    ("BROWSER_REMOTE_DEBUGGING_PORT", "9222"),
    (
        "BROWSER_COMMANDLINE_ARGS",
        "--disable-backgrounding-occluded-windows     "
        "--disable-background-timer-throttling     "
        "--disable-blink-features=AutomationControlled     "
        "--disable-dev-shm-usage     "
        "--disable-external-intent-requests     "
        "--disable-features=IPH_DesktopCustomizeChrome,IsolateOrigins,"
        "site-per-proces,Translate     "
        "--disable-focus-on-load     "
        "--disable-gpu     "
        "--disable-infobars     "
        "--disable-popup-blocking     "
        "--disable-prompt-on-repost     "
        "--disable-renderer-backgrounding     "
        "--disable-site-isolation-trials     "
        "--disable-web-security     "
        "--disable-window-activation     "
        "--mute-audio     "
        "--no-default-browser-check     "
        "--no-first-run     "
        "--noerrdialogs     "
        "--remote-allow-origins=*     "
        "--remote-debugging-port=9222     "
        "--suppress-message-center-popups     "
        "--start-maximized",
    ),
    ("BROWSER_EXTRA_ARGS", ""),
    ("DNS_OVER_HTTPS_TEMPLATES", ""),
    ("LOG_DIR", "/var/log/gem"),
    ("JWT_PUBLIC_KEY", ""),
    ("VNC_SERVER_PORT", "5900"),
    ("WEBSOCKET_PROXY_PORT", "6080"),
    ("GEM_SERVER_PORT", "8088"),
    ("MCP_SERVER_PORT", "8089"),
    ("PUBLIC_PORT", "8080"),
    ("AUTH_BACKEND_PORT", "8081"),
    ("WAIT_PORTS", "8091"),
    ("WAIT_TIMEOUT", "300"),
    ("WAIT_INTERVAL", "0.25"),
    ("RUN_HOOK_INIT", ""),
    ("RUN_HOOK_PRE_SERVICES", ""),
    ("RUN_HOOK_POST_READY", ""),
    ("RUN_HOOKS_STRICT", "false"),
    ("SANDBOX_SRV_PORT", "8091"),
    ("JUPYTER_LAB_PORT", "8888"),
    ("CODE_SERVER_PORT", "8200"),
    ("MCP_SERVER_BROWSER_PORT", "8100"),
    ("TINYPROXY_PORT", "8118"),
    ("MAX_SHELL_SESSIONS", "50"),
    ("PYTHONPATH", ""),
    ("LOG_TOOL_TRACE", "false"),
    ("LANG", "en_US.UTF-8"),
    ("LANGUAGE", "en_US:en"),
    ("LC_ALL", "en_US.UTF-8"),
    ("PUPPETEER_EXECUTABLE_PATH", "/usr/local/bin/browser"),
    ("PUPPETEER_SKIP_CHROMIUM_DOWNLOAD", "true"),
    ("BROWSER_NO_SANDBOX", ""),
    ("BROWSER_LANG", "en-US"),
    (
        "BROWSER_USER_AGENT",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36",
    ),
    ("UV_TOOL_BIN_DIR", "/usr/local/bin/"),
    ("UV_TOOL_DIR", "/usr/local/share/uv/tools"),
    ("DISABLE_JUPYTER", "false"),
    ("DISABLE_CODE_SERVER", "false"),
    ("EXTRA_MCP_SERVERS", ""),
    ("OTEL_SDK_DISABLED", "false"),
    (
        "SRV_PYTHONPATH",
        "/otel-auto-instrumentation-python/opentelemetry/instrumentation/"
        "auto_instrumentation:/otel-auto-instrumentation-python",
    ),
    ("OTEL_PYTHON_DISABLED_INSTRUMENTATIONS", "redis"),
    ("FAAS_SANDBOX_RUNTIME_INJECTION_ENABLE_SANDBOXD", "false"),
    ("PYTHON_CODE_EXEC_VERSION", "python3"),
    ("GO_PATH", "/usr/local/go"),
)
DISABLED_SERVICE_ENV_KEYS = (
    "DISABLE_JUPYTER",
    "DISABLE_CODE_SERVER",
    "DISABLE_NODEJS_REPL",
)
BROWSER_EXTRA_ARGS_ENV = "BROWSER_EXTRA_ARGS"
DEFAULT_BROWSER_EXTRA_ARGS = (
    "--enable-unsafe-swiftshader --use-gl=angle "
    "--use-angle=swiftshader-webgl --ignore-gpu-blocklist"
)
WEB_SEARCH_API_KEY_ENV = "WEB_SEARCH_API_KEY"

MODEL_AGENT_ENV_KEYS = (
    "MODEL_AGENT_API_BASE",
    "MODEL_AGENT_API_KEY",
    "MODEL_AGENT_PROVIDER",
    "MODEL_AGENT_NAME",
    "MODEL_AGENT_EXTRA_HEADERS",
)
REQUIRED_MODEL_AGENT_ENV_KEYS = (
    "MODEL_AGENT_API_BASE",
    "MODEL_AGENT_API_KEY",
    "MODEL_AGENT_PROVIDER",
    "MODEL_AGENT_NAME",
)
OPENCLAW_CONFIG_FILE = Path("/root/.openclaw/openclaw.json")
OPENCLAW_MODEL_CONFIG_ROOTS = (
    ("models",),
    ("model",),
    ("modelProviders",),
    ("model_providers",),
    ("providers",),
    ("agents", "defaults", "model"),
)
OPENCLAW_API_BASE_KEYS = (
    "api_base_url",
    "apiBaseUrl",
    "api_base",
    "apiBase",
    "base_url",
    "baseURL",
    "baseUrl",
    "baseurl",
)
OPENCLAW_API_KEY_KEYS = (
    "api_key",
    "apiKey",
    "apikey",
    "key",
    "model_key",
    "modelKey",
)
OPENCLAW_PROVIDER_API_KEYS = (
    "api",
    "model_api",
    "modelApi",
    "api_type",
    "apiType",
)
OPENCLAW_MODEL_HEADER_KEYS = (
    "headers",
    "extra_headers",
    "extraHeaders",
)
OPENCLAW_PROVIDER_API_ROUTES = {
    "openai-completions": "openai",
    "openai-responses": "openai/responses",
    "openai-codex-responses": "openai/responses",
    "anthropic-messages": "anthropic",
    "google-generative-ai": "gemini",
    "github-copilot": "github_copilot",
    "bedrock-converse-stream": "bedrock/converse",
    "ollama": "ollama_chat",
    "azure-openai-responses": "azure/responses",
}


class EnvBundle:
    """Ordered environment map with small adapters for SDK request types."""

    def __init__(self) -> None:
        self._values: OrderedDict[str, str] = OrderedDict()

    def add(
        self, key: str, value: Optional[str], *, include_empty: bool = False
    ) -> None:
        resolved = (value or "").strip()
        if not resolved and not include_empty:
            return
        self._values[key] = resolved

    def add_many(
        self,
        keys: tuple[str, ...],
        value: Optional[str],
        *,
        include_empty: bool = False,
    ) -> None:
        for key in keys:
            self.add(key, value, include_empty=include_empty)

    def to_create_tool_envs(self) -> list[tools_types.EnvsItemForCreateTool] | None:
        if not self._values:
            return None
        return [
            tools_types.EnvsItemForCreateTool(Key=key, Value=value)
            for key, value in self._values.items()
        ]

    def to_create_session_envs(
        self,
    ) -> list[tools_types.EnvsItemForCreateSession] | None:
        if not self._values:
            return None
        return [
            tools_types.EnvsItemForCreateSession(key=key, value=value)
            for key, value in self._values.items()
        ]

    def to_required_create_session_envs(
        self,
    ) -> list[tools_types.EnvsItemForCreateSession]:
        return [
            tools_types.EnvsItemForCreateSession(key=key, value=value)
            for key, value in self._values.items()
        ]


@dataclass(frozen=True)
class ResolvedSandboxModelEnv:
    provider: str | None
    model_name: str | None
    base_url: str | None
    anthropic_base_url: str | None
    api_key: str | None
    model_base_url: str | None


def _resolve_sandbox_model_env(
    *,
    model_name: Optional[str],
    model_api_key: Optional[str],
    model_provider: str | ModelProviderType | None,
    model_base_url: Optional[str],
    model_provider_was_provided: Optional[bool],
    model_base_url_was_provided: Optional[bool],
    require_provider: bool,
) -> ResolvedSandboxModelEnv:
    validate_model_provider_base_url(
        model_provider=model_provider,
        model_base_url=model_base_url,
        model_provider_was_provided=model_provider_was_provided,
        model_base_url_was_provided=model_base_url_was_provided,
    )
    resolved_model_base_url = normalize_model_base_url(model_base_url)
    effective_model_provider = model_provider or infer_model_provider_from_base_url(
        resolved_model_base_url
    )
    resolved_model_provider = (
        normalize_model_provider(effective_model_provider)
        if require_provider
        else normalize_optional_model_provider(effective_model_provider)
    )
    resolved_model_name = (
        resolve_model_name(model_name, resolved_model_provider)
        if resolved_model_provider
        else (model_name or "").strip()
    )
    should_resolve_urls = bool(
        require_provider or resolved_model_provider or resolved_model_base_url
    )
    resolved_base_url, resolved_anthropic_base_url = (
        resolve_model_base_urls(
            model_provider=resolved_model_provider,
            model_base_url=resolved_model_base_url,
        )
        if should_resolve_urls
        else (None, None)
    )
    return ResolvedSandboxModelEnv(
        provider=resolved_model_provider,
        model_name=resolved_model_name,
        base_url=resolved_base_url,
        anthropic_base_url=resolved_anthropic_base_url,
        api_key=model_api_key or os.getenv(MODEL_API_KEY_ENV),
        model_base_url=resolved_model_base_url,
    )


def _append_standard_model_envs(
    bundle: EnvBundle,
    resolved: ResolvedSandboxModelEnv,
    *,
    include_base_urls: bool,
    include_api_key: bool,
    api_key_before_base_urls: bool = False,
) -> None:
    bundle.add_many((MODEL_PROVIDER_ENV,), resolved.provider)
    bundle.add_many(MODEL_NAME_ENV_KEYS, resolved.model_name)
    if include_api_key and api_key_before_base_urls:
        bundle.add_many(MODEL_API_KEY_ENV_KEYS, resolved.api_key)
    if include_base_urls:
        bundle.add_many(MODEL_BASE_URL_ENV_KEYS, resolved.base_url)
        bundle.add_many(ANTHROPIC_BASE_URL_ENV_KEYS, resolved.anthropic_base_url)
    if include_api_key and not api_key_before_base_urls:
        bundle.add_many(MODEL_API_KEY_ENV_KEYS, resolved.api_key)


def build_create_tool_envs(
    *,
    tool_type: str,
    model_name: Optional[str] = None,
    model_api_key: Optional[str] = None,
    model_provider: str | ModelProviderType | None = None,
    model_base_url: Optional[str] = None,
    model_provider_was_provided: Optional[bool] = None,
    model_base_url_was_provided: Optional[bool] = None,
    websearch_apikey: Optional[str] = None,
) -> list[tools_types.EnvsItemForCreateTool] | None:
    """Build CreateTool.Envs for the sandbox create profile."""

    bundle = EnvBundle()
    resolved = _resolve_sandbox_model_env(
        model_name=model_name,
        model_api_key=model_api_key,
        model_provider=model_provider,
        model_base_url=model_base_url,
        model_provider_was_provided=model_provider_was_provided,
        model_base_url_was_provided=model_base_url_was_provided,
        require_provider=True,
    )
    _append_standard_model_envs(
        bundle,
        resolved,
        include_base_urls=True,
        include_api_key=True,
        api_key_before_base_urls=True,
    )
    bundle.add_many(DISABLED_SERVICE_ENV_KEYS, "true")
    bundle.add(BROWSER_EXTRA_ARGS_ENV, DEFAULT_BROWSER_EXTRA_ARGS)
    bundle.add(WEB_SEARCH_API_KEY_ENV, websearch_apikey)

    if tool_type.strip() == DEFAULT_CREATE_TOOL_TYPE:
        bundle.add("OPENCODE_DISABLE_AUTOUPDATE", "1")
        bundle.add("HOME", CODE_ENV_HOME)
        bundle.add("CODEX_HOME", CODE_ENV_CODEX_HOME)
        if resolved.model_name and should_emit_codex_model_config(
            model_provider=resolved.provider,
            model_base_url=resolved.model_base_url,
        ):
            bundle.add(
                CODEX_CONFIG_TOML_ENV,
                build_codex_config_toml(
                    resolved.model_name,
                    resolved.provider,
                    resolved.model_base_url,
                ),
            )
            if should_emit_codex_model_catalog(resolved.provider):
                bundle.add(
                    CODEX_MODEL_CATALOG_JSON_ENV,
                    build_codex_model_catalog_json(
                        resolved.model_name,
                        resolved.provider,
                    ),
                )
    return bundle.to_create_tool_envs()


def build_private_tool_envs(
    *,
    model_name: Optional[str] = None,
    model_api_key: Optional[str] = None,
    model_provider: str | ModelProviderType | None = None,
    model_base_url: Optional[str] = None,
    model_provider_was_provided: Optional[bool] = None,
    model_base_url_was_provided: Optional[bool] = None,
    websearch_apikey: Optional[str] = None,
) -> list[tools_types.EnvsItemForCreateTool]:
    """Build CreateTool.Envs for Private plus CodeEnv-only envs."""

    envs = [
        tools_types.EnvsItemForCreateTool(Key=key, Value=value)
        for key, value in PRIVATE_TOOL_VARS
    ]
    private_tool_keys = {key for key, _value in PRIVATE_TOOL_VARS}
    code_envs = build_create_tool_envs(
        tool_type=DEFAULT_CREATE_TOOL_TYPE,
        model_name=model_name,
        model_api_key=model_api_key,
        model_provider=model_provider,
        model_base_url=model_base_url,
        model_provider_was_provided=model_provider_was_provided,
        model_base_url_was_provided=model_base_url_was_provided,
        websearch_apikey=websearch_apikey,
    )
    for env in code_envs or []:
        if env.key not in private_tool_keys:
            envs.append(env)
    return envs


def build_exec_session_envs(
    *,
    model_name: Optional[str] = None,
    model_api_key: Optional[str] = None,
    model_provider: str | ModelProviderType | None = None,
    model_base_url: Optional[str] = None,
    model_provider_was_provided: Optional[bool] = None,
    model_base_url_was_provided: Optional[bool] = None,
    include_codex_config: bool = False,
    disable_websearch_apikey: bool = False,
) -> list[tools_types.EnvsItemForCreateSession] | None:
    """Build CreateSession.Envs for the exec/shell CodeEnv profile."""

    bundle = EnvBundle()
    resolved = _resolve_sandbox_model_env(
        model_name=model_name,
        model_api_key=model_api_key,
        model_provider=model_provider,
        model_base_url=model_base_url,
        model_provider_was_provided=model_provider_was_provided,
        model_base_url_was_provided=model_base_url_was_provided,
        require_provider=False,
    )
    _append_standard_model_envs(
        bundle,
        resolved,
        include_base_urls=bool(resolved.base_url or resolved.anthropic_base_url),
        include_api_key=False,
    )
    if (
        include_codex_config
        and resolved.model_name
        and should_emit_codex_model_config(
            model_provider=resolved.provider,
            model_base_url=resolved.model_base_url,
        )
    ):
        bundle.add(
            CODEX_CONFIG_TOML_ENV,
            build_codex_config_toml(
                resolved.model_name,
                resolved.provider,
                resolved.model_base_url,
            ),
        )
        if should_emit_codex_model_catalog(resolved.provider):
            bundle.add(
                CODEX_MODEL_CATALOG_JSON_ENV,
                build_codex_model_catalog_json(
                    resolved.model_name,
                    resolved.provider,
                ),
            )
    bundle.add_many(MODEL_API_KEY_ENV_KEYS, resolved.api_key)
    if disable_websearch_apikey:
        bundle.add(WEB_SEARCH_API_KEY_ENV, "", include_empty=True)
    return bundle.to_create_session_envs()


def build_invoke_session_envs(
    *,
    model_name: Optional[str] = None,
    model_provider: Optional[str] = None,
    model_base_url: Optional[str] = None,
    model_api_key: Optional[str] = None,
    openclaw_config_file: Path = OPENCLAW_CONFIG_FILE,
) -> list[tools_types.EnvsItemForCreateSession]:
    """Build CreateSession.Envs for the A2A invoke SkillEnv profile."""

    cli_values = {
        "MODEL_AGENT_API_BASE": (model_base_url or "").strip(),
        "MODEL_AGENT_API_KEY": (model_api_key or "").strip(),
        "MODEL_AGENT_PROVIDER": (model_provider or "").strip(),
        "MODEL_AGENT_NAME": (model_name or "").strip(),
    }
    env_values = _collect_model_agent_envs_from_env()
    openclaw_values = _collect_openclaw_model_agent_envs(openclaw_config_file)

    bundle = EnvBundle()
    for key in MODEL_AGENT_ENV_KEYS:
        include_empty = key in REQUIRED_MODEL_AGENT_ENV_KEYS
        bundle.add(
            key,
            cli_values.get(key) or env_values.get(key) or openclaw_values.get(key),
            include_empty=include_empty,
        )
    return bundle.to_required_create_session_envs()


def _collect_model_agent_envs_from_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for key in MODEL_AGENT_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            values[key] = value
    return values


def _collect_openclaw_model_agent_envs(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}

    primary = _get_nested(data, ("agents", "defaults", "model", "primary"))
    if not isinstance(primary, str):
        return {}

    provider, model_name = _parse_openclaw_primary(primary)
    if not provider or not model_name:
        return {}

    model_config = _find_openclaw_model_config(data, provider, model_name)
    if not model_config:
        return {}

    api_base = _pick_openclaw_text(model_config, OPENCLAW_API_BASE_KEYS)
    api_key = _pick_openclaw_text(model_config, OPENCLAW_API_KEY_KEYS)
    provider_api = _pick_openclaw_text(model_config, OPENCLAW_PROVIDER_API_KEYS)
    if not api_base or not api_key or not provider_api:
        return {}

    litellm_provider, model_agent_name = _resolve_openclaw_provider_api_route(
        provider_api,
        model_name,
    )
    if not litellm_provider or not model_agent_name:
        return {}

    values = {
        "MODEL_AGENT_API_BASE": api_base,
        "MODEL_AGENT_API_KEY": api_key,
        "MODEL_AGENT_PROVIDER": litellm_provider,
        "MODEL_AGENT_NAME": model_agent_name,
    }
    extra_headers = _pick_openclaw_headers_json(model_config)
    if extra_headers:
        values["MODEL_AGENT_EXTRA_HEADERS"] = extra_headers
    return values


def _resolve_openclaw_provider_api_route(
    provider_api: str,
    model_name: str,
) -> tuple[str, str]:
    litellm_provider = OPENCLAW_PROVIDER_API_ROUTES.get(provider_api)
    if not litellm_provider:
        return "", ""
    return litellm_provider, model_name


def _parse_openclaw_primary(primary: str) -> tuple[str, str]:
    provider, separator, model_name = primary.strip().partition("/")
    if not separator:
        return "", ""
    return provider.strip(), model_name.strip()


def _find_openclaw_model_config(
    data: dict[str, Any],
    provider: str,
    model_name: str,
) -> dict[str, Any] | None:
    for path in OPENCLAW_MODEL_CONFIG_ROOTS:
        root = _get_nested(data, path)
        match = _find_openclaw_model_config_in(root, provider, model_name)
        if match:
            return match
    return _find_openclaw_model_config_in(data, provider, model_name)


def _find_openclaw_model_config_in(
    value: Any,
    provider: str,
    model_name: str,
) -> dict[str, Any] | None:
    if isinstance(value, dict):
        direct = _openclaw_direct_model_config(value, provider, model_name)
        if direct:
            return direct

        if _openclaw_model_config_matches(value, provider, model_name):
            return value

        for child in value.values():
            match = _find_openclaw_model_config_in(child, provider, model_name)
            if match:
                return match
    elif isinstance(value, list):
        for item in value:
            match = _find_openclaw_model_config_in(item, provider, model_name)
            if match:
                return match
    return None


def _openclaw_direct_model_config(
    value: dict[str, Any],
    provider: str,
    model_name: str,
) -> dict[str, Any] | None:
    direct_keys = (
        f"{provider}/{model_name}",
        model_name,
    )
    for key in direct_keys:
        candidate = value.get(key)
        if isinstance(candidate, dict):
            return candidate

    provider_config = value.get(provider)
    if isinstance(provider_config, dict):
        candidate = provider_config.get(model_name)
        if isinstance(candidate, dict):
            return _merge_openclaw_model_config(provider_config, candidate)
        if _openclaw_provider_config_has_model(provider_config, model_name):
            model_item = _find_openclaw_model_item(provider_config, model_name)
            return _merge_openclaw_model_config(provider_config, model_item)
    return None


def _merge_openclaw_model_config(
    provider_config: dict[str, Any],
    model_config: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = {key: value for key, value in provider_config.items() if key != "models"}
    if model_config:
        merged.update(model_config)
        provider_headers = _pick_openclaw_headers(provider_config)
        model_headers = _pick_openclaw_headers(model_config)
        if provider_headers or model_headers:
            headers = {}
            headers.update(provider_headers)
            headers.update(model_headers)
            merged["headers"] = headers
    return merged


def _openclaw_provider_config_has_model(
    provider_config: dict[str, Any],
    model_name: str,
) -> bool:
    return _find_openclaw_model_item(provider_config, model_name) is not None


def _find_openclaw_model_item(
    provider_config: dict[str, Any],
    model_name: str,
) -> dict[str, Any] | None:
    models = provider_config.get("models")
    if isinstance(models, dict):
        candidate = models.get(model_name)
        if isinstance(candidate, dict):
            return candidate
        for item in models.values():
            if isinstance(item, dict) and _openclaw_model_config_matches_model_name(
                item, model_name
            ):
                return item
    if isinstance(models, list):
        for item in models:
            if isinstance(item, dict) and _openclaw_model_config_matches_model_name(
                item, model_name
            ):
                return item
    return None


def _openclaw_model_config_matches_model_name(value: Any, model_name: str) -> bool:
    if isinstance(value, str):
        return value == model_name
    if not isinstance(value, dict):
        return False

    name_value = _pick_openclaw_text(
        value,
        ("id", "name", "model", "model_name", "modelName"),
    )
    return name_value == model_name


def _openclaw_model_config_matches(
    value: dict[str, Any],
    provider: str,
    model_name: str,
) -> bool:
    provider_value = _pick_openclaw_text(
        value,
        ("provider", "provider_name", "providerName", "type"),
    )
    name_value = _pick_openclaw_text(
        value,
        ("name", "model", "model_name", "modelName", "id"),
    )
    return provider_value == provider and name_value in {
        model_name,
        f"{provider}/{model_name}",
    }


def _get_nested(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _pick_openclaw_text(value: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def _pick_openclaw_headers_json(value: dict[str, Any]) -> str | None:
    headers = _pick_openclaw_headers(value)
    if not headers:
        return None
    return json.dumps(headers, ensure_ascii=False, sort_keys=True)


def _pick_openclaw_headers(value: dict[str, Any]) -> dict[str, str]:
    for key in OPENCLAW_MODEL_HEADER_KEYS:
        item = value.get(key)
        if not isinstance(item, dict):
            continue
        headers: dict[str, str] = {}
        for header_key, header_value in item.items():
            if (
                isinstance(header_key, str)
                and isinstance(header_value, str)
                and header_key.strip()
                and header_value.strip()
            ):
                headers[header_key.strip()] = header_value.strip()
        if headers:
            return headers
    return {}

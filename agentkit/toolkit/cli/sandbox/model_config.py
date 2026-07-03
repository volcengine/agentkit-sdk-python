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

"""Model and runtime configuration helpers for sandbox CLI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Optional

MODEL_NAME_ENV_KEYS = ("OPENCODE_MODEL", "CODEX_MODEL", "ANTHROPIC_MODEL")
MODEL_API_KEY_ENV_KEYS = (
    "OPENCODE_API_KEY",
    "CODEX_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
)
MODEL_BASE_URL_ENV_KEYS = (
    "OPENCODE_BASE_URL",
    "CODEX_BASE_URL",
    "MODEL_BASE_URL",
)
ANTHROPIC_BASE_URL_ENV_KEYS = ("ANTHROPIC_BASE_URL",)
MODEL_API_KEY_ENV = "MODEL_API_KEY"
MODEL_PROVIDER_ENV = "AGENTKIT_SANDBOX_MODEL_PROVIDER"

CODE_ENV_HOME = "/home/gem"
CODE_ENV_CODEX_HOME = "/home/gem/.codex"
CODEX_CONFIG_TOML_ENV = "CODEX_CONFIG_TOML"
CODEX_MODEL_CATALOG_JSON_ENV = "CODEX_MODEL_CATALOG_JSON"
CODEX_MODEL_CATALOG_PATH = f"{CODE_ENV_CODEX_HOME}/model-catalog.json"
CODEX_RESERVED_MODEL_PROVIDER_IDS = {"openai"}


class ModelProviderType(str, Enum):
    MODEL_SQUARE = "model_square"
    CODING_PLAN = "coding_plan"
    AGENT_PLAN = "agent_plan"


@dataclass(frozen=True)
class ModelSpec:
    supports_reasoning_summaries: bool
    context_window: int


@dataclass(frozen=True)
class ModelProviderConfig:
    model_base_url: str
    anthropic_base_url: str
    default_model_name: str
    models: dict[str, ModelSpec]


DEFAULT_MODEL_CONTEXT_WINDOW = 1000000
LIMITED_MODEL_CONTEXT_WINDOW = 200000
DEFAULT_MODEL_PROVIDER = ModelProviderType.MODEL_SQUARE.value

MODEL_PROVIDER_CONFIGS: dict[str, ModelProviderConfig] = {
    ModelProviderType.MODEL_SQUARE.value: ModelProviderConfig(
        model_base_url="https://ark.cn-beijing.volces.com/api/v3",
        anthropic_base_url="https://ark.cn-beijing.volces.com/api/compatible",
        default_model_name="deepseek-v4-flash-260425",
        models={
            "doubao-seed-2-0-pro-260215": ModelSpec(
                supports_reasoning_summaries=True,
                context_window=LIMITED_MODEL_CONTEXT_WINDOW,
            ),
            "deepseek-v4-flash-260425": ModelSpec(
                supports_reasoning_summaries=True,
                context_window=DEFAULT_MODEL_CONTEXT_WINDOW,
            ),
            "deepseek-v4-pro-260425": ModelSpec(
                supports_reasoning_summaries=True,
                context_window=DEFAULT_MODEL_CONTEXT_WINDOW,
            ),
        },
    ),
    ModelProviderType.CODING_PLAN.value: ModelProviderConfig(
        model_base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
        anthropic_base_url="https://ark.cn-beijing.volces.com/api/coding",
        default_model_name="deepseek-v4-flash",
        models={
            "doubao-seed-2.0-pro": ModelSpec(
                supports_reasoning_summaries=True,
                context_window=LIMITED_MODEL_CONTEXT_WINDOW,
            ),
            "deepseek-v4-flash": ModelSpec(
                supports_reasoning_summaries=True,
                context_window=DEFAULT_MODEL_CONTEXT_WINDOW,
            ),
            "deepseek-v4-pro": ModelSpec(
                supports_reasoning_summaries=True,
                context_window=DEFAULT_MODEL_CONTEXT_WINDOW,
            ),
        },
    ),
    ModelProviderType.AGENT_PLAN.value: ModelProviderConfig(
        model_base_url="https://ark.cn-beijing.volces.com/api/plan/v3",
        anthropic_base_url="https://ark.cn-beijing.volces.com/api/plan",
        default_model_name="deepseek-v4-flash",
        models={
            "doubao-seed-2.0-pro": ModelSpec(
                supports_reasoning_summaries=True,
                context_window=LIMITED_MODEL_CONTEXT_WINDOW,
            ),
            "deepseek-v4-flash": ModelSpec(
                supports_reasoning_summaries=True,
                context_window=DEFAULT_MODEL_CONTEXT_WINDOW,
            ),
            "deepseek-v4-pro": ModelSpec(
                supports_reasoning_summaries=True,
                context_window=DEFAULT_MODEL_CONTEXT_WINDOW,
            ),
        },
    ),
}

DEFAULT_MODEL_NAME = MODEL_PROVIDER_CONFIGS[DEFAULT_MODEL_PROVIDER].default_model_name
DEFAULT_MODEL_NAME_LIST = tuple(
    dict.fromkeys(
        (
            DEFAULT_MODEL_NAME,
            *MODEL_PROVIDER_CONFIGS[DEFAULT_MODEL_PROVIDER].models,
        )
    )
)
DEFAULT_MODEL_BASE_URL = MODEL_PROVIDER_CONFIGS[DEFAULT_MODEL_PROVIDER].model_base_url
DEFAULT_ANTHROPIC_BASE_URL = MODEL_PROVIDER_CONFIGS[
    DEFAULT_MODEL_PROVIDER
].anthropic_base_url
BUILTIN_MODEL_BASE_URL_PROVIDERS = {
    config.model_base_url: provider
    for provider, config in MODEL_PROVIDER_CONFIGS.items()
}
BUILTIN_MODEL_BASE_URLS = tuple(
    BUILTIN_MODEL_BASE_URL_PROVIDERS,
)


def _model_provider_value(
    model_provider: str | ModelProviderType | None,
) -> Optional[str]:
    if isinstance(model_provider, ModelProviderType):
        return model_provider.value
    return model_provider


def normalize_model_provider(
    model_provider: str | ModelProviderType | None,
) -> str:
    resolved = (_model_provider_value(model_provider) or DEFAULT_MODEL_PROVIDER).strip()
    return resolved


def normalize_optional_model_provider(
    model_provider: str | ModelProviderType | None,
) -> str | None:
    resolved = (_model_provider_value(model_provider) or "").strip()
    return resolved or None


def normalize_model_base_url(model_base_url: Optional[str]) -> str | None:
    resolved = (model_base_url or "").strip()
    return resolved or None


def is_builtin_model_base_url(model_base_url: Optional[str]) -> bool:
    resolved = normalize_model_base_url(model_base_url)
    return bool(resolved and resolved in BUILTIN_MODEL_BASE_URLS)


def infer_model_provider_from_base_url(model_base_url: Optional[str]) -> str | None:
    resolved = normalize_model_base_url(model_base_url)
    if not resolved:
        return None
    return BUILTIN_MODEL_BASE_URL_PROVIDERS.get(resolved)


def validate_model_provider_base_url(
    *,
    model_provider: str | ModelProviderType | None,
    model_base_url: Optional[str],
    model_provider_was_provided: Optional[bool] = None,
    model_base_url_was_provided: Optional[bool] = None,
) -> None:
    resolved_model_provider = normalize_optional_model_provider(model_provider)
    resolved_model_base_url = normalize_model_base_url(model_base_url)
    provider_was_provided = (
        bool(resolved_model_provider)
        if model_provider_was_provided is None
        else model_provider_was_provided
    )
    base_url_was_provided = (
        bool(resolved_model_base_url)
        if model_base_url_was_provided is None
        else model_base_url_was_provided
    )

    if (
        base_url_was_provided
        and resolved_model_base_url
        and not is_builtin_model_base_url(resolved_model_base_url)
        and not provider_was_provided
    ):
        raise ValueError(
            "--model-base-url requires --model-provider for non-Ark base URLs"
        )


def get_model_provider_config_if_known(
    model_provider: str | ModelProviderType | None,
) -> ModelProviderConfig | None:
    return MODEL_PROVIDER_CONFIGS.get(normalize_model_provider(model_provider))


def get_model_provider_config(
    model_provider: str | ModelProviderType | None,
) -> ModelProviderConfig:
    resolved_provider = normalize_model_provider(model_provider)
    config = MODEL_PROVIDER_CONFIGS.get(resolved_provider)
    if config is None:
        raise ValueError(
            f"--model-provider has no built-in configuration: {resolved_provider}"
        )
    return config


def model_provider_from_env_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    resolved = value.strip()
    if not resolved:
        return None
    return resolved


def resolve_model_name(
    model_name: Optional[str],
    model_provider: str | ModelProviderType | None,
) -> str:
    resolved_provider = normalize_model_provider(model_provider)
    config = MODEL_PROVIDER_CONFIGS.get(resolved_provider)
    resolved_model_name = (model_name or "").strip()
    if resolved_model_name:
        return resolved_model_name
    if config:
        return config.default_model_name
    return DEFAULT_MODEL_NAME


def resolve_model_base_urls(
    *,
    model_provider: str | ModelProviderType | None,
    model_base_url: Optional[str] = None,
) -> tuple[str | None, str | None]:
    resolved_model_base_url = normalize_model_base_url(model_base_url)
    if resolved_model_base_url:
        return resolved_model_base_url, resolved_model_base_url

    config = get_model_provider_config_if_known(model_provider)
    if not config:
        return None, None
    return config.model_base_url, config.anthropic_base_url


def should_emit_codex_model_config(
    *,
    model_provider: str | ModelProviderType | None,
    model_base_url: Optional[str] = None,
) -> bool:
    return True


def should_emit_codex_model_catalog(
    model_provider: str | ModelProviderType | None,
) -> bool:
    resolved_provider = normalize_model_provider(model_provider)
    return resolved_provider in MODEL_PROVIDER_CONFIGS


def codex_model_provider_id(
    model_provider: str | ModelProviderType | None,
) -> str:
    resolved_provider = normalize_model_provider(model_provider)
    if resolved_provider in MODEL_PROVIDER_CONFIGS:
        return resolved_provider
    if resolved_provider in CODEX_RESERVED_MODEL_PROVIDER_IDS:
        return f"{resolved_provider}-custom"
    return resolved_provider


def _toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_codex_config_toml(
    model_name: str,
    model_provider: str | ModelProviderType | None = None,
    model_base_url: Optional[str] = None,
) -> str:
    resolved_provider = normalize_model_provider(model_provider)
    config = get_model_provider_config_if_known(resolved_provider)
    resolved_model_base_url = normalize_model_base_url(model_base_url)
    provider_base_url = resolved_model_base_url or (
        config.model_base_url
        if config
        else MODEL_PROVIDER_CONFIGS[DEFAULT_MODEL_PROVIDER].model_base_url
    )
    resolved_model_name = resolve_model_name(model_name, resolved_provider)
    resolved_codex_provider = codex_model_provider_id(resolved_provider)
    quoted_model = _toml_quote(resolved_model_name)
    lines = [
        f"model_provider = {_toml_quote(resolved_codex_provider)}",
        f"model = {quoted_model}",
        f"review_model = {quoted_model}",
        'approval_policy = "never"',
        'sandbox_mode = "danger-full-access"',
        'model_reasoning_effort = "medium"',
        'personality = "pragmatic"',
        "check_for_update_on_startup = false",
        'web_search = "disabled"',
    ]
    if should_emit_codex_model_catalog(resolved_provider):
        lines.append(f"model_catalog_json = {_toml_quote(CODEX_MODEL_CATALOG_PATH)}")
    lines.extend(
        [
            'developer_instructions = """',
            (
                "When the user asks for simple browser operation tasks, "
                "you can use xdg-open to complete them."
            ),
            '"""',
            "",
            f"[model_providers.{resolved_codex_provider}]",
            f"name = {_toml_quote(resolved_codex_provider)}",
            f"base_url = {_toml_quote(provider_base_url)}",
            'wire_api = "responses"',
            'env_key = "CODEX_API_KEY"',
            "",
            "[tui]",
            "show_tooltips = false",
            "",
            '[projects."/home/gem"]',
            'trust_level = "trusted"',
            "",
            "[mcp_servers.browser-use]",
            'url = "http://localhost:8100/mcp"',
            "",
        ]
    )
    return "\n".join(lines)


def _reasoning_levels() -> list[dict[str, str]]:
    return [
        {
            "effort": "low",
            "description": "Fast responses with lighter reasoning",
        },
        {
            "effort": "medium",
            "description": "Balances speed and reasoning depth",
        },
        {
            "effort": "high",
            "description": "Greater reasoning depth",
        },
    ]


def _build_model_catalog_item(model_name: str, spec: ModelSpec) -> dict:
    return {
        "slug": model_name,
        "display_name": model_name,
        "supported_reasoning_levels": _reasoning_levels(),
        "max_context_window": spec.context_window,
        "shell_type": "shell_command",
        "visibility": "list",
        "supported_in_api": True,
        "priority": 100,
        "base_instructions": "",
        "supports_reasoning_summaries": spec.supports_reasoning_summaries,
        "support_verbosity": False,
        "truncation_policy": {"mode": "tokens", "limit": 10000},
        "supports_parallel_tool_calls": False,
        "experimental_supported_tools": [],
    }


def infer_model_spec(model_name: str) -> ModelSpec:
    normalized_model_name = model_name.strip().lower()
    if normalized_model_name == "glm-5.2" or normalized_model_name.startswith(
        "deepseek-v4"
    ):
        context_window = DEFAULT_MODEL_CONTEXT_WINDOW
    else:
        context_window = LIMITED_MODEL_CONTEXT_WINDOW

    return ModelSpec(
        supports_reasoning_summaries=True,
        context_window=context_window,
    )


def model_catalog_context_window(
    model_name: str,
    model_provider: str | ModelProviderType | None = None,
) -> int:
    config = get_model_provider_config_if_known(model_provider)
    spec = config.models.get(model_name) if config else None
    if spec:
        return spec.context_window
    return infer_model_spec(model_name).context_window


def build_codex_model_catalog_json(
    model_name: str,
    model_provider: str | ModelProviderType | None = None,
) -> str:
    resolved_provider = normalize_model_provider(model_provider)
    config = get_model_provider_config(resolved_provider)
    resolved_model_name = resolve_model_name(model_name, resolved_provider)
    deduped_model_names = list(dict.fromkeys((resolved_model_name, *config.models)))
    payload = {
        "models": [
            _build_model_catalog_item(
                name,
                config.models.get(name) or infer_model_spec(name),
            )
            for name in deduped_model_names
        ]
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

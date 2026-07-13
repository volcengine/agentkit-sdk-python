"""Target model replacement helpers for migrated AgentKit apps."""

from __future__ import annotations

import importlib
import logging
import os
from typing import Any


logger = logging.getLogger(__name__)
ARK_DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
_DISABLED_VALUES = {"0", "false", "off", "none", "disabled"}
_MODEL_PARAM_KEYS = {
    "frequency_penalty",
    "max_tokens",
    "presence_penalty",
    "stop",
    "temperature",
    "top_p",
}
_MODEL_ID_ALIAS_ENV_KEYS = (
    "BEDROCK_MODEL_ID",
    "DEFAULT_MODEL",
    "MODEL_ID",
    "MODEL_NAME",
)
_BASE_URL_ALIAS_ENV_KEYS = (
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE",
)
_API_KEY_ALIAS_ENV_KEYS = ("OPENAI_API_KEY",)


def _target_model_id() -> str:
    return os.getenv("ARK_MODEL_ID") or ""


def _target_api_key() -> str:
    return os.getenv("ARK_API_KEY") or ""


def _target_base_url() -> str:
    return os.getenv("ARK_BASE_URL") or ARK_DEFAULT_BASE_URL


def _replacement_enabled() -> bool:
    value = os.getenv("ARK_MODEL_REPLACEMENT", "ark").strip().lower()
    return value not in _DISABLED_VALUES


def _replacement_model_config(config: dict[str, Any]) -> dict[str, Any]:
    model_id = _target_model_id()
    if not model_id:
        raise RuntimeError(
            "AgentKit model replacement is enabled, but no target model was "
            "configured. Set ARK_MODEL_ID."
        )

    params = dict(config.get("params") or {})
    for key in _MODEL_PARAM_KEYS:
        if key in config and config[key] is not None:
            params.setdefault(key, config[key])

    replacement: dict[str, Any] = {"model_id": model_id}
    if params:
        replacement["params"] = params
    if "context_window_limit" in config:
        replacement["context_window_limit"] = config["context_window_limit"]
    if "stream" in config:
        replacement["stream"] = config["stream"]
    return replacement


def _agentkit_openai_model_cls() -> type[Any]:
    from strands.models.openai import OpenAIModel

    class AgentKitOpenAIModel(OpenAIModel):
        """OpenAI-compatible Strands model backed by the AgentKit target model."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            del args
            api_key = _target_api_key()
            if not api_key:
                raise RuntimeError(
                    "AgentKit model replacement is enabled, but no API key was "
                    "configured. Set ARK_API_KEY."
                )
            super().__init__(
                client_args={
                    "base_url": _target_base_url(),
                    "api_key": api_key,
                },
                **_replacement_model_config(kwargs),
            )

    AgentKitOpenAIModel.__name__ = "AgentKitOpenAIModel"
    return AgentKitOpenAIModel


def _patch_model_attr(module_name: str, attr: str, replacement: type[Any]) -> bool:
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return False
    if hasattr(module, attr):
        setattr(module, attr, replacement)
        return True
    return False


def _apply_env_aliases() -> bool:
    changed = False
    model_id = _target_model_id()
    if not model_id:
        return False

    for key in _MODEL_ID_ALIAS_ENV_KEYS:
        if key not in os.environ:
            os.environ[key] = model_id
            changed = True

    base_url = _target_base_url()
    for key in _BASE_URL_ALIAS_ENV_KEYS:
        if key not in os.environ:
            os.environ[key] = base_url
            changed = True

    api_key = _target_api_key()
    if api_key:
        for key in _API_KEY_ALIAS_ENV_KEYS:
            if key not in os.environ:
                os.environ[key] = api_key
                changed = True
    return changed


def _patch_strands_model_classes() -> bool:
    try:
        replacement = _agentkit_openai_model_cls()
    except Exception:
        return False

    patched = False
    for module_name, attr in (
        ("strands.models", "BedrockModel"),
        ("strands.models.bedrock", "BedrockModel"),
        ("strands.models.anthropic", "AnthropicModel"),
    ):
        patched = _patch_model_attr(module_name, attr, replacement) or patched
    return patched


def apply_agentkit_model_replacement() -> bool:
    """Apply explicit target-model replacement for generated migration wrappers.

    The helper intentionally stays low-intrusion: it normalizes common model
    environment variables and patches only stable Strands Bedrock/Anthropic
    model classes before user code constructs them. It does not rewrite project
    source code or chase framework-specific model SDK constructor details.
    """

    if not _replacement_enabled():
        logger.info("AgentKit model replacement disabled by ARK_MODEL_REPLACEMENT.")
        return False
    env_changed = _apply_env_aliases()
    patched = _patch_strands_model_classes()
    logger.info(
        "AgentKit model replacement enabled: env_aliases=%s strands_model_patch=%s target_model_configured=%s base_url_configured=%s",
        env_changed,
        patched,
        bool(_target_model_id()),
        bool(_target_base_url()),
    )
    return env_changed or patched

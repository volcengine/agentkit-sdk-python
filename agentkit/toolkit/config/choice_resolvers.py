from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class ResolvedChoices:
    """Resolved choice list and input policy for a field.

    This structure is intentionally JSON/YAML-friendly (only primitives, list, dict).
    """

    choices: List[Dict[str, str]]
    allow_free_input: bool = False
    validate_against_choices: bool = True
    default_value: Optional[str] = None


ChoiceResolver = Callable[
    [
        str,
        Dict[str, Any],
        Optional[Dict[str, Any]],
        Optional[type],
        Optional[Dict[str, Any]],
    ],
    ResolvedChoices,
]


def _values_from_choices(choices: Sequence[Dict[str, str]]) -> List[str]:
    values: List[str] = []
    for c in choices:
        if isinstance(c, dict) and "value" in c:
            values.append(str(c["value"]))
    return values


def resolve_field_choices(
    field_name: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
    current_config: Optional[Dict[str, Any]] = None,
    dataclass_type: Optional[type] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[ResolvedChoices]:
    """Resolve dynamic choices for a field based on metadata.

    The metadata is expected to be JSON/YAML-friendly.
    If no resolver is configured, returns None.
    """

    metadata = metadata or {}
    resolver_id = metadata.get("choices_resolver")
    if not resolver_id:
        return None
    if not isinstance(resolver_id, str):
        return None

    resolver = CHOICE_RESOLVERS.get(resolver_id)
    if resolver is None:
        return None

    try:
        resolved = resolver(
            field_name, metadata, current_config, dataclass_type, context
        )
    except Exception:
        # Resolver failure should never break config flows.
        # Fallback to free input with no validation.
        return ResolvedChoices(
            choices=[],
            allow_free_input=True,
            validate_against_choices=False,
            default_value=None,
        )

    # Normalize choice list shape defensively.
    if resolved.choices is None:
        return ResolvedChoices(
            choices=[],
            allow_free_input=True,
            validate_against_choices=False,
            default_value=resolved.default_value,
        )

    return resolved


def region_by_cloud_provider(
    field_name: str,
    metadata: Dict[str, Any],
    current_config: Optional[Dict[str, Any]],
    dataclass_type: Optional[type],
    context: Optional[Dict[str, Any]],
) -> ResolvedChoices:
    """Resolve region choices based on the active cloud provider.

    Provider resolution precedence is:
    - process env (AGENTKIT_CLOUD_PROVIDER / CLOUD_PROVIDER)
    - global config defaults.cloud_provider
    - fallback: volcengine
    """

    # Global escape hatch: allow free input when strict restrictions are disabled.
    try:
        from agentkit.toolkit.config.global_config import get_global_config

        gc = get_global_config()
        if bool(getattr(gc.defaults, "disable_region_strict_restrictions", False)):
            return ResolvedChoices(
                choices=[],
                allow_free_input=True,
                validate_against_choices=False,
                default_value=None,
            )
    except Exception:
        pass

    provider = None
    if isinstance(context, dict):
        try:
            from agentkit.platform.provider import normalize_cloud_provider

            provider = normalize_cloud_provider(context.get("cloud_provider"))
        except Exception:
            provider = None

    try:
        from agentkit.platform.provider import (
            normalize_cloud_provider,
            read_cloud_provider_from_env,
        )

        if provider is None:
            provider = normalize_cloud_provider(read_cloud_provider_from_env())
    except Exception:
        pass

    if provider is None:
        try:
            from agentkit.toolkit.config.global_config import get_global_config
            from agentkit.platform.provider import normalize_cloud_provider

            gc = get_global_config()
            provider = normalize_cloud_provider(
                getattr(gc.defaults, "cloud_provider", None)
            )
        except Exception:
            provider = None

    provider_value = provider.value if provider is not None else "volcengine"

    if provider_value == "byteplus":
        choices = [
            {"value": "ap-southeast-1", "description": "AP Southeast 1"},
        ]
        return ResolvedChoices(
            choices=choices,
            allow_free_input=False,
            validate_against_choices=True,
            default_value="ap-southeast-1",
        )

    # Default: Volcano Engine (CN)
    choices = [
        {"value": "cn-beijing", "description": "Beijing"},
        {"value": "cn-shanghai", "description": "Shanghai"},
    ]
    return ResolvedChoices(
        choices=choices,
        allow_free_input=False,
        validate_against_choices=True,
        default_value="cn-beijing",
    )


CHOICE_RESOLVERS: Dict[str, ChoiceResolver] = {
    "region_by_cloud_provider": region_by_cloud_provider,
}


__all__ = [
    "ResolvedChoices",
    "resolve_field_choices",
    "CHOICE_RESOLVERS",
]

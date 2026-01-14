from __future__ import annotations

from enum import Enum
from typing import Optional


class CloudProvider(str, Enum):
    """Cloud provider identifier.

    This is used to isolate region defaults, endpoint registry, and credential
    resolution between Volcano Engine (CN) and BytePlus (Overseas).
    """

    VOLCENGINE = "volcengine"
    BYTEPLUS = "byteplus"


ENV_CLOUD_PROVIDER = "AGENTKIT_CLOUD_PROVIDER"
ENV_CLOUD_PROVIDER_ALIAS = "CLOUD_PROVIDER"


def read_cloud_provider_from_env() -> Optional[str]:
    """Read provider setting from environment variables.

    Precedence:
    1) AGENTKIT_CLOUD_PROVIDER (preferred)
    2) CLOUD_PROVIDER (compat alias)
    """

    import os

    return os.getenv(ENV_CLOUD_PROVIDER) or os.getenv(ENV_CLOUD_PROVIDER_ALIAS)


def normalize_cloud_provider(value: Optional[str]) -> Optional[CloudProvider]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if not v:
        return None
    try:
        return CloudProvider(v)
    except Exception:
        return None


def resolve_cloud_provider(
    *,
    explicit_provider: Optional[str] = None,
    env_provider: Optional[str] = None,
    config_provider: Optional[str] = None,
    default: CloudProvider = CloudProvider.VOLCENGINE,
) -> CloudProvider:
    """Resolve provider with precedence: explicit > env > config > default."""
    return (
        normalize_cloud_provider(explicit_provider)
        or normalize_cloud_provider(env_provider)
        or normalize_cloud_provider(config_provider)
        or default
    )

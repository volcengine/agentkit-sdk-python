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

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict

from agentkit.platform.constants import (
    DEFAULT_REGION,
    SERVICE_METADATA,
    ServiceMeta,
    SERVICE_METADATA_BY_PROVIDER,
    DEFAULT_REGION_BY_PROVIDER,
    DEFAULT_REGION_RULES_BY_PROVIDER,
)
from agentkit.platform.provider import (
    CloudProvider,
    normalize_cloud_provider,
    read_cloud_provider_from_env,
)
from agentkit.utils.global_config_io import (
    get_global_config_str,
    get_global_config_value,
    read_global_config_dict,
)
from agentkit.utils.logging_config import get_logger

logger = get_logger(__name__)

VEFAAS_IAM_CREDENTIAL_PATH = "/var/run/secrets/iam/credential"
VEFAAS_IAM_CREDENTIAL_FALLBACK_TTL_SECONDS = 60
VEFAAS_IAM_CREDENTIAL_MIN_VALIDITY_SECONDS = 60


@dataclass
class Endpoint:
    host: str
    region: str
    scheme: str
    service: str
    api_version: str


@dataclass
class Credentials:
    access_key: str
    secret_key: str
    session_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    source: Optional[str] = None

    def __repr__(self) -> str:
        masked_sk = "*" * 6
        if self.secret_key and len(self.secret_key) > 4:
            masked_sk = "*" * (len(self.secret_key) - 4) + self.secret_key[-4:]

        return (
            f"Credentials(access_key='{self.access_key}', "
            f"secret_key='{masked_sk}', "
            f"session_token={'***' if self.session_token else 'None'}, "
            f"expires_at={self.expires_at.isoformat() if self.expires_at else 'None'}, "
            f"source={self.source or 'None'})"
        )


class VolcConfiguration:
    """
    Centralized configuration manager for Volcengine services.
    Handles resolution of Region, Credentials, and Endpoints from multiple sources.
    """

    def __init__(
        self,
        region: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        session_token: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        self._region = region
        self._ak = access_key
        self._sk = secret_key
        self._token = session_token
        # Resolve cloud provider at construction time.
        try:
            from agentkit.platform.context import get_default_cloud_provider

            context_provider = get_default_cloud_provider()
        except Exception:
            context_provider = None
        env_provider = read_cloud_provider_from_env()
        try:
            global_dict = read_global_config_dict()
            cfg_provider = (
                (global_dict.get("defaults") or {}).get("cloud_provider")
                if isinstance(global_dict, dict)
                else None
            )
        except Exception:
            cfg_provider = None

        self._provider = (
            normalize_cloud_provider(provider)
            or context_provider
            or normalize_cloud_provider(env_provider)
            or normalize_cloud_provider(cfg_provider)
            or CloudProvider.VOLCENGINE
        )
        self._vefaas_cache_mtime_ns: Optional[int] = None
        self._vefaas_cache_loaded_at_monotonic: Optional[float] = None
        self._vefaas_cache_credentials: Optional[Credentials] = None
        self._vefaas_lock = threading.Lock()

    def get_vefaas_iam_credentials(
        self, *, force: bool = False
    ) -> Optional[Credentials]:
        return self._get_credential_from_vefaas_iam(force=force)

    @property
    def provider(self) -> CloudProvider:
        return self._provider

    @property
    def region(self) -> str:
        """
        Resolves the current region.
        Priority:
        1. Explicitly passed in constructor
        2. Environment variable (VOLCENGINE_REGION / VOLC_REGION)
        3. Global config file (~/.agentkit/config.yaml)
        4. Default (cn-beijing)
        """
        if self._region:
            return self._region

        if self._provider == CloudProvider.BYTEPLUS:
            base_region = (
                os.getenv("BYTEPLUS_REGION")
                or get_global_config_str("byteplus", "region")
                or get_global_config_str("region")
            )
        else:
            base_region = (
                os.getenv("VOLCENGINE_REGION")
                or os.getenv("VOLC_REGION")
                or get_global_config_str("region")
                or get_global_config_str("volcengine", "region")
            )

        if base_region:
            return base_region

        # Fallback to provider-specific default region
        return DEFAULT_REGION_BY_PROVIDER.get(self._provider, DEFAULT_REGION)

    def get_service_endpoint(self, service_key: str) -> Endpoint:
        """
        Resolves the endpoint for a specific service.
        """
        key_lower = service_key.lower()
        provider_registry: Dict[str, ServiceMeta] = SERVICE_METADATA_BY_PROVIDER.get(
            self._provider, SERVICE_METADATA
        )
        meta = provider_registry.get(key_lower)
        if not meta:
            # Fallback for unknown services if needed, or raise error
            # For strictness, we raise error as in original design
            raise ValueError(
                f"Unsupported service for endpoint resolution: {service_key}"
            )

        env_host = self._get_service_override(service_key, "host")
        env_scheme = self._get_service_override(service_key, "scheme")
        env_version = self._get_service_override(service_key, "api_version")
        env_service_code = self._get_service_override(service_key, "service")

        svc_region = self._resolve_service_region(service_key)

        host = env_host or meta.host_template.format(region=svc_region)
        scheme = env_scheme or meta.scheme
        api_version = env_version or meta.default_version
        service_code = env_service_code or meta.code

        return Endpoint(
            host=host,
            region=svc_region,
            scheme=scheme,
            service=service_code,
            api_version=api_version,
        )

    def get_service_credentials(self, service_key: str) -> Credentials:
        """
        Resolves credentials for a specific service.
        Priority:
        1. Explicit (Instance level)
        2. Service-specific Env Vars
        3. Global Env Vars
        4. Global Config File
        5. VeFaaS IAM
        6. .env file in current working directory (fallback)
        """
        # 1. Explicit
        if self._ak and self._sk:
            creds = Credentials(
                access_key=self._ak,
                secret_key=self._sk,
                session_token=self._token,
                source="explicit",
            )
            return creds

        # 2. Service-specific Environment Variables
        if creds := self._get_service_env_credentials(service_key):
            return creds

        # 3. Global Environment Variables
        if creds := self._get_global_env_credentials():
            return creds

        # 4. SSO session (STS credentials from `agentkit login`).
        # Placed above the config file so an *active* login takes precedence over a
        # *passive* saved key; an AK/SK exported in this shell (steps 2-3) still wins,
        # and `agentkit logout` removes the session to fall back to the config file.
        if creds := self._get_sso_credentials():
            return creds

        # 5. Global Config File
        if creds := self._get_config_file_credentials():
            return creds

        # 6. VeFaaS IAM (Runtime)
        if creds := self._get_credential_from_vefaas_iam():
            return creds

        # 6. .env file fallback (Current Working Directory)
        if creds := self._get_dotenv_credentials(service_key):
            return creds

        if self._provider == CloudProvider.BYTEPLUS:
            raise ValueError(
                f"BytePlus credentials not found (Service: {service_key}). Please set environment variables BYTEPLUS_ACCESS_KEY and "
                "BYTEPLUS_SECRET_KEY, or configure ~/.agentkit/config.yaml under byteplus.access_key/byteplus.secret_key."
            )

        raise ValueError(
            "\n".join(
                [
                    f"Volcengine credentials not found (Service: {service_key}).",
                    "Recommended (global, set once):",
                    "  agentkit config --global --set volcengine.access_key=YOUR_ACCESS_KEY",
                    "  agentkit config --global --set volcengine.secret_key=YOUR_SECRET_KEY",
                    "Alternative (per-shell):",
                    "  export VOLCENGINE_ACCESS_KEY=YOUR_ACCESS_KEY",
                    "  export VOLCENGINE_SECRET_KEY=YOUR_SECRET_KEY",
                ]
            )
        )

    def _get_sso_credentials(self) -> Optional[Credentials]:
        """Resolve STS credentials from a stored SSO session (`agentkit login`).

        Decoupled by design: :mod:`agentkit.auth` is imported lazily so the SDK
        keeps working even if the auth library is absent, and BytePlus (which has
        no SSO path here) is skipped.
        """
        if self._provider == CloudProvider.BYTEPLUS:
            return None
        try:
            from agentkit.auth.providers import SsoStsCredentialProvider
        except Exception:
            return None
        try:
            profile = os.getenv("AGENTKIT_AUTH_PROFILE") or None
            resolved = SsoStsCredentialProvider(profile).resolve()
        except Exception:
            return None
        if resolved is None:
            return None
        return Credentials(
            access_key=resolved.access_key,
            secret_key=resolved.secret_key,
            session_token=resolved.session_token,
            source="sso-sts",
        )

    def _get_dotenv_credentials(self, service_key: str) -> Optional[Credentials]:
        """Attempt to read credentials from a local .env file.

        This is a last-resort fallback for CLI users who commonly expect `.env` in the
        current working directory to provide environment variables.

        Notes:
        - Reads only `Path.cwd() / '.env'`.
        - Does NOT mutate the current process environment.
        """

        try:
            from dotenv import dotenv_values
        except Exception:
            return None

        env_file_path = Path.cwd() / ".env"

        try:
            values = dotenv_values(env_file_path)
        except Exception:
            return None

        if not isinstance(values, dict):
            return None

        def _get(key: str) -> str:
            v = values.get(key)
            return str(v) if v is not None else ""

        svc_upper = service_key.upper()

        if self._provider == CloudProvider.BYTEPLUS:
            ak = _get(f"BYTEPLUS_{svc_upper}_ACCESS_KEY")
            sk = _get(f"BYTEPLUS_{svc_upper}_SECRET_KEY")
            token = _get(f"BYTEPLUS_{svc_upper}_SESSION_TOKEN")
        else:
            # Service-specific keys (align with environment variable behavior)
            ak = _get(f"VOLCENGINE_{svc_upper}_ACCESS_KEY")
            sk = _get(f"VOLCENGINE_{svc_upper}_SECRET_KEY")
            token = _get(f"VOLCENGINE_{svc_upper}_SESSION_TOKEN")
            if not ak or not sk:
                # Legacy support
                ak = ak or _get(f"VOLC_{svc_upper}_ACCESSKEY")
                sk = sk or _get(f"VOLC_{svc_upper}_SECRETKEY")

        if ak and sk:
            return Credentials(
                access_key=ak,
                secret_key=sk,
                session_token=token or None,
                source="dotenv",
            )

        # Global keys
        if self._provider == CloudProvider.BYTEPLUS:
            ak = _get("BYTEPLUS_ACCESS_KEY")
            sk = _get("BYTEPLUS_SECRET_KEY")
            token = _get("BYTEPLUS_SESSION_TOKEN")
        else:
            ak = _get("VOLCENGINE_ACCESS_KEY") or _get("VOLC_ACCESSKEY")
            sk = _get("VOLCENGINE_SECRET_KEY") or _get("VOLC_SECRETKEY")
            token = _get("VOLCENGINE_SESSION_TOKEN") or _get("VOLC_SESSIONTOKEN")

        if ak and sk:
            return Credentials(
                access_key=ak,
                secret_key=sk,
                session_token=token or None,
                source="dotenv",
            )

        return None

    def _get_service_env_credentials(self, service_key: str) -> Optional[Credentials]:
        svc_upper = service_key.upper()
        if self._provider == CloudProvider.BYTEPLUS:
            ak = os.getenv(f"BYTEPLUS_{svc_upper}_ACCESS_KEY")
            sk = os.getenv(f"BYTEPLUS_{svc_upper}_SECRET_KEY")
            token = os.getenv(f"BYTEPLUS_{svc_upper}_SESSION_TOKEN")
        else:
            ak = os.getenv(f"VOLCENGINE_{svc_upper}_ACCESS_KEY")
            sk = os.getenv(f"VOLCENGINE_{svc_upper}_SECRET_KEY")
            token = os.getenv(f"VOLCENGINE_{svc_upper}_SESSION_TOKEN")

            if not ak or not sk:
                # Legacy support
                ak = ak or os.getenv(f"VOLC_{svc_upper}_ACCESSKEY")
                sk = sk or os.getenv(f"VOLC_{svc_upper}_SECRETKEY")

        if ak and sk:
            return Credentials(
                access_key=ak,
                secret_key=sk,
                session_token=token or None,
                source="service_env",
            )
        return None

    def _get_global_env_credentials(self) -> Optional[Credentials]:
        if self._provider == CloudProvider.BYTEPLUS:
            ak = os.getenv("BYTEPLUS_ACCESS_KEY")
            sk = os.getenv("BYTEPLUS_SECRET_KEY")
            token = os.getenv("BYTEPLUS_SESSION_TOKEN")
        else:
            ak = os.getenv("VOLCENGINE_ACCESS_KEY") or os.getenv("VOLC_ACCESSKEY")
            sk = os.getenv("VOLCENGINE_SECRET_KEY") or os.getenv("VOLC_SECRETKEY")
            token = os.getenv("VOLCENGINE_SESSION_TOKEN") or os.getenv("VOLC_SESSIONTOKEN")

        if ak and sk:
            return Credentials(
                access_key=ak,
                secret_key=sk,
                session_token=token or None,
                source="global_env",
            )
        return None

    def _get_config_file_credentials(self) -> Optional[Credentials]:
        if self._provider == CloudProvider.BYTEPLUS:
            gc_ak = get_global_config_str("byteplus", "access_key")
            gc_sk = get_global_config_str("byteplus", "secret_key")
            gc_token = get_global_config_str("byteplus", "session_token")
        else:
            gc_ak = get_global_config_str("volcengine", "access_key")
            gc_sk = get_global_config_str("volcengine", "secret_key")
            gc_token = get_global_config_str("volcengine", "session_token")
        if gc_ak and gc_sk:
            return Credentials(
                access_key=gc_ak,
                secret_key=gc_sk,
                session_token=gc_token or None,
                source="global_config",
            )
        return None

    def _get_credential_from_vefaas_iam(
        self, *, force: bool = False
    ) -> Optional[Credentials]:
        """
        Internal helper to attempt retrieving credentials from VeFaaS IAM environment.
        """
        if self._provider != CloudProvider.VOLCENGINE:
            return None
        path = Path(VEFAAS_IAM_CREDENTIAL_PATH)
        if not path.exists():
            return None

        try:
            mtime_ns = path.stat().st_mtime_ns
        except Exception:
            return None

        now = datetime.now(tz=timezone.utc)

        def _get_cached_if_usable(
            *, min_validity_seconds: int
        ) -> Optional[Credentials]:
            with self._vefaas_lock:
                cached = self._vefaas_cache_credentials
                if not cached or self._vefaas_cache_mtime_ns != mtime_ns:
                    return None

                if cached.expires_at is None:
                    loaded_at = self._vefaas_cache_loaded_at_monotonic
                    if loaded_at is None:
                        return None
                    if (
                        time.monotonic() - loaded_at
                        <= VEFAAS_IAM_CREDENTIAL_FALLBACK_TTL_SECONDS
                    ):
                        return cached
                    return None

                if (cached.expires_at - now).total_seconds() > min_validity_seconds:
                    return cached
                return None

        if not force:
            cached = _get_cached_if_usable(
                min_validity_seconds=VEFAAS_IAM_CREDENTIAL_MIN_VALIDITY_SECONDS
            )
            if cached is not None:
                return cached

        try:
            with open(path, "r") as f:
                cred_dict = json.load(f)
                access_key = str(cred_dict.get("access_key_id") or "")
                secret_key = str(cred_dict.get("secret_access_key") or "")
                session_token = str(cred_dict.get("session_token") or "") or None

                expired_time_raw = cred_dict.get("expired_time")
                expires_at: Optional[datetime] = None
                if expired_time_raw:
                    try:
                        s = str(expired_time_raw)
                        if s.endswith("Z"):
                            s = s[:-1] + "+00:00"
                        expires_at = datetime.fromisoformat(s)
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=timezone.utc)
                        expires_at = expires_at.astimezone(timezone.utc)
                    except Exception:
                        expires_at = None

                if not access_key or not secret_key:
                    return None

                if expires_at is not None:
                    if expires_at <= now:
                        return None

                creds = Credentials(
                    access_key=access_key,
                    secret_key=secret_key,
                    session_token=session_token,
                    expires_at=expires_at,
                    source="vefaas",
                )
                with self._vefaas_lock:
                    self._vefaas_cache_mtime_ns = mtime_ns
                    self._vefaas_cache_loaded_at_monotonic = time.monotonic()
                    self._vefaas_cache_credentials = creds
                return creds
        except Exception as e:
            if not force:
                cached = _get_cached_if_usable(
                    min_validity_seconds=VEFAAS_IAM_CREDENTIAL_MIN_VALIDITY_SECONDS
                )
                if cached is not None:
                    return cached
            logger.warning(f"Found VeFaaS credential file but failed to parse: {e}")
            return None

    def _resolve_service_region(self, service_key: str) -> str:
        """
        Resolves region for a specific service.
        Priority:
        1. Explicitly passed in constructor
        2. Service-specific environment variable: VOLCENGINE_{SERVICE}_REGION
        3. Service-specific config file: services.{service}.region
        4. Logical region mapping: region_policy.rules.{logical_region}.{service}
        5. Global environment variable: VOLCENGINE_REGION
        6. Global config file: volcengine.region
        7. Default: DEFAULT_REGION
        """
        key_lower = service_key.lower()
        key_upper = service_key.upper()

        if self._region:
            mapped_region = self._get_mapped_region(self._region, service_key)
            if mapped_region:
                return mapped_region
            return self._region

        if self._provider == CloudProvider.BYTEPLUS:
            svc_region = os.getenv(f"BYTEPLUS_{key_upper}_REGION")
        else:
            svc_region = os.getenv(f"VOLCENGINE_{key_upper}_REGION") or os.getenv(
                f"VOLC_{key_upper}_REGION"
            )
        if svc_region:
            return svc_region

        if self._provider == CloudProvider.BYTEPLUS:
            svc_region = get_global_config_value(
                "byteplus", "services", key_lower, "region"
            )
        else:
            svc_region = get_global_config_value("services", key_lower, "region")
        if svc_region:
            return svc_region

        logical_region = self.region
        mapped_region = self._get_mapped_region(logical_region, service_key)
        if mapped_region:
            return mapped_region

        return logical_region

    def _get_mapped_region(
        self, logical_region: str, service_key: str
    ) -> Optional[str]:
        """
        Gets mapped region from region policy rules.
        Priority:
        1. Custom rules from global config
        2. Built-in rules
        """
        logical_region = logical_region.lower()
        service_key = service_key.lower()

        global_config_dict = read_global_config_dict()
        if self._provider == CloudProvider.BYTEPLUS:
            custom_rules = (
                (global_config_dict.get("byteplus") or {})
                .get("region_policy", {})
                .get("rules", {})
                if isinstance(global_config_dict, dict)
                else {}
            )
        else:
            custom_rules = (
                global_config_dict.get("region_policy", {}).get("rules", {})
                if isinstance(global_config_dict, dict)
                else {}
            )

        provider_rules = DEFAULT_REGION_RULES_BY_PROVIDER.get(self._provider, {})
        active_rule = provider_rules.get(logical_region, {}).copy()
        if custom_rules:
            user_rule = custom_rules.get(logical_region, {})
            active_rule.update(user_rule)

        return active_rule.get(service_key)

    def _get_service_override(self, service_key: str, field: str) -> Optional[str]:
        """Resolve provider-aware overrides for endpoint details.

        Supported fields: host, scheme, api_version, service

        Precedence: provider env > provider config > legacy/global config (volcengine only)
        """
        key_lower = service_key.lower()
        key_upper = key_lower.upper()

        if self._provider == CloudProvider.BYTEPLUS:
            env_prefix = "BYTEPLUS"
            env_value = os.getenv(f"{env_prefix}_{key_upper}_{field.upper()}")
            if env_value:
                return env_value

            cfg_value = get_global_config_value(
                "byteplus", "services", key_lower, field
            )
            return cfg_value

        # Volcano Engine (CN)
        env_value = os.getenv(f"VOLCENGINE_{key_upper}_{field.upper()}") or os.getenv(
            f"VOLC_{key_upper}_{field.upper()}"
        )
        if env_value:
            return env_value

        return get_global_config_value("services", key_lower, field)

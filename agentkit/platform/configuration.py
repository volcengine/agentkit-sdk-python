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
import logging
import os
from dataclasses import dataclass
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

logger = logging.getLogger(__name__)

VEFAAS_IAM_CREDENTIAL_PATH = "/var/run/secrets/iam/credential"


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

    def __repr__(self) -> str:
        masked_sk = "*" * 6
        if self.secret_key and len(self.secret_key) > 4:
            masked_sk = "*" * (len(self.secret_key) - 4) + self.secret_key[-4:]

        return (
            f"Credentials(access_key='{self.access_key}', "
            f"secret_key='{masked_sk}', "
            f"session_token={'***' if self.session_token else 'None'})"
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
            return Credentials(
                access_key=self._ak,
                secret_key=self._sk,
                session_token=self._token,
            )

        # 2. Service-specific Environment Variables
        if creds := self._get_service_env_credentials(service_key):
            return creds

        # 3. Global Environment Variables
        if creds := self._get_global_env_credentials():
            return creds

        # 4. Global Config File
        if creds := self._get_config_file_credentials():
            return creds

        # 5. VeFaaS IAM (Runtime)
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
        else:
            # Service-specific keys (align with environment variable behavior)
            ak = _get(f"VOLCENGINE_{svc_upper}_ACCESS_KEY")
            sk = _get(f"VOLCENGINE_{svc_upper}_SECRET_KEY")
            if not ak or not sk:
                # Legacy support
                ak = ak or _get(f"VOLC_{svc_upper}_ACCESSKEY")
                sk = sk or _get(f"VOLC_{svc_upper}_SECRETKEY")

        if ak and sk:
            return Credentials(access_key=ak, secret_key=sk)

        # Global keys
        if self._provider == CloudProvider.BYTEPLUS:
            ak = _get("BYTEPLUS_ACCESS_KEY")
            sk = _get("BYTEPLUS_SECRET_KEY")
        else:
            ak = _get("VOLCENGINE_ACCESS_KEY") or _get("VOLC_ACCESSKEY")
            sk = _get("VOLCENGINE_SECRET_KEY") or _get("VOLC_SECRETKEY")

        if ak and sk:
            return Credentials(access_key=ak, secret_key=sk)

        return None

    def _get_service_env_credentials(self, service_key: str) -> Optional[Credentials]:
        svc_upper = service_key.upper()
        if self._provider == CloudProvider.BYTEPLUS:
            ak = os.getenv(f"BYTEPLUS_{svc_upper}_ACCESS_KEY")
            sk = os.getenv(f"BYTEPLUS_{svc_upper}_SECRET_KEY")
        else:
            ak = os.getenv(f"VOLCENGINE_{svc_upper}_ACCESS_KEY")
            sk = os.getenv(f"VOLCENGINE_{svc_upper}_SECRET_KEY")

            if not ak or not sk:
                # Legacy support
                ak = ak or os.getenv(f"VOLC_{svc_upper}_ACCESSKEY")
                sk = sk or os.getenv(f"VOLC_{svc_upper}_SECRETKEY")

        if ak and sk:
            return Credentials(access_key=ak, secret_key=sk)
        return None

    def _get_global_env_credentials(self) -> Optional[Credentials]:
        if self._provider == CloudProvider.BYTEPLUS:
            ak = os.getenv("BYTEPLUS_ACCESS_KEY")
            sk = os.getenv("BYTEPLUS_SECRET_KEY")
        else:
            ak = os.getenv("VOLCENGINE_ACCESS_KEY") or os.getenv("VOLC_ACCESSKEY")
            sk = os.getenv("VOLCENGINE_SECRET_KEY") or os.getenv("VOLC_SECRETKEY")

        if ak and sk:
            return Credentials(access_key=ak, secret_key=sk)
        return None

    def _get_config_file_credentials(self) -> Optional[Credentials]:
        if self._provider == CloudProvider.BYTEPLUS:
            gc_ak = get_global_config_str("byteplus", "access_key")
            gc_sk = get_global_config_str("byteplus", "secret_key")
        else:
            gc_ak = get_global_config_str("volcengine", "access_key")
            gc_sk = get_global_config_str("volcengine", "secret_key")
        if gc_ak and gc_sk:
            return Credentials(access_key=gc_ak, secret_key=gc_sk)
        return None

    def _get_credential_from_vefaas_iam(self) -> Optional[Credentials]:
        """
        Internal helper to attempt retrieving credentials from VeFaaS IAM environment.
        """
        if self._provider != CloudProvider.VOLCENGINE:
            return None
        path = Path(VEFAAS_IAM_CREDENTIAL_PATH)
        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                cred_dict = json.load(f)
                return Credentials(
                    access_key=cred_dict.get("access_key_id", ""),
                    secret_key=cred_dict.get("secret_access_key", ""),
                    session_token=cred_dict.get("session_token", ""),
                )
        except Exception as e:
            logger.warning(f"Found VeFaaS credential file but failed to parse: {e}")
            return None

    def _resolve_service_region(self, service_key: str) -> str:
        """
        Resolves region for a specific service.
        Priority:
        1. Service-specific environment variable: VOLCENGINE_{SERVICE}_REGION
        2. Service-specific config file: services.{service}.region
        3. Logical region mapping: region_policy.rules.{logical_region}.{service}
        4. Global environment variable: VOLCENGINE_REGION
        5. Global config file: volcengine.region
        6. Default: DEFAULT_REGION
        """
        key_lower = service_key.lower()
        key_upper = service_key.upper()

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

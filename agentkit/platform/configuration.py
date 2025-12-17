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
from typing import Optional

from agentkit.platform.constants import DEFAULT_REGION, SERVICE_METADATA
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
    ):
        self._region = region
        self._ak = access_key
        self._sk = secret_key
        self._token = session_token

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

        return (
            os.getenv("VOLCENGINE_REGION")
            or os.getenv("VOLC_REGION")
            or get_global_config_str("region")
            or get_global_config_str("volcengine", "region")
            or DEFAULT_REGION
        )

    def get_service_endpoint(self, service_key: str) -> Endpoint:
        """
        Resolves the endpoint for a specific service.
        """
        key_lower = service_key.lower()
        meta = SERVICE_METADATA.get(key_lower)
        if not meta:
            # Fallback for unknown services if needed, or raise error
            # For strictness, we raise error as in original design
            raise ValueError(
                f"Unsupported service for endpoint resolution: {service_key}"
            )

        key_upper = key_lower.upper()

        # 1. Check for overrides in environment variables
        # Format: VOLCENGINE_{SERVICE}_HOST
        env_host = (
            os.getenv(f"VOLCENGINE_{key_upper}_HOST")
            or os.getenv(f"VOLC_{key_upper}_HOST")
            or get_global_config_value("services", key_lower, "host")
        )

        env_scheme = (
            os.getenv(f"VOLCENGINE_{key_upper}_SCHEME")
            or os.getenv(f"VOLC_{key_upper}_SCHEME")
            or get_global_config_value("services", key_lower, "scheme")
        )

        env_version = (
            os.getenv(f"VOLCENGINE_{key_upper}_API_VERSION")
            or os.getenv(f"VOLC_{key_upper}_API_VERSION")
            or get_global_config_value("services", key_lower, "api_version")
        )

        env_service_code = (
            os.getenv(f"VOLCENGINE_{key_upper}_SERVICE")
            or os.getenv(f"VOLC_{key_upper}_SERVICE")
            or get_global_config_value("services", key_lower, "service")
        )

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

        raise ValueError(
            f"Volcengine credentials not found (Service: {service_key}). Please set environment variables VOLCENGINE_ACCESS_KEY and "
            "VOLCENGINE_SECRET_KEY, or configure in global config file ~/.agentkit/config.yaml."
        )

    def _get_service_env_credentials(self, service_key: str) -> Optional[Credentials]:
        svc_upper = service_key.upper()
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
        ak = os.getenv("VOLCENGINE_ACCESS_KEY") or os.getenv("VOLC_ACCESSKEY")
        sk = os.getenv("VOLCENGINE_SECRET_KEY") or os.getenv("VOLC_SECRETKEY")

        if ak and sk:
            return Credentials(access_key=ak, secret_key=sk)
        return None

    def _get_config_file_credentials(self) -> Optional[Credentials]:
        gc_ak = get_global_config_str("volcengine", "access_key")
        gc_sk = get_global_config_str("volcengine", "secret_key")
        if gc_ak and gc_sk:
            return Credentials(access_key=gc_ak, secret_key=gc_sk)
        return None

    def _get_credential_from_vefaas_iam(self) -> Optional[Credentials]:
        """
        Internal helper to attempt retrieving credentials from VeFaaS IAM environment.
        """
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

        svc_region = os.getenv(f"VOLCENGINE_{key_upper}_REGION") or os.getenv(
            f"VOLC_{key_upper}_REGION"
        )
        if svc_region:
            return svc_region

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
        from agentkit.platform.constants import DEFAULT_REGION_RULES

        logical_region = logical_region.lower()
        service_key = service_key.lower()

        global_config_dict = read_global_config_dict()
        custom_rules = global_config_dict.get("region_policy", {}).get("rules", {})

        active_rule = DEFAULT_REGION_RULES.get(logical_region, {}).copy()
        if custom_rules:
            user_rule = custom_rules.get(logical_region, {})
            active_rule.update(user_rule)

        return active_rule.get(service_key)

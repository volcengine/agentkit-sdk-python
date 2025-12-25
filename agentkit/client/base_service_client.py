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

"""
Base service client that provides common implementation for all Volcengine services.
This is the top-level base class for all service clients.
"""

import json
from typing import Any, Dict, Type, TypeVar, Union, Optional
from dataclasses import dataclass

from volcengine.ApiInfo import ApiInfo
from volcengine.base.Service import Service
from volcengine.Credentials import Credentials
from volcengine.ServiceInfo import ServiceInfo

from agentkit.platform import (
    VolcConfiguration,
    resolve_credentials,
    resolve_endpoint,
)
from agentkit.utils.ve_sign import ensure_x_custom_source_header

T = TypeVar("T")


@dataclass
class ApiConfig:
    """Configuration for a single API endpoint."""

    action: str
    method: str = "POST"
    path: str = "/"
    form: Optional[Dict[str, Any]] = None
    header: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.form is None:
            self.form = {}
        if self.header is None:
            self.header = {}


class BaseServiceClient(Service):
    """
    Base class for all Volcengine service clients.

    This class provides:
    1. Unified interface for all Volcengine services (AgentKit, IAM, etc.)
    2. Common implementation using volcengine.base.Service
    3. Shared credential management and API invocation logic

    Subclasses should:
    1. Override API_ACTIONS with their API action configurations
    """

    # Subclasses should override this with their API action configurations
    API_ACTIONS: Dict[str, Union[str, ApiConfig]] = {}

    def __init__(
        self,
        service: str,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
        session_token: str = "",
        service_name: str = "",
        platform_config: Optional[VolcConfiguration] = None,
        header: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize the service client.

        Args:
            service: Logical service name for signing and endpoint resolution
            access_key: Volcengine access key
            secret_key: Volcengine secret key
            region: Volcengine region override for endpoint
            session_token: Optional session token
            service_name: Service name for logging
            platform_config: Optional platform-level configuration overrides
        """
        if platform_config is None:
            platform_config = VolcConfiguration()

        creds = resolve_credentials(
            service=service,
            explicit_access_key=access_key or None,
            explicit_secret_key=secret_key or None,
            platform_config=platform_config,
        )

        ep = resolve_endpoint(
            service=service,
            region=region or None,
            platform_config=platform_config,
        )

        self.access_key = creds.access_key
        self.secret_key = creds.secret_key
        self.session_token = creds.session_token

        self.host = ep.host
        self.region = ep.region
        self.service = ep.service
        self.scheme = ep.scheme
        self.api_version = ep.api_version

        self.service_name = service_name

        if header is None:
            effective_header: Dict[str, Any] = {"Accept": "application/json"}
        else:
            effective_header = header.copy()
            if "Accept" not in effective_header:
                effective_header = {"Accept": "application/json", **effective_header}

        effective_header = ensure_x_custom_source_header(effective_header)
        # Create ServiceInfo
        self.service_info = ServiceInfo(
            host=self.host,
            header=effective_header,
            credentials=Credentials(
                ak=self.access_key,
                sk=self.secret_key,
                service=self.service,
                region=self.region,
                session_token=self.session_token,
            ),
            connection_timeout=30,
            socket_timeout=30,
            scheme=self.scheme,
        )

        # Generate ApiInfo for all actions
        self.api_info = self._build_api_info()

        # Initialize parent Service class
        Service.__init__(self, service_info=self.service_info, api_info=self.api_info)
        # need setting ak/sk after initializing Service to avoid volcengine SDK bugs
        self.set_ak(self.access_key)
        self.set_sk(self.secret_key)

    def _build_api_info(self) -> Dict[str, ApiInfo]:
        """
        Build ApiInfo dictionary from API_ACTIONS.

        Supports two formats:
        1. Simple string: {"ListItems": "ListItems"} -> POST to / with Action query param
        2. ApiConfig: {"GetItem": ApiConfig(action="GetItem", method="GET", path="/items")}

        Returns:
            Dictionary mapping action names to ApiInfo objects
        """
        api_info = {}
        for action_key, action_config in self.API_ACTIONS.items():
            # If it's a simple string, use default POST configuration
            if isinstance(action_config, str):
                api_info[action_key] = ApiInfo(
                    method="POST",
                    path="/",
                    query={"Action": action_config, "Version": self.api_version},
                    form={},
                    header={},
                )
            # If it's an ApiConfig, use the detailed configuration
            elif isinstance(action_config, ApiConfig):
                api_info[action_key] = ApiInfo(
                    method=action_config.method,
                    path=action_config.path,
                    query={"Action": action_config.action, "Version": self.api_version},
                    form=action_config.form,
                    header=action_config.header,
                )
            else:
                raise ValueError(
                    f"Invalid API_ACTIONS configuration for '{action_key}': "
                    f"expected str or ApiConfig, got {type(action_config)}"
                )
        return api_info

    def _invoke_api(
        self,
        api_action: str,
        request: Any,
        response_type: Type[T],
        params: Dict[str, Any] = None,
    ) -> T:
        """
        Unified API invocation with error handling.

        Args:
            api_action: The API action name (e.g., 'GetUser', 'ListRuntimes')
            request: The request object (Pydantic model)
            response_type: The response type to parse into
            params: Additional query parameters

        Returns:
            Typed response object

        Raises:
            Exception: If API call fails or returns an error
        """
        # Make API call
        try:
            res = self.json(
                api=api_action,
                params=params or {},
                body=json.dumps(request.model_dump(by_alias=True, exclude_none=True)),
            )
        except Exception as e:
            raise Exception(f"Failed to {api_action}: {str(e)}")

        if not res:
            raise Exception(f"Empty response from {api_action} request.")

        # Parse response
        response_data = json.loads(res)

        # Check for errors
        metadata = response_data.get("ResponseMetadata", {})
        if metadata.get("Error"):
            error_msg = metadata.get("Error", {}).get("Message", "Unknown error")
            raise Exception(f"Failed to {api_action}: {error_msg}")

        # Return typed response
        return response_type(**response_data.get("Result", {}))

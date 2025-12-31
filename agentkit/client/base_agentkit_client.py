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
Base client for AgentKit services.
Provides common initialization and API invocation logic.
"""

from typing import Any, Dict, Union, Optional

from agentkit.client.base_service_client import BaseServiceClient, ApiConfig


class BaseAgentkitClient(BaseServiceClient):
    """
    Base client for all AgentKit services.

    This class provides:
    1. Common credential initialization
    2. Unified API invocation logic with error handling
    3. Automatic ApiInfo generation with flexible configuration

    Subclasses should override API_ACTIONS with either:
    - Simple dict mapping: {"ActionName": "ActionName"}
    - Detailed ApiConfig: {"ActionName": ApiConfig(action="ActionName", method="GET", path="/custom")}
    """

    # Subclasses should override this with their API action configurations
    API_ACTIONS: Dict[str, Union[str, ApiConfig]] = {}

    def __init__(
        self,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
        session_token: str = "",
        service_name: str = "",
        header: Optional[Dict[str, Any]] = {"Accept": "application/json"},
    ) -> None:
        """
        Initialize the AgentKit client.

        Args:
            access_key: Volcengine access key
            secret_key: Volcengine secret key
            region: Volcengine region
            session_token: Optional session token
            service_name: Service name for logging (e.g., 'knowledge', 'memory')
        """
        super().__init__(
            service="agentkit",
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            session_token=session_token,
            service_name=service_name,
            header=header,
        )

    def _get(self, api_action: str, params: Dict[str, Any] = None) -> str:
        """Legacy method for GET requests."""
        try:
            resp = self.get(api_action, params)
            return resp
        except Exception as e:
            raise Exception(f"Failed to {api_action}: {str(e)}")

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
Base client for IAM services.
Uses the same volcengine.base.Service approach as AgentKit services.
"""

from typing import Dict, Union

from agentkit.client.base_service_client import BaseServiceClient, ApiConfig


class BaseIAMClient(BaseServiceClient):
    """
    Base client for IAM services.

    This class provides the same interface as BaseAgentkitClient but for IAM services:
    1. Common credential initialization
    2. Unified API invocation logic with error handling
    3. Automatic ApiInfo generation with flexible configuration

    Subclasses should override API_ACTIONS with either:
    - Simple dict mapping: {"ActionName": "ActionName"}
    - Detailed ApiConfig: {"ActionName": ApiConfig(action="ActionName", method="GET", path="/custom")}
    """

    # Subclasses should override this with their API action configurations
    API_ACTIONS: Dict[str, Union[str, ApiConfig]] = {}

    # IAM service specific configuration
    IAM_API_VERSION = "2018-01-01"
    IAM_SERVICE_CODE = "iam"
    IAM_HOST = "open.volcengineapi.com"

    def __init__(
        self,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
        session_token: str = "",
        service_name: str = "iam",
    ) -> None:
        """
        Initialize the IAM client.

        Args:
            access_key: Volcengine access key
            secret_key: Volcengine secret key
            region: Volcengine region
            session_token: Optional session token
            service_name: Service name for logging
        """
        super().__init__(
            service="iam",
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            session_token=session_token,
            service_name=service_name,
        )

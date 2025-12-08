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

# Auto-generated from API JSON definition
# Do not edit manually

from __future__ import annotations

from typing import Dict, List, Optional
from agentkit.client import BaseAgentkitClient
from agentkit.sdk.account.types import (
    ListAccountLinkedServicesRequest,
    ListAccountLinkedServicesResponse,
)


class AgentkitAccountClient(BaseAgentkitClient):
    """AgentKit Account Management Service"""

    API_ACTIONS: Dict[str, str] = {
        "ListAccountLinkedServices": "ListAccountLinkedServices",
    }

    def __init__(
        self,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
        session_token: str = "",
    ) -> None:
        super().__init__(
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            session_token=session_token,
            service_name="account",
        )

    def list_account_linked_services(
        self, request: ListAccountLinkedServicesRequest
    ) -> ListAccountLinkedServicesResponse:
        return self._invoke_api(
            api_action="ListAccountLinkedServices",
            request=request,
            response_type=ListAccountLinkedServicesResponse,
        )

    def get_service_status(self, service_name: str) -> Optional[str]:
        """
        Query the LinkServices status for a specific service.

        Args:
            service_name: The name of the service to query (e.g., 'ark', 'vefaas')

        Returns:
            The status string ('Enabled' or 'Disabled'), or None if service not found.
        """
        print(1)
        response = self.list_account_linked_services(ListAccountLinkedServicesRequest())
        print(2)
        if not response.service_statuses:
            return None
        for svc in response.service_statuses:
            if svc.service_name == service_name:
                return svc.status
        return None

    def get_services_status(self, service_names: List[str]) -> Dict[str, Optional[str]]:
        """
        Query the LinkServices status for multiple services.

        Args:
            service_names: List of service names to query (e.g., ['ark', 'vefaas', 'cr'])

        Returns:
            A dict mapping service_name -> status ('Enabled'/'Disabled'/None if not found).
        """
        response = self.list_account_linked_services(ListAccountLinkedServicesRequest())
        status_map: Dict[str, Optional[str]] = {name: None for name in service_names}
        if response.service_statuses:
            for svc in response.service_statuses:
                if svc.service_name in status_map:
                    status_map[svc.service_name] = svc.status
        return status_map

    def has_disabled_services(self) -> List[str]:
        """
        Check if any returned service has a disabled status.

        Returns:
            A list of service names that are disabled (status != 'Enabled').
            Returns empty list if all services are enabled.
        """
        response = self.list_account_linked_services(ListAccountLinkedServicesRequest())
        disabled = []
        if response.service_statuses:
            for svc in response.service_statuses:
                if svc.status != "Enabled":
                    disabled.append(svc.service_name)
        return disabled

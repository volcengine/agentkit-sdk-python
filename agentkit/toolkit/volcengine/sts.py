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
Volcengine STS (Security Token Service) client.

Provides identity verification through the GetCallerIdentity API.
"""

import json
import logging
from typing import Dict, Optional

from pydantic import BaseModel, Field

from agentkit.client.base_service_client import BaseServiceClient, ApiConfig


logger = logging.getLogger(__name__)


class GetCallerIdentityResponse(BaseModel):
    """Response for GetCallerIdentity API"""

    account_id: Optional[int] = Field(None, alias="AccountId")
    trn: Optional[str] = Field(None, alias="Trn")
    identity_type: Optional[str] = Field(None, alias="IdentityType")
    identity_id: Optional[str] = Field(None, alias="IdentityId")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class VeSTS(BaseServiceClient):
    """Volcengine STS Service Client"""

    # Define all API actions for this service
    API_ACTIONS: Dict[str, ApiConfig] = {
        "GetCallerIdentity": ApiConfig(action="GetCallerIdentity", method="GET"),
    }

    def __init__(
        self,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
        session_token: str = "",
    ) -> None:
        super().__init__(
            service="sts",
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            session_token=session_token,
            service_name="sts",
        )

    def get_caller_identity(self) -> Optional[GetCallerIdentityResponse]:
        """
        Get the identity of the caller.

        Returns:
            GetCallerIdentityResponse containing account_id, trn, identity_type, and identity_id
        """
        res = self.request("GetCallerIdentity", params={}, data="{}")
        response_data = json.loads(res)
        return GetCallerIdentityResponse(**response_data.get("Result", {}))

    def get_account_id(self) -> Optional[int]:
        """
        Get the account ID of the caller.

        Returns:
            Account ID as integer, or None if not available
        """
        identity = self.get_caller_identity()
        return identity.account_id if identity else None

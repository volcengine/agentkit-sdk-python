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

import os
import json
import logging
from typing import Dict, Optional, List
from pydantic import BaseModel, Field

from agentkit.client.base_iam_client import BaseIAMClient
from agentkit.client.base_service_client import ApiConfig


logger = logging.getLogger(__name__)


class UserInfo(BaseModel):
    """User information"""

    user_name: Optional[str] = Field(None, alias="UserName")
    id: Optional[int] = Field(None, alias="Id")
    trn: Optional[str] = Field(None, alias="Trn")
    account_id: Optional[int] = Field(None, alias="AccountId")
    display_name: Optional[str] = Field(None, alias="DisplayName")
    description: Optional[str] = Field(None, alias="Description")
    email: Optional[str] = Field(None, alias="Email")
    mobile_phone: Optional[str] = Field(None, alias="MobilePhone")
    create_date: Optional[str] = Field(None, alias="CreateDate")
    update_date: Optional[str] = Field(None, alias="UpdateDate")
    email_is_verified: Optional[bool] = Field(None, alias="EmailIsVerified")
    mobile_phone_is_verified: Optional[bool] = Field(
        None, alias="MobilePhoneIsVerified"
    )
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class GetUserRequest(BaseModel):
    """Get user request"""

    user_name: Optional[str] = Field(None, alias="UserName")
    id: Optional[str] = Field(None, alias="ID")  # User ID
    access_key_id: Optional[str] = Field(None, alias="AccessKeyID")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class GetUserResponse(BaseModel):
    """Get user response"""

    user: Optional[UserInfo] = Field(None, alias="User")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class ListUsersRequest(BaseModel):
    """List users request"""

    limit: Optional[int] = Field(None, alias="Limit")
    offset: Optional[int] = Field(None, alias="Offset")
    query: Optional[str] = Field(None, alias="Query")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class ListUsersResponse(BaseModel):
    """List users response"""

    user_metadata: Optional[List[UserInfo]] = Field(None, alias="UserMetadata")
    limit: Optional[int] = Field(None, alias="Limit")
    offset: Optional[int] = Field(None, alias="Offset")
    total: Optional[int] = Field(None, alias="Total")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class RoleInfo(BaseModel):
    """Role information"""

    role_name: Optional[str] = Field(None, alias="RoleName")
    role_id: Optional[int] = Field(None, alias="RoleId")
    trn: Optional[str] = Field(None, alias="Trn")
    account_id: Optional[int] = Field(None, alias="AccountId")
    display_name: Optional[str] = Field(None, alias="DisplayName")
    description: Optional[str] = Field(None, alias="Description")
    trust_policy_document: Optional[str] = Field(None, alias="TrustPolicyDocument")
    max_session_duration: Optional[int] = Field(None, alias="MaxSessionDuration")
    create_date: Optional[str] = Field(None, alias="CreateDate")
    update_date: Optional[str] = Field(None, alias="UpdateDate")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class GetRoleRequest(BaseModel):
    """Get role request"""

    role_name: str = Field(..., alias="RoleName")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class GetRoleResponse(BaseModel):
    """Get role response"""

    role: Optional[RoleInfo] = Field(None, alias="Role")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class ListRolesRequest(BaseModel):
    """List roles request"""

    limit: Optional[int] = Field(None, alias="Limit")
    offset: Optional[int] = Field(None, alias="Offset")
    query: Optional[str] = Field(None, alias="Query")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class ListRolesResponse(BaseModel):
    """List roles response"""

    role_metadata: Optional[List[RoleInfo]] = Field(None, alias="RoleMetadata")
    limit: Optional[int] = Field(None, alias="Limit")
    offset: Optional[int] = Field(None, alias="Offset")
    total: Optional[int] = Field(None, alias="Total")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class CreateRoleRequest(BaseModel):
    """Create role request"""

    role_name: str = Field(..., alias="RoleName")
    display_name: Optional[str] = Field(None, alias="DisplayName")
    trust_policy_document: str = Field(..., alias="TrustPolicyDocument")
    description: Optional[str] = Field(None, alias="Description")
    max_session_duration: Optional[int] = Field(None, alias="MaxSessionDuration")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class CreateRoleResponse(BaseModel):
    """Create role response"""

    role: Optional[RoleInfo] = Field(None, alias="Role")
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class AttachRolePolicyRequest(BaseModel):
    """Attach role policy request"""

    role_name: str = Field(..., alias="RoleName")
    policy_name: str = Field(..., alias="PolicyName")
    policy_type: str = Field(..., alias="PolicyType")  # System or Custom
    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class AttachRolePolicyResponse(BaseModel):
    """Attach role policy response"""

    pass  # No result data in response


class VeIAM(BaseIAMClient):
    """Volcengine IAM Service Client"""

    # Define all API actions for this service
    API_ACTIONS: Dict[str, ApiConfig] = {
        "GetUser": ApiConfig(action="GetUser", method="GET"),
        "ListUsers": ApiConfig(action="ListUsers", method="GET"),
        "GetRole": ApiConfig(action="GetRole", method="GET"),
        "ListRoles": ApiConfig(action="ListRoles", method="GET"),
        "CreateRole": ApiConfig(action="CreateRole", method="GET"),
        "AttachRolePolicy": ApiConfig(action="AttachRolePolicy", method="GET"),
    }

    def __init__(
        self,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
    ) -> None:
        super().__init__(
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            service_name="iam",
        )

    def list_users(
        self, limit: int = 10, offset: int = 0, query: str = ""
    ) -> Optional[ListUsersResponse]:
        """List users"""
        request = ListUsersRequest(limit=limit, offset=offset, query=query)
        res = self.request(
            "ListUsers",
            params=request.model_dump(by_alias=True, exclude_none=True),
            data="{}",
        )
        response_data = json.loads(res)
        return ListUsersResponse(**response_data.get("Result", {}))

    def list_roles(self, request: ListRolesRequest) -> Optional[ListRolesResponse]:
        """List roles"""
        res = self.request(
            "ListRoles",
            params=request.model_dump(by_alias=True, exclude_none=True),
            data="{}",
        )
        response_data = json.loads(res)
        return ListRolesResponse(**response_data.get("Result", {}))

    def get_role(self, role_name: str) -> Optional[GetRoleResponse]:
        """Get role"""
        request = GetRoleRequest(role_name=role_name)
        try:
            res = self.request(
                "GetRole",
                params=request.model_dump(by_alias=True, exclude_none=True),
                data="{}",
            )
            response_data = json.loads(res)
            result_data = response_data.get("Result", {})
            role_data = result_data.get("Role")
            if isinstance(role_data, dict):
                tpd = role_data.get("TrustPolicyDocument")
                if isinstance(tpd, dict):
                    role_data["TrustPolicyDocument"] = json.dumps(tpd)
            return GetRoleResponse(**result_data)
        except Exception as e:
            # If role not found, return None
            if "RoleNotExist" in str(e) or "NotFound" in str(e) or "404" in str(e):
                return None
            raise e

    def create_role(
        self, role_name: str, trust_policy_document: str
    ) -> Optional[CreateRoleResponse]:
        """Create role"""
        request = CreateRoleRequest(
            display_name=role_name,
            role_name=role_name,
            trust_policy_document=trust_policy_document,
        )
        res = self.request(
            "CreateRole",
            params=request.model_dump(by_alias=True, exclude_none=True),
            data="{}",
        )
        response_data = json.loads(res)
        result_data = response_data.get("Result", {})
        role_data = result_data.get("Role")
        if isinstance(role_data, dict):
            tpd = role_data.get("TrustPolicyDocument")
            if isinstance(tpd, dict):
                role_data["TrustPolicyDocument"] = json.dumps(tpd)
        return CreateRoleResponse(**result_data)

    def attach_role_policy(
        self, role_name: str, policy_name: str, policy_type: str
    ) -> Optional[AttachRolePolicyResponse]:
        """Attach role policy"""
        request = AttachRolePolicyRequest(
            role_name=role_name,
            policy_name=policy_name,
            policy_type=policy_type,
        )
        res = self.request(
            "AttachRolePolicy",
            params=request.model_dump(by_alias=True, exclude_none=True),
            data="{}",
        )
        response_data = json.loads(res)
        return AttachRolePolicyResponse(**response_data.get("Result", {}))

    def ensure_role_for_agentkit(self, role_name: str) -> bool:
        """Ensure role for agentkit"""
        resp = self.get_role(role_name)
        agentkit_service_code = (
            (
                os.getenv("VOLCENGINE_AGENTKIT_SERVICE")
                or os.getenv("VOLC_AGENTKIT_SERVICE")
                or ""
            )
            .strip()
            .lower()
        )
        service = "vefaas"
        if "stg" in agentkit_service_code:
            service = "vefaas_dev"
        trust_policy_document = (
            '{"Statement":[{"Effect":"Allow","Action":["sts:AssumeRole"],"Principal":{"Service":["%s"]}}]}'
            % service
        )
        if resp is None:
            resp = self.create_role(role_name, trust_policy_document)
            """
            ArkReadOnlyAccess
            TLSReadOnlyAccess
            APMPlusServerReadOnlyAccess
            VikingdbReadOnlyAccess
            ESCloudReadOnlyAccess
            LLMShieldProtectSdkAccess
            AgentKitReadOnlyAccess
            TorchlightApiFullAccess
            Mem0ReadOnlyAccess
            AgentKitTosAccess
            AgentKitToolAccess
            """
            try:
                from agentkit.toolkit.config.global_config import get_global_config

                gc = get_global_config()
                defaults = getattr(gc, "defaults", None)
                custom_policies = (
                    getattr(defaults, "iam_role_policies", None) if defaults else None
                )
            except Exception:
                custom_policies = None

            if (
                custom_policies
                and isinstance(custom_policies, list)
                and len(custom_policies) > 0
            ):
                to_attach = custom_policies
            else:
                to_attach = [
                    "ArkReadOnlyAccess",
                    "TLSReadOnlyAccess",
                    "APMPlusServerReadOnlyAccess",
                    "VikingdbReadOnlyAccess",
                    "ESCloudReadOnlyAccess",
                    "LLMShieldProtectSdkAccess",
                    "AgentKitReadOnlyAccess",
                    "TorchlightApiFullAccess",
                    "Mem0ReadOnlyAccess",
                    "IDReadOnlyAccess",
                    "AgentKitTosAccess",
                    "AgentKitToolAccess",
                ]
            for policy in to_attach:
                self.attach_role_policy(
                    role_name, policy_name=policy, policy_type="System"
                )
        return True

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

from typing import Optional
from pydantic import BaseModel, Field


class KnowledgeBaseModel(BaseModel):
    """AgentKit auto-generated base model"""

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


# Data Types
class AssociatedRuntimesForGetKnowledgeBase(KnowledgeBaseModel):
    id: Optional[str] = Field(default=None, alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")


class AssociatedRuntimesForListKnowledgeBases(KnowledgeBaseModel):
    id: Optional[str] = Field(default=None, alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")


class ConnectionInfosForGetKnowledgeConnectionInfo(KnowledgeBaseModel):
    addr_type: Optional[str] = Field(default=None, alias="AddrType")
    auth_key: Optional[str] = Field(default=None, alias="AuthKey")
    auth_type: Optional[str] = Field(default=None, alias="AuthType")
    base_url: Optional[str] = Field(default=None, alias="BaseUrl")
    expire_at: Optional[str] = Field(default=None, alias="ExpireAt")
    extra_config: Optional[str] = Field(default=None, alias="ExtraConfig")
    region: Optional[str] = Field(default=None, alias="Region")
    status: Optional[str] = Field(default=None, alias="Status")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")
    vpc_name: Optional[str] = Field(default=None, alias="VpcName")


class KnowledgeBasesForAddKnowledgeBase(KnowledgeBaseModel):
    knowledge_id: Optional[str] = Field(default=None, alias="KnowledgeId")
    message: Optional[str] = Field(default=None, alias="Message")
    provider_knowledge_id: Optional[str] = Field(
        default=None, alias="ProviderKnowledgeId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")
    status: Optional[str] = Field(default=None, alias="Status")


class KnowledgeBasesForListKnowledgeBases(KnowledgeBaseModel):
    associated_runtimes: Optional[list[AssociatedRuntimesForListKnowledgeBases]] = (
        Field(default=None, alias="AssociatedRuntimes")
    )
    create_time: Optional[str] = Field(default=None, alias="CreateTime")
    description: Optional[str] = Field(default=None, alias="Description")
    knowledge_id: Optional[str] = Field(default=None, alias="KnowledgeId")
    last_update_time: Optional[str] = Field(default=None, alias="LastUpdateTime")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configuration: Optional[NetworkConfigurationForListKnowledgeBases] = Field(
        default=None, alias="NetworkConfiguration"
    )
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    provider_knowledge_id: Optional[str] = Field(
        default=None, alias="ProviderKnowledgeId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")
    region: Optional[str] = Field(default=None, alias="Region")
    status: Optional[str] = Field(default=None, alias="Status")


class NetworkConfigurationForListKnowledgeBases(KnowledgeBaseModel):
    enable_private_network: Optional[bool] = Field(
        default=None, alias="EnablePrivateNetwork"
    )
    enable_public_network: Optional[bool] = Field(
        default=None, alias="EnablePublicNetwork"
    )
    vpc_configuration: Optional[VpcConfigurationForListKnowledgeBases] = Field(
        default=None, alias="VpcConfiguration"
    )


class VpcConfigForGetKnowledgeBase(KnowledgeBaseModel):
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


class VpcConfigurationForListKnowledgeBases(KnowledgeBaseModel):
    security_group_ids: Optional[list[str]] = Field(
        default=None, alias="SecurityGroupIds"
    )
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


# AddKnowledgeBase - Request
class KnowledgeBasesItemForAddKnowledgeBase(KnowledgeBaseModel):
    description: Optional[str] = Field(default=None, alias="Description")
    name: str = Field(..., alias="Name")
    provider_knowledge_id: str = Field(..., alias="ProviderKnowledgeId")
    provider_type: str = Field(..., alias="ProviderType")


class AddKnowledgeBaseRequest(KnowledgeBaseModel):
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    knowledge_bases: Optional[list[KnowledgeBasesItemForAddKnowledgeBase]] = Field(
        default=None, alias="KnowledgeBases"
    )


# AddKnowledgeBase - Response
class AddKnowledgeBaseResponse(KnowledgeBaseModel):
    knowledge_bases: Optional[list[KnowledgeBasesForAddKnowledgeBase]] = Field(
        default=None, alias="KnowledgeBases"
    )


# DeleteKnowledgeBase - Request
class DeleteKnowledgeBaseRequest(KnowledgeBaseModel):
    knowledge_id: str = Field(..., alias="KnowledgeId")


# DeleteKnowledgeBase - Response
class DeleteKnowledgeBaseResponse(KnowledgeBaseModel):
    knowledge_id: Optional[str] = Field(default=None, alias="KnowledgeId")
    provider_knowledge_id: Optional[str] = Field(
        default=None, alias="ProviderKnowledgeId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")


# GetKnowledgeBase - Request
class GetKnowledgeBaseRequest(KnowledgeBaseModel):
    knowledge_id: str = Field(..., alias="KnowledgeId")


# GetKnowledgeBase - Response
class GetKnowledgeBaseResponse(KnowledgeBaseModel):
    associated_runtimes: Optional[list[AssociatedRuntimesForGetKnowledgeBase]] = Field(
        default=None, alias="AssociatedRuntimes"
    )
    create_time: Optional[str] = Field(default=None, alias="CreateTime")
    description: Optional[str] = Field(default=None, alias="Description")
    knowledge_id: Optional[str] = Field(default=None, alias="KnowledgeId")
    last_update_time: Optional[str] = Field(default=None, alias="LastUpdateTime")
    name: Optional[str] = Field(default=None, alias="Name")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    provider_knowledge_id: Optional[str] = Field(
        default=None, alias="ProviderKnowledgeId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")
    region: Optional[str] = Field(default=None, alias="Region")
    status: Optional[str] = Field(default=None, alias="Status")
    trn: Optional[str] = Field(default=None, alias="Trn")
    vpc_config: Optional[VpcConfigForGetKnowledgeBase] = Field(
        default=None, alias="VpcConfig"
    )


# GetKnowledgeConnectionInfo - Request
class GetKnowledgeConnectionInfoRequest(KnowledgeBaseModel):
    knowledge_id: str = Field(..., alias="KnowledgeId")


# GetKnowledgeConnectionInfo - Response
class GetKnowledgeConnectionInfoResponse(KnowledgeBaseModel):
    connection_infos: Optional[list[ConnectionInfosForGetKnowledgeConnectionInfo]] = (
        Field(default=None, alias="ConnectionInfos")
    )
    knowledge_id: Optional[str] = Field(default=None, alias="KnowledgeId")
    message: Optional[str] = Field(default=None, alias="Message")
    name: Optional[str] = Field(default=None, alias="Name")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    provider_knowledge_id: Optional[str] = Field(
        default=None, alias="ProviderKnowledgeId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")
    status: Optional[str] = Field(default=None, alias="Status")


# ListKnowledgeBases - Request
class FiltersItemForListKnowledgeBases(KnowledgeBaseModel):
    name: Optional[str] = Field(default=None, alias="Name")
    name_contains: Optional[str] = Field(default=None, alias="NameContains")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class ListKnowledgeBasesRequest(KnowledgeBaseModel):
    create_time_after: Optional[str] = Field(default=None, alias="CreateTimeAfter")
    create_time_before: Optional[str] = Field(default=None, alias="CreateTimeBefore")
    max_results: Optional[int] = Field(default=None, alias="MaxResults")
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    update_time_after: Optional[str] = Field(default=None, alias="UpdateTimeAfter")
    update_time_before: Optional[str] = Field(default=None, alias="UpdateTimeBefore")
    filters: Optional[list[FiltersItemForListKnowledgeBases]] = Field(
        default=None, alias="Filters"
    )


# ListKnowledgeBases - Response
class ListKnowledgeBasesResponse(KnowledgeBaseModel):
    knowledge_bases: Optional[list[KnowledgeBasesForListKnowledgeBases]] = Field(
        default=None, alias="KnowledgeBases"
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")


# UpdateKnowledgeBase - Request
class VpcForUpdateKnowledgeBase(KnowledgeBaseModel):
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: str = Field(..., alias="VpcId")


class UpdateKnowledgeBaseRequest(KnowledgeBaseModel):
    description: Optional[str] = Field(default=None, alias="Description")
    knowledge_id: str = Field(..., alias="KnowledgeId")
    vpc_config: Optional[VpcForUpdateKnowledgeBase] = Field(
        default=None, alias="VpcConfig"
    )


# UpdateKnowledgeBase - Response
class UpdateKnowledgeBaseResponse(KnowledgeBaseModel):
    knowledge_id: Optional[str] = Field(default=None, alias="KnowledgeId")
    provider_knowledge_id: Optional[str] = Field(
        default=None, alias="ProviderKnowledgeId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")

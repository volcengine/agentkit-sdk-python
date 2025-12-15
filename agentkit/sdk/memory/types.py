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


class MemoryBaseModel(BaseModel):
    """AgentKit auto-generated base model"""

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


# Data Types
class AssociatedRuntimesForGetMemoryCollection(MemoryBaseModel):
    id: Optional[str] = Field(default=None, alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")


class AssociatedRuntimesForListMemoryCollections(MemoryBaseModel):
    id: Optional[str] = Field(default=None, alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")


class CollectionsForAddMemoryCollection(MemoryBaseModel):
    memory_id: Optional[str] = Field(default=None, alias="MemoryId")
    message: Optional[str] = Field(default=None, alias="Message")
    provider_collection_id: Optional[str] = Field(
        default=None, alias="ProviderCollectionId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")
    status: Optional[str] = Field(default=None, alias="Status")


class ConnectionInfosForGetMemoryConnectionInfo(MemoryBaseModel):
    addr_type: Optional[str] = Field(default=None, alias="AddrType")
    auth_key: Optional[str] = Field(default=None, alias="AuthKey")
    auth_type: Optional[str] = Field(default=None, alias="AuthType")
    base_url: Optional[str] = Field(default=None, alias="BaseUrl")
    expire_at: Optional[str] = Field(default=None, alias="ExpireAt")
    status: Optional[str] = Field(default=None, alias="Status")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


class LongTermConfigurationForGetMemoryCollection(MemoryBaseModel):
    strategies: Optional[list[StrategiesForGetMemoryCollection]] = Field(
        default=None, alias="Strategies"
    )


class LongTermConfigurationForUpdateMemoryCollection(MemoryBaseModel):
    strategies: Optional[list[StrategiesForUpdateMemoryCollection]] = Field(
        default=None, alias="Strategies"
    )


class MemoriesForListMemoryCollections(MemoryBaseModel):
    associated_runtimes: Optional[list[AssociatedRuntimesForListMemoryCollections]] = (
        Field(default=None, alias="AssociatedRuntimes")
    )
    create_time: Optional[str] = Field(default=None, alias="CreateTime")
    description: Optional[str] = Field(default=None, alias="Description")
    last_update_time: Optional[str] = Field(default=None, alias="LastUpdateTime")
    managed: Optional[bool] = Field(default=None, alias="Managed")
    memory_id: Optional[str] = Field(default=None, alias="MemoryId")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configuration: Optional[NetworkConfigurationForListMemoryCollections] = (
        Field(default=None, alias="NetworkConfiguration")
    )
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    provider_collection_id: Optional[str] = Field(
        default=None, alias="ProviderCollectionId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")
    region: Optional[str] = Field(default=None, alias="Region")
    status: Optional[str] = Field(default=None, alias="Status")
    strategies_count: Optional[int] = Field(default=None, alias="StrategiesCount")
    tags: Optional[list[TagsForListMemoryCollections]] = Field(
        default=None, alias="Tags"
    )


class NetworkConfigurationForListMemoryCollections(MemoryBaseModel):
    enable_private_network: Optional[bool] = Field(
        default=None, alias="EnablePrivateNetwork"
    )
    enable_public_network: Optional[bool] = Field(
        default=None, alias="EnablePublicNetwork"
    )
    vpc_configuration: Optional[VpcConfigurationForListMemoryCollections] = Field(
        default=None, alias="VpcConfiguration"
    )


class StrategiesForGetMemoryCollection(MemoryBaseModel):
    custom_extraction_instructions: Optional[str] = Field(
        default=None, alias="CustomExtractionInstructions"
    )
    name: Optional[str] = Field(default=None, alias="Name")
    type: Optional[str] = Field(default=None, alias="Type")


class StrategiesForUpdateMemoryCollection(MemoryBaseModel):
    custom_extraction_instructions: Optional[str] = Field(
        default=None, alias="CustomExtractionInstructions"
    )
    name: Optional[str] = Field(default=None, alias="Name")
    type: Optional[str] = Field(default=None, alias="Type")


class TagsForGetMemoryCollection(MemoryBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class TagsForListMemoryCollections(MemoryBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class VpcConfigForGetMemoryCollection(MemoryBaseModel):
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


class VpcConfigurationForListMemoryCollections(MemoryBaseModel):
    security_group_ids: Optional[list[str]] = Field(
        default=None, alias="SecurityGroupIds"
    )
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


# AddMemoryCollection - Request
class CollectionsItemForAddMemoryCollection(MemoryBaseModel):
    description: Optional[str] = Field(default=None, alias="Description")
    name: Optional[str] = Field(default=None, alias="Name")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    provider_collection_id: str = Field(..., alias="ProviderCollectionId")
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")


class AddMemoryCollectionRequest(MemoryBaseModel):
    collections: Optional[list[CollectionsItemForAddMemoryCollection]] = Field(
        default=None, alias="Collections"
    )


# AddMemoryCollection - Response
class AddMemoryCollectionResponse(MemoryBaseModel):
    collections: Optional[list[CollectionsForAddMemoryCollection]] = Field(
        default=None, alias="Collections"
    )


# CreateMemoryCollection - Request
class LongTermForCreateMemoryCollection(MemoryBaseModel):
    strategies: Optional[list[LongTermStrategiesItemForCreateMemoryCollection]] = Field(
        default=None, alias="Strategies"
    )


class VpcForCreateMemoryCollection(MemoryBaseModel):
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: str = Field(..., alias="VpcId")


class LongTermStrategiesItemForCreateMemoryCollection(MemoryBaseModel):
    custom_extraction_instructions: Optional[str] = Field(
        default=None, alias="CustomExtractionInstructions"
    )
    name: str = Field(..., alias="Name")
    type: str = Field(..., alias="Type")


class TagsItemForCreateMemoryCollection(MemoryBaseModel):
    key: str = Field(..., alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class CreateMemoryCollectionRequest(MemoryBaseModel):
    description: Optional[str] = Field(default=None, alias="Description")
    name: str = Field(..., alias="Name")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")
    long_term_configuration: Optional[LongTermForCreateMemoryCollection] = Field(
        default=None, alias="LongTermConfiguration"
    )
    vpc_config: Optional[VpcForCreateMemoryCollection] = Field(
        default=None, alias="VpcConfig"
    )
    tags: Optional[list[TagsItemForCreateMemoryCollection]] = Field(
        default=None, alias="Tags"
    )


# CreateMemoryCollection - Response
class CreateMemoryCollectionResponse(MemoryBaseModel):
    memory_id: Optional[str] = Field(default=None, alias="MemoryId")
    provider_collection_id: Optional[str] = Field(
        default=None, alias="ProviderCollectionId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")
    status: Optional[str] = Field(default=None, alias="Status")


# DeleteMemoryCollection - Request
class DeleteMemoryCollectionRequest(MemoryBaseModel):
    memory_id: str = Field(..., alias="MemoryId")


# DeleteMemoryCollection - Response
class DeleteMemoryCollectionResponse(MemoryBaseModel):
    memory_id: Optional[str] = Field(default=None, alias="MemoryId")
    provider_collection_id: Optional[str] = Field(
        default=None, alias="ProviderCollectionId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")
    status: Optional[str] = Field(default=None, alias="Status")


# GetMemoryCollection - Request
class GetMemoryCollectionRequest(MemoryBaseModel):
    memory_id: str = Field(..., alias="MemoryId")


# GetMemoryCollection - Response
class GetMemoryCollectionResponse(MemoryBaseModel):
    associated_runtimes: Optional[list[AssociatedRuntimesForGetMemoryCollection]] = (
        Field(default=None, alias="AssociatedRuntimes")
    )
    create_time: Optional[str] = Field(default=None, alias="CreateTime")
    description: Optional[str] = Field(default=None, alias="Description")
    last_update_time: Optional[str] = Field(default=None, alias="LastUpdateTime")
    long_term_configuration: Optional[LongTermConfigurationForGetMemoryCollection] = (
        Field(default=None, alias="LongTermConfiguration")
    )
    managed: Optional[bool] = Field(default=None, alias="Managed")
    memory_id: Optional[str] = Field(default=None, alias="MemoryId")
    name: Optional[str] = Field(default=None, alias="Name")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    provider_collection_id: Optional[str] = Field(
        default=None, alias="ProviderCollectionId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")
    region: Optional[str] = Field(default=None, alias="Region")
    status: Optional[str] = Field(default=None, alias="Status")
    tags: Optional[list[TagsForGetMemoryCollection]] = Field(default=None, alias="Tags")
    trn: Optional[str] = Field(default=None, alias="Trn")
    vpc_config: Optional[VpcConfigForGetMemoryCollection] = Field(
        default=None, alias="VpcConfig"
    )


# GetMemoryConnectionInfo - Request
class GetMemoryConnectionInfoRequest(MemoryBaseModel):
    memory_id: str = Field(..., alias="MemoryId")


# GetMemoryConnectionInfo - Response
class GetMemoryConnectionInfoResponse(MemoryBaseModel):
    connection_infos: Optional[list[ConnectionInfosForGetMemoryConnectionInfo]] = Field(
        default=None, alias="ConnectionInfos"
    )
    managed: Optional[bool] = Field(default=None, alias="Managed")
    memory_id: Optional[str] = Field(default=None, alias="MemoryId")
    message: Optional[str] = Field(default=None, alias="Message")
    provider_collection_id: Optional[str] = Field(
        default=None, alias="ProviderCollectionId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")
    status: Optional[str] = Field(default=None, alias="Status")


# ListMemoryCollections - Request
class FiltersItemForListMemoryCollections(MemoryBaseModel):
    name: Optional[str] = Field(default=None, alias="Name")
    name_contains: Optional[str] = Field(default=None, alias="NameContains")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class TagFiltersItemForListMemoryCollections(MemoryBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class ListMemoryCollectionsRequest(MemoryBaseModel):
    create_time_after: Optional[str] = Field(default=None, alias="CreateTimeAfter")
    create_time_before: Optional[str] = Field(default=None, alias="CreateTimeBefore")
    max_results: Optional[int] = Field(default=None, alias="MaxResults")
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    update_time_after: Optional[str] = Field(default=None, alias="UpdateTimeAfter")
    update_time_before: Optional[str] = Field(default=None, alias="UpdateTimeBefore")
    filters: Optional[list[FiltersItemForListMemoryCollections]] = Field(
        default=None, alias="Filters"
    )
    tag_filters: Optional[list[TagFiltersItemForListMemoryCollections]] = Field(
        default=None, alias="TagFilters"
    )


# ListMemoryCollections - Response
class ListMemoryCollectionsResponse(MemoryBaseModel):
    memories: Optional[list[MemoriesForListMemoryCollections]] = Field(
        default=None, alias="Memories"
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")


# UpdateMemoryCollection - Request
class LongTermForUpdateMemoryCollection(MemoryBaseModel):
    strategies: Optional[list[LongTermStrategiesItemForUpdateMemoryCollection]] = Field(
        default=None, alias="Strategies"
    )


class VpcForUpdateMemoryCollection(MemoryBaseModel):
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: str = Field(..., alias="VpcId")


class LongTermStrategiesItemForUpdateMemoryCollection(MemoryBaseModel):
    custom_extraction_instructions: Optional[str] = Field(
        default=None, alias="CustomExtractionInstructions"
    )
    name: str = Field(..., alias="Name")
    type: str = Field(..., alias="Type")


class UpdateMemoryCollectionRequest(MemoryBaseModel):
    description: Optional[str] = Field(default=None, alias="Description")
    memory_id: str = Field(..., alias="MemoryId")
    long_term_configuration: Optional[LongTermForUpdateMemoryCollection] = Field(
        default=None, alias="LongTermConfiguration"
    )
    vpc_config: Optional[VpcForUpdateMemoryCollection] = Field(
        default=None, alias="VpcConfig"
    )


# UpdateMemoryCollection - Response
class UpdateMemoryCollectionResponse(MemoryBaseModel):
    long_term_configuration: Optional[
        LongTermConfigurationForUpdateMemoryCollection
    ] = Field(default=None, alias="LongTermConfiguration")
    memory_id: Optional[str] = Field(default=None, alias="MemoryId")
    provider_collection_id: Optional[str] = Field(
        default=None, alias="ProviderCollectionId"
    )
    provider_type: Optional[str] = Field(default=None, alias="ProviderType")

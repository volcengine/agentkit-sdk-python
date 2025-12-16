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


class ToolsBaseModel(BaseModel):
    """AgentKit auto-generated base model"""

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


# Data Types
class AssociatedRuntimesForGetTool(ToolsBaseModel):
    id: Optional[str] = Field(default=None, alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")


class AuthorizerConfigurationForGetTool(ToolsBaseModel):
    key_auth: Optional[KeyAuthForGetTool] = Field(default=None, alias="KeyAuth")


class AuthorizerConfigurationForListTools(ToolsBaseModel):
    key_auth: Optional[KeyAuthForListTools] = Field(default=None, alias="KeyAuth")


class EnvsForGetTool(ToolsBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class EnvsForListTools(ToolsBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class KeyAuthForGetTool(ToolsBaseModel):
    api_key: Optional[str] = Field(default=None, alias="ApiKey")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    api_key_name: Optional[str] = Field(default=None, alias="ApiKeyName")


class KeyAuthForListTools(ToolsBaseModel):
    api_key: Optional[str] = Field(default=None, alias="ApiKey")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    api_key_name: Optional[str] = Field(default=None, alias="ApiKeyName")


class NetworkConfigurationsForGetTool(ToolsBaseModel):
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    network_type: Optional[str] = Field(default=None, alias="NetworkType")
    vpc_configuration: Optional[VpcConfigurationForGetTool] = Field(
        default=None, alias="VpcConfiguration"
    )


class NetworkConfigurationsForListTools(ToolsBaseModel):
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    network_type: Optional[str] = Field(default=None, alias="NetworkType")
    vpc_configuration: Optional[VpcConfigurationForListTools] = Field(
        default=None, alias="VpcConfiguration"
    )


class SessionInfosForListSessions(ToolsBaseModel):
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    expire_at: Optional[str] = Field(default=None, alias="ExpireAt")
    internal_endpoint: Optional[str] = Field(default=None, alias="InternalEndpoint")
    session_id: Optional[str] = Field(default=None, alias="SessionId")
    status: Optional[str] = Field(default=None, alias="Status")
    tool_type: Optional[str] = Field(default=None, alias="ToolType")
    user_session_id: Optional[str] = Field(default=None, alias="UserSessionId")


class TagsForGetTool(ToolsBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class TagsForListTools(ToolsBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class TlsConfigurationForGetTool(ToolsBaseModel):
    enable_log: Optional[bool] = Field(default=None, alias="EnableLog")
    tls_project_id: Optional[str] = Field(default=None, alias="TlsProjectId")
    tls_topic_id: Optional[str] = Field(default=None, alias="TlsTopicId")


class TlsConfigurationForListTools(ToolsBaseModel):
    enable_log: Optional[bool] = Field(default=None, alias="EnableLog")
    tls_project_id: Optional[str] = Field(default=None, alias="TlsProjectId")
    tls_topic_id: Optional[str] = Field(default=None, alias="TlsTopicId")


class ToolsForListTools(ToolsBaseModel):
    apmplus_enable: Optional[bool] = Field(default=None, alias="ApmplusEnable")
    authorizer_configuration: Optional[AuthorizerConfigurationForListTools] = Field(
        default=None, alias="AuthorizerConfiguration"
    )
    command: Optional[str] = Field(default=None, alias="Command")
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    description: Optional[str] = Field(default=None, alias="Description")
    envs: Optional[list[EnvsForListTools]] = Field(default=None, alias="Envs")
    image_url: Optional[str] = Field(default=None, alias="ImageUrl")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configurations: Optional[list[NetworkConfigurationsForListTools]] = Field(
        default=None, alias="NetworkConfigurations"
    )
    port: Optional[int] = Field(default=None, alias="Port")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    role_name: Optional[str] = Field(default=None, alias="RoleName")
    status: Optional[str] = Field(default=None, alias="Status")
    tags: Optional[list[TagsForListTools]] = Field(default=None, alias="Tags")
    tls_configuration: Optional[TlsConfigurationForListTools] = Field(
        default=None, alias="TlsConfiguration"
    )
    tool_id: Optional[str] = Field(default=None, alias="ToolId")
    tool_type: Optional[str] = Field(default=None, alias="ToolType")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")


class VpcConfigurationForGetTool(ToolsBaseModel):
    security_group_ids: Optional[list[str]] = Field(
        default=None, alias="SecurityGroupIds"
    )
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


class VpcConfigurationForListTools(ToolsBaseModel):
    security_group_ids: Optional[list[str]] = Field(
        default=None, alias="SecurityGroupIds"
    )
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


# CreateSession - Request
class CreateSessionRequest(ToolsBaseModel):
    tool_id: str = Field(..., alias="ToolId")
    ttl: Optional[int] = Field(default=None, alias="Ttl")
    ttl_unit: Optional[str] = Field(default=None, alias="TtlUnit")
    user_session_id: Optional[str] = Field(default=None, alias="UserSessionId")


# CreateSession - Response
class CreateSessionResponse(ToolsBaseModel):
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    internal_endpoint: Optional[str] = Field(default=None, alias="InternalEndpoint")
    session_id: Optional[str] = Field(default=None, alias="SessionId")
    user_session_id: Optional[str] = Field(default=None, alias="UserSessionId")


# CreateTool - Request
class AuthorizerForCreateTool(ToolsBaseModel):
    key_auth: Optional[AuthorizerKeyAuthForCreateTool] = Field(
        default=None, alias="KeyAuth"
    )


class AuthorizerKeyAuthForCreateTool(ToolsBaseModel):
    api_key: Optional[str] = Field(default=None, alias="ApiKey")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    api_key_name: Optional[str] = Field(default=None, alias="ApiKeyName")


class NetworkForCreateTool(ToolsBaseModel):
    vpc_configuration: Optional[NetworkVpcForCreateTool] = Field(
        default=None, alias="VpcConfiguration"
    )
    enable_private_network: Optional[bool] = Field(
        default=None, alias="EnablePrivateNetwork"
    )
    enable_public_network: Optional[bool] = Field(
        default=None, alias="EnablePublicNetwork"
    )


class NetworkVpcForCreateTool(ToolsBaseModel):
    security_group_ids: Optional[list[str]] = Field(
        default=None, alias="SecurityGroupIds"
    )
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: str = Field(..., alias="VpcId")


class TlsForCreateTool(ToolsBaseModel):
    enable_log: bool = Field(..., alias="EnableLog")
    tls_project_id: Optional[str] = Field(default=None, alias="TlsProjectId")
    tls_topic_id: Optional[str] = Field(default=None, alias="TlsTopicId")


class EnvsItemForCreateTool(ToolsBaseModel):
    key: str = Field(..., alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class TagsItemForCreateTool(ToolsBaseModel):
    key: str = Field(..., alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class CreateToolRequest(ToolsBaseModel):
    apmplus_enable: Optional[bool] = Field(default=None, alias="ApmplusEnable")
    command: Optional[str] = Field(default=None, alias="Command")
    description: Optional[str] = Field(default=None, alias="Description")
    image_url: Optional[str] = Field(default=None, alias="ImageUrl")
    name: str = Field(..., alias="Name")
    port: Optional[int] = Field(default=None, alias="Port")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    role_name: Optional[str] = Field(default=None, alias="RoleName")
    tool_type: str = Field(..., alias="ToolType")
    authorizer_configuration: Optional[AuthorizerForCreateTool] = Field(
        default=None, alias="AuthorizerConfiguration"
    )
    network_configuration: Optional[NetworkForCreateTool] = Field(
        default=None, alias="NetworkConfiguration"
    )
    tls_configuration: Optional[TlsForCreateTool] = Field(
        default=None, alias="TlsConfiguration"
    )
    envs: Optional[list[EnvsItemForCreateTool]] = Field(default=None, alias="Envs")
    tags: Optional[list[TagsItemForCreateTool]] = Field(default=None, alias="Tags")


# CreateTool - Response
class CreateToolResponse(ToolsBaseModel):
    tool_id: Optional[str] = Field(default=None, alias="ToolId")


# DeleteSession - Request
class DeleteSessionRequest(ToolsBaseModel):
    session_id: str = Field(..., alias="SessionId")
    tool_id: Optional[str] = Field(default=None, alias="ToolId")


# DeleteSession - Response
class DeleteSessionResponse(ToolsBaseModel):
    session_id: Optional[str] = Field(default=None, alias="SessionId")


# DeleteTool - Request
class DeleteToolRequest(ToolsBaseModel):
    tool_id: Optional[str] = Field(default=None, alias="ToolId")


# DeleteTool - Response
class DeleteToolResponse(ToolsBaseModel):
    tool_id: Optional[str] = Field(default=None, alias="ToolId")


# GetSession - Request
class GetSessionRequest(ToolsBaseModel):
    session_id: str = Field(..., alias="SessionId")
    tool_id: str = Field(..., alias="ToolId")


# GetSession - Response
class GetSessionResponse(ToolsBaseModel):
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    expire_at: Optional[str] = Field(default=None, alias="ExpireAt")
    internal_endpoint: Optional[str] = Field(default=None, alias="InternalEndpoint")
    session_id: Optional[str] = Field(default=None, alias="SessionId")
    status: Optional[str] = Field(default=None, alias="Status")
    tool_type: Optional[str] = Field(default=None, alias="ToolType")
    user_session_id: Optional[str] = Field(default=None, alias="UserSessionId")


# GetSessionLogs - Request
class GetSessionLogsRequest(ToolsBaseModel):
    limit: Optional[int] = Field(default=None, alias="Limit")
    session_id: str = Field(..., alias="SessionId")
    tool_id: str = Field(..., alias="ToolId")


# GetSessionLogs - Response
class GetSessionLogsResponse(ToolsBaseModel):
    logs: Optional[str] = Field(default=None, alias="Logs")


# GetTool - Request
class GetToolRequest(ToolsBaseModel):
    tool_id: str = Field(..., alias="ToolId")


# GetTool - Response
class GetToolResponse(ToolsBaseModel):
    apmplus_enable: Optional[bool] = Field(default=None, alias="ApmplusEnable")
    associated_runtimes: Optional[list[AssociatedRuntimesForGetTool]] = Field(
        default=None, alias="AssociatedRuntimes"
    )
    authorizer_configuration: Optional[AuthorizerConfigurationForGetTool] = Field(
        default=None, alias="AuthorizerConfiguration"
    )
    command: Optional[str] = Field(default=None, alias="Command")
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    description: Optional[str] = Field(default=None, alias="Description")
    envs: Optional[list[EnvsForGetTool]] = Field(default=None, alias="Envs")
    image_url: Optional[str] = Field(default=None, alias="ImageUrl")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configurations: Optional[list[NetworkConfigurationsForGetTool]] = Field(
        default=None, alias="NetworkConfigurations"
    )
    port: Optional[int] = Field(default=None, alias="Port")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    role_name: Optional[str] = Field(default=None, alias="RoleName")
    status: Optional[str] = Field(default=None, alias="Status")
    tags: Optional[list[TagsForGetTool]] = Field(default=None, alias="Tags")
    tls_configuration: Optional[TlsConfigurationForGetTool] = Field(
        default=None, alias="TlsConfiguration"
    )
    tool_id: Optional[str] = Field(default=None, alias="ToolId")
    tool_type: Optional[str] = Field(default=None, alias="ToolType")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")


# ListSessions - Request
class FiltersItemForListSessions(ToolsBaseModel):
    name: Optional[str] = Field(default=None, alias="Name")
    name_contains: Optional[str] = Field(default=None, alias="NameContains")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class ListSessionsRequest(ToolsBaseModel):
    create_time_after: Optional[str] = Field(default=None, alias="CreateTimeAfter")
    create_time_before: Optional[str] = Field(default=None, alias="CreateTimeBefore")
    expire_time_after: Optional[str] = Field(default=None, alias="ExpireTimeAfter")
    expire_time_before: Optional[str] = Field(default=None, alias="ExpireTimeBefore")
    max_results: Optional[int] = Field(default=None, alias="MaxResults")
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    tool_id: str = Field(..., alias="ToolId")
    filters: Optional[list[FiltersItemForListSessions]] = Field(
        default=None, alias="Filters"
    )


# ListSessions - Response
class ListSessionsResponse(ToolsBaseModel):
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    session_infos: Optional[list[SessionInfosForListSessions]] = Field(
        default=None, alias="SessionInfos"
    )


# ListTools - Request
class FiltersItemForListTools(ToolsBaseModel):
    name: Optional[str] = Field(default=None, alias="Name")
    name_contains: Optional[str] = Field(default=None, alias="NameContains")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class TagFiltersItemForListTools(ToolsBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class ListToolsRequest(ToolsBaseModel):
    create_time_after: Optional[str] = Field(default=None, alias="CreateTimeAfter")
    create_time_before: Optional[str] = Field(default=None, alias="CreateTimeBefore")
    max_results: Optional[int] = Field(default=None, alias="MaxResults")
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    update_time_after: Optional[str] = Field(default=None, alias="UpdateTimeAfter")
    update_time_before: Optional[str] = Field(default=None, alias="UpdateTimeBefore")
    filters: Optional[list[FiltersItemForListTools]] = Field(
        default=None, alias="Filters"
    )
    tag_filters: Optional[list[TagFiltersItemForListTools]] = Field(
        default=None, alias="TagFilters"
    )


# ListTools - Response
class ListToolsResponse(ToolsBaseModel):
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    tools: Optional[list[ToolsForListTools]] = Field(default=None, alias="Tools")


# SetSessionTtl - Request
class SetSessionTtlRequest(ToolsBaseModel):
    session_id: str = Field(..., alias="SessionId")
    tool_id: str = Field(..., alias="ToolId")
    ttl: int = Field(..., alias="Ttl")
    ttl_unit: Optional[str] = Field(default=None, alias="TtlUnit")


# SetSessionTtl - Response
class SetSessionTtlResponse(ToolsBaseModel):
    expire_at: Optional[str] = Field(default=None, alias="ExpireAt")
    session_id: Optional[str] = Field(default=None, alias="SessionId")
    tool_id: Optional[str] = Field(default=None, alias="ToolId")


# UpdateTool - Request
class EnvsItemForUpdateTool(ToolsBaseModel):
    key: str = Field(..., alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class UpdateToolRequest(ToolsBaseModel):
    apmplus_enable: Optional[bool] = Field(default=None, alias="ApmplusEnable")
    command: Optional[str] = Field(default=None, alias="Command")
    description: Optional[str] = Field(default=None, alias="Description")
    image_url: Optional[str] = Field(default=None, alias="ImageUrl")
    port: Optional[int] = Field(default=None, alias="Port")
    tool_id: str = Field(..., alias="ToolId")
    tool_type: Optional[str] = Field(default=None, alias="ToolType")
    envs: Optional[list[EnvsItemForUpdateTool]] = Field(default=None, alias="Envs")


# UpdateTool - Response
class UpdateToolResponse(ToolsBaseModel):
    tool_id: Optional[str] = Field(default=None, alias="ToolId")

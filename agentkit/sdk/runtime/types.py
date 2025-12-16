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


class RuntimeTypeBaseModel(BaseModel):
    """AgentKit auto-generated base model"""

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


# Data Types
class AgentKitRuntimeVersionsForListRuntimeVersions(RuntimeTypeBaseModel):
    apmplus_enable: Optional[bool] = Field(default=None, alias="ApmplusEnable")
    artifact_type: Optional[str] = Field(default=None, alias="ArtifactType")
    artifact_url: Optional[str] = Field(default=None, alias="ArtifactUrl")
    authorizer_configuration: Optional[
        AuthorizerConfigurationForListRuntimeVersions
    ] = Field(default=None, alias="AuthorizerConfiguration")
    command: Optional[str] = Field(default=None, alias="Command")
    cpu_milli: Optional[int] = Field(default=None, alias="CpuMilli")
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    description: Optional[str] = Field(default=None, alias="Description")
    envs: Optional[list[EnvsForListRuntimeVersions]] = Field(default=None, alias="Envs")
    memory_mb: Optional[int] = Field(default=None, alias="MemoryMb")
    role_name: Optional[str] = Field(default=None, alias="RoleName")
    runtime_id: Optional[str] = Field(default=None, alias="RuntimeId")
    status: Optional[str] = Field(default=None, alias="Status")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")
    version_number: Optional[int] = Field(default=None, alias="VersionNumber")


class AgentKitRuntimesForListRuntimes(RuntimeTypeBaseModel):
    apmplus_enable: Optional[bool] = Field(default=None, alias="ApmplusEnable")
    artifact_type: Optional[str] = Field(default=None, alias="ArtifactType")
    artifact_url: Optional[str] = Field(default=None, alias="ArtifactUrl")
    authorizer_configuration: Optional[AuthorizerConfigurationForListRuntimes] = Field(
        default=None, alias="AuthorizerConfiguration"
    )
    command: Optional[str] = Field(default=None, alias="Command")
    cpu_milli: Optional[int] = Field(default=None, alias="CpuMilli")
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    current_version_number: Optional[int] = Field(
        default=None, alias="CurrentVersionNumber"
    )
    description: Optional[str] = Field(default=None, alias="Description")
    envs: Optional[list[EnvsForListRuntimes]] = Field(default=None, alias="Envs")
    knowledge_id: Optional[str] = Field(default=None, alias="KnowledgeId")
    mcp_toolset_id: Optional[str] = Field(default=None, alias="MCPToolsetId")
    memory_id: Optional[str] = Field(default=None, alias="MemoryId")
    memory_mb: Optional[int] = Field(default=None, alias="MemoryMb")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configurations: Optional[list[NetworkConfigurationsForListRuntimes]] = (
        Field(default=None, alias="NetworkConfigurations")
    )
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    role_name: Optional[str] = Field(default=None, alias="RoleName")
    runtime_id: Optional[str] = Field(default=None, alias="RuntimeId")
    status: Optional[str] = Field(default=None, alias="Status")
    tags: Optional[list[TagsForListRuntimes]] = Field(default=None, alias="Tags")
    tls_configuration: Optional[TlsConfigurationForListRuntimes] = Field(
        default=None, alias="TlsConfiguration"
    )
    tool_id: Optional[str] = Field(default=None, alias="ToolId")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")


class AuthorizerConfigurationForGetRuntime(RuntimeTypeBaseModel):
    custom_jwt_authorizer: Optional[CustomJwtAuthorizerForGetRuntime] = Field(
        default=None, alias="CustomJwtAuthorizer"
    )
    key_auth: Optional[KeyAuthForGetRuntime] = Field(default=None, alias="KeyAuth")


class AuthorizerConfigurationForGetRuntimeVersion(RuntimeTypeBaseModel):
    custom_jwt_authorizer: Optional[CustomJwtAuthorizerForGetRuntimeVersion] = Field(
        default=None, alias="CustomJwtAuthorizer"
    )
    key_auth: Optional[KeyAuthForGetRuntimeVersion] = Field(
        default=None, alias="KeyAuth"
    )


class AuthorizerConfigurationForListRuntimeVersions(RuntimeTypeBaseModel):
    custom_jwt_authorizer: Optional[CustomJwtAuthorizerForListRuntimeVersions] = Field(
        default=None, alias="CustomJwtAuthorizer"
    )
    key_auth: Optional[KeyAuthForListRuntimeVersions] = Field(
        default=None, alias="KeyAuth"
    )


class AuthorizerConfigurationForListRuntimes(RuntimeTypeBaseModel):
    custom_jwt_authorizer: Optional[CustomJwtAuthorizerForListRuntimes] = Field(
        default=None, alias="CustomJwtAuthorizer"
    )
    key_auth: Optional[KeyAuthForListRuntimes] = Field(default=None, alias="KeyAuth")


class CrRegistriesForListRuntimeCrRegistries(RuntimeTypeBaseModel):
    artifact_url: Optional[str] = Field(default=None, alias="ArtifactUrl")
    description: Optional[str] = Field(default=None, alias="Description")
    framework_type: Optional[str] = Field(default=None, alias="FrameworkType")
    label: Optional[str] = Field(default=None, alias="Label")
    language: Optional[str] = Field(default=None, alias="Language")
    name: Optional[str] = Field(default=None, alias="Name")
    tag: Optional[str] = Field(default=None, alias="Tag")


class CustomJwtAuthorizerForGetRuntime(RuntimeTypeBaseModel):
    allowed_clients: Optional[list[str]] = Field(default=None, alias="AllowedClients")
    discovery_url: Optional[str] = Field(default=None, alias="DiscoveryUrl")


class CustomJwtAuthorizerForGetRuntimeVersion(RuntimeTypeBaseModel):
    allowed_clients: Optional[list[str]] = Field(default=None, alias="AllowedClients")
    discovery_url: Optional[str] = Field(default=None, alias="DiscoveryUrl")


class CustomJwtAuthorizerForListRuntimeVersions(RuntimeTypeBaseModel):
    allowed_clients: Optional[list[str]] = Field(default=None, alias="AllowedClients")
    discovery_url: Optional[str] = Field(default=None, alias="DiscoveryUrl")


class CustomJwtAuthorizerForListRuntimes(RuntimeTypeBaseModel):
    allowed_clients: Optional[list[str]] = Field(default=None, alias="AllowedClients")
    discovery_url: Optional[str] = Field(default=None, alias="DiscoveryUrl")


class EnvsForGetRuntime(RuntimeTypeBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class EnvsForGetRuntimeVersion(RuntimeTypeBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class EnvsForListRuntimeVersions(RuntimeTypeBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class EnvsForListRuntimes(RuntimeTypeBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class InstanceItemsForListRuntimeInstances(RuntimeTypeBaseModel):
    create_time: Optional[str] = Field(default=None, alias="CreateTime")
    function_id: Optional[str] = Field(default=None, alias="FunctionId")
    instance_name: Optional[str] = Field(default=None, alias="InstanceName")
    instance_status: Optional[str] = Field(default=None, alias="InstanceStatus")
    revision_number: Optional[int] = Field(default=None, alias="RevisionNumber")


class KeyAuthForGetRuntime(RuntimeTypeBaseModel):
    api_key: Optional[str] = Field(default=None, alias="ApiKey")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    api_key_name: Optional[str] = Field(default=None, alias="ApiKeyName")


class KeyAuthForGetRuntimeVersion(RuntimeTypeBaseModel):
    api_key: Optional[str] = Field(default=None, alias="ApiKey")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    api_key_name: Optional[str] = Field(default=None, alias="ApiKeyName")


class KeyAuthForListRuntimeVersions(RuntimeTypeBaseModel):
    api_key: Optional[str] = Field(default=None, alias="ApiKey")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    api_key_name: Optional[str] = Field(default=None, alias="ApiKeyName")


class KeyAuthForListRuntimes(RuntimeTypeBaseModel):
    api_key: Optional[str] = Field(default=None, alias="ApiKey")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    api_key_name: Optional[str] = Field(default=None, alias="ApiKeyName")


class NetworkConfigurationsForGetRuntime(RuntimeTypeBaseModel):
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    network_type: Optional[str] = Field(default=None, alias="NetworkType")
    vpc_configuration: Optional[VpcConfigurationForGetRuntime] = Field(
        default=None, alias="VpcConfiguration"
    )


class NetworkConfigurationsForListRuntimes(RuntimeTypeBaseModel):
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    network_type: Optional[str] = Field(default=None, alias="NetworkType")
    vpc_configuration: Optional[VpcConfigurationForListRuntimes] = Field(
        default=None, alias="VpcConfiguration"
    )


class TagsForGetRuntime(RuntimeTypeBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class TagsForGetRuntimeVersion(RuntimeTypeBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class TagsForListRuntimes(RuntimeTypeBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class TlsConfigurationForGetRuntime(RuntimeTypeBaseModel):
    enable_log: Optional[bool] = Field(default=None, alias="EnableLog")
    tls_project_id: Optional[str] = Field(default=None, alias="TlsProjectId")
    tls_topic_id: Optional[str] = Field(default=None, alias="TlsTopicId")


class TlsConfigurationForListRuntimes(RuntimeTypeBaseModel):
    enable_log: Optional[bool] = Field(default=None, alias="EnableLog")
    tls_project_id: Optional[str] = Field(default=None, alias="TlsProjectId")
    tls_topic_id: Optional[str] = Field(default=None, alias="TlsTopicId")


class VpcConfigurationForGetRuntime(RuntimeTypeBaseModel):
    security_group_ids: Optional[list[str]] = Field(
        default=None, alias="SecurityGroupIds"
    )
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


class VpcConfigurationForListRuntimes(RuntimeTypeBaseModel):
    security_group_ids: Optional[list[str]] = Field(
        default=None, alias="SecurityGroupIds"
    )
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


# CreateRuntime - Request
class AuthorizerForCreateRuntime(RuntimeTypeBaseModel):
    custom_jwt_authorizer: Optional[AuthorizerCustomJwtAuthorizerForCreateRuntime] = (
        Field(default=None, alias="CustomJwtAuthorizer")
    )
    key_auth: Optional[AuthorizerKeyAuthForCreateRuntime] = Field(
        default=None, alias="KeyAuth"
    )


class AuthorizerCustomJwtAuthorizerForCreateRuntime(RuntimeTypeBaseModel):
    allowed_clients: Optional[list[str]] = Field(default=None, alias="AllowedClients")
    discovery_url: str = Field(..., alias="DiscoveryUrl")


class AuthorizerKeyAuthForCreateRuntime(RuntimeTypeBaseModel):
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    api_key_name: Optional[str] = Field(default=None, alias="ApiKeyName")


class NetworkForCreateRuntime(RuntimeTypeBaseModel):
    vpc_configuration: Optional[NetworkVpcForCreateRuntime] = Field(
        default=None, alias="VpcConfiguration"
    )
    enable_private_network: Optional[bool] = Field(
        default=None, alias="EnablePrivateNetwork"
    )
    enable_public_network: Optional[bool] = Field(
        default=None, alias="EnablePublicNetwork"
    )


class NetworkVpcForCreateRuntime(RuntimeTypeBaseModel):
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: str = Field(..., alias="VpcId")


class TlsForCreateRuntime(RuntimeTypeBaseModel):
    enable_log: bool = Field(..., alias="EnableLog")
    tls_project_id: Optional[str] = Field(default=None, alias="TlsProjectId")
    tls_topic_id: Optional[str] = Field(default=None, alias="TlsTopicId")


class EnvsItemForCreateRuntime(RuntimeTypeBaseModel):
    key: str = Field(..., alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class TagsItemForCreateRuntime(RuntimeTypeBaseModel):
    key: str = Field(..., alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class CreateRuntimeRequest(RuntimeTypeBaseModel):
    apmplus_enable: Optional[bool] = Field(default=None, alias="ApmplusEnable")
    artifact_type: str = Field(..., alias="ArtifactType")
    artifact_url: str = Field(..., alias="ArtifactUrl")
    client_token: Optional[str] = Field(default=None, alias="ClientToken")
    cpu_milli: Optional[int] = Field(default=None, alias="CpuMilli")
    description: Optional[str] = Field(default=None, alias="Description")
    knowledge_id: Optional[str] = Field(default=None, alias="KnowledgeId")
    mcp_toolset_id: Optional[str] = Field(default=None, alias="MCPToolsetId")
    max_concurrency: Optional[int] = Field(default=None, alias="MaxConcurrency")
    max_instance: Optional[int] = Field(default=None, alias="MaxInstance")
    memory_id: Optional[str] = Field(default=None, alias="MemoryId")
    memory_mb: Optional[int] = Field(default=None, alias="MemoryMb")
    min_instance: Optional[int] = Field(default=None, alias="MinInstance")
    model_agent_name: Optional[str] = Field(default=None, alias="ModelAgentName")
    name: str = Field(..., alias="Name")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    role_name: str = Field(..., alias="RoleName")
    tool_id: Optional[str] = Field(default=None, alias="ToolId")
    authorizer_configuration: Optional[AuthorizerForCreateRuntime] = Field(
        default=None, alias="AuthorizerConfiguration"
    )
    network_configuration: Optional[NetworkForCreateRuntime] = Field(
        default=None, alias="NetworkConfiguration"
    )
    tls_configuration: Optional[TlsForCreateRuntime] = Field(
        default=None, alias="TlsConfiguration"
    )
    envs: Optional[list[EnvsItemForCreateRuntime]] = Field(default=None, alias="Envs")
    tags: Optional[list[TagsItemForCreateRuntime]] = Field(default=None, alias="Tags")


# CreateRuntime - Response
class CreateRuntimeResponse(RuntimeTypeBaseModel):
    runtime_id: Optional[str] = Field(default=None, alias="RuntimeId")


# DeleteRuntime - Request
class DeleteRuntimeRequest(RuntimeTypeBaseModel):
    runtime_id: str = Field(..., alias="RuntimeId")


# DeleteRuntime - Response
class DeleteRuntimeResponse(RuntimeTypeBaseModel):
    runtime_id: Optional[str] = Field(default=None, alias="RuntimeId")


# GetRuntime - Request
class GetRuntimeRequest(RuntimeTypeBaseModel):
    runtime_id: str = Field(..., alias="RuntimeId")


# GetRuntime - Response
class GetRuntimeResponse(RuntimeTypeBaseModel):
    apmplus_enable: Optional[bool] = Field(default=None, alias="ApmplusEnable")
    artifact_type: Optional[str] = Field(default=None, alias="ArtifactType")
    artifact_url: Optional[str] = Field(default=None, alias="ArtifactUrl")
    authorizer_configuration: Optional[AuthorizerConfigurationForGetRuntime] = Field(
        default=None, alias="AuthorizerConfiguration"
    )
    command: Optional[str] = Field(default=None, alias="Command")
    cpu_milli: Optional[int] = Field(default=None, alias="CpuMilli")
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    current_version_number: Optional[int] = Field(
        default=None, alias="CurrentVersionNumber"
    )
    description: Optional[str] = Field(default=None, alias="Description")
    envs: Optional[list[EnvsForGetRuntime]] = Field(default=None, alias="Envs")
    failed_log_file_url: Optional[str] = Field(default=None, alias="FailedLogFileUrl")
    knowledge_id: Optional[str] = Field(default=None, alias="KnowledgeId")
    mcp_toolset_id: Optional[str] = Field(default=None, alias="MCPToolsetId")
    max_concurrency: Optional[int] = Field(default=None, alias="MaxConcurrency")
    max_instance: Optional[int] = Field(default=None, alias="MaxInstance")
    memory_id: Optional[str] = Field(default=None, alias="MemoryId")
    memory_mb: Optional[int] = Field(default=None, alias="MemoryMb")
    min_instance: Optional[int] = Field(default=None, alias="MinInstance")
    model_agent_name: Optional[str] = Field(default=None, alias="ModelAgentName")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configurations: Optional[list[NetworkConfigurationsForGetRuntime]] = Field(
        default=None, alias="NetworkConfigurations"
    )
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    role_name: Optional[str] = Field(default=None, alias="RoleName")
    runtime_id: Optional[str] = Field(default=None, alias="RuntimeId")
    status: Optional[str] = Field(default=None, alias="Status")
    status_message: Optional[str] = Field(default=None, alias="StatusMessage")
    tags: Optional[list[TagsForGetRuntime]] = Field(default=None, alias="Tags")
    tls_configuration: Optional[TlsConfigurationForGetRuntime] = Field(
        default=None, alias="TlsConfiguration"
    )
    tool_id: Optional[str] = Field(default=None, alias="ToolId")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")


# GetRuntimeCozeToken - Request
class GetRuntimeCozeTokenRequest(RuntimeTypeBaseModel):
    runtime_id: str = Field(..., alias="RuntimeId")


# GetRuntimeCozeToken - Response
class GetRuntimeCozeTokenResponse(RuntimeTypeBaseModel):
    jwt_token: Optional[str] = Field(default=None, alias="JwtToken")


# GetRuntimeInstanceLogs - Request
class GetRuntimeInstanceLogsRequest(RuntimeTypeBaseModel):
    function_id: str = Field(..., alias="FunctionId")
    instance_name: str = Field(..., alias="InstanceName")
    limit: Optional[int] = Field(default=None, alias="Limit")


# GetRuntimeInstanceLogs - Response
class GetRuntimeInstanceLogsResponse(RuntimeTypeBaseModel):
    logs: Optional[str] = Field(default=None, alias="Logs")


# GetRuntimeVersion - Request
class GetRuntimeVersionRequest(RuntimeTypeBaseModel):
    runtime_id: str = Field(..., alias="RuntimeId")
    version_number: Optional[int] = Field(default=None, alias="VersionNumber")


# GetRuntimeVersion - Response
class GetRuntimeVersionResponse(RuntimeTypeBaseModel):
    apmplus_enable: Optional[bool] = Field(default=None, alias="ApmplusEnable")
    artifact_type: Optional[str] = Field(default=None, alias="ArtifactType")
    artifact_url: Optional[str] = Field(default=None, alias="ArtifactUrl")
    authorizer_configuration: Optional[AuthorizerConfigurationForGetRuntimeVersion] = (
        Field(default=None, alias="AuthorizerConfiguration")
    )
    command: Optional[str] = Field(default=None, alias="Command")
    cpu_milli: Optional[int] = Field(default=None, alias="CpuMilli")
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    description: Optional[str] = Field(default=None, alias="Description")
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    envs: Optional[list[EnvsForGetRuntimeVersion]] = Field(default=None, alias="Envs")
    max_concurrency: Optional[int] = Field(default=None, alias="MaxConcurrency")
    memory_mb: Optional[int] = Field(default=None, alias="MemoryMb")
    model_agent_name: Optional[str] = Field(default=None, alias="ModelAgentName")
    name: Optional[str] = Field(default=None, alias="Name")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    role_name: Optional[str] = Field(default=None, alias="RoleName")
    runtime_id: Optional[str] = Field(default=None, alias="RuntimeId")
    status: Optional[str] = Field(default=None, alias="Status")
    tags: Optional[list[TagsForGetRuntimeVersion]] = Field(default=None, alias="Tags")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")
    version_number: Optional[int] = Field(default=None, alias="VersionNumber")


# ListRuntimeCrRegistries - Request
class ListRuntimeCrRegistriesRequest(RuntimeTypeBaseModel):
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")


# ListRuntimeCrRegistries - Response
class ListRuntimeCrRegistriesResponse(RuntimeTypeBaseModel):
    cr_registries: Optional[list[CrRegistriesForListRuntimeCrRegistries]] = Field(
        default=None, alias="CrRegistries"
    )
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")


# ListRuntimeInstances - Request
class ListRuntimeInstancesRequest(RuntimeTypeBaseModel):
    runtime_id: str = Field(..., alias="RuntimeId")


# ListRuntimeInstances - Response
class ListRuntimeInstancesResponse(RuntimeTypeBaseModel):
    instance_items: Optional[list[InstanceItemsForListRuntimeInstances]] = Field(
        default=None, alias="InstanceItems"
    )
    running_instance: Optional[int] = Field(default=None, alias="RunningInstance")


# ListRuntimeVersions - Request
class ListRuntimeVersionsRequest(RuntimeTypeBaseModel):
    max_results: Optional[int] = Field(default=None, alias="MaxResults")
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    runtime_id: str = Field(..., alias="RuntimeId")


# ListRuntimeVersions - Response
class ListRuntimeVersionsResponse(RuntimeTypeBaseModel):
    agent_kit_runtime_versions: Optional[
        list[AgentKitRuntimeVersionsForListRuntimeVersions]
    ] = Field(default=None, alias="AgentKitRuntimeVersions")
    next_token: Optional[str] = Field(default=None, alias="NextToken")


# ListRuntimes - Request
class FiltersItemForListRuntimes(RuntimeTypeBaseModel):
    name: Optional[str] = Field(default=None, alias="Name")
    name_contains: Optional[str] = Field(default=None, alias="NameContains")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class TagFiltersItemForListRuntimes(RuntimeTypeBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class ListRuntimesRequest(RuntimeTypeBaseModel):
    create_time_after: Optional[str] = Field(default=None, alias="CreateTimeAfter")
    create_time_before: Optional[str] = Field(default=None, alias="CreateTimeBefore")
    max_results: Optional[int] = Field(default=None, alias="MaxResults")
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    sort_by: Optional[str] = Field(default=None, alias="SortBy")
    sort_order: Optional[str] = Field(default=None, alias="SortOrder")
    update_time_after: Optional[str] = Field(default=None, alias="UpdateTimeAfter")
    update_time_before: Optional[str] = Field(default=None, alias="UpdateTimeBefore")
    filters: Optional[list[FiltersItemForListRuntimes]] = Field(
        default=None, alias="Filters"
    )
    tag_filters: Optional[list[TagFiltersItemForListRuntimes]] = Field(
        default=None, alias="TagFilters"
    )


# ListRuntimes - Response
class ListRuntimesResponse(RuntimeTypeBaseModel):
    agent_kit_runtimes: Optional[list[AgentKitRuntimesForListRuntimes]] = Field(
        default=None, alias="AgentKitRuntimes"
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")


# ReleaseRuntime - Request
class ReleaseRuntimeRequest(RuntimeTypeBaseModel):
    runtime_id: str = Field(..., alias="RuntimeId")
    version_number: Optional[int] = Field(default=None, alias="VersionNumber")


# ReleaseRuntime - Response
class ReleaseRuntimeResponse(RuntimeTypeBaseModel):
    runtime_id: Optional[str] = Field(default=None, alias="RuntimeId")


# UpdateRuntime - Request
class EnvsItemForUpdateRuntime(RuntimeTypeBaseModel):
    key: str = Field(..., alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class TagsItemForUpdateRuntime(RuntimeTypeBaseModel):
    key: str = Field(..., alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class UpdateRuntimeRequest(RuntimeTypeBaseModel):
    apmplus_enable: Optional[bool] = Field(default=None, alias="ApmplusEnable")
    artifact_type: Optional[str] = Field(default=None, alias="ArtifactType")
    artifact_url: Optional[str] = Field(default=None, alias="ArtifactUrl")
    cpu_milli: Optional[int] = Field(default=None, alias="CpuMilli")
    description: Optional[str] = Field(default=None, alias="Description")
    knowledge_id: Optional[str] = Field(default=None, alias="KnowledgeId")
    mcp_toolset_id: Optional[str] = Field(default=None, alias="MCPToolsetId")
    max_concurrency: Optional[int] = Field(default=None, alias="MaxConcurrency")
    max_instance: Optional[int] = Field(default=None, alias="MaxInstance")
    memory_id: Optional[str] = Field(default=None, alias="MemoryId")
    memory_mb: Optional[int] = Field(default=None, alias="MemoryMb")
    min_instance: Optional[int] = Field(default=None, alias="MinInstance")
    model_agent_name: Optional[str] = Field(default=None, alias="ModelAgentName")
    release_enable: Optional[bool] = Field(default=None, alias="ReleaseEnable")
    runtime_id: str = Field(..., alias="RuntimeId")
    tool_id: Optional[str] = Field(default=None, alias="ToolId")
    envs: Optional[list[EnvsItemForUpdateRuntime]] = Field(default=None, alias="Envs")
    tags: Optional[list[TagsItemForUpdateRuntime]] = Field(default=None, alias="Tags")


# UpdateRuntime - Response
class UpdateRuntimeResponse(RuntimeTypeBaseModel):
    runtime_id: Optional[str] = Field(default=None, alias="RuntimeId")

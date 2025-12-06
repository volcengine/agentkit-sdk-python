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


class MCPBaseModel(BaseModel):
    """AgentKit auto-generated base model"""

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


# Data Types
class CustomJwtAuthorizerForListMCPToolsets(MCPBaseModel):
    allowed_clients: Optional[list[str]] = Field(default=None, alias="AllowedClients")
    discovery_url: Optional[str] = Field(default=None, alias="DiscoveryUrl")


class ApiKeysForListMCPToolsets(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    name: Optional[str] = Field(default=None, alias="Name")


class KeyAuthForListMCPToolsets(MCPBaseModel):
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    api_keys: Optional[list[ApiKeysForListMCPToolsets]] = Field(
        default=None, alias="ApiKeys"
    )
    parameter: Optional[str] = Field(default=None, alias="Parameter")


class AuthorizerForListMCPToolsets(MCPBaseModel):
    custom_jwt_authorizer: Optional[CustomJwtAuthorizerForListMCPToolsets] = Field(
        default=None, alias="CustomJwtAuthorizer"
    )
    key_auth: Optional[KeyAuthForListMCPToolsets] = Field(default=None, alias="KeyAuth")


class AuthorizerConfigurationForListMCPToolsets(MCPBaseModel):
    authorizer: Optional[AuthorizerForListMCPToolsets] = Field(
        default=None, alias="Authorizer"
    )
    authorizer_type: Optional[str] = Field(default=None, alias="AuthorizerType")


class VpcConfigurationForListMCPToolsets(MCPBaseModel):
    security_group_ids: Optional[list[str]] = Field(
        default=None, alias="SecurityGroupIds"
    )
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


class NetworkConfigurationsForListMCPToolsets(MCPBaseModel):
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    network_type: Optional[str] = Field(default=None, alias="NetworkType")
    vpc_configuration: Optional[VpcConfigurationForListMCPToolsets] = Field(
        default=None, alias="VpcConfiguration"
    )


class ProtocolConfigurationForListMCPToolsets(MCPBaseModel):
    protocol_convert_configuration: Optional[str] = Field(
        default=None, alias="ProtocolConvertConfiguration"
    )


class MCPServicesForListMCPToolsets(MCPBaseModel):
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    mcp_service_id: Optional[str] = Field(default=None, alias="MCPServiceId")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configurations: Optional[list[NetworkConfigurationsForListMCPToolsets]] = (
        Field(default=None, alias="NetworkConfigurations")
    )
    path: Optional[str] = Field(default=None, alias="Path")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    protocol_configuration: Optional[ProtocolConfigurationForListMCPToolsets] = Field(
        default=None, alias="ProtocolConfiguration"
    )
    protocol_type: Optional[str] = Field(default=None, alias="ProtocolType")
    status: Optional[str] = Field(default=None, alias="Status")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")


class TagsForListMCPToolsets(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class MCPToolsetsForListMCPToolsets(MCPBaseModel):
    authorizer_configuration: Optional[AuthorizerConfigurationForListMCPToolsets] = (
        Field(default=None, alias="AuthorizerConfiguration")
    )
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    mcp_services: Optional[list[MCPServicesForListMCPToolsets]] = Field(
        default=None, alias="MCPServices"
    )
    mcp_toolset_id: Optional[str] = Field(default=None, alias="MCPToolsetId")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configurations: Optional[list[NetworkConfigurationsForListMCPToolsets]] = (
        Field(default=None, alias="NetworkConfigurations")
    )
    path: Optional[str] = Field(default=None, alias="Path")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    status: Optional[str] = Field(default=None, alias="Status")
    tags: Optional[list[TagsForListMCPToolsets]] = Field(default=None, alias="Tags")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")


class MCPServiceToolsForListMCPTools(MCPBaseModel):
    mcp_service_id: Optional[str] = Field(default=None, alias="MCPServiceId")
    tools: Optional[str] = Field(default=None, alias="Tools")


class AssociatedRuntimesForGetMCPToolset(MCPBaseModel):
    id: Optional[str] = Field(default=None, alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")


class CustomJwtAuthorizerForGetMCPToolset(MCPBaseModel):
    allowed_clients: Optional[list[str]] = Field(default=None, alias="AllowedClients")
    discovery_url: Optional[str] = Field(default=None, alias="DiscoveryUrl")


class ApiKeysForGetMCPToolset(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    name: Optional[str] = Field(default=None, alias="Name")


class KeyAuthForGetMCPToolset(MCPBaseModel):
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    api_keys: Optional[list[ApiKeysForGetMCPToolset]] = Field(
        default=None, alias="ApiKeys"
    )
    parameter: Optional[str] = Field(default=None, alias="Parameter")


class AuthorizerForGetMCPToolset(MCPBaseModel):
    custom_jwt_authorizer: Optional[CustomJwtAuthorizerForGetMCPToolset] = Field(
        default=None, alias="CustomJwtAuthorizer"
    )
    key_auth: Optional[KeyAuthForGetMCPToolset] = Field(default=None, alias="KeyAuth")


class AuthorizerConfigurationForGetMCPToolset(MCPBaseModel):
    authorizer: Optional[AuthorizerForGetMCPToolset] = Field(
        default=None, alias="Authorizer"
    )
    authorizer_type: Optional[str] = Field(default=None, alias="AuthorizerType")


class VpcConfigurationForGetMCPToolset(MCPBaseModel):
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


class NetworkConfigurationsForGetMCPToolset(MCPBaseModel):
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    network_type: Optional[str] = Field(default=None, alias="NetworkType")
    vpc_configuration: Optional[VpcConfigurationForGetMCPToolset] = Field(
        default=None, alias="VpcConfiguration"
    )


class ProtocolConfigurationForGetMCPToolset(MCPBaseModel):
    protocol_convert_configuration: Optional[str] = Field(
        default=None, alias="ProtocolConvertConfiguration"
    )


class TagsForGetMCPToolset(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class MCPServicesForGetMCPToolset(MCPBaseModel):
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    mcp_service_id: Optional[str] = Field(default=None, alias="MCPServiceId")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configurations: Optional[list[NetworkConfigurationsForGetMCPToolset]] = (
        Field(default=None, alias="NetworkConfigurations")
    )
    path: Optional[str] = Field(default=None, alias="Path")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    protocol_configuration: Optional[ProtocolConfigurationForGetMCPToolset] = Field(
        default=None, alias="ProtocolConfiguration"
    )
    protocol_type: Optional[str] = Field(default=None, alias="ProtocolType")
    status: Optional[str] = Field(default=None, alias="Status")
    tags: Optional[list[TagsForGetMCPToolset]] = Field(default=None, alias="Tags")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")


class MCPToolsetForGetMCPToolset(MCPBaseModel):
    associated_runtimes: Optional[list[AssociatedRuntimesForGetMCPToolset]] = Field(
        default=None, alias="AssociatedRuntimes"
    )
    authorizer_configuration: Optional[AuthorizerConfigurationForGetMCPToolset] = Field(
        default=None, alias="AuthorizerConfiguration"
    )
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    mcp_services: Optional[list[MCPServicesForGetMCPToolset]] = Field(
        default=None, alias="MCPServices"
    )
    mcp_toolset_id: Optional[str] = Field(default=None, alias="MCPToolsetId")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configurations: Optional[list[NetworkConfigurationsForGetMCPToolset]] = (
        Field(default=None, alias="NetworkConfigurations")
    )
    path: Optional[str] = Field(default=None, alias="Path")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    status: Optional[str] = Field(default=None, alias="Status")
    tags: Optional[list[TagsForGetMCPToolset]] = Field(default=None, alias="Tags")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")


class VpcConfigurationForListMCPServices(MCPBaseModel):
    security_group_ids: Optional[list[str]] = Field(
        default=None, alias="SecurityGroupIds"
    )
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


class NetworkConfigurationsForListMCPServices(MCPBaseModel):
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    network_type: Optional[str] = Field(default=None, alias="NetworkType")
    vpc_configuration: Optional[VpcConfigurationForListMCPServices] = Field(
        default=None, alias="VpcConfiguration"
    )


class ProtocolConfigurationForListMCPServices(MCPBaseModel):
    protocol_convert_configuration: Optional[str] = Field(
        default=None, alias="ProtocolConvertConfiguration"
    )


class TagsForListMCPServices(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class MCPServicesForListMCPServices(MCPBaseModel):
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    mcp_service_id: Optional[str] = Field(default=None, alias="MCPServiceId")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configurations: Optional[list[NetworkConfigurationsForListMCPServices]] = (
        Field(default=None, alias="NetworkConfigurations")
    )
    path: Optional[str] = Field(default=None, alias="Path")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    protocol_configuration: Optional[ProtocolConfigurationForListMCPServices] = Field(
        default=None, alias="ProtocolConfiguration"
    )
    protocol_type: Optional[str] = Field(default=None, alias="ProtocolType")
    status: Optional[str] = Field(default=None, alias="Status")
    tags: Optional[list[TagsForListMCPServices]] = Field(default=None, alias="Tags")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")


class CustomConfigurationForGetMCPService(MCPBaseModel):
    domain: Optional[str] = Field(default=None, alias="Domain")
    port: Optional[int] = Field(default=None, alias="Port")
    protocol_type: Optional[str] = Field(default=None, alias="ProtocolType")


class EnvsForGetMCPService(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class PrivatePackageForGetMCPService(MCPBaseModel):
    command: Optional[str] = Field(default=None, alias="Command")
    envs: Optional[list[EnvsForGetMCPService]] = Field(default=None, alias="Envs")
    image_url: Optional[str] = Field(default=None, alias="ImageUrl")


class PublicPackageForGetMCPService(MCPBaseModel):
    mcp_type: Optional[str] = Field(default=None, alias="McpType")
    package_manager_type: Optional[str] = Field(
        default=None, alias="PackageManagerType"
    )
    raw_config: Optional[str] = Field(default=None, alias="RawConfig")


class CustomMcpConfigurationForGetMCPService(MCPBaseModel):
    function_id: Optional[str] = Field(default=None, alias="FunctionId")
    function_name: Optional[str] = Field(default=None, alias="FunctionName")
    private_package: Optional[PrivatePackageForGetMCPService] = Field(
        default=None, alias="PrivatePackage"
    )
    public_package: Optional[PublicPackageForGetMCPService] = Field(
        default=None, alias="PublicPackage"
    )


class FunctionConfigurationForGetMCPService(MCPBaseModel):
    function_id: Optional[str] = Field(default=None, alias="FunctionId")
    function_name: Optional[str] = Field(default=None, alias="FunctionName")


class BackendConfigurationForGetMCPService(MCPBaseModel):
    custom_configuration: Optional[CustomConfigurationForGetMCPService] = Field(
        default=None, alias="CustomConfiguration"
    )
    custom_mcp_configuration: Optional[CustomMcpConfigurationForGetMCPService] = Field(
        default=None, alias="CustomMcpConfiguration"
    )
    function_configuration: Optional[FunctionConfigurationForGetMCPService] = Field(
        default=None, alias="FunctionConfiguration"
    )


class CustomJwtAuthorizerForGetMCPService(MCPBaseModel):
    allowed_clients: Optional[list[str]] = Field(default=None, alias="AllowedClients")
    discovery_url: Optional[str] = Field(default=None, alias="DiscoveryUrl")


class ApiKeysForGetMCPService(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    name: Optional[str] = Field(default=None, alias="Name")


class KeyAuthForGetMCPService(MCPBaseModel):
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    api_keys: Optional[list[ApiKeysForGetMCPService]] = Field(
        default=None, alias="ApiKeys"
    )
    parameter: Optional[str] = Field(default=None, alias="Parameter")


class AuthorizerForGetMCPService(MCPBaseModel):
    custom_jwt_authorizer: Optional[CustomJwtAuthorizerForGetMCPService] = Field(
        default=None, alias="CustomJwtAuthorizer"
    )
    key_auth: Optional[KeyAuthForGetMCPService] = Field(default=None, alias="KeyAuth")


class InboundAuthorizerConfigurationForGetMCPService(MCPBaseModel):
    authorizer: Optional[AuthorizerForGetMCPService] = Field(
        default=None, alias="Authorizer"
    )
    authorizer_type: Optional[str] = Field(default=None, alias="AuthorizerType")


class VpcConfigurationForGetMCPService(MCPBaseModel):
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")
    vpc_id: Optional[str] = Field(default=None, alias="VpcId")


class NetworkConfigurationsForGetMCPService(MCPBaseModel):
    endpoint: Optional[str] = Field(default=None, alias="Endpoint")
    network_type: Optional[str] = Field(default=None, alias="NetworkType")
    vpc_configuration: Optional[VpcConfigurationForGetMCPService] = Field(
        default=None, alias="VpcConfiguration"
    )


class OutboundAuthorizerConfigurationForGetMCPService(MCPBaseModel):
    authorizer: Optional[AuthorizerForGetMCPService] = Field(
        default=None, alias="Authorizer"
    )
    authorizer_type: Optional[str] = Field(default=None, alias="AuthorizerType")


class ProtocolConfigurationForGetMCPService(MCPBaseModel):
    protocol_convert_configuration: Optional[str] = Field(
        default=None, alias="ProtocolConvertConfiguration"
    )


class TagsForGetMCPService(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class MCPServiceForGetMCPService(MCPBaseModel):
    backend_configuration: Optional[BackendConfigurationForGetMCPService] = Field(
        default=None, alias="BackendConfiguration"
    )
    backend_type: Optional[str] = Field(default=None, alias="BackendType")
    created_at: Optional[str] = Field(default=None, alias="CreatedAt")
    inbound_authorizer_configuration: Optional[
        InboundAuthorizerConfigurationForGetMCPService
    ] = Field(default=None, alias="InboundAuthorizerConfiguration")
    mcp_service_id: Optional[str] = Field(default=None, alias="MCPServiceId")
    name: Optional[str] = Field(default=None, alias="Name")
    network_configurations: Optional[list[NetworkConfigurationsForGetMCPService]] = (
        Field(default=None, alias="NetworkConfigurations")
    )
    outbound_authorizer_configuration: Optional[
        OutboundAuthorizerConfigurationForGetMCPService
    ] = Field(default=None, alias="OutboundAuthorizerConfiguration")
    path: Optional[str] = Field(default=None, alias="Path")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    protocol_configuration: Optional[ProtocolConfigurationForGetMCPService] = Field(
        default=None, alias="ProtocolConfiguration"
    )
    protocol_type: Optional[str] = Field(default=None, alias="ProtocolType")
    status: Optional[str] = Field(default=None, alias="Status")
    tags: Optional[list[TagsForGetMCPService]] = Field(default=None, alias="Tags")
    updated_at: Optional[str] = Field(default=None, alias="UpdatedAt")


# UpdateMCPToolset - Request
class AuthorizerForUpdateMCPToolset(MCPBaseModel):
    authorizer: Optional[AuthorizerAuthorizerForUpdateMCPToolset] = Field(
        default=None, alias="Authorizer"
    )
    authorizer_type: str = Field(..., alias="AuthorizerType")


class AuthorizerAuthorizerForUpdateMCPToolset(MCPBaseModel):
    key_auth: Optional[AuthorizerAuthorizerKeyAuthForUpdateMCPToolset] = Field(
        default=None, alias="KeyAuth"
    )


class AuthorizerAuthorizerKeyAuthForUpdateMCPToolset(MCPBaseModel):
    api_keys: Optional[
        list[AuthorizerAuthorizerKeyAuthApiKeysItemForUpdateMCPToolset]
    ] = Field(default=None, alias="ApiKeys")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    parameter: Optional[str] = Field(default=None, alias="Parameter")


class AuthorizerAuthorizerKeyAuthApiKeysItemForUpdateMCPToolset(MCPBaseModel):
    name: str = Field(..., alias="Name")
    key: Optional[str] = Field(default=None, alias="Key")


class UpdateMCPToolsetRequest(MCPBaseModel):
    client_token: Optional[str] = Field(default=None, alias="ClientToken")
    mcp_service_ids: Optional[str] = Field(default=None, alias="MCPServiceIds")
    mcp_toolset_id: str = Field(..., alias="MCPToolsetId")
    authorizer_configuration: Optional[AuthorizerForUpdateMCPToolset] = Field(
        default=None, alias="AuthorizerConfiguration"
    )


# UpdateMCPToolset - Response
class UpdateMCPToolsetResponse(MCPBaseModel):
    mcp_toolset_id: Optional[str] = Field(default=None, alias="MCPToolsetId")


# CreateMCPService - Request
class BackendForCreateMCPService(MCPBaseModel):
    custom_configuration: Optional[BackendCustomForCreateMCPService] = Field(
        default=None, alias="CustomConfiguration"
    )
    custom_mcp_configuration: Optional[BackendCustomMcpForCreateMCPService] = Field(
        default=None, alias="CustomMcpConfiguration"
    )
    function_configuration: Optional[BackendFunctionForCreateMCPService] = Field(
        default=None, alias="FunctionConfiguration"
    )


class BackendCustomForCreateMCPService(MCPBaseModel):
    domain: Optional[str] = Field(default=None, alias="Domain")
    port: Optional[int] = Field(default=None, alias="Port")
    protocol_type: Optional[str] = Field(default=None, alias="ProtocolType")


class BackendCustomMcpForCreateMCPService(MCPBaseModel):
    private_package: Optional[BackendCustomMcpPrivatePackageForCreateMCPService] = (
        Field(default=None, alias="PrivatePackage")
    )
    public_package: Optional[BackendCustomMcpPublicPackageForCreateMCPService] = Field(
        default=None, alias="PublicPackage"
    )
    function_id: Optional[str] = Field(default=None, alias="FunctionId")
    function_name: Optional[str] = Field(default=None, alias="FunctionName")


class BackendCustomMcpPrivatePackageForCreateMCPService(MCPBaseModel):
    envs: Optional[list[BackendCustomMcpPrivatePackageEnvsItemForCreateMCPService]] = (
        Field(default=None, alias="Envs")
    )
    command: Optional[str] = Field(default=None, alias="Command")
    image_url: Optional[str] = Field(default=None, alias="ImageUrl")


class BackendCustomMcpPublicPackageForCreateMCPService(MCPBaseModel):
    mcp_type: Optional[str] = Field(default=None, alias="McpType")
    package_manager_type: Optional[str] = Field(
        default=None, alias="PackageManagerType"
    )
    raw_config: Optional[str] = Field(default=None, alias="RawConfig")


class BackendFunctionForCreateMCPService(MCPBaseModel):
    function_id: Optional[str] = Field(default=None, alias="FunctionId")
    function_name: Optional[str] = Field(default=None, alias="FunctionName")


class InboundAuthorizerForCreateMCPService(MCPBaseModel):
    authorizer: Optional[InboundAuthorizerAuthorizerForCreateMCPService] = Field(
        default=None, alias="Authorizer"
    )
    authorizer_type: str = Field(..., alias="AuthorizerType")


class InboundAuthorizerAuthorizerForCreateMCPService(MCPBaseModel):
    custom_jwt_authorizer: Optional[
        InboundAuthorizerAuthorizerCustomJwtAuthorizerForCreateMCPService
    ] = Field(default=None, alias="CustomJwtAuthorizer")
    key_auth: Optional[InboundAuthorizerAuthorizerKeyAuthForCreateMCPService] = Field(
        default=None, alias="KeyAuth"
    )


class InboundAuthorizerAuthorizerCustomJwtAuthorizerForCreateMCPService(MCPBaseModel):
    discovery_url: str = Field(..., alias="DiscoveryUrl")
    allowed_clients: Optional[list[str]] = Field(default=None, alias="AllowedClients")


class InboundAuthorizerAuthorizerKeyAuthForCreateMCPService(MCPBaseModel):
    api_keys: Optional[
        list[InboundAuthorizerAuthorizerKeyAuthApiKeysItemForCreateMCPService]
    ] = Field(default=None, alias="ApiKeys")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    parameter: Optional[str] = Field(default=None, alias="Parameter")


class NetworkForCreateMCPService(MCPBaseModel):
    vpc_configuration: Optional[NetworkVpcForCreateMCPService] = Field(
        default=None, alias="VpcConfiguration"
    )
    enable_private_network: Optional[bool] = Field(
        default=None, alias="EnablePrivateNetwork"
    )
    enable_public_network: Optional[bool] = Field(
        default=None, alias="EnablePublicNetwork"
    )


class NetworkVpcForCreateMCPService(MCPBaseModel):
    vpc_id: str = Field(..., alias="VpcId")
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")


class OutboundAuthorizerForCreateMCPService(MCPBaseModel):
    authorizer: Optional[OutboundAuthorizerAuthorizerForCreateMCPService] = Field(
        default=None, alias="Authorizer"
    )
    authorizer_type: str = Field(..., alias="AuthorizerType")


class OutboundAuthorizerAuthorizerForCreateMCPService(MCPBaseModel):
    key_auth: Optional[OutboundAuthorizerAuthorizerKeyAuthForCreateMCPService] = Field(
        default=None, alias="KeyAuth"
    )


class OutboundAuthorizerAuthorizerKeyAuthForCreateMCPService(MCPBaseModel):
    api_keys: Optional[
        list[OutboundAuthorizerAuthorizerKeyAuthApiKeysItemForCreateMCPService]
    ] = Field(default=None, alias="ApiKeys")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    parameter: Optional[str] = Field(default=None, alias="Parameter")


class ProtocolForCreateMCPService(MCPBaseModel):
    http_api_configuration: Optional[ProtocolHttpApiForCreateMCPService] = Field(
        default=None, alias="HttpApiConfiguration"
    )


class ProtocolHttpApiForCreateMCPService(MCPBaseModel):
    configuration: Optional[str] = Field(default=None, alias="Configuration")
    type: Optional[str] = Field(default=None, alias="Type")


class BackendCustomMcpPrivatePackageEnvsItemForCreateMCPService(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class InboundAuthorizerAuthorizerKeyAuthApiKeysItemForCreateMCPService(MCPBaseModel):
    name: str = Field(..., alias="Name")
    key: Optional[str] = Field(default=None, alias="Key")


class OutboundAuthorizerAuthorizerKeyAuthApiKeysItemForCreateMCPService(MCPBaseModel):
    name: str = Field(..., alias="Name")
    key: Optional[str] = Field(default=None, alias="Key")


class TagsItemForCreateMCPService(MCPBaseModel):
    key: str = Field(..., alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class CreateMCPServiceRequest(MCPBaseModel):
    backend_type: str = Field(..., alias="BackendType")
    client_token: Optional[str] = Field(default=None, alias="ClientToken")
    name: str = Field(..., alias="Name")
    path: str = Field(..., alias="Path")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    protocol_type: str = Field(..., alias="ProtocolType")
    backend_configuration: Optional[BackendForCreateMCPService] = Field(
        default=None, alias="BackendConfiguration"
    )
    inbound_authorizer_configuration: Optional[InboundAuthorizerForCreateMCPService] = (
        Field(default=None, alias="InboundAuthorizerConfiguration")
    )
    network_configuration: Optional[NetworkForCreateMCPService] = Field(
        default=None, alias="NetworkConfiguration"
    )
    outbound_authorizer_configuration: Optional[
        OutboundAuthorizerForCreateMCPService
    ] = Field(default=None, alias="OutboundAuthorizerConfiguration")
    protocol_configuration: Optional[ProtocolForCreateMCPService] = Field(
        default=None, alias="ProtocolConfiguration"
    )
    tags: Optional[list[TagsItemForCreateMCPService]] = Field(
        default=None, alias="Tags"
    )


# CreateMCPService - Response
class CreateMCPServiceResponse(MCPBaseModel):
    mcp_service_id: Optional[str] = Field(default=None, alias="MCPServiceId")


# ListMCPToolsets - Request
class FiltersItemForListMCPToolsets(MCPBaseModel):
    name: Optional[str] = Field(default=None, alias="Name")
    name_contains: Optional[str] = Field(default=None, alias="NameContains")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class TagFiltersItemForListMCPToolsets(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class ListMCPToolsetsRequest(MCPBaseModel):
    max_results: Optional[int] = Field(default=None, alias="MaxResults")
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    filters: Optional[list[FiltersItemForListMCPToolsets]] = Field(
        default=None, alias="Filters"
    )
    tag_filters: Optional[list[TagFiltersItemForListMCPToolsets]] = Field(
        default=None, alias="TagFilters"
    )


# ListMCPToolsets - Response
class ListMCPToolsetsResponse(MCPBaseModel):
    mcp_toolsets: Optional[list[MCPToolsetsForListMCPToolsets]] = Field(
        default=None, alias="MCPToolsets"
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    total_count: Optional[int] = Field(default=None, alias="TotalCount")


# ListMCPTools - Request
class ListMCPToolsRequest(MCPBaseModel):
    mcp_toolset_ids: str = Field(..., alias="MCPToolsetIds")


# ListMCPTools - Response
class ListMCPToolsResponse(MCPBaseModel):
    mcp_service_tools: Optional[list[MCPServiceToolsForListMCPTools]] = Field(
        default=None, alias="MCPServiceTools"
    )


# CreateMCPToolset - Request
class AuthorizerForCreateMCPToolset(MCPBaseModel):
    authorizer: Optional[AuthorizerAuthorizerForCreateMCPToolset] = Field(
        default=None, alias="Authorizer"
    )
    authorizer_type: str = Field(..., alias="AuthorizerType")


class AuthorizerAuthorizerForCreateMCPToolset(MCPBaseModel):
    custom_jwt_authorizer: Optional[
        AuthorizerAuthorizerCustomJwtAuthorizerForCreateMCPToolset
    ] = Field(default=None, alias="CustomJwtAuthorizer")
    key_auth: Optional[AuthorizerAuthorizerKeyAuthForCreateMCPToolset] = Field(
        default=None, alias="KeyAuth"
    )


class AuthorizerAuthorizerCustomJwtAuthorizerForCreateMCPToolset(MCPBaseModel):
    discovery_url: str = Field(..., alias="DiscoveryUrl")
    allowed_clients: Optional[list[str]] = Field(default=None, alias="AllowedClients")


class AuthorizerAuthorizerKeyAuthForCreateMCPToolset(MCPBaseModel):
    api_keys: Optional[
        list[AuthorizerAuthorizerKeyAuthApiKeysItemForCreateMCPToolset]
    ] = Field(default=None, alias="ApiKeys")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    parameter: Optional[str] = Field(default=None, alias="Parameter")


class NetworkForCreateMCPToolset(MCPBaseModel):
    vpc_configuration: Optional[NetworkVpcForCreateMCPToolset] = Field(
        default=None, alias="VpcConfiguration"
    )
    enable_private_network: Optional[bool] = Field(
        default=None, alias="EnablePrivateNetwork"
    )
    enable_public_network: Optional[bool] = Field(
        default=None, alias="EnablePublicNetwork"
    )


class NetworkVpcForCreateMCPToolset(MCPBaseModel):
    vpc_id: str = Field(..., alias="VpcId")
    security_group_ids: Optional[list[str]] = Field(
        default=None, alias="SecurityGroupIds"
    )
    subnet_ids: Optional[list[str]] = Field(default=None, alias="SubnetIds")


class AuthorizerAuthorizerKeyAuthApiKeysItemForCreateMCPToolset(MCPBaseModel):
    name: str = Field(..., alias="Name")
    key: Optional[str] = Field(default=None, alias="Key")


class TagsItemForCreateMCPToolset(MCPBaseModel):
    key: str = Field(..., alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class CreateMCPToolsetRequest(MCPBaseModel):
    client_token: Optional[str] = Field(default=None, alias="ClientToken")
    mcp_service_ids: str = Field(..., alias="MCPServiceIds")
    name: str = Field(..., alias="Name")
    path: str = Field(..., alias="Path")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    authorizer_configuration: Optional[AuthorizerForCreateMCPToolset] = Field(
        default=None, alias="AuthorizerConfiguration"
    )
    network_configuration: Optional[NetworkForCreateMCPToolset] = Field(
        default=None, alias="NetworkConfiguration"
    )
    tags: Optional[list[TagsItemForCreateMCPToolset]] = Field(
        default=None, alias="Tags"
    )


# CreateMCPToolset - Response
class CreateMCPToolsetResponse(MCPBaseModel):
    mcp_toolset_id: Optional[str] = Field(default=None, alias="MCPToolsetId")


# GetMCPTools - Request
class GetMCPToolsRequest(MCPBaseModel):
    mcp_toolset_id: str = Field(..., alias="MCPToolsetId")


# GetMCPTools - Response
class GetMCPToolsResponse(MCPBaseModel):
    tools: Optional[str] = Field(default=None, alias="Tools")


# DeleteMCPService - Request
class DeleteMCPServiceRequest(MCPBaseModel):
    mcp_service_id: str = Field(..., alias="MCPServiceId")


# DeleteMCPService - Response
class DeleteMCPServiceResponse(MCPBaseModel):
    mcp_service_id: Optional[str] = Field(default=None, alias="MCPServiceId")


# GetMCPToolset - Request
class GetMCPToolsetRequest(MCPBaseModel):
    mcp_toolset_id: str = Field(..., alias="MCPToolsetId")


# GetMCPToolset - Response
class GetMCPToolsetResponse(MCPBaseModel):
    mcp_toolset: Optional[MCPToolsetForGetMCPToolset] = Field(
        default=None, alias="MCPToolset"
    )


# ListMCPServices - Request
class FiltersItemForListMCPServices(MCPBaseModel):
    name: Optional[str] = Field(default=None, alias="Name")
    name_contains: Optional[str] = Field(default=None, alias="NameContains")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class TagFiltersItemForListMCPServices(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    values: Optional[list[str]] = Field(default=None, alias="Values")


class ListMCPServicesRequest(MCPBaseModel):
    max_results: Optional[int] = Field(default=None, alias="MaxResults")
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    filters: Optional[list[FiltersItemForListMCPServices]] = Field(
        default=None, alias="Filters"
    )
    tag_filters: Optional[list[TagFiltersItemForListMCPServices]] = Field(
        default=None, alias="TagFilters"
    )


# ListMCPServices - Response
class ListMCPServicesResponse(MCPBaseModel):
    mcp_services: Optional[list[MCPServicesForListMCPServices]] = Field(
        default=None, alias="MCPServices"
    )
    next_token: Optional[str] = Field(default=None, alias="NextToken")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    total_count: Optional[int] = Field(default=None, alias="TotalCount")


# DeleteMCPToolset - Request
class DeleteMCPToolsetRequest(MCPBaseModel):
    mcp_toolset_id: str = Field(..., alias="MCPToolsetId")


# DeleteMCPToolset - Response
class DeleteMCPToolsetResponse(MCPBaseModel):
    mcp_toolset_id: Optional[str] = Field(default=None, alias="MCPToolsetId")


# UpdateMCPTools - Request
class UpdateMCPToolsRequest(MCPBaseModel):
    mcp_service_id: str = Field(..., alias="MCPServiceId")
    tools: str = Field(..., alias="Tools")


# UpdateMCPTools - Response
class UpdateMCPToolsResponse(MCPBaseModel):
    mcp_service_id: Optional[str] = Field(default=None, alias="MCPServiceId")


# UpdateMCPService - Request
class BackendForUpdateMCPService(MCPBaseModel):
    custom_configuration: Optional[BackendCustomForUpdateMCPService] = Field(
        default=None, alias="CustomConfiguration"
    )
    custom_mcp_configuration: Optional[BackendCustomMcpForUpdateMCPService] = Field(
        default=None, alias="CustomMcpConfiguration"
    )
    function_configuration: Optional[BackendFunctionForUpdateMCPService] = Field(
        default=None, alias="FunctionConfiguration"
    )


class BackendCustomForUpdateMCPService(MCPBaseModel):
    domain: Optional[str] = Field(default=None, alias="Domain")
    port: Optional[int] = Field(default=None, alias="Port")
    protocol_type: Optional[str] = Field(default=None, alias="ProtocolType")


class BackendCustomMcpForUpdateMCPService(MCPBaseModel):
    private_package: Optional[BackendCustomMcpPrivatePackageForUpdateMCPService] = (
        Field(default=None, alias="PrivatePackage")
    )
    public_package: Optional[BackendCustomMcpPublicPackageForUpdateMCPService] = Field(
        default=None, alias="PublicPackage"
    )
    function_id: Optional[str] = Field(default=None, alias="FunctionId")
    function_name: Optional[str] = Field(default=None, alias="FunctionName")


class BackendCustomMcpPrivatePackageForUpdateMCPService(MCPBaseModel):
    envs: Optional[list[BackendCustomMcpPrivatePackageEnvsItemForUpdateMCPService]] = (
        Field(default=None, alias="Envs")
    )
    command: Optional[str] = Field(default=None, alias="Command")
    image_url: Optional[str] = Field(default=None, alias="ImageUrl")


class BackendCustomMcpPublicPackageForUpdateMCPService(MCPBaseModel):
    mcp_type: Optional[str] = Field(default=None, alias="McpType")
    package_manager_type: Optional[str] = Field(
        default=None, alias="PackageManagerType"
    )
    raw_config: Optional[str] = Field(default=None, alias="RawConfig")


class BackendFunctionForUpdateMCPService(MCPBaseModel):
    function_id: Optional[str] = Field(default=None, alias="FunctionId")
    function_name: Optional[str] = Field(default=None, alias="FunctionName")


class InboundAuthorizerForUpdateMCPService(MCPBaseModel):
    authorizer: Optional[InboundAuthorizerAuthorizerForUpdateMCPService] = Field(
        default=None, alias="Authorizer"
    )
    authorizer_type: str = Field(..., alias="AuthorizerType")


class InboundAuthorizerAuthorizerForUpdateMCPService(MCPBaseModel):
    key_auth: Optional[InboundAuthorizerAuthorizerKeyAuthForUpdateMCPService] = Field(
        default=None, alias="KeyAuth"
    )


class InboundAuthorizerAuthorizerKeyAuthForUpdateMCPService(MCPBaseModel):
    api_keys: Optional[
        list[InboundAuthorizerAuthorizerKeyAuthApiKeysItemForUpdateMCPService]
    ] = Field(default=None, alias="ApiKeys")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    parameter: Optional[str] = Field(default=None, alias="Parameter")


class OutboundAuthorizerForUpdateMCPService(MCPBaseModel):
    authorizer: Optional[OutboundAuthorizerAuthorizerForUpdateMCPService] = Field(
        default=None, alias="Authorizer"
    )
    authorizer_type: str = Field(..., alias="AuthorizerType")


class OutboundAuthorizerAuthorizerForUpdateMCPService(MCPBaseModel):
    key_auth: Optional[OutboundAuthorizerAuthorizerKeyAuthForUpdateMCPService] = Field(
        default=None, alias="KeyAuth"
    )


class OutboundAuthorizerAuthorizerKeyAuthForUpdateMCPService(MCPBaseModel):
    api_keys: Optional[
        list[OutboundAuthorizerAuthorizerKeyAuthApiKeysItemForUpdateMCPService]
    ] = Field(default=None, alias="ApiKeys")
    api_key_location: Optional[str] = Field(default=None, alias="ApiKeyLocation")
    parameter: Optional[str] = Field(default=None, alias="Parameter")


class BackendCustomMcpPrivatePackageEnvsItemForUpdateMCPService(MCPBaseModel):
    key: Optional[str] = Field(default=None, alias="Key")
    value: Optional[str] = Field(default=None, alias="Value")


class InboundAuthorizerAuthorizerKeyAuthApiKeysItemForUpdateMCPService(MCPBaseModel):
    name: str = Field(..., alias="Name")
    key: Optional[str] = Field(default=None, alias="Key")


class OutboundAuthorizerAuthorizerKeyAuthApiKeysItemForUpdateMCPService(MCPBaseModel):
    name: str = Field(..., alias="Name")
    key: Optional[str] = Field(default=None, alias="Key")


class UpdateMCPServiceRequest(MCPBaseModel):
    backend_type: Optional[str] = Field(default=None, alias="BackendType")
    mcp_service_id: str = Field(..., alias="MCPServiceId")
    backend_configuration: Optional[BackendForUpdateMCPService] = Field(
        default=None, alias="BackendConfiguration"
    )
    inbound_authorizer_configuration: Optional[InboundAuthorizerForUpdateMCPService] = (
        Field(default=None, alias="InboundAuthorizerConfiguration")
    )
    outbound_authorizer_configuration: Optional[
        OutboundAuthorizerForUpdateMCPService
    ] = Field(default=None, alias="OutboundAuthorizerConfiguration")


# UpdateMCPService - Response
class UpdateMCPServiceResponse(MCPBaseModel):
    mcp_service_id: Optional[str] = Field(default=None, alias="MCPServiceId")


# GetMCPService - Request
class GetMCPServiceRequest(MCPBaseModel):
    mcp_service_id: str = Field(..., alias="MCPServiceId")


# GetMCPService - Response
class GetMCPServiceResponse(MCPBaseModel):
    mcp_service: Optional[MCPServiceForGetMCPService] = Field(
        default=None, alias="MCPService"
    )

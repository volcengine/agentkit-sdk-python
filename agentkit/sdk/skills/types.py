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


class SkillsBaseModel(BaseModel):
    """AgentKit auto-generated base model"""

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class CreateSkillRequest(SkillsBaseModel):
    name: Optional[str] = Field(default=None, alias="Name")
    description: Optional[str] = Field(default=None, alias="Description")
    tos_url: str = Field(..., alias="TosUrl")
    skill_spaces: Optional[list[str]] = Field(default=None, alias="SkillSpaces")
    bucket_name: Optional[str] = Field(default=None, alias="BucketName")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    tags: Optional[list[TagForSkill]] = Field(default=None, alias="Tags")


class CreateSkillResponse(SkillsBaseModel):
    id: Optional[str] = Field(default=None, alias="Id")
    tags: Optional[list[TagForSkill]] = Field(default=None, alias="Tags")


class CreateSkillSpaceRequest(SkillsBaseModel):
    name: str = Field(..., alias="Name")
    description: Optional[str] = Field(default=None, alias="Description")
    skills: Optional[list[SkillBasicInfo]] = Field(default=None, alias="Skills")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    tags: Optional[list[TagForSkill]] = Field(default=None, alias="Tags")


class CreateSkillSpaceResponse(SkillsBaseModel):
    id: Optional[str] = Field(default=None, alias="Id")
    tags: Optional[list[TagForSkill]] = Field(default=None, alias="Tags")


class DeleteSkillRequest(SkillsBaseModel):
    id: str = Field(..., alias="Id")


class DeleteSkillResponse(SkillsBaseModel):
    pass


class DeleteSkillSpaceRequest(SkillsBaseModel):
    id: str = Field(..., alias="Id")


class DeleteSkillSpaceResponse(SkillsBaseModel):
    pass


class GetSkillInfoRequest(SkillsBaseModel):
    skill_name: str = Field(..., alias="SkillName")
    skill_space_name: str = Field(..., alias="SkillSpaceName")
    skill_space_id: str = Field(..., alias="SkillSpaceId")


class GetSkillInfoResponse(SkillsBaseModel):
    bucket_name: Optional[str] = Field(default=None, alias="BucketName")
    skill_name: Optional[str] = Field(default=None, alias="SkillName")
    description: Optional[str] = Field(default=None, alias="Description")
    skill_md: Optional[str] = Field(default=None, alias="SkillMd")
    tos_path: Optional[str] = Field(default=None, alias="TosPath")


class GetSkillRequest(SkillsBaseModel):
    id: str = Field(..., alias="Id")


class GetSkillResponse(SkillsBaseModel):
    id: Optional[str] = Field(default=None, alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")
    status: Optional[str] = Field(default=None, alias="Status")
    description: Optional[str] = Field(default=None, alias="Description")
    versions: Optional[list[str]] = Field(default=None, alias="Versions")
    create_time_stamp: Optional[str] = Field(default=None, alias="CreateTimeStamp")
    update_time_stamp: Optional[str] = Field(default=None, alias="UpdateTimeStamp")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    tags: Optional[list[TagForSkill]] = Field(default=None, alias="Tags")


class GetSkillSpaceRequest(SkillsBaseModel):
    id: str = Field(..., alias="Id")


class GetSkillSpaceResponse(SkillsBaseModel):
    id: Optional[str] = Field(default=None, alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")
    status: Optional[str] = Field(default=None, alias="Status")
    description: Optional[str] = Field(default=None, alias="Description")
    create_time_stamp: Optional[str] = Field(default=None, alias="CreateTimeStamp")
    update_time_stamp: Optional[str] = Field(default=None, alias="UpdateTimeStamp")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    tags: Optional[list[TagForSkill]] = Field(default=None, alias="Tags")


class GetSkillVersionRequest(SkillsBaseModel):
    id: str = Field(..., alias="Id")
    skill_version: Optional[str] = Field(default=None, alias="SkillVersion")


class GetSkillVersionResponse(SkillsBaseModel):
    id: Optional[str] = Field(default=None, alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")
    status: Optional[str] = Field(default=None, alias="Status")
    description: Optional[str] = Field(default=None, alias="Description")
    version: Optional[str] = Field(default=None, alias="Version")
    create_time_stamp: Optional[str] = Field(default=None, alias="CreateTimeStamp")
    update_time_stamp: Optional[str] = Field(default=None, alias="UpdateTimeStamp")
    skill_md: Optional[str] = Field(default=None, alias="SkillMd")
    tos_path: Optional[str] = Field(default=None, alias="TosPath")
    bucket_name: Optional[str] = Field(default=None, alias="BucketName")
    error_message: Optional[str] = Field(default=None, alias="ErrorMessage")


class ListSkillSpacesBySkillRequest(SkillsBaseModel):
    skill_id: str = Field(..., alias="SkillId")
    skill_version: Optional[str] = Field(default=None, alias="SkillVersion")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    filter: Optional[SkillRelationFilter] = Field(default=None, alias="Filter")


class ListSkillSpacesBySkillResponse(SkillsBaseModel):
    items: Optional[list[Relation]] = Field(default=None, alias="Items")
    total_count: Optional[int] = Field(default=None, alias="TotalCount")


class ListSkillSpacesRequest(SkillsBaseModel):
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    filter: Optional[SkillSpaceFilter] = Field(default=None, alias="Filter")
    project_name: Optional[str] = Field(default=None, alias="ProjectName")
    tag_filters: Optional[list[TagFilterForSkill]] = Field(
        default=None, alias="TagFilters"
    )


class ListSkillSpacesResponse(SkillsBaseModel):
    total_count: Optional[int] = Field(default=None, alias="TotalCount")
    items: Optional[list[SkillSpace]] = Field(default=None, alias="Items")


class ListSkillVersionsRequest(SkillsBaseModel):
    id: str = Field(..., alias="Id")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")


class ListSkillVersionsResponse(SkillsBaseModel):
    total_count: Optional[int] = Field(default=None, alias="TotalCount")
    items: Optional[list[SkillVersionWithRelation]] = Field(default=None, alias="Items")


class ListSkillsBySkillSpaceRequest(SkillsBaseModel):
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    filter: Optional[SkillRelationFilter] = Field(default=None, alias="Filter")
    skill_space_id: str = Field(..., alias="SkillSpaceId")
    page_number: Optional[int] = Field(default=None, alias="PageNumber")


class ListSkillsBySkillSpaceResponse(SkillsBaseModel):
    items: Optional[list[Relation]] = Field(default=None, alias="Items")
    total_count: Optional[int] = Field(default=None, alias="TotalCount")


class ListSkillsBySpaceIdRequest(SkillsBaseModel):
    skill_space_id: str = Field(..., alias="SkillSpaceId")
    skill_space_name: str = Field(..., alias="SkillSpaceName")


class ListSkillsBySpaceIdResponse(SkillsBaseModel):
    items: Optional[list[SkillBasicInfoForAgent]] = Field(default=None, alias="Items")


class ListSkillsBySpaceNameRequest(SkillsBaseModel):
    skill_space_name: str = Field(..., alias="SkillSpaceName")


class ListSkillsBySpaceNameResponse(SkillsBaseModel):
    items: Optional[list[SkillBasicInfoForAgent]] = Field(default=None, alias="Items")


class ListSkillsRequest(SkillsBaseModel):
    page_number: Optional[int] = Field(default=None, alias="PageNumber")
    page_size: Optional[int] = Field(default=None, alias="PageSize")
    filter: Optional[SkillFilter] = Field(default=None, alias="Filter")
    tag_filters: Optional[list[TagFilterForSkill]] = Field(
        default=None, alias="TagFilters"
    )
    project_name: Optional[str] = Field(default=None, alias="ProjectName")


class ListSkillsResponse(SkillsBaseModel):
    total_count: Optional[int] = Field(default=None, alias="TotalCount")
    items: Optional[list[Skill]] = Field(default=None, alias="Items")


class PublishSkillToSkillSpaceRequest(SkillsBaseModel):
    skill_spaces: list[str] = Field(..., alias="SkillSpaces")
    skills: list[SkillBasicInfo] = Field(..., alias="Skills")


class PublishSkillToSkillSpaceResponse(SkillsBaseModel):
    pass


class Relation(SkillsBaseModel):
    skill_status: Optional[str] = Field(default=None, alias="SkillStatus")
    skill_space_id: str = Field(..., alias="SkillSpaceId")
    skill_space_name: Optional[str] = Field(default=None, alias="SkillSpaceName")
    skill_space_description: Optional[str] = Field(
        default=None, alias="SkillSpaceDescription"
    )
    skill_space_status: Optional[str] = Field(default=None, alias="SkillSpaceStatus")
    skill_id: str = Field(..., alias="SkillId")
    skill_name: Optional[str] = Field(default=None, alias="SkillName")
    version: Optional[str] = Field(default=None, alias="Version")
    skill_description: Optional[str] = Field(default=None, alias="SkillDescription")


class RemoveSkillFromSkillSpaceRequest(SkillsBaseModel):
    skill_id: str = Field(..., alias="SkillId")
    skill_space_id: str = Field(..., alias="SkillSpaceId")


class RemoveSkillFromSkillSpaceResponse(SkillsBaseModel):
    pass


class Skill(SkillsBaseModel):
    id: str = Field(..., alias="Id")
    name: str = Field(..., alias="Name")
    status: str = Field(..., alias="Status")
    description: str = Field(..., alias="Description")
    create_time_stamp: str = Field(..., alias="CreateTimeStamp")
    update_time_stamp: str = Field(..., alias="UpdateTimeStamp")
    versions: list[str] = Field(..., alias="Versions")
    project_name: str = Field(..., alias="ProjectName")
    tags: Optional[list[TagForSkill]] = Field(default=None, alias="Tags")


class SkillBasicInfo(SkillsBaseModel):
    skill_id: str = Field(..., alias="SkillId")
    version: str = Field(..., alias="Version")


class SkillBasicInfoForAgent(SkillsBaseModel):
    name: str = Field(..., alias="Name")
    description: str = Field(..., alias="Description")


class SkillFilter(SkillsBaseModel):
    status: Optional[list[str]] = Field(default=None, alias="Status")
    name: Optional[str] = Field(default=None, alias="Name")
    id: Optional[str] = Field(default=None, alias="Id")


class SkillRelationFilter(SkillsBaseModel):
    status: Optional[list[str]] = Field(default=None, alias="Status")
    id: Optional[str] = Field(default=None, alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")


class SkillSpace(SkillsBaseModel):
    id: str = Field(..., alias="Id")
    name: str = Field(..., alias="Name")
    status: str = Field(..., alias="Status")
    description: str = Field(..., alias="Description")
    create_time_stamp: str = Field(..., alias="CreateTimeStamp")
    update_time_stamp: str = Field(..., alias="UpdateTimeStamp")
    relations: list[SkillSpaceRelation] = Field(..., alias="Relations")
    project_name: str = Field(..., alias="ProjectName")
    tags: Optional[list[TagForSkill]] = Field(default=None, alias="Tags")


class SkillSpaceFilter(SkillsBaseModel):
    status: Optional[list[str]] = Field(default=None, alias="Status")
    name: Optional[str] = Field(default=None, alias="Name")
    id: Optional[str] = Field(default=None, alias="Id")


class SkillSpaceRelation(SkillsBaseModel):
    skill_space_id: str = Field(..., alias="SkillSpaceId")
    skill_id: str = Field(..., alias="SkillId")
    skill_name: str = Field(..., alias="SkillName")
    skill_description: str = Field(..., alias="SkillDescription")
    skill_status: str = Field(..., alias="SkillStatus")
    version: str = Field(..., alias="Version")


class SkillVersionWithRelation(SkillsBaseModel):
    id: str = Field(..., alias="Id")
    name: str = Field(..., alias="Name")
    status: str = Field(..., alias="Status")
    description: str = Field(..., alias="Description")
    version: str = Field(..., alias="Version")
    create_time_stamp: str = Field(..., alias="CreateTimeStamp")
    update_time_stamp: str = Field(..., alias="UpdateTimeStamp")
    relations: list[Relation] = Field(..., alias="Relations")
    error_message: Optional[str] = Field(default=None, alias="ErrorMessage")


class TagFilterForSkill(SkillsBaseModel):
    key: str = Field(..., alias="Key")
    values: list[str] = Field(..., alias="Values")


class TagForSkill(SkillsBaseModel):
    key: str = Field(..., alias="Key")
    value: str = Field(..., alias="Value")


class UpdateSkillRequest(SkillsBaseModel):
    id: str = Field(..., alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")
    description: Optional[str] = Field(default=None, alias="Description")
    tos_url: str = Field(..., alias="TosUrl")
    skill_spaces: Optional[list[str]] = Field(default=None, alias="SkillSpaces")
    bucket_name: Optional[str] = Field(default=None, alias="BucketName")


class UpdateSkillResponse(SkillsBaseModel):
    pass


class UpdateSkillSpaceRequest(SkillsBaseModel):
    id: str = Field(..., alias="Id")
    name: Optional[str] = Field(default=None, alias="Name")
    description: Optional[str] = Field(default=None, alias="Description")


class UpdateSkillSpaceResponse(SkillsBaseModel):
    pass

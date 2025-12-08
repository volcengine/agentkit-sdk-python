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


class AccountBaseModel(BaseModel):
    """AgentKit auto-generated base model"""

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


# Data Types
class ServiceStatusesForListAccountLinkedServices(AccountBaseModel):
    service_name: Optional[str] = Field(default=None, alias="ServiceName")
    status: Optional[str] = Field(default=None, alias="Status")


# ListAccountLinkedServices - Request
class ListAccountLinkedServicesRequest(AccountBaseModel):
    pass


# ListAccountLinkedServices - Response
class ListAccountLinkedServicesResponse(AccountBaseModel):
    service_statuses: Optional[list[ServiceStatusesForListAccountLinkedServices]] = (
        Field(default=None, alias="ServiceStatuses")
    )

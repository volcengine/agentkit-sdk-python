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

from .client import AgentkitMemoryClient
from .types import (
    CreateMemoryCollectionRequest,
    CreateMemoryCollectionResponse,
    UpdateMemoryCollectionRequest,
    UpdateMemoryCollectionResponse,
    DeleteMemoryCollectionRequest,
    DeleteMemoryCollectionResponse,
    ListMemoryCollectionsRequest,
    ListMemoryCollectionsResponse,
    AddMemoryCollectionRequest,
    AddMemoryCollectionResponse,
    GetMemoryCollectionRequest,
    GetMemoryCollectionResponse,
    GetMemoryConnectionInfoRequest,
    GetMemoryConnectionInfoResponse,
    MemoriesForListMemoryCollections,
    CollectionsForAddMemoryCollection,
    ConnectionInfosForGetMemoryConnectionInfo,
    StrategiesForUpdateMemoryCollection,
    StrategiesForGetMemoryCollection,
    LongTermConfigurationForUpdateMemoryCollection,
    LongTermConfigurationForGetMemoryCollection,
)

__all__ = [
    "AgentkitMemoryClient",
    "CreateMemoryCollectionRequest",
    "CreateMemoryCollectionResponse",
    "UpdateMemoryCollectionRequest",
    "UpdateMemoryCollectionResponse",
    "DeleteMemoryCollectionRequest",
    "DeleteMemoryCollectionResponse",
    "ListMemoryCollectionsRequest",
    "ListMemoryCollectionsResponse",
    "AddMemoryCollectionRequest",
    "AddMemoryCollectionResponse",
    "GetMemoryCollectionRequest",
    "GetMemoryCollectionResponse",
    "GetMemoryConnectionInfoRequest",
    "GetMemoryConnectionInfoResponse",
    "MemoriesForListMemoryCollections",
    "CollectionsForAddMemoryCollection",
    "ConnectionInfosForGetMemoryConnectionInfo",
    "StrategiesForUpdateMemoryCollection",
    "StrategiesForGetMemoryCollection",
    "LongTermConfigurationForUpdateMemoryCollection",
    "LongTermConfigurationForGetMemoryCollection",
]

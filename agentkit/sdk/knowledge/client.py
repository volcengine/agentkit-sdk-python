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

from typing import Dict
from agentkit.client import BaseAgentkitClient
from .types import (
    AddKnowledgeBaseRequest,
    AddKnowledgeBaseResponse,
    DeleteKnowledgeBaseRequest,
    DeleteKnowledgeBaseResponse,
    GetKnowledgeBaseRequest,
    GetKnowledgeBaseResponse,
    GetKnowledgeConnectionInfoRequest,
    GetKnowledgeConnectionInfoResponse,
    ListKnowledgeBasesRequest,
    ListKnowledgeBasesResponse,
    UpdateKnowledgeBaseRequest,
    UpdateKnowledgeBaseResponse,
)


class AgentkitKnowledgeClient(BaseAgentkitClient):
    """AgentKit Knowledge Base Management Service"""

    API_ACTIONS: Dict[str, str] = {
        "AddKnowledgeBase": "AddKnowledgeBase",
        "DeleteKnowledgeBase": "DeleteKnowledgeBase",
        "GetKnowledgeBase": "GetKnowledgeBase",
        "GetKnowledgeConnectionInfo": "GetKnowledgeConnectionInfo",
        "ListKnowledgeBases": "ListKnowledgeBases",
        "UpdateKnowledgeBase": "UpdateKnowledgeBase",
    }

    def __init__(
        self,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
        session_token: str = "",
    ) -> None:
        super().__init__(
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            session_token=session_token,
            service_name="knowledge",
        )

    def add_knowledge_base(
        self, request: AddKnowledgeBaseRequest
    ) -> AddKnowledgeBaseResponse:
        return self._invoke_api(
            api_action="AddKnowledgeBase",
            request=request,
            response_type=AddKnowledgeBaseResponse,
        )

    def delete_knowledge_base(
        self, request: DeleteKnowledgeBaseRequest
    ) -> DeleteKnowledgeBaseResponse:
        return self._invoke_api(
            api_action="DeleteKnowledgeBase",
            request=request,
            response_type=DeleteKnowledgeBaseResponse,
        )

    def get_knowledge_base(
        self, request: GetKnowledgeBaseRequest
    ) -> GetKnowledgeBaseResponse:
        return self._invoke_api(
            api_action="GetKnowledgeBase",
            request=request,
            response_type=GetKnowledgeBaseResponse,
        )

    def get_knowledge_connection_info(
        self, request: GetKnowledgeConnectionInfoRequest
    ) -> GetKnowledgeConnectionInfoResponse:
        return self._invoke_api(
            api_action="GetKnowledgeConnectionInfo",
            request=request,
            response_type=GetKnowledgeConnectionInfoResponse,
        )

    def list_knowledge_bases(
        self, request: ListKnowledgeBasesRequest
    ) -> ListKnowledgeBasesResponse:
        return self._invoke_api(
            api_action="ListKnowledgeBases",
            request=request,
            response_type=ListKnowledgeBasesResponse,
        )

    def update_knowledge_base(
        self, request: UpdateKnowledgeBaseRequest
    ) -> UpdateKnowledgeBaseResponse:
        return self._invoke_api(
            api_action="UpdateKnowledgeBase",
            request=request,
            response_type=UpdateKnowledgeBaseResponse,
        )

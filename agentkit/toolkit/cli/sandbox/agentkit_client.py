# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

"""Sandbox-specific AgentKit tools client helpers."""

from __future__ import annotations

import json
import os
from typing import Any, Type, TypeVar
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from agentkit.platform.constants import SERVICE_METADATA
from agentkit.sdk.tools.client import AgentkitToolsClient as _OpenapiAgentkitToolsClient
from agentkit.sdk.tools.types import (
    CreateSessionRequest,
    CreateSessionResponse,
    GetSessionRequest,
    GetSessionResponse,
    ListSessionsRequest,
    ListSessionsResponse,
)

SANDBOX_APIG_ENDPOINT_ENV = "SANDBOX_APIG_ENDPOINT"
TIP_TOKEN_ENV = "TIP_TOKEN"
_AGENTKIT_API_VERSION = SERVICE_METADATA["agentkit"].default_version

T = TypeVar("T")


def _env_value(name: str) -> str:
    return (os.getenv(name) or "").strip()


def tip_auth_env_enabled() -> bool:
    return bool(_env_value(SANDBOX_APIG_ENDPOINT_ENV) and _env_value(TIP_TOKEN_ENV))


def _with_action_query(endpoint: str, action: str) -> str:
    split = urlsplit(endpoint)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query.setdefault("Action", action)
    query.setdefault("Version", _AGENTKIT_API_VERSION)
    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(query),
            split.fragment,
        )
    )


def _tip_endpoint_url(endpoint: str, action: str) -> str:
    if "{Action}" in endpoint or "{action}" in endpoint:
        return endpoint.replace("{Action}", action).replace("{action}", action)
    return _with_action_query(endpoint, action)


def _extract_error_message(payload: object, default: str) -> str:
    if not isinstance(payload, dict):
        return default

    metadata = payload.get("ResponseMetadata")
    if isinstance(metadata, dict):
        api_error = metadata.get("Error")
        if isinstance(api_error, dict):
            message = api_error.get("Message")
            if isinstance(message, str) and message:
                return message

    for key in ("message", "Message", "error", "Error"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            message = value.get("message") or value.get("Message")
            if isinstance(message, str) and message:
                return message
    return default


def _tip_result_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    if "Result" in payload:
        return payload.get("Result") or {}
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return payload


class TipAgentkitToolsClient(_OpenapiAgentkitToolsClient):
    """AgentKit tools client with optional TIP bearer-token session routing.

    When both SANDBOX_APIG_ENDPOINT and TIP_TOKEN are present, session APIs are
    sent directly to the APIG endpoint. Otherwise this behaves exactly like the
    generated AgentkitToolsClient.
    """

    def __init__(
        self,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
        session_token: str = "",
        timeout: int = 30,
    ) -> None:
        self._tip_endpoint = _env_value(SANDBOX_APIG_ENDPOINT_ENV).rstrip("/")
        self._tip_token = _env_value(TIP_TOKEN_ENV)
        self._tip_timeout = timeout
        self._tip_session: requests.Session | None = None
        if self.uses_tip_auth:
            self._tip_session = requests.Session()
            return

        super().__init__(
            access_key=access_key,
            secret_key=secret_key,
            region=region,
            session_token=session_token,
        )

    @property
    def uses_tip_auth(self) -> bool:
        return bool(self._tip_endpoint and self._tip_token)

    def _invoke_tip_api(
        self,
        api_action: str,
        request: Any,
        response_type: Type[T],
    ) -> T:
        if not self.uses_tip_auth or self._tip_session is None:
            return self._invoke_api(
                api_action=api_action,
                request=request,
                response_type=response_type,
            )

        url = _tip_endpoint_url(self._tip_endpoint, api_action)
        body = request.model_dump(by_alias=True, exclude_none=True)
        try:
            response = self._tip_session.post(
                url,
                json=body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._tip_token}",
                },
                timeout=self._tip_timeout,
            )
        except requests.RequestException as exc:
            raise Exception(f"Failed to {api_action}: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise Exception(
                f"Failed to {api_action}: invalid JSON response: {response.text}"
            ) from exc

        if response.status_code >= 400:
            raise Exception(
                f"Failed to {api_action}: "
                f"{_extract_error_message(payload, response.text)}"
            )

        if isinstance(payload, dict):
            metadata = payload.get("ResponseMetadata")
            if isinstance(metadata, dict) and metadata.get("Error"):
                raise Exception(
                    f"Failed to {api_action}: "
                    f"{_extract_error_message(payload, json.dumps(payload))}"
                )

        result = _tip_result_payload(payload)
        if not isinstance(result, dict):
            raise Exception(f"Failed to {api_action}: invalid response payload")
        return response_type(**result)

    def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
        return self._invoke_tip_api(
            api_action="CreateSession",
            request=request,
            response_type=CreateSessionResponse,
        )

    def get_session(self, request: GetSessionRequest) -> GetSessionResponse:
        return self._invoke_tip_api(
            api_action="GetSession",
            request=request,
            response_type=GetSessionResponse,
        )

    def list_sessions(self, request: ListSessionsRequest) -> ListSessionsResponse:
        return self._invoke_tip_api(
            api_action="ListSessions",
            request=request,
            response_type=ListSessionsResponse,
        )

    def _raise_tip_unsupported(self, api_action: str) -> None:
        raise Exception(
            f"{api_action} is not available with TIP sandbox auth. "
            f"Unset {SANDBOX_APIG_ENDPOINT_ENV}/{TIP_TOKEN_ENV} to use the "
            "standard AgentKit OpenAPI client."
        )

    def create_tool(self, request: Any) -> Any:
        if self.uses_tip_auth:
            self._raise_tip_unsupported("CreateTool")
        return super().create_tool(request)

    def get_tool(self, request: Any) -> Any:
        if self.uses_tip_auth:
            self._raise_tip_unsupported("GetTool")
        return super().get_tool(request)

    def list_tools(self, request: Any) -> Any:
        if self.uses_tip_auth:
            self._raise_tip_unsupported("ListTools")
        return super().list_tools(request)


def is_tip_agentkit_client(client: object) -> bool:
    return bool(getattr(client, "uses_tip_auth", False))


# Keep sandbox modules/tests able to patch a local AgentkitToolsClient symbol,
# while routing construction through the sandbox-aware implementation.
AgentkitToolsClient = TipAgentkitToolsClient

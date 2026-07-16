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

"""
Base service client that provides common implementation for all Volcengine services.
This is the top-level base class for all service clients.
"""

import json
from typing import Any, Dict, Type, TypeVar, Union, Optional
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from volcengine.ApiInfo import ApiInfo
from volcengine.base.Service import Service
from volcengine.Credentials import Credentials as VolcCredentials
from volcengine.ServiceInfo import ServiceInfo

from agentkit.auth.errors import NetworkError
from agentkit.platform import (
    VolcConfiguration,
    resolve_credentials,
    resolve_endpoint,
)
from agentkit.platform.configuration import Credentials as PlatformCredentials
from agentkit.platform.provider import CloudProvider
from agentkit.utils.http_defaults import http_retries, http_timeout
from agentkit.utils.logging_config import get_logger
from agentkit.utils.ve_sign import ensure_x_custom_source_header

logger = get_logger(__name__)

T = TypeVar("T")
_CREDENTIAL_ERROR_TOKENS = frozenset(
    {
        "invalidaccesskeyid",
        "invalidaccesskey",
        "signaturedoesnotmatch",
        "expiredtoken",
        "invalidsecuritytoken",
        "invalidtoken",
        "requestexpired",
    }
)


@dataclass
class ApiConfig:
    """Configuration for a single API endpoint."""

    action: str
    method: str = "POST"
    path: str = "/"
    form: Optional[Dict[str, Any]] = None
    header: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.form is None:
            self.form = {}
        if self.header is None:
            self.header = {}


class BaseServiceClient(Service):
    """
    Base class for all Volcengine service clients.

    This class provides:
    1. Unified interface for all Volcengine services (AgentKit, IAM, etc.)
    2. Common implementation using volcengine.base.Service
    3. Shared credential management and API invocation logic

    Subclasses should:
    1. Override API_ACTIONS with their API action configurations
    """

    # Subclasses should override this with their API action configurations
    API_ACTIONS: Dict[str, Union[str, ApiConfig]] = {}

    def __init__(
        self,
        service: str,
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
        session_token: str = "",
        service_name: str = "",
        platform_config: Optional[VolcConfiguration] = None,
        header: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize the service client.

        Args:
            service: Logical service name for signing and endpoint resolution
            access_key: Volcengine access key
            secret_key: Volcengine secret key
            region: Volcengine region override for endpoint
            session_token: Optional session token
            service_name: Service name for logging
            platform_config: Optional platform-level configuration overrides
        """
        if platform_config is None:
            platform_config = VolcConfiguration()
        self._platform_config = platform_config
        self._explicit_credentials = bool(access_key and secret_key)
        self._credential_source: Optional[str] = None

        creds = resolve_credentials(
            service=service,
            explicit_access_key=access_key or None,
            explicit_secret_key=secret_key or None,
            explicit_session_token=session_token or None,
            platform_config=platform_config,
        )
        self._credential_source = getattr(creds, "source", None)

        ep = resolve_endpoint(
            service=service,
            region=region or None,
            platform_config=platform_config,
        )

        self.access_key = creds.access_key
        self.secret_key = creds.secret_key
        # An explicitly passed session_token must win: resolve_credentials only
        # resolves ak/sk, so STS callers would otherwise lose their token here.
        self.session_token = session_token or creds.session_token

        self.host = ep.host
        self.region = ep.region
        self.service = ep.service
        self.scheme = ep.scheme
        self.api_version = ep.api_version

        self.service_name = service_name

        if header is None:
            effective_header: Dict[str, Any] = {"Accept": "application/json"}
        else:
            effective_header = header.copy()
            if "Accept" not in effective_header:
                effective_header = {"Accept": "application/json", **effective_header}

        effective_header = ensure_x_custom_source_header(effective_header)
        # Create ServiceInfo
        self.service_info = ServiceInfo(
            host=self.host,
            header=effective_header,
            credentials=VolcCredentials(
                ak=self.access_key,
                sk=self.secret_key,
                service=self.service,
                region=self.region,
                session_token=self.session_token or "",
            ),
            connection_timeout=int(http_timeout()),
            socket_timeout=int(http_timeout()),
            scheme=self.scheme,
        )

        # Generate ApiInfo for all actions
        self.api_info = self._build_api_info()

        # Initialize parent Service class
        Service.__init__(self, service_info=self.service_info, api_info=self.api_info)
        # need setting ak/sk after initializing Service to avoid volcengine SDK bugs
        self.set_ak(self.access_key)
        self.set_sk(self.secret_key)
        if self.session_token:
            self.set_session_token(self.session_token)

        self._install_retry_adapter()

    def _install_retry_adapter(self) -> None:
        """Retry transient overload responses (429/503) and connection failures
        with exponential backoff on the shared ``Service`` session.

        Scoped to cases that mean the request was not processed, so
        non-idempotent ``Create*`` actions are never double-executed: read
        timeouts are not retried (``read=0``) and only 429/503 are status-
        retried. Honors ``Retry-After``. Disabled with AGENTKIT_HTTP_RETRIES=0.
        """
        retries = http_retries()
        if retries <= 0:
            return
        session = getattr(self, "session", None)
        if session is None:
            return
        retry = Retry(
            total=retries,
            connect=retries,
            read=0,
            status=retries,
            status_forcelist=(429, 503),
            allowed_methods=None,  # OpenAPI calls are POST; gate by status only
            backoff_factor=0.5,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

    def _should_auto_refresh_vefaas_credentials(self) -> bool:
        if self._explicit_credentials:
            return False
        if self._platform_config.provider != CloudProvider.VOLCENGINE:
            return False
        return self._credential_source == "vefaas"

    def _apply_credentials(self, creds: PlatformCredentials) -> bool:
        new_token = creds.session_token or ""
        old_token = self.session_token or ""
        if (
            creds.access_key == self.access_key
            and creds.secret_key == self.secret_key
            and new_token == old_token
        ):
            return False

        self.access_key = creds.access_key
        self.secret_key = creds.secret_key
        self.session_token = creds.session_token

        self.service_info.credentials = VolcCredentials(
            ak=self.access_key,
            sk=self.secret_key,
            service=self.service,
            region=self.region,
            session_token=self.session_token or "",
        )
        self.set_ak(self.access_key)
        self.set_sk(self.secret_key)
        self.set_session_token(self.session_token or "")
        return True

    def _refresh_credentials_if_needed(self, *, force: bool = False) -> bool:
        if not self._should_auto_refresh_vefaas_credentials():
            return False
        creds = self._platform_config.get_vefaas_iam_credentials(force=force)
        if not creds:
            return False
        applied = self._apply_credentials(creds)
        if applied:
            logger.info(
                "Refreshed vefaas credentials (force=%s) for service %s",
                force,
                self.service,
            )
        return applied

    def _is_probable_credential_error_code(self, code: str) -> bool:
        c = (code or "").lower()
        return c in _CREDENTIAL_ERROR_TOKENS

    def _is_probable_credential_error_text(self, text: str) -> bool:
        t = (text or "").lower()
        return any(token in t for token in _CREDENTIAL_ERROR_TOKENS)

    def _build_api_info(self) -> Dict[str, ApiInfo]:
        """
        Build ApiInfo dictionary from API_ACTIONS.

        Supports two formats:
        1. Simple string: {"ListItems": "ListItems"} -> POST to / with Action query param
        2. ApiConfig: {"GetItem": ApiConfig(action="GetItem", method="GET", path="/items")}

        Returns:
            Dictionary mapping action names to ApiInfo objects
        """
        api_info = {}
        for action_key, action_config in self.API_ACTIONS.items():
            # If it's a simple string, use default POST configuration
            if isinstance(action_config, str):
                api_info[action_key] = ApiInfo(
                    method="POST",
                    path="/",
                    query={"Action": action_config, "Version": self.api_version},
                    form={},
                    header={},
                )
            # If it's an ApiConfig, use the detailed configuration
            elif isinstance(action_config, ApiConfig):
                api_info[action_key] = ApiInfo(
                    method=action_config.method,
                    path=action_config.path,
                    query={"Action": action_config.action, "Version": self.api_version},
                    form=action_config.form,
                    header=action_config.header,
                )
            else:
                raise ValueError(
                    f"Invalid API_ACTIONS configuration for '{action_key}': "
                    f"expected str or ApiConfig, got {type(action_config)}"
                )
        return api_info

    def _invoke_api(
        self,
        api_action: str,
        request: Any,
        response_type: Type[T],
        params: Dict[str, Any] = None,
    ) -> T:
        """
        Unified API invocation with error handling.

        Args:
            api_action: The API action name (e.g., 'GetUser', 'ListRuntimes')
            request: The request object (Pydantic model)
            response_type: The response type to parse into
            params: Additional query parameters

        Returns:
            Typed response object

        Raises:
            ApiError: If the API call fails or returns an error response.
            NetworkError: If a transport-level failure occurs.
        """
        # Imported lazily: ``agentkit.toolkit`` pulls in ``sdk`` which imports
        # back into ``agentkit.client``, so a module-level import would cycle.
        from agentkit.toolkit.errors import ApiError

        self._refresh_credentials_if_needed()
        last_error: Optional[BaseException] = None

        for attempt in (0, 1):
            logger.debug("Invoking API %s (attempt %d)", api_action, attempt)
            if attempt == 1:
                self._refresh_credentials_if_needed(force=True)

            try:
                res = self.json(
                    api=api_action,
                    params=params or {},
                    body=json.dumps(
                        request.model_dump(by_alias=True, exclude_none=True)
                    ),
                )
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError,
                requests.exceptions.RequestException,
            ) as e:
                # Transport-level failure: not a credential issue, surface as
                # a typed network error so callers can distinguish it.
                raise NetworkError(f"Failed to {api_action}: network error") from e
            except Exception as e:
                last_error = e
                if attempt == 0 and self._is_probable_credential_error_text(str(e)):
                    logger.debug(
                        "Retrying %s after probable credential error", api_action
                    )
                    continue
                raise ApiError(f"Failed to {api_action}: {str(e)}") from e

            if not res:
                raise ApiError(f"Empty response from {api_action} request.")

            try:
                response_data = json.loads(res)
            except (ValueError, TypeError) as e:
                raise ApiError(
                    f"Failed to {api_action}: malformed response body"
                ) from e

            metadata = response_data.get("ResponseMetadata", {})
            if metadata.get("Error"):
                err = metadata.get("Error", {}) or {}
                error_code = str(err.get("Code") or "")
                error_msg = str(err.get("Message") or "Unknown error")
                if attempt == 0 and (
                    self._is_probable_credential_error_code(error_code)
                    or self._is_probable_credential_error_text(error_msg)
                ):
                    logger.debug(
                        "Retrying %s after credential error code %s",
                        api_action,
                        error_code or "<none>",
                    )
                    continue
                raise ApiError(
                    f"Failed to {api_action}: {error_msg}",
                    error_code=error_code or None,
                )

            return response_type(**response_data.get("Result", {}))

        if last_error is not None:
            raise ApiError(
                f"Failed to {api_action}: {str(last_error)}"
            ) from last_error
        raise ApiError(f"Failed to {api_action}: Unknown error")

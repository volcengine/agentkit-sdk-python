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

import asyncio
from functools import wraps
from typing import Any, Callable

from agentkit.utils.ve_sign import ve_request
from agentkit.platform import (
    resolve_credentials,
    resolve_endpoint,
)
from agentkit.toolkit.errors import ApiError


def requires_api_key(
    *,
    provider_name: str,
    into: str = "api_key",
    identity_token: str | None = None,
):
    """Decorator that fetches an API key before calling the decorated function.

    Args:
        provider_name: The credential provider name
        into: Parameter name to inject the API key into
        identity_token: Workload identity token forwarded to ``GetResourceApiKey``
            as ``IdentityToken``. Supply this when the provider validates it;
            when omitted the field is not sent (previously a hard-coded
            ``"identity_token"`` placeholder was sent, which never validated).

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        def _get_api_key() -> str:
            creds = resolve_credentials("identity")
            endpoint = resolve_endpoint("identity")
            access_key = creds.access_key
            secret_key = creds.secret_key
            # Forward the STS session token so signing works under temporary
            # credentials (ve_request signs X-Security-Token when present).
            session_token = creds.session_token or None

            request_body: dict[str, str] = {"ProviderName": provider_name}
            if identity_token:
                request_body["IdentityToken"] = identity_token

            response = ve_request(
                request_body=request_body,
                action="GetResourceApiKey",
                ak=access_key,
                sk=secret_key,
                session_token=session_token,
                version=endpoint.api_version,
                service=endpoint.service,
                host=endpoint.host,
                region=endpoint.region,
            )

            try:
                return response["Result"]["ApiKey"]
            except Exception as e:
                raise ApiError("GetResourceApiKey did not return an ApiKey") from e

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            api_key = _get_api_key()
            kwargs[into] = api_key
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            api_key = _get_api_key()
            kwargs[into] = api_key
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator

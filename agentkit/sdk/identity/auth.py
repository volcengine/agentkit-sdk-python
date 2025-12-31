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


def requires_api_key(*, provider_name: str, into: str = "api_key"):
    """Decorator that fetches an API key before calling the decorated function.

    Args:
        provider_name: The credential provider name
        into: Parameter name to inject the API key into

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        def _get_api_key() -> str:
            creds = resolve_credentials("identity")
            endpoint = resolve_endpoint("identity")
            access_key = creds.access_key
            secret_key = creds.secret_key
            session_token = ""

            response = ve_request(
                request_body={
                    "ProviderName": provider_name,
                    "IdentityToken": "identity_token",
                },
                action="GetResourceApiKey",
                header={"X-Security-Token": session_token} if session_token else {},
                ak=access_key,
                sk=secret_key,
                version=endpoint.api_version,
                service=endpoint.service,
                host=endpoint.host,
                region=endpoint.region,
            )

            try:
                return response["Result"]["ApiKey"]
            except Exception as _:
                raise RuntimeError(f"Get api key failed: {response}")

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

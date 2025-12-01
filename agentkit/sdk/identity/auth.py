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
import os
from functools import wraps
from typing import Any, Callable

from agentkit.utils.credential import get_credential_from_vefaas_iam
from agentkit.utils.ve_sign import ve_request, get_identity_host_info


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
            access_key = os.getenv("VOLCENGINE_ACCESS_KEY")
            secret_key = os.getenv("VOLCENGINE_SECRET_KEY")
            session_token = ""
            host, version, service, region = get_identity_host_info()

            if not (access_key and secret_key):
                cred = get_credential_from_vefaas_iam()
                access_key = cred.access_key_id
                secret_key = cred.secret_access_key
                session_token = cred.session_token

            response = ve_request(
                request_body={
                    "ProviderName": provider_name,
                    "IdentityToken": "identity_token",
                },
                action="GetResourceApiKey",
                header={"X-Security-Token": session_token} if session_token else {},
                ak=access_key,
                sk=secret_key,
                version=version,
                service=service,
                host=host,
                region=region,
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

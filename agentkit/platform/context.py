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

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Optional, Iterator, Union

from agentkit.platform.provider import CloudProvider, normalize_cloud_provider


_default_cloud_provider: ContextVar[Optional[CloudProvider]] = ContextVar(
    "default_cloud_provider", default=None
)


def set_default_cloud_provider(
    provider: Union[str, CloudProvider, None],
) -> Token[Optional[CloudProvider]]:
    return _default_cloud_provider.set(normalize_cloud_provider(provider))


def reset_default_cloud_provider(token: Token[Optional[CloudProvider]]) -> None:
    _default_cloud_provider.reset(token)


def get_default_cloud_provider() -> Optional[CloudProvider]:
    return _default_cloud_provider.get()


@contextmanager
def default_cloud_provider(
    provider: Union[str, CloudProvider, None],
) -> Iterator[None]:
    token = set_default_cloud_provider(provider)
    try:
        yield
    finally:
        reset_default_cloud_provider(token)

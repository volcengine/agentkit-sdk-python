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

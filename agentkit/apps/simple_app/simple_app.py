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

import inspect
import logging
from typing import Callable
from typing_extensions import override

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route

from agentkit.apps.base_app import BaseAgentkitApp
from agentkit.apps.simple_app.simple_app_handlers import (
    AsyncTaskHandler,
    InvokeHandler,
    PingHandler,
)

logger = logging.getLogger("agentkit." + __name__)


class AgentkitSimpleApp(BaseAgentkitApp, Starlette):
    def __init__(self) -> None:
        self.ping_handler = PingHandler()
        self.invoke_handler = InvokeHandler()
        self.async_task_handler = AsyncTaskHandler()

        routes = [
            Route("/ping", self.ping_handler.handle, methods=["GET"]),
            Route("/health", self.ping_handler.health_check, methods=["GET"]),
            Route("/readiness", self.ping_handler.readiness, methods=["GET"]),
            Route("/liveness", self.ping_handler.liveness, methods=["GET"]),
            Route("/invoke", self.invoke_handler.handle, methods=["POST"]),
        ]

        super().__init__(routes=routes)

    def entrypoint(self, func: Callable) -> Callable:
        self.invoke_handler.func = func
        return func

    def ping(self, func: Callable) -> Callable:
        assert len(list(inspect.signature(func).parameters.keys())) == 0, (
            f"Health check function `{func.__name__}` should not receive any arguments."
        )

        self.ping_handler.func = func
        return func

    # async def async_task(self, func: Callable) -> Callable:
    #     if not asyncio.iscoroutinefunction(func):
    #         raise ValueError("@async_task can only be applied to async functions")

    #     async def wrapper(*args, **kwargs):
    #         task_id = self.async_task_handler.add_async_task(func.__name__)

    #         try:
    #             logger.debug("Starting async task: %s", func.__name__)
    #             start_time = time.time()
    #             result = await func(*args, **kwargs)
    #             duration = time.time() - start_time
    #             logger.info("Async task completed: %s (%.3fs)", func.__name__, duration)
    #             return result
    #         except Exception as e:
    #             duration = time.time() - start_time
    #             logger.error(
    #                 "Async task failed: %s (%.3fs) - %s: %s",
    #                 func.__name__,
    #                 duration,
    #                 type(e).__name__,
    #                 e,
    #             )
    #             raise
    #         finally:
    #             self.async_task_handler.complete_async_task(task_id)

    #     wrapper.__name__ = func.__name__
    #     return wrapper

    @override
    def run(self, host: str | None, port: int = 8000):
        host = host if host else "0.0.0.0"
        uvicorn.run(self, host=host, port=port)

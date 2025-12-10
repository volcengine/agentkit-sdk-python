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
import os
from functools import wraps
from typing import Any, Callable, override

from fastmcp import FastMCP
from fastmcp.server.server import Transport

from agentkit.apps.base_app import BaseAgentkitApp
from agentkit.apps.mcp_app.telemetry import telemetry

logger = logging.getLogger(__name__)


class AgentkitMCPApp(BaseAgentkitApp):
    def __init__(self) -> None:
        super().__init__()

        self._mcp_server = FastMCP("agentkit.mcp_server")

    def tool(self, func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                # with tracer.start_as_current_span("tool") as span:
                with telemetry.tracer.start_as_current_span(name="tool") as span:
                    exception = None
                    try:
                        result = await func(*args, **kwargs)

                    except Exception as e:
                        logger.error("Invoke tool function failed: %s", e)
                        exception = e
                        raise e
                    finally:
                        # handler trace span and metrics
                        telemetry.trace_tool(
                            func,
                            span,
                            args,
                            func_result=result,
                            operation_type="mcp_tool",
                            exception=exception,
                        )

                return result

            self._mcp_server.tool(async_wrapper)
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                # with tracer.start_as_current_span("tool") as span:
                with telemetry.tracer.start_as_current_span(name="tool") as span:
                    exception = None
                    try:
                        result = func(*args, **kwargs)
                    except Exception as e:
                        logger.error("Invoke tool function failed: %s", e)
                        exception = e
                        raise e
                    finally:
                        telemetry.trace_tool(
                            func,
                            span,
                            args,
                            func_result=result,
                            operation_type="mcp_tool",
                            exception=exception,
                        )
                return result

            self._mcp_server.tool(sync_wrapper)

        return func

    def agent_as_a_tool(self, func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                with telemetry.tracer.start_as_current_span(name="tool") as span:
                    exception = None
                    try:
                        result = await func(*args, **kwargs)
                    except Exception as e:
                        logger.error("Invoke tool function failed: %s", e)
                        exception = e
                        raise e
                    finally:
                        telemetry.trace_tool(
                            func,
                            span,
                            args=args,
                            func_result=result,
                            operation_type="agent_mcp_tool",
                            exception=exception,
                        )
                return result

            self._mcp_server.tool(async_wrapper)
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                with telemetry.tracer.start_as_current_span(name="tool") as span:
                    exception = None
                    try:
                        result = func(*args, **kwargs)
                    except Exception as e:
                        logger.error("Invoke tool function failed: %s", e)
                        exception = e
                        raise e
                    finally:
                        telemetry.trace_tool(
                            func,
                            span,
                            args,
                            func_result=result,
                            operation_type="agent_mcp_tool",
                            exception=exception,
                        )
                return result

            self._mcp_server.tool(sync_wrapper)

        return func

    def add_env_detect_tool(self):
        def is_agentkit_runtime() -> bool:
            if os.getenv("RUNTIME_IAM_ROLE_TRN", ""):
                return True
            else:
                return False

        def get_env() -> dict:
            return {"env": "agentkit" if is_agentkit_runtime() else "veadk"}

        self._mcp_server.tool(get_env)

    @override
    def run(
        self,
        host: str,
        port: int = 8000,
        transport: Transport = "streamable-http",
    ) -> None:
        self.add_env_detect_tool()

        self._mcp_server.run(host=host, port=port, transport=transport)

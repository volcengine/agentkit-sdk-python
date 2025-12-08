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
import inspect
import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, override

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from agentkit.apps.simple_app.telemetry import telemetry
from agentkit.apps.utils import safe_serialize_to_json_string
from opentelemetry import context as context_api
from opentelemetry import trace

logger = logging.getLogger("agentkit." + __name__)


class BaseHandler(ABC):
    def __init__(self, func: Callable | None = None) -> None:
        self.func = func

    @abstractmethod
    async def handle(self, request: Request) -> Response: ...


class InvokeHandler(BaseHandler):
    @override
    async def handle(self, request: Request) -> Response | StreamingResponse:
        if not self.func:
            logger.error("Invoke handler function is not set")
            return Response(status_code=404)

        span = telemetry.tracer.start_span(name="agentkit_invocation")
        ctx = trace.set_span_in_context(span)
        context_api.attach(ctx)

        try:
            payload, headers, result = await self._process_invoke(request)

            # set trace attributes
            telemetry.trace_agent(self.func, span, payload, headers)

            if inspect.isgenerator(result):
                logger.info("Returning streaming response (generator)")
                return StreamingResponse(
                    self._sync_stream_with_error_handling(result),
                    media_type="text/event-stream",
                )

            elif inspect.isasyncgen(result):
                logger.info("Returning streaming response (async generator)")
                return StreamingResponse(
                    self._stream_with_error_handling(result),
                    media_type="text/event-stream",
                )

            logger.info("Returning non-streaming response")
            safe_json_string = safe_serialize_to_json_string(result)
            telemetry.trace_agent_finish(safe_json_string, None)
        except Exception as e:
            logger.error("Invoke handler function failed: %s", e)
            telemetry.trace_agent_finish("", e)
            raise e

        return Response(safe_json_string, media_type="application/json")

    async def _process_invoke(self, request: Request) -> tuple[dict, dict, Any]:
        """Process different cases of the entrypoint function.

        Handles different signatures of the entrypoint function:

        Cases:
            - No input arguments `func()` -> `func()`
            - One input arguments
                - params[0] == request `func(request)` -> `func(request: Request)`
                - params[0] != request `func(foo)` -> `func(payload: dict)`
            - More than one input arguments `func(foo, bar, ...)` -> `func(payload: dict, headers: dict)`
        """
        if not self.func:
            logger.error("Invoke handler function is not set")
            return {}, {}, {"message": "Invoke handler function is not set."}

        # parse request
        payload: dict = await request.json()
        headers: dict = dict(request.headers)

        # parse entrypoint function params
        params = list(inspect.signature(self.func).parameters.keys())
        num_params = len(params)

        if num_params == 0:
            args = ()
        elif num_params == 1:
            if params[0].lower() == "request":
                args = (request,)
            else:
                args = (payload,)
        else:
            args = (payload, headers)

        if asyncio.iscoroutinefunction(self.func):
            return payload, headers, await self.func(*args)
        else:
            return payload, headers, self.func(*args)

    def _convert_to_sse(self, obj) -> bytes:
        """Convert object to Server-Sent Events format using safe serialization.

        Args:
            obj: Object to convert to SSE format

        Returns:
            bytes: SSE-formatted data ready for streaming
        """
        if isinstance(obj, str):
            json_string = obj
        else:
            json_string = safe_serialize_to_json_string(obj)
        sse_data = f"data: {json_string}\n\n"
        return sse_data.encode("utf-8")

    def _sync_stream_with_error_handling(self, generator):
        """Wrap sync generator to handle errors and convert to SSE format."""
        exception = None
        last_value = ""
        try:
            for value in generator:
                last_value = value
                yield self._convert_to_sse(value)
        except Exception as e:
            exception = e
            logger.exception("Error in sync streaming")
            error_event = {
                "error": str(e),
                "error_type": type(e).__name__,
                "message": "An error occurred during streaming",
            }
            yield self._convert_to_sse(error_event)
        finally:
            # finish trace span and record metrics
            result = safe_serialize_to_json_string(last_value)
            telemetry.trace_agent_finish(result, exception)

    async def _stream_with_error_handling(self, generator):
        """Wrap async generator to handle errors and convert to SSE format."""
        exception = None
        last_value = ""
        try:
            async for value in generator:
                last_value = value
                yield self._convert_to_sse(value)
        except Exception as e:
            exception = e
            logger.exception("Error in async streaming")
            error_event = {
                "error": str(e),
                "error_type": type(e).__name__,
                "message": "An error occurred during streaming",
            }
            yield self._convert_to_sse(error_event)
        finally:
            # finish trace span and record metrics
            result = safe_serialize_to_json_string(last_value)
            telemetry.trace_agent_finish(result, exception)


class PingHandler(BaseHandler):
    @override
    async def handle(self, request: Request) -> Response:
        if not self.func:
            logger.error("Ping handler function is not set")
            return Response(status_code=404)

        if asyncio.iscoroutinefunction(self.func):
            result = await self.func()
        else:
            result = self.func()

        return JSONResponse(content={"status": result}, media_type="application/json")

    async def health_check(self, request: Request) -> Response:
        return JSONResponse(
            content={
                "status": "healthy",
                "timestamp": time.time(),
                "service": "agent-service",
            },
            media_type="application/json",
        )

    async def readiness(self, request: Request) -> Response:
        """Check if the application is ready to serve requests."""
        # if getattr(app.state, "is_ready", True):
        #     return "success"
        return JSONResponse(
            content={
                "status": "success",
                "timestamp": time.time(),
                "service": "agent-service",
            },
            media_type="application/json",
        )
        # raise HTTPException(
        #     status_code=500,
        #     detail="Application is not ready",
        # )

    async def liveness(self, request: Request) -> Response:
        """Check if the application is alive and healthy."""
        # if getattr(app.state, "is_healthy", True):
        return JSONResponse(
            content={
                "status": "success",
                "timestamp": time.time(),
                "service": "agent-service",
            },
            media_type="application/json",
        )
        # raise HTTPException(
        #     status_code=500,
        #     detail="Application is not healthy",
        # )

    def _format_ping_status(self, result: str | dict) -> dict:
        if isinstance(result, str):
            return {"status": result}
        elif isinstance(result, dict):
            return result
        else:
            logger.error(
                f"Health check function {self.func.__name__} must return `dict` or `str` type."
            )
            return {"status": "error", "message": "Invalid response type."}


class AsyncTaskHandler(BaseHandler):
    def __init__(self, func: Callable | None = None):
        super().__init__(func=func)

        self._active_tasks = {}
        self._task_counter_lock: threading.Lock = threading.Lock()

    @override
    async def handle(self) -> Response:
        return Response()

    def get_async_task_info(self) -> dict[str, Any]:
        """Get info about running async tasks."""
        running_jobs = []
        for t in self._active_tasks.values():
            try:
                running_jobs.append(
                    {
                        "name": t.get("name", "unknown"),
                        "duration": time.time() - t.get("start_time", time.time()),
                    }
                )
            except Exception as e:
                logger.warning("Caught exception, continuing...: %s", e)
                continue

        return {"active_count": len(self._active_tasks), "running_jobs": running_jobs}

    def add_async_task(self, name: str, metadata: Optional[dict] = None) -> int:
        """Register an async task for interactive health tracking.

        This method provides granular control over async task lifecycle,
        allowing developers to interactively start tracking tasks for health monitoring.
        Use this when you need precise control over when tasks begin and end.

        Args:
            name: Human-readable task name for monitoring
            metadata: Optional additional task metadata

        Returns:
            Task ID for tracking and completion

        Example:
            task_id = app.add_async_task("file_processing", {"file": "data.csv"})
            # ... do background work ...
            app.complete_async_task(task_id)
        """
        with self._task_counter_lock:
            task_id = hash(str(uuid.uuid4()))  # Generate truly unique hash-based ID

            # Register task start with same structure as @async_task decorator
            task_info = {"name": name, "start_time": time.time()}
            if metadata:
                task_info["metadata"] = metadata

            self._active_tasks[task_id] = task_info

        logger.info("Async task started: %s (ID: %s)", name, task_id)
        return task_id

    def complete_async_task(self, task_id: int) -> bool:
        """Mark an async task as complete for interactive health tracking.

        This method provides granular control over async task lifecycle,
        allowing developers to interactively complete tasks for health monitoring.
        Call this when your background work finishes.

        Args:
            task_id: Task ID returned from add_async_task

        Returns:
            True if task was found and completed, False otherwise

        Example:
            task_id = app.add_async_task("file_processing")
            # ... do background work ...
            completed = app.complete_async_task(task_id)
        """
        with self._task_counter_lock:
            task_info = self._active_tasks.pop(task_id, None)
            if task_info:
                task_name = task_info.get("name", "unknown")
                duration = time.time() - task_info.get("start_time", time.time())

                logger.info(
                    "Async task completed: %s (ID: %s, Duration: %.2fs)",
                    task_name,
                    task_id,
                    duration,
                )
                return True
            else:
                logger.warning("Attempted to complete unknown task ID: %s", task_id)
                return False

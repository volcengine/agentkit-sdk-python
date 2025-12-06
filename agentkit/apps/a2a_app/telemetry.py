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


import logging
import time
from typing import Callable

from opentelemetry import trace
from opentelemetry.trace import get_tracer
from opentelemetry.metrics import get_meter
from opentelemetry.trace.span import Span
from a2a.server.agent_execution.context import RequestContext
from google.adk.a2a.converters.request_converter import _get_user_id

from agentkit.apps.utils import safe_serialize_to_json_string

_GEN_AI_CLIENT_OPERATION_DURATION_BUCKETS = [
    0.01,
    0.02,
    0.04,
    0.08,
    0.16,
    0.32,
    0.64,
    1.28,
    2.56,
    5.12,
    10.24,
    20.48,
    40.96,
    81.92,
    163.84,
]

logger = logging.getLogger("agentkit." + __name__)


class Telemetry:
    def __init__(self):
        self.tracer = get_tracer("agentkit.a2a_app")
        self.meter = get_meter("agentkit.a2a_app")
        self.latency_histogram = self.meter.create_histogram(
            name="agentkit_runtime_operation_latency",
            description="operation latency",
            unit="s",
            explicit_bucket_boundaries_advisory=_GEN_AI_CLIENT_OPERATION_DURATION_BUCKETS,
        )

    def trace_a2a_agent(
        self,
        func: Callable,
        span: Span,
        request: RequestContext,
        result: any,
        exception: Exception,
    ) -> None:
        """Get current span and set required attributes."""
        trace_id = span.get_span_context().trace_id
        span_id = span.get_span_context().span_id
        logger.debug(
            f"Set attributes for span with trace_id={trace_id}, span_id={span_id}"
        )

        # ===============================
        # Set attributes for current span
        # ===============================

        span.set_attribute(key="gen_ai.system", value="agentkit")

        span.set_attribute(key="gen_ai.func_name", value=func.__name__)

        # TODO:  get user_id and session_id, output from event queue
        session_id = request.context_id
        if session_id:
            span.set_attribute(key="gen_ai.session.id", value=session_id)
        user_id = _get_user_id(request)
        if user_id:
            span.set_attribute(key="gen_ai.user.id", value=user_id)

        span.set_attribute(
            key="gen_ai.input",
            value=safe_serialize_to_json_string(request.message.parts),
        )

        span.set_attribute(key="gen_ai.span.kind", value="a2a_agent")
        span.set_attribute(key="gen_ai.operation.name", value="invoke_agent")
        span.set_attribute(key="gen_ai.operation.type", value="a2a_agent")
        attributes = {
            "gen_ai_operation_name": "invoke_agent",
            "gen_ai_operation_type": "a2a_agent",
        }

        if exception:
            self.handle_exception(span, exception)
            attributes["error_type"] = exception.__class__.__name__

        # record latency metrics
        if hasattr(span, "start_time") and self.latency_histogram:
            duration = (time.time_ns() - span.start_time) / 1e9  # type: ignore
            self.latency_histogram.record(duration, attributes)

    @staticmethod
    def handle_exception(span: trace.Span, exception: Exception) -> None:
        status = trace.Status(
            status_code=trace.StatusCode.ERROR,
            # Follow the format in OTEL SDK for description, see:
            # https://github.com/open-telemetry/opentelemetry-python/blob/2b9dcfc5d853d1c10176937a6bcaade54cda1a31/opentelemetry-api/src/opentelemetry/trace/__init__.py#L588  # noqa E501
            description=f"{type(exception).__name__}: {exception}",
        )
        span.set_status(status)
        span.record_exception(exception)


telemetry = Telemetry()

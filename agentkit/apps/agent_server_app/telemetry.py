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
from typing import Optional

from opentelemetry import trace
from opentelemetry.trace import get_tracer
from opentelemetry.metrics import get_meter
from opentelemetry.trace.span import Span

from agentkit.apps.utils import safe_serialize_to_json_string

_INVOKE_PATH = ["/run_sse", "/run", "/invoke"]

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
        self.tracer = get_tracer("agentkit.agent_server_app")
        self.meter = get_meter("agentkit.agent_server_app")
        self.latency_histogram = self.meter.create_histogram(
            name="agentkit_runtime_operation_latency",
            description="operation latency",
            unit="s",
            explicit_bucket_boundaries_advisory=_GEN_AI_CLIENT_OPERATION_DURATION_BUCKETS,
        )

    def trace_agent_server(
        self,
        func_name: str,
        span: Span,
        headers: dict,
        text: str,
    ) -> None:
        span.set_attribute(key="gen_ai.system", value="agentkit")
        span.set_attribute(key="gen_ai.func_name", value=func_name)

        span.set_attribute(
            key="gen_ai.request.headers",
            value=safe_serialize_to_json_string(headers),
        )

        session_id = headers.get("session_id")
        if session_id:
            span.set_attribute(key="gen_ai.session.id", value=session_id)
        user_id = headers.get("user_id")
        if user_id:
            span.set_attribute(key="gen_ai.user.id", value=user_id)

        # Currently unable to retrieve input
        # span.set_attribute(
        #     key="gen_ai.input", value=safe_serialize_to_json_string(text)
        # )

        span.set_attribute(key="gen_ai.span.kind", value="agent_server")
        span.set_attribute(key="gen_ai.operation.name", value="invoke_agent")
        span.set_attribute(key="gen_ai.operation.type", value="agent_server")

    def trace_agent_server_finish(
        self,
        path: str,
        func_result: str,
        exception: Optional[Exception],
    ) -> None:
        span = trace.get_current_span()
        if span and span.is_recording():
            # Currently unable to retrieve output
            # span.set_attribute(key="gen_ai.output", value=func_result)

            attributes = {
                "gen_ai_operation_name": "invoke_agent",
                "gen_ai_operation_type": "agent_server",
            }
            if exception:
                self.handle_exception(span, exception)
                attributes["error_type"] = exception.__class__.__name__

            # only record invoke request latency metrics
            if (
                hasattr(span, "start_time")
                and self.latency_histogram
                and path in _INVOKE_PATH
            ):
                duration = (time.time_ns() - span.start_time) / 1e9  # type: ignore
                self.latency_histogram.record(duration, attributes)
            span.end()

    @staticmethod
    def handle_exception(span: trace.Span, exception: Exception) -> None:
        status = trace.Status(
            status_code=trace.StatusCode.ERROR,
            description=f"{type(exception).__name__}: {exception}",
        )
        span.set_status(status)
        span.record_exception(exception)


telemetry = Telemetry()

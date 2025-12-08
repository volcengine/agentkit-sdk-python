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

'''
**simple agent demo app with veadk and apmplus**

Before running, the user must set the following environment variables; otherwise, runtime exceptions will inevitably occur:
- MODEL_AGENT_API_KEY
- OBSERVABILITY_OPENTELEMETRY_APMPLUS_API_KEY
- OBSERVABILITY_OPENTELEMETRY_APMPLUS_ENDPOINT
- OBSERVABILITY_OPENTELEMETRY_APMPLUS_SERVICE_NAME

MODEL_AGENT_API_KEY is used to access the model service of the Volcano Engine Ark platform.
The remaining three variables are used to set up the observable services of APMPLUS

'''

import logging

from veadk import Agent, Runner
# from veadk.tools.demo_tools import get_city_weather
from veadk.tracing.telemetry.exporters.apmplus_exporter import APMPlusExporter
from veadk.tracing.telemetry.opentelemetry_tracer import OpentelemetryTracer

from agentkit.apps import AgentkitSimpleApp

logger = logging.getLogger(__name__)


app = AgentkitSimpleApp()

tracer = OpentelemetryTracer(exporters=[APMPlusExporter()])
agent = Agent(tracers=[tracer])
runner = Runner(agent=agent)


@app.entrypoint
async def run(payload: dict, headers: dict) -> str:
    prompt = payload["prompt"]
    user_id = headers["user_id"]
    session_id = headers["session_id"]

    logger.info(
        f"Running agent with prompt: {prompt}, user_id: {user_id}, session_id: {session_id}"
    )
    response = await runner.run(messages=prompt, user_id=user_id, session_id=session_id)

    logger.info(f"Run response: {response}")
    return response


@app.ping
def ping() -> str:
    return "pong!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
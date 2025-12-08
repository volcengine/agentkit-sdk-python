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

from veadk import Agent, Runner
from veadk.a2a.agent_card import get_agent_card
from veadk.tools.demo_tools import get_city_weather

from agentkit.apps import AgentkitMCPApp

logger = logging.getLogger(__name__)


mcp_app = AgentkitMCPApp()


# add an agent as a tool
APP_NAME = "mcp_sample_app"

agent = Agent(
    tools=[get_city_weather], description="An agent that provides weather information."
)

runner = Runner(agent=agent, app_name=APP_NAME)


@mcp_app.agent_as_a_tool
async def run_agent(
    user_input: str,
    user_id: str = "mcp_user",
    session_id: str = "mcp_session",
) -> str:
    # Set user_id for runner
    runner.user_id = user_id

    # Running agent and get final output
    final_output = await runner.run(
        messages=user_input,
        session_id=session_id,
    )
    return final_output


@mcp_app.tool
async def agent_card() -> dict:
    agent_card = get_agent_card(agent=agent, url="0.0.0.0:8000")

    return agent_card.model_dump()


if __name__ == "__main__":
    mcp_app.run(host="0.0.0.0", port=8000)
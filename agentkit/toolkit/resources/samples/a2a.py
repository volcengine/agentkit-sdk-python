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
from veadk.prompts.agent_default_prompt import DEFAULT_DESCRIPTION, DEFAULT_INSTRUCTION
from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor
from agentkit.apps import AgentkitA2aApp

logger = logging.getLogger(__name__)

a2a_app = AgentkitA2aApp()

agent_name = "{{ agent_name | default('Agent') }}"
{% if description %}description = "{{ description }}" {% else %}description = DEFAULT_DESCRIPTION {% endif %}
{% if system_prompt %}system_prompt = "{{ system_prompt }}" {% else %}system_prompt = DEFAULT_INSTRUCTION {% endif %}
{% if model_name %}model_name = "{{ model_name }}"{% endif %}

tools = []
{% if tools %}
{% if 'web_search' in tools %}
from veadk.tools.builtin_tools.web_search import web_search
tools.append(web_search)
{% endif %}
{% if 'run_code' in tools %}
from veadk.tools.builtin_tools.run_code import run_code
tools.append(run_code)
{% endif %}
{% if 'get_weather' in tools %}
# from veadk.tools.builtin_tools.get_weather import get_weather
# tools.append(get_weather)
{% endif %}
{% else %}
# from veadk.tools.builtin_tools.web_search import web_search
# tools.append(web_search)
{% endif %}

agent = Agent(
    name=agent_name,
    description=description,
    instruction=system_prompt,
{%- if model_name %}
    model_name=model_name,
{%- endif %}
    tools=tools,
)
runner = Runner(agent=agent)

@a2a_app.agent_executor(runner=runner)
class MyAgentExecutor(A2aAgentExecutor):
    pass

@a2a_app.ping
def ping() -> str:
    return "pong!"

if __name__ == "__main__":
    from a2a.types import AgentCard, AgentProvider, AgentSkill, AgentCapabilities
    
    agent_card = AgentCard(
        capabilities=AgentCapabilities(streaming=True),
        description=agent.description,
        name=agent.name,
        default_input_modes=["text"],
        default_output_modes=["text"],
        provider=AgentProvider(organization="veadk", url=""),
        skills=[AgentSkill(id="0", name="chat", description="Chat", tags=["chat"])],
        url="http://0.0.0.0:8000",
        version="1.0.0",
    )
    
    a2a_app.run(
        agent_card=agent_card,
        host="0.0.0.0",
        port=8000,
    )

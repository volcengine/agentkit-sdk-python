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

from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory

from agentkit.apps import AgentkitAgentServerApp
from veadk.prompts.agent_default_prompt import DEFAULT_DESCRIPTION, DEFAULT_INSTRUCTION

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
agent.model._additional_args["stream_options"] = {"include_usage": True}

short_term_memory = ShortTermMemory(backend="local")
agent_server_app = AgentkitAgentServerApp(agent=agent, short_term_memory=short_term_memory)


if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
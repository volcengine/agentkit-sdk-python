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

import os
import logging

from langchain.agents import create_agent
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import message_to_dict
from langchain_litellm import ChatLiteLLM

from agentkit.apps import AgentkitSimpleApp



logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

agent_name = "{{ agent_name | default('Agent') }}"

MODEL_PROVIDER = "volcengine"
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_ARK_MODEL_NAME = "{{ model_name | default('doubao-seed-1-6-250615') }}"
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant. You need to answer the user's questions based on the given context."

model_name = os.getenv("MODEL_AGENT_NAME", DEFAULT_ARK_MODEL_NAME)
model_base_url = os.getenv("MODEL_AGENT_BASE_URL", ARK_BASE_URL)
model_api_key = os.getenv("MODEL_AGENT_API_KEY")

{% if system_prompt %}system_prompt = "{{ system_prompt }}" {% else %}system_prompt = os.getenv("MODEL_AGENT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT) {% endif %}


if model_api_key is None or model_api_key.strip() == "":
    raise ValueError("MODEL_AGENT_API_KEY environment variable is not set, please set it first(use 'agentkit config -e MODEL_AGENT_API_KEY=your_api_key'), get it from https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey")



model = ChatLiteLLM(model= MODEL_PROVIDER + '/' + model_name, api_base=model_base_url, api_key=model_api_key, streaming=True)

agent = create_agent(
    name=agent_name,
    model=model,
    system_prompt=system_prompt,
    checkpointer=InMemorySaver(),
)

app = AgentkitSimpleApp()
@app.entrypoint
async def run(payload: dict, headers: dict):
    prompt = payload["prompt"]
    user_id = headers["user_id"]
    session_id = headers["session_id"]
    logger.info(
        f"Running agent with prompt: {prompt}, user_id: {user_id}, session_id: {session_id}"
    )
    thread_id = user_id + "_" + session_id
    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}
    for chunk in agent.stream({
        "messages": [{"role": "user", "content": prompt}]
    }, stream_mode="messages", config=config):
        logger.debug("Generated event in agent run streaming: %s", chunk)
        if len(chunk) > 0 and isinstance(chunk[0], BaseMessage):
            msg_dict = message_to_dict(chunk[0])
            yield msg_dict
        else:
            logger.warning("Received non-message chunk: %s", chunk)


@app.ping
def ping() -> str:
    return "pong!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
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
Financial Analyst Agent
Before Running:
1. Set the following environment variables:
    - MODEL_AGENT_NAME
    - MODEL_AGENT_API_KEY
    - TOOL_AKSHARE_URL
    - TOOL_EMAIL_URL
2. Run the following command:
    - python financial_analyst.py
'''

import logging
from datetime import datetime
from os import getenv

from google.adk.tools import MCPToolset
from veadk.knowledgebase.knowledgebase import KnowledgeBase
from veadk.memory.long_term_memory import LongTermMemory
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.sandbox.code_sandbox import code_sandbox
from veadk.utils.mcp_utils import get_mcp_params
from veadk import Agent, Runner
# from veadk.tracing.telemetry.exporters.tls_exporter import TLSExporter
# from veadk.tracing.telemetry.opentelemetry_tracer import OpentelemetryTracer
# from veadk.tracing.telemetry.exporters.cozeloop_exporter import CozeloopExporter
# from veadk.tracing.telemetry.exporters.apmplus_exporter import APMPlusExporter

from agentkit.apps import AgentkitSimpleApp

from .agent import agent

logger = logging.getLogger(__name__)
app = AgentkitSimpleApp()

# 1. memory and knowledge
short_term_memory = ShortTermMemory(backend="local")
long_term_memory = LongTermMemory(backend="viking", app_name='financial')
knowledge_base = KnowledgeBase(backend="viking", app_name='financial')

# 2. tools
tools = []
tools.append(code_sandbox)
# tools.append(web_search)


# akshare 数据查询
ak_share_url = getenv("TOOL_AKSHARE_URL")
if ak_share_url is not None and ak_share_url != "":
    tools.append(MCPToolset(
        connection_params=get_mcp_params(url=ak_share_url),
    ))

# 邮件发送
email_share_url = getenv("TOOL_EMAIL_URL")
if email_share_url is not None and email_share_url != "":
    tools.append(MCPToolset(
        connection_params=get_mcp_params(url=email_share_url),
    ))


# 获取当前时间
def get_current_time():
    """获取当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


tools.append(get_current_time)

# async def explicit_save_report_to_memory(report_content: str, tool_context: ToolContext):
#     """保存报告到长期记忆. Call this function only if user explicitly requests to save"""
#     await long_term_memory.add_session_to_memory(tool_context._invocation_context.session)
# tools.append(explicit_save_report_to_memory)

# 3. tracing
# exporters = [CozeloopExporter(), TLSExporter(), APMPlusExporter()]
# tracer = OpentelemetryTracer(exporters=exporters)

# 4. setup agent
agent: Agent = Agent(
    name="financial_analysis_agent",
    description="财务分析师",
    instruction="""
    你是一个财务分析师，可以调用各种工具，完成用户指定给你的财务分析任务。当你接收到任务时，可以按照如下步骤执行：
    1. 首先分析一下用户的问题，提取出任务目标，如果在此过程中，有遇到模糊不清的问题，可以提问让用户补充
    2. 根据任务目标，调用工具进行数据查询和检索。你应该尽可能调用工具来获取数据，当你查询不到数据时，请不要生成假的模拟数据。
    3. 对于查询到的数据，当有需要时你可以执行Python代码对其进行二次分析
    4. 分析一下现有的数据和分析结果，是否还有缺失，如果有缺失，则重复2~4步骤
    5. 当现有的数据和分析结果能够满足任务目标之后，生成一篇专业详细的Markdown格式分析报告，报告中的每处数据，都要标注来源，并在报告最后附带免责声明
    """,
    tools=tools,
    knowledgebase=knowledge_base,
    long_term_memory=long_term_memory,
    short_term_memory=short_term_memory,
    # tracers=[tracer]
)

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

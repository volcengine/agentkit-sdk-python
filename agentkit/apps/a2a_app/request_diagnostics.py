"""只读取 A2A 请求的诊断标识，不改变协议消息或任务语义。"""

import json
import re

from agentkit.apps.agent_server_app.diagnostics import DIAGNOSTIC_RUN_ID_PATTERN

_MAX_DIAGNOSTIC_BODY_BYTES = 64 * 1024


def observe_a2a_request(scope, receive, span):
    # 只观察 JSON-RPC 消息执行入口；任务查询、取消和健康检查不归为新一轮执行。
    if scope.get("method") != "POST" or scope.get("path") != "/":
        return receive
    body = bytearray()
    finished = False

    async def observed_receive():
        nonlocal finished
        message = await receive()
        if finished or message.get("type") != "http.request":
            return message
        chunk = message.get("body", b"")
        if len(body) + len(chunk) > _MAX_DIAGNOSTIC_BODY_BYTES:
            # 限制观测缓存；较大请求仍完整交给原处理器，不为埋点改变协议结果。
            body.clear()
            finished = True
            return message
        body.extend(chunk)
        if not message.get("more_body", False):
            finished = True
            try:
                payload = json.loads(body)
                if (
                    isinstance(payload, dict)
                    and payload.get("jsonrpc") == "2.0"
                    and payload.get("method") in ("message/send", "message/stream")
                ):
                    params = payload.get("params")
                    metadata = (
                        params.get("metadata") if isinstance(params, dict) else None
                    )
                    run_id = (
                        metadata.get("agentkitDiagnosticRunId")
                        if isinstance(metadata, dict)
                        else None
                    )
                    if isinstance(run_id, str) and re.fullmatch(
                        DIAGNOSTIC_RUN_ID_PATTERN, run_id
                    ):
                        # Run 仅用于归集观测记录，不作为 Task、会话或租户授权依据。
                        span.set_attribute("agentkit.run.id", run_id)
            except (ValueError, TypeError, RecursionError):
                # 非法可选元数据由协议层处理；观测失败不替换业务错误或输出原始正文。
                pass
            finally:
                body.clear()
        return message

    return observed_receive

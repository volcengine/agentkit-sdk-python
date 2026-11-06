"""请求遥测仅记录明确允许的协议和关联字段。"""

import re


def telemetry_request_headers(headers: dict[str, str]) -> dict[str, str]:
    # 平台会注入临时凭证，且凭证头会继续增加；不能依靠敏感名称黑名单。
    # 这里只构造上报副本，不影响鉴权、业务收到的 Header 或 Trace 上下文提取。
    result = {}
    for key, value in headers.items():
        name = key.lower()
        if not isinstance(value, str):
            continue
        if name == "content-type":
            media_type = value.split(";", 1)[0].strip().lower()
            if len(media_type) <= 128 and re.fullmatch(
                r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", media_type
            ):
                result[name] = media_type
        elif name == "traceparent":
            if re.fullmatch(r"00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}", value):
                result[name] = value
        elif name in {"x-request-id", "x-faas-request-id"}:
            if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
                result[name] = value
    return result

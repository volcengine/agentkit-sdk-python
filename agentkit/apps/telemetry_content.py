"""应用遥测沿用已有内容采集开关，不依赖可选的 VeADK 包。"""

import os


def should_trace_content() -> bool:
    # 未配置时保留 SDK 旧行为；显式关闭或非法配置均不记录正文。
    # 在写入时读取，避免应用初始化先后顺序导致平台注入的开关失效。
    return (
        os.getenv("OBSERVABILITY_OPENTELEMETRY_TRACE_CONTENT", "true").lower() == "true"
    )

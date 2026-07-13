"""Framework adapters for running third-party agents in AgentKit apps."""

from __future__ import annotations

from typing import Any

from agentkit.frameworks._common import (
    FrameworkBridgeError,
    UnsupportedFrameworkAgentError,
)

__all__ = [
    "FrameworkBridgeError",
    "BedrockAgentCoreAgentkitBridge",
    "LangChainAgentkitBridge",
    "LangGraphAgentkitBridge",
    "StrandsAgentkitBridge",
    "UnsupportedFrameworkAgentError",
    "load_entry_object",
]


def __getattr__(name: str) -> Any:
    if name == "BedrockAgentCoreAgentkitBridge":
        from agentkit.frameworks.agentcore import BedrockAgentCoreAgentkitBridge

        return BedrockAgentCoreAgentkitBridge
    if name == "LangChainAgentkitBridge":
        from agentkit.frameworks.langchain import LangChainAgentkitBridge

        return LangChainAgentkitBridge
    if name == "LangGraphAgentkitBridge":
        from agentkit.frameworks.langgraph import LangGraphAgentkitBridge

        return LangGraphAgentkitBridge
    if name == "StrandsAgentkitBridge":
        from agentkit.frameworks.strands import StrandsAgentkitBridge

        return StrandsAgentkitBridge
    if name == "load_entry_object":
        from agentkit.frameworks.migration import load_entry_object

        return load_entry_object
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

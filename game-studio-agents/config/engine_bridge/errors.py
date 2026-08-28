# ============================================================
# 引擎桥接层 · 异常定义
# 版本: v0.1
# 说明: 引擎桥接层统一异常体系。所有引擎操作失败时抛出明确的
#       异常类型，便于上层 Agent 识别并做出降级/重试/上报决策。
#
# 异常层级:
#   EngineBridgeError (基类)
#   ├── EngineConnectionError  - 连接引擎失败
#   ├── EngineNotAvailableError - 引擎未安装/未运行/不在当前环境
#   ├── EngineTimeoutError     - 引擎操作超时
#   ├── MCPError               - MCP 通信错误
#   ├── PluginError            - 引擎插件调用错误
#   └── UnsupportedEngineError - 不支持的引擎类型
# ============================================================
from __future__ import annotations


class EngineBridgeError(Exception):
    """引擎桥接层基类异常。所有引擎相关错误继承此类。"""

    def __init__(self, message: str = "", *, engine: str = "",
                 operation: str = "", details: dict = None):
        self.engine = engine
        self.operation = operation
        self.details = details or {}
        prefix = f"[{engine}:{operation}] " if engine and operation else ""
        super().__init__(f"{prefix}{message}")


class EngineConnectionError(EngineBridgeError):
    """连接引擎失败（如 MCP Server 不可达、插件端口未监听等）。"""


class EngineNotAvailableError(EngineBridgeError):
    """引擎不可用（未安装、未启动、不在当前环境等）。"""


class EngineTimeoutError(EngineBridgeError):
    """引擎操作超时。"""


class MCPError(EngineBridgeError):
    """MCP (Model Context Protocol) 通信错误。"""


class PluginError(EngineBridgeError):
    """引擎插件调用错误。"""


class UnsupportedEngineError(EngineBridgeError):
    """不支持的引擎类型。"""

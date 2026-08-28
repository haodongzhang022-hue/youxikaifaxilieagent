# ============================================================
# 引擎桥接层 · MCP 客户端
# 版本: v0.1
# 说明: 通过 MCP (Model Context Protocol) 协议连接引擎 MCP Server。
#
#   MCP 是 Anthropic 提出的标准协议，用于让 AI 模型与外部工具/服务交互。
#   本模块提供：
#     - MCPClient：管理到引擎 MCP Server 的连接
#     - 工具调用：通过 MCP tools/call 发送引擎操作
#     - 资源访问：通过 MCP resources/read 读取引擎状态
#     - 事件订阅：通过 MCP events 接收引擎事件
#
#   传输协议：当前架构默认 HTTP/SSE 传输，可扩展 WebSocket。
#   引擎 MCP Server 需要由引擎插件/扩展实现（Cocos 插件、UE5 插件）。
#
#   注意：当前 CI 环境无实际引擎，MCPClient 提供 Mock 模式供测试。
# ============================================================
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .errors import EngineConnectionError, EngineTimeoutError, MCPError
from .protocol import EngineCommand, EngineResult, EngineStatus


# ============================================================
# MCP 常量
# ============================================================

# MCP 协议版本
MCP_PROTOCOL_VERSION = "2024-11-05"

# MCP 方法名
MCP_METHODS = {
    "initialize": "initialize",
    "tools_list": "tools/list",
    "tools_call": "tools/call",
    "resources_list": "resources/list",
    "resources_read": "resources/read",
    "events_subscribe": "events/subscribe",
    "events_unsubscribe": "events/unsubscribe",
}


# ============================================================
# MCP 客户端
# ============================================================

class MCPClient:
    """MCP 客户端：管理到引擎 MCP Server 的连接与工具调用。

    架构设计：
      - **连接管理**：connect() / disconnect() / is_connected()
      - **工具调用**：call_tool(name, arguments) → dict
      - **资源读取**：read_resource(uri) → dict
      - **事件订阅**：subscribe_events() / on_event(callback)
      - **命令翻译**：execute_command(cmd) 把 EngineCommand 翻译为 MCP 工具调用

    当前实现：
      - 使用 requests 库做 HTTP 调用（若已安装）；
      - 若 requests 不可用或配置为 mock，使用 Mock 响应（供 CI 测试）。
    """

    def __init__(self, endpoint: str, engine: str = "",
                 api_key: str = "", use_mock: bool = False):
        """
        Args:
            endpoint: MCP Server 的 HTTP/SSE 端点 URL
            engine: 引擎标识（"cocos" / "ue5"），用于错误上下文
            api_key: 可选的 API 密钥
            use_mock: 强制使用 Mock 模式（不发送真实 HTTP 请求）
        """
        self.endpoint = endpoint
        self.engine = engine
        self.api_key = api_key
        self._connected = False
        self._session_id = ""
        self._event_callbacks: List[Callable[[Dict], None]] = []
        self.use_mock = use_mock
        self._request_id = 0
        self._available_tools: List[Dict] = []
        self._last_response_time = 0.0

        # 尝试导入 requests
        try:
            import requests  # noqa: F401
            self._requests_available = True
        except ImportError:
            self._requests_available = False

    # ---------- 连接管理 ----------

    def connect(self, timeout: float = 10.0) -> bool:
        """连接引擎 MCP Server。

        Returns:
            bool: 连接是否成功
        """
        if self._connected:
            return True

        # Mock 模式或 requests 不可用时直接返回成功
        if self.use_mock or not self._requests_available:
            self._connected = True
            self._session_id = f"mock_{uuid.uuid4().hex[:8]}"
            self._last_response_time = time.time()
            return True

        try:
            import requests
            response = requests.post(
                f"{self.endpoint}/initialize",
                json={
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": MCP_METHODS["initialize"],
                    "params": {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "clientInfo": {"name": "engine-bridge", "version": "0.1"},
                    },
                },
                timeout=timeout,
                headers=self._headers(),
            )
            if response.status_code == 200:
                data = response.json()
                self._connected = True
                self._session_id = data.get("result", {}).get("sessionId", "")
                self._last_response_time = time.time()
                # 拉取可用工具列表
                self._load_tools(timeout)
                return True
            raise EngineConnectionError(
                f"MCP Server 返回 HTTP {response.status_code}",
                engine=self.engine, operation="connect",
                details={"endpoint": self.endpoint})
        except EngineConnectionError:
            raise
        except Exception as exc:
            raise EngineConnectionError(
                f"连接 MCP Server 失败: {exc}",
                engine=self.engine, operation="connect",
                details={"endpoint": self.endpoint}) from exc

    def disconnect(self) -> None:
        """断开与引擎 MCP Server 的连接。"""
        self._connected = False
        self._session_id = ""

    @property
    def is_connected(self) -> bool:
        return self._connected

    def status(self) -> EngineStatus:
        """获取连接状态对应的引擎状态。"""
        if not self._connected:
            return EngineStatus.NOT_RUNNING
        return EngineStatus.RUNNING

    # ---------- 工具调用 ----------

    def call_tool(self, tool_name: str, arguments: Dict[str, Any],
                  timeout: float = 30.0) -> Dict[str, Any]:
        """调用引擎 MCP Server 上的工具。

        Args:
            tool_name: 工具名（如 "scene.load" / "node.create"）
            arguments: 工具参数
            timeout: 超时秒数

        Returns:
            dict: 工具调用结果（JSON-RPC result 结构）
        """
        if not self._connected:
            raise EngineConnectionError(
                "MCP 未连接，请先调用 connect()",
                engine=self.engine, operation=f"call_tool({tool_name})")

        # Mock 模式
        if self.use_mock or not self._requests_available:
            return self._mock_call_tool(tool_name, arguments)

        try:
            import requests
            response = requests.post(
                f"{self.endpoint}/tools",
                json={
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": MCP_METHODS["tools_call"],
                    "params": {"name": tool_name, "arguments": arguments},
                },
                timeout=timeout,
                headers=self._headers(),
            )
            if response.status_code != 200:
                raise MCPError(
                    f"MCP 工具调用失败: HTTP {response.status_code}",
                    engine=self.engine, operation=f"call_tool({tool_name})",
                    details={"endpoint": self.endpoint})
            result = response.json()
            self._last_response_time = time.time()
            return result.get("result", result)
        except MCPError:
            raise
        except Exception as exc:
            raise MCPError(
                f"MCP 工具调用异常: {exc}",
                engine=self.engine, operation=f"call_tool({tool_name})") from exc

    def read_resource(self, resource_uri: str,
                      timeout: float = 10.0) -> Dict[str, Any]:
        """读取引擎 MCP Server 上的资源（如场景图、资产信息）。

        Args:
            resource_uri: 资源 URI（如 "scene://current/graph"）
            timeout: 超时秒数

        Returns:
            dict: 资源内容
        """
        if not self._connected:
            raise EngineConnectionError(
                "MCP 未连接，请先调用 connect()",
                engine=self.engine, operation=f"read_resource({resource_uri})")

        if self.use_mock or not self._requests_available:
            return {"uri": resource_uri, "content": {"mock": True}}

        try:
            import requests
            response = requests.post(
                f"{self.endpoint}/resources",
                json={
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": MCP_METHODS["resources_read"],
                    "params": {"uri": resource_uri},
                },
                timeout=timeout,
                headers=self._headers(),
            )
            if response.status_code != 200:
                raise MCPError(
                    f"MCP 资源读取失败: HTTP {response.status_code}",
                    engine=self.engine, operation=f"read_resource({resource_uri})")
            result = response.json()
            return result.get("result", result)
        except MCPError:
            raise
        except Exception as exc:
            raise MCPError(
                f"MCP 资源读取异常: {exc}",
                engine=self.engine, operation=f"read_resource({resource_uri})") from exc

    # ---------- 事件订阅 ----------

    def on_event(self, callback: Callable[[Dict], None]) -> None:
        """注册事件回调。当引擎事件到达时调用。"""
        self._event_callbacks.append(callback)

    def _emit_event(self, event: Dict) -> None:
        """触发所有注册的事件回调。"""
        for cb in self._event_callbacks:
            try:
                cb(event)
            except Exception:  # pragma: no cover
                pass  # 回调异常不应影响主流程

    # ---------- 命令执行 ----------

    def execute_command(self, command: EngineCommand) -> EngineResult:
        """把 EngineCommand 翻译为 MCP 工具调用并执行。

        架构设计：EngineCommand 是引擎无关的统一语义，
        MCP Client 把它映射为引擎 MCP Server 上的工具调用。
        工具命名约定：`engine.<capability.value>`（如 "engine.scene.load"）。
        """
        start = time.time()
        try:
            # 构造 MCP 工具名
            cap_str = command.capability.value if hasattr(
                command.capability, "value") else str(command.capability)
            tool_name = f"engine.{cap_str}"

            # 调用 MCP 工具
            result = self.call_tool(tool_name, command.params,
                                    timeout=command.timeout)
            duration = time.time() - start

            # 解析结果
            content = result.get("content", [])
            data = {}
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    try:
                        data = json.loads(item.get("text", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        data = {"text": item.get("text", "")}

            # 检查是否有错误
            is_error = result.get("isError", False)
            error_msg = data.get("error", "") if isinstance(data, dict) else ""

            return EngineResult(
                command=command,
                success=not is_error and not error_msg,
                data=data if isinstance(data, dict) else {"raw": data},
                error=error_msg,
                duration=duration,
            )
        except EngineTimeoutError as exc:
            return EngineResult(
                command=command, success=False,
                error=f"操作超时: {exc}", duration=time.time() - start)
        except MCPError as exc:
            return EngineResult(
                command=command, success=False,
                error=f"MCP 错误: {exc}", duration=time.time() - start)
        except EngineConnectionError as exc:
            return EngineResult(
                command=command, success=False,
                error=f"连接错误: {exc}", duration=time.time() - start)
        except Exception as exc:  # pragma: no cover
            return EngineResult(
                command=command, success=False,
                error=f"未知错误: {exc}", duration=time.time() - start)

    # ---------- 工具列表 ----------

    def list_tools(self) -> List[Dict]:
        """列出引擎 MCP Server 支持的可用工具。"""
        if not self._connected:
            raise EngineConnectionError(
                "MCP 未连接，请先调用 connect()",
                engine=self.engine, operation="list_tools")
        if self._available_tools:
            return self._available_tools
        # Mock 模式返回标准引擎工具集
        return [
            {"name": f"engine.{cap}", "description": f"Engine {cap}"}
            for cap in self._mock_tool_names()
        ]

    # ---------- 内部方法 ----------

    def _next_id(self) -> int:
        """生成下一个 JSON-RPC 请求 ID。"""
        self._request_id += 1
        return self._request_id

    def _headers(self) -> Dict[str, str]:
        """构造 HTTP 请求头。"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self._session_id:
            headers["X-Session-Id"] = self._session_id
        return headers

    def _load_tools(self, timeout: float) -> None:
        """从 MCP Server 拉取可用工具列表。"""
        try:
            result = self.call_tool("list_tools", {}, timeout)
            tools = result.get("tools", [])
            if tools:
                self._available_tools = tools
        except Exception:  # pragma: no cover
            pass  # 工具列表加载失败不阻塞连接

    def _mock_tool_names(self) -> List[str]:
        """Mock 模式下的标准工具名。"""
        from .protocol import (COCOS_DEFAULT_CAPABILITIES,
                               UE5_DEFAULT_CAPABILITIES)
        caps = set(COCOS_DEFAULT_CAPABILITIES) | set(UE5_DEFAULT_CAPABILITIES)
        return sorted(c.value for c in caps)

    def _mock_call_tool(self, tool_name: str,
                        arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Mock 模式下的工具调用响应。"""
        # 根据工具名构造合理的 Mock 响应
        name = tool_name.replace("engine.", "", 1)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "ok": True,
                        "mock": True,
                        "tool": name,
                        "args": arguments,
                        "result": {
                            "success": True,
                            "message": f"Mock 执行 {name} 成功",
                        },
                    }),
                }
            ],
            "isError": False,
        }

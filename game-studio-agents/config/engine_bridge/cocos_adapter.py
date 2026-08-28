# ============================================================
# 引擎桥接层 · Cocos Creator 适配器
# 版本: v0.1
# 说明: Cocos Creator 引擎适配器。
#       通过 MCP Server 或引擎插件与 Cocos Creator 编辑器交互。
#
#   Cocos Creator 特性:
#     - 基于 TypeScript / JavaScript 的脚本系统
#     - 场景以 .scene 文件存储
#     - 扩展系统通过 `Editor.Message` 通信
#     - 插件位于 extensions/ 目录
#
#   连接通道（优先顺序）:
#     1. MCP Server（Cocos 扩展提供 MCP Server 插件）
#     2. 插件通道（Cocos 扩展通过 Editor.Message 调用）
# ============================================================
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .engine_adapter import EngineAdapter
from .environment import EngineEnvironment
from .mcp_client import MCPClient
from .plugin_adapter import PluginAdapter, PluginInfo
from .protocol import (COCOS_DEFAULT_CAPABILITIES, EngineCapability,
                       EngineCommand, EngineResult, EngineStatus)


class CocosAdapter(EngineAdapter):
    """Cocos Creator 引擎适配器。"""

    def __init__(self, env: Optional[EngineEnvironment] = None,
                 use_mock: bool = False,
                 mcp_endpoint: str = "",
                 plugin_dir: str = ""):
        super().__init__("cocos", env)
        self.use_mock = use_mock
        # 从 env 或参数确定 MCP 端点
        endpoint = mcp_endpoint or (
            env.mcp_endpoints.get("cocos") if env else ""
        ) or "http://127.0.0.1:12345/mcp"
        # 从 env 或参数确定插件目录
        pdir = plugin_dir or (
            env.plugin_dirs.get("cocos") if env else ""
        )

        # 初始化 MCP 客户端
        self.mcp = MCPClient(endpoint, engine="cocos",
                             use_mock=use_mock)

        # 初始化插件适配器
        self.plugins = PluginAdapter("cocos", pdir, use_mock=use_mock)

        # 能力集（Cocos Creator 标准能力）
        self._capabilities = set(COCOS_DEFAULT_CAPABILITIES)

        # 状态
        self._status = EngineStatus.NOT_RUNNING

    # ---------- 连接管理 ----------

    def connect(self, **kw) -> bool:
        """连接 Cocos Creator。

        优先通过 MCP Server 连接；MCP 不可用时回退到插件通道。
        """
        # 先尝试 MCP 连接
        mcp_ok = self.mcp.connect(timeout=kw.get("timeout", 10.0))
        if mcp_ok:
            self._connected = True
            self._status = EngineStatus.RUNNING
            self._connect_time = time.time()
            # 扫描插件
            self.plugins.scan_plugins()
            return True

        # MCP 不可用时检查插件通道
        if self.use_mock or (self.plugins.plugin_dir and
                             self.plugins.get_plugins()):
            self._connected = True
            self._status = EngineStatus.RUNNING
            self._connect_time = time.time()
            return True

        self._status = EngineStatus.NOT_RUNNING
        return False

    def disconnect(self) -> None:
        self.mcp.disconnect()
        self._connected = False
        self._status = EngineStatus.NOT_RUNNING

    # ---------- 命令执行 ----------

    def execute(self, command: EngineCommand) -> EngineResult:
        """执行引擎命令。

        优先通过 MCP 通道，MCP 不可用时降级到插件通道。
        """
        start = time.time()
        # 检查能力
        if command.capability not in self._capabilities:
            return EngineResult(
                command=command, success=False,
                error=f"Cocos 引擎不支持能力 {command.capability.value}",
                duration=time.time() - start)

        # 如果未连接，尝试连接
        if not self._connected:
            self.connect()

        # 优先通过 MCP
        result = self.mcp.execute_command(command)
        if result.success:
            self._command_log.append(result)
            return result

        # MCP 失败，降级到插件通道
        plugin_result = self.plugins.execute_command(command)
        self._command_log.append(plugin_result)
        return plugin_result

    # ---------- Cocos 特有方法 ----------

    def create_script(self, path: str, content: str = "") -> EngineResult:
        """创建 Cocos 脚本（TypeScript）。"""
        return self.execute(EngineCommand(
            EngineCapability.SCRIPT_CREATE,
            {"path": path, "content": content}))

    def query_node(self, path: str) -> EngineResult:
        """查询节点信息。"""
        return self.execute(EngineCommand(
            EngineCapability.QUERY_SCENE_GRAPH,
            {"root": path, "depth": 1}))

# ============================================================
# 引擎桥接层 · Unreal Engine 5 适配器
# 版本: v0.1
# 说明: Unreal Engine 5 引擎适配器。
#       通过 MCP Server 或引擎插件与 UE5 编辑器交互。
#
#   UE5 特性:
#     - 基于 C++ / Blueprint 的编程模型
#     - 场景以 .umap 文件存储（关卡）
#     - 插件位于 Plugins/ 目录
#     - 编辑器自动化通过命令行参数 / EditorUtility / Python 脚本
#
#   连接通道（优先顺序）:
#     1. MCP Server（UE5 插件提供 MCP Server）
#     2. 插件通道（UE5 编辑器模块通过 Python/命令行调用）
#     3. 命令行参数（直接调用 UnrealEditor.exe -run=...）
# ============================================================
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .engine_adapter import EngineAdapter
from .environment import EngineEnvironment
from .mcp_client import MCPClient
from .plugin_adapter import PluginAdapter
from .protocol import (UE5_DEFAULT_CAPABILITIES, EngineCapability,
                       EngineCommand, EngineResult, EngineStatus)


class UE5Adapter(EngineAdapter):
    """Unreal Engine 5 引擎适配器。"""

    def __init__(self, env: Optional[EngineEnvironment] = None,
                 use_mock: bool = False,
                 mcp_endpoint: str = "",
                 plugin_dir: str = ""):
        super().__init__("ue5", env)
        self.use_mock = use_mock
        # 从 env 或参数确定 MCP 端点
        endpoint = mcp_endpoint or (
            env.mcp_endpoints.get("ue5") if env else ""
        ) or "http://127.0.0.1:54321/mcp"
        # 从 env 或参数确定插件目录
        pdir = plugin_dir or (
            env.plugin_dirs.get("ue5") if env else ""
        )

        # 初始化 MCP 客户端
        self.mcp = MCPClient(endpoint, engine="ue5",
                             use_mock=use_mock)

        # 初始化插件适配器
        self.plugins = PluginAdapter("ue5", pdir, use_mock=use_mock)

        # 能力集（UE5 标准能力）
        self._capabilities = set(UE5_DEFAULT_CAPABILITIES)

        # 状态
        self._status = EngineStatus.NOT_RUNNING

    # ---------- 连接管理 ----------

    def connect(self, **kw) -> bool:
        """连接 UE5。

        优先通过 MCP Server 连接；MCP 不可用时回退到插件/命令行通道。
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
                error=f"UE5 引擎不支持能力 {command.capability.value}",
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

    # ---------- UE5 特有方法 ----------

    def create_blueprint(self, path: str, parent_class: str = "") -> EngineResult:
        """创建 UE5 蓝图。"""
        params = {"path": path}
        if parent_class:
            params["parent_class"] = parent_class
        return self.execute(EngineCommand(
            EngineCapability.BLUEPRINT_CREATE, params))

    def build_project(self, target: str = "Development") -> EngineResult:
        """构建 UE5 项目。"""
        return self.execute(EngineCommand(
            EngineCapability.BUILD_START,
            {"target": target}))

    def start_debug(self, command_line: str = "") -> EngineResult:
        """启动 UE5 调试。"""
        return self.execute(EngineCommand(
            EngineCapability.DEBUG_START,
            {"command_line": command_line}))

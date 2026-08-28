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
from typing import Any, Dict, List, Optional, Set

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

    def connect(self) -> bool:
        """连接 Cocos Creator 编辑器。"""
        if self._connected:
            return True

        # 优先尝试 MCP
        if self.mcp.connect():
            self._connected = True
            self._status = EngineStatus.RUNNING
            return True

        # MCP 失败，尝试插件
        if self.plugins.connect():
            self._connected = True
            self._status = EngineStatus.RUNNING
            return True

        return False

    def disconnect(self) -> None:
        self._connected = False
        self._status = EngineStatus.NOT_RUNNING

    def execute(self, command: EngineCommand) -> EngineResult:
        """执行引擎命令（MCP → 插件降级）。"""
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

    # ---------- 中间件 C ABI 接入（wp_client 适配层 · 真实联调） ----------

    def middleware_available(self) -> bool:
        """检查 C++ 中间件是否可用（Python 绑定 / WASM / Native Plugin）。"""
        try:
            from middleware.bindings.python.cabi import procgen_terrain
            return True
        except ImportError:
            try:
                from middleware.bindings.typescript.cabi import GameMiddleware
                return True
            except ImportError:
                try:
                    import middleware
                    return True
                except ImportError:
                    return False

    def middleware_terrain(self, seed: str, width: int = 8, height: int = 8) -> Dict[str, Any]:
        """经中间件 C ABI 生成地形数据（确定性）→ 真实调用 Python 核心。"""
        if not self.middleware_available():
            return {"error": "middleware not available"}
        try:
            from middleware.bindings.python.cabi import procgen_terrain, hash_json
            data = procgen_terrain(seed, width, height, {"octaves": 3})
            return {
                "engine": "cocos",
                "seed": seed,
                "width": width,
                "height": height,
                "data": data,
                "hash": hash_json(data),
                "note": "Cocos 经中间件 C ABI（Python 绑定 procgen_terrain）真实调用",
            }
        except Exception as e:
            return {"error": f"middleware terrain call failed: {e}"}

    def middleware_level(self, seed: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """经中间件 C ABI 生成关卡数据（确定性）→ 真实调用 Python 核心。"""
        if not self.middleware_available():
            return {"error": "middleware not available"}
        try:
            from middleware.bindings.python.cabi import procgen_level, hash_json
            data = procgen_level(seed, params or {})
            return {
                "engine": "cocos",
                "seed": seed,
                "data": data,
                "hash": hash_json(data),
                "note": "Cocos 经中间件 C ABI（Python 绑定 procgen_level）真实调用",
            }
        except Exception as e:
            return {"error": f"middleware level call failed: {e}"}

    def middleware_narrative(self, seed: str, schema: Dict[str, Any] = None) -> Dict[str, Any]:
        """经中间件 C ABI 生成叙事数据（确定性）→ 真实调用 Python 核心。"""
        if not self.middleware_available():
            return {"error": "middleware not available"}
        try:
            from middleware.bindings.python.cabi import procgen_narrative, hash_json
            data = procgen_narrative(seed)
            return {
                "engine": "cocos",
                "seed": seed,
                "data": data,
                "hash": hash_json(data),
                "note": "Cocos 经中间件 C ABI（Python 绑定 procgen_narrative）真实调用",
            }
        except Exception as e:
            return {"error": f"middleware narrative call failed: {e}"}

    def middleware_gameplay_state(self, state: int = None) -> Dict[str, Any]:
        """经中间件 C ABI 访问玩法状态机 → 真实调用 Python 核心。"""
        if not self.middleware_available():
            return {"error": "middleware not available"}
        try:
            from middleware.bindings.python.cabi import GameMiddleware
            gsm = GameMiddleware()
            if state is not None:
                gsm.set_state(state)
                return {"engine": "cocos", "state": state, "applied": True,
                        "note": "Cocos 经中间件 C ABI set_state 真实调用"}
            current = gsm.get_state()
            return {"engine": "cocos", "state": current, "applied": False,
                    "note": "Cocos 经中间件 C ABI get_state 真实调用"}
        except Exception as e:
            return {"error": f"middleware gameplay state failed: {e}"}

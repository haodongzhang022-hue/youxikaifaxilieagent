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
from typing import Any, Dict, List, Optional, Set

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

    def connect(self) -> bool:
        """连接 UE5 编辑器。"""
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

    # ---------- UE5 特有方法 ----------

    def start_debug(self, command_line: str = "") -> EngineResult:
        """启动 UE5 调试。"""
        return self.execute(EngineCommand(
            EngineCapability.DEBUG_START,
            {"command_line": command_line}))

    # ---------- 中间件 C ABI 接入（wp_client 适配层 · 真实联调） ----------

    def middleware_available(self) -> bool:
        """检查 C++ 中间件是否可用（Python 绑定 / 直接链接 C++ 核心）。"""
        try:
            from middleware.bindings.python.cabi import procgen_terrain
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
                "engine": "ue5",
                "seed": seed,
                "width": width,
                "height": height,
                "data": data,
                "hash": hash_json(data),
                "note": "UE5 经中间件 C ABI（Python 绑定 procgen_terrain）真实调用",
            }
        except Exception as e:
            return {"error": f"middleware terrain call failed: {e}"}

    def middleware_combat(self, skill_id: str, attacker: Dict[str, Any],
                          target: Dict[str, Any]) -> Dict[str, Any]:
        """经中间件 C ABI 计算战斗伤害（确定性，定点数）→ 真实调用 Python 核心。"""
        if not self.middleware_available():
            return {"error": "middleware not available"}
        try:
            from middleware.bindings.python.cabi import calc_damage, hash_json
            # 构造默认技能配置
            skill_config = {
                "id": skill_id,
                "power": 1.0,
                "crit_rate": 0.1,
                "crit_multiplier": 1.5,
            }
            atk = attacker or {"attack": 100, "level": 1, "crit": False}
            tgt = target or {"defense": 50, "level": 1}
            damage = calc_damage(skill_config, atk, tgt)
            return {
                "engine": "ue5",
                "skill_id": skill_id,
                "attacker": atk,
                "target": tgt,
                "damage": damage,
                "note": "UE5 经中间件 C ABI（Python 绑定 calc_damage）真实调用",
            }
        except Exception as e:
            return {"error": f"middleware combat call failed: {e}"}

    def middleware_gameplay_tick(self, dt: float) -> Dict[str, Any]:
        """经中间件 C ABI 驱动玩法状态机 Tick → 真实调用 Python 核心。"""
        if not self.middleware_available():
            return {"error": "middleware not available"}
        try:
            from middleware.bindings.python.cabi import GameMiddleware
            gsm = GameMiddleware()
            gsm.update(dt)
            state = gsm.get_state()
            return {
                "engine": "ue5",
                "dt": dt,
                "state": state,
                "note": "UE5 经中间件 C ABI（Python 绑定 GameStateMachine.update）真实调用",
            }
        except Exception as e:
            return {"error": f"middleware gameplay tick failed: {e}"}

    def middleware_procgen(self, gen_type: str, seed: str,
                           params: Dict[str, Any] = None) -> Dict[str, Any]:
        """通用程序化生成入口（terrain/level/resources/props/narrative）→ 真实调用 Python 核心。"""
        if not self.middleware_available():
            return {"error": "middleware not available"}
        try:
            from middleware.bindings.python.cabi import (
                procgen_terrain, procgen_level, procgen_resources,
                procgen_props, procgen_narrative, hash_json,
            )
            generators = {
                "terrain": procgen_terrain,
                "level": procgen_level,
                "resources": procgen_resources,
                "props": procgen_props,
                "narrative": procgen_narrative,
            }
            fn = generators.get(gen_type)
            if fn is None:
                return {"error": f"unknown gen_type: {gen_type}"}
            if gen_type == "terrain":
                p = params or {}
                data = fn(seed, p.get("width", 8), p.get("height", 8), p)
            elif gen_type == "level":
                data = fn(seed, params or {})
            else:
                data = fn(seed)
            return {
                "engine": "ue5",
                "type": gen_type,
                "seed": seed,
                "data": data,
                "hash": hash_json(data),
                "note": f"UE5 经中间件 C ABI（Python 绑定 procgen_{gen_type}）真实调用",
            }
        except Exception as e:
            return {"error": f"middleware procgen failed: {e}"}

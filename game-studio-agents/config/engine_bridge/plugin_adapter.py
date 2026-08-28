# ============================================================
# 引擎桥接层 · 引擎插件适配器
# 版本: v0.1
# 说明: 通过引擎原生插件（Editor Extension / Plugin）作为补充通道，
#       在 MCP 不可用或需要引擎内操作的场景下直接调用引擎插件 API。
#
#   架构设计:
#     - **插件发现**：从引擎插件目录扫描可用插件
#     - **插件调用**：通过标准接口调用插件暴露的功能
#     - **插件注册**：管理插件生命周期
#     - **降级机制**：MCP 不可用时降级到插件调用
#
#   引擎插件工作模式:
#     Cocos Creator: 扩展（Extension）通过 `Editor.Message` 通信
#     UE5: 编辑器模块通过命令行参数或 `EditorUtility` 调用
# ============================================================
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .errors import PluginError
from .protocol import EngineCommand, EngineResult


# ============================================================
# 插件信息
# ============================================================

@dataclass
class PluginInfo:
    """引擎插件信息。"""

    plugin_id: str          # 插件唯一标识
    name: str               # 插件名称
    version: str            # 插件版本
    engine_type: str        # "cocos" / "ue5"
    path: str               # 插件目录路径
    enabled: bool = True    # 是否启用
    capabilities: List[str] = field(default_factory=list)  # 支持的引擎能力

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "engine_type": self.engine_type,
            "path": self.path,
            "enabled": self.enabled,
            "capabilities": self.capabilities,
        }


# ============================================================
# 插件适配器
# ============================================================

class PluginAdapter:
    """引擎插件适配器：发现、加载、调用引擎插件。

    架构设计：
      - **插件发现**：扫描引擎插件目录，识别引擎可用的插件
      - **插件调用**：通过统一的调用接口（execute_plugin_call）执行插件操作
      - **Mock 支持**：在无实际引擎环境下返回模拟结果，供 CI 测试

    实际引擎环境中，插件适配器需要调用：
      - Cocos Creator 扩展的 `Editor.Message.send()` API
      - UE5 编辑器插件通过命令行参数调用或 Blueprint Function Library
    """

    def __init__(self, engine_type: str, plugin_dir: str = "",
                 use_mock: bool = False):
        self.engine_type = engine_type
        self.plugin_dir = plugin_dir
        self.use_mock = use_mock
        self._plugins: List[PluginInfo] = []

    # ---------- 插件发现 ----------

    def scan_plugins(self) -> List[PluginInfo]:
        """扫描插件目录，发现可用引擎插件。"""
        if self.use_mock or not self.plugin_dir or not os.path.isdir(self.plugin_dir):
            # Mock 插件集
            if self.engine_type == "cocos":
                self._plugins = self._mock_cocos_plugins()
            elif self.engine_type == "ue5":
                self._plugins = self._mock_ue5_plugins()
            else:
                self._plugins = []
        else:
            self._plugins = self._scan_real_plugins()
        return self._plugins

    def get_plugins(self) -> List[PluginInfo]:
        """获取已扫描到的插件列表。"""
        if not self._plugins:
            self.scan_plugins()
        return self._plugins

    def get_plugin(self, plugin_id: str) -> Optional[PluginInfo]:
        """按插件 ID 查找插件。"""
        for p in self._plugins:
            if p.plugin_id == plugin_id:
                return p
        return None

    def has_capability(self, capability: str) -> bool:
        """检查插件是否支持某个引擎能力。"""
        for p in self._plugins:
            if capability in p.capabilities:
                return True
        return False

    # ---------- 插件调用 ----------

    def execute_plugin_call(self, plugin_id: str, method: str,
                            params: Dict[str, Any],
                            timeout: float = 30.0) -> Dict[str, Any]:
        """调用指定插件的指定方法。

        Args:
            plugin_id: 插件 ID
            method: 插件方法名
            params: 方法参数
            timeout: 超时秒数

        Returns:
            dict: 插件调用结果

        Raises:
            PluginError: 插件不存在或调用失败
        """
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            raise PluginError(
                f"插件 {plugin_id} 未找到",
                engine=self.engine_type, operation=f"plugin.call({plugin_id})")

        if not plugin.enabled:
            raise PluginError(
                f"插件 {plugin_id} 未启用",
                engine=self.engine_type, operation=f"plugin.call({plugin_id})")

        if self.use_mock or not os.path.exists(plugin.path):
            return {
                "ok": True,
                "mock": True,
                "plugin": plugin_id,
                "method": method,
                "params": params,
                "result": {"success": True, "message": f"Mock 调用插件 {plugin_id}.{method}"},
            }

        # 真实插件调用路径（需要各引擎插件实现具体协议）
        raise PluginError(
            f"真实插件调用尚未实现（需要引擎插件提供调用接口）",
            engine=self.engine_type, operation=f"plugin.call({plugin_id}.{method})")

    def execute_command(self, command: EngineCommand) -> EngineResult:
        """通过插件执行引擎命令。

        这是从 EngineCommand 到插件调用的翻译层。
        在 MCP 不可用或需要引擎内操作时使用插件通道执行命令。
        """
        import time
        start = time.time()
        try:
            # 找到能处理此能力命令的插件
            cap_str = command.capability.value if hasattr(
                command.capability, "value") else str(command.capability)
            target_plugin = None
            for p in self._plugins:
                if cap_str in p.capabilities:
                    target_plugin = p
                    break

            if not target_plugin:
                return EngineResult(
                    command=command, success=False,
                    error=f"无插件支持能力 {cap_str}",
                    duration=time.time() - start)

            result = self.execute_plugin_call(
                target_plugin.plugin_id, cap_str,
                command.params, timeout=command.timeout)
            duration = time.time() - start

            return EngineResult(
                command=command,
                success=result.get("ok", False),
                data=result.get("result", result),
                duration=duration,
            )
        except PluginError as exc:
            return EngineResult(
                command=command, success=False,
                error=str(exc), duration=time.time() - start)
        except Exception as exc:  # pragma: no cover
            return EngineResult(
                command=command, success=False,
                error=f"插件调用异常: {exc}", duration=time.time() - start)

    # ---------- 内部方法 ----------

    def _scan_real_plugins(self) -> List[PluginInfo]:
        """扫描真实引擎插件目录。"""
        from .protocol import (COCOS_DEFAULT_CAPABILITIES,
                               UE5_DEFAULT_CAPABILITIES)
        plugins: List[PluginInfo] = []
        if not os.path.isdir(self.plugin_dir):
            return plugins
        for entry in sorted(os.listdir(self.plugin_dir)):
            plugin_path = os.path.join(self.plugin_dir, entry)
            if not os.path.isdir(plugin_path):
                continue
            # 尝试读取插件 manifest
            manifest = self._read_plugin_manifest(plugin_path, entry)
            if manifest:
                plugins.append(PluginInfo(
                    plugin_id=entry,
                    name=manifest.get("name", entry),
                    version=manifest.get("version", "0.0.0"),
                    engine_type=self.engine_type,
                    path=plugin_path,
                    enabled=manifest.get("enabled", True),
                    capabilities=list(
                        COCOS_DEFAULT_CAPABILITIES | UE5_DEFAULT_CAPABILITIES
                    ) if not manifest.get("capabilities") else manifest["capabilities"],
                ))
        return plugins

    def _read_plugin_manifest(self, plugin_path: str,
                              plugin_id: str) -> Optional[Dict[str, Any]]:
        """读取插件 manifest（package.json / PluginDescriptor）。"""
        for manifest_name in ["package.json", "plugin.json", "Descriptor.json"]:
            manifest_file = os.path.join(plugin_path, manifest_name)
            if os.path.isfile(manifest_file):
                try:
                    with open(manifest_file, encoding="utf-8") as f:
                        return json.load(f)
                except (json.JSONDecodeError, OSError):
                    return None
        return None

    def _mock_cocos_plugins(self) -> List[PluginInfo]:
        """Mock 模式的 Cocos 插件集。"""
        return [
            PluginInfo(
                plugin_id="cnb-scene-controller",
                name="场景控制器",
                version="0.1.0",
                engine_type="cocos",
                path="mock://cocos/scene-controller",
                capabilities=[
                    "scene.load", "scene.save", "scene.new",
                    "node.create", "node.delete", "node.transform",
                ],
            ),
            PluginInfo(
                plugin_id="cnb-asset-manager",
                name="资产管理器",
                version="0.1.0",
                engine_type="cocos",
                path="mock://cocos/asset-manager",
                capabilities=[
                    "asset.import", "asset.export", "asset.list",
                    "material.create", "material.update",
                ],
            ),
            PluginInfo(
                plugin_id="cnb-play-runtime",
                name="Play 运行控制器",
                version="0.1.0",
                engine_type="cocos",
                path="mock://cocos/play-runtime",
                capabilities=[
                    "play.start", "play.stop",
                    "test.run", "test.collect",
                ],
            ),
        ]

    def _mock_ue5_plugins(self) -> List[PluginInfo]:
        """Mock 模式的 UE5 插件集。"""
        return [
            PluginInfo(
                plugin_id="CnBLevelController",
                name="关卡控制器",
                version="0.1.0",
                engine_type="ue5",
                path="mock://ue5/level-controller",
                capabilities=[
                    "scene.load", "scene.save", "scene.new",
                    "node.create", "node.delete", "node.transform",
                ],
            ),
            PluginInfo(
                plugin_id="CnBAssetTools",
                name="资产工具",
                version="0.1.0",
                engine_type="ue5",
                path="mock://ue5/asset-tools",
                capabilities=[
                    "asset.import", "asset.export", "asset.list",
                    "material.create", "material.update",
                ],
            ),
            PluginInfo(
                plugin_id="CnBBlueprint",
                name="蓝图助手",
                version="0.1.0",
                engine_type="ue5",
                path="mock://ue5/blueprint",
                capabilities=[
                    "script.create", "script.edit",
                    "blueprint.create",
                ],
            ),
            PluginInfo(
                plugin_id="CnBPlayDebug",
                name="Play/Debug 控制",
                version="0.1.0",
                engine_type="ue5",
                path="mock://ue5/play-debug",
                capabilities=[
                    "play.start", "play.stop",
                    "debug.start", "debug.stop",
                    "build.start", "build.cancel",
                ],
            ),
        ]

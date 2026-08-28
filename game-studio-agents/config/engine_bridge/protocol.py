# ============================================================
# 引擎桥接层 · 引擎命令协议定义
# 版本: v0.1
# 说明: 定义统一的引擎操作语义。无论底层是 Cocos 还是 UE5，
#       上层 Agent 使用同一套 EngineCommand 标准命令集与引擎交互。
#
# 设计原则:
#   - **命令语义统一**：EngineCommand 定义"做什么"，不定义"怎么做"，
#     底层由各引擎适配器翻译为对应引擎的具体操作；
#   - **能力自描述**：每个引擎适配器声明它支持的 EngineCapability，
#     上层可查询能力集决定可用操作，避免"能力越界"调用；
#   - **事件驱动**：引擎操作结果通过 EngineEvent 上报，与 message_bus
#     解耦但语义可映射；
#   - **状态可查询**：EngineStatus 统一引擎运行状态，供上层 Agent 判断
#     是否需要启动/重连/降级。
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================
# 引擎能力枚举
# ============================================================

class EngineCapability(str, Enum):
    """引擎能力标识。用于声明某个引擎适配器支持哪些操作。"""

    # --- 场景操作 ---
    SCENE_LOAD = "scene.load"                # 加载场景/关卡
    SCENE_SAVE = "scene.save"                # 保存场景/关卡
    SCENE_NEW = "scene.new"                  # 新建场景/关卡

    # --- 节点/对象操作 ---
    NODE_CREATE = "node.create"              # 创建节点/对象
    NODE_DELETE = "node.delete"              # 删除节点/对象
    NODE_TRANSFORM = "node.transform"        # 设置节点变换
    NODE_COMPONENT_ADD = "node.component.add" # 添加组件
    NODE_COMPONENT_REMOVE = "node.component.remove" # 移除组件

    # --- 资产操作 ---
    ASSET_IMPORT = "asset.import"            # 导入资产
    ASSET_EXPORT = "asset.export"            # 导出资产
    ASSET_DELETE = "asset.delete"            # 删除资产
    ASSET_LIST = "asset.list"                # 列出资产

    # --- 资源/材质操作 ---
    MATERIAL_CREATE = "material.create"      # 创建材质
    MATERIAL_UPDATE = "material.update"      # 更新材质
    PREFAB_CREATE = "prefab.create"          # 创建预制体
    PREFAB_INSTANTIATE = "prefab.instantiate" # 实例化预制体

    # --- 动画操作 ---
    ANIMATION_CREATE = "animation.create"    # 创建动画
    ANIMATION_PLAY = "animation.play"        # 播放动画
    ANIMATION_STOP = "animation.stop"        # 停止动画
    ANIMATION_RECORD = "animation.record"    # 录制动画

    # --- 代码/蓝图操作 ---
    SCRIPT_CREATE = "script.create"          # 创建脚本/蓝图
    SCRIPT_EDIT = "script.edit"              # 编辑脚本/蓝图
    BLUEPRINT_CREATE = "blueprint.create"    # 创建蓝图（UE5）

    # --- 运行/调试 ---
    PLAY_MODE_START = "play.start"           # 进入 Play 模式
    PLAY_MODE_STOP = "play.stop"             # 退出 Play 模式
    DEBUG_START = "debug.start"              # 启动调试
    DEBUG_STOP = "debug.stop"                # 停止调试
    BUILD_START = "build.start"              # 启动构建
    BUILD_CANCEL = "build.cancel"            # 取消构建

    # --- 测试操作 ---
    TEST_RUN = "test.run"                    # 运行自动化测试
    TEST_COLLECT = "test.collect"            # 收集测试用例

    # --- 查询操作 ---
    QUERY_SCENE_GRAPH = "query.scene_graph"  # 查询场景图
    QUERY_ASSET_INFO = "query.asset_info"    # 查询资产信息
    QUERY_PROJECT_INFO = "query.project_info" # 查询项目信息
    QUERY_LOG = "query.log"                  # 查询引擎日志


# ============================================================
# 引擎命令
# ============================================================

@dataclass
class EngineCommand:
    """一条统一的引擎命令。

    Attributes:
        capability: 命令对应的能力标识
        params: 命令参数（与具体引擎无关的标准参数）
        timeout: 超时秒数（默认 30s）
        engine: 目标引擎标识（"cocos" / "ue5"），空表示当前激活引擎
    """
    capability: EngineCapability
    params: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0
    engine: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability.value if isinstance(
                self.capability, EngineCapability) else str(self.capability),
            "params": self.params,
            "timeout": self.timeout,
            "engine": self.engine,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EngineCommand":
        return cls(
            capability=EngineCapability(data["capability"]),
            params=data.get("params", {}),
            timeout=data.get("timeout", 30.0),
            engine=data.get("engine", ""),
        )


# ============================================================
# 引擎命令集
# ============================================================

class EngineCommandSet:
    """引擎命令集工具：按能力值查找/校验命令。

    提供标准命令的快捷构建方法，便于上层 Agent 直接使用。
    """

    @staticmethod
    def load_scene(path: str, **kw) -> EngineCommand:
        return EngineCommand(EngineCapability.SCENE_LOAD, {"path": path}, **kw)

    @staticmethod
    def save_scene(path: str = "", **kw) -> EngineCommand:
        return EngineCommand(EngineCapability.SCENE_SAVE, {"path": path}, **kw)

    @staticmethod
    def create_node(name: str, parent: str = "", **kw) -> EngineCommand:
        return EngineCommand(EngineCapability.NODE_CREATE,
                             {"name": name, "parent": parent}, **kw)

    @staticmethod
    def delete_node(path: str, **kw) -> EngineCommand:
        return EngineCommand(EngineCapability.NODE_DELETE, {"path": path}, **kw)

    @staticmethod
    def set_transform(path: str, position: list = None,
                      rotation: list = None, scale: list = None,
                      **kw) -> EngineCommand:
        params = {"path": path}
        if position is not None:
            params["position"] = position
        if rotation is not None:
            params["rotation"] = rotation
        if scale is not None:
            params["scale"] = scale
        return EngineCommand(EngineCapability.NODE_TRANSFORM, params, **kw)

    @staticmethod
    def add_component(path: str, component_type: str,
                      component_name: str = "", **kw) -> EngineCommand:
        params = {"path": path, "component_type": component_type}
        if component_name:
            params["component_name"] = component_name
        return EngineCommand(EngineCapability.NODE_COMPONENT_ADD, params, **kw)

    @staticmethod
    def play(asset_path: str = "", **kw) -> EngineCommand:
        return EngineCommand(EngineCapability.PLAY_MODE_START,
                             {"asset_path": asset_path}, **kw)

    @staticmethod
    def stop(**kw) -> EngineCommand:
        return EngineCommand(EngineCapability.PLAY_MODE_STOP, {}, **kw)

    @staticmethod
    def run_test(test_filter: str = "", **kw) -> EngineCommand:
        return EngineCommand(EngineCapability.TEST_RUN,
                             {"filter": test_filter}, **kw)

    @staticmethod
    def query_scene_graph(root: str = "", depth: int = 0, **kw) -> EngineCommand:
        return EngineCommand(EngineCapability.QUERY_SCENE_GRAPH,
                             {"root": root, "depth": depth}, **kw)


# ============================================================
# 引擎状态
# ============================================================

class EngineStatus(str, Enum):
    """引擎运行状态。"""
    UNKNOWN = "unknown"        # 未知状态
    NOT_FOUND = "not_found"    # 引擎未安装
    NOT_RUNNING = "not_running" # 引擎已安装但未启动
    RUNNING = "running"        # 引擎正在运行
    BUSY = "busy"              # 引擎忙（正在执行操作）
    ERROR = "error"            # 引擎出错


# ============================================================
# 引擎结果
# ============================================================

@dataclass
class EngineResult:
    """引擎命令执行结果。"""

    command: EngineCommand
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration: float = 0.0

    @property
    def ok(self) -> bool:
        return self.success

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command.to_dict(),
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "duration": self.duration,
        }


# ============================================================
# 引擎事件
# ============================================================

@dataclass
class EngineEvent:
    """引擎事件（如场景变更、日志输出、编译完成等）。"""

    event_type: str        # "scene_changed" / "log" / "build_completed" / ...
    data: Dict[str, Any] = field(default_factory=dict)
    engine: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "engine": self.engine,
            "timestamp": self.timestamp,
        }


# ============================================================
# 引擎能力注册表
# ============================================================

# 各引擎的标准能力集（可被各适配器扩展/缩减）
COCOS_DEFAULT_CAPABILITIES = {
    EngineCapability.SCENE_LOAD,
    EngineCapability.SCENE_SAVE,
    EngineCapability.SCENE_NEW,
    EngineCapability.NODE_CREATE,
    EngineCapability.NODE_DELETE,
    EngineCapability.NODE_TRANSFORM,
    EngineCapability.NODE_COMPONENT_ADD,
    EngineCapability.NODE_COMPONENT_REMOVE,
    EngineCapability.ASSET_IMPORT,
    EngineCapability.ASSET_EXPORT,
    EngineCapability.MATERIAL_CREATE,
    EngineCapability.MATERIAL_UPDATE,
    EngineCapability.PREFAB_CREATE,
    EngineCapability.PREFAB_INSTANTIATE,
    EngineCapability.ANIMATION_CREATE,
    EngineCapability.ANIMATION_PLAY,
    EngineCapability.ANIMATION_STOP,
    EngineCapability.SCRIPT_CREATE,
    EngineCapability.SCRIPT_EDIT,
    EngineCapability.PLAY_MODE_START,
    EngineCapability.PLAY_MODE_STOP,
    EngineCapability.TEST_RUN,
    EngineCapability.TEST_COLLECT,
    EngineCapability.QUERY_SCENE_GRAPH,
    EngineCapability.QUERY_ASSET_INFO,
    EngineCapability.QUERY_PROJECT_INFO,
    EngineCapability.QUERY_LOG,
}

UE5_DEFAULT_CAPABILITIES = {
    EngineCapability.SCENE_LOAD,
    EngineCapability.SCENE_SAVE,
    EngineCapability.SCENE_NEW,
    EngineCapability.NODE_CREATE,
    EngineCapability.NODE_DELETE,
    EngineCapability.NODE_TRANSFORM,
    EngineCapability.NODE_COMPONENT_ADD,
    EngineCapability.NODE_COMPONENT_REMOVE,
    EngineCapability.ASSET_IMPORT,
    EngineCapability.ASSET_EXPORT,
    EngineCapability.MATERIAL_CREATE,
    EngineCapability.MATERIAL_UPDATE,
    EngineCapability.PREFAB_CREATE,
    EngineCapability.PREFAB_INSTANTIATE,
    EngineCapability.ANIMATION_CREATE,
    EngineCapability.ANIMATION_PLAY,
    EngineCapability.ANIMATION_STOP,
    EngineCapability.SCRIPT_CREATE,
    EngineCapability.SCRIPT_EDIT,
    EngineCapability.BLUEPRINT_CREATE,
    EngineCapability.PLAY_MODE_START,
    EngineCapability.PLAY_MODE_STOP,
    EngineCapability.DEBUG_START,
    EngineCapability.DEBUG_STOP,
    EngineCapability.BUILD_START,
    EngineCapability.BUILD_CANCEL,
    EngineCapability.TEST_RUN,
    EngineCapability.TEST_COLLECT,
    EngineCapability.QUERY_SCENE_GRAPH,
    EngineCapability.QUERY_ASSET_INFO,
    EngineCapability.QUERY_PROJECT_INFO,
    EngineCapability.QUERY_LOG,
}

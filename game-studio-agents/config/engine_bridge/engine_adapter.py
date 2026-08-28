# ============================================================
# 引擎桥接层 · 引擎适配器基类与工厂
# 版本: v0.1
# 说明: 定义统一的引擎适配器接口，并提供工厂函数创建具体引擎适配器。
#
#   引擎适配器职责:
#     - 管理到引擎的连接（通过 MCP 或插件通道）
#     - 翻译 EngineCommand 为引擎具体操作
#     - 报告引擎状态与能力集
#     - 收集引擎事件
#
#   适配器层级:
#     EngineAdapter (抽象基类)
#     ├── CocosAdapter    - Cocos Creator 3.x
#     ├── UE5Adapter      - Unreal Engine 5
#     └── MockAdapter     - Mock 引擎（测试/架构验证用）
# ============================================================
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .errors import EngineBridgeError, EngineNotAvailableError
from .mcp_client import MCPClient
from .plugin_adapter import PluginAdapter
from .protocol import (EngineCapability, EngineCommand, EngineCommandSet,
                       EngineEvent, EngineResult, EngineStatus)


# ============================================================
# 引擎适配器基类
# ============================================================

class EngineAdapter(ABC):
    """引擎适配器抽象基类。

    所有具体引擎适配器（Cocos/UE5/Mock）继承此类，实现：
      - connect() / disconnect() / is_connected()
      - execute() 执行 EngineCommand
      - status() 查询引擎状态
      - capabilities() 查询能力集
      - events() 获取事件流
    """

    def __init__(self, engine_type: str, env=None):
        self.engine_type = engine_type
        self.env = env  # EngineEnvironment 可选
        self._connected = False
        self._status = EngineStatus.NOT_FOUND
        self._capabilities: Set[EngineCapability] = set()
        self._event_callbacks: List[Callable[[EngineEvent], None]] = []
        self._command_log: List[EngineResult] = []
        self._connect_time = 0.0

    # ---------- 连接管理 ----------

    @abstractmethod
    def connect(self, **kw) -> bool:
        """连接引擎。"""

    @abstractmethod
    def disconnect(self) -> None:
        """断开引擎连接。"""

    def is_connected(self) -> bool:
        return self._connected

    def status(self) -> EngineStatus:
        return self._status

    # ---------- 能力查询 ----------

    def capabilities(self) -> Set[EngineCapability]:
        """获取引擎支持的能力集。"""
        return set(self._capabilities)

    def has_capability(self, capability: EngineCapability) -> bool:
        """检查引擎是否支持指定能力。"""
        return capability in self._capabilities

    # ---------- 命令执行 ----------

    @abstractmethod
    def execute(self, command: EngineCommand) -> EngineResult:
        """执行引擎命令。"""

    def execute_batch(self, commands: List[EngineCommand]) -> List[EngineResult]:
        """批量执行引擎命令。"""
        return [self.execute(cmd) for cmd in commands]

    # ---------- 快捷命令 ----------

    def load_scene(self, path: str) -> EngineResult:
        """加载场景/关卡。"""
        return self.execute(EngineCommandSet.load_scene(path))

    def save_scene(self, path: str = "") -> EngineResult:
        """保存场景/关卡。"""
        return self.execute(EngineCommandSet.save_scene(path))

    def create_node(self, name: str, parent: str = "") -> EngineResult:
        """创建节点/对象。"""
        return self.execute(EngineCommandSet.create_node(name, parent))

    def delete_node(self, path: str) -> EngineResult:
        """删除节点/对象。"""
        return self.execute(EngineCommandSet.delete_node(path))

    def set_transform(self, path: str, position: list = None,
                      rotation: list = None, scale: list = None) -> EngineResult:
        """设置节点变换。"""
        return self.execute(EngineCommandSet.set_transform(
            path, position, rotation, scale))

    def add_component(self, path: str, component_type: str,
                      component_name: str = "") -> EngineResult:
        """添加组件。"""
        return self.execute(EngineCommandSet.add_component(
            path, component_type, component_name))

    def play(self) -> EngineResult:
        """进入 Play 模式。"""
        return self.execute(EngineCommandSet.play())

    def stop(self) -> EngineResult:
        """退出 Play 模式。"""
        return self.execute(EngineCommandSet.stop())

    def run_test(self, test_filter: str = "") -> EngineResult:
        """运行自动化测试。"""
        return self.execute(EngineCommandSet.run_test(test_filter))

    def query_scene_graph(self, root: str = "", depth: int = 0) -> EngineResult:
        """查询场景图。"""
        return self.execute(EngineCommandSet.query_scene_graph(root, depth))

    # ---------- 事件 ----------

    def on_event(self, callback: Callable[[EngineEvent], None]) -> None:
        """注册引擎事件回调。"""
        self._event_callbacks.append(callback)

    def _emit_event(self, event: EngineEvent) -> None:
        """向所有注册的回调发出事件。"""
        for cb in self._event_callbacks:
            try:
                cb(event)
            except Exception:  # pragma: no cover
                pass

    # ---------- 状态报告 ----------

    def report(self) -> Dict[str, Any]:
        """生成引擎适配器状态报告。"""
        return {
            "engine_type": self.engine_type,
            "connected": self._connected,
            "status": self._status.value,
            "capabilities": sorted(c.value for c in self._capabilities),
            "command_count": len(self._command_log),
            "connect_time": self._connect_time,
            "env": self.env.to_dict() if self.env else None,
        }

    def command_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近执行的命令日志。"""
        return [r.to_dict() for r in self._command_log[-limit:]]


# ============================================================
# Mock 引擎适配器（测试/架构验证用）
# ============================================================

class MockEngineAdapter(EngineAdapter):
    """Mock 引擎适配器。

    用于架构验证、测试和开发阶段的引擎仿真。
    不对真实引擎发请求，返回预设的模拟响应。
    """

    def __init__(self, engine_type: str = "mock", env=None):
        super().__init__(engine_type, env)
        from .protocol import COCOS_DEFAULT_CAPABILITIES, UE5_DEFAULT_CAPABILITIES
        self._capabilities = set(COCOS_DEFAULT_CAPABILITIES) | set(UE5_DEFAULT_CAPABILITIES)
        self._status = EngineStatus.RUNNING

    def connect(self, **kw) -> bool:
        self._connected = True
        self._status = EngineStatus.RUNNING
        self._connect_time = time.time()
        return True

    def disconnect(self) -> None:
        self._connected = False
        self._status = EngineStatus.NOT_RUNNING

    def execute(self, command: EngineCommand) -> EngineResult:
        start = time.time()
        # 模拟执行
        result = EngineResult(
            command=command,
            success=True,
            data={
                "mock": True,
                "operation": command.capability.value,
                "params": command.params,
                "message": f"Mock 引擎执行 {command.capability.value} 成功",
            },
            duration=time.time() - start,
        )
        self._command_log.append(result)
        self._emit_event(EngineEvent(
            event_type="command_executed",
            data={"capability": command.capability.value,
                  "success": True},
            engine=self.engine_type,
            timestamp=time.time(),
        ))
        return result


# ============================================================
# 引擎适配器工厂
# ============================================================

def create_engine_adapter(engine_type: str, env=None,
                          use_mock: bool = False,
                          mcp_endpoint: str = "",
                          plugin_dir: str = "") -> EngineAdapter:
    """创建引擎适配器。

    Args:
        engine_type: "cocos" / "ue5" / "mock"
        env: EngineEnvironment 实例（可选）
        use_mock: 强制使用 Mock 模式
        mcp_endpoint: MCP Server 端点（可选，缺省从 env 读取）
        plugin_dir: 插件目录（可选，缺省从 env 读取）

    Returns:
        EngineAdapter: 具体引擎适配器实例

    Raises:
        UnsupportedEngineError: 不支持的引擎类型
    """
    from .errors import UnsupportedEngineError

    engine_type = engine_type.lower()

    # Mock 引擎直接返回
    if engine_type == "mock":
        return MockEngineAdapter("mock", env)

    if engine_type == "cocos":
        from .cocos_adapter import CocosAdapter
        return CocosAdapter(env=env, use_mock=use_mock,
                            mcp_endpoint=mcp_endpoint,
                            plugin_dir=plugin_dir)

    if engine_type == "ue5":
        from .ue5_adapter import UE5Adapter
        return UE5Adapter(env=env, use_mock=use_mock,
                          mcp_endpoint=mcp_endpoint,
                          plugin_dir=plugin_dir)

    raise UnsupportedEngineError(
        f"不支持的引擎类型: {engine_type}",
        engine=engine_type, operation="create_engine_adapter")

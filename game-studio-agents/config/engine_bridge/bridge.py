# ============================================================
# 引擎桥接层 · 统一门面 (EngineBridgeFacade)
# 版本: v0.1
# 说明: 为上层 Agent 提供统一的引擎访问入口。
#       封装引擎发现、适配器创建、命令执行、状态查询等。
#
#   使用方式:
#     from engine_bridge.bridge import EngineBridgeFacade
#     bridge = EngineBridgeFacade()
#     bridge.init()   # 初始化（发现引擎、创建适配器）
#     bridge.load_scene("path/to/scene")
#     bridge.execute(EngineCommand(...))
#
#   设计原则:
#     - **单一入口**：Agent 只需与 EngineBridgeFacade 交互
#     - **自动降级**：MCP → 插件 → Mock，逐级降级
#     - **能力查询**：可查询当前可用引擎与能力
#     - **可测试**：Mock 模式保证在任何环境可运行
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .engine_adapter import EngineAdapter, MockEngineAdapter
from .environment import EngineEnvironment, detect_engine_environment, get_windows_environment
from .errors import EngineBridgeError, UnsupportedEngineError
from .protocol import EngineCapability, EngineCommand, EngineResult, EngineStatus


@dataclass
class BridgeConfig:
    """引擎桥接配置。"""

    use_mock: bool = False          # 强制 Mock 模式（测试用）
    engines: List[str] = None       # 要启用的引擎列表（["cocos", "ue5"]）
    default_engine: str = ""        # 默认引擎（缺省为第一个可用）
    env_override: EngineEnvironment = None  # 覆盖环境探测结果

    def __post_init__(self):
        if self.engines is None:
            self.engines = []


class EngineBridgeFacade:
    """引擎桥接统一门面。

    上层 Agent 通过此门面访问引擎能力：
      - init(): 初始化，发现引擎并创建适配器
      - execute(): 执行引擎命令
      - capabilities(): 查询可用能力
      - status(): 查询引擎状态
    """

    def __init__(self, config: Optional[BridgeConfig] = None):
        self.config = config or BridgeConfig()
        self.env: Optional[EngineEnvironment] = None
        self._adapters: Dict[str, EngineAdapter] = {}
        self._default_engine: str = ""
        self._initialized = False

    # ---------- 初始化 ----------

    def init(self) -> bool:
        """初始化引擎桥接。

        步骤:
          1. 探测引擎环境（Windows 目标环境 / 当前环境）
          2. 创建各引擎适配器
          3. 尝试连接可用引擎
          4. 设置默认引擎

        Returns:
            bool: 初始化是否成功
        """
        if self._initialized:
            return True

        # 探测环境
        if self.config.env_override:
            self.env = self.config.env_override
        else:
            self.env = detect_engine_environment()

        # 确定要启用的引擎
        engines = self.config.engines or []
        if not engines:
            # 自动探测
            if self.config.use_mock:
                engines = ["mock"]
            else:
                engines = []
                if self.env.engine_type in ("cocos", "both"):
                    engines.append("cocos")
                if self.env.engine_type in ("ue5", "both"):
                    engines.append("ue5")
                if not engines:
                    engines = ["mock"]  # 无引擎时回退 Mock

        # 创建适配器
        from .engine_adapter import create_engine_adapter
        for engine_type in engines:
            try:
                adapter = create_engine_adapter(
                    engine_type,
                    env=self.env if engine_type != "mock" else None,
                    use_mock=self.config.use_mock or engine_type == "mock")
                self._adapters[engine_type] = adapter
            except UnsupportedEngineError:
                continue

        # 尝试连接
        for engine_type, adapter in self._adapters.items():
            try:
                adapter.connect()
            except Exception:  # pragma: no cover
                pass  # 连接失败不阻塞初始化

        # 设置默认引擎
        if self.config.default_engine and self.config.default_engine in self._adapters:
            self._default_engine = self.config.default_engine
        elif "cocos" in self._adapters:
            self._default_engine = "cocos"
        elif "ue5" in self._adapters:
            self._default_engine = "ue5"
        elif self._adapters:
            self._default_engine = next(iter(self._adapters))

        self._initialized = True
        return bool(self._adapters)

    # ---------- 引擎查询 ----------

    @property
    def available_engines(self) -> List[str]:
        """获取可用引擎列表。"""
        return list(self._adapters.keys())

    def get_adapter(self, engine_type: str = "") -> Optional[EngineAdapter]:
        """获取指定引擎的适配器。"""
        if not self._initialized:
            self.init()
        if not engine_type:
            engine_type = self._default_engine
        return self._adapters.get(engine_type)

    def engine_status(self, engine_type: str = "") -> EngineStatus:
        """查询引擎状态。"""
        adapter = self.get_adapter(engine_type)
        if not adapter:
            return EngineStatus.NOT_FOUND
        return adapter.status()

    def capabilities(self, engine_type: str = "") -> Set[EngineCapability]:
        """查询引擎能力集。"""
        adapter = self.get_adapter(engine_type)
        if not adapter:
            return set()
        return adapter.capabilities()

    def has_capability(self, capability: EngineCapability,
                       engine_type: str = "") -> bool:
        """检查引擎是否支持指定能力。"""
        adapter = self.get_adapter(engine_type)
        if not adapter:
            return False
        return adapter.has_capability(capability)

    # ---------- 命令执行 ----------

    def execute(self, command: EngineCommand,
                engine_type: str = "") -> EngineResult:
        """执行引擎命令。

        未指定 engine_type 时使用默认引擎。
        """
        if not self._initialized:
            self.init()
        adapter = self.get_adapter(engine_type)
        if not adapter:
            return EngineResult(
                command=command, success=False,
                error=f"引擎 {engine_type or self._default_engine or 'unknown'} 不可用")
        return adapter.execute(command)

    def execute_batch(self, commands: List[EngineCommand],
                      engine_type: str = "") -> List[EngineResult]:
        """批量执行引擎命令。"""
        if not self._initialized:
            self.init()
        adapter = self.get_adapter(engine_type)
        if not adapter:
            return [EngineResult(cmd, False, error="引擎不可用") for cmd in commands]
        return adapter.execute_batch(commands)

    # ---------- 快捷方法 ----------

    def load_scene(self, path: str, engine_type: str = "") -> EngineResult:
        """加载场景。"""
        return self.execute(EngineCommand(EngineCapability.SCENE_LOAD,
                                          {"path": path}), engine_type)

    def save_scene(self, path: str = "", engine_type: str = "") -> EngineResult:
        """保存场景。"""
        return self.execute(EngineCommand(EngineCapability.SCENE_SAVE,
                                          {"path": path}), engine_type)

    def create_node(self, name: str, parent: str = "",
                    engine_type: str = "") -> EngineResult:
        """创建节点。"""
        return self.execute(EngineCommand(EngineCapability.NODE_CREATE,
                                          {"name": name, "parent": parent}),
                            engine_type)

    def play(self, engine_type: str = "") -> EngineResult:
        """进入 Play 模式。"""
        return self.execute(EngineCommand(EngineCapability.PLAY_MODE_START, {}),
                            engine_type)

    def stop(self, engine_type: str = "") -> EngineResult:
        """退出 Play 模式。"""
        return self.execute(EngineCommand(EngineCapability.PLAY_MODE_STOP, {}),
                            engine_type)

    def run_test(self, test_filter: str = "", engine_type: str = "") -> EngineResult:
        """运行自动化测试。"""
        return self.execute(EngineCommand(EngineCapability.TEST_RUN,
                                          {"filter": test_filter}), engine_type)

    # ---------- 状态报告 ----------

    def report(self) -> Dict[str, Any]:
        """生成引擎桥接整体状态报告。"""
        if not self._initialized:
            self.init()
        return {
            "initialized": self._initialized,
            "env": self.env.to_dict() if self.env else None,
            "default_engine": self._default_engine,
            "engines": {
                engine_type: adapter.report()
                for engine_type, adapter in self._adapters.items()
            },
        }

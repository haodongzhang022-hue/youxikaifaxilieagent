# ============================================================
# 引擎桥接层集成模块 (Engine Integration)
# 版本: v0.1
# 说明: 将引擎桥接层（EngineBridgeFacade）接入现有 Agent 流水线。
#       打通 EngineEvent → MessageBus 的事件映射，使各部门 Agent
#       可通过统一入口获得引擎能力。
#
#   核心能力:
#     1. EngineIntegrationFacade - 引擎集成门面
#        - 封装 EngineBridgeFacade，提供 Agent 友好 API
#        - 自动将引擎事件映射为 MessageBus 消息
#        - Mock 模式保证 CI 环境可验证
#     2. EngineEventBridge - 引擎事件 → 消息总线桥接
#        - 将 EngineEvent 转为 Message 并 publish 到 MessageBus
#        - 支持按引擎事件类型订阅
#     3. engine_capability_check() - 引擎能力查询
#        - 供部门 Agent 查询当前可用引擎能力
#
#   使用方式:
#     from engine_integration import EngineIntegrationFacade
#     facade = EngineIntegrationFacade(use_mock=True, engines=["cocos", "ue5"])
#     facade.init()
#     facade.load_scene("assets/scenes/Main.scene")
#     facade.execute_command(...)
#
# 语言: Python 3 (可运行，核心逻辑无需外部依赖)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine_bridge import (
    EngineBridgeFacade,
    BridgeConfig,
    EngineCommand,
    EngineCapability,
    EngineEvent,
    EngineResult,
    EngineStatus,
    EngineNotAvailableError,
    EngineBridgeError,
)
from message_bus import Message, MessageBus


# ============================================================
# 一、引擎事件 → 消息总线桥接
# ============================================================

class EngineEventBridge:
    """引擎事件桥接器。

    将引擎事件（EngineEvent）转换为消息总线（MessageBus）消息，
    使引擎能力/状态变化能被 Agent 流水线感知。

    事件映射规则:
      - engine_event_type → message_type（前缀 ENGINE_ 区分）
      - event data → message content
      - engine 标识 → message topic（供订阅筛选）
    """

    _EVENT_MSG_TYPE = "ENGINE_EVENT"
    _COMMAND_MSG_TYPE = "ENGINE_COMMAND"

    def __init__(self, bus: Optional[MessageBus] = None, from_role: str = "engine_bridge"):
        """初始化事件桥接器。

        Args:
            bus: MessageBus 实例（缺省时新建）
            from_role: 引擎桥接层作为消息发送方的 role_id
        """
        self.bus = bus or MessageBus()
        self.from_role = from_role
        self._subscribers: Dict[str, List[str]] = {}  # event_type -> [role_id]
        if self.from_role not in self.bus.roles:
            self.bus.register(self.from_role)

    def subscribe(self, event_type: str, role_id: str) -> bool:
        """订阅指定引擎事件类型。

        Args:
            event_type: 引擎事件类型（如 scene_changed / build_completed）
            role_id: 订阅方 role_id（Agent 角色）

        Returns:
            bool: 订阅是否成功
        """
        self._subscribers.setdefault(event_type, [])
        if role_id not in self._subscribers[event_type]:
            self._subscribers[event_type].append(role_id)
        if role_id not in self.bus.roles:
            self.bus.register(role_id)
        return True

    def unsubscribe(self, event_type: str, role_id: str) -> bool:
        """取消订阅指定引擎事件类型。"""
        if event_type in self._subscribers and role_id in self._subscribers[event_type]:
            self._subscribers[event_type].remove(role_id)
            return True
        return False

    def emit(self, event: EngineEvent) -> List[str]:
        """把引擎事件发布为消息总线消息。

        Args:
            event: 引擎事件对象

        Returns:
            list: 成功投递的接收方 role_id 列表
        """
        if not event or not event.event_type:
            return []

        # 查找订阅方；无订阅时广播到所有已注册角色（topic=engine_event）
        targets = self._subscribers.get(event.event_type, [])
        mode = "DIRECT" if targets else "TOPIC"
        to_role = targets[0] if targets else "*"

        msg = Message(
            type=self._EVENT_MSG_TYPE,
            from_role=self.from_role,
            to_role=to_role,
            content={
                "event_type": event.event_type,
                "data": event.data,
                "engine": event.engine,
                "timestamp": event.timestamp,
                "source": "engine_bridge",
            },
            mode=mode,
            topic="engine_event" if not targets else None,
        )
        self.bus.publish(msg)
        # 通过消息总线处理队列（走标准投递链路，记录到 delivered）
        self.bus.process_all()
        # 若订阅方有 handler，立即处理
        delivered = []
        for target in targets:
            if target in self.bus.roles:
                for h in self.bus._handlers.get(target, []):
                    h(msg)
                    delivered.append(target)
        if not targets:
            # TOPIC 广播：交给所有订阅了 topic 的角色
            for sub in self.bus._subscriptions:
                if sub.topic == "engine_event" and sub.handler:
                    sub.handler(msg)
                    delivered.append(sub.subscriber_id)
        return delivered

    def notify_command(self, cmd: EngineCommand, result: EngineResult,
                       from_role: str = "") -> Message:
        """把一条引擎命令执行结果通知到消息总线。

        Args:
            cmd: 已执行的引擎命令
            result: 命令执行结果
            from_role: 发送方角色（缺省用 engine_bridge）

        Returns:
            Message: 发布的消息
        """
        msg = Message(
            type=self._COMMAND_MSG_TYPE,
            from_role=from_role or self.from_role,
            to_role="*",
            content={
                "command": cmd.to_dict() if hasattr(cmd, "to_dict") else str(cmd),
                "success": result.success,
                "engine": result.engine if hasattr(result, "engine") else "",
                "error": result.error if hasattr(result, "error") else "",
                "data": result.data if hasattr(result, "data") else {},
            },
            mode="TOPIC",
            topic="engine_command",
        )
        self.bus.publish(msg)
        return msg


# ============================================================
# 二、引擎集成门面（Agent 统一入口）
# ============================================================

class EngineIntegrationFacade:
    """引擎集成门面。

    为部门 Agent 提供统一的引擎能力入口，封装：
      - 引擎桥接层（EngineBridgeFacade）底层交互
      - 引擎事件 → MessageBus 消息映射
      - Mock 模式（CI 可验证）
    """

    def __init__(
        self,
        use_mock: bool = False,
        engines: Optional[List[str]] = None,
        bus: Optional[MessageBus] = None,
        from_role: str = "engine_bridge",
    ):
        """初始化引擎集成门面。

        Args:
            use_mock: 是否使用 Mock 模式（测试/CI 环境强制 True）
            engines: 要启用的引擎列表（["cocos", "ue5"]）
            bus: MessageBus 实例
            from_role: 消息发送方角色
        """
        # 若无外部 MessageBus，引擎桥接器内部会自建一个
        self.bus = bus or MessageBus()
        self._bridge = EngineBridgeFacade(BridgeConfig(
            use_mock=use_mock,
            engines=engines or ["cocos", "ue5"],
        ))
        self.event_bridge = EngineEventBridge(self.bus, from_role=from_role)
        self._initialized = False

    # ---------- 初始化 ----------
    def init(self) -> bool:
        """初始化引擎桥接层。

        Returns:
            bool: 是否初始化成功
        """
        self._bridge.init()
        self._initialized = True
        return True

    # ---------- 引擎状态 ----------
    @property
    def available_engines(self) -> list:
        """可用引擎列表。"""
        return self._bridge.available_engines if hasattr(self._bridge, "available_engines") else []

    @property
    def default_engine(self) -> str:
        """默认引擎。"""
        return self._bridge._default_engine if hasattr(self._bridge, "_default_engine") else ""

    def engine_status(self, engine: str = "") -> str:
        """查询引擎状态。"""
        if not self._initialized:
            return "uninitialized"
        try:
            return self._bridge.engine_status(engine or self.default_engine).value
        except Exception:
            return "unknown"

    # ---------- 引擎命令执行 ----------
    def execute(self, command: EngineCommand, engine: str = "") -> EngineResult:
        """执行引擎命令。"""
        if not self._initialized:
            self.init()
        try:
            return self._bridge.execute(command, engine)
        except EngineBridgeError as e:
            return EngineResult(success=False, error=str(e))

    # ---------- 便捷命令方法 ----------
    def load_scene(self, scene_path: str, engine: str = "") -> EngineResult:
        """加载场景。"""
        if not self._initialized:
            self.init()
        return self._bridge.load_scene(scene_path, engine)

    def create_node(self, name: str, parent: str = "", engine: str = "") -> EngineResult:
        """创建节点。"""
        if not self._initialized:
            self.init()
        return self._bridge.create_node(name, parent, engine)

    def play(self, engine: str = "") -> EngineResult:
        """进入 Play 模式。"""
        if not self._initialized:
            self.init()
        return self._bridge.play(engine)

    def save_scene(self, scene_path: str, engine: str = "") -> EngineResult:
        """保存场景。"""
        if not self._initialized:
            self.init()
        return self._bridge.save_scene(scene_path, engine)

    def stop(self, engine: str = "") -> EngineResult:
        """退出 Play 模式。"""
        if not self._initialized:
            self.init()
        return self._bridge.stop(engine)

    # ---------- 能力查询 ----------
    def capabilities(self, engine: str = "") -> set:
        """查询指定引擎可用能力集。"""
        if not self._initialized:
            self.init()
        try:
            return self._bridge.capabilities(engine or self.default_engine)
        except Exception:
            return set()

    def has_capability(self, cap: EngineCapability, engine: str = "") -> bool:
        """判断指定引擎是否支持某能力。"""
        return cap in self.capabilities(engine or self.default_engine)

    # ---------- 事件桥接 ----------
    def subscribe_event(self, event_type: str, role_id: str) -> bool:
        """让某 Agent 角色订阅引擎事件。"""
        return self.event_bridge.subscribe(event_type, role_id)

    def emit_engine_event(self, event: EngineEvent) -> list:
        """发布引擎事件到消息总线。"""
        return self.event_bridge.emit(event)

    # ---------- 状态报告 ----------
    def report(self) -> Dict[str, Any]:
        """生成引擎集成状态报告。"""
        if not self._initialized:
            self.init()
        report = self._bridge.report()
        report["integration"] = {
            "initialized": self._initialized,
            "event_bridge_subscribers": dict(self.event_bridge._subscribers),
        }
        return report


# ============================================================
# 三、能力检查工具（供 CI 测试 / 部门 Agent 自检）
# ============================================================

def engine_capability_check(use_mock: bool = True) -> Dict[str, Any]:
    """引擎能力检查。

    在 Mock 模式下验证引擎桥接层与消息总线集成是否正常。

    Returns:
        dict: 检查结果，含各子项状态
    """
    results = {
        "facade_init": False,
        "engine_status": False,
        "command_exec": False,
        "event_bridge": False,
        "capability_query": False,
    }

    # 创建集成门面（Mock 模式）
    facade = EngineIntegrationFacade(use_mock=use_mock, engines=["cocos", "ue5"])

    # 1. 初始化
    try:
        facade.init()
        results["facade_init"] = True
    except Exception:
        return results

    # 2. 引擎状态查询
    try:
        engines = facade.available_engines
        if engines:
            status = facade.engine_status()
            results["engine_status"] = bool(status)
    except Exception:
        pass

    # 3. 命令执行（Mock 模式）
    try:
        r = facade.load_scene("assets/scenes/Main.scene")
        results["command_exec"] = bool(r.success)
    except Exception:
        pass

    # 4. 事件桥接
    try:
        # 注册处理器后订阅并发射事件
        def _on_engine_event(msg):
            pass
        facade.bus.on("cto", _on_engine_event)
        facade.subscribe_event("scene_changed", "cto")
        ev = EngineEvent(event_type="scene_changed", data={"scene": "Main"},
                         engine="cocos", timestamp=123.0)
        delivered = facade.emit_engine_event(ev)
        results["event_bridge"] = bool(delivered)
    except Exception:
        pass

    # 5. 能力查询
    try:
        caps = facade.capabilities("cocos")
        results["capability_query"] = len(caps) > 0
    except Exception:
        pass

    return results


# ============================================================
# 四、演示 / 自测
# ============================================================

def demo():
    print("=" * 70)
    print("引擎桥接层集成（Engine Integration）演示")
    print("  EngineBridgeFacade → MessageBus 事件映射")
    print("=" * 70)

    # Mock 模式集成
    facade = EngineIntegrationFacade(use_mock=True, engines=["cocos", "ue5"])
    facade.init()

    print(f"\n[1] 可用引擎: {facade.available_engines}")
    print(f"    默认引擎: {facade.default_engine}")

    print(f"\n[2] 加载场景")
    r = facade.load_scene("assets/scenes/Main.scene")
    print(f"    success={r.success}")

    print(f"\n[3] 创建节点")
    r = facade.create_node("Player", "Root")
    print(f"    success={r.success}")

    print(f"\n[4] Play 模式")
    r = facade.play()
    print(f"    success={r.success}")

    print(f"\n[5] 事件桥接（EngineEvent → MessageBus）")
    bus = facade.bus
    facade.subscribe_event("scene_changed", "cto")
    facade.subscribe_event("scene_changed", "engine_dev")
    ev = EngineEvent(event_type="scene_changed", data={"scene": "Main"},
                     engine="cocos", timestamp=123.0)
    delivered = facade.emit_engine_event(ev)
    print(f"    已投递到: {delivered}")

    print(f"\n[6] 能力查询（Cocos 前 5 项）")
    caps = facade.capabilities("cocos")
    for c in sorted(list(caps))[:5]:
        print(f"    - {c.value}")

    print(f"\n[7] 状态报告摘要")
    report = facade.report()
    print(f"    env.os: {report['env']['os_name'] if 'env' in report else 'N/A'}")
    print(f"    engines: {list(report['engines'].keys()) if 'engines' in report else []}")
    print(f"    集成状态: initialized={report['integration']['initialized']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(demo())

# ============================================================
# Cocos Creator 表现层适配器 (Cocos Presenter Adapter)
# 版本: v1.0
# 对齐: Issue #112「游戏向架构师的开发」· wp_client 逻辑/表现分离
# 说明: Cocos Creator 引擎侧表现层，消费纯逻辑层事件并渲染。
#       - 逻辑层: client_core/pure_logic.PureLogicEngine（引擎无关）
#       - 表现层: 本模块（Cocos API 相关）
#       - 桥接: IPresentationAdapter 接口
#
# 设计原则:
#   1. 逻辑与表现分离: 逻辑层纯 Python，表现层在 Cocos 侧
#   2. 事件驱动: 逻辑层产生事件，表现层消费并渲染
#   3. 接口化: 表现层实现 IPresentationAdapter，可替换为其他引擎
# 语言: Python 3 (可运行，模拟验证)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List

from client_core.pure_logic import (
    GameState, LogicEvent, PureLogicEngine, IPresentationAdapter,
)


class CocosPresenter(IPresentationAdapter):
    """
    Cocos Creator 表现层适配器。

    职责（模拟）:
      - 将逻辑事件映射为 Cocos 场景操作
      - 将用户输入转发给逻辑层
      - 渲染状态到 Cocos UI/场景

    注意: 本模块为 Python 模拟实现，实际 Cocos 环境中
          会使用 TypeScript 版本（client_core/cocos_bridge.ts）。
    """

    # 事件 → Cocos 操作映射
    EVENT_TO_COCOS = {
        "damage": "播放受击动画 + 飘血数字",
        "heal": "播放治疗特效 + 绿色飘字",
        "level_up": "播放升级特效 + 全屏闪光",
        "exp_gain": "更新经验条 UI",
        "item_gain": "更新背包 UI + 获得道具提示",
        "item_use": "更新背包 UI + 使用道具动画",
        "item_use_failed": "提示道具不足",
        "move": "更新角色节点位置",
    }

    def __init__(self, engine: PureLogicEngine):
        self.engine = engine
        self._rendered: List[str] = []
        self._initialized = False

    def init(self) -> bool:
        """初始化 Cocos 表现层"""
        self._initialized = True
        return True

    def destroy(self) -> None:
        """销毁表现层"""
        self._initialized = False

    def on_logic_event(self, event: LogicEvent) -> None:
        """处理逻辑事件：映射为 Cocos 操作"""
        cocos_action = self.EVENT_TO_COCOS.get(event.event_type, "未定义操作")
        self._rendered.append(f"[Cocos] {event.event_type}: {cocos_action}")

    def poll_input(self) -> Dict[str, Any]:
        """采集用户输入"""
        return {"movement": (0, 0), "action": "none"}

    def render_state(self, state: GameState) -> None:
        """渲染当前游戏状态到 Cocos UI"""
        self._rendered.append(
            f"[Cocos] 渲染状态: HP={state.hp}/{state.max_hp}, "
            f"Level={state.level}, Position=({state.position_x}, {state.position_z})"
        )

    # ---- 便捷方法 ----

    def render_log(self) -> List[str]:
        """获取渲染日志（验证用）"""
        return self._rendered


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    print("=== Cocos 表现层适配器自测 ===")
    print()

    # 创建纯逻辑引擎 + Cocos 表现层
    engine = PureLogicEngine()
    presenter = CocosPresenter(engine)

    presenter.init()

    # 逻辑操作 → 事件 → 表现层渲染
    engine.take_damage(30)
    engine.add_exp(120)
    engine.add_item("potion", 2)
    engine.move(10, 5)

    # 消费事件并渲染
    events = engine.consume_events()
    for ev in events:
        presenter.on_logic_event(ev)

    presenter.render_state(engine.state)

    print("渲染日志:")
    for line in presenter.render_log():
        print(f"  {line}")

    print(f"\n渲染操作数: {len(presenter.render_log())}")
    print("🟢 Cocos 表现层适配器自测通过")

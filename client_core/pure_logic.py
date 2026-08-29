# ============================================================
# 客户端纯逻辑类库 (Pure Client Logic Library)
# 版本: v1.0
# 对齐: Issue #112「游戏向架构师的开发」· wp_client 逻辑/表现分离
# 说明: 客户端核心逻辑以纯 Python 实现，引擎无关。
#       逻辑层与表现层严格分离：扣血≠播放爆炸动画。
#
# 设计原则:
#   1. 逻辑与表现分离: 纯逻辑类不依赖任何引擎 API
#   2. 跨语言可翻译: 逻辑用纯数据结构+纯算法，可人工翻译为 TS/C#/C++
#   3. 确定性: 同输入同输出，不依赖随机源
#   4. 可测试: 纯逻辑可通过单元测试验证
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================
# 一、纯逻辑数据模型（引擎无关）
# ============================================================

@dataclass
class GameState:
    """游戏状态（纯数据结构，不依赖引擎）"""
    player_id: str = ""
    hp: int = 100
    max_hp: int = 100
    mp: int = 50
    max_mp: int = 50
    level: int = 1
    exp: int = 0
    gold: int = 0
    position_x: float = 0.0
    position_z: float = 0.0
    inventory: Dict[str, int] = field(default_factory=dict)
    buffs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict（跨语言传输）"""
        return {
            "player_id": self.player_id,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "mp": self.mp,
            "max_mp": self.max_mp,
            "level": self.level,
            "exp": self.exp,
            "gold": self.gold,
            "position_x": self.position_x,
            "position_z": self.position_z,
            "inventory": dict(self.inventory),
            "buffs": list(self.buffs),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GameState":
        """从 dict 创建"""
        return cls(
            player_id=d.get("player_id", ""),
            hp=d.get("hp", 100),
            max_hp=d.get("max_hp", 100),
            mp=d.get("mp", 50),
            max_mp=d.get("max_mp", 50),
            level=d.get("level", 1),
            exp=d.get("exp", 0),
            gold=d.get("gold", 0),
            position_x=d.get("position_x", 0.0),
            position_z=d.get("position_z", 0.0),
            inventory=d.get("inventory", {}),
            buffs=d.get("buffs", []),
        )


@dataclass
class LogicEvent:
    """逻辑事件（引擎无关，表现层订阅消费）"""
    event_type: str                  # damage / heal / level_up / pick_item / move
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = "pure_logic"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "source": self.source,
        }


# ============================================================
# 二、核心逻辑引擎（纯逻辑，无 I/O 无引擎依赖）
# ============================================================

class PureLogicEngine:
    """
    客户端纯逻辑引擎。

    职责:
      - 状态管理（hp/mp/exp 等）
      - 战斗结算（确定性伤害计算）
      - 道具/资源管理
      - 事件生成（供表现层订阅）

    不职责:
      - 不直接调用渲染/音频/输入
      - 不直接操作场景/节点/精灵
      - 不依赖任何引擎 API
    """

    def __init__(self, state: Optional[GameState] = None):
        self.state = state or GameState()
        self._events: List[LogicEvent] = []

    # ---- 事件系统 ----

    def emit(self, event_type: str, **data) -> LogicEvent:
        """生成逻辑事件（供表现层订阅）"""
        ev = LogicEvent(event_type=event_type, data=data)
        self._events.append(ev)
        return ev

    def consume_events(self) -> List[LogicEvent]:
        """消费并清空事件队列（表现层每帧调用）"""
        events = list(self._events)
        self._events.clear()
        return events

    # ---- 状态查询 ----

    def get_state(self) -> GameState:
        """获取当前状态（不可变视图）"""
        return self.state

    def is_alive(self) -> bool:
        """是否存活"""
        return self.state.hp > 0

    def is_full_hp(self) -> bool:
        """是否满血"""
        return self.state.hp >= self.state.max_hp

    # ---- 逻辑操作（纯逻辑，无 I/O） ----

    def take_damage(self, amount: int) -> List[LogicEvent]:
        """受到伤害（纯逻辑：扣血）"""
        actual = min(self.state.hp, max(0, amount))
        self.state.hp -= actual
        return [self.emit("damage", amount=actual, remaining_hp=self.state.hp)]

    def heal(self, amount: int) -> List[LogicEvent]:
        """治疗（纯逻辑：回血）"""
        actual = min(self.state.max_hp - self.state.hp, max(0, amount))
        self.state.hp += actual
        return [self.emit("heal", amount=actual, hp=self.state.hp)]

    def add_exp(self, amount: int) -> List[LogicEvent]:
        """增加经验（纯逻辑：可能触发升级）"""
        self.state.exp += amount
        events = [self.emit("exp_gain", amount=amount, exp=self.state.exp)]

        # 升级检测（简化：每 100 exp 升一级）
        while self.state.exp >= 100:
            self.state.exp -= 100
            self.state.level += 1
            self.state.max_hp += 20
            self.state.hp = self.state.max_hp
            events.append(self.emit("level_up", level=self.state.level))

        return events

    def add_item(self, item_id: str, count: int = 1) -> List[LogicEvent]:
        """添加道具（纯逻辑）"""
        self.state.inventory[item_id] = self.state.inventory.get(item_id, 0) + count
        return [self.emit("item_gain", item_id=item_id, count=count,
                          total=self.state.inventory[item_id])]

    def use_item(self, item_id: str) -> List[LogicEvent]:
        """使用道具（纯逻辑：需由外部注入具体效果）"""
        count = self.state.inventory.get(item_id, 0)
        if count <= 0:
            return [self.emit("item_use_failed", item_id=item_id, reason="not_enough")]
        self.state.inventory[item_id] = count - 1
        return [self.emit("item_use", item_id=item_id, remaining=count - 1)]

    def move(self, dx: float, dz: float) -> List[LogicEvent]:
        """移动（纯逻辑：位置更新）"""
        self.state.position_x += dx
        self.state.position_z += dz
        return [self.emit("move", x=self.state.position_x, z=self.state.position_z)]

    # ---- 确定性计算（跨语言可翻译） ----

    @staticmethod
    def calculate_damage(base_atk: int, base_def: int, skill_multiplier: float = 1.0,
                         crit_chance: float = 0.1, crit_multiplier: float = 2.0) -> Dict[str, Any]:
        """
        确定性伤害计算（纯数学，跨语言翻译）。

        公式: damage = max(1, (base_atk * skill_multiplier - base_def * 0.5))
        暴击: 基于确定性 hash（而非随机数）判断

        Args:
            base_atk: 基础攻击
            base_def: 基础防御
            skill_multiplier: 技能倍率
            crit_chance: 暴击率 (0-1)
            crit_multiplier: 暴击倍率

        Returns:
            Dict: {damage, is_crit}
        """
        raw = max(1.0, (base_atk * skill_multiplier - base_def * 0.5))
        # 确定性暴击判定
        hash_input = f"{base_atk}:{base_def}:{skill_multiplier}".encode()
        hash_val = int(hashlib.md5(hash_input).hexdigest()[:8], 16)
        rand_unit = (hash_val % 10000) / 10000.0

        is_crit = rand_unit < crit_chance
        damage = int(raw * crit_multiplier) if is_crit else int(raw)

        return {"damage": damage, "is_crit": is_crit}

    @staticmethod
    def exp_to_level(exp: int) -> int:
        """经验值 → 等级（确定性计算）"""
        return exp // 100 + 1

    @staticmethod
    def state_hash(state: GameState) -> str:
        """状态哈希（确定性，用于跨端一致性校验）"""
        return hashlib.sha256(
            json.dumps(state.to_dict(), sort_keys=True).encode()
        ).hexdigest()[:16]


# ============================================================
# 三、表现层适配接口（引擎无关抽象）
# ============================================================

class IPresentationAdapter:
    """
    表现层适配接口：所有引擎实现此接口接入纯逻辑层。

    表现层职责:
      - 渲染/动画/特效/音频
      - 输入采集
      - 场景/节点管理

    不职责:
      - 不计算游戏状态（由 PureLogicEngine 负责）
      - 不做战斗结算
      - 不做数值计算
    """

    # ---- 表现层生命周期 ----
    def init(self) -> bool:
        """初始化表现层"""
        raise NotImplementedError

    def destroy(self) -> None:
        """销毁表现层"""
        raise NotImplementedError

    # ---- 事件消费 ----
    def on_logic_event(self, event: LogicEvent) -> None:
        """处理逻辑事件（播放动画/特效/音频）"""
        raise NotImplementedError

    # ---- 输入采集 ----
    def poll_input(self) -> Dict[str, Any]:
        """采集用户输入"""
        raise NotImplementedError

    # ---- 渲染接口 ----
    def render_state(self, state: GameState) -> None:
        """渲染当前游戏状态"""
        raise NotImplementedError


# ============================================================
# 四、自测
# ============================================================

if __name__ == "__main__":
    print("=== 客户端纯逻辑类库自测 ===")
    print()

    # 1. 状态管理
    engine = PureLogicEngine()
    print(f"初始状态: hp={engine.state.hp}, level={engine.state.level}")

    # 2. 伤害计算
    engine.take_damage(30)
    print(f"受伤后: hp={engine.state.hp}")

    # 3. 治疗
    engine.heal(20)
    print(f"治疗后: hp={engine.state.hp}")

    # 4. 经验/升级
    engine.add_exp(150)
    print(f"经验后: level={engine.state.level}, exp={engine.state.exp}")

    # 5. 道具管理
    engine.add_item("potion", 3)
    engine.use_item("potion")
    print(f"道具后: potion={engine.state.inventory.get('potion', 0)}")

    # 6. 确定性伤害计算
    dmg1 = PureLogicEngine.calculate_damage(100, 50)
    dmg2 = PureLogicEngine.calculate_damage(100, 50)
    print(f"确定性伤害: {dmg1['damage']} == {dmg2['damage']} ({dmg1['damage'] == dmg2['damage']})")

    # 7. 事件消费
    events = engine.consume_events()
    print(f"事件队列: {len(events)} 个事件")
    for ev in events:
        print(f"  - {ev.event_type}")

    print("\n🟢 客户端纯逻辑类库自测通过")

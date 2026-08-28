"""
combat_service.py - 战斗服务

服务端权威战斗结算。
- 战斗帧率固定 30Hz（与客户端 Tick 对齐）
- 伤害计算使用定点数（保证多端一致）
- 掉落表驱动 + 统一随机种子管理
"""

import hashlib
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from middleware.bindings.python import cabi


@dataclass
class CombatSession:
    """战斗会话"""
    combat_id: str
    player_id: str
    seed: int
    monster_hp: int = 100
    player_hp: int = 100
    tick: int = 0
    finished: bool = False
    rewards: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "combat_id": self.combat_id,
            "player_id": self.player_id,
            "seed": self.seed,
            "monster_hp": self.monster_hp,
            "player_hp": self.player_hp,
            "tick": self.tick,
            "finished": self.finished,
            "rewards": self.rewards,
        }


class CombatService:
    """战斗服务：服务端权威结算"""

    FIXED_TICK_RATE = 30  # 30Hz 固定 Tick

    def __init__(self):
        self._sessions: Dict[str, CombatSession] = {}

    def start_combat(self, player_id: str, seed: int,
                     monster_hp: int = 100) -> CombatSession:
        """开始战斗会话"""
        combat_id = hashlib.sha256(
            f"{player_id}:{seed}:{time.time_ns()}".encode()
        ).hexdigest()[:16]

        session = CombatSession(
            combat_id=combat_id,
            player_id=player_id,
            seed=seed,
            monster_hp=monster_hp,
        )
        self._sessions[combat_id] = session
        return session

    def process_attack(self, combat_id: str, attack_power: int) -> Dict:
        """
        处理攻击动作（服务端权威结算）。
        使用定点数保证多端伤害计算一致。
        """
        session = self._sessions.get(combat_id)
        if not session or session.finished:
            return {"status": "error", "reason": "combat not found or finished"}

        session.tick += 1

        # 定点数伤害计算（对齐中间件 FixedPoint）
        # 伤害 = attack_power * 1.0 定点数乘法，保证跨端一致
        fp_power = cabi.fp_from_int(attack_power)
        fp_scale = cabi.fp_from_float(1.0)
        fp_damage = cabi.fp_mul(fp_power, fp_scale)
        damage = cabi.fp_to_float(fp_damage)

        # 应用伤害
        session.monster_hp = max(0, session.monster_hp - int(damage))

        # 检查战斗结束
        if session.monster_hp <= 0:
            session.finished = True
            session.rewards = self._roll_loot(session.seed)
            return {
                "status": "victory",
                "damage": damage,
                "monster_hp": 0,
                "rewards": session.rewards,
                "xp_earned": 50 + int(session.seed % 50),
            }

        return {
            "status": "in_progress",
            "damage": damage,
            "monster_hp": session.monster_hp,
            "tick": session.tick,
        }

    def get_session(self, combat_id: str) -> Optional[CombatSession]:
        return self._sessions.get(combat_id)

    def end_combat(self, combat_id: str) -> Optional[Dict]:
        """结束战斗并返回结果"""
        session = self._sessions.get(combat_id)
        if not session:
            return None
        result = session.to_dict()
        del self._sessions[combat_id]
        return result

    # ============================================================
    # 掉落表（确定性：同 seed 同掉落）
    # ============================================================
    def _roll_loot(self, seed: int) -> List[Dict]:
        """确定性掉落（与中间件 procgen_loot 对齐）"""
        item_types = ["gold", "iron_ore", "herb", "potion", "star_shard"]
        st = [cabi._fnv1a_hash(str(seed))]

        count = 1 + cabi._splitmix64_next(st) % 3
        loot = []
        for _ in range(count):
            r = cabi._splitmix64_next(st)
            item = item_types[r % len(item_types)]
            amount = 1 + ((r >> 8) % 10)
            loot.append({"item": item, "amount": amount})
        return loot


class EconomyService:
    """经济服务：统一账本 + 防作弊"""

    def __init__(self):
        self._ledger: Dict[str, Dict[str, int]] = {}  # player_id -> {currency: amount}
        self._transactions: List[Dict] = []           # 交易记录（全审计）

    def init_account(self, player_id: str) -> None:
        """初始化玩家账户"""
        if player_id not in self._ledger:
            self._ledger[player_id] = {
                "gold": 0,
                "star_core": 0,
                "eroding_stone": 0,
            }

    def credit(self, player_id: str, currency: str, amount: int,
               reason: str = "") -> Dict:
        """入账（服务端权威）"""
        self.init_account(player_id)
        if currency not in self._ledger[player_id]:
            return {"status": "error", "reason": f"invalid currency '{currency}'"}
        self._ledger[player_id][currency] += amount
        tx = {
            "player_id": player_id,
            "currency": currency,
            "delta": amount,
            "balance": self._ledger[player_id][currency],
            "reason": reason,
            "timestamp": int(time.time() * 1000),
        }
        self._transactions.append(tx)
        return {"status": "ok", "transaction": tx}

    def debit(self, player_id: str, currency: str, amount: int,
              reason: str = "") -> Dict:
        """出账（服务端权威，防作弊校验余额）"""
        self.init_account(player_id)
        if currency not in self._ledger[player_id]:
            return {"status": "error", "reason": f"invalid currency '{currency}'"}
        balance = self._ledger[player_id][currency]
        if balance < amount:
            return {
                "status": "insufficient",
                "currency": currency,
                "balance": balance,
                "required": amount,
            }
        self._ledger[player_id][currency] -= amount
        tx = {
            "player_id": player_id,
            "currency": currency,
            "delta": -amount,
            "balance": self._ledger[player_id][currency],
            "reason": reason,
            "timestamp": int(time.time() * 1000),
        }
        self._transactions.append(tx)
        return {"status": "ok", "transaction": tx}

    def transfer(self, from_id: str, to_id: str,
                 currency: str, amount: int) -> Dict:
        """跨玩家转账（统一账本）"""
        result = self.debit(from_id, currency, amount, reason=f"transfer to {to_id}")
        if result["status"] != "ok":
            return result
        self.credit(to_id, currency, amount, reason=f"transfer from {from_id}")
        return {"status": "ok"}

    def get_balance(self, player_id: str) -> Dict[str, int]:
        self.init_account(player_id)
        return dict(self._ledger[player_id])

    def get_transactions(self, player_id: str) -> List[Dict]:
        """获取玩家交易记录（全审计）"""
        return [tx for tx in self._transactions if tx["player_id"] == player_id]

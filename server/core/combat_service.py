"""
combat_service.py - 战斗服务

服务端权威战斗结算。
- 战斗帧率固定 30Hz（与客户端 Tick 对齐）
- 伤害计算使用定点数（保证多端一致）
- 掉落表驱动 + 统一随机种子管理
- 服务端权威校验（身份 / 参数合法性 / 幂等）
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
    MAX_ATTACK_POWER = 10000  # W1: attack_power 服务端上限

    def __init__(self):
        self._sessions: Dict[str, CombatSession] = {}
        # W5: 发奖幂等 - 已发奖战斗 ID 集合
        self._rewarded_combats: set = set()

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

    def process_attack(self, combat_id: str, attack_power: int,
                       caller_player_id: str = None) -> Dict:
        """
        处理攻击动作（服务端权威结算）。
        使用定点数保证多端伤害计算一致。
        
        C2 修复：增加 caller_player_id 参数，校验调用者是否为战斗会话 owner。
        W1 修复：attack_power 服务端上限校验。
        W3 修复：使用 cabi.calc_damage() 对齐中间件伤害计算。
        """
        session = self._sessions.get(combat_id)
        if not session or session.finished:
            return {"status": "error", "reason": "combat not found or finished"}

        # C2: 越权校验 - 仅会话 owner 可攻击
        if caller_player_id is not None and caller_player_id != session.player_id:
            return {"status": "error", "reason": "permission denied: not combat owner"}

        # W1: attack_power 上限校验（服务端权威）
        if attack_power <= 0 or attack_power > self.MAX_ATTACK_POWER:
            return {"status": "error", "reason": "invalid attack_power range"}

        session.tick += 1

        # W3: 使用中间件 calc_damage 对齐跨端伤害
        skill_config = {"base_power": attack_power}
        attacker_stats = {"atk": 100}
        target_stats = {"def": 50}
        damage = cabi.calc_damage(skill_config, attacker_stats, target_stats)

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

    def end_combat(self, combat_id: str,
                   caller_player_id: str = None) -> Optional[Dict]:
        """结束战斗并返回结果（C2: 增加越权校验）"""
        session = self._sessions.get(combat_id)
        if not session:
            return None
        # C2: 越权校验
        if caller_player_id is not None and caller_player_id != session.player_id:
            return None
        result = session.to_dict()
        del self._sessions[combat_id]
        return result

    def is_rewarded(self, combat_id: str) -> bool:
        """W5: 检查战斗是否已发奖（幂等）"""
        return combat_id in self._rewarded_combats

    def mark_rewarded(self, combat_id: str) -> None:
        """W5: 标记战斗已发奖"""
        self._rewarded_combats.add(combat_id)

    # ============================================================
    # 掉落表（确定性：同 seed 同掉落，对齐中间件 cabi.roll_loot）
    # ============================================================
    def _roll_loot(self, seed: int) -> List[Dict]:
        """C3 修复：使用中间件 cabi.roll_loot() 保证跨端一致"""
        result = cabi.roll_loot("loot_table_main", seed)
        items = result.get("items", [])
        # 转换为服务端内部格式
        loot = []
        for item in items:
            loot.append({
                "item": item.get("id", ""),
                "amount": item.get("qty", 1),
            })
        return loot


class EconomyService:
    """经济服务：统一账本 + 防作弊"""

    MAX_SINGLE_TRANSFER = 1000000  # W4: 单笔转账上限

    def __init__(self):
        self._ledger: Dict[str, Dict[str, int]] = {}  # player_id -> {currency: amount}
        self._transactions: List[Dict] = []           # 交易记录（全审计）
        # W7: 持久化支持
        self._persist_file = None

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
        """入账（服务端权威）
        C1 修复：校验 amount > 0，禁止负数入账。
        """
        self.init_account(player_id)
        if currency not in self._ledger[player_id]:
            return {"status": "error", "reason": f"invalid currency '{currency}'"}
        # C1: 金额必须为正数
        if amount <= 0:
            return {"status": "error", "reason": "amount must be > 0"}
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
        """出账（服务端权威，防作弊校验余额）
        C1 修复：校验 amount > 0，禁止负数出账。
        """
        self.init_account(player_id)
        if currency not in self._ledger[player_id]:
            return {"status": "error", "reason": f"invalid currency '{currency}'"}
        # C1: 金额必须为正数
        if amount <= 0:
            return {"status": "error", "reason": "amount must be > 0"}
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
        """跨玩家转账（统一账本）
        W4 修复：from != to + 单笔上限校验。
        """
        # W4: from != to
        if from_id == to_id:
            return {"status": "error", "reason": "cannot transfer to self"}
        # W4: 单笔上限
        if amount > self.MAX_SINGLE_TRANSFER:
            return {"status": "error", "reason": "transfer exceeds single limit"}
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

    # W7: 持久化支持
    def persist(self, filepath: str) -> bool:
        """持久化账本到磁盘"""
        import json
        try:
            with open(filepath, 'w') as f:
                json.dump({
                    'ledger': self._ledger,
                    'transactions': self._transactions,
                }, f)
            self._persist_file = filepath
            return True
        except Exception:
            return False

    def load(self, filepath: str) -> bool:
        """从磁盘加载账本"""
        import json
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            self._ledger = data.get('ledger', {})
            self._transactions = data.get('transactions', [])
            self._persist_file = filepath
            return True
        except Exception:
            return False

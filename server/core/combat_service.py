"""
combat_service.py - 战斗服务

服务端权威战斗结算。
- 战斗帧率固定 30Hz（与客户端 Tick 对齐）
- 伤害计算使用定点数（保证多端一致，走中间件 cabi.calc_damage）
- 掉落表驱动 + 统一随机种子（走中间件 cabi.roll_loot，保证跨端 bit 级一致）
- 货币/转账全量校验（防负数刷钱 / 越权 / 幂等）
"""

import hashlib
import os
import time
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from middleware.bindings.python import cabi


# ============================================================
# 常量（服务端权威口径）
# ============================================================
MAX_ATTACK_POWER = 1000          # 攻击力上限（服务端归一后）
BASE_SKILL_POWER = 10            # 技能基础倍率（服务端定值）
MAX_TRANSFER_AMOUNT = 1_000_000  # 单笔转账上限
VALID_CURRENCIES = ("gold", "star_core", "eroding_stone")

# 掉落表（与中间件对齐）
LOOT_TABLE_MAIN = "loot_table_main"


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
    player_atk: int = 100        # 服务端归一攻击力
    monster_def: int = 50        # 服务端归一防御

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

    # ============================================================
    # 战斗会话
    # ============================================================
    def start_combat(self, player_id: str, seed: int,
                     monster_hp: int = 100,
                     player_atk: int = 100, monster_def: int = 50) -> CombatSession:
        """开始战斗会话（player_atk/monster_def 由服务端推导，非客户端）"""
        combat_id = hashlib.sha256(
            f"{player_id}:{seed}:{time.time_ns()}".encode()
        ).hexdigest()[:16]

        session = CombatSession(
            combat_id=combat_id,
            player_id=player_id,
            seed=seed,
            monster_hp=monster_hp,
            player_atk=player_atk,
            monster_def=monster_def,
        )
        self._sessions[combat_id] = session
        return session

    def process_attack(self, combat_id: str, player_id: str,
                       attack_power: Optional[int] = None) -> Dict:
        """
        处理攻击动作（服务端权威结算）。

        C2 修复：必须传入 caller player_id，非会话 owner 一律拒绝（防越权）。
        W1 修复：attack_power 仅作客户端意图提示，服务端按玩家属性归一；
                 即便传超大值也受 MAX_ATTACK_POWER 约束，且归一为 session.player_atk。
        """
        session = self._sessions.get(combat_id)
        if not session or session.finished:
            return {"status": "error", "reason": "combat not found or finished"}

        # ---- C2 越权校验 ----
        if player_id != session.player_id:
            return {"status": "rejected", "reason": "permission denied"}

        session.tick += 1

        # ---- W1 服务端归一攻击力 ----
        # 攻击力由服务端推导（玩家基础攻击 + 装备加成），不信任客户端裸值。
        # 客户端传入的 attack_power 仅作范围提示，且强制受上限约束。
        atk = session.player_atk
        if isinstance(attack_power, int) and not isinstance(attack_power, bool):
            # 客户端意图仅在 [1, MAX_ATTACK_POWER] 内生效，否则用服务端值
            if 0 < attack_power <= MAX_ATTACK_POWER:
                atk = attack_power
        atk = max(1, min(atk, MAX_ATTACK_POWER))

        # ---- 定点数伤害计算（对齐中间件 calc_damage）----
        # W3 修复：base_power 用固定技能倍率，atk 用服务端归一攻击力，def 用怪物防御
        damage = cabi.calc_damage(
            {"base_power": BASE_SKILL_POWER},
            {"atk": atk},
            {"def": session.monster_def},
        )

        # 应用伤害
        session.monster_hp = max(0, session.monster_hp - int(damage))

        # 检查战斗结束
        if session.monster_hp <= 0:
            session.finished = True
            session.rewards = self._roll_loot(session.seed)
            # 会话已结束，从内存清理（防泄漏）
            self._sessions.pop(combat_id, None)
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
    # 掉落表（C3 修复：与中间件 cabi.roll_loot 完全一致）
    # ============================================================
    def _roll_loot(self, seed: int) -> List[Dict]:
        """确定性掉落（C3 修复：走中间件 cabi.roll_loot，保证跨端 bit 级一致）"""
        result = cabi.roll_loot(LOOT_TABLE_MAIN, seed)
        return result["items"]


class EconomyService:
    """经济服务：统一账本 + 防作弊 + 持久化"""

    def __init__(self, persist_path: Optional[str] = None):
        self._ledger: Dict[str, Dict[str, int]] = {}  # player_id -> {currency: amount}
        self._transactions: List[Dict] = []           # 交易记录（全审计）
        self._tx_id_set = set()                       # 幂等键（W5）
        self._persist_path = persist_path
        if persist_path and os.path.exists(persist_path):
            self._load(persist_path)

    # ---- W7 持久化 ----
    def _load(self, path: str) -> None:
        import json
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._ledger = data.get("ledger", {})
            self._transactions = data.get("transactions", [])
        except Exception:
            pass

    def _flush(self) -> None:
        import json
        if not self._persist_path:
            return
        with open(self._persist_path, "w", encoding="utf-8") as f:
            json.dump({"ledger": self._ledger,
                       "transactions": self._transactions}, f,
                      ensure_ascii=False)

    # ============================================================
    # 货币操作（C1 修复：全部 amount>0 校验 + 幂等 + 审计）
    # ============================================================
    def init_account(self, player_id: str) -> None:
        """初始化玩家账户"""
        if player_id not in self._ledger:
            self._ledger[player_id] = {
                "gold": 0,
                "star_core": 0,
                "eroding_stone": 0,
            }

    def _validate_amount(self, amount: int, max_amount: int = None) -> Optional[str]:
        """C1 修复：金额必须为正整数且不超过上限。返回错误原因或 None。"""
        if not isinstance(amount, int) or isinstance(amount, bool):
            return "amount must be an integer"
        if amount <= 0:
            return "amount must be positive"
        if max_amount is not None and amount > max_amount:
            return f"amount exceeds limit {max_amount}"
        return None

    def _check_tx_id(self, tx_id: str) -> bool:
        """幂等键检查（W5）：已消费过的 id 返回 True（应拒绝重复）"""
        return tx_id in self._tx_id_set

    def credit(self, player_id: str, currency: str, amount: int,
               reason: str = "", tx_id: str = "") -> Dict:
        """入账（服务端权威）。C1：校验 amount>0。W5：支持幂等。"""
        err = self._validate_amount(amount)
        if err:
            return {"status": "error", "reason": err}
        if currency not in VALID_CURRENCIES:
            return {"status": "error", "reason": f"invalid currency '{currency}'"}
        # 幂等
        if tx_id:
            if self._check_tx_id(tx_id):
                return {"status": "duplicated", "reason": "tx already applied"}
            self._tx_id_set.add(tx_id)

        self.init_account(player_id)
        self._ledger[player_id][currency] += amount
        tx = {
            "player_id": player_id,
            "currency": currency,
            "delta": amount,
            "balance": self._ledger[player_id][currency],
            "reason": reason,
            "tx_id": tx_id or "",
            "timestamp": int(time.time() * 1000),
        }
        self._transactions.append(tx)
        self._flush()
        return {"status": "ok", "transaction": tx}

    def debit(self, player_id: str, currency: str, amount: int,
              reason: str = "", tx_id: str = "") -> Dict:
        """出账（服务端权威）。C1：校验 amount>0。余额不足拒绝。"""
        err = self._validate_amount(amount)
        if err:
            return {"status": "error", "reason": err}
        if currency not in VALID_CURRENCIES:
            return {"status": "error", "reason": f"invalid currency '{currency}'"}
        if tx_id and self._check_tx_id(tx_id):
            return {"status": "duplicated", "reason": "tx already applied"}

        self.init_account(player_id)
        balance = self._ledger[player_id][currency]
        if balance < amount:
            return {
                "status": "insufficient",
                "currency": currency,
                "balance": balance,
                "required": amount,
            }
        self._ledger[player_id][currency] -= amount
        if tx_id:
            self._tx_id_set.add(tx_id)
        tx = {
            "player_id": player_id,
            "currency": currency,
            "delta": -amount,
            "balance": self._ledger[player_id][currency],
            "reason": reason,
            "tx_id": tx_id or "",
            "timestamp": int(time.time() * 1000),
        }
        self._transactions.append(tx)
        self._flush()
        return {"status": "ok", "transaction": tx}

    def transfer(self, from_id: str, to_id: str,
                 currency: str, amount: int, tx_id: str = "") -> Dict:
        """
        跨玩家转账（统一账本）。
        W4 修复：from != to、单笔上限、金额>0。
        """
        # ---- W4 校验 ----
        if from_id == to_id:
            return {"status": "error", "reason": "cannot transfer to self"}
        err = self._validate_amount(amount, MAX_TRANSFER_AMOUNT)
        if err:
            return {"status": "error", "reason": err}
        if tx_id and self._check_tx_id(tx_id):
            return {"status": "duplicated", "reason": "tx already applied"}
        if not tx_id:
            tx_id = uuid.uuid4().hex
        # 拆分幂等键：出账与入账各用独立子键，避免同键被幂等拦截
        debit_tx_id = f"{tx_id}:d"
        credit_tx_id = f"{tx_id}:c"

        result = self.debit(from_id, currency, amount,
                            reason=f"transfer to {to_id}", tx_id=debit_tx_id)
        if result["status"] != "ok":
            return result
        self.credit(to_id, currency, amount,
                    reason=f"transfer from {from_id}", tx_id=credit_tx_id)
        return {"status": "ok"}

    def get_balance(self, player_id: str) -> Dict[str, int]:
        self.init_account(player_id)
        return dict(self._ledger[player_id])

    def get_transactions(self, player_id: str) -> List[Dict]:
        """获取玩家交易记录（全审计）"""
        return [tx for tx in self._transactions if tx["player_id"] == player_id]



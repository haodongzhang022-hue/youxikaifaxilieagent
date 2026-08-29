"""
test_pitfalls_scan.py - 坑点经验库配套巡检脚本

对 docs/game-pitfalls/ 经验库中已声明的坑做自动检测。
修复完成后，这些断言改为「验证漏洞已堵住」（防回退）。

对应经验库：
- C1/A1: 负数转账刷钱 → 应被拒绝
- C2/B1: 战斗越权 → 应被拒绝
- C3/C1: 掉落跨端不一致 → 应一致（走 cabi.roll_loot）
- W1/E1: attack_power 无上限 → 应受服务端归一约束
- W3/D3: quest progress 客户端可控 → 应单调校验
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.core.combat_service import EconomyService, CombatService
from middleware.bindings.python import cabi
from server.core.gateway import Gateway
from server.proto.messages import GameRequest


class TestKnownPitfallsFixed(unittest.TestCase):
    """确认经验库中已声明坑的当前状态（修复后防回退）"""

    def test_a1_negative_credit(self):
        """A1: 负数入账应被拒绝（C1 已修复）"""
        eco = EconomyService()
        eco.init_account("p1")
        r = eco.credit("p1", "gold", -1000)
        self.assertNotEqual(r["status"], "ok")
        # 余额不受影响
        self.assertEqual(eco.get_balance("p1")["gold"], 0)

    def test_a1_zero_credit(self):
        """A1: 零金额入账应被拒绝"""
        eco = EconomyService()
        eco.init_account("p1")
        r = eco.credit("p1", "gold", 0)
        self.assertNotEqual(r["status"], "ok")

    def test_a1_string_credit(self):
        """A1: 字符串金额应被拒绝（防 DoS）"""
        eco = EconomyService()
        eco.init_account("p1")
        r = eco.credit("p1", "gold", "100")
        self.assertNotEqual(r["status"], "ok")

    def test_b1_combat_privilege(self):
        """B1: 战斗越权应被拒绝（C2 已修复）"""
        cs = CombatService()
        s = cs.start_combat("owner", seed=42)
        r = cs.process_attack(s.combat_id, "attacker", attack_power=999)
        self.assertEqual(r["status"], "rejected")

    def test_c1_loot_inconsistent(self):
        """C1: 服务端掉落应与中间件 roll_loot 一致（C3 已修复）"""
        cs = CombatService()
        server_loot = cs._roll_loot(42)
        mid_loot = cabi.roll_loot("loot_table_main", 42)["items"]
        self.assertEqual(server_loot, mid_loot)

    def test_e1_attack_power_unbounded(self):
        """E1: attack_power 超上限应受服务端约束（W1 已修复）"""
        cs = CombatService()
        s = cs.start_combat("p1", seed=7, monster_hp=100)
        # 传超大值，服务端归一后伤害受限，无法一次秒 100HP
        r = cs.process_attack(s.combat_id, "p1", attack_power=10 ** 12)
        self.assertNotEqual(r["status"], "victory")

    def test_d3_quest_progress_client_controlled(self):
        """D3: quest progress 客户端可控 → 应单调校验（W3 已修复）"""
        gw = Gateway()
        _, result = gw.auth.login("web", "token_abcdefg", "d1")
        player_id = result["player"]["player_id"]
        token = result["session_token"]
        # 先设置 progress=50
        req1 = GameRequest.create(player_id, "quest_update",
                                  {"session_token": token, "quest_id": "q1", "progress": 50})
        resp1 = gw.handle(req1)
        self.assertFalse(resp1.payload.get("completed"))
        # 再回退到 20，应被拒绝（单调校验）
        req2 = GameRequest.create(player_id, "quest_update",
                                  {"session_token": token, "quest_id": "q1", "progress": 20})
        resp2 = gw.handle(req2)
        self.assertNotEqual(resp2.status, 0)

    def test_w4_transfer_to_self(self):
        """W4: 转账给自己应被拒绝"""
        eco = EconomyService()
        eco.init_account("p1")
        eco.credit("p1", "gold", 100)
        r = eco.transfer("p1", "p1", "gold", 10)
        self.assertNotEqual(r["status"], "ok")

    def test_w6_move_too_fast(self):
        """W6: 移动超速应被拒绝（防瞬移）"""
        from server.core.world_state import WorldState
        ws = WorldState()
        ws.set_entity("player_1", {"player_id": "1", "x": 0, "z": 0, "hp": 100})
        result = ws.apply_action("1", {"type": "move", "x": 50, "z": 0})
        self.assertEqual(result["status"], "rejected")

    def test_w2_collect_invalid_type(self):
        """W2: 采集非法资源类型应被拒绝"""
        from server.core.world_state import WorldState
        ws = WorldState()
        ws.set_entity("player_1", {"player_id": "1", "x": 0, "z": 0, "inventory": {}})
        result = ws.apply_action("1", {"type": "collect", "resource": {"type": "hack", "amount": 5}})
        self.assertEqual(result["status"], "rejected")


if __name__ == "__main__":
    unittest.main()

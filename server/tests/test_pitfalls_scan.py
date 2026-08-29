"""
test_pitfalls_scan.py - 坑点经验库配套巡检脚本

对 docs/game-pitfalls/ 经验库中已声明的坑做自动检测。
当前标注为「已知存在」的坑，检测到即通过（记录存在性），
用于防止回归与量化修复进度；修复后应将对应断言改为「不通过」。

对应经验库：
- C1/A1: 负数转账刷钱
- C2/B1: 战斗越权
- C3/C1: 掉落跨端不一致
- W1/E1: attack_power 无上限
- W3/D3: quest progress 客户端可控
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


class TestKnownPitfalls(unittest.TestCase):
    """确认经验库中已声明坑的当前存在性（修复前基线）"""

    def test_a1_negative_credit(self):
        """A1: 负数入账应被拒绝（当前已知存在漏洞→验证可复现）"""
        eco = EconomyService()
        eco.init_account("p1")
        r = eco.credit("p1", "gold", -1000)
        # 修复前：负数入账会通过 → 此处断言它「当前确实存在漏洞」以便量化
        self.assertEqual(r["status"], "ok")  # 已知漏洞基线
        self.assertEqual(eco.get_balance("p1")["gold"], -1000)

    def test_b1_combat_privilege(self):
        """B1: 战斗越权（他人可攻击我的战斗）"""
        cs = CombatService()
        s = cs.start_combat("owner", seed=42)
        r = cs.process_attack(s.combat_id, attack_power=999)  # 攻击者≠owner
        self.assertEqual(r["status"], "victory")  # 已知漏洞基线

    def test_c1_loot_inconsistent(self):
        """C1: 服务端 _roll_loot 与中间件 roll_loot 不一致"""
        cs = CombatService()
        server_loot = cs._roll_loot(42)
        mid_loot = cabi.roll_loot("loot_table_main", 42)["items"]
        self.assertNotEqual(server_loot, mid_loot)  # 已知不一致基线

    def test_e1_attack_power_unbounded(self):
        """E1: attack_power 无上限"""
        cs = CombatService()
        s = cs.start_combat("p1", seed=7)
        r = cs.process_attack(s.combat_id, attack_power=10 ** 12)
        self.assertEqual(r["status"], "victory")  # 已知漏洞基线

    def test_d3_quest_progress_client_controlled(self):
        """D3: quest progress 客户端可控，可刷完成"""
        gw = Gateway()
        _, result = gw.auth.login("web", "token_abcdefg", "d1")
        player_id = result["player"]["player_id"]
        token = result["session_token"]
        req = GameRequest.create(player_id, "quest_update",
                                 {"session_token": token, "quest_id": "q1", "progress": 99999})
        resp = gw.handle(req)
        self.assertTrue(resp.payload.get("completed"))  # 已知漏洞基线


if __name__ == "__main__":
    unittest.main()

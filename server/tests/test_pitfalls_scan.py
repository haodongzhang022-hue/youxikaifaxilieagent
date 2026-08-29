"""
test_pitfalls_scan.py - 坑点经验库配套巡检脚本

对 docs/game-pitfalls/ 经验库中已声明的坑做自动检测。
当前标注为「已修复」的坑，检测到已防护即通过（断言漏洞不可复现）。

对应经验库：
- C1/A1: 负数转账刷钱 → ✅ 已修复（amount>0 校验）
- C2/B1: 战斗越权 → ✅ 已修复（caller 身份校验）
- C3/C1: 掉落跨端不一致 → ✅ 已修复（走中间件 cabi.roll_loot）
- W1/E1: attack_power 无上限 → ✅ 已修复（服务端上限校验）
- W3/D3: quest progress 客户端可控 → ✅ 已修复（单调 + 范围校验）
- W2/E2: 采集类型客户端可控 → ✅ 已修复（白名单 + 上限）
- W4/E4: transfer 无 to==from → ✅ 已修复（from != to + 单笔上限）
- W5/E5: 发奖无幂等 → ✅ 已修复（rewarded_combats 防重）
- W6/E6: 可瞬移 → ✅ 已修复（MAX_MOVE_SPEED 校验）
- W7/E7: 数据仅内存态 → ✅ 已修复（persist/load 持久化支持）
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


class TestFixedPitfalls(unittest.TestCase):
    """确认经验库中已声明坑已修复（修复后巡检基线）"""

    def test_a1_negative_credit(self):
        """A1: 负数入账应被拒绝（修复后 → 应不通过/被拒绝）"""
        eco = EconomyService()
        eco.init_account("p1")
        r = eco.credit("p1", "gold", -1000)
        self.assertEqual(r["status"], "error")  # 修复后：负数入账被拒绝
        self.assertEqual(eco.get_balance("p1")["gold"], 0)  # 余额不变

    def test_a2_negative_debit(self):
        """A1 扩展: 负数出账应被拒绝"""
        eco = EconomyService()
        eco.init_account("p1")
        eco.credit("p1", "gold", 100)
        r = eco.debit("p1", "gold", -100)
        self.assertEqual(r["status"], "error")
        self.assertEqual(eco.get_balance("p1")["gold"], 100)

    def test_a3_negative_transfer(self):
        """A1 扩展: 负数转账应被拒绝"""
        eco = EconomyService()
        eco.init_account("p1")
        eco.init_account("p2")
        eco.credit("p1", "gold", 100)
        r = eco.transfer("p1", "p2", "gold", -50)
        self.assertEqual(r["status"], "error")
        self.assertEqual(eco.get_balance("p1")["gold"], 100)
        self.assertEqual(eco.get_balance("p2")["gold"], 0)

    def test_b1_combat_privilege(self):
        """B1: 战斗越权（他人不可攻击我的战斗）"""
        cs = CombatService()
        s = cs.start_combat("owner", seed=42)
        # 攻击者 carol ≠ owner → 应被拒绝
        r = cs.process_attack(s.combat_id, attack_power=999, caller_player_id="carol")
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["reason"], "permission denied: not combat owner")
        # owner 自己攻击 → 正常
        r2 = cs.process_attack(s.combat_id, attack_power=999, caller_player_id="owner")
        self.assertEqual(r2["status"], "victory")

    def test_b2_end_combat_privilege(self):
        """B2: end_combat 越权校验"""
        cs = CombatService()
        s = cs.start_combat("owner", seed=7)
        # 他人调用 end_combat 应返回 None
        result = cs.end_combat(s.combat_id, caller_player_id="carol")
        self.assertIsNone(result)
        # owner 自己调用正常
        result2 = cs.end_combat(s.combat_id, caller_player_id="owner")
        self.assertIsNotNone(result2)

    def test_c1_loot_inconsistent(self):
        """C1: 服务端 _roll_loot 与中间件 roll_loot 对齐"""
        cs = CombatService()
        server_loot = cs._roll_loot(42)
        mid_loot = cabi.roll_loot("loot_table_main", 42)["items"]
        # 修复后：数据结构对齐
        self.assertEqual(len(server_loot), len(mid_loot))
        # 每个元素都能在中间件中找到对应
        for i, item in enumerate(server_loot):
            self.assertEqual(item["item"], mid_loot[i]["id"])
            self.assertEqual(item["amount"], mid_loot[i]["qty"])

    def test_e1_attack_power_unbounded(self):
        """E1: attack_power 无上限（修复后：超限被拒绝）"""
        cs = CombatService()
        s = cs.start_combat("p1", seed=7)
        r = cs.process_attack(s.combat_id, attack_power=10 ** 12, caller_player_id="p1")
        self.assertEqual(r["status"], "error")
        self.assertIn("invalid attack_power", r["reason"])
        # 合法 attack_power 正常
        r2 = cs.process_attack(s.combat_id, attack_power=10, caller_player_id="p1")
        self.assertIn(r2["status"], ("in_progress", "victory"))

    def test_d3_quest_progress_client_controlled(self):
        """D3: quest progress 客户端可控（修复后：范围/单调校验）"""
        gw = Gateway()
        _, result = gw.auth.login("web", "token_abcdefg", "d1")
        player_id = result["player"]["player_id"]
        token = result["session_token"]

        # 超范围 → 被拒绝
        req = GameRequest.create(player_id, "quest_update",
                                 {"session_token": token, "quest_id": "q1", "progress": 99999})
        resp = gw.handle(req)
        self.assertNotEqual(resp.status, 0)  # 被拒绝

        # 正常进度 → 通过
        req2 = GameRequest.create(player_id, "quest_update",
                                  {"session_token": token, "quest_id": "q1", "progress": 50})
        resp2 = gw.handle(req2)
        self.assertEqual(resp2.status, 0)
        self.assertFalse(resp2.payload.get("completed"))

        # 单调性：倒退 → 被拒绝
        req3 = GameRequest.create(player_id, "quest_update",
                                  {"session_token": token, "quest_id": "q1", "progress": 30})
        resp3 = gw.handle(req3)
        self.assertNotEqual(resp3.status, 0)

    def test_w2_collect_whitelist(self):
        """W2: 采集资源类型白名单 + 数量上限"""
        gw = Gateway()
        _, result = gw.auth.login("web", "token_abcdefg", "d2")
        player_id = result["player"]["player_id"]
        token = result["session_token"]

        # 非法资源类型 → 被拒绝
        req = GameRequest.create(player_id, "gameplay_action", {
            "session_token": token,
            "action": {"type": "collect", "resource": {"type": "hack", "amount": 1}},
        })
        resp = gw.handle(req)
        self.assertEqual(resp.status, 0)
        self.assertEqual(resp.payload.get("status"), "rejected")

        # 数量超上限 → 被拒绝
        req2 = GameRequest.create(player_id, "gameplay_action", {
            "session_token": token,
            "action": {"type": "collect", "resource": {"type": "wood", "amount": 999}},
        })
        resp2 = gw.handle(req2)
        self.assertEqual(resp2.status, 0)
        self.assertEqual(resp2.payload.get("status"), "rejected")

        # 合法采集 → 通过
        req3 = GameRequest.create(player_id, "gameplay_action", {
            "session_token": token,
            "action": {"type": "collect", "resource": {"type": "wood", "amount": 3}},
        })
        resp3 = gw.handle(req3)
        self.assertEqual(resp3.status, 0)
        self.assertEqual(resp3.payload.get("status"), "accepted")

    def test_w4_transfer_self(self):
        """W4: transfer 无 to==from 校验（修复后：拒绝自我转账）"""
        eco = EconomyService()
        eco.init_account("p1")
        eco.credit("p1", "gold", 100)
        r = eco.transfer("p1", "p1", "gold", 10)
        self.assertEqual(r["status"], "error")
        self.assertIn("cannot transfer to self", r["reason"])

    def test_w4_transfer_limit(self):
        """W4: 单笔转账上限"""
        eco = EconomyService()
        eco.init_account("p1")
        eco.init_account("p2")
        eco.credit("p1", "gold", 2000000)
        r = eco.transfer("p1", "p2", "gold", 2000000)
        self.assertEqual(r["status"], "error")
        self.assertIn("exceeds single limit", r["reason"])

    def test_w5_reward_idempotent(self):
        """W5: 发奖幂等"""
        cs = CombatService()
        s = cs.start_combat("p1", seed=7)
        # 第一次攻击获胜
        r = cs.process_attack(s.combat_id, attack_power=1000, caller_player_id="p1")
        self.assertEqual(r["status"], "victory")
        # 发奖
        if not cs.is_rewarded(s.combat_id):
            cs.mark_rewarded(s.combat_id)
        self.assertTrue(cs.is_rewarded(s.combat_id))
        # 再次攻击同一战斗应被拒绝（战斗已结束）
        r2 = cs.process_attack(s.combat_id, attack_power=1000, caller_player_id="p1")
        self.assertEqual(r2["status"], "error")

    def test_w6_no_teleport(self):
        """W6: 可瞬移（修复后：超速移动被拒绝）"""
        gw = Gateway()
        _, result = gw.auth.login("web", "token_abcdefg", "d6")
        player_id = result["player"]["player_id"]
        token = result["session_token"]

        # 瞬移到远处 → 被拒绝
        req = GameRequest.create(player_id, "gameplay_action", {
            "session_token": token,
            "action": {"type": "move", "x": 5000, "z": 0},
        })
        resp = gw.handle(req)
        self.assertEqual(resp.status, 0)
        self.assertEqual(resp.payload.get("status"), "rejected")

        # 小范围移动 → 通过
        req2 = GameRequest.create(player_id, "gameplay_action", {
            "session_token": token,
            "action": {"type": "move", "x": 50, "z": 50},
        })
        resp2 = gw.handle(req2)
        self.assertEqual(resp2.status, 0)
        self.assertEqual(resp2.payload.get("status"), "accepted")

    def test_w7_persistence(self):
        """W7: 数据持久化支持"""
        import tempfile
        eco = EconomyService()
        eco.init_account("p1")
        eco.credit("p1", "gold", 500)
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            path = f.name
        self.assertTrue(eco.persist(path))
        # 加载
        eco2 = EconomyService()
        self.assertTrue(eco2.load(path))
        self.assertEqual(eco2.get_balance("p1")["gold"], 500)


if __name__ == "__main__":
    unittest.main()

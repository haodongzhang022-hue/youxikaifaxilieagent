"""
test_server.py - 多端共享服务端核心测试

验证：
1. 多端统一协议（登录/玩法/战斗/经济）
2. 服务端权威状态同步
3. 定点数战斗结算一致性
4. 统一经济账本
"""

import os
import sys
import unittest

# 确保能导入 middleware 和 server 包
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.proto.messages import GameRequest, GameResponse, PlayerData, serialize
from server.core.gateway import Gateway
from server.core.auth_service import AuthService
from server.core.combat_service import CombatService, EconomyService
from server.core.world_state import WorldState
from server.core.gameplay_service import GameplayService


class TestProtocol(unittest.TestCase):
    """统一协议测试"""

    def test_request_serialization(self):
        req = GameRequest.create("P_TEST", "login", {"token": "abcdef123456"})
        data = serialize(req)
        self.assertIn("request_id", data)
        self.assertIn("msg_type", data)
        self.assertIn("login", data)

    def test_response_serialization(self):
        resp = GameResponse.ok("req123", {"status": "ok"})
        data = serialize(resp)
        self.assertIn("request_id", data)
        self.assertIn("status", data)


class TestAuthService(unittest.TestCase):
    """账号服务测试"""

    def setUp(self):
        self.auth = AuthService()

    def test_multi_platform_login(self):
        """四平台都能登录"""
        for platform in ("web", "cocos", "unity", "ue"):
            ok, result = self.auth.login(platform, "token_abcdefg", f"device_{platform}")
            self.assertTrue(ok)
            self.assertIn("session_token", result)
            self.assertIn("player", result)

    def test_session_verify(self):
        """会话验证"""
        _, result = self.auth.login("web", "token_abcdefg", "device_1")
        token = result["session_token"]
        player_id = self.auth.verify_session(token)
        self.assertIsNotNone(player_id)

    def test_bad_token_rejected(self):
        """无效 token 拒绝"""
        ok, _ = self.auth.login("web", "bad", "device_2")
        self.assertFalse(ok)

    def test_platform_bind(self):
        """多端绑定"""
        _, result = self.auth.login("web", "token_abcdefg", "device_web")
        token = result["session_token"]
        player_id = result["player"]["player_id"]
        self.assertTrue(self.auth.bind_platform(token, "cocos", "device_cocos"))
        # 用新平台登录应得到同一个 player_id
        _, result2 = self.auth.login("cocos", "token_abcdefg", "device_cocos")
        self.assertEqual(result2["player"]["player_id"], player_id)


class TestWorldState(unittest.TestCase):
    """服务端权威世界状态测试"""

    def setUp(self):
        self.world = WorldState()

    def test_set_get_entity(self):
        """设置/获取实体"""
        self.world.set_entity("player_1", {"hp": 100, "x": 10, "z": 20})
        entity = self.world.get_entity("player_1")
        self.assertEqual(entity["hp"], 100)
        self.assertEqual(entity["x"], 10)

    def test_apply_action_move(self):
        """移动动作（服务端权威）"""
        self.world.set_entity("player_1", {"player_id": "1", "x": 0, "z": 0, "hp": 100})
        result = self.world.apply_action("1", {"type": "move", "x": 15, "z": 30})
        self.assertEqual(result["status"], "accepted")
        entity = self.world.get_entity("player_1")
        self.assertEqual(entity["x"], 15)
        self.assertEqual(entity["z"], 30)

    def test_apply_action_collect(self):
        """采集动作"""
        self.world.set_entity("player_1", {"player_id": "1", "x": 0, "z": 0, "hp": 100, "inventory": {}})
        result = self.world.apply_action("1", {"type": "collect", "resource": {"type": "wood", "amount": 5}})
        self.assertEqual(result["status"], "accepted")
        entity = self.world.get_entity("player_1")
        self.assertEqual(entity["inventory"]["wood"], 5)

    def test_invalid_action_rejected(self):
        """非法动作被拒绝"""
        self.world.set_entity("player_1", {"player_id": "1", "x": 0, "z": 0})
        result = self.world.apply_action("1", {"type": "hack", "x": 0, "z": 0})
        self.assertEqual(result["status"], "rejected")

    def test_snapshot_version(self):
        """快照版本递增"""
        snap1 = self.world.snapshot()
        self.world.set_entity("player_1", {"hp": 100})
        snap2 = self.world.snapshot()
        self.assertGreater(snap2["version"], snap1["version"])


class TestCombatService(unittest.TestCase):
    """战斗服务测试"""

    def setUp(self):
        self.combat = CombatService()

    def test_start_combat(self):
        """开始战斗"""
        session = self.combat.start_combat("P1", seed=42, monster_hp=100)
        self.assertEqual(session.monster_hp, 100)
        self.assertFalse(session.finished)

    def test_fixed_point_damage(self):
        """定点数伤害计算一致"""
        from middleware.bindings.python import cabi
        # 与中间件定点数完全一致
        fp = cabi.fp_from_int(15)
        self.assertEqual(cabi.fp_to_float(fp), 15.0)
        fp_dmg = cabi.fp_mul(cabi.fp_from_int(10), cabi.fp_from_int(1))
        self.assertEqual(cabi.fp_to_float(fp_dmg), 10.0)

    def test_combat_attack_victory(self):
        """战斗攻击到胜利"""
        session = self.combat.start_combat("P1", seed=42, monster_hp=20)
        result = self.combat.process_attack(session.combat_id, attack_power=25)
        self.assertEqual(result["status"], "victory")
        self.assertIn("rewards", result)

    def test_deterministic_loot(self):
        """确定性掉落：同 seed 同掉落"""
        loot1 = self.combat._roll_loot(42)
        loot2 = self.combat._roll_loot(42)
        self.assertEqual(loot1, loot2)


class TestEconomyService(unittest.TestCase):
    """经济服务测试"""

    def setUp(self):
        self.economy = EconomyService()

    def test_init_and_credit(self):
        """开户 + 入账"""
        self.economy.init_account("P1")
        result = self.economy.credit("P1", "gold", 100, reason="test")
        self.assertEqual(result["status"], "ok")
        balance = self.economy.get_balance("P1")
        self.assertEqual(balance["gold"], 100)

    def test_debit_insufficient(self):
        """余额不足拒绝出账"""
        self.economy.init_account("P1")
        result = self.economy.debit("P1", "gold", 50, reason="test")
        self.assertEqual(result["status"], "insufficient")

    def test_transfer(self):
        """跨玩家转账"""
        self.economy.init_account("P1")
        self.economy.init_account("P2")
        self.economy.credit("P1", "gold", 100, reason="test")
        result = self.economy.transfer("P1", "P2", "gold", 30)
        self.assertEqual(result["status"], "ok")
        b1 = self.economy.get_balance("P1")
        b2 = self.economy.get_balance("P2")
        self.assertEqual(b1["gold"], 70)
        self.assertEqual(b2["gold"], 30)

    def test_audit_trail(self):
        """交易记录全审计"""
        self.economy.init_account("P1")
        self.economy.credit("P1", "gold", 100, reason="audit_test")
        txns = self.economy.get_transactions("P1")
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns[0]["reason"], "audit_test")


class TestGateway(unittest.TestCase):
    """统一网关测试"""

    def setUp(self):
        self.gateway = Gateway()

    def test_full_login_flow(self):
        """完整登录流程"""
        req = GameRequest.create(
            "temp", "login",
            {"token": "token_abcdefg", "device_id": "dev_1"},
            platform="web",
        )
        resp = self.gateway.handle(req)
        self.assertEqual(resp.status, 0)  # ERR_OK
        self.assertIn("session_token", resp.payload)
        self.assertIn("player", resp.payload)

    def test_session_required(self):
        """未登录请求被拒"""
        req = GameRequest.create("P1", "gameplay_action", {"action": {"type": "move"}})
        resp = self.gateway.handle(req)
        self.assertNotEqual(resp.status, 0)  # 非 OK
        self.assertEqual(resp.status, 1002)  # ERR_SESSION_EXPIRED

    def test_gameplay_after_login(self):
        """登录后玩法操作"""
        # 登录获取 token
        req = GameRequest.create(
            "temp", "login",
            {"token": "token_abcdefg", "device_id": "dev_gw1"},
            platform="web",
        )
        resp = self.gateway.handle(req)
        player_id = resp.payload["player"]["player_id"]
        token = resp.payload["session_token"]

        # 移动
        req2 = GameRequest.create(
            player_id, "gameplay_action",
            {"session_token": token, "action": {"type": "move", "x": 10, "z": 20}},
        )
        resp2 = self.gateway.handle(req2)
        self.assertEqual(resp2.status, 0)
        self.assertEqual(resp2.payload["status"], "accepted")

    def test_combat_flow(self):
        """战斗流程"""
        # 登录
        req = GameRequest.create(
            "temp", "login",
            {"token": "token_abcdefg", "device_id": "dev_gw2"},
            platform="unity",
        )
        resp = self.gateway.handle(req)
        player_id = resp.payload["player"]["player_id"]
        token = resp.payload["session_token"]

        # 开始战斗
        req2 = GameRequest.create(
            player_id, "combat_result",
            {"session_token": token, "action": "start", "seed": 2, "monster_hp": 10},
        )
        resp2 = self.gateway.handle(req2)
        self.assertEqual(resp2.status, 0)
        combat_id = resp2.payload["combat_id"]

        # 攻击直到胜利
        req3 = GameRequest.create(
            player_id, "combat_result",
            {"session_token": token, "action": "attack",
             "combat_id": combat_id, "attack_power": 20},
        )
        resp3 = self.gateway.handle(req3)
        self.assertEqual(resp3.status, 0)
        self.assertEqual(resp3.payload["status"], "victory")

        # 验证奖励入账（战斗胜利后应至少有一种货币 > 0）
        req4 = GameRequest.create(
            player_id, "economy_transfer",
            {"session_token": token, "action": "balance"},
        )
        resp4 = self.gateway.handle(req4)
        self.assertEqual(resp4.status, 0)
        balance = resp4.payload["balance"]
        total_value = (balance["gold"] + balance["star_core"]
                       + balance["eroding_stone"])
        self.assertGreater(total_value, 0)

    def test_quest_update(self):
        """任务进度同步"""
        # 登录
        req = GameRequest.create(
            "temp", "login",
            {"token": "token_abcdefg", "device_id": "dev_gw3"},
            platform="cocos",
        )
        resp = self.gateway.handle(req)
        player_id = resp.payload["player"]["player_id"]
        token = resp.payload["session_token"]

        # 更新任务进度
        req2 = GameRequest.create(
            player_id, "quest_update",
            {"session_token": token, "quest_id": "hunt_wolves", "progress": 50},
        )
        resp2 = self.gateway.handle(req2)
        self.assertEqual(resp2.status, 0)
        self.assertEqual(resp2.payload["progress"], 50)
        self.assertFalse(resp2.payload["completed"])

    def test_economy_transfer(self):
        """经济转账"""
        # 登录两个玩家
        req_a = GameRequest.create(
            "temp", "login",
            {"token": "token_abcdefg", "device_id": "dev_a"},
            platform="web",
        )
        resp_a = self.gateway.handle(req_a)
        player_a = resp_a.payload["player"]["player_id"]
        token_a = resp_a.payload["session_token"]

        req_b = GameRequest.create(
            "temp", "login",
            {"token": "token_abcdefg", "device_id": "dev_b"},
            platform="ue",
        )
        resp_b = self.gateway.handle(req_b)
        player_b = resp_b.payload["player"]["player_id"]
        token_b = resp_b.payload["session_token"]

        # A 给 B 转账
        req_tx = GameRequest.create(
            player_a, "economy_transfer",
            {"session_token": token_a, "action": "transfer",
             "to_player": player_b, "currency": "gold", "amount": 100},
        )
        resp_tx = self.gateway.handle(req_tx)
        self.assertEqual(resp_tx.status, 0)


if __name__ == "__main__":
    unittest.main()


# ============================================================
# 安全修复回归测试（C1/C2/C3/W1/W2/W3/W4）
# ============================================================

class TestSecurityFixC1(unittest.TestCase):
    """C1 修复：货币复制漏洞 —— 负数金额校验"""

    def setUp(self):
        self.economy = EconomyService()

    def test_negative_credit_rejected(self):
        """负数 credit 必须被拒绝（C1）"""
        self.economy.init_account("P1")
        result = self.economy.credit("P1", "gold", -100, reason="hack")
        self.assertEqual(result["status"], "error")
        # 余额不应变化
        balance = self.economy.get_balance("P1")
        self.assertEqual(balance["gold"], 0)

    def test_zero_credit_rejected(self):
        """零 credit 必须被拒绝（C1）"""
        self.economy.init_account("P1")
        result = self.economy.credit("P1", "gold", 0)
        self.assertEqual(result["status"], "error")

    def test_negative_debit_rejected(self):
        """负数 debit 必须被拒绝（C1）"""
        self.economy.init_account("P1")
        result = self.economy.debit("P1", "gold", -100)
        self.assertEqual(result["status"], "error")

    def test_negative_transfer_rejected(self):
        """负数 transfer 必须被拒绝（C1）"""
        self.economy.init_account("P1")
        self.economy.init_account("P2")
        result = self.economy.transfer("P1", "P2", "gold", -100)
        self.assertEqual(result["status"], "error")

    def test_self_transfer_rejected(self):
        """自转必须被拒绝（C1）"""
        self.economy.init_account("P1")
        result = self.economy.transfer("P1", "P1", "gold", 100)
        self.assertEqual(result["status"], "error")


class TestSecurityFixC2(unittest.TestCase):
    """C2 修复：战斗越权 —— 会话所有者校验"""

    def setUp(self):
        self.combat = CombatService()

    def test_attack_own_session_allowed(self):
        """自己攻击自己会话允许（C2）"""
        session = self.combat.start_combat("P1", seed=42, monster_hp=100)
        result = self.combat.process_attack(session.combat_id, 10, caller_player_id="P1")
        self.assertIn("status", result)
        self.assertNotEqual(result["status"], "error")

    def test_attack_other_session_rejected(self):
        """攻击他人会话必须被拒绝（C2）"""
        session = self.combat.start_combat("P1", seed=42, monster_hp=100)
        result = self.combat.process_attack(session.combat_id, 10, caller_player_id="P2")
        self.assertEqual(result["status"], "error")
        self.assertIn("forbidden", result["reason"])

    def test_attack_no_caller_works(self):
        """未传 caller 时行为兼容（C2 向后兼容）"""
        session = self.combat.start_combat("P1", seed=42, monster_hp=100)
        result = self.combat.process_attack(session.combat_id, 10)
        self.assertIn("status", result)


class TestSecurityFixC3(unittest.TestCase):
    """C3 修复：跨端一致 —— _roll_loot 对齐中间件"""

    def setUp(self):
        self.combat = CombatService()

    def test_loot_aligned_with_middleware(self):
        """掉落结果必须与中间件 cabi.roll_loot 一致（C3）"""
        from middleware.bindings.python import cabi

        # 服务端 _roll_loot 与中间件 roll_loot 应产生一致物品集合
        server_loot = self.combat._roll_loot(42)
        middleware_loot = cabi.roll_loot(self.combat.LOOT_TABLE_ID, 42)

        middleware_items = middleware_loot.get("items", [])
        self.assertEqual(len(server_loot), len(middleware_items))

        # 逐项比对（服务端转换为 {"item", "amount"} 格式）
        for s_item, m_item in zip(server_loot, middleware_items):
            self.assertEqual(s_item["item"], m_item["id"])
            self.assertEqual(s_item["amount"], m_item["qty"])

    def test_loot_items_from_middleware_table(self):
        """掉落物品必须来自中间件掉落表（C3）"""
        server_loot = self.combat._roll_loot(42)
        allowed = {"coin", "potion", "gem", "ore", "rune"}
        for item in server_loot:
            self.assertIn(item["item"], allowed)

    def test_loot_deterministic_same_seed(self):
        """同 seed 掉落确定性（C3）"""
        loot1 = self.combat._roll_loot(12345)
        loot2 = self.combat._roll_loot(12345)
        self.assertEqual(loot1, loot2)


class TestWorldStateFixW1W2(unittest.TestCase):
    """W1/W2 修复：attack/interact 结算 + rejected 传播"""

    def setUp(self):
        self.world = WorldState()

    def test_attack_action_settles(self):
        """attack 动作有服务端结算逻辑（W1）"""
        self.world.set_entity("player_1", {"player_id": "1", "hp": 100})
        self.world.set_entity("enemy_1", {"hp": 100})

        result = self.world.apply_action(
            "1", {"type": "attack", "target_id": "enemy_1", "attack_power": 30}
        )
        self.assertEqual(result["status"], "accepted")
        enemy = self.world.get_entity("enemy_1")
        self.assertEqual(enemy["hp"], 70)

    def test_attack_missing_target_rejected(self):
        """attack 目标不存在应返回 rejected（W1/W2）"""
        self.world.set_entity("player_1", {"player_id": "1", "hp": 100})
        result = self.world.apply_action(
            "1", {"type": "attack", "target_id": "nobody", "attack_power": 30}
        )
        self.assertEqual(result["status"], "rejected")

    def test_interact_action_settles(self):
        """interact 动作有服务端结算逻辑（W1）"""
        self.world.set_entity("player_1", {"player_id": "1", "hp": 100})
        self.world.set_entity("npc_1", {"name": "Blacksmith"})

        result = self.world.apply_action(
            "1", {"type": "interact", "target_id": "npc_1"}
        )
        self.assertEqual(result["status"], "accepted")
        npc = self.world.get_entity("npc_1")
        self.assertTrue(npc.get("interacted", False))
        self.assertEqual(npc.get("interacted_by"), "1")

    def test_use_item_missing_item_rejected(self):
        """使用不存在的物品应返回 rejected（W2 传播）"""
        self.world.set_entity("player_1", {"player_id": "1", "inventory": {}})
        result = self.world.apply_action(
            "1", {"type": "use_item", "item": "potion"}
        )
        self.assertEqual(result["status"], "rejected")


class TestGameplayServiceW4(unittest.TestCase):
    """W4 修复：GameplayService 接入 Gateway 路由"""

    def setUp(self):
        self.gateway = Gateway()
        # 登录获取 token
        req = GameRequest.create(
            "temp", "login",
            {"token": "token_abcdefg", "device_id": "dev_gw_w4"},
            platform="web",
        )
        resp = self.gateway.handle(req)
        self.player_id = resp.payload["player"]["player_id"]
        self.token = resp.payload["session_token"]

    def test_gameplay_with_scene(self):
        """带 scene_id 的玩法动作经 GameplayService 路由（W4）"""
        req = GameRequest.create(
            self.player_id, "gameplay_action",
            {"session_token": self.token, "scene_id": "LVL_001",
             "action": {"type": "move", "x": 5, "z": 8}},
        )
        resp = self.gateway.handle(req)
        self.assertEqual(resp.status, 0)
        self.assertEqual(resp.payload["status"], "accepted")

    def test_invalid_scene_rejected(self):
        """不存在的场景应被拒绝（W4）"""
        req = GameRequest.create(
            self.player_id, "gameplay_action",
            {"session_token": self.token, "scene_id": "NOT_A_SCENE",
             "action": {"type": "move", "x": 5, "z": 8}},
        )
        resp = self.gateway.handle(req)
        self.assertEqual(resp.status, 0)
        self.assertEqual(resp.payload["status"], "rejected")
        self.assertIn("not found", resp.payload["reason"])

    def test_get_scene_config(self):
        """场景配置可查询（W4）"""
        config = self.gateway.gameplay.get_scene_config("LVL_001")
        self.assertIsNotNone(config)
        self.assertEqual(config["procedural_seed"], 42)


if __name__ == "__main__":
    unittest.main()

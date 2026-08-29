"""
test_server.py - 多端共享服务端核心测试

验证：
1. 多端统一协议（登录/玩法/战斗/经济）
2. 服务端权威状态同步
3. 定点数战斗结算一致性（C1/C2/C3 + W1-W4 修复后）
4. 统一经济账本（含安全校验）
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

    def test_attack_action_settles(self):
        """[W1-FIX] 攻击动作有结算逻辑"""
        self.world.set_entity("player_1", {"player_id": "1", "x": 0, "z": 0, "hp": 100})
        result = self.world.apply_action("1", {"type": "attack", "target": "monster", "damage": 15})
        self.assertEqual(result["status"], "accepted")
        entity = self.world.get_entity("player_1")
        self.assertIn("last_attack", entity)
        self.assertEqual(entity["last_attack"]["damage"], 15)

    def test_interact_action_settles(self):
        """[W1-FIX] 交互动作有结算逻辑"""
        self.world.set_entity("player_1", {"player_id": "1", "x": 0, "z": 0})
        result = self.world.apply_action("1", {"type": "interact", "target": "npc_elder"})
        self.assertEqual(result["status"], "accepted")
        entity = self.world.get_entity("player_1")
        self.assertIn("last_interact", entity)
        self.assertEqual(entity["last_interact"]["target"], "npc_elder")

    def test_use_item_rejected_delta_rejects_action(self):
        """[W2-FIX] 单条 rejected delta 导致整体 rejected"""
        self.world.set_entity("player_1", {"player_id": "1", "inventory": {}})
        result = self.world.apply_action("1", {"type": "use_item", "item": "nonexistent"})
        self.assertEqual(result["status"], "rejected")


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
        # C2-FIX: 传入 caller_player_id
        result = self.combat.process_attack(session.combat_id, "P1", attack_power=25)
        # W3-FIX: damage = 25 * (25/50) = 12，20 HP 怪物需要多次攻击
        self.assertIn(result["status"], ("in_progress", "victory"))
        if result["status"] == "victory":
            self.assertIn("rewards", result)

    def test_combat_attack_owner_only(self):
        """[C2-FIX] 非 owner 攻击被拒绝"""
        session = self.combat.start_combat("P1", seed=42, monster_hp=100)
        result = self.combat.process_attack(session.combat_id, "P2", attack_power=10)
        self.assertEqual(result["status"], "error")
        self.assertIn("permission denied", result.get("reason", ""))

    def test_combat_attack_victory_high_power(self):
        """高攻击力一次击败"""
        session = self.combat.start_combat("P1", seed=42, monster_hp=10)
        result = self.combat.process_attack(session.combat_id, "P1", attack_power=50)
        self.assertEqual(result["status"], "victory")
        self.assertIn("rewards", result)

    def test_deterministic_loot(self):
        """[C3-FIX] 确定性掉落：同 seed 同掉落"""
        loot1 = self.combat._roll_loot(42)
        loot2 = self.combat._roll_loot(42)
        self.assertEqual(loot1, loot2)

    def test_loot_uses_cabi(self):
        """[C3-FIX] 掉落使用 cabi.roll_loot()"""
        from middleware.bindings.python import cabi
        cabi_loot = cabi.roll_loot("combat_loot", 42)
        service_loot = self.combat._roll_loot(42)
        # 掉落物品数量应与中间件一致
        self.assertEqual(len(service_loot), len(cabi_loot.get("items", [])))


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

    def test_credit_negative_amount_rejected(self):
        """[C1-FIX] 负数金额入账被拒绝"""
        self.economy.init_account("P1")
        result = self.economy.credit("P1", "gold", -100, reason="hack")
        self.assertEqual(result["status"], "error")

    def test_credit_zero_amount_rejected(self):
        """[C1-FIX] 零金额入账被拒绝"""
        self.economy.init_account("P1")
        result = self.economy.credit("P1", "gold", 0, reason="hack")
        self.assertEqual(result["status"], "error")

    def test_debit_negative_amount_rejected(self):
        """[C1-FIX] 负数金额出账被拒绝"""
        self.economy.init_account("P1")
        result = self.economy.debit("P1", "gold", -50, reason="hack")
        self.assertEqual(result["status"], "error")

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

    def test_transfer_negative_amount_rejected(self):
        """[C1-FIX] 负数金额转账被拒绝"""
        self.economy.init_account("P1")
        self.economy.init_account("P2")
        result = self.economy.transfer("P1", "P2", "gold", -100)
        self.assertEqual(result["status"], "error")

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

    def test_gameplay_action_with_scene(self):
        """[W4-FIX] GameplayService 场景路由"""
        # 登录
        req = GameRequest.create(
            "temp", "login",
            {"token": "token_abcdefg", "device_id": "dev_gw_scene"},
            platform="web",
        )
        resp = self.gateway.handle(req)
        player_id = resp.payload["player"]["player_id"]
        token = resp.payload["session_token"]

        # 带场景上下文的玩法动作
        req2 = GameRequest.create(
            player_id, "gameplay_action",
            {"session_token": token, "scene_id": "LVL_001",
             "action": {"type": "move", "x": 5, "z": 10}},
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

        # 攻击直到胜利（使用高攻击力保证一次击败）
        req3 = GameRequest.create(
            player_id, "combat_result",
            {"session_token": token, "action": "attack",
             "combat_id": combat_id, "attack_power": 100},
        )
        resp3 = self.gateway.handle(req3)
        self.assertEqual(resp3.status, 0)
        self.assertEqual(resp3.payload["status"], "victory")

        # 验证奖励入账
        req4 = GameRequest.create(
            player_id, "economy_transfer",
            {"session_token": token, "action": "balance"},
        )
        resp4 = self.gateway.handle(req4)
        self.assertEqual(resp4.status, 0)
        balance = resp4.payload["balance"]
        total_value = (balance.get("gold", 0) + balance.get("star_core", 0)
                       + balance.get("eroding_stone", 0) + balance.get("potion", 0)
                       + balance.get("gem", 0) + balance.get("iron_ore", 0)
                       + balance.get("rune", 0))
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

    def test_combat_attack_caller_not_owner(self):
        """[C2-FIX] 网关层越权攻击被拒绝"""
        # 登录两个玩家
        req_a = GameRequest.create(
            "temp", "login",
            {"token": "token_abcdefg", "device_id": "dev_att1"},
            platform="web",
        )
        resp_a = self.gateway.handle(req_a)
        player_a = resp_a.payload["player"]["player_id"]
        token_a = resp_a.payload["session_token"]

        # A 开始战斗
        req_start = GameRequest.create(
            player_a, "combat_result",
            {"session_token": token_a, "action": "start", "seed": 99, "monster_hp": 50},
        )
        resp_start = self.gateway.handle(req_start)
        self.assertEqual(resp_start.status, 0)
        combat_id = resp_start.payload["combat_id"]

        # B 试图攻击 A 的战斗（B 不是 owner）
        req_b = GameRequest.create(
            "temp", "login",
            {"token": "token_abcdefg", "device_id": "dev_att2"},
            platform="web",
        )
        resp_b = self.gateway.handle(req_b)
        player_b = resp_b.payload["player"]["player_id"]
        token_b = resp_b.payload["session_token"]

        req_attack = GameRequest.create(
            player_b, "combat_result",
            {"session_token": token_b, "action": "attack",
             "combat_id": combat_id, "attack_power": 100},
        )
        resp_attack = self.gateway.handle(req_attack)
        self.assertEqual(resp_attack.status, 0)
        self.assertIn("permission denied", resp_attack.payload.get("reason", ""))


if __name__ == "__main__":
    unittest.main()

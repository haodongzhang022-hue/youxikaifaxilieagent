"""
gateway.py - 统一网关

多端统一接入：协议转换 / 鉴权认证 / 路由分发。
所有平台（web/cocos/unity/ue）连接同一网关，走同一套协议。
"""

from typing import Dict, Optional

from server.proto.messages import (
    GameRequest, GameResponse, PlayerData,
    ERR_AUTH_FAILED, ERR_SESSION_EXPIRED, ERR_INVALID_REQUEST,
    MSG_LOGIN, MSG_REFRESH, MSG_GAMEPLAY_ACTION, MSG_GAMEPLAY_SNAPSHOT,
    MSG_COMBAT_RESULT, MSG_QUEST_UPDATE, MSG_ECONOMY_TRANSFER,
)
from server.core.auth_service import AuthService
from server.core.world_state import WorldState
from server.core.combat_service import CombatService, EconomyService


class Gateway:
    """
    统一网关：所有平台请求入口。

    职责：
    1. 协议转换（JSON 入 → 内部消息出）
    2. 鉴权认证（Session Token 校验）
    3. 路由分发（按消息类型路由到对应服务）
    """

    def __init__(self):
        self.auth = AuthService()
        self.world = WorldState()
        self.combat = CombatService()
        self.economy = EconomyService()

    # ============================================================
    # 主入口
    # ============================================================
    def handle(self, request: GameRequest) -> GameResponse:
        """处理统一请求，返回统一响应。"""
        # 路由分发
        msg_type = request.msg_type

        if msg_type == MSG_LOGIN:
            return self._handle_login(request)

        # 除登录外，其余消息需验证会话
        session_token = request.payload.get("session_token", "")
        player_id = self.auth.verify_session(session_token)
        if player_id is None:
            return GameResponse.error(request.request_id, ERR_SESSION_EXPIRED)
        if player_id != request.player_id:
            return GameResponse.error(request.request_id, ERR_AUTH_FAILED)

        if msg_type == MSG_REFRESH:
            return self._handle_refresh(request, session_token)
        elif msg_type == MSG_GAMEPLAY_ACTION:
            return self._handle_gameplay_action(request)
        elif msg_type == MSG_GAMEPLAY_SNAPSHOT:
            return self._handle_snapshot(request)
        elif msg_type == MSG_COMBAT_RESULT:
            return self._handle_combat(request)
        elif msg_type == MSG_QUEST_UPDATE:
            return self._handle_quest(request)
        elif msg_type == MSG_ECONOMY_TRANSFER:
            return self._handle_economy(request)
        else:
            return GameResponse.error(request.request_id, ERR_INVALID_REQUEST)

    # ============================================================
    # 各消息处理
    # ============================================================
    def _handle_login(self, request: GameRequest) -> GameResponse:
        """处理登录"""
        platform = request.platform
        token = request.payload.get("token", "")
        device_id = request.payload.get("device_id", "")

        success, result = self.auth.login(platform, token, device_id)
        if not success:
            return GameResponse.error(request.request_id, ERR_AUTH_FAILED)

        player_id = result["player"]["player_id"]
        # 初始化经济账户
        self.economy.init_account(player_id)
        # 初始化玩家世界实体
        self.world.set_entity(f"player_{player_id}", {
            "player_id": player_id,
            "x": 0, "z": 0, "hp": 100, "max_hp": 100,
            "inventory": {},
        })

        return GameResponse.ok(request.request_id, result)

    def _handle_refresh(self, request: GameRequest, old_token: str) -> GameResponse:
        """处理会话续期"""
        success, new_token = self.auth.refresh_session(old_token)
        if not success:
            return GameResponse.error(request.request_id, ERR_SESSION_EXPIRED)
        return GameResponse.ok(request.request_id, {"session_token": new_token})

    def _handle_gameplay_action(self, request: GameRequest) -> GameResponse:
        """处理玩法动作（服务端权威）"""
        action = request.payload.get("action", {})
        result = self.world.apply_action(request.player_id, action)
        return GameResponse.ok(request.request_id, result)

    def _handle_snapshot(self, request: GameRequest) -> GameResponse:
        """获取世界状态快照"""
        snap = self.world.snapshot()
        return GameResponse.ok(request.request_id, {"snapshot": snap})

    def _handle_combat(self, request: GameRequest) -> GameResponse:
        """处理战斗请求"""
        action = request.payload.get("action", "start")
        player_id = request.player_id

        if action == "start":
            seed = request.payload.get("seed", 42)
            monster_hp = request.payload.get("monster_hp", 100)
            session = self.combat.start_combat(player_id, seed, monster_hp)
            return GameResponse.ok(request.request_id, {
                "combat_id": session.combat_id,
                "monster_hp": session.monster_hp,
            })
        elif action == "attack":
            combat_id = request.payload.get("combat_id", "")
            attack_power = request.payload.get("attack_power", 10)
            result = self.combat.process_attack(combat_id, attack_power)
            # 战斗胜利后自动发放奖励到经济账户
            if result.get("status") == "victory":
                for reward in result.get("rewards", []):
                    item = reward["item"]
                    amount = reward["amount"]
                    if item == "gold":
                        self.economy.credit(player_id, "gold", amount,
                                            reason="combat reward")
                    elif item == "star_shard":
                        self.economy.credit(player_id, "star_core", amount,
                                            reason="combat reward")
            return GameResponse.ok(request.request_id, result)
        else:
            return GameResponse.error(request.request_id, ERR_INVALID_REQUEST)

    def _handle_quest(self, request: GameRequest) -> GameResponse:
        """处理任务更新"""
        quest_id = request.payload.get("quest_id", "")
        progress = request.payload.get("progress", 0)
        player_id = request.player_id

        # 任务进度存服务端
        entity_key = f"quest_{player_id}"
        cur = self.world.get_entity(entity_key) or {"quest_id": quest_id, "progress": 0}
        cur["quest_id"] = quest_id
        cur["progress"] = progress
        self.world.set_entity(entity_key, cur)

        return GameResponse.ok(request.request_id, {
            "quest_id": quest_id,
            "progress": progress,
            "completed": progress >= 100,
        })

    def _handle_economy(self, request: GameRequest) -> GameResponse:
        """处理经济操作"""
        action = request.payload.get("action", "balance")
        player_id = request.player_id

        if action == "balance":
            return GameResponse.ok(request.request_id, {
                "balance": self.economy.get_balance(player_id),
            })
        elif action == "transfer":
            to_id = request.payload.get("to_player", "")
            currency = request.payload.get("currency", "gold")
            amount = request.payload.get("amount", 0)
            result = self.economy.transfer(player_id, to_id, currency, amount)
            return GameResponse.ok(request.request_id, result)
        else:
            return GameResponse.error(request.request_id, ERR_INVALID_REQUEST)

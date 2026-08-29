"""
gateway.py - 统一网关

多端统一接入：协议转换 / 鉴权认证 / 路由分发。
所有平台（web/cocos/unity/ue）连接同一网关，走同一套协议。

服务端权威：所有玩法/经济决策服务端计算，客户端只传意图。
本文件包含坑点经验库多项修复：
- W3: 任务进度单调校验（防刷完成）
- W4: 转账 from!=to + 单笔上限（EconomyService 内）
- W5: 战斗发奖幂等（防重复领奖）
- DoS: 入参类型/范围校验，防异常崩溃
"""

import uuid
from typing import Dict, Optional

from server.proto.messages import (
    GameRequest, GameResponse, PlayerData,
    ERR_AUTH_FAILED, ERR_SESSION_EXPIRED, ERR_INVALID_REQUEST,
    MSG_LOGIN, MSG_REFRESH, MSG_GAMEPLAY_ACTION, MSG_GAMEPLAY_SNAPSHOT,
    MSG_COMBAT_RESULT, MSG_QUEST_UPDATE, MSG_ECONOMY_TRANSFER,
)
from server.core.auth_service import AuthService
from server.core.world_state import WorldState
from server.core.combat_service import (
    CombatService, EconomyService, MAX_ATTACK_POWER, VALID_CURRENCIES,
)
from server.core.gameplay_service import GameplayService


class Gateway:
    """
    统一网关：所有平台请求入口。

    职责：
    1. 协议转换（JSON 入 → 内部消息出）
    2. 鉴权认证（Session Token 校验）
    3. 路由分发（按消息类型路由到对应服务）
    """

    def __init__(self, persist_dir: Optional[str] = None):
        self.auth = AuthService()
        self.world = WorldState(
            persist_path=f"{persist_dir}/world.json" if persist_dir else None
        )
        self.combat = CombatService()
        self.economy = EconomyService(
            persist_path=f"{persist_dir}/economy.json" if persist_dir else None
        )
        self.gameplay = GameplayService(self.world)

        # 战斗发奖幂等键（W5）：combat_id -> 已发放标记
        self._rewarded_combats = set()

    # ============================================================
    # 主入口
    # ============================================================
    def handle(self, request: GameRequest) -> GameResponse:
        """处理统一请求，返回统一响应。"""
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
        # W4 修复：接入 GameplayService（scene_id 场景上下文），替换死代码路径
        scene_id = request.payload.get("scene_id", "LVL_001")
        result = self.gameplay.player_action(request.player_id, scene_id, action)
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
            if not isinstance(seed, int) or isinstance(seed, bool):
                return GameResponse.error(request.request_id, ERR_INVALID_REQUEST)
            if not isinstance(monster_hp, int) or isinstance(monster_hp, bool) \
               or monster_hp <= 0:
                return GameResponse.error(request.request_id, ERR_INVALID_REQUEST)
            # 服务端归一攻击/防御（可根据玩家等级/装备推导，此处简化为常量）
            session = self.combat.start_combat(
                player_id, seed, monster_hp,
                player_atk=100, monster_def=50,
            )
            return GameResponse.ok(request.request_id, {
                "combat_id": session.combat_id,
                "monster_hp": session.monster_hp,
            })
        elif action == "attack":
            combat_id = request.payload.get("combat_id", "")
            attack_power = request.payload.get("attack_power", None)
            result = self.combat.process_attack(combat_id, player_id, attack_power)
            # 战斗胜利后自动发放奖励到经济账户（W5 幂等：防重复领奖）
            if result.get("status") == "victory":
                if combat_id in self._rewarded_combats:
                    # 已发放过，返回但不再入账
                    pass
                else:
                    self._rewarded_combats.add(combat_id)
                    self._grant_combat_rewards(player_id, result.get("rewards", []))
            return GameResponse.ok(request.request_id, result)
        else:
            return GameResponse.error(request.request_id, ERR_INVALID_REQUEST)

    def _grant_combat_rewards(self, player_id: str, rewards: list) -> None:
        """发放战斗奖励（幂等，防重复领奖）"""
        for reward in rewards:
            item = reward.get("id", "")
            qty = reward.get("qty", 1)
            if not isinstance(qty, int) or qty <= 0:
                continue
            tx_id = uuid.uuid4().hex
            # 掉落表 id → 货币/背包映射（与中间件 loot 表对齐）
            mapping = {
                "coin": ("gold", "gold"),
                "gem": ("star_core", "star_core"),
                "ore": ("eroding_stone", "eroding_stone"),
                # potion / rune 发放到玩家背包（WorldState inventory）
                "potion": (None, "potion"),
                "rune": (None, "rune"),
            }
            if item not in mapping:
                continue
            currency, inv_key = mapping[item]
            if currency:
                self.economy.credit(player_id, currency, qty,
                                    reason="combat reward", tx_id=tx_id)
            else:
                # 发放到玩家背包
                inv = self.world.get_entity(f"player_{player_id}") or {"inventory": {}}
                inv = dict(inv)
                inv_inv = dict(inv.get("inventory", {}))
                inv_inv[inv_key] = inv_inv.get(inv_key, 0) + qty
                inv["inventory"] = inv_inv
                self.world.set_entity(f"player_{player_id}", inv)

    def _handle_quest(self, request: GameRequest) -> GameResponse:
        """处理任务更新（W3 修复：服务端单调校验，防刷完成）"""
        quest_id = request.payload.get("quest_id", "")
        progress = request.payload.get("progress", 0)
        player_id = request.player_id

        # DoS + W3 校验
        if not isinstance(quest_id, str) or not quest_id:
            return GameResponse.error(request.request_id, ERR_INVALID_REQUEST)
        if not isinstance(progress, int) or isinstance(progress, bool):
            return GameResponse.error(request.request_id, ERR_INVALID_REQUEST)
        if progress < 0 or progress > 100:
            return GameResponse.error(request.request_id, ERR_INVALID_REQUEST)

        # W3 修复：进度只增不减（单调），且以服务端已记录值为基准
        entity_key = f"quest_{player_id}"
        cur = self.world.get_entity(entity_key) or {"quest_id": quest_id, "progress": 0}
        prev_progress = cur.get("progress", 0) if cur.get("quest_id") == quest_id else 0
        # 单调校验：新进度必须 >= 旧进度，否则拒绝（防回退刷完成）
        if progress < prev_progress:
            return GameResponse.error(request.request_id, ERR_INVALID_REQUEST)

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

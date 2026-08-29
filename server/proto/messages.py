"""
messages.py - 多端统一通信协议

对齐 wp_server 设计文档中的 Protobuf 定义。
以 JSON 作为序列化载体，语义与 Protobuf GameRequest/GameResponse 完全一致。

协议覆盖：登录/玩法/战斗/任务/经济。
"""

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================
# 平台标识
# ============================================================
PLATFORMS = ("web", "cocos", "unity", "ue")

# 错误码
ERR_OK = 0
ERR_AUTH_FAILED = 1001
ERR_SESSION_EXPIRED = 1002
ERR_INVALID_REQUEST = 1003
ERR_ACTION_REJECTED = 2001
ERR_COMBAT_NOT_FOUND = 3001
ERR_ECONOMY_INSUFFICIENT = 4001

ERROR_MSG = {
    ERR_OK: "ok",
    ERR_AUTH_FAILED: "authentication failed",
    ERR_SESSION_EXPIRED: "session expired",
    ERR_INVALID_REQUEST: "invalid request",
    ERR_ACTION_REJECTED: "action rejected by server authority",
    ERR_COMBAT_NOT_FOUND: "combat session not found",
    ERR_ECONOMY_INSUFFICIENT: "insufficient funds",
}


# ============================================================
# 消息类型
# ============================================================
MSG_LOGIN = "login"
MSG_REFRESH = "refresh"
MSG_GAMEPLAY_ACTION = "gameplay_action"
MSG_GAMEPLAY_SNAPSHOT = "gameplay_snapshot"
MSG_COMBAT_RESULT = "combat_result"
MSG_QUEST_UPDATE = "quest_update"
MSG_ECONOMY_TRANSFER = "economy_transfer"


# ============================================================
# 核心数据模型（与 Protobuf 定义对齐）
# ============================================================
@dataclass
class PlayerData:
    """玩家数据（对齐 player_data 表结构）"""
    player_id: str
    level: int = 1
    exp: int = 0
    gold: int = 0
    star_core: int = 0
    eroding_stone: int = 0
    platform: str = "web"
    data_version: int = 1

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "level": self.level,
            "exp": self.exp,
            "gold": self.gold,
            "star_core": self.star_core,
            "eroding_stone": self.eroding_stone,
            "platform": self.platform,
            "data_version": self.data_version,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "PlayerData":
        return cls(
            player_id=d["player_id"],
            level=d.get("level", 1),
            exp=d.get("exp", 0),
            gold=d.get("gold", 0),
            star_core=d.get("star_core", 0),
            eroding_stone=d.get("eroding_stone", 0),
            platform=d.get("platform", "web"),
            data_version=d.get("data_version", 1),
        )


@dataclass
class GameRequest:
    """统一请求消息（对齐 GameRequest）"""
    request_id: str
    player_id: str
    client_version: int
    platform: str
    msg_type: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "player_id": self.player_id,
            "client_version": self.client_version,
            "platform": self.platform,
            "msg_type": self.msg_type,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "GameRequest":
        return cls(
            request_id=d["request_id"],
            player_id=d["player_id"],
            client_version=d.get("client_version", 1),
            platform=d.get("platform", "web"),
            msg_type=d["msg_type"],
            payload=d.get("payload", {}),
        )

    @classmethod
    def create(cls, player_id: str, msg_type: str,
               payload: Dict = None, platform: str = "web") -> "GameRequest":
        return cls(
            request_id=str(uuid.uuid4()),
            player_id=player_id,
            client_version=1,
            platform=platform,
            msg_type=msg_type,
            payload=payload or {},
        )


@dataclass
class GameResponse:
    """统一响应消息（对齐 GameResponse）"""
    request_id: str
    status: int = ERR_OK
    message: str = "ok"
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "message": self.message,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "GameResponse":
        return cls(
            request_id=d["request_id"],
            status=d.get("status", ERR_OK),
            message=d.get("message", "ok"),
            payload=d.get("payload", {}),
        )

    @classmethod
    def ok(cls, request_id: str, payload: Dict = None) -> "GameResponse":
        return cls(request_id=request_id, status=ERR_OK,
                   message="ok", payload=payload or {})

    @classmethod
    def error(cls, request_id: str, code: int) -> "GameResponse":
        return cls(request_id=request_id, status=code,
                   message=ERROR_MSG.get(code, "unknown error"))


# ============================================================
# 序列化辅助
# ============================================================
def serialize(msg: Any) -> str:
    """将消息序列化为 JSON 字符串"""
    import json
    return json.dumps(msg.to_dict())


def deserialize(data: str, msg_cls) -> Any:
    """将 JSON 字符串反序列化为消息"""
    import json
    d = json.loads(data)
    return msg_cls.from_dict(d)

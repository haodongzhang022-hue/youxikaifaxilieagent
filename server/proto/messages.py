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


# ============================================================
# M-A 协议冻结 · 发布转化协议 (Issue #135 / WP-02)
# 里程碑: M-A（MVP 首开发里程碑）
# ============================================================

# 播放状态机（对齐 WP-01 三态状态机）
PLAY_STATE_UNKNOWN = 0
PLAY_STATE_LOCAL_LITE = 1    # 本地轻量版
PLAY_STATE_CG_ANCHOR = 2     # CG 锚点播放
PLAY_STATE_CLOUD_PLAY = 3    # 云会话中
PLAY_STATE_LOCAL_FULL = 4    # 本地完整版


class PlayState:
    """播放状态枚举（对齐 protocol.proto PlayState）"""
    UNKNOWN = PLAY_STATE_UNKNOWN
    LOCAL_LITE = PLAY_STATE_LOCAL_LITE
    CG_ANCHOR = PLAY_STATE_CG_ANCHOR
    CLOUD_PLAY = PLAY_STATE_CLOUD_PLAY
    LOCAL_FULL = PLAY_STATE_LOCAL_FULL

    # 状态机合法流转（本地轻量 -> CG锚点 -> 云 -> 本地完整）
    TRANSITIONS = {
        LOCAL_LITE: frozenset({CG_ANCHOR}),          # 点击增强 -> CG
        CG_ANCHOR: frozenset({CLOUD_PLAY, LOCAL_FULL}),  # 云就绪/用户跳过
        CLOUD_PLAY: frozenset({LOCAL_FULL, LOCAL_LITE}), # 下载接管/断网回退
        LOCAL_FULL: frozenset(),                     # 终态
    }

    @classmethod
    def can_transition(cls, src: int, dst: int) -> bool:
        """判断状态机流转是否合法"""
        return dst in cls.TRANSITIONS.get(src, frozenset())

    @classmethod
    def to_str(cls, state: int) -> str:
        names = {
            cls.UNKNOWN: "UNKNOWN",
            cls.LOCAL_LITE: "LOCAL_LITE",
            cls.CG_ANCHOR: "CG_ANCHOR",
            cls.CLOUD_PLAY: "CLOUD_PLAY",
            cls.LOCAL_FULL: "LOCAL_FULL",
        }
        return names.get(state, "UNKNOWN")


# 会话超时策略
TIMEOUT_UNKNOWN = 0
TIMEOUT_DEFAULT = 1
TIMEOUT_PRE_RELEASE = 2
TIMEOUT_USER_EXIT = 3


class TimeoutPolicy:
    """会话超时策略枚举"""
    UNKNOWN = TIMEOUT_UNKNOWN
    DEFAULT = TIMEOUT_DEFAULT
    PRE_RELEASE = TIMEOUT_PRE_RELEASE
    USER_EXIT = TIMEOUT_USER_EXIT


# 增强请求类型
ENHANCE_UNKNOWN = 0
ENHANCE_CG_PLAY = 1
ENHANCE_CLOUD_UPGRADE = 2


class EnhancementType:
    """增强请求类型枚举"""
    UNKNOWN = ENHANCE_UNKNOWN
    CG_PLAY = ENHANCE_CG_PLAY
    CLOUD_UPGRADE = ENHANCE_CLOUD_UPGRADE


# ============================================================
# 存档同步协议 (SaveSync)
# ============================================================

@dataclass
class SaveSyncPush:
    """存档推送（云端/本地切换时上传存档）"""
    player_id: str
    progress_checkpoint: str = ""
    platform: str = "web"
    data_version: int = 1
    session_token: str = ""

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "progress_checkpoint": self.progress_checkpoint,
            "platform": self.platform,
            "data_version": self.data_version,
            "session_token": self.session_token,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "SaveSyncPush":
        return cls(
            player_id=d["player_id"],
            progress_checkpoint=d.get("progress_checkpoint", ""),
            platform=d.get("platform", "web"),
            data_version=d.get("data_version", 1),
            session_token=d.get("session_token", ""),
        )

    @classmethod
    def create(cls, player_id: str, progress_checkpoint: str,
               platform: str = "web", data_version: int = 1,
               session_token: str = "") -> "SaveSyncPush":
        return cls(
            player_id=player_id,
            progress_checkpoint=progress_checkpoint,
            platform=platform,
            data_version=data_version,
            session_token=session_token,
        )


@dataclass
class SaveSyncPull:
    """存档拉取（切换后从目标端拉回同 checkpoint 续玩）"""
    player_id: str
    progress_checkpoint: str = ""
    platform: str = "web"
    data_version: int = 1
    session_token: str = ""

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "progress_checkpoint": self.progress_checkpoint,
            "platform": self.platform,
            "data_version": self.data_version,
            "session_token": self.session_token,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "SaveSyncPull":
        return cls(
            player_id=d["player_id"],
            progress_checkpoint=d.get("progress_checkpoint", ""),
            platform=d.get("platform", "web"),
            data_version=d.get("data_version", 1),
            session_token=d.get("session_token", ""),
        )

    @classmethod
    def create(cls, player_id: str, progress_checkpoint: str,
               platform: str = "web", data_version: int = 1,
               session_token: str = "") -> "SaveSyncPull":
        return cls(
            player_id=player_id,
            progress_checkpoint=progress_checkpoint,
            platform=platform,
            data_version=data_version,
            session_token=session_token,
        )


# ============================================================
# 云会话协议 (CloudSession)
# ============================================================

@dataclass
class CloudSessionApply:
    """云会话申请"""
    player_id: str
    session_id: str = ""
    from_state: int = PLAY_STATE_LOCAL_LITE
    bandwidth_budget: int = 0
    session_token: str = ""

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "session_id": self.session_id,
            "from_state": self.from_state,
            "bandwidth_budget": self.bandwidth_budget,
            "session_token": self.session_token,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "CloudSessionApply":
        return cls(
            player_id=d["player_id"],
            session_id=d.get("session_id", ""),
            from_state=d.get("from_state", PLAY_STATE_LOCAL_LITE),
            bandwidth_budget=d.get("bandwidth_budget", 0),
            session_token=d.get("session_token", ""),
        )

    @classmethod
    def create(cls, player_id: str, session_id: str = "",
               from_state: int = PLAY_STATE_LOCAL_LITE,
               bandwidth_budget: int = 0,
               session_token: str = "") -> "CloudSessionApply":
        return cls(
            player_id=player_id,
            session_id=session_id or str(uuid.uuid4()),
            from_state=from_state,
            bandwidth_budget=bandwidth_budget,
            session_token=session_token,
        )


@dataclass
class CloudSessionPrewarm:
    """云会话预热（CG 播放期后台静默申请）"""
    player_id: str
    play_stage: str = ""
    expected_duration: int = 0
    session_token: str = ""

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "play_stage": self.play_stage,
            "expected_duration": self.expected_duration,
            "session_token": self.session_token,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "CloudSessionPrewarm":
        return cls(
            player_id=d["player_id"],
            play_stage=d.get("play_stage", ""),
            expected_duration=d.get("expected_duration", 0),
            session_token=d.get("session_token", ""),
        )

    @classmethod
    def create(cls, player_id: str, play_stage: str = "",
               expected_duration: int = 0,
               session_token: str = "") -> "CloudSessionPrewarm":
        return cls(
            player_id=player_id,
            play_stage=play_stage,
            expected_duration=expected_duration,
            session_token=session_token,
        )


@dataclass
class CloudSessionHeartbeat:
    """云会话心跳（保活防僵尸会话）"""
    player_id: str
    session_id: str = ""
    sequence: int = 0
    session_token: str = ""

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "session_token": self.session_token,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "CloudSessionHeartbeat":
        return cls(
            player_id=d["player_id"],
            session_id=d.get("session_id", ""),
            sequence=d.get("sequence", 0),
            session_token=d.get("session_token", ""),
        )

    @classmethod
    def create(cls, player_id: str, session_id: str = "",
               sequence: int = 0,
               session_token: str = "") -> "CloudSessionHeartbeat":
        return cls(
            player_id=player_id,
            session_id=session_id,
            sequence=sequence,
            session_token=session_token,
        )


@dataclass
class CloudSessionRelease:
    """云会话释放（超时/退出/下载90%+预释放）"""
    player_id: str
    session_id: str = ""
    timeout_policy: int = TIMEOUT_DEFAULT
    target_state: int = PLAY_STATE_LOCAL_FULL
    session_token: str = ""

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "session_id": self.session_id,
            "timeout_policy": self.timeout_policy,
            "target_state": self.target_state,
            "session_token": self.session_token,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "CloudSessionRelease":
        return cls(
            player_id=d["player_id"],
            session_id=d.get("session_id", ""),
            timeout_policy=d.get("timeout_policy", TIMEOUT_DEFAULT),
            target_state=d.get("target_state", PLAY_STATE_LOCAL_FULL),
            session_token=d.get("session_token", ""),
        )

    @classmethod
    def create(cls, player_id: str, session_id: str = "",
               timeout_policy: int = TIMEOUT_DEFAULT,
               target_state: int = PLAY_STATE_LOCAL_FULL,
               session_token: str = "") -> "CloudSessionRelease":
        return cls(
            player_id=player_id,
            session_id=session_id,
            timeout_policy=timeout_policy,
            target_state=target_state,
            session_token=session_token,
        )


# ============================================================
# 下载状态协议 (DownloadStatus)
# ============================================================

@dataclass
class DownloadStatusReport:
    """下载状态上报"""
    player_id: str
    download_id: str = ""
    bytes_done: int = 0
    bytes_total: int = 0
    resume_point: int = 0
    bandwidth_budget: int = 100
    session_token: str = ""

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "download_id": self.download_id,
            "bytes_done": self.bytes_done,
            "bytes_total": self.bytes_total,
            "resume_point": self.resume_point,
            "bandwidth_budget": self.bandwidth_budget,
            "session_token": self.session_token,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "DownloadStatusReport":
        return cls(
            player_id=d["player_id"],
            download_id=d.get("download_id", ""),
            bytes_done=d.get("bytes_done", 0),
            bytes_total=d.get("bytes_total", 0),
            resume_point=d.get("resume_point", 0),
            bandwidth_budget=d.get("bandwidth_budget", 100),
            session_token=d.get("session_token", ""),
        )

    @classmethod
    def create(cls, player_id: str, download_id: str = "",
               bytes_done: int = 0, bytes_total: int = 0,
               resume_point: int = 0, bandwidth_budget: int = 100,
               session_token: str = "") -> "DownloadStatusReport":
        return cls(
            player_id=player_id,
            download_id=download_id or str(uuid.uuid4()),
            bytes_done=bytes_done,
            bytes_total=bytes_total,
            resume_point=resume_point,
            bandwidth_budget=bandwidth_budget,
            session_token=session_token,
        )


@dataclass
class DownloadChunkComplete:
    """分片完成上报"""
    player_id: str
    download_id: str = ""
    chunk_index: int = 0
    bytes_done: int = 0
    pre_release_signal: bool = False
    session_token: str = ""

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "download_id": self.download_id,
            "chunk_index": self.chunk_index,
            "bytes_done": self.bytes_done,
            "pre_release_signal": self.pre_release_signal,
            "session_token": self.session_token,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "DownloadChunkComplete":
        return cls(
            player_id=d["player_id"],
            download_id=d.get("download_id", ""),
            chunk_index=d.get("chunk_index", 0),
            bytes_done=d.get("bytes_done", 0),
            pre_release_signal=d.get("pre_release_signal", False),
            session_token=d.get("session_token", ""),
        )

    @classmethod
    def create(cls, player_id: str, download_id: str = "",
               chunk_index: int = 0, bytes_done: int = 0,
               pre_release_signal: bool = False,
               session_token: str = "") -> "DownloadChunkComplete":
        return cls(
            player_id=player_id,
            download_id=download_id,
            chunk_index=chunk_index,
            bytes_done=bytes_done,
            pre_release_signal=pre_release_signal,
            session_token=session_token,
        )


# ============================================================
# 增强入口协议 (EnhancementRequest)
# ============================================================

@dataclass
class EnhancementRequest:
    """增强画质请求（点击「增强画质」跳云）"""
    player_id: str
    from_state: int = PLAY_STATE_LOCAL_LITE
    target_stage: int = PLAY_STATE_CG_ANCHOR
    request_type: int = ENHANCE_CG_PLAY
    session_token: str = ""

    def to_dict(self) -> Dict:
        return {
            "player_id": self.player_id,
            "from_state": self.from_state,
            "target_stage": self.target_stage,
            "request_type": self.request_type,
            "session_token": self.session_token,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "EnhancementRequest":
        return cls(
            player_id=d["player_id"],
            from_state=d.get("from_state", PLAY_STATE_LOCAL_LITE),
            target_stage=d.get("target_stage", PLAY_STATE_CG_ANCHOR),
            request_type=d.get("request_type", ENHANCE_CG_PLAY),
            session_token=d.get("session_token", ""),
        )

    @classmethod
    def create(cls, player_id: str,
               from_state: int = PLAY_STATE_LOCAL_LITE,
               target_stage: int = PLAY_STATE_CG_ANCHOR,
               request_type: int = ENHANCE_CG_PLAY,
               session_token: str = "") -> "EnhancementRequest":
        return cls(
            player_id=player_id,
            from_state=from_state,
            target_stage=target_stage,
            request_type=request_type,
            session_token=session_token,
        )

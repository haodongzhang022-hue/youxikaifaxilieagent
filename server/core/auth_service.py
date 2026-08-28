"""
auth_service.py - 账号服务

支持 4 平台（web/cocos/unity/ue）登录 + 会话管理 + 多端绑定。
服务端权威认证，客户端只持有会话 Token。
"""

import hashlib
import secrets
import time
from typing import Dict, Optional

from server.proto.messages import (
    PlayerData, ERR_AUTH_FAILED, ERR_SESSION_EXPIRED,
)


class AuthService:
    """账号服务：多端登录 / 会话管理 / 多端绑定"""

    SESSION_TTL_SEC = 3600 * 24 * 7  # 7 天会话有效期

    def __init__(self):
        self._players: Dict[str, PlayerData] = {}
        self._sessions: Dict[str, Dict] = {}       # token -> session data
        self._platform_bindings: Dict[str, str] = {}  # "platform:device_id" -> player_id

    # ============================================================
    # 登录
    # ============================================================
    def login(self, platform: str, token: str,
              device_id: str) -> tuple[bool, Optional[Dict]]:
        """
        多端登录。返回 (success, {session_token, player, is_new_player})。
        """
        if platform not in ("web", "cocos", "unity", "ue"):
            return False, None

        # 模拟平台 token 校验
        if not token or len(token) < 8:
            return False, None

        # 查找或创建玩家
        binding_key = f"{platform}:{device_id}"
        player_id = self._platform_bindings.get(binding_key)
        is_new = False
        if player_id is None:
            player_id = self._generate_player_id(platform, device_id)
            self._players[player_id] = PlayerData(
                player_id=player_id,
                platform=platform,
            )
            self._platform_bindings[binding_key] = player_id
            is_new = True

        # 签发会话
        session_token = self._issue_session(player_id, platform)
        player = self._players[player_id]

        return True, {
            "session_token": session_token,
            "player": player.to_dict(),
            "is_new_player": is_new,
        }

    def refresh_session(self, session_token: str) -> tuple[bool, Optional[str]]:
        """续期会话。返回 (success, new_token)。"""
        session = self._sessions.get(session_token)
        if not session:
            return False, None
        if time.time() > session["expires_at"]:
            del self._sessions[session_token]
            return False, None
        # 签发新 token
        new_token = self._issue_session(session["player_id"], session["platform"])
        del self._sessions[session_token]
        return True, new_token

    def bind_platform(self, session_token: str, platform: str,
                      device_id: str) -> bool:
        """多端绑定：将另一平台设备绑定到当前账号。"""
        session = self._sessions.get(session_token)
        if not session or time.time() > session["expires_at"]:
            return False
        player_id = session["player_id"]
        self._platform_bindings[f"{platform}:{device_id}"] = player_id
        # 更新玩家平台标记
        player = self._players[player_id]
        player.platform = platform
        return True

    def get_player(self, player_id: str) -> Optional[PlayerData]:
        return self._players.get(player_id)

    def verify_session(self, session_token: str) -> Optional[str]:
        """验证会话。返回 player_id 或 None。"""
        session = self._sessions.get(session_token)
        if not session:
            return None
        if time.time() > session["expires_at"]:
            del self._sessions[session_token]
            return None
        return session["player_id"]

    # ============================================================
    # 内部方法
    # ============================================================
    def _issue_session(self, player_id: str, platform: str) -> str:
        token = secrets.token_hex(32)
        self._sessions[token] = {
            "player_id": player_id,
            "platform": platform,
            "expires_at": time.time() + self.SESSION_TTL_SEC,
        }
        return token

    def _generate_player_id(self, platform: str, device_id: str) -> str:
        h = hashlib.sha256(f"{platform}:{device_id}".encode()).hexdigest()[:16]
        return f"P_{h}"

    def logout(self, session_token: str) -> bool:
        if session_token in self._sessions:
            del self._sessions[session_token]
            return True
        return False

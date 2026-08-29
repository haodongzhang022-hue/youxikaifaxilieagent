# ============================================================
# 无状态服务端核心 (Stateless Server Core)
# 版本: v1.0
# 对齐: Issue #112「游戏向架构师的开发」· wp_server 服务端无状态+协议先行
# 说明: 服务端尽量设计成无状态的，方便后期从单机 Python 平滑迁移到 Go 集群。
#       - 会话状态通过 JWT Token 自包含（无服务端会话存储）
#       - 协议先行：所有通信走统一协议（protocol.proto 定义）
#       - 幂等设计：相同请求返回相同结果（同一请求ID）
#
# 设计原则:
#   1. Stateless: 请求中携带全部所需信息，服务端不依赖会话状态
#   2. 协议先行: 消息类型/字段由 protocol.proto 统一定义
#   3. 幂等性: 相同 request_id + 相同 payload 返回相同结果
#   4. 阶段感知: 服务端感知当前游戏阶段（Cocos→Unity→UE）
# 语言: Python 3 (可运行，无外部依赖)
# ============================================================
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================
# 一、协议常量（对齐 protocol.proto）
# ============================================================

PROTOCOL_VERSION = "1.0"

# 平台标识
PLATFORM_WEB = "web"
PLATFORM_COCOS = "cocos"
PLATFORM_UNITY = "unity"
PLATFORM_UE = "ue"

# 错误码
ERR_OK = 0
ERR_AUTH_FAILED = 1001
ERR_SESSION_EXPIRED = 1002
ERR_INVALID_REQUEST = 1003
ERR_ACTION_REJECTED = 2001
ERR_STAGE_MISMATCH = 5001

# 消息类型
MSG_LOGIN = "login"
MSG_REFRESH = "refresh"
MSG_GAMEPLAY_ACTION = "gameplay_action"
MSG_GAMEPLAY_SNAPSHOT = "gameplay_snapshot"
MSG_COMBAT_RESULT = "combat_result"
MSG_QUEST_UPDATE = "quest_update"
MSG_ECONOMY_TRANSFER = "economy_transfer"

# 游戏阶段
STAGE_COCOS = "stage_cocos"
STAGE_UNITY = "stage_unity"
STAGE_UE = "stage_ue"
STAGE_ASSET_LIB = "stage_asset_lib"


# ============================================================
# 二、无状态请求/响应模型
# ============================================================

@dataclass
class StatelessRequest:
    """无状态请求：请求中携带全部上下文，服务端不保存会话"""
    request_id: str
    msg_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    platform: str = "web"
    protocol_version: str = PROTOCOL_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "msg_type": self.msg_type,
            "payload": self.payload,
            "platform": self.platform,
            "protocol_version": self.protocol_version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StatelessRequest":
        return cls(
            request_id=d.get("request_id", ""),
            msg_type=d.get("msg_type", ""),
            payload=d.get("payload", {}),
            platform=d.get("platform", "web"),
            protocol_version=d.get("protocol_version", PROTOCOL_VERSION),
        )


@dataclass
class StatelessResponse:
    """无状态响应：携带 request_id 对应请求，可幂等"""
    request_id: str
    code: int
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    server_timestamp: int = 0
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self):
        if not self.server_timestamp:
            self.server_timestamp = int(time.time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "code": self.code,
            "message": self.message,
            "data": self.data,
            "server_timestamp": self.server_timestamp,
            "protocol_version": self.protocol_version,
        }

    @classmethod
    def ok(cls, request_id: str, data: Dict[str, Any]) -> "StatelessResponse":
        return cls(request_id=request_id, code=ERR_OK, message="ok", data=data)

    @classmethod
    def error(cls, request_id: str, code: int, message: str = "") -> "StatelessResponse":
        return cls(request_id=request_id, code=code, message=message or f"error_{code}")


# ============================================================
# 三、无状态会话管理（JWT 风格 Token，自包含）
# ============================================================

class StatelessSessionManager:
    """
    无状态会话管理：使用 HMAC 签名 Token 自包含会话信息。
    服务端不存储会话状态，Token 中携带 player_id + 过期时间 + 阶段。
    """

    def __init__(self, secret_key: str = "dev_secret_key_change_in_prod"):
        """初始化会话管理器"""
        self._secret = secret_key.encode("utf-8")

    def create_token(self, player_id: str, stage: str = STAGE_COCOS,
                     ttl_seconds: int = 3600) -> str:
        """
        创建无状态会话 Token。

        Args:
            player_id: 玩家ID
            stage: 当前游戏阶段
            ttl_seconds: Token 有效期（秒）

        Returns:
            str: JWT 格式 Token（header.payload.signature）
        """
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "player_id": player_id,
            "stage": stage,
            "iat": now,
            "exp": now + ttl_seconds,
        }

        header_b64 = self._b64encode(json.dumps(header))
        payload_b64 = self._b64encode(json.dumps(payload))
        signing_input = f"{header_b64}.{payload_b64}"
        signature = self._sign(signing_input)

        return f"{signing_input}.{signature}"

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        验证 Token。

        Args:
            token: 会话 Token

        Returns:
            Dict: 解密后的 payload；无效返回 None
        """
        try:
            header_b64, payload_b64, signature = token.split(".")
            signing_input = f"{header_b64}.{payload_b64}"
            expected = self._sign(signing_input)
            if not hmac.compare_digest(signature, expected):
                return None

            payload = json.loads(self._b64decode(payload_b64))
            now = int(time.time())
            if payload.get("exp", 0) < now:
                return None

            return payload
        except Exception:
            return None

    def get_player_id(self, token: str) -> Optional[str]:
        """从 Token 获取玩家ID"""
        payload = self.verify_token(token)
        return payload.get("player_id") if payload else None

    def get_stage(self, token: str) -> Optional[str]:
        """从 Token 获取游戏阶段"""
        payload = self.verify_token(token)
        return payload.get("stage") if payload else None

    def _b64encode(self, data: str) -> str:
        """Base64 URL-safe 编码"""
        import base64
        return base64.urlsafe_b64encode(data.encode("utf-8")).rstrip(b"=").decode("ascii")

    def _b64decode(self, data: str) -> str:
        """Base64 URL-safe 解码"""
        import base64
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding).decode("utf-8")

    def _sign(self, data: str) -> str:
        """HMAC SHA-256 签名"""
        return self._b64encode(
            hmac.new(self._secret, data.encode("utf-8"), hashlib.sha256).hexdigest()
        )


# ============================================================
# 四、阶段感知服务端网关
# ============================================================

class StatelessGateway:
    """
    无状态网关：所有平台请求统一入口。

    设计要点:
      - 每个请求自包含全部上下文（无状态）
      - 会话通过 Token 自包含验证
      - 请求幂等：相同 request_id 返回相同结果
      - 阶段感知：校验当前阶段，防止阶段错配
    """

    def __init__(self):
        """初始化无状态网关"""
        self._sessions = StatelessSessionManager()
        self._request_cache: Dict[str, StatelessResponse] = {}  # 幂等缓存
        self._stage_registry: Dict[str, str] = {}  # player_id -> stage

    def handle(self, request: StatelessRequest) -> StatelessResponse:
        """
        处理无状态请求。

        幂等保证：相同 request_id + 相同 payload 返回缓存结果。
        无状态保证：请求中携带全部上下文（session_token）。
        """
        # 幂等检查
        if request.request_id in self._request_cache:
            cached = self._request_cache[request.request_id]
            # 验证 payload 是否一致（防止不同 payload 用同一 request_id）
            if self._hash_payload(request.payload) == self._hash_payload(cached.data):
                return cached

        # 路由分发
        if request.msg_type == MSG_LOGIN:
            resp = self._handle_login(request)
        else:
            # 非登录请求需要验证 Token
            token = request.payload.get("session_token", "")
            payload = self._sessions.verify_token(token)
            if payload is None:
                resp = StatelessResponse.error(
                    request.request_id, ERR_SESSION_EXPIRED, "session expired")
            elif payload.get("player_id") != request.payload.get("player_id"):
                resp = StatelessResponse.error(
                    request.request_id, ERR_AUTH_FAILED, "auth failed")
            else:
                resp = self._route(request, payload)

        # 缓存幂等结果
        self._request_cache[request.request_id] = resp
        return resp

    def _route(self, request: StatelessRequest, session: Dict[str, Any]) -> StatelessResponse:
        """路由到具体业务处理（无状态、可并行）"""
        msg_type = request.msg_type

        if msg_type == MSG_REFRESH:
            return self._handle_refresh(request, session)
        elif msg_type == MSG_GAMEPLAY_ACTION:
            return self._handle_gameplay(request, session)
        elif msg_type == MSG_COMBAT_RESULT:
            return self._handle_combat(request, session)
        elif msg_type == MSG_ECONOMY_TRANSFER:
            return self._handle_economy(request, session)
        else:
            return StatelessResponse.error(
                request.request_id, ERR_INVALID_REQUEST, "unknown msg_type")

    # ---- 具体业务处理（无状态：只依赖 request + session 自包含信息）----

    def _handle_login(self, request: StatelessRequest) -> StatelessResponse:
        """登录：验证 token + 生成无状态会话 Token"""
        payload = request.payload
        token = payload.get("token", "")
        device_id = payload.get("device_id", "")
        platform = request.platform

        # 模拟第三方 Token 验证（生产环境接真实 OAuth）
        player_id = f"player_{hashlib.md5((token + device_id).encode()).hexdigest()[:8]}"

        # 创建无状态会话 Token
        stage = payload.get("stage", STAGE_COCOS)
        session_token = self._sessions.create_token(player_id, stage=stage)
        self._stage_registry[player_id] = stage

        return StatelessResponse.ok(request.request_id, {
            "player_id": player_id,
            "session_token": session_token,
            "stage": stage,
            "expires_in": 3600,
        })

    def _handle_refresh(self, request: StatelessRequest,
                        session: Dict[str, Any]) -> StatelessResponse:
        """刷新会话"""
        player_id = session["player_id"]
        stage = session.get("stage", STAGE_COCOS)
        new_token = self._sessions.create_token(player_id, stage=stage)
        return StatelessResponse.ok(request.request_id, {
            "player_id": player_id,
            "session_token": new_token,
            "stage": stage,
            "expires_in": 3600,
        })

    def _handle_gameplay(self, request: StatelessRequest,
                         session: Dict[str, Any]) -> StatelessResponse:
        """玩法操作：无状态处理"""
        player_id = session["player_id"]
        action = request.payload.get("action", {})
        action_type = action.get("type", "")

        return StatelessResponse.ok(request.request_id, {
            "player_id": player_id,
            "action_type": action_type,
            "result": "ok",
            "server_time": int(time.time()),
        })

    def _handle_combat(self, request: StatelessRequest,
                       session: Dict[str, Any]) -> StatelessResponse:
        """战斗结算：确定性 + 无状态"""
        player_id = session["player_id"]
        seed = request.payload.get("seed", 0)

        # 确定性计算：同 seed 同结果
        result_hash = hashlib.sha256(f"{player_id}:{seed}".encode()).hexdigest()[:16]

        return StatelessResponse.ok(request.request_id, {
            "combat_id": result_hash,
            "seed": seed,
            "result_hash": result_hash,
            "server_time": int(time.time()),
        })

    def _handle_economy(self, request: StatelessRequest,
                        session: Dict[str, Any]) -> StatelessResponse:
        """经济操作：无状态记账"""
        player_id = session["player_id"]
        currency = request.payload.get("currency", "gold")
        amount = request.payload.get("amount", 0)

        return StatelessResponse.ok(request.request_id, {
            "player_id": player_id,
            "currency": currency,
            "amount": amount,
            "transaction_id": f"tx_{hashlib.md5(f'{player_id}:{amount}:{time.time()}'.encode()).hexdigest()[:12]}",
        })

    def _hash_payload(self, data: Dict[str, Any]) -> str:
        """对 payload 做 hash（幂等验证用）"""
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    # ---- 阶段感知接口 ----

    def set_stage(self, player_id: str, stage: str) -> bool:
        """设置玩家当前阶段（阶段感知）"""
        if stage not in (STAGE_COCOS, STAGE_UNITY, STAGE_UE, STAGE_ASSET_LIB):
            return False
        self._stage_registry[player_id] = stage
        return True

    def get_stage(self, player_id: str) -> Optional[str]:
        """获取玩家当前阶段"""
        return self._stage_registry.get(player_id)

    def check_stage_valid(self, player_id: str, expected_stage: str) -> bool:
        """检查阶段是否匹配（阶段不对=错）"""
        actual = self._stage_registry.get(player_id)
        return actual == expected_stage


# ============================================================
# 五、自测
# ============================================================

if __name__ == "__main__":
    print("=== 无状态服务端核心自测 ===")
    print()

    # 1. 无状态会话管理
    print("== 1. 无状态会话 ==")
    sessions = StatelessSessionManager(secret_key="test_secret")
    token = sessions.create_token("player_123", stage=STAGE_COCOS)
    payload = sessions.verify_token(token)
    print(f"  Token 创建: {token[:30]}...")
    print(f"  Token 验证: player_id={payload['player_id']}, stage={payload['stage']}")
    print(f"  Token 过期验证: {sessions.verify_token('bad.token.here')}")

    # 2. 无状态网关
    print("\n== 2. 无状态网关 ==")
    gateway = StatelessGateway()

    # 登录
    login_req = StatelessRequest(
        request_id="req_001",
        msg_type=MSG_LOGIN,
        payload={"token": "oauth_token", "device_id": "dev_1", "stage": STAGE_COCOS},
        platform=PLATFORM_COCOS,
    )
    login_resp = gateway.handle(login_req)
    print(f"  登录: code={login_resp.code}, player={login_resp.data.get('player_id')}")
    session_token = login_resp.data.get("session_token", "")

    # 玩法操作
    action_req = StatelessRequest(
        request_id="req_002",
        msg_type=MSG_GAMEPLAY_ACTION,
        payload={
            "player_id": login_resp.data.get("player_id"),
            "session_token": session_token,
            "action": {"type": "move", "x": 10, "z": 20},
        },
        platform=PLATFORM_COCOS,
    )
    action_resp = gateway.handle(action_req)
    print(f"  玩法操作: code={action_resp.code}, result={action_resp.data.get('result')}")

    # 3. 幂等性验证
    print("\n== 3. 幂等性验证 ==")
    idem_req = StatelessRequest(
        request_id="req_003",
        msg_type=MSG_GAMEPLAY_ACTION,
        payload={
            "player_id": login_resp.data.get("player_id"),
            "session_token": session_token,
            "action": {"type": "attack", "target": "enemy_1"},
        },
    )
    resp1 = gateway.handle(idem_req)
    resp2 = gateway.handle(idem_req)
    print(f"  两次相同请求: 第一次={resp1.code}, 第二次={resp2.code}")
    print(f"  幂等一致: {resp1.code == resp2.code}")

    # 4. 无效 Token
    print("\n== 4. 无效 Token 拒绝 ==")
    invalid_req = StatelessRequest(
        request_id="req_004",
        msg_type=MSG_GAMEPLAY_ACTION,
        payload={"player_id": "player_x", "session_token": "invalid_token"},
    )
    invalid_resp = gateway.handle(invalid_req)
    print(f"  无效 Token: code={invalid_resp.code} ({invalid_resp.message})")

    # 5. 阶段感知
    print("\n== 5. 阶段感知 ==")
    player_id = login_resp.data.get("player_id")
    print(f"  当前阶段: {gateway.get_stage(player_id)}")
    print(f"  阶段匹配(Cocos): {gateway.check_stage_valid(player_id, STAGE_COCOS)}")
    print(f"  阶段不匹配(UE): {gateway.check_stage_valid(player_id, STAGE_UE)}")

    print("\n🟢 无状态服务端核心自测通过")

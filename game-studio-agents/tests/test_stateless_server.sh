#!/usr/bin/env bash
# ============================================================
# 无状态服务端核心测试信号灯（stateless_server + protocol_tools）
# 说明: 验证 Issue #112「游戏向架构师的开发」wp_server——
#       1. 无状态会话管理（JWT 风格 Token）
#       2. 无状态网关（请求自包含上下文）
#       3. 幂等性保证（相同请求返回相同结果）
#       4. 协议生成工具链（proto → 多语言代码）
# 退出码: 0 = 🟢 通过，1 = 🔴 阻塞
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/../.."
PY=python3
pass=0
fail=0

report() {
  if [ "$2" = "0" ]; then
    echo "  ✅ $1"
    pass=$((pass+1))
  else
    echo "  ❌ $1"
    fail=$((fail+1))
  fi
}

echo "== 1. 无状态服务端核心 =="
out=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'server')
from server.core.stateless_server import (
    StatelessSessionManager, StatelessGateway, StatelessRequest,
    PLATFORM_COCOS, STAGE_COCOS, STAGE_UNITY,
    MSG_LOGIN, MSG_GAMEPLAY_ACTION,
)

# 1. 无状态会话
sessions = StatelessSessionManager(secret_key="test")
token = sessions.create_token("player_1", stage=STAGE_COCOS)
payload = sessions.verify_token(token)
print(f"TOKEN_VALID={payload is not None}")
print(f"TOKEN_PLAYER={payload.get('player_id') if payload else 'None'}")
print(f"TOKEN_STAGE={payload.get('stage') if payload else 'None'}")

# 无效 token
bad = sessions.verify_token("invalid.token.here")
print(f"BAD_TOKEN={bad is None}")

# 2. 无状态网关
gateway = StatelessGateway()
login_req = StatelessRequest(
    request_id="req1", msg_type=MSG_LOGIN,
    payload={"token": "oauth", "device_id": "dev1", "stage": STAGE_COCOS},
    platform=PLATFORM_COCOS,
)
login_resp = gateway.handle(login_req)
print(f"LOGIN_CODE={login_resp.code}")
print(f"LOGIN_HAS_TOKEN={'session_token' in login_resp.data}")
session_token = login_resp.data.get("session_token", "")
player_id = login_resp.data.get("player_id", "")

# 3. 玩法操作
action_req = StatelessRequest(
    request_id="req2", msg_type=MSG_GAMEPLAY_ACTION,
    payload={"player_id": player_id, "session_token": session_token,
             "action": {"type": "move"}},
)
action_resp = gateway.handle(action_req)
print(f"ACTION_CODE={action_resp.code}")

# 4. 幂等性
idem_req = StatelessRequest(
    request_id="req3", msg_type=MSG_GAMEPLAY_ACTION,
    payload={"player_id": player_id, "session_token": session_token,
             "action": {"type": "attack"}},
)
resp1 = gateway.handle(idem_req)
resp2 = gateway.handle(idem_req)
print(f"IDEMPOTENT={resp1.code == resp2.code}")

# 5. 无效 Token
invalid_req = StatelessRequest(
    request_id="req4", msg_type=MSG_GAMEPLAY_ACTION,
    payload={"player_id": "x", "session_token": "invalid"},
)
invalid_resp = gateway.handle(invalid_req)
print(f"INVALID_TOKEN_CODE={invalid_resp.code}")

# 6. 阶段感知
print(f"STAGE_COCOS={gateway.get_stage(player_id)}")
print(f"STAGE_MATCH={gateway.check_stage_valid(player_id, STAGE_COCOS)}")
print(f"STAGE_UNMATCH={gateway.check_stage_valid(player_id, STAGE_UNITY)}")
PYEOF
)

# 1. Token 验证
if echo "$out" | grep -q "TOKEN_VALID=True"; then
  report "无状态 Token 创建与验证" 0
else
  report "无状态 Token 创建与验证" 1
fi

# 2. Token 携带玩家信息
if echo "$out" | grep -q "TOKEN_PLAYER=player_1" && echo "$out" | grep -q "TOKEN_STAGE=stage_cocos"; then
  report "Token 自包含玩家/阶段信息" 0
else
  report "Token 自包含玩家/阶段信息" 1
fi

# 3. 无效 Token 拒绝
if echo "$out" | grep -q "BAD_TOKEN=True"; then
  report "无效 Token 拒绝" 0
else
  report "无效 Token 拒绝" 1
fi

# 4. 登录成功
if echo "$out" | grep -q "LOGIN_CODE=0" && echo "$out" | grep -q "LOGIN_HAS_TOKEN=True"; then
  report "无状态登录返回 Token" 0
else
  report "无状态登录返回 Token" 1
fi

# 5. 玩法操作
if echo "$out" | grep -q "ACTION_CODE=0"; then
  report "无状态玩法操作成功" 0
else
  report "无状态玩法操作成功" 1
fi

# 6. 幂等性
if echo "$out" | grep -q "IDEMPOTENT=True"; then
  report "相同请求幂等" 0
else
  report "相同请求幂等" 1
fi

# 7. 无效 Token 拒绝
if echo "$out" | grep -q "INVALID_TOKEN_CODE=1002"; then
  report "无效 Token 返回会话过期" 0
else
  report "无效 Token 返回会话过期" 1
fi

# 8. 阶段感知
if echo "$out" | grep -q "STAGE_COCOS=stage_cocos" && echo "$out" | grep -q "STAGE_MATCH=True" && echo "$out" | grep -q "STAGE_UNMATCH=False"; then
  report "阶段感知正确" 0
else
  report "阶段感知正确" 1
fi

echo "== 2. 协议生成工具链 =="
out2=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'game-studio-agents/config')
from protocol_tools import ProtocolParser, ProtocolCodegen, ProtocolVersionManager

# 解析协议
parser = ProtocolParser()
parsed = parser.parse('server/proto/protocol.proto')

# 统计
print(f"MSG_COUNT={len(parsed['messages'])}")
print(f"ENUM_COUNT={len(parsed['enums'])}")

# 生成各语言代码
codegen = ProtocolCodegen(parsed)
py = codegen.generate_python()
ts = codegen.generate_typescript()
cs = codegen.generate_csharp()
cpp = codegen.generate_cpp()

print(f"PY_LINES={len(py.splitlines())}")
print(f"TS_LINES={len(ts.splitlines())}")
print(f"CS_LINES={len(cs.splitlines())}")
print(f"CPP_LINES={len(cpp.splitlines())}")

# 验证生成内容包含关键消息
print(f"PY_HAS_PLAYER={'class PlayerData' in py}")
print(f"PY_HAS_REQUEST={'class GameRequest' in py}")
print(f"TS_HAS_PLAYER={'interface PlayerData' in ts}")

# 版本兼容检查
manager = ProtocolVersionManager()
compat = manager.check_backward_compat(parsed, parsed)
print(f"COMPAT={compat['backward_compatible']}")
PYEOF
)

# 9. 协议解析
if echo "$out2" | grep -q "MSG_COUNT=13" && echo "$out2" | grep -q "ENUM_COUNT=4"; then
  report "协议解析完整(13消息/4枚举)" 0
else
  report "协议解析完整(13消息/4枚举)" 1
fi

# 10. 四语言代码生成
if echo "$out2" | grep -q "PY_LINES=15[0-9]" && echo "$out2" | grep -q "TS_LINES=14[0-9]" && echo "$out2" | grep -q "CS_LINES=15[0-9]" && echo "$out2" | grep -q "CPP_LINES=14[0-9]"; then
  report "四种语言代码生成成功" 0
else
  report "四种语言代码生成成功" 1
fi

# 11. 关键消息生成
if echo "$out2" | grep -q "PY_HAS_PLAYER=True" && echo "$out2" | grep -q "PY_HAS_REQUEST=True"; then
  report "Python 生成关键消息" 0
else
  report "Python 生成关键消息" 1
fi

# 12. TS 接口生成
if echo "$out2" | grep -q "TS_HAS_PLAYER=True"; then
  report "TypeScript 生成接口" 0
else
  report "TypeScript 生成接口" 1
fi

# 13. 向后兼容
if echo "$out2" | grep -q "COMPAT=True"; then
  report "协议向后兼容检查通过" 0
else
  report "协议向后兼容检查通过" 1
fi

echo ""
echo "=== 汇总: $pass 通过 / $fail 失败 ==="
if [ "$fail" -gt 0 ]; then
  echo "🔴 无状态服务端核心存在阻塞项"
  exit 1
fi
echo "🟢 无状态服务端核心全部通过"

#!/usr/bin/env bash
# ============================================================
# 游戏开发小组闭环引擎测试信号灯（test_game_dev_team）
# 说明: 参考 dongjiagoushi DevTeam + Goose "执行-验证-规划-监督" 四维闭环，
#       验证程序线落地"开发小组"机制——一套循环 N 个开发（默认 2），
#       多个角色循环的小组，而非单个开发自己循环。
#
# 核心机制:
#   1. 一套循环 N 个开发（默认 2）—— Leader(技术总监) + N 开发
#   2. 执行-验证分离—— dev 只负责做，客观验证器裁定
#   3. 确定性状态机—— 不让 LLM 决定"下一步/是否结束"
#   4. 硬性熔断—— 单 dev 重做超限上报 Leader 换方案；总迭代熔断
#   5. 进度北极星监督—— goal_meter 停滞/横跳被哨兵拦截
#   6. 记录优先于对话—— 过程只写进度留痕，干完统一交付给经理
#   7. 开发密度量化—— dev_ratio() 暴露"开发实干占比"
#   8. 程序线部门接入—— ProgramDeptAgent 使用开发小组闭环
# 退出码: 0 = 🟢 通过，1 = 🔴 阻塞
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/../config"
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

echo "== 1. 一套循环 N 个开发（默认 2，多角色小组而非单开发循环）=="
out=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from game_dev_team import run_dev_team
r = run_dev_team(
    {"id": "wp_a", "module": "client", "label": "战斗系统", "project": "Game"},
    dev_roles=["client_dev", "server_dev"])
print("OK=" + str(r.get("ok")))
print("DEV_COUNT=" + str(r.get("dev_count")))
print("DEVS=" + ",".join(sorted(r.get("devs", []))))
print("LEADER=" + str(r.get("leader")))
PYEOF
)
if echo "$out" | grep -q "OK=True"; then report "开发小组闭环成功运行" 0; else report "开发小组闭环成功运行" 1; fi
if echo "$out" | grep -q "DEV_COUNT=2"; then report "一套循环 2 个开发（devs_per_team=2）" 0; else report "一套循环 2 个开发（devs_per_team=2）" 1; fi
if echo "$out" | grep -q "DEVS=client_dev,server_dev"; then report "小组角色 = 客户端 + 服务端（多角色）" 0; else report "小组角色 = 客户端 + 服务端（多角色）" 1; fi
if echo "$out" | grep -q "LEADER=cto"; then report "Leader = 技术总监（cto）" 0; else report "Leader = 技术总监（cto）" 1; fi

echo "== 2. 执行-验证分离：客观验证器裁定（dev 只做不判）=="
out=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from game_dev_team import GameDevTeamEngine

# 用一个"产出为空"的开发验证客观验证器驳回
def bad_produce(task):
    return {"module": task.module, "artifact_type": "code", "content": None}

def strict_verifier(task):
    art = task.artifact or {}
    if not art.get("content"):
        return False, "开发产出为空（客观验证驳回）"
    return True, "通过"

engine = GameDevTeamEngine(devs_per_team=1, max_attempts=1, max_iterations=3, verifier=strict_verifier)
engine.create_team("t2", "cto", ["client_dev"], "client")
engine.execute_dev("client_dev", produce=bad_produce)
res = engine.verify_dev("client_dev")
print("VERIFY=" + res)
print("NOTE=" + engine.team.tasks["client_dev"].verify_note)
PYEOF
)
if echo "$out" | grep -q "VERIFY=REJECTED"; then report "产出为空被客观验证器 REJECTED（执行-验证分离）" 0; else report "产出为空被客观验证器 REJECTED（执行-验证分离）" 1; fi

echo "== 3. 确定性状态机：run_round 用代码控制流转（非 LLM 自决）=="
out=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from game_dev_team import GameDevTeamEngine
engine = GameDevTeamEngine(devs_per_team=2)
engine.create_team("t3", "cto", ["client_dev", "server_dev"], "client")
r = engine.run_round()
print("ROUND=" + str(r.round_no))
print("EXEC=" + ",".join(sorted(r.tasks)))
print("VERIFIED=" + ",".join(sorted(r.verified)))
print("FUSED=" + str(len(r.fused) > 0))
PYEOF
)
if echo "$out" | grep -q "ROUND=1" && echo "$out" | grep -q "VERIFIED=client_dev,server_dev"; then report "确定性状态机一轮执行→验证→整合" 0; else report "确定性状态机一轮执行→验证→整合" 1; fi
if echo "$out" | grep -q "FUSED=True"; then report "全组通过后 Leader 整合（fuse）" 0; else report "全组通过后 Leader 整合（fuse）" 1; fi

echo "== 4. 硬性熔断：单 dev 重做超限上报 Leader 换方案 =="
out=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from game_dev_team import GameDevTeamEngine

def always_reject(task):
    return False, "一直失败"

engine = GameDevTeamEngine(devs_per_team=1, max_attempts=3, max_iterations=10, verifier=always_reject)
engine.create_team("t4", "cto", ["client_dev"], "client")
for _ in range(5):
    try:
        engine.run_round()
    except RuntimeError as e:
        print("FUSE_ERR=" + str("熔断" in str(e)))
        break
t = engine.team.tasks["client_dev"]
print("STATUS=" + t.status)
print("ATTEMPTS=" + str(t.attempts))
print("NOTE=" + t.verify_note)
PYEOF
)
if echo "$out" | grep -q "STATUS=FAILED" && echo "$out" | grep -q "ATTEMPTS=3"; then report "单开发重做 3 次后熔断（硬性熔断）" 0; else report "单开发重做 3 次后熔断（硬性熔断）" 1; fi
if echo "$out" | grep -q "上报 Leader 换方案"; then report "熔断上报 Leader 换方案" 0; else report "熔断上报 Leader 换方案" 1; fi

echo "== 5. 进度北极星监督：goal_meter 完成度留痕 =="
out=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from game_dev_team import run_dev_team
r = run_dev_team({"id": "wp_b", "module": "server", "label": "战斗服", "project": "Game"},
                 dev_roles=["server_dev", "engine_dev"])
ov = r.get("overview", {}).get("devs", [])
meters = [d["goal_meter"] for d in ov]
print("METER=" + str(all(m >= 1.0 for m in meters)))
print("ROUNDS=" + str(len(r.get("progress", {}).get("rounds", []))))
PYEOF
)
if echo "$out" | grep -q "METER=True"; then report "进度北极星 goal_meter 打满（完成度可监督）" 0; else report "进度北极星 goal_meter 打满（完成度可监督）" 1; fi
if echo "$out" | grep -q "ROUNDS="; then report "过程只写进度留痕（rounds 留痕非对话）" 0; else report "过程只写进度留痕（rounds 留痕非对话）" 1; fi

echo "== 6. 干完统一交付给经理（含进度回放）=="
out=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from game_dev_team import run_dev_team
r = run_dev_team({"id": "wp_c", "module": "ai_logic", "label": "NPC AI", "project": "Game"},
                 dev_roles=["ai_programmer", "engine_dev"])
dl = r.get("deliver", {})
print("EVENT=" + str(dl.get("event")))
print("HAS_ARTIFACT=" + str(r.get("artifact") is not None))
print("HAS_PROGRESS=" + str("progress" in r and len(r["progress"].get("rounds", [])) > 0))
PYEOF
)
if echo "$out" | grep -q "EVENT=dev_team_deliver"; then report "统一交付（一次性通知，含进度回放）" 0; else report "统一交付（一次性通知，含进度回放）" 1; fi

echo "== 7. 开发密度量化：dev_ratio 暴露开发实干占比 =="
out=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from game_dev_team import run_dev_team
r = run_dev_team({"id": "wp_d", "module": "client", "label": "登录", "project": "Game"},
                 dev_roles=["client_dev", "server_dev"])
print("RATIO=" + str(r.get("dev_ratio")))
PYEOF
)
if echo "$out" | grep -q "RATIO=0.67"; then report "开发密度 2/3=0.67（开发过半，辅助不挤占）" 0; else report "开发密度 2/3=0.67（开发过半，辅助不挤占）" 1; fi

echo "== 8. 程序线部门接入：ProgramDeptAgent 使用开发小组闭环 =="
out=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from message_bus import MessageBus, Message
from department_agents import ProgramDeptAgent
bus = MessageBus()
p = ProgramDeptAgent(bus)
p.boot()
msg = Message("TASK_ASSIGN", "producer", "cto", {
    "task_id": "wp_client_x",
    "payload": {"work_package": {
        "id": "wp_client_x", "label": "UI系统", "module": "client", "project": "Game"
    }}
})
bus.publish(msg)
bus.process_all()
# 检查是否执行完成且带开发小组闭环信息
done = "wp_client_x" in p.done_packages
has_dev_team = False
for evt in p.log:
    if evt.get("event") == "dev_team" and "2 开发" in evt.get("note", ""):
        has_dev_team = True
print("DONE=" + str(done))
print("DEV_TEAM_LOOP=" + str(has_dev_team))
PYEOF
)
if echo "$out" | grep -q "DONE=True"; then report "程序线部门执行完成工作包" 0; else report "程序线部门执行完成工作包" 1; fi
if echo "$out" | grep -q "DEV_TEAM_LOOP=True"; then report "程序线接入开发小组闭环（2 开发）" 0; else report "程序线接入开发小组闭环（2 开发）" 1; fi

echo ""
echo "======================"
echo "  游戏开发小组闭环测试"
echo "======================"
echo "  ✅ 通过: $pass"
echo "  ❌ 失败: $fail"
echo "======================"

echo "== 9. 评审修复回归（fused 内容校验 + 失败透传）=="
out=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from game_dev_team import run_dev_team

# 9a. fused 记录正确的被整合开发角色
r = run_dev_team(
    {"id": "wp_fuse", "module": "client", "label": "Fuse验证", "project": "Game"},
    dev_roles=["client_dev", "server_dev"])
rounds = r.get("progress", {}).get("rounds", [])
last_round = rounds[-1] if rounds else {}
fused_roles = sorted(last_round.get("fused", []))
print("FUSED_ROLES=" + ",".join(fused_roles))

# 9b. dev_team ok=False 时 _verify 失败透传
from message_bus import MessageBus
from department_agents import ProgramDeptAgent
bus = MessageBus()
p = ProgramDeptAgent(bus)
p.boot()
art = {"module": "client", "label": "x", "project": "y",
       "content": {"note": "test"},
       "dev_team": {"ok": False, "reason": "测试熔断"}}
ok, note = p._verify({}, art)
print("VERIFY_OK=" + str(ok))
print("VERIFY_NOTE=" + note)
PYEOF
)
if echo "$out" | grep -q "FUSED_ROLES=client_dev,server_dev"; then report "fused 记录被整合的开发角色（修复 Bug1）" 0; else report "fused 记录被整合的开发角色（修复 Bug1）" 1; fi
if echo "$out" | grep -q "VERIFY_OK=False"; then report "dev_team 失败透传到验收（修复 Warning2）" 0; else report "dev_team 失败透传到验收（修复 Warning2）" 1; fi
if echo "$out" | grep -q "VERIFY_NOTE=开发小组闭环失败"; then report "失败原因透传（熔断原因）" 0; else report "失败原因透传（熔断原因）" 1; fi

if [ "$fail" -gt 0 ]; then
  exit 1
fi
exit 0

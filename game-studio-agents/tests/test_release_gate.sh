#!/usr/bin/env bash
# ============================================================
# 发版质量门禁与验收放行测试信号灯（wp_release）
# 说明: 验证 wp_release（项目管理·project_manager）落地产出——
#       对生态角色接入 + 市场预演产出做发版质量门禁与验收放行。
#       含 stage_gate 阶段边界审查门禁（PR #113 下游解锁）。
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

echo "== 1. 发版质量门禁与验收放行（wp_release·project_manager）=="
out=$($PY release_gate.py 2>&1)

# 1. 发版质量门禁逐项核对（四部分达标）
if echo "$out" | grep -q "market_preview.*3/3 通过" \
   && echo "$out" | grep -q "ecosystem_roles.*3/3 通过" \
   && echo "$out" | grep -q "progress_pusher.*4/4 通过" \
   && echo "$out" | grep -q "stage_gate.*3/3 通过"; then
  report "发版质量门禁逐项核对（市场预演/生态角色/进度督导/stage_gate）" 0
else
  report "发版质量门禁逐项核对（市场预演/生态角色/进度督导/stage_gate）" 1
fi

# 1b. stage_gate 阶段边界审查纳入发版门禁
if echo "$out" | grep -q "stage_gate.*3/3 通过"; then
  report "stage_gate 阶段边界审查纳入发版门禁（3/3）" 0
else
  report "stage_gate 阶段边界审查纳入发版门禁（3/3）" 1
fi

# 2. 验收结论 GO 放行
if echo "$out" | grep -q "放行: GO"; then
  report "验收放行 GO" 0
else
  report "验收放行 GO" 1
fi

# 3. 验收结论通过
if echo "$out" | grep -q "验收放行：全链路产出达标"; then
  report "验收结论：全链路产出达标" 0
else
  report "验收结论：全链路产出达标" 1
fi

echo "== 2. PmDeptAgent 集成（wp_release 产出放行结论）=="
out2=$($PY - <<'PYEOF'
from department_agents import PmDeptAgent
from message_bus import MessageBus
agent = PmDeptAgent(MessageBus())
agent.boot()
wp = {"module":"release","label":"发版","project":"P","id":"wp_release","department_name":"项目管理"}
a = agent._execute(wp, {})
rg = a.get("release_gate", {})
print("HAS_GATE=", "release_gate" in a)
print("GO_NO_GO=", rg.get("go_no_go",""))
print("VERIFY=", agent._verify(wp, a)[0])
PYEOF
)

if echo "$out2" | grep -q "HAS_GATE= True"; then
  report "PmDeptAgent 产出发版质量门禁" 0
else
  report "PmDeptAgent 产出发版质量门禁" 1
fi
if echo "$out2" | grep -q "GO_NO_GO= GO"; then
  report "发版门禁验收放行 GO" 0
else
  report "发版门禁验收放行 GO" 1
fi
if echo "$out2" | grep -q "VERIFY= True"; then
  report "wp_release 产出自检通过" 0
else
  report "wp_release 产出自检通过" 1
fi

# 2b. milestone_plan 含 stage_gate 检查点 + release_checklist
out3=$($PY - <<'PYEOF'
from department_agents import PmDeptAgent
from message_bus import MessageBus
agent = PmDeptAgent(MessageBus())
agent.boot()
wp = {"module":"release","label":"发版","project":"P","id":"wp_release","department_name":"项目管理"}
a = agent._execute(wp, {})
content = a.get("content", {})
mp = content.get("milestone_plan", {})
print(f"HAS_MILESTONE_PLAN={bool(mp)}")
print(f"MILESTONE_M1_STAGE_GATE={'stage_gate' in mp.get('M1', {})}")
print(f"CHECKLIST_STAGE_GATE={'阶段边界审查通过' in content.get('release_checklist', [])}")
PYEOF
)

if echo "$out3" | grep -q "HAS_MILESTONE_PLAN=True" && echo "$out3" | grep -q "MILESTONE_M1_STAGE_GATE=True"; then
  report "里程碑计划含 stage_gate 阶段边界检查点（M1-M5）" 0
else
  report "里程碑计划含 stage_gate 阶段边界检查点（M1-M5）" 1
fi
if echo "$out3" | grep -q "CHECKLIST_STAGE_GATE=True"; then
  report "release_checklist 含「阶段边界审查通过」" 0
else
  report "release_checklist 含「阶段边界审查通过」" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 发版质量门禁与验收放行通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 发版质量门禁与验收放行存在阻塞项"
  exit 1
fi

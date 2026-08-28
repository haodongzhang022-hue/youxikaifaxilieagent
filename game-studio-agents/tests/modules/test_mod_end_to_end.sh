#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：端到端全链路联动 (EndToEndOrchestrator)
# 功能定义: 装配「游戏向经理 + 六大部门 Agent + task_scheduler +
#           message_bus」，自动跑通策划→程序→美术→测试→发版→运营。
# 验收标准: 全链路自动编排完成，工作包全部 DONE。
# 退出码: 0 = 🟢 通过，1 = 🔴 阻塞
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/../../config"
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

echo "== 功能模块验收：端到端全链路联动 =="

out=$($PY - <<'PYEOF'
from run_end_to_end import EndToEndOrchestrator

# 1. 创建编排器
orch = EndToEndOrchestrator()
print(f"ORCH_CREATED=True")

# 2. 下发架构蓝图
architecture = {
    "vision": "游戏开发系列 Agent",
    "milestones": ["架构", "实现"],
    "modules": ["gameplay", "client", "testing", "release", "data_ops"]
}
orch.assemble(architecture)

# 3. 驱动全链路
result = orch.drive(max_rounds=100)
print(f"ALL_DONE={result.get('all_done')}")
print(f"ROUNDS={result.get('rounds')}")

# 4. 验证工作包全部 DONE
states = {tid: t.state for tid, t in orch.scheduler.queue.tasks.items()}
print(f"ALL_WP_DONE={all(s == 'DONE' for s in states.values()) if states else False}")
print(f"WP_COUNT={len(states)}")

# 5. 验证六大部门 Agent 全部就绪
print(f"DEPT_COUNT={len(orch.departments)}")
dept_keys = list(orch.departments.keys())
print(f"ALL_6_DEPTS={all(d in dept_keys for d in ['design', 'program', 'art', 'qa', 'pm', 'ops'])}")

# 6. 验证消息总线有交互
print(f"BUS_MESSAGES={len(orch.bus.delivered)}")
PYEOF
)

# 1. 编排器创建
if echo "$out" | grep -q "ORCH_CREATED=True"; then
  report "端到端编排器创建成功" 0
else
  report "端到端编排器创建成功" 1
fi

# 2. 全链路完成
if echo "$out" | grep -q "ALL_DONE=True"; then
  report "全链路端到端联动完成" 0
else
  report "全链路端到端联动完成" 1
fi

# 3. 工作包全部完成
if echo "$out" | grep -q "ALL_WP_DONE=True" && echo "$out" | grep -q "WP_COUNT=.*[1-9]"; then
  report "工作包全部 DONE" 0
else
  report "工作包全部 DONE" 1
fi

# 4. 六大部门就绪
if echo "$out" | grep -q "DEPT_COUNT=6" && echo "$out" | grep -q "ALL_6_DEPTS=True"; then
  report "六大部门 Agent 全部就绪" 0
else
  report "六大部门 Agent 全部就绪" 1
fi

# 5. 有限轮次内完成
if echo "$out" | grep -q "ROUNDS=.*[1-9][0-9]*"; then
  report "有限轮次内自动完成" 0
else
  report "有限轮次内自动完成" 1
fi

# 6. 总线消息交互
if echo "$out" | grep -q "BUS_MESSAGES=.*[1-9][0-9]*"; then
  report "全链路消息总线交互充分" 0
else
  report "全链路消息总线交互充分" 1
fi

echo ""
echo "【端到端联动模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 端到端联动功能模块验收通过"
exit 0

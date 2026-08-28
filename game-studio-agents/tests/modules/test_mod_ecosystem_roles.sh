#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：生态角色注册与派发 (EcosystemRoleRegistry)
# 功能定义: 把生态角色（玩家圈/外部市场圈/协作支持圈/美术圈）注册进
#           message_bus + task_scheduler，成为可派发 Agent。
# 验收标准: 生态角色能正确注册、派发并 publish 到总线。
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

echo "== 功能模块验收：生态角色注册与派发 =="

out=$($PY - <<'PYEOF'
from ecosystem_role_registry import load_ecosystem_roles, EcosystemRoleRegistry
from message_bus import MessageBus
from task_scheduler import Scheduler, Task

# 1. 加载生态角色
roles = load_ecosystem_roles()
print(f"ECOSYSTEM_ROLES={len(roles)}")

# 2. 创建注册器并注册到总线
bus = MessageBus()
reg = EcosystemRoleRegistry(bus=bus)
reg.load()
registered = reg.register()
print(f"REGISTERED_TO_BUS={len(registered)}")

# 3. 接入调度器
sched = Scheduler(bus=bus)
reg.register_scheduler(sched)

# 4. 派发生态角色任务
task = Task(id="eco_task", name="市场预演", owner="publisher", priority="NORMAL")
sched.enqueue(task)
bus.process_all()
print(f"BUS_DELIVERED={len(bus.delivered)}")
print(f"BUS_TASK_ASSIGN={len([m for m in bus.delivered if m.type == 'TASK_ASSIGN'])}")

# 5. 按圈层统计
summary = reg.summary()
print(f"SUMMARY_TOTAL={summary.get('total', 0)}")
print(f"SUMMARY_CIRCLES={list(summary.get('by_circle', {}).keys())}")

# 6. 按圈层查询
print(f"COLLAB_SUPPORT_COUNT={len(reg.by_circle('collab_support'))}")
print(f"PLAYERS_COUNT={len(reg.by_circle('players'))}")
print(f"MARKET_COUNT={len(reg.by_circle('market'))}")
print(f"ART_COUNT={len(reg.by_circle('art'))}")
PYEOF
)

# 1. 生态角色加载
if echo "$out" | grep -q "ECOSYSTEM_ROLES=.*[1-9][0-9]"; then
  report "生态角色加载完整（10+ 角色）" 0
else
  report "生态角色加载完整（10+ 角色）" 1
fi

# 2. 注册到总线
if echo "$out" | grep -q "REGISTERED_TO_BUS=.*[1-9][0-9]"; then
  report "生态角色注册到消息总线" 0
else
  report "生态角色注册到消息总线" 1
fi

# 3. 任务派发投递
if echo "$out" | grep -q "BUS_DELIVERED=.*[1-9]" && echo "$out" | grep -q "BUS_TASK_ASSIGN=.*[1-9]"; then
  report "生态角色任务派发并投递到总线" 0
else
  report "生态角色任务派发并投递到总线" 1
fi

# 4. 注册汇总
if echo "$out" | grep -q "SUMMARY_TOTAL=.*[1-9][0-9]"; then
  report "生态角色注册汇总正确" 0
else
  report "生态角色注册汇总正确" 1
fi

# 5. 四圈层统计
if echo "$out" | grep -q "SUMMARY_CIRCLES=.*协作支持圈" && echo "$out" | grep -q "SUMMARY_CIRCLES=.*玩家圈" && echo "$out" | grep -q "SUMMARY_CIRCLES=.*外部市场圈" && echo "$out" | grep -q "SUMMARY_CIRCLES=.*美术圈"; then
  report "生态角色四个圈层注册完整" 0
else
  report "生态角色四个圈层注册完整" 1
fi

# 6. 各圈层角色数量
if echo "$out" | grep -q "COLLAB_SUPPORT_COUNT=.*[1-9]" && echo "$out" | grep -q "PLAYERS_COUNT=.*[1-9]" && echo "$out" | grep -q "MARKET_COUNT=.*[1-9]" && echo "$out" | grep -q "ART_COUNT=.*[1-9]"; then
  report "每个圈层均有角色注册" 0
else
  report "每个圈层均有角色注册" 1
fi

echo ""
echo "【生态角色模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 生态角色功能模块验收通过"
exit 0

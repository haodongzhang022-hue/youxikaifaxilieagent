#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：游戏向经理 (GameProducerAgent)
# 功能定义: 把架构蓝图拆解为可执行工作包，按部门分配任务与资源，
#           通过事件驱动机制自动推进部门间协作。
# 验收标准: 经理能正确拆解蓝图、分配部门、派发任务、验收产出、
#           解锁下游。
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

echo "== 功能模块验收：游戏向经理 (GameProducerAgent) =="

out=$($PY - <<'PYEOF'
from game_producer_agent import GameProducerAgent, DEPARTMENTS, ARCHITECTURE_MODULES
from message_bus import MessageBus, build_task_assign, build_message
from task_scheduler import Task, TaskState

# 1. 创建经理
bus = MessageBus()
manager = GameProducerAgent(bus=bus)
manager.boot()
print(f"MANAGER_ROLE={manager.role_id}")
print(f"BIZ_STATE_INIT={manager.biz_state}")

# 2. 验证部门注册
print(f"DEPT_COUNT={len(DEPARTMENTS)}")
print(f"DEPT_KEYS={sorted(DEPARTMENTS.keys())}")

# 3. 验证架构模块到部门映射
print(f"ARCH_MODULE_COUNT={len(ARCHITECTURE_MODULES)}")
print(f"GAMEPLAY_DEPT={ARCHITECTURE_MODULES['gameplay']['department']}")
print(f"CLIENT_DEPT={ARCHITECTURE_MODULES['client']['department']}")
print(f"TESTING_DEPT={ARCHITECTURE_MODULES['testing']['department']}")

# 4. 下发架构蓝图
architecture = {
    "vision": "游戏开发系列Agent",
    "milestones": ["架构", "实现"],
    "modules": ["gameplay", "client", "testing", "release"]
}
msg = build_task_assign("architect", manager.role_id, "e2e_001",
                        {"architecture": architecture})
bus.publish(msg)
bus.process_all()
print(f"WORK_PACKAGES={len(manager.work_packages)}")
if manager.work_packages:
    wp_ids = [wp.get("id") for wp in manager.work_packages]
    print(f"WP_IDS={wp_ids}")
    first = manager.work_packages[0]
    print(f"WP_FIRST_DEPT={first.get('department_name', '')}")
    print(f"WP_FIRST_ID={first.get('id', '')}")

# 5. 验证 scheduler 使用
print(f"HAS_SCHEDULER={manager.scheduler is not None}")
print(f"QUEUE_TASKS={len(manager.scheduler.queue.tasks)}")

# 6. 验证 manager 可接收消息
print(f"BUS_ROLES={'producer' in bus.roles}")
PYEOF
)

# 1. 经理角色正确
if echo "$out" | grep -q "MANAGER_ROLE=producer"; then
  report "经理 role_id 为 producer" 0
else
  report "经理 role_id 为 producer" 1
fi

# 2. 六大部门注册
if echo "$out" | grep -q "DEPT_COUNT=6"; then
  report "六大部门全部注册（6 个）" 0
else
  report "六大部门全部注册（6 个）" 1
fi

# 3. 部门键正确
if echo "$out" | grep -q "DEPT_KEYS=\['art', 'design', 'ops', 'pm', 'program', 'qa'\]"; then
  report "部门键正确（design/program/art/qa/pm/ops）" 0
else
  report "部门键正确（design/program/art/qa/pm/ops）" 1
fi

# 4. 架构模块映射正确
if echo "$out" | grep -q "GAMEPLAY_DEPT=design" && echo "$out" | grep -q "CLIENT_DEPT=program" && echo "$out" | grep -q "TESTING_DEPT=qa"; then
  report "架构模块→部门映射正确" 0
else
  report "架构模块→部门映射正确" 1
fi

# 5. 工作包拆解
if echo "$out" | grep -q "WORK_PACKAGES=.*[1-9]"; then
  report "蓝图拆解为工作包" 0
else
  report "蓝图拆解为工作包" 1
fi

# 6. 工作包 ID 正确
if echo "$out" | grep -q "WP_IDS=.*wp_"; then
  report "工作包 ID 前缀 wp_ 正确" 0
else
  report "工作包 ID 前缀 wp_ 正确" 1
fi

# 7. 工作包分配部门
if echo "$out" | grep -q "WP_FIRST_DEPT=" && ! echo "$out" | grep -q "WP_FIRST_DEPT=$"; then
  report "工作包分配到部门" 0
else
  report "工作包分配到部门" 1
fi

# 8. 经理使用调度器
if echo "$out" | grep -q "HAS_SCHEDULER=True"; then
  report "经理复用任务调度器" 0
else
  report "经理复用任务调度器" 1
fi

# 9. 经理注册到总线
if echo "$out" | grep -q "BUS_ROLES=True"; then
  report "经理注册到消息总线" 0
else
  report "经理注册到消息总线" 1
fi

echo ""
echo "【游戏向经理模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 游戏向经理功能模块验收通过"
exit 0

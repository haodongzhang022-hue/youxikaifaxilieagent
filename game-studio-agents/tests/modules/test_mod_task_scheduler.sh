#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：任务调度 (TaskScheduler / TaskQueue)
# 功能定义: 任务队列管理（优先级/DDL/状态流转）、依赖调度、
#           事件驱动（任务状态变化发布到 MessageBus）。
# 验收标准: 任务能正确入队/排序/执行/完成，依赖解锁正确，
#           调度器事件通过总线正确投递。
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

echo "== 功能模块验收：任务调度 (TaskScheduler) =="

out=$($PY - <<'PYEOF'
from task_scheduler import Scheduler, Task, TaskState, TaskQueue
from message_bus import MessageBus, Message

# 1. 创建调度器
bus = MessageBus()
sched = Scheduler(bus=bus)

# 2. 任务创建与状态流转
t1 = Task(id="t1", name="上游任务", owner="designer", priority="NORMAL")
t2 = Task(id="t2", name="下游任务", owner="client_dev", priority="HIGH", depends_on=["t1"])
t3 = Task(id="t3", name="独立任务", owner="qa", priority="LOW")

sched.enqueue(t1)
sched.enqueue(t2)
sched.enqueue(t3)

# 处理总线消息
bus.process_all()
print(f"READY_ORDER_INIT={sched.queue.ready_order}")

# 完成 t1 后 t2 就绪
sched.on_complete("t1", "designer")
bus.process_all()
print(f"READY_ORDER_AFTER_T1_DONE={sched.queue.ready_order}")

# 3. 验证 DDL 和优先级
print(f"T1_STATE={t1.state}")
print(f"T2_STATE={t2.state}")
print(f"T3_PRIORITY={t3.priority}")
print(f"T2_PRIORITY_WEIGHT={t2.priority_weight}")

# 4. 事件发布检查
print(f"EVENTS_TOTAL={len(bus.delivered)}")
events = [m.type for m in bus.delivered]
print(f"EVENT_TYPES={sorted(set(events))}")

# 5. 验证任务状态
print(f"TASK_STATES={ {k:v.state for k,v in sched.queue.tasks.items()} }")

# 6. 验证超时判断
import time
t_late = Task(id="t_late", name="逾期任务", owner="dev", ddl=time.time() - 86400)
t_ok = Task(id="t_ok", name="正常任务", owner="dev", ddl=time.time() + 86400)
print(f"T_LATE_OVERDUE={t_late.overdue():.1f}")
print(f"T_OK_OVERDUE={t_ok.overdue():.1f}")

# 7. 依赖阻塞验证
t_blocked = Task(id="t_b", name="阻塞任务", owner="dev", depends_on=["not_exist"])
sched.enqueue(t_blocked)
print(f"T_BLOCKED_STATE={t_blocked.state}")

# 8. 验证 TASK_ASSIGN 消息投递到总线
print(f"ASSIGN_MSGS={len(sched._last_assign_msgs)}")
PYEOF
)

# 1. 初始就绪顺序：无依赖任务优先
if echo "$out" | grep -q "READY_ORDER_INIT=.*t1.*t3"; then
  report "无依赖任务初始就绪（t1, t3 先就绪）" 0
else
  report "无依赖任务初始就绪（t1, t3 先就绪）" 1
fi

# 2. t1 完成后 t2 被解锁
if echo "$out" | grep -q "READY_ORDER_AFTER_T1_DONE=.*t2"; then
  report "上游完成解锁下游依赖（t1 完成→t2 就绪）" 0
else
  report "上游完成解锁下游依赖（t1 完成→t2 就绪）" 1
fi

# 3. 任务状态流转
if echo "$out" | grep -q "T1_STATE=DONE" && echo "$out" | grep -q "T2_STATE=TODO"; then
  report "任务状态流转正确（完成=DONE / 未执行=TODO）" 0
else
  report "任务状态流转正确（完成=DONE / 未执行=TODO）" 1
fi

# 4. 优先级权重
if echo "$out" | grep -q "T3_PRIORITY=LOW" && echo "$out" | grep -q "T2_PRIORITY_WEIGHT=2"; then
  report "优先级权重计算正确" 0
else
  report "优先级权重计算正确" 1
fi

# 5. 调度器事件发布到消息总线
if echo "$out" | grep -q "EVENTS_TOTAL=.*[1-9]"; then
  report "调度器事件发布到消息总线" 0
else
  report "调度器事件发布到消息总线" 1
fi

# 6. 任务状态完整
if echo "$out" | grep -q "TASK_STATES=.*t1.*DONE" && echo "$out" | grep -q "TASK_STATES=.*t3.*TODO"; then
  report "任务状态完整记录" 0
else
  report "任务状态完整记录" 1
fi

# 7. DDL 超时判断
if echo "$out" | grep -q "T_LATE_OVERDUE=[1-9]" && echo "$out" | grep -q "T_OK_OVERDUE=0.0"; then
  report "DDL 超时判断正确（逾期>0 / 未逾期=0）" 0
else
  report "DDL 超时判断正确（逾期>0 / 未逾期=0）" 1
fi

# 8. 阻塞任务未就绪
if echo "$out" | grep -q "T_BLOCKED_STATE=TODO"; then
  report "依赖未满足任务保持 TODO 状态" 0
else
  report "依赖未满足任务保持 TODO 状态" 1
fi

# 9. TASK_ASSIGN 已派发
if echo "$out" | grep -q "ASSIGN_MSGS=.*[2-9]"; then
  report "TASK_ASSIGN 消息已派发（就绪任务被分配）" 0
else
  report "TASK_ASSIGN 消息已派发（就绪任务被分配）" 1
fi

echo ""
echo "【任务调度模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 任务调度功能模块验收通过"
exit 0

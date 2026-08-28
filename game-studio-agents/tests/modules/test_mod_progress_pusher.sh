#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：进度督导 (ProgressPusher)
# 功能定义: 盯 DDL、主动催办、识别阻塞并升级，四类决策
#           WATCH / PUSH / ESCALATE / WARN 规则化。
# 验收标准: 四类决策正确触发并投递到总线，冷却机制生效。
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

echo "== 功能模块验收：进度督导 (ProgressPusher) =="

out=$($PY - <<'PYEOF'
from progress_pusher import ProgressPusherAgent, load_policy
from task_scheduler import Task, TaskQueue, TaskState
from message_bus import MessageBus
import time

# 1. 创建进度督导 Agent
bus = MessageBus()
queue = TaskQueue()
pusher = ProgressPusherAgent(bus=bus, queue=queue)
pusher.boot()

# 2. 加载策略
policy = load_policy()
print(f"POLICY_LAG_THRESHOLD={policy.get('lag_threshold_days')}")
print(f"POLICY_MAX_PUSHES={policy.get('max_pushes_per_task')}")

# 3. 创建不同状态的任务
now = time.time()
t_ok = Task(id="t_ok", name="正常任务", owner="designer", ddl=now + 5 * 86400)
t_late = Task(id="t_late", name="逾期任务", owner="client_dev", ddl=now - 2 * 86400)
# 阻塞任务：设 BLOCKED 状态 + 超过 24 小时的阻塞时间
t_block = Task(id="t_block", name="阻塞任务", owner="qa", ddl=now + 1 * 86400)
t_block.touch(TaskState.BLOCKED.value, "阻塞")
t_block.updated_at = now - 25 * 3600
t_near = Task(id="t_near", name="临近任务", owner="system_designer", ddl=now + 0.2 * 86400)
for t in [t_ok, t_late, t_block, t_near]:
    queue.add(t)

# 4. 对每个任务执行督导决策
for tid in ["t_ok", "t_late", "t_block", "t_near"]:
    task = queue.tasks[tid]
    decision = pusher.supervise(task)
    print(f"DECISION:{tid}={decision.get('action')}")

# 5. 处理总线消息
bus.process_all()

# 6. 验证催办消息送达
msgs = [m for m in bus.delivered]
print(f"DELIVERED_COUNT={len(msgs)}")
for m in msgs:
    event = m.content.get('event', str(m.content))
    print(f"MSG:{m.type}:{m.to_role}:{event}")

# 7. 检查 decisions 记录
print(f"DECISIONS_RECORDED={len(pusher.decisions)}")
PYEOF
)

# 1. 策略加载
if echo "$out" | grep -q "POLICY_LAG_THRESHOLD=2.0" && echo "$out" | grep -q "POLICY_MAX_PUSHES=3"; then
  report "策略声明化配置加载正确" 0
else
  report "策略声明化配置加载正确" 1
fi

# 2. 正常任务→WATCH
if echo "$out" | grep -q "DECISION:t_ok=WATCH"; then
  report "正常任务→WATCH（不打扰）" 0
else
  report "正常任务→WATCH（不打扰）" 1
fi

# 3. 逾期任务→PUSH
if echo "$out" | grep -q "DECISION:t_late=PUSH"; then
  report "逾期任务→PUSH（催办）" 0
else
  report "逾期任务→PUSH（催办）" 1
fi

# 4. 阻塞任务→ESCALATE
if echo "$out" | grep -q "DECISION:t_block=ESCALATE"; then
  report "阻塞任务→ESCALATE（升级）" 0
else
  report "阻塞任务→ESCALATE（升级）" 1
fi

# 5. 临近任务→WARN
if echo "$out" | grep -q "DECISION:t_near=WARN"; then
  report "临近任务→WARN（预警）" 0
else
  report "临近任务→WARN（预警）" 1
fi

# 6. 催办消息投递
if echo "$out" | grep -q "DELIVERED_COUNT=.*[1-9]"; then
  report "督导消息投递到总线" 0
else
  report "督导消息投递到总线" 1
fi

# 7. 消息送达责任 owner
if echo "$out" | grep -q "MSG:.*client_dev"; then
  report "PUSH 催办消息送达责任 owner" 0
else
  report "PUSH 催办消息送达责任 owner" 1
fi

# 8. 消息送达项目经理
if echo "$out" | grep -q "MSG:.*project_manager"; then
  report "ESCALATE 升级消息送达项目经理" 0
else
  report "ESCALATE 升级消息送达项目经理" 1
fi

# 9. 决策记录完整
if echo "$out" | grep -q "DECISIONS_RECORDED=.*[1-9]"; then
  report "督导决策全量记录" 0
else
  report "督导决策全量记录" 1
fi

echo ""
echo "【进度督导模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 进度督导功能模块验收通过"
exit 0

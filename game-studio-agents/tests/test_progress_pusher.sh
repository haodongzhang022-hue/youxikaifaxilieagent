#!/usr/bin/env bash
# ============================================================
# 进度督导（Progress Pusher）测试信号灯（护栏）
# 说明: 验证进度督导 v1.0（程序规则化 + 声明化策略）稳定可生效：
#       1. 正常任务 → WATCH（不打扰）
#       2. 逾期任务 → PUSH（经总线催办 owner）
#       3. 阻塞超时 → ESCALATE（升级项目经理）
#       4. 临近 DDL → WARN（友好预警）
#       5. 策略声明化：修改 YAML 可调阈值，不碰代码
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

echo "== 1. 进度督导四类决策（WATCH / PUSH / ESCALATE / WARN）=="
out=$($PY progress_pusher.py 2>&1)
if echo "$out" | grep -q "t_ok.*WATCH"; then
  report "正常任务 → WATCH（不打扰）" 0
else
  report "正常任务 → WATCH（不打扰）" 1
fi
if echo "$out" | grep -q "t_late.*PUSH"; then
  report "逾期任务 → PUSH（催办）" 0
else
  report "逾期任务 → PUSH（催办）" 1
fi
if echo "$out" | grep -q "t_block.*ESCALATE"; then
  report "阻塞超时 → ESCALATE（升级）" 0
else
  report "阻塞超时 → ESCALATE（升级）" 1
fi
if echo "$out" | grep -q "t_near.*WARN"; then
  report "临近DDL → WARN（预警）" 0
else
  report "临近DDL → WARN（预警）" 1
fi
if echo "$out" | grep -q "t_exhaust.*ESCALATE"; then
  report "催满次数未完成 → ESCALATE（不再无效催办）" 0
else
  report "催满次数未完成 → ESCALATE（不再无效催办）" 1
fi

echo "== 2. 督导消息真正经总线发出（程序规则化生效）=="
if echo "$out" | grep -q "PUSH:t_late"; then
  report "PUSH 消息已发出给 owner" 0
else
  report "PUSH 消息已发出给 owner" 1
fi
if echo "$out" | grep -q "ESCALATE:t_block"; then
  report "ESCALATE 消息已发出给项目经理" 0
else
  report "ESCALATE 消息已发出给项目经理" 1
fi

echo "== 3. 演示自检结论（结果: 🟢 通过）=="
if echo "$out" | grep -q "结果: 🟢 通过"; then
  report "progress_pusher.py 自检通过" 0
else
  report "progress_pusher.py 自检通过" 1
fi

echo "== 4. 协作支持编排可运行（兼容 v0.2 封装）=="
cout=$($PY collaboration_support.py 2>&1)
if echo "$cout" | grep -q "进度督导.*任务 t1 决策"; then
  report "collaboration_support.py 演示可运行" 0
else
  report "collaboration_support.py 演示可运行" 1
fi

echo "== 5. 打扰成本控制（行级评审升级点）=="
cost=$($PY - <<'PYEOF'
import time
from message_bus import MessageBus
from task_scheduler import Task, TaskQueue
from progress_pusher import ProgressPusherAgent

bus = MessageBus()
queue = TaskQueue()
pusher = ProgressPusherAgent(bus=bus, queue=queue)
pusher.boot()
now = time.time()

# 5.1 warn/push 拆分：soft 预警不消耗正式催办额度
t_near = Task(id="t_warn_many", name="预警任务", owner="dev", priority="HIGH",
              ddl=now + 3600, progress=0.9)
t_near.updated_at = now
queue.add(t_near)
for i in range(6):
    pusher.pushed_at.pop("t_warn_many", None)  # 清冷却以便连续触发
    pusher.supervise(t_near, now=now + 0.1)
warn_ok = pusher.warn_count.get("t_warn_many", 0) >= 1 and pusher.push_count.get("t_warn_many", 0) == 0
print("WARN_SPLIT=" + ("OK" if warn_ok else "BAD"))

# 5.2 ESCALATE 冷却：持续 BLOCKED 在冷却期内降级为 WARN，不重复升级
t_block = Task(id="t_block_cool", name="阻塞", owner="qa", priority="URGENT",
               ddl=now + 86400, progress=0.2)
t_block.touch("BLOCKED", "依赖缺失")
t_block.updated_at = now - 86400*2
queue.add(t_block)
pusher.scan(now=now)
first = pusher.escalate_count.get("t_block_cool", 0)
pusher.scan(now=now + 30)   # 冷却期内
second = pusher.escalate_count.get("t_block_cool", 0)
downgraded = any(d["action"] == "WARN" and d["task_id"] == "t_block_cool" for d in pusher.decisions)
esc_cool = (first == 1 and second == 1 and downgraded)
print("ESCALATE_COOLDOWN=" + ("OK" if esc_cool else "BAD"))

# 5.3 deque 滚动留痕：超出上限即裁剪
from progress_pusher import DEFAULT_POLICY
p2 = {**DEFAULT_POLICY, "max_decisions_keep": 5}
p3 = ProgressPusherAgent(bus=bus, queue=queue, policy=p2)
p3.boot()
for i in range(20):
    p3.decisions.append({"task_id": f"t{i}", "action": "WATCH"})
keep_ok = len(p3.decisions) == 5 and p3.decisions[0]["task_id"] == "t15"
print("DEQUE_KEEP=" + ("OK" if keep_ok else "BAD"))
PYEOF
)
if echo "$cost" | grep -q "WARN_SPLIT=OK"; then
  report "WARN(soft) 不消耗正式催办额度" 0
else
  report "WARN(soft) 不消耗正式催办额度" 1
fi
if echo "$cost" | grep -q "ESCALATE_COOLDOWN=OK"; then
  report "ESCALATE 冷却期内不重复升级（降级 WARN）" 0
else
  report "ESCALATE 冷却期内不重复升级（降级 WARN）" 1
fi
if echo "$cost" | grep -q "DEQUE_KEEP=OK"; then
  report "decisions 滚动留痕（防内存泄漏）" 0
else
  report "decisions 滚动留痕（防内存泄漏）" 1
fi

echo "== 6. producer 不再重复督导逾期（消除双督导）=="
pout=$($PY - <<'PYEOF'
import time
from message_bus import MessageBus
from game_producer_agent import GameProducerAgent
from task_scheduler import Task, TaskQueue

bus = MessageBus()
m = GameProducerAgent(bus=bus)
m.boot()
q = TaskQueue()
now = time.time()
t_ov = Task(id="t_overdue", name="逾期", owner="dev", ddl=now - 86400*5, progress=0.3)
t_ov.updated_at = now
q.add(t_ov)
t_blk = Task(id="t_blocked", name="阻塞", owner="dev", ddl=now + 86400, progress=0.2)
t_blk.touch("BLOCKED", "依赖缺失")
t_blk.updated_at = now - 86400*2
q.add(t_blk)
m.scheduler.queue = q
m.work_packages = [{"id": "wp_dummy"}]
m.last_heartbeat = 0
m.heartbeat()
notes = [e["note"] for e in m.log if e["event"] == "supervise"]
ok = any("t_blocked" in n for n in notes) and not any("t_overdue" in n for n in notes)
print("PRODUCER_OVERDUE_DROP=" + ("OK" if ok else "BAD"))
PYEOF
)
if echo "$pout" | grep -q "PRODUCER_OVERDUE_DROP=OK"; then
  report "producer 心跳不再督导逾期（仅阻塞/依赖级联）" 0
else
  report "producer 心跳不再督导逾期（仅阻塞/依赖级联）" 1
fi

echo ""
echo "进度督导测试结果: $pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then
  echo "🔴 阻塞：存在未通过断言"
  exit 1
fi
echo "🟢 全部通过"
exit 0

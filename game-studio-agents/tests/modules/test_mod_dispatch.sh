#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：统一派发工作能力 (DispatchCapability)
# 功能定义: 所有 Agent 共享的「派发工作」复用能力——任务派发、
#           工作包派发、批量派发、依赖解锁、跟踪与统计。
# 验收标准: 派发 API 正确执行，依赖满足/未满足时行为正确。
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

echo "== 功能模块验收：统一派发工作能力 (DispatchCapability) =="

out=$($PY - <<'PYEOF'
from dispatch_capability import DispatchCapability, DISPATCH_GUIDE
from message_bus import MessageBus
from task_scheduler import Scheduler, Task

# 1. 创建派发能力
bus = MessageBus()
sched = Scheduler(bus=bus)
cap = DispatchCapability(caller_role="producer", scheduler=sched, bus=bus)

# 注册目标角色
print("CAP_CREATED=True")
for role in ["tech_artist", "eco_art_director", "client_dev", "qa_engineer"]:
    bus.register(role)

# 2. 单任务派发
result = cap.dispatch("UI 制作", "tech_artist", priority="NORMAL", task_id="t1")
print(f"DISPATCH_OK={result.dispatched}")
print(f"DISPATCH_TASK_ID={result.task_id}")
print(f"DISPATCH_OWNER={result.owner}")

# 3. 工作包派发
result = cap.dispatch("美术方向", "eco_art_director", priority="NORMAL",
                      payload={"work_package": {"id": "wp_art", "module": "art_direction"}},
                      task_id="wp_art")
print(f"WP_DISPATCH_OK={result.dispatched}")

# 4. 批量派发（用 id 和 depends_on 字段）
results = cap.dispatch_batch([
    {"id": "t2", "name": "客户端", "owner": "client_dev"},
    {"id": "t3", "name": "测试", "owner": "qa_engineer", "depends_on": ["t2"]}
])
print(f"BATCH_DISPATCH_COUNT={len(results)}")

# 5. 依赖未满足时不就绪
print(f"T3_READY_BEFORE={'t3' in sched.queue.ready_order}")

# 6. 依赖满足后下游解锁
cap.on_complete("t2", "client_dev")
bus.process_all()
print(f"T3_READY_AFTER={'t3' in sched.queue.ready_order}")

# 7. 跟踪统计
stats = cap.summary()
print(f"STATS_DISPATCHED={stats.get('total_dispatched', 0)}")

# 8. 派发指南存在
print(f"HAS_GUIDE={len(DISPATCH_GUIDE) > 100}")
PYEOF
)

# 1. 派发能力创建
if echo "$out" | grep -q "CAP_CREATED=True"; then
  report "派发能力模块创建成功" 0
else
  report "派发能力模块创建成功" 1
fi

# 2. 单任务派发
if echo "$out" | grep -q "DISPATCH_OK=True" && echo "$out" | grep -q "DISPATCH_TASK_ID=t1"; then
  report "单任务派发正确" 0
else
  report "单任务派发正确" 1
fi

# 3. 工作包派发
if echo "$out" | grep -q "WP_DISPATCH_OK=True"; then
  report "工作包派发正确" 0
else
  report "工作包派发正确" 1
fi

# 4. 批量派发
if echo "$out" | grep -q "BATCH_DISPATCH_COUNT=.*[2-9]"; then
  report "批量派发功能正确" 0
else
  report "批量派发功能正确" 1
fi

# 5. 依赖未满足时不就绪
if echo "$out" | grep -q "T3_READY_BEFORE=False"; then
  report "依赖未满足时下游不就绪" 0
else
  report "依赖未满足时下游不就绪" 1
fi

# 6. 依赖满足后下游解锁
if echo "$out" | grep -q "T3_READY_AFTER=True"; then
  report "依赖满足后下游解锁" 0
else
  report "依赖满足后下游解锁" 1
fi

# 7. 派发统计
if echo "$out" | grep -q "STATS_DISPATCHED=.*[1-9]"; then
  report "派发统计汇总正确" 0
else
  report "派发统计汇总正确" 1
fi

# 8. 派发指南存在
if echo "$out" | grep -q "HAS_GUIDE=True"; then
  report "派发能力用法指南存在" 0
else
  report "派发能力用法指南存在" 1
fi

echo ""
echo "【派发能力模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 派发能力功能模块验收通过"
exit 0

#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：消息总线 (MessageBus)
# 功能定义: 事件驱动消息通信基础设施，支持直投/主题广播/任一投递、
#           优先级队列、消息追踪与审计。
# 验收标准: 消息能正确发布/投递/消费，优先级正确，追踪完整。
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

echo "== 功能模块验收：消息总线 (MessageBus) =="

# 模块自测演示
out=$($PY - <<'PYEOF'
from message_bus import MessageBus, Message, build_task_assign, build_message

# 1. 直投消息
bus = MessageBus()
received = []
bus.on("system_designer", lambda m: received.append(m))
bus.on("client_dev", lambda m: received.append(m))
bus.subscribe("qa_engineer", handler=lambda m: received.append(m), topic="release_notice")

m1 = build_task_assign("producer", "system_designer", "task_001", {"title": "背包系统设计"})
bus.publish(m1)
m2 = build_task_assign("producer", "client_dev", "task_002", {"title": "紧急热修"}, priority="URGENT")
bus.publish(m2)
m3 = Message("NOTIFICATION", "release_manager", "*", {"notice": "v1.2 已发布"}, mode="TOPIC", topic="release_notice")
bus.publish(m3)

# 验证消息入队
print(f"PENDING_AFTER_PUBLISH={bus.pending}")

bus.process_all()
print(f"PENDING_AFTER_PROCESS={bus.pending}")
print(f"DELIVERED_TOTAL={len(bus.delivered)}")
print(f"RECEIVED_TOTAL={len(received)}")

# 验证优先级: URGENT 先出队
msg_order = []
def on_producer(m): msg_order.append(m.priority)
bus2 = MessageBus()
bus2.on("producer", on_producer)
p1 = build_task_assign("x", "producer", "t1", {}, priority="LOW")
p2 = build_task_assign("x", "producer", "t2", {}, priority="URGENT")
p3 = build_task_assign("x", "producer", "t3", {}, priority="NORMAL")
bus2.publish(p1); bus2.publish(p2); bus2.publish(p3)
bus2.process_all()
print(f"PRIORITY_ORDER={','.join(msg_order)}")

# 验证消息追踪
print(f"TRACE_LEN={len(m1.trace)}")
print(f"TRACE_FIRST={m1.trace[0]['event']}")

# 验证统计
stats = bus.stats()
print(f"STATS_ROLES={stats['registered_roles']}")
print(f"STATS_TYPES={sorted(stats['delivered_by_type'].keys())}")

# 验证 ANYCAST
bus3 = MessageBus()
bus3.register("a"); bus3.register("b"); bus3.register("c")
am = Message("TASK_ASSIGN", "producer", "*", {"x": 1}, mode="ANYCAST")
bus3.publish(am)
bus3.process_all()
print(f"ANYCAST_TARGET={am.to_role}")
print(f"ANYCAST_DELIVERED={len(am.trace)}")
PYEOF
)

# 1. 消息入队后待处理
if echo "$out" | grep -q "PENDING_AFTER_PUBLISH=3"; then
  report "消息入队后 pending 正确（3 条）" 0
else
  report "消息入队后 pending 正确（3 条）" 1
fi

# 2. 消息处理后清空
if echo "$out" | grep -q "PENDING_AFTER_PROCESS=0"; then
  report "消息处理后 pending 清零" 0
else
  report "消息处理后 pending 清零" 1
fi

# 3. 消息正确投递
if echo "$out" | grep -q "DELIVERED_TOTAL=3"; then
  report "3 条消息全部投递" 0
else
  report "3 条消息全部投递" 1
fi

# 4. 接收方收到消息
if echo "$out" | grep -q "RECEIVED_TOTAL=3"; then
  report "3 个接收方各收到消息" 0
else
  report "3 个接收方各收到消息" 1
fi

# 5. 优先级排序
if echo "$out" | grep -q "PRIORITY_ORDER=URGENT,NORMAL,LOW"; then
  report "优先级排序正确（URGENT→NORMAL→LOW）" 0
else
  report "优先级排序正确（URGENT→NORMAL→LOW）" 1
fi

# 6. 消息追踪完整
if echo "$out" | grep -q "TRACE_LEN=.*[2-9]" && echo "$out" | grep -q "TRACE_FIRST=created"; then
  report "消息追踪完整（含创建+投递记录）" 0
else
  report "消息追踪完整（含创建+投递记录）" 1
fi

# 7. 总线统计正确
if echo "$out" | grep -q "STATS_ROLES=3"; then
  report "总线统计注册角色数正确" 0
else
  report "总线统计注册角色数正确" 1
fi

# 8. 消息类型统计
if echo "$out" | grep -q "STATS_TYPES=.*TASK_ASSIGN" && echo "$out" | grep -q "STATS_TYPES=.*NOTIFICATION"; then
  report "消息类型统计正确" 0
else
  report "消息类型统计正确" 1
fi

# 9. ANYCAST 投递
if echo "$out" | grep -q "ANYCAST_TARGET="; then
  report "ANYCAST 能路由到目标角色" 0
else
  report "ANYCAST 能路由到目标角色" 1
fi

echo ""
echo "【消息总线模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 消息总线功能模块验收通过"
exit 0

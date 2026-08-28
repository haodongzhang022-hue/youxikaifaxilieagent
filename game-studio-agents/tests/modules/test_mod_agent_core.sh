#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：Agent 内核 (BaseAgent / AgentCore)
# 功能定义: Agent 通用生命周期管理、状态机、决策引擎、
#           知识库与消息收发能力。
# 验收标准: Agent 能正确启动/接收任务/执行/交付/停止。
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

echo "== 功能模块验收：Agent 内核 (BaseAgent) =="

out=$($PY - <<'PYEOF'
from agent_core import BaseAgent
from message_bus import MessageBus, build_task_assign, build_message
from task_scheduler import Scheduler, Task

# 创建自定义 Agent 来测试
class DemoAgent(BaseAgent):
    def __init__(self, role_id, bus):
        super().__init__(role_id, bus)
        self.executed = []
    def on_boot(self):
        self.knowledge.add_doc("test", "demo")
    def handle_task(self, msg):
        self.executed.append(msg.content.get("task_id"))

bus = MessageBus()
agent = DemoAgent("demo_agent", bus)
agent.boot()

# 1. 验证生命周期
print(f"LIFECYCLE_STATE={agent.state}")

# 2. 验证知识库
print(f"KNOWLEDGE_DOCS={list(agent.knowledge.documents.keys())}")

# 3. 验证消息处理
msg = build_task_assign("producer", "demo_agent", "test_task_1", {"data": "x"})
bus.publish(msg)
bus.process_all()
print(f"EXECUTED_TASKS={agent.executed}")

# 4. 验证消息回复（交付到总线）
print(f"DELIVERED_TOTAL={len(bus.delivered)}")

# 5. 验证状态流转
print(f"FINAL_STATE={agent.state}")

# 6. 验证 LIFECYCLE_STATES 定义
from agent_core import LIFECYCLE_STATES, DEFAULT_TRANSITIONS
print(f"LIFECYCLE_COUNT={len(LIFECYCLE_STATES)}")
print(f"HAS_BOOT={'BOOT' in LIFECYCLE_STATES}")
print(f"HAS_TRANSITIONS={'IDLE' in DEFAULT_TRANSITIONS}")

# 7. 验证状态转换合法性
print(f"TRANSITION_VALID={('BOOT','IDLE') in [(s, t) for s, ts in DEFAULT_TRANSITIONS.items() for t in ts]}")

# 8. 验证知识库 add_doc / get_doc
agent.knowledge.add_doc("experience", {"level": 1})
print(f"EXPERIENCE={agent.knowledge.experience}")
print(f"HAS_EXP_DOC={'experience' in agent.knowledge.documents}")
PYEOF
)

# 1. Agent 启动进入 IDLE 状态
if echo "$out" | grep -q "LIFECYCLE_STATE=IDLE"; then
  report "Agent 启动后进入 IDLE 状态" 0
else
  report "Agent 启动后进入 IDLE 状态" 1
fi

# 2. 知识库初始化
if echo "$out" | grep -q "KNOWLEDGE_DOCS=.*test"; then
  report "知识库文档初始化成功" 0
else
  report "知识库文档初始化成功" 1
fi

# 3. Agent 处理消息
if echo "$out" | grep -q "EXECUTED_TASKS=\['test_task_1'\]"; then
  report "Agent 能接收并处理任务消息" 0
else
  report "Agent 能接收并处理任务消息" 1
fi

# 4. 消息投递到总线
if echo "$out" | grep -q "DELIVERED_TOTAL=.*[1-9]"; then
  report "Agent 消息投递到总线" 0
else
  report "Agent 消息投递到总线" 1
fi

# 5. 生命周期完整
if echo "$out" | grep -q "LIFECYCLE_COUNT=.*1[3-9]" || echo "$out" | grep -q "LIFECYCLE_COUNT=13"; then
  report "生命周期状态完整（13 种状态）" 0
else
  report "生命周期状态完整（13 种状态）" 1
fi

# 6. BOOT 状态存在
if echo "$out" | grep -q "HAS_BOOT=True"; then
  report "BOOT 生命周期状态存在" 0
else
  report "BOOT 生命周期状态存在" 1
fi

# 7. 状态转换表完整
if echo "$out" | grep -q "HAS_TRANSITIONS=True" && echo "$out" | grep -q "TRANSITION_VALID=True"; then
  report "状态转换表定义完整且合法" 0
else
  report "状态转换表定义完整且合法" 1
fi

echo ""
echo "【Agent 内核模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 Agent 内核功能模块验收通过"
exit 0

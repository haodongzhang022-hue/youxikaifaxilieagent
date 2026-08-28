#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：借鉴学习 Agent (ReferenceLearnerAgent)
# 功能定义: 从其他游戏借鉴玩法经验，以创意工坊模组（Mod）方式
#           落地到自有游戏，含探索→分析→决策→构建→验证→审核。
# 验收标准: 借鉴流程完整可执行，Mod 正确构建并提交审核。
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

echo "== 功能模块验收：借鉴学习 Agent (ReferenceLearnerAgent) =="

out=$($PY - <<'PYEOF'
from reference_learner_agent import ReferenceLearnerAgent
from message_bus import MessageBus, build_task_assign

# 1. 创建 Agent
bus = MessageBus()
agent = ReferenceLearnerAgent(bus=bus)
agent.boot()

# 2. 下发借鉴任务
msg = build_task_assign("producer", "reference_learner", "rl_001",
                        {"mechanism": "完美闪避反击循环", "game": "某动作游戏",
                         "constraints": "不要踩版权雷同的坑"})
bus.publish(msg)
bus.process_all()

# 3. 验证决策历史
print(f"DECISIONS={len(agent.decisions)}")
if agent.decisions:
    d = agent.decisions[0]
    print(f"DECISION_STRATEGY={d.get('strategy', '')}")
    print(f"DECISION_ACTION={d.get('action', '')}")

# 4. 验证 Mod 构建
print(f"MOD_COUNT={len(agent.mod_versions)}")
if agent.mod_versions:
    m = agent.mod_versions[0]
    print(f"MOD_ID={m.get('mod_id', '')}")
    print(f"MOD_STRATEGY={m.get('strategy', '')}")

# 5. 验证总线消息
print(f"BUS_MESSAGES={len(bus.delivered)}")
PYEOF
)

# 1. 借鉴决策
if echo "$out" | grep -q "DECISIONS=.*[1-9]"; then
  report "借鉴决策历史完整记录" 0
else
  report "借鉴决策历史完整记录" 1
fi

# 2. Mod 构建
if echo "$out" | grep -q "MOD_COUNT=.*[1-9]" && echo "$out" | grep -q "MOD_ID=mod_"; then
  report "创意工坊 Mod 正确构建" 0
else
  report "创意工坊 Mod 正确构建" 1
fi

# 3. 总线消息
if echo "$out" | grep -q "BUS_MESSAGES=.*[1-9]"; then
  report "借鉴 Agent 消息投递到总线" 0
else
  report "借鉴 Agent 消息投递到总线" 1
fi

# 4. 决策策略
if echo "$out" | grep -q "DECISION_STRATEGY=.*[a-z]"; then
  report "借鉴决策策略输出正确" 0
else
  report "借鉴决策策略输出正确" 1
fi

echo ""
echo "【借鉴学习模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 借鉴学习功能模块验收通过"
exit 0

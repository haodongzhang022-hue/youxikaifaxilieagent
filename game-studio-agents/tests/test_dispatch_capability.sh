#!/usr/bin/env bash
# ============================================================
# 统一派发工作能力测试信号灯（DispatchCapability）
# 说明: 验证所有 Agent 共享的「派发工作」复用能力：
#       1. DispatchCapability 独立派发 API（dispatch / dispatch_work_package /
#          dispatch_batch / on_complete / on_fail / track）；
#       2. BaseAgent 内置派发能力（dispatch / dispatch_work_package 等快捷方法）；
#       3. GameProducerAgent 复用 scheduler 的派发能力；
#       4. 依赖解锁后下游自动派发。
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

echo "== 1. DispatchCapability 独立模块演示 =="
out=$($PY dispatch_capability.py 2>&1)

# 1. 单个任务派发成功
if echo "$out" | grep -q "UI 制作 → tech_artist.*dispatched=True"; then
  report "单个任务派发（dispatch）" 0
else
  report "单个任务派发（dispatch）" 1
fi

# 2. 工作包派发成功
if echo "$out" | grep -q "生态 UI/UX 接入流水线 → eco_tech_artist dispatched=True" \
   && echo "$out" | grep -q "生态音频接入流水线 → eco_audio_designer dispatched=True"; then
  report "工作包派发（dispatch_work_package）" 0
else
  report "工作包派发（dispatch_work_package）" 1
fi

# 3. 批量派发成功
if echo "$out" | grep -q "美术品质基准 → eco_art_director dispatched=True" \
   && echo "$out" | grep -q "美术线验收回归 → qa_engineer dispatched=True"; then
  report "批量派发（dispatch_batch）" 0
else
  report "批量派发（dispatch_batch）" 1
fi

# 4. 任务状态统计
if echo "$out" | grep -q "TODO: 5"; then
  report "任务状态统计（task_stats）" 0
else
  report "任务状态统计（task_stats）" 1
fi

# 5. 依赖解锁后下游就绪
if echo "$out" | grep -q "wp_art_testing: state=TODO"; then
  report "依赖解锁后下游自动就绪" 0
else
  report "依赖解锁后下游自动就绪" 1
fi

# 6. 派发能力使用统计
if echo "$out" | grep -q "total_dispatched: 5"; then
  report "派发能力使用统计（summary）" 0
else
  report "派发能力使用统计（summary）" 1
fi

# 7. 演示通过
if echo "$out" | grep -q "🟢 通过"; then
  report "DispatchCapability 演示通过" 0
else
  report "DispatchCapability 演示通过" 1
fi

echo "== 2. BaseAgent 内置派发能力 =="
out2=$($PY -c "
import sys
sys.path.insert(0, '.')
from agent_core import BaseAgent, DemoDesigner
from message_bus import MessageBus

# 验证 BaseAgent 具备 dispatch_capability() 方法
agent = DemoDesigner('system_designer', MessageBus())
cap = agent.dispatch_capability()
assert hasattr(agent, 'dispatch'), 'BaseAgent 应具备 dispatch 方法'
assert hasattr(agent, 'dispatch_work_package'), 'BaseAgent 应具备 dispatch_work_package 方法'
assert hasattr(agent, 'dispatch_batch'), 'BaseAgent 应具备 dispatch_batch 方法'
assert hasattr(agent, 'dispatch_complete'), 'BaseAgent 应具备 dispatch_complete 方法'
assert hasattr(agent, 'dispatch_fail'), 'BaseAgent 应具备 dispatch_fail 方法'
assert hasattr(agent, 'dispatch_track'), 'BaseAgent 应具备 dispatch_track 方法'

# 验证派发能力可正常使用
agent.bus.register('qa_engineer')
agent.bus.on('qa_engineer', lambda m: None)
result = agent.dispatch('测试任务', 'qa_engineer', priority='NORMAL')
assert result.dispatched, f'派发应成功: {result.reason}'
print('BaseAgent 内置派发能力验证通过')
" 2>&1)

if echo "$out2" | grep -q "BaseAgent 内置派发能力验证通过"; then
  report "BaseAgent 内置派发能力（dispatch/dispatch_batch 等）" 0
else
  report "BaseAgent 内置派发能力（dispatch/dispatch_batch 等）" 1
  echo "    $out2"
fi

echo "== 3. GameProducerAgent 复用 scheduler 的派发能力 =="
out3=$($PY -c "
import sys
sys.path.insert(0, '.')
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus

bus = MessageBus()
manager = GameProducerAgent(bus=bus)
manager.boot()

# 验证经理的 dispatch_capability 与 self.scheduler 共享
cap = manager.dispatch_capability()
assert cap.scheduler is manager.scheduler, '经理的派发能力应复用现有 scheduler'
assert cap.bus is manager.bus, '经理的派发能力应共享 bus'

# 用统一派发能力派发一个任务
bus.register('tech_artist')
bus.on('tech_artist', lambda m: None)
result = cap.dispatch('UI 制作', 'tech_artist', priority='HIGH')
assert result.dispatched, f'经理派发应成功: {result.reason}'
assert result.owner == 'tech_artist'
assert result.priority == 'HIGH'
print('GameProducerAgent 复用 scheduler 派发能力验证通过')
" 2>&1)

if echo "$out3" | grep -q "GameProducerAgent 复用 scheduler 派发能力验证通过"; then
  report "GameProducerAgent 复用 scheduler 派发能力" 0
else
  report "GameProducerAgent 复用 scheduler 派发能力" 1
  echo "    $out3"
fi

echo "== 4. 派发能力文档 =="
if [ -f "../docs/dispatch-capability.md" ]; then
  report "派发能力文档存在（docs/dispatch-capability.md）" 0
else
  report "派发能力文档存在（docs/dispatch-capability.md）" 1
fi

if grep -q "DISPATCH_GUIDE" "../config/dispatch_capability.py" \
   && grep -q "何时派发" "../config/dispatch_capability.py"; then
  report "DISPATCH_GUIDE 用法规则定义" 0
else
  report "DISPATCH_GUIDE 用法规则定义" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 统一派发工作能力通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 统一派发工作能力存在阻塞项"
  exit 1
fi

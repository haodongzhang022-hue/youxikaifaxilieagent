#!/usr/bin/env bash
# ============================================================
# 游戏向经理 Agent 测试信号灯（护栏）
# 说明: 借鉴 dongjiagoushi 架构师 Agent 的"测试信号灯"实践，
#       对评审修复项做静态/功能断言，CI 强制校验。
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

echo "== 1. 架构蓝图消费（评审点1：inputs['architecture'] 被正确读取）=="
out=$($PY game_producer_agent.py 2>&1)
if echo "$out" | grep -q "收到架构蓝图: 开放世界动作游戏 demo"; then
  report "架构蓝图被 handle_task 正确消费" 0
else
  report "架构蓝图被 handle_task 正确消费" 1
fi
if ! echo "$out" | grep -q "未命名项目"; then
  report "不再出现『未命名项目』回退" 0
else
  report "不再出现『未命名项目』回退" 1
fi

echo "== 2. 状态机告警（评审点4：ANALYZING->IDLE 合法）=="
if ! echo "$out" | grep -q "state_fail"; then
  report "无 [state_fail] 告警" 0
else
  report "无 [state_fail] 告警" 1
fi

echo "== 3. 打回阻塞（评审点2：on_fail + queue.block 真正落地）=="
out=$($PY - <<'PYEOF'
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, build_task_assign, build_message
bus = MessageBus()
m = GameProducerAgent(role_id='game_manager', bus=bus)
m.boot()
arch = {'project': 't', 'modules': ['gameplay','client']}
bus.publish(build_task_assign('architect','game_manager','o1',{'architecture': arch}))
bus.process_all()
bus.publish(build_message('REVIEW_RESULT','qa','game_manager',
                          {'work_package_id':'wp_gameplay','approved':False,'reason':'设计不完整'}))
bus.process_all()
for t in m.scheduler.queue.tasks.values():
    if t.payload.get('work_package',{}).get('id')=='wp_gameplay':
        print('GAMEPLAY_STATE=' + t.state)
for e in m.log:
    if e['event']=='blocked':
        print('BLOCK_LOG=' + e['note'])
PYEOF
)
if echo "$out" | grep -q "GAMEPLAY_STATE=BLOCKED"; then
  report "打回后任务被标记 BLOCKED" 0
else
  report "打回后任务被标记 BLOCKED" 1
fi
if echo "$out" | grep -q "BLOCK_LOG=.*已阻塞下游"; then
  report "打回分支真正阻塞下游（非仅日志）" 0
else
  report "打回分支真正阻塞下游（非仅日志）" 1
fi

echo ""
echo "测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then
  echo "🔴 阻塞：存在未通过断言"
  exit 1
fi
echo "🟢 全部通过"
exit 0

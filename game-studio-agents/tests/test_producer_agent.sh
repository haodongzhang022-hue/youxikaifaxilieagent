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

echo "== 3. 打回阻塞（评审点2：仅 block，非 FAILED + 返工通知）=="
out=$($PY - <<'PYEOF'
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, build_task_assign, build_message
bus = MessageBus()
m = GameProducerAgent(bus=bus)   # 默认 producer（对齐 roles.yaml）
m.boot()
arch = {'project': 't', 'modules': ['gameplay','client']}
bus.publish(build_task_assign('architect', m.role_id, 'o1', {'architecture': arch}))
bus.process_all()
bus.publish(build_message('REVIEW_RESULT','qa', m.role_id,
                          {'work_package_id':'wp_gameplay','approved':False,'reason':'设计不完整'}))
bus.process_all()
for t in m.scheduler.queue.tasks.values():
    if t.payload.get('work_package',{}).get('id')=='wp_gameplay':
        print('GAMEPLAY_STATE=' + t.state)
for e in m.log:
    if e['event']=='blocked':
        print('BLOCK_LOG=' + e['note'])
print('BIZ_STATE=' + m.biz_state)
PYEOF
)
if echo "$out" | grep -q "GAMEPLAY_STATE=BLOCKED"; then
  report "打回后任务被标记 BLOCKED" 0
else
  report "打回后任务被标记 BLOCKED" 1
fi
if ! echo "$out" | grep -q "GAMEPLAY_STATE=FAILED"; then
  report "打回不再产生 FAILED 瞬时态" 0
else
  report "打回不再产生 FAILED 瞬时态" 1
fi
if echo "$out" | grep -q "BLOCK_LOG=.*已阻塞下游"; then
  report "打回分支真正阻塞下游（非仅日志）" 0
else
  report "打回分支真正阻塞下游（非仅日志）" 1
fi
if echo "$out" | grep -q "BIZ_STATE=TRACK_DEPS"; then
  report "打回后保留 TRACK_DEPS 终态（可观测）" 0
else
  report "打回后保留 TRACK_DEPS 终态（可观测）" 1
fi

echo "== 4. 岗位对齐 roles.yaml（评审点3：默认 producer）=="
out=$($PY - <<'PYEOF'
from game_producer_agent import GameProducerAgent, DEPARTMENTS
from message_bus import MessageBus
m = GameProducerAgent(bus=MessageBus())
m.boot()
print('ROLE_ID=' + m.role_id)
print('DESIGN_ROLES=' + ','.join(DEPARTMENTS['design']['roles']))
PYEOF
)
if echo "$out" | grep -q "ROLE_ID=producer"; then
  report "默认岗位对齐 producer（经理融合岗）" 0
else
  report "默认岗位对齐 producer（经理融合岗）" 1
fi
if ! echo "$out" | grep -q "DESIGN_ROLES=.*producer"; then
  report "设计部角色不含经理岗 producer（非自派单）" 0
else
  report "设计部角色不含经理岗 producer（非自派单）" 1
fi
if echo "$out" | grep -q "DESIGN_ROLES=.*lead_designer"; then
  report "设计部角色来自 roles.yaml（lead_designer）" 0
else
  report "设计部角色来自 roles.yaml（lead_designer）" 1
fi

echo "== 5. 验收保留 ACCEPT 终态（评审点2：可观测）=="
out=$($PY - <<'PYEOF'
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, build_task_assign, build_message
bus = MessageBus()
m = GameProducerAgent(bus=bus)
m.boot()
arch = {'project': 't', 'modules': ['gameplay']}
bus.publish(build_task_assign('architect', m.role_id, 'o1', {'architecture': arch}))
bus.process_all()
bus.publish(build_message('REVIEW_RESULT','qa', m.role_id,
                          {'work_package_id':'wp_gameplay','approved':True}))
bus.process_all()
print('BIZ_STATE=' + m.biz_state)
PYEOF
)
if echo "$out" | grep -q "BIZ_STATE=ACCEPT"; then
  report "验收后保留 ACCEPT 终态（可观测）" 0
else
  report "验收后保留 ACCEPT 终态（可观测）" 1
fi

echo "== 6. 依赖解锁核心机制（评审critical：上游完成→下游解锁重派发）=="
out=$($PY - <<'PYEOF'
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, build_task_assign, build_message
bus = MessageBus()
m = GameProducerAgent(bus=bus)
m.boot()
arch = {'project': 't', 'modules': ['gameplay','numeric_model','client','server']}
bus.publish(build_task_assign('architect', m.role_id, 'o1', {'architecture': arch}))
bus.process_all()
print('READY_BEFORE=' + ','.join(m.scheduler.queue.ready_order))
# 验收上游两个策划任务
for wid in ['wp_gameplay','wp_numeric_model']:
    bus.publish(build_message('REVIEW_RESULT','qa', m.role_id,
                              {'work_package_id': wid, 'approved': True}))
    bus.process_all()
print('READY_AFTER=' + ','.join(m.scheduler.queue.ready_order))
print('CLIENT_STATE=' + m.scheduler.queue.tasks['wp_client'].state)
# 下游被解锁且重新派发（ready_order 包含 wp_client）
print('CLIENT_READY=' + str('wp_client' in m.scheduler.queue.ready_order))
PYEOF
)
if echo "$out" | grep -q "READY_BEFORE=wp_gameplay,wp_numeric_model"; then
  report "验收前仅无依赖上游就绪（wp_gameplay/wp_numeric_model）" 0
else
  report "验收前仅无依赖上游就绪（wp_gameplay/wp_numeric_model）" 1
fi
if echo "$out" | grep -q "READY_AFTER=.*wp_client.*wp_server"; then
  report "验收上游后下游 wp_client/wp_server 被解锁入队" 0
else
  report "验收上游后下游 wp_client/wp_server 被解锁入队" 1
fi
if echo "$out" | grep -q "CLIENT_READY=True"; then
  report "下游解锁后重新派发（可被取出执行）" 0
else
  report "下游解锁后重新派发（可被取出执行）" 1
fi


echo "== 6b. 依赖一致性（评审warning：上游打回→级联阻塞已解锁下游）=="
out=$($PY - <<'PYEOF'
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, build_task_assign, build_message
bus = MessageBus()
m = GameProducerAgent(bus=bus)
m.boot()
arch = {'project': 't', 'modules': ['gameplay','numeric_model','client','server']}
bus.publish(build_task_assign('architect', m.role_id, 'o1', {'architecture': arch}))
bus.process_all()
# 先验收上游 -> 解锁下游 wp_client / wp_server
for wid in ['wp_gameplay','wp_numeric_model']:
    bus.publish(build_message('REVIEW_RESULT','qa', m.role_id,
                              {'work_package_id': wid, 'approved': True}))
    bus.process_all()
print('UNLOCKED_CLIENT=' + m.scheduler.queue.tasks['wp_client'].state)
# 再打回上游 wp_gameplay -> 下游应被级联重新阻塞
bus.publish(build_message('REVIEW_RESULT','qa', m.role_id,
                          {'work_package_id':'wp_gameplay','approved':False,'reason':'返工'}))
bus.process_all()
print('REBLOCK_CLIENT=' + m.scheduler.queue.tasks['wp_client'].state)
print('REBLOCK_SERVER=' + m.scheduler.queue.tasks['wp_server'].state)
for e in m.log:
    if e['event']=='cascade':
        print('CASCADE_LOG=' + e['note'])
PYEOF
)
if echo "$out" | grep -q "UNLOCKED_CLIENT=TODO"; then
  report "验收上游后下游先被解锁" 0
else
  report "验收上游后下游先被解锁 ($out)" 1
fi
if echo "$out" | grep -q "REBLOCK_CLIENT=BLOCKED"; then
  report "上游打回后代联重新阻塞下游 wp_client" 0
else
  report "上游打回后代联重新阻塞下游 wp_client ($out)" 1
fi
if echo "$out" | grep -q "REBLOCK_SERVER=BLOCKED"; then
  report "上游打回后代联重新阻塞下游 wp_server" 0
else
  report "上游打回后代联重新阻塞下游 wp_server ($out)" 1
fi
if echo "$out" | grep -q "CASCADE_LOG=.*wp_client.*wp_server"; then
  report "级联阻塞日志明确列出受影响下游" 0
else
  report "级联阻塞日志明确列出受影响下游 ($out)" 1
fi

echo "== 6c. 未知架构模块不再静默丢弃（评审info：加告警）=="
out=$($PY - <<'PYEOF'
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, build_task_assign
bus = MessageBus()
m = GameProducerAgent(bus=bus)
m.boot()
arch = {'project': 't', 'modules': ['gameplay','unknown_mod_xyz']}
bus.publish(build_task_assign('architect', m.role_id, 'o1', {'architecture': arch}))
bus.process_all()
for e in m.log:
    if e['event']=='decompose_unknown':
        print('UNKNOWN_LOG=' + e['note'])
print('WPS=' + ','.join(w['id'] for w in m.work_packages))
PYEOF
)
if echo "$out" | grep -q "UNKNOWN_LOG=.*unknown_mod_xyz.*未在 ARCHITECTURE_MODULES"; then
  report "未知模块明确告警（不再静默丢弃）" 0
else
  report "未知模块明确告警（不再静默丢弃） ($out)" 1
fi
if echo "$out" | grep -q "WPS=wp_gameplay"; then
  report "未知模块不进入工作包（仅告警）" 0
else
  report "未知模块不进入工作包（仅告警） ($out)" 1
fi



echo "== 7. 心跳督导落地（评审点4：阻塞扫描）=="
out=$($PY - <<'PYEOF'
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, build_task_assign, build_message
bus = MessageBus()
m = GameProducerAgent(bus=bus)
m.boot()
arch = {'project': 't', 'modules': ['gameplay','client']}
bus.publish(build_task_assign('architect', m.role_id, 'o1', {'architecture': arch}))
bus.process_all()
bus.publish(build_message('REVIEW_RESULT','qa', m.role_id,
                          {'work_package_id':'wp_gameplay','approved':False,'reason':'不完整'}))
bus.process_all()
m.last_heartbeat = 0
m.heartbeat()
for e in m.log:
    if e['event']=='supervise':
        print('SUPERVISE_LOG=' + e['note'])
PYEOF
)
if echo "$out" | grep -q "SUPERVISE_LOG=.*wp_gameplay.*阻塞"; then
  report "心跳扫描到阻塞并督导下游" 0
else
  report "心跳扫描到阻塞并督导下游" 1
fi


echo ""
echo "测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then
  echo "🔴 阻塞：存在未通过断言"
  exit 1
fi
echo "🟢 全部通过"
exit 0

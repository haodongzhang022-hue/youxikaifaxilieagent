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

# 3. 批量派发成功（wp_art_testing 依赖未满足应 dispatched=False —— Bug2 修复）
if echo "$out" | grep -q "美术品质基准 → eco_art_director dispatched=True" \
   && echo "$out" | grep -q "美术线验收回归 → qa_engineer dispatched=False"; then
  report "批量派发（dispatch_batch，依赖未满足不派发）" 0
else
  report "批量派发（dispatch_batch，依赖未满足不派发）" 1
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

echo "== 5. 修复项回归（4 Bug + 3 质量/架构） =="
reg=$($PY << 'REGRESSION_EOF'
import sys
sys.path.insert(0, '.')
from dispatch_capability import DispatchCapability
from message_bus import MessageBus
import io, contextlib, yaml

res = {}

# Bug1: message_id 非空
bus = MessageBus()
cap = DispatchCapability('producer', bus=bus)
bus.register('tech_artist'); bus.on('tech_artist', lambda m: None)
r1 = cap.dispatch('UI 制作', 'tech_artist')
res['bug1'] = bool(r1.message_id)

# Bug2+Bug3: 依赖未满足不派发，解锁后只派发一次
bus2 = MessageBus()
cap2 = DispatchCapability('producer', bus=bus2)
for r in ['tech_artist','qa_engineer']:
    bus2.register(r); bus2.on(r, lambda m: None)
cap2.dispatch_work_package({'id':'wp_ui_ux','label':'UI','owner':'tech_artist','depends_on':[]})
cap2.dispatch_work_package({'id':'wp_art_testing','label':'Test','owner':'qa_engineer','depends_on':['wp_ui_ux']})
n_before = len([m for m in bus2.delivered if m.type=='TASK_ASSIGN' and m.content['name']=='Test'])
res['bug2'] = (n_before == 0)
cap2.on_complete('wp_ui_ux')
n_after = len([m for m in bus2.delivered if m.type=='TASK_ASSIGN' and m.content['name']=='Test'])
res['bug3'] = (n_after == 1)

# Bug4: task_id 唯一
ids = set()
for i in range(5):
    ids.add(cap.dispatch('t'+str(i), 'tech_artist').task_id)
res['bug4'] = (len(ids) == 5)

# Quality1: 未注册角色拒绝
rg = cap.dispatch('ghost', 'ghost_role')
res['q1'] = (rg.dispatched is False)

# Quality2: demo 已注册 eco_audio_designer
import dispatch_capability
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    dispatch_capability.demo()
res['q2'] = ('生态音频接入流水线 → eco_audio_designer dispatched=True' in buf.getvalue())

# 架构: roles.yaml 含 dispatch_capability
roles = yaml.safe_load(open('roles.yaml'))
res['arch'] = ('dispatch_capability' in str(roles))

ok = all(res.values())
for k, v in res.items():
    print('  %s: %s' % (k, 'OK' if v else 'FAIL'))
print('REGRESSION_PASS' if ok else 'REGRESSION_FAIL')
REGRESSION_EOF
)

if echo "$reg" | grep -q "REGRESSION_PASS"; then
  report "修复项回归（Bug1-4 + 质量/架构）" 0
  echo "$reg"
else
  report "修复项回归（Bug1-4 + 质量/架构）" 1
  echo "$reg"
fi

echo "== 6. 评审修复回归（Critical1 + Warning2 + Warning3 + Info4） =="
reg2=$($PY << 'REGRESSION2_EOF'
import sys
sys.path.insert(0, '.')
from dispatch_capability import DispatchCapability
from message_bus import MessageBus
res = {}

# Critical 1: 返工重派发不假阳性
bus = MessageBus()
cap = DispatchCapability('producer', bus=bus)
bus.register('tech_artist'); bus.on('tech_artist', lambda m: None)
r1 = cap.dispatch('UI 制作', 'tech_artist', task_id='wp_ui')
cap.on_fail('wp_ui')
res['c1_cleanup'] = ('wp_ui' not in cap.scheduler._dispatched)
r2 = cap.dispatch('UI 制作(返工)', 'tech_artist', task_id='wp_ui')
res['c1_redispatch'] = (r2.dispatched and r2.message_id != r1.message_id)

# Warning 2: on_complete 全部依赖满足才解锁
bus2 = MessageBus()
cap2 = DispatchCapability('producer', bus=bus2)
for r in ['tech_artist','qa_engineer']:
    bus2.register(r); bus2.on(r, lambda m: None)
cap2.dispatch('B', 'tech_artist', task_id='wp_B')
cap2.dispatch('C', 'tech_artist', task_id='wp_C')
cap2.dispatch('D', 'qa_engineer', task_id='wp_D', depends_on=['wp_B','wp_C'])
unlocked1 = cap2.on_complete('wp_B')
res['w2_partial'] = ('wp_D' not in unlocked1)
unlocked2 = cap2.on_complete('wp_C')
res['w2_all'] = ('wp_D' in unlocked2)

# Warning 3: 循环依赖检测
bus3 = MessageBus()
cap3 = DispatchCapability('producer', bus=bus3)
for r in ['tech_artist','qa_engineer']:
    bus3.register(r); bus3.on(r, lambda m: None)
wps_cycle = [
    {'id':'wp_A','label':'A','owner':'tech_artist','depends_on':['wp_B']},
    {'id':'wp_B','label':'B','owner':'qa_engineer','depends_on':['wp_A']},
]
res['w3_cycle'] = all(not r.dispatched for r in cap3.dispatch_batch(wps_cycle))

# Info 4: 空 owner 拒绝
bus4 = MessageBus()
cap4 = DispatchCapability('producer', bus=bus4)
r_empty = cap4.dispatch('ghost_task', '')
res['i4_empty_owner'] = (r_empty.dispatched is False)

# 死 import 清理
import inspect
import dispatch_capability
src = inspect.getsource(dispatch_capability)
res['dead_import'] = ('build_task_assign' not in src.split('from message_bus')[1].split('\n')[0])
# 实际上检查 import 行
import_lines = [l for l in src.split('\n') if 'import' in l and 'message_bus' in l]
res['dead_import'] = (not any('build_task_assign' in l or 'build_message' in l for l in import_lines))

ok = all(res.values())
for k, v in res.items():
    print('  %s: %s' % (k, 'OK' if v else 'FAIL'))
print('REGRESSION2_PASS' if ok else 'REGRESSION2_FAIL')
REGRESSION2_EOF
)

if echo "$reg2" | grep -q "REGRESSION2_PASS"; then
  report "评审修复回归（返工重派发/多依赖解锁/循环依赖/空owner/死import）" 0
  echo "$reg2"
else
  report "评审修复回归（返工重派发/多依赖解锁/循环依赖/空owner/死import）" 1
  echo "$reg2"
fi

echo "== 部门统一头派发（dispatch_to_department）=="
out=$($PY - <<'PYBLK'
from message_bus import MessageBus
from department_agents import DesignDeptAgent
from dispatch_capability import DispatchCapability
bus = MessageBus()
d = DesignDeptAgent(bus); d.boot()
cap = DispatchCapability("producer", bus=bus)
r = cap.dispatch_to_department(
    "策划线", {"id": "wp_dd", "label": "联调", "module": "gameplay"},
    internal_assignments=[{"role": "system_designer", "desc": "系统"}],
    peer_collabs=[{"peer": "程序线", "need": "评审"}])
print("DD_OK=" + str(r.dispatched))
print("DD_OWNER=" + r.owner)
bus.process_all()
print("DD_INTERNAL=" + str("system_designer" in d.internal_subtasks.get("wp_dd", [])))
bus2 = MessageBus()
cap2 = DispatchCapability("producer", bus=bus2)
r2 = cap2.dispatch_to_department("不存在部门", {"id": "wp_no"})
print("DD_UNREG_REJECT=" + str(r2.dispatched is False))
PYBLK
)
if echo "$out" | grep -q "DD_OK=True" && echo "$out" | grep -q "DD_OWNER=策划线"; then
  report "派发到部门统一头成功（@部门名）" 0
else
  report "派发到部门统一头成功（@部门名）" 1
fi
if echo "$out" | grep -q "DD_INTERNAL=True"; then
  report "部门头消费派单后触发组内协作" 0
else
  report "部门头消费派单后触发组内协作" 1
fi
if echo "$out" | grep -q "DD_UNREG_REJECT=True"; then
  report "未注册部门名被拒绝派发（护栏）" 0
else
  report "未注册部门名被拒绝派发（护栏）" 1
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

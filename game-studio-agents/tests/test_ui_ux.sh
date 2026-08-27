#!/usr/bin/env bash
# ============================================================
# 生态 UI/UX 接入部门流水线测试信号灯（wp_ui_ux）
# 说明: 验证 wp_ui_ux（美术线·tech_artist）落地产出——
#       1. ecosystem_roles.yaml 美术圈已登记 eco_tech_artist，复用
#          ecosystem_role_registry 注册为可派发 Agent；
#       2. eco_tech_artist 可被 task_scheduler 派发（TASK_ASSIGN 到 message_bus）；
#       3. ArtDeptAgent 承接 ui_ux 工作包产出完整的 UI/UX 规范（交互/视觉/绑定）。
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

echo "== 1. 美术圈生态角色注册（eco_tech_artist 可派发） =="
out1=$($PY - <<'PYEOF'
from ecosystem_role_registry import EcosystemRoleRegistry
from task_scheduler import Scheduler, Task

registry = EcosystemRoleRegistry().load()
registered = registry.register()

# 1. eco_tech_artist 已登记为生态角色
has_role = 'eco_tech_artist' in registry.roles
# 2. 已注册到 message_bus
has_bus = 'eco_tech_artist' in registry.bus.roles

# 3. 可被 task_scheduler 派发（TASK_ASSIGN publish 到 message_bus）
sched = Scheduler(bus=registry.bus)
registry.register_scheduler(sched)
registry.dispatch(Task(id='wp_ui_ux', name='生态UI/UX', owner='eco_tech_artist', priority='HIGH'))
registry.bus.process_all()
assigns = [m for m in registry.bus.delivered
           if m.type=='TASK_ASSIGN' and m.to_role=='eco_tech_artist']

print('HAS_ROLE=', has_role)
print('HAS_BUS=', has_bus)
print('DISPATCHED=', len(assigns) > 0)
print('ASSIGN_TO=', assigns[0].to_role if assigns else '')
PYEOF
)

if echo "$out1" | grep -q "HAS_ROLE= True" && echo "$out1" | grep -q "HAS_BUS= True"; then
  report "美术圈 eco_tech_artist 已登记并注册到 message_bus" 0
else
  report "美术圈 eco_tech_artist 已登记并注册到 message_bus" 1
fi

if echo "$out1" | grep -q "DISPATCHED= True" && echo "$out1" | grep -q "ASSIGN_TO= eco_tech_artist"; then
  report "eco_tech_artist 可被 task_scheduler 派发（TASK_ASSIGN）" 0
else
  report "eco_tech_artist 可被 task_scheduler 派发（TASK_ASSIGN）" 1
fi

echo "== 2. ArtDeptAgent 承接 ui_ux 产出完整 UI/UX 规范 =="
out2=$($PY - <<'PYEOF'
from department_agents import ArtDeptAgent
from message_bus import MessageBus
agent = ArtDeptAgent(MessageBus())
agent.boot()
wp = {"module":"ui_ux","label":"生态UI/UX","project":"P",
      "id":"wp_ui_ux","department_name":"美术线"}
a = agent._execute(wp, {})
content = a.get("content", {})
print('ARTIFACT_TYPE=', a.get("artifact_type"))
print('HAS_INTERACTION=', 'interaction_spec' in content)
print('HAS_VISUAL=', 'visual_consistency' in content)
print('HAS_BINDING=', 'ui_binding' in content)
print('DISPATCHABLE_OWNER=', a.get("dispatchable_owner"))
print('DISPATCHABLE_ECO=', a.get("dispatchable_eco_owner"))
print('VERIFY=', agent._verify(wp, a)[0])
PYEOF
)

if echo "$out2" | grep -q "ARTIFACT_TYPE= ui_asset" \
   && echo "$out2" | grep -q "HAS_INTERACTION= True" \
   && echo "$out2" | grep -q "HAS_VISUAL= True"; then
  report "ArtDeptAgent 产出完整 UI/UX 规范（交互/视觉）" 0
else
  report "ArtDeptAgent 产出完整 UI/UX 规范（交互/视觉）" 1
fi

if echo "$out2" | grep -q "DISPATCHABLE_OWNER= tech_artist" \
   && echo "$out2" | grep -q "DISPATCHABLE_ECO= eco_tech_artist"; then
  report "UI/UX 产出标注可派发 owner（tech_artist / eco_tech_artist）" 0
else
  report "UI/UX 产出标注可派发 owner（tech_artist / eco_tech_artist）" 1
fi

if echo "$out2" | grep -q "VERIFY= True"; then
  report "wp_ui_ux 产出自检通过" 0
else
  report "wp_ui_ux 产出自检通过" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 生态 UI/UX 接入部门流水线通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 生态 UI/UX 接入部门流水线存在阻塞项"
  exit 1
fi

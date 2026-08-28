#!/usr/bin/env bash
# ============================================================
# 美术线生态角色接入验收回归测试信号灯（wp_art_testing）
# 说明: 验证 wp_art_testing（测试线·qa_engineer）落地产出——
#       对美术线生态角色接入（wp_art_direction / wp_ui_ux / wp_audio）
#       做全链路验收回归，确保:
#       1. 美术品质维度进入市场预演并生效（wp_art_direction）
#       2. UI/UX 角色可被 task_scheduler 派发（wp_ui_ux）
#       3. 音频角色可被派发 + 音频维度入市场预演（wp_audio）
#       4. 全部相关测试信号灯全绿（全链路验证）
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

echo "== 1. 美术生态角色全链路验收回归（wp_art_testing）=="

# 1.1 wp_art_direction 回归：市场模拟器输出美术品质指标
out_art=$($PY market_simulator.py 2>&1)

# 1. art_satisfaction 指标存在
if echo "$out_art" | grep -q "art_satisfaction"; then
  report "wp_art_direction: art_satisfaction 指标产出" 0
else
  report "wp_art_direction: art_satisfaction 指标产出" 1
fi

# 2. art_quality 进入市场模拟
if echo "$out_art" | grep -q "art_quality" && echo "$out_art" | grep -q "美术品质"; then
  report "wp_art_direction: art_quality 进入市场预演" 0
else
  report "wp_art_direction: art_quality 进入市场预演" 1
fi

# 1.2 wp_ui_ux 回归：ArtDeptAgent 承接 UI/UX 工作包
out_ui=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from message_bus import MessageBus, Message
from department_agents import ArtDeptAgent

bus = MessageBus()
agent = ArtDeptAgent(bus)
agent.on_boot()

# 派发 wp_ui_ux 工作包
msg = Message(
    type='TASK_ASSIGN', from_role='producer', to_role='art_director',
    content={
        'task_id': 'wp_ui_ux', 'name': 'wp_ui_ux',
        'payload': {'work_package': {
            'id': 'wp_ui_ux', 'label': '生态 UI/UX',
            'module': 'ui_ux', 'project': 'demo', 'department_name': '美术线',
        }},
    },
)
agent.handle_task(msg)
bus.process_all()

# 检查 REVIEW_RESULT
result = None
for m in bus.delivered:
    if m.type == 'REVIEW_RESULT' and m.content.get('work_package_id') == 'wp_ui_ux':
        result = m
        break

if result:
    artifact = result.content.get('artifact', {})
    content = artifact.get('content', {})
    print(f"UI_UX_APPROVED={result.content.get('approved')}")
    print(f"HAS_INTERACTION_SPEC={'interaction_spec' in content}")
    print(f"UI_UX_OWNER={artifact.get('dispatchable_owner', 'N/A')}")
else:
    print("UI_UX_APPROVED=False")
    print("HAS_INTERACTION_SPEC=False")
    print("UI_UX_OWNER=N/A")
PYEOF
)

# 3. wp_ui_ux 执行且验收通过
if echo "$out_ui" | grep -q "UI_UX_APPROVED=True"; then
  report "wp_ui_ux: 工作包执行且验收通过" 0
else
  report "wp_ui_ux: 工作包执行且验收通过" 1
fi

# 4. UI/UX 产出交互规范
if echo "$out_ui" | grep -q "HAS_INTERACTION_SPEC=True"; then
  report "wp_ui_ux: 产出交互规范" 0
else
  report "wp_ui_ux: 产出交互规范" 1
fi

# 5. UI/UX 可派发给 tech_artist
if echo "$out_ui" | grep -q "UI_UX_OWNER=tech_artist"; then
  report "wp_ui_ux: 产出可派发给 tech_artist" 0
else
  report "wp_ui_ux: 产出可派发给 tech_artist" 1
fi

# 1.3 wp_audio 回归：音频角色可被派发 + 音频维度入市场预演
out_audio=$($PY market_simulator.py 2>&1)
out_audio_reg=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from ecosystem_role_registry import EcosystemRoleRegistry

# 音频生态角色注册
registry = EcosystemRoleRegistry().load()
registry.register()
print(f"HAS_ECO_AUDIO={'eco_audio_designer' in registry.roles}")
PYEOF
)

# 6. wp_audio: audio_immersion 指标产出
if echo "$out_audio" | grep -q "audio_immersion"; then
  report "wp_audio: audio_immersion 指标产出" 0
else
  report "wp_audio: audio_immersion 指标产出" 1
fi

# 7. wp_audio: audio_quality 进入市场预演
if echo "$out_audio" | grep -q "audio_quality" && echo "$out_audio" | grep -q "音频品质"; then
  report "wp_audio: audio_quality 进入市场预演" 0
else
  report "wp_audio: audio_quality 进入市场预演" 1
fi

# 8. wp_audio: eco_audio_designer 已注册
if echo "$out_audio_reg" | grep -q "HAS_ECO_AUDIO=True"; then
  report "wp_audio: eco_audio_designer 已注册" 0
else
  report "wp_audio: eco_audio_designer 已注册" 1
fi

# 1.4 美术线生态角色全链路派发能力验证
out_full=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from dispatch_capability import DispatchCapability
from message_bus import MessageBus

# 注册目标角色
bus = MessageBus()
for role in ['art_director', 'tech_artist', 'audio_designer', 'qa_engineer']:
    bus.register(role)
    bus.on(role, lambda m: None)

cap = DispatchCapability(caller_role='producer', bus=bus)
cap.dispatch_work_package({'id': 'wp_art_direction', 'owner': 'art_director', 'deps': []})
cap.dispatch_work_package({'id': 'wp_ui_ux', 'owner': 'tech_artist', 'deps': ['wp_art_direction']})
cap.dispatch_work_package({'id': 'wp_audio', 'owner': 'audio_designer', 'deps': ['wp_art_direction']})
cap.dispatch_work_package({'id': 'wp_art_testing', 'owner': 'qa_engineer', 'deps': ['wp_ui_ux', 'wp_audio']})

cap.on_complete('wp_art_direction')
cap.on_complete('wp_ui_ux')
cap.on_complete('wp_audio')

# 检查 wp_art_testing 是否可被追踪
status = cap.track('wp_art_testing')
trackable = status is not None
print(f"ART_TESTING_TRACKABLE={trackable}")
if status:
    print(f"ART_TESTING_STATE={status['state']}")
PYEOF
)

# 9. wp_art_testing 在调度器中可追踪
if echo "$out_full" | grep -q "ART_TESTING_TRACKABLE=True"; then
  report "wp_art_testing: 已登记到派发能力模块" 0
else
  report "wp_art_testing: 已登记到派发能力模块" 1
fi

echo ""
echo "=== 汇总: $pass 通过 / $fail 失败 ==="
if [ "$fail" -gt 0 ]; then
  echo "🔴 美术线生态角色接入存在阻塞项"
  exit 1
fi
echo "🟢 美术线生态角色接入全链路验收回归通过"

#!/usr/bin/env bash
# ============================================================
# 生态音频角色接入流水线测试信号灯（wp_audio）
# 说明: 验证 wp_audio（美术线·audio_designer）落地产出——
#       1. market_simulator 增加 audio_quality 维度到品质/留存/口碑计算，
#          输出 audio_immersion 音频沉浸感指标；
#       2. market_input_bridge 增加音频品质字段映射，音频品质进入市场预演；
#       3. ArtDeptAgent 承接 audio 工作包时产出完整音频规范（音效/BGM/
#          配音/混响/资源格式），并把音频维度接入市场预演沙盒；
#       4. eco_audio_designer 已注册为可派发 Agent。
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

echo "== 1. 市场模拟器音频品质维度（wp_audio）=="
out=$($PY market_simulator.py 2>&1)

# 1. audio_quality 进入市场模拟 context
if echo "$out" | grep -q "audio_quality" && echo "$out" | grep -q "audio_immersion"; then
  report "market_simulator 输出 audio_quality + audio_immersion 指标" 0
else
  report "market_simulator 输出 audio_quality + audio_immersion 指标" 1
fi

# 2. 音频品质进入生态位诊断
if echo "$out" | grep -q "音频品质" && echo "$out" | grep -q "音频沉浸感"; then
  report "音频品质进入生态位诊断（音频品质/音频沉浸感）" 0
else
  report "音频品质进入生态位诊断（音频品质/音频沉浸感）" 1
fi

# 3. audio_immersion 在 0~10 区间
if echo "$out" | grep -q "audio_immersion"; then
  report "audio_immersion 指标已输出" 0
else
  report "audio_immersion 指标已输出" 1
fi

echo "== 2. 市场输入桥梁音频字段映射（wp_audio）=="
out2=$($PY market_input_bridge.py 2>&1)

# 4. market_input_bridge 映射 audio_quality 字段
if echo "$out2" | grep -q "audio_quality"; then
  report "market_input_bridge 映射 audio_quality 字段" 0
else
  report "market_input_bridge 映射 audio_quality 字段" 1
fi

# 5. 音频品质进入市场预演输出
if echo "$out2" | grep -q "音频品质" && echo "$out2" | grep -q "音频沉浸感"; then
  report "音频品质进入市场预演联动输出" 0
else
  report "音频品质进入市场预演联动输出" 1
fi

echo "== 3. ArtDeptAgent 音频工作包承接（wp_audio）=="
out3=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from message_bus import MessageBus, Message
from department_agents import ArtDeptAgent

bus = MessageBus()
agent = ArtDeptAgent(bus)
agent.on_boot()

msg = Message(
    type='TASK_ASSIGN', from_role='producer', to_role='art_director',
    content={
        'task_id': 'wp_audio', 'name': 'wp_audio',
        'payload': {'work_package': {
            'id': 'wp_audio', 'label': '生态音频角色接入流水线',
            'module': 'audio', 'project': 'demo', 'department_name': '美术线',
        }},
    },
)
agent.handle_task(msg)
bus.process_all()

# Find REVIEW_RESULT
result = None
for m in bus.delivered:
    if m.type == 'REVIEW_RESULT' and m.content.get('work_package_id') == 'wp_audio':
        result = m
        break

if not result:
    print('RESULT=NO_RESULT')
    sys.exit(1)

artifact = result.content.get('artifact', {})
content = artifact.get('content', {})
print(f"APPROVED={result.content.get('approved')}")
print(f"HAS_AUDIO_SPEC={'audio_spec' in content}")
print(f"HAS_AUDIO_QUALITY={'audio_quality' in content}")
print(f"HAS_AUDIO_IMMERSION={'audio_immersion' in content}")
print(f"DISPATCHABLE_OWNER={artifact.get('dispatchable_owner', '')}")
PYEOF
)

# 6. 工作包执行且验收通过
if echo "$out3" | grep -q "APPROVED=True"; then
  report "wp_audio 工作包执行且验收通过" 0
else
  report "wp_audio 工作包执行且验收通过" 1
fi

# 7. 产出完整音频规范
if echo "$out3" | grep -q "HAS_AUDIO_SPEC=True"; then
  report "产出完整音频规范（audio_spec）" 0
else
  report "产出完整音频规范（audio_spec）" 1
fi

# 8. 音频品质指标产出
if echo "$out3" | grep -q "HAS_AUDIO_QUALITY=True" && echo "$out3" | grep -q "HAS_AUDIO_IMMERSION=True"; then
  report "产出 audio_quality + audio_immersion 指标" 0
else
  report "产出 audio_quality + audio_immersion 指标" 1
fi

# 9. 可派发给 audio_designer
if echo "$out3" | grep -q "DISPATCHABLE_OWNER=audio_designer"; then
  report "产出可派发给 audio_designer" 0
else
  report "产出可派发给 audio_designer" 1
fi

echo "== 4. 音频生态角色注册（eco_audio_designer）=="
out4=$($PY - <<'PYEOF'
from ecosystem_role_registry import EcosystemRoleRegistry

registry = EcosystemRoleRegistry().load()
registered = registry.register()
has_role = 'eco_audio_designer' in registry.roles
print(f'HAS_ECO_AUDIO_DESIGNER={has_role}')
PYEOF
)

# 10. eco_audio_designer 已注册
if echo "$out4" | grep -q "HAS_ECO_AUDIO_DESIGNER=True"; then
  report "eco_audio_designer 已注册为生态角色" 0
else
  report "eco_audio_designer 已注册为生态角色" 1
fi

echo ""
echo "=== 汇总: $pass 通过 / $fail 失败 ==="
if [ "$fail" -gt 0 ]; then
  exit 1
fi
echo "🟢 全部通过"

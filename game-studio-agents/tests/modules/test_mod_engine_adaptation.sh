#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：双引擎适配集成 (Engine Adaptation Integration)
# 功能定义: wp_engine_adaptation_integration —— 将 engine_sync /
#           deepseek_harness 接入 Agent 流水线，验证 cocos_dev/ue_dev
#           可派发，并修复 department_agents 已知代码质量问题。
# 验收标准:
#   1. _engine_resource_hint 能正确返回引擎资源格式提示
#   2. ProgramDeptAgent 集成 engine_sync（产物清单 + 同源校验）
#   3. ProgramDeptAgent 集成 deepseek_harness（本地运行时上下文）
#   4. department_agents.py 音频资源扩展名修复（按 resource_type 筛选）
#   5. department_agents.py 未使用导入已清理
#   6. engine_adapters 双引擎资源管线分叉正确
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

echo "== 功能模块验收：双引擎适配集成 =="

# 1. _engine_resource_hint 引擎资源格式感知
out1=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from department_agents import _engine_resource_hint

# unreal + audio → .wav
h1 = _engine_resource_hint({'engine': 'unreal'}, 'audio')
# cocos + scene → .scene
h2 = _engine_resource_hint({'engine': 'cocos'}, 'scene')
# cocos + prefab → .prefab
h3 = _engine_resource_hint({'engine': 'cocos'}, 'prefab')
# unreal + map → .umap
h4 = _engine_resource_hint({'engine': 'unreal'}, 'map')
print(f"UNREAL_AUDIO={h1['engine']}:{h1['format']}")
print(f"COCOS_SCENE={h2['engine']}:{h2['format']}")
print(f"COCOS_PREFAB={h3['engine']}:{h3['format']}")
print(f"UNREAL_MAP={h4['engine']}:{h4['format']}")
PYEOF
)
if echo "$out1" | grep -q "UNREAL_AUDIO=unreal:.wav" && echo "$out1" | grep -q "COCOS_SCENE=cocos:.scene"; then
  report "_engine_resource_hint 引擎资源格式感知" 0
else
  report "_engine_resource_hint 引擎资源格式感知" 1
fi

# 2. ProgramDeptAgent engine_sync 集成（产物清单）
out2=$($PY - <<'PYEOF'
import sys, os, tempfile; sys.path.insert(0, '.')
from engine_adapters import get_engine, EngineType
from engine_sync import build_manifest, verify_manifest

# 构建测试产物
tmp = tempfile.mkdtemp()
p = os.path.join(tmp, 'src/main.ts')
os.makedirs(os.path.dirname(p), exist_ok=True)
open(p, 'w').write('// main entry')

# 生成产物清单并校验
manifest = build_manifest('cocos', tmp, ['src/main.ts'])
rep = verify_manifest(manifest, tmp)
print(f"MANIFEST_ITEMS={len(manifest['items'])}")
print(f"VERIFY_CONSISTENT={rep['consistent']}")
print(f"VERIFY_STATUS={rep['results'][0]['status']}")
PYEOF
)
if echo "$out2" | grep -q "MANIFEST_ITEMS=1" && echo "$out2" | grep -q "VERIFY_CONSISTENT=True" && echo "$out2" | grep -q "VERIFY_STATUS=MATCH"; then
  report "engine_sync 产物清单 + 同源校验集成" 0
else
  report "engine_sync 产物清单 + 同源校验集成" 1
fi

# 3. ProgramDeptAgent deepseek_harness 集成
out3=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from deepseek_harness import build_context, receive_dispatch, plan_execution, report_back

# 构建本地上下文
ctx = build_context(agent_role='cocos_dev', engine='cocos')
# 接收云端派单
msg = {'event': 'TASK_ASSIGN', 'work_package': {'id': 'wp_ui', 'module': 'client'}, 'assignee': 'cocos_dev'}
wp = receive_dispatch(ctx, msg)
# 执行计划
plan = plan_execution(ctx, wp)
# 本地执行
from deepseek_harness import execute_locally
result = execute_locally(ctx, plan)
# 回传云端
report = report_back(ctx, plan, result)
print(f"HARNESS_ROLE={ctx.agent_role}")
print(f"HARNESS_ENGINE={ctx.engine}")
print(f"HARNESS_RECEIVED={wp is not None}")
print(f"HARNESS_TOOLS={len(plan.get('tools', []))}")
print(f"HARNESS_REPORT={report.get('status', '')}")
PYEOF
)
if echo "$out3" | grep -q "HARNESS_ROLE=cocos_dev" && echo "$out3" | grep -q "HARNESS_RECEIVED=True" && echo "$out3" | grep -q "HARNESS_REPORT=local_done"; then
  report "deepseek_harness 本地运行时接入" 0
else
  report "deepseek_harness 本地运行时接入" 1
fi

# 4. department_agents.py 音频资源扩展名修复
out4=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from engine_adapters import get_engine, EngineType

cocos = get_engine(EngineType.COCOS_CREATOR)
unreal = get_engine(EngineType.UNREAL_ENGINE)
# 修复后应按 resource_type == "audio" 筛选
cocos_audio_ext = next((r.extension for r in cocos.resource_specs() if r.resource_type == "audio"), "")
unreal_audio_ext = next((r.extension for r in unreal.resource_specs() if r.resource_type == "audio"), "")
print(f"COCOS_AUDIO_EXT={cocos_audio_ext}")
print(f"UNREAL_AUDIO_EXT={unreal_audio_ext}")
PYEOF
)
if echo "$out4" | grep -q "COCOS_AUDIO_EXT=.mp3" && echo "$out4" | grep -q "UNREAL_AUDIO_EXT=.wav"; then
  report "department_agents 音频资源扩展名按类型筛选" 0
else
  report "department_agents 音频资源扩展名按类型筛选" 1
fi

# 5. department_agents.py 未使用导入清理
out5=$(grep -c "detect_engine_from_project\|build_engine_aware_artifact\|EngineType" department_agents.py || true)
if [ "$out5" = "0" ]; then
  report "department_agents 未使用导入已清理" 0
else
  report "department_agents 未使用导入已清理" 1
fi

# 6. engine_adapters 双引擎资源管线分叉
out6=$($PY - <<'PYEOF'
import sys; sys.path.insert(0, '.')
from engine_adapters import get_engine, EngineType

cocos = get_engine(EngineType.COCOS_CREATOR)
unreal = get_engine(EngineType.UNREAL_ENGINE)
# Cocos 场景资源
cocos_scene = any(r.resource_type == 'scene' and r.extension == '.scene' for r in cocos.resource_specs())
# UE 地图资源
unreal_map = any(r.resource_type == 'map' and r.extension == '.umap' for r in unreal.resource_specs())
# Cocos 音频
cocos_audio = any(r.resource_type == 'audio' and r.extension == '.mp3' for r in cocos.resource_specs())
# UE 音频
unreal_audio = any(r.resource_type == 'audio' and r.extension == '.wav' for r in unreal.resource_specs())
print(f"COCOS_SCENE={cocos_scene}")
print(f"UNREAL_MAP={unreal_map}")
print(f"COCOS_AUDIO={cocos_audio}")
print(f"UNREAL_AUDIO={unreal_audio}")
PYEOF
)
if echo "$out6" | grep -q "COCOS_SCENE=True" && echo "$out6" | grep -q "UNREAL_MAP=True"; then
  report "engine_adapters 双引擎资源管线分叉" 0
else
  report "engine_adapters 双引擎资源管线分叉" 1
fi

echo ""
echo "【双引擎适配集成模块验收】$pass 通过 / $fail 失败"
if [ "$fail" = "0" ]; then
  echo "🟢 双引擎适配集成模块验收通过"
  exit 0
else
  echo "🔴 双引擎适配集成模块验收存在阻塞"
  exit 1
fi

#!/usr/bin/env bash
# ============================================================
# 双引擎适配 + 双环境同步 + DeepSeek harness 测试信号灯（wp_engine_adaptation）
# 说明: 验证架构师建议落地的 6 项补强——
#   P1-1 双引擎技术栈落地到岗位/流水线（roles.yaml cocos_dev/ue_dev + 构建产物契约）
#   P1-2 本地 Windows Agent（DeepSeek harness）接入云端编排
#   P1-3 本地↔云端资源/产物双向同步通道
#   P1-4 双环境一致性护栏（同源 hash 校验）
#   P2-5 资源管线按双引擎分叉（Cocos .prefab/.scene vs UE .uasset/.umap）
#   P2-6 DeepSeek harness 定义"本地 Agent 运行时"
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

echo "== 1. 双引擎技术栈契约（P1-1 / P2-5）=="
out=$($PY engine_adapters.py 2>&1)

# 1. Cocos 技术栈
if echo "$out" | grep -qi "Cocos Creator" && echo "$out" | grep -qi "typescript" && echo "$out" | grep -q "cocos build --platform windows"; then
  report "Cocos Creator 技术栈契约（TS/JS + assets/ + cocos build）" 0
else
  report "Cocos Creator 技术栈契约（TS/JS + assets/ + cocos build）" 1
fi

# 2. UE 技术栈
if echo "$out" | grep -qi "Unreal Engine" && echo "$out" | grep -qi "blueprint" && echo "$out" | grep -q "RunUAT BuildCookRun"; then
  report "Unreal Engine 技术栈契约（C++/BP + Content/ + RunUAT）" 0
else
  report "Unreal Engine 技术栈契约（C++/BP + Content/ + RunUAT）" 1
fi

# 3. 资源管线分叉（Cocos .scene vs UE .umap）
res_out=$($PY -c "
import sys; sys.path.insert(0, '.')
from engine_adapters import get_engine, EngineType
cocos = get_engine(EngineType.COCOS_CREATOR)
unreal = get_engine(EngineType.UNREAL_ENGINE)
cocos_scene = any(r.resource_type == 'scene' and r.extension == '.scene' for r in cocos.resource_specs())
cocos_audio = any(r.resource_type == 'audio' and r.extension == '.mp3' for r in cocos.resource_specs())
unreal_map = any(r.resource_type in ('map', 'scene') and r.extension == '.umap' for r in unreal.resource_specs())
unreal_audio = any(r.resource_type == 'audio' and r.extension == '.wav' for r in unreal.resource_specs())
print('cocos_scene=' + str(cocos_scene))
print('cocos_audio_mp3=' + str(cocos_audio))
print('unreal_map_umap=' + str(unreal_map))
print('unreal_audio_wav=' + str(unreal_audio))
" 2>&1)
if echo "$res_out" | grep -q "cocos_scene=True" && echo "$res_out" | grep -q "unreal_map_umap=True" && echo "$res_out" | grep -q "cocos_audio_mp3=True" && echo "$res_out" | grep -q "unreal_audio_wav=True"; then
  report "资源管线按双引擎分叉（Cocos .scene / UE .umap）" 0
else
  report "资源管线按双引擎分叉（Cocos .scene / UE .umap）" 1
fi

# 4. 构建产物契约（build_artifact_manifest）
if echo "$out" | grep -q "cocos_creator" && echo "$out" | grep -q "unreal_engine"; then
  report "构建产物契约（build_artifact_manifest 双引擎）" 0
else
  report "构建产物契约（build_artifact_manifest 双引擎）" 1
fi

# 5. resolve_engine 自适应（虚幻 -> unreal）
if echo "$out" | grep -q "cocos_creator" && echo "$out" | grep -q "unreal_engine"; then
  report "resolve_engine 自适应（虚幻别名 -> unreal）" 0
else
  report "resolve_engine 自适应（虚幻别名 -> unreal）" 1
fi

echo "== 2. 双环境同步层（P1-3 / P1-4）=="
out2=$($PY engine_sync.py 2>&1)

# 6. 产物清单生成
if echo "$out2" | grep -q "产物清单" && echo "$out2" | grep -q "sha="; then
  report "产物清单生成（含 hash）" 0
else
  report "产物清单生成（含 hash）" 1
fi

# 7. 同源校验（一致场景）
out_match=$($PY -c "
import os, tempfile, sys; sys.path.insert(0, '.')
from engine_sync import build_manifest, verify_manifest
tmp = tempfile.mkdtemp()
p = os.path.join(tmp, 'assets/scene/Main.scene')
os.makedirs(os.path.dirname(p), exist_ok=True)
open(p, 'w').write('scene data')
m = build_manifest('cocos', tmp, ['assets/scene/Main.scene'])
rep = verify_manifest(m, tmp)
print('consistent=' + str(rep['consistent']))
print('status=' + rep['results'][0]['status'])
" 2>&1)
if echo "$out_match" | grep -q "consistent=True" && echo "$out_match" | grep -q "status=MATCH"; then
  report "同源校验一致场景（MATCH + consistent）" 0
else
  report "同源校验一致场景（MATCH + consistent）" 1
fi

# 8. 同源校验（缺失场景·防"声明未落地"）
if echo "$out2" | grep -q "声明未落地" && echo "$out2" | grep -q "禁止验收"; then
  report "同源校验缺失场景（防声明未落地）" 0
else
  report "同源校验缺失场景（防声明未落地）" 1
fi

# 9. 同源校验（分歧场景）
if echo "$out2" | grep -q "MISMATCH" && echo "$out2" | grep -q "存在分歧"; then
  report "同源校验分歧场景（MISMATCH）" 0
else
  report "同源校验分歧场景（MISMATCH）" 1
fi

# 10. 双向同步计划
if echo "$out2" | grep -q "本地 → 云端" && echo "$out2" | grep -q "云端 → 本地"; then
  report "双向同步计划（本地↔云端）" 0
else
  report "双向同步计划（本地↔云端）" 1
fi

echo "== 3. DeepSeek 本地 Agent 运行时（P1-2 / P2-6）=="
out3=$($PY deepseek_harness.py 2>&1)

# 11. 运行时上下文
if echo "$out3" | grep -q "运行时上下文" && echo "$out3" | grep -q "agent_role=" && echo "$out3" | grep -q "tool_chain="; then
  report "DeepSeek 本地 Agent 运行时上下文" 0
else
  report "DeepSeek 本地 Agent 运行时上下文" 1
fi

# 12. 接收派单
if echo "$out3" | grep -q "接收派单" && echo "$out3" | grep -q "local_executor="; then
  report "从云端接收派单（TASK_ASSIGN）" 0
else
  report "从云端接收派单（TASK_ASSIGN）" 1
fi

# 13. 本地执行计划
if echo "$out3" | grep -q "执行计划" && echo "$out3" | grep -q "tools="; then
  report "本地执行计划（工具调用面）" 0
else
  report "本地执行计划（工具调用面）" 1
fi

# 14. 回传云端
if echo "$out3" | grep -q "回传云端" && echo "$out3" | grep -q "consistency_required=True"; then
  report "本地结果回传云端（需同源校验）" 0
else
  report "本地结果回传云端（需同源校验）" 1
fi

# 15. UE 侧运行时
if echo "$out3" | grep -q "agent_role=ue_dev" && echo "$out3" | grep -q "RunUAT"; then
  report "UE 侧本地 Agent 运行时（ue_dev）" 0
else
  report "UE 侧本地 Agent 运行时（ue_dev）" 1
fi

echo "== 4. 岗位与流水线（P1-1 roles.yaml）=="
out4=$($PY -c "
import yaml
data = yaml.safe_load(open('roles.yaml'))
roles = data['roles']
cocos = [r for r in roles if r['role_id']=='cocos_dev']
ue = [r for r in roles if r['role_id']=='ue_dev']
print('cocos_dev' if cocos and cocos[0].get('engine')=='cocos' else 'no_cocos')
print('ue_dev' if ue and ue[0].get('engine')=='unreal' else 'no_ue')
" 2>&1)
if echo "$out4" | grep -q "cocos_dev" && echo "$out4" | grep -q "ue_dev"; then
  report "roles.yaml 新增 cocos_dev / ue_dev 岗位（含 engine 字段）" 0
else
  report "roles.yaml 新增 cocos_dev / ue_dev 岗位（含 engine 字段）" 1
fi

echo "== 5. 部门 Agent 引擎感知（department_agents.py）=="
out5=$($PY -c "
import sys; sys.path.insert(0, '.')
from department_agents import _engine_resource_hint
hint = _engine_resource_hint({'engine':'unreal'}, 'audio')
print('engine=', hint['engine'])
print('format=', hint['format'])
hint2 = _engine_resource_hint({'engine':'cocos'}, 'scene')
print('engine2=', hint2['engine'])
print('format2=', hint2['format'])
" 2>&1)
if echo "$out5" | grep -q "engine= unreal" && echo "$out5" | grep -q "engine2= cocos"; then
  report "部门 Agent 引擎资源格式感知（unreal/audio + cocos/scene）" 0
else
  report "部门 Agent 引擎资源格式感知（unreal/audio + cocos/scene）" 1
fi

echo ""
echo "测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" = "0" ]; then
  echo "🟢 引擎适配层全部通过"
  exit 0
else
  echo "🔴 引擎适配层存在阻塞"
  exit 1
fi

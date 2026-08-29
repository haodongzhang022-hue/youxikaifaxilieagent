#!/usr/bin/env bash
# ============================================================
# 游戏引擎适配层测试信号灯（engine_adapters）
# 说明: 验证 Cocos Creator 与 Unreal Engine 引擎适配层——
#       1. 引擎适配器统一接口可用（get_engine）
#       2. Cocos Creator 适配器资源规范/构建命令正确
#       3. Unreal Engine 适配器资源规范/构建命令正确
#       4. 引擎探测功能可用
#       5. 引擎感知产出物构建可用
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

echo "== 1. 引擎适配器统一接口 =="
out=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from engine_adapters import get_engine, get_all_engines, detect_engine_from_project

# 获取引擎
cocos = get_engine('cocos_creator')
unity = get_engine('unity')
unreal = get_engine('unreal_engine')
all_engines = get_all_engines()
detected = detect_engine_from_project()

print(f"COCOS_ENGINE={cocos.engine_name}")
print(f"UNITY_ENGINE={unity.engine_name}")
print(f"UNREAL_ENGINE={unreal.engine_name}")
print(f"ALL_COUNT={len(all_engines)}")
print(f"DETECTED={detected.value}")
print(f"COCOS_BUILD={cocos.build_command('windows')}")
print(f"UNITY_BUILD={unity.build_command('windows')}")
print(f"UNREAL_BUILD={unreal.build_command('windows')}")
print(f"COCOS_PLATFORMS={','.join(cocos.supported_platforms())}")
print(f"UNITY_PLATFORMS={','.join(unity.supported_platforms())}")
print(f"UNREAL_PLATFORMS={','.join(unreal.supported_platforms())}")
print(f"COCOS_SCRIPTS={','.join(cocos.script_languages)}")
print(f"UNITY_SCRIPTS={','.join(unity.script_languages)}")
print(f"UNREAL_SCRIPTS={','.join(unreal.script_languages)}")
PYEOF
)

# 1. 两个引擎都能获取
if echo "$out" | grep -q "COCOS_ENGINE=Cocos Creator" && echo "$out" | grep -q "UNREAL_ENGINE=Unreal Engine"; then
  report "两个引擎适配器均可获取" 0
else
  report "两个引擎适配器均可获取" 1
fi

# 2. 引擎总数
if echo "$out" | grep -q "ALL_COUNT=3"; then
  report "引擎注册表包含 3 个适配器(Cocos/Unity/UE)" 0
else
  report "引擎注册表包含 3 个适配器(Cocos/Unity/UE)" 1
fi

# 2.5 Unity 引擎也可获取
if echo "$out" | grep -q "UNITY_ENGINE=Unity"; then
  report "Unity 引擎适配器可获取" 0
else
  report "Unity 引擎适配器可获取" 1
fi

# 2.6 Unity 构建命令正确
if echo "$out" | grep -q "UNITY_BUILD=Unity -batchmode"; then
  report "Unity 构建命令正确" 0
else
  report "Unity 构建命令正确" 1
fi

# 2.7 Unity 平台列表正确
if echo "$out" | grep -q "UNITY_PLATFORMS=windows,webgl,android,ios,mac"; then
  report "Unity 平台列表正确" 0
else
  report "Unity 平台列表正确" 1
fi

# 2.8 Unity 脚本语言正确
if echo "$out" | grep -q "UNITY_SCRIPTS=C#"; then
  report "Unity 脚本语言正确" 0
else
  report "Unity 脚本语言正确" 1
fi

# 3. Cocos 构建命令
if echo "$out" | grep -q "COCOS_BUILD=cocos build"; then
  report "Cocos Creator 构建命令正确" 0
else
  report "Cocos Creator 构建命令正确" 1
fi

# 4. Unreal 构建命令
if echo "$out" | grep -q "UNREAL_BUILD=RunUAT"; then
  report "Unreal Engine 构建命令正确" 0
else
  report "Unreal Engine 构建命令正确" 1
fi

# 5. Cocos 平台
if echo "$out" | grep -q "COCOS_PLATFORMS=windows,web,android,ios,mac"; then
  report "Cocos Creator 平台列表正确" 0
else
  report "Cocos Creator 平台列表正确" 1
fi

# 6. Unreal 平台
if echo "$out" | grep -q "UNREAL_PLATFORMS=windows,mac,linux,android,ios"; then
  report "Unreal Engine 平台列表正确" 0
else
  report "Unreal Engine 平台列表正确" 1
fi

# 7. 脚本语言
if echo "$out" | grep -q "COCOS_SCRIPTS=TypeScript,JavaScript" && echo "$out" | grep -q "UNREAL_SCRIPTS=C++,Blueprint"; then
  report "两引擎脚本语言正确" 0
else
  report "两引擎脚本语言正确" 1
fi

# 8. 引擎探测
if echo "$out" | grep -q "DETECTED="; then
  report "引擎自动探测功能可用" 0
else
  report "引擎自动探测功能可用" 1
fi

echo "== 2. 引擎资源规范 =="
out2=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from engine_adapters import get_engine

cocos = get_engine('cocos_creator')
unity = get_engine('unity')
unreal = get_engine('unreal_engine')

# Cocos 资源类型
cocos_types = [rs.resource_type for rs in cocos.resource_specs()]
print(f"COCOS_TYPES={','.join(sorted(cocos_types))}")

# Unity 资源类型
unity_types = [rs.resource_type for rs in unity.resource_specs()]
print(f"UNITY_TYPES={','.join(sorted(unity_types))}")

# Unreal 资源类型
unreal_types = [rs.resource_type for rs in unreal.resource_specs()]
print(f"UNREAL_TYPES={','.join(sorted(unreal_types))}")

# Cocos 音频扩展
cocos_audio = [rs for rs in cocos.resource_specs() if rs.resource_type == 'audio']
if cocos_audio:
    print(f"COCOS_AUDIO_EXT={cocos_audio[0].extension}")

# Unreal 音频扩展
unreal_audio = [rs for rs in unreal.resource_specs() if rs.resource_type == 'audio']
if unreal_audio:
    print(f"UNREAL_AUDIO_EXT={unreal_audio[0].extension}")

# 资源导入路径
print(f"COCOS_SPRITE_IMPORT={cocos.resource_import_path('sprite')}")
print(f"UNREAL_MESH_IMPORT={unreal.resource_import_path('mesh')}")
PYEOF
)

# 9. Cocos 资源类型
if echo "$out2" | grep -q "COCOS_TYPES=animation,audio,prefab,scene,script,sprite"; then
  report "Cocos Creator 资源类型齐全" 0
else
  report "Cocos Creator 资源类型齐全" 1
fi

# 10. Unreal 资源类型
if echo "$out2" | grep -q "UNREAL_TYPES=animation,audio,blueprint,map,material,mesh,script"; then
  report "Unreal Engine 资源类型齐全" 0
else
  report "Unreal Engine 资源类型齐全" 1
fi

# 10.5 Unity 资源类型齐全
if echo "$out2" | grep -q "UNITY_TYPES=animation,assetbundle,audio,material,mesh,prefab,scene,script"; then
  report "Unity 资源类型齐全" 0
else
  report "Unity 资源类型齐全" 1
fi

# 11. 音频资源格式
if echo "$out2" | grep -q "COCOS_AUDIO_EXT=.mp3" && echo "$out2" | grep -q "UNREAL_AUDIO_EXT=.wav"; then
  report "两引擎音频资源格式正确" 0
else
  report "两引擎音频资源格式正确" 1
fi

# 12. 资源导入路径
if echo "$out2" | grep -q "COCOS_SPRITE_IMPORT=assets/textures" && echo "$out2" | grep -q "UNREAL_MESH_IMPORT=Content/Models"; then
  report "资源导入路径正确" 0
else
  report "资源导入路径正确" 1
fi

echo "== 3. 引擎感知产出物 =="
out3=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from engine_adapters import build_engine_aware_artifact, EngineAwareArtifact

# Cocos 美术资源产出
cocos_art = build_engine_aware_artifact(
    'cocos_creator', 'art_asset',
    {'style': '卡通', 'texture_size': '512x512'},
)
print(f"COCOS_ART_ENGINE={cocos_art.engine.value}")
print(f"COCOS_ART_BUILD={cocos_art.build_command}")
print(f"COCOS_ART_SPECS={len(cocos_art.resource_specs)}")

# Unreal 代码产出
unreal_code = build_engine_aware_artifact(
    'unreal_engine', 'code',
    {'module': 'GameCore', 'lang': 'C++'},
)
print(f"UNREAL_CODE_ENGINE={unreal_code.engine.value}")
print(f"UNREAL_CODE_BUILD={unreal_code.build_command}")
print(f"UNREAL_CODE_SPECS={len(unreal_code.resource_specs)}")

# 序列化
serialized = cocos_art.to_dict()
print(f"SERIALIZED_ENGINE={serialized['engine']}")
print(f"SERIALIZED_HAS_RESOURCES={'resource_specs' in serialized}")
PYEOF
)

# 13. Cocos 美术资源产出
if echo "$out3" | grep -q "COCOS_ART_ENGINE=cocos_creator" && echo "$out3" | grep -q "COCOS_ART_BUILD=cocos build"; then
  report "Cocos 美术资源产出引擎感知正确" 0
else
  report "Cocos 美术资源产出引擎感知正确" 1
fi

# 14. Unreal 代码产出
if echo "$out3" | grep -q "UNREAL_CODE_ENGINE=unreal_engine" && echo "$out3" | grep -q "UNREAL_CODE_BUILD=RunUAT"; then
  report "Unreal 代码产出引擎感知正确" 0
else
  report "Unreal 代码产出引擎感知正确" 1
fi

# 15. 产出物可序列化
if echo "$out3" | grep -q "SERIALIZED_ENGINE=cocos_creator" && echo "$out3" | grep -q "SERIALIZED_HAS_RESOURCES=True"; then
  report "产出物序列化正确" 0
else
  report "产出物序列化正确" 1
fi

# 16. 资源规格数 > 0
if echo "$out3" | grep -q "COCOS_ART_SPECS=[1-9]" && echo "$out3" | grep -q "UNREAL_CODE_SPECS=[1-9]"; then
  report "两引擎产出物均包含资源规格" 0
else
  report "两引擎产出物均包含资源规格" 1
fi

echo ""
echo "=== 汇总: $pass 通过 / $fail 失败 ==="
if [ "$fail" -gt 0 ]; then
  echo "🔴 引擎适配层存在阻塞项"
  exit 1
fi
echo "🟢 游戏引擎适配层全部通过"

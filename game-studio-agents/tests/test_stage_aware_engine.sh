#!/usr/bin/env bash
# ============================================================
# 四阶段感知引擎模块测试信号灯（stage_aware_engine）
# 说明: 验证 Issue #112「游戏向架构师的开发」引擎感知架构——
#       1. 四阶段枚举可用（Cocos → Unity → UE → 资产库）
#       2. 阶段选型决策正确
#       3. 阶段边界检查（阶段不对=错）功能正确
#       4. 阶段切换规则正确
#       5. 阶段感知引擎模型可用
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

echo "== 1. 四阶段感知引擎基础 =="
out=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from stage_aware_engine import (
    GameStage, StageEngineType, EngineStageSelector,
    STAGE_BOUNDARIES, get_stage_aware_engines,
)

# 阶段枚举
stages = list(GameStage)
print(f"STAGE_COUNT={len(stages)}")

# 阶段顺序
order = [s.order for s in stages]
print(f"ORDER={order}")

# 阶段标签
print(f"LABEL_1={GameStage.STAGE1_COCOS.label}")

# 阶段选型
for st in [GameStage.STAGE1_COCOS, GameStage.STAGE2_UNITY, GameStage.STAGE3_UE]:
    d = EngineStageSelector.select(st)
    print(f"SELECT_{st.order}={d['engine']}|{len(d['boundary_in'])}|{len(d['boundary_out'])}")

# 引擎对应阶段
for eng in [StageEngineType.COCOS_CREATOR, StageEngineType.UNITY, StageEngineType.UNREAL]:
    st = EngineStageSelector.get_stage_for_engine(eng)
    print(f"ENGINE_STAGE_{eng.value}={st.value if st else 'None'}")

# 阶段切换
print(f"CAN_1_TO_2={EngineStageSelector.can_transition(GameStage.STAGE1_COCOS, GameStage.STAGE2_UNITY)}")
print(f"CAN_3_TO_2={EngineStageSelector.can_transition(GameStage.STAGE3_UE, GameStage.STAGE2_UNITY)}")
print(f"NEXT_3={EngineStageSelector.next_stage(GameStage.STAGE3_UE).value if EngineStageSelector.next_stage(GameStage.STAGE3_UE) else 'None'}")

# 感知引擎模型
engines = get_stage_aware_engines()
print(f"ENGINE_COUNT={len(engines)}")
for e in engines:
    print(f"SAE_{e.engine.value}={e.stage.value}|{e.languages}")
PYEOF
)

# 1. 四阶段
if echo "$out" | grep -q "STAGE_COUNT=4"; then
  report "四阶段枚举完整" 0
else
  report "四阶段枚举完整" 1
fi

# 2. 阶段顺序
if echo "$out" | grep -q "ORDER=\[1, 2, 3, 4\]"; then
  report "阶段顺序正确(1→2→3→4)" 0
else
  report "阶段顺序正确(1→2→3→4)" 1
fi

# 3. 阶段1选型
if echo "$out" | grep -q "SELECT_1=cocos_creator|5|5"; then
  report "阶段1选型正确(Cocos Creator)" 0
else
  report "阶段1选型正确(Cocos Creator)" 1
fi

# 4. 阶段2选型
if echo "$out" | grep -q "SELECT_2=unity|5|5"; then
  report "阶段2选型正确(Unity)" 0
else
  report "阶段2选型正确(Unity)" 1
fi

# 5. 阶段3选型
if echo "$out" | grep -q "SELECT_3=unreal_engine|5|2"; then
  report "阶段3选型正确(UE)" 0
else
  report "阶段3选型正确(UE)" 1
fi

# 6. 引擎对应阶段
if echo "$out" | grep -q "ENGINE_STAGE_cocos_creator=stage1_cocos" && echo "$out" | grep -q "ENGINE_STAGE_unity=stage2_unity"; then
  report "引擎-阶段绑定正确" 0
else
  report "引擎-阶段绑定正确" 1
fi

# 7. 阶段切换规则
if echo "$out" | grep -q "CAN_1_TO_2=True" && echo "$out" | grep -q "CAN_3_TO_2=False"; then
  report "阶段切换规则正确(只能向后演进)" 0
else
  report "阶段切换规则正确(只能向后演进)" 1
fi

# 8. 感知引擎模型
if echo "$out" | grep -q "ENGINE_COUNT=3"; then
  report "感知引擎模型覆盖3引擎" 0
else
  report "感知引擎模型覆盖3引擎" 1
fi

echo "== 2. 阶段边界检查 =="
out2=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from stage_aware_engine import StageBoundaryGuard, GameStage

guard = StageBoundaryGuard()

# Cocos 阶段：合规模块
ok_cocos = guard.check('combat_turn_based', GameStage.STAGE1_COCOS)
# Cocos 阶段：越界模块（过度设计）
over_cocos = guard.check('combat_frame_sync', GameStage.STAGE1_COCOS)
# Unity 阶段：合规模块
ok_unity = guard.check('combat_real_time', GameStage.STAGE2_UNITY)
# Unity 阶段：越界模块
over_unity = guard.check('ai_behavior_tree', GameStage.STAGE2_UNITY)
# 未登记模块
unknown = guard.check('unknown_module', GameStage.STAGE1_COCOS)

print(f"OK_COCOS={ok_cocos['ok']}|{ok_cocos['action']}")
print(f"OVER_COCOS={over_cocos['ok']}|{over_cocos['action']}|{over_cocos['reason']}")
print(f"OK_UNITY={ok_unity['ok']}|{ok_unity['action']}")
print(f"OVER_UNITY={over_unity['ok']}|{over_unity['action']}")
print(f"UNKNOWN={unknown['ok']}|{unknown['action']}")
print(f"VIOLATIONS={len(guard.violations())}")
PYEOF
)

# 9. Cocos 阶段合规
if echo "$out2" | grep -q "OK_COCOS=True|ok"; then
  report "Cocos阶段合规模块通过" 0
else
  report "Cocos阶段合规模块通过" 1
fi

# 10. Cocos 阶段越界
if echo "$out2" | grep -q "OVER_COCOS=False|remove_or_defer|过度设计"; then
  report "Cocos阶段越界检测(过度设计)" 0
else
  report "Cocos阶段越界检测(过度设计)" 1
fi

# 11. Unity 阶段合规
if echo "$out2" | grep -q "OK_UNITY=True|ok"; then
  report "Unity阶段合规模块通过" 0
else
  report "Unity阶段合规模块通过" 1
fi

# 12. Unity 阶段越界
if echo "$out2" | grep -q "OVER_UNITY=False|remove_or_defer"; then
  report "Unity阶段越界检测(过度设计)" 0
else
  report "Unity阶段越界检测(过度设计)" 1
fi

# 13. 未登记模块
if echo "$out2" | grep -q "UNKNOWN=True|review_required"; then
  report "未登记模块标记审查" 0
else
  report "未登记模块标记审查" 1
fi

# 14. 越界计数
if echo "$out2" | grep -q "VIOLATIONS=2"; then
  report "越界计数正确(2项)" 0
else
  report "越界计数正确(2项)" 1
fi

echo ""
echo "=== 汇总: $pass 通过 / $fail 失败 ==="
if [ "$fail" -gt 0 ]; then
  echo "🔴 四阶段感知引擎模块存在阻塞项"
  exit 1
fi
echo "🟢 四阶段感知引擎模块全部通过"

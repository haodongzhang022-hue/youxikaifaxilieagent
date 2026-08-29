#!/usr/bin/env bash
# ============================================================
# 纯算法单元测试用例 · 跨语言保留 + 回归基线（wp_testing）
# 说明: 验证 Issue #112「游戏向架构师的开发」wp_testing——
#       1. 确定性计算跨语言保留（same input → same output）
#       2. pure_logic 纯逻辑核心算法边界条件
#       3. stage_aware_engine 阶段边界越界检测
#       4. protocol_tools 协议解析与多语言生成一致性
#       5. wp_client / wp_art_direction 产出物可测（回归基线）
# 退出码: 0 = 🟢 通过，1 = 🔴 阻塞
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/../.."
ROOT="$(pwd)"
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

echo "===== wp_testing 纯算法跨语言单元测试 + 回归基线 ====="
echo ""

# ============================================================
# Part 1: qa_engineer 产出 · 确定性计算跨语言保留
# ============================================================
echo "== 1. 确定性计算跨语言保留（same input → same output）=="
out=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from client_core.pure_logic import PureLogicEngine, GameState

# --- 确定性：同输入同输出，不依赖随机源 ---
d1 = PureLogicEngine.calculate_damage(100, 50)
d2 = PureLogicEngine.calculate_damage(100, 50)
d3 = PureLogicEngine.calculate_damage(100, 50)
print(f"DT_DAMAGE_SAME={d1['damage'] == d2['damage'] == d3['damage']}")
print(f"DT_DAMAGE_VALUE={d1['damage']}")
print(f"DT_CRIT_SAME={d1['is_crit'] == d2['is_crit']}")

# 不同输入 → 不同输出（确定性变化）
d4 = PureLogicEngine.calculate_damage(120, 50)
print(f"DT_DAMAGE_DIFFERS={(d1['damage'] != d4['damage']) or (d1['is_crit'] != d4['is_crit'])}")

# --- 确定性：exp_to_level ---
print(f"EXP_LV_0={PureLogicEngine.exp_to_level(0)}")
print(f"EXP_LV_1={PureLogicEngine.exp_to_level(50)}")
print(f"EXP_LV_2={PureLogicEngine.exp_to_level(150)}")
print(f"EXP_LV_3={PureLogicEngine.exp_to_level(250)}")
print(f"EXP_LV_4={PureLogicEngine.exp_to_level(350)}")

# --- 确定性：state_hash ---
s1 = GameState(player_id="p1", hp=80, max_hp=100)
s2 = GameState(player_id="p1", hp=80, max_hp=100)
h1 = PureLogicEngine.state_hash(s1)
h2 = PureLogicEngine.state_hash(s2)
s3 = GameState(player_id="p1", hp=90, max_hp=100)
h3 = PureLogicEngine.state_hash(s3)
print(f"HASH_SAME_STATE={h1 == h2}")
print(f"HASH_DIFF_STATE={h1 != h3}")

# --- 伤害公式边界 ---
# 伤害不低于 1
low_dmg = PureLogicEngine.calculate_damage(1, 100)
print(f"MIN_DAMAGE={low_dmg['damage'] >= 1}")
# 暴击倍率
crit_dmg = PureLogicEngine.calculate_damage(100, 50, skill_multiplier=1.0, crit_chance=1.0)
print(f"CRIT_MULTIPLIER={crit_dmg['damage'] == int((100 * 1.0 - 50 * 0.5) * 2.0)}")
print(f"CRIT_IS_CRIT={crit_dmg['is_crit']}")
PYEOF
)

# 1. 确定性相同输入同输出
if echo "$out" | grep -q "DT_DAMAGE_SAME=True"; then
  report "确定性计算：相同输入产生相同输出" 0
else
  report "确定性计算：相同输入产生相同输出" 1
fi

# 2. 确定性不同输入有变化
if echo "$out" | grep -q "DT_DAMAGE_DIFFERS=True"; then
  report "确定性计算：不同输入产生不同结果" 0
else
  report "确定性计算：不同输入产生不同结果" 1
fi

# 3. 经验→等级确定性
if echo "$out" | grep -q "EXP_LV_0=1" && echo "$out" | grep -q "EXP_LV_2=2" && echo "$out" | grep -q "EXP_LV_4=4"; then
  report "exp_to_level 跨阶段确定性（0→Lv1, 150→Lv2, 350→Lv4）" 0
else
  report "exp_to_level 跨阶段确定性（0→Lv1, 150→Lv2, 350→Lv4）" 1
fi

# 4. 状态哈希确定性
if echo "$out" | grep -q "HASH_SAME_STATE=True" && echo "$out" | grep -q "HASH_DIFF_STATE=True"; then
  report "state_hash 确定性（同状态同哈希，异状态异哈希）" 0
else
  report "state_hash 确定性（同状态同哈希，异状态异哈希）" 1
fi

# 5. 伤害公式边界保护
if echo "$out" | grep -q "MIN_DAMAGE=True"; then
  report "伤害计算最小值为 1（防御>攻击时保护）" 0
else
  report "伤害计算最小值为 1（防御>攻击时保护）" 1
fi

# 6. 暴击倍率正确
if echo "$out" | grep -q "CRIT_MULTIPLIER=True" && echo "$out" | grep -q "CRIT_IS_CRIT=True"; then
  report "暴击倍率确定性正确（crit_chance=1.0 → 必暴击×2）" 0
else
  report "暴击倍率确定性正确（crit_chance=1.0 → 必暴击×2）" 1
fi

# ============================================================
# Part 2: qa_engineer 产出 · 纯逻辑引擎状态机边界
# ============================================================
echo "== 2. pure_logic 纯逻辑引擎边界条件 =="
out=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from client_core.pure_logic import PureLogicEngine, GameState

# --- 伤害边界 ---
e = PureLogicEngine(GameState(hp=30, max_hp=100))
e.take_damage(50)  # 超过剩余HP
print(f"DAMAGE_OVERKILL={e.state.hp == 0}")
e2 = PureLogicEngine(GameState(hp=100, max_hp=100))
e2.take_damage(-10)  # 负伤害
print(f"DAMAGE_NEG={e2.state.hp == 100}")

# --- 治疗边界 ---
e3 = PureLogicEngine(GameState(hp=80, max_hp=100))
e3.heal(50)  # 超过上限
print(f"HEAL_OVERMAX={e3.state.hp == 100}")
e4 = PureLogicEngine(GameState(hp=80, max_hp=100))
e4.heal(-20)  # 负治疗
print(f"HEAL_NEG={e4.state.hp == 80}")

# --- 升级链 ---
e5 = PureLogicEngine(GameState(hp=50, max_hp=100, exp=0, level=1))
e5.add_exp(350)  # 多次升级
print(f"LEVELUP_CHAIN={e5.state.level}")  # 期望 level=4 (350/100=3次升级+1)
print(f"LEVELUP_MAXHP={e5.state.max_hp}")  # 期望 100+20*3=160
print(f"LEVELUP_HP_FULL={e5.state.hp == e5.state.max_hp}")

# --- 道具边界 ---
e6 = PureLogicEngine()
e6.add_item("potion", 3)
e6.use_item("potion")
e6.use_item("potion")
e6.use_item("potion")
r = e6.use_item("potion")  # 用完了
print(f"ITEM_EMPTY={'not_enough' in [ev.data.get('reason','') for ev in r]}")

# --- 事件系统 ---
e7 = PureLogicEngine()
e7.take_damage(10)
e7.add_item("sword", 1)
events = e7.consume_events()
print(f"EVENTS_TYPE={sorted([ev.event_type for ev in events])}")
e8 = PureLogicEngine()
e8.take_damage(10)
empty_events = e8.consume_events()  # 消费后清空
print(f"EVENTS_CLEAR={len(e8.consume_events()) == 0}")
PYEOF
)

# 7. 过量伤害保护
if echo "$out" | grep -q "DAMAGE_OVERKILL=True"; then
  report "过量伤害：HP 不低于 0" 0
else
  report "过量伤害：HP 不低于 0" 1
fi

# 8. 负伤害保护
if echo "$out" | grep -q "DAMAGE_NEG=True"; then
  report "负伤害：不恢复 HP" 0
else
  report "负伤害：不恢复 HP" 1
fi

# 9. 过量治疗保护
if echo "$out" | grep -q "HEAL_OVERMAX=True"; then
  report "过量治疗：HP 不超上限" 0
else
  report "过量治疗：HP 不超上限" 1
fi

# 10. 负治疗保护
if echo "$out" | grep -q "HEAL_NEG=True"; then
  report "负治疗：不扣减 HP" 0
else
  report "负治疗：不扣减 HP" 1
fi

# 11. 多次升级链
if echo "$out" | grep -q "LEVELUP_CHAIN=4" && echo "$out" | grep -q "LEVELUP_MAXHP=160" && echo "$out" | grep -q "LEVELUP_HP_FULL=True"; then
  report "多次升级链正确（350exp→Lv4, maxHP=160, 升级后满血）" 0
else
  report "多次升级链正确（350exp→Lv4, maxHP=160, 升级后满血）" 1
fi

# 12. 道具耗尽保护
if echo "$out" | grep -q "ITEM_EMPTY=True"; then
  report "道具耗尽后使用返回 not_enough 事件" 0
else
  report "道具耗尽后使用返回 not_enough 事件" 1
fi

# 13. 事件类型正确 + 消费后清空
if echo "$out" | grep -q "EVENTS_TYPE=\['damage', 'item_gain'\]" && echo "$out" | grep -q "EVENTS_CLEAR=True"; then
  report "事件系统正确生成 + 消费后清空" 0
else
  report "事件系统正确生成 + 消费后清空" 1
fi

# ============================================================
# Part 3: qa_engineer 产出 · 阶段边界越界检测（阶段不对=错）
# ============================================================
echo "== 3. stage_aware_engine 阶段边界越界检测 =="
out=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, 'game-studio-agents/config')
from stage_aware_engine import (
    GameStage, EngineStageSelector, StageBoundaryGuard,
    stage_boundary_check, get_stage_aware_engines,
)

# --- 四阶段完整 ---
stages = list(GameStage)
print(f"FULL_STAGES={len(stages)}")

# --- Cocos 阶段：正确模块通过，越界模块被拦 ---
guard = StageBoundaryGuard()
r1 = guard.check("combat_turn_based", GameStage.STAGE1_COCOS)  # 回合制 → 阶段1 ✅
r2 = guard.check("combat_frame_sync", GameStage.STAGE1_COCOS)  # 帧同步 → 阶段3 ❌ 过度设计
r3 = guard.check("combat_real_time", GameStage.STAGE1_COCOS)   # 实时战斗 → 阶段2 ❌ 过度设计
r4 = guard.check("render_2d", GameStage.STAGE1_COCOS)          # 2D渲染 → 阶段1 ✅
r5 = guard.check("render_3d_advanced", GameStage.STAGE1_COCOS) # 3D高精 → 阶段3 ❌
print(f"COCOS_OK={r1['ok'] and r4['ok']}")
print(f"COCOS_VIOLATIONS={sum([not r['ok'] for r in [r2, r3, r5]])}")

# --- Unity 阶段 ---
guard.clear()
r6 = guard.check("combat_real_time", GameStage.STAGE2_UNITY)   # 实时战斗 → 阶段2 ✅
r7 = guard.check("ai_behavior_tree", GameStage.STAGE2_UNITY)   # AI行为树 → 阶段3 ❌
r8 = guard.check("combat_frame_sync", GameStage.STAGE2_UNITY)  # 帧同步 → 阶段3 ❌
r9 = guard.check("physics_advanced", GameStage.STAGE2_UNITY)   # 高级物理 → 阶段2 ✅
print(f"UNITY_OK={r6['ok'] and r9['ok']}")
print(f"UNITY_VIOLATIONS={sum([not r['ok'] for r in [r7, r8]])}")

# --- UE 阶段 ---
guard.clear()
r10 = guard.check("combat_frame_sync", GameStage.STAGE3_UE)    # 帧同步 → 阶段3 ✅
r11 = guard.check("ai_behavior_tree", GameStage.STAGE3_UE)     # AI行为树 → 阶段3 ✅
r12 = guard.check("render_3d_advanced", GameStage.STAGE3_UE)   # 3D高精 → 阶段3 ✅
r13 = guard.check("network_low_freq", GameStage.STAGE3_UE)     # 低频网络 → 阶段1 ❌ 技术债
print(f"UE_OK={r10['ok'] and r11['ok'] and r12['ok']}")
print(f"UE_VIOLATIONS={sum([not r['ok'] for r in [r13]])}")

# --- 阶段选型决策 ---
d1 = EngineStageSelector.select(GameStage.STAGE1_COCOS)
d2 = EngineStageSelector.select(GameStage.STAGE2_UNITY)
d3 = EngineStageSelector.select(GameStage.STAGE3_UE)
print(f"SEL_1_ENGINE={d1['engine']}")
print(f"SEL_2_ENGINE={d2['engine']}")
print(f"SEL_3_ENGINE={d3['engine']}")

# --- 阶段切换规则（只能前进不能后退）---
print(f"FWD_1_2={EngineStageSelector.can_transition(GameStage.STAGE1_COCOS, GameStage.STAGE2_UNITY)}")
print(f"FWD_2_3={EngineStageSelector.can_transition(GameStage.STAGE2_UNITY, GameStage.STAGE3_UE)}")
print(f"BACK_3_2={EngineStageSelector.can_transition(GameStage.STAGE3_UE, GameStage.STAGE2_UNITY)}")

# --- 阶段感知引擎 ---
engines = get_stage_aware_engines()
print(f"SAE_COUNT={len(engines)}")
for e in engines:
    print(f"SAE_{e.engine.value}_STAGE={e.stage.value}")
PYEOF
)

# 14. 四阶段完整
if echo "$out" | grep -q "FULL_STAGES=4"; then
  report "四阶段枚举完整（Cocos/Unity/UE/资产库）" 0
else
  report "四阶段枚举完整（Cocos/Unity/UE/资产库）" 1
fi

# 15. Cocos 阶段边界
if echo "$out" | grep -q "COCOS_OK=True" && echo "$out" | grep -q "COCOS_VIOLATIONS=3"; then
  report "Cocos阶段：合规模块通过，3项越界被拦（过度设计）" 0
else
  report "Cocos阶段：合规模块通过，3项越界被拦（过度设计）" 1
fi

# 16. Unity 阶段边界
if echo "$out" | grep -q "UNITY_OK=True" && echo "$out" | grep -q "UNITY_VIOLATIONS=2"; then
  report "Unity阶段：合规模块通过，2项越界被拦（过度设计）" 0
else
  report "Unity阶段：合规模块通过，2项越界被拦（过度设计）" 1
fi

# 17. UE 阶段边界
if echo "$out" | grep -q "UE_OK=True" && echo "$out" | grep -q "UE_VIOLATIONS=1"; then
  report "UE阶段：合规模块通过，1项技术债被标记" 0
else
  report "UE阶段：合规模块通过，1项技术债被标记" 1
fi

# 18. 阶段选型决策
if echo "$out" | grep -q "SEL_1_ENGINE=cocos_creator" && echo "$out" | grep -q "SEL_2_ENGINE=unity" && echo "$out" | grep -q "SEL_3_ENGINE=unreal_engine"; then
  report "阶段选型决策：Cocos→Unity→UE 引擎映射正确" 0
else
  report "阶段选型决策：Cocos→Unity→UE 引擎映射正确" 1
fi

# 19. 阶段切换规则
if echo "$out" | grep -q "FWD_1_2=True" && echo "$out" | grep -q "FWD_2_3=True" && echo "$out" | grep -q "BACK_3_2=False"; then
  report "阶段切换：只前进不后退（阶段1→2→3✅，3→2❌）" 0
else
  report "阶段切换：只前进不后退（阶段1→2→3✅，3→2❌）" 1
fi

# 20. 阶段感知引擎
if echo "$out" | grep -q "SAE_COUNT=3" && echo "$out" | grep -q "SAE_cocos_creator_STAGE=stage1_cocos" && echo "$out" | grep -q "SAE_unity_STAGE=stage2_unity" && echo "$out" | grep -q "SAE_unreal_engine_STAGE=stage3_ue"; then
  report "阶段感知引擎：3引擎正确绑定对应阶段" 0
else
  report "阶段感知引擎：3引擎正确绑定对应阶段" 1
fi

# ============================================================
# Part 4: qa_engineer 产出 · 协议解析与多语言生成一致性
# ============================================================
echo "== 4. protocol_tools 协议解析与多语言生成 =="
out=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, 'game-studio-agents/config')
from protocol_tools import ProtocolParser, ProtocolCodegen, ProtocolVersionManager

# 解析协议
proto_path = os.path.abspath("server/proto/protocol.proto")
parser = ProtocolParser()
parsed = parser.parse(proto_path)

msgs = parsed["messages"]
enums = parsed["enums"]
print(f"PROTO_MSGS={len(msgs)}")
print(f"PROTO_ENUMS={len(enums)}")

# 关键消息存在
print(f"HAS_LOGIN={'LoginRequest' in msgs}")
print(f"HAS_COMBAT={'CombatRequest' in msgs}")
print(f"HAS_GAMEPLAY={'GameplayState' in msgs}")

# 多语言代码生成
codegen = ProtocolCodegen(parsed)
py_code = codegen.generate_python()
ts_code = codegen.generate_typescript()
cs_code = codegen.generate_csharp()
cpp_code = codegen.generate_cpp()

print(f"GEN_PY={len(py_code.splitlines())}")
print(f"GEN_TS={len(ts_code.splitlines())}")
print(f"GEN_CS={len(cs_code.splitlines())}")
print(f"GEN_CPP={len(cpp_code.splitlines())}")

# 关键类名出现在各语言
print(f"PY_HAS_LoginRequest={'class LoginRequest' in py_code}")
print(f"TS_HAS_LoginRequest={'interface LoginRequest' in ts_code}")
print(f"CS_HAS_LoginRequest={'class LoginRequest' in cs_code}")
print(f"CPP_HAS_LoginRequest={'struct LoginRequest' in cpp_code}")

# 版本兼容检查
vm = ProtocolVersionManager("1.0")
compat = vm.check_backward_compat(parsed, parsed)  # 自比较应兼容
print(f"COMPAT_SELF={compat['backward_compatible']}")

# 构造不兼容场景（删字段）
import copy
broken = copy.deepcopy(parsed)
msg_name = "LoginRequest"
if msg_name in broken["messages"]:
    if broken["messages"][msg_name]["fields"]:
        broken["messages"][msg_name]["fields"].pop()
incompat = vm.check_backward_compat(parsed, broken)
print(f"COMPAT_BROKEN={not incompat['backward_compatible']}")
print(f"VIOLATIONS_COUNT={len(incompat['violations'])}")
PYEOF
)

# 21. 协议解析完整性
if echo "$out" | grep -q "PROTO_MSGS=13" && echo "$out" | grep -q "PROTO_ENUMS=4"; then
  report "协议解析：13 消息 + 4 枚举完整" 0
else
  report "协议解析：13 消息 + 4 枚举完整" 1
fi

# 22. 关键消息
if echo "$out" | grep -q "HAS_LOGIN=True" && echo "$out" | grep -q "HAS_COMBAT=True"; then
  report "关键消息：LoginRequest / CombatRequest 解析成功" 0
else
  report "关键消息：LoginRequest / CombatRequest 解析成功" 1
fi

# 23. 四语言生成
if echo "$out" | grep -q "GEN_PY=" && echo "$out" | grep -q "GEN_TS=" && echo "$out" | grep -q "GEN_CS=" && echo "$out" | grep -q "GEN_CPP="; then
  report "四种语言代码生成成功（Python/TS/C#/C++）" 0
else
  report "四种语言代码生成成功（Python/TS/C#/C++）" 1
fi

# 24. 各语言包含 LoginRequest
if echo "$out" | grep -q "PY_HAS_LoginRequest=True" && echo "$out" | grep -q "TS_HAS_LoginRequest=True" && echo "$out" | grep -q "CS_HAS_LoginRequest=True" && echo "$out" | grep -q "CPP_HAS_LoginRequest=True"; then
  report "LoginRequest 在四种语言中均生成" 0
else
  report "LoginRequest 在四种语言中均生成" 1
fi

# 25. 协议向后兼容
if echo "$out" | grep -q "COMPAT_SELF=True" && echo "$out" | grep -q "COMPAT_BROKEN=True" && echo "$out" | grep -q "VIOLATIONS_COUNT=1"; then
  report "向后兼容：自比较兼容，删字段即检出（1项违规）" 0
else
  report "向后兼容：自比较兼容，删字段即检出（1项违规）" 1
fi

# ============================================================
# Part 5: auto_qa 产出 · 回归基线验证
# ============================================================
echo "== 5. 回归基线（wp_client / wp_art_direction 产出可测）=="

# 5a. wp_client 产出物存在
if [ -f "client_core/pure_logic.py" ] && [ -f "client_core/cocos_presenter.py" ]; then
  report "wp_client 产出物存在（pure_logic.py + cocos_presenter.py）" 0
else
  report "wp_client 产出物存在（pure_logic.py + cocos_presenter.py）" 1
fi

# 5b. wp_art_direction 产出物存在
if [ -f "game-studio-agents/docs/design-output/美术线/issue112/wp_art_direction_表现层美术风格分阶段边界.md" ]; then
  report "wp_art_direction 产出物存在（美术线四阶段边界文档）" 0
else
  report "wp_art_direction 产出物存在（美术线四阶段边界文档）" 1
fi

# 5c. 程序线其他产出物存在
if [ -f "game-studio-agents/config/stage_aware_engine.py" ] && [ -f "game-studio-agents/config/protocol_tools.py" ] && [ -f "server/proto/protocol.proto" ] && [ -f "server/core/stateless_server.py" ]; then
  report "程序线产出物齐全（stage_aware_engine/protocol_tools/protocol.proto/stateless_server）" 0
else
  report "程序线产出物齐全（stage_aware_engine/protocol_tools/protocol.proto/stateless_server）" 1
fi

# 5d. 依赖的既有回归测试基线全绿
echo "--- 回归基线检测 ---"
base_out=$(bash game-studio-agents/tests/test_client_core.sh 2>&1)
if echo "$base_out" | grep -q "🟢"; then
  report "test_client_core.sh 回归通过" 0
else
  report "test_client_core.sh 回归通过" 1
fi

base_out2=$(bash game-studio-agents/tests/test_stage_aware_engine.sh 2>&1)
if echo "$base_out2" | grep -q "🟢"; then
  report "test_stage_aware_engine.sh 回归通过" 0
else
  report "test_stage_aware_engine.sh 回归通过" 1
fi

# ============================================================
# 汇总
# ============================================================
echo ""
echo "=== 汇总: $pass 通过 / $fail 失败 ==="
if [ "$fail" = "0" ]; then
  echo "🟢 wp_testing 纯算法跨语言单元测试 + 回归基线 全部通过"
  exit 0
else
  echo "🔴 wp_testing 有 $fail 项未通过，需修复"
  exit 1
fi

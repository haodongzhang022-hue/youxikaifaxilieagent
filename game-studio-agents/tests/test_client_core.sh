#!/usr/bin/env bash
# ============================================================
# 客户端纯逻辑类库测试信号灯（client_core）
# 说明: 验证 Issue #112「游戏向架构师的开发」wp_client——
#       1. 纯逻辑类库可用（状态管理/战斗结算/道具）
#       2. 确定性计算（跨语言翻译基础）
#       3. 逻辑/表现分离（事件驱动 + 表现层适配）
#       4. Cocos 表现层适配器可用
# 退出码: 0 = 🟢 通过，1 = 🔴 阻塞
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/../.."
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

echo "== 1. 纯逻辑类库 =="
out=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from client_core.pure_logic import PureLogicEngine, GameState, LogicEvent, IPresentationAdapter

# 创建引擎
engine = PureLogicEngine()

# 状态管理
engine.take_damage(30)
print(f"HP_AFTER_DAMAGE={engine.state.hp}")

engine.heal(20)
print(f"HP_AFTER_HEAL={engine.state.hp}")

engine.add_exp(150)
print(f"LEVEL={engine.state.level}")
print(f"EXP={engine.state.exp}")

engine.add_item("potion", 3)
engine.use_item("potion")
print(f"POTION={engine.state.inventory.get('potion', 0)}")

# 确定性计算
dmg1 = PureLogicEngine.calculate_damage(100, 50)
dmg2 = PureLogicEngine.calculate_damage(100, 50)
print(f"DAMAGE_DETERMINISTIC={dmg1['damage'] == dmg2['damage']}")
print(f"DAMAGE_VALUE={dmg1['damage']}")

# 事件队列
events = engine.consume_events()
print(f"EVENT_COUNT={len(events)}")
print(f"EVENT_TYPES={','.join(ev.event_type for ev in events)}")

# 序列化
state_dict = engine.state.to_dict()
print(f"STATE_HAS_HP={'hp' in state_dict}")
print(f"STATE_HAS_LEVEL={'level' in state_dict}")
PYEOF
)

# 1. 伤害计算
if echo "$out" | grep -q "HP_AFTER_DAMAGE=70"; then
  report "伤害计算正确" 0
else
  report "伤害计算正确" 1
fi

# 2. 治疗
if echo "$out" | grep -q "HP_AFTER_HEAL=90"; then
  report "治疗计算正确" 0
else
  report "治疗计算正确" 1
fi

# 3. 经验升级
if echo "$out" | grep -q "LEVEL=2" && echo "$out" | grep -q "EXP=50"; then
  report "经验/升级逻辑正确" 0
else
  report "经验/升级逻辑正确" 1
fi

# 4. 道具管理
if echo "$out" | grep -q "POTION=2"; then
  report "道具管理正确" 0
else
  report "道具管理正确" 1
fi

# 5. 确定性计算
if echo "$out" | grep -q "DAMAGE_DETERMINISTIC=True" && echo "$out" | grep -q "DAMAGE_VALUE=75"; then
  report "确定性伤害计算(跨语言基础)" 0
else
  report "确定性伤害计算(跨语言基础)" 1
fi

# 6. 事件系统
if echo "$out" | grep -q "EVENT_COUNT=6" && echo "$out" | grep -q "EVENT_TYPES=damage,heal,exp_gain,level_up,item_gain,item_use"; then
  report "事件系统生成正确" 0
else
  report "事件系统生成正确" 1
fi

# 7. 状态序列化
if echo "$out" | grep -q "STATE_HAS_HP=True" && echo "$out" | grep -q "STATE_HAS_LEVEL=True"; then
  report "状态序列化(跨语言传输)" 0
else
  report "状态序列化(跨语言传输)" 1
fi

echo "== 2. Cocos 表现层适配 =="
out2=$($PY - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from client_core.pure_logic import PureLogicEngine
from client_core.cocos_presenter import CocosPresenter

engine = PureLogicEngine()
presenter = CocosPresenter(engine)

# 初始化
print(f"INIT={presenter.init()}")

# 逻辑操作
engine.take_damage(30)
engine.add_exp(120)
engine.add_item("potion", 2)

# 消费事件并渲染
events = engine.consume_events()
for ev in events:
    presenter.on_logic_event(ev)
presenter.render_state(engine.state)

# 检查渲染日志
log = presenter.render_log()
print(f"LOG_COUNT={len(log)}")
print(f"HAS_DAMAGE={any('damage' in l for l in log)}")
print(f"HAS_LEVEL_UP={any('level_up' in l for l in log)}")
print(f"HAS_ITEM={any('item_gain' in l for l in log)}")
print(f"HAS_STATE={any('渲染状态' in l for l in log)}")
PYEOF
)

# 8. 表现层初始化
if echo "$out2" | grep -q "INIT=True"; then
  report "Cocos 表现层初始化" 0
else
  report "Cocos 表现层初始化" 1
fi

# 9. 事件→表现映射
if echo "$out2" | grep -q "LOG_COUNT=5" && echo "$out2" | grep -q "HAS_DAMAGE=True"; then
  report "逻辑事件→表现层映射" 0
else
  report "逻辑事件→表现层映射" 1
fi

# 10. 升级渲染
if echo "$out2" | grep -q "HAS_LEVEL_UP=True"; then
  report "升级特效渲染触发" 0
else
  report "升级特效渲染触发" 1
fi

# 11. 道具渲染
if echo "$out2" | grep -q "HAS_ITEM=True"; then
  report "道具获得渲染触发" 0
else
  report "道具获得渲染触发" 1
fi

# 12. 状态渲染
if echo "$out2" | grep -q "HAS_STATE=True"; then
  report "状态渲染触发" 0
else
  report "状态渲染触发" 1
fi

echo ""
echo "=== 汇总: $pass 通过 / $fail 失败 ==="
if [ "$fail" -gt 0 ]; then
  echo "🔴 客户端纯逻辑类库存在阻塞项"
  exit 1
fi
echo "🟢 客户端纯逻辑类库全部通过"

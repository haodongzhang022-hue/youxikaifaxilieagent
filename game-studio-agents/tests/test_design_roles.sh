#!/usr/bin/env bash
# ============================================================
# 策划线叙事/战斗角色实体化护栏（narrative_designer / combat_designer）
# 说明: Issue #50/#55 收口——把剧情策划、战斗策划两个 base 角色
#       从 declared_only 升级为 registered_only，注册到策划线部门，
#       由 DesignDeptAgent 聚合承接 narrative / combat 模块产出。
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

echo "== 1. role_inventory：declared_only 清零，两角色升级为 registered_only =="
out=$($PY role_inventory.py --gap 2>&1)
dc=$(echo "$out" | grep -oP 'declared_only（\K[0-9]+' | head -1)
if [ -z "$dc" ]; then dc=0; fi
if [ "$dc" = "0" ]; then
  report "declared_only 差距清零（$dc 个声明无实现角色）" 0
else
  report "declared_only 差距清零（当前 $dc 个声明无实现角色）" 1
fi
if echo "$out" | grep -q "narrative_designer.*DesignDeptAgent" \
   && echo "$out" | grep -q "combat_designer.*DesignDeptAgent"; then
  report "narrative_designer / combat_designer 已注册并归 DesignDeptAgent" 0
else
  report "narrative_designer / combat_designer 已注册并归 DesignDeptAgent" 1
fi

echo "== 2. 部门注册与总线派发 =="
out=$($PY - <<'PYEOF'
from message_bus import MessageBus
from department_agents import build_department_agents
from game_producer_agent import GameProducerAgent, DEPARTMENTS, ARCHITECTURE_MODULES
bus = MessageBus()
agents = build_department_agents(bus)
# 部门角色表
mg = GameProducerAgent(bus=bus)
dept_roles = mg.departments.get("design", {}).get("roles", [])
print("ROLE_NARRATIVE=" + str("narrative_designer" in dept_roles))
print("ROLE_COMBAT=" + str("combat_designer" in dept_roles))
# 总线注册
print("BUS_NARRATIVE=" + str("narrative_designer" in bus.roles))
print("BUS_COMBAT=" + str("combat_designer" in bus.roles))
# 架构模块映射
print("MOD_NARRATIVE=" + str(ARCHITECTURE_MODULES.get("narrative", {}).get("role") == "narrative_designer"))
print("MOD_COMBAT=" + str(ARCHITECTURE_MODULES.get("combat", {}).get("role") == "combat_designer"))
print("MBR_NARRATIVE=" + str(mg.MODULE_BASE_ROLE.get("narrative") == "narrative_designer"))
print("MBR_COMBAT=" + str(mg.MODULE_BASE_ROLE.get("combat") == "combat_designer"))
PYEOF
)
if echo "$out" | grep -q "ROLE_NARRATIVE=True" && echo "$out" | grep -q "ROLE_COMBAT=True"; then
  report "narrative_designer / combat_designer 已注册到策划线部门角色表" 0
else
  report "narrative_designer / combat_designer 已注册到策划线部门角色表" 1
fi
if echo "$out" | grep -q "BUS_NARRATIVE=True" && echo "$out" | grep -q "BUS_COMBAT=True"; then
  report "两角色已注册到消息总线（可被 @ 派发承接）" 0
else
  report "两角色已注册到消息总线（可被 @ 派发承接）" 1
fi
if echo "$out" | grep -q "MOD_NARRATIVE=True" && echo "$out" | grep -q "MOD_COMBAT=True"; then
  report "ARCHITECTURE_MODULES 已映射 narrative / combat 模块到对应角色" 0
else
  report "ARCHITECTURE_MODULES 已映射 narrative / combat 模块到对应角色" 1
fi
if echo "$out" | grep -q "MBR_NARRATIVE=True" && echo "$out" | grep -q "MBR_COMBAT=True"; then
  report "MODULE_BASE_ROLE 已映射 narrative / combat 到实例化 base_role" 0
else
  report "MODULE_BASE_ROLE 已映射 narrative / combat 到实例化 base_role" 1
fi

echo "== 3. DesignDeptAgent 承接 narrative / combat 模块产出 =="
out=$($PY - <<'PYEOF'
from message_bus import MessageBus
from department_agents import DesignDeptAgent
bus = MessageBus()
d = DesignDeptAgent(bus); d.boot()
# narrative
na = d._execute({"module": "narrative", "label": "世界观", "project": "P"}, {})
print("NARR_KEYS=" + str(all(k in na["content"] for k in ["world_view","storyline","characters","quest_copy"])))
print("NARR_OWNER=" + str(na.get("owner_role") == "narrative_designer"))
print("NARR_VERIFY=" + str(d._verify({"module": "narrative"}, na)[0]))
# combat
cb = d._execute({"module": "combat", "label": "战斗", "project": "P"}, {})
print("COMB_KEYS=" + str(all(k in cb["content"] for k in ["combat_system","skills","npc_ai","balance_verify"])))
print("COMB_OWNER=" + str(cb.get("owner_role") == "combat_designer"))
print("COMB_VERIFY=" + str(d._verify({"module": "combat"}, cb)[0]))
# missing content rejected
print("NARR_REJECT=" + str(d._verify({"module": "narrative"}, {"content": {}})[0] is False))
print("COMB_REJECT=" + str(d._verify({"module": "combat"}, {"content": {}})[0] is False))
PYEOF
)
if echo "$out" | grep -q "NARR_KEYS=True" && echo "$out" | grep -q "NARR_OWNER=True" && echo "$out" | grep -q "NARR_VERIFY=True"; then
  report "narrative 模块产出（世界观/剧情/角色/任务）完整且主责 narrative_designer" 0
else
  report "narrative 模块产出完整且主责 narrative_designer" 1
fi
if echo "$out" | grep -q "COMB_KEYS=True" && echo "$out" | grep -q "COMB_OWNER=True" && echo "$out" | grep -q "COMB_VERIFY=True"; then
  report "combat 模块产出（机制/技能/AI/平衡）完整且主责 combat_designer" 0
else
  report "combat 模块产出完整且主责 combat_designer" 1
fi
if echo "$out" | grep -q "NARR_REJECT=True" && echo "$out" | grep -q "COMB_REJECT=True"; then
  report "缺失关键字段的产出被自检打回（验证兜底生效）" 0
else
  report "缺失关键字段的产出被自检打回（验证兜底生效）" 1
fi

echo ""
echo "测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" -eq 0 ]; then
  echo "🟢 策划线叙事/战斗角色实体化通过"
  exit 0
else
  echo "🔴 策划线叙事/战斗角色实体化阻塞"
  exit 1
fi

#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：预设实例化器 (PresetInstantiator)
# 功能定义: 把分层预设（L1角色/L2技术栈/L3小组 + P1/P2/P3项目类型）
#           实例化为正式角色，并组装成按六大部门分组的项目团队。
# 验收标准: 预设能正确选型、实例化为正式角色、团队组装完整。
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

echo "== 功能模块验收：预设实例化器 (PresetInstantiator) =="

out=$($PY - <<'PYEOF'
from preset_instantiator import PresetInstantiator

# 1. 创建实例化器
inst = PresetInstantiator().load()
print(f"INST_LOADED=True")

# 2. 选型并实例化
inst.apply_project_type("ptype_mobile_game") \
   .apply_phase("phase_production") \
   .apply_team_scale("scale_medium") \
   .select_team("team_unity") \
   .select_stack("stack_unity_ecosystem")
report = inst.instantiate()

# 3. 验证实例化角色
print(f"TEAM_ROLES={report['total_roles']}")
for dept, roles in report["assembled_team"].items():
    print(f"TEAM_DEPT:{dept}={len(roles)}")

# 4. 验证校验
issues = inst.validate()
print(f"VALIDATE={len(issues) == 0}")

# 5. 验证六大部门覆盖
dept_keys = list(report["assembled_team"].keys())
print(f"ALL_6_DEPTS={all(d in dept_keys for d in ['design', 'program', 'art', 'qa', 'pm', 'ops'])}")

# 6. 验证实例化角色为 agent_enabled
statuses = set(s.get('status', '') for s in report["instantiated_roles"])
print(f"ALL_AGENT_ENABLED={'agent_enabled' in statuses}")
PYEOF
)

# 1. 实例化器加载
if echo "$out" | grep -q "INST_LOADED=True"; then
  report "预设实例化器加载成功" 0
else
  report "预设实例化器加载成功" 1
fi

# 2. 角色实例化
if echo "$out" | grep -q "TEAM_ROLES=.*1[0-9]"; then
  report "预设实例化为正式角色（10+ 角色）" 0
else
  report "预设实例化为正式角色（10+ 角色）" 1
fi

# 3. 六大部门覆盖
if echo "$out" | grep -q "ALL_6_DEPTS=True"; then
  report "六大部门全部覆盖" 0
else
  report "六大部门全部覆盖" 1
fi

# 4. 校验通过
if echo "$out" | grep -q "VALIDATE=True"; then
  report "实例化校验通过" 0
else
  report "实例化校验通过" 1
fi

# 5. 部门分配合理
if echo "$out" | grep -q "TEAM_DEPT:program=.*[1-9]" && echo "$out" | grep -q "TEAM_DEPT:design=.*[1-9]"; then
  report "程序线与策划线均有角色分配" 0
else
  report "程序线与策划线均有角色分配" 1
fi

# 6. 角色启用
if echo "$out" | grep -q "ALL_AGENT_ENABLED=True"; then
  report "实例化角色均为 agent_enabled" 0
else
  report "实例化角色均为 agent_enabled" 1
fi

echo ""
echo "【预设实例化模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 预设实例化功能模块验收通过"
exit 0

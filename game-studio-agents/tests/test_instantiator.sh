# ============================================================
# 预设实例化器测试信号灯（v0.8 新增）
# 说明: 验证预设实例化器能正确
#       1. 加载 role_presets / project_type_presets / roles.yaml
#       2. 按 P1×P2×P3 + L3小组 + L2技术栈 选型
#       3. 实例化预设为正式角色（status=agent_enabled，role_id唯一）
#       4. 组装成按六大部门分组、可直接被部门Agent承接的团队
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

echo "== 1. 预设实例化器自测（Unity小组 + 移动端手游 + 开发期 + 中型团队）=="
out=$($PY preset_instantiator.py 2>&1)

# 选型组合被正确识别
if echo "$out" | grep -q "项目类型: 移动端手游"; then
  report "P1 项目类型选型识别（移动端手游）" 0
else
  report "P1 项目类型选型识别（移动端手游）" 1
fi
if echo "$out" | grep -q "产品阶段: 正式开发阶段"; then
  report "P2 产品阶段选型识别（正式开发）" 0
else
  report "P2 产品阶段选型识别（正式开发）" 1
fi
if echo "$out" | grep -q "团队规模: 中型团队"; then
  report "P3 团队规模选型识别（中型团队）" 0
else
  report "P3 团队规模选型识别（中型团队）" 1
fi
if echo "$out" | grep -q "L3 小组:  Unity 生态开发小组"; then
  report "L3 小组选型识别（Unity小组）" 0
else
  report "L3 小组选型识别（Unity小组）" 1
fi

echo "== 2. 实例化（预设→正式角色）=="
if echo "$out" | grep -q "✅ 通过：role_id 唯一"; then
  report "实例化角色校验通过（role_id唯一/status=agent_enabled/部门可识别）" 0
else
  report "实例化角色校验通过（role_id唯一/status=agent_enabled/部门可识别）" 1
fi
# 小组 composition 角色实例化
if echo "$out" | grep -q "client_dev_unity_1"; then
  report "L3 小组 composition 实例化（client_dev_unity_1）" 0
else
  report "L3 小组 composition 实例化（client_dev_unity_1）" 1
fi
# 阶段关键角色补充
if echo "$out" | grep -q "project_manager_phase_production"; then
  report "P2 阶段关键角色实例化（project_manager_phase_production）" 0
else
  report "P2 阶段关键角色实例化（project_manager_phase_production）" 1
fi
# 项目类型关键角色补充
if echo "$out" | grep -q "balance_designer_ptype_mobile_game"; then
  report "P1 项目类型关键角色实例化（balance_designer_ptype_mobile_game）" 0
else
  report "P1 项目类型关键角色实例化（balance_designer_ptype_mobile_game）" 1
fi

echo "== 3. 团队组装（六大部门齐全，可直接被部门 Agent 承接）=="
for dept in "design" "program" "art" "qa" "pm" "ops"; do
  if echo "$out" | grep -q "  - $dept: .*role"; then
    report "部门 $dept 已组装角色" 0
  elif echo "$out" | grep -q "  - $dept: "; then
    # 部门行存在（可能为空，需有角色才通过）
    if echo "$out" | grep -q "  - $dept: [^ (]"; then
      report "部门 $dept 已组装角色" 0
    else
      report "部门 $dept 已组装角色" 1
    fi
  else
    report "部门 $dept 已组装角色" 1
  fi
done

echo ""
echo "预设实例化器测试结果: $pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then
  echo "🔴 阻塞：存在未通过断言"
  exit 1
fi
echo "🟢 全部通过"
exit 0

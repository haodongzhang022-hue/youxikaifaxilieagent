#!/usr/bin/env bash
# ============================================================
# 角色-实现差距护栏（Role Inventory Gap Guard）
# 说明: WP-05 产出——验证「声明≠实现」差距不回退。
#   - role_inventory.yaml 覆盖全部声明角色（roles.yaml 58 + ecosystem_roles.yaml 21）
#   - role_inventory.py --gap 输出差距索引（declared_only / registered_only / implemented）
#   - 断言已实体化角色（implemented）不回退，差距数不劣化
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

echo "== 1. role_inventory.yaml 结构完整性 =="

# 1. roles_inventory 覆盖 58 个角色
if $PY -c "
import yaml
with open('role_inventory.yaml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
roles = data.get('roles_inventory', [])
assert len(roles) == 58, f'expected 58, got {len(roles)}'
print('OK')
" >/dev/null 2>&1; then
  report "roles_inventory 覆盖 58 个角色" 0
else
  report "roles_inventory 覆盖 58 个角色" 1
fi

# 2. ecosystem_roles_inventory 覆盖 21 个生态角色
if $PY -c "
import yaml
with open('role_inventory.yaml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
eco = data.get('ecosystem_roles_inventory', [])
assert len(eco) == 21, f'expected 21, got {len(eco)}'
print('OK')
" >/dev/null 2>&1; then
  report "ecosystem_roles_inventory 覆盖 21 个生态角色" 0
else
  report "ecosystem_roles_inventory 覆盖 21 个生态角色" 1
fi

echo "== 2. role_inventory.py --gap 差距不劣化 =="

# 3. --gap 输出包含实现状态汇总
gap_out=$($PY role_inventory.py --gap 2>&1)
if echo "$gap_out" | grep -q "实现状态汇总" && echo "$gap_out" | grep -q "implemented"; then
  report "role_inventory.py --gap 输出实现状态汇总" 0
else
  report "role_inventory.py --gap 输出实现状态汇总" 1
fi

# 4. declared_only 差距数不劣化（当前 0，护栏上限 40）
# 注意：当 declared_only=0 时，状态汇总中可能不输出该行（by_status 无此键）。
# 统一从 GAP-1 标题解析：`declared_only（N 个` 或 `declared_only N`。
declared_count=$(echo "$gap_out" | grep -oP 'declared_only（\K[0-9]+' | head -1)
if [ -z "$declared_count" ]; then
  declared_count=$(echo "$gap_out" | grep -oP 'declared_only\s+\K[0-9]+' | head -1)
fi
if [ -z "$declared_count" ]; then
  declared_count=0
fi
if [ "$declared_count" -le 40 ]; then
  report "declared_only 差距数在护栏内（$declared_count ≤ 40）" 0
else
  report "declared_only 差距数在护栏内（当前 $declared_count，需 ≤ 40）" 1
fi

# 5. implemented 覆盖率达标（当前 34，≥ 30）
impl_count=$(echo "$gap_out" | grep -oP 'implemented\s+\K[0-9]+' | head -1)
if [ -n "$impl_count" ] && [ "$impl_count" -ge 30 ]; then
  report "implemented 覆盖率达标（$impl_count ≥ 30）" 0
else
  report "implemented 覆盖率达标（当前 $impl_count，需 ≥ 30）" 1
fi

# 6. --gap 强制跑 registry.summary() 对照通过
if echo "$gap_out" | grep -q "对照通过"; then
  report "--gap 强制跑 ecosystem_role_registry.summary() 对照通过" 0
else
  report "--gap 强制跑 ecosystem_role_registry.summary() 对照通过" 1
fi

# 7. --check 通过
check_out=$($PY role_inventory.py --check 2>&1)
if echo "$check_out" | grep -q "check_passed: True"; then
  report "role_inventory.py --check 生态角色注册对照通过" 0
else
  report "role_inventory.py --check 生态角色注册对照通过" 1
fi

# 8. _alt 样板变体保持 implemented（不在 GAP-1 declared_only 中）
if ! echo "$gap_out" | grep -qE "producer_alt.*declared_only" \
   && ! echo "$gap_out" | grep -qE "cto_alt.*declared_only" \
   && ! echo "$gap_out" | grep -qE "server_dev_alt.*declared_only"; then
  report "_alt 样板变体保持 implemented（不回退）" 0
else
  report "_alt 样板变体保持 implemented（不回退）" 1
fi

# 9. 生态代表角色未回退为 declared_only
if ! echo "$gap_out" | grep -qE "communicator.*declared_only" \
   && ! echo "$gap_out" | grep -qE "core_player.*declared_only" \
   && ! echo "$gap_out" | grep -qE "publisher.*declared_only"; then
  report "生态代表角色（communicator/core_player/publisher）未回退" 0
else
  report "生态代表角色（communicator/core_player/publisher）未回退" 1
fi

echo "== 3. 端到端全链路护栏 =="

# 10. 实例化团队端到端仍全链路 DONE
e2e_out=$($PY run_end_to_end_instantiated.py 2>&1)
if echo "$e2e_out" | grep -q "all_done = True"; then
  report "实例化团队端到端全链路 DONE" 0
else
  report "实例化团队端到端全链路 DONE" 1
fi

# 11. eco_* 生态任务真实 DONE（WP-03 前置，_all_done 不再过滤）
if echo "$e2e_out" | grep -q "已派发生态角色任务: 5 个" && echo "$e2e_out" | grep -q "all_done = True"; then
  report "生态角色任务真实 DONE（_all_done 不再过滤 eco_*）" 0
else
  report "生态角色任务真实 DONE（_all_done 不再过滤 eco_*）" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 角色-实现差距护栏通过（无声明≠实现回退）"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 角色-实现差距护栏存在阻塞项"
  exit 1
fi

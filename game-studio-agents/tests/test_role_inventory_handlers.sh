#!/usr/bin/env bash
# ============================================================
# 角色-实现映射索引 + 生态角色 handler 实体化测试信号灯
# 说明: 验证 WP-01 / WP-02 / WP-02b 落地产出。
#   - WP-01: role_inventory.yaml + role_inventory.py --list / --gap
#   - WP-02: ecosystem_handlers.py 生态角色 handler 实体化
#   - WP-02b: producer_alt / cto_alt / server_dev_alt 样板变体
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

echo "== 1. WP-01: 角色-实现映射索引 =="

# 1. role_inventory.yaml 存在且可解析
if $PY -c "
import yaml
with open('role_inventory.yaml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
assert len(data['roles_inventory']) == 58, f'roles_inventory should be 58, got {len(data[\"roles_inventory\"])}'
assert len(data['ecosystem_roles_inventory']) == 21, f'ecosystem should be 21, got {len(data[\"ecosystem_roles_inventory\"])}'
print('OK')
" >/dev/null 2>&1; then
  report "role_inventory.yaml 存在且覆盖 58+21=79 角色" 0
else
  report "role_inventory.yaml 存在且覆盖 58+21=79 角色" 1
fi

# 2. role_inventory.py --list 输出 79 个角色
out=$($PY role_inventory.py --list 2>&1)
if echo "$out" | grep -q "总计: 79 个角色"; then
  report "role_inventory.py --list 列出全部 79 个角色" 0
else
  report "role_inventory.py --list 列出全部 79 个角色" 1
fi

# 3. role_inventory.py --gap 包含 GAP-1/GAP-2/GAP-3
out=$($PY role_inventory.py --gap 2>&1)
if echo "$out" | grep -q "GAP-1" && echo "$out" | grep -q "GAP-2" && echo "$out" | grep -q "GAP-3"; then
  report "role_inventory.py --gap 输出 GAP-1/2/3 差距索引" 0
else
  report "role_inventory.py --gap 输出 GAP-1/2/3 差距索引" 1
fi

# 4. role_inventory.py --gap 强制跑 ecosystem_role_registry.summary() 对照
if echo "$out" | grep -q "对照通过"; then
  report "role_inventory.py --gap 强制跑 registry.summary() 对照通过" 0
else
  report "role_inventory.py --gap 强制跑 registry.summary() 对照通过" 1
fi

# 5. role_inventory.py --check 通过
out=$($PY role_inventory.py --check 2>&1)
if echo "$out" | grep -q "check_passed: True"; then
  report "role_inventory.py --check 生态角色注册对照通过" 0
else
  report "role_inventory.py --check 生态角色注册对照通过" 1
fi

echo "== 2. WP-02: 生态角色 handler 实体化 =="

# 6. ecosystem_handlers.py 演示通过
out=$($PY ecosystem_handlers.py 2>&1)
if echo "$out" | grep -q "🟢 通过"; then
  report "ecosystem_handlers.py 演示通过（handler 注册 + 任务 DONE）" 0
else
  report "ecosystem_handlers.py 演示通过（handler 注册 + 任务 DONE）" 1
fi

# 7. handler 数量（21 生态 + 28 _alt + 2 部门基角色 = 51）
if echo "$out" | grep -q "handler_count: 51"; then
  report "handler 实体化（51 个：21 生态 + 28 _alt + 2 部门基角色）" 0
else
  report "生态角色 handler 实体化（49 个：21 生态 + 28 _alt）" 1
fi

# 8. inventory / registry 对齐
if echo "$out" | grep -q "inventory_aligned: True" \
   && echo "$out" | grep -q "registry_aligned: True" \
   && echo "$out" | grep -q "alt_aligned_with_roles_yaml: True"; then
  report "handler 注册命名与 role_inventory.yaml / registry 逐项对齐" 0
else
  report "handler 注册命名与 role_inventory.yaml / registry 逐项对齐" 1
fi

# 9. eco_* 任务真实 DONE
if echo "$out" | grep -q "eco_市场预演派发.*→ DONE" \
   && echo "$out" | grep -q "eco_进度督导盯守.*→ DONE"; then
  report "eco_* 生态角色任务真实 DONE（WP-03 _all_done 修复前置）" 0
else
  report "eco_* 生态角色任务真实 DONE（WP-03 _all_done 修复前置）" 1
fi

echo "== 3. WP-02b: _alt 样板变体 =="

# 10. 全部 28 个 _alt handler 已实现
if echo "$out" | grep -q "alt_handlers:.*producer_alt" \
   && echo "$out" | grep -q "alt_handlers:.*qa_engineer_alt" \
   && echo "$out" | grep -q "alt_handlers:.*game_operator_alt" \
   && echo "$out" | grep -q "alt_handler_count: 28"; then
  report "28 个 _alt handler 已批量实体化" 0
else
  report "28 个 _alt handler 已批量实体化" 1
fi

# 11. _alt 任务真实 DONE
if echo "$out" | grep -q "eco_制作人进取规划.*→ DONE" \
   && echo "$out" | grep -q "eco_技术前瞻规划.*→ DONE" \
   && echo "$out" | grep -q "eco_服务端性能优化.*→ DONE"; then
  report "_alt 样板任务真实 DONE" 0
else
  report "_alt 样板任务真实 DONE" 1
fi

echo "== 4. 集成验证 =="

# 12. 端到端流程仍全链路 DONE（含生态角色 handler）
out2=$($PY run_end_to_end_instantiated.py 2>&1)
if echo "$out2" | grep -q "all_done = True"; then
  report "实例化团队端到端全链路 DONE" 0
else
  report "实例化团队端到端全链路 DONE" 1
fi

# 13. eco_* 任务在端到端流程中真实 DONE（WP-03 前置验证）
if echo "$out2" | grep -q "已派发生态角色任务: 5 个"    && echo "$out2" | grep -q "all_done = True"; then
  report "生态角色 handler 已挂接，eco_* 任务可完成（all_done=True）" 0
else
  report "生态角色 handler 已挂接，eco_* 任务可完成（all_done=True）" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 角色-实现映射索引 + 生态角色 handler 实体化通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 角色-实现映射索引 + 生态角色 handler 实体化存在阻塞项"
  exit 1
fi

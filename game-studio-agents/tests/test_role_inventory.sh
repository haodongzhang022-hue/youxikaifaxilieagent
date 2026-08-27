#!/usr/bin/env bash
# ============================================================
# 角色-实现映射索引 + 生态 handler 实体化测试信号灯（WP-01 / WP-02 / WP-02b）
# 说明: 验证 P0 段三个工作包落地产出——
#   WP-01: config/role_inventory.yaml + role_inventory.py（--list / --gap）
#   WP-02: config/ecosystem_handlers.py（生态角色真实承接 handler，让 eco_* 真实 DONE）
#   WP-02b: ecosystem_handlers.py 的 _alt 样板段（producer_alt / cto_alt / server_dev_alt）
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

echo "== 1. WP-01 角色-实现映射索引（role_inventory.py --list / --gap）=="
# 1. --list 覆盖 roles.yaml(58) + ecosystem_roles.yaml(21)
out_list=$($PY role_inventory.py --list 2>&1)
if echo "$out_list" | grep -q "研发岗位（roles.yaml 事实源）: 58 个" \
   && echo "$out_list" | grep -q "生态角色（ecosystem_roles.yaml 事实源）: 21 个"; then
  report "--list 覆盖研发岗位 58 + 生态角色 21" 0
else
  report "--list 覆盖研发岗位 58 + 生态角色 21" 1
fi

# 2. --gap 强制对照 ecosystem_role_registry.summary()（G1 无缺口）
out_gap=$($PY role_inventory.py --gap 2>&1)
if echo "$out_gap" | grep -q "无缺口：全部 21 个生态角色均已注册可派发"; then
  report "--gap G1：生态角色均已注册可派发（registry.summary() 对照）" 0
else
  report "--gap G1：生态角色均已注册可派发（registry.summary() 对照）" 1
fi

# 3. --gap handler 注册命名与映射表对齐（G2 完全一致）
if echo "$out_gap" | grep -q "完全一致：24 个 handler 命名与映射表"; then
  report "--gap G2：handler 注册命名与映射表（生态段+_alt样板）对齐" 0
else
  report "--gap G2：handler 注册命名与映射表（生态段+_alt样板）对齐" 1
fi

# 4. --gap 无强制缺口
if echo "$out_gap" | grep -q "无强制缺口"; then
  report "--gap 无强制缺口（差距索引通过）" 0
else
  report "--gap 无强制缺口（差距索引通过）" 1
fi

echo "== 2. WP-02 生态角色 handler 实体化（ecosystem_handlers.py）=="
out_eco=$($PY ecosystem_handlers.py 2>&1)

# 5. 21 个生态角色挂接真实 handler
if echo "$out_eco" | grep -q "WP-02 生态角色: 21 个"; then
  report "WP-02 生态角色 handler 实体化（21 个）" 0
else
  report "WP-02 生态角色 handler 实体化（21 个）" 1
fi

# 6. eco_* 任务真实 DONE（WP-03 前置）
if echo "$out_eco" | grep -q "DONE 5 个"; then
  report "派发生态角色任务真实 DONE（5 个，WP-03 前置）" 0
else
  report "派发生态角色任务真实 DONE（5 个，WP-03 前置）" 1
fi

# 7. 强制 registry.summary() 对照无缺口
if echo "$out_eco" | grep -q "生态角色未注册到总线: 无"; then
  report "生态 handler 与 registry.summary() 对照无缺口" 0
else
  report "生态 handler 与 registry.summary() 对照无缺口" 1
fi

echo "== 3. WP-02b 样板变体实体化 =="
# 8. 三个高价值 _alt 样板真实 DONE
if echo "$out_eco" | grep -q "DONE 3 个" \
   && echo "$out_eco" | grep -q "producer_alt / cto_alt / server_dev_alt"; then
  report "WP-02b _alt 样板（producer_alt/cto_alt/server_dev_alt）实体化并 DONE" 0
else
  report "WP-02b _alt 样板（producer_alt/cto_alt/server_dev_alt）实体化并 DONE" 1
fi

# 9. 生态角色 21 + _alt 样板 3 = 24 个 handler
if echo "$out_eco" | grep -q "已挂接 handler 的生态角色 + _alt 样板：24 个"; then
  report "handler 挂接总数 24（21 生态 + 3 _alt 样板）" 0
else
  report "handler 挂接总数 24（21 生态 + 3 _alt 样板）" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 WP-01/02/02b 全部通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 WP-01/02/02b 存在阻塞项"
  exit 1
fi

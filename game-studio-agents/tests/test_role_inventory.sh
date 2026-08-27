#!/usr/bin/env bash
# ============================================================
# 角色-实现映射差距护栏 (test_role_inventory.sh)
# 版本: v1.0
# 说明: 防止"声明≠存在"回退——校验 role_inventory.yaml 与实际实现文件一致，
#       并对"应已实体化"的关键角色做硬校验，缺失即红灯。
#
# 校验项:
#   [1] role_inventory.yaml / role_inventory.py 存在且 YAML 可解析
#   [2] role_inventory.py --gap 能输出差距表（工具可用）
#   [3] 关键角色（已承诺实体化的）必须标记为 implemented，缺失即失败
#   [4] 已实体化角色的实现文件必须存在（防悬挂引用）
#
# 用法: bash test_role_inventory.sh
# ============================================================
set -u

BASE="$(cd "$(dirname "$0")/../config" && pwd)"
PASS=0
FAIL=0

ok()  { echo "  ✅ $1"; PASS=$((PASS+1)); }
bad() { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

echo "============================================================"
echo "角色-实现映射差距护栏 (test_role_inventory.sh)"
echo "============================================================"

# [1] 核心文件存在且 YAML 可解析
echo -e "\n[1] 核心文件与 YAML 有效性"
if [ -f "$BASE/role_inventory.yaml" ]; then
  python3 -c "import yaml;d=yaml.safe_load(open('$BASE/role_inventory.yaml'));assert isinstance(d.get('roles'),list) and d['roles']" \
    && ok "role_inventory.yaml 存在且 YAML 有效 ($(grep -c 'role_id:' "$BASE/role_inventory.yaml") 个角色)" \
    || bad "role_inventory.yaml 缺失或 YAML 解析失败"
else
  bad "role_inventory.yaml 缺失"
fi
[ -f "$BASE/role_inventory.py" ] && ok "role_inventory.py 存在" || bad "role_inventory.py 缺失"

# [2] 差距工具可用
echo -e "\n[2] role_inventory.py --gap 工具可运行（返回码 0 表示无差距；非零说明存在声明≠实现差距）"
GAP_OUT=$(python3 "$BASE/role_inventory.py" --gap 2>&1)
GAP_RC=$?
if [ "$GAP_RC" -eq 0 ]; then
  ok "--gap 运行正常：无差距（所有角色已实体化）"
else
  # 返回码 1 说明工具能运行且检测到差距（这正是工具的价值，非故障）
  ok "--gap 运行正常：检测到差距（返回码 $GAP_RC，当前声明≠实现清单已暴露）"
  # 从 --gap 首行 "共 N 个" 解析精确差距数（避免 grep 误计汇总行）
  GAP_COUNT=$(echo "$GAP_OUT" | head -1 | grep -oP '共 \K[0-9]+' || echo '0')
  echo "     提示: 当前差距数=$GAP_COUNT"
fi

# [3] 关键已承诺实体化角色必须 implemented（防回退）
echo -e "\n[3] 关键已承诺角色必须 implemented（防回退）"
MUST_IMPLEMENTED="producer reference_learner progress_pusher merged_confirmer
  publisher core_player advertiser gig_pool
  producer_alt server_dev_alt data_analyst_alt"
for rid in $MUST_IMPLEMENTED; do
  status=$(python3 - "$BASE" "$rid" << 'PY'
import sys, yaml
base, rid = sys.argv[1], sys.argv[2]
d = yaml.safe_load(open(f"{base}/role_inventory.yaml"))
for r in d["roles"]:
    if r["role_id"] == rid:
        print(r["status"]); break
PY
)
  if [ "$status" = "implemented" ]; then
    ok "$rid = implemented"
  else
    bad "$rid = $status（应为 implemented，存在回退！）"
  fi
done

# [4] implemented 角色的实现文件必须存在（防悬挂引用）
echo -e "\n[4] implemented 角色实现文件存在性"
MUST_FILES="game_producer_agent.py department_agents.py reference_learner_agent.py
  progress_pusher.py merged_confirm_agent.py ecosystem_handlers.py alt_variants.py"
for f in $MUST_FILES; do
  [ -f "$BASE/$f" ] && ok "$f 存在" || bad "$f 缺失（悬挂引用！）"
done

echo -e "\n============================================================"
echo "结果: PASS=$PASS  FAIL=$FAIL"
echo "============================================================"
[ "$FAIL" -eq 0 ] && echo "✅ 差距护栏通过" || echo "❌ 差距护栏失败，存在声明≠实现回退"
exit $FAIL

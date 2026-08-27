#!/usr/bin/env bash
# ============================================================
# 部门 NPC 流水线执行护栏
# 说明: 防止「声明了没做」断档——settings.yml 注册的每个部门 NPC，
#       都必须在 .cnb.yml 流水线中有对应的 npc:go 执行阶段，否则
#       游戏向经理 @部门名 派发后没有执行承接（歧义根源）。
# 校验:
#   1. settings.yml 注册的部门 NPC（策划/程序/美术/测试/项目管理/运营）
#      全部在 .cnb.yml 中存在对应 role 的 npc:go 执行阶段；
#   2. issue.open 与 pull_request.merged 两条部门执行链路均已接通；
#   3. 部门执行阶段包含组内协作 + 跨部门协作指令（必做）。
# 退出码: 0 = 🟢 通过，1 = 🔴 阻塞
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/../.."
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

SETTINGS=".cnb/settings.yml"
PIPELINE=".cnb.yml"

echo "== 1. settings.yml 注册的部门 NPC 均在 .cnb.yml 有 npc:go 执行阶段 =="
# 六大部门 + 协作支持圈（协作支持圈是跨部门服务圈，不强制独立执行阶段，这里仅校验六大执行部门）
DEPTS="策划线 程序线 美术线 测试线 项目管理 运营线"
for dept in $DEPTS; do
  # 部门角色必须注册在 settings.yml
  if grep -q "name: ${dept}" "$SETTINGS"; then
    report "settings.yml 已注册部门 NPC【${dept}】" 0
  else
    report "settings.yml 已注册部门 NPC【${dept}】" 1
  fi
  # 部门角色必须在 .cnb.yml 中有 npc:go 执行阶段
  if grep -q "role: ${dept}" "$PIPELINE"; then
    report ".cnb.yml 存在【${dept}】的 npc:go 执行阶段" 0
  else
    report ".cnb.yml 存在【${dept}】的 npc:go 执行阶段" 1
  fi
done

echo "== 2. 部门执行链路已接通（issue.open + pull_request.merged）=="
if grep -q "issue.open:" "$PIPELINE"; then
  issue_depts=$(awk '/issue.open:/,/pull_request:/' "$PIPELINE" | grep -c "role: \(策划线\|程序线\|美术线\|测试线\|项目管理\|运营线\)" || true)
  if [ "$issue_depts" = "6" ]; then
    report "issue.open 含 6 个部门执行阶段（@部门派发有承接）" 0
  else
    report "issue.open 含 6 个部门执行阶段（@部门派发有承接，实际=${issue_depts}）" 1
  fi
else
  report "issue.open 含 6 个部门执行阶段" 1
fi
if grep -q "pull_request.merged:" "$PIPELINE"; then
  merged_depts=$(awk '/pull_request.merged:/,/pull_request.changes_requested:/' "$PIPELINE" | grep -c "role: \(策划线\|程序线\|美术线\|测试线\|项目管理\|运营线\)" || true)
  if [ "$merged_depts" = "6" ]; then
    report "pull_request.merged 含 6 个部门执行阶段（下游解锁有承接）" 0
  else
    report "pull_request.merged 含 6 个部门执行阶段（下游解锁有承接，实际=${merged_depts}）" 1
  fi
else
  report "pull_request.merged 含 6 个部门执行阶段" 1
fi

echo "== 3. 部门执行阶段含组内协作 + 跨部门协作指令（必做）=="
if grep -q "组内协作" "$PIPELINE"; then
  report "部门执行阶段包含【组内协作】指令" 0
else
  report "部门执行阶段包含【组内协作】指令" 1
fi
if grep -q "跨部门协作" "$PIPELINE"; then
  report "部门执行阶段包含【跨部门协作】指令" 0
else
  report "部门执行阶段包含【跨部门协作】指令" 1
fi

echo ""
echo "测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" = "0" ]; then
  echo "🟢 部门 NPC 流水线执行链路全部接通"
  exit 0
else
  echo "🔴 存在断档：部分部门 NPC 在流水线中无执行承接"
  exit 1
fi

#!/usr/bin/env bash
# ============================================================
# 部门派发路由决策护栏（DepartmentRouting v2.0）
# 说明: 验证"路由决策"机制——解决无工作部门凑热闹问题：
#       1. routing.py 支持 %部门名 显性声明触发；
#       2. 裸提及部门名不触发（如"测试线验收中"标签）；
#       3. @部门名 点名 / 依赖解锁可驱动部门触发；
#       4. game_producer_agent 编排时按路由只派发命中部门；
#       5. .cnb.yml 部门 stage 含路由守卫指令（未被点名不评论）。
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

# 清理 CNB 注入的环境变量（避免 CI 平台变量污染 CLI 测试判定）
clean_env() {
  CNB_EVENT="${1:-issue.open}" \
  CNB_ISSUE_TITLE="${2:-}" \
  CNB_ISSUE_DESCRIPTION="" \
  CNB_ISSUE_LABELS="" \
  CNB_PULL_REQUEST_TITLE="" \
  CNB_PULL_REQUEST_DESCRIPTION="" \
  CNB_DEPS_UNLOCKED="" \
  "$@"
}

echo "== 1. routing.py 演示通过 =="
out=$($PY routing.py 2>&1)
if echo "$out" | grep -q "🟢 部门派发路由决策演示通过"; then
  report "routing.py 演示通过" 0
else
  report "routing.py 演示通过" 1
  echo "$out"
fi


echo "== 1.5 CLI 路由决策：从环境变量读取并判断部门命中 =="
CLI_TEST=$(
  CNB_EVENT=issue.open \
  CNB_ISSUE_TITLE="修复服务端接口并发 bug" \
  CNB_ISSUE_DESCRIPTION="" \
  CNB_ISSUE_LABELS="" \
  CNB_PULL_REQUEST_TITLE="" \
  CNB_PULL_REQUEST_DESCRIPTION="" \
  $PY routing.py route 2>&1
)
# 纯程序 bug 任务没有 %程序线 显性声明，不触发任何部门
if [ -z "$CLI_TEST" ] || [ "$CLI_TEST" = " " ]; then
  report "CLI route 无显性声明不触发" 0
else
  report "CLI route 无显性声明不触发" 1
  echo "  output: '$CLI_TEST'"
fi

# CLI route 显性声明 %测试线
CLI_TEST2=$(
  CNB_EVENT=issue.open \
  CNB_ISSUE_TITLE="回归验证" \
  CNB_ISSUE_DESCRIPTION="请 %测试线 完成回归测试" \
  CNB_ISSUE_LABELS="" \
  CNB_PULL_REQUEST_TITLE="" \
  CNB_PULL_REQUEST_DESCRIPTION="" \
  $PY routing.py route 2>&1
)
if echo "$CLI_TEST2" | grep -q "测试线"; then
  report "CLI route 显性声明 %测试线 触发" 0
else
  report "CLI route 显性声明 %测试线 触发" 1
  echo "  output: '$CLI_TEST2'"
fi

# CLI check 程序线：裸提及不触发（退出码非 0）
if ! CNB_EVENT=issue.open CNB_ISSUE_TITLE="修复服务端接口 bug" CNB_ISSUE_DESCRIPTION="" CNB_ISSUE_LABELS="" CNB_PULL_REQUEST_TITLE="" CNB_PULL_REQUEST_DESCRIPTION="" $PY routing.py check 程序线 >/dev/null 2>&1; then
  report "CLI check 程序线未命中（裸提及）" 0
else
  report "CLI check 程序线未命中（裸提及）" 1
fi

# CLI check 测试线：显性声明 %测试线 → 命中
if CNB_EVENT=issue.open CNB_ISSUE_TITLE="回归验证" CNB_ISSUE_DESCRIPTION="请 %测试线 完成回归" CNB_ISSUE_LABELS="" CNB_PULL_REQUEST_TITLE="" CNB_PULL_REQUEST_DESCRIPTION="" $PY routing.py check 测试线 >/dev/null 2>&1; then
  report "CLI check 测试线命中（%显性声明）" 0
else
  report "CLI check 测试线命中（%显性声明）" 1
fi

# CLI marker 写入文件
MARKER_FILE="$(mktemp)"
CNB_EVENT=issue.open CNB_ISSUE_TITLE="回归验证" CNB_ISSUE_DESCRIPTION="请 %测试线 完成回归" CNB_ISSUE_LABELS="" CNB_PULL_REQUEST_TITLE="" CNB_PULL_REQUEST_DESCRIPTION="" $PY routing.py marker "$MARKER_FILE" >/dev/null 2>&1
if [ -f "$MARKER_FILE" ] && grep -q "测试线" "$MARKER_FILE"; then
  report "CLI marker 写入路由清单文件" 0
else
  report "CLI marker 写入路由清单文件" 1
fi
rm -f "$MARKER_FILE"

echo "== 2. 显性声明 vs 裸提及 =="
out2=$($PY - <<'PYBLK'
import sys; sys.path.insert(0, '.')
from routing import route, is_department_active

# 裸提及部门名（如状态标签）→ 不触发
r = route(issue_title="职责明确（测试线验收中 美术线验收中）")
assert r["active_departments"] == [], f"裸提及不应触发: {r['active_departments']}"

# 显性声明 %测试线 → 触发
r2 = route(issue_title="回归验证", issue_body="请 %测试线 完成")
assert "测试线" in r2["active_departments"], "显性声明应触发"

# 显性声明 %美术线 → 触发
r3 = route(issue_title="美术资源", issue_body="请 %美术线 出原画")
assert "美术线" in r3["active_departments"], "显性声明应触发"

# 混合场景：裸提及美术线不触发，但 %测试线 触发
r4 = route(issue_title="机制改动（美术线关注）", issue_body="请 %测试线 回归验证")
assert "美术线" not in r4["active_departments"], "裸提及美术线不应触发"
assert "测试线" in r4["active_departments"], "%测试线显性声明应触发"

# 完全无关 → 不触发任何部门
r5 = route(issue_title="环境变量说明文档")
assert r5["active_departments"] == [], f"无关任务不应触发: {r5['active_departments']}"
assert is_department_active(r5, "策划线") is False

print("ROUTE_MATCH_OK")
PYBLK
)
if echo "$out2" | grep -q "ROUTE_MATCH_OK"; then
  report "显性声明触发 + 裸提及不触发" 0
else
  report "显性声明触发 + 裸提及不触发" 1
  echo "$out2"
fi

echo "== 3. @点名 / 依赖解锁驱动触发 =="
out3=$($PY - <<'PYBLK'
import sys; sys.path.insert(0, '.')
from routing import route

# @点名 → 强制触发
r = route(issue_body="机制改动，@美术线 请协助")
assert "美术线" in r["active_departments"]

# manually_requested 参数 → 强制触发
r1 = route(issue_body="机制改动", manually_requested=["美术线"])
assert "美术线" in r1["active_departments"]

# 依赖解锁 → 触发下游部门
r2 = route(issue_body="上游设计验收", deps_unlocked=["wp_gameplay", "wp_engine"])
assert "策划线" in r2["active_departments"]
assert "程序线" in r2["active_departments"]
print("ROUTE_DRIVE_OK")
PYBLK
)
if echo "$out3" | grep -q "ROUTE_DRIVE_OK"; then
  report "@点名/依赖解锁可驱动部门触发" 0
else
  report "@点名/依赖解锁可驱动部门触发" 1
  echo "$out3"
fi

echo "== 4. game_producer_agent 编排按路由只派发命中部门 =="
out4=$($PY - <<'PYBLK'
import sys; sys.path.insert(0, '.')
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, build_task_assign

bus = MessageBus()
manager = GameProducerAgent(bus=bus); manager.boot()

# 模拟增量需求：仅涉及程序线（服务端 bug），提供 routing 上下文
architecture = {
    "project": "服务端 bug 修复",
    "modules": ["server", "engine"],
    "routing": {"title": "修复服务端接口并发 bug", "body": "请 %程序线 修复"},
}
msg = build_task_assign("architect", manager.role_id, "orch_r1", {"architecture": architecture})
bus.publish(msg); bus.process_all()

routed = [wp for wp in manager.work_packages if wp.get("routed")]
skipped = [wp for wp in manager.work_packages if not wp.get("routed")]
print("ROUTED=" + ",".join(wp["department"] for wp in routed))
print("SKIPPED=" + ",".join(wp["department"] for wp in skipped))
# 服务端/引擎都是程序线 → 只派发 program
assert all(wp["department"] == "program" for wp in routed), routed
print("PRODUCER_ROUTE_OK")
PYBLK
)
if echo "$out4" | grep -q "PRODUCER_ROUTE_OK"; then
  report "经理编排按路由只派发命中部门" 0
  echo "    $out4"
else
  report "经理编排按路由只派发命中部门" 1
  echo "$out4"
fi

echo "== 5. .cnb.yml 部门 stage 含路由守卫指令 =="
PIPELINE="../../.cnb.yml"
routing_guard=$(grep -c "路由守卫" "$PIPELINE" || true)
if [ "$routing_guard" -ge 12 ]; then
  report ".cnb.yml 部门 stage 含路由守卫指令（${routing_guard} 处）" 0
else
  report ".cnb.yml 部门 stage 含路由守卫指令（${routing_guard} 处，期望>=12）" 1
fi
if grep -q "只派发/只 @ 本轮" "$PIPELINE" && grep -q "本轮应触发部门" "$PIPELINE"; then
  report "游戏向经理编排含路由决策指令" 0
else
  report "游戏向经理编排含路由决策指令" 1
fi

# 新增：验证 .cnb.yml 中部门 stage 含 if 路由守卫（条件不满足时跳过，不消耗资源）
if_guard=$(grep -c "grep -q" "$PIPELINE" || true)
if [ "$if_guard" -ge 12 ]; then
  report ".cnb.yml 部门 stage 含 if 条件拦截（${if_guard} 处）" 0
else
  report ".cnb.yml 部门 stage 含 if 条件拦截（${if_guard} 处，期望>=12）" 1
fi

# 新增：验证路由决策 stage 已写入流水线
if grep -q "routing.py marker" "$PIPELINE"; then
  report ".cnb.yml 含路由决策 marker 写文件 stage" 0
else
  report ".cnb.yml 含路由决策 marker 写文件 stage" 1
fi

echo ""
echo "测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" = "0" ]; then
  echo "🟢 部门派发路由决策护栏通过"
  exit 0
else
  echo "🔴 部门派发路由决策存在阻塞项"
  exit 1
fi

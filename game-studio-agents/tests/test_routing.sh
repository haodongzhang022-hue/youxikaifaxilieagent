#!/usr/bin/env bash
# ============================================================
# 部门派发路由决策护栏（DepartmentRouting）
# 说明: 验证"路由决策"机制——解决无工作部门凑热闹问题：
#       1. routing.py 可按工作内容关键词精确匹配部门；
#       2. 未命中部门不触发（无关任务不凑热闹）；
#       3. 明确点名 / 依赖解锁可驱动部门触发；
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

echo "== 1. routing.py 演示通过 =="
out=$($PY routing.py 2>&1)
if echo "$out" | grep -q "🟢 部门派发路由决策"; then
  report "routing.py 演示通过" 0
else
  report "routing.py 演示通过" 1
  echo "$out"
fi


echo "== 1.5 CLI 路由决策：从环境变量读取并判断部门命中 =="
CLI_TEST=$(
  CNB_EVENT=issue.open \
  CNB_ISSUE_TITLE="修复服务端接口并发 bug" \
  CNB_ISSUE_DESCRIPTION="涉及 server 端接口逻辑与引擎适配" \
  $PY routing.py route 2>&1
)
if echo "$CLI_TEST" | grep -q "程序线"; then
  report "CLI route 输出 active 部门清单" 0
else
  report "CLI route 输出 active 部门清单" 1
  echo "$CLI_TEST"
fi

# CLI check 程序线应命中（退出码 0）
if CNB_EVENT=issue.open CNB_ISSUE_TITLE="修复服务端接口 bug" $PY routing.py check 程序线 >/dev/null 2>&1; then
  report "CLI check 程序线命中" 0
else
  report "CLI check 程序线命中" 1
fi

# CLI check 美术线不应命中（退出码非 0）
if ! CNB_EVENT=issue.open CNB_ISSUE_TITLE="修复服务端接口 bug" $PY routing.py check 美术线 >/dev/null 2>&1; then
  report "CLI check 美术线未命中" 0
else
  report "CLI check 美术线未命中" 1
fi

# CLI marker 写入文件
MARKER_FILE="$(mktemp)"
CNB_EVENT=issue.open CNB_ISSUE_TITLE="修复服务端接口 bug" $PY routing.py marker "$MARKER_FILE" >/dev/null 2>&1
if [ -f "$MARKER_FILE" ] && grep -q "程序线" "$MARKER_FILE"; then
  report "CLI marker 写入路由清单文件" 0
else
  report "CLI marker 写入路由清单文件" 1
fi
rm -f "$MARKER_FILE"

echo "== 2. 按工作内容精确匹配（无关任务不凑热闹）=="
out2=$($PY - <<'PYBLK'
import sys; sys.path.insert(0, '.')
from routing import route, is_department_active

# 纯程序 bug → 只触发程序线，美术/测试不凑热闹
r = route(issue_title="修复服务端接口并发 bug", issue_body="server 接口与引擎适配")
assert "程序线" in r["active_departments"]
assert "美术线" not in r["active_departments"]
assert "测试线" not in r["active_departments"]

# 纯美术任务 → 只触发美术线，程序不凑热闹
r2 = route(issue_title="角色原画与 3D 建模规范", issue_body="美术风格 原画 建模 材质")
assert "美术线" in r2["active_departments"]
assert "程序线" not in r2["active_departments"]

# 完全无关 → 不触发任何部门
r3 = route(issue_title="环境变量说明文档")
assert r3["active_departments"] == []
assert is_department_active(r3, "策划线") is False
print("ROUTE_MATCH_OK")
PYBLK
)
if echo "$out2" | grep -q "ROUTE_MATCH_OK"; then
  report "工作内容精确匹配，无关部门不触发" 0
else
  report "工作内容精确匹配，无关部门不触发" 1
  echo "$out2"
fi

echo "== 3. 点名 / 依赖解锁驱动触发 =="
out3=$($PY - <<'PYBLK'
import sys; sys.path.insert(0, '.')
from routing import route

# 明确点名 → 强制触发
r = route(issue_body="机制改动", manually_requested=["美术线"])
assert "美术线" in r["active_departments"]

# 依赖解锁 → 触发下游部门
r2 = route(issue_body="上游设计验收", deps_unlocked=["wp_gameplay", "wp_engine"])
assert "策划线" in r2["active_departments"]
assert "程序线" in r2["active_departments"]
print("ROUTE_DRIVE_OK")
PYBLK
)
if echo "$out3" | grep -q "ROUTE_DRIVE_OK"; then
  report "点名/依赖解锁可驱动部门触发" 0
else
  report "点名/依赖解锁可驱动部门触发" 1
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
    "routing": {"title": "修复服务端接口并发 bug", "body": "server 接口与引擎适配"},
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


# ============================================================
# 三层触发引擎新增护栏（routing.py v3.0）
# ============================================================
echo "== 6. 显式声明（最高优先）：%部门 / @部门 / [触发:部门] =="
out6=$($PY - <<'PYBLK'
import sys; sys.path.insert(0, '.')
from routing import route

# %部门名 显式声明 → 即使内容无关也触发，且为高置信
r = route(issue_body="机制改动，请 %测试线 完成回归。")
assert "测试线" in r["active_departments"]
assert r["confidence"]["测试线"]["confidence"] == "high"
assert r["confidence"]["测试线"]["method"] == "explicit"

# @部门名
r2 = route(issue_body="@运营线 请分析本次上线数据。")
assert "运营线" in r2["active_departments"]
assert r2["confidence"]["运营线"]["method"] == "explicit"

# [触发:部门名]（dongjiagoushi 风格）
r3 = route(issue_body="[触发:美术线] 请给出 UI 视觉规范。")
assert "美术线" in r3["active_departments"]
assert r3["confidence"]["美术线"]["method"] == "explicit"
print("EXPLICIT_OK")
PYBLK
)
if echo "$out6" | grep -q "EXPLICIT_OK"; then
  report "显式声明(%/@/[触发:])最高优先触发" 0
else
  report "显式声明(%/@/[触发:])最高优先触发" 1
  echo "$out6"
fi

echo "== 7. 裸提及部门名（状态标签）不触发——消灭'测试线验收中'误判 =="
out7=$($PY - <<'PYBLK'
import sys; sys.path.insert(0, '.')
from routing import route

# 状态标签文本：裸提及部门名、无显式声明、无职责分配语境 → 不触发任何部门
r = route(issue_body="测试线验收中、美术线验收中（状态标签，非分配工作）。")
assert r["active_departments"] == [], r["active_departments"]

# 纯无关文本
r2 = route(issue_title="今天天气不错，吃饭了吗")
assert r2["active_departments"] == [], r2["active_departments"]
print("BARE_MENTION_OK")
PYBLK
)
if echo "$out7" | grep -q "BARE_MENTION_OK"; then
  report "裸提及部门名/状态标签不触发（未命中=静默）" 0
else
  report "裸提及部门名/状态标签不触发（未命中=静默）" 1
  echo "$out7"
fi

echo "== 8. 语义/关键词触发带阈值下限（强职责词命中才触发） =="
out8=$($PY - <<'PYBLK'
import sys; sys.path.insert(0, '.')
from routing import route

# 强职责词命中 → 触发对应部门
r = route(issue_title="角色原画与 3D 建模规范", issue_body="美术风格 原画 建模 材质")
assert "美术线" in r["active_departments"]
assert r["confidence"]["美术线"]["method"] in ("explicit", "semantic")

# 纯程序 bug → 只触发程序线
r2 = route(issue_title="修复服务端接口并发 bug", issue_body="server 接口与引擎适配")
assert "程序线" in r2["active_departments"]
assert "美术线" not in r2["active_departments"]
assert "测试线" not in r2["active_departments"]
print("SEMANTIC_OK")
PYBLK
)
if echo "$out8" | grep -q "SEMANTIC_OK"; then
  report "语义/关键词触发带阈值下限" 0
else
  report "语义/关键词触发带阈值下限" 1
  echo "$out8"
fi

echo "== 9. route_from_env 不再拼接 CNB_ISSUE_LABELS（标签不污染路由） =="
out9=$($PY - <<'PYBLK'
import sys; sys.path.insert(0, '.')
import os
from routing import route_from_env, serialize_active

# 模拟 CI 环境：labels 含"测试线验收中,美术线验收中"，标题为纯程序任务
env = {
    "CNB_EVENT": "issue.open",
    "CNB_ISSUE_TITLE": "修复服务端接口并发 bug",
    "CNB_ISSUE_DESCRIPTION": "server 接口与引擎适配",
    "CNB_ISSUE_LABELS": "测试线验收中,美术线验收中,路由机制已落地",
}
old = {k: os.environ.get(k) for k in env}
os.environ.update(env)
try:
    r = route_from_env()
    active = serialize_active(r)
finally:
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

# labels 不再被拼接 → 测试线/美术线不被"验收中"状态标签误拉起
assert "测试线" not in active, active
assert "美术线" not in active, active
assert "程序线" in active, active
print("LABELS_ISOLATED_OK")
PYBLK
)
if echo "$out9" | grep -q "LABELS_ISOLATED_OK"; then
  report "route_from_env 不拼接 labels，状态标签不污染路由" 0
else
  report "route_from_env 不拼接 labels，状态标签不污染路由" 1
  echo "$out9"
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

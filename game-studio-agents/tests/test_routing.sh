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
if echo "$out" | grep -q "🟢 部门派发路由决策演示通过"; then
  report "routing.py 演示通过" 0
else
  report "routing.py 演示通过" 1
  echo "$out"
fi

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

echo ""
echo "测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" = "0" ]; then
  echo "🟢 部门派发路由决策护栏通过"
  exit 0
else
  echo "🔴 部门派发路由决策存在阻塞项"
  exit 1
fi

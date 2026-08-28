#!/usr/bin/env bash
# ============================================================
# 可调配小组池测试信号灯（SquadPool）
# 说明: 验证小组**独立于部门**、**可灵活调配**、**可重复调用**、
#       **多个小组分别做不一样的事**。
#
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

echo "== 1. SquadPool 独立模块演示 =="
out=$($PY squad_pool.py 2>&1)

# 1. 预置 5 个小组
if echo "$out" | grep -q "小组池共 5 个小组"; then
  report "预置 5 个可调配小组" 0
else
  report "预置 5 个可调配小组" 1
fi

# 2. 程序线调配成功
if echo "$out" | grep -q "调配成功: 客户端开发A组 → 程序线"; then
  report "程序线调配客户端组" 0
else
  report "程序线调配客户端组" 1
fi

# 3. 重复调用（同一小组再次被调配）
if echo "$out" | grep -q "再次调配成功: 客户端开发A组 → 美术线"; then
  report "小组重复调用（美术线二次调配同一小组）" 0
else
  report "小组重复调用（美术线二次调配同一小组）" 1
fi

# 4. 按技能寻址
if echo "$out" | grep -q "按技能 \[behavior_tree\] 调配: AI 逻辑C组"; then
  report "按技能寻址（多组各司其职）" 0
else
  report "按技能寻址（多组各司其职）" 1
fi

# 5. 多组并行互不影响
if echo "$out" | grep -q "调配引擎组: 引擎适配D组" \
   && echo "$out" | grep -q "调配工具链组: 工具链E组"; then
  report "多小组并行（引擎/工具链同时被调配）" 0
else
  report "多小组并行（引擎/工具链同时被调配）" 1
fi

# 6. 未注册领域拒绝
if echo "$out" | grep -q "调配 narrative_design: ok=False"; then
  report "未注册领域查询被拒绝" 0
else
  report "未注册领域查询被拒绝" 1
fi

# 7. 演示通过
if echo "$out" | grep -q "🟢 通过"; then
  report "SquadPool 演示通过" 0
else
  report "SquadPool 演示通过" 1
fi

echo "== 2. DispatchCapability 集成（dispatch_to_squad） =="
out2=$($PY << 'PYBLK2'
from message_bus import MessageBus
from dispatch_capability import DispatchCapability
from squad_pool import create_default_squad_pool

bus = MessageBus()
pool = create_default_squad_pool()
cap = DispatchCapability("producer", bus=bus, squad_pool=pool)

# 注册小组长
for s in pool.list_squads():
    leader = s["leader"]
    bus.register(leader)
    bus.on(leader, lambda m: None)

results = {}

# 1. 按领域调配
wp1 = {"id": "wp_client_001", "label": "客户端 UI", "module": "client"}
r1 = cap.dispatch_to_squad_by_domain("client_dev", wp1, "程序线")
results["by_domain"] = (r1.dispatched and r1.owner == "client_lead")

# 2. 小组变为 BUSY
client_squads = pool.find(domain="client_dev")
results["squad_busy"] = (client_squads[0].status == "BUSY")

# 3. 释放回池
rel = cap.release_squad(client_squads[0].squad_id)
results["release"] = rel["ok"]
results["squad_idle"] = (client_squads[0].status == "IDLE")

# 4. 重复调用（另一部门再次调配同一小组）
wp2 = {"id": "wp_client_002", "label": "客户端 UI v2", "module": "client"}
r2 = cap.dispatch_to_squad_by_domain("client_dev", wp2, "美术线")
results["repeat_call"] = (r2.dispatched)
results["assign_count"] = (client_squads[0].assign_count >= 2)

# 5. 按 squad_id 直调
wp3 = {"id": "wp_ai_001", "label": "AI 行为树", "module": "ai_logic"}
ai_squads = pool.find(domain="ai_dev")
r3 = cap.dispatch_to_squad(ai_squads[0].squad_id, wp3, "测试线")
results["by_squad_id"] = (r3.dispatched)

# 6. 多组并行
wp4 = {"id": "wp_engine_001", "label": "引擎适配", "module": "engine"}
r4 = cap.dispatch_to_squad_by_domain("engine_dev", wp4, "程序线")
results["multi_parallel"] = (r4.dispatched)

# 7. 未注册小组拒绝
r5 = cap.dispatch_to_squad("ghost_squad", {"id": "wp_x"}, "程序线")
results["unreg_reject"] = (not r5.dispatched)

# 8. 一键释放某部门全部小组
released = cap.release_squads_by_department("程序线")
results["release_by_dept"] = (len(released) >= 1)

# 输出
for k, v in results.items():
    print(f"  {k}: {'OK' if v else 'FAIL'}")
print("ALL_PASS" if all(results.values()) else "SOME_FAIL")
PYBLK2
)

if echo "$out2" | grep -q "ALL_PASS"; then
  report "dispatch_to_squad 集成全部通过" 0
  echo "$out2"
else
  report "dispatch_to_squad 集成全部通过" 1
  echo "$out2"
fi

echo "== 3. SquadPool 文档 =="
if [ -f "../docs/squad-pool.md" ]; then
  report "文档存在（docs/squad-pool.md）" 0
else
  report "文档存在（docs/squad-pool.md）" 1
fi

if grep -q "独立于部门" "../docs/squad-pool.md" \
   && grep -q "重复调用" "../docs/squad-pool.md" \
   && grep -q "多组并行" "../docs/squad-pool.md"; then
  report "文档覆盖核心能力（独立调配/重复调用/多组并行）" 0
else
  report "文档覆盖核心能力（独立调配/重复调用/多组并行）" 1
fi

echo "== 4. 与现有派发能力回归 =="
reg=$($PY dispatch_capability.py 2>&1)
if echo "$reg" | grep -q "🟢 通过"; then
  report "DispatchCapability 原有演示仍通过（回归）" 0
else
  report "DispatchCapability 原有演示仍通过（回归）" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 可调配小组池通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 可调配小组池存在阻塞项"
  exit 1
fi

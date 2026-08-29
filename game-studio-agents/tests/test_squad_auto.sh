#!/usr/bin/env bash
# ============================================================
# 可调配小组自动化调度测试信号灯 (SquadAutoScheduler)
# 说明: 验证「自动触发调配 + 自动释放」闭环：
#       - 工作包声明 squad_domain → 部门 Agent 自动从小组池调配小组
#       - 工作包完成 → 自动释放小组回池（可重复调用）
#       - 未声明 squad_domain → 不触发（不干扰正常执行）
#       - 无可用小组 → 不阻塞部门执行
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

echo "== 1. SquadAutoScheduler 独立模块演示 =="
out=$($PY squad_auto.py 2>&1)

# 1. 自动触发调配成功
if echo "$out" | grep -q "auto_dispatched=True"; then
  report "自动触发调配成功" 0
else
  report "自动触发调配成功" 1
fi

# 2. 自动释放成功
if echo "$out" | grep -q "released=True reason=小组 客户端开发A组 已释放回池"; then
  report "自动释放小组回池" 0
else
  report "自动释放小组回池" 1
fi

# 3. 重复调用（同一小组被再次调配）
if echo "$out" | grep -q "assign_count=2"; then
  report "同一小组重复调用" 0
else
  report "同一小组重复调用" 1
fi

# 4. 无 squad_domain 不触发
if echo "$out" | grep -q "工作包未声明 squad_domain"; then
  report "无 squad_domain 不触发小组" 0
else
  report "无 squad_domain 不触发小组" 1
fi

# 5. 多领域小组并行
if echo "$out" | grep -q "当前活跃小组: 2 个"; then
  report "多领域小组并行自动化" 0
else
  report "多领域小组并行自动化" 1
fi

# 6. 演示通过
if echo "$out" | grep -q "🟢 通过"; then
  report "SquadAutoScheduler 演示通过" 0
else
  report "SquadAutoScheduler 演示通过" 1
fi

echo "== 2. 部门 Agent 自动化对接（自动触发 + 自动释放） =="
out2=$($PY << 'PYBLK2'
from message_bus import MessageBus
from department_agents import ProgramDeptAgent
from dispatch_capability import DispatchCapability
from squad_pool import create_default_squad_pool, SQUAD_IDLE, SQUAD_BUSY
from squad_auto import SquadAutoScheduler

bus = MessageBus()
agent = ProgramDeptAgent(bus)
agent.boot()

pool = create_default_squad_pool()
for s in pool.list_squads():
    leader = s["leader"]
    if leader not in bus.roles:
        bus.register(leader)
        bus.on(leader, lambda m: None)

agent._auto_squad = SquadAutoScheduler(squad_pool=pool)
agent.dispatch_capability().squad_pool = pool
cap = DispatchCapability("producer", bus=bus, squad_pool=pool)

res = {}

# --- (1) 声明 squad_domain 的工作包自动触发调配 ---
wp1 = {"id": "wp_client_auto_1", "label": "客户端 UI", "module": "client",
       "department_name": "程序线", "squad_domain": "client_dev", "owner": "cto"}
r1 = cap.dispatch_work_package(wp1)
bus.process_all()

# 验证自动触发日志（说明 _auto_squad_dispatch 被调用且成功）
auto_trigger_logs = [e for e in agent.log if e['event'] == 'auto_squad']
res["auto_trigger_logged"] = bool(auto_trigger_logs)

# 验证自动释放日志
auto_release_logs = [e for e in agent.log if e['event'] == 'auto_squad_release']
res["auto_release_logged"] = bool(auto_release_logs)

# 自动释放后小组回到 IDLE
client_squads = pool.find(domain="client_dev")
res["squad_back_to_idle"] = all(s.status == SQUAD_IDLE for s in client_squads)

# 工作包→小组映射清除（幂等清理）
res["wp_tracked_cleared"] = (len(agent._squad_wp_ids) == 0)
res["squad_tracked_cleared"] = (len(agent._auto_squad._wp_squad_map) == 0)

# --- (2) 未声明 squad_domain 不触发 ---
wp2 = {"id": "wp_no_squad_1", "label": "普通任务", "module": "gameplay",
       "department_name": "策划线", "owner": "lead_designer"}
# 用 DesignDeptAgent 验证（不需要小组）
from department_agents import DesignDeptAgent
design = DesignDeptAgent(bus)
design.boot()
r2 = cap.dispatch_work_package(wp2)
bus.process_all()
res["no_squad_no_trigger"] = (len(design._squad_wp_ids) == 0)
res["no_squad_normal_exec"] = ("wp_no_squad_1" in design.done_packages)

# --- (3) 无可用小组时不阻塞部门执行 ---
# 构造一个不存在的 squad_domain
wp3 = {"id": "wp_ghost_squad_1", "label": "幽灵小组任务", "module": "client",
       "department_name": "程序线", "squad_domain": "ghost_domain", "owner": "cto"}
r3 = cap.dispatch_work_package(wp3)
bus.process_all()
res["ghost_no_block"] = ("wp_ghost_squad_1" in agent.done_packages)
res["ghost_no_track"] = (len(agent._squad_wp_ids) == 0)

for k, v in res.items():
    print(f"  {k}: {'OK' if v else 'FAIL'}")
print("ALL_PASS" if all(res.values()) else "SOME_FAIL")
PYBLK2
)

if echo "$out2" | grep -q "ALL_PASS"; then
  report "部门 Agent 自动化对接全部通过" 0
  echo "$out2"
else
  report "部门 Agent 自动化对接全部通过" 1
  echo "$out2"
fi

echo "== 3. 与既有 SquadPool / DispatchCapability 回归 =="
reg1=$($PY squad_pool.py 2>&1)
if echo "$reg1" | grep -q "🟢 通过"; then
  report "SquadPool 原有演示通过（回归）" 0
else
  report "SquadPool 原有演示通过（回归）" 1
fi

reg2=$($PY dispatch_capability.py 2>&1)
if echo "$reg2" | grep -q "🟢 通过"; then
  report "DispatchCapability 原有演示通过（回归）" 0
else
  report "DispatchCapability 原有演示通过（回归）" 1
fi

echo "== 4. 文档 =="
if [ -f "../docs/squad-auto.md" ]; then
  report "文档存在（docs/squad-auto.md）" 0
else
  report "文档存在（docs/squad-auto.md）" 1
fi

if grep -q "自动触发" "../docs/squad-auto.md" \
   && grep -q "自动释放" "../docs/squad-auto.md"; then
  report "文档覆盖自动触发/自动释放" 0
else
  report "文档覆盖自动触发/自动释放" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 可调配小组自动化调度通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 可调配小组自动化调度存在阻塞项"
  exit 1
fi

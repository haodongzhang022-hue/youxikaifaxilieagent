#!/usr/bin/env bash
# ============================================================
# v0.7 游戏团队端到端联动测试信号灯（护栏）
# 说明: 验证「游戏向经理 + 六部门执行 Agent」端到端联动闭环：
#       策划→程序→美术→测试→发版→运营 全链路，验收→解锁下游→自动推进。
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

echo "== 1. 六部门执行 Agent 可构造并启动 =="
out=$($PY - <<'PYEOF'
from department_agents import (DesignDeptAgent, ProgramDeptAgent, ArtDeptAgent,
                               QADeptAgent, PMDeptAgent, OpsDeptAgent)
from message_bus import MessageBus
from task_scheduler import Scheduler
bus = MessageBus(); sched = Scheduler(bus=bus)
agents = [
    DesignDeptAgent(role_id="lead_designer", bus=bus, scheduler=sched),
    ProgramDeptAgent(role_id="cto", bus=bus, scheduler=sched),
    ArtDeptAgent(role_id="art_director", bus=bus, scheduler=sched),
    QADeptAgent(role_id="qa_engineer", bus=bus, scheduler=sched),
    PMDeptAgent(role_id="project_manager", bus=bus, scheduler=sched),
    OpsDeptAgent(role_id="data_analyst", bus=bus, scheduler=sched),
]
for a in agents:
    a.boot()
    print("BOOTED=" + a.role_id + ":" + a.dept_name())
PYEOF
)
if echo "$out" | grep -q "BOOTED=lead_designer:策划线"; then
  report "策划线 Agent 可启动" 0
else
  report "策划线 Agent 可启动" 1
fi
if echo "$out" | grep -q "BOOTED=cto:程序线"; then
  report "程序线 Agent 可启动" 0
else
  report "程序线 Agent 可启动" 1
fi
if echo "$out" | grep -q "BOOTED=art_director:美术线"; then
  report "美术线 Agent 可启动" 0
else
  report "美术线 Agent 可启动" 1
fi
if echo "$out" | grep -q "BOOTED=qa_engineer:测试线"; then
  report "测试线 Agent 可启动" 0
else
  report "测试线 Agent 可启动" 1
fi
if echo "$out" | grep -q "BOOTED=project_manager:项目管理"; then
  report "项目管理 Agent 可启动" 0
else
  report "项目管理 Agent 可启动" 1
fi
if echo "$out" | grep -q "BOOTED=data_analyst:运营线"; then
  report "运营线 Agent 可启动" 0
else
  report "运营线 Agent 可启动" 1
fi

echo "== 2. 端到端全链路联动（12 工作包全部 DONE）=="
out=$($PY game_team_orchestration.py 2>&1)
if echo "$out" | grep -q "端到端全部完成: ✅"; then
  report "端到端全部工作包完成" 0
else
  report "端到端全部工作包完成" 1
fi
if echo "$out" | grep -q "六部门全链路联动: ✅"; then
  report "六部门全链路联动跑通" 0
else
  report "六部门全链路联动跑通" 1
fi

echo "== 3. 依赖解锁正确（下游依赖上游，全链路按序推进）=="
out=$($PY - <<'PYEOF'
from game_team_orchestration import GameTeamOrchestrator
orch = GameTeamOrchestrator()
result = orch.run()
dep = {tid: t.depends_on for tid, t in orch.sched.queue.tasks.items()}
print('GAMEPLAY_DEPS=' + str(dep.get('wp_gameplay')))
print('CLIENT_DEPS=' + ','.join(dep.get('wp_client', [])))
print('TESTING_DEPS=' + str(len(dep.get('wp_testing', []))))
print('RELEASE_DEPS=' + str(len(dep.get('wp_release', []))))
print('OPS_DEPS=' + str(len(dep.get('wp_data_ops', []))))
PYEOF
)
if echo "$out" | grep -q "GAMEPLAY_DEPS=\[\]"; then
  report "策划工作包无依赖（先执行）" 0
else
  report "策划工作包无依赖（先执行）" 1
fi
if echo "$out" | grep -q "CLIENT_DEPS=wp_gameplay,wp_numeric_model"; then
  report "程序工作包依赖策划产出" 0
else
  report "程序工作包依赖策划产出" 1
fi
if echo "$out" | grep -q "TESTING_DEPS=9"; then
  report "测试工作包依赖程序+美术全量产出" 0
else
  report "测试工作包依赖程序+美术全量产出" 1
fi
if echo "$out" | grep -q "RELEASE_DEPS=10"; then
  report "发版依赖测试完成（含全链路）" 0
else
  report "发版依赖测试完成（含全链路）" 1
fi
if echo "$out" | grep -q "OPS_DEPS=9"; then
  report "运营依赖程序+美术产出（全链路后置）" 0
else
  report "运营依赖程序+美术产出（全链路后置）" 1
fi

echo "== 4. 验收→解锁下游→自动推进闭环（机制驱动，非手动）=="
out=$($PY - <<'PYEOF'
from game_team_orchestration import GameTeamOrchestrator
orch = GameTeamOrchestrator()
# 仅下发策划+程序两个模块，验证上游验收后才解锁下游执行
orch.modules = ["gameplay", "client"]
result = orch.run()
# 依赖 chain: gameplay(无依赖) -> client(依赖 gameplay)
print('GAMEPLAY_STATE=' + orch.sched.queue.tasks['wp_gameplay'].state)
print('CLIENT_STATE=' + orch.sched.queue.tasks['wp_client'].state)
print('GAMEPLAY_DELIVERED=' + str('wp_gameplay' in result['dept_deliveries'].get('策划线', [])))
print('CLIENT_DELIVERED=' + str('wp_client' in result['dept_deliveries'].get('程序线', [])))
print('ACCEPTED=' + ','.join(sorted(result['manager_accepted'])))
PYEOF
)
if echo "$out" | grep -q "GAMEPLAY_STATE=DONE"; then
  report "上游策划工作包已完成" 0
else
  report "上游策划工作包已完成" 1
fi
if echo "$out" | grep -q "CLIENT_STATE=DONE"; then
  report "下游程序工作包被解锁并完成" 0
else
  report "下游程序工作包被解锁并完成" 1
fi
if echo "$out" | grep -q "GAMEPLAY_DELIVERED=True"; then
  report "策划部门实际交付 gameplay" 0
else
  report "策划部门实际交付 gameplay" 1
fi
if echo "$out" | grep -q "CLIENT_DELIVERED=True"; then
  report "程序部门在解锁后实际交付 client" 0
else
  report "程序部门在解锁后实际交付 client" 1
fi
if echo "$out" | grep -q "ACCEPTED=wp_client,wp_gameplay"; then
  report "经理验收全部产出（自动解锁）" 0
else
  report "经理验收全部产出（自动解锁）" 1
fi

echo "== 5. 返工机制（部门收到 rework 通知进入 REWORK 态）=="
out=$($PY - <<'PYEOF'
from department_agents import DesignDeptAgent
from message_bus import MessageBus, build_message
from task_scheduler import Scheduler
bus = MessageBus(); sched = Scheduler(bus=bus)
a = DesignDeptAgent(role_id="lead_designer", bus=bus, scheduler=sched)
a.boot()
bus.publish(build_message("NOTIFICATION", "producer", "lead_designer",
                          {"event": "rework", "work_package_id": "wp_gameplay",
                           "reason": "设计不完整"}))
bus.process_all()
print('BIZ_STATE=' + a.biz_state)
print('PENDING=' + ','.join(a.pending_rework))
for e in a.log:
    if e['event']=='rework':
        print('REWORK_LOG=' + e['note'])
PYEOF
)
if echo "$out" | grep -q "BIZ_STATE=REWORK"; then
  report "部门收到返工后进入 REWORK 态" 0
else
  report "部门收到返工后进入 REWORK 态" 1
fi
if echo "$out" | grep -q "PENDING=wp_gameplay"; then
  report "返工工作包被记入待返工清单" 0
else
  report "返工工作包被记入待返工清单" 1
fi

echo "== 6. 同 role 单实例（避免同 role 多实例重复消费）=="
out=$($PY - <<'PYEOF'
from game_team_orchestration import GameTeamOrchestrator
orch = GameTeamOrchestrator()
orch.modules = ["gameplay"]
result = orch.run()
# 策划仅一个工作包，应只交付一次
deliv = result['dept_deliveries'].get('策划线', [])
print('DESIGN_DELIVERY=' + str(len(deliv)))
PYEOF
)
if echo "$out" | grep -q "DESIGN_DELIVERY=1"; then
  report "单实例下策划仅交付一次（无重复消费）" 0
else
  report "单实例下策划仅交付一次（无重复消费）" 1
fi

echo ""
echo "v0.7 端到端联动测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then
  echo "🔴 阻塞：存在未通过断言"
  exit 1
fi
echo "🟢 全部通过"
exit 0

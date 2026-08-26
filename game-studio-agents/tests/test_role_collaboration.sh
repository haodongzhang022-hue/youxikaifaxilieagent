#!/usr/bin/env bash
# ============================================================
# 角色间协作层测试信号灯（护栏）
# 说明: 验证多角色互相 @ 的任务转交 / 分工 / 协作能力可用。
#       - @分工：一个大任务拆为多子任务分发给多角色
#       - @转交：角色 A 将任务转交给 B，B 接受/退回
#       - 转交链留痕：全程可审计、可回退
#       - 经理 Agent 集成：handle_task 能路由协作事件
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

echo "== 1. 模块导入与语法 =="
if $PY -c "import role_collaboration" 2>&1; then
  report "role_collaboration 模块可导入" 0
else
  report "role_collaboration 模块可导入" 1
fi

echo "== 2. 经理 @分工：一个大任务拆为多子任务 =="
out=$($PY - <<'PYEOF'
from role_collaboration import RoleCollabHub
from message_bus import MessageBus
bus = MessageBus()
hub = RoleCollabHub(bus)
for r in ["system_designer","client_dev","balance_designer","qa_engineer"]:
    bus.register(r)
msgs = hub.delegate("producer","wp_combat","战斗系统",
    [{"to_role":"system_designer","sub_task":"玩法设计","inputs":{}},
     {"to_role":"client_dev","sub_task":"客户端实现","inputs":{}},
     {"to_role":"balance_designer","sub_task":"数值平衡","inputs":{}},
     {"to_role":"qa_engineer","sub_task":"功能测试","inputs":{}}])
for m in msgs:
    hub.ack_subtask(m.to_role, m.from_role, m.content["sub_task_id"])
print("SPLIT_COUNT=" + str(len(msgs)))
print("TO_ROLES=" + ",".join(sorted(m.to_role for m in msgs)))
rep = hub.report("wp_combat")["split"]
print("ACCEPTED=" + str(rep["accepted"]) + "/" + str(rep["total"]))
PYEOF
)
if echo "$out" | grep -q "SPLIT_COUNT=4"; then report "@分工生成4条子任务" 0; else report "@分工生成4条子任务" 1; echo "$out"; fi
if echo "$out" | grep -q "ACCEPTED=4/4"; then report "4个角色全部承接子任务" 0; else report "4个角色全部承接子任务" 1; fi

echo "== 3. 角色 @转交：B 接受后任务持有者变更 =="
out=$($PY - <<'PYEOF'
from role_collaboration import RoleCollabHub
from task_scheduler import Task
from message_bus import MessageBus
bus = MessageBus()
hub = RoleCollabHub(bus)
for r in ["balance_designer","system_designer"]:
    bus.register(r)
task = Task(id="wp_combat#sub3", name="数值平衡", owner="balance_designer")
hub.handoff("balance_designer","system_designer",task,reason="需玩法数据")
hub.accept_transfer("system_designer","balance_designer","wp_combat#sub3")
print("OWNER_AFTER_TRANSFER=" + str(hub.report("wp_combat#sub3")["owner"]))
PYEOF
)
if echo "$out" | grep -q "OWNER_AFTER_TRANSFER=system_designer"; then report "@转交接受后 owner 变更为 B" 0; else report "@转交接受后 owner 变更为 B" 1; echo "$out"; fi

echo "== 4. 任务 @退回：B 无法完成退回原主 =="
out=$($PY - <<'PYEOF'
from role_collaboration import RoleCollabHub
from task_scheduler import Task
from message_bus import MessageBus
bus = MessageBus()
hub = RoleCollabHub(bus)
for r in ["balance_designer","system_designer"]:
    bus.register(r)
task = Task(id="wp_combat#sub3", name="数值平衡", owner="balance_designer")
hub.handoff("balance_designer","system_designer",task,reason="需玩法数据")
hub.accept_transfer("system_designer","balance_designer","wp_combat#sub3")
hub.handback("system_designer","balance_designer","wp_combat#sub3",reason="数据已提供请继续")
print("OWNER_AFTER_BACK=" + str(hub.report("wp_combat#sub3")["owner"]))
chain = hub.report("wp_combat#sub3")["transfer_chain"]
print("HAS_CALLBACK=" + str(any(c["kind"]=="CALLBACK" and c["status"]=="BACK" for c in chain)))
print("CHAIN_LEN=" + str(len(chain)))
PYEOF
)
if echo "$out" | grep -q "OWNER_AFTER_BACK=balance_designer"; then report "@退回后 owner 恢复原主" 0; else report "@退回后 owner 恢复原主" 1; echo "$out"; fi
if echo "$out" | grep -q "HAS_CALLBACK=True"; then report "转交链含退回(CALLBACK)留痕" 0; else report "转交链含退回(CALLBACK)留痕" 1; fi
if echo "$out" | grep -q "CHAIN_LEN=3"; then report "转交链完整留痕(3条)" 0; else report "转交链完整留痕(3条)" 1; echo "$out"; fi

echo "== 5. 经理 Agent 集成：协作事件可路由 =="
out=$($PY - <<'PYEOF'
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, build_message
bus = MessageBus()
m = GameProducerAgent(bus=bus)
m.boot()
# 经理收到 @转交 事件，能记录并广播
m.handle_task(build_message("TASK_TRANSFER","balance_designer", m.role_id,
    {"task_id":"wp_numeric_model","reason":"需策划数据","to_role":"system_designer","origin_role":"balance_designer"}))
# 经理收到 @分工 事件，能记录并广播
m.handle_task(build_message("WORKSPLIT","producer","client_dev",
    {"parent_task_id":"wp_client","sub_task_id":"wp_client#sub1","sub_task":"客户端UI"}))
print("HAS_COLLAB=" + str(hasattr(m,"collab")))
print("LOG=" + "|".join(x.get("note","")[:20] for x in m.log[-4:]))
PYEOF
)
if echo "$out" | grep -q "HAS_COLLAB=True"; then report "经理 Agent 内置协作工作台 collab" 0; else report "经理 Agent 内置协作工作台 collab" 1; echo "$out"; fi
if echo "$out" | grep -q "转交"; then report "经理路由 @转交 事件成功" 0; else report "经理路由 @转交 事件成功" 1; fi
if echo "$out" | grep -q "分工"; then report "经理路由 @分工 事件成功" 0; else report "经理路由 @分工 事件成功" 1; fi

echo ""
echo "=================================="
echo "角色间协作层测试结果: 🟢 $pass 通过 / 🔴 $fail 失败"
echo "=================================="
[ "$fail" -eq 0 ] || exit 1

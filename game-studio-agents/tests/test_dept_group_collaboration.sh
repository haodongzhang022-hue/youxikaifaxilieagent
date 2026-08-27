#!/usr/bin/env bash
# ============================================================
# 部门统一头（小组）协作护栏
# 说明: 部门 == NPC 小组，@部门名 = 一次 @ 部门内多个角色；
#       部门头对外承接，对内组内协作 @分工 拆派给部门内角色，
#       并可跨部门 @协作请求/转交。复用协作工作台能力 + 协作规则。
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

echo "== 1. 部门统一头：部门名注册为可召唤/可派发目标 =="
out=$($PY - <<'PYEOF'
from message_bus import MessageBus
from department_agents import DesignDeptAgent, ProgramDeptAgent
bus = MessageBus()
DesignDeptAgent(bus).boot()
ProgramDeptAgent(bus).boot()
print("DEPT_DESIGN_REG=" + str("策划线" in bus.roles))
print("DEPT_PROGRAM_REG=" + str("程序线" in bus.roles))
PYEOF
)
if echo "$out" | grep -q "DEPT_DESIGN_REG=True"; then
  report "@策划线 部门统一头已注册为总线目标" 0
else
  report "@策划线 部门统一头已注册为总线目标" 1
fi
if echo "$out" | grep -q "DEPT_PROGRAM_REG=True"; then
  report "@程序线 部门统一头已注册为总线目标" 0
else
  report "@程序线 部门统一头已注册为总线目标" 1
fi

echo "== 2. 组内协作：部门头 @分工 拆派给部门内角色 =="
out=$($PY - <<'PYEOF'
from message_bus import MessageBus
from department_agents import DesignDeptAgent
bus = MessageBus()
d = DesignDeptAgent(bus); d.boot()
r = d._delegate_internal("wp_design", "核心系统",
    [{"role": "system_designer", "desc": "系统设计"},
     {"role": "balance_designer", "desc": "数值模型"},
     {"role": "client_dev", "desc": "跨部门，应过滤"}])
print("GROUP_OK=" + str(r["ok"]))
print("GROUP_ROLES=" + ",".join(r["roles"]))
print("HAS_SUB=" + str("wp_design__sub1" in r["sub_tasks"]))
PYEOF
)
if echo "$out" | grep -q "GROUP_OK=True"; then
  report "组内协作 @分工 成功" 0
else
  report "组内协作 @分工 成功" 1
fi
if echo "$out" | grep -q "GROUP_ROLES=system_designer,balance_designer"; then
  report "跨部门角色被过滤，仅拆派给部门内角色" 0
else
  report "跨部门角色被过滤，仅拆派给部门内角色" 1
fi
if echo "$out" | grep -q "HAS_SUB=True"; then
  report "协作工作台生成组内子任务（__subN）" 0
else
  report "协作工作台生成组内子任务（__subN）" 1
fi

echo "== 3. 组内子任务进度汇总（@分工 承接状态）=="
out=$($PY - <<'PYEOF'
from message_bus import MessageBus
from department_agents import DesignDeptAgent
bus = MessageBus()
d = DesignDeptAgent(bus); d.boot()
d._delegate_internal("wp_prog", "进度", [
    {"role": "system_designer", "desc": "A"},
    {"role": "balance_designer", "desc": "B"}])
d.collab.sub_ack("wp_prog", "wp_prog__sub1", "system_designer", "ACCEPT")
d.collab.sub_ack("wp_prog", "wp_prog__sub1", "system_designer", "COMPLETE")
p = d._sub_progress("wp_prog")
print("PROG=" + str(p["done"]) + "/" + str(p["total"]))
print("PROG_HAS_DETAIL=" + str("detail" in p))
PYEOF
)
if echo "$out" | grep -q "PROG=1/2"; then
  report "组内子任务进度 1/2 完成" 0
else
  report "组内子任务进度 1/2 完成" 1
fi
if echo "$out" | grep -q "PROG_HAS_DETAIL=True"; then
  report "进度含逐子任务 detail" 0
else
  report "进度含逐子任务 detail" 1
fi

echo "== 4. 跨部门协作：部门 @协作请求 其他部门 =="
out=$($PY - <<'PYEOF'
from message_bus import MessageBus
from department_agents import DesignDeptAgent
bus = MessageBus()
d = DesignDeptAgent(bus); d.boot()
r = d.request_peer("wp_tech", "技术评估", "cto", need="需要技术方案评审")
print("PEER_OK=" + str(r["ok"]))
print("PEER_TO=" + r["assist_requested_to"])
print("HAS_PEER_REC=" + str(any(p["task_id"]=="wp_tech" and p["peer"]=="cto" for p in d.peer_collab)))
PYEOF
)
if echo "$out" | grep -q "PEER_OK=True" && echo "$out" | grep -q "PEER_TO=cto"; then
  report "跨部门 @协作请求 正确指定对方角色" 0
else
  report "跨部门 @协作请求 正确指定对方角色" 1
fi
if echo "$out" | grep -q "HAS_PEER_REC=True"; then
  report "跨部门协作全程留痕（peer_collab）" 0
else
  report "跨部门协作全程留痕（peer_collab）" 1
fi

echo "== 5. 部门统一头审计（组内+跨部门全记录）=="
out=$($PY - <<'PYEOF'
from message_bus import MessageBus
from department_agents import DesignDeptAgent
bus = MessageBus()
d = DesignDeptAgent(bus); d.boot()
d._delegate_internal("wp_audit", "审计", [
    {"role": "system_designer", "desc": "A"}])
d.request_peer("wp_audit", "审计", "cto", need="评估")
aud = d.group_audit("wp_audit")
print("HEAD=" + aud["head"])
print("DEPT=" + aud["department"])
print("INTERNAL=" + ",".join(aud["internal_subtasks"]))
print("EVENTS=" + str(aud["collab"]["event_count"]))
print("PEER_COUNT=" + str(len(aud["peer_collab"])))
PYEOF
)
if echo "$out" | grep -q "HEAD=lead_designer" && echo "$out" | grep -q "DEPT=策划线"; then
  report "审计识别部门统一头与部门归属" 0
else
  report "审计识别部门统一头与部门归属" 1
fi
if echo "$out" | grep -q "INTERNAL=system_designer" && echo "$out" | grep -q "EVENTS=2"; then
  report "审计含组内子任务与协作事件留痕" 0
else
  report "审计含组内子任务与协作事件留痕" 1
fi
if echo "$out" | grep -q "PEER_COUNT=1"; then
  report "审计含跨部门协作记录" 0
else
  report "审计含跨部门协作记录" 1
fi

echo "== 6. 机制层：dispatch_to_department 派发到部门统一头 =="
out=$($PY - <<'PYEOF'
from message_bus import MessageBus
from department_agents import DesignDeptAgent
from dispatch_capability import DispatchCapability
bus = MessageBus()
d = DesignDeptAgent(bus); d.boot()
cap = DispatchCapability("producer", bus=bus)
r = cap.dispatch_to_department(
    "策划线", {"id": "wp_x", "label": "联调", "module": "gameplay"},
    internal_assignments=[{"role": "system_designer", "desc": "系统"}],
    peer_collabs=[{"peer": "程序线", "need": "评审"}])
print("DISPATCH_OK=" + str(r.dispatched))
print("OWNER=" + r.owner)
bus.process_all()
print("INTERNAL_AFTER=" + str("system_designer" in d.internal_subtasks.get("wp_x", [])))
print("PEER_AFTER=" + str(any(p["task_id"]=="wp_x" for p in d.peer_collab)))
print("DONE=" + str("wp_x" in d.done_packages))
PYEOF
)
if echo "$out" | grep -q "DISPATCH_OK=True" && echo "$out" | grep -q "OWNER=策划线"; then
  report "派发到部门名成功（@部门=@统一头）" 0
else
  report "派发到部门名成功（@部门=@统一头）" 1
fi
if echo "$out" | grep -q "INTERNAL_AFTER=True" && echo "$out" | grep -q "PEER_AFTER=True"; then
  report "部门头消费派单后自动触发组内+跨部门协作" 0
else
  report "部门头消费派单后自动触发组内+跨部门协作" 1
fi
if echo "$out" | grep -q "DONE=True"; then
  report "部门统一头承接完成后上报验收" 0
else
  report "部门统一头承接完成后上报验收" 1
fi

echo ""
echo "测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" = "0" ]; then
  echo "🟢 部门统一头（小组）协作机制全部通过"
  exit 0
else
  echo "🔴 存在失败项"
  exit 1
fi

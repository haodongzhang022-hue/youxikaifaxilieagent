#!/usr/bin/env bash
# ============================================================
# 角色间协作层 · 多角色互相@ 测试信号灯（护栏）
# 说明: 验证「任务转交 + 分工协作 + 协作请求」能力，
#       确保多角色互相@、任务转交与分工协作可靠可用。
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

echo "== 1. 多角色 @转交（HANDOFF）=="
out=$($PY - <<'PYEOF'
from role_collaboration import CollaborationWorkbench
wb = CollaborationWorkbench()
r = wb.handoff("wp_client", "客户端界面", "system_designer", "client_dev", note="UI已设计")
print("CHAIN=" + ";".join(r["record"].transfer_chain))
print("OWNER=" + r["record"].owner)
print("STATUS=" + r["record"].status)
PYEOF
)
if echo "$out" | grep -q "system_designer->client_dev"; then
  report "@转交 记录转交链（A->B）" 0
else
  report "@转交 记录转交链（A->B）" 1
fi
if echo "$out" | grep -q "OWNER=client_dev"; then
  report "@转交 更新持有者为目标角色" 0
else
  report "@转交 更新持有者为目标角色" 1
fi

echo "== 2. 转交承接：接受 / 拒绝 =="
out=$($PY - <<'PYEOF'
from role_collaboration import CollaborationWorkbench
wb = CollaborationWorkbench()
wb.handoff("t1", "任务", "A", "B")
r = wb.acknowledge("t1", "B", "ACCEPT")
print("ACCEPT_STATUS=" + r["record"].status)
print("ACCEPT_OWNER=" + r["record"].owner)
wb2 = CollaborationWorkbench()
wb2.handoff("t2", "任务2", "A", "B")
r2 = wb2.acknowledge("t2", "B", "REJECT", reason="忙")
print("REJECT_STATUS=" + r2["record"].status)
PYEOF
)
if echo "$out" | grep -q "ACCEPT_STATUS=ACCEPTED"; then
  report "承接方接受 @转交 -> ACCEPTED" 0
else
  report "承接方接受 @转交 -> ACCEPTED" 1
fi
if echo "$out" | grep -q "ACCEPT_OWNER=B"; then
  report "接受后持有者变为承接方" 0
else
  report "接受后持有者变为承接方" 1
fi
if echo "$out" | grep -q "REJECT_STATUS=DECLINED"; then
  report "承接方拒绝 @转交 -> DECLINED" 0
else
  report "承接方拒绝 @转交 -> DECLINED" 1
fi

echo "== 3. 再转交 / 退回（REHANDOFF / RETURN）=="
out=$($PY - <<'PYEOF'
from role_collaboration import CollaborationWorkbench
wb = CollaborationWorkbench()
wb.handoff("t3", "任务3", "A", "B")
wb.acknowledge("t3", "B", "ACCEPT")
r = wb.acknowledge("t3", "B", "REHANDOFF", reassign_to="C")
print("REHANDOFF_CHAIN=" + ";".join(r["record"].transfer_chain))
print("REHANDOFF_OWNER=" + r["record"].owner)
wb2 = CollaborationWorkbench()
wb2.handoff("t4", "任务4", "A", "B")
wb2.acknowledge("t4", "B", "ACCEPT")
r2 = wb2.acknowledge("t4", "B", "RETURN", reason="需求不明确")
print("RETURN_OWNER=" + r2["record"].owner)
print("RETURN_STATUS=" + r2["record"].status)
PYEOF
)
if echo "$out" | grep -q "B->C"; then
  report "再转交 追加转交链（B->C）" 0
else
  report "再转交 追加转交链（B->C）" 1
fi
if echo "$out" | grep -q "RETURN_OWNER=A"; then
  report "退回 回到上一持有者 A" 0
else
  report "退回 回到上一持有者 A" 1
fi

echo "== 4. 多角色 @分工（DELEGATE 并行协作）=="
out=$($PY - <<'PYEOF'
from role_collaboration import CollaborationWorkbench
wb = CollaborationWorkbench()
r = wb.delegate("wp_testing", "全量测试", "project_manager",
                [{"role": "qa_engineer", "desc": "功能测试"},
                 {"role": "auto_qa", "desc": "自动化回归"}])
print("SUBS=" + ",".join(r["sub_tasks"]))
wb.sub_ack("wp_testing", "wp_testing__sub1", "qa_engineer", "ACCEPT")
wb.sub_ack("wp_testing", "wp_testing__sub2", "auto_qa", "COMPLETE")
p = wb.sub_progress("wp_testing")
print(f"PROG={p['done']}/{p['total']}")
PYEOF
)
if echo "$out" | grep -q "SUBS=.*__sub1.*__sub2"; then
  report "@分工 拆出多个并行子任务" 0
else
  report "@分工 拆出多个并行子任务" 1
fi
if echo "$out" | grep -q "PROG=1/2"; then
  report "分工子任务进度汇总（1/2 完成）" 0
else
  report "分工子任务进度汇总（1/2 完成）" 1
fi

echo "== 5. 多角色 @协作请求（COLLAB_REQ）=="
out=$($PY - <<'PYEOF'
from role_collaboration import CollaborationWorkbench
wb = CollaborationWorkbench()
r = wb.request_collab("wp_server", "服务端", "client_dev", "server_dev", need="表结构")
print("REQ_TO=" + r["assist_requested_to"])
PYEOF
)
if echo "$out" | grep -q "REQ_TO=server_dev"; then
  report "@协作请求 正确指定协助角色" 0
else
  report "@协作请求 正确指定协助角色" 1
fi

echo "== 6. 转交链留痕与审计（可审计可回退）=="
out=$($PY - <<'PYEOF'
from role_collaboration import CollaborationWorkbench
wb = CollaborationWorkbench()
wb.handoff("wp_a", "任务A", "system_designer", "client_dev")
wb.acknowledge("wp_a", "client_dev", "ACCEPT")
wb.acknowledge("wp_a", "client_dev", "REHANDOFF", reassign_to="ui_ux")
aud = wb.audit("wp_a")
print("EVENTS=" + str(aud["event_count"]))
print("CHAIN_LEN=" + str(len(aud["transfer_chain"])))
print("HAS_HANDOFF=" + str(any(e["event"] == "HANDOFF" for e in aud["events"])))
PYEOF
)
if echo "$out" | grep -q "EVENTS=3"; then
  report "协作事件全程留痕（3 条事件）" 0
else
  report "协作事件全程留痕（3 条事件）" 1
fi
if echo "$out" | grep -q "HAS_HANDOFF=True"; then
  report "审计可回溯 @转交事件" 0
else
  report "审计可回溯 @转交事件" 1
fi

echo "== 7. 经理 Agent 接入协作（game_producer_agent 便捷方法）=="
out=$($PY - <<'PYEOF'
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus
bus = MessageBus()
m = GameProducerAgent(bus=bus)
m.boot()
r = m.handoff_wp("wp_client", "system_designer", "client_dev", title="界面")
print("HANDOFF_OK=" + str(r["ok"]))
d = m.delegate_wp("wp_testing", "project_manager",
                  [{"role": "qa_engineer", "desc": "功能"},
                   {"role": "auto_qa", "desc": "自动化"}], title="测试")
print("DELEGATE_OK=" + str(d["ok"]))
print("HAS_COLLAB=" + str(hasattr(m, "collab")))
PYEOF
)
if echo "$out" | grep -q "HANDOFF_OK=True"; then
  report "经理可 @转交 工作包" 0
else
  report "经理可 @转交 工作包" 1
fi
if echo "$out" | grep -q "DELEGATE_OK=True"; then
  report "经理可 @分工 工作包" 0
else
  report "经理可 @分工 工作包" 1
fi
if echo "$out" | grep -q "HAS_COLLAB=True"; then
  report "经理已接入协作工作台 collab" 0
else
  report "经理已接入协作工作台 collab" 1
fi


echo "== 8. 评审修复回归：无 A->A 自环 / REJECT owner / 连续回退 / 弹链 =="
out=$($PY - <<'PYEOF'
from role_collaboration import CollaborationWorkbench
wb = CollaborationWorkbench()
r = wb.handoff("r1", "任务", "A", "B")
chain = r["record"].transfer_chain
print("NO_SELF_LOOP=" + str(not any(l.split("->")[0] == l.split("->")[1] for l in chain)))
wb2 = CollaborationWorkbench()
wb2.handoff("r2", "任务2", "A", "B")
r2 = wb2.acknowledge("r2", "B", "REJECT", reason="忙")
print("REJECT_OWNER=" + r2["record"].owner)
wb3 = CollaborationWorkbench()
wb3.handoff("r3", "任务3", "A", "B")
wb3.acknowledge("r3", "B", "ACCEPT")
wb3.acknowledge("r3", "B", "REHANDOFF", reassign_to="C")
r3 = wb3.acknowledge("r3", "C", "RETURN", reason="回退")
r3b = wb3.acknowledge("r3", "B", "RETURN", reason="再回退")
print("CONTINUOUS_RETURN_OWNER=" + r3b["record"].owner)
print("POP_TAIL_CHAIN=" + ";".join(wb3.audit("r3")["transfer_chain"]))
r4 = wb3.acknowledge("nope", "X", "ACCEPT")
print("FAIL_HAS_RECORD=" + str("record" in r4))
r5 = wb3.acknowledge("r3", "B", "BAD_ACTION")
print("UNKNOWN_HAS_RECORD=" + str("record" in r5))
PYEOF
)
if echo "$out" | grep -q "NO_SELF_LOOP=True"; then
  report "转交链无 A->A 虚假自环" 0
else
  report "转交链无 A->A 虚假自环" 1
fi
if echo "$out" | grep -q "REJECT_OWNER=A"; then
  report "REJECT 后 owner 重置为发起者" 0
else
  report "REJECT 后 owner 重置为发起者" 1
fi
if echo "$out" | grep -q "CONTINUOUS_RETURN_OWNER=A"; then
  report "RETURN 连续回退不死锁" 0
else
  report "RETURN 连续回退不死锁" 1
fi
if echo "$out" | grep -q "POP_TAIL_CHAIN=$"; then
  report "RETURN 弹出转交链末节点" 0
else
  report "RETURN 弹出转交链末节点" 1
fi
if echo "$out" | grep -q "FAIL_HAS_RECORD=True" && echo "$out" | grep -q "UNKNOWN_HAS_RECORD=True"; then
  report "失败/未知动作统一返回含 record 键" 0
else
  report "失败/未知动作统一返回含 record 键" 1
fi

echo "== 9. 消息类型三处登记 =="
out=$($PY - <<'PYEOF'
from message_bus import MESSAGE_TYPES as MB
from agent_behavior import MESSAGE_TYPES as AB
import yaml
with open("roles.yaml") as f:
    doc = yaml.safe_load(f)
def find_mt(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "message_types" and isinstance(v, list):
                return v
            r = find_mt(v)
            if r:
                return r
    elif isinstance(node, list):
        for x in node:
            r = find_mt(x)
            if r:
                return r
    return None
mt = find_mt(doc) or []
ok_mb = all(t in MB for t in ("HANDOFF", "DELEGATE", "COLLAB_REQ", "ACK", "COLLAB_NOTIFY"))
ok_ab = all(t in AB for t in ("HANDOFF", "DELEGATE", "COLLAB_REQ", "ACK", "COLLAB_NOTIFY"))
ok_yaml = all(t in mt for t in ("HANDOFF", "DELEGATE", "COLLAB_REQ", "ACK", "COLLAB_NOTIFY"))
print("MB_OK=" + str(ok_mb))
print("AB_OK=" + str(ok_ab))
print("YAML_OK=" + str(ok_yaml))
PYEOF
)
if echo "$out" | grep -q "MB_OK=True"; then
  report "message_bus 登记 5 种协作消息类型" 0
else
  report "message_bus 登记 5 种协作消息类型" 1
fi
if echo "$out" | grep -q "AB_OK=True"; then
  report "agent_behavior 登记 5 种协作消息类型" 0
else
  report "agent_behavior 登记 5 种协作消息类型" 1
fi
if echo "$out" | grep -q "YAML_OK=True"; then
  report "roles.yaml 登记 5 种协作消息类型" 0
else
  report "roles.yaml 登记 5 种协作消息类型" 1
fi

echo "== 10. 任意角色接入协作路由 + 幂等守卫 =="
out=$($PY - <<'PYEOF'
from department_agents import DesignDeptAgent
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, Message

bus = MessageBus()
dept = DesignDeptAgent(bus)
dept.boot()
bus.publish(Message("HANDOFF", "producer", "lead_designer",
                    {"task_id": "wp_x", "title": "设计", "note": ""}))
bus.process_all()
dept_ok = dept.collab.get("wp_x") is not None
print("DEPT_ROUTE=" + str(dept_ok))

bus2 = MessageBus()
m = GameProducerAgent(bus=bus2)
m.boot()
m.handoff_wp("wp_y", "system_designer", "client_dev", title="界面")
bus2.process_all()
rec = m.collab.get("wp_y")
print("HANDOFF_NO_DUP=" + str(rec is not None and len(rec.events) == 1))

bus3 = MessageBus()
m2 = GameProducerAgent(bus=bus3)
m2.boot()
bus3.publish(Message("HANDOFF", m2.role_id, m2.role_id, {"task_id": "wp_z", "title": "x"}))
bus3.process_all()
print("IDEMPOTENT=" + str(m2.collab.get("wp_z") is None))
PYEOF
)
if echo "$out" | grep -q "DEPT_ROUTE=True"; then
  report "任意角色（部门Agent）接入协作事件路由" 0
else
  report "任意角色（部门Agent）接入协作事件路由" 1
fi
if echo "$out" | grep -q "HANDOFF_NO_DUP=True"; then
  report "便捷方法单一数据源，无二次处理" 0
else
  report "便捷方法单一数据源，无二次处理" 1
fi
if echo "$out" | grep -q "IDEMPOTENT=True"; then
  report "自发起协作消息幂等守卫生效" 0
else
  report "自发起协作消息幂等守卫生效" 1
fi

echo ""
echo "测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" = "0" ]; then
  echo "🟢 全部通过"
  exit 0
else
  echo "🔴 存在失败项"
  exit 1
fi

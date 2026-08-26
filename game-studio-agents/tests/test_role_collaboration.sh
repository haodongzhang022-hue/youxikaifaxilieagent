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

echo ""
echo "测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" = "0" ]; then
  echo "🟢 全部通过"
  exit 0
else
  echo "🔴 存在失败项"
  exit 1
fi

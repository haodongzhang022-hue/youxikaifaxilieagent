#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：角色协作层 (CollaborationWorkbench)
# 功能定义: 多角色互相@（任务转交 HANDOFF / 分工 DELEGATE /
#           协作请求 COLLAB_REQ / 回执 ACK），全程留痕可审计。
# 验收标准: 转交/分工/协作请求/回执均正确执行，状态流转正确。
# 退出码: 0 = 🟢 通过，1 = 🔴 阻塞
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/../../config"
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

echo "== 功能模块验收：角色协作层 (CollaborationWorkbench) =="

out=$($PY - <<'PYEOF'
from role_collaboration import CollaborationWorkbench, HANDOFF, DELEGATE, COLLAB_REQ, ACK

# 1. 创建协作工作台
wb = CollaborationWorkbench()
print(f"WORKBENCH_CREATED=True")

# 2. @转交（HANDOFF）
result = wb.handoff("wp_client", "客户端任务", "system_designer", "client_dev", "把客户端任务转给你")
rec = result.get("record")
print(f"HANDOFF_OK={result.get('ok', False)}")
print(f"HANDOFF_STATUS={rec.status if rec else ''}")
print(f"HANDOFF_OWNER={rec.owner if rec else ''}")

# 3. @分工（DELEGATE）
result = wb.delegate("wp_testing", "测试任务", "qa_engineer", [
    {"role": "qa_engineer", "task": "功能测试"},
    {"role": "auto_qa", "task": "自动化测试"}
])
rec = result.get("record")
print(f"DELEGATE_OK={result.get('ok', False)}")
print(f"DELEGATE_SUBTASKS={len(rec.sub_tasks) if rec else 0}")

# 4. @协作请求（COLLAB_REQ）
result = wb.request_collab("wp_gameplay", "玩法任务", "lead_designer", "program", need="评审技术方案")
print(f"COLLAB_OK={result.get('ok', False)}")
print(f"COLLAB_PEER={result.get('assist_requested_to', '')}")

# 5. 转交链审计（events 是 dict 列表）
audit = wb.audit("wp_client")
print(f"AUDIT_OK={audit.get('ok', False)}")
print(f"AUDIT_COUNT={audit.get('event_count', 0)}")
events = audit.get("events", [])
if events:
    print(f"AUDIT_FIRST={events[0].get('event', '')}")
    print(f"AUDIT_FIRST_FROM={events[0].get('from', '')}")

# 6. 分工进度跟踪
stats = wb.sub_progress("wp_testing")
print(f"PROGRESS_STATS={stats}")

# 7. 回执（ACK）
result = wb.acknowledge("wp_client", "client_dev", action="ACCEPT")
rec = result.get("record")
print(f"ACK_OK={result.get('ok', False)}")
print(f"ACK_STATUS={rec.status if rec else ''}")

# 8. 协作事件类型完整性
print(f"HAS_HANDOFF={HANDOFF == 'HANDOFF'}")
print(f"HAS_DELEGATE={DELEGATE == 'DELEGATE'}")
print(f"HAS_COLLAB={COLLAB_REQ == 'COLLAB_REQ'}")
print(f"HAS_ACK={ACK == 'ACK'}")
PYEOF
)

# 1. 工作台创建
if echo "$out" | grep -q "WORKBENCH_CREATED=True"; then
  report "协作工作台创建成功" 0
else
  report "协作工作台创建成功" 1
fi

# 2. @转交功能
if echo "$out" | grep -q "HANDOFF_OK=True" && echo "$out" | grep -q "HANDOFF_STATUS=OFFERED"; then
  report "@转交功能正确（HANDOFF 状态为 OFFERED）" 0
else
  report "@转交功能正确（HANDOFF 状态为 OFFERED）" 1
fi

# 3. @分工功能
if echo "$out" | grep -q "DELEGATE_OK=True" && echo "$out" | grep -q "DELEGATE_SUBTASKS=2"; then
  report "@分工功能正确（拆分 2 个子任务）" 0
else
  report "@分工功能正确（拆分 2 个子任务）" 1
fi

# 4. @协作请求功能
if echo "$out" | grep -q "COLLAB_OK=True" && echo "$out" | grep -q "COLLAB_PEER=program"; then
  report "@协作请求功能正确（请求程序线）" 0
else
  report "@协作请求功能正确（请求程序线）" 1
fi

# 5. 转交链留痕可审计
if echo "$out" | grep -q "AUDIT_OK=True" && echo "$out" | grep -q "AUDIT_COUNT=.*[1-9]" && echo "$out" | grep -q "AUDIT_FIRST=HANDOFF"; then
  report "转交链全程留痕可审计" 0
else
  report "转交链全程留痕可审计" 1
fi

# 6. 分工进度统计
if echo "$out" | grep -q "PROGRESS_STATS="; then
  report "分工进度统计可用" 0
else
  report "分工进度统计可用" 1
fi

# 7. @回执功能
if echo "$out" | grep -q "ACK_OK=True" && echo "$out" | grep -q "ACK_STATUS=ACCEPTED"; then
  report "@回执功能正确（接受 ACK→ACCEPTED）" 0
else
  report "@回执功能正确（接受 ACK→ACCEPTED）" 1
fi

# 8. 协作消息类型完整
if echo "$out" | grep -q "HAS_HANDOFF=True" && echo "$out" | grep -q "HAS_DELEGATE=True" && echo "$out" | grep -q "HAS_COLLAB=True" && echo "$out" | grep -q "HAS_ACK=True"; then
  report "协作消息类型定义完整（HANDOFF/DELEGATE/COLLAB_REQ/ACK）" 0
else
  report "协作消息类型定义完整（HANDOFF/DELEGATE/COLLAB_REQ/ACK）" 1
fi

echo ""
echo "【角色协作模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 角色协作功能模块验收通过"
exit 0

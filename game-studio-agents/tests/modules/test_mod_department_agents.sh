#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：部门 Agent (DepartmentAgents)
# 功能定义: 六大部门 Agent 执行体，支持部门统一头（小组）机制、
#           组内协作、跨部门协作、工作包执行与验收上报。
# 验收标准: 部门能接收派单、执行工作包、上报验收、组内协作拆派。
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

echo "== 功能模块验收：部门 Agent (DepartmentAgents) =="

out=$($PY - <<'PYEOF'
from department_agents import build_department_agents, DepartmentAgent
from game_producer_agent import DEPARTMENTS
from message_bus import MessageBus, Message, build_message

# 1. 创建全部部门 Agent
bus = MessageBus()
agents = build_department_agents(bus)
print(f"DEPT_AGENT_COUNT={len(agents)}")
print(f"DEPT_KEYS={sorted(agents.keys())}")

# 2. 验证部门 Agent role 名称
for key, agent in agents.items():
    print(f"AGENT_{key.upper()}={agent.role_id}")

# 3. QA 部门存在
qa_agent = agents.get("qa")
print(f"QA_AGENT_FOUND={qa_agent is not None}")

# 4. 部门角色注册到总线
print(f"QA_REGISTERED={'qa_engineer' in bus.roles}")
print(f"DEPT_NAME_REGISTERED={'测试线' in bus.roles}")

# 5. 通过消息派单驱动部门执行（而不是直接调 _execute）
wp = {
    "id": "wp_testing_module",
    "module": "testing",
    "label": "测试",
    "department_name": "测试线"
}
msg = build_message("TASK_ASSIGN", "scheduler", "qa_engineer",
                    {"task_id": "wp_testing_module", "payload": {"work_package": wp}})
bus.publish(msg)
bus.process_all()
print(f"QA_DONE_AFTER_ASSIGN={qa_agent.done_packages}")
print(f"QA_BIZ_STATE={qa_agent.biz_state}")

# 6. 验证 REVIEW_RESULT 已上报
review_msgs = [m for m in bus.delivered if m.type == "REVIEW_RESULT"]
print(f"REVIEW_RESULT_COUNT={len(review_msgs)}")
if review_msgs:
    print(f"REVIEW_RESULT_TO={review_msgs[0].to_role}")

# 7. 验证部门角色映射完整性
all_roles = []
for key, dept in DEPARTMENTS.items():
    all_roles.extend(dept.get("roles", []))
print(f"TOTAL_DEPT_ROLES={len(all_roles)}")

# 8. 验证每部门 agent 的部门名
print(f"DESIGN_DEPT_NAME={agents.get('design').department if agents.get('design') else ''}")

# 9. 验证组内协作（internal_assignments 字段处理）
wp_collab = {
    "id": "wp_collab_module",
    "module": "testing",
    "label": "测试协作",
    "department_name": "测试线",
    "internal_assignments": [
        {"role": "qa_engineer", "task": "功能测试"},
        {"role": "auto_qa", "task": "自动化测试"}
    ]
}
msg2 = build_message("TASK_ASSIGN", "scheduler", "qa_engineer",
                     {"task_id": "wp_collab_module", "payload": {"work_package": wp_collab}})
bus.publish(msg2)
bus.process_all()
print(f"COLLAB_DONE={qa_agent.done_packages}")
print(f"COLLAB_SUBTASKS={list(qa_agent.internal_subtasks.keys()) if qa_agent.internal_subtasks else []}")
PYEOF
)

# 1. 六大部门 Agent 全部创建
if echo "$out" | grep -q "DEPT_AGENT_COUNT=6"; then
  report "六大部门 Agent 全部创建" 0
else
  report "六大部门 Agent 全部创建" 1
fi

# 2. 部门键正确
if echo "$out" | grep -q "DEPT_KEYS=\['art', 'design', 'ops', 'pm', 'program', 'qa'\]"; then
  report "部门 Agent 键正确" 0
else
  report "部门 Agent 键正确" 1
fi

# 3. 各部门 Agent role 正确
if echo "$out" | grep -q "AGENT_DESIGN=.*lead_designer" && echo "$out" | grep -q "AGENT_PROGRAM=.*cto" && echo "$out" | grep -q "AGENT_QA=.*qa_engineer"; then
  report "各部门 Agent 角色正确" 0
else
  report "各部门 Agent 角色正确" 1
fi

# 4. QA 部门存在
if echo "$out" | grep -q "QA_AGENT_FOUND=True"; then
  report "测试线部门 Agent 存在" 0
else
  report "测试线部门 Agent 存在" 1
fi

# 5. 部门角色注册到总线
if echo "$out" | grep -q "QA_REGISTERED=True"; then
  report "部门角色注册到消息总线" 0
else
  report "部门角色注册到消息总线" 1
fi

# 6. 部门名注册为可寻址
if echo "$out" | grep -q "DEPT_NAME_REGISTERED=True"; then
  report "部门名注册为可寻址角色（@部门名）" 0
else
  report "部门名注册为可寻址角色（@部门名）" 1
fi

# 7. 派单驱动部门执行
if echo "$out" | grep -q "QA_DONE_AFTER_ASSIGN=.*wp_testing_module"; then
  report "派单驱动部门 Agent 执行工作包并记录完成" 0
else
  report "派单驱动部门 Agent 执行工作包并记录完成" 1
fi

# 8. REVIEW_RESULT 上报
if echo "$out" | grep -q "REVIEW_RESULT_COUNT=.*[1-9]" && echo "$out" | grep -q "REVIEW_RESULT_TO=producer"; then
  report "部门 Agent 上报 REVIEW_RESULT 给经理" 0
else
  report "部门 Agent 上报 REVIEW_RESULT 给经理" 1
fi

# 9. 全部部门角色注册
if echo "$out" | grep -q "TOTAL_DEPT_ROLES=.*[2-9][0-9]"; then
  report "全部部门角色注册（20+ 角色）" 0
else
  report "全部部门角色注册（20+ 角色）" 1
fi

# 10. 部门名映射正确
if echo "$out" | grep -q "DESIGN_DEPT_NAME=策划线"; then
  report "部门 Agent 部门名映射正确" 0
else
  report "部门 Agent 部门名映射正确" 1
fi

# 11. 组内协作记录
if echo "$out" | grep -q "COLLAB_SUBTASKS=.*wp_collab_module"; then
  report "部门 Agent 组内协作拆派记录完整" 0
else
  report "部门 Agent 组内协作拆派记录完整" 1
fi

echo ""
echo "【部门 Agent 模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 部门 Agent 功能模块验收通过"
exit 0

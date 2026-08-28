#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：合并确认 Agent (MergedConfirmAgent)
# 功能定义: 探查带「已合并」标签且 open 的 Issue，确认判定
#           close / new_issue / keep，输出结构化决策表。
# 验收标准: 探查正确、确认判定准确、决策输出完整。
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

echo "== 功能模块验收：合并确认 Agent (MergedConfirmAgent) =="

out=$($PY - <<'PYEOF'
from merged_confirm_agent import MergedConfirmAgent, MergedIssue, DECISION_CLOSE, DECISION_NEW_ISSUE, DECISION_KEEP

# 1. 创建 Agent
agent = MergedConfirmAgent()
print(f"AGENT_CREATED=True")

# 2. 构造测试 Issues
issues = [
    {"number": "1", "title": "已完成功能", "state": "open", "labels": ["已合并"], "body": "功能已完成"},
    {"number": "2", "title": "待推进", "state": "open", "labels": ["已合并"], "body": "下一阶段：需要继续推进"},
    {"number": "3", "title": "讨论中", "state": "open", "labels": ["已合并"], "body": "模糊讨论，无明确排期"},
    {"number": "4", "title": "非合并", "state": "open", "labels": ["其他"], "body": "没有合并标签"},
]

# 3. 探查
candidates = agent.probe(issues)
print(f"PROBE_COUNT={len(candidates)}")

# 4. 确认
agent.confirm(candidates)

# 5. 决策输出
result = agent.decide()
print(f"DECISIONS_COUNT={result['probed_count']}")
for d in result['decided']:
    print(f"DECISION:{d['number']}={d['decision']}")

# 6. 决策类型
print(f"HAS_CLOSE={DECISION_CLOSE == 'close'}")
print(f"HAS_NEW_ISSUE={DECISION_NEW_ISSUE == 'new_issue'}")
print(f"HAS_KEEP={DECISION_KEEP == 'keep'}")
PYEOF
)

# 1. Agent 创建
if echo "$out" | grep -q "AGENT_CREATED=True"; then
  report "合并确认 Agent 创建成功" 0
else
  report "合并确认 Agent 创建成功" 1
fi

# 2. 探查筛选
if echo "$out" | grep -q "PROBE_COUNT=3"; then
  report "探查正确筛选出已合并标签 Issue（3 个）" 0
else
  report "探查正确筛选出已合并标签 Issue（3 个）" 1
fi

# 3. 决策输出完整
if echo "$out" | grep -q "DECISIONS_COUNT=3"; then
  report "决策输出完整（3 个判定）" 0
else
  report "决策输出完整（3 个判定）" 1
fi

# 4. close 判定
if echo "$out" | grep -q "DECISION:1=close"; then
  report "已完成功能→close 判定" 0
else
  report "已完成功能→close 判定" 1
fi

# 5. new_issue 判定
if echo "$out" | grep -q "DECISION:2=new_issue"; then
  report "有后续任务→new_issue 判定" 0
else
  report "有后续任务→new_issue 判定" 1
fi

# 6. keep 判定
if echo "$out" | grep -q "DECISION:3=keep"; then
  report "模糊讨论→keep 判定" 0
else
  report "模糊讨论→keep 判定" 1
fi

# 7. 决策类型常量
if echo "$out" | grep -q "HAS_CLOSE=True" && echo "$out" | grep -q "HAS_NEW_ISSUE=True" && echo "$out" | grep -q "HAS_KEEP=True"; then
  report "决策类型定义完整" 0
else
  report "决策类型定义完整" 1
fi

echo ""
echo "【合并确认模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 合并确认功能模块验收通过"
exit 0

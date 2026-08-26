# ============================================================
# 合并确认 Agent 测试信号灯
# 说明: 验证「合并确认 Agent」的核心逻辑：
#       1. 探查：筛出带「已合并」标签且 open 状态的 Issue；
#       2. 确认：判定是否还有内容需要推进（close / new_issue / keep）；
#       3. 决策汇总：输出结构化决策表供「合并确认员」NPC 使用。
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

echo "== 1. 合并确认 Agent 探查（筛出已合并标签 + open）=="
out=$($PY - <<'PY'
from merged_confirm_agent import MergedConfirmAgent

a = MergedConfirmAgent()
issues = [
    {"number": "14", "state": "open", "title": "安全改进",
     "body": "已合并，下游工作包已由 #24 承接",
     "labels": [{"name": "安全加固已合并"}], "comment_count": 4},
    {"number": "10", "state": "open", "title": "对比借鉴开源项目",
     "body": "已合并，下游已由 #16/#19 承接",
     "labels": [{"name": "经理编排已合并"}], "comment_count": 9},
    {"number": "24", "state": "closed", "title": "安全加固下游",
     "body": "已完成", "labels": [{"name": "下游工作包"}], "comment_count": 1},
    {"number": "5", "state": "open", "title": "审核PR",
     "body": "无已合并标签", "labels": [], "comment_count": 1},
]
candidates = a.probe(issues)
print("probed=%d" % len(candidates))
print("numbers=%s" % sorted(c.number for c in candidates))
PY
)
report "探查到已合并标签+open的 Issue" $?
echo "$out"

echo "== 2. 确认判定（close / new_issue / keep）=="
out=$($PY - <<'PY'
from merged_confirm_agent import MergedConfirmAgent, DECISION_CLOSE, DECISION_NEW_ISSUE

a = MergedConfirmAgent()
issues = [
    # 下游已承接 → close
    {"number": "14", "state": "open", "title": "安全改进",
     "body": "已合并，下游工作包已由 #24 承接",
     "labels": [{"name": "安全加固已合并"}], "comment_count": 4},
    # 有下一阶段但未派发 → new_issue
    {"number": "29", "state": "open", "title": "跨仓库调用",
     "body": "已合并，但仍有下一阶段待推进，未派发完成",
     "labels": [{"name": "跨仓库已合并"}], "comment_count": 3},
    # 无后续任务 → close
    {"number": "99", "state": "open", "title": "简单修复",
     "body": "已完成",
     "labels": [{"name": "修复已合并"}], "comment_count": 1},
]
candidates = a.probe(issues)
decided = a.confirm(candidates)
for d in decided:
    print("%s=%s" % (d.number, d.decision))
PY
)
report "确认判定输出" $?
echo "$out"

# 校验 close 决策
out=$($PY - <<'PY'
from merged_confirm_agent import MergedConfirmAgent, DECISION_CLOSE, DECISION_NEW_ISSUE
a = MergedConfirmAgent()
issues = [
    {"number": "14", "state": "open", "title": "安全改进",
     "body": "已合并，下游工作包已由 #24 承接",
     "labels": [{"name": "安全加固已合并"}], "comment_count": 4},
    {"number": "29", "state": "open", "title": "跨仓库调用",
     "body": "已合并，但仍有下一阶段待推进，未派发完成",
     "labels": [{"name": "跨仓库已合并"}], "comment_count": 3},
    {"number": "99", "state": "open", "title": "简单修复",
     "body": "已完成",
     "labels": [{"name": "修复已合并"}], "comment_count": 1},
]
candidates = a.probe(issues)
decided = a.confirm(candidates)
res = {d.number: d.decision for d in decided}
ok = (res.get("14") == DECISION_CLOSE and
      res.get("29") == DECISION_NEW_ISSUE and
      res.get("99") == DECISION_CLOSE)
print("all_ok=%s" % ok)
PY
)
if echo "$out" | grep -q "all_ok=True"; then
  report "确认判定正确（14=close, 29=new_issue, 99=close）" 0
else
  report "确认判定正确（14=close, 29=new_issue, 99=close）" 1
  echo "$out"
fi

echo "== 3. 决策汇总（结构化决策表）=="
out=$($PY - <<'PY'
from merged_confirm_agent import MergedConfirmAgent

a = MergedConfirmAgent()
issues = [
    {"number": "14", "state": "open", "title": "安全改进",
     "body": "已合并，下游工作包已由 #24 承接",
     "labels": [{"name": "安全加固已合并"}], "comment_count": 4},
    {"number": "1", "state": "open", "title": "岗位探查",
     "body": "已合并，下一阶段已由 #27 承接",
     "labels": [{"name": "生态角色体系已合并"}], "comment_count": 7},
]
a.probe(issues)
a.confirm()
result = a.decide()
print("probed=%d" % result["probed_count"])
print("close=%d" % result["close_count"])
print("decided_len=%d" % len(result["decided"]))
print("has_suggested=%s" % all(d.get("suggested_action") for d in result["decided"]))
PY
)
report "决策汇总输出" $?
echo "$out"

if echo "$out" | grep -q "probed=2" && echo "$out" | grep -q "close=2"; then
  report "决策汇总正确（2 个候选、2 个 close）" 0
else
  report "决策汇总正确（2 个候选、2 个 close）" 1
fi

echo ""
echo "======== 汇总 ========"
echo "通过: $pass  失败: $fail"
if [ "$fail" -gt 0 ]; then
  echo "❌ 合并确认 Agent 测试未通过"
  exit 1
else
  echo "✅ 合并确认 Agent 测试全部通过"
  exit 0
fi

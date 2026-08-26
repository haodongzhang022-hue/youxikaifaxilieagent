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

echo "== 4. 启发式防误判回归（评审点 1-3）=="
out=$($PY - <<'PY'
from merged_confirm_agent import (
    MergedConfirmAgent, DECISION_CLOSE, DECISION_KEEP, DECISION_NEW_ISSUE,
)

# 评审点1：MERGED_LABEL_KEYWORDS 无重复元素
kw = MergedConfirmAgent.MERGED_LABEL_KEYWORDS
no_dup = len(kw) == len(set(kw))

# 评审点2：未带 #编号 的「已由…承接」不误判 close；「已通过评审/已修复 bug」不误判 keep
a = MergedConfirmAgent()
issues = [
    # 已通过评审、已修复 bug → 已完成表述，不应 KEEP
    {"number": "201", "state": "open", "title": "已通过评审的模块",
     "body": "功能已实现，已通过代码评审，已修复发现的 bug", "labels": [{"name": "已合并"}], "comment_count": 1},
    # 未带编号的「已由负责人正在讨论」→ 未落地，不应 CLOSE（无 # 锚点）
    {"number": "202", "state": "open", "title": "讨论中的功能",
     "body": "已合并，已由负责人正在讨论后续方案", "labels": [{"name": "已合并"}], "comment_count": 2},
]
decided = a.confirm(a.probe(issues))
res = {d.number: d.decision for d in decided}
# 201：无后续/无阻塞 → CLOSE（完成态），不得误判 KEEP
ok_201 = res.get("201") == DECISION_CLOSE
# 202：含「正在讨论」模糊后续 → KEEP（保守保留，不新建 Issue 不关闭）
ok_202 = res.get("202") == DECISION_KEEP

# 评审点3：decide() 未 confirm 但有候选时自动补齐，probed>0 时 decided 非空
b = MergedConfirmAgent()
b.probe([
    {"number": "203", "state": "open", "title": "已完成", "body": "已完成无后续",
     "labels": [{"name": "已合并"}], "comment_count": 0},
])
r = b.decide()
ok_autofill = r["probed_count"] > 0 and len(r["decided"]) > 0

print("no_dup=%s ok_201=%s ok_202=%s ok_autofill=%s" % (no_dup, ok_201, ok_202, ok_autofill))
PY
)
if echo "$out" | grep -q "no_dup=True ok_201=True ok_202=True ok_autofill=True"; then
  report "启发式防误判回归（无重复/不误关/模糊讨论KEEP/decide自动补齐）" 0
else
  report "启发式防误判回归（无重复/不误关/模糊讨论KEEP/decide自动补齐）" 1
  echo "$out"
fi

echo "== 5. 「后续」精度回归（评审点 3 修正验证）=="
out=$($PY - <<'PY'
from merged_confirm_agent import (
    MergedConfirmAgent, DECISION_CLOSE, DECISION_KEEP, DECISION_NEW_ISSUE,
)

# 评审点3a：宽泛「后续方案」不触发 NEW_ISSUE（已由负责人正在讨论 → KEEP）
a = MergedConfirmAgent()
issues = [
    # 模糊「后续方案」→ 不触发 NEW_ISSUE；「正在讨论」→ KEEP
    {"number": "301", "state": "open", "title": "讨论中的方案",
     "body": "已合并，已由负责人正在讨论后续方案", "labels": [{"name": "已合并"}], "comment_count": 2},
    # 精准「后续任务」→ NEW_ISSUE（明确有后续但未派发）
    {"number": "302", "state": "open", "title": "有后续任务",
     "body": "已合并，但仍有后续任务待推进，未派发", "labels": [{"name": "已合并"}], "comment_count": 3},
    # 「后续方案已定」无模糊讨论 → 不误判 KEEP，也不 NEW_ISSUE（无精准关键词）→ CLOSE
    {"number": "303", "state": "open", "title": "方案已定",
     "body": "已合并，后续方案已确定并落地", "labels": [{"name": "已合并"}], "comment_count": 1},
]
decided = a.confirm(a.probe(issues))
res = {d.number: d.decision for d in decided}
ok_301 = res.get("301") == DECISION_KEEP
ok_302 = res.get("302") == DECISION_NEW_ISSUE
ok_303 = res.get("303") == DECISION_CLOSE
print("ok_301=%s ok_302=%s ok_303=%s" % (ok_301, ok_302, ok_303))
PY
)
if echo "$out" | grep -q "ok_301=True ok_302=True ok_303=True"; then
  report "「后续」精度回归（模糊讨论KEEP/精准后续NEW/无后续CLOSE）" 0
else
  report "「后续」精度回归（模糊讨论KEEP/精准后续NEW/无后续CLOSE）" 1
  echo "$out"
fi

echo "== 6. 启发式精度回归（Bug A/B + 版本号 + 下游优先 + merged大小写）=="
out=$($PY - <<'PY'
from merged_confirm_agent import (
    MergedConfirmAgent, DECISION_CLOSE, DECISION_KEEP, DECISION_NEW_ISSUE,
)

# Bug A：否定/完成态不误判 NEW_ISSUE
a = MergedConfirmAgent()
issues = [
    {"number": "401", "state": "open", "title": "无后续",
     "body": "已合并，无后续任务，可关闭", "labels": [{"name": "已合并"}], "comment_count": 1},
    {"number": "402", "state": "open", "title": "后续已完成",
     "body": "已合并，后续任务已完成落地", "labels": [{"name": "已合并"}], "comment_count": 1},
    # Bug B：来源/关联引用不误判 close（有未派发后续时不该被短路为 close）
    {"number": "403", "state": "open", "title": "来源引用",
     "body": "已合并，仍有下一阶段待推进未派发。该需求由 #100 提出",
     "labels": [{"name": "已合并"}], "comment_count": 1},
    {"number": "404", "state": "open", "title": "关联引用",
     "body": "已合并，仍有后续任务待推进未派发。已完成，关联 #55",
     "labels": [{"name": "已合并"}], "comment_count": 1},
    # 真实承接 → close
    {"number": "405", "state": "open", "title": "真实承接",
     "body": "已合并，下游工作包已由 #24 承接", "labels": [{"name": "已合并"}], "comment_count": 1},
    # 裸版本号完成态 → 不误判 NEW_ISSUE
    {"number": "406", "state": "open", "title": "版本号",
     "body": "已在 v1.0 交付完成", "labels": [{"name": "已合并"}], "comment_count": 1},
    # 阶段+版本组合 → NEW_ISSUE
    {"number": "407", "state": "open", "title": "版本阶段",
     "body": "已合并，下一阶段 v2.0 待推进未派发", "labels": [{"name": "已合并"}], "comment_count": 1},
]
decided = a.confirm(a.probe(issues))
res = {d.number: d.decision for d in decided}
ok_401 = res.get("401") == DECISION_CLOSE
ok_402 = res.get("402") == DECISION_CLOSE
ok_403 = res.get("403") == DECISION_NEW_ISSUE
ok_404 = res.get("404") == DECISION_NEW_ISSUE
ok_405 = res.get("405") == DECISION_CLOSE
ok_406 = res.get("406") == DECISION_CLOSE
ok_407 = res.get("407") == DECISION_NEW_ISSUE

# merged 大小写不敏感 + 无「已上线」
b = MergedConfirmAgent()
cands = b.probe([
    {"number": "501", "state": "open", "title": "t", "body": "已完成",
     "labels": [{"name": "MERGED 完成"}], "comment_count": 1},
    {"number": "502", "state": "open", "title": "t", "body": "已完成",
     "labels": [{"name": "已上线"}], "comment_count": 1},  # 已移除 → 不probe
])
ok_merged = sorted(c.number for c in cands) == ["501"]
no_shangxian = "已上线" not in MergedConfirmAgent.MERGED_LABEL_KEYWORDS

print("ok_401=%s ok_402=%s ok_403=%s ok_404=%s ok_405=%s ok_406=%s ok_407=%s ok_merged=%s no_shangxian=%s" %
      (ok_401, ok_402, ok_403, ok_404, ok_405, ok_406, ok_407, ok_merged, no_shangxian))
PY
)
if echo "$out" | grep -q "ok_401=True ok_402=True ok_403=True ok_404=True ok_405=True ok_406=True ok_407=True ok_merged=True no_shangxian=True"; then
  report "启发式精度回归（否定/完成态/来源关联引用/版本号/下游/merged大小写）" 0
else
  report "启发式精度回归（否定/完成态/来源关联引用/版本号/下游/merged大小写）" 1
  echo "$out"
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

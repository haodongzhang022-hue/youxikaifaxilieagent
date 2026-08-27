#!/usr/bin/env bash
# ============================================================
# 框架自升级闭环 · 四环节验收测试信号灯（wp_testing）
# 说明: 验证 wp_testing（测试线·qa_engineer）对框架自升级闭环的
#       「触发→评估→决策→留痕」四环节做端到端验收。
#       验收对象 = wp_server（共享记忆接线）+ wp_data_ops（记录沉淀）
#       已合并产出，本测试验证二者联动后的完整闭环是否符合政策要求。
#
# 验收维度：
#   1. 触发环节：各类触发信号（P0缺口/评审反复/用户诉求/10轮超限）可识别留痕
#   2. 评估环节：影响面/可行性/风险/优先级四步评估完整沉淀
#   3. 决策环节：人类 CP 拍板（批准/打回/搁置）正确记录且可追溯
#   4. 留痕环节：升级记录「只增不改只追加」不可变，历史可回溯
#   5. 端到端闭环：一次完整升级从触发到留痕全链路可验证
#
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

echo "============================================================"
echo "框架自升级闭环 · 四环节验收测试（wp_testing·qa_engineer）"
echo "============================================================"

echo ""
echo "== 1. 触发环节验收：各类触发信号可识别并留痕 =="
out1=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.abspath("../../game-architect-team/src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_memory import FrameworkUpgradeMemory

fmu = FrameworkUpgradeMemory()

# 5 类触发信号（对齐 FRAMEWORK_UPGRADE.md 第一节）
signals = [
    ("P0 缺口", "新能力调研发现 P0 缺口"),
    ("评审反复", "评审反复指出同类问题≥3次"),
    ("用户诉求", "用户提出新架构诉求"),
    ("10轮超限", "10 轮修复上限触发"),
    ("多源叠加", "多源触发信号并存"),
]

# 每种信号触发一条记录
for name, trigger_text in signals:
    rec = fmu.record_trigger(trigger_text, {"source": name}, upg_id=f"TEST-{name}")
    assert rec.content["type"] == "trigger", f"{name} 记录类型错误"
    assert trigger_text in rec.content["trigger"], f"{name} 触发内容错误"

# 查询所有触发记录
triggers = [r for r in fmu.query_upgrades(keyword="trigger") if r.content.get("type") == "trigger"]
print("TRIGGER_COUNT=", len(triggers))
print("HAS_P0=", any("P0 缺口" in r.content["trigger"] for r in triggers))
print("HAS_REVIEW=", any("评审反复" in r.content["trigger"] for r in triggers))
print("HAS_USER=", any("用户提出" in r.content["trigger"] for r in triggers))
print("HAS_10ROUND=", any("10 轮修复" in r.content["trigger"] for r in triggers))
print("HAS_MULTI=", any("多源触发" in r.content["trigger"] for r in triggers))
PYEOF
)

if echo "$out1" | grep -q "TRIGGER_COUNT= 5"; then
  report "5 类触发信号均可识别并留痕" 0
else
  report "5 类触发信号均可识别并留痕" 1
fi

for sig in HAS_P0 HAS_REVIEW HAS_USER HAS_10ROUND HAS_MULTI; do
  if echo "$out1" | grep -q "$sig= True"; then
    report "触发信号 $sig 正确记录" 0
  else
    report "触发信号 $sig 正确记录" 1
  fi
done

echo ""
echo "== 2. 评估环节验收：影响面/可行性/风险/优先级完整 =="
out2=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.abspath("../../game-architect-team/src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_memory import FrameworkUpgradeMemory

fmu = FrameworkUpgradeMemory()

# 完整评估：影响面 + 可行性 + 风险 + 优先级
fmu.record_evaluation(
    "UPG-001",
    impact={"scope": "框架治理", "modules": ["docs/FRAMEWORK_UPGRADE.md"],
            "compat": "向后兼容", "rollback": "回退到旧版"},
    feasibility={"tech": "可行", "resource": "充足", "dependency": "无阻塞",
                 "strategy": "分阶段"},
    risk={"level": "低", "mitigation": "测试信号灯+回退路径",
          "acceptance": "可接受"},
    priority="P0",
    owner="cto",
)

evals = [r for r in fmu.query_upgrades(keyword="evaluation") if r.content.get("type") == "evaluation"]
print("EVAL_COUNT=", len(evals))
if evals:
    e = evals[-1]
    print("HAS_IMPACT=", bool(e.content.get("impact")))
    print("HAS_FEASIBILITY=", bool(e.content.get("feasibility")))
    print("HAS_RISK=", bool(e.content.get("risk")))
    print("HAS_PRIORITY=", bool(e.content.get("priority")))
    print("PRIORITY_VALUE=", e.content.get("priority", ""))
    print("RISK_LEVEL=", e.content.get("risk", {}).get("level", ""))
    print("HAS_ROLLBACK=", "rollback" in e.content.get("impact", {}))
    print("HAS_MITIGATION=", bool(e.content.get("risk", {}).get("mitigation")))
PYEOF
)

if echo "$out2" | grep -q "EVAL_COUNT= 1"; then
  report "评估记录已写入" 0
else
  report "评估记录已写入" 1
fi

for item in HAS_IMPACT HAS_FEASIBILITY HAS_RISK HAS_PRIORITY HAS_ROLLBACK HAS_MITIGATION; do
  if echo "$out2" | grep -q "$item= True"; then
    report "评估环节 $item 完整" 0
  else
    report "评估环节 $item 完整" 1
  fi
done

if echo "$out2" | grep -q "PRIORITY_VALUE= P0"; then
  report "优先级正确（P0）" 0
else
  report "优先级正确（P0）" 1
fi

if echo "$out2" | grep -q "RISK_LEVEL= 低"; then
  report "风险等级正确（低）" 0
else
  report "风险等级正确（低）" 1
fi

echo ""
echo "== 3. 决策环节验收：人类 CP 拍板结果可追溯 =="
out3=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.abspath("../../game-architect-team/src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_memory import FrameworkUpgradeMemory

fmu = FrameworkUpgradeMemory()

# 三种决策结果
fmu.record_decision("UPG-001", "批准", "框架演进需要统一沉淀", owner="producer")
fmu.record_decision("UPG-002", "打回", "影响面未评估完整", owner="producer")
fmu.record_decision("UPG-003", "搁置", "待评估资源优先级", owner="producer")

decisions = [r for r in fmu.query_upgrades(keyword="decision") if r.content.get("type") == "decision"]
print("DECISION_COUNT=", len(decisions))
print("HAS_APPROVE=", any(r.content.get("decision") == "批准" for r in decisions))
print("HAS_REJECT=", any(r.content.get("decision") == "打回" for r in decisions))
print("HAS_HOLD=", any(r.content.get("decision") == "搁置" for r in decisions))
print("HAS_REASON=", all(r.content.get("reason") for r in decisions))
print("DECISION_OWNER_OK=", all(r.owner == "producer" for r in decisions))
PYEOF
)

if echo "$out3" | grep -q "DECISION_COUNT= 3"; then
  report "3 种决策结果均已记录" 0
else
  report "3 种决策结果均已记录" 1
fi

for item in HAS_APPROVE HAS_REJECT HAS_HOLD HAS_REASON DECISION_OWNER_OK; do
  if echo "$out3" | grep -q "$item= True"; then
    report "决策环节 $item 通过" 0
  else
    report "决策环节 $item 通过" 1
  fi
done

echo ""
echo "== 4. 留痕环节验收：只增不改只追加不可变 =="
out4=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.abspath("../../game-architect-team/src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_memory import FrameworkUpgradeMemory

fmu = FrameworkUpgradeMemory()

# 写入一条完整升级记录
rec1 = fmu.record_upgrade(
    trigger="框架自升级闭环缺失（P0 缺口）",
    impact={"scope": "框架治理"},
    feasibility={"tech": "兼容"},
    risk={"level": "低", "mitigation": "回退"},
    priority="P0",
    decision="批准",
    reason="统一沉淀",
    tasks=["定义政策", "接线共享记忆"],
    pr_links=["https://cnb.cool/example/repo/-/pulls/49"],
    version="v0.6.4",
    upg_id="UPG-ACCEPT",
)
old_count = len(fmu.get_all_records())

# 追加一条新记录（只增）
fmu.record_trigger("追加测试", {}, upg_id="UPG-NEW")
new_count = len(fmu.get_all_records())

# 尝试模拟：旧记录仍在且内容不变
old_rec = next(r for r in fmu.get_all_records() if r.mem_id == rec1.mem_id)
content_same = old_rec.content == rec1.content

# 尝试修订：应追加新版本而非覆盖
from shared_memory import SharedMemory
rev = fmu.memory.revise(rec1.mem_id, dict(rec1.content, status="superseded"), acl_check="cto")
all_versions = [r for r in fmu.get_all_records() if r.mem_id == rec1.mem_id]
has_active = any(r.status == "active" for r in all_versions)
has_superseded = any(r.status == "superseded" for r in all_versions)
old_version_kept = any(r.version == 1 for r in all_versions)

print("APPENDED=", new_count > old_count)
print("OLD_CONTENT_SAME=", content_same)
print("REV_NEW_VERSION=", rev.version)
print("HAS_ACTIVE=", has_active)
print("HAS_SUPERSEDED=", has_superseded)
print("OLD_VERSION_KEPT=", old_version_kept)
PYEOF
)

if echo "$out4" | grep -q "APPENDED= True"; then
  report "追加记录后总数增加（只增）" 0
else
  report "追加记录后总数增加（只增）" 1
fi

if echo "$out4" | grep -q "OLD_CONTENT_SAME= True"; then
  report "旧记录内容不可变（不改）" 0
else
  report "旧记录内容不可变（不改）" 1
fi

if echo "$out4" | grep -q "REV_NEW_VERSION= 2"; then
  report "修订追加新版本（version+1）而非覆盖" 0
else
  report "修订追加新版本（version+1）而非覆盖" 1
fi

if echo "$out4" | grep -q "HAS_ACTIVE= True" && echo "$out4" | grep -q "HAS_SUPERSEDED= True"; then
  report "旧版本标 superseded 保留、新版本 active" 0
else
  report "旧版本标 superseded 保留、新版本 active" 1
fi

if echo "$out4" | grep -q "OLD_VERSION_KEPT= True"; then
  report "旧版本 v1 物理保留（只追加不删减）" 0
else
  report "旧版本 v1 物理保留（只追加不删减）" 1
fi

echo ""
echo "== 5. 端到端闭环验收：完整升级全链路可追溯 =="
out5=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.abspath("../../game-architect-team/src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_memory import FrameworkUpgradeMemory

fmu = FrameworkUpgradeMemory()

# 用一条命令完成完整升级闭环
rec = fmu.record_upgrade(
    trigger="用户提出新架构诉求",
    impact={"scope": "协作层", "modules": ["role_collaboration.py"]},
    feasibility={"tech": "可行", "resource": "充足"},
    risk={"level": "中", "mitigation": "分阶段灰度", "acceptance": "可接受"},
    priority="P1",
    decision="批准",
    reason="提升跨部门协作效率",
    tasks=["评估影响面", "实现接线", "补充测试"],
    pr_links=["https://cnb.cool/example/repo/-/pulls/100"],
    version="v0.7",
    upg_id="UPG-E2E",
)

# 从共享记忆中追溯完整闭环
all_recs = fmu.get_all_records()
related = [r for r in all_recs if r.content.get("upgrade_id") == "UPG-E2E"]
types = {r.content.get("type") for r in related}

has_trigger = "trigger" in types
has_evaluation = "evaluation" in types
has_decision = "decision" in types
has_implementation = "implementation" in types
has_upgrade = "upgrade" in types

# 验证升级记录字段完整
upg_rec = next(r for r in related if r.content.get("type") == "upgrade")
has_full_fields = all(
    k in upg_rec.content for k in
    ["upgrade_id", "trigger", "scope", "risk", "priority", "decision", "implemented", "status"]
)

# 验证实现详情
impl = upg_rec.content.get("implemented", {})
has_version = bool(impl.get("version"))
has_pr_links = bool(impl.get("pr_links"))
has_tasks = bool(impl.get("tasks"))

# 验证可追溯性：通过 upgrade_id 可查询到完整记录
queried = fmu.get_upgrade("UPG-E2E")
query_ok = queried is not None and queried.content.get("upgrade_id") == "UPG-E2E"

print("HAS_TRIGGER=", has_trigger)
print("HAS_EVAL=", has_evaluation)
print("HAS_DECISION=", has_decision)
print("HAS_IMPL=", has_implementation)
print("HAS_UPGRADE=", has_upgrade)
print("HAS_FULL_FIELDS=", has_full_fields)
print("HAS_VERSION=", has_version)
print("HAS_PR_LINKS=", has_pr_links)
print("HAS_TASKS=", has_tasks)
print("QUERY_OK=", query_ok)
PYEOF
)

for item in HAS_TRIGGER HAS_EVAL HAS_DECISION HAS_IMPL HAS_UPGRADE; do
  if echo "$out5" | grep -q "$item= True"; then
    report "端到端闭环 $item 环节留痕完整" 0
  else
    report "端到端闭环 $item 环节留痕完整" 1
  fi
done

for item in HAS_FULL_FIELDS HAS_VERSION HAS_PR_LINKS HAS_TASKS QUERY_OK; do
  if echo "$out5" | grep -q "$item= True"; then
    report "端到端闭环 $item 通过" 0
  else
    report "端到端闭环 $item 通过" 1
  fi
done

echo ""
echo "============================================================"
echo "四环节验收汇总"
echo "============================================================"
if [ "$fail" -eq 0 ]; then
  echo "验收结果: $pass 通过 / $fail 失败"
  echo "🟢 框架自升级闭环「触发→评估→决策→留痕」四环节验收通过"
  exit 0
else
  echo "验收结果: $pass 通过 / $fail 失败"
  echo "🔴 框架自升级闭环四环节验收存在阻塞项"
  exit 1
fi

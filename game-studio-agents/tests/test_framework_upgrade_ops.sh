#!/usr/bin/env bash
# ============================================================
# 框架升级记录沉淀与复盘审计测试信号灯（wp_data_ops）
# 说明: 验证 wp_data_ops（运营线·data_analyst）的落地产出——
#       1. UPG-001 升级记录已沉淀进共享记忆（只增不改只追加）；
#       2. 闭环完整性：触发/评估/决策/落地四环节齐全；
#       3. 版本清晰：每条升级记录含版本号；
#       4. 不可变性：旧记录不可删改，只增不改；
#       5. 幂等沉淀：重复执行不产生重复记录（含跨实例）。
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

echo "== 1. 升级记录沉淀（UPG-001 写入共享记忆）=="
out1=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_ops import seed_known_upgrades, list_upgrade_summaries

# 全新内存环境（用新实例保证不污染）
from framework_upgrade_memory import FrameworkUpgradeMemory
fmu = FrameworkUpgradeMemory()

result = seed_known_upgrades(fmu)
seeded_cnt = result["seeded"]
summaries = list_upgrade_summaries(fmu)

# 检查 UPG-001 是否已沉淀
has_upg_001 = any(s["upgrade_id"] == "UPG-001" for s in summaries)
upg_001 = next((s for s in summaries if s["upgrade_id"] == "UPG-001"), None)

print("SEEDED=", seeded_cnt)
print("HAS_UPG_001=", has_upg_001)
if upg_001:
    print("TRIGGER=", upg_001["trigger"])
    print("PRIORITY=", upg_001["priority"])
    print("DECISION=", upg_001["decision"])
    print("VERSION=", upg_001["version"])
    print("STATUS=", upg_001["status"])
PYEOF
)

if echo "$out1" | grep -q "SEEDED= 1"; then
  report "已沉淀 1 条升级记录" 0
else
  report "已沉淀 1 条升级记录" 1
fi

if echo "$out1" | grep -q "HAS_UPG_001= True"; then
  report "UPG-001 已写入共享记忆" 0
else
  report "UPG-001 已写入共享记忆" 1
fi

if echo "$out1" | grep -q "PRIORITY= P0" && echo "$out1" | grep -q "DECISION= 批准"; then
  report "UPG-001 含优先级 P0 与决策批准" 0
else
  report "UPG-001 含优先级 P0 与决策批准" 1
fi

if echo "$out1" | grep -q "VERSION= v0.6.4"; then
  report "UPG-001 含版本号 v0.6.4" 0
else
  report "UPG-001 含版本号 v0.6.4" 1
fi

if echo "$out1" | grep -q "STATUS= active"; then
  report "UPG-001 状态为 active" 0
else
  report "UPG-001 状态为 active" 1
fi

echo "== 2. 复盘审计（闭环完整性/不可变性/状态一致性）=="
out2=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_ops import seed_known_upgrades, audit_upgrade_records
from framework_upgrade_memory import FrameworkUpgradeMemory

fmu = FrameworkUpgradeMemory()
seed_known_upgrades(fmu)
audit = audit_upgrade_records(fmu)

summary = audit["summary"]
immut = audit["immutability"]
status = audit["status_consistency"]

print("CHAIN_RATE=", summary["chain_rate"])
print("VERSION_RATE=", summary["version_rate"])
print("TOTAL=", summary["total_upgrades"])
print("CHAIN_COMPLETE=", summary["chain_complete"])
print("IMMUTABLE_OK=", immut["immutable_ok"])
print("STATUS_VALID=", status["valid"])
print("VERDICT=", audit["verdict"])
print("KINDS=", audit["kind_distribution"])
PYEOF
)

if echo "$out2" | grep -q "CHAIN_RATE= 100.0"; then
  report "闭环完整率 100%（触发/评估/决策/落地四环节齐全）" 0
else
  report "闭环完整率 100%（触发/评估/决策/落地四环节齐全）" 1
fi

if echo "$out2" | grep -q "VERSION_RATE= 100.0"; then
  report "版本清晰率 100%（每条升级记录含版本号）" 0
else
  report "版本清晰率 100%（每条升级记录含版本号）" 1
fi

if echo "$out2" | grep -q "IMMUTABLE_OK= True"; then
  report "不可变性通过（只增不改，旧记录保留）" 0
else
  report "不可变性通过（只增不改，旧记录保留）" 1
fi

if echo "$out2" | grep -q "STATUS_VALID= True"; then
  report "状态一致性通过（active/superseded 合法）" 0
else
  report "状态一致性通过（active/superseded 合法）" 1
fi

if echo "$out2" | grep -q "VERDICT= 通过"; then
  report "审计结论：通过" 0
else
  report "审计结论：通过" 1
fi

echo "== 3. 幂等沉淀（重复执行不产生重复记录）=="
out3=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_ops import seed_known_upgrades, list_upgrade_summaries
from framework_upgrade_memory import FrameworkUpgradeMemory
from shared_memory import SharedMemory

# 同一实例内重复执行
fmu = FrameworkUpgradeMemory()
r1 = seed_known_upgrades(fmu)
s1 = len(list_upgrade_summaries(fmu))
r2 = seed_known_upgrades(fmu)
s2 = len(list_upgrade_summaries(fmu))

# 跨实例：通过序列化共享记忆（模拟持久化重启）
serialized = fmu.memory.to_json()
sm2 = SharedMemory.from_json(serialized)
fmu2 = FrameworkUpgradeMemory(memory=sm2)
r3 = seed_known_upgrades(fmu2)
s3 = len(list_upgrade_summaries(fmu2))

print("FIRST_SEEDED=", r1["seeded"])
print("SECOND_SEEDED=", r2["seeded"])
print("SECOND_SKIPPED=", r2["skipped"])
print("THIRD_SEEDED=", r3["seeded"])
print("THIRD_SKIPPED=", r3["skipped"])
print("COUNT_AFTER_FIRST=", s1)
print("COUNT_AFTER_SECOND=", s2)
print("COUNT_AFTER_THIRD=", s3)
PYEOF
)

if echo "$out3" | grep -q "SECOND_SEEDED= 0" && echo "$out3" | grep -q "SECOND_SKIPPED= 1"; then
  report "同一实例重复沉淀被跳过（幂等）" 0
else
  report "同一实例重复沉淀被跳过（幂等）" 1
fi

if echo "$out3" | grep -q "THIRD_SEEDED= 0" && echo "$out3" | grep -q "THIRD_SKIPPED= 1"; then
  report "跨实例重复沉淀被跳过（幂等）" 0
else
  report "跨实例重复沉淀被跳过（幂等）" 1
fi

echo "== 4. 多升级记录与 topk 截断回归（>2 条全部返回）=="
out4=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_ops import seed_known_upgrades, audit_upgrade_records, list_upgrade_summaries
from framework_upgrade_memory import FrameworkUpgradeMemory

fmu = FrameworkUpgradeMemory()

# 沉淀已知升级记录（UPG-001）
seed_known_upgrades(fmu)

# 再手动写入 UPG-002 和 UPG-003（模拟后续新升级，不走 _KNOWN_UPGRADES 清单）
fmu.record_upgrade(
    trigger="评审反复指出同类问题≥3次",
    impact={"scope": "流水线", "modules": ["game_producer_agent.py"]},
    feasibility={"tech": "兼容", "migration": "中"},
    risk={"level": "中", "mitigation": "分阶段灰度"},
    priority="P1",
    decision="批准",
    reason="评审反馈需框架级修复",
    tasks=["修复评审问题", "补充回归测试"],
    pr_links=["#52"],
    version="v0.7",
    owner="data_analyst",
)
fmu.record_upgrade(
    trigger="用户提出新架构诉求",
    impact={"scope": "协作层", "modules": ["role_collaboration.py"]},
    feasibility={"tech": "可行", "migration": "低"},
    risk={"level": "低", "mitigation": "回退到旧版"},
    priority="P2",
    decision="搁置",
    reason="待评估资源",
    tasks=[],
    pr_links=[],
    version="v0.8",
    owner="data_analyst",
)

# 多升级记录场景：UPG-001/002/003 三条都应完整沉淀
summaries = list_upgrade_summaries(fmu)
total = len(summaries)
ids = sorted(s["upgrade_id"] for s in summaries)
audit = audit_upgrade_records(fmu)

print("TOTAL=", total)
print("IDS=", ids)
print("AUDIT_TOTAL=", audit["summary"]["total_upgrades"])
print("CHAIN_RATE=", audit["summary"]["chain_rate"])
print("VERSION_RATE=", audit["summary"]["version_rate"])
print("VERDICT=", audit["verdict"])
PYEOF
)

if echo "$out4" | grep -q "TOTAL= 3"; then
  report "多升级记录全部返回（3 条未被 topk=10 截断）" 0
else
  report "多升级记录全部返回（3 条未被 topk=10 截断）" 1
fi

if echo "$out4" | grep -q "AUDIT_TOTAL= 3"; then
  report "审计覆盖 3 条升级记录（无截断遗漏）" 0
else
  report "审计覆盖 3 条升级记录（无截断遗漏）" 1
fi

if echo "$out4" | grep -q "CHAIN_RATE= 100.0" && echo "$out4" | grep -q "VERSION_RATE= 100.0"; then
  report "3 条记录闭环完整率 100% + 版本清晰率 100%" 0
else
  report "3 条记录闭环完整率 100% + 版本清晰率 100%" 1
fi

if echo "$out4" | grep -q "VERDICT= 通过"; then
  report "多记录场景审计结论：通过" 0
else
  report "多记录场景审计结论：通过" 1
fi

echo "== 5. 不可变性回归（修订保留旧版本仍判只增不改）=="
out5=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.abspath("../../game-architect-team/src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_ops import seed_known_upgrades, audit_upgrade_records
from framework_upgrade_memory import FrameworkUpgradeMemory

fmu = FrameworkUpgradeMemory()
seed_known_upgrades(fmu)

# 模拟一次修订：修订=追加高版本，原记录标 superseded 保留（只增不改只追加）
target = next((r for r in fmu.get_all_records() if r.kind == "content"), None)
if target:
    fmu.memory.revise(target.mem_id, dict(target.content, note="修订"))

audit = audit_upgrade_records(fmu)
immut = audit["immutability"]
print("IMMUTABLE_OK=", immut["immutable_ok"])
print("SUPERSEDED=", immut["superseded"])
print("VERDICT=", audit["verdict"])
PYEOF
)

if echo "$out5" | grep -q "IMMUTABLE_OK= True"; then
  report "修订保留旧版本（superseded）仍判只增不改（immutable_ok=True）" 0
else
  report "修订保留旧版本（superseded）仍判只增不改（immutable_ok=True）" 1
fi

if echo "$out5" | grep -q "SUPERSEDED= 1"; then
  report "存在 1 条 superseded 旧版本（历史被保留未删除）" 0
else
  report "存在 1 条 superseded 旧版本（历史被保留未删除）" 1
fi

if echo "$out5" | grep -q "VERDICT= 通过"; then
  report "修订场景审计结论仍为通过" 0
else
  report "修订场景审计结论仍为通过" 1
fi

echo "== 6. 共享内存复用持久化（跨调用复用同一 SharedMemory 幂等）=="
out6=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.abspath("../../game-architect-team/src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared_memory import SharedMemory
from framework_upgrade_ops import run_data_ops_upgrade

# 模拟 OpsDeptAgent 模块级共享内存：跨多次调用复用同一 SharedMemory 实例
sm = SharedMemory()
r1 = run_data_ops_upgrade(shared_memory=sm)
r2 = run_data_ops_upgrade(shared_memory=sm)

print("FIRST_SEEDED=", r1["seeded"]["seeded"])
print("SECOND_SEEDED=", r2["seeded"]["seeded"])
print("SECOND_SKIPPED=", r2["seeded"]["skipped"])
print("VERDICT=", r2["audit"]["verdict"])
PYEOF
)

if echo "$out6" | grep -q "FIRST_SEEDED= 1"; then
  report "首次调用沉淀 1 条升级记录" 0
else
  report "首次调用沉淀 1 条升级记录" 1
fi

if echo "$out6" | grep -q "SECOND_SEEDED= 0" && echo "$out6" | grep -q "SECOND_SKIPPED= 1"; then
  report "复用同一 SharedMemory 二次调用幂等（seeded=0, skipped=1）" 0
else
  report "复用同一 SharedMemory 二次调用幂等（seeded=0, skipped=1）" 1
fi

if echo "$out6" | grep -q "VERDICT= 通过"; then
  report "共享内存复用场景审计结论通过" 0
else
  report "共享内存复用场景审计结论通过" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 框架升级记录沉淀与复盘审计通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 框架升级记录沉淀与复盘审计存在阻塞项"
  exit 1
fi

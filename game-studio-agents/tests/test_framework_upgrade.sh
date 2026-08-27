#!/usr/bin/env bash
# ============================================================
# 框架自升级闭环 · 共享记忆接线测试信号灯（wp_server）
# 说明: 验证 wp_server（程序线·cto）落地产出——
#       1. loc://memory.framework_upgrade.* 已与 SharedMemory 对接接线；
#       2. UPG 编号递增规则正确（UPG-001 → UPG-002 → ...）；
#       3. 四环节闭环留痕完整（触发→评估→决策→落地）；
#       4. 只增不改只追加（追加后旧记录保留、不可删改）。
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

echo "== 1. SharedMemory 接线（framework_upgrade 空间注册）=="
out1=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.abspath("../../game-architect-team/src"))
from shared_memory import SharedMemory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_memory import (
    FrameworkUpgradeMemory, FRAMEWORK_UPGRADE_SPACE, ALLOWED_WRITERS,
    next_upg_id,
)

# 1. 可创建并接线
fmu = FrameworkUpgradeMemory()
space_ok = fmu.memory is not None

# 2. ACL 已设置（cto / server_dev / producer / data_analyst 可写）
acl_ok = all(
    fmu.memory.can_write(FRAMEWORK_UPGRADE_SPACE, w) for w in ALLOWED_WRITERS
)

# 3. 写入一条记录，验证格式 loc://memory.framework_upgrade.<kind>.<seq>
rec = fmu.record_trigger("新能力调研发现 P0 缺口", {"detail": "共享记忆缺少版本管理"},
                         upg_id="UPG-001")
mem_id_ok = rec.mem_id.startswith(f"loc://memory.{FRAMEWORK_UPGRADE_SPACE}.")

print("SPACE_OK=", space_ok)
print("ACL_OK=", acl_ok)
print("MEM_ID_OK=", mem_id_ok)
print("MEM_ID=", rec.mem_id)
PYEOF
)

if echo "$out1" | grep -q "SPACE_OK= True" && echo "$out1" | grep -q "ACL_OK= True"; then
  report "framework_upgrade 空间已注册，ACL 写入权限已设置" 0
else
  report "framework_upgrade 空间已注册，ACL 写入权限已设置" 1
fi

if echo "$out1" | grep -q "MEM_ID_OK= True"; then
  report "记录格式符合 loc://memory.framework_upgrade.<kind>.<seq>" 0
else
  report "记录格式符合 loc://memory.framework_upgrade.<kind>.<seq>" 1
fi

echo "== 2. UPG 编号递增规则 =="
out2=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.abspath("../../game-architect-team/src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_memory import FrameworkUpgradeMemory, next_upg_id

fmu = FrameworkUpgradeMemory()

# 初始编号应为 UPG-001
upg_1 = next_upg_id(fmu.memory)

# 记录一条升级，应使用 UPG-001
rec1 = fmu.record_upgrade(
    trigger="测试触发", impact={}, feasibility={}, risk={},
    priority="P0", decision="批准", reason="测试",
    tasks=["t1"], pr_links=["#49"], version="v0.6.4"
)
id1 = rec1.content["upgrade_id"]

# 下一条应递增为 UPG-002
upg_2 = next_upg_id(fmu.memory)

# 再记录一条，应使用 UPG-002
rec2 = fmu.record_upgrade(
    trigger="用户新诉求", impact={}, feasibility={}, risk={},
    priority="P1", decision="搁置", reason="待评估",
    tasks=[], pr_links=[], version="v0.7"
)
id2 = rec2.content["upgrade_id"]

# 跨实例：模拟序列化恢复后编号仍递增
from shared_memory import SharedMemory
data = fmu.memory.to_json()
sm2 = SharedMemory.from_json(data)
fmu2 = FrameworkUpgradeMemory(memory=sm2)
upg_3 = next_upg_id(fmu2.memory)

print("UPG_1=", upg_1)
print("ID1=", id1)
print("UPG_2=", upg_2)
print("ID2=", id2)
print("UPG_3=", upg_3)
PYEOF
)

if echo "$out2" | grep -q "UPG_1= UPG-001" && echo "$out2" | grep -q "ID1= UPG-001"; then
  report "初始编号 UPG-001，首条记录使用 UPG-001" 0
else
  report "初始编号 UPG-001，首条记录使用 UPG-001" 1
fi

if echo "$out2" | grep -q "UPG_2= UPG-002" && echo "$out2" | grep -q "ID2= UPG-002"; then
  report "编号递增为 UPG-002，第二条记录使用 UPG-002" 0
else
  report "编号递增为 UPG-002，第二条记录使用 UPG-002" 1
fi

if echo "$out2" | grep -q "UPG_3= UPG-003"; then
  report "跨实例编号不重复，序列化后仍从 UPG-003 递增" 0
else
  report "跨实例编号不重复，序列化后仍从 UPG-003 递增" 1
fi

echo "== 3. 四环节闭环留痕完整（触发→评估→决策→落地）=="
out3=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.abspath("../../game-architect-team/src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_memory import FrameworkUpgradeMemory

fmu = FrameworkUpgradeMemory()
fmu.record_upgrade(
    trigger="框架自升级闭环缺失（P0 缺口）",
    impact={"scope": "框架治理", "modules": ["docs/FRAMEWORK_UPGRADE.md"]},
    feasibility={"tech": "兼容", "migration": "低"},
    risk={"level": "低", "mitigation": "回退旧版"},
    priority="P0",
    decision="批准",
    reason="框架演进需要统一沉淀",
    tasks=["定义触发条件", "定义评估流程", "定义决策机制", "定义留痕方式"],
    pr_links=["#49"],
    version="v0.6.4"
)

# 检查各环节记录是否存在
types = set()
for r in fmu.get_all_records():
    if r.content.get("upgrade_id") == "UPG-001":
        types.add(r.content.get("type", ""))

has_trigger = "trigger" in types
has_evaluation = "evaluation" in types
has_decision = "decision" in types
has_implementation = "implementation" in types
has_complete = "upgrade" in types

print("HAS_TRIGGER=", has_trigger)
print("HAS_EVAL=", has_evaluation)
print("HAS_DECISION=", has_decision)
print("HAS_IMPL=", has_implementation)
print("HAS_COMPLETE=", has_complete)

# 验证决策字段
for r in fmu.get_all_records():
    if r.content.get("type") == "upgrade" and r.content.get("upgrade_id") == "UPG-001":
        print("DECISION_VALUE=", r.content.get("decision", ""))
        print("PRIORITY=", r.content.get("priority", ""))
        print("VERSION=", r.content.get("implemented", {}).get("version", ""))
PYEOF
)

if echo "$out3" | grep -q "HAS_TRIGGER= True" \
   && echo "$out3" | grep -q "HAS_EVAL= True" \
   && echo "$out3" | grep -q "HAS_DECISION= True" \
   && echo "$out3" | grep -q "HAS_IMPL= True"; then
  report "四环节记录完整（触发/评估/决策/落地）" 0
else
  report "四环节记录完整（触发/评估/决策/落地）" 1
fi

if echo "$out3" | grep -q "HAS_COMPLETE= True" \
   && echo "$out3" | grep -q "DECISION_VALUE= 批准" \
   && echo "$out3" | grep -q "PRIORITY= P0"; then
  report "完整升级记录含决策与优先级" 0
else
  report "完整升级记录含决策与优先级" 1
fi

if echo "$out3" | grep -q "VERSION= v0.6.4"; then
  report "升级记录含版本号 v0.6.4" 0
else
  report "升级记录含版本号 v0.6.4" 1
fi

echo "== 4. 只增不改只追加（不可变性）=="
out4=$($PY - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.abspath("../../game-architect-team/src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from framework_upgrade_memory import FrameworkUpgradeMemory

fmu = FrameworkUpgradeMemory()
# 先写入一条升级记录
rec1 = fmu.record_upgrade(
    trigger="触发A", impact={}, feasibility={}, risk={},
    priority="P1", decision="搁置", reason="待定",
    tasks=[], pr_links=[], version="v0.7"
)
old_total = len(fmu.get_all_records())
old_content = dict(rec1.content)  # 深拷贝当前内容

# 再追加一条
fmu.record_trigger("追加触发", {}, upg_id="UPG-999")
new_total = len(fmu.get_all_records())

# 旧记录仍在
old_still_there = any(
    r.mem_id == rec1.mem_id for r in fmu.get_all_records()
)

# 旧记录内容未被修改
content_unchanged = any(
    r.mem_id == rec1.mem_id and r.content == old_content
    for r in fmu.get_all_records()
)

print("APPENDED=", new_total > old_total)
print("OLD_KEPT=", old_still_there)
print("CONTENT_SAME=", content_unchanged)
print("OLD_TOTAL=", old_total)
print("NEW_TOTAL=", new_total)
PYEOF
)

if echo "$out4" | grep -q "APPENDED= True"; then
  report "追加记录后总数增加（只增）" 0
else
  report "追加记录后总数增加（只增）" 1
fi

if echo "$out4" | grep -q "OLD_KEPT= True" && echo "$out4" | grep -q "CONTENT_SAME= True"; then
  report "旧记录保留且内容不变（不改不减）" 0
else
  report "旧记录保留且内容不变（不改不减）" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 框架自升级闭环 · 共享记忆接线通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 框架自升级闭环 · 共享记忆接线存在阻塞项"
  exit 1
fi

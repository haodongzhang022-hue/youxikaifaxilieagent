#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：发版质量门禁 (ReleaseGate)
# 功能定义: 对全链路产出做发版质量门禁与验收放行，聚合上游
#           各工作包产出，逐项核对，满足则 GO 放行。
# 验收标准: 门禁逐项核对正确，GO/NO-GO 判定正确。
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

echo "== 功能模块验收：发版质量门禁 (ReleaseGate) =="

out=$($PY - <<'PYEOF'
from release_gate import RELEASE_GATE, run_release_gate, aggregate_and_release

# 1. 门禁标准定义
print(f"GATE_ITEMS={list(RELEASE_GATE.keys())}")
print(f"GATE_COUNT={len(RELEASE_GATE)}")

# 2. 聚合验收
gate = aggregate_and_release()
print(f"GATE_GO_NO_GO={gate.get('go_no_go')}")
print(f"GATE_VERDICT={gate.get('verdict')}")

# 3. 门禁结果逐项
for key, g in gate.get("gate_results", {}).items():
    print(f"GATE_RESULT:{key}={g.get('ok')}")

# 4. 手动构造全部达标输入 → GO
ok_inputs = {
    "market_preview": {"equilibrium": {"a": 1}, "metrics": {"dau": 100}, "diagnosis": "健康"},
    "ecosystem_roles": {"registered": 21, "dispatchable": 21, "publish_to_bus": True},
    "progress_pusher": {"watch": 5, "push": 2, "escalate": 1, "warn": 1},
    "stage_gate": {"no_stage_crossing": True, "reusable_assets_validated": True, "stage_alignment": True},
    # Issue #128 引入的管线级发布评审门禁，需喂全达标输入才会 GO
    "pipeline_quality": {"ok": True, "passed": 3, "total": 3,
                         "passed_checks": ["pipeline_reviewed", "pipeline_go", "stage_gate_per_pipeline"]},
}
result = run_release_gate(ok_inputs)
print(f"MANUAL_GO={result.get('go_no_go')}")

# 5. 手动构造缺项输入 → NO-GO
bad_inputs = {
    "market_preview": {"equilibrium": None, "metrics": {}, "diagnosis": ""},
    "ecosystem_roles": {"registered": 0, "dispatchable": 0, "publish_to_bus": False},
    "progress_pusher": {},
}
result2 = run_release_gate(bad_inputs)
print(f"MANUAL_NO_GO={result2.get('go_no_go')}")

# 6. 验证门禁结果中每项的通过率
for key, g in result.get("gate_results", {}).items():
    print(f"MANUAL_RESULT:{key}={g.get('ok')}")

# 7. 验证拒绝时输出未达标项
missing = result2.get("missing_items", [])
print(f"MISSING_ITEMS={missing}")
PYEOF
)

# 1. 门禁项目定义（含 Issue#128 新增的 pipeline_quality，共 5 项）
if echo "$out" | grep -q "GATE_ITEMS=.*market_preview.*ecosystem_roles.*progress_pusher.*stage_gate.*pipeline_quality" && echo "$out" | grep -q "GATE_COUNT=5"; then
  report "发版门禁五项标准定义完整（含 stage_gate + pipeline_quality）" 0
else
  report "发版门禁五项标准定义完整（含 stage_gate + pipeline_quality）" 1
fi

# 2. 聚合验收 GO
if echo "$out" | grep -q "GATE_GO_NO_GO=GO"; then
  report "全链路产出达标→GO 放行" 0
else
  report "全链路产出达标→GO 放行" 1
fi

# 3. 验收结论明确
if echo "$out" | grep -q "GATE_VERDICT="; then
  report "验收结论输出明确" 0
else
  report "验收结论输出明确" 1
fi

# 4. 门禁结果逐项记录
if echo "$out" | grep -q "GATE_RESULT:market_preview=True" && echo "$out" | grep -q "GATE_RESULT:ecosystem_roles=True"; then
  report "门禁结果逐项核对记录" 0
else
  report "门禁结果逐项核对记录" 1
fi

# 5. 全部达标→GO
if echo "$out" | grep -q "MANUAL_GO=GO"; then
  report "全部达标输入→GO 放行" 0
else
  report "全部达标输入→GO 放行" 1
fi

# 6. 缺项→NO-GO
if echo "$out" | grep -q "MANUAL_NO_GO=NO-GO"; then
  report "缺项输入→NO-GO 阻塞" 0
else
  report "缺项输入→NO-GO 阻塞" 1
fi

# 7. 全部达标时门禁结果全 True（含第 5 项 pipeline_quality）
if echo "$out" | grep -q "MANUAL_RESULT:market_preview=True" && echo "$out" | grep -q "MANUAL_RESULT:progress_pusher=True" && echo "$out" | grep -q "MANUAL_RESULT:pipeline_quality=True"; then
  report "达标输入门禁逐项全部通过（含 pipeline_quality）" 0
else
  report "达标输入门禁逐项全部通过（含 pipeline_quality）" 1
fi

echo ""
echo "【发版门禁模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 发版质量门禁功能模块验收通过"
exit 0

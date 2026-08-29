#!/usr/bin/env bash
# ============================================================
# 引擎阶段化 stage_gate 门禁接入生产调度链测试信号灯
# 说明: 验证 PR #113 下游工作包 —— 程序线把「引擎阶段化阶段边界门禁
#       （总师助理 stage_gate）」接入生产调度链（department_agents.py）：
#       1. ProgramDeptAgent._execute 嵌入 stage_gate 阶段边界审计（引擎×阶段二维）
#       2. 产出 artifact 含 stage_gate 留痕（stage/violations/results）
#       3. _verify 阶段越界（过度设计/技术债）→ 验收打回
#       4. 合规模块（协议先行/纯逻辑库）→ 通过
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

echo "== 1. stage_gate 阶段边界门禁（StageBoundaryGuard）=="
out=$($PY - <<'PYEOF'
from stage_aware_engine import StageBoundaryGuard, GameStage
guard = StageBoundaryGuard()
# Cocos 阶段: combat_frame_sync（属 UE 阶段）→ 过度设计越界
r = guard.check("combat_frame_sync", GameStage.STAGE1_COCOS)
assert r["ok"] is False and r["action"] == "remove_or_defer"
# Cocos 阶段: protobuf_protocol（协议先行，所有阶段）→ 合规
r2 = guard.check("protobuf_protocol", GameStage.STAGE1_COCOS)
assert r2["ok"] is True and r2["action"] == "ok"
print("stage_gate 阶段边界检测正确")
PYEOF
)
if echo "$out" | grep -q "stage_gate 阶段边界检测正确"; then report "StageBoundaryGuard 阶段越界/合规检测正确" 0; else report "StageBoundaryGuard 阶段越界/合规检测正确" 1; fi

echo "== 2. ProgramDeptAgent 嵌入 stage_gate 审计 =="
out=$($PY - <<'PYEOF'
from message_bus import MessageBus
from department_agents import ProgramDeptAgent
from engine_adapters import get_engine

bus = MessageBus()
agent = ProgramDeptAgent(bus)
agent.boot()
# 直接执行一个 client 工作包，验证 stage_gate 审计嵌入 artifact
wp = {"id": "wp_client", "module": "client", "label": "客户端", "project": "game", "department": "program"}
artifact = agent._execute(wp, {"role": "cto"})
assert "stage_gate" in artifact, "artifact 缺少 stage_gate 审计"
sg = artifact["stage_gate"]
assert "stage" in sg and "engine" in sg, "stage_gate 缺 stage/engine 字段"
assert "violations" in sg and "results" in sg, "stage_gate 缺 violations/results 字段"
print(f"stage_gate 审计嵌入: engine={sg['engine']} stage={sg['stage']} ok={sg['ok']} violations={len(sg['violations'])}")
PYEOF
)
if echo "$out" | grep -q "stage_gate 审计嵌入"; then report "ProgramDeptAgent._execute 嵌入 stage_gate 审计留痕" 0; else report "ProgramDeptAgent._execute 嵌入 stage_gate 审计留痕" 1; fi

echo "== 3. stage_gate 越界 → 验收打回 =="
out=$($PY - <<'PYEOF'
from message_bus import MessageBus
from department_agents import ProgramDeptAgent
bus = MessageBus()
agent = ProgramDeptAgent(bus)
agent.boot()
# 构造含越界模块的 stage_gate 产物（combat_frame_sync 在 Cocos 阶段越界）
artifact = {
    "content": {"note": "程序实现"},
    "dev_team": {"ok": True, "reason": ""},
    "stage_gate": {
        "engine": "cocos", "stage": "stage1_cocos", "ok": False,
        "violations": [{"module": "combat_frame_sync", "action": "remove_or_defer"}],
        "results": [{"module": "combat_frame_sync", "ok": False}],
    },
}
ok, msg = agent._verify({}, artifact)
assert ok is False, "阶段越界应被打回"
assert "引擎阶段化门禁拦截" in msg, "打回原因应为阶段越界"
print(f"阶段越界打回: {msg}")
PYEOF
)
if echo "$out" | grep -q "阶段越界打回"; then report "stage_gate 越界验收打回（总师助理纠偏）" 0; else report "stage_gate 越界验收打回（总师助理纠偏）" 1; fi

echo "== 4. stage_gate 合规 → 通过 =="
out=$($PY - <<'PYEOF'
from message_bus import MessageBus
from department_agents import ProgramDeptAgent
bus = MessageBus()
agent = ProgramDeptAgent(bus)
agent.boot()
# 合规 stage_gate（无越界）→ 验收通过
artifact = {
    "content": {"note": "程序实现"},
    "dev_team": {"ok": True, "reason": ""},
    "stage_gate": {"engine": "cocos", "stage": "stage1_cocos", "ok": True,
                   "violations": [], "results": [{"module": "protobuf_protocol", "ok": True}]},
}
ok, msg = agent._verify({}, artifact)
assert ok is True, "合规 stage_gate 应通过验收"
print(f"合规 stage_gate 通过: {msg}")
PYEOF
)
if echo "$out" | grep -q "合规 stage_gate 通过"; then report "stage_gate 合规模块验收通过" 0; else report "stage_gate 合规模块验收通过" 1; fi

echo ""
echo "=== 汇总: $pass 通过 / $fail 失败 ==="
if [ "$fail" = "0" ]; then
  echo "🟢 引擎阶段化 stage_gate 接入生产调度链全部通过"
  exit 0
else
  echo "🔴 存在未通过断言"
  exit 1
fi

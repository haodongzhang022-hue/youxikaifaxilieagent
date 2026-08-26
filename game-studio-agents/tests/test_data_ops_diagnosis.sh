#!/usr/bin/env bash
# ============================================================
# 市场预演生态位诊断与发布建议测试信号灯（wp_data_ops）
# 说明: 验证 wp_data_ops（运营线·data_analyst）落地产出——
#       对市场预演纳什均衡结果做生态位诊断 + 敏感性分析 + 发布建议。
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

echo "== 1. 市场预演生态位诊断与发布建议（wp_data_ops·data_analyst）=="
out=$($PY data_ops_diagnosis.py 2>&1)

# 1. 生态位健康度诊断输出
if echo "$out" | grep -q "生态位:" && echo "$out" | grep -q "健康分"; then
  report "生态位健康度诊断输出" 0
else
  report "生态位健康度诊断输出" 1
fi

# 2. 敏感性分析结论（含 CV 波动度量）
if echo "$out" | grep -q "敏感度:" && echo "$out" | grep -q "CV"; then
  report "敏感性分析结论输出（含变异系数）" 0
else
  report "敏感性分析结论输出（含变异系数）" 1
fi

# 3. 发布建议输出（结论/时机/放行）
if echo "$out" | grep -q "结论:" && echo "$out" | grep -q "时机:" \
   && echo "$out" | grep -q "放行:"; then
  report "发布建议输出（结论/时机/放行）" 0
else
  report "发布建议输出（结论/时机/放行）" 1
fi

# 4. 敏感性分析沿参数轴有实际波动（非恒定）
if echo "$out" | grep -qE "iap=0.3.*营收=[0-9]+" && echo "$out" | grep -qE "iap=0.9.*营收=[0-9]+"; then
  report "敏感性分析沿参数轴有实际波动" 0
else
  report "敏感性分析沿参数轴有实际波动" 1
fi

echo "== 2. OpsDeptAgent 集成（wp_data_ops 产出市场生态位诊断）=="
out2=$($PY - <<'PYEOF'
from department_agents import OpsDeptAgent
from message_bus import MessageBus
agent = OpsDeptAgent(MessageBus())
agent.boot()
wp = {"module":"data_ops","label":"数据运营","project":"P","id":"wp_data_ops","department_name":"运营线"}
a = agent._execute(wp, {})
md = a.get("market_diagnosis")
print("HAS_DIAG=", md is not None)
print("POSITION=", (md or {}).get("ecosystem_diagnosis",{}).get("position",""))
print("GO_NO_GO=", (md or {}).get("release_recommendation",{}).get("go_no_go",""))
print("VERIFY=", agent._verify(wp, a)[0])
PYEOF
)

if echo "$out2" | grep -q "HAS_DIAG= True"; then
  report "OpsDeptAgent 产出市场生态位诊断" 0
else
  report "OpsDeptAgent 产出市场生态位诊断" 1
fi
if echo "$out2" | grep -qE "GO_NO_GO= (GO|NO-GO)"; then
  report "发布放行结论输出" 0
else
  report "发布放行结论输出" 1
fi
if echo "$out2" | grep -q "VERIFY= True"; then
  report "wp_data_ops 产出自检通过" 0
else
  report "wp_data_ops 产出自检通过" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 市场预演生态位诊断与发布建议通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 市场预演生态位诊断与发布建议存在阻塞项"
  exit 1
fi

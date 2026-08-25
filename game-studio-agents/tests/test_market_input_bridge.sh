#!/usr/bin/env bash
# ============================================================
# 数值模型 → 市场预演标准化输入桥梁测试信号灯（wp_numeric_model）
# 说明: 验证 wp_numeric_model（策划线·balance_designer）落地产出——
#       把数值模型/商业化设计输出为 market_simulator 标准化输入，
#       跑通「研发产物 → 市场预演沙盒」，收敛到纳什均衡并输出生态位诊断。
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

echo "== 1. 数值模型 → 市场预演标准化输入桥梁（wp_numeric_model）=="
out=$($PY market_input_bridge.py 2>&1)

# 1. 数值模型字段正确映射为市场模拟 context
if echo "$out" | grep -q "arpu_base" && echo "$out" | grep -q "competition_pressure"; then
  report "数值模型字段映射为市场 context（arpu/竞品等）" 0
else
  report "数值模型字段映射为市场 context（arpu/竞品等）" 1
fi

# 2. 参与博弈的生态角色与策略空间已构建
if echo "$out" | grep -q "mass_player" && echo "$out" | grep -q "advertiser" \
   && echo "$out" | grep -q "publisher"; then
  report "构建博弈角色与策略空间（玩家/广告/宣发）" 0
else
  report "构建博弈角色与策略空间（玩家/广告/宣发）" 1
fi

# 3. 纳什均衡收敛并输出均衡策略
if echo "$out" | grep -q "均衡策略" && echo "$out" | grep -q "payer.*内购"; then
  report "纳什均衡收敛并输出均衡策略" 0
else
  report "纳什均衡收敛并输出均衡策略" 1
fi

# 4. 均衡结果指标输出
if echo "$out" | grep -q "dau" && echo "$out" | grep -q "roi" \
   && echo "$out" | grep -q "d30_retention"; then
  report "均衡结果指标输出（DAU/留存/ROI）" 0
else
  report "均衡结果指标输出（DAU/留存/ROI）" 1
fi

# 5. 生态位诊断输出
if echo "$out" | grep -q "生态位诊断"; then
  report "生态位诊断输出" 0
else
  report "生态位诊断输出" 1
fi

echo "== 2. DesignDeptAgent 集成（wp_numeric_model 产出市场预演沙盒）=="
out2=$($PY - <<'PYEOF'
from department_agents import DesignDeptAgent
from message_bus import MessageBus
agent = DesignDeptAgent(MessageBus())
agent.boot()
wp = {"module":"numeric_model","label":"数值模型","project":"P","id":"wp_numeric_model","department_name":"策划线"}
a = agent._execute(wp, {})
print("HAS_INPUT=", "market_input" in a)
print("HAS_SIM=", "market_simulation" in a)
print("EQ=", sorted(a.get("market_simulation",{}).get("equilibrium",{}).keys()))
print("VERIFY=", agent._verify(wp, a)[0])
PYEOF
)

if echo "$out2" | grep -q "HAS_INPUT= True" && echo "$out2" | grep -q "HAS_SIM= True"; then
  report "DesignDeptAgent 产出标准化输入+模拟结果" 0
else
  report "DesignDeptAgent 产出标准化输入+模拟结果" 1
fi
if echo "$out2" | grep -q "VERIFY= True"; then
  report "wp_numeric_model 产出自检通过" 0
else
  report "wp_numeric_model 产出自检通过" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 数值模型 → 市场预演联动通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 数值模型 → 市场预演联动存在阻塞项"
  exit 1
fi

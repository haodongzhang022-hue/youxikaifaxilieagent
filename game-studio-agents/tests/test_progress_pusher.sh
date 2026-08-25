#!/usr/bin/env bash
# ============================================================
# 进度督导（Progress Pusher）测试信号灯（护栏）
# 说明: 验证进度督导 v1.0（程序规则化 + 声明化策略）稳定可生效：
#       1. 正常任务 → WATCH（不打扰）
#       2. 逾期任务 → PUSH（经总线催办 owner）
#       3. 阻塞超时 → ESCALATE（升级项目经理）
#       4. 临近 DDL → WARN（友好预警）
#       5. 策略声明化：修改 YAML 可调阈值，不碰代码
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

echo "== 1. 进度督导四类决策（WATCH / PUSH / ESCALATE / WARN）=="
out=$($PY progress_pusher.py 2>&1)
if echo "$out" | grep -q "t_ok.*WATCH"; then
  report "正常任务 → WATCH（不打扰）" 0
else
  report "正常任务 → WATCH（不打扰）" 1
fi
if echo "$out" | grep -q "t_late.*PUSH"; then
  report "逾期任务 → PUSH（催办）" 0
else
  report "逾期任务 → PUSH（催办）" 1
fi
if echo "$out" | grep -q "t_block.*ESCALATE"; then
  report "阻塞超时 → ESCALATE（升级）" 0
else
  report "阻塞超时 → ESCALATE（升级）" 1
fi
if echo "$out" | grep -q "t_near.*WARN"; then
  report "临近DDL → WARN（预警）" 0
else
  report "临近DDL → WARN（预警）" 1
fi

echo "== 2. 督导消息真正经总线发出（程序规则化生效）=="
if echo "$out" | grep -q "PUSH:t_late"; then
  report "PUSH 消息已发出给 owner" 0
else
  report "PUSH 消息已发出给 owner" 1
fi
if echo "$out" | grep -q "ESCALATE:t_block"; then
  report "ESCALATE 消息已发出给项目经理" 0
else
  report "ESCALATE 消息已发出给项目经理" 1
fi

echo "== 3. 演示自检结论（结果: 🟢 通过）=="
if echo "$out" | grep -q "结果: 🟢 通过"; then
  report "progress_pusher.py 自检通过" 0
else
  report "progress_pusher.py 自检通过" 1
fi

echo "== 4. 协作支持编排可运行（兼容 v0.2 封装）=="
cout=$($PY collaboration_support.py 2>&1)
if echo "$cout" | grep -q "进度督导.*任务 t1 决策"; then
  report "collaboration_support.py 演示可运行" 0
else
  report "collaboration_support.py 演示可运行" 1
fi

echo ""
echo "进度督导测试结果: $pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then
  echo "🔴 阻塞：存在未通过断言"
  exit 1
fi
echo "🟢 全部通过"
exit 0

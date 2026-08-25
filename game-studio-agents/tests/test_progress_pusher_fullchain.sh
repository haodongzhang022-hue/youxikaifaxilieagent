#!/usr/bin/env bash
# ============================================================
# 进度督导四类决策全链路验证测试信号灯（wp_testing）
# 说明: 验证 wp_testing（测试线·qa_engineer）落地产出——
#       进度督导「WATCH / PUSH / ESCALATE / WARN」四类决策在
#       真实部门工作包上全链路生效（催办/升级经 message_bus 真实送达）。
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

echo "== 1. 进度督导四类决策全链路验证（wp_testing·qa_engineer）=="
out=$($PY progress_pusher_fullchain.py 2>&1)

# 1. 真实部门工作包队列生成（含 wp_* 真实任务）
if echo "$out" | grep -q "真实部门工作包队列"; then
  report "生成真实部门工作包队列（wp_* 任务）" 0
else
  report "生成真实部门工作包队列（wp_* 任务）" 1
fi

# 2. 四类决策在真实工作包上全部匹配
for pair in "wp_numeric_model_fullchain 期望=PUSH.*实际=PUSH" \
            "wp_client_fullchain      期望=WARN.*实际=WARN" \
            "wp_testing_fullchain     期望=ESCALATE.*实际=ESCALATE" \
            "wp_release_fullchain     期望=WATCH.*实际=WATCH"; do
  if echo "$out" | grep -q "$pair"; then
    report "真实工作包决策匹配：$pair" 0
  else
    report "真实工作包决策匹配：$pair" 1
  fi
done

# 3. 催办消息送达责任 owner
if echo "$out" | grep -q "PUSH 消息送达责任 owner: 🟢"; then
  report "PUSH 催办消息送达责任 owner" 0
else
  report "PUSH 催办消息送达责任 owner" 1
fi

# 4. 升级消息送达项目经理
if echo "$out" | grep -q "ESCALATE 消息送达项目经理: 🟢"; then
  report "ESCALATE 升级消息送达项目经理" 0
else
  report "ESCALATE 升级消息送达项目经理" 1
fi

# 5. 全链路验证通过
if echo "$out" | grep -q "结果: 🟢 通过"; then
  report "进度督导四类决策全链路验证通过" 0
else
  report "进度督导四类决策全链路验证通过" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 进度督导全链路验证通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 进度督导全链路验证存在阻塞项"
  exit 1
fi

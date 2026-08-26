#!/usr/bin/env bash
# ============================================================
# 生态角色注册与派发测试信号灯（wp_server / wp_ai_logic）
# 说明: 验证 wp_server / wp_ai_logic（程序线·cto / ai_programmer）落地产出——
#       把生态角色（玩家圈 / 外部市场圈 / 协作支持圈）注册进 task_scheduler +
#       message_bus，作为可派发 Agent 真正进入部门流水线派发。
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

echo "== 1. 生态角色注册与派发桥梁（wp_server / wp_ai_logic）=="
out=$($PY ecosystem_role_registry.py 2>&1)

# 1. 三大生态圈角色注册（协作支持/玩家/外部市场）
if echo "$out" | grep -q "协作支持圈.*progress_pusher" \
   && echo "$out" | grep -q "玩家圈.*core_player" \
   && echo "$out" | grep -q "外部市场圈.*publisher"; then
  report "三大生态圈角色注册（协作支持/玩家/外部市场）" 0
else
  report "三大生态圈角色注册（协作支持/玩家/外部市场）" 1
fi

# 1b. 美术圈生态角色注册（wp_art_direction，评审点2：eco_ 前缀隔离命名）
if echo "$out" | grep -q "美术圈.*eco_art_director" \
   && echo "$out" | grep -q "美术圈.*eco_tech_artist" \
   && echo "$out" | grep -q "美术圈.*eco_audio_designer"; then
  report "美术圈生态角色注册（eco_art_director/eco_tech_artist/eco_audio_designer）" 0
else
  report "美术圈生态角色注册（eco_art_director/eco_tech_artist/eco_audio_designer）" 1
fi

# 2. 生态角色接入 task_scheduler（可派发 owner）
if echo "$out" | grep -q "owner=publisher" && echo "$out" | grep -q "owner=progress_pusher" \
   && echo "$out" | grep -q "owner=eco_art_director"; then
  report "生态角色接入 task_scheduler 派发" 0
else
  report "生态角色接入 task_scheduler 派发" 1
fi

# 3. 派发消息 publish 到 message_bus
if echo "$out" | grep -q "TASK_ASSIGN: 4 条"; then
  report "TASK_ASSIGN 派发消息 publish 到 message_bus" 0
else
  report "TASK_ASSIGN 派发消息 publish 到 message_bus" 1
fi

# 4. 注册汇总（total>=21）
if echo "$out" | grep -q "total: 21"; then
  report "生态角色注册汇总（21 个，含美术圈 3 个）" 0
else
  report "生态角色注册汇总（21 个，含美术圈 3 个）" 1
fi

echo "== 2. 实例化团队端到端中的生态角色装配派发 =="
out2=$($PY run_end_to_end_instantiated.py 2>&1)

# 5. 实例化团队流程中生态角色注册为可派发 Agent
if echo "$out2" | grep -q "已注册生态角色: 21 个"; then
  report "端到端流程注册 21 个生态角色为可派发 Agent" 0
else
  report "端到端流程注册 21 个生态角色为可派发 Agent" 1
fi

# 6. 生态角色任务已派发
if echo "$out2" | grep -q "已派发生态角色任务: 5 个"; then
  report "生态角色任务已派发（5 个代表角色）" 0
else
  report "生态角色任务已派发（5 个代表角色）" 1
fi

# 7. 派发消息 publish 到 message_bus
if echo "$out2" | grep -q "派发消息已 publish 到 message_bus"; then
  report "生态角色派发消息已 publish 到 message_bus" 0
else
  report "生态角色派发消息已 publish 到 message_bus" 1
fi

# 8. 全链路仍 DONE（生态角色接入不影响部门流水线完成）
if echo "$out2" | grep -q "all_done = True"; then
  report "生态角色接入后部门全链路仍 DONE" 0
else
  report "生态角色接入后部门全链路仍 DONE" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 生态角色注册与派发通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 生态角色注册与派发存在阻塞项"
  exit 1
fi

#!/usr/bin/env bash
# ============================================================
# 美术品质维度接入市场预演测试信号灯（wp_art_direction）
# 说明: 验证 wp_art_direction（美术线·art_director）落地产出——
#       1. market_simulator 增加 art_quality 维度到品质/留存/口碑计算；
#       2. market_input_bridge 增加美术品质字段映射，美术品质进入市场预演；
#       3. ecosystem_roles.yaml 登记美术生态角色（art_director/tech_artist/
#          audio_designer），复用 ecosystem_role_registry 注册为可派发 Agent；
#       4. ArtDeptAgent 承接 art_direction 工作包时把美术品质接入市场预演沙盒，
#          玩家圈对美术品质的偏好生效。
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

echo "== 1. 市场模拟器美术品质维度（wp_art_direction）=="
out=$($PY market_simulator.py 2>&1)

# 1. art_quality 进入市场模拟 context
if echo "$out" | grep -q "art_quality" && echo "$out" | grep -q "art_satisfaction"; then
  report "market_simulator 输出 art_quality + art_satisfaction 指标" 0
else
  report "market_simulator 输出 art_quality + art_satisfaction 指标" 1
fi

# 2. 核心玩家对美术品质偏好进入博弈（core_player 角色）
if echo "$out" | grep -q "core_player"; then
  report "核心玩家(core_player)对美术品质偏好的博弈角色参与纳什均衡" 0
else
  report "核心玩家(core_player)对美术品质偏好的博弈角色参与纳什均衡" 1
fi

# 3. 美术品质进入生态位诊断
if echo "$out" | grep -q "美术品质" && echo "$out" | grep -q "美术满意度"; then
  report "美术品质进入生态位诊断（美术品质/美术满意度）" 0
else
  report "美术品质进入生态位诊断（美术品质/美术满意度）" 1
fi

echo "== 2. 数值模型→市场预演桥梁美术品质字段映射 =="
out2=$($PY market_input_bridge.py 2>&1)

# 4. art_quality 字段映射进市场 context
if echo "$out2" | grep -q "art_quality"; then
  report "market_input_bridge 映射 art_quality 字段进市场 context" 0
else
  report "market_input_bridge 映射 art_quality 字段进市场 context" 1
fi

# 5. 核心玩家角色加入博弈角色空间
if echo "$out2" | grep -q "core_player" && echo "$out2" | grep -q "美术宽松"; then
  report "桥梁构建含美术偏好的博弈角色（core_player 美术宽松/挑剔）" 0
else
  report "桥梁构建含美术偏好的博弈角色（core_player 美术宽松/挑剔）" 1
fi

# 6. 美术满意度进入生态位诊断
if echo "$out2" | grep -q "美术满意度"; then
  report "桥梁生态位诊断含美术满意度" 0
else
  report "桥梁生态位诊断含美术满意度" 1
fi

echo "== 3. 美术生态角色注册为可派发 Agent =="
out3=$($PY ecosystem_role_registry.py 2>&1)

# 7. 美术圈三个生态角色注册到 message_bus
if echo "$out3" | grep -q "美术圈.*art_director" \
   && echo "$out3" | grep -q "美术圈.*tech_artist" \
   && echo "$out3" | grep -q "美术圈.*audio_designer"; then
  report "美术圈生态角色注册（art_director/tech_artist/audio_designer）" 0
else
  report "美术圈生态角色注册（art_director/tech_artist/audio_designer）" 1
fi

# 8. 美术生态角色接入 task_scheduler 派发（art_director 可派发）
if echo "$out3" | grep -q "owner=art_director"; then
  report "美术生态角色(art_director)接入 task_scheduler 派发" 0
else
  report "美术生态角色(art_director)接入 task_scheduler 派发" 1
fi

echo "== 4. ArtDeptAgent 承接 art_direction 接入市场预演 =="
out4=$($PY - <<'PYEOF'
from department_agents import ArtDeptAgent
from message_bus import MessageBus
agent = ArtDeptAgent(MessageBus())
agent.boot()
wp = {"module":"art_direction","label":"美术风格","project":"P",
      "id":"wp_art_direction","department_name":"美术线"}
a = agent._execute(wp, {})
print("ART_QUALITY=", a.get("content",{}).get("art_quality"))
print("HAS_MARKET_INPUT=", "market_input" in a)
print("HAS_SIM=", "market_simulation" in a)
ms = a.get("market_simulation",{}).get("metrics",{})
print("ART_SATISFACTION=", "art_satisfaction" in ms)
print("VERIFY=", agent._verify(wp, a)[0])
PYEOF
)

# 9. art_direction 产出含美术品质基准 + 市场预演
if echo "$out4" | grep -q "ART_QUALITY= 72.0" \
   && echo "$out4" | grep -q "HAS_MARKET_INPUT= True" \
   && echo "$out4" | grep -q "HAS_SIM= True"; then
  report "ArtDeptAgent 产出美术品质基准并接入市场预演沙盒" 0
else
  report "ArtDeptAgent 产出美术品质基准并接入市场预演沙盒" 1
fi

# 10. 美术满意度进入市场预演输出（玩家圈偏好生效）
if echo "$out4" | grep -q "ART_SATISFACTION= True"; then
  report "美术满意度进入市场预演输出（玩家圈对美术品质偏好生效）" 0
else
  report "美术满意度进入市场预演输出（玩家圈对美术品质偏好生效）" 1
fi

# 11. art_direction 产出自检通过
if echo "$out4" | grep -q "VERIFY= True"; then
  report "wp_art_direction 产出自检通过" 0
else
  report "wp_art_direction 产出自检通过" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 美术品质维度接入市场预演通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 美术品质维度接入市场预演存在阻塞项"
  exit 1
fi

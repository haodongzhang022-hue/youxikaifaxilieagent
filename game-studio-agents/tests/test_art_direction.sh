#!/usr/bin/env bash
# ============================================================
# 美术品质维度接入市场预演测试信号灯（wp_art_direction）
# 说明: 验证 wp_art_direction（美术线·art_director）落地产出——
#       1. market_simulator 增加 art_quality 维度到品质/留存/口碑计算；
#       2. market_input_bridge 增加美术品质字段映射，美术品质进入市场预演；
#       3. ecosystem_roles.yaml 登记美术生态角色（eco_art_director/eco_tech_artist/
#          eco_audio_designer，eco_ 前缀隔离命名），复用 ecosystem_role_registry
#          注册为可派发 Agent；
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

# 7. 美术圈三个生态角色注册到 message_bus（评审点2：eco_ 前缀隔离命名）
if echo "$out3" | grep -q "美术圈.*eco_art_director" \
   && echo "$out3" | grep -q "美术圈.*eco_tech_artist" \
   && echo "$out3" | grep -q "美术圈.*eco_audio_designer"; then
  report "美术圈生态角色注册（eco_art_director/eco_tech_artist/eco_audio_designer）" 0
else
  report "美术圈生态角色注册（eco_art_director/eco_tech_artist/eco_audio_designer）" 1
fi

# 8. 美术生态角色接入 task_scheduler 派发（eco_art_director 可派发）
if echo "$out3" | grep -q "owner=eco_art_director"; then
  report "美术生态角色(eco_art_director)接入 task_scheduler 派发" 0
else
  report "美术生态角色(eco_art_director)接入 task_scheduler 派发" 1
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

echo "== 5. 评审修复验证（核心玩家美术偏好博弈 + 满意度区间）=="

# 12. core_player 美术偏好博弈失效修复（评审点1）：
#     art_preference 被 MarketSimulator.run 读取，三策略收益差异化，纳什均衡不退化
out5=$($PY - <<'PYEOF'
from market_simulator import MarketSimulator, Role, Strategy, Outcome
ctx = {"base_quality":65.0,"art_quality":72.0,"mass_player_base":200000,
       "arpu_base":2.5,"ecpm_base":6.0,"ad_impressions":8,"channel_cut":0.3,
       "competition_pressure":0.4,"marketing_budget":80000,"last_outcome":Outcome()}
roles = [
  Role("mass_player","泛玩家","players",payoff_fn=lambda c,m,o:0,
       strategy_space=[Strategy("低门槛",{"complexity":0.2,"art_sens":0.15})]),
  Role("core_player","核心玩家","players",payoff_fn=lambda c,m,o:0,
       strategy_space=[Strategy("美术宽松",{"art_preference":0.3}),
                       Strategy("基准偏好",{"art_preference":0.5}),
                       Strategy("美术挑剔",{"art_preference":0.8})]),
  Role("payer","付费玩家","players",payoff_fn=lambda c,m,o:0,
       strategy_space=[Strategy("温和内购",{"iap_depth":0.5})]),
  Role("advertiser","广告方","market",payoff_fn=lambda c,m,o:0,
       strategy_space=[Strategy("低密度广告",{"ad_density":0.2})]),
  Role("publisher","宣发平台","market",payoff_fn=lambda c,m,o:0,
       strategy_space=[Strategy("小预算",{"budget":40000})]),
]
sim = MarketSimulator(ctx, roles)
base = {"mass_player":Strategy("低门槛",{"complexity":0.2,"art_sens":0.15}),
        "payer":Strategy("温和内购",{"iap_depth":0.5}),
        "advertiser":Strategy("低密度广告",{"ad_density":0.2}),
        "publisher":Strategy("小预算",{"budget":40000})}
sats = {}
for pref in [0.3,0.5,0.8]:
    s = dict(base); s["core_player"]=Strategy("x",{"art_preference":pref})
    out=sim.run(s); sats[pref]=out.metrics["art_satisfaction"]
print("SATS=", round(sats[0.3],2), round(sats[0.5],2), round(sats[0.8],2))
print("DIFF=", len(set(sats.values()))>1)
print("IN_RANGE=", all(0<=v<=10 for v in sats.values()))
PYEOF
)

# 12. 三策略收益差异化（art_preference 被读取，纳什均衡不退化）
if echo "$out5" | grep -q "DIFF= True"; then
  report "core_player 美术偏好博弈生效（宽松/基准/挑剔三策略收益差异化）" 0
else
  report "core_player 美术偏好博弈生效（宽松/基准/挑剔三策略收益差异化）" 1
fi

# 13. art_satisfaction 收敛到 0~10 区间（评审点3）
if echo "$out5" | grep -q "IN_RANGE= True"; then
  report "art_satisfaction 收敛到 0~10 区间" 0
else
  report "art_satisfaction 收敛到 0~10 区间" 1
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

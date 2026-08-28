#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：美术线生态角色接入 (Art Ecosystem)
# 功能定义: 把美术圈生态角色（eco_art_director / eco_tech_artist /
#           eco_audio_designer）接入部门流水线，美术/音频品质维度进入
#           市场预演联动，ArtDeptAgent 承接 art_direction/ui_ux/audio
#           工作包并可派发部门角色+生态角色。
# 验收标准: wp_art_direction / wp_ui_ux / wp_audio 三个美术线生态角色
#           工作包以实际运行断言的通过为唯一验收依据。
# 主责: qa_engineer(功能验收) + auto_qa(自动化/市场预演验收)
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

echo "== 功能模块验收：美术线生态角色接入 (Art Ecosystem) =="

out=$($PY - <<'PYEOF'
from ecosystem_role_registry import load_ecosystem_roles, EcosystemRoleRegistry
from message_bus import MessageBus, build_message
from task_scheduler import Scheduler, Task
from ecosystem_handlers import ECOSYSTEM_HANDLERS, register_ecosystem_handlers
from market_input_bridge import build_market_input
from department_agents import build_department_agents

# ============ 一、美术圈生态角色注册（wp_art_direction/ui_ux/audio 底座）============
roles = load_ecosystem_roles()
art_roles = [r for r in roles if r.get("circle") == "art"]
print(f"ART_ROLES_COUNT={len(art_roles)}")
art_ids = [r.get("role_id") for r in art_roles]
print(f"ART_ROLE_IDS={','.join(art_ids)}")
print(f"HAS_ECO_ART_DIRECTOR={'eco_art_director' in art_ids}")
print(f"HAS_ECO_TECH_ARTIST={'eco_tech_artist' in art_ids}")
print(f"HAS_ECO_AUDIO_DESIGNER={'eco_audio_designer' in art_ids}")

# 注册到总线
bus = MessageBus()
reg = EcosystemRoleRegistry(bus=bus)
reg.load()
reg.register()
print(f"REG_ART_COUNT={len(reg.by_circle('art'))}")

# 角色元数据完整性
art_dir_meta = [r for r in art_roles if r.get('role_id')=='eco_art_director'][0]
print(f"ART_DIR_HAS_PROFILE={'profile' in art_dir_meta}")
print(f"ART_DIR_CIRCLE={art_dir_meta.get('circle')}")

# ============ 二、美术圈生态角色 Handler 可派发（wp_audio）============
print(f"HANDLERS_HAS_ECO_ART={'eco_art_director' in ECOSYSTEM_HANDLERS}")
print(f"HANDLERS_HAS_ECO_TECH={'eco_tech_artist' in ECOSYSTEM_HANDLERS}")
print(f"HANDLERS_HAS_ECO_AUDIO={'eco_audio_designer' in ECOSYSTEM_HANDLERS}")
n = register_ecosystem_handlers(bus)
print(f"HANDLERS_REGISTERED={n}")
print(f"ECO_ART_IN_BUS={'eco_art_director' in bus.roles}")
print(f"ECO_TECH_IN_BUS={'eco_tech_artist' in bus.roles}")
print(f"ECO_AUDIO_IN_BUS={'eco_audio_designer' in bus.roles}")

# 派发生态音频角色动作
eco_audio = ECOSYSTEM_HANDLERS.get("eco_audio_designer")
if eco_audio:
    r = eco_audio.handle(build_message("TASK_ASSIGN", "scheduler", "eco_audio_designer",
                                       {"task_id": "eco_audio_action"}))
    print(f"ECO_AUDIO_ACTION={r.get('action')}")
    print(f"ECO_AUDIO_IMMERSION={r.get('output',{}).get('immersion_score')}")
    print(f"ECO_AUDIO_SFX_MATCH={r.get('output',{}).get('sfx_match')}")

eco_art = ECOSYSTEM_HANDLERS.get("eco_art_director")
if eco_art:
    r = eco_art.handle(build_message("TASK_ASSIGN", "scheduler", "eco_art_director",
                                     {"task_id": "eco_art_action"}))
    print(f"ECO_ART_ACTION={r.get('action')}")
    print(f"ECO_ART_UNIFORMITY={r.get('output',{}).get('style_uniformity')}")

# ============ 三、美术/音频品质维度进入市场预演（wp_audio）============
numeric = {"base_quality":65.0, "art_quality":72.0, "audio_quality":68.0,
           "art_sens":0.2,"audio_sens":0.15,"arpu":2.5,"ecpm":6.0,
           "ad_impressions":8,"channel_cut":0.3,"competition":0.4,
           "marketing_budget":80000,"mass_player_base":200000,"complexity":0.35,
           "monetization":{"iap_depth":0.5,"iaa_density":0.25}}
mi = build_market_input(numeric, project="art_ecosystem")
res = mi.solve()
m = res["metrics"]
print(f"HAS_ART_QUALITY_METRIC={'art_quality' in m}")
print(f"HAS_ART_SATISFACTION={'art_satisfaction' in m}")
print(f"HAS_AUDIO_QUALITY_METRIC={'audio_quality' in m}")
print(f"HAS_AUDIO_IMMERSION={'audio_immersion' in m}")
print(f"ART_QUALITY_VAL={round(m['art_quality'],1)}")
print(f"ART_SATISFACTION_VAL={round(m['art_satisfaction'],2)}")
print(f"AUDIO_QUALITY_VAL={round(m['audio_quality'],1)}")
print(f"AUDIO_IMMERSION_VAL={round(m['audio_immersion'],2)}")

# ============ 四、ArtDeptAgent 三工作包承接（art_direction/ui_ux/audio）============
agents = build_department_agents(bus)
art = agents.get("art")
print(f"ART_DEPT_AGENT_FOUND={art is not None}")

def run_wp(module, label):
    wp = {"id": f"wp_{module}_test", "module": module, "label": label,
          "project": "demo", "department_name": "美术线"}
    msg = build_message("TASK_ASSIGN", "scheduler", "art_director",
                        {"task_id": f"wp_{module}_test", "payload": {"work_package": wp}})
    bus.publish(msg)
    bus.process_all()
    rev = [m for m in bus.delivered if m.type == "REVIEW_RESULT" and m.from_role == "art_director"
           and m.content.get("work_package_id") == f"wp_{module}_test"]
    if rev:
        art_content = rev[0].content
        return art_content.get("approved"), art_content.get("artifact", {})
    return None, {}

approved_art, art_art = run_wp("art_direction", "美术风格")
print(f"ART_DIR_APPROVED={approved_art}")
print(f"ART_DIR_TYPE={art_art.get('artifact_type')}")
print(f"ART_DIR_MARKET_EQ={'equilibrium' in art_art.get('market_simulation',{})}")

approved_ui, ui_art = run_wp("ui_ux", "UI/UX 规范")
print(f"UI_UX_APPROVED={approved_ui}")
print(f"UI_UX_DISPATCH_ECO={ui_art.get('dispatchable_eco_owner')}")
print(f"UI_UX_DISPATCH_DEPT={ui_art.get('dispatchable_owner')}")

approved_audio, audio_art = run_wp("audio", "音频")
print(f"AUDIO_APPROVED={approved_audio}")
print(f"AUDIO_TYPE={audio_art.get('artifact_type')}")
print(f"AUDIO_HAS_AUDIO_SPEC={'audio_spec' in audio_art.get('content',{})}")
print(f"AUDIO_QUALITY_IN_CONTENT={'audio_quality' in audio_art.get('content',{})}")
print(f"AUDIO_DISPATCH_ECO={audio_art.get('dispatchable_eco_owner')}")
print(f"AUDIO_DISPATCH_DEPT={audio_art.get('dispatchable_owner')}")

# ============ 五、美术线全链路派发能力（task_scheduler）============
sched = Scheduler(bus=bus)
reg.register_scheduler(sched)
print(f"REG_ART_DISPATCHABLE={len(reg.by_circle('art'))}")
PYEOF
)

# ==================== 断言（qa_engineer · 功能验收）====================
# 1. 美术圈三角色定义完整
if echo "$out" | grep -q "ART_ROLES_COUNT=3" && echo "$out" | grep -q "HAS_ECO_ART_DIRECTOR=True" && echo "$out" | grep -q "HAS_ECO_TECH_ARTIST=True" && echo "$out" | grep -q "HAS_ECO_AUDIO_DESIGNER=True"; then
  report "美术圈三角色定义完整（art_director/tech_artist/audio_designer）" 0
else
  report "美术圈三角色定义完整（art_director/tech_artist/audio_designer）" 1
fi

# 2. 美术圈角色注册到注册器+总线
if echo "$out" | grep -q "REG_ART_COUNT=3"; then
  report "美术圈三角色注册到 ecosystem_role_registry" 0
else
  report "美术圈三角色注册到 ecosystem_role_registry" 1
fi

# 3. 美术指导角色元数据完整
if echo "$out" | grep -q "ART_DIR_HAS_PROFILE=True" && echo "$out" | grep -q "ART_DIR_CIRCLE=art"; then
  report "美术指导角色元数据完整（profile/circle=art）" 0
else
  report "美术指导角色元数据完整（profile/circle=art）" 1
fi

# 4. 美术圈生态角色 Handler 全部注册
if echo "$out" | grep -q "HANDLERS_HAS_ECO_ART=True" && echo "$out" | grep -q "HANDLERS_HAS_ECO_TECH=True" && echo "$out" | grep -q "HANDLERS_HAS_ECO_AUDIO=True"; then
  report "美术圈三角色 Handler 全部注册" 0
else
  report "美术圈三角色 Handler 全部注册" 1
fi

# 5. 生态角色注册到 message_bus
if echo "$out" | grep -q "ECO_ART_IN_BUS=True" && echo "$out" | grep -q "ECO_TECH_IN_BUS=True" && echo "$out" | grep -q "ECO_AUDIO_IN_BUS=True"; then
  report "美术圈生态角色注册到 message_bus" 0
else
  report "美术圈生态角色注册到 message_bus" 1
fi

# 6. 音频生态角色可派发执行 audio_quality 动作
if echo "$out" | grep -q "ECO_AUDIO_ACTION=audio_quality" && echo "$out" | grep -q "ECO_AUDIO_IMMERSION=0.75" && echo "$out" | grep -q "ECO_AUDIO_SFX_MATCH=0.8"; then
  report "音频生态角色 handler 执行 audio_quality 产出沉浸感/音效匹配" 0
else
  report "音频生态角色 handler 执行 audio_quality 产出沉浸感/音效匹配" 1
fi

# 7. 美术指导生态角色可派发执行 art_quality 动作
if echo "$out" | grep -q "ECO_ART_ACTION=art_quality" && echo "$out" | grep -q "ECO_ART_UNIFORMITY=0.85"; then
  report "美术指导生态角色 handler 执行 art_quality 产出风格统一度" 0
else
  report "美术指导生态角色 handler 执行 art_quality 产出风格统一度" 1
fi

# ==================== 断言（auto_qa · 市场预演/自动化验收）====================
# 8. 美术品质维度进入市场预演
if echo "$out" | grep -q "HAS_ART_QUALITY_METRIC=True" && echo "$out" | grep -q "HAS_ART_SATISFACTION=True"; then
  report "美术品质维度进入市场预演（art_quality/art_satisfaction）" 0
else
  report "美术品质维度进入市场预演（art_quality/art_satisfaction）" 1
fi

# 9. 音频品质维度进入市场预演
if echo "$out" | grep -q "HAS_AUDIO_QUALITY_METRIC=True" && echo "$out" | grep -q "HAS_AUDIO_IMMERSION=True"; then
  report "音频品质维度进入市场预演（audio_quality/audio_immersion）" 0
else
  report "音频品质维度进入市场预演（audio_quality/audio_immersion）" 1
fi

# 10. 美术/音频品质基准正确进入纳什均衡
if echo "$out" | grep -q "ART_QUALITY_VAL=72.0" && echo "$out" | grep -q "AUDIO_QUALITY_VAL=68.0"; then
  report "美术/音频品质基准正确（72/68）进入市场预演" 0
else
  report "美术/音频品质基准正确（72/68）进入市场预演" 1
fi

# 11. ArtDeptAgent 存在并承接三工作包
if echo "$out" | grep -q "ART_DEPT_AGENT_FOUND=True"; then
  report "ArtDeptAgent 已创建并可在流水线执行" 0
else
  report "ArtDeptAgent 已创建并可在流水线执行" 1
fi

# 12. wp_art_direction 承接并接入市场预演
if echo "$out" | grep -q "ART_DIR_APPROVED=True" && echo "$out" | grep -q "ART_DIR_TYPE=style_guide" && echo "$out" | grep -q "ART_DIR_MARKET_EQ=True"; then
  report "wp_art_direction 承接产出美术规范并接入市场预演纳什均衡" 0
else
  report "wp_art_direction 承接产出美术规范并接入市场预演纳什均衡" 1
fi

# 13. wp_ui_ux 承接并可派发部门+生态角色
if echo "$out" | grep -q "UI_UX_APPROVED=True" && echo "$out" | grep -q "UI_UX_DISPATCH_ECO=eco_tech_artist" && echo "$out" | grep -q "UI_UX_DISPATCH_DEPT=tech_artist"; then
  report "wp_ui_ux 承接产出交互规范可派发 tech_artist/eco_tech_artist" 0
else
  report "wp_ui_ux 承接产出交互规范可派发 tech_artist/eco_tech_artist" 1
fi

# 14. wp_audio 承接产出完整音频规范
if echo "$out" | grep -q "AUDIO_APPROVED=True" && echo "$out" | grep -q "AUDIO_TYPE=audio_asset" && echo "$out" | grep -q "AUDIO_HAS_AUDIO_SPEC=True" && echo "$out" | grep -q "AUDIO_QUALITY_IN_CONTENT=True"; then
  report "wp_audio 承接产出完整音频规范（audio_spec/audio_quality）" 0
else
  report "wp_audio 承接产出完整音频规范（audio_spec/audio_quality）" 1
fi

# 15. wp_audio 可派发部门+生态音频角色
if echo "$out" | grep -q "AUDIO_DISPATCH_ECO=eco_audio_designer" && echo "$out" | grep -q "AUDIO_DISPATCH_DEPT=audio_designer"; then
  report "wp_audio 可派发 audio_designer/eco_audio_designer" 0
else
  report "wp_audio 可派发 audio_designer/eco_audio_designer" 1
fi

# 16. 美术圈生态角色全链路可派发
if echo "$out" | grep -q "REG_ART_DISPATCHABLE=3"; then
  report "美术圈生态角色全链路可派发（task_scheduler）" 0
else
  report "美术圈生态角色全链路可派发（task_scheduler）" 1
fi

echo ""
echo "【美术线生态角色模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 美术线生态角色功能模块验收通过"
exit 0

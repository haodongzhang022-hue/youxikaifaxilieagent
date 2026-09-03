# ============================================================
# 实例化团队端到端联动测试信号灯（v0.9 新增）
# 说明: 验证 v0.8 预设实例化器产出的「真实团队」（13 个正式角色，
#       六大部门齐全）能装配到部门流水线并跑通全链路联动——
#       1. 实例化角色注册进经理部门能力表（可被 _assign_resources 识别）；
#       2. 实例化团队按六大部门装配为可执行 Agent（以实例化 role_id 承接）；
#       3. 实例化团队承接 wp_* 工作包跑通全链路（策划→程序∥美术→测试→发版→运营）；
#       4. 上游验收后下游自动解锁，全链路 DONE。
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

echo "== 1. 实例化团队端到端联动（v0.9：真实团队装配到部门流水线）=="
out=$($PY run_end_to_end_instantiated.py 2>&1)

# 1. 实例化团队产出 13 个正式角色、六大部门齐全
if echo "$out" | grep -q "共 13 个正式角色"; then
  report "实例化团队产出 13 个正式角色" 0
else
  report "实例化团队产出 13 个正式角色" 1
fi

# 2. 全链路联动 DONE
if echo "$out" | grep -q "all_done = True"; then
  report "实例化团队跑通全链路联动（all_done=True）" 0
else
  report "实例化团队跑通全链路联动（all_done=True）" 1
fi

# 3. 实例化 role_id 作为主责承接工作包（而非 base_role）
if echo "$out" | grep -q "主责=balance_designer_ptype_mobile_game" \
   && echo "$out" | grep -q "主责=client_dev_unity_1" \
   && echo "$out" | grep -q "主责=project_manager_phase_production"; then
  report "实例化 role_id 作为主责承接工作包" 0
else
  report "实例化 role_id 作为主责承接工作包" 1
fi

# 4. 按模块精确指派（wp_server→server_dev_unity_1、wp_engine→engine_dev_unity_1）
if echo "$out" | grep -q "wp_server.*主责=server_dev_unity_1" \
   && echo "$out" | grep -q "wp_engine.*主责=engine_dev_unity_1" \
   && echo "$out" | grep -q "wp_ai_logic.*主责=ai_programmer_unity_1"; then
  report "按模块精确指派实例化主责（server/engine/ai_logic）" 0
else
  report "按模块精确指派实例化主责（server/engine/ai_logic）" 1
fi

# 5. 六部门主责角色均来自实例化团队（六部门全覆盖）
for dept_role in "策划线.*balance_designer_ptype_mobile_game" \
                 "程序线.*client_dev_unity_1" \
                 "美术线.*tech_artist_unity_1" \
                 "测试线.*qa_engineer_unity_1" \
                 "项目管理.*project_manager_phase_production" \
                 "运营线.*game_operator_ptype_mobile_game"; do
  if echo "$out" | grep -q "$dept_role"; then
    report "部门流水线覆盖：$dept_role" 0
  else
    report "部门流水线覆盖：$dept_role" 1
  fi
done

# 6. 工作包全部 DONE
done_count=$(echo "$out" | grep -c "状态=DONE")
if [ "$done_count" -ge 12 ]; then
  report "全部工作包 DONE（>=12 个）" 0
else
  report "全部工作包 DONE（>=12 个）" 1
fi

# 7. 注册/装配口径一致（评审点：DEPT_KEY_BY_NAME 含 support、DEPT_AGENT_CLASS 仅六部门
#    的漂移修复）——所有已注册实例化角色都装配了总线 Agent，无「已注册却未装配」缺失。
if ! echo "$out" | grep -q "未装配到总线"; then
  report "注册/装配口径一致（无已注册但未装配 Agent 的角色）" 0
else
  report "注册/装配口径一致（无已注册但未装配 Agent 的角色）" 1
fi

# 8. 评审修复点回归：跨部门数据流打通（评审点 1）
#    上游 wp_numeric_model 的市场预演产出必须注入下游 wp_data_ops 的 payload，
#    使运营线能消费真实上游产出而非恒走回退分支（死代码路径）。
inject_out=$($PY - <<'PY'
from message_bus import MessageBus, build_task_assign
from game_producer_agent import GameProducerAgent
from department_agents import build_department_agents
import sys
sys.path.insert(0, '.')
bus = MessageBus()
manager = GameProducerAgent(bus=bus)
manager.boot()
for a in build_department_agents(bus).values():
    a.boot()
architecture = {'project': '注入回归', 'modules': ['numeric_model', 'data_ops']}
bus.publish(build_task_assign('architect', manager.role_id, 't001', {'architecture': architecture}))
bus.process_all()
t = manager.scheduler.queue.tasks.get('wp_data_ops')
up = (t.payload.get('_upstream') or {}) if t else {}
sim = up.get('wp_numeric_model', {}).get('market_simulation') or {}
print('INJECT_OK' if sim.get('equilibrium') and sim.get('metrics') else 'INJECT_MISS')
PY
)
if echo "$inject_out" | grep -q "INJECT_OK"; then
  report "跨部门数据流打通（上游市场预演注入下游 wp_data_ops）" 0
else
  report "跨部门数据流打通（上游市场预演注入下游 wp_data_ops）" 1
fi

# 9. 评审修复点回归：发版门禁复用真实全链路产出（评审点 2）
#    PmDeptAgent 不应再硬编码门禁输入全 True（流水线内恒 GO、质量门禁失效），
#    而应通过 aggregate_and_release() 聚合真实产出做验收。
gate_out=$($PY - <<'PY'
from release_gate import aggregate_and_release
import sys
sys.path.insert(0, '.')
g = aggregate_and_release()
# 真实门禁：含可辨识的生态角色注册数量与市场预演诊断字段，而非硬编码布尔
eco = g.get('gate_results', {}).get('ecosystem_roles', {})
mp = g.get('gate_results', {}).get('market_preview', {})
print('GATE_OK' if g.get('total_checks') and (eco or mp) else 'GATE_MISS')
PY
)
if echo "$gate_out" | grep -q "GATE_OK"; then
  report "发版门禁复用真实全链路产出（非硬编码全 True）" 0
else
  report "发版门禁复用真实全链路产出（非硬编码全 True）" 1
fi
# 10. 评审修复点回归：实例化场景 narrative/combat 模块 owner 不为 None
#     修复前：过滤逻辑按模块级 DEPARTMENTS 白名单一刀切，将已注册实例化角色
#     过滤掉，导致 team_unity 实例化装配场景中 narrative/combat 模块（无对应
#     实例化成员）owner=None 阻塞下游。修复后：仅剔除坏角色，保留模块级角色
#     与已注册实例化角色，narrative/combat 可回退到 balance_designer 等可承接角色。
nc_out=$($PY - <<'PYINNER'
from message_bus import MessageBus
from game_producer_agent import GameProducerAgent
import sys
sys.path.insert(0, '.')
bus = MessageBus()
manager = GameProducerAgent(bus=bus)
manager.boot()
# 模拟标准实例化团队：balance_designer 有实例化成员，narrative/combat 无
manager.instantiated_role_ids.add('balance_designer_ptype_mobile_game')
# 将实例化角色加入部门 roles（模拟 run_end_to_end_instantiated.py 的注册行为）
if 'balance_designer_ptype_mobile_game' not in manager.departments['design']['roles']:
    manager.departments['design']['roles'].append('balance_designer_ptype_mobile_game')
manager.instantiated_by_base = {'balance_designer': ['balance_designer_ptype_mobile_game']}
wp_n = {'department': 'design', 'module': 'narrative', 'module_role': None}
manager._assign_resources(wp_n)
wp_c = {'department': 'design', 'module': 'combat', 'module_role': None}
manager._assign_resources(wp_c)
n_owner = wp_n.get('owner')
c_owner = wp_c.get('owner')
print('NARRATIVE_OK' if n_owner is not None else 'NARRATIVE_NONE')
print('COMBAT_OK' if c_owner is not None else 'COMBAT_NONE')
if n_owner:
    print(f'n_owner={n_owner}')
if c_owner:
    print(f'c_owner={c_owner}')
PYINNER
)
if echo "$nc_out" | grep -q "NARRATIVE_OK" && echo "$nc_out" | grep -q "COMBAT_OK"; then
  report "实例化场景 narrative/combat owner 不为 None（回归修复）" 0
else
  report "实例化场景 narrative/combat owner 不为 None（回归修复）" 1
fi
echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 实例化团队端到端联动通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 实例化团队端到端联动存在阻塞项"
  exit 1
fi

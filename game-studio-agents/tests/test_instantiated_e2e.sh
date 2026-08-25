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

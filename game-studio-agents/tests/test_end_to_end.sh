# ============================================================
# 多部门 Agent 端到端联动测试信号灯（v0.7 新增）
# 说明: 验证六大部门 Agent 能否接收派单、执行工作包、上报验收，
#       并通过 task_scheduler 自动解锁下游，跑通全链路。
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

echo "== 1. 六大部门 Agent 就绪（v0.7）=="
out=$($PY department_agents.py 2>&1)
for dept in "design:lead_designer:策划线" "program:cto:程序线" "art:art_director:美术线" "qa:qa_engineer:测试线" "pm:project_manager:项目管理" "ops:data_analyst:运营线"; do
  key="${dept%%:*}"
  rest="${dept#*:}"
  role="${rest%%:*}"
  deptname="${rest#*:}"
  if echo "$out" | grep -q "${key}: ${role} (${deptname})"; then
    report "部门 Agent ${key}(${role}) 就绪" 0
  else
    report "部门 Agent ${key}(${role}) 就绪" 1
  fi
done

echo "== 2. 端到端联动跑通全链路（v0.7）=="
out=$($PY run_end_to_end.py 2>&1)
if echo "$out" | grep -q "all_done=True"; then
  report "全链路端到端联动完成（all_done=True）" 0
else
  report "全链路端到端联动完成（all_done=True）" 1
fi
# 六个部门工作包全部 DONE
for wp in "wp_gameplay:策划线" "wp_client:程序线" "wp_art_direction:美术线" "wp_testing:测试线" "wp_release:项目管理" "wp_data_ops:运营线"; do
  id="${wp%%:*}"
  dept="${wp#*:}"
  if echo "$out" | grep -q "${id}[[:space:]]*${dept}[[:space:]]*.*DONE"; then
    report "工作包 ${id}(${dept}) 完成 DONE" 0
  else
    report "工作包 ${id}(${dept}) 完成 DONE" 1
  fi
done
# 依赖解锁（下游依赖上游）
if echo "$out" | grep -q "wp_client.*DONE.*\['wp_gameplay', 'wp_numeric_model'\]"; then
  report "下游 wp_client 依赖上游策划产出并完成" 0
else
  report "下游 wp_client 依赖上游策划产出并完成" 1
fi
if echo "$out" | grep -q "wp_testing.*DONE.*wp_client"; then
  report "下游 wp_testing 依赖程序产出并完成" 0
else
  report "下游 wp_testing 依赖程序产出并完成" 1
fi
if echo "$out" | grep -q "wp_release.*DONE.*wp_testing"; then
  report "下游 wp_release 依赖测试通过并完成" 0
else
  report "下游 wp_release 依赖测试通过并完成" 1
fi

echo "== 3. 幂等执行（重复派单不重复执行）=="
if ! echo "$out" | grep -qE "已完成 \['wp_client', 'wp_server', 'wp_engine', 'wp_ai_logic', 'wp_client'"; then
  report "部门 Agent 幂等（重复派单不重复执行）" 0
else
  report "部门 Agent 幂等（重复派单不重复执行）" 1
fi

echo ""
echo "端到端联动测试结果: $pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then
  echo "🔴 阻塞：存在未通过断言"
  exit 1
fi
echo "🟢 全部通过"
exit 0

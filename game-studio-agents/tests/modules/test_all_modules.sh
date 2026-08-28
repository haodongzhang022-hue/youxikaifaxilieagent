#!/usr/bin/env bash
# ============================================================
# 功能模块测试总入口（一键运行全部模块验收）
# 说明: 以每个功能模块为单位，逐个运行模块测试脚本，
#       汇总各模块验收结果。
# 退出码: 0 = 🟢 全部通过，1 = 🔴 有阻塞
# ============================================================
set -uo pipefail

cd "$(dirname "$0")"

# 按依赖顺序排列模块测试
MODULES=(
    "test_mod_message_bus.sh"
    "test_mod_task_scheduler.sh"
    "test_mod_agent_core.sh"
    "test_mod_agent_identity.sh"
    "test_mod_collaboration.sh"
    "test_mod_dispatch.sh"
    "test_mod_game_producer.sh"
    "test_mod_department_agents.sh"
    "test_mod_engine_adaptation.sh"
    "test_mod_progress_pusher.sh"
    "test_mod_release_gate.sh"
    "test_mod_ecosystem_roles.sh"
    "test_mod_instantiator.sh"
    "test_mod_merged_confirm.sh"
    "test_mod_reference_learner.sh"
    "test_mod_end_to_end.sh"
)

total_pass=0
total_fail=0
declare -a RESULTS=()

echo "=============================================="
echo "  功能模块验收测试汇总"
echo "=============================================="
echo ""

for mod in "${MODULES[@]}"; do
    if [ ! -f "$mod" ]; then
        echo "⚠️  缺失模块测试脚本: $mod"
        total_fail=$((total_fail+1))
        RESULTS+=("${mod}|⚠️|0")
        continue
    fi
    
    echo "--- 运行模块测试: ${mod} ---"
    if bash "$mod" > /tmp/mod_test_out_$$.txt 2>&1; then
        # 提取断言通过数（格式：【xxx模块验收】N 通过 / M 失败）
        pass_count=$(grep -oP '【.*?】\s*\K\d+(?= 通过)' /tmp/mod_test_out_$$.txt | head -1)
        if [ -z "$pass_count" ]; then
            pass_count="✓"
        fi
        echo "  🟢 ${mod} 通过 (${pass_count} 项断言)"
        total_pass=$((total_pass+1))
        RESULTS+=("${mod}|🟢|${pass_count}")
    else
        fail_count=$(grep -oP '\d+(?= 失败)' /tmp/mod_test_out_$$.txt | head -1 || echo "?")
        echo "  🔴 ${mod} 失败"
        tail -20 /tmp/mod_test_out_$$.txt
        total_fail=$((total_fail+1))
        RESULTS+=("${mod}|🔴|${fail_count}")
    fi
    echo ""
done

echo "=============================================="
echo "  验收结果汇总"
echo "=============================================="
for r in "${RESULTS[@]}"; do
    IFS='|' read -r mod status count <<< "$r"
    echo "  ${status} ${mod} — ${count} 项断言"
done
echo ""
echo "----------------------------------------------"
echo "总览: $total_pass 个模块通过 / $total_fail 个模块失败"
echo "----------------------------------------------"

if [ "$total_fail" -gt 0 ]; then
    echo "🔴 存在未通过的功能模块，需修复后重验"
    exit 1
fi
echo "🟢 全部功能模块验收通过"
exit 0

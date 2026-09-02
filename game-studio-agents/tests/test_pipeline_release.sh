#!/usr/bin/env bash
# ============================================================
# 管线矩阵驱动发布评审 测试信号灯（Issue #128 · 程序线）
# 对齐游戏架构师 M1-M5 蓝图：
#   M1 pipeline_release.py 单管线 GO/NO-GO
#   M2 pipeline_quality_gate.py 管线质量门禁 + release_gate 管线级聚合
#   M3 game_producer_agent 拆包标注 pipeline_id
#   M4 department_agents 执行后回报管线状态
#   M5 pipeline_release_plan.py 发版计划与里程碑编排
# ============================================================

set -e
cd "$(dirname "$0")/.."

PASS=0
FAIL=0

if ! command -v python3 &>/dev/null; then
    echo "[FAIL] python3 不可用"
    exit 1
fi

echo ""
echo "=== 1. M1 pipeline_release.py 管线发布评审核心自测 ==="
if output=$(python3 config/pipeline_release.py 2>&1); then
    if echo "$output" | grep -q "PASS.*管线发布评审核心"; then
        echo "[PASS] M1 管线发布评审核心自测通过（单管线 GO/NO-GO）"
        PASS=$((PASS+1))
    else
        echo "[FAIL] M1 自测未通过"
        FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] M1 运行失败"; echo "$output" | tail -5; FAIL=$((FAIL+1))
fi

echo ""
echo "=== 2. M1 单管线 GO/NO-GO 语义验证 ==="
if output=$(python3 -c "
import sys; sys.path.insert(0, 'config')
from pipeline_release import PipelineReleaseReviewer, run_pipeline_release
r = PipelineReleaseReviewer()
# GO 场景：character_animation 依赖 skeleton_binding，须传入上游已放行集合
go = r.run_pipeline_release('unity','character_animation',
    {'state':'completed','quality_checks':{'动作流畅度':True,'性能基准':True,'风格一致性':True}},
    {'no_stage_crossing':True,'reusable_assets':True,'stage_alignment':True},
    released={'pipeline.skeleton_binding.unity'})
assert go.release_verdict == 'GO', f'应 GO, got {go.release_verdict}'
# 依赖未放行（缺省 released）→ 保守 NO-GO/BLOCKED（统一单条/批量依赖判定）
dep_nogo = r.run_pipeline_release('unity','character_animation',
    {'state':'completed','quality_checks':{'动作流畅度':True,'性能基准':True,'风格一致性':True}},
    {'no_stage_crossing':True,'reusable_assets':True,'stage_alignment':True})
assert dep_nogo.release_verdict == 'NO-GO', f'依赖未放行应 NO-GO, got {dep_nogo.release_verdict}'
assert dep_nogo.state == 'blocked', f'应 blocked, got {dep_nogo.state}'
# NO-GO 场景（质量门禁未达标，无依赖的 cocos ai_trigger）
nogo = run_pipeline_release('cocos','ai_trigger',
    {'state':'completed','quality_checks':{'行为覆盖率':True,'帧率影响≤5%':False}})
assert nogo['verdict'] == 'NO-GO', f'应 NO-GO, got {nogo}'
assert nogo['missing_checks'], '应有未达标项'
print('单管线 GO/NO-GO 语义验证通过')
" 2>&1); then
    echo "[PASS] M1 单管线 GO/NO-GO 语义正确"; PASS=$((PASS+1))
else
    echo "[FAIL] M1 语义验证失败"; echo "$output" | tail -5; FAIL=$((FAIL+1))
fi

echo ""
echo "=== 3. M2 pipeline_quality_gate.py 管线质量门禁自测 ==="
if output=$(python3 config/pipeline_quality_gate.py 2>&1); then
    if echo "$output" | grep -q "PASS.*管线质量门禁"; then
        echo "[PASS] M2 管线质量门禁自测通过"; PASS=$((PASS+1))
    else
        echo "[FAIL] M2 自测未通过"; FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] M2 运行失败"; echo "$output" | tail -5; FAIL=$((FAIL+1))
fi

echo ""
echo "=== 4. M2 40 条管线逐条可评审验证 ==="
if output=$(python3 -c "
import sys; sys.path.insert(0, 'config')
from pipeline_quality_gate import PipelineQualityGate
gate = PipelineQualityGate()
all_r = gate.check_all_engines(all_quality_ok=True)
assert all_r['pipeline_count'] >= 40, f'应≥40, got {all_r[\"pipeline_count\"]}'
assert all_r['overall'] == 'GO', f'应全链路 GO, got {all_r[\"overall\"]}'
assert all_r['passed'] >= 40
for eng in ['react','cocos','unity','unreal']:
    assert eng in all_r['engine_summary'], f'缺 {eng} 引擎'
print('40 条管线逐条可评审验证通过')
" 2>&1); then
    echo "[PASS] M2 40 条管线逐条可评审 + 全链路 GO"; PASS=$((PASS+1))
else
    echo "[FAIL] M2 全链路评审失败"; echo "$output" | tail -5; FAIL=$((FAIL+1))
fi

echo ""
echo "=== 5. M2 release_gate 管线级聚合扩展 ==="
if output=$(python3 -c "
import sys; sys.path.insert(0, 'config')
from release_gate import RELEASE_GATE, run_release_gate
assert 'pipeline_quality' in RELEASE_GATE, 'RELEASE_GATE 应含 pipeline_quality'
# 缺省路径（未注入管线就绪）应保守非就绪（不恒绿），能真实拦截未放行管线
res = run_release_gate({})
pq = res['gate_results']['pipeline_quality']
assert not pq['ok'], f'缺省路径 pipeline_quality 不应恒绿, got {pq}'
assert pq['total'] == 3
# 显式注入管线全部就绪 → pipeline_quality 门禁 GO
from pipeline_quality_gate import run_pipeline_quality_gate
res2 = run_release_gate({'pipeline_quality': run_pipeline_quality_gate(all_quality_ok=True)})
pq2 = res2['gate_results']['pipeline_quality']
assert pq2['ok'], f'显式就绪时 pipeline_quality 应 ok, got {pq2}'
assert pq2['passed'] == 3 and pq2['total'] == 3
assert res2['total_checks'] >= 16, f'总检查数应≥16(含管线级), got {res2["total_checks"]}'
print('release_gate 管线级聚合扩展验证通过')
" 2>&1); then
    echo "[PASS] M2 release_gate 管线级聚合扩展通过"; PASS=$((PASS+1))
else
    echo "[FAIL] M2 release_gate 扩展失败"; echo "$output" | tail -5; FAIL=$((FAIL+1))
fi

echo ""
echo "=== 6. M3 game_producer_agent 拆包标注 pipeline_id ==="
if output=$(python3 -c "
import sys; sys.path.insert(0, 'config')
import game_producer_agent as g
agent = g.GameProducerAgent()
agent._current_architecture = {'project':'测试','engine':'unity','modules':['client','combat']}
decomposed = agent._decompose('测试', ['client','combat','numeric_model','testing'])
wps = agent._split_work_packages(decomposed)
for wp in wps:
    assert wp.get('pipeline_id'), f'{wp[\"id\"]} 应标注 pipeline_id'
    assert wp['pipeline_id'].startswith('pipeline.'), f'pipeline_id 格式错: {wp[\"pipeline_id\"]}'
    assert wp['pipeline_id'].endswith('.unity'), f'应绑定 unity 引擎: {wp[\"pipeline_id\"]}'
print('拆包标注 pipeline_id 验证通过')
" 2>&1); then
    echo "[PASS] M3 拆包标注 pipeline_id"; PASS=$((PASS+1))
else
    echo "[FAIL] M3 拆包标注失败"; echo "$output" | tail -5; FAIL=$((FAIL+1))
fi

echo ""
echo "=== 7. M4 department_agents 执行后回报管线状态 ==="
if output=$(python3 -c "
import sys; sys.path.insert(0, 'config')
from message_bus import MessageBus
from department_agents import ProgramDeptAgent
bus = MessageBus()
agent = ProgramDeptAgent(bus)
wp = {'id':'wp_client','module':'client','department_name':'程序线',
      'pipeline_id':'pipeline.character_animation.unity','pipeline_engine':'unity','pipeline_domain':'character_animation'}
status = agent._report_pipeline_status('wp_client','pipeline.character_animation.unity',wp,
                                      {'quality_checks':{'动作流畅度':True}}, True)
assert status['release_verdict'] == 'GO'
assert agent.pipeline_status['pipeline.character_animation.unity']['release_verdict'] == 'GO'
assert agent.report()['pipeline_status']['pipeline.character_animation.unity']
print('部门执行后回报管线状态验证通过')
" 2>&1); then
    echo "[PASS] M4 部门回报管线状态"; PASS=$((PASS+1))
else
    echo "[FAIL] M4 回报失败"; echo "$output" | tail -5; FAIL=$((FAIL+1))
fi

echo ""
echo "=== 8. M5 pipeline_release_plan.py 发版计划与里程碑编排自测 ==="
if output=$(python3 config/pipeline_release_plan.py 2>&1); then
    if echo "$output" | grep -q "PASS.*管线发版计划"; then
        echo "[PASS] M5 发版计划与里程碑编排自测通过"; PASS=$((PASS+1))
    else
        echo "[FAIL] M5 自测未通过"; FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] M5 运行失败"; echo "$output" | tail -5; FAIL=$((FAIL+1))
fi

echo ""
echo "=== 9. M5 依赖链发版编排验证 ==="
if output=$(python3 -c "
import sys; sys.path.insert(0, 'config')
from pipeline_release_plan import plan_pipeline_release
plan = plan_pipeline_release('unity')
order = plan['release_order']
assert plan['pipeline_count'] >= 12
# 骨骼绑定必须先于角色动作放行
assert order.index('pipeline.skeleton_binding.unity') < order.index('pipeline.character_animation.unity')
# 模型生成必须先于模型上色/法线/纹理材质
assert order.index('pipeline.model_generation.unity') < order.index('pipeline.model_painting.unity')
assert plan['milestones'].get('M1')
assert plan['max_milestone'] >= 3
print('依赖链发版编排验证通过')
" 2>&1); then
    echo "[PASS] M5 依赖链发版编排正确"; PASS=$((PASS+1))
else
    echo "[FAIL] M5 依赖链编排失败"; echo "$output" | tail -5; FAIL=$((FAIL+1))
fi

echo ""
echo "=============================="
echo "管线矩阵驱动发布评审测试结果: $PASS 通过 / $FAIL 失败"
echo "=============================="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0

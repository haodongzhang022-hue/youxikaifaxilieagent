#!/usr/bin/env bash
# ============================================================
# 引擎分层 × 专业方向 管线矩阵 测试信号灯
# 对齐 Issue #126：验证管线注册表 + 编排核心
# ============================================================

set -e
cd "$(dirname "$0")/.."

PASS=0
FAIL=0

# 检查 Python 可用性
if ! command -v python3 &>/dev/null; then
    echo "[FAIL] python3 不可用，无法运行管线矩阵测试"
    exit 1
fi

echo "=== 1. 管线注册表自测 ==="
if output=$(python3 config/pipeline_registry.py 2>&1); then
    if echo "$output" | grep -q "管线总数: 40"; then
        echo "[PASS] 管线注册表自测通过（40条管线）"
        PASS=$((PASS+1))
    else
        echo "[FAIL] 管线总数不是40"
        echo "$output" | tail -5
        FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] 管线注册表自测失败"
    echo "$output" | tail -10
    FAIL=$((FAIL+1))
fi

echo ""
echo "=== 2. 管线编排器自测 ==="
if output=$(python3 config/pipeline_orchestrator.py 2>&1); then
    if echo "$output" | grep -q "PASS.*编排器自测"; then
        echo "[PASS] 管线编排器自测通过"
        PASS=$((PASS+1))
    else
        echo "[FAIL] 编排器自测未通过"
        FAIL=$((FAIL+1))
    fi
else
    echo "[FAIL] 管线编排器运行失败"
    echo "$output" | tail -10
    FAIL=$((FAIL+1))
fi

echo ""
echo "=== 3. 管线矩阵文档完整性 ==="
if [[ -f docs/engine-pipeline-matrix/00-overview.md && -f docs/engine-pipeline-matrix/01-pipeline-registry.md && -f docs/engine-pipeline-matrix/02-director-booth.md && -f docs/engine-pipeline-matrix/03-pipeline-deep-dive.md ]]; then
    echo "[PASS] 管线矩阵文档完整（4份）"
    PASS=$((PASS+1))
else
    echo "[FAIL] 管线矩阵文档不完整"
    ls docs/engine-pipeline-matrix/ 2>/dev/null || echo "目录不存在"
    FAIL=$((FAIL+1))
fi

echo ""
echo "=== 4. 源码文件存在性 ==="
if [[ -f config/pipeline_registry.py && -f config/pipeline_orchestrator.py ]]; then
    echo "[PASS] 管线源码文件存在"
    PASS=$((PASS+1))
else
    echo "[FAIL] 管线源码文件缺失"
    ls config/pipeline_*.py 2>/dev/null
    FAIL=$((FAIL+1))
fi

echo ""
echo "=== 5. 四引擎覆盖验证 ==="
if output=$(python3 -c "
from config.pipeline_registry import PipelineRegistry
reg = PipelineRegistry()
# 验证四引擎均有管线
for eng in ['react', 'cocos', 'unity', 'unreal']:
    assert len(reg.by_engine(eng)) >= 7, f'{eng} 管线数不足'
# 验证导演台覆盖4引擎
assert len(reg.by_domain('director_booth')) >= 4
# 验证骨骼绑定覆盖≥4引擎
assert len(reg.by_domain('skeleton_binding')) >= 4
# 验证美术深度管线（模型生成等）覆盖Unity+UE
assert len(reg.by_domain('model_generation')) >= 2
assert len(reg.by_domain('texture_material')) >= 2
print('四引擎覆盖验证通过')
" 2>&1); then
    echo "[PASS] 四引擎覆盖验证通过"
    PASS=$((PASS+1))
else
    echo "[FAIL] 四引擎覆盖验证失败"
    echo "$output"
    FAIL=$((FAIL+1))
fi

echo ""
echo "=============================="
echo "管线矩阵测试结果: $PASS 通过 / $FAIL 失败"
echo "=============================="

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
exit 0

#!/usr/bin/env bash
# ============================================================
# 测试：基于时间的模型自动切换 + 历史消耗记录
# 覆盖 model_config.py 的 v2.0 新增功能
# ============================================================

set -e
cd "$(dirname "$0")/../config"

PASS=0
FAIL=0

check() {
    local desc="$1"
    local cond="$2"
    if eval "$cond"; then
        echo "  ✅ $desc"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $desc"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== 模型自动切换自测 ==="

# 1. 模型池存在
check "模型池含 GLM" "python3 -c \"from model_config import MODEL_POOL; assert 'glm' in MODEL_POOL\""
check "模型池含 DeepSeek" "python3 -c \"from model_config import MODEL_POOL; assert 'deepseek' in MODEL_POOL\""

# 2. 高峰/低峰判断
check "工作日 10:30 为高峰" "python3 -c \"from model_config import is_peak_hour; from datetime import datetime; assert is_peak_hour(datetime(2026, 9, 2, 10, 30))\""
check "工作日 22:30 为低峰" "python3 -c \"from model_config import is_peak_hour; from datetime import datetime; assert not is_peak_hour(datetime(2026, 9, 2, 22, 30))\""
check "周末 10:30 为低峰" "python3 -c \"from model_config import is_peak_hour; from datetime import datetime; assert not is_peak_hour(datetime(2026, 9, 5, 10, 30))\""

# 3. 自动选择模型
check "高峰→GLM" "python3 -c \"from model_config import get_auto_model; from datetime import datetime; assert get_auto_model(datetime(2026, 9, 2, 10, 30)) == 'glm-5.3-flash'\""
check "低峰→DeepSeek" "python3 -c \"from model_config import get_auto_model; from datetime import datetime; assert get_auto_model(datetime(2026, 9, 2, 22, 30)) == 'deepseek-v4-flash-0731'\""

# 4. 关闭自动切换
check "关闭自动切换→默认模型" "MODEL_AUTO_SWITCH=false python3 -c \"from model_config import get_auto_model; from datetime import datetime; assert get_auto_model(datetime(2026, 9, 2, 10, 30)) == 'glm-5.3-flash'\""

# 5. 自定义高峰时段
check "自定义高峰时段生效" "MODEL_PEAK_START=20:00 MODEL_PEAK_END=23:00 python3 -c \"from model_config import is_peak_hour; from datetime import datetime; assert is_peak_hour(datetime(2026, 9, 2, 21, 0))\""

# 6. 消耗记录
check "消耗记录写入" "MODEL_USAGE_LOG=/tmp/.test_usage.jsonl python3 -c \"
import os
from model_config import record_usage, read_usage_history, summarize_usage
record_usage('glm-5.3-flash', tokens_in=100, tokens_out=50, context='测试')
record_usage('deepseek-v4-flash-0731', tokens_in=200, tokens_out=100, cost=0.01, context='测试')
recs = read_usage_history()
assert len(recs) == 2, f'应2条, got {len(recs)}'
s = summarize_usage()
assert s['total_calls'] == 2
assert 'glm-5.3-flash' in s['by_model']
assert 'deepseek-v4-flash-0731' in s['by_model']
assert s['by_model']['glm-5.3-flash']['tokens_total'] == 150
print('OK')
\" | grep -q OK"

# 清理
rm -f /tmp/.test_usage.jsonl

echo ""
echo "=== 结果: $PASS 通过 / $FAIL 失败 ==="
[ "$FAIL" -eq 0 ] && echo "🟢 全部通过" || { echo "🔴 有失败"; exit 1; }

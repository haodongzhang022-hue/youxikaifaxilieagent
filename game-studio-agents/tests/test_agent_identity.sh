#!/bin/bash
# ============================================================
# 测试: 通用 Agent 身份自适应模块 (agent_identity.py)
# 版本: v1.0
# 说明: 验证 AgentIdentity 模块能正确探测仓库上下文并生成 @ 召唤格式。
# ============================================================
set -e
cd "$(dirname "$0")/../config"

echo "===== 测试 agent_identity.py 自适应识别 ====="

PASS=0
FAIL=0

# 测试1: 模块可导入且自测通过
echo -n "[1/5] 模块自测运行... "
python3 agent_identity.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅"
    PASS=$((PASS+1))
else
    echo "❌"
    FAIL=$((FAIL+1))
fi

# 测试2: 能探测到当前仓库 slug
echo -n "[2/5] 仓库 slug 探测... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
ctx = id.detect_repo_context()
print(ctx.full_slug)
")
if [ -n "$OUT" ] && echo "$OUT" | grep -q "/"; then
    echo "✅ ($OUT)"
    PASS=$((PASS+1))
else
    echo "❌ ($OUT)"
    FAIL=$((FAIL+1))
fi

# 测试3: 能生成正确的 CodeBuddy @ 召唤格式
echo -n "[3/5] CodeBuddy @ 召唤格式... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
print(id.get_codebuddy_mention())
")
if echo "$OUT" | grep -q "@.*(CodeBuddy)"; then
    echo "✅ ($OUT)"
    PASS=$((PASS+1))
else
    echo "❌ ($OUT)"
    FAIL=$((FAIL+1))
fi

# 测试4: 能生成修复专员的 @ 召唤格式
echo -n "[4/5] 修复专员 @ 召唤格式... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
print(id.get_fixer_mention())
")
if echo "$OUT" | grep -q "@.*(仓库修复专员)"; then
    echo "✅ ($OUT)"
    PASS=$((PASS+1))
else
    echo "❌ ($OUT)"
    FAIL=$((FAIL+1))
fi

# 测试5: 跨仓库策略识别
echo -n "[5/5] 跨仓库策略识别... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
strategy = id.decide_mention_strategy('otherorg/otherrepo')
print(strategy['strategy'])
print(strategy['mention'])
print(strategy['recommendation'])
" 2>&1)
if echo "$OUT" | grep -q "cross_repo"; then
    echo "✅ (跨仓库已识别)"
    PASS=$((PASS+1))
else
    echo "❌"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

echo ""
echo "===== 测试结果: $PASS 通过 / $FAIL 失败 ====="
[ $FAIL -eq 0 ] && echo "🟢 全部通过" || echo "🔴 存在失败"
exit $FAIL

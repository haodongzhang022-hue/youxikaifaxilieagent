#!/bin/bash
# ============================================================
# 测试: 通用 Agent 身份自适应模块 (agent_identity.py)
# 版本: v1.1
# 说明: 验证 AgentIdentity 模块能正确探测仓库上下文并生成 @ 召唤格式。
#       v1.1 新增：评审 NPC 专用 get_review_operational_advice() 自适应
#       召唤 CodeBuddy 操作建议（组织/仓库名不写死，跨仓可用）。
# ============================================================
set -e
cd "$(dirname "$0")/../config"

echo "===== 测试 agent_identity.py 自适应识别 ====="

PASS=0
FAIL=0

# 测试1: 模块可导入且自测通过
echo -n "[1/8] 模块自测运行... "
python3 agent_identity.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅"
    PASS=$((PASS+1))
else
    echo "❌"
    FAIL=$((FAIL+1))
fi

# 测试2: 能探测到当前仓库 slug
echo -n "[2/8] 仓库 slug 探测... "
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
echo -n "[3/8] CodeBuddy @ 召唤格式... "
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
echo -n "[4/8] 修复专员 @ 召唤格式... "
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
echo -n "[5/8] 跨仓库策略识别... "
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

# 测试6: 评审 NPC 自适应召唤 CodeBuddy 操作建议（组织/仓库名不写死）
echo -n "[6/8] 评审召唤 CodeBuddy 操作建议（自适应）... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
print(id.get_review_operational_advice())
" 2>&1)
if echo "$OUT" | grep -q "@.*(CodeBuddy)" && echo "$OUT" | grep -q "仓库自适应识别"; then
    echo "✅ (自适应带壳格式已生成)"
    PASS=$((PASS+1))
else
    echo "❌"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

# 测试7: 评审召唤操作建议支持按目标仓库（跨仓）生成，不写死
echo -n "[7/8] 评审召唤跨仓操作建议（按目标仓库）... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
print(id.get_review_operational_advice('otherorg/otherrepo'))
" 2>&1)
if echo "$OUT" | grep -q "@otherorg/otherrepo(CodeBuddy)"; then
    echo "✅ (按目标仓库自适应: @otherorg/otherrepo(CodeBuddy))"
    PASS=$((PASS+1))
else
    echo "❌"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

# 测试8: 部门统一头（小组）角色结构——六大部门 + 协作支持圈独立
echo -n "[8/8] 部门统一头 KNOWN_ROLES 结构... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import AgentIdentity
roles = list(AgentIdentity.KNOWN_ROLES)
six_depts = ['策划线','程序线','美术线','测试线','项目管理','运营线']
has_six = all(d in roles for d in six_depts)
support_in_six = roles.index('协作支持圈') > roles.index('运营线')
print(f'HAS_SIX={has_six}')
print(f'SUPPORT_AFTER_SIX={support_in_six}')
")
if echo "$OUT" | grep -q "HAS_SIX=True" && echo "$OUT" | grep -q "SUPPORT_AFTER_SIX=True"; then
    echo "✅ (六大部门 + 协作支持圈独立排在六部门之后)"
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

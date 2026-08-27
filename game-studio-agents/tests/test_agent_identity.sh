#!/bin/bash
# ============================================================
# 测试: 通用 Agent 身份自适应模块 (agent_identity.py)
# 版本: v1.2
# 说明: 验证 AgentIdentity 模块能正确探测仓库上下文并生成 @ 召唤格式。
#       v1.1 新增：评审 NPC 专用 get_review_operational_advice() 自适应
#       召唤 CodeBuddy 操作建议（组织/仓库名不写死，跨仓可用）。
#       v1.2 新增：召唤格式有效性断言——带壳召唤行必须独立成行、裸 @，
#       不被反引号/代码块包裹（平台不解析代码块内的 @ 提及）。
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
echo -n "[8/10] 部门统一头 KNOWN_ROLES 结构... "
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

# 测试9: 评审召唤 CodeBuddy 操作建议中，召唤格式行必须独立成行、裸 @（不被反引号/代码块包裹）
echo -n "[9/10] 评审召唤行裸@独立行（不包反引号/代码块）... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
advice = id.get_review_operational_advice()
# 取出召唤行（以 @ 开头、以 (CodeBuddy) 结尾的独立行）
import re
summon_line = None
for line in advice.splitlines():
    line_stripped = line.strip()
    if line_stripped.startswith('@') and line_stripped.endswith('(CodeBuddy)'):
        summon_line = line_stripped
        break
print(f'SUMMON={summon_line}')
BACKTICK = chr(96)  # 反引号，避免 bash 命令替换
print(f'RAW_LINE_HAS_BACKTICK={BACKTICK in summon_line if summon_line else "NA"}')
")
SUMMON=$(echo "$OUT" | grep "^SUMMON=" | cut -d= -f2-)
HAS_BT=$(echo "$OUT" | grep "^RAW_LINE_HAS_BACKTICK=" | cut -d= -f2-)
if [ -n "$SUMMON" ] && [ "$HAS_BT" = "False" ]; then
    echo "✅ (召唤行=$SUMMON，独立裸@行无反引号包裹)"
    PASS=$((PASS+1))
else
    echo "❌"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

# 测试10: 评审召唤操作建议的召唤行可被平台解析（不以反引号开头，非代码块包裹）
echo -n "[10/10] 召唤行格式可被平台解析（非代码块/反引号包裹）... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
advice = id.get_review_operational_advice()
# 校验召唤行是独立裸 @ 行：行首是 @，无前导反引号，整行无反引号包裹
import re
ok = False
for line in advice.splitlines():
    ls = line.strip()
    BACKTICK = chr(96)
    if ls.startswith('@') and ls.endswith('(CodeBuddy)') and BACKTICK not in ls:
        ok = True
        break
print(f'PARSABLE={ok}')
")
if echo "$OUT" | grep -q "PARSABLE=True"; then
    echo "✅ (召唤行@.../(CodeBuddy)独立成行、无反引号，可被平台解析触发)"
    PASS=$((PASS+1))
else
    echo "❌"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

# 测试11: 纯 git 探测场景（清除所有 CNB env）——_detect_from_git 不得泄漏 _remote 辅助键
echo -n "[11/11] 纯 git 探测（env 全清）不泄漏 _remote 辅助键... "
OUT=$(python3 -c "
import sys, os, subprocess, tempfile, re
sys.path.insert(0, '.')
# 清除所有 CNB 相关 env，强制走 _detect_from_git 路径
for k in list(os.environ.keys()):
    if k.startswith('CNB_'):
        del os.environ[k]
from agent_identity import _detect_from_git, AgentIdentity
git_data = _detect_from_git()
# 断言 _remote 辅助键不得出现在返回结果中
has_remote = '_remote' in git_data
print(f'GIT_DATA_HAS_REMOTE={has_remote}')
print(f'GIT_DATA={git_data}')
# 构造 RepoContext 不得崩溃
ctx = AgentIdentity().detect_repo_context()
print(f'CTX_SLUG={ctx.full_slug}')
" 2>&1)
if echo "$OUT" | grep -q "GIT_DATA_HAS_REMOTE=False" && echo "$OUT" | grep -q "CTX_SLUG=.*/"; then
    echo "✅ (纯 git 探测无 _remote 泄漏，RepoContext 构造正常)"
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

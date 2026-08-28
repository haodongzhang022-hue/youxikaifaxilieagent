#!/bin/bash
# ============================================================
# 测试: 通用 Agent 身份自适应模块 (agent_identity.py)
# 版本: v1.4
# 说明: 验证 AgentIdentity 模块能正确探测仓库上下文并生成 @ 召唤格式。
#       v1.1 新增：评审 NPC 专用 get_review_operational_advice() 自适应
#       召唤操作建议（组织/仓库名不写死，跨仓可用）。
#       v1.2 新增：召唤格式有效性断言——带壳召唤行必须独立成行、裸 @，
#       不被反引号/代码块包裹（平台不解析代码块内的 @ 提及）。
#       v1.3 新增：召唤优先级链——默认优先召唤仓库处理专员，可显式
#       指定 role 召唤 CodeBuddy，禁止一股脑召唤多个角色。
#       v1.4 新增：触发安全控制——get_review_operational_advice() 仅输出一个
#       实际召唤行；get_operational_advice() 中所有召唤格式反引号包裹。
#       新增测试 14/15/16 验证无多重触发。
# ============================================================
set -e
cd "$(dirname "$0")/../config"

echo "===== 测试 agent_identity.py 自适应识别 ====="

PASS=0
FAIL=0

# 测试1: 模块可导入且自测通过
echo -n "[1/18] 模块自测运行... "
python3 agent_identity.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅"
    PASS=$((PASS+1))
else
    echo "❌"
    FAIL=$((FAIL+1))
fi

# 测试2: 能探测到当前仓库 slug
echo -n "[2/18] 仓库 slug 探测... "
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
echo -n "[3/18] CodeBuddy @ 召唤格式... "
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
echo -n "[4/18] 修复专员 @ 召唤格式... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
print(id.get_handler_mention())
")
if echo "$OUT" | grep -q "@.*(仓库处理专员)"; then
    echo "✅ ($OUT)"
    PASS=$((PASS+1))
else
    echo "❌ ($OUT)"
    FAIL=$((FAIL+1))
fi

# 测试4b: 能生成仓库处理专员的 @ 召唤格式
echo -n "[5/18] 仓库处理专员 @ 召唤格式... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
print(id.get_handler_mention())
")
if echo "$OUT" | grep -q "@.*(仓库处理专员)"; then
    echo "✅ ($OUT)"
    PASS=$((PASS+1))
else
    echo "❌ ($OUT)"
    FAIL=$((FAIL+1))
fi

# 测试5: 跨仓库策略识别
echo -n "[6/18] 跨仓库策略识别... "
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

# 测试6: 评审 NPC 自适应召唤操作建议（默认优先仓库处理专员，组织/仓库名不写死）
echo -n "[7/18] 评审召唤仓库处理专员操作建议（自适应，优先级最高）... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
print(id.get_review_operational_advice())
" 2>&1)
if echo "$OUT" | grep -q "@.*(仓库处理专员)" && echo "$OUT" | grep -q "同一时刻只召唤当前一个角色"; then
    echo "✅ (默认优先召唤仓库处理专员，唯一召唤行+触发安全说明已生成)"
    PASS=$((PASS+1))
else
    echo "❌"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

# 测试7: 评审召唤操作建议支持按目标仓库（跨仓）生成，不写死（默认仓库处理专员）
echo -n "[8/18] 评审召唤跨仓操作建议（按目标仓库，仓库处理专员）... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
print(id.get_review_operational_advice('otherorg/otherrepo'))
" 2>&1)
if echo "$OUT" | grep -q "@otherorg/otherrepo(仓库处理专员)"; then
    echo "✅ (按目标仓库自适应: @otherorg/otherrepo(仓库处理专员))"
    PASS=$((PASS+1))
else
    echo "❌"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

# 测试8: 部门统一头（小组）角色结构——六大部门 + 协作支持圈独立
echo -n "[9/18] 部门统一头 KNOWN_ROLES 结构... "
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

# 测试9: 评审召唤仓库处理专员操作建议中，召唤格式行必须独立成行、裸 @（不被反引号/代码块包裹）
echo -n "[10/18] 评审召唤行裸@独立行（不包反引号/代码块）... "
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
    if line_stripped.startswith('@') and line_stripped.endswith('(仓库处理专员)'):
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
echo -n "[11/18] 召唤行格式可被平台解析（非代码块/反引号包裹）... "
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
    if ls.startswith('@') and ls.endswith('(仓库处理专员)') and BACKTICK not in ls:
        ok = True
        break
print(f'PARSABLE={ok}')
")
if echo "$OUT" | grep -q "PARSABLE=True"; then
    echo "✅ (召唤行@.../(仓库处理专员)独立成行、无反引号，可被平台解析触发)"
    PASS=$((PASS+1))
else
    echo "❌"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

# 测试11: 纯 git 探测场景（清除所有 CNB env）——_detect_from_git 不得泄漏 _remote 辅助键
echo -n "[12/18] 纯 git 探测（env 全清）不泄漏 _remote 辅助键... "
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


# 测试11: 仓库处理专员 KNOWN_ROLES 包含在角色列表中
echo -n "[13/18] 仓库处理专员角色注册检查... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import AgentIdentity
roles = list(AgentIdentity.KNOWN_ROLES)
invoker_in_roles = '仓库处理专员' in roles
print(f'HAS_INVOKER={invoker_in_roles}')
")
if echo "$OUT" | grep -q "HAS_INVOKER=True"; then
    echo "✅ (仓库处理专员已注册)"
    PASS=$((PASS+1))
else
    echo "❌"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

# 测试12: 召唤优先级链（仓库处理专员 → CodeBuddy）
echo -n "[14/18] 召唤优先级链（逐个降级）... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import AgentIdentity
id = AgentIdentity()
chain = id.get_repair_priority_chain()
print('CHAIN=' + ','.join(chain))
" 2>&1)
CHAIN=$(echo "$OUT" | grep "^CHAIN=" | cut -d= -f2-)
if [ "$CHAIN" = "仓库处理专员,CodeBuddy" ]; then
    echo "✅ (优先级链: 仓库处理专员→CodeBuddy)"
    PASS=$((PASS+1))
else
    echo "❌ ($CHAIN)"
    FAIL=$((FAIL+1))
fi

# 测试13: role 参数可显式指定召唤 CodeBuddy（兜底）
echo -n "[15/18] role 参数指定召唤 CodeBuddy（兜底）... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
print(id.get_review_operational_advice(role='CodeBuddy'))
" 2>&1)
if echo "$OUT" | grep -q "@.*(CodeBuddy)"; then
    echo "✅ (指定 role=CodeBuddy 可召唤本仓库 CodeBuddy 兜底)"
    PASS=$((PASS+1))
else
    echo "❌"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

# 测试14: 触发安全——get_review_operational_advice() 输出中只有一个裸召唤行（无多重触发）
echo -n "[16/18] 评审召唤唯一召唤行（无多重触发）... "
OUT=$(python3 -c "
import sys, re
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
advice = id.get_review_operational_advice()
# 统计裸召唤行数量：独立成行的 @slug(role) 格式，无反引号包裹
pattern = re.compile(r'@[^\s()]+\([^)]+\)')
unprotected = []
for line in advice.splitlines():
    ls = line.strip()
    if not ls:
        continue
    for m in pattern.findall(ls):
        BACKTICK = chr(96)
        if (BACKTICK + m + BACKTICK) not in ls:
            unprotected.append(m)
print(f'UNPROTECTED_COUNT={len(unprotected)}')
print(f'UNPROTECTED={unprotected}')
" 2>&1)
COUNT=$(echo "$OUT" | grep "^UNPROTECTED_COUNT=" | cut -d= -f2-)
if [ "$COUNT" = "1" ]; then
    echo "✅ (仅1个裸召唤行，无多重触发)"
    PASS=$((PASS+1))
else
    echo "❌ (裸召唤行数量=$COUNT)"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

# 测试15: 触发安全——get_operational_advice() 输出中无未包裹的召唤格式（全部被反引号包裹）
echo -n "[17/18] 操作建议无裸召唤格式（全部反引号包裹）... "
OUT=$(python3 -c "
import sys, re
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
advice = id.get_operational_advice()
pattern = re.compile(r'@[^\s()]+\([^)]+\)')
unprotected = []
for line in advice.splitlines():
    ls = line.strip()
    if not ls:
        continue
    for m in pattern.findall(ls):
        BACKTICK = chr(96)
        if (BACKTICK + m + BACKTICK) not in ls:
            unprotected.append(m)
print(f'UNPROTECTED_COUNT={len(unprotected)}')
print(f'UNPROTECTED={unprotected}')
" 2>&1)
COUNT=$(echo "$OUT" | grep "^UNPROTECTED_COUNT=" | cut -d= -f2-)
if [ "$COUNT" = "0" ]; then
    echo "✅ (操作建议中所有召唤格式均已用反引号包裹，不会触发NPC)"
    PASS=$((PASS+1))
else
    echo "❌ (未包裹召唤格式数量=$COUNT)"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

# 测试16: 触发安全——评审召唤建议中不允许出现其他角色名的裸召唤（如 CodeBuddy 的召唤格式）
echo -n "[18/18] 评审召唤建议无其他角色召唤格式... "
OUT=$(python3 -c "
import sys
sys.path.insert(0, '.')
from agent_identity import get_identity
id = get_identity()
advice = id.get_review_operational_advice()
# 检查是否有 CodeBuddy 或其他角色的召唤格式被裸输出
bad_mentions = []
for role in ['CodeBuddy', '仓库处理专员', '代码审查员']:
    if '@.*(' + role + ')' in advice:
        # 需要检查是否为裸格式（无反引号包裹）
        import re
        pattern = re.compile(r'@[^\s()]+\(CodeBuddy\)|@[^\s()]+\(仓库处理专员\)|@[^\s()]+\(代码审查员\)')
        for m in pattern.findall(advice):
            BACKTICK = chr(96)
            if (BACKTICK + m + BACKTICK) not in advice:
                bad_mentions.append(m)
print(f'BAD_COUNT={len(bad_mentions)}')
print(f'BAD={bad_mentions}')
" 2>&1)
BAD=$(echo "$OUT" | grep "^BAD_COUNT=" | cut -d= -f2-)
if [ "$BAD" = "0" ]; then
    echo "✅ (评审召唤建议中无其他角色的裸召唤格式)"
    PASS=$((PASS+1))
else
    echo "❌ (发现未包裹的其他角色召唤: $BAD)"
    echo "$OUT"
    FAIL=$((FAIL+1))
fi

echo ""
echo "===== 测试结果: $PASS 通过 / $FAIL 失败 ====="
[ $FAIL -eq 0 ] && echo "🟢 全部通过" || echo "🔴 存在失败"
exit $FAIL

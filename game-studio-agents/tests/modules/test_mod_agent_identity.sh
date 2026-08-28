#!/usr/bin/env bash
# ============================================================
# 功能模块验收测试：Agent 身份自适应 (AgentIdentity)
# 功能定义: 自动识别当前仓库上下文，生成正确的 @ 召唤格式，
#           支持同仓库/跨仓库策略与召唤优先级链。
# 验收标准: 仓库探测正确、召唤格式正确、优先级链正确。
# 退出码: 0 = 🟢 通过，1 = 🔴 阻塞
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/../../config"
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

echo "== 功能模块验收：Agent 身份自适应 (AgentIdentity) =="

out=$($PY - <<'PYEOF'
from agent_identity import AgentIdentity

# 1. 创建身份模块
identity = AgentIdentity()
ctx = identity.detect_repo_context()
print(f"REPO_OWNER={ctx.owner}")
print(f"REPO_NAME={ctx.repo_name}")
print(f"REPO_SLUG={ctx.full_slug}")

# 2. 召唤格式生成
mention = identity.build_mention("CodeBuddy", ctx.full_slug)
print(f"MENTION_CODEBUDDY={mention}")
mention2 = identity.build_mention("仓库处理专员", ctx.full_slug)
print(f"MENTION_HANDLER={mention2}")

# 3. 同仓库/跨仓库策略
strategy = identity.decide_mention_strategy(ctx.full_slug)
print(f"STRATEGY={strategy}")

# 4. 召唤优先级链（仓库处理专员 → CodeBuddy）
advice = identity.get_review_operational_advice()
print(f"ADVICE_STRING={advice}")

# 5. CodeBuddy 召唤
cb_mention = identity.get_codebuddy_mention()
print(f"CB_MENTION={cb_mention}")

# 6. 处理专员召唤
handler_mention = identity.get_handler_mention()
print(f"HANDLER_MENTION={handler_mention}")
PYEOF
)

# 1. 仓库探测
if echo "$out" | grep -q "REPO_OWNER=" && echo "$out" | grep -q "REPO_NAME=" && echo "$out" | grep -q "REPO_SLUG="; then
  report "仓库上下文探测成功（owner/repo/slug）" 0
else
  report "仓库上下文探测成功（owner/repo/slug）" 1
fi

# 2. 召唤格式
if echo "$out" | grep -q "MENTION_CODEBUDDY=@.*(CodeBuddy)"; then
  report "CodeBuddy 召唤格式正确" 0
else
  report "CodeBuddy 召唤格式正确" 1
fi

# 3. 处理专员召唤格式
if echo "$out" | grep -q "MENTION_HANDLER=@.*(仓库处理专员)"; then
  report "仓库处理专员召唤格式正确" 0
else
  report "仓库处理专员召唤格式正确" 1
fi

# 4. 召唤优先级链
if echo "$out" | grep -q "ADVICE_STRING=.*仓库处理专员"; then
  report "召唤优先级链优先仓库处理专员" 0
else
  report "召唤优先级链优先仓库处理专员" 1
fi

# 5. CodeBuddy 召唤可用
if echo "$out" | grep -q "CB_MENTION=@.*(CodeBuddy)"; then
  report "CodeBuddy 完整召唤格式可用" 0
else
  report "CodeBuddy 完整召唤格式可用" 1
fi

# 6. 处理专员召唤可用
if echo "$out" | grep -q "HANDLER_MENTION=@.*(仓库处理专员)"; then
  report "仓库处理专员完整召唤格式可用" 0
else
  report "仓库处理专员完整召唤格式可用" 1
fi

echo ""
echo "【Agent 身份模块验收】$pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then exit 1; fi
echo "🟢 Agent 身份自适应功能模块验收通过"
exit 0

#!/usr/bin/env bash
# ============================================================
# 通用 Agent 仓库身份解析测试信号灯
# 说明: 验证「自适应 @ 提及」模块（agent_identity_resolver.py）——
#       同仓库不重复适配，跨仓库按工作仓库动态重定向到有权限的角色，
#       不写死仓库/组织名、角色可参数化，供所有 Agent 跨仓库协作复用。
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

echo "== 1. 通用身份解析模块自测（agent_identity_resolver.py demo）=="
out=$($PY agent_identity_resolver.py 2>&1)

# 1. 自测通过
if echo "$out" | grep -q "身份解析模块自测通过"; then
  report "模块 demo 自测通过" 0
else
  report "模块 demo 自测通过" 1
fi

# 2. 同仓库触发不判跨仓库
if echo "$out" | grep -q "是否跨仓库: False" \
   && echo "$out" | grep -q "场景 A"; then
  report "同仓库触发不判为跨仓库（无需重复适配）" 0
else
  report "同仓库触发不判为跨仓库（无需重复适配）" 1
fi

# 3. 跨仓库触发自动重定向到工作仓库
if echo "$out" | grep -q "@dongdongxiaozu/other-game-repo(CodeBuddy)"; then
  report "跨仓库触发重定向到工作仓库 CodeBuddy" 0
else
  report "跨仓库触发重定向到工作仓库 CodeBuddy" 1
fi

# 4. 跨组织跨仓库也重定向
if echo "$out" | grep -q "@bob/unrelated-repo(代码审查员)"; then
  report "跨组织跨仓库也重定向到工作仓库角色" 0
else
  report "跨组织跨仓库也重定向到工作仓库角色" 1
fi

# 5. 角色参数化（多个角色通用）
if echo "$out" | grep -q "@bob/unrelated-repo(代码审查员)" \
   && echo "$out" | grep -q "@bob/unrelated-repo(游戏向经理)"; then
  report "角色参数化（代码审查员/游戏向经理 通用）" 0
else
  report "角色参数化（代码审查员/游戏向经理 通用）" 1
fi

# 6. 环境变量推导兜底（核心逻辑读 env，不写死仓库/组织名）
#    核心应依赖 CNB_NPC_SLUG / CNB_EVENT_URL 动态推导，而非硬编码固定值。
if grep -q "CNB_NPC_SLUG" agent_identity_resolver.py \
   && grep -q "CNB_EVENT_URL" agent_identity_resolver.py \
   && grep -q "CNB_REPO_NAME" agent_identity_resolver.py; then
  report "核心逻辑从环境变量动态推导仓库（不写死组织/仓库名）" 0
else
  report "核心逻辑从环境变量动态推导仓库（不写死组织/仓库名）" 1
fi

# 7. 场景 E 环境变量推导兜底存在
if echo "$out" | grep -q "从环境变量推导"; then
  report "环境变量推导兜底存在" 0
else
  report "环境变量推导兜底存在" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 通用身份解析模块通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 通用身份解析模块存在阻塞项"
  exit 1
fi

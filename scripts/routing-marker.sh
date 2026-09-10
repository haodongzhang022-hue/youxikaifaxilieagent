#!/usr/bin/env bash
# ============================================================
# 路由决策·部门派发（统一入口 · 防止触发来源漂移）
# 说明: issue.open 与 pull_request.merged 两条流水线复用本脚本，
#       避免同一逻辑在两处 stage 内联复制导致「改一处漏一处」。
#
# 【真实故障修复·环境态污染】Issue #133 收尾时发现：
#   `issue.comment@npc` 事件下，平台注入的 CNB_ISSUE_TITLE/DESCRIPTION 仍是
#   **Issue 原始正文**（含"美术线/测试线/项目管理/运营线"等历史链路词），
#   route_from_env 会把它当"本轮工作内容"做语义匹配 → 语义误触发
#   （出现"程序线 美术线 测试线 项目管理"这类幻影部门）。
#   修复：由本脚本定位**权威触发内容**（CNB_COMMENT_BODY / CNB_NPC_TRIGGER_CONTENT），
#   显式以 CNB_ROUTING_CONTENT 传给 routing.py，并同时显式置空
#   CNB_PULL_REQUEST_TITLE/DESCRIPTION 防止 PR 残留污染；routing.py 侧
#   同步支持 CNB_ROUTING_EVENT / CNB_ROUTING_CONTENT 覆盖（见 route_from_env）。
# ============================================================
set -euo pipefail

MARKER="${CNB_BUILD_WORKSPACE:-.}/.routing_active.txt"
EVENT="${CNB_EVENT:-}"
CONTENT=""

# ① 评论触发（issue.comment@npc / pull_request.comment@npc）：
#    权威内容 = 本次评论正文，**不是** Issue/PR 历史正文。
case "$EVENT" in
  *comment*)
    CONTENT="${CNB_COMMENT_BODY:-${CNB_NPC_TRIGGER_CONTENT:-}}"
    ;;
esac

# ② 未取得评论内容时，回退到事件对应正文（保持既有行为）
if [ -z "$CONTENT" ]; then
  case "$EVENT" in
    *comment*) CONTENT="${CNB_NPC_TRIGGER_CONTENT:-}" ;;
    *pull_request*|*merge*) CONTENT="${CNB_PULL_REQUEST_DESCRIPTION:-${CNB_ISSUE_DESCRIPTION:-}}" ;;
    *issue*) CONTENT="${CNB_ISSUE_DESCRIPTION:-}" ;;
    *) CONTENT="${CNB_ISSUE_DESCRIPTION:-${CNB_PULL_REQUEST_DESCRIPTION:-}}" ;;
  esac
fi

# ③ 显式传递给 routing.py（覆盖环境态），并清空 PR 残留防污染
export CNB_ROUTING_EVENT="$EVENT"
export CNB_ROUTING_CONTENT="$CONTENT"
export CNB_PULL_REQUEST_TITLE=""
export CNB_PULL_REQUEST_DESCRIPTION=""

echo "[routing] event=${EVENT}"
echo "[routing] content=$(printf '%s' "$CONTENT" | head -c 160)"

python3 game-studio-agents/config/routing.py marker "$MARKER"
cat "$MARKER"

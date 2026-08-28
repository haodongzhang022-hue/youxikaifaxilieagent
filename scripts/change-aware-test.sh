#!/usr/bin/env bash
# ============================================================
# 变更范围感知测试选择器（Change-Aware Test Selector）
# ============================================================
# 作用：根据本次 git 变更的文件范围，只运行受影响的测试脚本，
#       避免全量跑 31 个独立测试 + 汇总脚本造成 CPU 浪费。
#
# 用法：
#   bash scripts/change-aware-test.sh                 # 自动检测变更（PR/push 均适用）
#   bash scripts/change-aware-test.sh --all           # 强制全量跑
#   bash scripts/change-aware-test.sh --dry-run       # 只打印将运行的测试，不实际执行
#   bash scripts/change-aware-test.sh --dry-run --all # 只打印全量测试清单
#
# 环境变量：
#   CNB_PULL_REQUEST_TARGET_SHA   PR 目标分支 SHA（CNB 内置变量，PR 事件）
#   CNB_COMMIT                    本次提交 SHA（CNB 内置变量）
#
# 核心逻辑：调用 game-studio-agents/hybrid/selector.py 的 IncrementalSelector，
#   基于 TestRegistry（registry.json）做「git diff → 受影响测试」映射 + 依赖传播。
# ============================================================
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=false
FORCE_ALL=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --all) FORCE_ALL=true ;;
  esac
done

# ------------------------------------------------------------
# 1. 确定变更范围（git diff 基础）
# ------------------------------------------------------------
BASE=""
if [ "$FORCE_ALL" = "true" ]; then
  BASE="__ALL__"
elif [ -n "${CNB_PULL_REQUEST_TARGET_SHA:-}" ]; then
  # PR 事件：对比目标分支 SHA 与当前 HEAD
  if git rev-parse --verify "$CNB_PULL_REQUEST_TARGET_SHA" >/dev/null 2>&1; then
    BASE="$CNB_PULL_REQUEST_TARGET_SHA"
  fi
elif [ -n "${CNB_COMMIT:-}" ]; then
  # push 事件：对比上一个 commit
  if git rev-parse --verify "${CNB_COMMIT}~1" >/dev/null 2>&1; then
    BASE="${CNB_COMMIT}~1"
  fi
else
  # 本地开发：对比 main
  if git rev-parse --verify main >/dev/null 2>&1; then
    BASE="main"
  fi
fi

# 传给 Python selector（它内部处理 git diff 与工作区变更）
export CHANGE_AWARE_BASE="${BASE:-__ALL__}"

echo "==== [change-aware] 变更范围感知测试选择 ===="
if [ "$BASE" = "__ALL__" ]; then
  echo "  模式: 全量（无法确定变更范围或强制 --all）"
else
  echo "  变更基线: $BASE"
fi

# ------------------------------------------------------------
# 2. 调用 Python selector 计算受影响测试清单
# ------------------------------------------------------------
SELECTED_TESTS=""
if [ "$BASE" = "__ALL__" ]; then
  # 全量模式：返回全部已注册测试
  SELECTED_TESTS=$(python3 - <<'PY'
import sys
sys.path.insert(0, "game-studio-agents")
from hybrid.selector import IncrementalSelector
s = IncrementalSelector(root_dir=".")
print("\n".join(s.full_suite()))
PY
)
else
  SELECTED_TESTS=$(python3 - <<PY
import sys, os
sys.path.insert(0, "game-studio-agents")
from hybrid.selector import IncrementalSelector
s = IncrementalSelector(root_dir=".")
base = os.environ.get("CHANGE_AWARE_BASE", "HEAD~1")
tests = []
try:
    if base != "__ALL__":
        tests = s.incremental(base=base, head="HEAD")
except Exception:
    tests = []
if not tests:
    # base 不可解析 / 无提交差异 → 回退工作区未提交变更检测
    try:
        tests = s.incremental_workdir()
    except Exception:
        tests = []
if not tests:
    # 仍为空（首次推送 / 新分支）→ 全量兜底
    tests = s.full_suite()
print("\n".join(tests))
PY
)
fi

SELECTED_TESTS="$(echo "$SELECTED_TESTS" | grep -v '^$')"

echo "  受影响测试数: $(echo "$SELECTED_TESTS" | grep -c . )"
echo "  测试清单:"
echo "$SELECTED_TESTS" | sed 's/^/    /'

if [ "$DRY_RUN" = "true" ]; then
  echo ""
  echo "[change-aware] --dry-run 模式，仅打印不执行。"
  exit 0
fi

# ------------------------------------------------------------
# 3. 依次运行选中的测试脚本
# ------------------------------------------------------------
fail=0
for t in $SELECTED_TESTS; do
  # 去除可能存在的 game-studio-agents/ 前缀，统一从仓库根执行
  script="game-studio-agents/tests/$t"
  echo ""
  echo "---- 运行: $script ----"
  if [ -f "$script" ]; then
    if bash "$script"; then
      echo "  ✅ $t 通过"
    else
      echo "  ❌ $t 失败"
      fail=$((fail+1))
    fi
  else
    echo "  ⚠️  脚本不存在，跳过: $t"
  fi
done

echo ""
echo "==== [change-aware] 完成 ===="
if [ "$fail" -gt 0 ]; then
  echo "  🔴 $fail 个测试失败"
  exit 1
else
  echo "  🟢 全部通过"
  exit 0
fi

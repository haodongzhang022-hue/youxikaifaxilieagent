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
# 尝试增量选择
try:
    if base != "__ALL__":
        tests = s.incremental(base=base, head="HEAD")
except Exception:
    tests = []
# 增量返回空：检查变更范围，区分「仅非代码文件变更」与「首次推送/新分支」
if not tests:
    changed = []
    try:
        changed = s.changed_files(base=base, head="HEAD")
    except Exception:
        changed = []
    # git diff base..head 为空但工作区有变更 → 补充检查工作区
    if not changed:
        try:
            changed = s.changed_files_workdir()
        except Exception:
            changed = []
    # 判断变更文件中是否存在实际代码
    non_code_exts = ('.md', '.sh', '.yml', '.yaml', '.json', '.txt', '.cfg',
                     '.ini', '.toml', '.lock', '.gitignore', '.routing_active.txt')
    has_code_change = False
    for f in changed:
        low = f.lower()
        if not any(low.endswith(ext) for ext in non_code_exts):
            has_code_change = True
            break
    if not has_code_change:
        if changed:
            # 仅文档/配置/脚本变更，无实际代码变更 → 跳过测试，退出 0
            print("__SKIP_NO_CODE_CHANGE__")
            print("__CHANGED__=" + ",".join(changed[:20]))
            sys.exit(0)
        else:
            # 无任何变更文件（base==head 且无工作区改动）→ 视为无变更，跳过
            print("__SKIP_NO_CODE_CHANGE__")
            print("__CHANGED__=" + base + "..HEAD 无差异")
            sys.exit(0)
if not tests:
    # 有代码变更但 registry 未覆盖到 → 全量兜底
    tests = s.full_suite()
print("\n".join(tests))
PY
)
fi

# 检测跳过标记
if echo "$SELECTED_TESTS" | grep -q "__SKIP_NO_CODE_CHANGE__"; then
  echo "  [skip] 本次变更仅涉及文档/配置/脚本等非代码文件，跳过测试"
  CHANGED_LIST=$(echo "$SELECTED_TESTS" | grep "^__CHANGED__=" | cut -d= -f2)
  echo "  变更文件: $CHANGED_LIST"
  echo "==== [change-aware] 跳过，无代码变更 ===="
  exit 0
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

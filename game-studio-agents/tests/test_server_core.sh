#!/usr/bin/env bash
# ============================================================
# 多端共享服务端核心测试
# 说明: 验证 server/ 目录下的统一协议/服务端权威/定点数结算/经济账本
# 用法: bash game-studio-agents/tests/test_server_core.sh
# 退出码: 0 全部通过 / 1 存在失败
# ============================================================
set -u
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

echo "==== [test_server_core] 服务端核心测试 ===="

# 运行 Python unittest
if [ -f server/tests/test_server.py ]; then
  if python3 -m pytest server/tests/test_server.py -v 2>&1; then
    echo "  ✅ server/tests/test_server.py 全部通过"
    exit 0
  else
    # pytest 可能不存在，回退到 unittest
    if python3 -m unittest server.tests.test_server -v 2>&1; then
      echo "  ✅ server/tests/test_server.py unittest 全部通过"
      exit 0
    else
      echo "  ❌ server/tests/test_server.py 测试失败"
      exit 1
    fi
  fi
else
  echo "  ❌ server/tests/test_server.py 不存在"
  exit 1
fi

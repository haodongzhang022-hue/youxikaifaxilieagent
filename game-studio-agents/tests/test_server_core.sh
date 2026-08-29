#!/usr/bin/env bash
# ============================================================
# 多端共享服务端核心测试
# 说明: 验证 server/ 目录下的统一协议/服务端权威/定点数结算/经济账本
#       + 坑点经验库巡检脚本（服务端安全漏洞回归）
# 用法: bash game-studio-agents/tests/test_server_core.sh
# 退出码: 0 全部通过 / 1 存在失败
# ============================================================
set -u
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

echo "==== [test_server_core] 服务端核心测试 ===="

# 运行 test_server.py（核心协议/服务端权威/经济账本）
if [ -f server/tests/test_server.py ]; then
  if python3 -m unittest server.tests.test_server -v 2>&1 | tail -5; then
    echo "  ✅ server/tests/test_server.py 全部通过"
  else
    echo "  ❌ server/tests/test_server.py 测试失败"
    exit 1
  fi
else
  echo "  ❌ server/tests/test_server.py 不存在"
  exit 1
fi

# 运行 test_pitfalls_scan.py（坑点经验库巡检 + 服务端安全回归）
if [ -f server/tests/test_pitfalls_scan.py ]; then
  if python3 server/tests/test_pitfalls_scan.py -v 2>&1 | tail -5; then
    echo "  ✅ server/tests/test_pitfalls_scan.py 全部通过"
  else
    echo "  ❌ server/tests/test_pitfalls_scan.py 测试失败"
    exit 1
  fi
else
  echo "  ❌ server/tests/test_pitfalls_scan.py 不存在"
  exit 1
fi

echo "==== [test_server_core] 全部通过 ===="
exit 0

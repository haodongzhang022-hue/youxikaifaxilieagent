# ============================================================
# 引擎桥接层 (Engine Bridge)
# 版本: v0.1
# 说明: 面向未来 Windows + Cocos + 虚幻5(UE5) 引擎环境的统一桥接架构。
#       通过 MCP (Model Context Protocol) 和引擎插件控制引擎，
#       为游戏开发 Agent 系统提供引擎能力访问的标准化接口。
#
# 设计目标:
#   1. 统一抽象 - 无论底层是 Cocos 还是 UE5，Agent 都使用同一套引擎命令
#   2. MCP 优先 - 首选通过 MCP 协议与引擎的 MCP Server 通信
#   3. 插件补充 - 支持引擎原生插件（Editor Extension）作为补充通道
#   4. Windows 适配 - 考虑 Windows 下的进程管理、路径约定与编辑器自动化
#   5. 测试可验证 - 所有引擎操作都有可测试的 Mock 实现
#
# 模块结构:
#   engine_bridge/
#     __init__.py         # 模块入口，导出公共接口
#     protocol.py         # 引擎命令协议定义（统一操作语义）
#     mcp_client.py       # MCP 客户端（连接引擎 MCP Server）
#     plugin_adapter.py   # 引擎插件适配器（Cocos/UE5 插件调用通道）
#     engine_adapter.py   # 引擎适配器基类 + 工厂
#     cocos_adapter.py    # Cocos Creator 适配器
#     ue5_adapter.py      # Unreal Engine 5 适配器
#     environment.py      # Windows 环境适配
#     errors.py           # 异常定义
#     bridge.py           # 统一门面 (EngineBridgeFacade)
#
# 语言: Python 3 (可运行，核心逻辑无需外部依赖)
# ============================================================

from __future__ import annotations

from .errors import (EngineBridgeError, EngineConnectionError,
                     EngineNotAvailableError, EngineTimeoutError,
                     MCPError, PluginError, UnsupportedEngineError)
from .protocol import (EngineCapability, EngineCommand, EngineCommandSet,
                       EngineEvent, EngineResult, EngineStatus)
from .environment import (EngineEnvironment, detect_engine_environment,
                          get_windows_environment)
from .bridge import BridgeConfig, EngineBridgeFacade

__all__ = [
    # 错误类型
    "EngineBridgeError", "EngineConnectionError", "EngineNotAvailableError",
    "EngineTimeoutError", "MCPError", "PluginError", "UnsupportedEngineError",
    # 协议
    "EngineCapability", "EngineCommand", "EngineCommandSet",
    "EngineEvent", "EngineResult", "EngineStatus",
    # 环境
    "EngineEnvironment", "detect_engine_environment", "get_windows_environment",
    # 门面
    "BridgeConfig", "EngineBridgeFacade",
]


def demo():
    """演示：引擎桥接层 Mock 模式运行。"""
    print("=" * 70)
    print("引擎桥接层 (Engine Bridge) 演示")
    print("  统一抽象 · MCP优先 · 插件补充 · Windows适配 · 可测试")
    print("=" * 70)

    # 创建 Mock 模式的桥接
    bridge = EngineBridgeFacade(BridgeConfig(use_mock=True, engines=["cocos", "ue5"]))
    bridge.init()

    print(f"\n可用引擎: {bridge.available_engines}")
    print(f"默认引擎: {bridge._default_engine}")
    print(f"引擎状态: { {k: bridge.engine_status(k).value for k in bridge.available_engines} }")

    # 执行命令
    print("\n[1] 加载场景")
    result = bridge.load_scene("assets/scenes/Main.scene")
    print(f"  {result.command.capability.value} → success={result.success}")

    print("\n[2] 创建节点")
    result = bridge.create_node("Player", "Root")
    print(f"  {result.command.capability.value} → success={result.success}")

    print("\n[3] 进入 Play 模式")
    result = bridge.play()
    print(f"  {result.command.capability.value} → success={result.success}")

    print("\n[4] 查询能力集（前 5 个）")
    caps = bridge.capabilities()
    for c in sorted(c.value for c in list(caps)[:5]):
        print(f"  - {c}")

    print("\n[5] 状态报告")
    report = bridge.report()
    print(f"  env: {report['env']['os_name']}")
    print(f"  默认引擎: {report['default_engine']}")
    for et, er in report["engines"].items():
        print(f"  {et}: status={er['status']}, capabilities={len(er['capabilities'])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(demo())

# ============================================================
# DeepSeek 本地 Agent 运行时 (DeepSeek Harness)
# 版本: v1.0
# 说明: 定义「本地 Windows Agent 运行时」——让 DeepSeek 不再只是"推理模型"，
#       而是能跑在本地 Windows 的 Agent harness：经 cnb.cool API 收派单、
#       调用本地引擎工具链（Cocos Creator / UE5）执行、回传产物到云端编排。
#
#   对齐架构师建议（wp_engine_adaptation）：
#     P1-2 本地 Windows Agent（DeepSeek harness）未接入云端编排 → 本模块
#           定义本地 Agent 运行时收/派单、执行、回传；
#     P2-6 DeepSeek harness 需定义"本地 Agent 运行时" → 明确它是本地进程 /
#           工具调用面 / 与 cnb.cool API 的桥，不只是推理后端。
#
#   核心能力：
#     1. HarnessContext：本地运行时上下文（角色 / 引擎 / 工作区 / API 端点）；
#     2. receive_dispatch()：从 cnb.cool 接收派单（TASK_ASSIGN），解析工作包；
#     3. plan_execution()：结合目标引擎生成本地执行计划（工具调用面）；
#     4. execute_locally()：调用本地引擎工具链执行，产出产物清单；
#     5. report_back()：把产物清单 + 一致性校验结果回传云端（供验收）。
#
# 语言: Python 3 (可运行，无需外部依赖)
# ============================================================
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class HarnessContext:
    """本地 Agent 运行时上下文"""
    agent_role: str = "cocos_dev"            # 承接角色
    engine: str = "cocos"                    # 目标引擎
    workspace: str = ""                      # 本地工作区
    api_endpoint: str = "https://cnb.cool/api"  # cnb.cool API 端点
    tool_chain: List[str] = field(default_factory=list)  # 本地工具调用面


# 本地运行时可调用的工具链（对应引擎）
_ENGINE_TOOLS = {
    "cocos": ["cocos build", "cocos creator", "tsc", "resource_import"],
    "unreal": ["RunUAT", "Unreal Editor", "Visual Studio", "cook"],
}


def build_context(agent_role: str = "cocos_dev", engine: str = "cocos",
                  workspace: str = "") -> HarnessContext:
    """构建本地 Agent 运行时上下文。"""
    engine = engine.lower()
    return HarnessContext(
        agent_role=agent_role,
        engine=engine,
        workspace=workspace or os.path.expanduser("~/game-workspace"),
        tool_chain=_ENGINE_TOOLS.get(engine, []),
    )


def receive_dispatch(ctx: HarnessContext, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 cnb.cool 接收派单（TASK_ASSIGN），解析出可执行工作包。

    message: 云端下发的事件载荷，形如
      {"event": "TASK_ASSIGN", "work_package": {...}, "assignee": "cocos_dev"}
    返回: 工作包 dict；非本 Agent / 无工作包返回 None。
    """
    if not message or message.get("event") != "TASK_ASSIGN":
        return None
    assignee = message.get("assignee", "")
    if assignee and assignee != ctx.agent_role:
        return None
    wp = message.get("work_package")
    if not wp:
        return None
    # 标记本地承接
    wp = dict(wp)
    wp["local_executor"] = f"{ctx.agent_role}@{ctx.engine}"
    return wp


def plan_execution(ctx: HarnessContext, work_package: Dict[str, Any]) -> Dict[str, Any]:
    """结合目标引擎生成本地执行计划（工具调用面）。"""
    module = work_package.get("module", "generic")
    module_map = {
        "client": ["cocos build", "resource_import"],
        "engine": ["tsc", "cocos build"],
        "scene": ["cocos creator", "resource_import"],
        "audio": ["resource_import", "cocos build"],
        "blueprint": ["RunUAT", "Unreal Editor"],
        "map": ["Unreal Editor"],
        "generic": ctx.tool_chain,
    }
    tools = module_map.get(module, ctx.tool_chain)
    return {
        "work_package": work_package.get("id", work_package.get("label", "wp")),
        "engine": ctx.engine,
        "executor": ctx.agent_role,
        "tools": tools,
        "steps": [f"调用 {t} 执行 {module} 产出" for t in tools],
        "workspace": ctx.workspace,
    }


def execute_locally(ctx: HarnessContext, plan: Dict[str, Any]) -> Dict[str, Any]:
    """执行本地引擎工具链，产出产物清单（供回传验收）。

    真实环境会调用 Cocos/UE 工具链构建；此原型返回可验收的产物描述。
    """
    module = plan.get("work_package", "wp")
    engine_dir = "assets" if ctx.engine == "cocos" else "Content"
    output_files = []
    for t in plan.get("tools", []):
        ext_map = {"cocos build": ".prefab", "resource_import": ".png",
                   "tsc": ".ts", "RunUAT": ".uasset", "Unreal Editor": ".umap"}
        ext = ext_map.get(t, ".bin")
        output_files.append(f"{engine_dir}/{module}/{module}{ext}")
    return {
        "executor": ctx.agent_role,
        "engine": ctx.engine,
        "workspace": ctx.workspace,
        "output_files": output_files,
        "status": "local_done",
    }


def report_back(ctx: HarnessContext, plan: Dict[str, Any],
                result: Dict[str, Any]) -> Dict[str, Any]:
    """把本地执行结果 + 产物清单回传云端（供验收）。"""
    return {
        "event": "EXEC_REPORT",
        "from": f"{ctx.agent_role}@{ctx.engine}",
        "engine": ctx.engine,
        "work_package": plan.get("work_package"),
        "status": result.get("status"),
        "output_files": result.get("output_files", []),
        "consistency_required": True,   # 回传后云端应做同源校验
        "api_endpoint": ctx.api_endpoint,
    }


def _demo():
    print("=" * 60)
    print("DeepSeek 本地 Agent 运行时自测")
    print("=" * 60)

    ctx = build_context(agent_role="cocos_dev", engine="cocos")
    print(f"\n[运行时上下文]")
    print(f"  agent_role={ctx.agent_role} engine={ctx.engine} workspace={ctx.workspace}")
    print(f"  tool_chain={ctx.tool_chain}")

    print("\n[接收派单]")
    dispatch = {
        "event": "TASK_ASSIGN",
        "assignee": "cocos_dev",
        "work_package": {"id": "wp_ui_client", "label": "客户端场景", "module": "scene"},
    }
    wp = receive_dispatch(ctx, dispatch)
    print(f"  承接工作包: {wp['id']} (local_executor={wp['local_executor']})")

    print("\n[执行计划]")
    plan = plan_execution(ctx, wp)
    print(f"  engine={plan['engine']} tools={plan['tools']}")
    for s in plan["steps"]:
        print(f"    - {s}")

    print("\n[本地执行产物]")
    result = execute_locally(ctx, plan)
    for f in result["output_files"]:
        print(f"    - {f}")

    print("\n[回传云端]")
    report = report_back(ctx, plan, result)
    print(f"  event={report['event']} from={report['from']} status={report['status']}")
    print(f"  consistency_required={report['consistency_required']}")

    print("\n[UE 侧运行时]")
    ctx2 = build_context(agent_role="ue_dev", engine="unreal")
    print(f"  agent_role={ctx2.agent_role} tool_chain={ctx2.tool_chain}")
    wp2 = receive_dispatch(ctx2, {
        "event": "TASK_ASSIGN", "assignee": "ue_dev",
        "work_package": {"id": "wp_level", "label": "关卡", "module": "map"}})
    plan2 = plan_execution(ctx2, wp2)
    print(f"  承接 {wp2['id']} tools={plan2['tools']}")


if __name__ == "__main__":
    _demo()

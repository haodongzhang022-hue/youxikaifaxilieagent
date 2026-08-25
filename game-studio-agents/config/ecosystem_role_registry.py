# ============================================================
# 生态角色注册与派发桥梁 (Ecosystem Role Registry)
# 版本: v1.0
# 说明: wp_server / wp_ai_logic（程序线·cto / ai_programmer）的落地产出。
#       把生态角色（玩家圈 / 外部市场圈 / 协作支持圈）从 ecosystem_roles.yaml
#       注册进 `message_bus` + `task_scheduler`，使它们成为**可派发 Agent**，
#       真正进入部门流水线，而非仅停留在定义文件 / 独立原型。
#
# 三项能力（对照 Issue 验收标准「生态角色注册为可派发 Agent，接入
# task_scheduler 派发并 publish 到 message_bus」）：
#   1. load：从 ecosystem_roles.yaml 解析三大生态圈角色；
#   2. register：把生态角色注册进 message_bus（可收发消息的可寻址角色）；
#   3. dispatch：经 task_scheduler 把工作包/任务派发给生态角色，publish 到总线。
#
# 语言: Python 3 (可运行)
# 依赖: message_bus.py / task_scheduler.py / ecosystem_roles.yaml（同目录）
# ============================================================
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from message_bus import Message, MessageBus, build_task_assign
from task_scheduler import Scheduler, Task, TaskQueue

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


# ============================================================
# 一、生态角色数据加载
# ============================================================

# 生态圈 → ecosystem_roles.yaml 中的角色段键
CIRCLE_SECTION = {
    "collab_support": "collab_support_roles",
    "players":        "player_roles",
    "market":         "market_roles",
}

# 生态圈中文名（用于可读日志 / 报告）
CIRCLE_NAME = {
    "collab_support": "协作支持圈",
    "players":        "玩家圈",
    "market":         "外部市场圈",
}


def load_ecosystem_roles(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """从 ecosystem_roles.yaml 解析三大生态圈角色，返回角色定义列表。

    每个角色附带其所属圈层（circle）与类型（simulation_agent / 服务岗等），
    供后续注册 / 装配 / 派发使用。
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "ecosystem_roles.yaml")
    if yaml is None or not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:  # noqa: BLE001
        print(f"[生态角色注册] 加载失败({exc})")
        return []

    roles: List[Dict[str, Any]] = []
    for circle, section in CIRCLE_SECTION.items():
        for r in (data.get(section) or []):
            role = dict(r)
            role["circle"] = role.get("circle") or circle
            roles.append(role)
    return roles


# ============================================================
# 二、生态角色注册到 MessageBus
# ============================================================

class EcosystemRoleRegistry:
    """把生态角色注册进 message_bus，使其成为可寻址、可派发 Agent。

    核心：
      - register 把所有生态角色 role_id 注册到总线（可收发消息）；
      - 对协作支持圈等有可执行 Agent 的角色，可挂接 handler 使其真正承接
        派发的 TASK_ASSIGN（默认登记，实际执行逻辑由调用方注入）；
      - register_scheduler 让调度器能把任务派发给这些生态角色。
    """

    def __init__(self, bus: Optional[MessageBus] = None,
                 roles: Optional[List[Dict[str, Any]]] = None):
        self.bus = bus or MessageBus()
        self.roles: Dict[str, Dict[str, Any]] = {}
        self.scheduler: Scheduler = Scheduler(queue=TaskQueue(), bus=self.bus)
        self._handlers: Dict[str, Any] = {}
        self._loaded_path: Optional[str] = None

    def load(self, path: Optional[str] = None) -> "EcosystemRoleRegistry":
        """加载生态角色定义并登记到本注册表。"""
        self._loaded_path = path
        for r in load_ecosystem_roles(path):
            self.roles[r["role_id"]] = r
        return self

    def register(self) -> List[str]:
        """把已加载的生态角色注册到 message_bus（可寻址/可派发）。"""
        registered = []
        for role_id in self.roles:
            self.bus.register(role_id)
            registered.append(role_id)
        return registered

    def register_scheduler(self, scheduler: Scheduler) -> Scheduler:
        """把生态角色接入外部 task_scheduler，使其可被派发。

        传入的调度器与本地调度器共享同一总线，生态角色作为可派发 owner
        出现在调度队列中，任务就绪时经总线 publish TASK_ASSIGN。
        """
        self.scheduler = scheduler
        return scheduler

    def dispatch(self, task: Task) -> Task:
        """把一个任务派发给生态角色（owner 为生态角色 role_id）。

        经 task_scheduler.enqueue 入队并 publish TASK_ASSIGN 到 message_bus，
        使生态角色真正进入部门流水线派发。
        """
        if task.owner not in self.roles:
            # 显式告警：任务 owner 不是已注册生态角色，避免静默派发给未知角色
            print(f"[生态角色注册] 派发目标 {task.owner} 未注册为生态角色，仍尝试派发")
        self.scheduler.enqueue(task)
        return task

    # ---------- 查询 ----------
    def by_circle(self, circle: str) -> List[Dict[str, Any]]:
        """按圈层返回生态角色列表。"""
        return [r for r in self.roles.values() if r.get("circle") == circle]

    def summary(self) -> Dict[str, Any]:
        """注册情况汇总。"""
        return {
            "total": len(self.roles),
            "by_circle": {
                cname: len([r for r in self.roles.values()
                            if r.get("circle") == c])
                for c, cname in CIRCLE_NAME.items()
            },
            "registered_to_bus": sorted(self.bus.roles),
            "dispatchable": sorted(self.roles.keys()),
        }

    # ---------- 便捷装配：把生态角色作为部门可派发 Agent 并入 ----------
    def assemble_into_departments(self, manager_register_fn,
                                  dept_key_by_name: Dict[str, str]) -> List[str]:
        """把生态角色并入经理的部门能力表，作为可派发 Agent 装配来源。

        manager_register_fn: 类似 GameProducerAgent.register_instantiated_team 的
            回调，把生态角色（含 department 圈层 + role_id）注册为可派发来源。
        dept_key_by_name: 圈层中文名 → 部门键映射（如 {"协作支持圈":"support"}）。
        """
        # 生态角色没有 DEPARTMENT 字段，用 circle 圈层作为其"部门归属"，
        # 交由经理按圈层登记（跨部门服务岗 / 外部 / 玩家圈）。
        payload = []
        for role_id, r in self.roles.items():
            circle = r.get("circle", "")
            dept_name = CIRCLE_NAME.get(circle, circle)
            payload.append({
                "role_id": role_id,
                "department": dept_name,
                "name": r.get("name", role_id),
            })
        if payload:
            manager_register_fn(payload)
        return [p["role_id"] for p in payload]


# ============================================================
# 三、演示
# ============================================================

def demo():
    print("=" * 70)
    print("生态角色注册与派发桥梁（wp_server / wp_ai_logic）")
    print("  把玩家圈 / 外部市场圈 / 协作支持圈注册进 task_scheduler + message_bus")
    print("=" * 70)

    registry = EcosystemRoleRegistry().load()
    registered = registry.register()

    print(f"\n[1] 生态角色注册到 message_bus（共 {len(registered)} 个）")
    for circle, cname in CIRCLE_NAME.items():
        rids = [r["role_id"] for r in registry.by_circle(circle)]
        print(f"    {cname:<8}: {', '.join(rids)}")

    print("\n[2] 接入 task_scheduler 派发（生态角色作为可派发 owner）")
    # 派发几个生态角色任务：市场预演 / 进度督导 / 玩家反馈
    from task_scheduler import Scheduler
    scheduler = Scheduler(bus=registry.bus)
    registry.register_scheduler(scheduler)

    registry.dispatch(Task(id="eco_publish", name="市场预演", owner="publisher",
                           priority="HIGH"))
    registry.dispatch(Task(id="eco_push", name="催办任务", owner="progress_pusher",
                           priority="NORMAL"))
    registry.dispatch(Task(id="eco_player", name="玩家反馈", owner="core_player",
                           priority="NORMAL"))

    print("    已派发生态角色任务:")
    for tid, t in scheduler.queue.tasks.items():
        print(f"      - {tid:<12} owner={t.owner:<16} state={t.state}")

    # 派发消息已 publish 到 message_bus
    registry.bus.process_all()
    assigns = [m for m in registry.bus.delivered if m.type == "TASK_ASSIGN"]
    print(f"\n[3] 已 publish 到 message_bus 的 TASK_ASSIGN: {len(assigns)} 条")
    for m in assigns:
        print(f"      - {m.content['name']} -> {m.to_role}")

    print("\n[4] 生态角色注册汇总")
    for k, v in registry.summary().items():
        print(f"    {k}: {v}")

    ok = (len(registered) >= 10 and len(assigns) >= 3)
    print(f"\n结果: {'🟢 通过' if ok else '🔴 未通过'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(demo())

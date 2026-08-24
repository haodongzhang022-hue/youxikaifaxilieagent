# ============================================================
# 运行时状态快照提取（Runtime Snapshot）
# 版本: v0.9
# 说明: 从 message_bus / task_scheduler / game_producer_agent 提取
#       运行时状态快照，作为聚合引擎（Aggregator）的数据源。
#       支持两种模式：
#         - attach(existing) : 附加到已运行的 Agent 实例（共享内存引用）
#         - bootstrap()      : 独立拉起一次 demo，生成示范快照（用于演示/测试）
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional

# 让 config 模块可直接 import（与本 api 包同级）
_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")
if _CONFIG_DIR not in sys.path:
    sys.path.insert(0, _CONFIG_DIR)

from message_bus import MessageBus, build_task_assign  # noqa: E402


# ============================================================
# 快照构建
# ============================================================

def build_snapshot(manager=None, bus=None) -> Dict[str, Any]:
    """从 manager / bus 构建统一快照（供聚合器消费）。

    manager: GameProducerAgent 实例（含 work_packages / scheduler / bus）
    bus:     MessageBus 实例
    """
    snap: Dict[str, Any] = {"ts": time.time(), "project": "",
                            "work_packages": [], "tasks": {},
                            "events": [], "bus_stats": {}, "agents": []}

    # --- 项目名 ---
    if manager is not None and manager.work_packages:
        snap["project"] = manager.work_packages[0].get("project", "")

    # --- 工作包 ---
    if manager is not None:
        snap["work_packages"] = [
            {**wp, "project": wp.get("project", snap["project"])}
            for wp in manager.work_packages
        ]
        snap["agents"] = [{
            "id": manager.role_id, "state": manager.state,
            "biz_state": getattr(manager, "biz_state", ""),
            "work_packages": len(manager.work_packages),
            "accepted": getattr(manager, "accepted", []),
            "log_len": len(getattr(manager, "log", [])),
        }]

    # --- 调度任务 ---
    scheduler = getattr(manager, "scheduler", None)
    queue = getattr(scheduler, "queue", None) if scheduler else None
    if queue is not None:
        for tid, task in queue.tasks.items():
            # 从 payload 提取关联的工作包 id（供按工作包反查调度任务）
            wp_id = (task.payload.get("work_package", {}) or {}).get("id", "")
            snap["tasks"][tid] = {
                "id": task.id, "name": task.name, "owner": task.owner,
                "state": task.state, "priority": task.priority,
                "deps": list(task.depends_on), "progress": task.progress,
                "ddl": task.ddl, "history": list(task.history),
                "work_package_id": wp_id,
            }

    # --- 事件流（L3 溯源数据源）---
    bus = bus or getattr(manager, "bus", None)
    if bus is not None:
        delivered = getattr(bus, "delivered", []) or []
        snap["events"] = [_msg_to_raw(m) for m in delivered]
        snap["bus_stats"] = bus.stats()

    return snap


def _msg_to_raw(msg) -> Dict[str, Any]:
    """把 Message 转成 L3 RawEvent。"""
    content = getattr(msg, "content", {}) or {}
    return {
        "id": getattr(msg, "id", ""),
        "type": getattr(msg, "type", ""),
        "actor": getattr(msg, "from_role", ""),
        "target": getattr(msg, "to_role", ""),
        "ts": getattr(msg, "timestamp", 0.0),
        "summary": _summarize_msg(msg),
        "payload": content,
    }


def _summarize_msg(msg) -> str:
    """为消息生成一句话摘要（降熵）。"""
    content = getattr(msg, "content", {}) or {}
    mtype = getattr(msg, "type", "")
    if mtype == "TASK_ASSIGN":
        task_id = content.get("task_id", "")
        inputs = content.get("inputs", {}) or {}
        arch = inputs.get("architecture", {})
        proj = arch.get("project") if isinstance(arch, dict) else None
        return f"派发任务 {task_id}" + (f"（项目: {proj}）" if proj else "")
    if mtype == "DELIVERY":
        return f"交付产出 {content.get('work_package_id', '')}，状态 {content.get('status', '')}"
    if mtype == "NOTIFICATION":
        event = content.get("event", "")
        if event == "rework":
            return f"返工通知: {content.get('work_package_id', '')} 被打回（{content.get('reason','')}）"
        return f"通知: {event}"
    if mtype == "REVIEW_RESULT":
        return f"评审结果: {content.get('verdict', '')}"
    return f"{mtype} 事件"


# ============================================================
# bootstrap：独立拉起示范快照（演示/测试）
# ============================================================

def bootstrap(project: str = "开放世界动作游戏 demo",
              modules: Optional[List[str]] = None) -> Dict[str, Any]:
    """拉起一次完整编排，返回 {manager, bus, snapshot} 三件套。"""
    from game_producer_agent import GameProducerAgent

    modules = modules or ["gameplay", "numeric_model", "client", "server",
                          "art_direction", "ui_ux", "testing", "release"]
    bus = MessageBus()
    manager = GameProducerAgent(bus=bus)
    manager.boot()

    architecture = {"project": project, "modules": modules}
    msg = build_task_assign("architect", manager.role_id, "orch_001",
                            {"architecture": architecture})
    bus.publish(msg)
    bus.process_all()

    snap = build_snapshot(manager=manager, bus=bus)
    return {"manager": manager, "bus": bus, "snapshot": snap}

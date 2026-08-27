# ============================================================
# 通用任务队列与事件驱动调度器 (TaskQueue / Scheduler)
# 版本: v0.3
# 说明: 为所有 Agent 提供统一的任务管理基础设施：
#       - 任务队列（支持优先级 / DDL / 状态流转）
#       - 依赖调度（任务完成后自动解锁下游任务）
#       - 事件驱动（任务状态变化发布到 MessageBus）
#       - 负载统计（供零工池 / 进度督导复用）
# 本模块与具体岗位、生态角色完全解耦，任何角色 / 调度器可独立复用。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from message_bus import Message, MessageBus


# ============================================================
# 一、任务状态
# ============================================================

class TaskState(str, Enum):
    TODO = "TODO"               # 待执行
    IN_PROGRESS = "IN_PROGRESS" # 执行中
    BLOCKED = "BLOCKED"         # 阻塞（依赖未满足 / 缺资源）
    DONE = "DONE"               # 已完成
    FAILED = "FAILED"           # 失败


# 优先级权重
PRIORITY_WEIGHT = {"LOW": 0, "NORMAL": 1, "HIGH": 2, "URGENT": 3}


@dataclass
class Task:
    """一个可调度的任务单元"""
    id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    name: str = ""
    owner: str = ""                     # 负责角色 role_id
    priority: str = "NORMAL"            # LOW / NORMAL / HIGH / URGENT
    ddl: Optional[float] = None         # 截止时间戳
    depends_on: List[str] = field(default_factory=list)  # 前置任务 id
    state: str = TaskState.TODO.value
    progress: float = 0.0               # 0~1
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def touch(self, state: Optional[str] = None, note: str = ""):
        self.updated_at = time.time()
        self.history.append({"state": state or self.state, "note": note,
                             "at": self.updated_at})
        if state:
            self.state = state

    @property
    def priority_weight(self) -> int:
        return PRIORITY_WEIGHT.get(self.priority, 1)

    def overdue(self, now: Optional[float] = None) -> float:
        """返回超出 DDL 的天数（未超时为 <=0）"""
        if self.ddl is None:
            return 0.0
        now = now or time.time()
        return max(0.0, (now - self.ddl) / 86400.0)


# ============================================================
# 二、任务队列
# ============================================================

class TaskQueue:
    """带优先级与依赖解析的任务队列"""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.ready_order: List[str] = []     # 就绪任务 id（按优先级排序出队）

    def add(self, task: Task) -> Task:
        self.tasks[task.id] = task
        if self._is_ready(task):
            self._enqueue_ready(task)
        return task

    def _is_ready(self, task: Task) -> bool:
        """任务就绪：前置依赖全部完成"""
        if task.state not in (TaskState.TODO.value, TaskState.BLOCKED.value):
            return False
        return all(self.tasks.get(d, Task()).state == TaskState.DONE.value
                   for d in task.depends_on)

    def _enqueue_ready(self, task: Task):
        if task.id not in self.ready_order:
            self.ready_order.append(task.id)
            self._sort_ready()

    def _sort_ready(self):
        # 优先级权重降序 + DDL 升序（越急越靠前）
        self.ready_order.sort(
            key=lambda tid: (-self.tasks[tid].priority_weight,
                             self.tasks[tid].ddl or float("inf")))

    def next(self) -> Optional[Task]:
        """取出一个就绪任务（出队）"""
        while self.ready_order:
            tid = self.ready_order.pop(0)
            task = self.tasks.get(tid)
            if task and task.state == TaskState.TODO.value:
                task.touch(TaskState.IN_PROGRESS.value, "出队执行")
                return task
        return None

    def complete(self, task_id: str):
        """完成任务：解锁下游依赖"""
        task = self.tasks.get(task_id)
        if not task:
            return
        task.touch(TaskState.DONE.value, "完成")
        # 解锁依赖该任务的下游
        for other in self.tasks.values():
            if task_id in other.depends_on and self._is_ready(other):
                if other.state == TaskState.BLOCKED.value:
                    other.touch(TaskState.TODO.value, "依赖已满足")
                self._enqueue_ready(other)

    def fail(self, task_id: str):
        task = self.tasks.get(task_id)
        if task:
            task.touch(TaskState.FAILED.value, "失败")

    def block(self, task_id: str, reason: str = ""):
        task = self.tasks.get(task_id)
        if task:
            task.touch(TaskState.BLOCKED.value, reason or "阻塞")
            if task_id in self.ready_order:
                self.ready_order.remove(task_id)

    # ---------- 统计 ----------
    def pending_count(self) -> int:
        return len(self.ready_order)

    def stats(self) -> Dict[str, int]:
        from collections import Counter
        return dict(Counter(t.state for t in self.tasks.values()))


# ============================================================
# 三、事件驱动调度器
# ============================================================

class Scheduler:
    """
    事件驱动调度器：把 TaskQueue 与 MessageBus 打通。
    - 任务就绪 → 通过总线发 TASK_ASSIGN 给 owner
    - 任务完成 → 更新队列并解锁下游，同时发布通知
    """

    def __init__(self, queue: Optional[TaskQueue] = None,
                 bus: Optional[MessageBus] = None):
        self.queue = queue or TaskQueue()
        self.bus = bus or MessageBus()
        self._dispatched: set = set()   # 已派发过的任务 id（避免重复派发）
        self._last_assign_msgs: Dict[str, Message] = {}  # task_id -> 最近一次 TASK_ASSIGN 消息

    def enqueue(self, task: Task) -> Task:
        self.queue.add(task)
        self._dispatch_if_ready(task.id)
        return task

    def _dispatch_if_ready(self, task_id: str) -> Optional[Message]:
        """若任务就绪则发布 TASK_ASSIGN 并返回该消息；否则返回 None。"""
        task = self.queue.tasks.get(task_id)
        # 仅当任务为 TODO 且有 owner、且依赖全部满足时才派发 TASK_ASSIGN
        if (task and task.state == TaskState.TODO.value and task.owner
                and task.id not in self._dispatched
                and self.queue._is_ready(task)):
            msg = Message("TASK_ASSIGN", "scheduler", task.owner,
                          {"task_id": task.id, "name": task.name,
                           "payload": task.payload},
                          priority=task.priority)
            self.bus.publish(msg)
            self._dispatched.add(task.id)
            self._last_assign_msgs[task.id] = msg
            return msg
        return None

    def last_assign(self, task_id: str) -> Optional[Message]:
        """获取某任务最近一次 TASK_ASSIGN 消息（无则 None）。"""
        return self._last_assign_msgs.get(task_id)

    def clear_dispatched(self, task_id: str):
        """清除某任务的派发记录，允许重新派发。"""
        self._dispatched.discard(task_id)
        self._last_assign_msgs.pop(task_id, None)

    def on_complete(self, task_id: str, from_role: str):
        """收到执行完成信号，更新队列并解锁下游"""
        self.queue.complete(task_id)
        self.clear_dispatched(task_id)  # 任务完成后允许同 id 重新派发
        # 解锁的下游任务重新派发（_dispatch_if_ready 内部已用 _dispatched 防重复）
        for other in self.queue.tasks.values():
            if task_id in other.depends_on and other.state == TaskState.TODO.value:
                self._dispatch_if_ready(other.id)
        # 发布完成通知
        self.bus.publish(Message(
            "NOTIFICATION", from_role, "*",
            {"event": "task_done", "task_id": task_id},
            mode="TOPIC", topic="task_events"))

    def on_fail(self, task_id: str, from_role: str, reason: str = ""):
        self.queue.fail(task_id)
        self.clear_dispatched(task_id)  # 失败后允许同 task_id 重新派发（返工）
        self.bus.publish(Message(
            "NOTIFICATION", from_role, "*",
            {"event": "task_failed", "task_id": task_id, "reason": reason},
            mode="TOPIC", topic="task_events"))

    def block(self, task_id: str, reason: str = ""):
        """阻塞一个任务并清理其派发记录，允许后续重新派发。"""
        self.queue.block(task_id, reason)
        self.clear_dispatched(task_id)


# ============================================================
# 四、演示
# ============================================================

def demo():
    print("=" * 60)
    print("任务队列与事件驱动调度器演示")
    print("=" * 60)

    bus = MessageBus()
    sched = Scheduler(bus=bus)
    events: List[Message] = []
    bus.subscribe("watcher", handler=lambda m: events.append(m), topic="task_events")

    # 三个任务：task_2 依赖 task_1，task_3 高优先级
    t1 = Task(name="设计", owner="system_designer", priority="HIGH")
    t2 = Task(name="实现", owner="client_dev", depends_on=[t1.id])
    t3 = Task(name="紧急热修", owner="client_dev", priority="URGENT")

    sched.enqueue(t1)
    sched.enqueue(t2)
    sched.enqueue(t3)

    print(f"\n入队后: {bus.pending} 条 TASK_ASSIGN 待处理")
    bus.process_all()
    print("总线派发的任务分配消息:")
    for m in bus.delivered:
        if m.type == "TASK_ASSIGN":
            print(f"  - {m.content['name']} -> {m.to_role} (priority={m.priority})")

    # 完成 t1，解锁 t2
    print("\n[t1 完成] 解锁依赖它的下游...")
    sched.on_complete(t1.id, "system_designer")
    print(f"t2 状态: {sched.queue.tasks[t2.id].state}")
    bus.process_all()

    print("\n任务事件通知:")
    for m in events:
        print(f"  - {m.content.get('event')}: {m.content.get('task_id')}")

    print("\n队列统计:", sched.queue.stats())


if __name__ == "__main__":
    demo()

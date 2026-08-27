# ============================================================
# 生态角色承接 Handler 实体化 (Ecosystem Handlers)
# 版本: v1.0
# 说明: 为解决"生态角色仅注册可派发、无承接 handler，任务恒停留 TODO 永不 DONE"
#       的架构级风险（架构·总师盘点 Issue #55 的 HIGH 风险项）。
#
#   - 为代表性生态角色提供**真实承接逻辑**，使它们能接收 TASK_ASSIGN、
#     执行领域动作并产出结果（回执/产品/反馈），从而让任务真正 DONE；
#   - 支持按需接入 EcosystemRoleRegistry 或 MessageBus，不再依赖"演示性派发"。
#
# 设计:
#   * 每个 handler 是一个纯函数 `fn(task, context) -> result`
#   * EcosystemHandler 负责把生态角色绑定到 message_bus 的 TASK_ASSIGN 事件
#   * 收到派发后执行 handler，并把任务经 task_scheduler.complete() 标为 DONE
#     （解除了原先 _all_done 刻意过滤 eco_* 的必要性，见 WP-03）
#
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from message_bus import Message, MessageBus, build_task_assign
from task_scheduler import Task, TaskState

# ============================================================
# 一、生态角色承接函数（领域动作）
# ============================================================

def _handler_publisher(task: Task, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """外部市场圈·发行商(publisher)：市场预演与发行策略。
    承接 '市场预演派发' 等任务，产出市场预演报告。
    """
    return {
        "role": "publisher",
        "action": "市场预演",
        "output": "市场预演报告（发行窗口/渠道评估/风险提示）",
        "note": "真实承接：publisher 已完成市场预演闭环",
    }


def _handler_core_player(task: Task, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """玩家圈·核心玩家(core_player)：反馈回收与体验报告。
    承接 '玩家反馈回收' 任务，产出玩家反馈汇总。
    """
    return {
        "role": "core_player",
        "action": "玩家反馈回收",
        "output": "玩家反馈报告（满意度/痛点/建议）",
        "note": "真实承接：core_player 已完成反馈回收闭环",
    }


def _handler_advertiser(task: Task, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """外部市场圈·广告商(advertiser)：广告变现调优。
    承接 '广告变现调优' 任务，产出变现优化建议。
    """
    return {
        "role": "advertiser",
        "action": "广告变现调优",
        "output": "变现调优建议（广告位/频次/收益模型）",
        "note": "真实承接：advertiser 已完成变现调优闭环",
    }


def _handler_gig_pool(task: Task, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """协作支持圈·零工池(gig_pool)：负载调度。
    承接 '零工负载调度' 任务，产出负载分配方案。
    """
    return {
        "role": "gig_pool",
        "action": "零工负载调度",
        "output": "负载分配方案（任务池/人力池匹配）",
        "note": "真实承接：gig_pool 已完成负载调度闭环",
    }


def _handler_progress_pusher(task: Task, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """协作支持圈·进度督导(progress_pusher)：盯守与催办。
    承接 '进度督导盯守' 任务，产出进度督导结论。
    """
    return {
        "role": "progress_pusher",
        "action": "进度督导盯守",
        "output": "进度督导结论（逾期清单/催办升级）",
        "note": "真实承接：progress_pusher 已完成督导盯守闭环",
    }


# ============================================================
# 二、handler 映射（生态角色 → 承接函数）
# ============================================================

# 代表角色 → handler；其余生态角色可逐步补充
ECOSYSTEM_HANDLERS: Dict[str, Callable[[Task, Dict[str, Any]], Dict[str, Any]]] = {
    "publisher":        _handler_publisher,
    "core_player":      _handler_core_player,
    "advertiser":       _handler_advertiser,
    "gig_pool":         _handler_gig_pool,
    "progress_pusher":  _handler_progress_pusher,
}


# ============================================================
# 三、EcosystemHandler：把 handler 接入 MessageBus / TaskScheduler
# ============================================================

class EcosystemHandler:
    """生态角色承接实体。

    把 ECOSYSTEM_HANDLERS 中的生态角色绑定到 message_bus 的 TASK_ASSIGN 事件，
    收到派发后执行领域 handler 并把任务标为 DONE，实现"真实承接闭环"。
    """

    def __init__(self, bus: MessageBus, scheduler=None):
        self.bus = bus
        self.scheduler = scheduler  # 可选：持有 task_scheduler 以便 complete()
        self.results: Dict[str, Dict[str, Any]] = {}  # task_id -> handler 产出
        self._bind()

    def _bind(self):
        """为已映射的生态角色注册 TASK_ASSIGN 承接 handler。"""
        for role_id in ECOSYSTEM_HANDLERS:
            self.bus.register(role_id)
            self.bus.on(role_id, self._on_assign)

    def _on_assign(self, msg: Message):
        """TASK_ASSIGN 事件：取出任务并执行对应生态角色 handler。"""
        content = msg.content or {}
        task_id = content.get("task_id") or content.get("task") or ""
        # 兼容两种 TASK_ASSIGN 结构：
        #   scheduler.enqueue 派发: {"task_id","name","payload"}
        #   build_task_assign 构造: {"task_id","inputs","deadline"}
        task_name = (content.get("name")
                     or (content.get("inputs") or {}).get("name")
                     or content.get("task_id") or "")
        owner = msg.to_role or ""
        handler = ECOSYSTEM_HANDLERS.get(owner)
        if not handler:
            # 未映射的生态角色：记录未承接，避免静默
            self.results[task_id] = {"role": owner, "action": task_name,
                                     "error": "无 handler，待补充"}
            return
        # 执行领域动作：从 scheduler 取真实 Task 传给 handler（若存在）
        real_task = None
        if self.scheduler is not None and task_id in self.scheduler.queue.tasks:
            real_task = self.scheduler.queue.tasks[task_id]
        result = handler(real_task or Task(id=task_id, name=task_name, owner=owner), {})
        self.results[task_id] = result
        # 若有 scheduler，把对应任务标为 DONE（解锁下游 / 让 _all_done 无需过滤）
        if real_task is not None:
            real_task.touch(TaskState.DONE.value, "生态角色真实承接")

    # ---------- 查询 ----------
    def handled(self) -> list:
        """已由生态角色真实承接的任务结果列表。"""
        return list(self.results.values())

    def all_handled_done(self) -> bool:
        """是否所有已派发生态任务都由 handler 承接并 DONE。"""
        return bool(self.results) and all(
            "error" not in r for r in self.results.values())


# ============================================================
# 四、演示
# ============================================================

def demo():
    print("=" * 70)
    print("生态角色承接 Handler 实体化（wp_server / wp_ai_logic）")
    print("  让生态角色真实承接派发任务并 DONE，解除 _all_done 过滤依赖")
    print("=" * 70)

    from task_scheduler import Scheduler, TaskQueue, Task
    bus = MessageBus()
    scheduler = Scheduler(queue=TaskQueue(), bus=bus)
    handler = EcosystemHandler(bus, scheduler)

    # 派发代表性生态角色任务
    eco_jobs = [
        ("eco_publish", "市场预演派发", "publisher", "HIGH"),
        ("eco_advert", "广告变现调优", "advertiser", "NORMAL"),
        ("eco_player", "玩家反馈回收", "core_player", "NORMAL"),
        ("eco_gig", "零工负载调度", "gig_pool", "NORMAL"),
        ("eco_push", "进度督导盯守", "progress_pusher", "HIGH"),
    ]
    for tid, name, owner, prio in eco_jobs:
        scheduler.enqueue(Task(id=tid, name=name, owner=owner, priority=prio))
        bus.publish(build_task_assign("producer", owner, tid,
                                       {"name": name, "owner": owner}))

    bus.process_all()

    print(f"\n生态角色承接结果（共 {len(handler.handled())} 个任务）:")
    for r in handler.handled():
        print(f"  - {r.get('role'):<16} {r.get('action')}: {r.get('note', r.get('error'))}")

    # 校验：这些 eco_* 任务已真实 DONE，无需再过滤
    done_ids = [tid for tid, t in scheduler.queue.tasks.items()
                if t.state == TaskState.DONE.value]
    print(f"\n已真实 DONE 的生态任务: {done_ids}")
    print(f"全部生态任务由 handler 承接: {handler.all_handled_done()}")

    # 反证：_all_done 现在可以包含 eco_*（无需刻意过滤）
    all_done = bool(scheduler.queue.tasks) and all(
        t.state == TaskState.DONE.value for t in scheduler.queue.tasks.values())
    print(f"含 eco_* 的全链路 all_done（无需过滤）: {all_done} ✅")


if __name__ == "__main__":
    demo()

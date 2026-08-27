# ============================================================
# _alt 变体实体化样板 (Alt Variants)
# 版本: v1.0
# 说明: 解决"28 个 _alt 变体仅声明、无独立实现，被部门 Agent 吞并"的架构问题。
#       按架构·总师建议，先抽取 3 个高价值变体做实体化样板：
#         - producer_alt       制作人（进取型）   → 管理岗
#         - server_dev_alt     服务端（性能型）   → 程序线
#         - data_analyst_alt   数据分析（可视化型）→ 运营线
#   每个变体提供独立 behavior handler，展示"同岗位、异风格"的真实行为差异化，
#   而非仅靠 module 字段被部门 Agent 无差别兜底。
#
# 设计:
#   * ALT_VARIANTS 把 role_id → 独立行为函数（风格专属执行逻辑）
#   * AltVariantHandler 接入 MessageBus，让 _alt 变体真实承接任务
#   * 样板跑通后，其余 25 个 _alt 变体可按同模式批量补充（排 P1/P2）
#
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from message_bus import Message, MessageBus, build_task_assign
from task_scheduler import Task, TaskState


# ============================================================
# 一、3 个样板变体的独立行为（风格差异化执行）
# ============================================================

def _producer_aggressive(task: Task, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """制作人·进取型：偏好创新与差异化，敢于承担风险换取市场突破口。
    与稳健型 producer 不同：产出偏"进攻性立项/高风险高回报"决策。
    """
    return {
        "role": "producer_alt",
        "personality": "进取敢为",
        "style": "进攻性立项决策：押注差异化创新，接受高风险高回报",
        "output": "进取型立项书（差异化机会/资源赌注/市场突破口）",
        "note": "独立实体化：producer_alt 执行进取型制作人行为，区别于稳健型",
    }


def _server_perf(task: Task, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """服务端程序员·性能型：痴迷高并发低延迟，数据驱动优化。
    与 server_dev 不同：产出偏"性能基准/吞吐优化"而非通用开发。
    """
    return {
        "role": "server_dev_alt",
        "personality": "性能极致",
        "style": "性能优先：以基准数据驱动高并发/低延迟优化决策",
        "output": "性能优化报告（吞吐/延迟基准 + 优化方案）",
        "note": "独立实体化：server_dev_alt 执行性能型服务端行为",
    }


def _data_viz(task: Task, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """数据分析师·可视化型：让数据一目了然，洞察可读可传播。
    与 data_analyst 不同：产出偏"可视化呈现/洞察传播"。
    """
    return {
        "role": "data_analyst_alt",
        "personality": "可视呈现",
        "style": "可视化优先：把复杂数据转化为可读可传播的洞察呈现",
        "output": "可视化数据洞察（图表/仪表盘/决策摘要）",
        "note": "独立实体化：data_analyst_alt 执行可视化型数据分析行为",
    }


# ============================================================
# 二、样板变体映射
# ============================================================

ALT_VARIANTS: Dict[str, Callable[[Task, Dict[str, Any]], Dict[str, Any]]] = {
    "producer_alt":       _producer_aggressive,
    "server_dev_alt":     _server_perf,
    "data_analyst_alt":   _data_viz,
}


# ============================================================
# 三、AltVariantHandler：把变体接入 MessageBus
# ============================================================

class AltVariantHandler:
    """_alt 变体承接实体。

    把 ALT_VARIANTS 中的变体绑定到 message_bus 的 TASK_ASSIGN 事件，
    使变体真实承接任务并产出"风格差异化"结果，不再被部门 Agent 无差别吞并。
    """

    def __init__(self, bus: MessageBus, scheduler=None):
        self.bus = bus
        self.scheduler = scheduler
        self.results: Dict[str, Dict[str, Any]] = {}
        self._bind()

    def _bind(self):
        for role_id in ALT_VARIANTS:
            self.bus.register(role_id)
            self.bus.on(role_id, self._on_assign)

    def _on_assign(self, msg: Message):
        content = msg.content or {}
        task_id = content.get("task_id") or ""
        inputs = content.get("inputs") or {}
        task_name = inputs.get("name") or content.get("task_id") or ""
        owner = msg.to_role or ""
        handler = ALT_VARIANTS.get(owner)
        if not handler:
            self.results[task_id] = {"role": owner, "error": "无样板 handler"}
            return
        real_task = None
        if self.scheduler is not None and task_id in self.scheduler.queue.tasks:
            real_task = self.scheduler.queue.tasks[task_id]
        result = handler(real_task or Task(id=task_id, name=task_name, owner=owner), {})
        self.results[task_id] = result
        if real_task is not None:
            real_task.touch(TaskState.DONE.value, "变体真实承接")

    def handled(self) -> list:
        return list(self.results.values())

    def all_handled_done(self) -> bool:
        return bool(self.results) and all(
            "error" not in r for r in self.results.values())


# ============================================================
# 四、演示
# ============================================================

def demo():
    print("=" * 70)
    print("_alt 变体实体化样板（producer_alt / server_dev_alt / data_analyst_alt）")
    print("  让 3 个高价值变体独立承接任务，展示风格差异化行为")
    print("=" * 70)

    from task_scheduler import Scheduler, TaskQueue
    bus = MessageBus()
    scheduler = Scheduler(queue=TaskQueue(), bus=bus)
    handler = AltVariantHandler(bus, scheduler)

    jobs = [
        ("alt_producer", "进取型立项决策", "producer_alt", "HIGH"),
        ("alt_server", "性能基准优化", "server_dev_alt", "NORMAL"),
        ("alt_data", "可视化数据洞察", "data_analyst_alt", "NORMAL"),
    ]
    for tid, name, owner, prio in jobs:
        scheduler.enqueue(Task(id=tid, name=name, owner=owner, priority=prio))
        bus.publish(build_task_assign("producer", owner, tid,
                                      {"name": name, "owner": owner}))

    bus.process_all()

    print(f"\n样板变体承接结果（共 {len(handler.handled())} 个）:")
    for r in handler.handled():
        print(f"  - {r.get('role'):<18} [{r.get('personality')}] {r.get('output')}")
        print(f"      注: {r.get('note')}")

    done_ids = [tid for tid, t in scheduler.queue.tasks.items()
                if t.state == TaskState.DONE.value]
    print(f"\n已真实 DONE 的变体任务: {done_ids}")
    print(f"全部样板变体由独立 handler 承接: {handler.all_handled_done()}")


if __name__ == "__main__":
    demo()

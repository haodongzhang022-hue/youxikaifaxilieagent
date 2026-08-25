# ============================================================
# 多部门 Agent 端到端联动（v0.7）—— 可运行演示
# 说明: 把「游戏向经理 + 六大部门 Agent + task_scheduler + message_bus」
#       装配在同一总线上，跑通「策划→程序→美术→测试→发版→运营」全链路。
#
# 事件驱动机制（非手动推进）：
#   1. 经理把架构蓝图拆解为部门工作包，投递到 task_scheduler；
#   2. scheduler 将无依赖上游（策划）自动派发给策划线 Agent；
#   3. 部门 Agent 执行后上报 REVIEW_RESULT 给经理；
#   4. 经理验收通过 → scheduler 自动解锁下游部门（程序/美术）；
#   5. 逐级解锁直到测试 → 发版 → 运营，全链路自动完成。
#
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List

from agent_core import BaseAgent
from department_agents import build_department_agents, DepartmentAgent
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, Message, build_task_assign, build_message
from task_scheduler import Scheduler, Task, TaskState


class EndToEndOrchestrator:
    """端到端联动编排器：装配经理 + 六部门 Agent + 调度器。

    负责：
      - 创建统一 MessageBus 与 Scheduler；
      - 注册经理与六部门 Agent 到总线；
      - 下发架构蓝图触发拆解派单；
      - 驱动消息循环：派单 → 部门执行 → 上报验收 → 解锁下游；
      - 输出工作包完成情况与依赖解锁记录。
    """

    def __init__(self, with_progress_pusher: bool = True):
        self.bus = MessageBus()
        self.manager = GameProducerAgent(bus=self.bus)
        self.manager.boot()
        self.departments = build_department_agents(self.bus)
        # 用经理的 scheduler（其 bus 与本次一致）
        self.scheduler = self.manager.scheduler
        self.unlock_log: List[Dict[str, Any]] = []   # 依赖解锁记录
        self.progress_pusher = None
        # 评审点 #4：producer 已不再盯逾期，逾期/催办/升级须由 progress_pusher
        # 显式挂载接管；这里默认一键挂载，避免“逾期无人盯守”的责任真空。
        if with_progress_pusher:
            self.attach_progress_pusher()

    def attach_progress_pusher(self) -> "ProgressPusherAgent":
        """把进度督导挂到本链路：共享总线 + 复用经理 TaskQueue。

        挂载后 progress_pusher 会订阅 task_events 事件驱动即时督导，
        并在事件循环中随心跳扫描逾期/催办/升级，与 producer 的
        阻塞/依赖级联督导职责互补，不重复发同类催办。
        """
        from progress_pusher import ProgressPusherAgent, attach_to_scheduler
        self.progress_pusher = ProgressPusherAgent(bus=self.bus, queue=self.scheduler.queue)
        attach_to_scheduler(self.scheduler, self.progress_pusher)
        self.progress_pusher.boot()
        return self.progress_pusher

    # ---------- 装配 ----------
    def assemble(self, architecture: Dict[str, Any]):
        """下发架构蓝图，触发经理拆解派单。"""
        msg = build_task_assign(
            "architect", self.manager.role_id, "e2e_001",
            {"architecture": architecture})
        self.bus.publish(msg)
        self.bus.process_all()

    # ---------- 事件循环驱动 ----------
    def drive(self, max_rounds: int = 100) -> Dict[str, Any]:
        """事件循环：持续处理消息，自动推进验收与解锁，直到全链路完成或超轮次。"""
        rounds = 0
        all_done = False
        while rounds < max_rounds:
            rounds += 1
            # 处理总线上积压消息
            processed = self.bus.process_all()
            # 调度器取出就绪任务派发给部门 Agent（已由 enqueue/dispatch 处理）

            # 进度督导随事件循环运行：事件驱动即时督导（订阅 task_events）
            # + 心跳定时扫描逾期/催办/升级，真正接管“时间进度”盯守。
            if self.progress_pusher is not None:
                self.progress_pusher.heartbeat()

            # 检查是否全部完成（所有工作包 DONE）
            all_done = self._all_done()
            if all_done:
                break
            # 没有可处理消息也没有就绪任务则可能阻塞，做一次心跳督导
            if processed == 0 and not self.scheduler.queue.ready_order:
                self.manager.heartbeat()
                break
        return {"rounds": rounds, "all_done": all_done}

    def _all_done(self) -> bool:
        states = [t.state for t in self.scheduler.queue.tasks.values()]
        return states and all(s == TaskState.DONE.value for s in states)

    # ---------- 部门产出验收回执（由部门 Agent 上报后由经理处理） ----------
    # 说明：部门 Agent 已自行上报 REVIEW_RESULT 给经理；经理的
    #       _on_department_delivery 会自动完成验收并解锁下游，无需在此干预。
    #       本类仅做结果统计。

    # ---------- 结果汇总 ----------
    def report(self) -> Dict[str, Any]:
        """汇总工作包完成情况与依赖解锁记录。"""
        wp_states: List[Dict[str, Any]] = []
        for t in self.scheduler.queue.tasks.values():
            wp = t.payload.get("work_package", {}) or {}
            wp_states.append({
                "id": wp.get("id") or t.id,
                "label": wp.get("label") or t.name,
                "department": wp.get("department_name") or t.owner,
                "owner": wp.get("owner") or t.owner,
                "deps": wp.get("deps", []) or t.depends_on,
                "state": t.state,
            })
        return {
            "manager": self.manager.report(),
            "progress_pusher": self.progress_pusher.report() if self.progress_pusher else None,
            "work_packages": wp_states,
            "departments": {k: {"role": a.role_id, "done": a.done_packages}
                            for k, a in self.departments.items()},
            "unlock_log": self.unlock_log,
        }


def demo():
    print("=" * 70)
    print("多部门 Agent 端到端联动（v0.7）—— 策划→程序→美术→测试→发版→运营")
    print("=" * 70)

    orch = EndToEndOrchestrator()
    # 下发架构蓝图（对应 Issue #16 的派发清单）
    architecture = {
        "project": "开放世界动作游戏 demo",
        "modules": [
            "gameplay", "numeric_model",        # 策划线
            "client", "server", "engine", "ai_logic",  # 程序线
            "art_direction", "ui_ux", "audio",  # 美术线
            "testing",                          # 测试线
            "release",                          # 项目管理
            "data_ops",                         # 运营线
        ],
    }
    orch.assemble(architecture)
    result = orch.drive(max_rounds=200)
    report = orch.report()

    print(f"\n编排完成: all_done={result['all_done']}")
    print("\n== 工作包拆分与完成状态 ==")
    print(f"{'工作包':<16}{'部门':<6}{'主责角色':<16}{'状态':<10}依赖")
    for wp in report["work_packages"]:
        print(f"{wp['id']:<16}{wp['department']:<6}{wp['owner']:<16}{wp['state']:<10}{wp['deps']}")

    print("\n== 各部门 Agent 执行情况 ==")
    for k, v in report["departments"].items():
        print(f"  - {k}: {v['role']} 已完成 {v['done']}")

    # 评审点 #4：进度督导已一键挂载，接管逾期/催办/升级盯守
    if report.get("progress_pusher"):
        pp = report["progress_pusher"]
        print("\n== 进度督导已挂载（接管逾期/催办/升级盯守）==")
        print(f"  - 追踪任务数: {pp.get('watched_tasks')}")
        print(f"  - 催办次数: {pp.get('pushes')} / 预警: {pp.get('warns')} / 升级: {pp.get('escalates')}")

    return orch


if __name__ == "__main__":
    orch = demo()

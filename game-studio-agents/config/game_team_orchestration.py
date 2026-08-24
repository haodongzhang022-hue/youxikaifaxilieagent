# ============================================================
# 游戏团队端到端编排 · 可运行实现（GameTeamOrchestration）
# 版本: v0.7
# 说明: 把「游戏向经理 + 六大部门执行 Agent」串成一条端到端流水线，
#       跑通「策划→程序→美术→测试→发版→运营」全链路，验证
#       「验收→解锁下游→自动推进」闭环。
#
# 机制驱动（非手动推进）：
#   1. 游戏向经理收到架构蓝图 → 拆解为部门工作包（wp_*）→ 按依赖派发；
#   2. 无依赖上游（策划）先执行 → 上报 REVIEW_RESULT → 经理验收通过
#      → 调度器自动解锁下游（程序/美术）；
#   3. 下游部门 Agent 接收新派单 → 执行 → 上报 → 验收 → 继续解锁；
#   4. 直至 测试→发版→运营 全部完成，形成自动流水线。
#
# 本模块可作为验证 v0.7 端到端联动的可复现入口。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List

from agent_core import BaseAgent
from message_bus import Message, MessageBus, build_task_assign, build_message
from task_scheduler import Scheduler, TaskState

from game_producer_agent import GameProducerAgent
from department_agents import (
    DepartmentAgent,
    DesignDeptAgent,
    ProgramDeptAgent,
    ArtDeptAgent,
    QADeptAgent,
    PMDeptAgent,
    OpsDeptAgent,
)


# ============================================================
# 端到端编排器
# ============================================================

class GameTeamOrchestrator:
    """
    游戏团队端到端编排器：经理 + 六部门 Agent 协同跑全链路。

    - 每个部门只创建单一 Agent 实例（role 唯一），避免同 role 多实例重复消费；
    - 部门 Agent 在经理派发前 boot 注册，使调度器派单可被正确接收；
    - 通过消息总线事件驱动，自动完成「验收→解锁下游→再执行」的依赖推进。
    """

    def __init__(self, project: str = "开放世界动作游戏 demo",
                 modules: List[str] | None = None,
                 manager_role: str = "producer"):
        self.project = project
        self.modules = modules or [
            "gameplay", "numeric_model",           # 策划线（无依赖，先执行）
            "client", "server", "engine", "ai_logic",  # 程序线（依赖策划）
            "art_direction", "ui_ux", "audio",      # 美术线（依赖策划）
            "testing",                              # 测试线（依赖程序+美术）
            "release",                              # 项目管理（依赖测试）
            "data_ops",                             # 运营线（依赖全链路）
        ]
        self.manager_role = manager_role

        self.bus = MessageBus()
        self.sched = Scheduler(bus=self.bus)
        self.manager: GameProducerAgent = GameProducerAgent(
            role_id=manager_role, bus=self.bus, scheduler=self.sched)
        # 六部门 Agent（每个部门单一实例）
        self.departments: List[DepartmentAgent] = [
            DesignDeptAgent(role_id="lead_designer", bus=self.bus,
                            scheduler=self.sched, manager_role=manager_role),
            ProgramDeptAgent(role_id="cto", bus=self.bus,
                             scheduler=self.sched, manager_role=manager_role),
            ArtDeptAgent(role_id="art_director", bus=self.bus,
                         scheduler=self.sched, manager_role=manager_role),
            QADeptAgent(role_id="qa_engineer", bus=self.bus,
                        scheduler=self.sched, manager_role=manager_role),
            PMDeptAgent(role_id="project_manager", bus=self.bus,
                        scheduler=self.sched, manager_role=manager_role),
            OpsDeptAgent(role_id="data_analyst", bus=self.bus,
                         scheduler=self.sched, manager_role=manager_role),
        ]
        self.deliveries: Dict[str, List[str]] = {}   # role -> [wp_id, ...]

    # ---------- 启动与运行 ----------
    def boot(self):
        """启动所有 Agent 并注册到总线。"""
        self.manager.boot()
        for dept in self.departments:
            dept.boot()

    def run(self) -> Dict[str, Any]:
        """驱动端到端流程：下发架构蓝图 → 逐轮处理总线消息直至队列清空。"""
        self.boot()
        # 下发架构蓝图给游戏向经理
        self.bus.publish(build_task_assign(
            "architect", self.manager_role, "orch_v07",
            {"architecture": {"project": self.project, "modules": self.modules}}))
        # 处理消息队列（含依赖解锁后调度器产生的再派发），直到全部清空
        self._drain()
        return self.summary()

    def _drain(self, max_rounds: int = 200):
        """持续处理总线消息，直到队列清空（依赖自动解锁会不断产生新消息）。"""
        round_no = 0
        while round_no < max_rounds:
            processed = self.bus.process_all()
            if processed == 0:
                break
            round_no += 1

    # ---------- 观测 ----------
    def work_packages(self) -> List[Dict[str, Any]]:
        return self.manager.work_packages

    def dept_deliveries(self) -> Dict[str, List[str]]:
        """返回每个部门 Agent 已交付的工作包（去重）。"""
        out: Dict[str, List[str]] = {}
        for dept in self.departments:
            ids = sorted({d["work_package_id"] for d in dept.deliveries})
            if ids:
                out[dept.dept_name()] = ids
        return out

    def task_states(self) -> Dict[str, str]:
        return {tid: t.state for tid, t in self.sched.queue.tasks.items()}

    def summary(self) -> Dict[str, Any]:
        return {
            "project": self.project,
            "total_work_packages": len(self.work_packages()),
            "task_states": self.task_states(),
            "dept_deliveries": self.dept_deliveries(),
            "manager_accepted": self.manager.accepted,
        }


# ============================================================
# 演示 / 端到端验证
# ============================================================

def demo():
    print("=" * 60)
    print("游戏团队端到端编排 (GameTeamOrchestrator) 演示")
    print("  —— 经理 + 六部门 Agent 跑通全链路")
    print("=" * 60)

    orch = GameTeamOrchestrator()
    result = orch.run()

    print(f"\n项目: {result['project']}")
    print(f"工作包总数: {result['total_work_packages']}")

    print("\n六大部门交付物（按依赖解锁自动推进）:")
    for dept_name, wps in result["dept_deliveries"].items():
        print(f"  - {dept_name:<8} {len(wps)} 个工作包: {','.join(wps)}")

    print("\n调度队列任务最终状态:")
    for tid, state in result["task_states"].items():
        print(f"  - {tid:<22} {state}")

    print("\n经理已验收的工作包:", ",".join(result["manager_accepted"]))

    # 端到端断言
    all_done = all(
        s == TaskState.DONE.value for s in result["task_states"].values()
    ) and bool(result["task_states"])
    print(f"\n端到端全部完成: {'✅' if all_done else '❌'}")

    # 依赖链路完整（策划→程序/美术→测试→发版→运营 全部交付）
    dept_deliv = result["dept_deliveries"]
    chain_ok = (
        "策划线" in dept_deliv and "程序线" in dept_deliv and "美术线" in dept_deliv
        and "测试线" in dept_deliv and "项目管理" in dept_deliv and "运营线" in dept_deliv
    )
    print(f"六部门全链路联动: {'✅' if chain_ok else '❌'}")

    return result


if __name__ == "__main__":
    demo()

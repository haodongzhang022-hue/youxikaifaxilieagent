# ============================================================
# 实例化团队端到端联动（v0.9）—— 真实团队装配到部门流水线并跑通全链路
# 说明: 承接 Issue #22（解锁自 PR #20）。把 v0.8 预设实例化器产出的
#       「真实项目团队」（13 个正式角色，六大部门齐全）装配到部门执行
#       流水线，让实例化 role_id（如 client_dev_unity_1）作为工作包
#       主责/协办真正参与调度，跑通「策划→程序∥美术→测试→发版→运营」。
#
# v0.9 三项能力（对照 Issue 目标）：
#   1. 持久化/注册：register_instantiated_team 把实例化角色注册进经理的
#      部门能力表，使带后缀 role_id 可被 _assign_resources 识别为装配来源；
#   2. 装配派发：为每个实例化角色创建对应部门 Agent（以实例化 role_id 为
#      身份注册到 message_bus），task_scheduler 按 owner 派发 TASK_ASSIGN，
#      publish 到总线由实例化角色承接；
#   3. 端到端联动：实例化团队承接 wp_* 工作包，上游验收通过后自动解锁下游，
#      全链路 DONE。
#
# 全程事件驱动、无 / 命令推进；上游验收后下游自动解锁派发。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent_core import BaseAgent
from department_agents import (ArtDeptAgent, DesignDeptAgent, OpsDeptAgent,
                               PmDeptAgent, ProgramDeptAgent, QaDeptAgent)
from game_producer_agent import GameProducerAgent
from message_bus import MessageBus, build_task_assign
from preset_instantiator import PresetInstantiator
from task_scheduler import Scheduler, TaskState

# 部门中文名 → 对应部门 Agent 类（与 department_agents.py 的六部门一致）
DEPT_AGENT_CLASS = {
    "策划线": DesignDeptAgent,
    "程序线": ProgramDeptAgent,
    "美术线": ArtDeptAgent,
    "测试线": QaDeptAgent,
    "项目管理": PmDeptAgent,
    "运营线": OpsDeptAgent,
}


def _spawn_dept_agent(dept_agent_cls, role_id: str, dept_name: str,
                      bus: MessageBus) -> BaseAgent:
    """以实例化 role_id 为身份创建一个部门 Agent 实例。

    各部门 Agent 子类的 __init__ 硬编码了 base_role（如 lead_designer），
    无法直接传入实例化 role_id。这里用 __new__ 绕过子类 __init__，
    显式调用基类 DepartmentAgent.__init__ 以实例化 role_id 注册到总线，
    使调度器派发的 TASK_ASSIGN（owner=实例化 role_id）能命中该 Agent。
    """
    agent = dept_agent_cls.__new__(dept_agent_cls)
    # 直接调用基类 DepartmentAgent.__init__，设置 role_id + department
    DepartmentAgent = dept_agent_cls.__mro__[1]
    DepartmentAgent.__init__(agent, role_id, dept_name, bus)
    return agent


class InstantiatedTeamOrchestrator:
    """实例化团队端到端编排器：装配真实团队到部门流水线并联动。

    流程：
      1. PresetInstantiator 实例化团队（13 个正式角色）；
      2. 经理 register_instantiated_team 注册团队，作为装配来源；
      3. 为每个实例化角色生成部门 Agent，注册到总线；
      4. 下发架构蓝图 → 经理拆解 → 派发（owner=实例化角色）→ 全链路联动。
    """

    def __init__(self):
        self.bus = MessageBus()
        self.manager = GameProducerAgent(bus=self.bus)
        self.manager.boot()
        self.scheduler = self.manager.scheduler
        # 实例化团队
        self.instantiator = None
        self.report: Dict[str, Any] = {}
        self.team_agents: Dict[str, BaseAgent] = {}   # 实例化 role_id -> Agent
        self.department_agents: Dict[str, BaseAgent] = {}  # 部门键 -> 主责实例化 Agent

    # ---------- 1. 实例化 + 2. 注册 + 3. 装配 ----------
    def assemble_team(self,
                      project_type: str = "ptype_mobile_game",
                      phase: str = "phase_production",
                      scale: str = "scale_medium",
                      team: str = "team_unity",
                      stack: str = "stack_unity_ecosystem") -> Dict[str, Any]:
        """实例化真实团队并注册到经理部门能力表，装配可执行部门 Agent。"""
        inst = PresetInstantiator().load()
        inst.apply_project_type(project_type).apply_phase(phase) \
            .apply_team_scale(scale).select_team(team).select_stack(stack)
        report = inst.instantiate()
        self.instantiator = inst
        self.report = report

        # (a) 注册实例化角色到经理部门能力表（装配来源）
        self.manager.register_instantiated_team(inst.instantiated_roles)

        # (b) 为每个实例化角色创建对应部门 Agent 并注册到总线
        assembled = report["assembled_team"]
        dept_role = {
            "design": "策划线", "program": "程序线", "art": "美术线",
            "qa": "测试线", "pm": "项目管理", "ops": "运营线",
        }
        for dept_key, dept_name in dept_role.items():
            for role_summary in assembled.get(dept_key, []):
                rid = role_summary["role_id"]
                agent = _spawn_dept_agent(DEPT_AGENT_CLASS[dept_name], rid,
                                          dept_name, self.bus)
                agent.boot()
                self.team_agents[rid] = agent
                # 记录该部门主责实例化角色（部门第一个角色，同 instantiated 顺序）
                if dept_key not in self.department_agents:
                    self.department_agents[dept_key] = agent

        return report

    # ---------- 4. 派发 + 端到端联动 ----------
    def run_full_chain(self, architecture: Dict[str, Any],
                       max_rounds: int = 300) -> Dict[str, Any]:
        """下发架构蓝图，实例化团队承接工作包，跑通全链路联动。"""
        msg = build_task_assign(
            "architect", self.manager.role_id, "e2e_inst_001",
            {"architecture": architecture})
        self.bus.publish(msg)
        self.bus.process_all()

        rounds = 0
        all_done = False
        while rounds < max_rounds:
            rounds += 1
            processed = self.bus.process_all()
            all_done = self._all_done()
            if all_done:
                break
            if processed == 0 and not self.scheduler.queue.ready_order:
                self.manager.heartbeat()
                break
        return {"rounds": rounds, "all_done": all_done}

    def _all_done(self) -> bool:
        states = [t.state for t in self.scheduler.queue.tasks.values()]
        return states and all(s == TaskState.DONE.value for s in states)

    # ---------- 汇总 ----------
    def summary(self) -> Dict[str, Any]:
        """工作包完成情况（owner 为实例化 role_id）+ 团队装配清单。"""
        wp_states = []
        for t in self.scheduler.queue.tasks.values():
            wp = t.payload.get("work_package", {}) or {}
            wp_states.append({
                "id": wp.get("id") or t.id,
                "label": wp.get("label") or t.name,
                "department": wp.get("department_name") or t.owner,
                "owner": wp.get("owner") or t.owner,
                "support": wp.get("support", []),
                "deps": wp.get("deps", []),
                "state": t.state,
            })
        return {
            "project": self.report.get("project_type", {}),
            "phase": self.report.get("phase", {}),
            "team": self.report.get("team", {}),
            "stack": self.report.get("stack", {}),
            "assembled_team": self.report.get("assembled_team", {}),
            "total_roles": self.report.get("total_roles", 0),
            "department_count": self.report.get("department_count", {}),
            "work_packages": wp_states,
            "team_agents": sorted(self.team_agents.keys()),
            "all_done": self._all_done(),
        }


def demo() -> InstantiatedTeamOrchestrator:
    print("=" * 78)
    print("实例化团队端到端联动（v0.9）—— 真实团队装配到部门流水线")
    print("    移动端手游 × 正式开发 × 中型团队 × Unity小组/技术栈")
    print("=" * 78)

    orch = InstantiatedTeamOrchestrator()
    # 实例化 + 注册 + 装配
    report = orch.assemble_team()
    print(f"\n[1] 实例化团队（共 {report['total_roles']} 个正式角色）")
    for dept, roles in report["assembled_team"].items():
        ids = ", ".join(r["role_id"] for r in roles) or "(空)"
        print(f"    {dept:<8}: {ids}")

    # 下发架构蓝图（对齐六大部门派发清单）
    architecture = {
        "project": "移动端手游 demo（实例化团队）",
        "modules": [
            "gameplay", "numeric_model",        # 策划线
            "client", "server", "engine", "ai_logic",  # 程序线
            "art_direction", "ui_ux", "audio",  # 美术线
            "testing",                          # 测试线
            "release",                          # 项目管理
            "data_ops",                         # 运营线
        ],
    }
    orch.run_full_chain(architecture)

    print("\n[2] 工作包拆分与实例化团队承接（主责/协办/依赖）")
    for wp in orch.summary()["work_packages"]:
        support = ", ".join(wp["support"]) or "—"
        print(f"    {wp['id']:<18}{wp['department']:<8}主责={wp['owner']}")
        print(f"    {'':<18}{'':<8}协办={support}")
        print(f"    {'':<18}{'':<8}状态={wp['state']}  依赖={wp['deps']}")

    print("\n[3] 实例化团队装配到总线（可执行部门 Agent）")
    print("    ", ", ".join(orch.summary()["team_agents"]))

    print(f"\n[4] 端到端联动结果: all_done = {orch.summary()['all_done']}")
    return orch


if __name__ == "__main__":
    demo()

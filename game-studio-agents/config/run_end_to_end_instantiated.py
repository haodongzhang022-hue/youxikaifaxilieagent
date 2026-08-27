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
from department_agents import (ArtDeptAgent, DepartmentAgent, DesignDeptAgent,
                               OpsDeptAgent, PmDeptAgent, ProgramDeptAgent, QaDeptAgent)
from ecosystem_role_registry import (CIRCLE_NAME, EcosystemRoleRegistry)
from game_producer_agent import DEPT_KEY_BY_NAME, GameProducerAgent
from message_bus import MessageBus, build_task_assign
from preset_instantiator import PresetInstantiator
from task_scheduler import Scheduler, Task, TaskState

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
    # 直接显式调用基类 DepartmentAgent.__init__，设置 role_id + department。
    # 不再用 __mro__[1] 硬编码（MRO 变动会静默出错），显式引用更健壮。
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
        self.ecosystem: Optional[EcosystemRoleRegistry] = None  # wp_server/wp_ai_logic
        self.eco_tasks: List[str] = []                # 已派发的生态角色任务 id
        self.ecosystem_handlers = None                # WP-03: 生态 handler 实体（接入则计入 eco_* DONE）

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

        # (a) 注册实例化角色到经理部门能力表（装配来源）。
        # 口径统一：只注册能被 DEPT_AGENT_CLASS 装配出部门 Agent 的角色（六大执行部门），
        # 与下方 Agent 生成完全同源，消除「非六部门角色（如协作支持圈）被注册却无
        # Agent」导致的注册/装配口径漂移（DEPT_KEY_BY_NAME 含 support，而
        # DEPT_AGENT_CLASS 仅六部门）。
        assemblable = [
            r for r in inst.instantiated_roles
            if DEPT_AGENT_CLASS.get((r.get("department") or "").strip())
        ]
        skipped_dept = sorted({
            (r.get("department") or "").strip()
            for r in inst.instantiated_roles if r not in assemblable})
        if skipped_dept:
            self.manager._log("assemble_filter",
                              f"非六部门（无部门 Agent 类）角色不注册不装配: {skipped_dept}")
        self.manager.register_instantiated_team(assemblable)

        # (b) 为每个实例化角色创建对应部门 Agent 并注册到总线。
        # 以 inst.instantiated_roles（单一事实来源）驱动 Agent 生成，与
        # register_instantiated_team 同源，消除「主责未注册 Agent」的隐性耦合。
        for r in assemblable:
            rid = r.get("role_id")
            dept_name = (r.get("department") or "").strip()
            agent_cls = DEPT_AGENT_CLASS.get(dept_name)
            if not rid or agent_cls is None:
                # 部门无法映射时不静默丢弃：明确告警，便于发现装配遗漏
                self.manager._log("assemble_skip",
                                  f"实例化角色 {rid or '(空)'} 部门 '{dept_name}' 无对应 Agent 类，已跳过")
                continue
            agent = _spawn_dept_agent(agent_cls, rid, dept_name, self.bus)
            agent.boot()
            self.team_agents[rid] = agent

        # 指派前校验：每个已注册实例化角色都应有对应总线 Agent，避免出现
        # 「主责被指派但总线上无承接 Agent」导致派单无法被接收的隐性故障。
        missing = sorted(
            rid for rid in self.manager.instantiated_role_ids
            if rid not in self.team_agents)
        if missing:
            self.manager._log("assemble_missing",
                              f"以下实例化角色未装配到总线: {missing}")

        # ---- wp_server / wp_ai_logic：生态角色注册为可派发 Agent ----
        # 把生态角色（玩家圈 / 外部市场圈 / 协作支持圈）注册进 message_bus +
        # task_scheduler，使其作为可派发 owner 真正进入部门流水线派发。
        self.ecosystem = EcosystemRoleRegistry(bus=self.bus).load()
        eco_ids = self.ecosystem.register()
        self.manager._log("ecosystem_register",
                          f"已注册 {len(eco_ids)} 个生态角色到 message_bus（可派发 Agent）")

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
                # 无可推进任务且仍有未完成工作包：输出非 DONE 任务诊断，
                # 避免 BLOCKED/FAILED 静默返回 all_done=False。
                self._log_blocked_tasks()
                self.manager.heartbeat()
                break
        return {"rounds": rounds, "all_done": all_done}

    def _log_blocked_tasks(self):
        """输出所有非 DONE 工作包的状态诊断，定位阻塞/失败原因。

        仅诊断部门工作包流水线任务（带 work_package payload），
        不含生态角色演示派发任务（eco_*，非部门产出）。
        """
        pending = [
            (t.name or t.id, t.state, t.owner)
            for t in self.scheduler.queue.tasks.values()
            if t.state != TaskState.DONE.value and t.payload.get("work_package")
        ]
        if not pending:
            return
        self.manager._log("blocked_diagnose",
                          f"全链路未完成（rounds 耗尽/无可推进），"
                          f"非 DONE 任务 {len(pending)} 个：")
        for name, state, owner in pending:
            self.manager._log("blocked_task",
                              f"  {name} → {state}（owner={owner}）")

    def _all_done(self) -> bool:
        # 部门工作包流水线任务（带 work_package payload）必须全部 DONE。
        #
        # 生态角色任务（eco_*）处理策略（WP-03 实体化改造，Issue #55）：
        #   - 若生态 handler 已接入（self.ecosystem_handlers 非空），则已由 handler
        #     真实承接并 DONE 的 eco_* 计入全链路判定，不再刻意过滤；
        #   - 对仍未承接的 eco_*（无 handler、恒停 TODO）仍过滤，避免阻塞部门流水线，
        #     同时由 role_inventory --gap 护栏持续暴露，作为后续实体化 backlog。
        wp_tasks = [t for t in self.scheduler.queue.tasks.values()
                    if t.payload.get("work_package")]
        base_done = bool(wp_tasks) and all(
            t.state == TaskState.DONE.value for t in wp_tasks)
        if not base_done:
            return False
        # 生态 handler 未接入：不评估 eco_*，保持既有行为
        if getattr(self, "ecosystem_handlers", None) is None:
            return True
        # 生态 handler 已接入：eco_* 应真实 DONE，若有未承接的 eco_* 则不算全链路完成
        eco_tasks = [t for t in self.scheduler.queue.tasks.values()
                     if t.id.startswith("eco_")]
        return all(t.state == TaskState.DONE.value for t in eco_tasks)

    # ---------- 生态角色派发（wp_server / wp_ai_logic / wp_art_direction）----------
    def dispatch_ecosystem(self) -> Dict[str, Any]:
        """把生态角色作为可派发 Agent 接入 task_scheduler + message_bus。

        选取代表性的生态角色（协作支持圈 / 玩家圈 / 外部市场圈 / 美术圈）派发任务，
        证明生态角色已注册为可派发 Agent 并真正进入部门流水线派发。
        """
        if self.ecosystem is None:
            return {"dispatched": 0, "error": "ecosystem 未初始化，先调用 assemble_team"}
        registry = self.ecosystem
        registry.register_scheduler(self.scheduler)

        # WP-03: 接入生态角色承接 handler，让 eco_* 任务真实 DONE（解除"演示性派发"）
        if self.ecosystem_handlers is None:
            from ecosystem_handlers import EcosystemHandler
            self.ecosystem_handlers = EcosystemHandler(self.bus, self.scheduler)

        # 派发三圈代表性生态角色任务
        eco_jobs = [
            # (任务名, owner 生态角色, 优先级)
            ("市场预演派发", "publisher", "HIGH"),
            ("广告变现调优", "advertiser", "NORMAL"),
            ("玩家反馈回收", "core_player", "NORMAL"),
            ("零工负载调度", "gig_pool", "NORMAL"),
            ("进度督导盯守", "progress_pusher", "HIGH"),
        ]
        self.eco_tasks = []
        for name, owner, prio in eco_jobs:
            tid = f"eco_{name}"
            task = Task(id=tid, name=name, owner=owner, priority=prio)
            registry.dispatch(task)
            self.eco_tasks.append(tid)
        # 派发消息经总线 publish
        dispatched = registry.bus.process_all()
        return {
            "dispatched": len(eco_jobs),
            "publish_messages": dispatched,
            "tasks": self.eco_tasks,
        }

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
            # wp_server / wp_ai_logic：生态角色注册为可派发 Agent
            "ecosystem": (self.ecosystem.summary() if self.ecosystem else None),
            "eco_tasks": self.eco_tasks,
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

    # wp_server / wp_ai_logic：生态角色注册为可派发 Agent
    eco = orch.dispatch_ecosystem()
    print("\n[4] 生态角色注册为可派发 Agent（wp_server / wp_ai_logic / wp_art_direction）")
    print(f"    已注册生态角色: {len(orch.ecosystem.roles)} 个（协作支持/玩家/外部市场/美术）")
    print(f"    已派发生态角色任务: {eco['dispatched']} 个 -> {', '.join(orch.eco_tasks)}")
    print(f"    派发消息已 publish 到 message_bus: {eco['publish_messages']} 条")

    print(f"\n[5] 端到端联动结果: all_done = {orch.summary()['all_done']}")
    return orch


if __name__ == "__main__":
    demo()

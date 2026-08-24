# ============================================================
# 游戏向经理 Agent · 可运行实现（GameProducerAgent）
# 版本: v0.1
# 说明: 基于通用内核 agent_core.BaseAgent 落地「制作人/项目经理」岗位，
#       承担"游戏向经理"职责：把架构蓝图拆解为可执行的工作包(Work Package)，
#       按部门分配任务与资源，并通过事件驱动机制自动推进部门间协作。
#
# 机制驱动（非手动 / 命令推进）：
#   - 经理只做"拆解 + 分配 + 资源编排"，把工作包投递给 task_scheduler；
#   - 部门 Agent 完成工作包后发布事件，调度器按依赖自动解锁下游部门；
#   - 上游产出物验收通过后，自动触发下游，形成"生产 → 质检 → 协作 → 验收"
#     的自动流水线，全程无需人工手动推进度。
#
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional

from agent_core import BaseAgent
from message_bus import Message, MessageBus, build_task_assign, build_message
from task_scheduler import Scheduler, Task, TaskState


# ============================================================
# 部门编排模型
# ============================================================

# 游戏开发六大板块及其可承接的工作类型（供经理拆分派单）
DEPARTMENTS = {
    "design":   {"name": "策划线",   "roles": ["lead_designer", "system_designer", "balance_designer", "level_designer"]},
    "program":  {"name": "程序线",   "roles": ["cto", "client_dev", "server_dev", "engine_dev", "ai_programmer", "tools_dev"]},
    "art":      {"name": "美术线",   "roles": ["art_director", "concept_artist", "modeler", "animator", "vfx_artist", "ui_ux", "tech_artist", "audio_designer"]},
    "qa":       {"name": "测试线",   "roles": ["qa_engineer", "auto_qa"]},
    "pm":       {"name": "项目管理", "roles": ["project_manager", "release_manager"]},
    "ops":      {"name": "运营线",   "roles": ["data_analyst", "reference_learner", "game_operator"]},
}

# 架构模块 → 主要承接部门（供经理把架构拆成部门工作包）
ARCHITECTURE_MODULES = {
    "gameplay":        {"department": "design",  "label": "玩法/系统架构"},
    "numeric_model":   {"department": "design",  "label": "数值模型/经济系统"},
    "client":          {"department": "program", "label": "客户端渲染与交互"},
    "server":          {"department": "program", "label": "服务端逻辑与数据"},
    "engine":          {"department": "program", "label": "引擎底层与性能"},
    "ai_logic":        {"department": "program", "label": "游戏AI/NPC行为"},
    "art_direction":   {"department": "art",     "label": "美术风格与资源"},
    "ui_ux":           {"department": "art",     "label": "UI/UX与交互设计"},
    "audio":           {"department": "art",     "label": "音频与配音"},
    "testing":         {"department": "qa",      "label": "功能/性能/自动化测试"},
    "release":         {"department": "pm",      "label": "版本/发版与里程碑"},
    "data_ops":        {"department": "ops",     "label": "数据分析与运营"},
}


# ============================================================
# 游戏向经理状态机（角色 manager 编排）
# ============================================================

# IDLE → INPUT_PENDING → ARCH_DECOMPOSE → WORKSPLIT →
#        RESOURCE_ASSIGN → DISPATCH → TRACK_DEPS → ACCEPT → IDLE
BUSINESS_STATES = [
    "INPUT_PENDING", "ARCH_DECOMPOSE", "WORKSPLIT",
    "RESOURCE_ASSIGN", "DISPATCH", "TRACK_DEPS", "ACCEPT",
]


class GameProducerAgent(BaseAgent):
    """
    游戏向经理 Agent（制作人 + 项目经理 融合实现）。

    核心职责：
      - 接收架构蓝图（愿景/技术架构/里程碑）
      - 把架构拆解为部门可执行的工作包（ARCH_DECOMPOSE → WORKSPLIT）
      - 为每个工作包分配责任部门、角色与资源（RESOURCE_ASSIGN）
      - 通过 task_scheduler 事件驱动派发，按依赖自动推进部门协作（DISPATCH）
      - 跟踪依赖并验收产出，解锁下游（TRACK_DEPS → ACCEPT）

    机制化协同：本实现不依赖任何人工手动推进度 / 手动 / 命令，
    全部通过 message_bus 事件 + task_scheduler 依赖调度自动触发。
    """

    def __init__(self, role_id: str = "game_manager",
                 bus: Optional[MessageBus] = None,
                 scheduler: Optional[Scheduler] = None):
        super().__init__(role_id, bus)
        self.scheduler = scheduler or Scheduler(bus=self.bus)
        self.biz_state = "IDLE"
        self.work_packages: List[Dict[str, Any]] = []   # 已拆分的工作包
        self.accepted: List[str] = []                    # 已验收的部门产出

    # ---------- 覆写 BaseAgent 钩子 ----------
    def on_boot(self):
        """加载架构蓝图库与部门能力基线。"""
        self.knowledge.add_doc("架构蓝图库", {"note": "待拆解的游戏架构蓝图"})
        self.knowledge.add_doc("部门能力表", DEPARTMENTS)
        self.knowledge.add_doc("模块映射表", ARCHITECTURE_MODULES)

    def heartbeat(self):
        """心跳：定期扫描依赖阻塞的工作包（简化：打印当前状态）。"""
        pass

    # ---------- 编排主流程（业务状态机） ----------
    def handle_task(self, msg: Message):
        """处理主业务消息：驱动架构拆解 → 分配 → 派发 → 验收。"""
        if msg.type == "TASK_ASSIGN":
            self._start_orchestration(msg.content.get("architecture", {}))

        elif msg.type == "REVIEW_RESULT":
            self._on_department_delivery(msg.content)

        elif msg.type == "STATUS_REPORT":
            self.reply(msg, "STATUS_REPORT", self.report())

        elif msg.type == "NOTIFICATION":
            self._log("notification", str(msg.content))

    # ---------- 编排各阶段 ----------
    def _start_orchestration(self, architecture: Dict[str, Any]):
        """收到架构蓝图 → 拆解模块 → 拆分工作包 → 分配资源 → 派发。"""
        project = architecture.get("project", "未命名项目")
        modules = architecture.get("modules", list(ARCHITECTURE_MODULES.keys()))
        self.biz_state = "INPUT_PENDING"
        self._log("orchestrate", f"收到架构蓝图: {project}")

        # 1) 架构拆解：把蓝图落到部门模块
        self.biz_state = "ARCH_DECOMPOSE"
        decomposed = self._decompose(project, modules)
        self._log("decompose", f"拆解出 {len(decomposed)} 个部门模块")

        # 2) 拆分工作包：模块 → 部门工作包（含依赖）
        self.biz_state = "WORKSPLIT"
        wps = self._split_work_packages(decomposed)
        self.work_packages = wps
        self._log("worksplit", f"拆分出 {len(wps)} 个工作包")

        # 3) 分配资源：为每个工作包指定责任部门 / 角色 / 资源
        self.biz_state = "RESOURCE_ASSIGN"
        for wp in wps:
            self._assign_resources(wp)
        self._log("resource", "已完成部门资源分配")

        # 4) 事件驱动派发：工作包投递到 task_scheduler，按依赖自动解锁
        self.biz_state = "DISPATCH"
        tasks = self._dispatch(wps)
        self._log("dispatch", f"已派发 {len(tasks)} 个部门任务，等待依赖解锁")

    def _decompose(self, project: str, modules: List[str]) -> List[Dict[str, Any]]:
        """架构拆解：把项目蓝图映射到部门模块清单。"""
        result = []
        for mod in modules:
            if mod in ARCHITECTURE_MODULES:
                result.append({"project": project, "module": mod,
                               **ARCHITECTURE_MODULES[mod]})
        return result

    def _split_work_packages(self, decomposed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """拆分工作包：为每个部门模块生成独立工作包，并建立部门间依赖。"""
        # 依赖规则：程序需要策划先给设计，QA 需要程序/美术产出，发版依赖 QA
        dept_order = {"design": 0, "program": 1, "art": 1, "qa": 2, "pm": 3, "ops": 2}
        wps = []
        for i, mod in enumerate(decomposed):
            dept = mod["department"]
            deps = []
            # 依赖前置部门（同部门内部也按序，形成流水线）
            for prev in decomposed[:i]:
                if dept_order.get(prev["department"], 0) < dept_order.get(dept, 0):
                    deps.append(f"wp_{prev['module']}")
            wps.append({
                "id": f"wp_{mod['module']}",
                "module": mod["module"],
                "label": mod["label"],
                "department": dept,
                "department_name": DEPARTMENTS[dept]["name"],
                "deps": deps,
                "status": "pending",
            })
        return wps

    def _assign_resources(self, wp: Dict[str, Any]):
        """为工作包分配责任角色与资源（人力/优先级/DDL）。"""
        dept_roles = DEPARTMENTS[wp["department"]]["roles"]
        wp["owner"] = dept_roles[0]               # 主责角色
        wp["support"] = dept_roles[1:]            # 协办角色
        wp["resources"] = {
            "cpus": 2, "priority": "NORMAL",
            "budget_share": round(100 / max(1, len(self.work_packages)), 1),
        }

    def _dispatch(self, wps: List[Dict[str, Any]]) -> List[Task]:
        """事件驱动派发：把工作包入队，按依赖自动解锁，并广播派单消息。"""
        tasks = []
        for wp in wps:
            # 建调度任务（带依赖）
            task = Task(name=f"{wp['label']}@{wp['department_name']}",
                        owner=wp["owner"], priority="NORMAL",
                        depends_on=wp["deps"],
                        payload={"work_package": wp})
            self.scheduler.enqueue(task)
            tasks.append(task)
            # 广播派单通知到责任部门
            self.bus.publish(build_message(
                "NOTIFICATION", "game_manager", wp["owner"],
                {"notice": f"分配工作包 {wp['id']} 给 {wp['department_name']}（依赖 {wp['deps']}）"}))
        return tasks

    # ---------- 部门交付回调 ----------
    def _on_department_delivery(self, content: Dict[str, Any]):
        """收到部门产出物验收结果：通过则解锁下游并归档，打回则标记阻塞。"""
        wp_id = content.get("work_package_id")
        if content.get("approved"):
            self.biz_state = "ACCEPT"
            self.accepted.append(wp_id)
            # 完成对应任务，调度器自动解锁依赖它的下游工作包
            for task in self.scheduler.queue.tasks.values():
                if task.payload.get("work_package", {}).get("id") == wp_id:
                    self.scheduler.on_complete(task.id, self.role_id)
            self._log("accept", f"部门产出 {wp_id} 验收通过，自动解锁下游")
            self.biz_state = "IDLE"
        else:
            self.biz_state = "TRACK_DEPS"
            self._log("blocked", f"部门产出 {wp_id} 被打回，阻塞下游待返工")
            self.biz_state = "IDLE"

    # ---------- 汇报 ----------
    def report(self) -> Dict[str, Any]:
        return {
            "agent_id": self.role_id,
            "biz_state": self.biz_state,
            "state": self.state,
            "work_packages": len(self.work_packages),
            "accepted": len(self.accepted),
            "accepted_ids": self.accepted,
            "log_len": len(self.log),
        }


# ============================================================
# 演示
# ============================================================

def demo():
    print("=" * 60)
    print("游戏向经理 Agent (GameProducerAgent) 演示")
    print("  —— 架构拆解 → 部门分配 → 事件驱动派发 → 自动协作验收")
    print("=" * 60)

    bus = MessageBus()
    manager = GameProducerAgent(role_id="game_manager", bus=bus)
    manager.boot()

    # 模拟架构蓝图下发（真实场景由上游架构师 / 制作人提供）
    architecture = {
        "project": "开放世界动作游戏 demo",
        "modules": ["gameplay", "numeric_model", "client", "server",
                    "art_direction", "ui_ux", "testing", "release"],
    }
    msg = build_task_assign("architect", "game_manager", "orch_001",
                            {"architecture": architecture})
    bus.publish(msg)
    bus.process_all()

    print(f"\n处理完成后状态: {manager.state} / biz_state={manager.biz_state}")

    print("\n拆分出的部门工作包:")
    for wp in manager.work_packages:
        print(f"  - {wp['id']:<16} {wp['label']:<14} → {wp['department_name']:<6} "
              f"主责={wp['owner']:<16} 依赖={wp['deps']}")

    print("\n调度队列任务（含部门间依赖）:")
    for t in manager.scheduler.queue.tasks.values():
        print(f"  - {t.name:<24} state={t.state} depends={t.depends_on}")

    print("\n广播到总线上的派单消息数:", len(bus.delivered))
    print("已自动推进的部门数:", len({wp['department'] for wp in manager.work_packages}))

    print("\n经理 Agent 运行日志:")
    for entry in manager.log:
        print(f"  [{entry['event']}] {entry['note']}")


if __name__ == "__main__":
    demo()

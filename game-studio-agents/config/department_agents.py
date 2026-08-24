# ============================================================
# 六部门执行 Agent · 可运行实现（DepartmentAgents）
# 版本: v0.7
# 说明: 基于通用内核 agent_core.BaseAgent 落地六大部门（策划/程序/美术/测试/
#       项目管理/运营）的执行 Agent。让各部门 Agent 真正"接收并执行"被游戏向
#       经理派发的工作包（wp_*），跑通「策划→程序→美术→测试→发版→运营」
#       全链路，验证「验收→解锁下游」闭环。
#
# 机制驱动（与 game_producer_agent 一致，非手动推进）：
#   - 部门 Agent 收到 TASK_ASSIGN 派单后进入执行态，产出部门交付物；
#   - 产出后向经理上报 REVIEW_RESULT（approved/打回）；
#   - 经理验收通过 → 调度器自动解锁依赖该工作包的下游部门；
#   - 收到 rework 返工通知 → 回到执行态重新加工，形成闭环。
#
# 架构对齐：部门角色来自 config/roles.yaml 的 department 字段，
#   经理拆解出的工作包 owner（主责角色，如 lead_designer / cto）即本模块
#   各部门 Agent 的 role_id。一个部门 Agent 可同时承接该部门多个工作包。
#
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from abc import abstractmethod
from typing import Any, Dict, List, Optional

from agent_core import BaseAgent
from message_bus import Message, MessageBus, build_message
from task_scheduler import Scheduler, TaskState


# ============================================================
# 一、部门执行 Agent 基类
# ============================================================

class DepartmentAgent(BaseAgent):
    """
    部门执行 Agent 基类：为六大部门提供统一的工作包执行机制。

    统一职责（由基类实现，子类只需补足"部门业务"）：
      - 接收 TASK_ASSIGN 派单，从 content['payload']['work_package'] 取工作包；
      - 调用子类的部门业务方法执行工作包，产出交付物；
      - 向经理上报 REVIEW_RESULT 验收结果（通过则解锁下游）；
      - 接收 rework 返工通知，重新执行被打回的工作包。

    子类需实现：
      - dept_name()          : 部门中文名
      - execute_work_package : 针对具体模块产出交付物
      - deliverable_type()   : 交付物类型标识
    """

    # 该部门可承接的架构模块（由子类覆写，与 game_producer_agent 的
    # ARCHITECTURE_MODULES 部门归属保持一致）
    MODULES: List[str] = []

    def __init__(self, role_id: str,
                 bus: Optional[MessageBus] = None,
                 scheduler: Optional[Scheduler] = None,
                 manager_role: str = "producer"):
        super().__init__(role_id, bus)
        self.scheduler = scheduler or Scheduler(bus=self.bus)
        self.manager_role = manager_role      # 经理岗位（默认制作人）
        self.biz_state = "IDLE"
        self.deliveries: List[Dict[str, Any]] = []   # 已完成交付物
        self.pending_rework: List[str] = []          # 待返工工作包

    # ---------- 部门抽象接口 ----------
    @abstractmethod
    def dept_name(self) -> str:
        """部门中文名（如 策划线）"""
        raise NotImplementedError

    @abstractmethod
    def execute_work_package(self, wp: Dict[str, Any]) -> Dict[str, Any]:
        """针对一个工作包产出部门交付物。

        wp 结构（来自经理拆解）：
          {id, module, label, department, department_name,
           owner, support, ddl, resources, ...}
        返回交付物 dict（含 work_package_id / artifact 等字段）。
        """
        raise NotImplementedError

    @abstractmethod
    def deliverable_type(self) -> str:
        """交付物类型（如 design_doc / code / art_asset ...）"""
        raise NotImplementedError

    # ---------- 覆写 BaseAgent 钩子 ----------
    def on_boot(self):
        self.knowledge.add_doc("部门档案", {
            "dept": self.dept_name(),
            "modules": self.MODULES,
        })

    def heartbeat(self):
        """心跳：扫描本部门待返工的工作包并督导（简化：日志记录）。"""
        if self.pending_rework:
            self._log("heartbeat", f"本部门待返工 {len(self.pending_rework)} 个工作包: "
                                   f"{','.join(self.pending_rework)}")

    # ---------- 工作包执行主流程 ----------
    def handle_task(self, msg: Message):
        if msg.type == "TASK_ASSIGN":
            self._on_task_assign(msg)

        elif msg.type == "NOTIFICATION":
            # 接收经理的返工/督导通知
            content = msg.content or {}
            if content.get("event") == "rework":
                wp_id = content.get("work_package_id")
                if wp_id and wp_id not in self.pending_rework:
                    self.pending_rework.append(wp_id)
                self.biz_state = "REWORK"
                self._log("rework", f"收到返工通知 {wp_id}: {content.get('reason')}")
            else:
                self._log("notification", str(content))

        elif msg.type == "STATUS_REPORT":
            self.reply(msg, "STATUS_REPORT", self.report())

    def _on_task_assign(self, msg: Message):
        """接收派单：从 payload['work_package'] 取工作包并执行。"""
        content = msg.content or {}
        payload = content.get("payload") or {}
        wp = payload.get("work_package") or {}
        wp_id = wp.get("id") or content.get("task_id", "unknown_wp")

        # 若此前有该工作包的返工记录，进入执行态前先清除
        self.biz_state = "EXECUTING"
        self._transition("EXECUTING")
        self._log("assign", f"部门 {self.dept_name()} 承接工作包 {wp_id} ({wp.get('label')})")

        # 调用子类部门业务执行
        artifact = self.execute_work_package(wp)
        self.deliveries.append({
            "work_package_id": wp_id,
            "module": wp.get("module"),
            "artifact_type": self.deliverable_type(),
            "artifact": artifact,
            "at": __import__("time").time(),
        })
        if wp_id in self.pending_rework:
            self.pending_rework.remove(wp_id)

        # 完成执行 → 交付态
        self._transition("DELIVERING")
        # 向经理上报验收结果（默认 self-check 通过；子类可覆写 quality 判定）
        approved = self._self_verify(artifact, wp)
        self.biz_state = "ACCEPT" if approved else "TRACK_DEPS"
        self.bus.publish(build_message(
            "REVIEW_RESULT", self.role_id, self.manager_role,
            {"work_package_id": wp_id, "approved": approved,
             "reason": "" if approved else "部门自检未达验收标准",
             "deliverable_type": self.deliverable_type(),
             "artifact": artifact,
             "delivery": self.deliveries[-1]}))
        self._log("review", f"{wp_id} 验收上报: {'通过' if approved else '打回'}")

        # 完成对应调度任务（若部门自检通过则完成，否则保留由经理二次裁决）
        if approved and wp_id in self.scheduler.queue.tasks:
            # 部门自检通过 → 通知调度器完成该任务，解锁下游；
            # 由经理最终验收（approved=True）后 on_complete 同样会解锁，
            # 这里先不重复完成，统一交给经理 REVIEW_RESULT 仲裁，保证单一验收口径。
            pass
        self._transition("IDLE")

    def _self_verify(self, artifact: Dict[str, Any], wp: Dict[str, Any]) -> bool:
        """部门自检（子类可覆写）：默认只要产出非空即视为通过。"""
        return bool(artifact)

    # ---------- 汇报 ----------
    def report(self) -> Dict[str, Any]:
        return {
            "agent_id": self.role_id,
            "dept": self.dept_name(),
            "biz_state": self.biz_state,
            "state": self.state,
            "deliveries": len(self.deliveries),
            "pending_rework": self.pending_rework,
            "log_len": len(self.log),
        }


# ============================================================
# 二、六大部门执行 Agent
# ============================================================

class DesignDeptAgent(DepartmentAgent):
    """策划线执行 Agent：主责 lead_designer（承接玩法/系统、数值等设计工作包）"""

    MODULES = ["gameplay", "numeric_model"]

    def dept_name(self) -> str:
        return "策划线"

    def deliverable_type(self) -> str:
        return "design_doc"

    def execute_work_package(self, wp: Dict[str, Any]) -> Dict[str, Any]:
        module = wp.get("module", "")
        project = wp.get("project", "未命名项目")
        if module == "gameplay":
            artifact = {
                "module": "gameplay",
                "title": f"{project} 玩法/系统架构设计",
                "systems": ["核心循环", "系统依赖关系", "模块边界"],
                "doc_type": "系统架构文档",
            }
        elif module == "numeric_model":
            artifact = {
                "module": "numeric_model",
                "title": f"{project} 数值模型/经济系统",
                "curves": ["成长曲线", "产出消耗循环", "平衡基线"],
                "doc_type": "数值设计文档",
            }
        else:
            artifact = {"module": module, "title": f"{project} {wp.get('label')}",
                        "doc_type": "策划设计文档"}
        artifact["work_package_id"] = wp.get("id")
        return artifact


class ProgramDeptAgent(DepartmentAgent):
    """程序线执行 Agent：主责 cto（承接客户端/服务端/引擎/AI 等编码工作包）"""

    MODULES = ["client", "server", "engine", "ai_logic"]

    def dept_name(self) -> str:
        return "程序线"

    def deliverable_type(self) -> str:
        return "code"

    def execute_work_package(self, wp: Dict[str, Any]) -> Dict[str, Any]:
        module = wp.get("module", "")
        project = wp.get("project", "未命名项目")
        artifact = {
            "module": module,
            "title": f"{project} {wp.get('label')} 实现",
            "code_files": [f"{module}/main.py", f"{module}/core.py"],
            "tests": f"{module}/test_{module}.py",
            "build": "ok",
        }
        artifact["work_package_id"] = wp.get("id")
        return artifact


class ArtDeptAgent(DepartmentAgent):
    """美术线执行 Agent：主责 art_director（承接美术风格/UI/音频等工作包）"""

    MODULES = ["art_direction", "ui_ux", "audio"]

    def dept_name(self) -> str:
        return "美术线"

    def deliverable_type(self) -> str:
        return "art_asset"

    def execute_work_package(self, wp: Dict[str, Any]) -> Dict[str, Any]:
        module = wp.get("module", "")
        project = wp.get("project", "未命名项目")
        artifact = {
            "module": module,
            "title": f"{project} {wp.get('label')} 美术资源",
            "assets": [f"{module}/style_guide.png", f"{module}/asset_list.json"],
            "style_spec": "style_spec_v1",
        }
        artifact["work_package_id"] = wp.get("id")
        return artifact


class QADeptAgent(DepartmentAgent):
    """测试线执行 Agent：主责 qa_engineer（承接功能/性能/自动化测试工作包）"""

    MODULES = ["testing"]

    def dept_name(self) -> str:
        return "测试线"

    def deliverable_type(self) -> str:
        return "test_report"

    def execute_work_package(self, wp: Dict[str, Any]) -> Dict[str, Any]:
        project = wp.get("project", "未命名项目")
        artifact = {
            "module": "testing",
            "title": f"{project} 测试报告",
            "cases": 120,
            "passed": 118,
            "bugs": 2,
            "release_ready": True,
        }
        artifact["work_package_id"] = wp.get("id")
        return artifact

    def _self_verify(self, artifact: Dict[str, Any], wp: Dict[str, Any]) -> bool:
        # QA 自检更严格：通过率需达到阈值才放行
        passed = artifact.get("passed", 0)
        total = max(1, artifact.get("cases", 1))
        return passed / total >= 0.9


class PMDeptAgent(DepartmentAgent):
    """项目管理执行 Agent：主责 project_manager（承接版本/发版与里程碑工作包）"""

    MODULES = ["release"]

    def dept_name(self) -> str:
        return "项目管理"

    def deliverable_type(self) -> str:
        return "release_plan"

    def execute_work_package(self, wp: Dict[str, Any]) -> Dict[str, Any]:
        project = wp.get("project", "未命名项目")
        artifact = {
            "module": "release",
            "title": f"{project} 版本/发版计划",
            "milestones": ["垂直切片", "Alpha", "Beta", "软封", "硬封"],
            "gate": "green",
            "release_notes": "release_notes_v1",
        }
        artifact["work_package_id"] = wp.get("id")
        return artifact


class OpsDeptAgent(DepartmentAgent):
    """运营线执行 Agent：主责 data_analyst（承接数据分析与运营工作包）"""

    MODULES = ["data_ops"]

    def dept_name(self) -> str:
        return "运营线"

    def deliverable_type(self) -> str:
        return "data_report"

    def execute_work_package(self, wp: Dict[str, Any]) -> Dict[str, Any]:
        project = wp.get("project", "未命名项目")
        artifact = {
            "module": "data_ops",
            "title": f"{project} 数据分析与运营报告",
            "metrics": ["DAU", "留存", "付费率", "关卡通过率"],
            "insights": ["新手引导流失偏高", "付费转化集中在首周"],
        }
        artifact["work_package_id"] = wp.get("id")
        return artifact


# ============================================================
# 部门 Agent 注册表（按模块 → 部门 Agent 工厂）
# ============================================================

# 模块 → 可承接该模块的部门 Agent 工厂
MODULE_TO_DEPT_AGENT = {
    "gameplay": DesignDeptAgent,
    "numeric_model": DesignDeptAgent,
    "client": ProgramDeptAgent,
    "server": ProgramDeptAgent,
    "engine": ProgramDeptAgent,
    "ai_logic": ProgramDeptAgent,
    "art_direction": ArtDeptAgent,
    "ui_ux": ArtDeptAgent,
    "audio": ArtDeptAgent,
    "testing": QADeptAgent,
    "release": PMDeptAgent,
    "data_ops": OpsDeptAgent,
}


def build_department_agent(module: str, role_id: str, bus: MessageBus,
                           scheduler: Scheduler,
                           manager_role: str = "producer") -> Optional[DepartmentAgent]:
    """按模块构造对应部门的执行 Agent 实例。

    未匹配模块返回 None（不派发执行），避免对未知模块误创建 Agent。
    """
    factory = MODULE_TO_DEPT_AGENT.get(module)
    if factory is None:
        return None
    return factory(role_id=role_id, bus=bus, scheduler=scheduler,
                   manager_role=manager_role)


# ============================================================
# 演示
# ============================================================

def demo():
    print("=" * 60)
    print("六部门执行 Agent (DepartmentAgents) 演示")
    print("  —— 各部门承接工作包并产出交付物")
    print("=" * 60)

    from game_producer_agent import GameProducerAgent
    from message_bus import build_task_assign

    bus = MessageBus()
    sched = Scheduler(bus=bus)
    manager = GameProducerAgent(bus=bus, scheduler=sched)
    manager.boot()

    # 构造一个覆盖六部门的工作包集合，模拟经理派发
    # （复用经理的拆解逻辑生成工作包）
    arch = {"project": "开放世界动作游戏", "modules": [
        "gameplay", "numeric_model", "client", "server",
        "art_direction", "ui_ux", "testing", "release", "data_ops"]}

    # 六个部门各创建一个 Agent 实例（role 唯一，避免同 role 多实例重复消费）
    dept_agents = [
        DesignDeptAgent(role_id="lead_designer", bus=bus, scheduler=sched),
        ProgramDeptAgent(role_id="cto", bus=bus, scheduler=sched),
        ArtDeptAgent(role_id="art_director", bus=bus, scheduler=sched),
        QADeptAgent(role_id="qa_engineer", bus=bus, scheduler=sched),
        PMDeptAgent(role_id="project_manager", bus=bus, scheduler=sched),
        OpsDeptAgent(role_id="data_analyst", bus=bus, scheduler=sched),
    ]
    for a in dept_agents:
        a.boot()

    # 经理拆解并派发（调度器发出 TASK_ASSIGN，部门 Agent 已注册会被正确接收）
    bus.publish(build_task_assign("architect", manager.role_id, "orch_v07",
                                  {"architecture": arch}))
    bus.process_all()

    print(f"\n经理拆分出 {len(manager.work_packages)} 个工作包")

    # 无依赖上游的工作包在经理派发时已被部门 Agent 接收执行；
    # 依赖解锁下游由调度器在经理验收后自动再派发。
    print(f"\n各部门交付物（去重）:")
    delivered = {}
    for m in bus.delivered:
        if m.type == "REVIEW_RESULT":
            cid = m.content.get("work_package_id")
            if cid not in delivered.setdefault(m.from_role, set()):
                delivered[m.from_role].add(cid)
    for role, wps in delivered.items():
        print(f"  - {role:<16} 交付 {len(wps)} 个工作包: {','.join(sorted(wps))}")

    print(f"\n总线上 REVIEW_RESULT 消息数: "
          f"{sum(1 for m in bus.delivered if m.type=='REVIEW_RESULT')}")


if __name__ == "__main__":
    demo()

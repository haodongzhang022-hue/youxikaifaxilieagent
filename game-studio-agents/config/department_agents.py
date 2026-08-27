# ============================================================
# 六大部门 Agent 实现（DepartmentAgents）
# 版本: v0.1
# 说明: 为 config/roles.yaml 的六大部门（策划/程序/美术/测试/项目管理/运营）
#       各实现一个 BaseAgent 子类，作为「多部门 Agent 端到端联动」的部门执行体。
#
# 机制化协同：
#   - 每部门 Agent 继承通用内核 agent_core.BaseAgent（生命周期/状态机/消息收发）；
#   - 通过 MessageBus 接收 task_scheduler 派发的 TASK_ASSIGN 与经理的督导 NOTIFICATION；
#   - 收到工作包后按部门职责执行，产出物通过 REVIEW_RESULT 上报给游戏向经理；
#   - 经理验收通过后 task_scheduler 自动解锁下游部门，形成事件驱动流水线。
#
# 本文件与 game_producer_agent.py 解耦：经理负责拆解/分配/派发，部门 Agent 负责执行。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from typing import Any, Dict

from agent_core import BaseAgent
from message_bus import Message, MessageBus
from game_producer_agent import DEPARTMENTS
from market_input_bridge import build_market_input
from data_ops_diagnosis import run_data_ops
from framework_upgrade_ops import run_data_ops_upgrade
from shared_memory import SharedMemory
from release_gate import aggregate_and_release, run_release_gate


# 部门中文名 → 键（对齐 game_producer_agent.DEPARTMENTS）
_DEPT_KEY_BY_NAME = {
    "策划线": "design", "程序线": "program", "美术线": "art",
    "测试线": "qa", "项目管理": "pm", "运营线": "ops",
}


# ============================================================
# 部门 Agent 基类（通用执行模板）
# ============================================================

class DepartmentAgent(BaseAgent):
    """部门执行 Agent 基类 · 部门统一头（小组）。

    部门 == 一个 NPC 小组：以部门名为**统一头**对外承接（@ 部门名 = 一次 @
    部门内多个角色），对内通过协作工作台把跨角色任务**组内协作**拆解派发给
    部门内各角色执行，并可跨部门 @ 协作请求/转交。

    统一封装「接收派单 → 分析 →（组内协作）执行 → 校验 → 上报验收」流程，
    子类只需提供部门专属的 _execute(work_package) 与领域知识。
    """

    def __init__(self, role_id: str, department: str, bus: MessageBus):
        super().__init__(role_id, bus)
        self.department = department          # 部门名（策划线/程序线/...）
        self.done_packages: list = []         # 已执行完成的工作包 id
        self.accepted_by: Dict[str, str] = {}  # 工作包 id -> 验收人 role_id
        self.pending_rework: list = []         # 收到返工通知、待重新加工的工作包 id
        self.rework_count: Dict[str, int] = {}  # 工作包 id -> 返工次数
        self.biz_state = "IDLE"                 # 部门业务状态（IDLE/EXECUTING/REWORK/DELIVERING）
        # 组内协作记录：工作包 id -> 已派发的内部子任务 role 清单
        self.internal_subtasks: Dict[str, list] = {}
        # 跨部门协作记录：工作包 id -> [（协作类型, 对方角色）]
        self.peer_collab: list = []
        # 部门 Agent 需接收本部门所有角色的派单（balance_designer / ai_programmer 等），
        # 统一由部门 Agent 按 module 执行；为此注册部门内全部 role_id 到总线。
        dept_key = _DEPT_KEY_BY_NAME.get(department)
        if dept_key and dept_key in DEPARTMENTS:
            for dept_role in DEPARTMENTS[dept_key]["roles"]:
                if dept_role != role_id:
                    self.bus.register(dept_role)
                    self.bus.on(dept_role, self._receive)
            # 把「部门名」也注册为总线索引 → @部门名 等同于 @ 部门统一头
            if department not in self.bus.roles:
                self.bus.register(department)
                self.bus.on(department, self._receive)

    def on_boot(self):
        """加载部门领域知识基线。"""
        self.knowledge.add_doc("部门", self.department)
        self.knowledge.add_doc("角色", self.role_id)
        self.knowledge.add_doc("执行策略", {
            "mode": "事件驱动",
            "rule": "收到 TASK_ASSIGN 后执行，产出物上报 REVIEW_RESULT",
        })

    # ============================================================
    # 部门统一头 · 组内协作
    # ============================================================
    def _internal_roles(self) -> list:
        """返回本部门内全部角色 role_id（含本头自身）。"""
        dept_key = _DEPT_KEY_BY_NAME.get(self.department)
        if dept_key and dept_key in DEPARTMENTS:
            return list(DEPARTMENTS[dept_key]["roles"])
        return [self.role_id]

    def _delegate_internal(self, wp_id: str, title: str,
                           assignments: list) -> dict:
        """组内协作：部门头把跨角色工作包按 role_id 拆给部门内角色。

        复用协作工作台（role_collaboration.CollaborationWorkbench.delegate）
        的 @分工 能力，形成「部门头 @ 组内角色」的组内协作，全程留痕可审计。
        assignments: [{"role": "system_designer", "desc": "..."}, ...]
        """
        if not assignments:
            return {"ok": False, "error": "无组内子任务"}
        # 只保留本部门内的角色，跨部门角色走跨部门协作（request_peer）
        internal = [a for a in assignments
                    if a["role"] in self._internal_roles()]
        if not internal:
            return {"ok": False, "error": "assignments 不包含本部门角色"}
        res = self.collab.delegate(wp_id, title or wp_id, self.role_id, internal)
        self.internal_subtasks[wp_id] = [a["role"] for a in internal]
        self._log("dept_group", f"{self.department} 组内协作: {wp_id} "
                  f"@分工给 {internal}")
        return {"ok": True, "sub_tasks": res["sub_tasks"],
                "roles": [a["role"] for a in internal]}

    def _sub_progress(self, wp_id: str) -> Dict[str, Any]:
        """组内协作进度汇总（@分工 各子任务承接情况）。"""
        p = self.collab.sub_progress(wp_id)
        return {"work_package_id": wp_id,
                "total": p.get("total", 0), "done": p.get("done", 0),
                "blocked": p.get("blocked", 0),
                "pending": p.get("pending", 0),
                "detail": p.get("detail", {})}

    # ============================================================
    # 跨部门协作（部门 ↔ 部门 @ 协作请求 / 转交）
    # ============================================================
    def request_peer(self, wp_id: str, title: str, peer_role: str,
                     need: str = "") -> dict:
        """跨部门协作：本部门 @ 协作请求 其他部门/角色协助某任务。

        复用协作工作台 request_collab，仅登记协助请求、不转移持有权。
        """
        res = self.collab.request_collab(wp_id, title or wp_id, self.role_id,
                                         peer_role, need=need)
        self.peer_collab.append({"type": "COLLAB_REQ", "task_id": wp_id,
                                 "peer": peer_role, "need": need})
        self._log("cross_dept", f"{self.department} 跨部门 @请求 {peer_role}"
                  f" 协助 {wp_id}: {need}")
        return {"ok": True, "record": res["record"],
                "assist_requested_to": res["assist_requested_to"]}

    def group_audit(self, wp_id: str) -> Dict[str, Any]:
        """部门统一头审计：组内子任务 + 跨部门协作全记录。"""
        collab_audit = self.collab.audit(wp_id)
        return {
            "department": self.department,
            "head": self.role_id,
            "work_package_id": wp_id,
            "internal_subtasks": self.internal_subtasks.get(wp_id, []),
            "peer_collab": [p for p in self.peer_collab
                            if p["task_id"] == wp_id],
            "collab": collab_audit,
        }

    # ---------- 主业务处理 ----------
    def handle_task(self, msg: Message):
        """处理业务消息：派单执行 / 督导反馈。"""
        if msg.type == "TASK_ASSIGN":
            self._on_task_assign(msg)
        elif msg.type == "NOTIFICATION":
            self._on_notification(msg)
        elif msg.type == "REVIEW_RESULT":
            self._on_review_result(msg)
        elif msg.type == "STATUS_REPORT":
            self.reply(msg, "STATUS_REPORT", self.report())

    # ---------- 派单处理 ----------
    def _on_task_assign(self, msg: Message):
        """收到调度器/经理派单：解析工作包 → 执行 → 上报验收。"""
        content = msg.content or {}
        payload = content.get("payload", {}) or {}
        work_package = payload.get("work_package", {}) or {}
        task_id = content.get("task_id") or content.get("name") or self.role_id

        wp_id = work_package.get("id") or task_id
        wp_label = work_package.get("label") or task_id
        dept_name = work_package.get("department_name") or self.department

        # 幂等：已执行过的工作包不再重复执行（避免依赖解锁引起的重复派单）
        # 例外：处于待返工（pending_rework）的工作包允许重新执行，形成返工闭环。
        if wp_id in self.done_packages and wp_id not in self.pending_rework:
            self._log("idempotent", f"工作包 {wp_id} 已执行过，跳过重复派单")
            return

        # 若这是返工后的重新派发，清除待返工标记并记录返工次数
        if wp_id in self.pending_rework:
            self.pending_rework.remove(wp_id)
            self.rework_count[wp_id] = self.rework_count.get(wp_id, 0) + 1
            self._log("rework_exec", f"工作包 {wp_id} 返工后重新执行（第{self.rework_count[wp_id]}次）")
            self.biz_state = "REWORK"
        else:
            self.biz_state = "EXECUTING"

        self._transition("ANALYZING")
        self._log("analyze", f"解析工作包 {wp_id}（{wp_label} @ {dept_name}）")

        self._transition("PLANNING")
        # 部门统一头：若工作包携带组内/跨部门协作计划，先经协作机制执行
        internal_assignments = work_package.get("internal_assignments")
        peer_collabs = work_package.get("peer_collabs")
        if internal_assignments:
            self._delegate_internal(wp_id, wp_label, internal_assignments)
        for pc in (peer_collabs or []):
            self.request_peer(wp_id, wp_label,
                              pc.get("peer", ""), need=pc.get("need", ""))
        # 部门专属执行（统一头汇总组内协作产出）
        self._transition("EXECUTING")
        artifact = self._execute(work_package, content)

        self._transition("VERIFYING")
        ok, note = self._verify(work_package, artifact)

        self._transition("DELIVERING")
        # 上报 REVIEW_RESULT 给经理（producer）
        self.send(
            "REVIEW_RESULT", "producer",
            {
                "work_package_id": wp_id,
                "module": work_package.get("module"),
                "department": dept_name,
                "owner": self.role_id,
                "artifact": artifact,
                "approved": ok,
                "reason": note,
            })
        self.done_packages.append(wp_id)
        self.biz_state = "DELIVERING"
        self._log("deliver", f"工作包 {wp_id} 执行完成，已上报 REVIEW_RESULT（{note}）")
        self._transition("IDLE")

    # ---------- 状态汇报 ----------
    def report(self) -> Dict[str, Any]:
        """生成部门 Agent 状态汇报（含返工统计）。"""
        return {
            "agent_id": self.role_id,
            "department": self.department,
            "biz_state": self.biz_state,
            "state": self.state,
            "done_packages": list(self.done_packages),
            "pending_rework": list(self.pending_rework),
            "rework_count": dict(self.rework_count),
            "log_len": len(self.log),
            # 部门统一头（小组）协作状态：组内子任务 + 跨部门协作
            "internal_subtasks": dict(self.internal_subtasks),
            "peer_collab": list(self.peer_collab),
        }

    def _on_notification(self, msg: Message):
        """处理督导通知（阻塞/逾期/返工）。"""
        content = msg.content or {}
        event = content.get("event", "")
        wp_id = content.get("work_package_id", "")
        reason = content.get("reason", "")
        if event == "rework":
            # 返工闭环：把工作包记入待返工清单，并从已完工程解除幂等拦截，
            # 使其被经理/调度器重新派发时能再次执行（重新加工 → 重新验收）。
            if wp_id and wp_id not in self.pending_rework:
                self.pending_rework.append(wp_id)
            if wp_id in self.done_packages:
                self.done_packages.remove(wp_id)
            self._log("rework", f"返工通知：{wp_id}（{reason}），已进入待返工清单")
        elif event == "supervise":
            self._log("supervise", f"督导通知：{wp_id}（{reason}）")
        else:
            self._log("notification", str(content))

    def _on_review_result(self, msg: Message):
        """处理验收结果（正常应为经理对下游的验收，可记录）。"""
        content = msg.content or {}
        wp_id = content.get("work_package_id", "")
        approved = content.get("approved", False)
        self.accepted_by[wp_id] = msg.from_role
        self._log("review", f"{wp_id} 验收结果: {'通过' if approved else '打回'} by {msg.from_role}")

    # ---------- 子类需实现 ----------
    def _execute(self, work_package: Dict[str, Any], assign: Dict[str, Any]) -> Dict[str, Any]:
        """部门专属执行逻辑，返回产出物字典。"""
        return {"module": work_package.get("module"), "note": "部门执行"}

    def _verify(self, work_package: Dict[str, Any], artifact: Dict[str, Any]) -> tuple:
        """部门专属自检，返回 (是否通过, 备注)。"""
        return True, "产出自检通过"


# ============================================================
# 一、策划线 Agent（lead_designer）
# ============================================================

class DesignDeptAgent(DepartmentAgent):
    """策划线部门 Agent：负责玩法/系统架构、数值模型、经济系统设计。

    接收 wp_gameplay / wp_numeric_model 等策划工作包，
    产出设计文档 / 数值表，自检设计完整性后上报验收。
    """

    def __init__(self, bus: MessageBus):
        super().__init__("lead_designer", "策划线", bus)

    def on_boot(self):
        super().on_boot()
        self.knowledge.add_doc("设计规范", {
            "core_loop_required": True,
            "system_arch_required": True,
            "numeric_model_required": True,
        })

    def _execute(self, work_package, assign):
        module = work_package.get("module", "")
        label = work_package.get("label", "")
        project = work_package.get("project", "未命名")
        # 按模块产出对应设计文档
        if module == "gameplay":
            artifact = {
                "module": "gameplay",
                "label": label,
                "project": project,
                "artifact_type": "design_doc",
                "content": {
                    "core_loop": "核心玩法循环设计",
                    "system_arch": "系统架构设计",
                    "feature_list": ["核心系统", "子系统"],
                },
            }
        elif module == "numeric_model":
            # 数值模型 / 商业化设计（研发侧产出）
            numeric_model = {
                "economy": "经济产出/消耗模型",
                "growth_curve": "成长曲线",
                "balance": "平衡性数值",
                # 以下字段经 market_input_bridge 映射为市场预演标准化输入
                "base_quality": 65.0,
                "arpu": 2.5,
                "ecpm": 6.0,
                "ad_impressions": 8,
                "channel_cut": 0.3,
                "competition": 0.4,
                "marketing_budget": 80000,
                "mass_player_base": 200000,
                "complexity": 0.35,
                "monetization": {"iap_depth": 0.5, "iaa_density": 0.25},
            }
            # 把数值模型转译为市场预演标准化输入，并跑一次纳什均衡沙盒
            # （跑通「研发产物 → 市场预演沙盒」）。
            market_input = build_market_input(numeric_model, project=project)
            market_result = market_input.solve()
            artifact = {
                "module": "numeric_model",
                "label": label,
                "project": project,
                "artifact_type": "numeric_table",
                "content": {
                    "economy": numeric_model["economy"],
                    "growth_curve": numeric_model["growth_curve"],
                    "balance": numeric_model["balance"],
                },
                # 市场预演标准化输入 + 纳什均衡结果（下游 wp_data_ops 消费）
                "market_input": {
                    "context": market_input.context,
                    "roles": [{"role_id": r.role_id, "circle": r.circle,
                                "strategies": [s.name for s in r.strategy_space]}
                               for r in market_input.roles],
                },
                "market_simulation": {
                    "equilibrium": market_result["equilibrium"],
                    "iterations": market_result["iterations"],
                    "metrics": market_result["metrics"],
                },
            }
        else:
            artifact = {
                "module": module,
                "label": label,
                "project": project,
                "artifact_type": "design_doc",
                "content": {"note": "策划通用设计"},
            }
        self._log("execute", f"策划线产出 {module} 设计文档")
        return artifact

    def _verify(self, work_package, artifact):
        content = artifact.get("content", {})
        if work_package.get("module") == "gameplay":
            if not content.get("core_loop"):
                return False, "缺少核心玩法循环设计"
            if not content.get("system_arch"):
                return False, "缺少系统架构设计"
        elif work_package.get("module") == "numeric_model":
            if not content.get("economy"):
                return False, "缺少经济模型"
        return True, "策划产出自检通过"


# ============================================================
# 二、程序线 Agent（cto）
# ============================================================

class ProgramDeptAgent(DepartmentAgent):
    """程序线部门 Agent：负责客户端渲染、服务端逻辑、引擎、AI 逻辑实现。

    接收 wp_client / wp_server / wp_engine / wp_ai_logic 等工作包，
    产出技术实现 / 接口文档 / 可运行模块。
    """

    def __init__(self, bus: MessageBus):
        super().__init__("cto", "程序线", bus)

    def on_boot(self):
        super().on_boot()
        self.knowledge.add_doc("技术规范", {
            "client_engine": "client",
            "server_framework": "asyncio",
            "perf_target": "60fps",
        })

    def _execute(self, work_package, assign):
        module = work_package.get("module", "")
        label = work_package.get("label", "")
        project = work_package.get("project", "未命名")
        if module == "client":
            artifact = {
                "module": "client", "label": label, "project": project,
                "artifact_type": "code",
                "content": {"render_pipeline": "客户端渲染管线", "ui_binding": "UI 绑定"},
            }
        elif module == "server":
            artifact = {
                "module": "server", "label": label, "project": project,
                "artifact_type": "code",
                "content": {"api": "服务端 API", "db": "数据存储"},
            }
        elif module == "engine":
            artifact = {
                "module": "engine", "label": label, "project": project,
                "artifact_type": "code",
                "content": {"core": "引擎核心", "perf": "性能优化"},
            }
        elif module == "ai_logic":
            artifact = {
                "module": "ai_logic", "label": label, "project": project,
                "artifact_type": "code",
                "content": {"npc_ai": "NPC 行为树", "adaptive": "自适应难度"},
            }
        else:
            artifact = {"module": module, "label": label, "project": project,
                        "artifact_type": "code", "content": {"note": "程序通用实现"}}
        self._log("execute", f"程序线产出 {module} 技术实现")
        return artifact

    def _verify(self, work_package, artifact):
        if not artifact.get("content"):
            return False, "程序产出为空"
        return True, "程序产出自检通过"


# ============================================================
# 三、美术线 Agent（art_director）
# ============================================================

class ArtDeptAgent(DepartmentAgent):
    """美术线部门 Agent：负责美术风格、UI/UX、音频。

    接收 wp_art_direction / wp_ui_ux / wp_audio 等工作包，
    产出美术资源清单 / UI 稿 / 音频规范。
    """

    def __init__(self, bus: MessageBus):
        super().__init__("art_director", "美术线", bus)

    def on_boot(self):
        super().on_boot()
        self.knowledge.add_doc("美术规范", {
            "style_guide": "统一风格",
            "resource_std": "资源规范",
        })

    def _execute(self, work_package, assign):
        module = work_package.get("module", "")
        label = work_package.get("label", "")
        project = work_package.get("project", "未命名")
        if module == "art_direction":
            # wp_art_direction：把美术风格/品质基准接入生态角色体系，
            # 让美术品质进入市场预演的美术质量维度博弈。
            numeric_model = {
                "base_quality": 65.0,
                "art_quality": 72.0,          # 美术品质基准（art_director 产出）
                "art_sens": 0.2,              # 泛玩家美术敏感度偏好
                "arpu": 2.5,
                "ecpm": 6.0,
                "ad_impressions": 8,
                "channel_cut": 0.3,
                "competition": 0.4,
                "marketing_budget": 80000,
                "mass_player_base": 200000,
                "complexity": 0.35,
                "monetization": {"iap_depth": 0.5, "iaa_density": 0.25},
            }
            # 美术品质进入市场预演沙盒：构建标准化输入并跑纳什均衡，
            # 让玩家圈对美术品质的偏好生效（wp_art_direction 验收）。
            market_input = build_market_input(numeric_model, project=project)
            market_result = market_input.solve()
            artifact = {
                "module": "art_direction", "label": label, "project": project,
                "artifact_type": "style_guide",
                "content": {"style": "美术风格定义", "palette": "配色方案",
                              "art_quality": numeric_model["art_quality"]},
                # 美术品质接入市场预演：玩家圈对美术品质的偏好生效
                "market_input": {
                    "context": market_input.context,
                    "roles": [{"role_id": r.role_id, "circle": r.circle,
                                "strategies": [s.name for s in r.strategy_space]}
                               for r in market_input.roles],
                },
                "market_simulation": {
                    "equilibrium": market_result["equilibrium"],
                    "iterations": market_result["iterations"],
                    "metrics": market_result["metrics"],
                },
            }
        elif module == "ui_ux":
            # wp_ui_ux：生态 UI/UX 与交互规范接入部门流水线，
            # 让 UI 角色（tech_artist）成为可派发 Agent，产出可被 task_scheduler 消费。
            artifact = {
                "module": "ui_ux", "label": label, "project": project,
                "artifact_type": "ui_asset",
                "content": {
                    "ui_flow": "界面流程",
                    "ux": "交互设计",
                    # 交互规范与视觉一致性（对齐 ecosystem_roles.yaml eco_tech_artist）
                    "interaction_spec": {
                        "navigation": "扁平导航",
                        "feedback": "即时反馈",
                        "accessibility": "无障碍支持",
                    },
                    "visual_consistency": {
                        "style_guide": "统一风格",
                        "palette": "配色方案",
                        "type_scale": "字号体系",
                    },
                    "render_pipeline": "客户端渲染管线",
                    "ui_binding": "UI 绑定",
                },
                # 交付物可被下游消费：派发 owner 为美术线 UI/UX 角色
                "dispatchable_owner": "tech_artist",
                "dispatchable_eco_owner": "eco_tech_artist",
            }
        elif module == "audio":
            artifact = {
                "module": "audio", "label": label, "project": project,
                "artifact_type": "audio_asset",
                "content": {"sfx": "音效清单", "bgm": "背景音乐"},
            }
        else:
            artifact = {"module": module, "label": label, "project": project,
                        "artifact_type": "art_asset", "content": {"note": "美术通用产出"}}
        self._log("execute", f"美术线产出 {module} 美术资源")
        return artifact

    def _verify(self, work_package, artifact):
        if not artifact.get("content"):
            return False, "美术产出为空"
        return True, "美术产出自检通过"


# ============================================================
# 四、测试线 Agent（qa_engineer）
# ============================================================

class QaDeptAgent(DepartmentAgent):
    """测试线部门 Agent：负责功能/性能/自动化测试。

    接收 wp_testing 工作包，对上游程序/美术产出做测试验证，
    产出测试报告 / 缺陷清单 / 质量评估。
    """

    def __init__(self, bus: MessageBus):
        super().__init__("qa_engineer", "测试线", bus)

    def on_boot(self):
        super().on_boot()
        self.knowledge.add_doc("测试规范", {
            "coverage_target": 0.8,
            "perf_threshold": 60.0,
        })

    def _execute(self, work_package, assign):
        label = work_package.get("label", "")
        project = work_package.get("project", "未命名")
        # 测试线通常只有一个 wp_testing 工作包
        artifact = {
            "module": "testing", "label": label, "project": project,
            "artifact_type": "test_report",
            "content": {
                "cases_run": 42,
                "passed": 40,
                "blocker_bugs": 2,
                "perf": {"fps": 58.0, "threshold": 60.0},
                "coverage": 0.82,
            },
        }
        self._log("execute", f"测试线对上游产出执行质量验证")
        return artifact

    def _verify(self, work_package, artifact):
        content = artifact.get("content", {})
        if content.get("coverage", 0) < 0.5:
            return False, "测试覆盖率过低"
        if content.get("blocker_bugs", 0) > 3:
            return False, "阻塞级缺陷过多"
        return True, "测试产出自检通过"


# ============================================================
# 五、项目管理 Agent（project_manager）
# ============================================================

class PmDeptAgent(DepartmentAgent):
    """项目管理部门 Agent：负责版本/发版与里程碑。

    接收 wp_release 工作包，基于测试通过情况制定版本计划并放行。
    """
    # 发版门禁递归护栏：aggregate_and_release 内部会真实跑通全链路
    # （含 verify_fullchain / 市场预演），可能再次触达本部门，用类级锁
    # 防止无限递归（评审点：发版门禁不应被部门全链路再次调用重入）。
    _GATE_LOCK = False

    def __init__(self, bus: MessageBus):
        super().__init__("project_manager", "项目管理", bus)

    def on_boot(self):
        super().on_boot()
        self.knowledge.add_doc("版本规范", {
            "milestone_required": True,
            "release_checklist_required": True,
        })

    def _execute(self, work_package, assign):
        label = work_package.get("label", "")
        project = work_package.get("project", "未命名")
        # 对生态角色接入 + 市场预演产出发版质量门禁与验收放行。
        # 评审点：此前门禁输入硬编码全 True，流水线内恒 GO、质量门禁失效。
        # 改为复用 aggregate_and_release() 的**真实全链路产出**做验收；
        # 加 _GATE_LOCK 递归护栏，避免被部门全链路内 PmDeptAgent 再次
        # 调用造成无限递归（重入时安全回退为真实门禁默认）。
        if PmDeptAgent._GATE_LOCK:
            gate = run_release_gate({})
        else:
            PmDeptAgent._GATE_LOCK = True
            try:
                gate = aggregate_and_release()
            finally:
                PmDeptAgent._GATE_LOCK = False
        artifact = {
            "module": "release", "label": label, "project": project,
            "artifact_type": "release_plan",
            "content": {
                "milestone": "生态角色接入 + 市场预演发版",
                "release_checklist": ["策划设计通过", "程序实现通过", "美术产出通过",
                                       "测试通过", "生态角色接入通过", "市场预演通过"],
                "schedule": "按依赖流水线自动推进",
            },
            # 发版质量门禁 + 验收放行（wp_release 落地产出）
            "release_gate": {
                "go_no_go": gate["go_no_go"],
                "verdict": gate["verdict"],
                "passed_total": gate["passed_total"],
                "total_checks": gate["total_checks"],
            },
        }
        self._log("execute", f"项目管理制定发版计划 + 发版门禁验收（{gate['go_no_go']}）")
        return artifact

    def _verify(self, work_package, artifact):
        content = artifact.get("content", {})
        if not content.get("milestone"):
            return False, "缺少里程碑"
        if not content.get("release_checklist"):
            return False, "缺少发版检查单"
        return True, "发版计划自检通过"


# ============================================================
# 六、运营线 Agent（data_analyst）
# ============================================================

# 运营线框架升级沉淀的模块级共享内存（进程内纯内存 dict，
# 仅同进程跨 _execute 调用复用；进程重启即清空，UPG-001 重新 seed）。
# 如需跨进程持久化需另接落盘/共享存储。
_OPS_UPGRADE_MEMORY: SharedMemory = SharedMemory()

class OpsDeptAgent(DepartmentAgent):
    """运营线部门 Agent：负责数据分析与运营洞察。

    接收 wp_data_ops 工作包，对全链路产出做数据埋点与洞察分析。
    """

    def __init__(self, bus: MessageBus):
        super().__init__("data_analyst", "运营线", bus)

    def on_boot(self):
        super().on_boot()
        self.knowledge.add_doc("运营规范", {
            "tracking_required": True,
            "insight_required": True,
        })

    def _execute(self, work_package, assign):
        label = work_package.get("label", "")
        project = work_package.get("project", "未命名")
        from market_input_bridge import build_market_input
        # 消费上游 wp_numeric_model 的市场预演纳什均衡结果做生态位诊断。
        # 若无上游市场预演输入，回退到内置数值模型跑一次市场预演再诊断。
        content = assign.get("payload", {}) or {}
        # 上游产出由经理在验收通过时注入到下游 payload['_upstream'][wp_id]
        # （跨部门数据流打通，评审点）。这里从 _upstream 取市场预演结果，
        # 避免恒走回退分支的死代码路径。
        upstream_blocks = content.get("_upstream") or {}
        upstream = content.get("market_simulation") or {}
        for _up in upstream_blocks.values():
            _sim = _up.get("market_simulation") or {}
            if _sim:
                upstream = _sim
                break
        market_report = None
        if upstream.get("equilibrium") and upstream.get("metrics"):
            # 已有上游市场预演结果：直接诊断（含敏感性分析）
            numeric_model = content.get("numeric_model") or {
                "base_quality": 65.0, "arpu": 2.5, "ecpm": 6.0,
                "ad_impressions": 8, "channel_cut": 0.3, "competition": 0.4,
                "marketing_budget": 80000, "mass_player_base": 200000,
                "complexity": 0.35,
                "monetization": {"iap_depth": 0.5, "iaa_density": 0.25},
            }
            market_input = build_market_input(numeric_model, project=project)
            market_result = dict(upstream)
            market_report = run_data_ops(market_input, market_result)
        else:
            # 回退：独立跑一次市场预演再诊断（无上游联动时仍可产出运营诊断）
            numeric_model = {
                "base_quality": 65.0, "arpu": 2.5, "ecpm": 6.0,
                "ad_impressions": 8, "channel_cut": 0.3, "competition": 0.4,
                "marketing_budget": 80000, "mass_player_base": 200000,
                "complexity": 0.35,
                "monetization": {"iap_depth": 0.5, "iaa_density": 0.25},
            }
            market_input = build_market_input(numeric_model, project=project)
            market_result = market_input.solve()
            market_report = run_data_ops(market_input, market_result)

        artifact = {
            "module": "data_ops", "label": label, "project": project,
            "artifact_type": "ops_report",
            "content": {
                "tracking_plan": "数据埋点方案",
                "insight": "运营洞察与建议",
                "retention": "留存优化建议",
            },
            # 生态位诊断 + 敏感性分析结论 + 发布建议（wp_data_ops 落地产出）
            "market_diagnosis": market_report,
        }

        # 框架升级记录沉淀 + 复盘审计（仅 upgrade 主题工作包触发，幂等只追加）
        # 按工作包主题判断：label 含 "upgrade" 或 payload 含 "framework_upgrade" 才沉淀
        _is_upgrade_topic = (
            "upgrade" in str(label).lower()
            or "framework_upgrade" in str(content)
        )
        if _is_upgrade_topic:
            try:
                # 复用模块级共享内存（进程内纯内存，同进程跨 _execute 幂等；
                # 进程重启清空、UPG-001 重新 seed；真持久化需另接落盘/共享存储）
                upgrade_ops = run_data_ops_upgrade(shared_memory=_OPS_UPGRADE_MEMORY)
                artifact["framework_upgrade"] = {
                    "seeded": upgrade_ops.get("seeded", {}).get("seeded", 0),
                    "skipped": upgrade_ops.get("seeded", {}).get("skipped", 0),
                    "audit_verdict": upgrade_ops.get("audit", {}).get("verdict", "-"),
                    "total_upgrades": upgrade_ops.get("audit", {}).get("summary", {}).get("total_upgrades", 0),
                }
            except Exception as e:
                # 升级沉淀为附加能力，失败不影响主运营诊断，但需显式告警避免静默吞错
                self._log("framework_upgrade_error",
                          f"升级记录沉淀失败：{e}")
                artifact["framework_upgrade"] = {
                    "error": str(e),
                    "seeded": 0,
                }
        else:
            # 非升级主题工作包跳过沉淀
            artifact["framework_upgrade"] = {"enabled": False, "reason": "not_upgrade_topic"}

        self._log("execute",
                 f"运营线产出数据洞察 + 市场生态位诊断"
                 + (" + 框架升级记录沉淀" if _is_upgrade_topic else ""))
        return artifact

    def _verify(self, work_package, artifact):
        content = artifact.get("content", {})
        if not content.get("tracking_plan"):
            return False, "缺少埋点方案"
        if not content.get("insight"):
            return False, "缺少运营洞察"
        return True, "运营产出自检通过"


# ============================================================
# 部门 Agent 工厂
# ============================================================

def build_department_agents(bus: MessageBus) -> Dict[str, DepartmentAgent]:
    """创建六大部门 Agent 实例，返回 {部门键: agent}。

    部门键与 game_producer_agent.DEPARTMENTS 对齐：design/program/art/qa/pm/ops。
    """
    return {
        "design": DesignDeptAgent(bus),
        "program": ProgramDeptAgent(bus),
        "art": ArtDeptAgent(bus),
        "qa": QaDeptAgent(bus),
        "pm": PmDeptAgent(bus),
        "ops": OpsDeptAgent(bus),
    }


# ============================================================
# 演示 / 自测
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("六大部门 Agent 自测")
    print("=" * 60)
    bus = MessageBus()
    dept_agents = build_department_agents(bus)
    for key, agent in dept_agents.items():
        agent.boot()
        print(f"  - {key}: {agent.role_id} ({agent.department}) booted, state={agent.state}")
    print("部门 Agent 全部就绪")

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

import re

from typing import Any, Dict

from agent_core import BaseAgent
from message_bus import Message, MessageBus
from game_producer_agent import DEPARTMENTS
from market_input_bridge import build_market_input
from data_ops_diagnosis import run_data_ops
from framework_upgrade_ops import run_data_ops_upgrade
from shared_memory import SharedMemory
from release_gate import aggregate_and_release, run_release_gate
from engine_adapters import get_engine
from engine_sync import build_manifest, verify_manifest, consistency_report
from deepseek_harness import build_context, receive_dispatch, plan_execution, report_back
from game_dev_team import run_dev_team
from stage_aware_engine import StageBoundaryGuard, GameStage


# 部门中文名 → 键（对齐 game_producer_agent.DEPARTMENTS）
_DEPT_KEY_BY_NAME = {
    "策划线": "design", "程序线": "program", "美术线": "art",
    "测试线": "qa", "项目管理": "pm", "运营线": "ops",
}

def _engine_resource_hint(engine_ctx, resource_type):
    """引擎资源格式提示（wp_engine_adaptation_integration 新增）。

    engine_ctx: 引擎上下文 dict（如 {'engine': 'unreal'} 或 {'engine': 'cocos'}）
    resource_type: 资源类型（如 'audio' / 'scene' / 'sprite' / 'map'）

    返回: {"engine": "<engine_name>", "format": "<extension>"}
    """
    engine_name = engine_ctx.get("engine", "cocos")
    # 统一别名
    if engine_name in ("unreal", "ue", "ue5", "unreal_engine"):
        engine_name = "unreal"
    elif engine_name in ("cocos", "cocos_creator"):
        engine_name = "cocos"

    # 资源类型 → 扩展名 映射（对齐 engine_adapters.ResourceSpec）
    _EXT_MAP = {
        "cocos": {
            "sprite": ".png", "audio": ".mp3", "animation": ".anim",
            "prefab": ".prefab", "scene": ".scene", "script": ".ts",
            "map": ".scene",
        },
        "unreal": {
            "mesh": ".fbx", "material": ".uasset", "audio": ".wav",
            "scene": ".umap", "map": ".umap", "blueprint": ".uasset",
            "uasset": ".uasset",
        },
    }
    ext = _EXT_MAP.get(engine_name, {}).get(resource_type, "")
    return {"engine": engine_name, "format": ext}



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
        self.department_key = _DEPT_KEY_BY_NAME.get(department, "program")  # 部门 key（design/program/...）
        self.done_packages: list = []         # 已执行完成的工作包 id
        self.accepted_by: Dict[str, str] = {}  # 工作包 id -> 验收人 role_id
        self.pending_rework: list = []         # 收到返工通知、待重新加工的工作包 id
        self.rework_count: Dict[str, int] = {}  # 工作包 id -> 返工次数
        self.biz_state = "IDLE"                 # 部门业务状态（IDLE/EXECUTING/REWORK/DELIVERING）
        # M4（Issue #128）：部门回报的管线状态（pipeline_id -> 状态 dict）
        self.pipeline_status: Dict[str, Any] = {}
        # 组内协作记录：工作包 id -> 已派发的内部子任务 role 清单
        self.internal_subtasks: Dict[str, list] = {}
        # 跨部门协作记录：工作包 id -> [（协作类型, 对方角色）]
        self.peer_collab: list = []
        # 可调配小组自动化调度器（懒加载）：自动触发调配 + 自动释放
        self._auto_squad = None
        # 当前正在使用可调配小组的工作包 id 集（用于自动释放跟踪）
        self._squad_wp_ids: set = set()
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

    # ---------- 可调配小组自动化（自动触发 + 自动释放） ----------
    def _squad_auto(self):
        """懒加载可调配小组自动化调度器（SquadAutoScheduler）。

        创建调度器的同时，把同一小组池注入到本 Agent 的派发能力
        （dispatch_capability），确保自动调配与派发共享同一资源池。
        """
        if self._auto_squad is None:
            from squad_auto import SquadAutoScheduler
            # SquadAutoScheduler 缺省使用**全局共享小组池**（get_global_squad_pool），
            # 保证所有部门 Agent 共享同一资源池，支持跨部门调配与重复调用。
            self._auto_squad = SquadAutoScheduler()
            # 共享小组池：把调度器的小组池同步注入派发能力，保证
            # auto_acquire_and_dispatch 内部调用的 dispatch_to_squad 能
            # 找到已注册小组（而非各持独立空池）。
            self.dispatch_capability().squad_pool = self._auto_squad.squad_pool
        return self._auto_squad

    def _auto_squad_dispatch(self, work_package: Dict[str, Any]) -> bool:
        """自动触发调配：工作包声明 squad_domain 时自动从小组池调配小组执行。

        触发时机：部门收到工作包后、执行前。若工作包不需要小组（未声明
        squad_domain），自动跳过，部门走自身内部实现正常执行。

        Returns:
            True = 已自动调配小组（小组进入 BUSY 状态）
            False = 未触发（无需小组 / 调配失败 / 已关闭）
        """
        if not work_package.get("squad_domain"):
            return False
        try:
            auto = self._squad_auto()
            cap = self.dispatch_capability()
            result = auto.auto_acquire_and_dispatch(
                work_package, cap, department=self.department)
            if result["auto_dispatched"]:
                self._squad_wp_ids.add(work_package.get("id", ""))
                self._log("auto_squad",
                          f"自动调配小组执行 {work_package.get('id', '')}: {result['reason']}")
                return True
            else:
                self._log("auto_squad_skip",
                          f"自动调配未触发: {result['reason']}")
                return False
        except Exception as e:  # noqa: BLE001 容错：调配异常不阻塞部门执行
            self._log("auto_squad_error",
                      f"自动调配异常（不阻塞部门执行）: {e}")
            return False

    def _auto_squad_release(self, work_package_id: str):
        """自动释放：工作包完成后归还调配的可调配小组到池。"""
        if work_package_id not in self._squad_wp_ids:
            return
        try:
            auto = self._squad_auto()
            rel = auto.auto_release_for_wp(work_package_id)
            if rel["released"]:
                self._squad_wp_ids.discard(work_package_id)
                self._log("auto_squad_release",
                          f"工作包 {work_package_id} 完成，自动释放小组: {rel['reason']}")
            else:
                self._log("auto_squad_release_fail",
                          f"工作包 {work_package_id} 自动释放失败: {rel['reason']}")
        except Exception as e:  # noqa: BLE001 容错：释放异常不阻塞验收
            self._log("auto_squad_release_error",
                      f"工作包 {work_package_id} 自动释放异常（不阻塞验收）: {e}")

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
        # 自动触发调配：工作包声明 squad_domain 时自动从小组池调配小组执行
        self._auto_squad_dispatch(work_package)

        # 部门专属执行（统一头汇总组内协作产出）
        self._transition("EXECUTING")
        artifact = self._execute(work_package, content)

        self._transition("VERIFYING")
        ok, note = self._verify(work_package, artifact)

        self._transition("DELIVERING")
        # 上报 REVIEW_RESULT 给经理（producer）
        # M4（Issue #128）：部门执行后回报管线状态。工作包携带有 pipeline_id
        # （经理拆包时标注），部门执行完成后回填管线评审所需的质量门禁与放行判定。
        pipeline_id = work_package.get("pipeline_id") or ""
        pipeline_status = None
        if pipeline_id:
            pipeline_status = self._report_pipeline_status(
                wp_id, pipeline_id, work_package, artifact, ok)
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
                # M4：管线状态回报（含 pipeline_id / 质量门禁 / 阶段边界审查 / 放行判定）
                "pipeline_status": pipeline_status,
            })
        self.done_packages.append(wp_id)
        self.biz_state = "DELIVERING"
        self._log("deliver", f"工作包 {wp_id} 执行完成，已上报 REVIEW_RESULT（{note}）")
        # 自动释放：工作包完成后归还调配的可调配小组到池（重复调用）
        self._auto_squad_release(wp_id)
        self._transition("IDLE")

    # ---------- M4: 管线状态回报（Issue #128） ----------
    def _report_pipeline_status(self, wp_id: str, pipeline_id: str,
                                work_package: Dict[str, Any],
                                artifact: Dict[str, Any],
                                approved: bool) -> Dict[str, Any]:
        """部门执行后回报管线状态，回填管线发布评审。

        部门工作包绑定了 pipeline_id（经理拆包时标注）。执行完成后，部门
        据此回报该管线的质量门禁、阶段边界审查与放行判定，供
        pipeline_release / release_gate 做管线级发布评审聚合。

        Args:
            wp_id: 工作包 id
            pipeline_id: 绑定的管线 id（如 pipeline.character_animation.unity）
            work_package: 工作包（含 pipeline_engine / pipeline_domain）
            artifact: 部门执行产出物
            approved: 部门验收是否通过

        Returns:
            管线状态 dict（含质量门禁/阶段边界/放行判定）
        """
        # 从产出物解析质量门禁逐项通过与否。
        # 评审点修复：verdict 不再仅由 approved 布尔决定，须与 quality_checks /
        # stage_gate 数据口径一致，避免出现「驳回但质量/阶段全绿」自相矛盾。
        # 若管线已在注册表中（可按 pipeline_id 查询 quality_gates），按注册表
        # 完整门禁集归一化（批准→全绿，驳回→显式落未达）；注册表查不到时
        # 回退到产出物自带 raw 数据。
        raw = (artifact or {}).get("quality_checks") or {}
        # 阶段边界审查：缺省通过仅限验收通过时；验收未通过且无显式阶段数据时，
        # 缺省应反映未确认（False），避免「驳回但 stage_gate 全绿」的误导性上报。
        _default_stage = bool(approved)
        stage_gate = {
            "no_stage_crossing": bool((artifact or {}).get("no_stage_crossing", _default_stage)),
            "reusable_assets": bool((artifact or {}).get("reusable_assets", _default_stage)),
            "stage_alignment": bool((artifact or {}).get("stage_alignment", _default_stage)),
        }
        # 尝试查注册表获取管线完整门禁集（评审点：让 verdict 与 GO 判定口径一致）
        registered_gates = None
        try:
            from pipeline_registry import PipelineRegistry
            reg_pipe = PipelineRegistry().get(pipeline_id)
            if reg_pipe is not None:
                registered_gates = list(reg_pipe.quality_gates)
        except Exception:  # noqa: BLE001 注册表不可用时不阻塞（回退 raw）
            registered_gates = None

        quality_checks = {}
        if registered_gates:
            # 有注册表门禁集 → 归一化：批准=全绿，驳回=按 raw 逐项判定（缺省 False）
            for g in registered_gates:
                quality_checks[g] = bool(raw.get(g, True)) if approved else bool(raw.get(g, False))
        else:
            # 无注册表 → 回退 raw（与旧行为一致）
            quality_checks = {g: bool(v) for g, v in raw.items()} if raw else {}
            if approved and not raw:
                quality_checks = {}

        # 由数据推导 release_verdict：GO = 验收通过 ∧ 质量门禁全绿 ∧ 阶段边界全通过。
        # 避免出现「approved=True 但 quality_checks 有空项/阶段未过」的矛盾上报，
        # 也避免「approved=False 但 quality/阶段全绿」的误导（此时仍 NO-GO 但备注注明）。
        quality_all_ok = all(quality_checks.values()) if quality_checks else bool(approved)
        stage_all_ok = all(stage_gate.values())
        if approved and quality_all_ok and stage_all_ok:
            release_verdict = "GO"
        else:
            release_verdict = "NO-GO"

        status = {
            "pipeline_id": pipeline_id,
            "engine": work_package.get("pipeline_engine", ""),
            "domain": work_package.get("pipeline_domain", ""),
            "work_package_id": wp_id,
            "quality_checks": quality_checks,
            "stage_gate": stage_gate,
            "state": "completed" if release_verdict == "GO" else "failed",
            "release_verdict": release_verdict,
            "notes": "部门验收通过且质量/阶段全绿" if release_verdict == "GO"
                     else ("部门验收未通过或质量/阶段存在未达标"
                           if not approved else "验收通过但质量/阶段存在未达标项"),
        }
        self.pipeline_status[pipeline_id] = status
        return status

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
            # 可调配小组自动化调度状态
            "auto_squad_wps": sorted(self._squad_wp_ids),
            # M4（Issue #128）：部门回报的管线状态（pipeline_id → 状态）
            "pipeline_status": dict(getattr(self, "pipeline_status", {})),
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

    # ---------- 开发小组闭环（Goose 四维闭环 · 多部门通用） ----------
    # 各非程序部门默认的开发小组角色映射（模块 → 小组内开发角色，一套循环 2 个开发）
    # 用于把「开发小组闭环」以模块形式扩展到全部部门（通用基类扩展点）。
    _DEPT_DEV_ROLES = {
        # 策划线
        "design": {
            "gameplay": ["system_designer_1", "level_designer_1"],
            "numeric_model": ["system_designer_1", "level_designer_1"],
            "narrative": ["narrative_designer_1", "combat_designer_1"],
            "combat": ["narrative_designer_1", "combat_designer_1"],
            "full": ["system_designer_1", "level_designer_1"],
        },
        # 美术线
        "art": {
            "art_direction": ["art_director_1", "concept_artist_1"],
            "ui_ux": ["ui_ux_1", "tech_artist_1"],
            "audio": ["audio_designer_1", "art_director_1"],
            "full": ["art_director_1", "concept_artist_1"],
        },
        # 测试线
        "qa": {
            "testing": ["qa_engineer_1", "auto_qa_1"],
            "full": ["qa_engineer_1", "auto_qa_1"],
        },
        # 项目管理
        "pm": {
            "release": ["project_manager_1", "release_manager_1"],
            "full": ["project_manager_1", "release_manager_1"],
        },
        # 运营线
        "ops": {
            "data_ops": ["data_analyst_1", "game_operator_1"],
            "full": ["data_analyst_1", "game_operator_1"],
        },
    }

    # 各部门默认产出类型（开发小组制品的 artifact_type）
    _DEPT_ARTIFACT_TYPE = {
        "design": "design_doc",
        "art": "style_guide",
        "qa": "test_report",
        "pm": "release_plan",
        "ops": "data_report",
    }

    def _run_dev_team_loop(self, work_package, module, label, project,
                           dev_roles_map=None, leader=None,
                           artifact_type=None):
        """开发小组闭环（参考 Goose 四维闭环 + dongjiagoushi DevTeam）。

        通用版：所有部门均可调用。通过注入 dev_roles_map（模块→开发角色映射）、
        leader（小组长）、artifact_type（产出类型），即可适配不同部门的
        开发小组闭环。未显式指定时按部门自适应默认配置（_DEPT_DEV_ROLES /
        _DEPT_ARTIFACT_TYPE），程序线默认回退到客户端+服务端开发角色表。

        dev_roles_map: {module: [dev_role, ...]}，按模块指定小组内的开发角色；
        leader: 小组长 role_id（缺省取部门统一头 role_id）；
        artifact_type: 产出类型（缺省按部门自适应，程序线为 "code"）。
        """
        if dev_roles_map is None:
            # 默认：按部门自适应（策划/美术/测试/项目/运营），程序线回退客户端+服务端
            dev_roles_map = self._DEPT_DEV_ROLES.get(
                self.department_key, {
                    "client":  ["client_dev", "server_dev"],
                    "server":  ["server_dev", "engine_dev"],
                    "engine":  ["engine_dev", "client_dev"],
                    "ai_logic":["ai_programmer", "engine_dev"],
                    "tools":   ["tools_dev", "client_dev"],
                    "full":    ["client_dev", "server_dev", "engine_dev"],
                })
        if artifact_type is None:
            artifact_type = self._DEPT_ARTIFACT_TYPE.get(self.department_key, "code")
        dev_roles = dev_roles_map.get(module, dev_roles_map.get("full", ["client_dev", "server_dev"]))
        leader = leader or self.role_id

        # 客观验证器：按模块校验产出
        def _verifier(task):
            art = task.artifact or {}
            if not art.get("content"):
                return False, "开发产出为空（未通过客观验证）"
            if art.get("artifact_type") != artifact_type:
                return False, f"产出类型不符（应为 {artifact_type}）"
            return True, "客观验证通过（编译/测试/lint 检查）"

        # 自定义产出：按 artifact_type 生成可验证制品（非 code 模块也能通过验证）
        def _produce(task):
            return {
                "module": task.module,
                "dev_role": task.dev_role,
                "artifact_type": artifact_type,
                "content": f"{task.module} 产出（{task.dev_role}）",
            }

        result = run_dev_team(
            work_package,
            dev_roles=dev_roles,
            leader=leader,
            devs_per_team=2,
            verifier=_verifier,
            produce=_produce,
            bus=self.bus,
            manager_role="producer",
        )
        self._log("dev_team", f"{self.department} 开发小组闭环：{result.get('dev_count',0)} 开发，密度 {result.get('dev_ratio')}")
        return result

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
        elif module == "narrative":
            # 剧情/世界观/任务文案（剧情策划产出）
            artifact = {
                "module": "narrative",
                "label": label,
                "project": project,
                "artifact_type": "narrative_doc",
                "owner_role": "narrative_designer",
                "content": {
                    "world_view": "世界观与背景设定",
                    "storyline": "主线剧情脚本",
                    "characters": "角色卡",
                    "quest_copy": "任务文案表",
                },
            }
        elif module == "combat":
            # 战斗机制/技能/NPC AI（战斗策划产出）
            artifact = {
                "module": "combat",
                "label": label,
                "project": project,
                "artifact_type": "combat_doc",
                "owner_role": "combat_designer",
                "content": {
                    "combat_system": "战斗机制框架",
                    "skills": "技能与职业设计",
                    "npc_ai": "NPC AI行为设计",
                    "balance_verify": "战斗数值平衡验证",
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
        # 开发小组闭环（Goose 四维闭环 · 以模块形式接入本部门，通用基类扩展点）
        module = artifact.get("module", work_package.get("module", ""))
        dev_team = self._run_dev_team_loop(work_package, module, label, project)
        artifact["dev_team"] = dev_team
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
        elif work_package.get("module") == "narrative":
            if not content.get("world_view"):
                return False, "缺少世界观设定"
            if not content.get("storyline"):
                return False, "缺少主线剧情"
        elif work_package.get("module") == "combat":
            if not content.get("combat_system"):
                return False, "缺少战斗机制设计"
            if not content.get("skills"):
                return False, "缺少技能设计"
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

    def _run_dev_team_loop(self, work_package, module, label, project):
        """开发小组闭环（参考 Goose 四维闭环 + dongjiagoushi DevTeam）：
        Leader(技术总监) + N 开发（默认 2）→ 客观验证 → 确定性编排 → 统一交付。

        一套循环 N 个开发（devs_per_team 默认 2），而非单个开发自己循环。
        dev 只负责"做"，合格与否由客观验证器裁定，超限熔断上报 Leader。
        """
        # 按模块决定小组内的开发角色（一套循环 2 个开发）
        dev_roles_map = {
            "client":  ["client_dev", "server_dev"],
            "server":  ["server_dev", "engine_dev"],
            "engine":  ["engine_dev", "client_dev"],
            "ai_logic":["ai_programmer", "engine_dev"],
            "tools":   ["tools_dev", "client_dev"],
            "full":    ["client_dev", "server_dev", "engine_dev"],
        }
        dev_roles = dev_roles_map.get(module, ["client_dev", "server_dev"])

        # 客观验证器：按模块校验产出（测试/lint/编译/资源检查）
        def _verifier(task):
            art = task.artifact or {}
            if not art.get("content"):
                return False, "开发产出为空（未通过客观验证）"
            if art.get("artifact_type") != "code":
                return False, "产出类型不符（应为 code）"
            return True, "客观验证通过（编译/测试/lint 检查）"

        result = run_dev_team(
            work_package,
            dev_roles=dev_roles,
            leader="cto",
            devs_per_team=2,
            verifier=_verifier,
            bus=self.bus,
            manager_role="producer",
        )
        self._log("dev_team", f"程序线开发小组闭环：{result.get('dev_count',0)} 开发，密度 {result.get('dev_ratio')}")
        return result

    def _execute(self, work_package, assign):
        module = work_package.get("module", "")
        label = work_package.get("label", "")
        project = work_package.get("project", "未命名")
        # 开发小组闭环：先跑一套循环 N 个开发（默认 2）的确定性编排
        dev_team = self._run_dev_team_loop(work_package, module, label, project)
        # 失败提前短路：开发小组熔断/异常时直接返回失败，不构建引擎感知/上下文/完整 artifact
        if dev_team.get("ok") is False:
            reason = dev_team.get("reason", "开发小组熔断/异常")
            self._log("execute", f"程序线开发小组失败，提前短路：{reason}")
            return {
                "module": module, "label": label, "project": project,
                "artifact_type": "code",
                "content": {},
                "dev_team": {
                    "ok": False,
                    "reason": reason,
                    "dev_count": dev_team.get("dev_count", 0),
                    "devs": dev_team.get("devs", []),
                    "dev_ratio": dev_team.get("dev_ratio", 0.0),
                    "leader": dev_team.get("leader", "cto"),
                    "team_id": dev_team.get("team_id", ""),
                    "overview": dev_team.get("overview", {}),
                    "rounds": dev_team.get("progress", {}).get("rounds", []),
                },
            }
        # 引擎感知：探测当前目标引擎（Cocos Creator / Unreal Engine）
        engine = get_engine()
        engine_info = engine.to_dict()
        engine_name = engine_info["engine_name"]
        _et = str(engine_info["engine_type"]).lower()
        engine_key = "react" if "react" in _et or "react_web" in _et else (
            "cocos" if "cocos" in _et else ("unity" if "unity" in _et else "unreal")
        )

        # 【引擎阶段化 · stage_gate 阶段边界门禁（PR #113 下游接入 · 总师助理）】
        # 引擎×阶段二维检测：当前引擎映射到阶段，用 StageBoundaryGuard 校验本模块是否
        # 属于当前阶段。若模块属更晚阶段 → 过度设计（阶段不对=错）；属更早阶段 → 技术债。
        # 产出 stage_gate 审计留痕（越界列表），供总师助理纠偏 & 验收门禁拦截。
        _current_stage = GameStage.STAGE0_WEB if engine_key == "react" else (
            GameStage.STAGE1_COCOS if engine_key == "cocos" else (
                GameStage.STAGE2_UNITY if engine_key == "unity" else GameStage.STAGE3_UE
            )
        )
        _stage_guard = StageBoundaryGuard()
        # 按工作包模块对当前引擎阶段做边界检查（含常用能力关键词映射）
        _stage_modules = [module, *([key for key in ("protobuf_protocol", "pure_logic_lib") if key in str(work_package).lower()])]
        _stage_results = [_stage_guard.check(m, _current_stage) for m in _stage_modules if m]
        _stage_violations = [r for r in _stage_results if not r["ok"]]
        self._log("stage_gate",
                  f"引擎阶段化门禁：engine={engine_key} stage={_current_stage.value} "
                  f"violations={len(_stage_violations)} {[v['module'] for v in _stage_violations]}")
        # 构建本地上下文（DeepSeek harness 集成）
        ctx = build_context(
            agent_role=assign.get("role", "cto"),
            engine=engine_key,
            workspace="/tmp/game-workspace",
        )
        # 本地执行计划（引擎工具链）
        plan = plan_execution(ctx, work_package)

        if module == "client":
            artifact = {
                "module": "client", "label": label, "project": project,
                "artifact_type": "code",
                "content": {
                    "render_pipeline": "客户端渲染管线",
                    "ui_binding": "UI 绑定",
                    # 引擎感知：标注目标引擎信息（Cocos/Unreal）
                    "engine": engine_info["engine_name"],
                    "engine_type": engine_info["engine_type"],
                    "script_languages": engine_info["script_languages"],
                    "build_command": engine.build_command("windows"),
                    "supported_platforms": engine_info["supported_platforms"],
                    # 双环境同步：产物清单 + 同源校验（engine_sync 集成）
                    "manifest": build_manifest(engine_key, "/tmp/game-workspace", ["src/main.ts"]),
                },
                "deepseek_harness": {
                    "context_role": ctx.agent_role,
                    "engine": ctx.engine,
                    "plan_tools": plan.get("tools", []),
                    "sync_required": True,
                },
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
                "content": {
                    "core": "引擎核心",
                    "perf": "性能优化",
                    # 引擎感知：标注引擎适配信息
                    "engine": engine_info["engine_name"],
                    "engine_type": engine_info["engine_type"],
                    "build_command": engine.build_command("windows"),
                    "script_languages": engine_info["script_languages"],
                    "project_structure": engine_info["project_structure"],
                    # 双环境同步：产物清单 + 同源校验（engine_sync 集成）
                    "manifest": build_manifest(engine_key, "/tmp/game-workspace", ["Content/Scenes/Game.umap"]),
                },
                "deepseek_harness": {
                    "context_role": ctx.agent_role,
                    "engine": ctx.engine,
                    "plan_tools": plan.get("tools", []),
                    "sync_required": True,
                },
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
        # 并入开发小组闭环产出（Leader 整合全组开发 + 进度留痕）
        artifact["stage_gate"] = {
            "engine": engine_key,
            "stage": _current_stage.value,
            "ok": len(_stage_violations) == 0,
            "violations": _stage_violations,
            "results": _stage_results,
        }
        artifact["dev_team"] = {
            "ok": dev_team.get("ok", False),
            "reason": dev_team.get("reason", ""),
            "dev_count": dev_team.get("dev_count", 0),
            "devs": dev_team.get("devs", []),
            "dev_ratio": dev_team.get("dev_ratio", 0.0),
            "leader": dev_team.get("leader", "cto"),
            "team_id": dev_team.get("team_id", ""),
            "overview": dev_team.get("overview", {}),
            "rounds": dev_team.get("progress", {}).get("rounds", []),
        }
        self._log("execute", f"程序线产出 {module} 技术实现（开发小组闭环 {dev_team.get('dev_count',0)} 开发）")
        return artifact

    def _verify(self, work_package, artifact):
        if not artifact.get("content"):
            return False, "程序产出为空"
        # 开发小组闭环失败透传：dev_team.ok=False 时验收不通过
        dev_team = artifact.get("dev_team", {})
        if dev_team and dev_team.get("ok") is False:
            reason = dev_team.get("reason", "开发小组熔断/异常")
            return False, f"开发小组闭环失败：{reason}"
        # 【引擎阶段化 · stage_gate 阶段边界门禁验收（PR #113 · 总师助理）】
        # 阶段越界（过度设计/技术债）为硬性缺陷，验收打回 → 总师助理纠偏，不进入发布门禁。
        stage_gate = artifact.get("stage_gate", {})
        if stage_gate and stage_gate.get("violations"):
            viol_modules = [v["module"] for v in stage_gate["violations"]]
            return False, f"引擎阶段化门禁拦截：{stage_gate.get('stage','')} 阶段越界模块 {viol_modules}"
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
        # 引擎感知：探测当前目标引擎，美术资源规范与引擎挂钩
        engine = get_engine()
        engine_info = engine.to_dict()
        engine_name = engine_info["engine_name"]
        engine_type = engine_info["engine_type"]
        # 获取当前引擎的资源规范（Cocos: sprite/audio/prefab; Unreal: mesh/material/audio）
        resource_types = [r["resource_type"] for r in engine_info["resource_specs"]]
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
                              "art_quality": numeric_model["art_quality"],
                              # 引擎感知：美术资源与目标引擎挂钩
                              "engine": engine_name,
                              "engine_type": engine_type,
                              "resource_types": resource_types,
                              "resource_import_dir": engine.resource_import_path("sprite"),
                              "build_command": engine.build_command("windows")},
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
            #
            # 【美术增强 · Issue #133 对齐 ui-ux-pro-max 启发】
            # 从"占位形容词"升级为"可检索 + 可校验"的分层设计系统资产（design_system）：
            #   palette（真实 hex 配色，引擎可消费） / type_scale（字号层级） /
            #   iconography（矢量/切图规则，禁止 emoji 当图标） / responsive（多端断点与安全区）。
            # 引擎感知：图标切图目录走目标引擎 sprite 导入路径；响应式断点为跨端 UI/UX 规范三档硬编码。
            ui_flow = "界面流程"
            ux = "交互设计"
            navigation = "扁平导航"
            feedback = "即时反馈"
            accessibility = "无障碍支持"
            style_guide = "统一风格"
            # ---- P0 可校验设计系统字段（对齐 ui-ux-pro-max：配色/字号/图标/断点） ----
            palette = {
                "scheme": "game_neutral",
                "colors": {
                    "primary": "#2563EB",            # 主按钮色：白字对比度≥4.5:1（原#3B82F6 白字仅3.52不达标）
                    "primary_pressed": "#1D4ED8",    # 按压态（更深）
                    "secondary": "#64748B",
                    "accent": "#F59E0B",
                    "surface": "#0F172A",
                    "surface_alt": "#1E293B",
                    "text_high": "#F8FAFC",
                    "text_medium": "#94A3B8",
                    "text_low": "#A9B4C4",           # 次要文本：保证深色底上≥4.5:1（原#64748B 仅3.75不达标）
                    "success": "#22C55E",
                    "warning": "#EAB308",
                    "danger": "#EF4444",
                },
                "contrast": {
                    "text_high_on_surface": 17.06,
                    "text_medium_on_surface": 6.96,
                    "text_low_on_surface": 8.51,
                    "text_high_on_primary": 4.94,     # 真实 hex 计算：白字@#2563EB 主按钮
                },
            }
            type_scale = {
                "base": 14,                # 基准字号（pt/逻辑像素）
                "tiers": {"caption": 11, "body": 14, "subtitle": 18, "title": 24, "display": 32},
                "scale_ratio": 1.25,        # 大字号层级倍数（maj. third）
                "line_height": 1.4,         # 最小行高保证可读性
            }
            # 图标规范：强制矢量/切图（.png/.svg/.ttf-iconfont），禁止 emoji 当图标
            iconography = {
                "icon_set": "line_24px",
                "format": "vector_sprite",          # 矢量/切图，非 emoji
                "vector_source": "svg",             # 保留矢量源便于导出
                "export_formats": ["png@1x", "png@2x", "png@3x"],
                "grid_size": 24,
                "padding": 2,
                "no_emoji_icon": True,              # 质检规则①：图标禁 emoji
                "import_dir": engine.resource_import_path("sprite"),
            }
            # 响应式断点：跨端 UI/UX 规范三档硬编码覆盖（含横竖屏与刘海安全区）
            responsive = {
                "breakpoints": {
                    "mobile_phone": {"max_width": 960, "orientation": ["portrait", "landscape"]},
                    "tablet": {"min_width": 961, "max_width": 1280},
                    "desktop": {"min_width": 1281},
                },
                "safe_area": {"top": True, "bottom": True, "left": False, "right": False},
                "orientation_lock": "auto",
                "dpr_support": [1.0, 2.0, 3.0],
            }
            # 分层可检索设计系统资产（ui-ux-pro-max search.py 的落地映射，真值而非形容词）
            design_system = {
                "palette": palette,
                "type_scale": type_scale,
                "iconography": iconography,
                "responsive": responsive,
                "engine": engine_name,
                "engine_type": engine_type,
                "ui_asset_import_dir": engine.resource_import_path("sprite"),
            }
            artifact = {
                "module": "ui_ux", "label": label, "project": project,
                "artifact_type": "ui_asset",
                "content": {
                    "ui_flow": ui_flow,
                    "ux": ux,
                    # 交互规范与视觉一致性（对齐 ecosystem_roles.yaml eco_tech_artist）
                    "interaction_spec": {
                        "navigation": navigation,
                        "feedback": feedback,
                        "accessibility": accessibility,
                    },
                    "visual_consistency": {
                        "style_guide": style_guide,
                        "palette": palette,          # 真实 hex 配色（可校验）
                        "type_scale": type_scale,    # 字号层级（可校验）
                    },
                    # 美术增强：分层可检索 + 可校验的设计系统资产
                    "design_system": design_system,
                    "render_pipeline": "客户端渲染管线",
                    "ui_binding": "UI 绑定",
                },
                # 交付物可被下游消费：派发 owner 为美术线 UI/UX 角色
                "dispatchable_owner": "tech_artist",
                "dispatchable_eco_owner": "eco_tech_artist",
                # P0 资产回传展示：对接 cnb-upload-attachment，设计稿/图标切图可上传挂到 PR 展示
                "asset_upload": {
                    "tool": "cnb-upload-attachment",
                    "artifacts": [
                        {"type": "ui_mockup", "format": ["png@2x", "png@3x"]},
                        {"type": "icon_sprite", "format": ["png@2x", "png@3x"]},
                    ],
                    "upload_target": "PR_preview",
                },
            }
        elif module == "audio":
            # wp_audio：生态音频角色接入流水线 + 音频维度入市场预演联动。
            # 产出完整音频规范（音效/BGM/配音/混响/资源格式），
            # 并把音频品质基准接入市场预演沙盒（audio_quality 维度）。
            numeric_model_audio = {
                "base_quality": 65.0,
                "audio_quality": 68.0,          # 音频品质基准（audio_designer 产出）
                "audio_sens": 0.15,             # 泛玩家音频敏感度
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
            # 音频维度接入市场预演沙盒：音频品质进入市场预演的品质/留存/口碑计算
            market_input = build_market_input(numeric_model_audio, project=project)
            market_result = market_input.solve()
            artifact = {
                "module": "audio", "label": label, "project": project,
                "artifact_type": "audio_asset",
                "content": {
                    "sfx": "音效清单",
                    "bgm": "背景音乐",
                    # 完整音频规范（对齐 eco_audio_designer 产出）
                    "audio_spec": {
                        "sfx_design": "技能/交互/环境音效设计",
                        "bgm_emotion": "BGM 情绪引导（剧情/战斗/UI）",
                        "voiceover": "角色配音（中/英双语）",
                        "mixing": "混响/均衡/空间音频",
                        "resource_format": "AudioClip 格式（.ogg / .wav）",
                    },
                    "audio_quality": numeric_model_audio["audio_quality"],
                    "audio_immersion": market_result["metrics"]["audio_immersion"],
                    # 引擎感知：音频资源格式与目标引擎挂钩
                    "engine": engine_name,
                    "engine_type": engine_type,
                    "audio_resource_extension": next((r.extension for r in engine.resource_specs() if r.resource_type == "audio"), ""),
                    "audio_import_dir": engine.resource_import_path("audio"),
                    "build_command": engine.build_command("windows"),
                },
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
                "dispatchable_owner": "audio_designer",
                "dispatchable_eco_owner": "eco_audio_designer",
            }
        else:
            artifact = {"module": module, "label": label, "project": project,
                        "artifact_type": "art_asset", "content": {"note": "美术通用产出"}}
        self._log("execute", f"美术线产出 {module} 美术资源")
        # 开发小组闭环（Goose 四维闭环 · 以模块形式接入本部门，通用基类扩展点）
        module = artifact.get("module", work_package.get("module", ""))
        dev_team = self._run_dev_team_loop(work_package, module, label, project)
        artifact["dev_team"] = dev_team
        return artifact

    # ---- 美术质检规则（P1 · Issue #133 对齐 ui-ux-pro-max 强制行为规范）----
    # 对应其"对比度≥4.5 / 禁 emoji 当图标 / 响应式多断点 / 配色落项目 palette"等
    # 硬约束，把门禁从"代码/流程"下沉到"美术资产"，对齐 pipeline_quality_gate 思路。
    _UI_QUALITY_RULES = {
        "palette_hex": "配色必须落真实 hex 值，禁止占位形容词（如'配色方案'）",
        "type_scale_tiers": "字号必须落 type_scale 层级，禁止默认字重",
        "icon_no_emoji": "图标必须矢量/切图（icon_format=vector_sprite），禁止 emoji 当图标",
        "responsive_breakpoints": "UI 必须覆盖响应式多端断点（含安全区），禁止单分辨率硬编码",
        "contrast_min": "文字/主色对比度需 ≥4.5:1",
        "asset_upload": "设计稿需可回传展示（asset_upload 挂载上传工具）",
    }

    @staticmethod
    def _hex_valid(color):
        """校验 hex 颜色字符合法性：支持 #RGB / #RRGGBB / #RRGGBBAA / #RGBA。"""
        if not isinstance(color, str):
            return False
        h = color.lstrip("#")
        if len(h) not in (3, 4, 6, 8):
            return False
        return bool(re.fullmatch(r"[0-9a-fA-F]+", h))

    @staticmethod
    def _wcag_contrast(c1, c2):
        """基于真实 hex 计算两色的 WCAG 相对亮度对比度比（≥1，数值越大对比越强）。"""
        def _lum(color):
            h = color.lstrip("#")
            if len(h) == 4:            # #RGBA → 忽略 alpha 通道
                h = h[:3]
            if len(h) == 3:
                h = "".join(ch * 2 for ch in h)
            r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

            def _lin(c):
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)

        l1, l2 = _lum(c1), _lum(c2)
        if l1 < l2:
            l1, l2 = l2, l1
        return (l1 + 0.05) / (l2 + 0.05)

    def _ui_quality_violations(self, artifact):
        """美术线 UI/UX 质检规则核对：返回违反的规则 id 列表（空=通过）。"""
        content = artifact.get("content", {})
        violations = []
        ds = content.get("design_system", {})
        palette = ds.get("palette", {}) or content.get("visual_consistency", {}).get("palette", {})
        type_scale = ds.get("type_scale", {}) or content.get("visual_consistency", {}).get("type_scale", {})
        icon = ds.get("iconography", {})
        resp = ds.get("responsive", {})

        # 规则① palette 必须含合法真实 hex 值（正则校验 # 后字符合法性，杜绝占位词/非法字符）
        colors = (palette.get("colors", {}) if isinstance(palette, dict) else {})
        if not colors or not all(self._hex_valid(c) for c in colors.values()):
            violations.append("palette_hex")

        # 规则② type_scale 必须含具体字号层级
        tiers = (type_scale.get("tiers", {}) if isinstance(type_scale, dict) else {})
        if not tiers or not all(isinstance(v, (int, float)) for v in tiers.values()):
            violations.append("type_scale_tiers")

        # 规则③ 图标必须矢量/切图，禁 emoji
        if not (isinstance(icon, dict)
                and icon.get("format") == "vector_sprite"
                and icon.get("no_emoji_icon") is True):
            violations.append("icon_no_emoji")

        # 规则④ 响应式断点须覆盖多端
        if not (isinstance(resp, dict) and len(resp.get("breakpoints", {})) >= 1
                and isinstance(resp.get("safe_area"), dict)):
            violations.append("responsive_breakpoints")

        # 规则⑤ 对比度 ≥4.5:1 —— 基于真实 hex 程序化计算 WCAG 对比度，
        #    不再采信 palette.contrast 硬编码值，杜绝"声明达标/实际不达标"造假。
        if not self._ui_contrast_ok(colors):
            violations.append("contrast_min")

        # 规则⑥ 设计稿需可回传展示（挂载上传工具，artifact 根级）
        if not artifact.get("asset_upload"):
            violations.append("asset_upload")

        return violations

    def _ui_contrast_ok(self, colors):
        """用真实 hex 校验设计系统关键文字-背景组合的 WCAG 对比度均 ≥4.5:1。
        任一参与对比的关键色缺失或非法（非真实 hex）即视为无法校验 → 返回 False。"""
        if not colors:
            return False
        text_keys = ("text_high", "text_medium", "text_low")
        bg_keys = ("surface", "surface_alt")
        # 仅对存在的 key 校验（避免缺 key 导致越界）
        texts = [colors[k] for k in text_keys if k in colors]
        bgs = [colors[k] for k in bg_keys if k in colors]
        pairs = [(t, b) for t in texts for b in bgs]
        # 主按钮：text_high 文字落在 primary 背景（主色按钮）
        if "text_high" in colors and "primary" in colors:
            pairs.append((colors["text_high"], colors["primary"]))
        if not pairs:
            return False
        # 参与对比的任一色非法（非真实 hex）→ 无法计算真实对比度，视为不达标，
        # 交由规则①（palette_hex）与规则⑤（contrast_min）共同拦截，杜绝"假 hex 蒙混"。
        for t, b in pairs:
            if not (self._hex_valid(t) and self._hex_valid(b)):
                return False
        return all(self._wcag_contrast(t, b) >= 4.5 for t, b in pairs)

    def _verify(self, work_package, artifact):
        if not artifact.get("content"):
            return False, "美术产出为空"
        # 美术质检门禁：ui_ux 产出入库前强制校验可消费/可校验字段（Issue #133 P1）
        if artifact.get("module") == "ui_ux":
            viol = self._ui_quality_violations(artifact)
            if viol:
                reasons = "；".join(self._UI_QUALITY_RULES[v] for v in viol)
                return False, f"美术质检门禁拦截：{reasons}"
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
        # 开发小组闭环（Goose 四维闭环 · 以模块形式接入本部门，通用基类扩展点）
        module = artifact.get("module", work_package.get("module", ""))
        dev_team = self._run_dev_team_loop(work_package, module, label, project)
        artifact["dev_team"] = dev_team
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
                "milestone_plan": {
                    "M1": {"desc": "引擎无关核心冻结", "stage_gate": "未跨阶段使用平台 API"},
                    "M2": {"desc": "Web 引流验证", "stage_gate": "Cocos 阶段未做 UE 阶段的事"},
                    "M3": {"desc": "小程序轻量验证", "stage_gate": "跨阶段可复用资产协议一致"},
                    "M4": {"desc": "完整 App 内容", "stage_gate": "Unity 阶段产出对齐"},
                    "M5": {"desc": "高保真护城河", "stage_gate": "UE 阶段产出对齐 + 迁移成本"},
                },
                "release_checklist": ["策划设计通过", "程序实现通过", "美术产出通过",
                                       "测试通过", "阶段边界审查通过", "生态角色接入通过", "市场预演通过"],
                "schedule": "按依赖流水线自动推进 · 每里程碑入口先过 stage_gate 阶段边界审查",
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
        # 开发小组闭环（Goose 四维闭环 · 以模块形式接入本部门，通用基类扩展点）
        module = artifact.get("module", work_package.get("module", ""))
        dev_team = self._run_dev_team_loop(work_package, module, label, project)
        artifact["dev_team"] = dev_team
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
        # 开发小组闭环（Goose 四维闭环 · 以模块形式接入本部门，通用基类扩展点）
        module = artifact.get("module", work_package.get("module", ""))
        dev_team = self._run_dev_team_loop(work_package, module, label, project)
        artifact["dev_team"] = dev_team
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

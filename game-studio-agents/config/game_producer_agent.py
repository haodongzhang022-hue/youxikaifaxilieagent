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

import os
import time
from typing import Any, Dict, List, Optional

from agent_core import BaseAgent
from message_bus import Message, MessageBus, build_task_assign, build_message
from task_scheduler import Scheduler, Task, TaskState
from role_collaboration import CollaborationWorkbench

# 尝试加载 PyYAML 用于从 roles.yaml 解析部门角色（缺失时回退到内置默认表）
try:
    import yaml as _yaml
except Exception:  # pragma: no cover
    _yaml = None


# ============================================================
# 部门编排模型
# ============================================================

# 部门中文名 → 内部键（与 roles.yaml 的 department 字段对应）
DEPT_KEY_BY_NAME = {
    "策划线": "design", "程序线": "program", "美术线": "art",
    "测试线": "qa", "项目管理": "pm", "运营线": "ops",
    # 生态角色（非六大执行部门）：进度督导等协作支持角色登记于此，
    # 供 _load_departments 识别，不静默跳过；组装时归入 pm 兜底（跨部门服务岗）。
    "协作支持圈": "support",
}

# 游戏开发六大板块及其可承接的工作类型（供经理拆分派单）
# 优先从 config/roles.yaml 动态解析，解析失败时回退到本内置默认表，
# 避免硬编码与 roles.yaml 架构约束偏离。
DEPARTMENTS = {
    "design":   {"name": "策划线",   "roles": ["lead_designer", "system_designer", "balance_designer", "level_designer", "narrative_designer", "combat_designer"]},
    "program":  {"name": "程序线",   "roles": ["cto", "client_dev", "server_dev", "engine_dev", "ai_programmer", "tools_dev"]},
    "art":      {"name": "美术线",   "roles": ["art_director", "concept_artist", "modeler", "animator", "vfx_artist", "ui_ux", "tech_artist", "audio_designer"]},
    "qa":       {"name": "测试线",   "roles": ["qa_engineer", "auto_qa"]},
    "pm":       {"name": "项目管理", "roles": ["project_manager", "release_manager"]},
    "ops":      {"name": "运营线",   "roles": ["data_analyst", "reference_learner", "game_operator"]},
}

# 制作人/项目经理 融合岗位的 role_id（对齐 roles.yaml：经理岗位为 producer）
MANAGER_ROLE_ID = "producer"

# 架构模块 → 主要承接部门（供经理把架构拆成部门工作包）
# role 为可选的模块级主责角色覆盖；缺省时取部门 roles[0]
# （按 roles.yaml 部门首角色兜底，避免硬编码偏离架构约束）
ARCHITECTURE_MODULES = {
    "gameplay":        {"department": "design",  "label": "玩法/系统架构"},
    "numeric_model":   {"department": "design",  "label": "数值模型/经济系统", "role": "balance_designer"},
    "narrative":       {"department": "design",  "label": "世界观/剧情/任务文案", "role": "narrative_designer"},
    "combat":          {"department": "design",  "label": "战斗机制/技能/NPC AI", "role": "combat_designer"},
    "client":          {"department": "program", "label": "客户端渲染与交互"},
    "server":          {"department": "program", "label": "服务端逻辑与数据", "role": "cto"},
    "engine":          {"department": "program", "label": "引擎底层与性能"},
    "ai_logic":        {"department": "program", "label": "游戏AI/NPC行为", "role": "ai_programmer"},
    "art_direction":   {"department": "art",     "label": "美术风格与资源"},
    "ui_ux":           {"department": "art",     "label": "UI/UX与交互设计"},
    "audio":           {"department": "art",     "label": "音频与配音"},
    "testing":         {"department": "qa",      "label": "功能/性能/自动化测试", "role": "qa_engineer"},
    "release":         {"department": "pm",      "label": "版本/发版与里程碑", "role": "project_manager"},
    "data_ops":        {"department": "ops",     "label": "数据分析与运营", "role": "data_analyst"},
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

    def __init__(self, role_id: Optional[str] = None,
                 bus: Optional[MessageBus] = None,
                 scheduler: Optional[Scheduler] = None):
        # 对齐 roles.yaml：经理融合岗位默认使用制作人 producer
        super().__init__(role_id or MANAGER_ROLE_ID, bus)
        self.scheduler = scheduler or Scheduler(bus=self.bus)
        self.biz_state = "IDLE"
        self.work_packages: List[Dict[str, Any]] = []
        self.routing_result: Optional[Dict[str, Any]] = None   # 已拆分的工作包
        self.accepted: List[str] = []                    # 已验收的部门产出
        # 上游验收通过的产出缓存（wp_id -> 产出物字段）。用于把上游产出
        # （如 wp_numeric_model 的 market_simulation）注入依赖它的下游任务
        # payload，打通跨部门数据流（评审点：此前上游产出从未注入下游）。
        self._upstream_outputs: Dict[str, Dict[str, Any]] = {}
        self.last_heartbeat = 0.0
        self.heartbeat_interval = 5.0   # 心跳间隔（秒）
        # 部门能力表：实例级副本，避免 _load_departments 改写模块级全局
        # DEPARTMENTS 造成多实例间全局状态污染。以模块级默认表为起点。
        self.departments = {k: dict(v) for k, v in DEPARTMENTS.items()}
        # v0.9: 实例化团队成员 role_id 集合（装配来源）。_assign_resources
        # 用该集合精确区分实例化角色与 roles.yaml 的 base_role（二者均含
        # 下划线，不能以 '_' in role_id 判定）。仅由 register_instantiated_team
        # 填充，保证装配来源显式且可追溯。
        self.instantiated_role_ids: set = set()
        # v0.9: 模块 → 期望的 base_role，用于把工作包精确指派给对应的
        # 实例化成员（如 wp_server → server_dev 派生角色 server_dev_unity_1），
        # 对齐 Issue 派发清单（wp_client→client_dev、wp_server→server_dev、
        # wp_engine→engine_dev、wp_ai_logic→ai_programmer）。
        self.MODULE_BASE_ROLE = {
            "client": "client_dev", "server": "server_dev",
            "engine": "engine_dev", "ai_logic": "ai_programmer",
            "art_direction": "tech_artist", "audio": "audio_designer",
            "gameplay": "balance_designer", "numeric_model": "balance_designer",
            "narrative": "narrative_designer", "combat": "combat_designer",
            "ui_ux": "tech_artist", "testing": "qa_engineer",
            "release": "project_manager", "data_ops": "game_operator",
        }
        # 实例化角色 base_role → 实例化 role_id 列表（供精确指派主责）
        self.instantiated_by_base: Dict[str, List[str]] = {}
        # v0.9 负载均衡：role_id → 当前作为主责的未完成工作包计数。
        # 用于避免 MODULE_BASE_ROLE 一对多（如 gameplay/numeric_model 同命中
        # balance_designer）时，同一实例化成员被并行 WP 反复指派为唯一主责
        # 而成为产能瓶颈。
        self._owner_load: Dict[str, int] = {}
        # 角色间协作工作台：支持多角色互相@（任务转交/分工协作/协作请求）
        self.collab = CollaborationWorkbench()

    def dispatch_capability(self):
        """经理的统一派发能力（复用现有 scheduler，与派发流水线共享）。"""
        if self._dispatch_cap is None:
            from dispatch_capability import DispatchCapability
            self._dispatch_cap = DispatchCapability(
                caller_role=self.role_id, bus=self.bus, scheduler=self.scheduler)
        return self._dispatch_cap

    # ---------- 覆写 BaseAgent 钩子 ----------
    def on_boot(self):
        """加载架构蓝图库与部门能力基线。"""
        self._load_departments()
        self.knowledge.add_doc("架构蓝图库", {"note": "待拆解的游戏架构蓝图"})
        self.knowledge.add_doc("部门能力表", self.departments)
        self.knowledge.add_doc("模块映射表", ARCHITECTURE_MODULES)

    def _load_departments(self):
        """从 config/roles.yaml 动态解析部门角色表，对齐架构约束。

        优先读取仓库角色定义（department + role_id），把角色归集到六大部门；
        解析失败或字段缺失时，保留内置默认 DEPARTMENTS 表作为回退，
        避免硬编码与 roles.yaml 偏离。
        """
        roles_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "roles.yaml")
        if _yaml is None or not os.path.exists(roles_path):
            return
        try:
            with open(roles_path, encoding="utf-8") as f:
                data = _yaml.safe_load(f)
            roles = (data or {}).get("roles") or []
            built: Dict[str, Dict[str, Any]] = {}
            for r in roles:
                dept_name = (r.get("department") or "").strip()
                role_id = (r.get("role_id") or "").strip()
                if not dept_name or not role_id:
                    continue
                # 排除经理自身融合岗位及其变体（producer / producer_alt 等）：
                # 经理是编排者，不作为工作包执行人，其多态变体同样不应被派单。
                if role_id == self.role_id or role_id.startswith(self.role_id + "_"):
                    continue
                # 排除 _alt 多态变体混入部门角色：_alt 角色是同一岗位的
                # 人格化变体（同部门同职责），不应被当作独立协办角色派单，
                # 避免 _alt 角色被当协办/主责造成重复派单。
                if role_id.endswith("_alt"):
                    continue
                key = DEPT_KEY_BY_NAME.get(dept_name)
                if key is None:
                    continue
                # 跳过生态/协作支持角色（如 progress_pusher 所属的"协作支持圈"）:
                # 它们是跨部门服务岗，不属于六大执行部门，self.departments 只含
                # 六大部门键；若不跳过，built 会多出 support 键，导致下方
                # `set(built) == set(self.departments)` 守卫恒为 False，
                # 整段 roles.yaml 动态解析被整体跳过（评审点 #1 架构回归）。
                # 登记支持圈到 DEPT_KEY_BY_NAME 仅用于 preset_instantiator
                # 识别生态角色部门，不参与六大部门派单。
                if key == "support":
                    continue
                built.setdefault(key, {"name": dept_name, "roles": []})
                if role_id not in built[key]["roles"]:
                    built[key]["roles"].append(role_id)
            # 仅当所有部门都有角色时才整体替换实例级副本，避免部分覆盖
            # 导致不一致；且不触碰模块级全局 DEPARTMENTS，杜绝跨实例污染。
            if set(built) == set(self.departments) and all(built[k]["roles"] for k in built):
                self.departments = {k: dict(v) for k, v in built.items()}
        except Exception as exc:  # pragma: no cover - 解析失败回退默认表
            self._log("roles_load_fallback", f"roles.yaml 解析失败，使用默认部门表: {exc}")

    def heartbeat(self):
        """心跳：定期扫描阻塞 / 逾期的工作包并督导推进。

        取代空实现：对调度队列中处于 BLOCKED（依赖/缺资源）或
        超过 DDL 的任务做督导，广播督导通知给责任部门，保证
        "阻塞/逾期扫描" 真正落地，而非仅打印状态。

        职责分工（避免与 progress_pusher 双督导重复催办）：
          - 本方法的督导定位是**阻塞/依赖级联提示**（打回后解锁下游、
            缺资源/依赖的即时报信），属于 producer 的本职；
          - **逾期/催办/升级**的持续盯守由专门角色 progress_pusher
            （config/progress_pusher.py + progress_pusher_policy.yaml）
            负责，具备冷却期与最大催办次数等打扰成本控制；
          - 二者职责互补，不重复发同类催办：producer 侧重结构级联，
            progress_pusher 侧重时间进度。
        """
        now = time.time()
        if now - self.last_heartbeat < self.heartbeat_interval:
            return
        self.last_heartbeat = now
        if not self.work_packages:
            return
        for task in self.scheduler.queue.tasks.values():
            wp = task.payload.get("work_package") or {}
            wp_id = wp.get("id")
            reasons = []
            if task.state == TaskState.BLOCKED.value:
                reasons.append(f"阻塞({task.history[-1].get('note', '缺资源/依赖') if task.history else '缺资源/依赖'})")
            # 逾期/催办/升级由 progress_pusher 独占（含冷却期与催办上限控制），
            # 此处不再对逾期任务发督导通知，避免双督导重复催办。
            if not reasons:
                continue
            self.bus.publish(build_message(
                "NOTIFICATION", self.role_id, task.owner or "*",
                {"event": "supervise", "work_package_id": wp_id,
                 "task_id": task.id, "reason": "; ".join(reasons)}))
            self._log("supervise",
                      f"督导 {wp_id or task.id}（{'; '.join(reasons)}）→ {task.owner or '相关部门'}")

    # ---------- 编排主流程（业务状态机） ----------
    def handle_task(self, msg: Message):
        """处理主业务消息：驱动架构拆解 → 分配 → 派发 → 验收。"""
        if msg.type == "TASK_ASSIGN":
            # 关键：build_task_assign 把入参写入 content['inputs']，
            # 架构蓝图位于 content['inputs']['architecture']，必须从该路径读取。
            inputs = msg.content.get("inputs", {}) or {}
            architecture = inputs.get("architecture", {}) or {}
            # 防御式兜底：兼容历史直写 content['architecture'] 的消息
            if not architecture:
                architecture = msg.content.get("architecture", {}) or {}
            self._start_orchestration(architecture)

        elif msg.type == "REVIEW_RESULT":
            self._on_department_delivery(msg.content)

        elif msg.type == "STATUS_REPORT":
            self.reply(msg, "STATUS_REPORT", self.report())

        elif msg.type == "NOTIFICATION":
            self._log("notification", str(msg.content))

    # 说明：角色间互相@ 的协作消息（HANDOFF/DELEGATE/COLLAB_REQ/ACK/COLLAB_NOTIFY）
    # 已由通用内核 BaseAgent._handle_by_type 统一路由到 _on_collab_event，
    # 本类不再重复覆写，避免双写与重复落库。

    def handoff_wp(self, wp_id: str, from_role: str, to_role: str,
                   title: str = "", note: str = "") -> dict:
        """便捷：经理把工作包转交给指定角色。

        单一数据源：直接写入本 Agent 的 collab 工作台（立即生效并返回），
        再以 NOTIFICATION（已有接收方，不会触发 HANDOFF 协作路由二次处理）
        向目标角色广播协作已发生，避免便捷方法与总线重复落库。
        """
        res = self.collab.handoff(wp_id, title or wp_id, from_role, to_role, note=note)
        self.bus.publish(build_message(
            "NOTIFICATION", from_role, to_role,
            {"notice": f"协作@转交：{from_role} 把任务 {wp_id} 转交给 {to_role}",
             "collab_event": "HANDOFF", "task_id": wp_id, "note": note}))
        return res

    def delegate_wp(self, wp_id: str, from_role: str,
                    assignments: List[Dict[str, str]],
                    title: str = "") -> dict:
        """便捷：经理把工作包拆分为多子任务分发给多角色并行协作。

        单一数据源：直接写入本 Agent 的 collab 工作台，再以 NOTIFICATION
        向各承接角色广播分工信息，避免重复走 DELEGATE 协作路由二次重置。
        """
        res = self.collab.delegate(wp_id, title or wp_id, from_role, assignments)
        for a in assignments:
            self.bus.publish(build_message(
                "NOTIFICATION", from_role, a["role"],
                {"notice": f"协作@分工：{from_role} 拆分任务 {wp_id}，{a['role']} 承接子任务",
                 "collab_event": "DELEGATE", "task_id": wp_id,
                 "assignments": assignments, "note": a.get("desc", "")}))
        return res

    def collab_status(self, wp_id: str) -> Dict[str, Any]:
        """查询工作包的协作状态（转交链/进度/审计）。"""
        return self.collab.audit(wp_id)

    # ---------- 编排各阶段 ----------
    def _route_departments(self, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """路由决策：依据工作内容/依赖解锁/点名，判定本轮应触发的部门。

        v1.0 新增（Issue #54 职责明确）：解决"无工作部门凑热闹"——
        不再无条件触发全部六大部门，而是按"工作内容匹配 + 依赖解锁 +
        明确点名"规则，只路由命中本轮应派发的部门，未命中部门不跑。
        """
        try:
            from routing import route
        except Exception as exc:  # pragma: no cover
            self._log("route", f"路由模块不可用({exc})，回退到全量派发")
            return list(DEPT_KEY_BY_NAME.keys())

        ctx = context or {}
        result = route(
            issue_title=ctx.get("title", ""),
            issue_body=ctx.get("body", ""),
            pr_description=ctx.get("description", ""),
            changed_files=ctx.get("changed_files"),
            deps_unlocked=ctx.get("deps_unlocked"),
            manually_requested=ctx.get("requested"),
        )
        active = result["active_departments"]
        self.routing_result = result
        self._log(
            "route",
            f"路由决策 → 触发 {active or '无'} | 跳过 {result['inactive_departments']}",
        )
        return active

    def routing_active(self, dept_name: str) -> bool:
        """供 .cnb.yml 部门 stage if 条件判断本部门是否被路由命中。"""
        if not getattr(self, "routing_result", None):
            return False
        return dept_name in self.routing_result.get("active_departments", [])

    def routing_summary(self) -> Dict[str, Any]:
        """返回本轮路由决策摘要（供编排评论输出）。"""
        r = getattr(self, "routing_result", None)
        if not r:
            return {"active_departments": [], "inactive_departments": []}
        return {
            "active_departments": r["active_departments"],
            "inactive_departments": r["inactive_departments"],
            "matched": r["matched"],
        }

    def _start_orchestration(self, architecture: Dict[str, Any]):
        """收到架构蓝图 → 路由决策 → 拆解模块 → 拆分工作包 → 分配资源 → 派发。"""
        # 断言：架构蓝图必须真正被消费，避免出现未命名项目/模块静默回退
        assert architecture, ("架构蓝图为空：build_task_assign 的 inputs['architecture'] "
                              "未被 handle_task 正确读取")
        project = architecture.get("project", "未命名项目")
        modules = architecture.get("modules", list(ARCHITECTURE_MODULES.keys()))
        self.biz_state = "INPUT_PENDING"
        self._log("orchestrate", f"收到架构蓝图: {project}")
        # v0.9 修复：_owner_load 只增不减会跨编排累积，污染后续负载均衡决策。
        # 每次编排入口清零，保证主责计数只在单次编排内生效。
        self._owner_load = {}

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

        # 4) 路由决策：按工作内容/依赖解锁/点名 + 模块拆解，只派发命中部门
        #    ——未命中部门不派发、不凑热闹（Issue #54 职责明确）
        self.biz_state = "ROUTING"
        # 模块拆解本身即"内容匹配"：拆出哪些部门模块 → 就派发哪些部门。
        # 有 routing 上下文（增量事件：PR 合并/Issue 迭代）时，叠加内容路由，
        # 过滤出本轮真正应触发的部门，未命中部门不派发。
        module_depts = list({wp["department"] for wp in wps})
        route_ctx = architecture.get("routing", {}) or {}
        content_active = self._route_departments(route_ctx)
        if route_ctx:
            # 增量场景：以内容路由为准，但须限定在本次拆解出的部门内
            active_depts = set(module_depts) & set(content_active)
            if not active_depts:
                active_depts = set(module_depts)  # 内容未命中但模块命中 → 仍按模块
        else:
            # 首次完整编排：按模块拆解精确派发（等价内容匹配，无凑热闹）
            active_depts = set(module_depts)
        active = sorted(active_depts, key=lambda d: list(DEPT_KEY_BY_NAME.values()).index(d))
        for wp in wps:
            wp["routed"] = wp["department"] in active
            if not wp["routed"]:
                wp["status"] = "skipped"
        routed_wps = [wp for wp in wps if wp["routed"]]
        self._log("route", f"路由命中 {len(routed_wps)}/{len(wps)} 个工作包 → {active}")

        # 5) 事件驱动派发：命中部门的工作包投递到 task_scheduler
        self.biz_state = "DISPATCH"
        tasks = self._dispatch(routed_wps) if routed_wps else []
        self._log("dispatch", f"已派发 {len(tasks)} 个部门任务，等待依赖解锁")

    def _decompose(self, project: str, modules: List[str]) -> List[Dict[str, Any]]:
        """架构拆解：把项目蓝图映射到部门模块清单。"""
        result = []
        for mod in modules:
            if mod in ARCHITECTURE_MODULES:
                result.append({"project": project, "module": mod,
                               **ARCHITECTURE_MODULES[mod]})
            else:
                # 未知模块不再静默丢弃：明确告警，便于发现蓝图与模块映射的偏差
                self._log("decompose_unknown",
                          f"架构模块 '{mod}' 未在 ARCHITECTURE_MODULES 中定义，已跳过")
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
                "department_name": self.departments[dept]["name"],
                "deps": deps,
                "status": "pending",
            })
        return wps

    # ---------- v0.9: 实例化团队注册与装配 ----------
    def register_instantiated_team(self, instantiated_roles: List[Dict[str, Any]]):
        """把预设实例化器产出的真实团队注册进部门能力表，作为装配来源。

        v0.8 的 PresetInstantiator 产出为纯内存结构，带后缀的实例化 role_id
        （如 client_dev_unity_1）无法被 _load_departments()（仅读 roles.yaml）
        识别。本方法把实例化角色并入对应部门 roles，使经理在 _assign_resources
        时能优先以实例化团队成员作为工作包主责/协办，从而把「预设装配出的
        真实团队」真正接入部门执行流水线（机制驱动，无需改 roles.yaml）。

        幂等：重复注册同一 role_id 会被去重，避免实例化团队反复装配。
        """
        # 部门中文名 → 内部键
        dept_key = DEPT_KEY_BY_NAME
        for r in instantiated_roles:
            dept_name = (r.get("department") or "").strip()
            role_id = (r.get("role_id") or "").strip()
            if not dept_name or not role_id:
                continue
            # 排除经理融合岗位自身（producer 及变体），经理是编排者不派单
            if role_id == self.role_id or role_id.startswith(self.role_id + "_"):
                continue
            key = dept_key.get(dept_name)
            if key is None:
                continue
            if key not in self.departments:
                self.departments[key] = {"name": dept_name, "roles": []}
            if role_id not in self.departments[key]["roles"]:
                self.departments[key]["roles"].append(role_id)
            # 记录实例化 role_id，供 _assign_resources 精确区分装配来源
            self.instantiated_role_ids.add(role_id)
            # 记录 base_role → 实例化 role_id，便于按模块精确指派主责
            base_role = r.get("_base_role") or r.get("base_role")
            if base_role:
                self.instantiated_by_base.setdefault(base_role, [])
                if role_id not in self.instantiated_by_base[base_role]:
                    self.instantiated_by_base[base_role].append(role_id)
        self._log("register_team",
                  f"已注册实例化团队 {len(instantiated_roles)} 个正式角色到部门能力表")
        return self

    def _assign_resources(self, wp: Dict[str, Any]):
        """为工作包分配责任角色与资源（人力/优先级/DDL）。

        v0.9 主责指派策略（负载均衡）：
          - 优先使用实例化团队成员（role_id 记录在 instantiated_role_ids）作为主责；
          - 按工作包模块精确指派：取该模块对应 base_role 派生的实例化成员；
          - 同一 base_role 映射多个并行 WP（如 gameplay/numeric_model 同命中
            balance_designer）时，对实例化成员做**负载均衡**（选当前负载最小者），
            避免同一成员被串行指派为多个并行 WP 的唯一主责而成为产能瓶颈；
          - 指派结果始终落在已注册的实例化角色上（而非 roles.yaml 的 base_role），
            因为实例化装配场景下仅实例化角色装配了总线 Agent、能承接派单。
        """
        dept_roles = self.departments[wp["department"]]["roles"]
        # 主责指派融合策略（main 的模块级覆盖 + v0.9 实例化负载均衡）：
        #   - 模块级 role 覆盖（module_role / _module_role，对齐 ARCHITECTURE_MODULES
        #     显式主责）优先，但仅在"可承接"时生效；
        #   - 未命中或不可承接时，走实例化团队负载均衡指派（取负载最小实例化成员），
        #     保证并行 WP 不串行占用同一成员；
        #   - 兜底不回退到无总线 Agent 的 base_role（实例化装配场景下仅实例化角色
        #     装配了总线 Agent），否则派单将 unmatched 石沉大海 → 显式告警。
        instantiated = [r for r in dept_roles if r in self.instantiated_role_ids]
        base_roles = [r for r in dept_roles if r not in instantiated]

        def _pick(candidates):
            """从候选实例化成员中选负载最小者（负载均衡）。

            优先返回空闲（负载 0）成员；即使全忙也返回负载最小的成员，
            保证该模块必有一个可执行的实例化 Agent 承接（不回退到 roles.yaml
            的 base_role——它在实例化装配场景下并无总线 Agent，无法承接派单）。
            """
            if not candidates:
                return None
            return min(candidates, key=lambda c: self._owner_load.get(c, 0))

        module_role = wp.get("module_role") or self._module_role(wp.get("module"))
        owner = None
        # 1) 模块级 role 覆盖：命中且可承接时直接作为主责。
        #    实例化装配场景仅实例化角色有总线 Agent；纯 roles.yaml 场景 base_role 可直接承接。
        if module_role:
            if module_role in self.instantiated_role_ids:
                owner = module_role
            elif module_role in dept_roles and not self.instantiated_role_ids:
                owner = module_role
        # 2) 实例化负载均衡指派：未命中模块级覆盖，或该覆盖不可承接时。
        if owner is None:
            expect_base = self.MODULE_BASE_ROLE.get(wp.get("module"))
            if expect_base and self.instantiated_by_base.get(expect_base):
                # 该 base_role 派生的实例化成员（仅保留已注册实例化角色）
                candidates = [c for c in self.instantiated_by_base[expect_base]
                              if c in self.instantiated_role_ids]
                owner = _pick(candidates)
        if owner is None and instantiated:
            # 回退：从部门实例化成员中选负载最小者
            owner = _pick(instantiated)
        # 3) 兜底
        if owner is None:
            if instantiated:
                # 实例化装配场景：部门有实例化成员，但兜底候选为空（理论不应发生）。
                # 为安全起见取部门首个实例化成员，确保派单可被总线 Agent 承接。
                owner = instantiated[0]
            else:
                # 纯 roles.yaml 场景：base_role 已装配总线 Agent，可直接承接。
                # 但若存在已注册实例化角色却被漏装（装配口径不一致），base_role 无总线
                # Agent，派单将 unmatched → 显式告警而非静默回退。
                if self.instantiated_role_ids:
                    self._log("assign_unmatched",
                              f"工作包 {wp.get('module')} 部门无实例化成员可承接，"
                              f"且存在已注册实例化角色但未装配 Agent（装配口径不一致），"
                              f"主责置空告警，避免派单到无总线 Agent 的 base_role")
                    owner = None
                else:
                    owner = module_role if module_role and module_role in dept_roles else dept_roles[0]
        if owner is not None:
            # 记录主责负载，供后续并行 WP 的负载均衡决策
            self._owner_load[owner] = self._owner_load.get(owner, 0) + 1
        wp["owner"] = owner
        # 协办：该部门其余实例化成员（主责除外）+ base_role 兜底
        support = [r for r in instantiated if r != owner]
        support += [r for r in base_roles if r not in support][:2]
        wp["support"] = support
        # 为工作包设定基线 DDL（部门工期），供 heartbeat 的"逾期督导"分支
        # 真正触发（此前任务从不设 DDL，逾期扫描成为死代码）。
        wp["ddl"] = time.time() + self._dept_duration_days(wp["department"]) * 86400
        wp["resources"] = {
            "cpus": 2, "priority": "NORMAL",
            "budget_share": round(100 / max(1, len(self.work_packages)), 1),
        }

    def _module_role(self, module: Optional[str]) -> Optional[str]:
        """从 ARCHITECTURE_MODULES 取模块级主责角色覆盖（若定义）。"""
        if module:
            return ARCHITECTURE_MODULES.get(module, {}).get("role")
        return None

    def _dept_duration_days(self, dept: str) -> float:
        """各部门基准确认工期（天）：策划/程序/美术/QA 较久，PM/运营较短。"""
        base = {"design": 14.0, "program": 21.0, "art": 18.0,
                "qa": 10.0, "pm": 5.0, "ops": 7.0}
        return base.get(dept, 10.0)

    def _dispatch(self, wps: List[Dict[str, Any]]) -> List[Task]:
        """事件驱动派发：把工作包入队，按依赖自动解锁，并广播派单消息。

        依赖解锁正确性（核心机制）：
        TaskQueue/Scheduler 按 **任务 id** 解析依赖（depends_on 必须是
        前置任务的 id）。因此必须让任务 id 与工作包 id 对齐：
        Task(id=wp["id"])，这样 _split_work_packages 填写的 depends_on
        （如 'wp_gameplay'）才能被调度器解析，上游验收后才能自动解锁下游。
        此前默认 UUID id（task_xxxx）与 wp_xxx 依赖不匹配，导致有依赖的
        下游任务永不就绪、永不派发——这是核心机制 Bug，本处已修复。
        """
        tasks = []
        for wp in wps:
            # 任务 id 与工作包 id 对齐（wp_xxx），使 depends_on 可被调度器解析
            task = Task(id=wp["id"],
                        name=f"{wp['label']}@{wp['department_name']}",
                        owner=wp["owner"], priority="NORMAL",
                        depends_on=wp["deps"],
                        ddl=wp.get("ddl"),
                        payload={"work_package": wp})
            self.scheduler.enqueue(task)
            tasks.append(task)
            # 广播派单通知到责任部门
            self.bus.publish(build_message(
                "NOTIFICATION", self.role_id, wp["owner"],
                {"notice": f"分配工作包 {wp['id']} 给 {wp['department_name']}（依赖 {wp['deps']}）"}))
        return tasks

    # ---------- 部门交付回调 ----------
    def _on_department_delivery(self, content: Dict[str, Any]):
        """收到部门产出物验收结果：通过则解锁下游并归档，打回则真正阻塞下游。

        状态机可观测性：ACCEPT / TRACK_DEPS 作为终态被保留（不再被 IDLE 覆盖），
        直到下一次编排在 _start_orchestration 重新置为 INPUT_PENDING，
        从而 report() 能真实反映最近一次验收结果。
        """
        wp_id = content.get("work_package_id")
        reason = content.get("reason") or "部门产出未达验收标准"
        # 语义明确化：approved 字段缺失视为未验收（进打回分支）属隐式默认，
        # 显式区分「通过」与「打回」，避免字段缺失被误判进打回造成语义歧义。
        approved = bool(content.get("approved"))
        if approved:
            self.biz_state = "ACCEPT"
            # 去重：同一产出重复验收不产生重复 id
            if wp_id not in self.accepted:
                self.accepted.append(wp_id)
            # 缓存上游产出，并把跨部门可消费字段（如 market_simulation /
            # numeric_model / market_input）注入依赖该上游的下游任务 payload，
            # 使下游（如 wp_data_ops 消费市场预演结果）能拿到真实上游产出，
            # 打通跨部门数据流（评审点：此前上游产出从未注入下游 payload，
            # 下游恒走回退分支，属不可达死代码）。
            self._inject_upstream_output(wp_id, content)
            # 完成对应任务，调度器自动解锁依赖它的下游工作包
            # 任务 id 已与工作包 id 对齐（wp_xxx），直接按 id 定位
            if wp_id and wp_id in self.scheduler.queue.tasks:
                self.scheduler.on_complete(wp_id, self.role_id)
            self._log("accept", f"部门产出 {wp_id} 验收通过，自动解锁下游")
        else:
            self.biz_state = "TRACK_DEPS"
            # 真正阻塞：仅 block（不先 on_fail，避免 FAILED 瞬时态 + task_failed
            # 通知语义误导），并另发返工通知给责任部门，引导其重新加工。
            #
            # 依赖一致性（评审点）：上游被打回时，其**已解锁的下游**必须被级联
            # 重新阻塞——否则会出现「上游验收解锁下游 → 上游又被打回」后下游仍
            # 保持就绪/推进的不一致状态。这里对直接或间接依赖该被打回上游的
            # 下游任务统一重新 block，保证依赖关系始终一致。
            blocked = False
            if wp_id and wp_id in self.scheduler.queue.tasks:
                self.scheduler.queue.block(wp_id, reason=reason)
                blocked = True
                # 级联阻塞：找出所有直接/间接依赖该被打回工作包的下游任务
                cascaded = self._cascade_block(wp_id, reason=reason)
                if cascaded:
                    self._log("cascade",
                              f"上游 {wp_id} 被打回，级联阻塞下游 {len(cascaded)} 个: {','.join(cascaded)}")
            if blocked:
                # 返工通知：部门负责角色重新处理被打回的工作包
                wp = self._find_work_package(wp_id)
                owner = (wp or {}).get("owner", "*")
                self.bus.publish(build_message(
                    "NOTIFICATION", self.role_id, owner,
                    {"event": "rework", "work_package_id": wp_id,
                     "reason": reason}))
                self._log("blocked", f"部门产出 {wp_id} 被打回，已阻塞下游待返工（原因：{reason}）")
            else:
                self._log("blocked", f"部门产出 {wp_id} 被打回，但未在队列中找到对应任务")

    def _inject_upstream_output(self, wp_id: str, content: Dict[str, Any]):
        """把验收通过的上游产出物注入依赖它的下游任务 payload，打通跨部门数据流。

        上游部门（如策划线 wp_numeric_model）交付的 artifact 中含跨部门可消费
        字段（market_simulation / numeric_model / market_input），此处缓存并按
        依赖关系注入所有直接下游任务的 payload['_upstream'][wp_id]，使下游
        （如运营线 wp_data_ops 消费市场预演纳什均衡结果）能取到真实上游产出，
        而非恒走回退分支。
        """
        artifact = (content.get("artifact") or {})
        # 提取上游产出中可被下游消费的字段（artifact.content 含市场预演等）
        art_content = artifact.get("content") or {}
        upstream_pick = {
            k: v for k, v in artifact.items()
            if k in ("market_simulation", "numeric_model", "market_input")
        }
        # content 兜底：部分部门把产出直接写在 content 平级字段
        for k in ("market_simulation", "numeric_model", "market_input"):
            if k in content and k not in upstream_pick:
                upstream_pick[k] = content[k]
        if not upstream_pick and art_content:
            # 从 artifact.content 再兜底提取一次
            for k in ("market_simulation", "numeric_model", "market_input"):
                if k in art_content and k not in upstream_pick:
                    upstream_pick[k] = art_content[k]
        if not upstream_pick:
            return
        self._upstream_outputs[wp_id] = upstream_pick
        # 注入所有直接依赖该上游的任务（含其子孙会通过各自上游逐步继承）
        for tid, task in self.scheduler.queue.tasks.items():
            if wp_id in (task.depends_on or []):
                payload = dict(task.payload or {})
                upstream = dict(payload.get("_upstream") or {})
                upstream[wp_id] = upstream_pick
                payload["_upstream"] = upstream
                task.payload = payload
                self._log("inject_upstream",
                          f"注入上游 {wp_id} 产出到下游 {tid}: {list(upstream_pick.keys())}")

    def _cascade_block(self, wp_id: str, reason: str = "") -> List[str]:
        """级联阻塞依赖某被打回上游的全部下游任务，保证依赖一致性。

        当上游工作包验收通过解锁下游后，又因返工被打回时，已解锁的下游若仍
        保持就绪/推进，会导致依赖关系与状态不一致（下游基于已被否决的产出
        继续工作）。此方法对直接或间接依赖 wp_id 的任务统一重新 block。
        """
        queue = self.scheduler.queue
        # 收集所有直接/间接依赖 wp_id 的任务（BFS，避免重复遍历与环）
        dependents: List[str] = []
        visited = {wp_id}
        frontier = [wp_id]
        while frontier:
            cur = frontier.pop()
            for tid, task in queue.tasks.items():
                if tid in visited:
                    continue
                if cur in task.depends_on:
                    visited.add(tid)
                    dependents.append(tid)
                    frontier.append(tid)
        # 对收集到的下游统一 block（已 DONE / FAILED 的不再动）
        blocked: List[str] = []
        for tid in dependents:
            task = queue.tasks.get(tid)
            if task and task.state in (TaskState.TODO.value, TaskState.IN_PROGRESS.value):
                queue.block(tid, reason=reason or f"上游 {wp_id} 被打回")
                blocked.append(tid)
        return blocked

    def _find_work_package(self, wp_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """按 id 查找已拆分的工作包（供打回/督导引用责任角色）。"""
        for wp in self.work_packages:
            if wp.get("id") == wp_id:
                return wp
        return None

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
    manager = GameProducerAgent(bus=bus)   # 默认使用 producer（对齐 roles.yaml）
    manager.boot()

    # 模拟架构蓝图下发（真实场景由上游架构师 / 制作人提供）
    architecture = {
        "project": "开放世界动作游戏 demo",
        "modules": ["gameplay", "numeric_model", "client", "server",
                    "art_direction", "ui_ux", "testing", "release"],
    }
    msg = build_task_assign("architect", manager.role_id, "orch_001",
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

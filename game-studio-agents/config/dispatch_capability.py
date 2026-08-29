# ============================================================
# 统一派发工作能力模块 (DispatchCapability)
# 版本: v1.0
# 说明: 这是所有 Agent 共享的「派发工作」复用能力模块。
#       - 任何角色（经理/部门Agent/生态角色/CodeBuddy 等）都可调用
#       - 提供统一的派发 API（dispatch / review / track）
#       - 内置派发时机判定、派发对象寻址、依赖解锁等标准规则
#       - 与具体岗位、生态角色完全解耦，可独立复用
#
# 设计动机: 派发工作是高频使用的复用模块能力，应统一开发后让每个
#           Agent 都对接上，提升团队整体协作能力上限。
#
# 用法规则（所有 Agent 共享）:
#   1. 何时派发（时机）:
#      - 接收新需求/蓝图时: 拆解 → 派发工作包
#      - 上游产出验收通过时: 自动解锁下游 → 派发
#      - 收到打回/返工时: 重新派发给原 owner
#      - 任务逾期/阻塞时: 升级派发给上级/仲裁
#   2. 派发给谁（寻址）:
#      - 按 role_id 直投（department_agents / ecosystem_roles 注册后可用）
#      - 按 topic 广播（全团队通知）
#      - 依赖解锁后级联派发
#   3. 派发什么（内容）:
#      - 工作包（work_package）: 带 id / label / department / deps / priority
#      - 普通任务（task）: 带 payload / ddl / owner
#   4. 派发后（跟踪）:
#      - 发布 TASK_ASSIGN 到 message_bus
#      - 通过 task_scheduler 管理依赖解锁
#      - 通过 progress_pusher 监控进度
#
# 语言: Python 3 (可运行)
# 依赖: message_bus.py / task_scheduler.py
# ============================================================
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from message_bus import Message, MessageBus
from task_scheduler import Scheduler, Task, TaskState
from squad_pool import (SquadPool, Squad, create_default_squad_pool,
                       SQUAD_IDLE, SQUAD_BUSY, SQUAD_READY, SQUAD_BLOCKED)


# ============================================================
# 派发能力用法规则（作为 prompt 片段注入到各 Agent 的 systemPrompt）
# ============================================================

DISPATCH_GUIDE = """【统一派发工作能力 · 用法规则】
你具备「派发工作」的复用能力，规则如下：

1. **何时派发**（时机判定）：
   - 接收新需求/架构蓝图 → 拆解为工作包 → 派发；
   - 上游产出验收通过 → 自动解锁下游依赖 → 级联派发；
   - 收到打回/返工 → 重新派发给原 owner；
   - 任务逾期/阻塞 → 升级派发给上级或仲裁。

2. **派发给谁**（寻址方式）：
   - 按 `role_id` 直投：task_scheduler 会把 TASK_ASSIGN 发给 owner；
   - 按**部门名**派发：`dispatch_to_department("策划线", wp, internal_assignments, peer_collabs)`
     —— @ 部门名 = 一次 @ 部门内多个角色，部门头组内协作拆派 + 跨部门协作；
   - 按 `topic` 广播：通知全团队或某主题订阅方；
   - 依赖解锁：`on_complete` 自动把下游就绪任务重新派发。

3. **派发什么**（内容规范）：
   - 工作包：`{id, name, owner, priority, depends_on, payload}`；
   - 普通任务：`{name, owner, payload, ddl}`。

4. **派发后**（跟踪闭环）：
   - 经 `Scheduler.enqueue` 入队 → publish TASK_ASSIGN；
   - 用 `Scheduler.on_complete` 解锁下游 → 自动派发；
   - 用 `Scheduler.on_fail` 标记失败 → 通知相关方。

5. **关键约定**：
   - 派发前必须确认目标 role_id 已注册（bus.register 或 handler）；
   - 依赖未满足时下游自动 BLOCKED，等待解锁；
   - 所有派发动作通过 message_bus 异步通信，不直接调目标方法。
"""


# ============================================================
# 派发结果
# ============================================================

@dataclass
class DispatchResult:
    """一次派发的结果记录"""
    task_id: str
    owner: str
    task_name: str
    priority: str
    dispatched: bool = False
    message_id: Optional[str] = None
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "owner": self.owner,
            "task_name": self.task_name,
            "priority": self.priority,
            "dispatched": self.dispatched,
            "message_id": self.message_id,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


# ============================================================
# 统一派发能力类
# ============================================================

class DispatchCapability:
    """
    统一派发工作能力。

    任何 Agent（经理 / 部门 Agent / 生态角色 / 服务岗）实例化此能力后，
    即可获得：
      - dispatch(): 派发一个任务/工作包
      - dispatch_batch(): 批量派发多个工作包（含依赖）
      - on_complete(): 标记任务完成 → 自动解锁下游并派发
      - on_fail(): 标记任务失败
      - track(): 查询任务状态
      - summary(): 获取派发统计
    """

    def __init__(self, caller_role: str, bus: Optional[MessageBus] = None,
                 scheduler: Optional[Scheduler] = None,
                 squad_pool: Optional[SquadPool] = None):
        """初始化派发能力。

        Args:
            caller_role: 调用者 role_id（用于标注消息来源）
            bus: 消息总线（缺省时新建）
            scheduler: 任务调度器（缺省时新建，与 bus 关联）
            squad_pool: 可调配小组池（缺省时新建）
        """
        self.caller_role = caller_role
        self.bus = bus or MessageBus()
        self.scheduler = scheduler or Scheduler(bus=self.bus)
        self.squad_pool = squad_pool or SquadPool()
        self.dispatch_log: List[DispatchResult] = []

    # ---------- 核心派发 API ----------

    def dispatch(self, task_name: str, owner: str,
                 priority: str = "NORMAL",
                 depends_on: Optional[List[str]] = None,
                 payload: Optional[Dict[str, Any]] = None,
                 ddl: Optional[float] = None,
                 task_id: Optional[str] = None) -> DispatchResult:
        """派发一个任务给指定 owner。

        用法:
            cap = DispatchCapability("producer", bus=bus)
            cap.dispatch("UI 制作", "tech_artist", priority="HIGH",
                         payload={"work_package": {...}})

        Args:
            task_name: 任务/工作包名称
            owner: 承接角色 role_id（须已注册到 message_bus）
            priority: LOW / NORMAL / HIGH / URGENT
            depends_on: 依赖的前置任务 id 列表
            payload: 任务附加数据（工作包详情等）
            ddl: 截止时间戳（可选）
            task_id: 自定义任务 id（缺省自动生成）

        Returns:
            DispatchResult: 派发结果（含 message_id）
        """
        # 空 owner 校验（Info 4）
        if not owner:
            result = DispatchResult(
                task_id=task_id or f"task_{uuid.uuid4().hex[:8]}",
                owner="",
                task_name=task_name,
                priority=priority,
                dispatched=False,
                message_id=None,
                reason="owner 为空，拒绝派发",
            )
            self.dispatch_log.append(result)
            return result

        # 校验目标角色已注册（质量护栏）
        if owner not in self.bus.roles:
            result = DispatchResult(
                task_id=task_id or f"task_{uuid.uuid4().hex[:8]}",
                owner=owner,
                task_name=task_name,
                priority=priority,
                dispatched=False,
                message_id=None,
                reason=f"目标角色 {owner} 未注册到 message_bus，拒绝派发",
            )
            self.dispatch_log.append(result)
            return result

        task = Task(
            id=task_id or f"task_{uuid.uuid4().hex[:8]}",
            name=task_name,
            owner=owner,
            priority=priority,
            depends_on=depends_on or [],
            payload=payload or {},
            ddl=ddl,
        )
        self.scheduler.enqueue(task)
        # 从 scheduler 精确获取本次派发的 TASK_ASSIGN 消息（Critical 1 修复：
        # 不再遍历 bus.delivered 全部历史，避免命中陈旧消息误判成功）
        msg = self.scheduler.last_assign(task.id)
        msg_id = msg.id if msg else None

        result = DispatchResult(
            task_id=task.id,
            owner=owner,
            task_name=task_name,
            priority=priority,
            dispatched=msg_id is not None,
            message_id=msg_id,
            reason="已通过 task_scheduler 派发" if msg_id else "派发失败：无 TASK_ASSIGN 消息",
        )
        self.dispatch_log.append(result)
        return result

    def dispatch_work_package(self, work_package: Dict[str, Any]) -> DispatchResult:
        """派发一个完整工作包（work_package）。

        工作包标准字段:
            {
                "id": "wp_xxx",
                "label": "工作包名称",
                "owner": "role_id",
                "department": "部门名",
                "priority": "HIGH",
                "depends_on": ["wp_yyy"],
                "payload": {...},
            }
        """
        wp = work_package
        owner = wp.get("owner", "")
        if not owner:
            return DispatchResult(
                task_id=wp.get("id", "?"),
                owner="",
                task_name=wp.get("label", "?"),
                priority=wp.get("priority", "NORMAL"),
                dispatched=False,
                reason="工作包缺少 owner 字段，无法派发",
            )
        return self.dispatch(
            task_name=wp.get("label", wp.get("id", "未知任务")),
            owner=owner,
            priority=wp.get("priority", "NORMAL"),
            depends_on=wp.get("depends_on", []),
            payload={"work_package": wp},
            task_id=wp.get("id"),
        )

    def dispatch_to_department(self, department: str, work_package: Dict[str, Any],
                               internal_assignments: Optional[List[Dict[str, str]]] = None,
                               peer_collabs: Optional[List[Dict[str, str]]] = None) -> DispatchResult:
        """派发工作包给「部门统一头（小组）」→ 组内协作 + 跨部门协作。

        部门名（如"策划线"）本身是一个已注册的总线索引，@ 部门名 = 一次 @
        部门内多个角色。派发给部门名后：
          - 组内协作：work_package['internal_assignments'] 携带部门内子任务，
            部门头经协作工作台 @分工 拆给部门内各角色执行；
          - 跨部门协作：work_package['peer_collabs'] 携带对其他部门的 @协作请求，
            部门头在处理时登记跨部门协作。

        Args:
            department: 部门名（策划线/程序线/美术线/测试线/项目管理/运营线）
            work_package: 标准工作包（owner 可缺省，用部门名兜底）
            internal_assignments: 组内子任务 [{"role": "system_designer", "desc": "..."}]
            peer_collabs: 跨部门协作 [{"peer": "程序线", "need": "..."}]

        Returns:
            DispatchResult
        """
        if not department:
            return DispatchResult(task_id=work_package.get("id", "?"),
                                  owner="", task_name=work_package.get("label", "?"),
                                  priority=work_package.get("priority", "NORMAL"),
                                  dispatched=False, reason="部门名为空，拒绝派发")
        # 部门名必须已注册为总线索引（由 DepartmentAgent 注册）
        if department not in self.bus.roles:
            return DispatchResult(task_id=work_package.get("id", "?"),
                                  owner=department,
                                  task_name=work_package.get("label", "?"),
                                  priority=work_package.get("priority", "NORMAL"),
                                  dispatched=False,
                                  reason=f"部门 {department} 未注册到 message_bus，拒绝派发")
        # 把组内/跨部门协作计划注入工作包，供部门头执行时消费
        wp = dict(work_package)
        wp.setdefault("owner", department)
        wp.setdefault("department", department)
        if internal_assignments:
            wp["internal_assignments"] = internal_assignments
        if peer_collabs:
            wp["peer_collabs"] = peer_collabs
        return self.dispatch_work_package(wp)

    def dispatch_to_squad(self, squad_id: str, work_package: Dict[str, Any],
                          department: str = "") -> DispatchResult:
        """派发工作包给一个「可调配小组」（独立于部门的共享资源）。

        小组独立于部门存在，可通过 SquadPool 调配执行任务：
          - 调配：SquadPool.acquire() 将小组标记为 BUSY，并关联调配方；
          - 执行：工作包派发给小组长（leader），经 message_bus 投递；
          - 归还：工作完成后 SquadPool.release() 将小组释放回池（可重复调用）。

        Args:
            squad_id: 目标小组 id（须已在 SquadPool 注册）
            work_package: 标准工作包
            department: 调配方部门名（用于调配记录）

        Returns:
            DispatchResult
        """
        squad = self.squad_pool.get(squad_id)
        if squad is None:
            return DispatchResult(
                task_id=work_package.get("id", "?"),
                owner=squad_id,
                task_name=work_package.get("label", "?"),
                priority=work_package.get("priority", "NORMAL"),
                dispatched=False,
                reason=f"小组 {squad_id} 未注册到 SquadPool，拒绝派发",
            )

        # 若小组尚未被调配（仍 IDLE），先调配进入 BUSY；
        # 若已被调配（BUSY）且是本调配方调度的，直接复用（避免重复 acquire）
        caller = department or self.caller_role
        task_id = work_package.get("id", "")
        # newly_acquired: 本次调用是否真正新调配了该小组（用于派发失败时精确回滚）
        newly_acquired = False
        if squad.status == SQUAD_IDLE:
            # 直接对目标小组精确 acquire，不再走 squad_pool.acquire(domain=...)
            # 搜索路径，避免误调配到同领域 assign_count 最少（却不是本目标）的其他小组。
            squad.acquire(caller, task_id)
            newly_acquired = True
        elif squad.status == SQUAD_BUSY and squad.owner_department == caller:
            # 已被本调配方占用（复用正在执行任务的小组），不再重复 acquire，
            # 但需同步更新小组当前执行的任务 id（评审 W3），确保释放/追踪一致。
            squad.task_id = task_id
            newly_acquired = False
        elif squad.status == SQUAD_BUSY:
            # 已被其他部门占用，不可重复调配（除非释放）
            return DispatchResult(
                task_id=task_id or "?",
                owner=squad.squad_id,
                task_name=work_package.get("label", "?"),
                priority=work_package.get("priority", "NORMAL"),
                dispatched=False,
                reason=f"小组 {squad.name} 已被 {squad.owner_department} 占用，无法调配",
            )
        elif squad.status == SQUAD_READY:
            # READY：任务已完成待释放，先归还回池（release 内部记录留痕），再重新调配进入 BUSY
            self.squad_pool.release(squad.squad_id)
            squad.acquire(caller, task_id)
            newly_acquired = True
        elif squad.status == SQUAD_BLOCKED:
            # BLOCKED：阻塞/异常，拒绝调配
            return DispatchResult(
                task_id=task_id or "?",
                owner=squad.squad_id,
                task_name=work_package.get("label", "?"),
                priority=work_package.get("priority", "NORMAL"),
                dispatched=False,
                reason=f"小组 {squad.name} 处于 BLOCKED 状态，无法调配",
            )
        else:
            # 未知状态兜底拒绝
            return DispatchResult(
                task_id=task_id or "?",
                owner=squad.squad_id,
                task_name=work_package.get("label", "?"),
                priority=work_package.get("priority", "NORMAL"),
                dispatched=False,
                reason=f"小组 {squad.name} 状态异常（{squad.status}），拒绝派发",
            )

        # 派发给小组长（leader）
        wp = dict(work_package)
        wp.setdefault("owner", squad.leader)
        wp.setdefault("squad_id", squad.squad_id)
        wp.setdefault("department", caller)
        result = self.dispatch_work_package(wp)
        # 派发失败时，仅释放「本次新调配」的小组归还回池；
        # 若是复用的 BUSY 小组（正在执行原任务），不误释放其占用状态。
        if not result.dispatched and newly_acquired:
            self.squad_pool.release(squad.squad_id)
        return result

    def dispatch_to_squad_by_domain(self, domain: str, work_package: Dict[str, Any],
                                    department: str = "") -> DispatchResult:
        """按领域调配一个可调配小组并派发工作包。

        在 SquadPool 中按 domain/skill 自动匹配空闲小组，调配并派发。

        Args:
            domain: 领域或技能（如 "client_dev" / "ai_dev"）
            work_package: 标准工作包
            department: 调配方部门名

        Returns:
            DispatchResult
        """
        acquire_result = self.squad_pool.acquire(
            domain=domain,
            department=department or self.caller_role,
            task_id=work_package.get("id", ""),
        )
        if not acquire_result.get("ok"):
            return DispatchResult(
                task_id=work_package.get("id", "?"),
                owner="",
                task_name=work_package.get("label", "?"),
                priority=work_package.get("priority", "NORMAL"),
                dispatched=False,
                reason=acquire_result.get("reason", "无匹配可调配小组"),
            )
        squad = acquire_result["squad"]
        result = self.dispatch_to_squad(squad.squad_id, work_package, department)
        # by_domain 是本方法自行 acquire 调配的小组（进入 dispatch_to_squad 时已是
        # BUSY 且 owner==本调配方 → newly_acquired=False，内层不会释放）。
        # 派发失败时主动归还本次调配的小组，避免小组永久停留 BUSY 造成资源泄漏，
        # 导致该领域唯一空闲小组被占死、后续 by_domain 派发一律返回 ALL_BUSY。
        if not result.dispatched:
            self.squad_pool.release(squad.squad_id)
        return result

    def release_squad(self, squad_id: str) -> Dict[str, Any]:
        """释放小组回池（任务完成后归还，可被重复调用）。"""
        return self.squad_pool.release(squad_id)

    def release_squads_by_department(self, department: str) -> List[str]:
        """释放某部门占用的全部小组。"""
        return self.squad_pool.release_by_department(department)

    def list_squads(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出全部可调配小组。"""
        return self.squad_pool.list_squads(status=status)

    def squad_summary(self) -> Dict[str, Any]:
        """可调配小组池总览。"""
        return self.squad_pool.summary()

    def dispatch_batch(self, work_packages: List[Dict[str, Any]]) -> List[DispatchResult]:
        """批量派发多个工作包（含依赖关系自动处理）。

        依赖处理：
          - 先派发无依赖/依赖已满足的工作包；
          - 有依赖的工作包自动等待依赖完成。
          - 检测循环依赖（A→B→A），发现则整体拒绝（Warning 3）。
        """
        # 循环依赖检测（DFS 环检测）
        wp_ids = {wp.get("id") for wp in work_packages if wp.get("id")}
        def _has_cycle(start: str, visiting: set, visited: set) -> bool:
            if start in visiting:
                return True
            if start in visited:
                return False
            visiting.add(start)
            wp = next((w for w in work_packages if w.get("id") == start), None)
            if wp:
                for dep in wp.get("depends_on", []):
                    if dep in wp_ids and _has_cycle(dep, visiting, visited):
                        return True
            visiting.remove(start)
            visited.add(start)
            return False

        for wp in work_packages:
            wp_id = wp.get("id")
            if wp_id and wp_id in wp_ids and _has_cycle(wp_id, set(), set()):
                results: List[DispatchResult] = []
                for w in work_packages:
                    results.append(DispatchResult(
                        task_id=w.get("id", "?"),
                        owner=w.get("owner", ""),
                        task_name=w.get("label", w.get("id", "?")),
                        priority=w.get("priority", "NORMAL"),
                        dispatched=False,
                        reason=f"检测到循环依赖，批量派发整体拒绝（{wp_id}）",
                    ))
                self.dispatch_log.extend(results)
                return results

        results: List[DispatchResult] = []
        # 按依赖排序：无依赖的优先派发
        sorted_wps = sorted(work_packages,
                            key=lambda wp: len(wp.get("depends_on", [])))
        for wp in sorted_wps:
            results.append(self.dispatch_work_package(wp))
        return results

    # ---------- 生命周期管理 ----------

    def on_complete(self, task_id: str, note: str = "") -> List[str]:
        """标记任务完成 → 自动解锁下游依赖并重新派发。

        返回: 新解锁派发的下游任务 id 列表（全部依赖满足才计入，Warning 2）
        """
        self.scheduler.on_complete(task_id, self.caller_role)
        # 处理消息队列，让解锁后的下游 TASK_ASSIGN 立即投递可见
        self.bus.process_all()
        # 找出新解锁就绪的下游任务（所有依赖均满足才报告为已解锁）
        unlocked = []
        for t in self.scheduler.queue.tasks.values():
            if (task_id in t.depends_on
                    and t.state == TaskState.TODO.value
                    and self.scheduler.queue._is_ready(t)):
                unlocked.append(t.id)
        return unlocked

    def on_fail(self, task_id: str, reason: str = "") -> None:
        """标记任务失败，通知相关方。"""
        self.scheduler.on_fail(task_id, self.caller_role, reason)

    def block(self, task_id: str, reason: str = "") -> None:
        """阻塞一个任务（依赖未满足 / 返工等）。"""
        self.scheduler.block(task_id, reason)

    # ---------- 查询 ----------

    def track(self, task_id: str) -> Optional[Dict[str, Any]]:
        """查询任务状态。"""
        t = self.scheduler.queue.tasks.get(task_id)
        if not t:
            return None
        return {
            "id": t.id,
            "name": t.name,
            "owner": t.owner,
            "state": t.state,
            "priority": t.priority,
            "progress": t.progress,
            "depends_on": t.depends_on,
            "overdue_days": t.overdue(),
        }

    def task_stats(self) -> Dict[str, int]:
        """任务状态统计。"""
        return self.scheduler.queue.stats()

    def summary(self) -> Dict[str, Any]:
        """派发能力使用统计。"""
        return {
            "caller": self.caller_role,
            "total_dispatched": len(self.dispatch_log),
            "by_priority": _count_by(self.dispatch_log, lambda r: r.priority),
            "by_owner": _count_by(self.dispatch_log, lambda r: r.owner),
            "queue_stats": self.task_stats(),
        }

    # ---------- 便捷工具 ----------

    def notify(self, to_role: str, content: Dict[str, Any],
               msg_type: str = "NOTIFICATION", topic: Optional[str] = None) -> Message:
        """向某角色/主题发送通知消息。"""
        mode = "TOPIC" if topic else "DIRECT"
        msg = Message(msg_type, self.caller_role, to_role, content,
                      mode=mode, topic=topic)
        return self.bus.publish(msg)


# ============================================================
# 辅助函数
# ============================================================

def _count_by(items, key_fn) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for it in items:
        k = key_fn(it)
        out[k] = out.get(k, 0) + 1
    return out


# ============================================================
# 演示
# ============================================================

def demo():
    print("=" * 70)
    print("统一派发工作能力（DispatchCapability）演示")
    print("  所有 Agent 共享的高频复用能力模块")
    print("=" * 70)

    bus = MessageBus()
    cap = DispatchCapability("producer", bus=bus)

    # 注册几个可派发角色
    for role in ["tech_artist", "audio_designer", "qa_engineer",
                 "eco_art_director", "eco_tech_artist", "eco_audio_designer"]:
        bus.register(role)
        bus.on(role, lambda m: None)

    print("\n[1] 单个任务派发")
    r1 = cap.dispatch("UI 制作", "tech_artist", priority="HIGH",
                      payload={"module": "ui_ux"})
    print(f"    {r1.task_name} → {r1.owner} (priority={r1.priority}) dispatched={r1.dispatched}")

    print("\n[2] 工作包派发（含依赖）")
    wp1 = {
        "id": "wp_ui_ux",
        "label": "生态 UI/UX 接入流水线",
        "owner": "eco_tech_artist",
        "department": "美术线",
        "priority": "HIGH",
        "depends_on": [],
    }
    wp2 = {
        "id": "wp_audio",
        "label": "生态音频接入流水线",
        "owner": "eco_audio_designer",
        "department": "美术线",
        "priority": "HIGH",
        "depends_on": [],
    }
    r2 = cap.dispatch_work_package(wp1)
    r3 = cap.dispatch_work_package(wp2)
    print(f"    {r2.task_name} → {r2.owner} dispatched={r2.dispatched}")
    print(f"    {r3.task_name} → {r3.owner} dispatched={r3.dispatched}")

    print("\n[3] 批量派发")
    batch = [
        {"id": "wp_art_testing", "label": "美术线验收回归", "owner": "qa_engineer",
         "department": "测试线", "priority": "NORMAL",
         "depends_on": ["wp_ui_ux", "wp_audio"]},
        {"id": "wp_art_direction", "label": "美术品质基准", "owner": "eco_art_director",
         "department": "美术线", "priority": "HIGH"},
    ]
    batch_results = cap.dispatch_batch(batch)
    for r in batch_results:
        print(f"    {r.task_name} → {r.owner} dispatched={r.dispatched}")

    print("\n[4] 任务状态统计")
    for k, v in cap.task_stats().items():
        print(f"    {k}: {v}")

    print("\n[5] 完成 wp_art_direction → 解锁依赖它的下游")
    # 完成前置，看 wp_art_testing 的依赖是否满足
    cap.on_complete("wp_ui_ux")
    cap.on_complete("wp_audio")
    cap.on_complete("wp_art_direction")
    wp_testing = cap.track("wp_art_testing")
    if wp_testing:
        print(f"    wp_art_testing: state={wp_testing['state']} (依赖全部完成 → 应就绪)")

    print("\n[6] 派发能力使用统计")
    for k, v in cap.summary().items():
        if k == "queue_stats":
            print(f"    {k}: {v}")
        else:
            print(f"    {k}: {v}")

    # wp_art_testing 依赖 wp_ui_ux+wp_audio，依赖未满足时应 dispatched=False（Bug2 修复）
    # 但 on_complete 解锁后应自动派发；此处校验核心派发链路均成功
    ok = (r1.dispatched and r2.dispatched and r3.dispatched
          and all(r.dispatched for r in batch_results
                  if r.owner != "qa_engineer"))
    ok = ok and cap.track("wp_art_testing")["state"] == TaskState.TODO.value
    print(f"\n结果: {'🟢 通过' if ok else '🔴 未通过'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(demo())

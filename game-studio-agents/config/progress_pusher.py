# ============================================================
# 进度督导 Agent（Progress Pusher）— 程序规则化 + 声明化策略
# 版本: v1.0
# 说明: 把"盯 DDL、主动催、识别阻塞并升级"落地为**可生效**的督导 Agent。
#
# 三层设计（回答"skill / 声明 / 程序规则"三者之选）：
#   1. 程序规则化（本文件）：真正的执行体。继承 BaseAgent，
#      复用 TaskQueue/MessageBus，用 DecisionEngine 规则引擎做
#      确定性决策（WATCH / PUSH / ESCALATE），订阅任务事件 +
#      定时扫描，**接入总线真正生效**（不是只读的演示）。
#   2. 声明化（progress_pusher_policy.yaml）：把阈值/节奏/打扰成本
#      抽成 YAML 策略，改配置即可调行为，不碰代码，保证"稳定"。
#   3. skill/用法（docs/进度督导使用指南.md）：稳定可用的部署与使用说明。
#
# 语言: Python 3 (可运行)
# 依赖: 同目录下的 message_bus.py / agent_core.py / task_scheduler.py
# ============================================================
from __future__ import annotations

import time
from collections import deque
from typing import Any, Dict, Optional

from agent_core import BaseAgent, DecisionRule
from message_bus import Message
from task_scheduler import Task, TaskQueue

try:
    import yaml  # 可选依赖：缺失时回退默认策略，督导仍可运行
except ImportError:  # pragma: no cover
    yaml = None


# ============================================================
# 一、策略加载（声明化参数）
# ============================================================

DEFAULT_POLICY = {
    "role_id": "progress_pusher",
    "lag_threshold_days": 2.0,
    "near_ddl_warn_hours": 12.0,
    "block_timeout_hours": 24.0,
    "escalate_to": "project_manager",
    "push_cooldown_hours": 6.0,
    "max_pushes_per_task": 3,
    # ESCALATE 打扰成本控制：同一任务两次升级的最小间隔(小时)，
    # 防止持续 BLOCKED / 已催满的任务每次扫描都向 PM 轰炸升级通知。
    "escalate_cooldown_hours": 24.0,
    # 决策留痕上限：超过则滚动丢弃最旧记录，防长驻 Agent 内存泄漏。
    "max_decisions_keep": 1000,
    "scan_interval_sec": 30.0,
    "watch_topic": "task_events",
    "notify_owner_on_push": True,
    "notify_pm_on_escalate": True,
}


def load_policy(path: Optional[str] = None) -> Dict[str, Any]:
    """加载 YAML 策略；缺失/出错时回退到默认策略，保证督导总能生效。"""
    if path is None:
        import os
        path = os.path.join(os.path.dirname(__file__), "progress_pusher_policy.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        policy = data.get("progress_pusher_policy", {})
        # 只覆盖存在的键，缺失的用默认值（版本升级更稳健）
        merged = {**DEFAULT_POLICY, **policy}
        return merged
    except Exception as exc:  # noqa: BLE001 —— 配置异常不能阻断督导启动
        print(f"[进度督导] 策略加载失败({exc})，回退默认策略")
        return dict(DEFAULT_POLICY)


# ============================================================
# 二、进度督导 Agent
# ============================================================

class ProgressPusherAgent(BaseAgent):
    """进度督导：盯 DDL、主动催、识别阻塞并升级（可生效）。

    与 v0.2 的差异（v1.0 升级点）：
      - 不再自造 TaskStatus，直接复用 task_scheduler.Task / TaskQueue；
      - 决策逻辑改为 DecisionEngine 规则引擎（确定性、可测试、稳定）；
      - 接入 MessageBus：订阅 task_events + 定时扫描 TaskQueue，
        催办/升级都通过总线真实发出，真正"生效"；
      - 打扰成本控制：冷却期 + 最大催办次数，避免过度打扰。
    """

    def __init__(self, role_id: str = "progress_pusher",
                 bus=None, queue: Optional[TaskQueue] = None,
                 policy: Optional[Dict[str, Any]] = None,
                 policy_path: Optional[str] = None):
        super().__init__(role_id, bus)
        self.policy = policy or load_policy(policy_path)
        self.queue = queue or TaskQueue()          # 复用主任务队列

        # 状态机：与 ecosystem_roles.yaml / roles.yaml 声明的进度督导状态一致
        # （IDLE/TRACKING/PUSHING/ESCALATING/WARNING）。覆写基类通用生命周期，
        # 使 _do_push/_do_escalate 中的 PUSHING/ESCALATING 等生态状态合法，
        # 避免触发 state_fail（评审点 #1）。不污染 agent_core 全局状态表。
        self.transitions = {
            "BOOT": ["IDLE", "TRACKING", "PUSHING", "ESCALATING", "WARNING"],
            "IDLE": ["TRACKING", "PUSHING", "ESCALATING", "WARNING", "STOPPED"],
            "TRACKING": ["IDLE", "PUSHING", "ESCALATING", "WARNING"],
            "PUSHING": ["IDLE", "TRACKING", "ESCALATING", "WARNING"],
            "WARNING": ["IDLE", "TRACKING", "PUSHING", "ESCALATING"],
            "ESCALATING": ["IDLE", "TRACKING", "WARNING"],
        }
        self._last_scan = 0.0
        self.pushed_at: Dict[str, float] = {}       # task_id -> 上次催办时间
        self.push_count: Dict[str, int] = {}        # task_id -> 累计正式催办次数(firm)
        self.warn_count: Dict[str, int] = {}        # task_id -> 累计友好预警次数(soft)
        self.escalated_at: Dict[str, float] = {}    # task_id -> 上次升级时间
        self.escalate_count: Dict[str, int] = {}    # task_id -> 累计升级次数
        # 决策留痕（审计/复盘）：deque 定长滚动，防止无界增长导致内存泄漏
        self.decisions: deque = deque(maxlen=int(self.policy.get("max_decisions_keep", 1000)))

    # ---------- 启动：加载策略 + 注册规则 + 订阅事件 ----------
    def on_boot(self):
        p = self.policy
        # 订阅全局任务事件（完成/阻塞/失败），事件驱动感知状态变化
        if p.get("watch_topic"):
            self.bus.subscribe(
                self.role_id,
                handler=lambda m: self._on_task_event(m),
                topic=p["watch_topic"],
            )

        # 注册决策规则（顺序即优先级：先升级，再催办，再预警）
        # ESCALATE 规则带 escalate_cooling 守卫：处于升级冷却期内不重复升级，
        # 防止持续 BLOCKED / 已催满的任务每次扫描都向 PM 轰炸升级通知。
        self.decision.add_rule(DecisionRule(
            name="阻塞超时→升级",
            conditions=[
                {"key": "state", "op": "==", "value": "BLOCKED"},
                {"key": "blocked_hours", "op": ">=", "value": p["block_timeout_hours"]},
                {"key": "escalate_cooling", "op": "==", "value": False},
            ],
            action="ESCALATE",
            fallback=None,
        ))
        # 声明与实现一致：YAML 声明"催办次数达 max_pushes_per_task 后必须升级"。
        # 当单任务累计**正式催办**已达上限且仍未完成 → 升级项目经理（不再无效催办）。
        # 该规则必须放在"落后→催办"之前，否则催满后 PUSH 不匹配会落入 WARN，永不升级。
        # 注意：WARN(soft 预警) 不消耗正式催办额度，故此处用正式催办次数 pushes。
        self.decision.add_rule(DecisionRule(
            name="催办达上限仍未完成→升级",
            conditions=[
                {"key": "pushes", "op": ">=", "value": p["max_pushes_per_task"]},
                {"key": "state", "op": "!=", "value": "DONE"},
                {"key": "escalate_cooling", "op": "==", "value": False},
            ],
            action="ESCALATE",
            fallback=None,
        ))
        # 升级冷却期内：不轰炸 PM，降级为低频 WARN 预警（只提示不重复升级）
        self.decision.add_rule(DecisionRule(
            name="升级冷却期→降级预警",
            conditions=[
                {"key": "escalate_cooling", "op": "==", "value": True},
                {"key": "state", "op": "!=", "value": "DONE"},
            ],
            action="WARN",
            fallback=None,
        ))
        self.decision.add_rule(DecisionRule(
            name="落后超阈值→催办",
            conditions=[
                {"key": "overdue_days", "op": ">=", "value": p["lag_threshold_days"]},
                {"key": "state", "op": "!=", "value": "DONE"},
                {"key": "cooling", "op": "==", "value": False},
                {"key": "pushes", "op": "<", "value": p["max_pushes_per_task"]},
            ],
            action="PUSH",
            fallback=None,
        ))
        self.decision.add_rule(DecisionRule(
            name="临近DDL→预警",
            conditions=[
                {"key": "near_ddl", "op": "==", "value": True},
                {"key": "state", "op": "!=", "value": "DONE"},
                {"key": "cooling", "op": "==", "value": False},
            ],
            action="WARN",
            fallback=None,
        ))
        # 兜底：其余情况一律 WATCH（只跟踪不打扰），保证每个任务都有确定决策
        self.decision.add_rule(DecisionRule(
            name="默认跟踪",
            conditions=[],
            action="WATCH",
            fallback=None,
        ))

    # ---------- 事件驱动：感知任务状态变化 ----------
    def _on_task_event(self, msg: Message):
        """收到任务事件（task_done / task_failed / task_blocked）时即时重新监督该任务。

        事件驱动真正"感知状态变化"：状态变化往往意味着决策条件改变
        （如阻塞→解除、逾期加剧），这里对该任务立即触发一次 supervise，
        而非仅打日志、静等下一次心跳扫描，避免督导响应滞后。
        """
        evt = msg.content.get("event", "")
        task_id = msg.content.get("task_id")
        if task_id and evt:
            self._log("event", f"收到 {evt} 事件: {task_id}")
            task = self.queue.tasks.get(task_id)
            if task is not None:
                # 状态变化后立即重新决策（心跳扫描之外的即时督导路径）
                self.supervise(task, now=time.time())

    # ---------- 心跳：定时扫描任务队列（核心督导循环） ----------
    def heartbeat(self):
        interval = float(self.policy.get("scan_interval_sec", 0))
        now = time.time()
        if interval <= 0 or (now - self._last_scan) < interval:
            return
        self._last_scan = now
        self.scan(now=now)

    def scan(self, now: Optional[float] = None):
        """扫描整个 TaskQueue，对每个任务做一次督导决策并执行。"""
        now = now or time.time()
        for task in list(self.queue.tasks.values()):
            self.supervise(task, now=now)

    # ---------- 单任务督导（程序规则化的决策点） ----------
    def supervise(self, task: Task, now: Optional[float] = None) -> Dict[str, Any]:
        """对单个任务执行督导决策，返回决策结果。

        返回结构: {task_id, action, reason, source, confidence}
        """
        now = now or time.time()
        p = self.policy

        # 计算决策上下文
        overdue_days = task.overdue(now)          # 逾期天数（Task 自带）
        state = task.state
        # 阻塞时长：用 updated_at 近似（真实场景应从阻塞事件时间计算）
        blocked_hours = 0.0
        if state == "BLOCKED" and task.updated_at:
            blocked_hours = (now - task.updated_at) / 3600.0
        # 是否处于冷却期（避免过度打扰）
        last_push = self.pushed_at.get(task.id, 0.0)
        cooling = (now - last_push) < (p["push_cooldown_hours"] * 3600.0)
        # 正式催办次数（仅 firm PUSH 计入升级额度；WARN soft 预警不消耗）
        pushes = self.push_count.get(task.id, 0)
        # 是否处于升级冷却期（避免重复向 PM 轰炸升级通知）
        last_escalate = self.escalated_at.get(task.id, 0.0)
        escalate_cooling = (now - last_escalate) < (p["escalate_cooldown_hours"] * 3600.0)
        # 是否临近 DDL
        near_ddl = False
        if task.ddl and state != "DONE":
            near_ddl = (task.ddl - now) <= (p["near_ddl_warn_hours"] * 3600.0)

        ctx = {
            "task_id": task.id,
            "state": state,
            "overdue_days": overdue_days,
            "blocked_hours": blocked_hours,
            "cooling": cooling,
            "pushes": pushes,
            "near_ddl": near_ddl,
            "escalate_cooling": escalate_cooling,
        }
        decision = self.decision.decide(ctx)
        decision["task_id"] = task.id
        self.decisions.append(decision)
        self._log("decision", f"{task.id} -> {decision['action']} ({decision['reason']})")

        # 执行动作
        action = decision["action"]
        if action == "ESCALATE":
            self._do_escalate(task, reason=decision["reason"])
        elif action == "PUSH":
            self._do_push(task, intensity="firm", reason=decision["reason"])
        elif action == "WARN":
            self._do_push(task, intensity="soft", reason=decision["reason"])
        # WATCH / 其它 → 仅跟踪
        return decision

    # ---------- 动作执行 ----------
    def _do_push(self, task: Task, intensity: str, reason: str):
        """发出催办/预警通知（走总线，真正生效）。

        打扰成本控制（与策略语义一致）：
          - firm(正式催办) 才计入 push_count，消耗 max_pushes_per_task 升级额度；
          - soft(WARN 友好预警) 单独计入 warn_count，不消耗正式催办额度；
          - 仅在真正发送通知（notify_owner_on_push 且任务有 owner）时才累加计数。
        """
        p = self.policy
        now = time.time()
        self.pushed_at[task.id] = now
        self._transition("PUSHING")

        if intensity == "firm":
            msg_type = "NOTIFICATION"
            content = {
                "action": "PUSH", "task_id": task.id,
                "overdue_days": task.overdue(now),
                "intensity": p.get("reminder_intensity", {}).get("push", "firm"),
                "reason": reason,
                "push_no": self.push_count.get(task.id, 0) + 1,
            }
            priority = "URGENT" if task.overdue(now) > p["lag_threshold_days"] else "HIGH"
        else:  # soft / warn
            msg_type = "NOTIFICATION"
            content = {
                "action": "WARN", "task_id": task.id,
                "hours_to_ddl": round((task.ddl - now) / 3600.0, 1) if task.ddl else None,
                "intensity": p.get("reminder_intensity", {}).get("warn", "soft"),
                "reason": reason,
                "warn_no": self.warn_count.get(task.id, 0) + 1,
            }
            priority = "NORMAL"

        # 仅在真正发送通知时累加对应计数（soft 预警不消耗正式催办额度）
        if p.get("notify_owner_on_push") and task.owner:
            self.send(msg_type, task.owner, content, priority=priority)
            if intensity == "firm":
                self.push_count[task.id] = self.push_count.get(task.id, 0) + 1
            else:
                self.warn_count[task.id] = self.warn_count.get(task.id, 0) + 1
        # 记录（供测试/审计断言）
        self._log("push", f"{task.id} 强度={intensity} 次数={self.push_count.get(task.id, 0)}")

    def _do_escalate(self, task: Task, reason: str):
        """阻塞超时/催办无效 → 升级项目经理（带冷却/上限保护）。

        每次升级记录时间与次数；若已处于升级冷却期内（supervise 已降级为 WARN），
        此处不会重复发送升级通知，避免长期 BLOCKED / 已催满的任务高频轰炸 PM。
        """
        p = self.policy
        now = time.time()
        self.escalated_at[task.id] = now
        self.escalate_count[task.id] = self.escalate_count.get(task.id, 0) + 1
        self._transition("ESCALATING")
        content = {
            "action": "ESCALATE", "task_id": task.id,
            "owner": task.owner, "blocker": task.state,
            "intensity": p.get("reminder_intensity", {}).get("escalate", "urgent"),
            "reason": reason,
            "push_count": self.push_count.get(task.id, 0),
            "escalate_no": self.escalate_count[task.id],
        }
        target = p.get("escalate_to", "project_manager")
        if p.get("notify_pm_on_escalate"):
            self.send("NOTIFICATION", target, content, priority="URGENT")
        self._log("escalate", f"{task.id} -> {target} (第{self.escalate_count[task.id]}次)")

    # ---------- 消息处理（BaseAgent 抽象方法） ----------
    def handle_task(self, msg: Message):
        """处理直接发来的消息（如项目经理让其人工盯某个任务）。"""
        if msg.type == "TASK_ASSIGN":
            task_id = msg.content.get("task_id")
            if task_id in self.queue.tasks:
                self.supervise(self.queue.tasks[task_id])

    # ---------- 报告 ----------
    def report(self) -> Dict[str, Any]:
        base = super().report()
        base.update({
            "watched_tasks": len(self.queue.tasks),
            "pushes": sum(self.push_count.values()),
            "warns": sum(self.warn_count.values()),
            "escalates": sum(self.escalate_count.values()),
            "decisions": len(self.decisions),
        })
        return base


# ============================================================
# 三、与主任务队列/调度器打通（可生效接入点）
# ============================================================

def attach_to_scheduler(scheduler, pusher: ProgressPusherAgent):
    """把进度督导挂到现有 Scheduler 的 TaskQueue 上，共享同一份任务。

    这样任务由 scheduler 派发执行、进度督导负责盯 DDL 催办升级，
    二者共享同一 TaskQueue 实例，数据一致、互不冲突。
    """
    pusher.queue = scheduler.queue
    return pusher


# ============================================================
# 四、演示
# ============================================================

def demo():
    print("=" * 60)
    print("进度督导 Agent（程序规则化 + 声明化策略）演示")
    print("=" * 60)

    from message_bus import MessageBus
    from task_scheduler import Scheduler, Task

    bus = MessageBus()
    queue = TaskQueue()
    sched = Scheduler(queue=queue, bus=bus)
    pusher = ProgressPusherAgent(bus=bus, queue=queue)
    attach_to_scheduler(sched, pusher)
    pusher.boot()

    now = time.time()

    # 1) 正常任务（不应打扰）
    t_ok = Task(id="t_ok", name="正常任务", owner="client_dev", priority="NORMAL",
                ddl=now + 86400 * 5, progress=0.8)
    t_ok.updated_at = now
    queue.add(t_ok)

    # 2) 落后任务（应 PUSH 催办）
    t_late = Task(id="t_late", name="逾期任务", owner="client_dev", priority="HIGH",
                  ddl=now - 86400 * 3, progress=0.5)
    t_late.updated_at = now
    queue.add(t_late)

    # 3) 阻塞超时任务（应 ESCALATE 升级）
    t_block = Task(id="t_block", name="阻塞任务", owner="qa_engineer", priority="URGENT",
                   ddl=now + 86400, progress=0.2)
    t_block.touch("BLOCKED", "依赖缺失")
    t_block.updated_at = now - 86400 * 2   # 阻塞了 48h > 24h 阈值
    queue.add(t_block)

    # 4) 临近 DDL 未完成（应 WARN 预警）
    t_near = Task(id="t_near", name="临近DDL任务", owner="system_designer",
                  priority="HIGH", ddl=now + 3600 * 4, progress=0.9)  # 4h 后到期
    t_near.updated_at = now
    queue.add(t_near)

    # 5) 催办已达上限仍未完成（应 ESCALATE 升级，不再无效催办）
    t_exhaust = Task(id="t_exhaust", name="催满未完成任务", owner="server_dev",
                     priority="HIGH", ddl=now - 86400 * 10, progress=0.4)
    t_exhaust.updated_at = now
    queue.add(t_exhaust)
    pusher.push_count["t_exhaust"] = pusher.policy["max_pushes_per_task"]  # 已催满 3 次
    pusher.pushed_at["t_exhaust"] = now  # 不在冷却期

    # 督导扫描
    pusher.scan(now=now)
    bus.process_all()   # 把督导发出的催办/升级消息真正经总线派发并留痕

    print(f"\n[进度督导] 扫描 {len(queue.tasks)} 个任务：")
    for d in pusher.decisions:
        print(f"  - {d['task_id']:<8} -> {d['action']:<8} ({d['reason']})")

    # 验证催办/升级消息确实经总线发出
    pushes = [m for m in bus.delivered if m.type == "NOTIFICATION" and m.to_role != "*"]
    print(f"\n[总线] 已发出督导消息 {len(pushes)} 条：")
    for m in pushes:
        print(f"  - {m.content.get('action')}:{m.content.get('task_id')} -> {m.to_role} (priority={m.priority})")

    # 结论断言（供测试信号灯）
    actions = {d["task_id"]: d["action"] for d in pusher.decisions}
    print("\n[断言]")
    print(f"  - 正常任务 t_ok      应 WATCH  -> {actions.get('t_ok')}")
    print(f"  - 逾期任务 t_late     应 PUSH   -> {actions.get('t_late')}")
    print(f"  - 阻塞任务 t_block    应 ESCALATE -> {actions.get('t_block')}")
    print(f"  - 临近任务 t_near     应 WARN   -> {actions.get('t_near')}")
    print(f"  - 催满任务 t_exhaust  应 ESCALATE -> {actions.get('t_exhaust')}")

    ok = (actions.get("t_ok") in ("WATCH", "WARN")
          and actions.get("t_late") == "PUSH"
          and actions.get("t_block") == "ESCALATE"
          and actions.get("t_near") == "WARN"
          and actions.get("t_exhaust") == "ESCALATE")
    print(f"\n结果: {'🟢 通过' if ok else '🔴 未通过'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(demo())

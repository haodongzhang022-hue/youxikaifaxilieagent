# ============================================================
# 通用 Agent 内核基类 (BaseAgent / AgentCore)
# 版本: v0.3
# 说明: 所有 Agent / 生态角色的通用运行时内核。封装：
#       - 生命周期（BOOT→IDLE→...→STOPPED，与 v0.1 一致）
#       - 状态机（事件驱动的状态转换）
#       - 决策引擎（规则 + 知识库 + LLM 可选）
#       - 消息处理（接入 MessageBus，接收/发送/回复）
#       - 知识库与经验学习
# 本模块与具体岗位、生态角色完全解耦：任何角色只需继承 BaseAgent
# 并实现自己的任务处理方法即可，架构调整不影响内核本身。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from message_bus import Message, MessageBus, build_message
from role_collaboration import CollaborationWorkbench

# 统一派发工作能力（所有 Agent 共享的高频复用模块）
# 延迟 import 以避免循环依赖（dispatch_capability 只依赖 message_bus / task_scheduler）


# ============================================================
# 一、生命周期状态（与 v0.1 agent_behavior.py 一致）
# ============================================================

LIFECYCLE_STATES = [
    "BOOT",           # 启动，加载配置与知识库
    "IDLE",           # 空闲，等待任务
    "RECEIVING",      # 接收任务/消息
    "ANALYZING",      # 分析需求
    "PLANNING",       # 制定计划
    "EXECUTING",      # 执行任务
    "VERIFYING",      # 验证产出
    "DELIVERING",     # 交付产出
    "WAITING_REVIEW", # 等待上级审核
    "HANDLING_FEEDBACK",  # 处理反馈
    "REPORTING",      # 汇报状态
    "ERROR",          # 异常状态
    "STOPPED",        # 停止
]

# 默认状态转换表（与 v0.1 一致）
DEFAULT_TRANSITIONS = {
    "BOOT": ["IDLE"],
    "IDLE": ["RECEIVING", "REPORTING", "STOPPED"],
    "RECEIVING": ["ANALYZING", "IDLE"],
    "ANALYZING": ["PLANNING", "IDLE", "ERROR"],
    "PLANNING": ["EXECUTING", "ANALYZING"],
    "EXECUTING": ["VERIFYING", "ERROR"],
    "VERIFYING": ["DELIVERING", "EXECUTING", "ERROR"],
    "DELIVERING": ["WAITING_REVIEW", "IDLE"],
    "WAITING_REVIEW": ["IDLE", "HANDLING_FEEDBACK"],
    "HANDLING_FEEDBACK": ["EXECUTING", "DELIVERING", "REPORTING"],
    "REPORTING": ["IDLE"],
    "ERROR": ["ANALYZING", "IDLE", "STOPPED"],
}


# ============================================================
# 二、知识库
# ============================================================

class KnowledgeBase:
    """Agent 知识库：文档、经验、模板，供决策引擎查询与学习"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.documents: Dict[str, Any] = {}
        self.experience: List[Dict[str, Any]] = []
        self.templates: Dict[str, Any] = {}

    def add_doc(self, key: str, value: Any):
        self.documents[key] = value

    def query(self, context: Dict[str, Any]) -> List[Any]:
        """按上下文关键词查询相关知识（简化：做文档标题/标签匹配）"""
        results = []
        keywords = [str(v).lower() for v in context.values()]
        for key, doc in self.documents.items():
            if any(kw in key.lower() for kw in keywords if len(kw) > 1):
                results.append(doc)
        return results

    def learn(self, context: Dict[str, Any], action: str, result: Any):
        """记录经验，供后续决策参考"""
        self.experience.append({
            "time": time.time(),
            "context": context,
            "action": action,
            "result": result,
        })

    def set_template(self, ttype: str, tpl: Any):
        self.templates[ttype] = tpl

    def get_template(self, ttype: str) -> Optional[Any]:
        return self.templates.get(ttype)


# ============================================================
# 三、决策引擎
# ============================================================

@dataclass
class DecisionRule:
    """一条规则：全部条件满足则触发 action，否则 fallback"""
    name: str
    conditions: List[Dict[str, Any]]
    action: Any
    fallback: Any = None

    def evaluate(self, context: Dict[str, Any]) -> bool:
        for cond in self.conditions:
            key = cond.get("key")
            value = context.get(key)
            op = cond.get("op", "==")
            target = cond.get("value")
            if not _compare(value, op, target):
                return False
        return True


def _compare(actual, op, target) -> bool:
    """通用比较操作符"""
    try:
        if op == "==":
            return actual == target
        if op == "!=":
            return actual != target
        if op == ">=":
            return actual >= target
        if op == "<=":
            return actual <= target
        if op == ">":
            return actual > target
        if op == "<":
            return actual < target
        if op == "in":
            return actual in target
    except TypeError:
        return False
    return False


class DecisionEngine:
    """
    混合决策引擎：规则匹配（快速路径）→ 知识库辅助 → LLM 推理（可选）→ 人工兜底。
    决策结果统一带 reason / confidence / source 字段。
    """

    def __init__(self, agent, llm: Optional[Callable[[Dict], Dict]] = None):
        self.agent = agent
        self.rules: List[DecisionRule] = []
        self.llm = llm

    def add_rule(self, rule: DecisionRule):
        self.rules.append(rule)

    def decide(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # 第一步：规则匹配
        for rule in self.rules:
            if rule.evaluate(context):
                return {
                    "action": rule.action,
                    "reason": f"命中规则: {rule.name}",
                    "confidence": 0.95,
                    "source": "rule",
                }
            elif rule.fallback is not None:
                return {
                    "action": rule.fallback,
                    "reason": f"未满足规则: {rule.name}",
                    "confidence": 0.7,
                    "source": "rule_fallback",
                }

        # 第二步：知识库辅助
        knowledge = self.agent.knowledge.query(context)
        context["knowledge_hits"] = knowledge

        # 第三步：LLM 推理（复杂决策）
        if self.llm is not None and context.get("complexity", 0) > 5:
            decision = self.llm(context)
            return {
                "action": decision.get("action", "NEED_HUMAN_REVIEW"),
                "reason": decision.get("reasoning", "LLM 推理"),
                "confidence": decision.get("confidence", 0.5),
                "source": "llm_reasoning",
            }

        # 兜底：需要人工确认
        return {
            "action": "NEED_HUMAN_REVIEW",
            "options": self.agent.suggest_options(context),
            "reason": "无规则/知识可自动决策",
            "confidence": 0.1,
            "source": "unknown",
        }


# ============================================================
# 四、通用 Agent 内核
# ============================================================

class BaseAgent(ABC):
    """
    通用 Agent 基类。子类需实现：
      - handle_task(msg)  : 处理主业务任务
    可选覆写：
      - on_boot / on_idle / on_message / suggest_options
    """

    def __init__(self, role_id: str, bus: Optional[MessageBus] = None):
        self.role_id = role_id
        self.name = role_id
        self.state = "BOOT"
        self.transitions = {k: list(v) for k, v in DEFAULT_TRANSITIONS.items()}
        self.knowledge = KnowledgeBase(role_id)
        self.decision = DecisionEngine(self)
        self.bus = bus or MessageBus()
        self.status = "BOOT"
        # 角色间协作工作台：支持多角色互相@（转交/分工/协作请求）
        self.collab = CollaborationWorkbench()
        self.log: List[Dict[str, Any]] = []
        self._running = False

        # 注册到消息总线
        self.bus.register(role_id)
        self.bus.on(role_id, self._receive)

        # 统一派发工作能力（所有 Agent 共享）
        # 通过 DispatchCapability 让每个 Agent 都能：
        #   - dispatch(): 派发任务/工作包给其他角色
        #   - dispatch_work_package(): 派发标准工作包
        #   - dispatch_batch(): 批量派发（含依赖）
        #   - on_complete(): 完成 → 自动解锁下游并派发
        #   - on_fail(): 标记失败
        #   - track(): 查询任务状态
        # 用法见 config/dispatch_capability.py 的 DISPATCH_GUIDE
        self._dispatch_cap = None  # 惰性初始化

    def dispatch_capability(self):
        """获取本 Agent 的统一派发能力（懒加载）。

        返回 DispatchCapability 实例，即可使用 dispatch / dispatch_batch /
        on_complete / on_fail / track 等能力。
        """
        if self._dispatch_cap is None:
            # 延迟 import，避免循环依赖
            from dispatch_capability import DispatchCapability
            self._dispatch_cap = DispatchCapability(
                caller_role=self.role_id, bus=self.bus)
        return self._dispatch_cap

    # ---------- 统一派发能力快捷方法 ----------

    def dispatch(self, task_name: str, owner: str, priority: str = "NORMAL",
                 depends_on: list = None, payload: dict = None, ddl: float = None,
                 task_id: str = None):
        """派发一个任务给指定角色。"""
        return self.dispatch_capability().dispatch(
            task_name=task_name, owner=owner, priority=priority,
            depends_on=depends_on, payload=payload, ddl=ddl, task_id=task_id)

    def dispatch_work_package(self, work_package: dict):
        """派发一个标准工作包。"""
        return self.dispatch_capability().dispatch_work_package(work_package)

    def dispatch_batch(self, work_packages: list):
        """批量派发多个工作包（含依赖）。"""
        return self.dispatch_capability().dispatch_batch(work_packages)

    def dispatch_complete(self, task_id: str, note: str = ""):
        """标记任务完成 → 自动解锁下游并派发。"""
        return self.dispatch_capability().on_complete(task_id, note)

    def dispatch_fail(self, task_id: str, reason: str = ""):
        """标记任务失败。"""
        return self.dispatch_capability().on_fail(task_id, reason)

    def dispatch_track(self, task_id: str):
        """查询任务状态。"""
        return self.dispatch_capability().track(task_id)

    # ---------- 生命周期 ----------
    def boot(self) -> "BaseAgent":
        """启动：加载配置与知识库"""
        self.on_boot()
        self._transition("IDLE")
        self._log("boot", "Agent 就绪")
        return self

    def start(self):
        """进入主循环（阻塞式）"""
        if self.state == "BOOT":
            self.boot()
        self._running = True
        while self._running and self.state != "STOPPED":
            self.bus.process()
            self.heartbeat()
            time.sleep(0.01)
        return self

    def stop(self):
        self._running = False
        self._transition("STOPPED")

    def heartbeat(self):
        """心跳：可覆写做定期检查（如进度督导扫描任务）"""
        pass

    # ---------- 状态机 ----------
    def _transition(self, new_state: str) -> bool:
        if new_state == self.state:   # 原地停留视为幂等，允许
            return True
        allowed = self.transitions.get(self.state, [])
        if self.state == "BOOT":  # BOOT 允许直接去任何初始状态
            allowed = LIFECYCLE_STATES
        if new_state in allowed:
            self.state = new_state
            self.status = new_state
            self._log("state", f"{self.state}")
            return True
        self._log("state_fail", f"{self.state} -> {new_state} 不允许")
        return False

    def can(self, target: str) -> bool:
        """检查是否可转换到目标状态"""
        return target in self.transitions.get(self.state, [])

    # ---------- 消息处理 ----------
    def _receive(self, msg: Message):
        """总线回调：统一入口"""
        self._transition("RECEIVING")
        self.on_message(msg)
        self._handle_by_type(msg)

    def _handle_by_type(self, msg: Message):
        """按消息类型分发。

        角色间互相@ 的协作消息（HANDOFF/DELEGATE/COLLAB_REQ/ACK/COLLAB_NOTIFY）
        由通用 `_on_collab_event` 统一路由，不进入子类的 handle_task，
        避免各角色 Agent 各自重复实现/重复落库。
        """
        self._transition("ANALYZING")
        if msg.type in ("HANDOFF", "DELEGATE", "COLLAB_REQ", "ACK", "COLLAB_NOTIFY"):
            self._on_collab_event(msg)
        else:
            self.handle_task(msg)
        self._transition("IDLE")

    def _on_collab_event(self, msg: Message):
        """通用角色间协作事件路由（任意角色 Agent 均可消费）。

        幂等守卫：对自发起消息（from_role == 本角色）跳过，避免便捷方法
        直接落库后，经总线回流再被二次处理（如 DELEGATE 二次重置 sub_tasks）。
        """
        if msg.from_role == self.role_id:
            self._log("collab_idempotent", f"自发起协作消息 {msg.type} 跳过，已直接落库")
            return
        c = msg.content or {}
        task_id = c.get("task_id", "")
        if not task_id:
            self._log("collab", f"协作事件缺少 task_id: {msg.type}")
            return
        try:
            if msg.type == "HANDOFF":
                self.collab.handoff(task_id, c.get("title", ""),
                                    msg.from_role, msg.to_role,
                                    note=c.get("note", ""))
                self._log("collab_handoff", f"{msg.from_role}@转交 {task_id} -> {msg.to_role}")
            elif msg.type == "DELEGATE":
                self.collab.delegate(task_id, c.get("title", ""),
                                     msg.from_role,
                                     c.get("assignments", []),
                                     note=c.get("note", ""))
                self._log("collab_delegate",
                          f"{msg.from_role}@分工 {task_id} -> {c.get('assignments', [])}")
                # 汇总分工进度并发回发起者
                self.bus.publish(build_message(
                    "COLLAB_NOTIFY", self.role_id, msg.from_role,
                    {"task_id": task_id, "sub_tasks": list(
                        self.collab.records.get(task_id).sub_tasks.keys())
                     if task_id in self.collab.records else [],
                     "event": "DELEGATE_OFFERED"}))
            elif msg.type == "COLLAB_REQ":
                self.collab.request_collab(task_id, c.get("title", ""),
                                           msg.from_role, msg.to_role,
                                           need=c.get("need", ""))
                self._log("collab_request", f"{msg.from_role}@请求 {msg.to_role} 协助 {task_id}")
            elif msg.type == "ACK":
                self.collab.acknowledge(task_id, msg.from_role,
                                        c.get("action", ""),
                                        reason=c.get("reason", ""),
                                        reassign_to=c.get("reassign_to"))
                self._log("collab_ack", f"{msg.from_role} 对 {task_id} 执行 {c.get('action')}")
            elif msg.type == "COLLAB_NOTIFY":
                self._log("collab_notify", f"协作进度通知: {task_id} {str(c)}")
        except Exception as e:  # pragma: no cover
            self._log("collab_error", f"{task_id}: {e}")

    @abstractmethod
    def handle_task(self, msg: Message):
        """子类实现：处理业务消息"""
        raise NotImplementedError

    # ---------- 通信工具 ----------
    def send(self, msg_type: str, to_role: str, content: Dict[str, Any],
             **kwargs) -> Message:
        """发送一条消息到总线"""
        msg = Message(type=msg_type, from_role=self.role_id, to_role=to_role,
                      content=content, **kwargs)
        return self.bus.publish(msg)

    def reply(self, original: Message, msg_type: str, content: Dict[str, Any],
              **kwargs) -> Message:
        """回复消息给发送方"""
        return self.send(msg_type, original.from_role, content, **kwargs)

    # ---------- 钩子 ----------
    def on_boot(self):
        """启动钩子：子类加载自己的配置/知识"""
        pass

    def on_message(self, msg: Message):
        """收到消息钩子：可做日志/过滤"""
        self._log("recv", f"{msg.type} from {msg.from_role}")

    def suggest_options(self, context: Dict[str, Any]) -> List[Any]:
        """当决策无法自动完成时，给出候选方案（可覆写）"""
        return []

    # ---------- 辅助 ----------
    def _log(self, event: str, note: str):
        self.log.append({"time": time.time(), "event": event, "note": note})

    def report(self) -> Dict[str, Any]:
        """生成状态汇报（可发 STATUS_REPORT）"""
        return {
            "agent_id": self.role_id,
            "state": self.state,
            "status": self.status,
            "log_len": len(self.log),
        }


# ============================================================
# 五、演示：一个极简的继承示例
# ============================================================

class DemoDesigner(BaseAgent):
    """演示用：系统策划 Agent，继承 BaseAgent 即可获得完整内核"""

    def on_boot(self):
        # 加载领域知识
        self.knowledge.add_doc("背包系统模板", {"category": "inventory", "max_slots": 1000})
        # 注册决策规则
        self.decision.add_rule(DecisionRule(
            name="设计完整性检查",
            conditions=[
                {"key": "rule_coverage", "op": ">=", "value": 0.9},
                {"key": "edge_cases", "op": ">=", "value": 3},
            ],
            action="PASS_REVIEW",
            fallback="REVISE_DESIGN",
        ))

    def handle_task(self, msg: Message):
        if msg.type == "TASK_ASSIGN":
            self._transition("PLANNING")
            # 决策：检查设计完整性
            decision = self.decision.decide(
                {"rule_coverage": 0.95, "edge_cases": 4, "complexity": 3})
            self._log("decision", f"决策={decision['action']} ({decision['source']})")
            self._transition("EXECUTING")
            # 产出设计文档（模拟）
            design_doc = {
                "task_id": msg.content.get("task_id"),
                "title": msg.content.get("inputs", {}).get("title"),
                "status": "DRAFT",
            }
            self._transition("VERIFYING")
            self._transition("DELIVERING")
            # 交付
            self.reply(msg, "ARTIFACT_DELIVERY",
                       {"task_id": msg.content.get("task_id"),
                        "artifact_type": "design_doc",
                        "artifact": design_doc})
            self._transition("IDLE")


def demo():
    print("=" * 60)
    print("通用 Agent 内核 (BaseAgent) 演示")
    print("=" * 60)

    bus = MessageBus()
    agent = DemoDesigner("system_designer", bus)
    agent.boot()

    print(f"\n启动后状态: {agent.state}")

    # 模拟制作人下发任务
    from message_bus import build_task_assign
    msg = build_task_assign("producer", "system_designer", "task_001",
                            {"title": "背包系统设计"})
    bus.publish(msg)
    bus.process_all()

    print(f"\n处理后状态: {agent.state}")
    print("\nAgent 决策日志:")
    for entry in agent.log:
        print(f"  [{entry['event']}] {entry['note']}")

    print("\n交付到总线上的消息数:", len(bus.delivered))
    for m in bus.delivered:
        print(f"  - {m.type} from {m.from_role} to {m.to_role}")


if __name__ == "__main__":
    demo()

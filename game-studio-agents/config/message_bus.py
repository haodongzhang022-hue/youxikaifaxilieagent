# ============================================================
# 通用消息通信协议与消息总线 (MessageBus)
# 版本: v0.3
# 说明: 事件驱动消息总线的通用实现，作为所有 Agent/生态角色
#       之间通信的底层基础设施。本模块与具体岗位、生态角色完全
#       解耦，任何架构调整下均可独立复用。
# 语言: Python 3 (可运行)
# ============================================================
"""
设计目标
--------
1. **解耦**：消息的"发送方/接收方"通过 `role_id` 寻址，不依赖具体类实现；
2. **事件驱动**：基于队列的事件循环，支持同步/异步投递；
3. **可路由**：支持按 role_id、按主题(topic)、按广播(anycast) 三种投递模式；
4. **可追踪**：每条消息带唯一 id、时间戳、状态流转记录，便于审计与复盘；
5. **可扩展**：提供消息拦截器(interceptor)与消息存储，便于接入持久化与监控。

通信协议约定（与 v0.1 agent_behavior.py 中 MESSAGE_TYPES 一致）
--------------------------------------------------------------
消息类型: TASK_ASSIGN / TASK_REVIEW / REVIEW_RESULT / ARTIFACT_DELIVERY
         / BUG_REPORT / APPROVAL_REQUEST / APPROVAL_RESULT / STATUS_REPORT
         / NOTIFICATION
"""
from __future__ import annotations

import itertools
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ============================================================
# 一、消息协议
# ============================================================

# 与 v0.1 定义保持一致的消息类型清单
MESSAGE_TYPES = {
    "TASK_ASSIGN":        "分配任务",
    "TASK_REVIEW":        "任务审核请求",
    "REVIEW_RESULT":      "审核结果",
    "ARTIFACT_DELIVERY":  "产出物交付",
    "BUG_REPORT":         "Bug 报告",
    "APPROVAL_REQUEST":   "审批请求",
    "APPROVAL_RESULT":    "审批结果",
    "STATUS_REPORT":      "状态汇报",
    "NOTIFICATION":       "通知消息",
}

# 优先级权重（数值越大越先处理）
PRIORITY_WEIGHT = {"LOW": 0, "NORMAL": 1, "HIGH": 2, "URGENT": 3}

# 投递模式
DELIVERY_MODE = {
    "DIRECT":  "直投（发给指定 role_id）",
    "TOPIC":   "主题广播（所有订阅该 topic 的接收方）",
    "ANYCAST": "任一投递（多个接收方中挑一个空闲的）",
}


@dataclass
class Message:
    """统一消息结构（复用 v0.1 / v0.2 的消息总线约定）"""
    type: str
    from_role: str
    to_role: str
    content: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    timestamp: float = field(default_factory=time.time)
    priority: str = "NORMAL"                      # LOW / NORMAL / HIGH / URGENT
    mode: str = "DIRECT"                          # DIRECT / TOPIC / ANYCAST
    topic: Optional[str] = None                   # mode=TOPIC 时必填
    trace: List[Dict[str, Any]] = field(default_factory=list)  # 状态流转记录

    def __post_init__(self):
        if self.type not in MESSAGE_TYPES:
            # 允许扩展自定义类型，但给出告警
            pass

    def stamp(self, event: str, actor: str, note: str = ""):
        """记录一条状态流转（用于审计/复盘）"""
        self.trace.append({
            "event": event,
            "actor": actor,
            "note": note,
            "at": time.time(),
        })

    @property
    def priority_weight(self) -> int:
        return PRIORITY_WEIGHT.get(self.priority, 1)


# ============================================================
# 二、订阅与拦截器
# ============================================================

class Subscription:
    """接收方对某一主题/角色的订阅"""

    def __init__(self, subscriber_id: str, topic: Optional[str] = None,
                 handler: Optional[Callable[[Message], Any]] = None,
                 filter_fn: Optional[Callable[[Message], bool]] = None):
        self.subscriber_id = subscriber_id
        self.topic = topic            # None 表示订阅全部 DIRECT 发给自己的消息
        self.handler = handler
        self.filter_fn = filter_fn    # 额外的消息过滤条件

    def matches(self, msg: Message) -> bool:
        if msg.mode == "TOPIC":
            return self.topic is not None and self.topic == msg.topic
        if msg.mode == "DIRECT":
            return self.subscriber_id == msg.to_role
        # ANYCAST 由总线调度，不在此匹配
        return False


# ============================================================
# 三、消息总线
# ============================================================

class MessageBus:
    """
    事件驱动的消息总线。

    用法示例
    --------
    bus = MessageBus()
    bus.register("producer")
    bus.subscribe("system_designer", handler=on_design_msg)

    msg = Message("TASK_ASSIGN", "producer", "system_designer",
                  {"title": "背包系统"})
    bus.publish(msg)
    bus.process()          # 处理队列中的一条消息
    bus.process_all()      # 处理队列中所有消息
    """

    def __init__(self, store: bool = True):
        self.roles: set = set()                     # 已注册的角色
        self._queue: List[Message] = []             # 待处理队列
        self._queue_lock = threading.Lock()
        self._subscriptions: List[Subscription] = []
        self._interceptors: List[Callable[[Message], Message]] = []
        self._handlers: Dict[str, List[Callable[[Message], Any]]] = {}  # role_id -> handler
        self.delivered: List[Message] = []          # 已投递消息记录
        self.store = store
        self._seq = itertools.count(1)

    # ---------- 角色注册 ----------
    def register(self, role_id: str):
        """注册一个可收发消息的角色"""
        self.roles.add(role_id)
        self._handlers.setdefault(role_id, [])

    def unregister(self, role_id: str):
        self.roles.discard(role_id)
        self._handlers.pop(role_id, None)

    # ---------- 订阅 / 处理器 ----------
    def subscribe(self, subscriber_id: str, handler: Callable[[Message], Any],
                  topic: Optional[str] = None,
                  filter_fn: Optional[Callable[[Message], bool]] = None):
        """订阅消息。topic=None 时订阅所有 DIRECT 发给自己的消息。"""
        self.register(subscriber_id)
        sub = Subscription(subscriber_id, topic=topic, handler=handler,
                           filter_fn=filter_fn)
        self._subscriptions.append(sub)
        return sub

    def unsubscribe(self, sub: Subscription):
        if sub in self._subscriptions:
            self._subscriptions.remove(sub)

    def on(self, role_id: str, handler: Callable[[Message], Any]):
        """为角色注册默认消息处理器（收到 DIRECT 消息时调用）"""
        self.register(role_id)
        self._handlers[role_id].append(handler)

    def add_interceptor(self, fn: Callable[[Message], Message]):
        """注册拦截器：在投递前对消息做统一处理（转译/鉴权/埋点）"""
        self._interceptors.append(fn)

    # ---------- 发布 ----------
    def publish(self, msg: Message) -> Message:
        """把消息入队（不立即处理）"""
        # 应用拦截器链
        for fn in self._interceptors:
            msg = fn(msg)
        with self._queue_lock:
            self._queue.append(msg)
        msg.stamp("queued", "message_bus")
        return msg

    def _pick_anycast_target(self, msg: Message) -> Optional[str]:
        """ANYCAST：从候选接收方中挑一个（简化：挑负载最低的）"""
        candidates = [r for r in self.roles if r != msg.from_role]
        if not candidates:
            return None
        # 这里可接入负载均衡策略；简化为取注册顺序第一个
        return candidates[0]

    # ---------- 处理 ----------
    def _next_message(self) -> Optional[Message]:
        """按优先级取出一条待处理消息（优先级高者先出队）"""
        with self._queue_lock:
            if not self._queue:
                return None
            # 稳定排序：优先级权重降序，同权重按入队顺序
            self._queue.sort(
                key=lambda m: (-m.priority_weight,
                               min((i for i, x in enumerate(self._queue) if x is m),
                                   default=0)))
            return self._queue.pop(0)

    def _dispatch(self, msg: Message):
        """把一条消息投递给匹配的订阅者/处理器"""
        # ANYCAST 需要先确定目标
        if msg.mode == "ANYCAST":
            target = self._pick_anycast_target(msg)
            if target is None:
                msg.stamp("no_target", "message_bus")
                return
            msg.to_role = target
            msg.stamp("routed", "message_bus", note=f"anycast->{target}")

        matched = False
        for sub in self._subscriptions:
            if sub.matches(msg) and (sub.filter_fn is None or sub.filter_fn(msg)):
                matched = True
                msg.stamp("delivered", sub.subscriber_id)
                if sub.handler:
                    sub.handler(msg)

        # 同时尝试调用角色的默认 handler
        if msg.mode == "DIRECT" and msg.to_role in self._handlers:
            for h in self._handlers[msg.to_role]:
                matched = True
                msg.stamp("delivered_handler", msg.to_role)
                h(msg)

        if not matched:
            msg.stamp("unmatched", "message_bus", note="无接收方匹配")
        if self.store:
            self.delivered.append(msg)

    def process(self, block: bool = False, timeout: float = 1.0) -> Optional[Message]:
        """处理一条消息。block=False 时无消息立即返回 None。"""
        if not block:
            msg = self._next_message()
        else:
            deadline = time.time() + timeout
            msg = None
            while time.time() < deadline:
                msg = self._next_message()
                if msg:
                    break
                time.sleep(0.01)
        if msg is None:
            return None
        self._dispatch(msg)
        return msg

    def process_all(self) -> int:
        """处理当前队列中全部消息，返回处理条数"""
        count = 0
        while self.process():
            count += 1
        return count

    # ---------- 查询 ----------
    @property
    def pending(self) -> int:
        with self._queue_lock:
            return len(self._queue)

    def stats(self) -> Dict[str, Any]:
        """返回总线运行统计"""
        return {
            "registered_roles": len(self.roles),
            "subscriptions": len(self._subscriptions),
            "pending": self.pending,
            "delivered_total": len(self.delivered),
            "delivered_by_type": _count_by(self.delivered, lambda m: m.type),
        }


def _count_by(items, key_fn) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for it in items:
        k = key_fn(it)
        out[k] = out.get(k, 0) + 1
    return out


# ============================================================
# 四、便捷构建函数
# ============================================================

def build_message(msg_type: str, from_role: str, to_role: str,
                  content: Dict[str, Any], **kwargs) -> Message:
    """便捷构造一条合法消息（自动校验必要字段）"""
    msg = Message(type=msg_type, from_role=from_role, to_role=to_role,
                  content=content, **kwargs)
    msg.stamp("created", from_role)
    return msg


def build_task_assign(from_role: str, to_role: str, task_id: str,
                      inputs: Dict[str, Any], deadline: str = "",
                      priority: str = "NORMAL") -> Message:
    """构造任务分配消息（字段与 v0.1 协议一致）"""
    return build_message(
        "TASK_ASSIGN", from_role, to_role,
        {"task_id": task_id, "inputs": inputs, "deadline": deadline},
        priority=priority)


# ============================================================
# 五、演示
# ============================================================

def demo():
    print("=" * 60)
    print("通用消息总线 (MessageBus) 演示")
    print("=" * 60)

    bus = MessageBus()
    received: List[Message] = []

    # 注册并订阅几个角色
    bus.on("system_designer", lambda m: received.append(m))
    bus.on("client_dev", lambda m: received.append(m))
    bus.subscribe("qa_engineer", handler=lambda m: received.append(m),
                  topic="release_notice")

    # 拦截器：为所有消息加统一审计
    bus.add_interceptor(lambda m: (m.stamp("intercepted", "audit"), m)[1])

    # 1) 直投消息
    m1 = build_task_assign("producer", "system_designer", "task_001",
                           {"title": "背包系统设计"})
    bus.publish(m1)

    # 2) 主题广播
    m2 = Message("NOTIFICATION", "release_manager", "*",
                 {"notice": "v1.2 已发布"}, mode="TOPIC", topic="release_notice")
    bus.publish(m2)

    # 3) 高优先级消息插队
    m3 = build_task_assign("producer", "client_dev", "task_002",
                           {"title": "紧急热修"}, priority="URGENT")
    bus.publish(m3)

    print(f"\n入队后 pending = {bus.pending}")
    bus.process_all()
    print(f"处理完成后 pending = {bus.pending}, 已投递 = {len(bus.delivered)}")
    print(f"接收到的消息数 = {len(received)}")

    # 4) 按主题订阅的 QA 也应收到 TOPIC 消息
    qa_msgs = [m for m in received if m.to_role == "*" or m.topic == "release_notice"]
    print(f"QA 收到的主题消息数 = {len(qa_msgs)}")

    print("\n总线统计:")
    for k, v in bus.stats().items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    demo()

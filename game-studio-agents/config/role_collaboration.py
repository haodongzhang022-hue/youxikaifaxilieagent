# ============================================================
# 角色间协作层 (Role Collaboration) · @转交 / 分工 / 协作
# 版本: v0.1
# 说明: 补充"多角色互相 @，进行任务转交与分工协作"的能力。
#       这是对纵向"经理→部门"派单的横向补强：
#       - 角色 A 可将任务 @转交 给角色 B（B 可接受 / 拒绝 / 再转交 / 退回）；
#       - 角色 A 可 @请求 角色 B 协助（带分工切分点）；
#       - 任意角色可将一个大任务 @拆分为 多个子任务分发给多个角色并行协作；
#       - 全程转交链留痕（origin → 每次 @ 转交/退回），可审计、可回退。
#
# 本模块与具体岗位解耦，仅依赖 message_bus + task_scheduler 的基础协议，
# 任何角色只需调用 TransferCoordinator / SplitCoordinator 即可获得横向协作能力。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from message_bus import Message, MessageBus, build_message
from task_scheduler import Task, TaskState


# ============================================================
# 一、协作事件类型（扩展消息总线协议，与现有 MESSAGE_TYPES 并存）
# ============================================================

COLLAB_MESSAGE_TYPES = {
    "TASK_TRANSFER":     "任务 @转交：A 把任务转给 B",
    "TRANSFER_ACCEPT":   "接受 @转交",
    "TRANSFER_REJECT":   "拒绝 @转交",
    "TRANSFER_BACK":     "退回 @转交（B 无法完成，退回原主）",
    "COLLAB_REQUEST":    "协作 @请求：A 请求 B 协助某任务",
    "COLLAB_RESPONSE":   "协作 @响应：接受 / 婉拒",
    "WORKSPLIT":         "任务 @分工：一个大任务拆为多子任务分发",
    "SPLIT_ACK":         "子任务接收确认",
    "CALLBACK_ACK":      "协作回退确认",
}


# ============================================================
# 二、协作记录（留痕）
# ============================================================

@dataclass
class CollabRecord:
    """一次 @ 转交 / 协作 / 分工的留痕记录"""
    kind: str                       # TRANSFER / COLLAB / SPLIT / CALLBACK
    task_id: str
    origin_role: str                # 最初发起者
    from_role: str                  # 本次操作者
    to_role: str                    # 本次接收者
    reason: str = ""                # 转交/协作原因
    status: str = "PENDING"         # PENDING / ACCEPTED / REJECTED / BACK / DONE
    created_at: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)


class CollabLedger:
    """协作留痕账本：记录所有 @ 转交/协作/分工，可追溯转交链与回退"""

    def __init__(self):
        self.records: List[CollabRecord] = []

    def add(self, rec: CollabRecord):
        self.records.append(rec)
        return rec

    def chain_of(self, task_id: str) -> List[CollabRecord]:
        """某任务的完整转交链（按时间序）"""
        return [r for r in self.records if r.task_id == task_id]

    def last(self, task_id: str) -> Optional[CollabRecord]:
        chain = self.chain_of(task_id)
        return chain[-1] if chain else None

    def owner_of(self, task_id: str) -> Optional[str]:
        """当前实际持有者（转交链最后一条的 to_role）"""
        last = self.last(task_id)
        return last.to_role if last else None

    def origin_of(self, task_id: str) -> Optional[str]:
        chain = self.chain_of(task_id)
        return chain[0].origin_role if chain else None


# ============================================================
# 三、@转交协调器 (TransferCoordinator)
# ============================================================

class TransferCoordinator:
    """
    任务 @转交 协调器：让角色 A 能把任务转交给角色 B，并支持
    接受 / 拒绝 / 退回 / 再转交，全程留痕可审计。

    使用场景：
      - A 的任务实际属于 B 的专业范围 → A @B 转交；
      - A 发现任务缺前置数据，@拥有该数据的 B 协作；
      - B 接了但能力不足 → 退回 A 或 @再转交给 C。
    """

    def __init__(self, bus: MessageBus, ledger: Optional[CollabLedger] = None):
        self.bus = bus
        self.ledger = ledger or CollabLedger()

    # ---------- 发起 @转交 ----------
    def transfer(self, from_role: str, to_role: str, task: Task,
                 reason: str = "", priority: str = "NORMAL") -> Message:
        """A @B 转交任务。生成 TASK_TRANSFER 消息，并在账本留痕。"""
        self.ledger.add(CollabRecord(
            kind="TRANSFER", task_id=task.id,
            origin_role=from_role, from_role=from_role, to_role=to_role,
            reason=reason, status="PENDING",
            context={"task_name": task.name, "priority": task.priority,
                     "payload": dict(task.payload)},
        ))
        msg = build_message(
            "TASK_TRANSFER", from_role, to_role,
            {"task_id": task.id, "task_name": task.name, "reason": reason,
             "owner": to_role, "origin_role": from_role,
             "payload": dict(task.payload)},
            priority=priority)
        msg.stamp("transfer", from_role, note=f"{to_role}")
        self.bus.publish(msg)
        return msg

    # ---------- 接收方操作 ----------
    def accept(self, from_role: str, to_role: str, task_id: str) -> Message:
        """B 接受 @转交。任务 owner 更新为 B，状态进入 IN_PROGRESS。"""
        self.ledger.add(CollabRecord(
            kind="TRANSFER", task_id=task_id,
            origin_role=from_role, from_role=to_role, to_role=from_role,
            reason="接受转交", status="ACCEPTED",
            context={"accepted_by": from_role}))
        task = Task(id=task_id, owner=from_role)
        task.touch(TaskState.IN_PROGRESS.value, "接受 @转交")
        msg = build_message("TRANSFER_ACCEPT", from_role, to_role,
                            {"task_id": task_id, "accepted": True})
        msg.stamp("accept", from_role, note=task_id)
        self.bus.publish(msg)
        return msg

    def reject(self, from_role: str, to_role: str, task_id: str,
               reason: str = "") -> Message:
        """B 拒绝 @转交。任务仍归 A，状态回 TODO。"""
        self.ledger.add(CollabRecord(
            kind="TRANSFER", task_id=task_id,
            origin_role=to_role, from_role=from_role, to_role=to_role,
            reason=f"拒绝转交: {reason}", status="REJECTED",
            context={"rejected_by": from_role}))
        msg = build_message("TRANSFER_REJECT", from_role, to_role,
                            {"task_id": task_id, "accepted": False, "reason": reason})
        msg.stamp("reject", from_role, note=task_id)
        self.bus.publish(msg)
        return msg

    def transfer_back(self, from_role: str, to_role: str, task_id: str,
                      reason: str = "") -> Message:
        """B 无法完成，@退回原发起人 A。"""
        self.ledger.add(CollabRecord(
            kind="CALLBACK", task_id=task_id,
            origin_role=to_role, from_role=from_role, to_role=to_role,
            reason=f"退回: {reason}", status="BACK",
            context={"callback_to": to_role}))
        msg = build_message("TRANSFER_BACK", from_role, to_role,
                            {"task_id": task_id, "reason": reason})
        msg.stamp("back", from_role, note=f"退回 {to_role}")
        self.bus.publish(msg)
        return msg


# ============================================================
# 四、@分工协调器 (SplitCoordinator)
# ============================================================

class SplitCoordinator:
    """
    任务 @分工 协调器：把一个大任务 @拆分为 多个子任务，分发给多个角色
    并行协作，并由经理或发起人追踪各子任务的完成情况。

    场景：
      - 经理把"战斗系统"@拆为 [策划设计 / 程序实现 / 美术资源 / 测试] 四个子任务；
      - 任一角色发现自己手上的活需要多人配合时，也可 @发起分工。
    """

    def __init__(self, bus: MessageBus, ledger: Optional[CollabLedger] = None):
        self.bus = bus
        self.ledger = ledger or CollabLedger()
        self.splits: Dict[str, List[str]] = {}   # parent_task_id -> [child_task_ids]

    def split(self, from_role: str, parent_task_id: str, parent_name: str,
              assignments: List[Dict[str, Any]],
              priority: str = "NORMAL") -> List[Message]:
        """
        将父任务 @拆为 子任务分发。
        assignments: [{"to_role": str, "sub_task": str, "inputs": dict, "reason": str}, ...]
        返回生成的 TASK_ASSIGN 消息列表。
        """
        child_ids: List[str] = []
        msgs: List[Message] = []
        for i, asg in enumerate(assignments, 1):
            child_id = f"{parent_task_id}#sub{i}"
            child_ids.append(child_id)
            self.ledger.add(CollabRecord(
                kind="SPLIT", task_id=parent_task_id,
                origin_role=from_role, from_role=from_role,
                to_role=asg["to_role"],
                reason=asg.get("reason", f"分工子任务{i}"),
                status="PENDING",
                context={"sub_task_id": child_id, "sub_task": asg["sub_task"],
                         "inputs": asg.get("inputs", {})}))
            msg = build_message(
                "WORKSPLIT", from_role, asg["to_role"],
                {"parent_task_id": parent_task_id, "parent_name": parent_name,
                 "sub_task_id": child_id, "sub_task": asg["sub_task"],
                 "inputs": asg.get("inputs", {}), "reason": asg.get("reason", "")},
                priority=priority)
            msg.stamp("split", from_role, note=f"{asg['to_role']} <- {asg['sub_task']}")
            self.bus.publish(msg)
            msgs.append(msg)
        self.splits[parent_task_id] = child_ids
        return msgs

    def ack(self, from_role: str, to_role: str, sub_task_id: str) -> Message:
        """角色接收子任务，确认承接。"""
        self.ledger.add(CollabRecord(
            kind="SPLIT", task_id=sub_task_id,
            origin_role=to_role, from_role=from_role, to_role=to_role,
            reason="接收子任务", status="ACCEPTED",
            context={"ack_by": from_role}))
        msg = build_message("SPLIT_ACK", from_role, to_role,
                            {"sub_task_id": sub_task_id, "ack": True})
        msg.stamp("split_ack", from_role, note=sub_task_id)
        self.bus.publish(msg)
        return msg

    def report_split(self, parent_task_id: str) -> Dict[str, Any]:
        """汇总某父任务的各子任务承接情况（分工进度）。"""
        child_ids = self.splits.get(parent_task_id, [])
        rows = []
        for cid in child_ids:
            rec = self.ledger.last(cid) or self.ledger.last(parent_task_id)
            rows.append({"sub_task_id": cid,
                         "assignee": self.ledger.owner_of(cid),
                         "status": rec.status if rec else "UNKNOWN"})
        return {"parent_task_id": parent_task_id, "children": rows,
                "total": len(rows),
                "accepted": sum(1 for r in rows if r["status"] == "ACCEPTED")}


# ============================================================
# 五、协作工作台 (RoleCollabHub) · 一站式入口
# ============================================================

class RoleCollabHub:
    """
    角色协作工作台：把 @转交 与 @分工 能力统一封装，供任意角色（含经理）
    一键获得"多角色互相 @ 协作"的能力。同时提供协作事件的分发器，
    让消息总线上的协作事件被正确路由到各角色处理。
    """

    def __init__(self, bus: MessageBus, ledger: Optional[CollabLedger] = None):
        self.bus = bus
        self.ledger = ledger or CollabLedger()
        self.transfer = TransferCoordinator(bus, self.ledger)
        self.split = SplitCoordinator(bus, self.ledger)

    # ---------- 便捷 @转交 ----------

    def handoff(self, from_role: str, to_role: str, task: Task,
                reason: str = "") -> Message:
        """角色 @ 转交：A 把任务交给 B。"""
        return self.transfer.transfer(from_role, to_role, task, reason)

    def accept_transfer(self, from_role: str, to_role: str, task_id: str) -> Message:
        return self.transfer.accept(from_role, to_role, task_id)

    def reject_transfer(self, from_role: str, to_role: str, task_id: str,
                        reason: str = "") -> Message:
        return self.transfer.reject(from_role, to_role, task_id, reason)

    def handback(self, from_role: str, to_role: str, task_id: str,
                 reason: str = "") -> Message:
        """B 无法完成，@退回给 A。"""
        return self.transfer.transfer_back(from_role, to_role, task_id, reason)

    # ---------- 便捷 @分工 ----------
    def delegate(self, from_role: str, parent_task_id: str, parent_name: str,
                 assignments: List[Dict[str, Any]],
                 priority: str = "NORMAL") -> List[Message]:
        """角色 @ 分工：把一个任务拆给多个角色并行协作。"""
        return self.split.split(from_role, parent_task_id, parent_name,
                                assignments, priority)

    def ack_subtask(self, from_role: str, to_role: str, sub_task_id: str) -> Message:
        return self.split.ack(from_role, to_role, sub_task_id)

    def report(self, task_id: str) -> Dict[str, Any]:
        """某任务的协作全貌：转交链 + 分工进度。"""
        chain = self.ledger.chain_of(task_id)
        return {
            "task_id": task_id,
            "owner": self.ledger.owner_of(task_id),
            "origin": self.ledger.origin_of(task_id),
            "transfer_chain": [
                {"from": r.from_role, "to": r.to_role, "status": r.status,
                 "kind": r.kind, "reason": r.reason}
                for r in chain
            ],
            "split": self.split.report_split(task_id) if task_id in self.split.splits else None,
        }


# ============================================================
# 六、演示
# ============================================================

def demo():
    print("=" * 60)
    print("角色间协作层 (Role Collaboration) 演示：@转交 / 分工 / 协作")
    print("=" * 60)

    bus = MessageBus()
    hub = RoleCollabHub(bus)

    # 注册几个角色并订阅消息
    bus.on("system_designer", lambda m: None)
    bus.on("balance_designer", lambda m: None)
    bus.on("client_dev", lambda m: None)
    bus.on("qa_engineer", lambda m: None)

    # 1) 经理 @分工：战斗系统拆为 4 个子任务
    print("\n【场景1】经理 @分工：战斗系统拆为 4 个子任务")
    msgs = hub.delegate(
        "producer", "wp_combat", "战斗系统",
        [
            {"to_role": "system_designer", "sub_task": "玩法设计", "inputs": {"detail": "战斗手感"}},
            {"to_role": "client_dev", "sub_task": "客户端实现", "inputs": {"detail": "战斗动画"}},
            {"to_role": "balance_designer", "sub_task": "数值平衡", "inputs": {"detail": "伤害公式"}},
            {"to_role": "qa_engineer", "sub_task": "功能测试", "inputs": {"detail": "战斗回归"}},
        ])
    print(f"  ✅ 已生成 {len(msgs)} 条分工任务，分别发给 "
          f"{[m.to_role for m in msgs]}")

    # 各角色确认承接
    for m in msgs:
        hub.ack_subtask(m.to_role, m.from_role, m.content["sub_task_id"])
    split_report = hub.report("wp_combat")["split"]
    print(f"  ✅ 分工进度: 总 {split_report['total']}，已承接 {split_report['accepted']}")

    # 2) 数值平衡发现需要策划数据，@转交
    print("\n【场景2】balance_designer 数值不足，@转交 给 system_designer")
    task = Task(id="wp_combat#sub3", name="数值平衡", owner="balance_designer")
    hub.handoff("balance_designer", "system_designer", task,
                reason="需要玩法规则数据才能建模")
    hub.accept_transfer("system_designer", "balance_designer", "wp_combat#sub3")
    owner = hub.report("wp_combat#sub3")["owner"]
    print(f"  ✅ 任务已转交，当前持有者 = {owner}")

    # 3) system_designer 完成数据，@退回 给 balance_designer 继续
    print("\n【场景3】system_designer 提供数据后 @退回 数值任务给 balance_designer")
    hub.handback("system_designer", "balance_designer", "wp_combat#sub3",
                 reason="玩法数据已提供，数值建模请继续")
    owner2 = hub.report("wp_combat#sub3")["owner"]
    print(f"  ✅ 任务已退回，当前持有者 = {owner2}")

    # 4) 完整协作链留痕
    print("\n【场景4】wp_combat#sub3 完整转交链留痕")
    chain = hub.report("wp_combat#sub3")["transfer_chain"]
    for c in chain:
        print(f"  {c['kind']}: {c['from']} -> {c['to']} [{c['status']}] ({c['reason']})")

    print("\n✅ 角色间协作层演示完成：@转交 / @分工 / @退回 全链路可用")


if __name__ == "__main__":
    demo()

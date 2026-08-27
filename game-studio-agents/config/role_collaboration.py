# ============================================================
# 角色间协作层 · 多角色互相@（任务转交 + 分工协作 + 协作请求）
# 版本: v0.1
# 说明: 让任意角色（含经理）能够互相 @ 进行任务转交、分工协作，
#       全程留痕可审计、可回退，支持接受/拒绝/退回/再转交状态机。
#
# 核心能力：
#   A. @转交（HANDOFF）   ：角色 A 把任务转交给角色 B，B 可接受/拒绝/退回/再转交
#   B. @分工（DELEGATE）  ：角色 A 把一个任务拆为多个子任务分发给多个角色并行协作
#   C. @协作请求（COLLAB） ：角色 A 请求角色 B 协助某任务（双向补充）
#   D. 转交链留痕          ：记录 origin（发起者）→ owner（当前持有者）→ transfer_chain
#
# 语言: Python 3 (可运行，不依赖第三方库)
# ============================================================
from __future__ import annotations

import functools
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================
# 一、协作消息类型（扩展自 message_bus 的 MESSAGE_TYPES 语义）
# ============================================================

# 角色间互相@ 的协作事件类型
HANDOFF      = "HANDOFF"        # @转交：把任务交给另一位角色
DELEGATE     = "DELEGATE"       # @分工：把任务拆分分发给多个角色并行协作
COLLAB_REQ   = "COLLAB_REQ"     # @协作请求：请某角色协助当前任务
ACK          = "ACK"            # @回执：接受/拒绝/退回/完成 的应答
NOTIFY       = "COLLAB_NOTIFY"  # 协作进度通知（汇总承接状态）


# 转交/分工的承接状态机
#   OFFERED（已发出）→ ACCEPTED（已接受）/ DECLINED（已拒绝）
#   ACCEPTED → IN_PROGRESS（执行中）→ DONE（完成）/ RETURNED（退回）
#   RETURNED → 可再转交 OFFERED 或回到上一持有者
STATUS_FLOW = {
    "OFFERED":   ["ACCEPTED", "DECLINED", "RETURNED", "CANCELLED"],
    "ACCEPTED":  ["IN_PROGRESS", "RETURNED", "DONE"],
    "IN_PROGRESS": ["DONE", "RETURNED", "BLOCKED"],
    "DECLINED":  ["OFFERED", "CANCELLED"],     # 拒绝后可被再转交给他人
    "RETURNED":  ["OFFERED", "RETURNED", "DONE", "CANCELLED"],  # 允许连续回退
    "BLOCKED":   ["IN_PROGRESS", "RETURNED", "ESCALATE"],
    "DONE":      [],
    "CANCELLED": [],
}


@dataclass
class CollabEvent:
    """一次协作事件（多角色互相@ 的一次动作记录）"""
    event: str                       # HANDOFF / DELEGATE / COLLAB_REQ / ACK / NOTIFY
    from_role: str                   # @的发起者
    to_role: str                     # 被 @ 的角色
    task_id: str                     # 关联任务
    action: str = ""                 # 转交: OFFER; 分工: SPLIT; 回执: ACCEPT/REJECT/RETURN/COMPLETE
    detail: Dict[str, Any] = field(default_factory=dict)   # 附加说明 / 子任务清单 / 退回原因
    ts: float = field(default_factory=time.time)


@dataclass
class Collaboration:
    """一条协作记录（一个任务的跨角色协作全生命周期）"""
    task_id: str
    title: str = ""
    origin: str = ""                          # 发起者（第一手）
    owner: str = ""                           # 当前持有者
    status: str = "OFFERED"                   # 承接状态（见 STATUS_FLOW）
    transfer_chain: List[str] = field(default_factory=list)  # 转交链：A -> B -> C ...
    events: List[CollabEvent] = field(default_factory=list)  # 全程事件留痕
    sub_tasks: Dict[str, "SubTask"] = field(default_factory=dict)  # 分工后的子任务
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self):
        # 仅在 origin != owner 时登记首链，避免转交初始状态产生 A->A 虚假自环
        if self.origin and self.owner and self.origin != self.owner:
            self.transfer_chain.append(f"{self.origin}->{self.owner}")


@dataclass
class SubTask:
    """@分工 拆出的一个子任务"""
    sub_id: str
    role: str          # 承接子任务的角色
    desc: str = ""
    status: str = "OFFERED"    # OFFERED / ACCEPTED / IN_PROGRESS / DONE / BLOCKED
    accepted_at: float = 0.0


# ============================================================
# 二、协作工作台（多角色互相@ 的能力入口）
# ============================================================

def _synchronized(fn):
    """线程安全装饰器：以协作工作台的 RLock 保护并发访问 records/_events。"""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return fn(self, *args, **kwargs)
    return wrapper


class CollaborationWorkbench:
    """
    角色间协作工作台。任意角色（含经理）接入后即可：
      - handoff      @转交任务给另一位角色
      - delegate     @分工，把任务拆为多个子任务分发给多角色并行协作
      - request_collab @协作请求，请某角色协助
      - acknowledge  处理回执（接受 / 拒绝 / 退回 / 完成 / 再转交）
      - audit        审计任意协作记录（转交链 + 事件留痕）

    设计要点：
      - 全程留痕：每步操作写 events，转交链记录 origin->owner 演变，可回退
      - 状态机约束：承接状态流转受 STATUS_FLOW 约束，非法流转直接拒绝
      - 可回退：任务可退回上一持有者（RETURN），也可再转交（OFFERED）
    """

    def __init__(self):
        self.records: Dict[str, Collaboration] = {}   # task_id -> 协作记录
        self._events: List[CollabEvent] = []          # 全局事件流水（审计）
        self._lock = threading.RLock()                # 并发安全：保护 records/_events

    # ---------- 查询 ----------
    def get(self, task_id: str) -> Optional[Collaboration]:
        return self.records.get(task_id)

    def _collab(self, task_id: str, title: str = "",
                origin: str = "", owner: str = "") -> Collaboration:
        if task_id not in self.records:
            self.records[task_id] = Collaboration(
                task_id=task_id, title=title, origin=origin, owner=owner)
        return self.records[task_id]

    def _emit(self, ev: CollabEvent):
        self._events.append(ev)
        rec = self.records.get(ev.task_id)
        if rec:
            rec.events.append(ev)
            rec.updated_at = ev.ts

    def _change_status(self, rec: Collaboration, new: str) -> bool:
        """按 STATUS_FLOW 约束流转状态"""
        allowed = STATUS_FLOW.get(rec.status, [])
        if new not in allowed:
            return False
        rec.status = new
        rec.updated_at = time.time()
        return True

    # ---------- A. @转交（HANDOFF） ----------
    @_synchronized
    def handoff(self, task_id: str, title: str, from_role: str,
                to_role: str, note: str = "") -> dict:
        """角色 from_role @转交任务 task_id 给 to_role。返回 {ok, record}"""
        if from_role == to_role:
            return {"ok": False, "error": "转交目标不能是自身", "record": None}
        rec = self._collab(task_id, title, origin=from_role, owner=from_role)
        # 更新持有者与转交链
        rec.owner = to_role
        rec.transfer_chain.append(f"{from_role}->{to_role}")
        rec.status = "OFFERED"
        self._emit(CollabEvent(HANDOFF, from_role, to_role, task_id,
                               action="OFFER", detail={"note": note}))
        return {"ok": True, "record": rec, "transfer_chain": list(rec.transfer_chain)}

    # ---------- B. @分工（DELEGATE） ----------
    @_synchronized
    def delegate(self, task_id: str, title: str, from_role: str,
                 assignments: List[Dict[str, str]],
                 note: str = "") -> dict:
        """角色 from_role @分工：把任务 task_id 拆成多个子任务分发给多角色并行协作。

        assignments: [{"role": "client_dev", "desc": "实现背包界面"}, ...]
        """
        if not assignments:
            return {"ok": False, "error": "assignments 不能为空", "record": None}
        for a in assignments:
            role = a.get("role", "")
            if not role:
                return {"ok": False, "error": "assignments 元素缺少 role 键",
                        "record": None}
        rec = self._collab(task_id, title, origin=from_role, owner=from_role)
        rec.sub_tasks = {}
        for i, a in enumerate(assignments):
            role = a.get("role")
            sub_id = f"{task_id}__sub{i + 1}"
            rec.sub_tasks[sub_id] = SubTask(sub_id=sub_id, role=role,
                                            desc=a.get("desc", ""))
        rec.owner = "|".join(a["role"] for a in assignments)  # 多人并行承接
        rec.status = "OFFERED"
        self._emit(CollabEvent(DELEGATE, from_role,
                               "|".join(a["role"] for a in assignments),
                               task_id, action="SPLIT",
                               detail={"sub_tasks": list(rec.sub_tasks.keys()),
                                       "note": note}))
        return {"ok": True, "record": rec, "sub_tasks": list(rec.sub_tasks.keys())}

    # ---------- C. @协作请求（COLLAB_REQ） ----------
    @_synchronized
    def request_collab(self, task_id: str, title: str, from_role: str,
                       to_role: str, need: str = "") -> dict:
        """角色 from_role @请求 to_role 协助任务 task_id。"""
        rec = self._collab(task_id, title, origin=from_role, owner=from_role)
        # 协作请求不改变持有者，仅登记协助请求（_emit 已追加到 rec.events，
        # 此处不再手动 append，避免双重记录）
        self._emit(CollabEvent(COLLAB_REQ, from_role, to_role, task_id,
                               action="ASSIST", detail={"need": need}))
        return {"ok": True, "record": rec, "assist_requested_to": to_role}

    # ---------- D. 处理回执（ACK） ----------
    def acknowledge(self, task_id: str, from_role: str,
                    action: str, reason: str = "",
                    reassign_to: Optional[str] = None) -> dict:
        """承接方处理 @：ACCEPT / REJECT / RETURN / COMPLETE / REHANDOFF

        返回统一含 `record` 键（成功为协作记录，失败为 None），避免调用方 KeyError。
        """
        with self._lock:
            rec = self.records.get(task_id)
            if not rec:
                return {"ok": False, "error": f"协作记录 {task_id} 不存在",
                        "record": None}
            ack = action.upper()
            if ack == "ACCEPT":
                ok = self._change_status(rec, "ACCEPTED")
                if ok:
                    rec.owner = from_role
                    self._emit(CollabEvent(ACK, from_role, rec.owner, task_id,
                                           action="ACCEPT"))
            elif ack == "REJECT":
                ok = self._change_status(rec, "DECLINED")
                if ok:
                    # 拒绝后持有者回到发起者，避免「拒绝者仍被记录为持有者」
                    rec.owner = rec.origin
                    self._emit(CollabEvent(ACK, from_role, rec.origin, task_id,
                                           action="REJECT", detail={"reason": reason}))
            elif ack == "RETURN":
                # 退回：回到转交链上一持有者，并弹出转交链末节点以支持连续回退
                prev = self._previous_owner(rec)
                ok = self._change_status(rec, "RETURNED")
                if ok and prev:
                    rec.owner = prev
                    self._pop_transfer_tail(rec)
                    self._emit(CollabEvent(ACK, from_role, prev, task_id,
                                           action="RETURN", detail={"reason": reason}))
            elif ack == "COMPLETE":
                ok = self._change_status(rec, "DONE")
                if ok:
                    self._emit(CollabEvent(ACK, from_role, rec.origin, task_id,
                                           action="COMPLETE"))
            elif ack == "REHANDOFF":
                # 再转交：承接方把任务再 @ 给第三位角色
                # 终态（DONE/CANCELLED）不可再转交，走状态机约束
                if rec.status in ("DONE", "CANCELLED"):
                    return {"ok": False, "error": f"状态 {rec.status} 是终态，不可再转交",
                            "allowed": [], "record": None}
                if not reassign_to:
                    return {"ok": False, "error": "REHANDOFF 需指定 reassign_to",
                            "record": None}
                if from_role == reassign_to:
                    return {"ok": False, "error": "再转交目标不能是自身",
                            "record": None}
                rec.status = "OFFERED"
                rec.owner = reassign_to
                rec.transfer_chain.append(f"{from_role}->{reassign_to}")
                self._emit(CollabEvent(HANDOFF, from_role, reassign_to, task_id,
                                       action="REHANDOFF", detail={"reason": reason}))
                return {"ok": True, "record": rec}
            else:
                return {"ok": False, "error": f"未知回执动作: {action}", "record": None}

            if not ok:
                return {"ok": False, "error": f"状态 {rec.status} 不允许动作 {ack}",
                        "allowed": STATUS_FLOW.get(rec.status, []), "record": None}
            return {"ok": True, "record": rec}

    # ---------- 子任务回执（@分工 的承接方汇报） ----------
    @_synchronized
    def sub_ack(self, task_id: str, sub_id: str, from_role: str,
                action: str, note: str = "") -> dict:
        """分工子任务承接方回执：ACCEPT / COMPLETE / BLOCK"""
        rec = self.records.get(task_id)
        if not rec or sub_id not in rec.sub_tasks:
            return {"ok": False, "error": "子任务不存在"}
        sub = rec.sub_tasks[sub_id]
        if sub.role != from_role:
            return {"ok": False, "error": f"{from_role} 不是子任务 {sub_id} 的承接方"}
        if action == "ACCEPT":
            sub.status = "ACCEPTED"
        elif action == "COMPLETE":
            sub.status = "DONE"
        elif action == "BLOCK":
            sub.status = "BLOCKED"
        else:
            return {"ok": False, "error": f"未知子任务动作 {action}"}
        self._emit(CollabEvent(ACK, from_role, rec.origin, task_id,
                               action=f"SUB_{action}",
                               detail={"sub_id": sub_id, "note": note}))
        return {"ok": True, "sub_status": sub.status}

    @_synchronized
    def sub_progress(self, task_id: str) -> Dict[str, Any]:
        """汇总 @分工 各子任务承接进度"""
        rec = self.records.get(task_id)
        if not rec or not rec.sub_tasks:
            return {"ok": False, "error": "无分工子任务"}
        done = sum(1 for s in rec.sub_tasks.values() if s.status == "DONE")
        blocked = sum(1 for s in rec.sub_tasks.values() if s.status == "BLOCKED")
        return {
            "ok": True,
            "total": len(rec.sub_tasks),
            "done": done,
            "blocked": blocked,
            "pending": len(rec.sub_tasks) - done - blocked,
            "detail": {sid: s.status for sid, s in rec.sub_tasks.items()},
        }

    # ---------- 清理机制 ----------
    @_synchronized
    def cleanup(self, older_than_days: float = 30.0) -> int:
        """清理超过指定天数未更新的协作记录与事件流水，避免内存无限增长。

        Args:
            older_than_days: 清理阈值（天）。记录 updated_at 距今超过该天数即清理。
        Returns:
            int: 清理的记录条数。
        """
        cutoff = time.time() - older_than_days * 86400
        removed_ids = [tid for tid, rec in self.records.items()
                       if rec.updated_at < cutoff]
        for tid in removed_ids:
            del self.records[tid]
        # 同步清理事件流水：仅保留与现存记录关联的事件
        keep_tids = set(self.records.keys())
        self._events = [ev for ev in self._events if ev.task_id in keep_tids]
        return len(removed_ids)

    # ---------- 审计 ----------
    @_synchronized
    def audit(self, task_id: str) -> Dict[str, Any]:
        """审计某协作记录：转交链 + 全事件流水"""
        rec = self.records.get(task_id)
        if not rec:
            return {"ok": False, "error": f"无协作记录 {task_id}"}
        return {
            "ok": True,
            "task_id": rec.task_id,
            "title": rec.title,
            "origin": rec.origin,
            "owner": rec.owner,
            "status": rec.status,
            "transfer_chain": list(rec.transfer_chain),
            "event_count": len(rec.events),
            "events": [{"event": e.event, "from": e.from_role, "to": e.to_role,
                        "action": e.action, "detail": e.detail} for e in rec.events],
        }

    def _previous_owner(self, rec: Collaboration) -> Optional[str]:
        """转交链上当前持有者的上一手（即末节点 "X->Y" 的 X；用于退回）"""
        if len(rec.transfer_chain) < 2:
            return rec.origin
        last_link = rec.transfer_chain[-1]   # "A->B"
        if "->" in last_link:
            return last_link.split("->")[0]
        return rec.origin

    def _pop_transfer_tail(self, rec: Collaboration) -> Optional[str]:
        """弹出转交链末节点（RETURN 退回后使链与真实持有者一致，支持连续回退）"""
        if rec.transfer_chain:
            return rec.transfer_chain.pop()
        return None


# ============================================================
# 三、演示
# ============================================================

def demo():
    print("=" * 60)
    print("角色间协作层 · 多角色互相@ 演示")
    print("=" * 60)

    wb = CollaborationWorkbench()

    # 1) @转交：策划 -> 程序
    r = wb.handoff("wp_client", "客户端界面", "system_designer", "client_dev",
                   note="UI 设计已完成，请实现")
    print(f"\n[A. @转交] {r['record'].transfer_chain}")

    # 2) 程序接受
    r = wb.acknowledge("wp_client", "client_dev", "ACCEPT")
    print(f"[D. 接受] 状态={r['record'].status}, 持有者={r['record'].owner}")

    # 3) 程序再转交给 UI 美术
    r = wb.acknowledge("wp_client", "client_dev", "REHANDOFF", reassign_to="ui_ux")
    print(f"[D. 再转交] 转交链={r['record'].transfer_chain}")

    # 4) 程序把任务退回给策划
    r = wb.acknowledge("wp_client", "client_dev", "RETURN", reason="需求不明确")
    print(f"[D. 退回] 状态={r['record'].status}, 持有者={r['record'].owner}")

    # 5) @分工：经理把大任务拆给多角色并行
    r = wb.delegate("wp_testing", "全量测试", "project_manager",
                    [{"role": "qa_engineer", "desc": "功能测试"},
                     {"role": "auto_qa", "desc": "自动化回归"}])
    print(f"\n[B. @分工] 子任务={r['sub_tasks']}")

    # 6) 分工子任务承接
    wb.sub_ack("wp_testing", "wp_testing__sub1", "qa_engineer", "ACCEPT")
    wb.sub_ack("wp_testing", "wp_testing__sub2", "auto_qa", "ACCEPT")
    wb.sub_ack("wp_testing", "wp_testing__sub1", "qa_engineer", "COMPLETE")
    prog = wb.sub_progress("wp_testing")
    print(f"[B. 分工进度] {prog['done']}/{prog['total']} 完成")

    # 7) @协作请求
    r = wb.request_collab("wp_server", "服务端", "client_dev", "server_dev",
                          need="需要数据库表结构")
    print(f"[C. @协作请求] 已请求 {r['assist_requested_to']} 协助")

    # 8) 审计
    print("\n[D. 审计] wp_client 协作全记录:")
    for ev in wb.audit("wp_client")["events"]:
        print(f"  [{ev['event']}] {ev['from']} -> {ev['to']} :: {ev['action']}")


if __name__ == "__main__":
    demo()

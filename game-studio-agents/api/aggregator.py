# ============================================================
# 降熵聚合引擎（Aggregator）
# 版本: v0.9
# 说明: 把多 Agent 协同产生的海量、零散、高频事件流，通过
#       "聚类 → 折叠 → 摘要" 三步降熵，压缩成低熵的
#       关键信息（Signal）与判断信息（Judgment）。
#       每个聚合结论携带 依据链 + 置信度 + 溯源指针，确保可溯源。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

# 支持直接运行 / 相对导入双模式
if __package__:
    from .models import (Aggregate, ClusterGroup, HealthMetric, Judgment,
                         Overview, RawEvent, WorkPackageDetail)
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from models import (Aggregate, ClusterGroup, HealthMetric, Judgment,
                        Overview, RawEvent, WorkPackageDetail)


# ============================================================
# 状态 / 风险 常量
# ============================================================

# 任务状态 → 工作包业务状态映射
STATE_TO_WP_STATUS = {
    "TODO": "pending",
    "IN_PROGRESS": "active",
    "BLOCKED": "blocked",
    "DONE": "done",
    "FAILED": "rework",
}

# 业务状态中文标签
STATUS_LABELS = {
    "pending": "待派发", "active": "进行中", "done": "已验收",
    "blocked": "阻塞中", "rework": "待返工",
}

# 风险等级
RISK_LEVEL = {"low": 0, "medium": 1, "high": 2, "critical": 3}


# ============================================================
# 工具函数
# ============================================================

def _fmt_time(ts: Optional[float]) -> Optional[str]:
    if not ts:
        return None
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _state_status(state: str) -> str:
    return STATE_TO_WP_STATUS.get(state, "pending")


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def _find_task_for_wp(tasks: Dict[str, Any], wp_id: str) -> Optional[Dict[str, Any]]:
    """按工作包 id 查找对应调度任务快照。

    调度任务 id 与工作包 id 不同（task_xxx vs wp_xxx），二者通过
    task['work_package_id'] 关联。此处先按 task_id 直查，再按
    work_package_id 反查，兼容两种输入。
    """
    if not wp_id:
        return None
    t = tasks.get(wp_id)   # 若 key 即工作包 id
    if t is not None:
        return t
    for task in tasks.values():
        if task.get("work_package_id") == wp_id:
            return task
    return None


def _wp_status_from_task(wp: Dict[str, Any], task: Optional[Dict[str, Any]]) -> Optional[str]:
    """从调度任务状态推导工作包真实业务状态（优先于滞后的 wp.status）。

    工作包编排时的 status 字段可能滞后（如打回只阻塞调度任务而不更新 wp.status），
    因此聚合层优先看对应调度任务的真实状态，避免判断失真。
    """
    if not task:
        return None
    tstate = task.get("state")
    if tstate == "BLOCKED":
        return "blocked"
    if tstate == "DONE":
        return "done"
    if tstate == "FAILED":
        return "rework"
    if tstate == "IN_PROGRESS":
        return "active"
    if tstate == "TODO":
        return "pending"
    return None


def _wp_effective_status(wp: Dict[str, Any], tasks: Dict[str, Any]) -> str:
    """工作包有效业务状态：优先从调度任务推导，其次回退到 wp.status。"""
    derived = _wp_status_from_task(wp, _find_task_for_wp(tasks, wp.get("id")))
    if derived:
        return derived
    return wp.get("status", "pending")


def _wp_effective_progress(wp: Dict[str, Any], tasks: Dict[str, Any]) -> float:
    task = _find_task_for_wp(tasks, wp.get("id"))
    if task and task.get("progress"):
        return task.get("progress", 0.0)
    return wp.get("progress", 0.0)


# ============================================================
# 判断信息生成（决策支撑）
# ============================================================

def build_judgment(wp: Dict[str, Any], tasks: Dict[str, Any]) -> Optional[Judgment]:
    """为单个工作包生成有依据的判断信息（依据链 + 置信度 + 建议动作）。"""
    reasons: List[str] = []
    evidence: List[str] = []
    confidence = "medium"
    action = ""

    status = _wp_effective_status(wp, tasks)
    task = _find_task_for_wp(tasks, wp.get("id"))
    deps = wp.get("deps", [])

    # 阻塞 / 返工判断
    if status == "blocked":
        reasons.append("blocked")
        evidence.append(f"工作包 {wp['id']} 处于阻塞状态")
        # 关联调度任务历史作证据
        if task and task.get("history"):
            evidence.append(f"最近流转: {task['history'][-1].get('note', '')}")
        confidence = "high"
        action = f"派督导/返工给 {wp.get('owner', '负责人')}，或调整依赖"
    elif status == "rework":
        reasons.append("rework")
        evidence.append(f"工作包 {wp['id']} 被打回返工")
        confidence = "high"
        action = f"派返工给 {wp.get('owner', '负责人')}"

    # 依赖风险判断
    if deps:
        locked = sum(1 for d in deps if tasks.get(d, {}).get("state") != "DONE")
        if locked > 0:
            reasons.append("dep_risk")
            evidence.append(f"有 {locked}/{len(deps)} 个前置依赖未完成")
            if confidence == "medium":
                confidence = "medium"

    # 进度判断
    progress = _wp_effective_progress(wp, tasks)
    if status == "active" and progress < 0.5:
        reasons.append("progress")
        evidence.append(f"进行中但进度仅 {int(progress*100)}%")

    if not reasons:
        return None

    # 置信度：多路信号一致 → high
    if len(reasons) >= 2:
        confidence = "high"

    conclusion = _compose_conclusion(wp, reasons, evidence)
    return Judgment(
        conclusion=conclusion,
        evidence_chain=evidence,
        confidence=confidence,
        suggested_action=action,
    )


def _compose_conclusion(wp: Dict[str, Any], reasons: List[str], evidence: List[str]) -> str:
    label = wp.get("label", wp.get("id", ""))
    if "blocked" in reasons:
        return f"{label} 处于阻塞状态，影响下游推进"
    if "rework" in reasons:
        return f"{label} 被打回返工，需尽快处理"
    if "dep_risk" in reasons:
        return f"{label} 存在依赖风险，部分前置未完成"
    return f"{label} 需关注：{'、'.join(reasons)}"


# ============================================================
# 风险聚合（RISK 聚类）
# ============================================================

def assess_risk(wp: Dict[str, Any], tasks: Dict[str, Any]) -> Dict[str, Any]:
    """评估工作包风险等级并给出风险原因。"""
    level = "low"
    reasons: List[str] = []
    status = _wp_effective_status(wp, tasks)

    if status == "blocked":
        level = "high"
        reasons.append("blocked")
    elif status == "rework":
        level = "high"
        reasons.append("rework")

    deps = wp.get("deps", [])
    locked = sum(1 for d in deps if tasks.get(d, {}).get("state") != "DONE")
    if locked > 0:
        if level != "high":
            level = "medium"
        reasons.append(f"deps_locked={locked}/{len(deps)}")

    # DDL 临近
    ddl = wp.get("ddl")
    progress = _wp_effective_progress(wp, tasks)
    if ddl and progress < 0.8:
        if level != "high":
            level = "medium"
        reasons.append("ddl_close")

    return {"level": level, "reasons": reasons}


# ============================================================
# 聚合器主类
# ============================================================

class Aggregator:
    """降熵聚合器：把运行时快照转成 L0/L1/L2/L3 各层信息。"""

    def __init__(self, snapshot: Dict[str, Any]):
        self.snap = snapshot
        self.work_packages: List[Dict[str, Any]] = snapshot.get("work_packages", [])
        self.tasks: Dict[str, Any] = snapshot.get("tasks", {})
        # events 统一转为 RawEvent 模型（兼容 dict 列表输入）
        raw_events = snapshot.get("events", [])
        self.events: List[RawEvent] = [
            e if isinstance(e, RawEvent) else RawEvent(**e)
            for e in raw_events
        ]
        self.bus_stats: Dict[str, Any] = snapshot.get("bus_stats", {})
        self.agents: List[Dict[str, Any]] = snapshot.get("agents", [])
        self.project = snapshot.get("project", "")

    # ---------- L0 总览 ----------
    def overview(self) -> Overview:
        total = len(self.work_packages)
        done = sum(1 for w in self.work_packages
                   if _wp_effective_status(w, self.tasks) == "done")
        blocked = sum(1 for w in self.work_packages
                      if _wp_effective_status(w, self.tasks) == "blocked")
        rework = sum(1 for w in self.work_packages
                     if _wp_effective_status(w, self.tasks) == "rework")
        active = sum(1 for w in self.work_packages
                     if _wp_effective_status(w, self.tasks) == "active")

        # 风险评估
        risks = []
        for wp in self.work_packages:
            r = assess_risk(wp, self.tasks)
            if r["level"] != "low":
                risks.append({"work_package_id": wp["id"],
                              "label": wp.get("label", wp["id"]),
                              "level": r["level"], "reasons": r["reasons"]})

        high_risks = [r for r in risks if r["level"] in ("high", "critical")]

        # 健康度
        if high_risks:
            health = "critical"
        elif blocked > 0 or rework > 0:
            health = "warning"
        else:
            health = "healthy"

        metrics = [
            HealthMetric(key="work_packages", label="工作包", value=str(total),
                         status="ok", detail=f"共 {total} 个"),
            HealthMetric(key="active", label="进行中", value=str(active),
                         status="ok", detail=f"{active} 个推进中"),
            HealthMetric(key="done", label="已验收", value=str(done),
                         status="ok", detail=f"完成率 {int(done/total*100) if total else 0}%"),
            HealthMetric(key="blocked", label="阻塞中", value=str(blocked),
                         status="danger" if blocked else "ok",
                         detail=f"{blocked} 个阻塞"),
            HealthMetric(key="rework", label="待返工", value=str(rework),
                         status="warn" if rework else "ok",
                         detail=f"{rework} 个待返工"),
            HealthMetric(key="risks", label="风险", value=str(len(risks)),
                         status="danger" if high_risks else ("warn" if risks else "ok"),
                         detail=f"{len(risks)} 项风险"),
        ]

        # 全局判断信息
        judgments = [self._global_judgment(blocked, rework, high_risks, total)]

        return Overview(
            project=self.project or "未命名项目",
            health=health,
            metrics=metrics,
            risks=risks,
            judgments=[j for j in judgments if j],
            updated_at=self.snap.get("ts", 0.0),
            source={"events": len(self.events), "agents": len(self.agents)},
        )

    def _global_judgment(self, blocked: int, rework: int,
                         high_risks: List[Dict], total: int) -> Optional[Judgment]:
        if not total:
            return None
        evidence: List[str] = []
        if blocked:
            evidence.append(f"{blocked} 个工作包阻塞")
        if rework:
            evidence.append(f"{rework} 个工作包待返工")
        if high_risks:
            evidence.append(f"{len(high_risks)} 项高风险")

        if not evidence:
            return Judgment(conclusion="整体推进正常，无明显阻塞或风险",
                            evidence_chain=["无阻塞/返工/高风险信号"],
                            confidence="high", suggested_action="保持当前节奏")
        level = "high" if (blocked or rework or high_risks) else "medium"
        return Judgment(
            conclusion="存在阻塞或风险，建议介入协调",
            evidence_chain=evidence,
            confidence=level,
            suggested_action="优先处理阻塞/返工工作包，重新评估依赖与 DDL",
        )

    # ---------- L1 聚合 ----------
    def work_packages_aggregate(self, group_by: str = "department") -> Aggregate:
        """按部门或状态聚类工作包（聚类 → 折叠 → 摘要）。"""
        groups: Dict[str, Dict[str, Any]] = {}
        for wp in self.work_packages:
            if group_by == "department":
                key = wp.get("department", "unknown")
                label = wp.get("department_name", key)
            else:  # status
                key = _wp_effective_status(wp, self.tasks)
                label = _status_label(key)
            g = groups.setdefault(key, {"key": key, "label": label,
                                        "members": [], "count": 0})
            g["members"].append(wp["id"])
            g["count"] += 1

        cluster_groups = [
            ClusterGroup(key=g["key"], label=g["label"], count=g["count"],
                         summary=self._group_summary(g["members"], g["label"]),
                         members=g["members"])
            for g in groups.values()
        ]

        # 聚合层判断信息（各工作包判断聚合，去重保序）
        judgments = []
        seen = set()
        for wp in self.work_packages:
            j = build_judgment(wp, self.tasks)
            if j and j.conclusion not in seen:
                seen.add(j.conclusion)
                judgments.append(j)

        return Aggregate(
            meta={"total": len(self.work_packages), "group_by": group_by,
                  "groups": len(cluster_groups), "judgments": len(judgments)},
            groups=cluster_groups,
            judgments=judgments,
            source={"events": len(self.events)},
        )

    def _group_summary(self, members: List[str], label: str) -> str:
        """一句话摘要一个聚类组（降熵核心：N 条信息 → 1 条结论）。"""
        if not members:
            return f"{label}: 无工作包"
        statuses = [_wp_effective_status(self._find_wp(m), self.tasks)
                    for m in members]
        done = statuses.count("done")
        blocked = statuses.count("blocked")
        rework = statuses.count("rework")
        active = statuses.count("active")
        parts = [f"{len(members)} 个工作包", f"{done} 已验收",
                 f"{active} 进行中", f"{blocked} 阻塞", f"{rework} 待返工"]
        kept = [p for p in parts if not p.startswith("0 ")]
        return f"{label}: " + " / ".join(kept) + "."

    def _find_wp(self, wp_id: str) -> Dict[str, Any]:
        for wp in self.work_packages:
            if wp.get("id") == wp_id:
                return wp
        return {"id": wp_id, "status": "pending"}

    # ---------- L2 明细 ----------
    def work_package_detail(self, wp_id: str) -> Optional[WorkPackageDetail]:
        for wp in self.work_packages:
            if wp.get("id") != wp_id:
                continue
            task = self.tasks.get(wp_id, {})
            detail = WorkPackageDetail(
                id=wp["id"], label=wp.get("label", wp["id"]),
                department=wp.get("department", ""),
                department_name=wp.get("department_name", wp.get("department", "")),
                status=_wp_effective_status(wp, self.tasks),
                progress=_wp_effective_progress(wp, self.tasks),
                owner=wp.get("owner", ""),
                deps=wp.get("deps", []),
                ddl=_fmt_time(wp.get("ddl")),
                risk=assess_risk(wp, self.tasks),
                judgment=build_judgment(wp, self.tasks),
                source_events=[e.id for e in self.events
                               if wp["id"] in str(e.payload)],
            )
            return detail
        return None

    def task_detail(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        return {
            "id": task.get("id", task_id), "name": task.get("name", ""),
            "owner": task.get("owner", ""), "state": task.get("state", ""),
            "priority": task.get("priority", ""), "deps": task.get("deps", []),
            "progress": task.get("progress", 0.0),
            "ddl": _fmt_time(task.get("ddl")),
            "history": task.get("history", []),
        }

    # ---------- L3 原始 ----------
    def raw_events(self, limit: int = 50, msg_type: Optional[str] = None) -> List[RawEvent]:
        events = self.events
        if msg_type:
            events = [e for e in events if e.type == msg_type]
        events = events[-limit:]
        return events

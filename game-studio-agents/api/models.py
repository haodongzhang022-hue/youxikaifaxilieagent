# ============================================================
# 四层信息模型（Pydantic 数据模型）
# 版本: v0.9
# 说明: 对应 docs/unified-command-center.md 的四层信息分层模型：
#       L0 总览 / L1 聚合 / L2 明细 / L3 原始。
#       统一返回结构为 { meta(聚合摘要), items(明细), source(溯源指针) }，
#       让前端 / AI 天然支持"聚合 → 明细 → 溯源"的渐进式展开。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# L3 原始层：可溯源的基础信息
# ============================================================

class RawEvent(BaseModel):
    """L3 原始事件（一条消息 / 日志 / 状态流转）"""
    id: str = ""
    type: str = ""                     # 消息类型（TASK_ASSIGN / DELIVERY / REVIEW ...）
    actor: str = ""                    # 产生方（role_id）
    target: str = ""                   # 接收方 / 目标实体
    ts: float = 0.0                    # 时间戳
    summary: str = ""                  # 一句话摘要
    payload: Dict[str, Any] = Field(default_factory=dict)  # 原始内容


# ============================================================
# 判断信息（决策支撑）
# ============================================================

class Judgment(BaseModel):
    """关键判断 + 依据链 + 置信度 + 建议动作（决策支撑）"""
    conclusion: str = ""               # 判断结论（如"发版存在延期风险"）
    evidence_chain: List[str] = Field(default_factory=list)   # 依据链
    confidence: str = "medium"         # low / medium / high
    suggested_action: str = ""         # 建议动作


# ============================================================
# L2 明细层：单个实体的结构化信息
# ============================================================

class WorkPackageDetail(BaseModel):
    """L2 单个工作包明细"""
    id: str = ""
    label: str = ""
    department: str = ""
    department_name: str = ""
    status: str = ""                   # pending/active/done/blocked/rework
    progress: float = 0.0
    owner: str = ""
    deps: List[str] = Field(default_factory=list)
    ddl: Optional[str] = None
    risk: Dict[str, Any] = Field(default_factory=dict)
    judgment: Optional[Judgment] = None
    source_events: List[str] = Field(default_factory=list)   # → L3


class TaskDetail(BaseModel):
    """L2 单个调度任务明细"""
    id: str = ""
    name: str = ""
    owner: str = ""
    state: str = ""
    priority: str = ""
    deps: List[str] = Field(default_factory=list)
    progress: float = 0.0
    ddl: Optional[str] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)   # → L3 溯源


# ============================================================
# L1 聚合层：聚类分类后的关键信息
# ============================================================

class ClusterGroup(BaseModel):
    """L1 一个聚类分组（按部门/状态/风险等维度）"""
    key: str = ""
    label: str = ""
    count: int = 0
    summary: str = ""                  # 一句话摘要（降熵）
    members: List[str] = Field(default_factory=list)   # 成员 id → L2


class Aggregate(BaseModel):
    """L1 聚合结果：聚类分组 + 判断信息 + 溯源指针"""
    meta: Dict[str, Any] = Field(default_factory=dict)   # 聚合摘要
    groups: List[ClusterGroup] = Field(default_factory=list)
    judgments: List[Judgment] = Field(default_factory=list)
    source: Dict[str, Any] = Field(default_factory=dict) # → L3 溯源指针


# ============================================================
# L0 总览层：一眼看懂全局
# ============================================================

class HealthMetric(BaseModel):
    """L0 一个健康指标"""
    key: str = ""
    label: str = ""
    value: str = ""
    status: str = "ok"                 # ok / warn / danger
    detail: str = ""


class Overview(BaseModel):
    """L0 总览：关键数字 + 健康度 + 风险信号 + 判断信息"""
    project: str = ""
    health: str = ""                   # healthy / warning / critical
    metrics: List[HealthMetric] = Field(default_factory=list)
    risks: List[Dict[str, Any]] = Field(default_factory=list)
    judgments: List[Judgment] = Field(default_factory=list)
    updated_at: float = 0.0
    source: Dict[str, Any] = Field(default_factory=dict)  # → L3 溯源


# ============================================================
# 统一响应信封
# ============================================================

class ApiResponse(BaseModel):
    """所有接口统一响应信封：降熵后的关键信息 + 溯源指针"""
    layer: str = ""                    # L0 / L1 / L2 / L3
    ok: bool = True
    data: Any = None
    meta: Dict[str, Any] = Field(default_factory=dict)   # 聚合摘要 / 计数
    source: Dict[str, Any] = Field(default_factory=dict) # 溯源指针

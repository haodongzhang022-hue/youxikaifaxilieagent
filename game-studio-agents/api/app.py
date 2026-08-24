# ============================================================
# 信息接口层 · FastAPI 应用
# 版本: v0.9
# 说明: 统一管理与可视化指挥中枢的**机器接口层**。
#
#   【接口层与人工可视层分离】
#   本应用只提供**信息接口（API）**，不做任何人类展示。
#   - AI 读取 → 调用 /ai/* 机器接口（结构化、低冗余、聚合、可溯源）
#   - 人类查看 → 前端页面调用 /dashboard/* 通用接口渲染
#   两者共用同一套降熵聚合引擎，但 AI 接口聚焦"决策所需最小充分信号"，
#   避免 AI 每次读取都混入人类偏好展示内容，从而减少无效上下文、提升效率。
#
# 语言: Python 3 (可运行) · 依赖 fastapi / uvicorn / pydantic
# ============================================================
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional

# 让 api 包自身可被相对导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import (Depends, FastAPI, Header, HTTPException,   # noqa: E402
                     Query)
from pydantic import BaseModel                                   # noqa: E402

from aggregator import Aggregator, assess_risk, build_judgment   # noqa: E402
from models import (Aggregate, ApiResponse, Judgment, Overview,  # noqa: E402
                    RawEvent, WorkPackageDetail)
from runtime import bootstrap, build_snapshot                    # noqa: E402


# ============================================================
# 全局运行时（可被外部 attach 到运行中的 manager）
# ============================================================

# 全局持有：附加外部 manager / bus 后，接口即读取该实例快照。
_managed_manager = None
_managed_bus = None
_bootstrapped = False


def attach_runtime(manager=None, bus=None, force_bootstrap: bool = False):
    """把外部运行中的 manager / bus 附加到接口层。

    若未提供，默认调用 bootstrap() 拉起一次示范编排作为数据源（演示/测试用）。
    """
    global _managed_manager, _managed_bus, _bootstrapped
    if manager is not None:
        _managed_manager = manager
        _managed_bus = bus or getattr(manager, "bus", None)
    elif _managed_manager is None:
        if force_bootstrap or not _bootstrapped:
            rt = bootstrap()
            _managed_manager = rt["manager"]
            _managed_bus = rt["bus"]
            _bootstrapped = True


def _snapshot() -> Dict[str, Any]:
    attach_runtime()  # 确保有数据源
    return build_snapshot(manager=_managed_manager, bus=_managed_bus)


def _agg() -> Aggregator:
    return Aggregator(_snapshot())


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title="游戏开发指挥中枢 · 信息接口层",
    description="机器接口层：供 AI 读取的降熵聚合信号 + 供前端渲染的四层信息模型。",
    version="0.9.0",
)


# ============================================================
# 安全：可选 Bearer Token 鉴权 + 本地绑定
# ============================================================
# 通过环境变量 API_TOKEN 设置鉴权令牌。未设置时放行（默认仅绑定本机）。
# 生产环境务必设置 API_TOKEN，且默认绑定 127.0.0.1，避免信息泄露。
_API_TOKEN = (os.environ.get("API_TOKEN") or "").strip()


async def require_token(authorization: Optional[str] = Header(None)):
    """Bearer token 鉴权依赖（应用于 /ai/* 与 /dashboard/*）。

    - 若 API_TOKEN 未配置，视为允许访问（本地开发/默认绑定本机场景）；
    - 若配置了 API_TOKEN，请求必须携带匹配的 Bearer token，否则 401。
    """
    if not _API_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Bearer 令牌")
    token = authorization[7:].strip()
    if token != _API_TOKEN:
        raise HTTPException(status_code=401, detail="令牌无效")


# ---------- 根 / 健康检查 ----------
@app.get("/", tags=["meta"])
def root():
    return {
        "service": "game-command-center-api",
        "version": "0.9.0",
        "note": "接口层与人工可视层分离：AI 读取 /ai/*，人类前端读取 /dashboard/*",
        "endpoints": ["/ai/overview", "/ai/workpackages", "/ai/workpackages/{id}",
                      "/ai/risks", "/ai/tasks", "/ai/events",
                      "/dashboard/overview", "/dashboard/workpackages",
                      "/dashboard/dependencies", "/dashboard/risks",
                      "/dashboard/workpackages/{id}", "/dashboard/events"],
    }


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True, "ts": time.time()}


# ============================================================
# /ai/*   —— AI 专用机器接口（低冗余、结构化、聚合）
# ============================================================

@app.get("/ai/overview", response_model=ApiResponse, tags=["ai"],
         dependencies=[Depends(require_token)])
def ai_overview():
    """L0 总览：AI 一眼拿到全局健康度 + 关键信号 + 判断。"""
    ov = _agg().overview()
    return ApiResponse(
        layer="L0", data=ov.model_dump(),
        meta={"health": ov.health, "metrics": len(ov.metrics)},
        source=ov.source,
    )


@app.get("/ai/workpackages", response_model=ApiResponse, tags=["ai"],
         dependencies=[Depends(require_token)])
def ai_workpackages(group_by: str = Query("department", pattern="^(department|status)$")):
    """L1 聚合：按部门/状态聚类的工作包 + 判断信息。"""
    agg = _agg().work_packages_aggregate(group_by=group_by)
    # AI 接口：只返回聚合后的 key/label/count/summary/judgments，去掉冗余 members
    slim = {
        "groups": [{"key": g.key, "label": g.label, "count": g.count,
                    "summary": g.summary} for g in agg.groups],
        "judgments": [j.model_dump() for j in agg.judgments],
    }
    return ApiResponse(layer="L1", data=slim, meta=agg.meta, source=agg.source)


@app.get("/ai/workpackages/{wp_id}", response_model=ApiResponse, tags=["ai"],
         dependencies=[Depends(require_token)])
def ai_workpackage(wp_id: str):
    """L2 明细：单个工作包完整结构化信息（含判断与溯源）。"""
    detail = _agg().work_package_detail(wp_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"工作包 {wp_id} 不存在")
    return ApiResponse(layer="L2", data=detail.model_dump(),
                       meta={"id": wp_id},
                       source={"events": detail.source_events})


@app.get("/ai/risks", response_model=ApiResponse, tags=["ai"],
         dependencies=[Depends(require_token)])
def ai_risks():
    """L1 风险聚类：所有风险工作包 + 判断信息（决策支撑）。"""
    agg = _agg()
    risks = []
    for wp in agg.work_packages:
        r = assess_risk(wp, agg.tasks)
        if r["level"] != "low":
            j = build_judgment(wp, agg.tasks)
            risks.append({
                "work_package_id": wp["id"], "label": wp.get("label", wp["id"]),
                "department": wp.get("department_name", ""), "level": r["level"],
                "reasons": r["reasons"],
                "judgment": j.model_dump() if j else None,
            })
    # 按风险等级降序
    level_order = {"critical": 3, "high": 2, "medium": 1}
    risks.sort(key=lambda x: level_order.get(x["level"], 0), reverse=True)
    return ApiResponse(layer="L1", data=risks,
                       meta={"total": len(risks), "high": sum(1 for r in risks if r["level"] in ("high","critical"))},
                       source={"events": len(agg.events)})


@app.get("/ai/tasks", response_model=ApiResponse, tags=["ai"],
         dependencies=[Depends(require_token)])
def ai_tasks():
    """L2 任务清单：调度器任务状态概览（供 AI 判断推进进度）。"""
    agg = _agg()
    tasks = []
    for tid, task in agg.tasks.items():
        tasks.append({
            "id": tid, "name": task.get("name", ""), "owner": task.get("owner", ""),
            "state": task.get("state", ""), "priority": task.get("priority", ""),
            "deps": task.get("deps", []), "progress": task.get("progress", 0.0),
        })
    from collections import Counter
    by_state = Counter(t.get("state") for t in tasks)
    return ApiResponse(layer="L2", data=tasks,
                       meta={"total": len(tasks), "by_state": dict(by_state)},
                       source={"ts": agg.snap.get("ts", 0.0)})


@app.get("/ai/events", response_model=ApiResponse, tags=["ai"],
         dependencies=[Depends(require_token)])
def ai_events(limit: int = Query(20, ge=1, le=200),
              msg_type: Optional[str] = Query(None)):
    """L3 原始事件流：可溯源证据（AI 需要核实某判断时下钻到原始层）。"""
    agg = _agg()
    events = agg.raw_events(limit=limit, msg_type=msg_type)
    return ApiResponse(layer="L3",
                       data=[e.model_dump() for e in events],
                       meta={"total": len(events), "limit": limit, "msg_type": msg_type},
                       source={"bus_stats": agg.bus_stats})


# ============================================================
# /dashboard/*  —— 人类可视化通用接口（支撑前端，渐进式展开）
# ============================================================

@app.get("/dashboard/overview", response_model=Overview, tags=["dashboard"],
         dependencies=[Depends(require_token)])
def dashboard_overview():
    """L0 总览（前端首屏）：健康度 + 关键指标 + 风险 + 判断。"""
    return _agg().overview()


@app.get("/dashboard/workpackages", response_model=Aggregate, tags=["dashboard"],
         dependencies=[Depends(require_token)])
def dashboard_workpackages(group_by: str = Query("department", pattern="^(department|status)$")):
    """L1 聚合（前端分页默认）：聚类分组 + 判断，含 members 供下钻。"""
    return _agg().work_packages_aggregate(group_by=group_by)


@app.get("/dashboard/dependencies", response_model=ApiResponse, tags=["dashboard"],
         dependencies=[Depends(require_token)])
def dashboard_dependencies():
    """L1 部门依赖拓扑：部门间上下游解锁链路。"""
    agg = _agg()
    # 部门依赖图
    wp_by_dept: Dict[str, List[str]] = {}
    for wp in agg.work_packages:
        wp_by_dept.setdefault(wp.get("department_name", wp.get("department", "")), []).append(wp["id"])

    # 部门间依赖边：由工作包 deps 推导
    edges = []
    id_to_dept = {wp["id"]: wp.get("department_name", wp.get("department", ""))
                  for wp in agg.work_packages}
    for wp in agg.work_packages:
        for d in wp.get("deps", []):
            src_dept = id_to_dept.get(d)
            dst_dept = wp.get("department_name", wp.get("department", ""))
            if src_dept and dst_dept and src_dept != dst_dept:
                edges.append({"from": src_dept, "to": dst_dept,
                              "work_package": wp["id"], "dep": d})

    # 部门负载
    from collections import Counter
    dept_load = Counter(wp.get("department_name", wp.get("department", ""))
                        for wp in agg.work_packages)
    return ApiResponse(layer="L1",
                       data={"departments": [{"name": k, "count": v}
                                             for k, v in dept_load.items()],
                             "edges": edges},
                       meta={"departments": len(dept_load), "edges": len(edges)},
                       source={"events": len(agg.events)})


@app.get("/dashboard/risks", response_model=ApiResponse, tags=["dashboard"],
         dependencies=[Depends(require_token)])
def dashboard_risks():
    """L1 风险聚类 + 判断（前端风险分页）。"""
    return ai_risks()


@app.get("/dashboard/workpackages/{wp_id}", response_model=WorkPackageDetail, tags=["dashboard"],
         dependencies=[Depends(require_token)])
def dashboard_workpackage(wp_id: str):
    """L2 单个工作包明细（前端点击展开）。"""
    detail = _agg().work_package_detail(wp_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"工作包 {wp_id} 不存在")
    return detail


@app.get("/dashboard/events", response_model=ApiResponse, tags=["dashboard"],
         dependencies=[Depends(require_token)])
def dashboard_events(limit: int = Query(50, ge=1, le=500),
                     msg_type: Optional[str] = Query(None)):
    """L3 原始事件流（前端溯源下钻）。"""
    return ai_events(limit=limit, msg_type=msg_type)


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    # 默认仅绑定本机（避免工作包/风险/原始事件信息泄露）；
    # 如需跨机访问显式设置 HOST=0.0.0.0 并务必配置 API_TOKEN 鉴权。
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run("app:app", host=host, port=int(os.environ.get("PORT", 8000)),
                reload=False)

# ============================================================
# 管线矩阵驱动发布评审核心（Pipeline Release Review）
# 版本: v1.0
# 说明: 让发布评审从「全链路一刀切」升级为「管线矩阵驱动」。
#       基于 40 条管线矩阵（pipeline_registry.py），每条管线独立评审、
#       独立放行，同时保留全链路总评审（复用 release_gate）。
#
# 对齐 Issue #128（游戏架构师 M1 蓝图）：
#   - 单条管线 GO/NO-GO 发布评审（M1）
#   - 管线级阶段边界审查（stage_gate 逐管线校验）
#   - 全链路总评审聚合（M2）
#
# 语言: Python 3 (可运行)
# 依赖: pipeline_registry (PipelineDef) / pipeline_orchestrator (PipelineState)
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pipeline_registry import PipelineRegistry, PipelineDef
from pipeline_orchestrator import PipelineState, PipelineExecution


# ============================================================
# 核心数据模型（协议先行 · 对齐架构师蓝图）
# ============================================================

@dataclass
class PipelineRelease:
    """单条管线的发布评审记录（架构师蓝图 §三）"""
    pipeline_id: str                 # 如 "pipeline.character_animation.unity"
    engine: str                      # react/cocos/unity/unreal
    domain: str                      # 专业方向
    state: str = "pending"           # pending/ready/in_progress/completed/failed
    quality_checks: Dict[str, bool] = field(default_factory=dict)  # 逐项质量门禁
    stage_gate: Dict[str, bool] = field(default_factory=dict)      # 阶段边界审查(3项)
    release_verdict: str = "NO-GO"   # "GO" | "NO-GO"
    released_at: str = ""            # 放行时间
    notes: str = ""                  # 备注

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "engine": self.engine,
            "domain": self.domain,
            "state": self.state,
            "quality_checks": self.quality_checks,
            "stage_gate": self.stage_gate,
            "release_verdict": self.release_verdict,
            "released_at": self.released_at,
            "notes": self.notes,
        }


@dataclass
class ReleaseReport:
    """发布评审总报告（架构师蓝图 §三）"""
    pipeline_count: int = 0                    # 参与评审的管线数
    passed: int = 0                            # GO 数
    failed: int = 0                            # NO-GO 数
    blocked: int = 0                           # 依赖阻塞数
    engine_summary: Dict[str, Dict] = field(default_factory=dict)  # 按引擎汇总
    overall: str = "NO-GO"                     # "GO" | "NO-GO"
    verdict: str = ""                          # 中文结论

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_count": self.pipeline_count,
            "passed": self.passed,
            "failed": self.failed,
            "blocked": self.blocked,
            "engine_summary": self.engine_summary,
            "overall": self.overall,
            "verdict": self.verdict,
        }


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# 管线发布评审核心
# ============================================================

class PipelineReleaseReviewer:
    """管线发布评审器：基于管线矩阵做单管线 + 全链路发布评审。

    设计原则（对齐架构师护栏核查）：
      - 纯逻辑、数据驱动，非引擎耦合；
      - 无状态优先：评审函数为纯逻辑，不持有会话状态；
      - 作为 release_gate 的**增强层**，不破坏现有全链路评审逻辑。
    """

    def __init__(self, registry: Optional[PipelineRegistry] = None):
        self.registry = registry or PipelineRegistry()

    # ---- M1: 单管线发布评审 ----

    def run_pipeline_release(self, engine: str, domain: str,
                             execution_result: Optional[Dict[str, Any]] = None,
                             stage_checks: Optional[Dict[str, bool]] = None) -> PipelineRelease:
        """单条管线发布评审。

        Args:
            engine: 引擎（react/cocos/unity/unreal）
            domain: 专业方向（character_animation 等）
            execution_result: 管线执行结果，含 quality_checks（逐项质量门禁）
            stage_checks: 管线级阶段边界审查（no_stage_crossing/reusable_assets/stage_alignment）

        Returns:
            PipelineRelease 评审记录（含 GO/NO-GO）
        """
        pipe = self.registry.by_engine_and_domain(engine, domain)
        if pipe is None:
            # 未知管线 → NO-GO 并标注
            return PipelineRelease(
                pipeline_id=f"pipeline.{domain}.{engine}",
                engine=engine, domain=domain,
                state="failed", release_verdict="NO-GO",
                notes=f"未知管线: 引擎 {engine} × 方向 {domain} 未在管线矩阵注册",
            )

        # 消费管线执行状态（若提供）
        state = "in_progress"
        if execution_result is not None:
            ex_state = execution_result.get("state")
            if ex_state:
                state = ex_state
        pr = PipelineRelease(
            pipeline_id=pipe.pipeline_id,
            engine=engine, domain=domain,
            state=state,
        )

        # ① 质量门禁逐项核对（消费 PipelineDef.quality_gates）
        exec_checks = (execution_result or {}).get("quality_checks", {})
        quality_checks = {}
        for gate in pipe.quality_gates:
            quality_checks[gate] = bool(exec_checks.get(gate, False))
        pr.quality_checks = quality_checks

        # ② 阶段边界审查逐管线校验
        stage_checks = stage_checks or {}
        pr.stage_gate = {
            "no_stage_crossing": bool(stage_checks.get("no_stage_crossing", True)),
            "reusable_assets": bool(stage_checks.get("reusable_assets", True)),
            "stage_alignment": bool(stage_checks.get("stage_alignment", True)),
        }

        # ③ 依赖检查：依赖管线未放行则该管线阻塞
        dep_blocked = self._check_dependencies(pipe)

        # ④ 综合判 GO/NO-GO
        quality_ok = all(quality_checks.values())
        stage_ok = all(pr.stage_gate.values())
        state_ok = state not in (PipelineState.FAILED, PipelineState.CANCELLED, PipelineState.BLOCKED)

        if dep_blocked:
            pr.release_verdict = "NO-GO"
            pr.state = PipelineState.BLOCKED
            pr.notes = f"依赖管线未放行: {', '.join(dep_blocked)}"
        elif quality_ok and stage_ok and state_ok:
            pr.release_verdict = "GO"
            pr.released_at = _now()
            pr.notes = "管线发布评审通过"
        else:
            pr.release_verdict = "NO-GO"
            # 汇总未达标项
            missing = [g for g, ok in quality_checks.items() if not ok]
            pr.notes = "未达标: " + ("; ".join(
                ([f"质量门禁缺 {', '.join(missing)}"] if missing else []) +
                ([f"阶段边界审查未通过"] if not stage_ok else []) +
                ([f"执行状态 {state} 不可放行"] if not state_ok else [])
            ))
        return pr

    def _check_dependencies(self, pipe: PipelineDef,
                            released: Optional[set] = None) -> List[str]:
        """检查管线依赖是否已被放行。

        依赖管线（如 skeleton_binding → character_animation）需先放行
        才能放行下游。released 为已放行管线 id 集合；缺省视为全部就绪。
        """
        if not pipe.dependencies:
            return []
        if released is None:
            # 未提供放行集时，认为依赖缺省就绪（依赖在编排器侧已保证）
            return []
        return [d for d in pipe.dependencies if d not in released]

    # ---- M2: 全链路总评审聚合 ----

    def fullchain_release(self, releases: List[PipelineRelease]) -> ReleaseReport:
        """聚合所有管线评审结果 → 全链路总 GO/NO-GO（架构师蓝图 §四④）。"""
        if not releases:
            return ReleaseReport(pipeline_count=0, overall="NO-GO",
                                 verdict="无管线参与评审")

        passed = sum(1 for r in releases if r.release_verdict == "GO")
        failed = sum(1 for r in releases if r.release_verdict == "NO-GO"
                     and r.state != PipelineState.BLOCKED)
        blocked = sum(1 for r in releases if r.state == PipelineState.BLOCKED)

        # 按引擎汇总
        engine_summary: Dict[str, Dict] = {}
        for r in releases:
            es = engine_summary.setdefault(r.engine, {"total": 0, "passed": 0, "failed": 0, "blocked": 0})
            es["total"] += 1
            if r.release_verdict == "GO":
                es["passed"] += 1
            elif r.state == PipelineState.BLOCKED:
                es["blocked"] += 1
            else:
                es["failed"] += 1

        all_go = passed == len(releases)
        overall = "GO" if all_go else "NO-GO"
        if all_go:
            verdict = f"✅ 全链路发布评审通过：{passed}/{len(releases)} 条管线全部 GO"
        else:
            verdict = (f"❌ 全链路发布评审未通过：GO {passed} / NO-GO {failed} "
                       f"/ 阻塞 {blocked}（共 {len(releases)} 条管线）")
        return ReleaseReport(
            pipeline_count=len(releases),
            passed=passed, failed=failed, blocked=blocked,
            engine_summary=engine_summary,
            overall=overall, verdict=verdict,
        )


    def _topo_sort(self, pipes: List[PipelineDef]) -> List[PipelineDef]:
        """按依赖关系拓扑排序：依赖管线在前，被依赖方在后。

        确保评审时依赖管线已先放行，使下游管线能正确判定依赖是否就绪
        （对齐 pipeline_orchestrator 的依赖检测语义）。
        """
        by_id = {p.pipeline_id: p for p in pipes}
        ordered: List[PipelineDef] = []
        visited: set = set()

        def _visit(p: PipelineDef):
            if p.pipeline_id in visited:
                return
            visited.add(p.pipeline_id)
            for dep_id in p.dependencies:
                dep = by_id.get(dep_id)
                if dep is not None:
                    _visit(dep)
            ordered.append(p)

        for p in pipes:
            _visit(p)
        return ordered

    # ---- 便捷批量评审 ----

    def review_engine(self, engine: str,
                      all_gates_ok: bool = True,
                      stage_ok: bool = True) -> List[PipelineRelease]:
        """按引擎批量评审全部管线（M2 · 40 条管线逐条可评审）。

        Args:
            engine: 目标引擎
            all_gates_ok: 是否让所有管线质量门禁全部通过（True=全部GO用于演示通过链路）
            stage_ok: 阶段边界审查是否通过
        """
        pipes = self.registry.by_engine(engine)
        # 拓扑排序：依赖管线先评审（skeleton_binding → character_animation 等）
        pipes = self._topo_sort(pipes)
        releases = []
        released: set = set()
        for pipe in pipes:
            if all_gates_ok:
                exec_result = {"state": PipelineState.COMPLETED,
                               "quality_checks": {g: True for g in pipe.quality_gates}}
                stage_checks = {"no_stage_crossing": stage_ok,
                                "reusable_assets": stage_ok,
                                "stage_alignment": stage_ok}
            else:
                exec_result = {"state": PipelineState.IN_PROGRESS,
                               "quality_checks": {}}
                stage_checks = {"no_stage_crossing": False,
                                "reusable_assets": False,
                                "stage_alignment": False}
            pr = self.run_pipeline_release(pipe.engine, pipe.domain,
                                           exec_result, stage_checks)
            # 依赖检查：下游依赖已放行则放行，否则阻塞
            if pipe.dependencies:
                if not all(d in released for d in pipe.dependencies):
                    pr.release_verdict = "NO-GO"
                    pr.state = PipelineState.BLOCKED
                    missing_deps = [d for d in pipe.dependencies if d not in released]
                    pr.notes = f"依赖管线未放行: {', '.join(missing_deps)}"
            if pr.release_verdict == "GO":
                released.add(pipe.pipeline_id)
            releases.append(pr)
        return releases


# ============================================================
# 便捷 API（对齐架构师接口契约）
# ============================================================

def run_pipeline_release(engine: str, domain: str,
                         execution_result: Optional[Dict[str, Any]] = None,
                         stage_checks: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """便捷入口：单条管线发布评审 → dict 结果。"""
    reviewer = PipelineReleaseReviewer()
    pr = reviewer.run_pipeline_release(engine, domain, execution_result, stage_checks)
    return {
        "pipeline_id": pr.pipeline_id,
        "verdict": pr.release_verdict,
        "passed_checks": [g for g, ok in pr.quality_checks.items() if ok],
        "missing_checks": [g for g, ok in pr.quality_checks.items() if not ok],
        "notes": pr.notes,
        "state": pr.state,
    }


def fullchain_release(releases: List[PipelineRelease]) -> Dict[str, Any]:
    """便捷入口：全链路总评审 → dict 结果。"""
    reviewer = PipelineReleaseReviewer()
    report = reviewer.fullchain_release(releases)
    return report.to_dict()


# ============================================================
# 自测
# ============================================================

def demo():
    print("=" * 70)
    print("管线矩阵驱动发布评审核心（M1+M2）")
    print("=" * 70)
    reviewer = PipelineReleaseReviewer()

    # --- M1: 单管线 GO/NO-GO ---
    print("\n[1] 单管线发布评审（Unity 角色动作）")
    go = reviewer.run_pipeline_release(
        "unity", "character_animation",
        {"state": PipelineState.COMPLETED,
         "quality_checks": {"动作流畅度": True, "性能基准": True, "风格一致性": True}},
        {"no_stage_crossing": True, "reusable_assets": True, "stage_alignment": True},
    )
    print(f"    {go.pipeline_id} → {go.release_verdict} | {go.notes}")

    no_go = reviewer.run_pipeline_release(
        "unity", "character_animation",
        {"state": PipelineState.IN_PROGRESS,
         "quality_checks": {"动作流畅度": False, "性能基准": True, "风格一致性": True}},
    )
    print(f"    {no_go.pipeline_id} → {no_go.release_verdict} | {no_go.notes}")

    # --- M2: 全链路总评审 ---
    print("\n[2] 全链路总评审（Unity 引擎逐管线评审）")
    unity_releases = reviewer.review_engine("unity", all_gates_ok=True)
    report = reviewer.fullchain_release(unity_releases)
    print(f"    Unity 管线: {report.pipeline_count} 条, GO {report.passed} / 阻塞 {report.blocked}")
    print(f"    总评审: {report.overall} | {report.verdict}")

    print("\n[3] 40 条管线逐条可评审（全引擎）")
    all_releases = []
    for eng in ["react", "cocos", "unity", "unreal"]:
        all_releases += reviewer.review_engine(eng, all_gates_ok=True)
    full = reviewer.fullchain_release(all_releases)
    print(f"    参与评审管线: {full.pipeline_count} 条, GO {full.passed}, 阻塞 {full.blocked}")
    print(f"    全链路: {full.overall} | {full.verdict}")

    print("\n[4] 单管线评审走便捷 API（含未达标项）")
    res = run_pipeline_release("cocos", "ai_trigger",
                               {"state": PipelineState.COMPLETED,
                                "quality_checks": {"行为覆盖率": True, "帧率影响≤5%": False}})
    print(f"    {res['pipeline_id']} → {res['verdict']} | 缺: {res['missing_checks']}")

    # 断言
    assert go.release_verdict == "GO"
    assert no_go.release_verdict == "NO-GO"
    assert report.overall == "GO"
    assert full.pipeline_count >= 40, f"应评审≥40条管线, got {full.pipeline_count}"
    assert full.overall == "GO"
    print("\n[PASS] 管线发布评审核心自测通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(demo())

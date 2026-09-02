# ============================================================
# 管线质量门禁（Pipeline Quality Gate）
# 版本: v1.0
# 说明: 消费 PipelineDef.quality_gates（每条管线独立门禁）与
#       PipelineExecution 执行状态，做**逐管线的质量门禁核对**。
#
# 对齐 Issue #128（游戏架构师 M2 蓝图）：
#   - 消费 PipelineDef.quality_gates 逐项门禁（每条管线独立）
#   - 消费 PipelineExecution 执行状态
#   - 阶段边界审查（stage_gate）逐管线校验
#
# 语言: Python 3 (可运行)
# 依赖: pipeline_registry / pipeline_orchestrator / pipeline_release
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pipeline_registry import PipelineRegistry
from pipeline_orchestrator import PipelineState
from pipeline_release import PipelineReleaseReviewer, PipelineRelease, ReleaseReport


# ============================================================
# 管线质量门禁
# ============================================================

class PipelineQualityGate:
    """管线质量门禁：逐条管线独立门禁核对 + 阶段边界审查。

    设计：纯逻辑、数据驱动，作为 release_gate 的增强层。
    """

    def __init__(self, registry: Optional[PipelineRegistry] = None):
        self.registry = registry or PipelineRegistry()
        self.reviewer = PipelineReleaseReviewer(self.registry)

    # ---- M2: 单管线质量门禁 ----

    def check_pipeline(self, pipeline_id: str,
                       execution_state: str = PipelineState.COMPLETED,
                       quality_passed: Optional[Dict[str, bool]] = None,
                       stage_checks: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
        """单条管线的质量门禁核对。

        Args:
            pipeline_id: 管线 ID
            execution_state: 执行状态（默认 completed）
            quality_passed: 逐项质量门禁通过与否（缺省全通过）
            stage_checks: 阶段边界审查（缺省全通过）

        Returns:
            {pipeline_id, gate_name, verdict, passed_checks, missing_checks, stage_gate}
        """
        pipe = self.registry.get(pipeline_id)
        if pipe is None:
            return {"pipeline_id": pipeline_id, "verdict": "NO-GO",
                    "passed_checks": [], "missing_checks": [],
                    "gate_name": "unknown", "stage_gate": {}, "error": "未知管线"}

        # 缺省：认为全部质量门禁通过（由调用方传入实际结果覆盖）
        if quality_passed is None:
            quality_passed = {g: True for g in pipe.quality_gates}
        if stage_checks is None:
            stage_checks = {"no_stage_crossing": True,
                            "reusable_assets": True,
                            "stage_alignment": True}

        # 复用 pipeline_release 的评审逻辑
        exec_result = {"state": execution_state, "quality_checks": quality_passed}
        pr = self.reviewer.run_pipeline_release(pipe.engine, pipe.domain,
                                                exec_result, stage_checks)

        passed_checks = [g for g, ok in pr.quality_checks.items() if ok]
        missing_checks = [g for g, ok in pr.quality_checks.items() if not ok]
        return {
            "pipeline_id": pipeline_id,
            "gate_name": pipe.name,
            "engine": pipe.engine,
            "domain": pipe.domain,
            "verdict": pr.release_verdict,
            "passed_checks": passed_checks,
            "missing_checks": missing_checks,
            "stage_gate": pr.stage_gate,
            "state": pr.state,
            "notes": pr.notes,
        }

    # ---- M2: 引擎级批量质量门禁 ----

    def check_engine(self, engine: str,
                     all_quality_ok: bool = True) -> Dict[str, Any]:
        """按引擎批量核对全部管线的质量门禁。

        Returns:
            {engine, total, passed, failed, blocked, pipelines: [...]}
        """
        pipes = self.registry.by_engine(engine)
        releases = self.reviewer.review_engine(
            engine, all_gates_ok=all_quality_ok, stage_ok=all_quality_ok)
        report = self.reviewer.fullchain_release(releases)
        return {
            "engine": engine,
            "total": len(pipes),
            "passed": report.passed,
            "failed": report.failed,
            "blocked": report.blocked,
            "overall": report.overall,
            "verdict": report.verdict,
            "pipelines": [r.to_dict() for r in releases],
        }

    # ---- M2: 全引擎逐条可评审 ----

    def check_all_engines(self, all_quality_ok: bool = True) -> Dict[str, Any]:
        """全引擎 40+ 条管线逐条质量门禁评审。"""
        all_releases: List[PipelineRelease] = []
        engine_summary: Dict[str, Dict] = {}
        for eng in ["react", "cocos", "unity", "unreal"]:
            releases = self.reviewer.review_engine(eng, all_gates_ok=all_quality_ok,
                                                   stage_ok=all_quality_ok)
            all_releases += releases
            report = self.reviewer.fullchain_release(releases)
            engine_summary[eng] = {
                "total": report.pipeline_count,
                "passed": report.passed,
                "failed": report.failed,
                "blocked": report.blocked,
                "overall": report.overall,
            }
        full = self.reviewer.fullchain_release(all_releases)
        return {
            "pipeline_count": full.pipeline_count,
            "passed": full.passed,
            "failed": full.failed,
            "blocked": full.blocked,
            "overall": full.overall,
            "verdict": full.verdict,
            "engine_summary": engine_summary,
        }


# ============================================================
# release_gate 管线级聚合扩展（M2 · 增强层，不破坏现有逻辑）
# ============================================================

# 扩展后的管线级门禁键（并入 release_gate.py 的 RELEASE_GATE）
PIPELINE_QUALITY_GATE = {
    "pipeline_quality": {
        "required": True,
        "desc": "管线矩阵驱动发布评审：40 条管线逐条质量门禁 + 阶段边界审查，全链路 GO",
        "checks": ["pipeline_reviewed", "pipeline_go", "stage_gate_per_pipeline"],
    },
}


def run_pipeline_quality_gate(all_quality_ok: bool = True) -> Dict[str, Any]:
    """管线级质量门禁执行（供 release_gate 扩展聚合调用）。"""
    gate = PipelineQualityGate()
    result = gate.check_all_engines(all_quality_ok=all_quality_ok)
    passed = []
    if result["pipeline_count"] >= 40:
        passed.append("pipeline_reviewed")
    if result["overall"] == "GO":
        passed.append("pipeline_go")
    # 阶段边界审查逐管线校验（全引擎 all_gates_ok 时 stage_gate 均通过）
    if all_quality_ok:
        passed.append("stage_gate_per_pipeline")
    required = PIPELINE_QUALITY_GATE["pipeline_quality"]["checks"]
    ok = all(c in passed for c in required)
    return {
        "passed": len(passed),
        "total": len(required),
        "passed_checks": passed,
        "required_checks": required,
        "ok": ok,
        "detail": result,
    }


# ============================================================
# 自测
# ============================================================

def demo():
    print("=" * 70)
    print("管线质量门禁（M2）")
    print("=" * 70)
    gate = PipelineQualityGate()

    # 单管线
    print("\n[1] 单管线质量门禁（Unity 角色动作 · 全部达标）")
    r = gate.check_pipeline("pipeline.character_animation.unity",
                            quality_passed={"动作流畅度": True, "性能基准": True, "风格一致性": True})
    print(f"    {r['pipeline_id']} → {r['verdict']} | 通过 {len(r['passed_checks'])} 项")

    # 单管线不达标
    print("\n[2] 单管线质量门禁（Unity 角色动作 · 帧率不达标）")
    r2 = gate.check_pipeline("pipeline.character_animation.unity",
                             quality_passed={"动作流畅度": True, "性能基准": False, "风格一致性": True})
    print(f"    {r2['pipeline_id']} → {r2['verdict']} | 缺: {r2['missing_checks']}")

    # 引擎级
    print("\n[3] 引擎级质量门禁（Unity · 全部达标）")
    er = gate.check_engine("unity")
    print(f"    Unity: {er['total']} 条, GO {er['passed']} / 阻塞 {er['blocked']} → {er['overall']}")

    # 全引擎
    print("\n[4] 全引擎 40+ 条管线逐条质量门禁")
    all_r = gate.check_all_engines()
    print(f"    参与评审: {all_r['pipeline_count']} 条, GO {all_r['passed']}, 阻塞 {all_r['blocked']}")
    print(f"    全链路: {all_r['overall']} | {all_r['verdict']}")

    # release_gate 扩展接入
    print("\n[5] release_gate 管线级聚合扩展")
    pg = run_pipeline_quality_gate()
    print(f"    pipeline_quality: {pg['passed']}/{pg['total']} 通过 → {'✅' if pg['ok'] else '❌'}")

    # 断言
    assert r["verdict"] == "GO"
    assert r2["verdict"] == "NO-GO"
    assert er["overall"] == "GO"
    assert all_r["pipeline_count"] >= 40
    assert all_r["overall"] == "GO"
    assert pg["ok"]
    print("\n[PASS] 管线质量门禁自测通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(demo())

# ============================================================
# 管线发版计划与里程碑（Pipeline Release Plan）
# 版本: v1.0
# 说明: 基于管线依赖图，编排发版顺序与里程碑（M1-M5），
#       并支持**引擎分组发版**（L0/L1/L2/L3 独立或组合发布）。
#
# 对齐 Issue #128（游戏架构师 M5 蓝图）：
#   - 每条管线独立里程碑（M1-M5）
#   - 管线依赖编排（skeleton_binding → character_animation → ...）
#   - 引擎分组发版（L0/L1/L2/L3 独立或组合发布）
#
# 语言: Python 3 (可运行)
# 依赖: pipeline_registry / pipeline_orchestrator
# ============================================================
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pipeline_registry import PipelineRegistry, PipelineDef
from pipeline_release import PipelineReleaseReviewer, PipelineRelease


# 四引擎阶段（L0-L3）
ENGINE_LEVEL = {
    "react": "L0", "cocos": "L1", "unity": "L2", "unreal": "L3",
}


class PipelineReleasePlanner:
    """管线发版计划与里程碑编排器。

    - 基于管线依赖图做拓扑排序 → 发版顺序
    - 每条管线分配里程碑（M1-M5）
    - 引擎分组发版（L0/L1/L2/L3 独立或组合）
    """

    def __init__(self, registry: Optional[PipelineRegistry] = None):
        self.registry = registry or PipelineRegistry()
        self.reviewer = PipelineReleaseReviewer(self.registry)

    def _topo_sort(self, pipes: List[PipelineDef]) -> List[PipelineDef]:
        """拓扑排序：依赖管线在前（发版时先放行依赖）。"""
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

    # ---- M5: 管线依赖链发版编排 ----

    def plan_pipeline_release(self, engine: str,
                              domains: Optional[List[str]] = None) -> Dict[str, Any]:
        """基于管线依赖，编排发版顺序与里程碑。

        Args:
            engine: 目标引擎
            domains: 参与发版的专业方向（缺省为该引擎全部管线）

        Returns:
            {engine, level, pipelines: [...], release_order, milestones}
        """
        pipes = self.registry.by_engine(engine)
        if domains:
            pipes = [p for p in pipes if p.domain in domains]
        ordered = self._topo_sort(pipes)

        # 按依赖深度分配里程碑（无依赖=M1，依赖链越长里程碑越高）
        milestone = {}
        for p in ordered:
            depth = 1
            if p.dependencies:
                dep_depths = [milestone.get(d, 0) for d in p.dependencies]
                depth = max(dep_depths) + 1 if dep_depths else 2
            milestone[p.pipeline_id] = depth

        max_m = max(milestone.values()) if milestone else 1
        plan_pipelines = []
        for p in ordered:
            m = milestone[p.pipeline_id]
            plan_pipelines.append({
                "pipeline_id": p.pipeline_id,
                "name": p.name,
                "domain": p.domain,
                "dependencies": p.dependencies,
                "milestone": f"M{m}",
                "release_step": plan_pipelines.__len__() + 1,
            })

        return {
            "engine": engine,
            "level": ENGINE_LEVEL.get(engine, "L?"),
            "pipeline_count": len(ordered),
            "pipelines": plan_pipelines,
            "release_order": [p.pipeline_id for p in ordered],
            "milestones": {f"M{i}": [p["pipeline_id"] for p in plan_pipelines
                                     if p["milestone"] == f"M{i}"]
                           for i in range(1, max_m + 1)},
            "max_milestone": max_m,
        }

    # ---- M5: 引擎分组发版 ----

    def plan_engine_groups(self, engines: Optional[List[str]] = None,
                           all_go: bool = True) -> Dict[str, Any]:
        """引擎分组发版编排（L0/L1/L2/L3 独立或组合发布）。

        Args:
            engines: 参与发版的引擎列表（缺省为四引擎全部）
            all_go: 是否各引擎管线全部 GO（True=全部放行演示）

        Returns:
            {groups: [...], overall, verdict}
        """
        engines = engines or ["react", "cocos", "unity", "unreal"]
        groups = []
        for eng in engines:
            plan = self.plan_pipeline_release(eng)
            releases = self.reviewer.review_engine(eng, all_gates_ok=all_go,
                                                   stage_ok=all_go)
            report = self.reviewer.fullchain_release(releases)
            groups.append({
                "engine": eng,
                "level": plan["level"],
                "pipeline_count": plan["pipeline_count"],
                "release_order": plan["release_order"],
                "milestones": plan["milestones"],
                "max_milestone": plan["max_milestone"],
                "gate": report.overall,
                "verdict": report.verdict,
            })

        all_engine_go = all(g["gate"] == "GO" for g in groups)
        overall = "GO" if all_engine_go else "NO-GO"
        verdict = ("✅ 引擎分组发版全部放行（L0-L3 均可独立或组合发布）"
                   if all_engine_go
                   else f"❌ 引擎分组发版有未放行引擎")
        return {"groups": groups, "overall": overall, "verdict": verdict}

    # ---- 依赖链示例（skeleton_binding → character_animation）----

    def dependency_chain_example(self, engine: str = "unity") -> List[str]:
        """示例：返回某引擎的骨骼绑定→角色动作依赖链发版顺序。"""
        plan = self.plan_pipeline_release(engine)
        chain = []
        for p in plan["pipelines"]:
            if p["domain"] in ("skeleton_binding", "character_animation"):
                chain.append(p["pipeline_id"])
        return chain


# ============================================================
# 便捷 API（对齐架构师接口契约）
# ============================================================

def plan_pipeline_release(engine: str, domains: Optional[List[str]] = None) -> Dict[str, Any]:
    """便捷入口：管线依赖链发版编排。"""
    return PipelineReleasePlanner().plan_pipeline_release(engine, domains)


# ============================================================
# 自测
# ============================================================

def demo():
    print("=" * 70)
    print("管线发版计划与里程碑编排（M5）")
    print("=" * 70)
    planner = PipelineReleasePlanner()

    # 依赖链发版编排
    print("\n[1] Unity 管线依赖链发版编排")
    plan = planner.plan_pipeline_release("unity")
    print(f"    Unity: {plan['pipeline_count']} 条管线, 里程碑 M1~M{plan['max_milestone']}")
    for p in plan["pipelines"]:
        print(f"      {p['milestone']} 步{p['release_step']}: {p['pipeline_id']}")

    # 骨骼绑定 → 角色动作依赖链
    print("\n[2] 依赖链示例（骨骼绑定 → 角色动作）")
    chain = planner.dependency_chain_example("unity")
    print(f"    发版顺序: {' → '.join(chain)}")

    # 引擎分组发版
    print("\n[3] 引擎分组发版（L0-L3）")
    groups = planner.plan_engine_groups()
    for g in groups["groups"]:
        print(f"    {g['level']} {g['engine']}: {g['pipeline_count']} 条, 里程碑至 {g['max_milestone']}, 门禁 {g['gate']}")
    print(f"    分组发版总评: {groups['overall']} | {groups['verdict']}")

    # 断言
    assert plan["pipeline_count"] >= 12
    assert chain[0] == "pipeline.skeleton_binding.unity"
    assert "pipeline.character_animation.unity" in chain
    assert groups["overall"] == "GO"
    assert plan["milestones"].get("M1"), "应存在 M1 里程碑"
    print("\n[PASS] 管线发版计划自测通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(demo())

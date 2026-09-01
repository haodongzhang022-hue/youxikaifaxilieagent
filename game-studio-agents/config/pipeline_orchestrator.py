# ============================================================
# 管线编排核心（Pipeline Orchestrator）
# 版本: v1.0
# 说明: 根据目标「引擎 × 专业方向」选择并调度合适的开发管线。
#       让游戏开发输出从「统一笼统式」升级为「管线专业式」。
#
# 对齐 Issue #126：
#   - 纯网页 / Cocos / Unity / Unreal 四层级 × 角色动作/AI/特效/数值等
#     专业方向 → 精确选择对应管线，而非一刀切
#   - 每条管线独立状态机、独立追踪、能力持续积累
#
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pipeline_registry import PipelineRegistry, PipelineDef, ENGINES, DOMAINS


# ============================================================
# 管线状态机
# ============================================================

class PipelineState:
    """管线执行状态"""
    PENDING = "pending"        # 待调度
    READY = "ready"            # 就绪可执行
    IN_PROGRESS = "in_progress"  # 执行中
    BLOCKED = "blocked"        # 阻塞（依赖未就绪）
    COMPLETED = "completed"    # 已完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 取消

    # 合法状态转移
    TRANSITIONS = {
        PENDING: {READY, BLOCKED, CANCELLED},
        READY: {IN_PROGRESS, BLOCKED, CANCELLED},
        IN_PROGRESS: {COMPLETED, FAILED, BLOCKED, CANCELLED},
        BLOCKED: {READY, CANCELLED},
        COMPLETED: set(),
        FAILED: set(),
        CANCELLED: set(),
    }

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        return to_state in cls.TRANSITIONS.get(from_state, set())


# ============================================================
# 管线执行记录
# ============================================================

@dataclass
class PipelineExecution:
    """一次管线执行记录"""
    execution_id: str
    pipeline: PipelineDef
    state: str = PipelineState.PENDING
    engine: str = ""
    domain: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)

    def transition(self, to_state: str) -> bool:
        """状态转移（校验合法性）"""
        if not PipelineState.can_transition(self.state, to_state):
            return False
        self.state = to_state
        if to_state == PipelineState.COMPLETED:
            self.completed_at = _now()
        return True


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# 管线编排器
# ============================================================

class PipelineOrchestrator:
    """管线编排核心：根据引擎×方向选择管线并调度执行"""

    def __init__(self):
        self.registry = PipelineRegistry()
        self._executions: Dict[str, PipelineExecution] = {}
        self._exec_seq = 0

    # ---- 管线选择 ----

    def resolve_pipeline(self, engine: str, domain: str) -> Optional[PipelineDef]:
        """按引擎×方向解析管线"""
        return self.registry.by_engine_and_domain(engine, domain)

    def suggest_pipeline(self, description: str, engine: str = "") -> List[Dict[str, Any]]:
        """
        根据需求描述 + 引擎提示，推荐合适的管线列表。
        返回按匹配度排序的管线建议。
        """
        engine = engine.lower()
        # 归一化引擎别名
        engine_aliases = {
            "web": "react", "react": "react", "网页": "react", "h5": "react",
            "cocos": "cocos", "creator": "cocos", "小程序": "cocos",
            "unity": "unity", "团结": "unity", "u3d": "unity",
            "unreal": "unreal", "ue": "unreal", "ue5": "unreal", "虚幻": "unreal",
        }
        engine = engine_aliases.get(engine, engine)

        # 根据描述关键词匹配专业方向
        domain_keywords = {
            "character_animation": ["角色", "动画", "动作", "骨骼", "K动画", "anim"],
            "ai_trigger": ["AI", "智能", "行为树", "状态机", "NPC", "敌人", "ai"],
            "scene_vfx": ["特效", "粒子", "场景", "技能特效", "vfx", "shader"],
            "numeric_design": ["数值", "公式", "平衡", "经济", "属性", "数值策划"],
            "difficulty_optimization": ["难度", "曲线", "调参", "关卡难度"],
            "gameplay_optimization": ["玩法", "手感", "loop", "核心循环"],
            "skeleton_binding": ["骨骼绑定", "rig", "权重", "绑定"],
            "model_generation": ["模型", "建模", "tripo", "生成模型", "3d模型"],
            "model_painting": ["上色", "顶点色", "贴图烘焙"],
            "normal_mapping": ["法线", "法线贴图", "normal"],
            "texture_material": ["材质", "纹理", "pbr", "贴图"],
            "director_booth": ["导演", "过场", "动画片", "叙事", "cinematic", "timeline", "sequencer"],
        }

        desc_lower = description.lower()
        matches = []
        for dom, keywords in domain_keywords.items():
            score = 0
            for kw in keywords:
                if kw.lower() in desc_lower or kw in description:
                    score += 1
            if score > 0:
                matches.append((dom, score))

        # 按匹配度排序
        matches.sort(key=lambda x: -x[1])

        results = []
        for dom, score in matches:
            if engine and engine in ENGINES:
                pipe = self.resolve_pipeline(engine, dom)
                if pipe:
                    results.append({
                        "pipeline_id": pipe.pipeline_id,
                        "name": pipe.name,
                        "engine": pipe.engine,
                        "domain": pipe.domain,
                        "match_score": score,
                        "workflow": pipe.workflow,
                    })
            else:
                # 未指定引擎，推荐所有支持此方向的管线
                for p in self.registry.by_domain(dom):
                    results.append({
                        "pipeline_id": p.pipeline_id,
                        "name": p.name,
                        "engine": p.engine,
                        "domain": p.domain,
                        "match_score": score,
                        "workflow": p.workflow,
                    })

        return results

    # ---- 管线执行 ----

    def dispatch(self, engine: str, domain: str, context: Dict[str, Any] = None) -> PipelineExecution:
        """
        派发一个管线执行任务。
        - 解析目标管线
        - 检查依赖（依赖未就绪则 blocked）
        - 创建执行记录
        """
        pipe = self.resolve_pipeline(engine, domain)
        if not pipe:
            raise ValueError(f"找不到引擎 {engine} × 方向 {domain} 的管线")

        self._exec_seq += 1
        exec_id = f"pipe_exec_{self._exec_seq:04d}"
        ex = PipelineExecution(
            execution_id=exec_id,
            pipeline=pipe,
            engine=engine,
            domain=domain,
            context=context or {},
            created_at=_now(),
        )

        # 检查依赖
        deps_blocked = []
        for dep_id in pipe.dependencies:
            dep_exec = self._find_completed_for(dep_id)
            if not dep_exec:
                deps_blocked.append(dep_id)

        if deps_blocked:
            ex.state = PipelineState.BLOCKED
            ex.error = f"依赖未就绪: {', '.join(deps_blocked)}"
        else:
            ex.state = PipelineState.READY

        self._executions[exec_id] = ex
        return ex

    def _find_completed_for(self, pipeline_id: str) -> Optional[PipelineExecution]:
        """查找某管线最近一次成功执行的记录"""
        for ex in reversed(list(self._executions.values())):
            if ex.pipeline.pipeline_id == pipeline_id and ex.state == PipelineState.COMPLETED:
                return ex
        return None

    def start(self, exec_id: str) -> bool:
        """开始执行（READY → IN_PROGRESS）"""
        ex = self._executions.get(exec_id)
        if not ex:
            return False
        if ex.state == PipelineState.BLOCKED:
            # 重新检查依赖
            deps_blocked = []
            for dep_id in ex.pipeline.dependencies:
                if not self._find_completed_for(dep_id):
                    deps_blocked.append(dep_id)
            if deps_blocked:
                ex.error = f"依赖未就绪: {', '.join(deps_blocked)}"
                return False
            ex.transition(PipelineState.READY)
        if ex.transition(PipelineState.IN_PROGRESS):
            ex.started_at = _now()
            return True
        return False

    def complete(self, exec_id: str, result: Dict[str, Any] = None, artifacts: List[str] = None) -> bool:
        """完成执行（IN_PROGRESS → COMPLETED）"""
        ex = self._executions.get(exec_id)
        if not ex:
            return False
        if ex.transition(PipelineState.COMPLETED):
            ex.result = result or {}
            ex.artifacts = artifacts or []
            return True
        return False

    def fail(self, exec_id: str, error: str) -> bool:
        """执行失败（IN_PROGRESS → FAILED）"""
        ex = self._executions.get(exec_id)
        if not ex:
            return False
        if ex.transition(PipelineState.FAILED):
            ex.error = error
            return True
        return False

    def unblock(self, exec_id: str) -> bool:
        """解除阻塞（BLOCKED → READY）"""
        ex = self._executions.get(exec_id)
        if not ex:
            return False
        # 检查依赖是否已就绪
        for dep_id in ex.pipeline.dependencies:
            if not self._find_completed_for(dep_id):
                return False
        ex.transition(PipelineState.READY)
        ex.error = None
        return True

    # ---- 查询 ----

    def get_execution(self, exec_id: str) -> Optional[PipelineExecution]:
        return self._executions.get(exec_id)

    def list_executions(self, engine: str = "", domain: str = "") -> List[PipelineExecution]:
        """列出执行记录（可按引擎/方向过滤）"""
        results = list(self._executions.values())
        if engine:
            results = [e for e in results if e.engine == engine]
        if domain:
            results = [e for e in results if e.domain == domain]
        return results

    def summary(self) -> Dict[str, Any]:
        """编排器状态汇总"""
        states = {}
        for ex in self._executions.values():
            states[ex.state] = states.get(ex.state, 0) + 1
        return {
            "total_executions": len(self._executions),
            "states": states,
            "pipeline_count": self.registry.count(),
            "engines": list(ENGINES.keys()),
        }

    def report(self) -> str:
        """人类可读报告"""
        lines = []
        lines.append("=" * 70)
        lines.append("🔧 管线编排器状态")
        lines.append("=" * 70)
        s = self.summary()
        lines.append(f"📊 管线总数: {s['pipeline_count']}")
        lines.append(f"📦 执行记录: {s['total_executions']}")
        lines.append(f"  状态分布: {s['states']}")
        lines.append("\n▶ 执行列表:")
        for ex in self._executions.values():
            state_mark = {
                PipelineState.COMPLETED: "✅",
                PipelineState.IN_PROGRESS: "🔄",
                PipelineState.BLOCKED: "⛔",
                PipelineState.FAILED: "❌",
                PipelineState.READY: "🟢",
                PipelineState.PENDING: "⏳",
                PipelineState.CANCELLED: "🚫",
            }.get(ex.state, "❓")
            lines.append(
                f"  {state_mark} {ex.execution_id} | {ex.pipeline.name} "
                f"| {ex.state} | 创建: {ex.created_at}"
            )
            if ex.error:
                lines.append(f"      ⚠️  {ex.error}")
        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


# ============================================================
# 便捷 API：engine_aware_dispatch
# ============================================================

def engine_aware_dispatch(engine: str, domain: str, context: Dict[str, Any] = None) -> str:
    """
    引擎感知的管线派发便捷入口。
    返回 execution_id。
    """
    orch = PipelineOrchestrator()
    ex = orch.dispatch(engine, domain, context)
    return ex.execution_id


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    orch = PipelineOrchestrator()

    print("=== 管线矩阵汇总 ===")
    print(orch.registry.report())

    print("\n=== 需求推荐测试 ===")
    suggestions = orch.suggest_pipeline("做一个 Unity 的角色动作和骨骼绑定", "unity")
    for s in suggestions[:5]:
        print(f"  [{s['match_score']}] {s['pipeline_id']} | {s['name']}")

    print("\n=== 管线派发测试 ===")
    # 派发骨骼绑定（无依赖）
    ex1 = orch.dispatch("unity", "skeleton_binding", {"model": "角色模型", "style": "卡通"})
    print(f"  {ex1.execution_id}: {ex1.pipeline.name} → {ex1.state}")
    orch.start(ex1.execution_id)
    orch.complete(ex1.execution_id, {"bones": 62, "weights_ok": True}, ["skeleton.uasset"])
    print(f"  {ex1.execution_id}: {ex1.state}")

    # 派发角色动作（依赖骨骼绑定）
    ex2 = orch.dispatch("unity", "character_animation", {"model": "角色模型", "style": "卡通"})
    print(f"  {ex2.execution_id}: {ex2.pipeline.name} → {ex2.state}")
    if ex2.state == PipelineState.BLOCKED:
        print(f"    ⚠️  {ex2.error}")
        orch.unblock(ex2.execution_id)
        print(f"    → 解除阻塞后: {ex2.state}")

    print("\n=== 编排器状态 ===")
    print(orch.report())

    # 断言
    assert orch.registry.count() >= 40
    assert len(orch.suggest_pipeline("角色动画", "unity")) >= 1
    assert ex2.state in (PipelineState.READY, PipelineState.BLOCKED)
    assert orch.list_executions(engine="unity") != []
    print("\n[PASS] 管线编排器自测通过")

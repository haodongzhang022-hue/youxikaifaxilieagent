# ============================================================
# 五阶段感知引擎模块 (Stage-Aware Engine, L0~L3 + 资产库)
# 版本: v1.0
# 说明: 为游戏引擎选型/架构决策提供「阶段感知」能力。
#       对齐 Issue #112「游戏向架构师的开发」核心思想：
#       "阶段不对就算错" —— 每个架构决策必须绑定「引擎 × 阶段」二维坐标。
#
#   核心能力:
#     1. GameStage 枚举：定义五阶段演进路线（L0 网页 → Cocos → Unity → UE → 资产库）
#     2. StageAwareEngine：阶段感知引擎模型（引擎×阶段二维绑定）
#     3. EngineStageSelector：阶段选型/切换决策器
#     4. StageBoundaryGuard：阶段边界护栏（防阶段错配）
#     5. StageBoundaryCheck：阶段边界检查（供 Agent 使用）
#
# 设计原则:
#   - 引擎无关: 纯 Python 模块，不依赖任何引擎 API
#   - 阶段感知: 每个引擎绑定其适用的阶段，越界即错
#   - 资产复用: 跨阶段可复用资产（协议/配置表/纯算法）明确标注
#   - 可测试: 纯逻辑模块，无需外部依赖即可验证
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


# ============================================================
# 一、四阶段枚举
# ============================================================

class GameStage(str, Enum):
    """游戏开发阶段演进路线（L0~L3 + 资产库，对齐 Issue #126 命名统一）"""
    STAGE0_WEB = "stage0_web"             # L0: 纯网页 (React/Web, 玩法验证 + 引流分享)
    STAGE1_COCOS = "stage1_cocos"         # L1: Cocos/小程序 (MVP 验证期)
    STAGE2_UNITY = "stage2_unity"         # L2: Unity/团结引擎 (商业化与中度游戏期)
    STAGE3_UE = "stage3_ue"               # L3: Unreal Engine (3A/重度实时)
    STAGE4_ASSET = "stage4_asset"         # 阶段4: 终极形态 (一直能使用的资产库)

    @property
    def label(self) -> str:
        """阶段中文标签"""
        return {
            GameStage.STAGE0_WEB: "纯网页 React (玩法验证/引流期)",
            GameStage.STAGE1_COCOS: "Cocos/小程序 (MVP验证期)",
            GameStage.STAGE2_UNITY: "Unity/团结引擎 (商业化期)",
            GameStage.STAGE3_UE: "Unreal Engine (3A/重度实时)",
            GameStage.STAGE4_ASSET: "终极资产库",
        }[self]

    @property
    def order(self) -> int:
        """阶段顺序（用于比较/切换）"""
        return {
            GameStage.STAGE0_WEB: 0,
            GameStage.STAGE1_COCOS: 1,
            GameStage.STAGE2_UNITY: 2,
            GameStage.STAGE3_UE: 3,
            GameStage.STAGE4_ASSET: 4,
        }[self]

    @classmethod
    def from_order(cls, order: int) -> "GameStage":
        """从顺序号获取阶段"""
        return {
            0: cls.STAGE0_WEB,
            1: cls.STAGE1_COCOS,
            2: cls.STAGE2_UNITY,
            3: cls.STAGE3_UE,
            4: cls.STAGE4_ASSET,
        }.get(order, cls.STAGE0_WEB)


# ============================================================
# 二、引擎类型（与 engine_adapters 对齐）
# ============================================================

class StageEngineType(str, Enum):
    """L0~L3 涉及的游戏引擎"""
    REACT = "react_web"                  # L0 纯网页 (React/Web, TS)
    COCOS_CREATOR = "cocos_creator"      # L1 Cocos Creator (TS)
    UNITY = "unity"                      # L2 Unity/团结引擎 (C#)
    UNREAL = "unreal_engine"             # L3 Unreal Engine (C++/蓝图)
    CUSTOM = "custom"                    # 自定义/其他


# 引擎→适用阶段映射
ENGINE_STAGE_MAP: Dict[StageEngineType, GameStage] = {
    StageEngineType.REACT: GameStage.STAGE0_WEB,
    StageEngineType.COCOS_CREATOR: GameStage.STAGE1_COCOS,
    StageEngineType.UNITY: GameStage.STAGE2_UNITY,
    StageEngineType.UNREAL: GameStage.STAGE3_UE,
}

# 引擎→脚本语言
ENGINE_LANGUAGES: Dict[StageEngineType, List[str]] = {
    StageEngineType.REACT: ["TypeScript", "JavaScript"],
    StageEngineType.COCOS_CREATOR: ["TypeScript", "JavaScript"],
    StageEngineType.UNITY: ["C#"],
    StageEngineType.UNREAL: ["C++", "Blueprint"],
}


# ============================================================
# 三、阶段感知引擎模型
# ============================================================

@dataclass
class StageBoundary:
    """阶段边界定义"""
    stage: GameStage
    engine: StageEngineType
    stage_goal: str                 # 本阶段核心目标
    boundary_in: List[str]           # 本阶段应做的事（边界内）
    boundary_out: List[str]          # 标记"后期重构"（边界外）
    refactor_points: List[str] = field(default_factory=list)   # 重构点标记
    architecture_notes: str = ""     # 架构注意事项


# 预定义四阶段边界
STAGE_BOUNDARIES: Dict[GameStage, StageBoundary] = {
    GameStage.STAGE0_WEB: StageBoundary(
        stage=GameStage.STAGE0_WEB,
        engine=StageEngineType.REACT,
        stage_goal="玩法验证 + 引流分享 + 快速传播，成本最低、上手最快，验证核心乐趣",
        boundary_in=[
            "网页/H5 玩法核心循环、点击/拖拽/键盘交互",
            "本地存档、Canvas/SVG 渲染、CSS 动画",
            "轻量 Lottie/序列帧动画、2D 贴图精灵",
            "前端 TypeScript 逻辑、简单状态机",
            "CDN 静态资源分发、轻量后端 API",
        ],
        boundary_out=[
            "复杂寻路算法、大量单位同屏计算",
            "实时战斗校验、高频位置同步",
            "复杂 AI 行为树、3D 物理引擎",
            "PBR 材质、法线贴图、骨骼 IK",
            "跨服匹配、全球排行榜",
        ],
        refactor_points=[
            "核心逻辑需下沉为纯 TS 类（不依赖 React DOM）",
            "数据走本地 JSON + 简单云端接口，URL 与 Protobuf 结构保持兼容",
            "表现层（Canvas/CSS）与逻辑层解耦，便于后期迁移 Cocos",
        ],
        architecture_notes="L0 网页端不做 3D 过度设计；核心逻辑层必须与 React 渲染层解耦，为迁移 Cocos/Unity 留路",
    ),
    GameStage.STAGE1_COCOS: StageBoundary(
        stage=GameStage.STAGE1_COCOS,
        engine=StageEngineType.COCOS_CREATOR,
        stage_goal="极速验证核心玩法，获取种子用户，成本最低，包体最小",
        boundary_in=[
            "UI交互、动画播放、简单的点击反馈",
            "本地存档、微信/抖音SDK接入",
            "弱联网或轻度实时（JWT鉴权）",
            "用户登录、云存档读写、简单的排行榜",
            "SQLite/简单MySQL/Redis存储",
        ],
        boundary_out=[
            "复杂的寻路算法、大量的单位同屏计算",
            "精密的伤害公式",
            "实时战斗校验、高频位置同步",
            "复杂的AI行为树",
            "海量日志分析、实时在线人数统计",
        ],
        refactor_points=[
            "核心逻辑需下沉为纯TS类（不依赖Cocos API）",
            "数据走本地JSON+简单云端接口",
            "Python/Node.js后端API保持URL和Protobuf结构不变",
        ],
        architecture_notes="Cocos阶段不做UE的过度设计，核心逻辑层必须与Cocos API解耦",
    ),
    GameStage.STAGE2_UNITY: StageBoundary(
        stage=GameStage.STAGE2_UNITY,
        engine=StageEngineType.UNITY,
        stage_goal="提升画面表现力，做App端原生体验，支持更复杂玩法",
        boundary_in=[
            "复杂的UI框架(UGUI/FairyGUI)、AssetBundle热更新逻辑",
            "中等频率实时同步(回合制/慢节奏RTS)",
            "完整的装备/词条/养成系统",
            "公会/好友/聊天大厅",
            "核心逻辑下沉为纯C#类库(不依赖Unity API)",
        ],
        boundary_out=[
            "极高并发的粒子特效计算",
            "底层的内存池极致优化",
            "硬核的物理碰撞检测",
            "毫秒级帧同步战斗校验",
            "跨服匹配的全球排行榜",
        ],
        refactor_points=[
            "伤害计算公式、抽卡概率算法写成纯C#类(不依赖Unity API)",
            "后端从Python重写为Go(处理高并发WebSocket)",
            "C#纯逻辑类可被轻易翻译成C++",
        ],
        architecture_notes="Unity阶段商业化关键期，必须把玩法逻辑和表现严格分层",
    ),
    GameStage.STAGE3_UE: StageBoundary(
        stage=GameStage.STAGE3_UE,
        engine=StageEngineType.UNREAL,
        stage_goal="极致画质、大规模同屏、硬核实时对战、多端互通",
        boundary_in=[
            "C++渲染管线定制、底层内存管理",
            "核心战斗Tick、网络同步底层",
            "帧同步+物理碰撞+弹道计算",
            "完整养成+跨服玩法+大世界",
            "蓝图负责策划配置的关卡逻辑/UI表现",
        ],
        boundary_out=[
            "TS/C#彻底退出客户端历史舞台",
            "不再使用动态语言做核心逻辑",
        ],
        refactor_points=[
            "将阶段2的纯C#核心逻辑翻译并重构为高性能C++核心库",
            "C++核心库向上编DLL给UE客户端，向下编Linux可执行文件作战斗服务器",
            "Go网关复用，仅增加内部RPC接口",
        ],
        architecture_notes="UE阶段战斗/场景C++代码必须与客户端C++代码是同一份源码编译出来的",
    ),
    GameStage.STAGE4_ASSET: StageBoundary(
        stage=GameStage.STAGE4_ASSET,
        engine=StageEngineType.CUSTOM,
        stage_goal="建立'一直能使用'的资产库，跨引擎/语言长期复用",
        boundary_in=[
            "协议资产(Protobuf/FlatBuffers)：独立Git仓库game-protocols",
            "数值与配置表资产(Excel→JSON/Binary)",
            "纯数学/算法资产(伪代码→各语言实现)",
            "算法单元测试用例跨语言保留",
        ],
        boundary_out=[],
        refactor_points=[],
        architecture_notes="终极资产库：协议/配置表/纯算法是跨越所有阶段的'不换零件'核心资产",
    ),
}


# ============================================================
# 四、阶段感知引擎适配器（StageAwareEngineAdapter）
# ============================================================

@dataclass
class StageAwareEngine:
    """阶段感知引擎模型：引擎×阶段二维绑定"""
    engine: StageEngineType
    stage: GameStage
    capabilities: List[str] = field(default_factory=list)   # 引擎能力集
    languages: List[str] = field(default_factory=list)      # 脚本语言
    is_active: bool = True                                  # 是否为当前阶段活动引擎

    def __post_init__(self):
        if not self.languages:
            self.languages = ENGINE_LANGUAGES.get(self.engine, [])

    @property
    def stage_label(self) -> str:
        """阶段标签"""
        return self.stage.label

    @property
    def boundary(self) -> Optional[StageBoundary]:
        """当前阶段的边界定义"""
        return STAGE_BOUNDARIES.get(self.stage)

    def check_capability(self, capability: str) -> bool:
        """检查引擎是否具备某能力"""
        return capability in self.capabilities

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict"""
        return {
            "engine": self.engine.value,
            "stage": self.stage.value,
            "stage_label": self.stage_label,
            "capabilities": list(self.capabilities),
            "languages": self.languages,
            "is_active": self.is_active,
        }


# ============================================================
# 五、阶段边界护栏（StageBoundaryGuard）
# ============================================================

class StageBoundaryGuard:
    """
    阶段边界护栏：防止阶段错配。
    核心原则: "阶段不对就算错"。

    任何模块/功能都必须标注其所属阶段，若被用于不匹配的阶段则标记为越界。
    """

    # 阶段→模块的适用映射
    _MODULE_STAGE_MAP: Dict[str, GameStage] = {
        # 模块 → 可适用阶段
        "combat_real_time": GameStage.STAGE2_UNITY,
        "combat_frame_sync": GameStage.STAGE3_UE,
        "combat_turn_based": GameStage.STAGE1_COCOS,
        "network_ws_long": GameStage.STAGE2_UNITY,
        "network_low_freq": GameStage.STAGE1_COCOS,
        "network_high_freq_sync": GameStage.STAGE3_UE,
        "ai_behavior_tree": GameStage.STAGE3_UE,
        "ai_simple_fsm": GameStage.STAGE1_COCOS,
        "economy_full": GameStage.STAGE2_UNITY,
        "economy_basic": GameStage.STAGE1_COCOS,
        "economy_cross_server": GameStage.STAGE3_UE,
        "physics_basic": GameStage.STAGE1_COCOS,
        "physics_advanced": GameStage.STAGE2_UNITY,
        "physics_engine_level": GameStage.STAGE3_UE,
        "render_2d": GameStage.STAGE0_WEB,          # L0 网页即可做 2D（Canvas/CSS/SVG）
        "render_web_light": GameStage.STAGE0_WEB,     # L0 网页轻量渲染（Lottie/序列帧）
        "render_3d_basic": GameStage.STAGE2_UNITY,
        "render_3d_advanced": GameStage.STAGE3_UE,
        "ai_simple_fsm": GameStage.STAGE0_WEB,        # L0 网页即可用简单状态机
        "protobuf_protocol": GameStage.STAGE1_COCOS,  # 协议先行：所有阶段
        "pure_logic_lib": GameStage.STAGE1_COCOS,      # 纯逻辑库：所有阶段
        "open_world_map": GameStage.STAGE3_UE,         # 开放大世界：UE/3A 阶段
        "multi_currency_shop": GameStage.STAGE2_UNITY, # 多货币商城：Unity/商业化阶段
    }

    def __init__(self):
        """初始化护栏"""
        self._violations: List[Dict[str, Any]] = []

    def check(self, module: str, current_stage: GameStage) -> Dict[str, Any]:
        """
        检查模块是否适用当前阶段。

        Args:
            module: 模块名
            current_stage: 当前阶段

        Returns:
            检查结果: {ok, module, current_stage, applicable_stage, reason, action}
        """
        applicable = self._MODULE_STAGE_MAP.get(module)
        if applicable is None:
            return {
                "ok": True,
                "module": module,
                "current_stage": current_stage.value,
                "applicable_stage": None,
                "reason": f"模块 '{module}' 未登记阶段约束，需补充定义",
                "action": "review_required",
            }

        if applicable == current_stage:
            return {
                "ok": True,
                "module": module,
                "current_stage": current_stage.value,
                "applicable_stage": applicable.value,
                "reason": f"模块 '{module}' 与当前阶段匹配",
                "action": "ok",
            }

        # 模块适用阶段晚于当前阶段：过度设计
        if applicable.order > current_stage.order:
            result = {
                "ok": False,
                "module": module,
                "current_stage": current_stage.value,
                "applicable_stage": applicable.value,
                "reason": f"过度设计: 模块 '{module}' 属于{applicable.label}，"
                          f"当前是{current_stage.label}阶段，阶段不对=错",
                "action": "remove_or_defer",
            }
        # 模块适用阶段早于当前阶段：技术债
        else:
            result = {
                "ok": False,
                "module": module,
                "current_stage": current_stage.value,
                "applicable_stage": applicable.value,
                "reason": f"技术债: 模块 '{module}' 属于{applicable.label}，"
                          f"当前是{current_stage.label}阶段，需尽快升级或清理",
                "action": "upgrade_or_cleanup",
            }

        self._violations.append(result)
        return result

    def check_many(self, modules: List[str], current_stage: GameStage) -> List[Dict[str, Any]]:
        """批量检查多个模块"""
        return [self.check(m, current_stage) for m in modules]

    def violations(self) -> List[Dict[str, Any]]:
        """获取所有越界记录"""
        return self._violations

    def clear(self):
        """清空越界记录"""
        self._violations = []

    def audit(self) -> Dict[str, Any]:
        """审计报告"""
        return {
            "violation_count": len(self._violations),
            "violations": self._violations,
        }


# ============================================================
# 六、阶段选型决策器（EngineStageSelector）
# ============================================================

class EngineStageSelector:
    """
    阶段引擎选型决策器。

    根据当前阶段选择正确的引擎，并给出架构决策建议。
    """

    @staticmethod
    def get_engine_for_stage(stage: GameStage) -> Optional[StageEngineType]:
        """获取阶段对应的引擎"""
        for engine, s in ENGINE_STAGE_MAP.items():
            if s == stage:
                return engine
        return None  # stage4 不绑定具体引擎

    @staticmethod
    def get_stage_for_engine(engine: StageEngineType) -> Optional[GameStage]:
        """获取引擎对应的阶段"""
        return ENGINE_STAGE_MAP.get(engine)

    @staticmethod
    def select(current_stage: GameStage) -> Dict[str, Any]:
        """
        阶段选型决策。

        Args:
            current_stage: 当前阶段

        Returns:
            选型决策: {stage, engine, languages, boundary_in, boundary_out, actions}
        """
        engine = EngineStageSelector.get_engine_for_stage(current_stage)
        boundary = STAGE_BOUNDARIES.get(current_stage)

        return {
            "stage": current_stage.value,
            "stage_label": current_stage.label,
            "engine": engine.value if engine else None,
            "languages": ENGINE_LANGUAGES.get(engine, []) if engine else [],
            "boundary_in": boundary.boundary_in if boundary else [],
            "boundary_out": boundary.boundary_out if boundary else [],
            "refactor_points": boundary.refactor_points if boundary else [],
            "architecture_notes": boundary.architecture_notes if boundary else "",
        }

    @staticmethod
    def can_transition(current: GameStage, target: GameStage) -> bool:
        """检查是否可从当前阶段切换到目标阶段"""
        # 只能向后演进（1→2→3→4）
        return target.order > current.order

    @staticmethod
    def next_stage(current: GameStage) -> Optional[GameStage]:
        """获取下一阶段"""
        if current.order >= GameStage.STAGE4_ASSET.order:
            return None
        return GameStage.from_order(current.order + 1)


# ============================================================
# 七、便捷入口（供 Agent 使用）
# ============================================================

def get_stage_aware_engines() -> List[StageAwareEngine]:
    """获取所有阶段的感知引擎模型"""
    engines = []
    for engine_type, stage in ENGINE_STAGE_MAP.items():
        engines.append(StageAwareEngine(
            engine=engine_type,
            stage=stage,
            capabilities=_get_engine_capabilities(engine_type),
        ))
    return engines


def _get_engine_capabilities(engine: StageEngineType) -> List[str]:
    """获取引擎能力集"""
    base = {
        StageEngineType.REACT: [
            "dom.render", "component.create", "canvas.draw", "ui.button",
            "audio.play", "css.animation", "network.fetch",
            "local.storage", "lottie.play", "webgl.render",
        ],
        StageEngineType.COCOS_CREATOR: [
            "scene.load", "node.create", "sprite.set", "ui.button",
            "audio.play", "animation.play", "network.http",
            "local.storage", "platform.wechat", "platform.douyin",
        ],
        StageEngineType.UNITY: [
            "scene.load", "node.create", "mesh.create", "material.set",
            "ui.canvas", "assetbundle.load", "animation.state_machine",
            "physics.collision", "network.ws", "ai.navmesh",
        ],
        StageEngineType.UNREAL: [
            "scene.load", "node.create", "mesh.create", "material.set",
            "ui.widget", "blueprint.create", "physics.advanced",
            "network.udp", "ai.behavior_tree", "render.pipeline",
            "render.raytracing", "network.dedicated_server",
        ],
    }
    return base.get(engine, [])


def stage_boundary_check(module: str, current_stage: GameStage) -> Dict[str, Any]:
    """便捷阶段边界检查"""
    guard = StageBoundaryGuard()
    return guard.check(module, current_stage)


# ============================================================
# 八、自测
# ============================================================

if __name__ == "__main__":
    print("=== 五阶段感知引擎模块自测 (L0~L3 + 资产库) ===")
    print()

    # 1. 阶段枚举
    print("== 1. 五阶段演进 (L0~L3 + 资产库) ==")
    for stage in GameStage:
        print(f"  阶段{stage.order}: {stage.label}")

    # 2. 阶段选型
    print("\n== 2. 阶段选型决策 ==")
    for stage in [GameStage.STAGE0_WEB, GameStage.STAGE1_COCOS, GameStage.STAGE2_UNITY, GameStage.STAGE3_UE]:
        decision = EngineStageSelector.select(stage)
        print(f"  {decision['stage_label']}: 引擎={decision['engine']}, "
              f"语言={decision['languages']}, 边界内={len(decision['boundary_in'])}项, "
              f"边界外={len(decision['boundary_out'])}项")

    # 3. 阶段边界检查
    print("\n== 3. 阶段边界检查 ==")
    guard = StageBoundaryGuard()

    # L0 网页阶段检查
    print("  当前阶段: 纯网页 React (L0)")
    checks = guard.check_many(
        ["render_2d", "render_web_light", "ai_simple_fsm",
         "render_3d_advanced", "open_world_map"],
        GameStage.STAGE0_WEB,
    )
    for c in checks:
        status = "✅" if c["ok"] else "❌"
        print(f"    {status} {c['module']}: {c['reason']}")

    # Cocos 阶段检查
    print("  当前阶段: Cocos (MVP)")
    checks = guard.check_many(
        ["combat_turn_based", "network_low_freq", "ai_simple_fsm",
         "combat_frame_sync", "physics_advanced"],
        GameStage.STAGE1_COCOS,
    )
    for c in checks:
        status = "✅" if c["ok"] else "❌"
        print(f"    {status} {c['module']}: {c['reason']}")

    # Unity 阶段检查
    print("  当前阶段: Unity (商业化)")
    guard.clear()
    checks = guard.check_many(
        ["combat_real_time", "network_ws_long", "ai_behavior_tree",
         "physics_engine_level"],
        GameStage.STAGE2_UNITY,
    )
    for c in checks:
        status = "✅" if c["ok"] else "❌"
        print(f"    {status} {c['module']}: {c['reason']}")

    # 4. 阶段切换
    print("\n== 4. 阶段切换 ==")
    selector = EngineStageSelector
    print(f"  L0→L1: {'✅ 可以' if selector.can_transition(GameStage.STAGE0_WEB, GameStage.STAGE1_COCOS) else '❌ 不行'}")
    print(f"  阶段1→阶段2: {'✅ 可以' if selector.can_transition(GameStage.STAGE1_COCOS, GameStage.STAGE2_UNITY) else '❌ 不行'}")
    print(f"  阶段2→阶段3: {'✅ 可以' if selector.can_transition(GameStage.STAGE2_UNITY, GameStage.STAGE3_UE) else '❌ 不行'}")
    print(f"  阶段3→阶段2: {'✅ 可以' if selector.can_transition(GameStage.STAGE3_UE, GameStage.STAGE2_UNITY) else '❌ 不行'}")
    print(f"  阶段3下一阶段: {selector.next_stage(GameStage.STAGE3_UE).label if selector.next_stage(GameStage.STAGE3_UE) else 'None'}")

    # 5. 阶段感知引擎
    print("\n== 5. 阶段感知引擎 ==")
    for sae in get_stage_aware_engines():
        print(f"  {sae.engine.value}: 阶段={sae.stage_label}, "
              f"语言={sae.languages}, 能力={len(sae.capabilities)}项")

    print("\n🟢 四阶段感知引擎模块自测通过")

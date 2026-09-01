# ============================================================
# 引擎分层 × 专业方向 管线注册表（Pipeline Registry）
# 版本: v1.0
# 说明: 将游戏开发输出从「统一笼统式」升级为「引擎×专业管线矩阵式」。
#       每条管线独立注册、独立追踪、独立优化，能力持续积累。
#
# 对齐 Issue #126：纯网页/Cocos/Unity/UE 四层级 × 角色动作/AI/特效/数值等
# 专业方向 → 40+ 独立管线，替代当前一刀切式输出。
#
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ============================================================
# 数据模型
# ============================================================

@dataclass
class PipelineDef:
    """管线定义"""
    pipeline_id: str          # 如 "pipeline.character_animation.unity"
    name: str                 # 中文名
    engine: str               # "react" | "cocos" | "unity" | "unreal"
    domain: str               # 专业方向（见 DOMAINS）
    status: str = "active"    # active | deprecated | draft
    inputs: List[str] = field(default_factory=list)
    workflow: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    quality_gates: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    knowledge_base: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "name": self.name,
            "engine": self.engine,
            "domain": self.domain,
            "status": self.status,
            "inputs": self.inputs,
            "workflow": self.workflow,
            "outputs": self.outputs,
            "tools": self.tools,
            "quality_gates": self.quality_gates,
            "dependencies": self.dependencies,
            "knowledge_base": self.knowledge_base,
        }


# ============================================================
# 专业方向（DOMAINS）
# ============================================================

# 专业方向定义（引擎无关层，各引擎都有对应的管线实例）
DOMAINS = {
    "character_animation": {
        "name": "角色动作",
        "description": "角色动画/动作制作，含骨骼绑定、K动画、状态机集成",
        "engines": ["react", "cocos", "unity", "unreal"],
    },
    "ai_trigger": {
        "name": "AI触发器",
        "description": "NPC/敌人 AI 行为逻辑，含行为树、状态机、感知系统",
        "engines": ["react", "cocos", "unity", "unreal"],
    },
    "scene_vfx": {
        "name": "场景特效",
        "description": "技能/环境特效，含粒子系统、Shader、性能优化",
        "engines": ["react", "cocos", "unity", "unreal"],
    },
    "numeric_design": {
        "name": "数值策划",
        "description": "数值模型设计，含公式、参数调优、平衡验证",
        "engines": ["react", "cocos", "unity", "unreal"],
    },
    "difficulty_optimization": {
        "name": "难度优化",
        "description": "难度曲线设计，含数据驱动调参、动态难度",
        "engines": ["react", "cocos", "unity", "unreal"],
    },
    "gameplay_optimization": {
        "name": "玩法优化",
        "description": "核心玩法循环优化，含手感调优、留存验证",
        "engines": ["react", "cocos", "unity", "unreal"],
    },
    "skeleton_binding": {
        "name": "骨骼绑定",
        "description": "骨骼创建、权重分配、约束设置（3D引擎必需）",
        "engines": ["react", "cocos", "unity", "unreal"],
    },
    "model_generation": {
        "name": "模型生成",
        "description": "AI 模型生成（Tripo 等）+ 拓扑 + UV + 优化",
        "engines": ["unity", "unreal"],
    },
    "model_painting": {
        "name": "模型上色",
        "description": "顶点色、贴图烘焙、上色验证",
        "engines": ["unity", "unreal"],
    },
    "normal_mapping": {
        "name": "法线贴图",
        "description": "高模烘焙、法线提取、切线空间映射",
        "engines": ["unity", "unreal"],
    },
    "texture_material": {
        "name": "纹理材质",
        "description": "PBR 材质制作、纹理映射、渲染管线对接",
        "engines": ["unity", "unreal"],
    },
    "director_booth": {
        "name": "导演台",
        "description": "过场动画/叙事编排，含时间轴、镜头、灯光、音效",
        "engines": ["react", "cocos", "unity", "unreal"],
    },
}

# ============================================================
# 四层级引擎定义
# ============================================================

ENGINES = {
    "react": {
        "name": "L0 纯网页",
        "full_name": "React (Web/WASM)",
        "positioning": "玩法验证 + 引流分享 + 快速传播",
        "script_lang": "TypeScript",
        "pipeline_domains": [
            "character_animation", "ai_trigger", "scene_vfx",
            "numeric_design", "difficulty_optimization",
            "gameplay_optimization", "skeleton_binding",
            "director_booth",
        ],
    },
    "cocos": {
        "name": "L1 Cocos",
        "full_name": "Cocos Creator",
        "positioning": "小程序 + 轻量分享传播",
        "script_lang": "TypeScript",
        "pipeline_domains": [
            "character_animation", "ai_trigger", "scene_vfx",
            "numeric_design", "difficulty_optimization",
            "gameplay_optimization", "skeleton_binding",
            "director_booth",
        ],
    },
    "unity": {
        "name": "L2 Unity",
        "full_name": "Unity (团结引擎)",
        "positioning": "完整地图 + App 客户端",
        "script_lang": "C#",
        "pipeline_domains": [
            "character_animation", "ai_trigger", "scene_vfx",
            "numeric_design", "difficulty_optimization",
            "gameplay_optimization", "skeleton_binding",
            "model_generation", "model_painting", "normal_mapping",
            "texture_material", "director_booth",
        ],
    },
    "unreal": {
        "name": "L3 Unreal",
        "full_name": "Unreal Engine",
        "positioning": "高品质效果 + 护城河",
        "script_lang": "C++ / Blueprint",
        "pipeline_domains": [
            "character_animation", "ai_trigger", "scene_vfx",
            "numeric_design", "difficulty_optimization",
            "gameplay_optimization", "skeleton_binding",
            "model_generation", "model_painting", "normal_mapping",
            "texture_material", "director_booth",
        ],
    },
}

# ============================================================
# 管线注册表（Pipeline Registry）
# ============================================================

# 每条管线的输入/工作流/产出物/工具链/质量门禁
_PIPELINES: List[PipelineDef] = []


def _build_pipelines() -> List[PipelineDef]:
    """构建全部管线定义（40+ 条）"""
    pipes: List[PipelineDef] = []

    # --- L0 React ---
    pipes.append(PipelineDef(
        pipeline_id="pipeline.character_animation.react",
        name="React角色动画管线",
        engine="react", domain="character_animation",
        inputs=["角色设计稿", "风格规范"],
        workflow=["CSS动画设计", "Sprite序列制作", "Lottie集成", "交互绑定", "性能验证"],
        outputs=["CSS动画", "Sprite资源", "Lottie文件"],
        tools=["CSS Animations", "Lottie", "Framer Motion"],
        quality_gates=["动画流畅度≥60fps", "风格一致性", "包体≤2MB"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.ai_trigger.react",
        name="React AI触发器管线",
        engine="react", domain="ai_trigger",
        inputs=["AI行为设计", "战斗策划"],
        workflow=["状态机设计", "TS逻辑实现", "事件系统", "测试验证"],
        outputs=["TS AI模块"],
        tools=["XState", "Zustand"],
        quality_gates=["行为覆盖率≥80%", "可调试性"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.scene_vfx.react",
        name="React场景特效管线",
        engine="react", domain="scene_vfx",
        inputs=["特效需求", "世界观"],
        workflow=["Canvas绘制", "Shader编写", "粒子系统", "性能优化", "集成验证"],
        outputs=["Canvas特效", "WebGL Shader"],
        tools=["PixiJS", "Three.js", "WebGL"],
        quality_gates=["特效帧率≥55fps", "视觉质量"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.numeric_design.react",
        name="React数值策划管线",
        engine="react", domain="numeric_design",
        inputs=["数值模型", "玩法设计"],
        workflow=["公式定义", "参数调优", "平衡模拟", "数据验证"],
        outputs=["JSON数值表", "TS公式库"],
        tools=["纯TS公式库", "Monte Carlo模拟"],
        quality_gates=["数值平衡达标", "公式可调参"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.difficulty_optimization.react",
        name="React难度优化管线",
        engine="react", domain="difficulty_optimization",
        inputs=["用户数据", "关卡设计"],
        workflow=["数据分析", "难度曲线", "动态调整", "A/B验证"],
        outputs=["难度配置", "分析报告"],
        tools=["埋点", "数据分析看板"],
        quality_gates=["留存提升≥10%", "通过率合理"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.gameplay_optimization.react",
        name="React玩法优化管线",
        engine="react", domain="gameplay_optimization",
        inputs=["玩法反馈", "核心Loop"],
        workflow=["Loop分析", "手感调优", "Playtest", "留存验证"],
        outputs=["玩法迭代方案"],
        tools=["Playtest", "A/B测试"],
        quality_gates=["核心指标提升", "用户反馈正面"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.director_booth.react",
        name="React导演台管线",
        engine="react", domain="director_booth",
        inputs=["分镜脚本", "场景资源"],
        workflow=["时间轴设计", "轨道编排", "相机控制", "音效同步", "预览验证"],
        outputs=["Timeline配置", "过场动画"],
        tools=["自定义Timeline(Web)"],
        quality_gates=["过场流畅", "时间轴精准"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.skeleton_binding.react",
        name="React骨骼绑定管线",
        engine="react", domain="skeleton_binding",
        inputs=["2D角色图", "动画需求"],
        workflow=["2D骨骼创建", "权重分配", "动画测试"],
        outputs=["骨骼动画资源"],
        tools=["DragonBone JS", "Spine Web"],
        quality_gates=["骨骼正确", "动画流畅"],
    ))

    # --- L1 Cocos ---
    pipes.append(PipelineDef(
        pipeline_id="pipeline.character_animation.cocos",
        name="Cocos角色动画管线",
        engine="cocos", domain="character_animation",
        inputs=["概念图", "风格规范"],
        workflow=["2D骨骼创建", "Spine/DragonBone动作", "动画集成", "性能验证"],
        outputs=[".anim", ".prefab", "Spine资源"],
        tools=["Spine", "DragonBone", "Cocos Animation Editor"],
        quality_gates=["动画流畅度", "包体控制", "风格一致性"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.ai_trigger.cocos",
        name="Cocos AI触发器管线",
        engine="cocos", domain="ai_trigger",
        inputs=["AI行为设计", "战斗策划"],
        workflow=["行为树设计", "TS实现", "感知系统", "测试验证"],
        outputs=["TS AI模块"],
        tools=["自研行为树", "FSM"],
        quality_gates=["行为覆盖率", "帧率影响≤5%"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.scene_vfx.cocos",
        name="Cocos场景特效管线",
        engine="cocos", domain="scene_vfx",
        inputs=["特效需求", "世界观"],
        workflow=["粒子组件", "Shader", "性能优化", "集成验证"],
        outputs=[".plist特效", ".prefab"],
        tools=["Cocos Particle System"],
        quality_gates=["特效帧率", "包体控制"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.numeric_design.cocos",
        name="Cocos数值策划管线",
        engine="cocos", domain="numeric_design",
        inputs=["数值模型", "玩法设计"],
        workflow=["配置表设计", "JSON生成", "平衡验证"],
        outputs=["JSON配置表"],
        tools=["Excel导出", "数值公式库"],
        quality_gates=["数值平衡", "配置可读"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.difficulty_optimization.cocos",
        name="Cocos难度优化管线",
        engine="cocos", domain="difficulty_optimization",
        inputs=["用户数据", "关卡设计"],
        workflow=["动态难度", "参数调优", "验证"],
        outputs=["难度配置"],
        tools=["Cocos动态调参"],
        quality_gates=["通过率合理", "留存提升"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.gameplay_optimization.cocos",
        name="Cocos玩法优化管线",
        engine="cocos", domain="gameplay_optimization",
        inputs=["玩法反馈", "核心Loop"],
        workflow=["Loop分析", "手感调优", "验证"],
        outputs=["玩法迭代"],
        tools=["Playtest"],
        quality_gates=["核心指标提升"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.skeleton_binding.cocos",
        name="Cocos骨骼绑定管线",
        engine="cocos", domain="skeleton_binding",
        inputs=["模型/图集", "动画需求"],
        workflow=["骨骼创建", "权重分配", "动画测试"],
        outputs=[".skel", ".prefab"],
        tools=["Spine", "DragonBone"],
        quality_gates=["骨骼正确", "权重合理"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.director_booth.cocos",
        name="Cocos导演台管线",
        engine="cocos", domain="director_booth",
        inputs=["分镜脚本", "场景资源"],
        workflow=["时间轴", "轨道编排", "动画集成", "预览"],
        outputs=["动画配置", "过场"],
        tools=["Cocos Animation Editor"],
        quality_gates=["过场流畅", "时间精准"],
    ))

    # --- L2 Unity ---
    pipes.append(PipelineDef(
        pipeline_id="pipeline.character_animation.unity",
        name="Unity角色动作管线",
        engine="unity", domain="character_animation",
        inputs=["绑定模型", "动作需求", "风格规范"],
        workflow=["K动画", "Animation Clip", "状态机", "集成验证"],
        outputs=[".anim", ".controller"],
        tools=["Unity Animator", "Unity Timeline"],
        quality_gates=["动作流畅度", "性能基准", "风格一致性"],
        dependencies=["pipeline.skeleton_binding.unity"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.ai_trigger.unity",
        name="Unity AI触发器管线",
        engine="unity", domain="ai_trigger",
        inputs=["AI行为设计", "战斗策划"],
        workflow=["C#行为树", "NavMesh", "感知系统", "集成"],
        outputs=["C# AI模块"],
        tools=["Behavior Designer", "GOAP", "Unity NavMesh"],
        quality_gates=["行为覆盖率", "帧率影响"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.scene_vfx.unity",
        name="Unity场景特效管线",
        engine="unity", domain="scene_vfx",
        inputs=["特效需求", "世界观"],
        workflow=["Particle System", "Shader", "材质", "性能验证"],
        outputs=[".prefab特效"],
        tools=["Unity VFX Graph", "Particle System"],
        quality_gates=["特效帧率", "视觉质量"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.numeric_design.unity",
        name="Unity数值策划管线",
        engine="unity", domain="numeric_design",
        inputs=["数值模型", "玩法设计"],
        workflow=["ScriptableObject", "数据表", "平衡验证"],
        outputs=["SO配置资产"],
        tools=["Unity SO系统"],
        quality_gates=["数值平衡", "配置可热更新"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.difficulty_optimization.unity",
        name="Unity难度优化管线",
        engine="unity", domain="difficulty_optimization",
        inputs=["用户数据", "关卡设计"],
        workflow=["Difficulty Curve", "动态调整", "验证"],
        outputs=["难度曲线配置"],
        tools=["Animation Curve"],
        quality_gates=["通过率合理", "留存提升"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.gameplay_optimization.unity",
        name="Unity玩法优化管线",
        engine="unity", domain="gameplay_optimization",
        inputs=["玩法反馈", "核心Loop"],
        workflow=["Gameplay Loop", "Ability System", "调优"],
        outputs=["玩法迭代"],
        tools=["Unity GAS"],
        quality_gates=["核心指标提升"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.skeleton_binding.unity",
        name="Unity骨骼绑定管线",
        engine="unity", domain="skeleton_binding",
        inputs=["模型", "动画需求"],
        workflow=["Avatar Rig", "权重分配", "约束设置", "验证"],
        outputs=["Avatar配置"],
        tools=["Unity Rigging"],
        quality_gates=["骨骼正确", "权重合理", "无穿模"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.model_generation.unity",
        name="Unity模型生成管线",
        engine="unity", domain="model_generation",
        inputs=["概念图", "技术规范"],
        workflow=["Tripo生成", "拓扑", "UV", "优化"],
        outputs=[".fbx", ".glb模型"],
        tools=["Tripo", "Blender"],
        quality_gates=["面数达标", "拓扑正确", "UV无重叠"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.model_painting.unity",
        name="Unity模型上色管线",
        engine="unity", domain="model_painting",
        inputs=["模型", "风格规范"],
        workflow=["顶点色", "贴图烘焙", "上色验证"],
        outputs=["顶点色+贴图"],
        tools=["Substance Painter"],
        quality_gates=["颜色正确", "UV对齐"],
        dependencies=["pipeline.model_generation.unity"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.normal_mapping.unity",
        name="Unity法线贴图管线",
        engine="unity", domain="normal_mapping",
        inputs=["高模", "低模"],
        workflow=["高模烘焙", "法线提取", "映射验证"],
        outputs=["法线贴图"],
        tools=["Substance", "xNormal"],
        quality_gates=["法线正确", "无接缝"],
        dependencies=["pipeline.model_generation.unity"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.texture_material.unity",
        name="Unity纹理材质管线",
        engine="unity", domain="texture_material",
        inputs=["模型+贴图", "PBR规范"],
        workflow=["纹理制作", "材质球", "PBR参数", "验证"],
        outputs=["材质资产"],
        tools=["Standard Shader", "URP/HDRP"],
        quality_gates=["PBR参数正确", "渲染质量"],
        dependencies=["pipeline.model_painting.unity"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.director_booth.unity",
        name="Unity导演台管线",
        engine="unity", domain="director_booth",
        inputs=["分镜脚本", "场景+角色"],
        workflow=["Timeline", "轨道编排", "相机", "灯光", "合成"],
        outputs=["Timeline资产"],
        tools=["Unity Timeline"],
        quality_gates=["过场流畅", "镜头合理", "灯光到位"],
    ))

    # --- L3 Unreal ---
    pipes.append(PipelineDef(
        pipeline_id="pipeline.character_animation.unreal",
        name="UE角色动作管线",
        engine="unreal", domain="character_animation",
        inputs=["绑定模型", "动作需求", "风格规范"],
        workflow=["K动画", "Animation Sequence", "Blend Space", "集成"],
        outputs=[".uasset动画"],
        tools=["UE AnimSequence", "Blend Space"],
        quality_gates=["动作流畅度", "性能基准"],
        dependencies=["pipeline.skeleton_binding.unreal"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.ai_trigger.unreal",
        name="UE AI触发器管线",
        engine="unreal", domain="ai_trigger",
        inputs=["AI行为设计", "战斗策划"],
        workflow=["C++/BP行为树", "感知", "NavMesh", "集成"],
        outputs=["行为树资产"],
        tools=["UE Behavior Tree", "GAS"],
        quality_gates=["行为覆盖率", "帧率影响"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.scene_vfx.unreal",
        name="UE场景特效管线",
        engine="unreal", domain="scene_vfx",
        inputs=["特效需求", "世界观"],
        workflow=["Niagara", "Cascade", "材质", "验证"],
        outputs=[".uasset特效"],
        tools=["UE Niagara", "Cascade"],
        quality_gates=["特效帧率", "视觉质量"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.numeric_design.unreal",
        name="UE数值策划管线",
        engine="unreal", domain="numeric_design",
        inputs=["数值模型", "玩法设计"],
        workflow=["Data Table", "Curve", "平衡验证"],
        outputs=[".uasset数据表"],
        tools=["UE Data Table"],
        quality_gates=["数值平衡", "配置可热加载"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.difficulty_optimization.unreal",
        name="UE难度优化管线",
        engine="unreal", domain="difficulty_optimization",
        inputs=["用户数据", "关卡设计"],
        workflow=["Difficulty Curve", "动态调整", "验证"],
        outputs=["难度配置"],
        tools=["UE Curve"],
        quality_gates=["通过率合理"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.gameplay_optimization.unreal",
        name="UE玩法优化管线",
        engine="unreal", domain="gameplay_optimization",
        inputs=["玩法反馈", "核心Loop"],
        workflow=["GAS", "调优", "验证"],
        outputs=["玩法迭代"],
        tools=["UE Gameplay Ability System"],
        quality_gates=["核心指标提升"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.skeleton_binding.unreal",
        name="UE骨骼绑定管线",
        engine="unreal", domain="skeleton_binding",
        inputs=["模型", "动画需求"],
        workflow=["Skeletal Mesh", "Physics Asset", "约束"],
        outputs=["骨骼资产"],
        tools=["UE Rigging", "Physics Asset"],
        quality_gates=["骨骼正确", "物理正确"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.model_generation.unreal",
        name="UE模型生成管线",
        engine="unreal", domain="model_generation",
        inputs=["概念图", "技术规范"],
        workflow=["Tripo生成", "拓扑", "UV", "优化"],
        outputs=[".fbx模型"],
        tools=["Tripo", "Maya"],
        quality_gates=["面数达标", "拓扑正确"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.model_painting.unreal",
        name="UE模型上色管线",
        engine="unreal", domain="model_painting",
        inputs=["模型", "风格规范"],
        workflow=["Vertex Color", "贴图烘焙", "验证"],
        outputs=["贴图资源"],
        tools=["Substance Painter"],
        quality_gates=["颜色正确"],
        dependencies=["pipeline.model_generation.unreal"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.normal_mapping.unreal",
        name="UE法线贴图管线",
        engine="unreal", domain="normal_mapping",
        inputs=["高模", "低模"],
        workflow=["高模烘焙", "法线提取", "映射"],
        outputs=["法线贴图"],
        tools=["Substance", "xNormal"],
        quality_gates=["法线正确"],
        dependencies=["pipeline.model_generation.unreal"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.texture_material.unreal",
        name="UE纹理材质管线",
        engine="unreal", domain="texture_material",
        inputs=["模型+贴图", "PBR规范"],
        workflow=["Material Graph", "PBR参数", "LOD"],
        outputs=["材质资产"],
        tools=["UE Material Editor"],
        quality_gates=["PBR正确", "LOD达标"],
        dependencies=["pipeline.model_painting.unreal"],
    ))
    pipes.append(PipelineDef(
        pipeline_id="pipeline.director_booth.unreal",
        name="UE导演台管线",
        engine="unreal", domain="director_booth",
        inputs=["分镜脚本", "场景+角色"],
        workflow=["Sequencer", "相机", "灯光", "过场"],
        outputs=["Level Sequence"],
        tools=["UE Sequencer"],
        quality_gates=["过场电影级", "镜头合理"],
    ))

    return pipes


# ============================================================
# 管线注册表类
# ============================================================

class PipelineRegistry:
    """引擎分层 × 专业方向 管线注册表"""

    def __init__(self):
        self._pipelines: List[PipelineDef] = _build_pipelines()
        self._by_id = {p.pipeline_id: p for p in self._pipelines}
        self._by_engine: Dict[str, List[PipelineDef]] = {}
        self._by_domain: Dict[str, List[PipelineDef]] = {}
        self._rebuild_index()

    def _rebuild_index(self):
        self._by_engine = {}
        self._by_domain = {}
        for p in self._pipelines:
            self._by_engine.setdefault(p.engine, []).append(p)
            self._by_domain.setdefault(p.domain, []).append(p)

    # ---- 查询接口 ----

    def all(self) -> List[PipelineDef]:
        """全部管线"""
        return self._pipelines

    def count(self) -> int:
        return len(self._pipelines)

    def get(self, pipeline_id: str) -> Optional[PipelineDef]:
        """按 ID 查询管线"""
        return self._by_id.get(pipeline_id)

    def by_engine(self, engine: str) -> List[PipelineDef]:
        """按引擎查询管线"""
        return self._by_engine.get(engine, [])

    def by_domain(self, domain: str) -> List[PipelineDef]:
        """按专业方向查询管线"""
        return self._by_domain.get(domain, [])

    def by_engine_and_domain(self, engine: str, domain: str) -> Optional[PipelineDef]:
        """按引擎+方向查询管线"""
        pid = f"pipeline.{domain}.{engine}"
        return self._by_id.get(pid)

    def domains_for_engine(self, engine: str) -> List[str]:
        """某引擎支持的专业方向列表"""
        return [d for d, defn in DOMAINS.items() if engine in defn["engines"]]

    def engines_for_domain(self, domain: str) -> List[str]:
        """某专业方向支持的引擎列表"""
        return DOMAINS.get(domain, {}).get("engines", [])

    # ---- 统计与报告 ----

    def summary(self) -> Dict[str, Any]:
        """管线矩阵汇总"""
        engines = {}
        for eng_name, eng_def in ENGINES.items():
            pipes = self.by_engine(eng_name)
            engines[eng_name] = {
                "name": eng_def["name"],
                "positioning": eng_def["positioning"],
                "pipeline_count": len(pipes),
                "domains": [p.domain for p in pipes],
            }
        domains = {}
        for dom_name, dom_def in DOMAINS.items():
            pipes = self.by_domain(dom_name)
            domains[dom_name] = {
                "name": dom_def["name"],
                "pipeline_count": len(pipes),
                "engines": [p.engine for p in pipes],
            }
        return {
            "total_pipelines": self.count(),
            "engines": engines,
            "domains": domains,
        }

    def report(self) -> str:
        """人类可读的管线矩阵报告"""
        lines = []
        lines.append("=" * 70)
        lines.append("🚀 引擎分层 × 专业方向 管线矩阵报告")
        lines.append("=" * 70)
        s = self.summary()
        lines.append(f"\n📊 管线总数: {s['total_pipelines']}")
        lines.append("\n▶ 引擎维度:")
        for eng, info in s["engines"].items():
            lines.append(f"  {info['name']:12s} | {info['pipeline_count']:2d} 条管线 | {info['positioning']}")
        lines.append("\n▶ 专业方向维度:")
        for dom, info in s["domains"].items():
            lines.append(f"  {info['name']:12s} | {info['pipeline_count']:2d} 条管线 | 引擎: {', '.join(info['engines'])}")
        lines.append("\n▶ 管线明细:")
        for eng_name, eng_def in ENGINES.items():
            lines.append(f"\n  --- {eng_def['name']} ({eng_def['full_name']}) ---")
            for p in self.by_engine(eng_name):
                lines.append(f"    {p.pipeline_id:55s} | {p.name}")
        lines.append("\n" + "=" * 70)
        return "\n".join(lines)

    def pipeline_card(self, pipeline_id: str) -> Optional[str]:
        """单条管线详情卡片"""
        p = self.get(pipeline_id)
        if not p:
            return None
        lines = [
            f"📋 管线: {p.name}",
            f"  ID: {p.pipeline_id}",
            f"  引擎: {ENGINES.get(p.engine, {}).get('name', p.engine)}",
            f"  方向: {DOMAINS.get(p.domain, {}).get('name', p.domain)}",
            f"  状态: {p.status}",
            f"  输入: {', '.join(p.inputs)}",
            f"  工作流: {' → '.join(p.workflow)}",
            f"  产出: {', '.join(p.outputs)}",
            f"  工具链: {', '.join(p.tools)}",
            f"  质量门禁: {', '.join(p.quality_gates)}",
        ]
        if p.dependencies:
            lines.append(f"  依赖: {', '.join(p.dependencies)}")
        if p.knowledge_base:
            lines.append(f"  知识库: {p.knowledge_base}")
        return "\n".join(lines)


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    reg = PipelineRegistry()
    print(reg.report())
    print()
    print(reg.pipeline_card("pipeline.character_animation.unity"))
    print()
    # 断言
    assert reg.count() >= 40, f"管线总数应≥40, got {reg.count()}"
    assert len(reg.by_engine("react")) >= 7
    assert len(reg.by_engine("cocos")) >= 8
    assert len(reg.by_engine("unity")) >= 12
    assert len(reg.by_engine("unreal")) >= 12
    assert len(reg.by_domain("director_booth")) >= 4, "导演台应覆盖4引擎"
    assert len(reg.by_domain("skeleton_binding")) >= 4
    assert len(reg.by_domain("model_generation")) >= 2
    print("[PASS] 管线注册表自测通过")

# ============================================================
# 游戏引擎适配层 (Game Engine Adapter Layer)
# 版本: v1.0
# 说明: 为 Cocos Creator 与 Unreal Engine 提供统一的引擎抽象。
#       目标环境: Windows + Cocos + 虚幻引擎。
#       - 引擎无关的资源规范、构建管线、平台适配通过本层解耦；
#       - 部门 Agent（程序线/美术线）通过本层感知当前目标引擎，
#         产出与引擎挂钩的代码/资源/构建指令；
#       - 未来新增引擎只需实现 EngineAdapter 接口。
#
# 设计原则:
#   - 单一接口: 所有引擎实现统一的 EngineAdapter 基类；
#   - 引擎感知: 各 Agent 通过 get_engine() 获取当前目标引擎；
#   - 资源绑定: 资源格式/命名/路径规范与引擎深度挂钩；
#   - 跨平台: Windows 环境为首要目标，同时预留 macOS/Linux 扩展。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================
# 一、引擎枚举与常量
# ============================================================

class EngineType(str, Enum):
    """支持的游戏引擎类型"""
    COCOS_CREATOR = "cocos_creator"      # Cocos Creator（2D/3D 轻量游戏）
    UNREAL_ENGINE = "unreal_engine"      # Unreal Engine（3D 重度游戏）
    CUSTOM = "custom"                    # 自定义/其他引擎


# 引擎标识（可在环境变量 CNB_ENGINE 中指定，默认自动探测）
DEFAULT_ENGINE = EngineType.COCOS_CREATOR


# ============================================================
# 二、资源类型定义（与引擎挂钩）
# ============================================================

@dataclass
class ResourceSpec:
    """引擎资源规范定义"""
    engine: EngineType
    resource_type: str                     # 资源类型（如 sprite / model / audio / scene）
    extension: str                         # 文件扩展名
    import_dir: str                        # 引擎导入目录
    export_dir: str                        # 引擎导出目录
    build_tool: str                        # 构建工具命令
    max_size_mb: float = 100.0             # 单资源体积上限(MB)
    notes: str = ""                        # 备注


# ============================================================
# 三、引擎适配器接口（抽象基类）
# ============================================================

class EngineAdapter:
    """引擎适配器基类——所有引擎实现需继承本类并实现全部方法。

    各部门 Agent 通过本适配器获取引擎相关能力：
      - 程序线: 获取引擎构建指令/版本/平台设置
      - 美术线: 获取资源格式/导入路径/命名规范
      - 项目管理: 获取构建/发版命令
      - 测试线: 获取引擎启动命令/自动化测试入口
    """

    # ---- 引擎基本信息 ----
    @property
    def engine_type(self) -> EngineType:
        raise NotImplementedError

    @property
    def engine_name(self) -> str:
        """引擎显示名称"""
        raise NotImplementedError

    @property
    def engine_version(self) -> str:
        """引擎版本"""
        raise NotImplementedError

    # ---- 构建与平台 ----
    def build_command(self, target_platform: str = "windows") -> str:
        """获取引擎构建命令"""
        raise NotImplementedError

    def run_command(self, project_path: str = "") -> str:
        """获取引擎运行/启动命令"""
        raise NotImplementedError

    def supported_platforms(self) -> List[str]:
        """支持的目标平台列表"""
        raise NotImplementedError

    # ---- 资源管理 ----
    def resource_specs(self) -> List[ResourceSpec]:
        """获取引擎支持的资源类型规范"""
        raise NotImplementedError

    def resource_import_path(self, resource_type: str) -> str:
        """获取指定类型资源的导入路径"""
        raise NotImplementedError

    def resource_export_path(self, resource_type: str) -> str:
        """获取指定类型资源的导出路径"""
        raise NotImplementedError

    # ---- 项目结构 ----
    def project_structure(self) -> Dict[str, str]:
        """获取引擎项目目录结构"""
        raise NotImplementedError

    # ---- 脚本语言 ----
    @property
    def script_languages(self) -> List[str]:
        """引擎支持的脚本语言"""
        raise NotImplementedError

    # ---- 序列化 ----
    def to_dict(self) -> Dict[str, Any]:
        """将适配器序列化为可传输的 dict"""
        return {
            "engine_type": self.engine_type.value,
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "supported_platforms": self.supported_platforms(),
            "script_languages": self.script_languages,
            "project_structure": self.project_structure(),
            "resource_specs": [
                {
                    "resource_type": r.resource_type,
                    "extension": r.extension,
                    "import_dir": r.import_dir,
                    "export_dir": r.export_dir,
                }
                for r in self.resource_specs()
            ],
        }


# ============================================================
# 四、Cocos Creator 适配器
# ============================================================

class CocosCreatorAdapter(EngineAdapter):
    """Cocos Creator 引擎适配器。

    Cocos Creator 特性:
      - 轻量级 2D/3D 游戏开发
      - TypeScript 脚本语言
      - 资源直接拖拽导入（.png/.jpg/.mp3/.fbx 等）
      - 支持 Web/iOS/Android/Windows/Mac 多平台发布
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.COCOS_CREATOR

    @property
    def engine_name(self) -> str:
        return "Cocos Creator"

    @property
    def engine_version(self) -> str:
        return "3.8.x"

    def build_command(self, target_platform: str = "windows") -> str:
        """Cocos Creator 构建命令"""
        return f"cocos build --platform {target_platform}"

    def run_command(self, project_path: str = "") -> str:
        """Cocos Creator 运行命令"""
        if project_path:
            return f"cocos run -p {project_path} --platform windows"
        return "cocos run --platform windows"

    def supported_platforms(self) -> List[str]:
        return ["windows", "web", "android", "ios", "mac"]

    def resource_specs(self) -> List[ResourceSpec]:
        return [
            ResourceSpec(
                engine=EngineType.COCOS_CREATOR,
                resource_type="sprite",
                extension=".png",
                import_dir="assets/textures",
                export_dir="build/",
                build_tool="cocos build",
                max_size_mb=10.0,
                notes="2D 精灵图资源（TexturePacker 打包）",
            ),
            ResourceSpec(
                engine=EngineType.COCOS_CREATOR,
                resource_type="audio",
                extension=".mp3",
                import_dir="assets/audio",
                export_dir="build/",
                build_tool="cocos build",
                max_size_mb=20.0,
                notes="背景音乐/音效资源（.ogg/.mp3 均可）",
            ),
            ResourceSpec(
                engine=EngineType.COCOS_CREATOR,
                resource_type="animation",
                extension=".anim",
                import_dir="assets/animations",
                export_dir="build/",
                build_tool="cocos build",
                max_size_mb=50.0,
                notes="动画资源（Cocos Creator 内部动画格式）",
            ),
            ResourceSpec(
                engine=EngineType.COCOS_CREATOR,
                resource_type="prefab",
                extension=".prefab",
                import_dir="assets/prefabs",
                export_dir="build/",
                build_tool="cocos build",
                max_size_mb=30.0,
                notes="预制体资源（场景组件/UI 复用）",
            ),
            ResourceSpec(
                engine=EngineType.COCOS_CREATOR,
                resource_type="scene",
                extension=".scene",
                import_dir="assets/scenes",
                export_dir="build/",
                build_tool="cocos build",
                max_size_mb=100.0,
                notes="场景资源（关卡/UI 场景）",
            ),
            ResourceSpec(
                engine=EngineType.COCOS_CREATOR,
                resource_type="script",
                extension=".ts",
                import_dir="assets/scripts",
                export_dir="build/",
                build_tool="cocos build",
                max_size_mb=5.0,
                notes="TypeScript 脚本资源",
            ),
        ]

    def resource_import_path(self, resource_type: str) -> str:
        mapping = {
            "sprite": "assets/textures",
            "audio": "assets/audio",
            "animation": "assets/animations",
            "prefab": "assets/prefabs",
            "scene": "assets/scenes",
            "script": "assets/scripts",
        }
        return mapping.get(resource_type, "assets/")

    def resource_export_path(self, resource_type: str) -> str:
        return "build/"

    def project_structure(self) -> Dict[str, str]:
        return {
            "assets": "资源目录（scripts/textures/audio/prefabs/scenes）",
            "build": "构建产物目录",
            "settings": "项目设置",
            "library": "导入缓存",
            "temp": "临时文件",
            "profiles": "构建配置",
        }

    @property
    def script_languages(self) -> List[str]:
        return ["TypeScript", "JavaScript"]


# ============================================================
# 五、Unreal Engine 适配器
# ============================================================

class UnrealEngineAdapter(EngineAdapter):
    """Unreal Engine 适配器。

    Unreal Engine 特性:
      - 重度 3D 游戏/影视开发
      - C++ + Blueprint 双脚本体系
      - 资源丰富（网格/材质/动画/物理资产）
      - 原生支持 Windows 平台构建（.exe 打包）
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.UNREAL_ENGINE

    @property
    def engine_name(self) -> str:
        return "Unreal Engine"

    @property
    def engine_version(self) -> str:
        return "5.x"

    def build_command(self, target_platform: str = "windows") -> str:
        """Unreal Engine 构建命令"""
        return f"RunUAT BuildCookRun -platform={target_platform} -project=Game.uproject"

    def run_command(self, project_path: str = "") -> str:
        """Unreal Engine 运行命令"""
        return "Game.uproject"

    def supported_platforms(self) -> List[str]:
        return ["windows", "mac", "linux", "android", "ios"]

    def resource_specs(self) -> List[ResourceSpec]:
        return [
            ResourceSpec(
                engine=EngineType.UNREAL_ENGINE,
                resource_type="mesh",
                extension=".fbx",
                import_dir="Content/Models",
                export_dir="Saved/Cooked/",
                build_tool="RunUAT BuildCookRun",
                max_size_mb=200.0,
                notes="3D 模型资源（.fbx/.obj）",
            ),
            ResourceSpec(
                engine=EngineType.UNREAL_ENGINE,
                resource_type="material",
                extension=".uasset",
                import_dir="Content/Materials",
                export_dir="Saved/Cooked/",
                build_tool="RunUAT BuildCookRun",
                max_size_mb=100.0,
                notes="材质资源（PBR 材质/Shader）",
            ),
            ResourceSpec(
                engine=EngineType.UNREAL_ENGINE,
                resource_type="audio",
                extension=".wav",
                import_dir="Content/Audio",
                export_dir="Saved/Cooked/",
                build_tool="RunUAT BuildCookRun",
                max_size_mb=50.0,
                notes="音频资源（.wav/.ogg 格式）",
            ),
            ResourceSpec(
                engine=EngineType.UNREAL_ENGINE,
                resource_type="animation",
                extension=".uasset",
                import_dir="Content/Animations",
                export_dir="Saved/Cooked/",
                build_tool="RunUAT BuildCookRun",
                max_size_mb=100.0,
                notes="动画序列/动画蓝图",
            ),
            ResourceSpec(
                engine=EngineType.UNREAL_ENGINE,
                resource_type="blueprint",
                extension=".uasset",
                import_dir="Content/Blueprints",
                export_dir="Saved/Cooked/",
                build_tool="RunUAT BuildCookRun",
                max_size_mb=50.0,
                notes="蓝图资产（可视化脚本）",
            ),
            ResourceSpec(
                engine=EngineType.UNREAL_ENGINE,
                resource_type="script",
                extension=".cpp",
                import_dir="Source/",
                export_dir="Saved/Cooked/",
                build_tool="RunUAT BuildCookRun",
                max_size_mb=5.0,
                notes="C++ 源码（模块/类）",
            ),
        ]

    def resource_import_path(self, resource_type: str) -> str:
        mapping = {
            "mesh": "Content/Models",
            "material": "Content/Materials",
            "audio": "Content/Audio",
            "animation": "Content/Animations",
            "blueprint": "Content/Blueprints",
            "script": "Source/",
        }
        return mapping.get(resource_type, "Content/")

    def resource_export_path(self, resource_type: str) -> str:
        return "Saved/Cooked/"

    def project_structure(self) -> Dict[str, str]:
        return {
            "Content": "游戏资源（Models/Materials/Audio/Blueprints）",
            "Source": "C++ 源码",
            "Config": "项目配置",
            "Saved": "构建缓存与输出",
            "Plugins": "引擎插件",
        }

    @property
    def script_languages(self) -> List[str]:
        return ["C++", "Blueprint"]


# ============================================================
# 六、引擎工厂与探测
# ============================================================

_ENGINE_REGISTRY: Dict[str, EngineAdapter] = {
    EngineType.COCOS_CREATOR.value: CocosCreatorAdapter(),
    EngineType.UNREAL_ENGINE.value: UnrealEngineAdapter(),
}


def get_engine(engine_type: str = None) -> EngineAdapter:
    """获取指定引擎的适配器实例。

    Args:
        engine_type: 引擎类型标识（cocos_creator / unreal_engine / custom）。
                     为 None 时从环境变量 CNB_ENGINE 探测，默认 cocos_creator。

    Returns:
        EngineAdapter: 引擎适配器实例。

    Raises:
        ValueError: 引擎类型不支持。
    """
    if engine_type is None:
        import os
        engine_type = os.environ.get("CNB_ENGINE", DEFAULT_ENGINE.value)

    if engine_type not in _ENGINE_REGISTRY:
        raise ValueError(
            f"不支持的引擎类型: {engine_type}。支持: {list(_ENGINE_REGISTRY.keys())}"
        )
    return _ENGINE_REGISTRY[engine_type]


def detect_engine_from_project(project_path: str = "") -> EngineType:
    """根据项目文件探测使用的引擎类型。

    通过检查项目目录中的特征文件判断引擎:
      - Cocos Creator: project.json / package.json (cocos 依赖)
      - Unreal Engine: .uproject 文件
      - 默认返回 cocos_creator

    Args:
        project_path: 项目目录路径（可为空，默认检查当前目录）

    Returns:
        EngineType: 探测到的引擎类型
    """
    import os
    from pathlib import Path

    root = Path(project_path) if project_path else Path(".")
    if not root.exists():
        return DEFAULT_ENGINE

    # 检查 Unreal Engine 标志文件 (.uproject)
    for f in root.glob("*.uproject"):
        return EngineType.UNREAL_ENGINE

    # 检查 Cocos Creator 标志文件 (project.json)
    if (root / "project.json").exists() or (root / "package.json").exists():
        try:
            import json
            if (root / "package.json").exists():
                with open(root / "package.json") as f:
                    pkg = json.load(f)
                if "cocos" in pkg.get("dependencies", {}) or \
                   "creator" in pkg.get("dependencies", {}):
                    return EngineType.COCOS_CREATOR
        except Exception:
            pass
        return EngineType.COCOS_CREATOR

    return DEFAULT_ENGINE


def get_all_engines() -> List[EngineAdapter]:
    """获取所有已注册的引擎适配器"""
    return list(_ENGINE_REGISTRY.values())


# ============================================================
# 七、引擎感知的资源产出接口（供部门 Agent 使用）
# ============================================================

@dataclass
class EngineAwareArtifact:
    """引擎感知的产出物——部门 Agent 产出时标注引擎信息"""
    engine: EngineType
    artifact_type: str
    content: Dict[str, Any] = field(default_factory=dict)
    resource_specs: List[ResourceSpec] = field(default_factory=list)
    build_command: str = ""
    platform: str = "windows"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine.value,
            "artifact_type": self.artifact_type,
            "content": self.content,
            "resource_specs": [
                {
                    "resource_type": r.resource_type,
                    "extension": r.extension,
                    "import_dir": r.import_dir,
                    "export_dir": r.export_dir,
                }
                for r in self.resource_specs
            ],
            "build_command": self.build_command,
            "platform": self.platform,
            "notes": self.notes,
        }


def build_engine_aware_artifact(
    engine_type: str,
    artifact_type: str,
    content: Dict[str, Any],
    platform: str = "windows",
    notes: str = "",
) -> EngineAwareArtifact:
    """构建引擎感知的产出物。

    根据引擎类型获取对应的资源规范与构建命令，
    生成带引擎信息的产出物（供各部门 Agent 消费）。

    Args:
        engine_type: 引擎类型（cocos_creator / unreal_engine）
        artifact_type: 产出物类型（如 art_asset / code / test_report）
        content: 产出内容
        platform: 目标平台（默认 windows）
        notes: 备注

    Returns:
        EngineAwareArtifact: 引擎感知产出物
    """
    engine = get_engine(engine_type)
    resource_specs = engine.resource_specs()
    build_cmd = engine.build_command(platform)

    return EngineAwareArtifact(
        engine=engine.engine_type,
        artifact_type=artifact_type,
        content=content,
        resource_specs=resource_specs,
        build_command=build_cmd,
        platform=platform,
        notes=notes,
    )


# ============================================================
# 八、自测
# ============================================================

if __name__ == "__main__":
    print("=== 游戏引擎适配层自测 ===")
    print()

    # 1. 探测默认引擎
    print("== 1. 默认引擎探测 ==")
    default = detect_engine_from_project()
    print(f"  当前项目探测引擎: {default.value}")

    # 2. Cocos Creator 适配器
    print("\n== 2. Cocos Creator 适配器 ==")
    cocos = get_engine("cocos_creator")
    print(f"  引擎名称: {cocos.engine_name} ({cocos.engine_version})")
    print(f"  支持平台: {cocos.supported_platforms()}")
    print(f"  脚本语言: {cocos.script_languages}")
    print(f"  构建命令: {cocos.build_command('windows')}")
    print(f"  资源规格数: {len(cocos.resource_specs())}")
    for rs in cocos.resource_specs()[:3]:
        print(f"    - {rs.resource_type} ({rs.extension}) → {rs.import_dir}")

    # 3. Unreal Engine 适配器
    print("\n== 3. Unreal Engine 适配器 ==")
    unreal = get_engine("unreal_engine")
    print(f"  引擎名称: {unreal.engine_name} ({unreal.engine_version})")
    print(f"  支持平台: {unreal.supported_platforms()}")
    print(f"  脚本语言: {unreal.script_languages}")
    print(f"  构建命令: {unreal.build_command('windows')}")
    print(f"  资源规格数: {len(unreal.resource_specs())}")
    for rs in unreal.resource_specs()[:3]:
        print(f"    - {rs.resource_type} ({rs.extension}) → {rs.import_dir}")

    # 4. 引擎感知产出物
    print("\n== 4. 引擎感知产出物 ==")
    artifact = build_engine_aware_artifact(
        "cocos_creator",
        "art_asset",
        {"style": "卡通渲染", "texture_scale": "512x512"},
    )
    print(f"  引擎: {artifact.engine.value}")
    print(f"  构建命令: {artifact.build_command}")
    print(f"  资源规格数: {len(artifact.resource_specs)}")

    # 5. 全部引擎
    print("\n== 5. 全部引擎 ==")
    for eng in get_all_engines():
        print(f"  - {eng.engine_name} ({eng.engine_type.value})")

    print("\n🟢 引擎适配层自测通过")

# ============================================================
# 双引擎适配层 (Engine Adapters)
# 版本: v1.0
# 说明: 面向「Windows + Cocos Creator + Unreal Engine」本地引擎环境，
#       为两类引擎提供**统一抽象**——技术栈、资源目录、构建命令、
#       资源类型契约、构建产物清单。让云端编排（task_scheduler / message_bus
#       / 六大部门）能按目标引擎把派单落到正确引擎上，产出可验收。
#
#   对齐架构师建议（wp_engine_adaptation）：
#     P1-1 双引擎技术栈落地到岗位/流水线 → 本模块定义引擎技术栈 + 构建产物契约
#     P2-5 资源管线按双引擎分叉        → Cocos .prefab/.scene vs UE .uasset/.umap
#
#   核心能力：
#     1. get_engine_spec(engine)：返回指定引擎的完整技术栈契约（脚本语言/资源
#        目录/构建命令/资源类型/产物目录/版本）；
#     2. resolve_engine()：从 CNB_ENGINE 环境变量 / 参数解析目标引擎，
#        默认识别 cocos / unreal；
#     3. build_artifact_manifest(engine, modules)：按引擎生成**构建产物清单**
#        （要产出哪些资源/代码，供验收）；
#     4. artifact_contract(engine, kind)：查询某资源类型在指定引擎的落地格式。
#
# 语言: Python 3 (可运行，无需外部依赖)
# ============================================================
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ============================================================
# 引擎技术栈契约
# ============================================================

@dataclass
class EngineSpec:
    """一种游戏引擎的完整技术栈契约"""
    engine: str                                # 引擎标识: cocos / unreal
    display_name: str                          # 显示名: Cocos Creator / Unreal Engine
    script_langs: List[str] = field(default_factory=list)   # 脚本语言
    resource_dir: str = ""                     # 资源根目录
    build_cmd: str = ""                        # 构建命令模板
    build_output_dir: str = ""                 # 构建产物输出目录
    resource_types: Dict[str, str] = field(default_factory=dict)  # 资源类型 -> 落地格式
    default_version: str = ""                  # 默认引擎版本
    tool_chain: List[str] = field(default_factory=list)          # 工具链


# 引擎注册表
_ENGINE_SPECS: Dict[str, EngineSpec] = {
    "cocos": EngineSpec(
        engine="cocos",
        display_name="Cocos Creator",
        script_langs=["typescript", "javascript"],
        resource_dir="assets",
        build_cmd="cocos build --platform {platform}",
        build_output_dir="build",
        resource_types={
            "sprite": ".png/.jpg",
            "prefab": ".prefab",
            "scene": ".scene",
            "animation": ".anim",
            "audio": ".mp3/.ogg/.wav",
            "script": ".ts/.js",
            "material": ".mtl",
            "effect": ".effect",
            "texture": ".png",
        },
        default_version="3.x",
        tool_chain=["Cocos Creator 编辑器", "cocos 命令行", "TypeScript 编译器"],
    ),
    "unreal": EngineSpec(
        engine="unreal",
        display_name="Unreal Engine",
        script_langs=["cpp", "blueprint"],
        resource_dir="Content",
        build_cmd="RunUAT BuildCookRun -platform={platform} -project={project}",
        build_output_dir="Saved/Build",
        resource_types={
            "mesh": ".uasset",
            "material": ".uasset",
            "texture": ".uasset",
            "audio": ".uasset",
            "animation": ".uasset",
            "blueprint": ".uasset",
            "map": ".umap",
            "data_asset": ".uasset",
            "script": ".cpp/.h",
            "fx": ".uasset",
        },
        default_version="UE 5.x",
        tool_chain=["Unreal Editor", "RunUAT", "Visual Studio", "C++ 编译器"],
    ),
}


def get_engine_spec(engine: str) -> Optional[EngineSpec]:
    """返回指定引擎的技术栈契约；引擎不存在返回 None。"""
    key = (engine or "").strip().lower()
    return _ENGINE_SPECS.get(key)


def list_engines() -> List[str]:
    """列出已注册的引擎。"""
    return list(_ENGINE_SPECS.keys())


def resolve_engine(hint: Optional[str] = None) -> str:
    """解析目标引擎：优先参数，其次 CNB_ENGINE 环境变量，最后默认 cocos。"""
    candidate = (hint or os.environ.get("CNB_ENGINE", "") or "").strip().lower()
    if candidate in _ENGINE_SPECS:
        return candidate
    # 别名归一
    if "cocos" in candidate:
        return "cocos"
    if "unreal" in candidate or "ue" in candidate or "虚幻" in candidate:
        return "unreal"
    return "cocos"


# ============================================================

def _safe_format(cmd: str, **kwargs) -> str:
    """容错格式化：只替换存在的占位符，缺失占位符保留原样。"""
    return cmd.format(**{k: v for k, v in kwargs.items() if "{%s}" % k in cmd})


# 构建产物契约（P1-1）
# ============================================================

@dataclass
class ArtifactItem:
    """构建产物清单中的一项"""
    kind: str            # 资源/代码类型，如 prefab / blueprint / scene
    engine_format: str   # 该类型在目标引擎的落地格式
    required: bool = True
    path_hint: str = ""  # 建议落地路径


def build_artifact_manifest(engine: str, modules: List[str]) -> Dict[str, Any]:
    """按引擎生成构建产物清单（面向验收）。

    modules: 工作包要产出的模块类型，如 ["scene", "ui", "audio", "blueprint"]。
    返回: {"engine", "display_name", "resource_dir", "artifacts": [...]}
    """
    spec = get_engine_spec(engine) or get_engine_spec("cocos")
    artifacts = []
    for mod in modules:
        fmt = spec.resource_types.get(mod, f".{mod}")
        artifacts.append({
            "kind": mod,
            "engine_format": fmt,
            "resource_dir": spec.resource_dir,
            "path_hint": f"{spec.resource_dir}/{mod}",
        })
    return {
        "engine": spec.engine,
        "display_name": spec.display_name,
        "resource_dir": spec.resource_dir,
        "build_cmd": _safe_format(spec.build_cmd, platform="windows", project="Game"),
        "artifacts": artifacts,
    }


def artifact_contract(engine: str, kind: str) -> str:
    """查询某资源类型在指定引擎的落地格式（如 .prefab / .umap）。"""
    spec = get_engine_spec(engine) or get_engine_spec("cocos")
    return spec.resource_types.get(kind, f".{kind}")


# ============================================================
# 部门适配（程序线 / 美术线按引擎落地）
# ============================================================

def engine_aware_artifact(engine: str, dept: str, work_package: Dict[str, Any]) -> Dict[str, Any]:
    """按目标引擎把部门工作包产出标注为可验收的引擎契约。

    dept: 部门标识，如 "程序线" / "美术线"。
    返回带 engine / display_name / build_cmd / resource_dir 的标注产出。
    """
    spec = get_engine_spec(engine) or get_engine_spec("cocos")
    module = work_package.get("module", "generic")
    fmt = spec.resource_types.get(module, f".{module}")
    return {
        "module": module,
        "engine": spec.engine,
        "display_name": spec.display_name,
        "script_langs": spec.script_langs,
        "resource_dir": spec.resource_dir,
        "build_cmd": _safe_format(spec.build_cmd, platform="windows", project="Game"),
        "resource_format": fmt,
        "dept": dept,
    }


def _demo():
    print("=" * 60)
    print("双引擎适配层自测")
    print("=" * 60)
    for eng in list_engines():
        spec = get_engine_spec(eng)
        print(f"\n[{spec.display_name}]")
        print(f"  脚本语言: {', '.join(spec.script_langs)}")
        print(f"  资源目录: {spec.resource_dir}")
        print(f"  构建命令: {_safe_format(spec.build_cmd, platform='windows', project='Game')}")
        print(f"  资源类型: scene -> {spec.resource_types.get('scene', 'N/A')}, "
              f"blueprint -> {spec.resource_types.get('blueprint', 'N/A')}, "
              f"audio -> {spec.resource_types.get('audio', 'N/A')}")

    print("\n[构建产物契约示例]")
    manifest = build_artifact_manifest("cocos", ["scene", "ui", "audio"])
    print(f"  引擎: {manifest['engine']} / 资源目录: {manifest['resource_dir']}")
    for a in manifest["artifacts"]:
        print(f"    - {a['kind']}: {a['engine_format']} @ {a['path_hint']}")

    manifest2 = build_artifact_manifest("unreal", ["map", "blueprint", "audio"])
    print(f"  引擎: {manifest2['engine']} / 资源目录: {manifest2['resource_dir']}")
    for a in manifest2["artifacts"]:
        print(f"    - {a['kind']}: {a['engine_format']} @ {a['path_hint']}")

    print("\n[引擎感知产出示例]")
    print(f"  resolve_engine() = {resolve_engine()}")
    print(f"  resolve_engine('虚幻') = {resolve_engine('虚幻')}")
    print(f"  engine_aware_artifact('unreal','程序线',{{'module':'blueprint'}}) = "
          f"{engine_aware_artifact('unreal','程序线',{'module':'blueprint'})}")


if __name__ == "__main__":
    _demo()

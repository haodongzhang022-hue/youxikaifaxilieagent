# ============================================================
# 引擎桥接层 · Windows 环境适配
# 版本: v0.1
# 说明: 面向 Windows 环境的引擎运行环境检测与配置。
#       提供引擎安装路径探测、环境变量管理、进程管理辅助。
#
# 设计考虑:
#   - Windows 路径约定：盘符、反斜杠、Program Files 等
#   - 环境变量：UE_ROOT / COCOS_CREATOR_PATH / ENGINE_PATH 等
#   - 引擎默认安装路径：Cocos Creator / Unreal Engine 常见路径
#   - 进程管理：查找/启动/停止引擎编辑器进程
# ============================================================
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ============================================================
# 引擎环境信息
# ============================================================

@dataclass
class EngineEnvironment:
    """引擎运行环境信息。"""

    os_name: str = ""                    # "windows" / "linux" / "darwin"
    engine_type: str = ""                # "cocos" / "ue5" / "both"
    is_windows: bool = False
    # 引擎安装路径
    cocos_path: str = ""
    ue5_path: str = ""
    # 引擎版本
    cocos_version: str = ""
    ue5_version: str = ""
    # 可执行文件
    cocos_executable: str = ""
    ue5_executable: str = ""
    # 环境变量
    env_vars: Dict[str, str] = field(default_factory=dict)
    # MCP Server 信息
    mcp_endpoints: Dict[str, str] = field(default_factory=dict)
    # 插件目录
    plugin_dirs: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "os_name": self.os_name,
            "engine_type": self.engine_type,
            "is_windows": self.is_windows,
            "cocos_path": self.cocos_path,
            "ue5_path": self.ue5_path,
            "cocos_version": self.cocos_version,
            "ue5_version": self.ue5_version,
            "cocos_executable": self.cocos_executable,
            "ue5_executable": self.ue5_executable,
            "env_vars": dict(self.env_vars),
            "mcp_endpoints": dict(self.mcp_endpoints),
            "plugin_dirs": dict(self.plugin_dirs),
        }


# ============================================================
# 常见安装路径探测
# ============================================================

# Windows 下 Cocos Creator 的常见安装位置
_WINDOWS_COCOS_PATHS = [
    r"C:\Program Files\CocosCreator",
    r"C:\Program Files (x86)\CocosCreator",
    r"C:\Program Files\Cocos\Creator",
    r"C:\CocosCreator",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\CocosCreator"),
]

# Windows 下 UE5 的常见安装位置
_WINDOWS_UE5_PATHS = [
    r"C:\Program Files\Epic Games\UE_5.0",
    r"C:\Program Files\Epic Games\UE_5.1",
    r"C:\Program Files\Epic Games\UE_5.2",
    r"C:\Program Files\Epic Games\UE_5.3",
    r"C:\Program Files\Epic Games\UE_5.4",
    r"C:\Program Files\Epic Games\UE_5.5",
]

# Cocos Creator 可执行文件名
_COCOS_EXECUTABLES = [
    "CocosCreator.exe",
    "CocosCreator",
]

# UE5 编辑器可执行文件名（随版本变化）
_UE5_EXECUTABLES = [
    "UnrealEditor.exe",
    "UnrealEditor",
    "UE4Editor.exe",
]


def _detect_windows():
    """检测是否 Windows 环境。"""
    return platform.system().lower() == "windows"


def _find_existing_path(paths: List[str]) -> str:
    """从候选路径列表中找到第一个存在的路径。"""
    for p in paths:
        expanded = os.path.expandvars(p)
        if os.path.exists(expanded):
            return expanded
    return ""


def _find_executable(engine_path: str, candidates: List[str]) -> str:
    """在引擎目录下查找可执行文件。"""
    if not engine_path:
        return ""
    # 搜索常见子目录
    search_dirs = [engine_path]
    for sub in ["bin", "Editor", "Mac", "Windows"]:
        search_dirs.append(os.path.join(engine_path, sub))
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for exe in candidates:
            full = os.path.join(d, exe)
            if os.path.isfile(full):
                return full
    # 回退：在 PATH 中查找
    for exe in candidates:
        found = shutil.which(exe)
        if found:
            return found
    return ""


def _detect_cocos(env_vars: Dict[str, str]) -> Dict[str, str]:
    """探测 Cocos Creator 安装信息。"""
    out = {"path": "", "version": "", "executable": ""}
    # 从环境变量
    cocos_path = env_vars.get("COCOS_CREATOR_PATH", "") or env_vars.get("COCOS_PATH", "")
    if cocos_path and os.path.exists(cocos_path):
        out["path"] = cocos_path
    else:
        out["path"] = _find_existing_path(_WINDOWS_COCOS_PATHS)
    # 可执行文件
    if out["path"]:
        out["executable"] = _find_executable(out["path"], _COCOS_EXECUTABLES)
    return out


def _detect_ue5(env_vars: Dict[str, str]) -> Dict[str, str]:
    """探测 UE5 安装信息。"""
    out = {"path": "", "version": "", "executable": ""}
    # 从环境变量
    ue_path = env_vars.get("UE5_PATH", "") or env_vars.get("UE_ROOT", "") \
        or env_vars.get("UNREAL_ENGINE_PATH", "")
    if ue_path and os.path.exists(ue_path):
        out["path"] = ue_path
    else:
        out["path"] = _find_existing_path(_WINDOWS_UE5_PATHS)
    # 版本号从路径推断
    if out["path"]:
        m = re.search(r"UE[_-]?(\d+\.\d+)", out["path"])
        if m:
            out["version"] = m.group(1)
    # 可执行文件
    if out["path"]:
        out["executable"] = _find_executable(out["path"], _UE5_EXECUTABLES)
    return out


# ============================================================
# 环境探测入口
# ============================================================

def detect_engine_environment() -> EngineEnvironment:
    """探测当前环境中的引擎配置。

    返回 EngineEnvironment，包含引擎类型、安装路径、版本、可执行文件
    和 MCP Server 端点等。当前 Linux 开发环境返回模拟的 Windows 目标环境
    （供测试与架构验证使用），Windows 部署时返回真实探测结果。
    """
    env = EngineEnvironment()
    env.os_name = platform.system().lower()
    env.is_windows = _detect_windows()

    # 收集相关环境变量
    for var in ["COCOS_CREATOR_PATH", "COCOS_PATH", "UE5_PATH", "UE_ROOT",
                "UNREAL_ENGINE_PATH", "COCOS_MCP_URL", "UE5_MCP_URL"]:
        val = os.environ.get(var, "")
        if val:
            env.env_vars[var] = val

    # 探测 Cocos
    cocos = _detect_cocos(env.env_vars)
    env.cocos_path = cocos["path"]
    env.cocos_version = cocos["version"]
    env.cocos_executable = cocos["executable"]

    # 探测 UE5
    ue5 = _detect_ue5(env.env_vars)
    env.ue5_path = ue5["path"]
    env.ue5_version = ue5["version"]
    env.ue5_executable = ue5["executable"]

    # 确定引擎类型
    if env.cocos_path and env.ue5_path:
        env.engine_type = "both"
    elif env.cocos_path:
        env.engine_type = "cocos"
    elif env.ue5_path:
        env.engine_type = "ue5"

    # MCP Server 端点（从环境变量或默认约定）
    env.mcp_endpoints = {
        "cocos": env.env_vars.get("COCOS_MCP_URL", "http://127.0.0.1:12345/mcp"),
        "ue5": env.env_vars.get("UE5_MCP_URL", "http://127.0.0.1:54321/mcp"),
    }

    # 插件目录
    env.plugin_dirs = {
        "cocos": os.path.join(env.cocos_path, "extensions") if env.cocos_path else "",
        "ue5": os.path.join(env.ue5_path, "Plugins") if env.ue5_path else "",
    }

    return env


def get_windows_environment() -> EngineEnvironment:
    """获取 Windows 目标环境的引擎配置（供架构设计/测试用）。

    在非 Windows 环境（如当前 Linux CI）返回模拟的 Windows 目标环境，
    供引擎桥接层架构验证与测试使用。
    """
    if _detect_windows():
        return detect_engine_environment()

    # 模拟 Windows 环境（供 CI 测试与架构验证）
    mock = EngineEnvironment(
        os_name="windows",
        engine_type="both",
        is_windows=True,
        cocos_path=r"C:\Program Files\CocosCreator",
        cocos_version="3.8",
        cocos_executable=r"C:\Program Files\CocosCreator\CocosCreator.exe",
        ue5_path=r"C:\Program Files\Epic Games\UE_5.3",
        ue5_version="5.3",
        ue5_executable=r"C:\Program Files\Epic Games\UE_5.3\Engine\Binaries\Win64\UnrealEditor.exe",
        env_vars={
            "COCOS_CREATOR_PATH": r"C:\Program Files\CocosCreator",
            "UE5_PATH": r"C:\Program Files\Epic Games\UE_5.3",
        },
        mcp_endpoints={
            "cocos": "http://127.0.0.1:12345/mcp",
            "ue5": "http://127.0.0.1:54321/mcp",
        },
        plugin_dirs={
            "cocos": r"C:\Program Files\CocosCreator\extensions",
            "ue5": r"C:\Program Files\Epic Games\UE_5.3\Plugins",
        },
    )
    return mock

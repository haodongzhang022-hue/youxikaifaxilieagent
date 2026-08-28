# ============================================================
# 双环境同步层 (Engine Sync)
# 版本: v1.0
# 说明: 打通「本地 Windows 引擎环境（Cocos/UE + DeepSeek harness）」与
#       「云端 cnb.cool 编排层」之间的资源/产物双向同步。
#
#   对齐架构师建议（wp_engine_adaptation）：
#     P1-3 本地↔云端资源/产物双向同步通道缺失 → 本模块定义产物清单格式
#           + 上传/落地协议；
#     P1-4 双环境一致性护栏缺失              → 同源 hash/版本一致性校验，
#           防「本地引擎 vs 云端 npc:go 各持一份代码/资源」导致的分歧事故
#           （即 wp_audio 那类「分支/commit 找不到、改动未落地」）。
#
#   核心能力：
#     1. build_manifest(engine, items)：把本地产出的资源/代码生成**产物清单**
#        （含 hash 与版本），作为上传云端的传输契约；
#     2. verify_manifest(manifest, local_root)：对落地产物做**同源校验**
#        ——比对 hash，发现不一致即告警，杜绝「声明未落地」；
#     3. sync_plan(engine, direction)：生成本地→云端 上传 / 云端→本地 派单
#        落地的**同步计划**；
#     4. consistency_report(manifest, actual)：输出双环境一致性护栏报告。
#
# 语言: Python 3 (可运行，无需外部依赖)
# ============================================================
from __future__ import annotations
import hashlib
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ============================================================
# 产物清单与 hash
# ============================================================

def _file_hash(path: str) -> str:
    """计算单个文件 SHA-256（不存在返回 'MISSING'）。"""
    if not path or not os.path.isfile(path):
        return "MISSING"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


@dataclass
class ManifestItem:
    """产物清单中的一项"""
    path: str            # 相对路径，如 Content/Scenes/Game.umap
    engine_format: str   # 落地格式，如 .umap / .prefab
    sha: str = ""        # 内容 hash（本地生成时计算）
    size: int = 0        # 字节数


def build_manifest(engine: str, local_root: str, items: List[str]) -> Dict[str, Any]:
    """生成本地产出物的产物清单（上传云端前）。

    local_root: 本地资源根目录
    items: 相对路径列表，如 ["Content/Scenes/Game.umap"]
    返回: {"engine", "version", "root", "items": [...]}
    """
    manifest_items = []
    for rel in items:
        full = os.path.join(local_root, rel) if local_root else rel
        sha = _file_hash(full)
        size = os.path.getsize(full) if os.path.isfile(full) else 0
        ext = os.path.splitext(rel)[1]
        manifest_items.append(ManifestItem(
            path=rel, engine_format=ext or ".bin", sha=sha, size=size))
    return {
        "engine": engine,
        "version": "1.0",
        "root": local_root,
        "items": [vars(m) for m in manifest_items],
    }


def verify_manifest(manifest: Dict[str, Any], local_root: str) -> Dict[str, Any]:
    """对落地产物做**同源校验**（P1-4 一致性护栏）。

    逐一比对 manifest 记录的 hash 与实际文件 hash：
    - MATCH  : 一致
    - MISSING: 本地缺失（声明未落地的典型）
    - MISMATCH: hash 不一致（内容分歧）
    返回一致性报告。
    """
    root = manifest.get("root", "") or local_root
    engine = manifest.get("engine", "")
    results = []
    all_ok = True
    for item in manifest.get("items", []):
        path = item.get("path", "")
        expected = item.get("sha", "")
        full = os.path.join(root, path) if root else path
        actual = _file_hash(full)
        if actual == "MISSING":
            status = "MISSING"
            all_ok = False
        elif actual != expected:
            status = "MISMATCH"
            all_ok = False
        else:
            status = "MATCH"
        results.append({"path": path, "expected_sha": expected,
                        "actual_sha": actual, "status": status})
    return {
        "engine": engine,
        "consistent": all_ok,
        "item_count": len(results),
        "results": results,
    }


def consistency_report(manifest: Dict[str, Any], local_root: str) -> str:
    """输出双环境一致性护栏报告（人可读文本）。"""
    report = verify_manifest(manifest, local_root)
    lines = [f"一致性护栏报告（engine={report['engine']}，共 {report['item_count']} 项）"]
    for r in report["results"]:
        mark = "✅" if r["status"] == "MATCH" else "❌"
        lines.append(f"  {mark} [{r['status']}] {r['path']} "
                     f"(期望 {r['expected_sha']} / 实际 {r['actual_sha']})")
    lines.append("结论: " + ("🟢 双环境一致" if report["consistent"] else "🔴 存在分歧，禁止验收"))
    return "\n".join(lines)


# ============================================================
# 双向同步计划（P1-3）
# ============================================================

def sync_plan(engine: str, direction: str, items: List[str]) -> Dict[str, Any]:
    """生成双环境同步计划。

    direction: "up"（本地→云端上传） / "down"（云端→本地落地）。
    返回同步计划，含通道、动作、校验要求。
    """
    if direction == "up":
        action = "上传本地产物到云端 cnb.cool 制品库"
        channel = "本地 → 云端"
    else:
        action = "从云端派单落地到本地引擎"
        channel = "云端 → 本地"
    return {
        "engine": engine,
        "direction": direction,
        "channel": channel,
        "action": action,
        "items": items,
        "require_consistency_check": True,  # 同步后强制同源校验
    }


def _demo():
    import tempfile
    print("=" * 60)
    print("双环境同步层自测")
    print("=" * 60)
    tmp = tempfile.mkdtemp()
    sample = os.path.join(tmp, "Content/Scenes/Game.umap")
    os.makedirs(os.path.dirname(sample), exist_ok=True)
    with open(sample, "w") as f:
        f.write("level data placeholder")

    manifest = build_manifest("unreal", tmp, ["Content/Scenes/Game.umap",
                                              "Content/BP/Enemy.blueprint"])
    print("\n[产物清单]")
    print(f"  engine={manifest['engine']} root={manifest['root']}")
    for it in manifest["items"]:
        print(f"    - {it['path']} ({it['engine_format']}, sha={it['sha']})")

    print("\n[同源校验（一致场景）]")
    print(consistency_report(manifest, tmp))

    # 模拟声明未落地（缺失文件）
    print("\n[同源校验（缺失场景·声明未落地）]")
    missing_manifest = {
        "engine": "unreal", "root": tmp,
        "items": [{"path": "Content/BP/NotReal.blueprint", "sha": "abc123"}],
    }
    print(consistency_report(missing_manifest, tmp))

    # 模拟内容分歧（hash 不一致）
    print("\n[同源校验（分歧场景）]")
    with open(sample, "w") as f:
        f.write("level data CHANGED")
    print(consistency_report(manifest, tmp))

    print("\n[同步计划]")
    plan_up = sync_plan("cocos", "up", ["assets/scene/Main.scene"])
    plan_down = sync_plan("unreal", "down", ["Content/Scenes/Game.umap"])
    print(f"  up   : {plan_up['channel']} -> {plan_up['action']}（需一致性校验={plan_up['require_consistency_check']}）")
    print(f"  down : {plan_down['channel']} -> {plan_down['action']}")


if __name__ == "__main__":
    _demo()

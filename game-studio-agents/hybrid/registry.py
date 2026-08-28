# -*- coding: utf-8 -*-
"""
TestRegistry · 集中测试注册表（接口层）
======================================
集中维护「每个测试覆盖哪些源码文件」「测试间依赖关系」
「CPU 成本估算」「执行时长估算」。

数据源：registry.json（本目录下），内容为 31 个独立测试脚本 +
test_all_modules.sh 汇总入口的覆盖关系。

核心接口：
  - all_tests()                 所有已注册测试脚本路径 list
  - get(name)                   单个测试条目 dict
  - covers(name)                该测试覆盖的源码文件 list
  - dependencies(name)          该测试依赖的其他测试 list
  - find_by_source(path)        覆盖指定源码的测试
  - find_many_by_source(paths)  覆盖指定多个源码的测试（去重）
  - impact_closure(name)        依赖传播闭包（该测试 + 依赖它的所有测试）
  - affected_tests(paths)       给定变更文件 → 受影响测试（含依赖传播）
  - summary()                   注册表统计概览
"""
import json
import os

_REGISTRY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registry.json")

# 全量兜底白名单：以下测试覆盖「配置/全链路/汇总」，任何源码变更都应兜底运行
# （它们是轻量静态校验或整体护栏，成本低，适合作为 safety net）
_FULL_COVERAGE_TESTS = {
    "test_dept_npc_pipeline.sh",   # 校验 .cnb.yml/settings.yml 全量一致性
    "modules/test_all_modules.sh", # 汇总入口，仅 PR 合并后兜底
}


def _load():
    if not os.path.exists(_REGISTRY_PATH):
        raise RuntimeError("registry.json 不存在: %s" % _REGISTRY_PATH)
    with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tests", {})


def all_tests():
    """返回所有已注册测试脚本路径 list（排序）。"""
    return sorted(_load().keys())


def get(name):
    """返回单个测试条目 dict；不存在返回 None。"""
    return _load().get(name)


def covers(name):
    """返回该测试覆盖的源码文件 list。"""
    info = get(name) or {}
    return list(info.get("covers", []))


def dependencies(name):
    """返回该测试依赖的其他测试 list。"""
    info = get(name) or {}
    return list(info.get("depends_on", []))


def _path_variants(path):
    """路径双向归一化：兼容带/不带 game-studio-agents 前缀。"""
    base = "game-studio-agents"
    p = path.rstrip("/")
    variants = {p}
    if p.startswith(base + "/"):
        variants.add(p[len(base) + 1:])
    elif p.startswith("config/"):
        variants.add(base + "/" + p)
    else:
        variants.add(base + "/config/" + p if not p.startswith(base) else p)
        variants.add(base + "/" + p)
    return variants


def _covers_match(source_path, covered):
    """判断变更文件是否命中某测试的覆盖范围（含目录前缀匹配）。"""
    for s in _path_variants(source_path):
        for c in _path_variants(covered):
            if (s == c or
                s.startswith(c + "/") or
                c.startswith(s + "/") or
                c.startswith(s)):
                return True
    return False


def find_by_source(path):
    """返回覆盖指定源码文件的所有测试 list。"""
    tests = _load()
    hits = []
    for name, info in tests.items():
        for covered in info.get("covers", []):
            if _covers_match(path, covered):
                hits.append(name)
                break
    return sorted(set(hits))


def find_many_by_source(paths):
    """给定多个变更文件 → 返回命中的所有测试（去重）。"""
    result = set()
    for p in paths:
        result.update(find_by_source(p))
    return sorted(result)


def impact_closure(name):
    """依赖传播闭包：给定测试 → 所有直接/间接依赖它的测试。"""
    tests = _load()
    visited = set()

    def dfs(t):
        if t in visited:
            return
        visited.add(t)
        for other, oinfo in tests.items():
            if t in oinfo.get("depends_on", []):
                dfs(other)

    dfs(name)
    return sorted(visited)


def affected_tests(paths):
    """给定变更文件清单 → 返回需运行的测试脚本（含依赖传播）。

    变更的 .sh 测试脚本自身不触发测试（避免改测试又跑自己导致的递归），
    但变更 config/.py 源码会触发覆盖它的测试 + 依赖传播闭包。
    """
    if not paths:
        return []
    # 过滤掉 .sh 测试脚本自身与纯文档变更
    source_files = [p for p in paths
                    if not p.endswith(".sh")
                    and not p.endswith(".md")
                    and not p.endswith(".pyc")]
    if not source_files:
        # 若只改了 .cnb.yml / settings.yml，兜底配置一致性测试
        if any("cnb.yml" in p or "settings.yml" in p for p in paths):
            return ["test_dept_npc_pipeline.sh"]
        return []
    direct = set(find_many_by_source(source_files))
    result = set()
    for t in direct:
        result.update(impact_closure(t))
    return sorted(result)


def summary():
    """注册表统计概览。"""
    tests = _load()
    return {
        "total": len(tests),
        "tests": sorted(tests.keys()),
    }

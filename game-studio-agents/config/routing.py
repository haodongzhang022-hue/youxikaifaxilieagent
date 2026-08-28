# ============================================================
# 部门派发路由决策模块 (DepartmentRouting)
# 版本: v1.0
# 说明: 解决「无工作部门凑热闹」问题——每次编排不再无条件触发全部
#       六大部门，而是由一个**路由决策**环节，依据"工作内容匹配"规则
#       精准判定本轮应触发哪些部门，只有被命中的部门才被派发/执行。
#
# 核心能力:
#   1. route_by_content(): 按工作内容(标题/正文/改动描述) 关键词规则
#       匹配 → 返回本轮应触发的部门清单；
#   2. route_by_deps():     按依赖解锁结果 → 返回应解锁的下游部门；
#   3. route():             综合内容匹配 + 依赖解锁 + 明确点名，
#       输出最终 active_departments 路由清单；
#   4. is_department_active(): 供流水线 stage 的 if 条件判断本部门
#       是否被路由命中，未命中则整体跳过（不再凑热闹）。
#
# 路由规则原则:
#   - 明确点名(manually_requested) 优先：人类/上游点名某部门 → 必触发；
#   - 工作内容匹配(rule) 兜底：标题/正文命中部门关键词 → 触发该部门；
#   - 依赖解锁(deps_unlocked) 补充：上游验收通过 → 解锁下游部门；
#   - 未命中任何规则 → 不触发（缺省不派发，杜绝无意义凑热闹）。
#
# 语言: Python 3 (可运行)
# 依赖: 无外部依赖（纯标准库）
# ============================================================
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

# 部门中文名 → 内部键（与 game_producer_agent / roles.yaml 对齐）
DEPT_KEY_BY_NAME = {
    "策划线": "design", "程序线": "program", "美术线": "art",
    "测试线": "qa", "项目管理": "pm", "运营线": "ops",
}

# ============================================================
# 部门 → 工作内容关键词匹配规则表
# 每个部门列出其职责强相关关键词；工作内容命中越多 → 越应触发该部门。
# 按"职责强绑定"设计，避免无关任务误触发（如"美术总是无工作凑热闹"）。
# ============================================================
DEPT_RULES: Dict[str, Dict[str, Any]] = {
    "策划线": {
        "keywords": [
            "玩法", "系统设计", "数值", "经济", "关卡", "剧情", "世界观",
            "战斗机制", "技能", "NPC AI", "任务文案", "设计文档", "gameplay",
            "level_design", "narrative", "combat_designer", "balance",
        ],
        "modules": ["gameplay", "numeric_model", "narrative", "combat", "level"],
    },
    "程序线": {
        "keywords": [
            "客户端", "服务端", "引擎", "渲染", "AI", "工具链", "接口",
            "bug修复", "代码", "实现", "重构", "client", "server", "engine",
            "backend", "frontend", "api", "refactor", "编码", "性能优化",
        ],
        "modules": ["client", "server", "engine", "ai_logic", "tools"],
    },
    "美术线": {
        "keywords": [
            "美术", "原画", "建模", "动画", "特效", "UI", "场景", "音频",
            "视觉", "贴图", "材质", "3D", "角色资产", "art", "concept",
            "modeling", "animation", "vfx", "ui_ux", "audio", "tech_artist",
        ],
        "modules": ["art_direction", "ui_ux", "audio"],
    },
    "测试线": {
        "keywords": [
            "测试", "验收", "回归", "质量", "QA", "自动化测试", "测试报告",
            "信号灯", "冒烟", "性能测试", "case", "断言", "test", "qa",
            "regression", "验收报告",
        ],
        "modules": ["testing"],
    },
    "项目管理": {
        "keywords": [
            "发版", "版本", "里程碑", "门禁", "排期", "验收", "闭环", "发布计划",
            "release", "milestone", "gate", "plan", "schedule", "project_manager",
        ],
        "modules": ["release"],
    },
    "运营线": {
        "keywords": [
            "运营", "数据分析", "竞品", "生态", "市场", "推广", "指标",
            "洞察", "运营策略", "数据", "ops", "data", "market", "运营部署",
        ],
        "modules": ["data_ops"],
    },
}

# 汇总所有部门名，供校验
ALL_DEPARTMENTS = list(DEPT_KEY_BY_NAME.keys())


# ============================================================
# 关键词命中打分
# ============================================================

def _compile_keywords(keywords: List[str]) -> re.Pattern:
    """把关键词列表编译为大小写不敏感的正则。"""
    escaped = [re.escape(kw) for kw in keywords]
    return re.compile("|".join(escaped), re.IGNORECASE)


# 预编译每个部门的匹配模式
_DEPT_PATTERNS = {
    dept: _compile_keywords(rule["keywords"])
    for dept, rule in DEPT_RULES.items()
}


def _count_hits(text: str, dept: str) -> int:
    """统计文本命中某部门关键词的次数。"""
    if not text:
        return 0
    return len(_DEPT_PATTERNS[dept].findall(text))


def route_by_content(text: str, threshold: int = 1) -> List[str]:
    """按工作内容关键词匹配，返回应触发的部门清单。

    Args:
        text: 工作内容文本（Issue 标题+正文 / PR 描述 / 改动说明）。
        threshold: 命中次数达到该值即触发（默认 1）。

    Returns:
        命中的部门中文名列表。
    """
    if not text:
        return []
    hits: Dict[str, int] = {}
    for dept in ALL_DEPARTMENTS:
        n = _count_hits(text, dept)
        if n >= threshold:
            hits[dept] = n
    # 按命中次数降序，越相关越靠前
    return [d for d, _ in sorted(hits.items(), key=lambda kv: -kv[1])]


def route_by_deps(deps_unlocked: List[str]) -> List[str]:
    """按依赖解锁结果，返回应解锁的下游部门。

    Args:
        deps_unlocked: 已解锁的下游工作包 id 列表（wp_xxx）。

    Returns:
        应触发的部门中文名列表。
    """
    if not deps_unlocked:
        return []
    active: List[str] = []
    for dept, rule in DEPT_RULES.items():
        # 工作包 id 以部门模块名开头（如 wp_engine / wp_art_testing）
        for module in rule["modules"]:
            for wp in deps_unlocked:
                if wp == module or wp.startswith(f"wp_{module}"):
                    if dept not in active:
                        active.append(dept)
                    break
    return active


# ============================================================
# 综合路由决策
# ============================================================

def route(
    issue_title: str = "",
    issue_body: str = "",
    pr_description: str = "",
    changed_files: Optional[List[str]] = None,
    deps_unlocked: Optional[List[str]] = None,
    manually_requested: Optional[List[str]] = None,
    threshold: int = 1,
) -> Dict[str, Any]:
    """综合路由决策：输出本轮应触发的部门清单。

    决策优先级（高→低）:
      1. manually_requested：人类/上游明确点名某部门 → 必触发；
      2. route_by_content：工作内容命中部门关键词 → 触发；
      3. route_by_deps：上游验收解锁下游工作包 → 触发下游部门。

    结果:
      {
        "active_departments": [...],   # 本轮应触发的部门（有序）
        "inactive_departments": [...], # 本轮应跳过的部门
        "matched": {...},              # 各命中来源明细
        "all_departments": [...],
      }
    """
    # 汇总内容文本（标题+正文+PR描述+变更文件路径）
    parts = [issue_title or "", issue_body or "", pr_description or ""]
    if changed_files:
        parts.append(" ".join(changed_files))
    content = " ".join([p for p in parts if p])

    matched_content = route_by_content(content, threshold=threshold)
    matched_deps = route_by_deps(deps_unlocked or [])

    # 明确点名（最高优先级）
    requested = set(manually_requested or [])

    # 合并命中部门（保持部门流水线顺序）
    active: List[str] = []
    for dept in ALL_DEPARTMENTS:  # 按固定部门顺序，保证输出稳定
        if dept in requested or dept in matched_content or dept in matched_deps:
            active.append(dept)

    inactive = [d for d in ALL_DEPARTMENTS if d not in active]

    return {
        "active_departments": active,
        "inactive_departments": inactive,
        "matched": {
            "content": matched_content,
            "deps": matched_deps,
            "requested": list(requested),
        },
        "all_departments": list(ALL_DEPARTMENTS),
    }


def is_department_active(route_result: Dict[str, Any], dept_name: str) -> bool:
    """判断某部门是否被路由命中（供流水线 stage if 条件调用）。"""
    if not route_result:
        return False
    return dept_name in route_result.get("active_departments", [])


def serialize_active(route_result: Dict[str, Any]) -> str:
    """把路由结果序列化为单行文本（供写入路由清单文件 / 环境变量）。"""
    return " ".join(route_result.get("active_departments", []))


def active_to_marker_file(route_result: Dict[str, Any], path: str) -> str:
    """把路由命中的部门清单写入标记文件。

    供 .cnb.yml 部门 stage 的 if 条件读取：部门名在清单中才执行，
    未命中部门 stage 整体跳过（杜绝无工作凑热闹）。
    返回写入的清单字符串。
    """
    import os
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    content = serialize_active(route_result)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content + "\n")
    return content


# ============================================================
# 命令行演示（可直接 python routing.py 运行）
# ============================================================

def demo() -> None:
    print("== 部门派发路由决策演示 ==")
    print("六大部门:", ALL_DEPARTMENTS)
    print()

    # 场景1: 纯程序类 Issue（美术/测试不应凑热闹）
    r1 = route(
        issue_title="修复服务端接口并发 bug",
        issue_body="涉及 server 端接口逻辑与引擎适配，需要代码实现与性能优化。",
    )
    print("场景1(服务端bug) 触发:", r1["active_departments"],
          "| 跳过:", r1["inactive_departments"])
    assert "美术线" not in r1["active_departments"], "美术线不应被无关任务触发"

    # 场景2: 纯美术类 Issue（程序/测试不应凑热闹）
    r2 = route(
        issue_title="角色原画与 3D 建模规范",
        issue_body="制定角色资产美术风格，含原画、建模、贴图材质。",
    )
    print("场景2(美术) 触发:", r2["active_departments"],
          "| 跳过:", r2["inactive_departments"])
    assert "美术线" in r2["active_departments"]
    assert "程序线" not in r2["active_departments"], "程序线不应被美术任务触发"

    # 场景3: 上游解锁下游（依赖驱动）
    r3 = route(
        issue_body="策划线 gameplay 设计文档已验收，解锁下游实现。",
        deps_unlocked=["wp_gameplay", "wp_engine"],
    )
    print("场景3(依赖解锁) 触发:", r3["active_departments"])
    assert "策划线" in r3["active_departments"]
    assert "程序线" in r3["active_departments"]

    # 场景4: 明确点名（最高优先级）
    r4 = route(
        issue_body="机制改动，未命中明显部门关键词",
        manually_requested=["美术线"],
    )
    print("场景4(点名美术) 触发:", r4["active_departments"])
    assert "美术线" in r4["active_departments"]

    # 场景5: 完全无关 → 不触发任何部门（杜绝凑热闹）
    r5 = route(issue_title="环境配置说明")
    print("场景5(无关) 触发:", r5["active_departments"],
          "| 跳过:", r5["inactive_departments"])
    assert r5["active_departments"] == [], "无关任务不应触发任何部门"

    # is_department_active 校验
    assert is_department_active(r1, "程序线") is True
    assert is_department_active(r1, "美术线") is False
    assert is_department_active(r5, "策划线") is False

    print()
    print("🟢 部门派发路由决策演示通过")


if __name__ == "__main__":
    demo()

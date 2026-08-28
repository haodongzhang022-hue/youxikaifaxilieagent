# ============================================================
# 部门派发路由决策模块 (DepartmentRouting)
# 版本: v2.0
# 说明: 解决「无工作部门凑热闹」问题——每次编排不再无条件触发全部
#       六大部门，而是由一个**路由决策**环节，依据"显性声明"规则
#       精准判定本轮应触发哪些部门，只有被命中的部门才被派发/执行。
#
# v2.0 核心变更（修复关键词匹配误判）:
#   1. 引入「显性声明」语法：`%部门名`（如 `%测试线`）才是有效的
#      触发标记。正文中普通提及部门名（如"测试线验收中"标签）不再触发。
#   2. 移除普通关键词匹配（v1.0 的 DEPT_RULES 关键词匹配已废弃），
#      避免"提及"与"分配"混淆导致的误判。
#   3. `manually_requested`（@部门名 点名）仍为最高优先级，必触发。
#   4. 依赖解锁（deps_unlocked）仍然有效——上游验收解锁下游部门。
#   5. `route_from_env()` 不再拼接 labels 到匹配内容，
#      避免 CI 平台注入的状态标签（如"测试线验收中"）导致误判。
#
# 路由规则原则:
#   - 显性声明 (%部门名) / 明确点名 (@部门名)  → 必触发；
#   - 依赖解锁 (deps_unlocked)                → 解锁下游部门；
#   - 其他情况                                 → 不触发（缺省不派发）。
#
# 语言: Python 3 (可运行)
# 依赖: 无外部依赖（纯标准库）
# ============================================================
from __future__ import annotations

import re
import os
from typing import Any, Dict, List, Optional, Set

# 部门中文名 → 内部键（与 game_producer_agent / roles.yaml 对齐）
DEPT_KEY_BY_NAME = {
    "策划线": "design", "程序线": "program", "美术线": "art",
    "测试线": "qa", "项目管理": "pm", "运营线": "ops",
}

# 显性声明前缀（类似于 @ 的部门点名语法，用于区分"提及"与"分配"）
EXPLICIT_PREFIX = "%"

# 所有部门名（有序）
ALL_DEPARTMENTS = list(DEPT_KEY_BY_NAME.keys())

# ============================================================
# 显性声明匹配
# ============================================================

def _extract_explicit_depts(text: str) -> List[str]:
    """从文本中提取显性声明（%部门名）的部门清单。

    规则：`%测试线`、`%美术线` 等带 % 前缀的部门名
    才视为显性声明。正文中裸提及（如"测试线验收中"）不触发。
    """
    if not text:
        return []
    found: List[str] = []
    for dept in ALL_DEPARTMENTS:
        # 匹配 %部门名（允许有空格）
        pattern = re.compile(
            re.escape(EXPLICIT_PREFIX) + r'\s*' + re.escape(dept),
            re.IGNORECASE
        )
        if pattern.search(text):
            found.append(dept)
    return found


def _extract_manual_requested(text: str) -> List[str]:
    """从文本中提取 @部门名 点名的部门清单（最高优先级）。"""
    if not text:
        return []
    found: List[str] = []
    for dept in ALL_DEPARTMENTS:
        # 匹配 @部门名（允许空格）
        pattern = re.compile(
            r'@\s*' + re.escape(dept),
            re.IGNORECASE
        )
        if pattern.search(text):
            found.append(dept)
    return found


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
    include_content_match: bool = True,
) -> Dict[str, Any]:
    """综合路由决策：输出本轮应触发的部门清单。

    v2.0 决策规则:
      1. 显性声明（%部门名）：正文中出现 `%测试线` 等 → 触发该部门；
      2. 明确点名（@部门名 / manually_requested）：最高优先级 → 必触发；
      3. 依赖解锁（deps_unlocked）：上游验收解锁下游 → 触发下游部门。

    注意：
      - v1.0 的「普通关键词匹配」已废弃——裸提及部门名不触发。
      - `include_content_match` 保留为兼容参数（默认 True 但已不影响行为）。

    Returns:
      {
        "active_departments": [...],   # 本轮应触发的部门（有序）
        "inactive_departments": [...], # 本轮应跳过的部门
        "matched": {...},              # 各命中来源明细
        "all_departments": [...],
      }
    """
    # 汇总内容文本（标题+正文+PR描述）
    parts = [issue_title or "", issue_body or "", pr_description or ""]
    content = " ".join([p for p in parts if p])

    # 1. 显性声明匹配（%部门名）
    explicit_depts = _extract_explicit_depts(content)

    # 2. 明确点名（@部门名 或 manually_requested 参数）
    requested = set(manually_requested or [])
    requested |= set(_extract_manual_requested(content))

    # 3. 依赖解锁
    matched_deps = _route_by_deps(deps_unlocked or [])

    # 合并命中部门（保持部门流水线顺序）
    active: List[str] = []
    for dept in ALL_DEPARTMENTS:  # 按固定部门顺序，保证输出稳定
        if dept in requested or dept in explicit_depts or dept in matched_deps:
            active.append(dept)

    inactive = [d for d in ALL_DEPARTMENTS if d not in active]

    return {
        "active_departments": active,
        "inactive_departments": inactive,
        "matched": {
            "explicit": explicit_depts,
            "deps": matched_deps,
            "requested": list(requested),
        },
        "all_departments": list(ALL_DEPARTMENTS),
    }


def _route_by_deps(deps_unlocked: List[str]) -> List[str]:
    """按依赖解锁结果，返回应解锁的下游部门。

    Args:
        deps_unlocked: 已解锁的下游工作包 id 列表（wp_xxx）。

    Returns:
        应触发的部门中文名列表。
    """
    if not deps_unlocked:
        return []
    # 部门 → 工作包模块前缀
    DEPT_MODULES = {
        "策划线": ["gameplay", "numeric_model", "narrative", "combat", "level"],
        "程序线": ["client", "server", "engine", "ai_logic", "tools"],
        "美术线": ["art_direction", "ui_ux", "audio", "art"],
        "测试线": ["testing", "test", "qa"],
        "项目管理": ["release", "plan", "gate"],
        "运营线": ["data_ops", "ops"],
    }
    active: List[str] = []
    for dept, modules in DEPT_MODULES.items():
        for module in modules:
            for wp in deps_unlocked:
                if wp == module or wp.startswith(f"wp_{module}"):
                    if dept not in active:
                        active.append(dept)
                    break
    return active


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
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    content = serialize_active(route_result)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content + "\n")
    return content


# ============================================================
# CLI 入口：供 .cnb.yml 流水线 stage if 条件调用
# ============================================================

def route_from_env(threshold: int = 1) -> Dict[str, Any]:
    """从 CNB 流水线环境变量读取 Issue/PR 信息，执行路由决策。

    v2.0 变更：
      - 不再将 CNB_ISSUE_LABELS 拼入内容参与匹配（避免状态标签误判）。
      - 只读取标题/描述，按 %部门名 显性声明 / @部门名 点名 / 依赖解锁 触发。
    """
    event = os.getenv("CNB_EVENT", "")
    is_issue = "issue" in event
    is_pr = "pull_request" in event or "merge" in event

    if is_issue:
        title = os.getenv("CNB_ISSUE_TITLE", "")
        body = os.getenv("CNB_ISSUE_DESCRIPTION", "")
    elif is_pr:
        title = os.getenv("CNB_PULL_REQUEST_TITLE", "")
        body = os.getenv("CNB_PULL_REQUEST_DESCRIPTION", "")
    else:
        # 兜底：优先 Issue 变量，回退到 PR 变量
        title = os.getenv("CNB_ISSUE_TITLE", "") or os.getenv("CNB_PULL_REQUEST_TITLE", "")
        body = os.getenv("CNB_ISSUE_DESCRIPTION", "") or os.getenv("CNB_PULL_REQUEST_DESCRIPTION", "")

    # 从环境变量读取依赖解锁信息（可选）
    deps_str = os.getenv("CNB_DEPS_UNLOCKED", "")
    deps = [d.strip() for d in deps_str.split(",") if d.strip()] if deps_str else None

    return route(issue_title=title, issue_body=body, pr_description="", deps_unlocked=deps, threshold=threshold)


def cli_main() -> None:
    """命令行入口。用法：
      python routing.py route                 # 输出 active 部门清单（空格分隔）
      python routing.py check 策划线          # 检查某部门是否命中（退出码 0/1）
      python routing.py marker <path>         # 写路由结果到 marker 文件
      python routing.py demo                  # 运行演示（默认）
    """
    import sys
    args = sys.argv[1:]
    cmd = args[0] if args else "demo"

    if cmd == "demo":
        demo()
        return

    if cmd == "route":
        result = route_from_env()
        print(serialize_active(result))
        return

    if cmd == "check":
        if len(args) < 2:
            print("用法: python routing.py check <部门名>", file=sys.stderr)
            sys.exit(2)
        dept = args[1]
        result = route_from_env()
        active = is_department_active(result, dept)
        if active:
            sys.exit(0)
        else:
            sys.exit(1)

    if cmd == "marker":
        if len(args) < 2:
            print("用法: python routing.py marker <文件路径>", file=sys.stderr)
            sys.exit(2)
        result = route_from_env()
        content = active_to_marker_file(result, args[1])
        print(f"路由标记已写入 {args[1]}: {content}")
        return

    print(f"未知命令: {cmd}", file=sys.stderr)
    sys.exit(2)


# ============================================================
# 命令行演示（可直接 python routing.py 运行）
# ============================================================

def demo() -> None:
    print("== 部门派发路由决策演示 (v2.0 显性声明机制) ==")
    print("六大部门:", ALL_DEPARTMENTS)
    print()

    # 场景1: 显性声明 %测试线 → 触发
    r1 = route(issue_body="请 %测试线 完成回归验证")
    print("场景1(%测试线显性声明) 触发:", r1["active_departments"])
    assert "测试线" in r1["active_departments"]

    # 场景2: 裸提及部门名（如"测试线验收中"标签）→ 不触发
    r2 = route(issue_title="职责明确（测试线验收中 美术线验收中）")
    print("场景2(裸提及标签) 触发:", r2["active_departments"],
          "| 跳过:", r2["inactive_departments"])
    assert r2["active_departments"] == [], "裸提及部门名不应触发"

    # 场景3: 明确点名 @美术线 → 必触发
    r3 = route(issue_body="机制改动，@美术线 请协助", manually_requested=[])
    print("场景3(@美术线点名) 触发:", r3["active_departments"])
    assert "美术线" in r3["active_departments"]

    # 场景4: 依赖解锁 → 触发下游部门
    r4 = route(issue_body="上游验收通过", deps_unlocked=["wp_gameplay", "wp_engine"])
    print("场景4(依赖解锁) 触发:", r4["active_departments"])
    assert "策划线" in r4["active_departments"]
    assert "程序线" in r4["active_departments"]

    # 场景5: 完全无关 → 不触发任何部门
    r5 = route(issue_title="环境配置说明")
    print("场景5(无关) 触发:", r5["active_departments"],
          "| 跳过:", r5["inactive_departments"])
    assert r5["active_departments"] == [], "无关任务不应触发任何部门"

    # 场景6: %部门名 显式声明与普通提及共存 → 只触发显式的
    r6 = route(issue_body="美术线验收中 请 %测试线 完成回归，同时需要 @程序线 修复")
    print("场景6(混合) 触发:", r6["active_departments"])
    assert "测试线" in r6["active_departments"]
    assert "程序线" in r6["active_departments"]
    assert "美术线" not in r6["active_departments"], "裸提及美术线不应触发"

    # is_department_active 校验
    assert is_department_active(r1, "测试线") is True
    assert is_department_active(r2, "美术线") is False
    assert is_department_active(r5, "策划线") is False

    print()
    print("🟢 部门派发路由决策演示通过")


if __name__ == "__main__":
    cli_main()

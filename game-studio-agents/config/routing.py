# ============================================================
# 部门派发路由决策模块 (DepartmentRouting)
# 版本: v3.0
# 说明: 解决「无工作部门凑热闹」问题——每次编排不再无条件触发全部
#       六大部门，而是由一个**路由决策**环节，依据三层触发引擎
#       （显式声明最高优先 + 语义/关键词阈值下限 + 未命中不拉起）
#       精准判定本轮应触发哪些部门，只有被命中的部门才被派发/执行。
#
# 设计来源: 参考同组织 dongjiagoushi 项目「语义触发 + 阈值下限 + 显式声明最高优先」
#           的成熟方案（其 src/memory/triggers.py 三层触发引擎），在本仓库落地为
#           「部门路由三层触发」，理念一致：未命中=静默不拉起，杜绝无关凑热闹。
#
# 三层触发引擎（route / route_from_env 内置，供流水线 stage 调用）:
#   ① 显式声明（最高优先）:
#       识别 `%部门名` / `@部门名` / `[触发:部门名]` 硬匹配；
#       命中即触发，不受阈值约束；
#       缺标记不猜测接手部门（显式优先，缺声明视为无效、交由发送方补齐）。
#   ② 语义/关键词触发（带阈值下限）:
#       工作内容命中部门关键词，且命中次数 ≥ 阈值才触发；
#       低于阈值 → method=none + confidence=low，视为未命中、静默放行不拉起。
#   ③ 依赖解锁补充:
#       上游验收解锁下游工作包 → 触发下游部门（事件驱动级联）。
#   未命中任何规则 → 不触发（缺省不派发，杜绝无意义凑热闹）。
#
# 核心能力:
#   1. route():             三层触发引擎综合决策，输出 active/inactive 部门 + 命中明细
#   2. route_by_content():  语义/关键词匹配（带阈值下限）
#   3. route_by_deps():     依赖解锁匹配
#   4. route_from_env():    从 CNB 环境变量读取 Issue/PR 信息做决策
#   5. is_department_active(): 供流水线 stage if 判断本部门是否命中
#   6. active_to_marker_file(): 写路由清单到 marker 文件（stage 级 if 拦截依据）
#
# 语言: Python 3 (可运行)
# 依赖: 无外部依赖（纯标准库）
# ============================================================
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

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
# 语义/关键词触发阈值下限
# ============================================================
# 命中关键词次数达到该值才判定为"语义触发"。
# 默认 1 意为"命中 1 个强职责关键词即触发"；但由于本仓库关键词为"职责强绑定"，
# 为防"标签/状态文本中偶发一个泛词（如『验收』）就拉起测试线"，语义触发采用
# 相对置信下限（见 _semantic_hits），单一弱命中且无上下文支撑时判为未命中。
DEFAULT_SEMANTIC_THRESHOLD = 1

# 泛化弱词：出现即可能与"职责强关键词"混淆的通用业务词。
# 若文本仅命中弱词、未命中强职责关键词，视为语义置信不足、不触发（静默放行）。
# 这些词本身不足以成为"分配工作"的依据，只作为"提及"存在。
WEAK_GENERIC_WORDS = {
    "验收", "回归", "测试", "数据", "UI", "AI", "接口", "实现", "代码", "引擎",
    "版本", "排期", "计划",
}

# ============================================================
# 显式声明触发（最高优先）
# ============================================================
# 支持三种显式标记，硬匹配部门名后必触发，不受阈值约束：
#   %部门名   （如 %测试线）
#   @部门名   （如 @美术线）
#   [触发:部门名] / [触发部门:部门名] （dongjiagoushi 风格，最高优先显式声明）
_EXPLICIT_PATTERNS = {
    dept: re.compile(
        r"(?:%|@|\[触发:?|\[触发[^]]*:)\s*" + re.escape(dept) + r"(?![一-龥])"
    )
    for dept in ALL_DEPARTMENTS
}
# 兜底：部门名独立成词（不紧跟汉字）也算显式提及，但仅在"出现频率较高"时提升置信。
_DEPT_NAME_PATTERN = re.compile(
    r"(?<![\u4e00-\u9fff])(?:%|@)?([\u4e00-\u9fff]+线)(?![\u4e00-\u9fff])"
)


def _find_explicit_depts(text: str) -> List[str]:
    """识别文本中的显式声明部门（%部门 / @部门 / [触发:部门]）。

    返回命中的部门列表；未命中任何显式标记 → 返回 []（不猜测）。
    """
    if not text:
        return []
    found: List[str] = []
    for dept in ALL_DEPARTMENTS:
        if _EXPLICIT_PATTERNS[dept].search(text):
            if dept not in found:
                found.append(dept)
    return found


# ============================================================
# 关键词命中打分与语义置信
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


def _weak_word_count(text: str) -> int:
    """统计文本中泛化弱词出现的次数（用于压制误触发）。"""
    if not text:
        return 0
    return sum(text.count(w) for w in WEAK_GENERIC_WORDS)


def route_by_content(
    text: str,
    threshold: int = DEFAULT_SEMANTIC_THRESHOLD,
    require_strong: bool = True,
) -> List[str]:
    """语义/关键词触发（带阈值下限）。

    命中部门强职责关键词次数 ≥ threshold 才触发；仅命中泛化弱词、
    未命中强职责关键词 → 视为语义置信不足、method=none（静默不拉起）。

    **关键：剥离"裸部门名"后再做语义匹配**——"美术线验收中""测试线验收中"
    这类状态标签/进度文本中的"部门名裸提及"，不含真正的职责分配语境，
    不应触发对应部门（杜绝"美术/测试凑热闹"）。显式声明（%部门/@部门/
    [触发:部门]）由显式引擎单独处理，不受此剥离影响。

    Args:
        text: 工作内容文本（Issue 标题+正文 / PR 描述 / 改动说明）。
        threshold: 强职责关键词命中次数下限（默认 1）。
        require_strong: 是否要求至少命中一个"强职责关键词"（默认 True，
            用于压制"仅提及弱词"导致的误触发）。

    Returns:
        命中的部门中文名列表。
    """
    if not text:
        return []
    # 剥离"裸部门名"整体（如"美术线""测试线"），避免部门名内的职责词
    # （"美术""测试"）被误算作语义分配命中。显式标记（%/@/[触发:]）已由
    # _find_explicit_depts 单独识别，此处一并剥离，交由显式引擎负责。
    stripped = text
    for dept in ALL_DEPARTMENTS:
        # 先剥离显式标记+部门名，再剥离裸部门名
        stripped = re.sub(
            r"(?:%|@|\[触发:?|\[触发[^]]*:)\s*" + re.escape(dept), " ", stripped
        )
        stripped = re.sub(re.escape(dept), " ", stripped)

    hits: Dict[str, int] = {}
    for dept in ALL_DEPARTMENTS:
        n = _count_hits(stripped, dept)
        if n <= 0:
            continue
        strong_n = n
        if require_strong:
            # 估算非弱强词命中数
            kw_hits = _DEPT_PATTERNS[dept].findall(stripped)
            strong_count = 0
            for kw in kw_hits:
                kw_lower = kw.lower()
                is_weak = any(
                    w.lower() == kw_lower or w.lower() in kw_lower
                    for w in WEAK_GENERIC_WORDS
                )
                if not is_weak:
                    strong_count += 1
            strong_n = strong_count
        if strong_n >= threshold:
            hits[dept] = strong_n
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
# 三层触发引擎 · 综合路由决策
# ============================================================

def route(
    issue_title: str = "",
    issue_body: str = "",
    pr_description: str = "",
    changed_files: Optional[List[str]] = None,
    deps_unlocked: Optional[List[str]] = None,
    manually_requested: Optional[List[str]] = None,
    threshold: int = DEFAULT_SEMANTIC_THRESHOLD,
) -> Dict[str, Any]:
    """三层触发引擎综合路由决策：输出本轮应触发的部门清单。

    决策优先级（高→低）:
      ① 显式声明（最高优先）:
         文本中出现 `%部门名` / `@部门名` / `[触发:部门名]` → 必触发；
         缺标记不猜测接手部门（若需明确派发，请发送方用显式标记点名）。
      ② 语义/关键词触发（带阈值下限）:
         工作内容命中部门强职责关键词且 ≥ threshold → 触发；
         低于阈值 → method=none + confidence=low，静默不拉起。
      ③ 依赖解锁（事件驱动级联）:
         上游验收解锁下游工作包 → 触发下游部门。
      ④ manually_requested（程序/上游点名）:
         显式传入的点名部门清单 → 必触发（与显式声明同级最高优先）。

    结果:
      {
        "active_departments": [...],   # 本轮应触发的部门（有序）
        "inactive_departments": [...], # 本轮应跳过的部门
        "matched": {...},              # 各命中来源明细（explicit/semantic/deps/requested）
        "confidence": {...},           # 各部门命中方式与置信度
        "all_departments": [...],
      }
    """
    # 汇总内容文本（标题+正文+PR描述+变更文件路径）
    parts = [issue_title or "", issue_body or "", pr_description or ""]
    if changed_files:
        parts.append(" ".join(changed_files))
    content = " ".join([p for p in parts if p])

    # ① 显式声明（最高优先）
    explicit = _find_explicit_depts(content)

    # ② 语义/关键词触发（带阈值下限）
    semantic = route_by_content(content, threshold=threshold)

    # ③ 依赖解锁
    matched_deps = route_by_deps(deps_unlocked or [])

    # ④ 程序/上游点名（与显式声明同级最高优先）
    requested = set(manually_requested or [])

    # 合并命中部门（保持部门流水线顺序）
    active: List[str] = []
    confidence: Dict[str, Dict[str, Any]] = {}
    for dept in ALL_DEPARTMENTS:  # 按固定部门顺序，保证输出稳定
        reasons = []
        if dept in requested:
            reasons.append("requested")
        if dept in explicit:
            reasons.append("explicit")
        if dept in semantic:
            reasons.append("semantic")
        if dept in matched_deps:
            reasons.append("deps")
        if reasons:
            active.append(dept)
            confidence[dept] = {
                "method": reasons[0],
                "reasons": reasons,
                # 显式/点名=高置信，语义=中置信（低于阈值的语义根本不进 active）
                "confidence": (
                    "high" if ("explicit" in reasons or "requested" in reasons) else "medium"
                ),
            }

    inactive = [d for d in ALL_DEPARTMENTS if d not in active]

    return {
        "active_departments": active,
        "inactive_departments": inactive,
        "matched": {
            "explicit": explicit,
            "content": semantic,
            "deps": matched_deps,
            "requested": list(requested),
        },
        "confidence": confidence,
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
    print("== 部门派发路由决策 · 三层触发引擎演示 ==")
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
    assert "测试线" not in r1["active_departments"], "测试线不应被无关任务触发"

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

    # 场景4: 显式声明 %部门名（最高优先，即使内容无关也触发）
    r4 = route(
        issue_body="机制改动，未命中明显部门关键词，但请 %测试线 完成回归。",
    )
    print("场景4(%显式声明) 触发:", r4["active_departments"],
          "| 命中方式:", {d: r4["confidence"][d]["method"] for d in r4["active_departments"]})
    assert "测试线" in r4["active_departments"], "显式声明应触发测试线"
    assert r4["confidence"]["测试线"]["confidence"] == "high", "显式声明应为高置信"

    # 场景4b: 裸提及（无显式标记）不触发——消灭"测试线验收中"标签误判
    r4b = route(
        issue_body="测试线验收中、美术线验收中（这是状态标签文本，不是分配工作）。",
    )
    print("场景4b(裸提及标签) 触发:", r4b["active_departments"],
          "| 跳过:", r4b["inactive_departments"])
    # "验收/测试/回归"为弱词，且无显式声明、无强职责关键词分配语境 → 应不触发测试线
    # （"测试线"是部门名裸提及，不含强职责关键词如 case/自动化，视为提及非分配）

    # 场景5: 完全无关 → 不触发任何部门（杜绝凑热闹）
    r5 = route(issue_title="今天天气不错，吃饭了吗")
    print("场景5(无关) 触发:", r5["active_departments"],
          "| 跳过:", r5["inactive_departments"])
    assert r5["active_departments"] == [], "无关任务不应触发任何部门"

    # 场景6: [触发:部门名] 显式声明（dongjiagoushi 风格）
    r6 = route(issue_body="[触发:美术线] 请给出 UI 视觉规范。")
    print("场景6([触发:部门]) 触发:", r6["active_departments"])
    assert "美术线" in r6["active_departments"], "[触发:美术线] 应触发美术线"

    # 场景7: @部门名 显式声明
    r7 = route(issue_body="@运营线 请分析本次上线数据。")
    print("场景7(@部门) 触发:", r7["active_departments"])
    assert "运营线" in r7["active_departments"], "@运营线 应触发运营线"

    # is_department_active 校验
    assert is_department_active(r1, "程序线") is True
    assert is_department_active(r1, "美术线") is False
    assert is_department_active(r5, "策划线") is False

    print()
    print("🟢 部门派发路由决策 · 三层触发引擎演示通过")


# ============================================================
# CLI 入口：供 .cnb.yml 流水线 stage if 条件调用
# ============================================================

def route_from_env(threshold: int = DEFAULT_SEMANTIC_THRESHOLD) -> Dict[str, Any]:
    """从 CNB 流水线环境变量读取 Issue/PR 信息，执行三层触发路由决策。

    自动按触发事件区分数据源：
      - CNB_EVENT 含 "issue" → 只读 CNB_ISSUE_TITLE / CNB_ISSUE_DESCRIPTION
      - CNB_EVENT 含 "pull_request" → 只读 CNB_PULL_REQUEST_TITLE / CNB_PULL_REQUEST_DESCRIPTION
      - 其他情况 → 优先 Issue 变量，回退到 PR 变量

    注意：**不再拼接 CNB_ISSUE_LABELS 到匹配内容**——平台注入的状态标签
    （如"测试线验收中,美术线验收中"）会污染语义判定、导致无关部门被误拉起。
    标签只反映进度状态，不应作为"分配工作"的触发依据（问题5修复）。
    """
    import os
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


if __name__ == "__main__":
    cli_main()
